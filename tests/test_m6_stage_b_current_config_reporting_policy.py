import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from m6.stage_b_evaluator import CapitalRealization
from m6.stage_b_current_config_reporting import summarize_current_config_realization

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class StageBCurrentConfigReportingPolicyTests(unittest.TestCase):
    def test_01_reporting_policy_is_frozen_before_outcome(self):
        p=load("data/M6_STAGE_B_CURRENT_CONFIG_REPORTING_POLICY_V1.json")
        self.assertEqual(p["status"],"FROZEN_PRE_OUTCOME_REPORTING_COMPLETENESS")
        self.assertEqual(p["current_config_outcomes_opened_at_freeze"],0)
        self.assertFalse(p["post_outcome_selection_or_tuning"])
        self.assertFalse(p["historical_margin_blocks_reporting_or_scenario"])
        self.assertFalse(p["protected_evidence_opened"])

    def test_02_reporting_is_summary_only_not_economic_core_change(self):
        e=load("evidence/M6_STAGE_B_CURRENT_CONFIG_REPORTING_COMPLETENESS_V1.json")
        self.assertEqual(e["status"],"PASS_PRE_OUTCOME_REPORTING_COMPLETENESS_ADDED_NO_ECONOMICS")
        self.assertFalse(e["resolution"]["economic_evaluator_changed"])
        self.assertFalse(e["resolution"]["authorization_v3_consumed"])
        self.assertEqual(e["resolution"]["current_config_outcomes_opened"],0)
        self.assertTrue(all(e["methodology_unchanged"].values()))

    def test_03_synthetic_reporting_retains_zero_periods_and_exact_occupancy(self):
        path=(
            {
                "event":"START",
                "equity_eur":200.0,
                "scenario":"STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
                "historical_margin_claim":False,
            },
            {
                "event":"TRADE_CLOSED",
                "entry_utc":"2022-01-03T10:00:00Z",
                "exit_utc":"2022-01-03T11:00:00Z",
                "direction":"LONG",
                "margin_side":"BUY",
                "required_margin_eur":33.38,
                "volume_cents":10,
                "net_pnl_eur":10.0,
                "equity_eur":210.0,
                "scenario":"STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
                "historical_margin_claim":False,
            },
            {
                "event":"TRADE_CLOSED",
                "entry_utc":"2022-02-01T10:00:00Z",
                "exit_utc":"2022-02-01T11:30:00Z",
                "direction":"SHORT",
                "margin_side":"SELL",
                "required_margin_eur":33.38,
                "volume_cents":10,
                "net_pnl_eur":-5.0,
                "equity_eur":205.0,
                "scenario":"STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
                "historical_margin_claim":False,
            },
        )
        r=CapitalRealization(
            candidate_id="V2-C006",
            starting_capital_eur=Decimal("200"),
            final_equity_eur=Decimal("205"),
            executed_trades=2,
            margin_blocked_trades=0,
            path=path,
        )
        x=summarize_current_config_realization(r)
        self.assertEqual(x["feasibility_status"],"SURVIVES_CURRENT_CONFIG_EUR200")
        self.assertEqual(x["weekly_final_equity_distribution"]["period_count"],246)
        self.assertEqual(x["monthly_final_equity_distribution"]["period_count"],57)
        self.assertEqual(x["capital_occupancy"]["occupied_minutes"],150.0)
        self.assertEqual(x["executed_trade_distribution"]["executed_trades"],2)
        self.assertEqual(x["margin_blockers"]["count"],0)
        self.assertFalse(x["historical_margin_claim"])

    def test_04_margin_block_status_is_explicit(self):
        path=(
            {
                "event":"START",
                "equity_eur":200.0,
                "scenario":"STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
                "historical_margin_claim":False,
            },
            {
                "event":"MARGIN_BLOCK",
                "entry_utc":"2022-01-03T10:00:00Z",
                "direction":"LONG_NAS100",
                "margin_side":"BUY",
                "required_margin_eur":129.04,
                "equity_eur":100.0,
                "scenario":"STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
                "historical_margin_claim":False,
            },
        )
        r=CapitalRealization(
            candidate_id="V2-C012",
            starting_capital_eur=Decimal("200"),
            final_equity_eur=Decimal("200"),
            executed_trades=0,
            margin_blocked_trades=1,
            path=path,
        )
        x=summarize_current_config_realization(r)
        self.assertEqual(x["feasibility_status"],"CURRENT_CONFIG_MARGIN_BLOCKED")
        self.assertEqual(x["margin_blockers"]["count"],1)
        self.assertFalse(x["continuous_capital"]["full_development_sequence_executed"])

    def test_05_live_state_records_two_persisted_current_config_outcomes(self):
        s=load("CURRENT_STATE.json")
        t=s["m6"]["stage_b_current_configuration"]
        self.assertFalse(t["execution_deferred_pending_v4_reporting_binding"])
        self.assertTrue(t["economics_run"])
        self.assertTrue(t["results_created"])
        self.assertEqual(t["stage_b_current_config_outcomes_opened"],2)
        self.assertEqual(s["economic_outcomes_opened"],4)
        self.assertFalse(s["protected_evidence_opened"])

if __name__=="__main__":
    unittest.main(verbosity=2)
