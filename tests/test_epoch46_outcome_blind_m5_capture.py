import csv,inspect,json,tempfile,unittest
from pathlib import Path
from m6.ctrader_capture import CaptureContractError
from research_v3.epoch46_outcome_blind_m5_capture import EXPECTED_PLAN_SHA,validate_plan,verify_ohlc_csv
ROOT=Path(__file__).resolve().parents[1]
class Epoch46OutcomeBlindM5CaptureTests(unittest.TestCase):
    def _plan(self): return json.loads((ROOT/"data/EPOCH46_OUTCOME_BLIND_M5_ACQUISITION_WAVE_01_PLAN_V1.json").read_text())
    def test_frozen_wave_is_exact_outcome_blind_and_non_economic(self):
        p=self._plan(); self.assertTrue(validate_plan(p)); self.assertEqual(p["plan_sha256"],EXPECTED_PLAN_SHA); self.assertEqual(len(p["symbols"]),34); self.assertEqual(len({x["symbol_id"] for x in p["symbols"]}),34); self.assertEqual(len({x["peer_candidate_cohort_id"] for x in p["symbols"]}),34); self.assertTrue(all(x["history_state_at_freeze"]=="NO_ACCEPTED_M5_SCOPE_IN_EPOCH45_AUDIT" for x in p["symbols"])); self.assertFalse(p["selection_authority"]["outcomes_used"]); self.assertEqual(p["selection_authority"]["accepted_scope_identity_exclusion_count"],45); self.assertEqual(p["accounting_effect"],{"economic_outcomes_opened":0,"v2_attempts_consumed":0,"v2_search_budget_change":0}); self.assertLess(p["interval"]["end_utc"],p["temporal_design"]["prior_accepted_m5_scope_floor_utc"]); self.assertFalse(p["protected_evidence_opened"])
    def test_plan_mutation_fails_closed(self):
        p=self._plan(); p["symbols"][0]["broker_symbol"]="NETH25"
        with self.assertRaises(CaptureContractError): validate_plan(p)
    def test_collector_contains_no_trade_requests(self):
        import research_v3.epoch46_outcome_blind_m5_capture as mod
        src=inspect.getsource(mod)
        for forbidden in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"): self.assertNotIn(forbidden,src)
    def test_top_level_pydroid_entrypoint_has_real_newlines(self):
        raw=(ROOT/"EPOCH46_OUTCOME_BLIND_M5_CAPTURE_RUN.py").read_text(encoding="utf-8")
        self.assertNotIn("\\n",raw)
        compile(raw,"EPOCH46_OUTCOME_BLIND_M5_CAPTURE_RUN.py","exec")
    def test_ohlc_invariants_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.csv"
            with p.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=("time_utc","open","high","low","close","tick_volume")); w.writeheader(); w.writerow({"time_utc":"2026-01-01T00:00:00Z","open":"2","high":"1","low":"0","close":"0.5","tick_volume":"1"})
            with self.assertRaises(CaptureContractError): verify_ohlc_csv(p)
if __name__=="__main__": unittest.main()
