import json, unittest
from pathlib import Path
from unittest.mock import patch
from discovery.canonical import compute_result_hash
from discovery.ledger import read_ledger
from research_v3.controller import CIDS, HASHES, project_post_batch_state, validate_bootstrap
from research_v3.wave01_execute import AUTH_REF, V3ExecutionNotAuthorized, execute_authorized

ROOT=Path(__file__).resolve().parents[1]
def load(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class PerformanceResearchV3BootstrapTests(unittest.TestCase):
    def test_01_bootstrap_is_restartable_and_unopened(self):
        r=validate_bootstrap(ROOT)
        self.assertEqual(r["candidate_ids"],list(CIDS))
        self.assertEqual(r["v2_attempts_used"],9)
        self.assertEqual(r["v2_search_budget_remaining"],75)
        self.assertFalse(r["economic_outcomes_opened"])

    def test_02_inventory_classifications_are_exact(self):
        inv=load("research_v3/UNOPENED_READINESS_V1.json")["classifications"]
        for cid in ("V2-C001","V2-C002","V2-C003","V2-C004","V2-C005"):
            self.assertEqual(inv[cid]["classification"],"DEFERRED_FOR_INDEPENDENT_REASON")
        for cid in ("V2-C007","V2-C009"):
            self.assertEqual(inv[cid]["classification"],"NEEDS_SMALL_TARGETED_CAPTURE")
        for cid in ("V2-C008","V2-C010","V2-C011"):
            self.assertEqual(inv[cid]["classification"],"BLOCKED_MATERIAL_EVIDENCE")
        for cid in CIDS:
            self.assertEqual(inv[cid]["classification"],"READY_NOW_WITH_EXISTING_EVIDENCE")

    def test_03_c013_c016_are_frozen_without_result(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        for cid in CIDS:
            rows=[x for x in ledger if x["candidate_id"]==cid]
            self.assertEqual([x["entry_type"] for x in rows],["CANDIDATE_FROZEN"])
            self.assertEqual(rows[0]["spec_hash"],HASHES[cid])

    def test_04_real_entry_path_fails_before_economics_without_matching_gate(self):
        auth=load(AUTH_REF)
        self.assertIn(auth["status"],{"PENDING_EXACT_HEAD_GREEN","AUTHORIZED_AFTER_EXACT_HEAD_GREEN"})
        with patch("research_v3.wave01_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
            with self.assertRaises(V3ExecutionNotAuthorized):
                execute_authorized(ROOT,us500_m15="missing",nas100_m15="missing",eurusd_m15="missing",us500_cost="missing",nas100_cost="missing",execution_head="x",execution_ci_run_id=0)
            economic.assert_not_called()

    def test_05_t2_fixture_result_hash_and_state_projection(self):
        results={}
        for cid in CIDS:
            x={"candidate_id":cid,"spec_hash":HASHES[cid],"stage":"A","status":"GROSS_EDGE_FAIL","implementation_validity":{"state":"VALID","reason":"fixture"},"metrics":{"event_count":1,"gross_pnl":-1.0,"coarse_net_pnl":-1.0,"gross_return":-0.001,"coarse_net_return":-0.001,"gross_per_event":-1.0,"net_per_event":-1.0,"cost_burden":0.0,"turnover":2000.0,"weekly_events":{"2026-W01":1},"active_weeks":1,"longest_inactive_gap":0,"weekday_distribution":{"MON":1},"session_distribution":{"FIXTURE":1},"hold_duration":{"min_minutes":15.0,"median_minutes":15.0,"mean_minutes":15.0,"max_minutes":15.0},"exposure":0.0,"drawdown":1.0,"symbol_contribution":{"FIXTURE":{"event_count":1,"gross_pnl_eur":-1.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":-1.0}},"direction_contribution":{"LONG":{"event_count":1,"gross_pnl_eur":-1.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":-1.0}},"subperiod_contribution":{"2026":{"event_count":1,"gross_pnl_eur":-1.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":-1.0}},"regime_contribution":{"state":"NOT_APPLICABLE","reason":"fixture"}},"eur200_feasibility":{"state":"NOT_EVALUATED","reason":"fixture"},"cost_confidence":{"state":"CONSERVATIVE_BOUND","reason":"fixture"},"data_completeness":{"state":"SUFFICIENT","reason":"fixture"},"provenance":{"data_evidence":{"identity":"fixture","binding":{"type":"DATASET_SHA256","sha256":"0"*64}},"cost_evidence":{"identity":"fixture","state":"CONSERVATIVE_BOUND","sha256":"1"*64},"evaluator":{"version":"fixture","sha256":"2"*64}}}
            x["result_hash"]=compute_result_hash(x); self.assertEqual(x["result_hash"],compute_result_hash(x)); results[cid]=x
        state=project_post_batch_state(load("CURRENT_STATE.json"),results)
        self.assertEqual(state["performance_research_v3"]["status"],"WAVE01_RESULTS_RECORDED")
        self.assertEqual(load("CURRENT_STATE.json")["v2_attempts_used"],9)

if __name__=="__main__": unittest.main(verbosity=2)
