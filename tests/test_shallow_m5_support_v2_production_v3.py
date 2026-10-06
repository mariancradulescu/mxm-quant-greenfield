from __future__ import annotations

import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from research_core_v4 import shallow_m5_support_v2_production_v3 as p


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _chain(mr=None, ma=None):
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    result = json.loads((p.ROOT / p.PROVIDER_RESULT_REL).read_text(encoding="utf-8"))
    acceptance = json.loads((p.ROOT / p.PROVIDER_ACCEPTANCE_REL).read_text(encoding="utf-8"))
    if mr:
        mr(result)
    rp = root / "result.json"
    rp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    rs = _sha(rp)
    acceptance["successor_exact_head_validation_and_provider_preflight"]["provider_result_sha256"] = rs
    if ma:
        ma(acceptance)
    ap = root / "acceptance.json"
    ap.write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
    return td, rp, ap, rs, _sha(ap)


def _must_fail(rp, ap, rs, aps):
    with mock.patch.object(p, "PROVIDER_RESULT_SHA256", rs), mock.patch.object(p, "PROVIDER_ACCEPTANCE_SHA256", aps):
        with unittest.TestCase().assertRaisesRegex(PermissionError, "PREARM_PROVIDER_AUTHORITY_BINDING_FAILURE"):
            p.validate_provider_authority(rp, ap)


