import json, unittest
from pathlib import Path
from unittest.mock import patch
from discovery.canonical import compute_result_hash
from discovery.ledger import read_ledger
from research_v3.controller import CIDS, HASHES, RESULT_REFS, project_post_batch_state, validate_bootstrap
from research_v3.wave01_execute import AUTH_REF, V3ExecutionNotAuthorized, execute_authorized

ROOT=Path(__file__).resolve().parents[1]
def load(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class PerformanceResearchV3BootstrapTests(unittest.TestCase):
    def test_01_control_plane_is_restartable_in_current_lifecycle(self):
        r=validate_bootstrap(ROOT)
        self.assertTrue(r["economic_outcomes_opened"])
        state=load("CURRENT_STATE.json")
        self.assertEqual(r["v2_attempts_used"],state["v2_attempts_used"])
        self.assertEqual(r["v2_search_budget_remaining"],state["v2_search_budget_remaining"])
        self.assertEqual(state["performance_research_v3"]["v2_attempts_used_after_wave01"],13)
        self.assertEqual(state["performance_research_v3"]["v2_search_budget_remaining_after_wave01"],71)
        self.assertEqual(r["result_statuses"],{"V2-C013":"COARSE_NET_FAIL","V2-C014":"GROSS_EDGE_FAIL","V2-C015":"COARSE_NET_FAIL","V2-C016":"COST_UNRESOLVED"})

    def test_02_inventory_classifications_remain_frozen(self):
        inv=load("research_v3/UNOPENED_READINESS_V1.json")["classifications"]
        for cid in ("V2-C001","V2-C002","V2-C003","V2-C004","V2-C005"):
            self.assertEqual(inv[cid]["classification"],"DEFERRED_FOR_INDEPENDENT_REASON")
        for cid in ("V2-C007","V2-C009"):
            self.assertEqual(inv[cid]["classification"],"NEEDS_SMALL_TARGETED_CAPTURE")
        for cid in ("V2-C008","V2-C010","V2-C011"):
            self.assertEqual(inv[cid]["classification"],"BLOCKED_MATERIAL_EVIDENCE")
        for cid in CIDS:
            self.assertEqual(inv[cid]["classification"],"READY_NOW_WITH_EXISTING_EVIDENCE")

    def test_03_each_wave01_identity_has_exactly_one_result_and_payload_matches(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        for cid in CIDS:
            rows=[x for x in ledger if x["candidate_id"]==cid]
            self.assertEqual([x["entry_type"] for x in rows],["CANDIDATE_FROZEN","RESULT_RECORDED"])
            self.assertEqual(rows[0]["spec_hash"],HASHES[cid])
            result=load(RESULT_REFS[cid])
            self.assertEqual(result["result_hash"],compute_result_hash(result))
            self.assertEqual(rows[1]["payload"]["result"],result)
            self.assertEqual(rows[1]["payload"]["result_hash"],result["result_hash"])

    def test_04_real_entry_path_fails_before_economics_without_matching_gate(self):
        auth=load(AUTH_REF)
        self.assertEqual(auth["status"],"AUTHORIZED_AFTER_EXACT_HEAD_GREEN")
        with patch("research_v3.wave01_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
            with self.assertRaises(V3ExecutionNotAuthorized):
                execute_authorized(ROOT,us500_m15="missing",nas100_m15="missing",eurusd_m15="missing",us500_cost="missing",nas100_cost="missing",execution_head="x",execution_ci_run_id=0)
            economic.assert_not_called()

    def test_05_post_batch_projection_is_idempotent_and_preserves_later_lifecycle(self):
        state=load("CURRENT_STATE.json")
        results={cid:load(RESULT_REFS[cid]) for cid in CIDS}
        projected=project_post_batch_state(state,results)

        # Current lifecycle state may legitimately be later than Wave01.
        for field in (
            "v2_attempts_used",
            "v2_search_budget_remaining",
            "v2_evaluated_identities",
            "global_attempts_seen",
            "economic_outcomes_opened",
            "discovery_ledger_entries",
            "discovery_result_recorded_entries",
            "phase",
            "next_action",
        ):
            self.assertEqual(projected[field],state[field])

        # The historical Wave01 snapshot itself remains exact and immutable.
        perf=projected["performance_research_v3"]
        self.assertEqual(perf["v2_attempts_used_after_wave01"],13)
        self.assertEqual(perf["v2_search_budget_remaining_after_wave01"],71)
        self.assertEqual(
            perf["wave01_result_statuses"],
            {"V2-C013":"COARSE_NET_FAIL","V2-C014":"GROSS_EDGE_FAIL","V2-C015":"COARSE_NET_FAIL","V2-C016":"COST_UNRESOLVED"},
        )
        self.assertEqual(
            perf["wave01_result_hashes"],
            {cid:results[cid]["result_hash"] for cid in CIDS},
        )

        # Regression guard: arbitrary future Wave03+ bookkeeping growth cannot
        # make a historical Wave01 projection overwrite current lifecycle state.
        future=json.loads(json.dumps(state))
        future["v2_attempts_used"] += 7
        future["v2_search_budget_remaining"] -= 7
        future["v2_evaluated_identities"] += 7
        future["global_attempts_seen"] += 7
        future["economic_outcomes_opened"] += 7
        future["discovery_ledger_entries"] += 14
        future["discovery_result_recorded_entries"] += 7
        future["phase"]="FUTURE_VALID_LIFECYCLE"
        future["next_action"]="FUTURE_ACTION"
        future_projected=project_post_batch_state(future,results)
        self.assertEqual(future_projected,future)

    def test_06_recovery_authority_records_zero_extra_attempts_and_c016_fail_closed(self):
        a=load("research_v3/WAVE_01_POST_OUTCOME_RECOVERY_V1.json")
        self.assertEqual(a["recovery_classification"],"POST_OUTCOME_PERSISTENCE_STALL")
        self.assertEqual(a["accounting"]["recovery_additional_attempts_consumed"],0)
        self.assertFalse(a["accounting"]["fresh_discovery_attempt_performed_during_recovery"])
        self.assertEqual(a["results"]["V2-C016"]["status"],"COST_UNRESOLVED")
        self.assertEqual(a["results"]["V2-C016"]["missing_required_cost_boundaries"],9)
        self.assertFalse(a["protected_evidence_opened"])
        self.assertFalse(a["live_orders"])
        self.assertFalse(a["competition_start"])

if __name__=="__main__": unittest.main(verbosity=2)
