import json
import unittest
from decimal import Decimal
from pathlib import Path
from competition.broker_universe_capture import classify_margin
from competition.shared_eur200_replay import ReplayEvent,replay_shared_eur200

ROOT=Path(__file__).resolve().parents[1]

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
        s=u["persisted_enabled_subset_summary"]
        self.assertEqual((s["count"],s["eur200_min_volume_feasible"],s["eur200_min_volume_infeasible"],s["broker_or_margin_unresolved"]),(49,10,1,38))

    def test_margin_classification_three_states(self):
        self.assertEqual(classify_margin(10,11),"EUR200_MIN_VOLUME_FEASIBLE")
        self.assertEqual(classify_margin(201,10),"EUR200_MIN_VOLUME_INFEASIBLE")
        self.assertEqual(classify_margin(None,10),"BROKER_OR_MARGIN_UNRESOLVED")

    def test_frontier_is_not_index_anchored(self):
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
            ReplayEvent("2026-01-05T08:00:00Z","ENTRY","TEST-A","AUDJPY","p1",direction="LONG",volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=10000000,margin_eur=31.02,transaction_cost_eur=1,active_position_mtm_eur={}),
            ReplayEvent("2026-01-05T09:00:00Z","ENTRY","TEST-B","XAUUSD","p2",direction="LONG",volume_cents=100,min_volume_cents=100,step_volume_cents=100,max_volume_cents=100000,margin_eur=191.31,active_position_mtm_eur={"p1":0}),
            ReplayEvent("2026-01-05T10:00:00Z","EXIT","TEST-A","AUDJPY","p1",realized_gross_pnl_eur=5,transaction_cost_eur=1,active_position_mtm_eur={}),
        ])
        self.assertEqual((r.accepted_entries,r.rejected_entries),(1,1))
        self.assertEqual(r.entries_by_iso_week,{"2026-W02":1})
        self.assertEqual(r.terminal_equity_eur,Decimal("203"))
        self.assertEqual(r.decisions[1].reason,"REJECT_INSUFFICIENT_FREE_MARGIN")

if __name__=="__main__":unittest.main()
