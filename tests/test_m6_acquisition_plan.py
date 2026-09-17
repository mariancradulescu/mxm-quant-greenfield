import hashlib
import json
import unittest
from pathlib import Path

from m6.acquisition import (
    AcquisitionPlanError,
    build_external_capture_request,
    build_plan,
    derive_auxiliary_evidence,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]
REQ_PATH = ROOT / "data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V2.json"
PLAN_PATH = ROOT / "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V1.json"
STATUS_PATH = ROOT / "data/PRIMARY_WAVE_02_M6_PREPARATION_STATUS_V1.json"
PROTECTED = "2026-09-17T12:02:58Z"
REQ_BLOB = "66281f5866d9fc59ebc008a6bb6a4507cb5ee87f"
PLAN_SHA = "69e59ffd14d2402f838a86519b22c2362e96c76470bb847a4754cf41b2517971"
ACTIVE_IDS = [f"V2-C{i:03d}" for i in range(6, 13)]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_blob_sha(path):
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class M6AcquisitionPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req = load(REQ_PATH)
        cls.plan = load(PLAN_PATH)

    def test_01_frozen_plan_is_exact_deterministic_build(self):
        built = build_plan(self.req, protected_start_utc=PROTECTED, requirements_git_blob_sha=REQ_BLOB)
        self.assertEqual(built, self.plan)
        self.assertEqual(validate_plan(self.plan, self.req, protected_start_utc=PROTECTED)["plan_sha256"], PLAN_SHA)

    def test_02_exact_primary_task_count_and_distribution(self):
        tasks = self.plan["primary_dataset_tasks"]
        self.assertEqual(len(tasks), 12)
        counts = {cid: sum(t["candidate_id"] == cid for t in tasks) for cid in ACTIVE_IDS}
        self.assertEqual(counts, {
            "V2-C006": 1, "V2-C007": 1, "V2-C008": 1, "V2-C009": 1,
            "V2-C010": 1, "V2-C011": 5, "V2-C012": 2,
        })
        self.assertTrue(all(t["broker_symbol_state"] == "UNRESOLVED_PENDING_ONE_TO_ONE_ENABLED_MAPPING" for t in tasks))

    def test_03_auxiliary_evidence_is_derived_verbatim_not_reinvented(self):
        c010 = derive_auxiliary_evidence(self.req, "V2-C010")
        self.assertEqual(c010["session_semantics"], self.req["requirements"]["V2-C010"]["session_semantics"])
        self.assertEqual(c010["special_requirement"], self.req["requirements"]["V2-C010"]["special_requirement"])
        c011 = derive_auxiliary_evidence(self.req, "V2-C011")
        self.assertEqual(c011["short_side_requirements"], self.req["requirements"]["V2-C011"]["short_side_requirements"])
        c012 = derive_auxiliary_evidence(self.req, "V2-C012")
        self.assertEqual(c012["synchronization"], self.req["requirements"]["V2-C012"]["synchronization"])

    def test_04_external_request_is_read_only_and_candidate_scoped(self):
        request = build_external_capture_request(self.plan, self.req, candidate_ids=["V2-C011"])
        self.assertEqual(request["permission"], "READ_ONLY_NO_ORDERS_NO_ACCOUNT_MUTATION")
        self.assertFalse(request["credentials_persisted"])
        self.assertFalse(request["economic_evaluation_requested"])
        self.assertEqual(len(request["primary_dataset_tasks"]), 5)
        self.assertEqual(set(request["auxiliary_evidence"]), {"V2-C011"})

    def test_05_plan_hash_and_protected_boundary_fail_closed(self):
        broken = json.loads(json.dumps(self.plan))
        broken["primary_dataset_tasks"][0]["resolution"] = "H1"
        with self.assertRaises(AcquisitionPlanError):
            validate_plan(broken, self.req, protected_start_utc=PROTECTED)
        req = json.loads(json.dumps(self.req))
        req["requirements"]["V2-C006"]["interval"]["end_utc"] = PROTECTED
        with self.assertRaises(AcquisitionPlanError):
            build_plan(req, protected_start_utc=PROTECTED, requirements_git_blob_sha=REQ_BLOB)

    def test_06_plan_forbids_substitutions_and_preserves_zero_economics(self):
        block = self.plan["current_execution_block"]
        self.assertEqual(block["state"], "BLOCKED_EXTERNAL_BROKER_READ_ONLY_CAPTURE_REQUIRED")
        self.assertTrue(block["user_action_required"])
        self.assertIn("approximate margin estimates", block["forbidden_substitutions"])
        self.assertIn("current spread/swap snapshots as VERIFIED historical evidence", block["forbidden_substitutions"])
        inv = self.plan["state_invariants"]
        self.assertEqual(inv["result_recorded_count"], 0)
        self.assertEqual(inv["v2_attempts_used"], 0)
        self.assertEqual(inv["v2_evaluated_identities"], 0)
        self.assertEqual(inv["economic_outcomes_opened"], 0)
        self.assertFalse(inv["protected_evidence_opened"])
        self.assertEqual(inv["m6_status"], "PENDING")

    def test_07_no_actual_data_manifest_mutation_without_bytes(self):
        self.assertEqual(git_blob_sha(ROOT / "data/DATA_MANIFEST.json"), "491d5bc6d682538d9967a792cc8dbe81ed973b8d")
        self.assertFalse((ROOT / "data/materialized").exists())

    def test_08_checkpoint_binds_plan_and_preserves_pre_economic_state(self):
        status = load(STATUS_PATH)
        infra = status["acquisition_infrastructure_checkpoint"]
        self.assertEqual(infra["plan"], "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V1.json")
        self.assertEqual(infra["plan_sha256"], PLAN_SHA)
        self.assertEqual(infra["staging_parent_head"], "802608d4a231f1017b206f356dbccaf317a9c148")
        self.assertEqual(infra["state"], "BLOCKED_EXTERNAL_BROKER_READ_ONLY_CAPTURE_REQUIRED")
        self.assertTrue(infra["user_action_required_for_actual_capture"])
        p = status["pre_economic_integrity"]
        self.assertEqual(p["result_recorded_count"], 0)
        self.assertEqual(p["v2_attempts_used"], 0)
        self.assertEqual(p["v2_evaluated_identities"], 0)
        self.assertEqual(p["economic_outcomes_opened"], 0)
        self.assertFalse(p["protected_evidence_opened"])
        self.assertEqual(p["m6_status"], "PENDING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
