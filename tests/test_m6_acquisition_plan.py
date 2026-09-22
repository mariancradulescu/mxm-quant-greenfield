import hashlib
import json
import unittest
from pathlib import Path

from m6.acquisition import (
    AcquisitionPlanError,
    build_external_capture_request,
    build_plan,
    classify_historical_bytes,
    derive_auxiliary_evidence,
    validate_broker_universe_use,
    validate_legacy_v1_input,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]
REQ_PATH = ROOT / "data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V2.json"
PLAN_V1_PATH = ROOT / "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V1.json"
PLAN_PATH = ROOT / "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json"
STATUS_PATH = ROOT / "data/PRIMARY_WAVE_02_M6_PREPARATION_STATUS_V1.json"
CURRENT_STATE_PATH = ROOT / "CURRENT_STATE.json"
LEDGER_PATH = ROOT / "discovery/ledger.jsonl"
PROTECTED = "2026-09-17T12:02:58Z"
REQ_BLOB = "66281f5866d9fc59ebc008a6bb6a4507cb5ee87f"
V1_BLOB = "47a2fed5c6eb08e4ebb841ac57f2f007c6ed2209"
V1_PLAN_SHA = "69e59ffd14d2402f838a86519b22c2362e96c76470bb847a4754cf41b2517971"
PLAN_SHA = "da9e9a65f5c8b3e9a3edb0189de6d60bee2b5cc922d0a3ea99c1dc14ef5066fa"
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
        cls.plan_v1 = load(PLAN_V1_PATH)
        cls.plan = load(PLAN_PATH)

    def test_01_v1_preserved_and_v2_exact_deterministic_build(self):
        self.assertEqual(git_blob_sha(PLAN_V1_PATH), V1_BLOB)
        self.assertEqual(self.plan_v1["plan_sha256"], V1_PLAN_SHA)
        built = build_plan(
            self.req,
            protected_start_utc=PROTECTED,
            requirements_git_blob_sha=REQ_BLOB,
        )
        self.assertEqual(built, self.plan)
        result = validate_plan(self.plan, self.req, protected_start_utc=PROTECTED)
        self.assertEqual(result["plan_sha256"], PLAN_SHA)
        self.assertEqual(result["unique_raw_capture_count"], 11)
        self.assertEqual(result["candidate_binding_count"], 12)

    def test_02_exact_11_unique_primary_raw_market_capture_identities(self):
        tasks = self.plan["unique_raw_capture_tasks"]
        self.assertEqual(len(tasks), 11)
        self.assertEqual(len({t["raw_capture_id"] for t in tasks}), 11)
        self.assertTrue(all("candidate_id" not in t for t in tasks))
        self.assertTrue(all(t["actual_bytes_sha256"] is None for t in tasks))
        self.assertEqual(
            {(t["canonical_instrument"], t["resolution"]) for t in tasks},
            {
                ("US500", "M15"), ("XAUUSD", "H4"), ("WTIUSD", "H1"),
                ("BTCUSD", "H1"), ("AUDJPY", "D1"), ("AAPL", "D1"),
                ("MSFT", "D1"), ("NVDA", "D1"), ("AMZN", "D1"),
                ("META", "D1"), ("NAS100", "M15"),
            },
        )

    def test_03_exact_12_candidate_bindings_and_frozen_distribution(self):
        bindings = self.plan["candidate_dataset_bindings"]
        self.assertEqual(len(bindings), 12)
        counts = {cid: sum(b["candidate_id"] == cid for b in bindings) for cid in ACTIVE_IDS}
        self.assertEqual(counts, {
            "V2-C006": 1, "V2-C007": 1, "V2-C008": 1, "V2-C009": 1,
            "V2-C010": 1, "V2-C011": 5, "V2-C012": 2,
        })
        for binding in bindings:
            self.assertEqual(
                binding["spec_hash"],
                self.req["candidate_spec_hashes"][binding["candidate_id"]],
            )

    def test_04_c006_c012_share_us500_raw_identity_but_not_semantics(self):
        bindings = self.plan["candidate_dataset_bindings"]
        c006 = next(b for b in bindings if b["candidate_id"] == "V2-C006")
        c012 = next(
            b for b in bindings
            if b["candidate_id"] == "V2-C012" and b["canonical_instrument"] == "US500"
        )
        self.assertEqual(c006["raw_capture_id"], c012["raw_capture_id"])
        self.assertEqual(c006["raw_identity_sha256"], c012["raw_identity_sha256"])
        self.assertNotEqual(c006["binding_id"], c012["binding_id"])
        self.assertNotEqual(
            c006["semantic_requirements_sha256"],
            c012["semantic_requirements_sha256"],
        )

    def test_05_no_raw_capture_duplication_from_candidate_reuse_and_no_over_dedupe(self):
        tasks = self.plan["unique_raw_capture_tasks"]
        self.assertEqual(
            sum(t["canonical_instrument"] == "US500" and t["resolution"] == "M15" for t in tasks),
            1,
        )
        defaults = self.plan["raw_capture_defaults"]
        self.assertEqual(defaults["source_environment"], "Pepperstone - Europe LIVE")
        self.assertEqual(defaults["timezone"], "UTC")
        self.assertTrue(
            self.plan["raw_capture_identity_contract"][
                "must_remain_distinct_when_any_identity_component_differs"
            ]
        )
        self.assertTrue(
            self.plan["acquisition_contract"]["auxiliary_evidence_is_separate_from_raw_ohlc_identity"]
        )

    def test_06_candidate_auxiliary_semantics_stay_frozen_and_separate(self):
        c006 = derive_auxiliary_evidence(self.req, "V2-C006")
        c012 = derive_auxiliary_evidence(self.req, "V2-C012")
        self.assertEqual(
            c006["session_semantics"],
            self.req["requirements"]["V2-C006"]["session_semantics"],
        )
        self.assertEqual(
            c012["synchronization"],
            self.req["requirements"]["V2-C012"]["synchronization"],
        )
        self.assertNotEqual(c006["synchronization"], c012["synchronization"])

    def test_07_external_request_is_read_only_candidate_scoped_and_raw_deduplicated(self):
        request = build_external_capture_request(
            self.plan,
            self.req,
            candidate_ids=["V2-C006", "V2-C012"],
        )
        self.assertEqual(request["permission"], "READ_ONLY_NO_ORDERS_NO_ACCOUNT_MUTATION")
        self.assertFalse(request["credentials_persisted"])
        self.assertFalse(request["economic_evaluation_requested"])
        self.assertEqual(len(request["candidate_dataset_bindings"]), 3)
        self.assertEqual(len(request["unique_raw_capture_tasks"]), 2)
        self.assertEqual(
            {t["canonical_instrument"] for t in request["unique_raw_capture_tasks"]},
            {"US500", "NAS100"},
        )

    def test_08_plan_hash_and_protected_boundary_fail_closed(self):
        broken = json.loads(json.dumps(self.plan))
        broken["unique_raw_capture_tasks"][0]["resolution"] = "H1"
        with self.assertRaises(AcquisitionPlanError):
            validate_plan(broken, self.req, protected_start_utc=PROTECTED)
        req = json.loads(json.dumps(self.req))
        req["requirements"]["V2-C006"]["interval"]["end_utc"] = PROTECTED
        with self.assertRaises(AcquisitionPlanError):
            build_plan(req, protected_start_utc=PROTECTED, requirements_git_blob_sha=REQ_BLOB)

    def test_09_legacy_strategy_economic_outputs_forbidden_inputs(self):
        for forbidden in (
            "V2_CANDIDATE_SELECTION", "MECHANISM_SELECTION", "SIGNAL_DEFINITION",
            "ENTRY_EXIT_LOGIC", "THRESHOLD", "LOOKBACK", "PARAMETER", "RANKING",
            "CANDIDATE_RESCUE", "ECONOMIC_CONCLUSION", "SURVIVOR_DECISION",
            "PORTFOLIO_SELECTION", "LEGACY_STRATEGY_CODE", "LEGACY_CANDIDATE_LOGIC",
            "LEGACY_ECONOMIC_RESULT", "LEGACY_PERFORMANCE_CONCLUSION", "LEGACY_ALLOCATOR",
        ):
            with self.assertRaises(AcquisitionPlanError):
                validate_legacy_v1_input(forbidden)
        named = self.plan["legacy_contamination_boundary"]["forbidden_named_reconstruction_or_import"]
        for token in ("PF01", "PF02", "BNY", "old signals", "old thresholds", "old economic outcomes"):
            self.assertIn(token, named)

    def test_10_legacy_broker_truth_and_raw_development_only_allowed_under_boundary(self):
        for allowed in (
            "INDEPENDENTLY_VERIFIED_BROKER_TRUTH",
            "COMPETITION_TRUTH",
            "VERIFIED_EXECUTION_SEMANTICS",
            "CONTAMINATION_PRIOR_ATTEMPT_ACCOUNTING",
        ):
            self.assertEqual(
                validate_legacy_v1_input(allowed)["state"],
                "ALLOWED_BOUNDARY_INPUT",
            )
        valid_sha = "a" * 64
        self.assertEqual(
            validate_legacy_v1_input(
                "RAW_DEVELOPMENT_MARKET_BYTES",
                provenance_sha256=valid_sha,
                historical_classification="DEVELOPMENT",
            )["state"],
            "ALLOWED_BOUNDARY_INPUT",
        )
        with self.assertRaises(AcquisitionPlanError):
            validate_legacy_v1_input(
                "RAW_DEVELOPMENT_MARKET_BYTES",
                provenance_sha256=valid_sha,
                historical_classification="PROTECTED_FORWARD",
            )

    def test_11_broker_universe_metadata_cannot_change_candidate_selection(self):
        for allowed in (
            "CANONICAL_SYMBOL_MAPPING", "ENABLED_STATUS", "EXECUTABLE_SYMBOL_IDENTITY",
            "VOLUME_MARGIN_EXECUTION_METADATA", "BROKER_STRUCTURAL_FEASIBILITY",
        ):
            self.assertEqual(
                validate_broker_universe_use(allowed)["state"],
                "ALLOWED_STRUCTURAL_METADATA_USE",
            )
        for forbidden in (
            "ECONOMIC_SEARCH_UNIVERSE", "WHOLE_UNIVERSE_BACKTEST",
            "PRIMARY_WAVE_02_RESELECTION", "CANDIDATE_RANKING",
        ):
            with self.assertRaises(AcquisitionPlanError):
                validate_broker_universe_use(forbidden)
        self.assertTrue(
            self.plan["broker_universe_rule"]["broker_universe_may_not_change_primary_wave_02_selection"]
        )

    def test_12_reacquired_pre_protected_history_remains_development(self):
        self.assertEqual(
            classify_historical_bytes(
                data_end_utc="2026-09-16T23:59:59Z",
                protected_start_utc=PROTECTED,
                acquisition_utc="2026-09-17T21:31:00+03:00",
            ),
            "DEVELOPMENT",
        )
        self.assertEqual(
            self.plan["data_classification_rule"]["basis"],
            "HISTORICAL_TIMESTAMP_NOT_DOWNLOAD_DATE",
        )
        self.assertTrue(
            self.plan["data_classification_rule"][
                "fresh_reacquisition_does_not_create_untouched_or_oos_evidence"
            ]
        )
        self.assertEqual(self.plan["protected_forward_start"], PROTECTED)

    def test_13_historical_live_parity_and_final_architecture_preserved(self):
        parity = self.plan["historical_live_parity"]
        self.assertTrue(parity["information_at_t_only"])
        self.assertTrue(parity["future_bars_forbidden"])
        self.assertTrue(parity["future_normalization_forbidden"])
        self.assertTrue(parity["hindsight_forbidden"])
        self.assertTrue(parity["retrospective_fills_forbidden"])
        self.assertEqual(parity["final_architecture"], [
            "SHARED_DETERMINISTIC_ECONOMIC_CORE",
            "HISTORICAL_REPLAY_ADAPTER",
            "CTRADER_LIVE_ADAPTER",
        ])

    def test_14_frozen_acquisition_plan_stays_unchanged_after_actual_bytes_bind_central_manifest(self):
        manifest = load(ROOT / "data/DATA_MANIFEST.json")
        acceptance = load(ROOT / "data/PRIMARY_WAVE_02_CAPTURE_ACCEPTANCE_V1.json")
        self.assertEqual(
            manifest["status"],
            "PRIMARY_WAVE_02_RAW_COMPONENTS_MATERIALIZED_HASH_VERIFIED_AUXILIARY_GATES_PARTIAL",
        )
        self.assertEqual(
            manifest["primary_wave_02_materialization"]["acceptance_ref"],
            "data/PRIMARY_WAVE_02_CAPTURE_ACCEPTANCE_V1.json",
        )
        self.assertEqual(len(acceptance["raw_components"]), 11)
        self.assertFalse((ROOT / "data/materialized").exists())
        # The frozen pre-acquisition plan remains immutable. Actual byte hashes are bound
        # through DATA_MANIFEST + the capture-acceptance receipt, not back-written into it.
        self.assertTrue(
            all(t["actual_bytes_sha256"] is None for t in self.plan["unique_raw_capture_tasks"])
        )
        self.assertEqual(
            self.plan["status"],
            "FROZEN_PRE_ACQUISITION_CHECKPOINT",
        )

    def test_15_zero_economic_state_and_m6_pending(self):
        inv = self.plan["state_invariants"]
        self.assertEqual(inv["result_recorded_count"], 0)
        self.assertEqual(inv["v2_attempts_used"], 0)
        self.assertEqual(inv["v2_evaluated_identities"], 0)
        self.assertEqual(inv["economic_outcomes_opened"], 0)
        self.assertFalse(inv["protected_evidence_opened"])
        self.assertEqual(inv["m6_status"], "PENDING")
        self.assertIn(
            "legacy strategy/economic outputs",
            self.plan["current_execution_block"]["forbidden_substitutions"],
        )

    def test_16_checkpoint_binds_corrected_v2_and_preserves_pre_economic_state(self):
        status = load(STATUS_PATH)
        infra = status["acquisition_infrastructure_checkpoint"]
        self.assertEqual(infra["plan"], "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json")
        self.assertEqual(infra["plan_sha256"], PLAN_SHA)
        self.assertEqual(
            infra["staging_parent_head"],
            "26fbf399d7aa4b6fee0b7cad64fd6322e153e2c7",
        )
        self.assertEqual(infra["unique_raw_primary_market_capture_count"], 11)
        self.assertEqual(infra["candidate_dataset_binding_count"], 12)
        self.assertTrue(infra["c006_c012_shared_us500_m15_raw_identity"])
        self.assertTrue(infra["candidate_specific_semantics_preserved"])
        self.assertTrue(infra["legacy_contamination_boundary_explicit"])
        self.assertFalse(infra["legacy_economic_logic_or_results_imported"])
        self.assertFalse(infra["broker_universe_used_for_economic_candidate_selection"])
        self.assertEqual(infra["pre_protected_reacquired_history_classification"], "DEVELOPMENT")
        self.assertFalse(status["central_data_manifest_updated"])
        self.assertFalse(status["economic_attempt_consumed"])
        self.assertFalse(status["economic_outcome_opened"])
        self.assertFalse(status["protected_evidence_opened"])

    def test_17_authoritative_state_and_ledger_remain_pre_economic(self):
        current = load(CURRENT_STATE_PATH)
        auth = load(ROOT / "data/M6_STAGE_A_EXECUTION_AUTHORIZATION_V1.json")
        self.assertEqual(current["v2_protected_forward_start"], PROTECTED)
        self.assertEqual(auth["preconditions"]["v2_attempts_used"], 0)
        self.assertEqual(auth["preconditions"]["v2_evaluated_identities"], 0)
        self.assertEqual(auth["preconditions"]["economic_outcomes_opened"], 0)
        self.assertEqual(auth["preconditions"]["ledger_entries"], 20)
        self.assertFalse(current["protected_evidence_opened"])
        entries = [json.loads(line) for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(entries), 26)
        self.assertFalse(any(e.get("entry_type") == "RESULT_RECORDED" for e in entries[:20]))
if __name__ == "__main__":
    unittest.main(verbosity=2)