class V3GateTests(unittest.TestCase):
    def test_ARM_V3_ABSENT_FAILS(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(PermissionError, "PRODUCTION_ARM_V3_ABSENT"):
                p.validate_arm(Path(td) / "missing.json")

    def test_ARM_V2_CANNOT_AUTHORIZE_V3_WORKFLOW(self):
        w = (p.ROOT / p.WORKFLOW_REL).read_text(encoding="utf-8")
        self.assertIn("PRODUCTION_ARM_V3.json", w)
        self.assertNotIn("PRODUCTION_ARM_V2.json", w)
        self.assertIn("shallow_m5_support_v2_production_v3", w)

    def test_PROVIDER_RESULT_FILE_MISSING_FAILS(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(PermissionError):
                p.validate_provider_authority(Path(td) / "missing.json", p.ROOT / p.PROVIDER_ACCEPTANCE_REL)

    def test_PROVIDER_RESULT_HASH_MISMATCH_FAILS(self):
        td, rp, ap, _, _ = _chain()
        try:
            rp.write_text(rp.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(PermissionError):
                p.validate_provider_authority(rp, ap)
        finally:
            td.cleanup()

    def test_PROVIDER_ACCEPTANCE_FILE_MISSING_FAILS(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(PermissionError):
                p.validate_provider_authority(p.ROOT / p.PROVIDER_RESULT_REL, Path(td) / "missing.json")

    def test_PROVIDER_ACCEPTANCE_HASH_MISMATCH_FAILS(self):
        td, rp, ap, rs, aps = _chain()
        try:
            ap.write_text(ap.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with mock.patch.object(p, "PROVIDER_RESULT_SHA256", rs), mock.patch.object(p, "PROVIDER_ACCEPTANCE_SHA256", aps):
                with self.assertRaises(PermissionError):
                    p.validate_provider_authority(rp, ap)
        finally:
            td.cleanup()

    def test_VALID_EXACT_PROVIDER_CHAIN_PASSES(self):
        out = p.validate_provider_authority()
        self.assertEqual(out["result"]["run_id"], p.PROVIDER_RUN_ID)
        self.assertTrue(out["acceptance"]["cleanup_independent_reconciliation"]["cleanup_accepted"])

    def test_EXECUTION_PATH_EQUIVALENCE_TO_V2(self):
        proof = p.execution_path_equivalence_proof()
        self.assertEqual(proof["delegated_execution_runner_sha256"], p.V2_RUNNER_SHA256)
        self.assertTrue(all(proof["proof"].values()))
        src = inspect.getsource(p.run_segment)
        self.assertIn("return v2.run_segment", src)
        self.assertNotIn("_connect_and_auth", src)
        self.assertNotIn("ProtoOAGetTrendbarsReq", src)

    def test_ZERO_WORKFLOW_DISPATCH(self):
        self.assertNotIn("workflow_dispatch", (p.ROOT / p.WORKFLOW_REL).read_text(encoding="utf-8"))

    def test_ZERO_CTRADER_SECRET_INJECTION_IN_OFFLINE_VALIDATION(self):
        w = (p.ROOT / ".github/workflows/breadth-first-shallow-m5-support-v2-production-v3-offline-validation.yml").read_text(encoding="utf-8")
        self.assertNotIn("secrets.CTRADER_", w)
        self.assertNotIn("CTRADER_CLIENT_ID:", w)
        self.assertNotIn("CTRADER_CLIENT_SECRET:", w)
        self.assertNotIn("CTRADER_ACCESS_TOKEN:", w)

    def test_ZERO_ARM(self):
        self.assertFalse((p.ROOT / p.ARM_REL).exists())
        self.assertFalse((p.ROOT / "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V2.json").exists())
        self.assertFalse((p.ROOT / "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V1.json").exists())

    def test_ZERO_BROKER_CONTACT(self):
        w = (p.ROOT / ".github/workflows/breadth-first-shallow-m5-support-v2-production-v3-offline-validation.yml").read_text(encoding="utf-8")
        self.assertNotIn("run-segment", w)
        self.assertNotIn("shallow_m5_support_v2_provider_preflight", w)

    def test_EXACT_ARM_V3_SCHEMA_AND_BINDING_SET(self):
        b = p._expected_arm_bindings()
        self.assertEqual(p.ARM_SCHEMA, "mxm.v4.breadth-first-shallow-m5-support-v2.production-arm.v3")
        for key in (
            "PROVIDER_PREFLIGHT_RESULT_SHA256",
            "PROVIDER_PREFLIGHT_ACCEPTANCE_AUTHORITY_SHA256",
            "V3_GATE_RUNNER_SHA256",
            "V3_GATE_WORKFLOW_SHA256",
            "V3_GATE_ARCHITECTURE_FREEZE_SHA256",
        ):
            self.assertIn(key, b)

    def test_V2_HISTORICAL_FILES_IMMUTABLE_BY_V3(self):
        self.assertNotEqual(p.RUNNER_REL, p.v2.RUNNER_REL)
        self.assertNotEqual(p.WORKFLOW_REL, p.v2.WORKFLOW_REL)
        self.assertNotEqual(p.ARCH_FREEZE_REL, p.v2.ARCH_FREEZE_REL)


def _result_case(field, bad):
    def test(self):
        td, rp, ap, rs, aps = _chain(lambda x: x.__setitem__(field, bad))
        try:
            _must_fail(rp, ap, rs, aps)
        finally:
            td.cleanup()
    return test


for _name, _field, _bad in (
    ("test_PROVIDER_RESULT_WRONG_SCHEMA_FAILS", "schema", "wrong"),
    ("test_PROVIDER_RESULT_WRONG_STATUS_FAILS", "status", "wrong"),
    ("test_PROVIDER_RESULT_WRONG_RUN_ID_FAILS", "run_id", 1),
    ("test_PROVIDER_RESULT_WRONG_JOB_ID_FAILS", "job_id", 1),
    ("test_PROVIDER_RESULT_WRONG_TESTED_HEAD_FAILS", "exact_tested_head", "0" * 40),
    ("test_PROVIDER_RESULT_ASSET_REDOWNLOAD_HASH_MISMATCH_FAILS", "redownload_sha256", "0" * 64),
    ("test_PROVIDER_RESULT_CLEANUP_FAILURE_FAILS", "cleanup_release_status", "FAIL"),
    ("test_PROVIDER_RESULT_RESIDUAL_RESOURCE_NONZERO_FAILS", "residual_release_count", 1),
    ("test_PROVIDER_RESULT_CTRADER_SECRET_COUNT_NONZERO_FAILS", "ctrader_secret_injection_count", 1),
    ("test_PROVIDER_RESULT_BROKER_CONTACT_NONZERO_FAILS", "broker_contact_count", 1),
    ("test_PROVIDER_RESULT_HISTORY_COUNT_NONZERO_FAILS", "historical_request_count", 1),
    ("test_PROVIDER_RESULT_MARKET_DATA_NONZERO_FAILS", "market_data_row_count", 1),
    ("test_PROVIDER_RESULT_MANIFEST_ROUNDTRIP_FAILURE_FAILS", "manifest_roundtrip_status", "FAIL"),
    ("test_PROVIDER_RESULT_RECOVERY_SKIP_FAILURE_FAILS", "recovery_skip_status", "FAIL"),
    ("test_PROVIDER_RESULT_CONFLICT_FAIL_CLOSED_FAILURE_FAILS", "conflict_fail_closed_status", "FAIL"),
    ("test_PROVIDER_RESULT_BRANCH_DRIFT_GUARD_FAILURE_FAILS", "branch_drift_guard_status", "FAIL"),
):
    setattr(V3GateTests, _name, _result_case(_field, _bad))


def _acceptance_case(name, mutator):
    def test(self):
        td, rp, ap, rs, aps = _chain(ma=mutator)
        try:
            _must_fail(rp, ap, rs, aps)
        finally:
            td.cleanup()
    setattr(V3GateTests, name, test)


_acceptance_case("test_PROVIDER_ACCEPTANCE_WRONG_STATUS_FAILS", lambda x: x.__setitem__("status", "wrong"))
_acceptance_case(
    "test_PROVIDER_ACCEPTANCE_WRONG_RESULT_HASH_FAILS",
    lambda x: x["successor_exact_head_validation_and_provider_preflight"].__setitem__("provider_result_sha256", "0" * 64),
)
_acceptance_case(
    "test_PROVIDER_ACCEPTANCE_WRONG_RUN_ID_FAILS",
    lambda x: x["successor_exact_head_validation_and_provider_preflight"].__setitem__("run_id", 1),
)
_acceptance_case(
    "test_PROVIDER_ACCEPTANCE_WRONG_JOB_ID_FAILS",
    lambda x: x["successor_exact_head_validation_and_provider_preflight"].__setitem__("job_id", 1),
)
_acceptance_case(
    "test_PROVIDER_ACCEPTANCE_WRONG_TESTED_HEAD_FAILS",
    lambda x: x["successor_exact_head_validation_and_provider_preflight"].__setitem__("tested_head", "0" * 40),
)
_acceptance_case(
    "test_PROVIDER_ACCEPTANCE_CLEANUP_NOT_ACCEPTED_FAILS",
    lambda x: x["cleanup_independent_reconciliation"].__setitem__("cleanup_accepted", False),
)


if __name__ == "__main__":
    unittest.main()
