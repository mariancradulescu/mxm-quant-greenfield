import json
import tempfile
import unittest
from pathlib import Path

from m6.preopen_supplement import (
    PREOPEN_PACKAGE_FILES,
    build_preopen_pydroid_package,
    signal_blind_preopen_windows,
)

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class PreM6CostMethodologyResolutionTests(unittest.TestCase):
    def test_01_protocol_explicitly_permits_post_capture_candidate_independent_calibration(self):
        p=load("data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json")
        joined="\n".join(p["selection_process"])
        self.assertIn("before opening C006/C012 economic outcomes",joined)
        self.assertIn("define only a defensible adverse conservative bound",joined)
        self.assertEqual(p["pre_capture_numeric_rules"]["slippage_number"],"NONE_FROZEN")
        v2=load("evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V2.json")
        self.assertTrue(v2["protocol_interpretation_corrected"])
        self.assertEqual(v2["discovery_bound_method"]["state"],"CONSERVATIVE_BOUND")

    def test_02_candidate_economic_inputs_remain_forbidden(self):
        p=load("data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json")
        forbidden=set(p["forbidden_inputs"])
        for key in ("C006_SIGNALS","C012_SIGNALS","C006_RETURNS","C012_RETURNS","C006_PNL","C012_PNL","ANY_CANDIDATE_OUTCOME","PROTECTED_FORWARD_EVIDENCE"):
            self.assertIn(key,forbidden)
        v2=load("evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V2.json")
        self.assertFalse(any(v2["forbidden_inputs_used"].values()))

    def test_03_c006_discovery_bound_is_adverse_and_does_not_claim_exact_fill_truth(self):
        v2=load("evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V2.json")
        x=v2["products"]["US500"]
        self.assertEqual(x["state"],"CONSERVATIVE_BOUND")
        self.assertEqual(x["observed_adverse_support_points"]["round_trip_envelope"],13.3)
        self.assertEqual(x["readiness"],"READY_PRE_OUTCOME")
        self.assertFalse(v2["discovery_bound_method"]["exact_fill_truth_claimed"])
        self.assertEqual(v2["c006_exact_fill_requirement"],"NOT_REQUIRED_FOR_STAGE_A_DISCOVERY_WHEN_THE_FROZEN_ADVERSE_BOUND_IS_APPLIED")

    def test_04_c012_gap_is_acquisition_domain_insufficiency_before_irreducible(self):
        v2=load("evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V2.json")
        x=v2["products"]["NAS100"]
        self.assertIn("ACQUISITION_DOMAIN_INSUFFICIENCY",x["current_0930_causal_state"])
        self.assertFalse(x["irreducible_execution_unknown"])
        self.assertEqual(x["readiness"],"BLOCKED_PREOPEN_0930_SUPPLEMENT")

    def test_05_preopen_windows_are_signal_blind_exactly_one_predecessor_m15_and_protected_safe(self):
        plan=load("data/TIER1_PREOPEN_0930_SUPPLEMENT_PLAN_V1.json")
        self.assertEqual(plan["acquisition_domain"]["weekday_envelope_local"],["09:15:00.000","09:29:59.999"])
        self.assertTrue(plan["acquisition_domain"]["no_signal_conditioned_windows"])
        self.assertTrue(plan["acquisition_domain"]["no_return_conditioned_windows"])
        self.assertTrue(plan["acquisition_domain"]["no_candidate_pnl_conditioned_windows"])
        self.assertTrue(plan["development_interval"]["protected_boundary_excluded"])
        windows=signal_blind_preopen_windows()
        self.assertEqual(len(windows),1228)
        self.assertTrue(all(w.to_ms-w.from_ms==899999 for w in windows))
        protected=plan["development_interval"]["protected_forward_start"]
        self.assertLess(windows[-1].close_utc,protected)

    def test_06_preopen_runtime_is_read_only_fixed_symbols_resumable_and_no_economics(self):
        plan=load("data/TIER1_PREOPEN_0930_SUPPLEMENT_PLAN_V1.json")
        self.assertEqual(plan["targets"]["US500"]["symbol_id"],127)
        self.assertEqual(plan["targets"]["NAS100"]["symbol_id"],126)
        self.assertTrue(plan["economic_constraints"]["no_orders"])
        self.assertTrue(plan["economic_constraints"]["no_account_mutation"])
        self.assertTrue(plan["economic_constraints"]["no_candidate_outcome"])
        runtime=(ROOT/"m6/preopen_evidence_openapi.py").read_text(encoding="utf-8")
        launcher=(ROOT/"m6/pydroid_preopen_launcher.py").read_text(encoding="utf-8")
        self.assertIn("_capture_chunk",runtime)
        self.assertIn("ETA",runtime)
        self.assertIn("existing v3 chunks are read locally only",launcher.lower())
        self.assertNotIn("ProtoOANewOrderReq",runtime+launcher)

    def test_07_raw_commitments_are_not_misreported_as_external_raw_byte_recomputation(self):
        e=load("evidence/TIER1_RAW_COMMITMENT_VERIFICATION_CORRECTION_V1.json")
        self.assertTrue(e["raw_chunk_commitments_verified"])
        self.assertFalse(e["raw_bytes_transferred"])
        self.assertFalse(e["raw_bytes_independently_recomputed"])
        self.assertTrue(e["local_retention_required"])
        self.assertFalse(e["deletion_authorized"])

    def test_08_commission_uses_discovery_policy_coverage_not_daily_certification_claim(self):
        e=load("evidence/TIER1_DISCOVERY_COMMISSION_POLICY_COVERAGE_V1.json")
        self.assertEqual(e["status"],"VERIFIED_DISCOVERY_POLICY_COVERAGE")
        self.assertEqual(e["products"]["US500"]["separate_commission"],"0_FOR_DISCOVERY_POLICY")
        self.assertEqual(e["products"]["NAS100"]["separate_commission"],"0_FOR_DISCOVERY_POLICY")
        self.assertTrue(any("No claim" in x for x in e["limitations"]))

    def test_09_current_state_keeps_all_economics_and_protected_counters_zero(self):
        state = load("CURRENT_STATE.json")
        auth = load("data/M6_STAGE_A_EXECUTION_AUTHORIZATION_V1.json")
        ledger = [json.loads(x) for x in (ROOT / "discovery/ledger.jsonl").read_text().splitlines() if x.strip()]
        self.assertEqual(auth["preconditions"]["economic_outcomes_opened"], 0)
        self.assertEqual(auth["preconditions"]["v2_attempts_used"], 0)
        self.assertEqual(auth["preconditions"]["v2_evaluated_identities"], 0)
        self.assertFalse(state["protected_evidence_opened"])
        self.assertEqual(state["m6"]["status"], "PENDING")
        self.assertFalse(any(x["entry_type"] == "RESULT_RECORDED" for x in ledger[:20]))
    def test_10_v5_readiness_and_tier2_path_are_pre_outcome(self):
        r=load("data/PRIMARY_WAVE_02_PRE_M6_READINESS_V5.json")
        self.assertEqual(r["candidates"]["V2-C006"]["m6_stage_a_readiness"],"READY_PRE_OUTCOME")
        self.assertEqual(r["candidates"]["V2-C012"]["m6_stage_a_readiness"],"BLOCKED_PREOPEN_0930_SUPPLEMENT")
        self.assertFalse(r["global_m6_economics_authorized"])
        p=load("evidence/C007_C009_TIER2_COST_EVIDENCE_PATH_V1.json")
        self.assertFalse(p["economics_run"])

    def test_11_preopen_package_is_self_contained_and_deterministic(self):
        required={
            "M6_PREOPEN_SUPPLEMENT_RUN.py","m6/preopen_evidence_openapi.py",
            "m6/pydroid_preopen_launcher.py","data/TIER1_PREOPEN_0930_SUPPLEMENT_PLAN_V1.json",
            "data/TIER1_COST_EVIDENCE_CAPTURE_ACCEPTANCE_V1.json",
        }
        self.assertTrue(required.issubset(set(PREOPEN_PACKAGE_FILES)))
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"a.zip"; b=Path(td)/"b.zip"
            ha=build_preopen_pydroid_package(ROOT,a)
            hb=build_preopen_pydroid_package(ROOT,b)
            self.assertEqual(ha,hb)
            self.assertEqual(a.read_bytes(),b.read_bytes())

if __name__=="__main__":
    unittest.main(verbosity=2)
