import json
import unittest
from decimal import Decimal
from pathlib import Path
from competition.broker_universe_capture import (
    FEASIBLE,INFEASIBLE,UNRESOLVED,
    account_execution_semantics,classify_direction,directional_summary,entry_eligibility,
)
from competition.shared_eur200_replay import ReplayContractError,ReplayEvent,replay_shared_eur200

ROOT=Path(__file__).resolve().parents[1]

def ev(*args,**kwargs):
    kwargs.setdefault("direction_feasibility",FEASIBLE)
    return ReplayEvent(*args,**kwargs)

class CompetitionPerformanceResetV1Tests(unittest.TestCase):
    def test_authority_state(self):
        a=json.loads((ROOT/"COMPETITION_PERFORMANCE_AUTHORITY_V1.json").read_text())
        self.assertEqual(a["search_budget_at_reset"],{"v2_budget_total":84,"evaluated_economic_identities":2,"v2_attempts_used":2,"remaining":82})
        self.assertEqual(a["reset_effect"]["economic_outcomes_opened"],0)
        self.assertEqual(a["reset_effect"]["v2_attempts_consumed"],0)
        self.assertFalse(a["reset_effect"]["protected_evidence_opened"])
        self.assertEqual(a["competition_objective"]["hard21"],">=21 ACTUALLY EXECUTED entry trades in EVERY certified UTC ISO competition week")

    def test_universe_is_fail_closed(self):
        u=json.loads((ROOT/"data"/"BROKER_NATIVE_COMPETITION_UNIVERSE_V1.json").read_text())
        self.assertFalse(u["scope"]["full_account_universe_claimed"])
        self.assertIsNone(u["scope"]["exhaustive_current_accessible_symbol_count"])
        self.assertEqual(u["scope"]["confirmed_accessible_symbol_lower_bound"],47)

    def test_directional_margin_classification(self):
        self.assertEqual(classify_direction(10,True),FEASIBLE)
        self.assertEqual(classify_direction(201,True),INFEASIBLE)
        self.assertEqual(classify_direction(None,True),UNRESOLVED)
        self.assertEqual(classify_direction(10,False),INFEASIBLE)
        self.assertEqual(classify_direction(10,None),UNRESOLVED)
        self.assertEqual(directional_summary(FEASIBLE,FEASIBLE),"BOTH_FEASIBLE")
        self.assertEqual(directional_summary(FEASIBLE,INFEASIBLE),"BUY_ONLY")
        self.assertEqual(directional_summary(INFEASIBLE,FEASIBLE),"SELL_ONLY")
        self.assertEqual(directional_summary(INFEASIBLE,INFEASIBLE),"NEITHER_FEASIBLE")
        self.assertEqual(directional_summary(FEASIBLE,UNRESOLVED),"UNRESOLVED")

    def test_shortability_is_directional(self):
        self.assertEqual(entry_eligibility({"enabled":True},{"tradingMode":0,"enableShortSelling":False}),(True,False))
        self.assertEqual(entry_eligibility({"enabled":True},{"tradingMode":0,"enableShortSelling":True}),(True,True))
        self.assertEqual(entry_eligibility({"enabled":True},{"tradingMode":0}),(True,None))
        self.assertEqual(entry_eligibility({"enabled":True},{"tradingMode":3,"enableShortSelling":True}),(False,False))

    def test_account_semantics_are_normalized_without_guessing_stopout_level(self):
        s=account_execution_semantics({
            "accountType":0,"totalMarginCalculationType":2,"fairStopOut":False,
            "stopOutStrategy":1,"accessRights":0,"leverageInCents":3000,
            "isLimitedRisk":False,
        },"EUR",{"state":"CAPTURED","items":[{"marginCallType":61,"marginLevelThreshold":100.0}]})
        self.assertEqual(s["account_type"]["name"],"HEDGED")
        self.assertEqual(s["total_margin_calculation_type"]["name"],"NET")
        self.assertEqual(s["stop_out_strategy"]["name"],"MOST_LOSING_FIRST")
        self.assertEqual(s["deposit_currency"],"EUR")
        self.assertEqual(s["stop_out_margin_level_threshold"]["state"],"UNKNOWN_NOT_IDENTIFIED_BY_PROTOOA_TRADER_OR_MARGIN_CALL_LIST")

    def test_material_audit_correction_blocks_old_frontier(self):
        a=json.loads((ROOT/"COMPETITION_UNIVERSE_AUDIT_CORRECTION_V1.json").read_text())
        s=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertEqual(a["accounting"]["remaining"],82)
        self.assertEqual(a["accounting"]["correction_attempts_consumed"],0)
        self.assertEqual(a["accounting"]["correction_economic_outcomes_opened"],0)
        self.assertEqual(a["old_frontier"]["state"],"PRESERVED_HISTORICAL_PROSPECTIVE_ARTIFACT_SUSPENDED_BEFORE_OWN_OUTCOMES")
        self.assertFalse(a["old_frontier"]["execute_before_exhaustive_universe"])
        self.assertEqual(s["active_competition_frontier_authority"],"discovery/COMPETITION_FRONTIER_WAVE_01_V3.json")
        self.assertEqual(s["active_competition_universe_audit_correction"],"COMPETITION_UNIVERSE_AUDIT_CORRECTION_V1.json")
        self.assertFalse(s["competition_first_reset"]["first_frontier_execution_authorized"])
        self.assertTrue(s["competition_first_reset"]["exhaustive_account_native_universe_required_before_new_economics"])
        self.assertEqual(s["competition_first_reset"]["broker_native_universe_state"],"ACCEPTED_EXHAUSTIVE_CURRENT_ACCOUNT_NATIVE_DIRECTIONAL")
        self.assertEqual(s["competition_first_reset"]["successor_frontier_authority"],"discovery/COMPETITION_FRONTIER_WAVE_01_V3.json")

    def test_frontier_is_preserved_but_not_economically_opened(self):
        f=json.loads((ROOT/"discovery"/"COMPETITION_FRONTIER_WAVE_01_V1.json").read_text())
        self.assertEqual([x["broker_symbol"] for x in f["selected_traded_markets"]],["AUDJPY","SpotCrude","XAUUSD"])
        self.assertFalse(f["C013_C016"]["execute_in_wave_01"])
        self.assertEqual(f["economic_outcomes_opened"],0)

    def test_c013_c016_specs_unchanged_unopened(self):
        expected={"V2-C013":"cd91f3b0008fef672fd5722ed44db23046fb516ad174b60205a55cd0c54cfea1","V2-C014":"7bb7a21f40dd742357f4800f7762314724b73609c34c2de04b10329df2221e6d","V2-C015":"aa067cc4aa807731ec3a0caa9029b574eeae43e068e241790d994d55a1f8ff64","V2-C016":"fdd6286d1a8fdbbe53610af45c91e3f949bb75805b7cc7ab790b997c77458783"}
        for cid,h in expected.items():
            doc=json.loads((ROOT/"discovery"/"candidates"/f"{cid}.json").read_text())
            self.assertEqual(doc["spec_hash"],h)
            self.assertTrue(doc["provenance"]["frozen_before_own_economic_outcome"])
            self.assertFalse(any((ROOT/"m6"/"results").glob(f"{cid}*")))

    def test_shared_replay_margin_rejection_and_continuity(self):
        r=replay_shared_eur200([
            ev("2026-01-05T08:00:00Z","ENTRY","TEST-A","AUDJPY","p1",direction="LONG",volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=10000000,margin_eur=31.02,transaction_cost_eur=1,active_position_mtm_eur={}),
            ev("2026-01-05T09:00:00Z","ENTRY","TEST-B","XAUUSD","p2",direction="LONG",volume_cents=100,min_volume_cents=100,step_volume_cents=100,max_volume_cents=100000,margin_eur=191.31,active_position_mtm_eur={"p1":0}),
            ReplayEvent("2026-01-05T10:00:00Z","EXIT","TEST-A","AUDJPY","p1",realized_gross_pnl_eur=5,transaction_cost_eur=1,active_position_mtm_eur={}),
        ],account_type="HEDGED",total_margin_calculation_type="SUM")
        self.assertEqual((r.accepted_entries,r.rejected_entries),(1,1))
        self.assertEqual(r.entries_by_iso_week,{"2026-W02":1})
        self.assertEqual(r.terminal_equity_eur,Decimal("203"))
        self.assertEqual(r.decisions[1].reason,"REJECT_INSUFFICIENT_FREE_MARGIN")

    def test_shared_replay_same_timestamp_cross_symbol_concurrency(self):
        r=replay_shared_eur200([
            ev("2026-01-05T08:00:00Z","ENTRY","TEST-A","AUDJPY","p1",priority=10,direction="LONG",volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=10000000,margin_eur=31.02,active_position_mtm_eur={}),
            ev("2026-01-05T08:00:00Z","ENTRY","TEST-B","SpotCrude","p2",priority=20,direction="SHORT",volume_cents=100,min_volume_cents=100,step_volume_cents=100,max_volume_cents=500000,margin_eur=8.73,active_position_mtm_eur={}),
            ReplayEvent("2026-01-05T09:00:00Z","EXIT","TEST-A","AUDJPY","p1",realized_gross_pnl_eur=2,active_position_mtm_eur={"p1":0,"p2":0}),
            ReplayEvent("2026-01-05T09:00:00Z","EXIT","TEST-B","SpotCrude","p2",realized_gross_pnl_eur=3,active_position_mtm_eur={"p1":0,"p2":0}),
        ],account_type="HEDGED",total_margin_calculation_type="SUM")
        self.assertEqual((r.accepted_entries,r.rejected_entries),(2,0))
        self.assertEqual(r.entries_by_iso_week,{"2026-W02":2})
        self.assertEqual(r.terminal_equity_eur,Decimal("205"))

    def test_hedged_same_symbol_uses_real_margin_aggregation(self):
        r=replay_shared_eur200([
            ev("2026-01-05T08:00:00Z","ENTRY","A","AUDJPY","p1",priority=10,direction="LONG",volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=10000000,margin_eur=40,active_position_mtm_eur={}),
            ev("2026-01-05T08:00:00Z","ENTRY","B","AUDJPY","p2",priority=20,direction="SHORT",volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=10000000,margin_eur=30,active_position_mtm_eur={}),
            ReplayEvent("2026-01-05T09:00:00Z","EXIT","A","AUDJPY","p1",active_position_mtm_eur={"p1":0,"p2":0}),
            ReplayEvent("2026-01-05T09:00:00Z","EXIT","B","AUDJPY","p2",active_position_mtm_eur={"p1":0,"p2":0}),
        ],account_type="HEDGED",total_margin_calculation_type="MAX")
        self.assertEqual((r.accepted_entries,r.rejected_entries),(2,0))
        self.assertEqual(r.decisions[1].used_margin_eur_after,Decimal("40"))

    def test_netted_same_symbol_requires_allocator_netting(self):
        with self.assertRaisesRegex(ReplayContractError,"pre-netted"):
            replay_shared_eur200([
                ev("2026-01-05T08:00:00Z","ENTRY","A","AUDJPY","p1",direction="LONG",volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=10000000,margin_eur=40,active_position_mtm_eur={}),
                ev("2026-01-05T08:01:00Z","ENTRY","B","AUDJPY","p2",direction="SHORT",volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=10000000,margin_eur=30,active_position_mtm_eur={"p1":0}),
            ],account_type="NETTED",total_margin_calculation_type="NET")

    def test_directional_infeasibility_cannot_execute(self):
        r=replay_shared_eur200([
            ReplayEvent("2026-01-05T08:00:00Z","ENTRY","A","X","p1",direction="SHORT",direction_feasibility=INFEASIBLE,volume_cents=100,min_volume_cents=100,step_volume_cents=100,max_volume_cents=1000,margin_eur=1,active_position_mtm_eur={}),
        ],account_type="HEDGED",total_margin_calculation_type="SUM")
        self.assertEqual((r.accepted_entries,r.rejected_entries),(0,1))
        self.assertEqual(r.decisions[0].reason,"REJECT_DIRECTION_INFEASIBLE")

    def test_shared_replay_rejects_unknown_entry_direction(self):
        with self.assertRaisesRegex(ValueError,"direction"):
            replay_shared_eur200([
                ReplayEvent("2026-01-05T08:00:00Z","ENTRY","TEST-A","AUDJPY","p1",direction_feasibility=FEASIBLE,volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=10000000,margin_eur=31.02,active_position_mtm_eur={}),
            ],account_type="HEDGED",total_margin_calculation_type="SUM")

if __name__=="__main__":unittest.main()
