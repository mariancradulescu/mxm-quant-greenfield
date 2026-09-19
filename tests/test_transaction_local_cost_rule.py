import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from m6.causal_conversion import CausalConversionSeries
from m6.stage_a_tier1_runner import (
    CANDIDATE_HASHES,
    StageAExecutionNotAuthorized,
    StageAInputPaths,
    _prepare_candidate,
    execute_stage_a_in_memory,
    verify_repository_authorities,
)
from m6.tier1_candidate_replay import ReplayIntent
from m6.transaction_local_cost import (
    C006_STRESS_DIAGNOSTIC,
    C012_KNOWN_UNSUPPORTED_BOUNDARIES_MS,
    C012_STRESS_DIAGNOSTIC,
    CostEvidenceUnavailable,
    TransactionCostEvidence,
    TransactionLocalCostIndex,
    from_c012_support_rows,
    from_original_boundary_rows,
)

ROOT=Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))


class TransactionLocalCostRuleTests(unittest.TestCase):
    def test_01_authority_freezes_formula_before_signals_pnl_or_outcomes(self):
        a=load("evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json")
        self.assertEqual(
            a["status"],
            "FROZEN_PRE_OUTCOME_TRANSACTION_LOCAL_PRIMARY_COST_WITH_STRESS_DIAGNOSTICS",
        )
        self.assertTrue(a["frozen_before_any_affected_candidate_economic_outcome"])
        self.assertEqual(
            a["primary_discovery_cost"]["formula"],
            "FULL_CAUSAL_SPREAD_AT_BOUNDARY + ABS_MID_DISPLACEMENT_TO_FIRST_BILATERAL_QUOTE_REFRESH",
        )
        self.assertFalse(any(a["primary_discovery_cost"]["calibration_inputs"].values()))
        self.assertEqual(a["research_state"]["economic_outcomes_opened"],0)
        self.assertEqual(a["research_state"]["v2_attempts_used"],0)
        self.assertEqual(a["research_state"]["result_recorded"],0)
        self.assertFalse(a["research_state"]["protected_evidence_opened"])

    def test_02_same_row_formula_never_combines_cross_row_maxima(self):
        rows=[
            {
                "session_date":"2024-01-02","boundary_timestamp_ms":"1000",
                "causal_bid":"100","causal_ask":"102","causal_spread":"2",
                "both_sides_refreshed_state_timestamp_ms":"1010",
                "both_sides_refreshed_bid":"103","both_sides_refreshed_ask":"105",
                "both_sides_refreshed_classification":"QUOTE_REFRESH_DIAGNOSTIC_ONLY",
                "causal_state_availability":"CAUSAL_TWO_SIDED_AVAILABLE",
            },
            {
                "session_date":"2024-01-02","boundary_timestamp_ms":"2000",
                "causal_bid":"200","causal_ask":"210","causal_spread":"10",
                "both_sides_refreshed_state_timestamp_ms":"2010",
                "both_sides_refreshed_bid":"200.1","both_sides_refreshed_ask":"210.1",
                "both_sides_refreshed_classification":"QUOTE_REFRESH_DIAGNOSTIC_ONLY",
                "causal_state_availability":"CAUSAL_TWO_SIDED_AVAILABLE",
            },
        ]
        idx=from_original_boundary_rows("US500",rows)
        self.assertEqual(idx.cost_points(1000),Decimal("5"))
        self.assertEqual(idx.cost_points(2000),Decimal("10.1"))
        self.assertNotEqual(idx.cost_points(1000),Decimal("13"))
        self.assertNotEqual(idx.cost_points(2000),Decimal("13"))

    def test_03_c006_exact_transaction_timestamps_select_exact_rows(self):
        entry=datetime(2024,1,2,14,45,tzinfo=timezone.utc)
        exit_=datetime(2024,1,2,17,45,tzinfo=timezone.utc)
        rows=[
            TransactionCostEvidence("US500","2024-01-02",int(entry.timestamp()*1000),Decimal("1"),Decimal("2"),Decimal("1"),1,Decimal("2"),Decimal("3"),Decimal("1"),Decimal("2"),"VALID_GENERIC_COST_SUPPORT"),
            TransactionCostEvidence("US500","2024-01-02",int(exit_.timestamp()*1000),Decimal("1"),Decimal("2"),Decimal("1"),2,Decimal("4"),Decimal("5"),Decimal("3"),Decimal("4"),"VALID_GENERIC_COST_SUPPORT"),
        ]
        idx=TransactionLocalCostIndex("US500",rows)
        intent=ReplayIntent("V2-C006",CANDIDATE_HASHES["V2-C006"],"LONG",entry,entry,5000.0,exit_,5010.0,{})
        eurusd=CausalConversionSeries.from_rows("EURUSD",[
            {"time_utc":"2024-01-02T14:15:00Z","close":"1.10"},
            {"time_utc":"2024-01-02T17:15:00Z","close":"1.11"},
        ])
        c=_prepare_candidate("V2-C006",[intent],cost_index=idx,eurusd=eurusd)
        self.assertEqual(c.cost_state,"CONSERVATIVE_BOUND")
        self.assertEqual(c.trades[0].entry_cost_evidence.boundary_timestamp_ms,int(entry.timestamp()*1000))
        self.assertEqual(c.trades[0].entry_cost_evidence.transaction_cost_proxy_points,Decimal("2"))
        self.assertEqual(c.trades[0].exit_cost_evidence.boundary_timestamp_ms,int(exit_.timestamp()*1000))
        self.assertEqual(c.trades[0].exit_cost_evidence.transaction_cost_proxy_points,Decimal("4"))

    def test_04_c012_exact_transaction_timestamps_select_exact_rows(self):
        entry=datetime(2024,1,2,15,0,tzinfo=timezone.utc)
        exit_=datetime(2024,1,2,16,0,tzinfo=timezone.utc)
        rows=[
            TransactionCostEvidence("NAS100","2024-01-02",int(entry.timestamp()*1000),Decimal("1"),Decimal("2"),Decimal("1"),1,Decimal("3"),Decimal("4"),Decimal("2"),Decimal("3"),"VALID_GENERIC_COST_SUPPORT"),
            TransactionCostEvidence("NAS100","2024-01-02",int(exit_.timestamp()*1000),Decimal("1"),Decimal("2"),Decimal("1"),2,Decimal("2"),Decimal("3"),Decimal("1"),Decimal("2"),"VALID_GENERIC_COST_SUPPORT"),
        ]
        idx=TransactionLocalCostIndex("NAS100",rows)
        intent=ReplayIntent("V2-C012",CANDIDATE_HASHES["V2-C012"],"SHORT_NAS100",entry,entry,16000.0,exit_,15990.0,{})
        eurusd=CausalConversionSeries.from_rows("EURUSD",[
            {"time_utc":"2024-01-02T14:30:00Z","close":"1.10"},
            {"time_utc":"2024-01-02T15:30:00Z","close":"1.11"},
        ])
        c=_prepare_candidate("V2-C012",[intent],cost_index=idx,eurusd=eurusd)
        self.assertEqual(c.cost_state,"CONSERVATIVE_BOUND")
        self.assertEqual(c.trades[0].entry_cost_evidence.transaction_cost_proxy_points,Decimal("3"))
        self.assertEqual(c.trades[0].exit_cost_evidence.transaction_cost_proxy_points,Decimal("2"))

    def test_05_candidate_direction_cannot_reduce_transaction_cost(self):
        row=TransactionCostEvidence("NAS100","2024-01-02",1000,Decimal("10"),Decimal("11"),Decimal("1"),1010,Decimal("12"),Decimal("13"),Decimal("2"),Decimal("3"),"VALID_GENERIC_COST_SUPPORT")
        idx=TransactionLocalCostIndex("NAS100",[row])
        self.assertEqual(idx.cost_points(1000,direction="LONG_NAS100"),Decimal("3"))
        self.assertEqual(idx.cost_points(1000,direction="SHORT_NAS100"),Decimal("3"))

    def test_06_unsupported_or_missing_row_is_cost_unresolved(self):
        idx=TransactionLocalCostIndex("NAS100",[
            TransactionCostEvidence("NAS100","2024-01-02",1000,None,None,None,None,None,None,None,None,"MISSING_POST_BOUNDARY_SIDE_EVENT")
        ])
        with self.assertRaises(CostEvidenceUnavailable):
            idx.evidence_for(1000)
        with self.assertRaises(CostEvidenceUnavailable):
            idx.evidence_for(2000)

    def test_07_two_known_c012_1500_contexts_remain_fail_closed(self):
        self.assertEqual(
            C012_KNOWN_UNSUPPORTED_BOUNDARIES_MS,
            frozenset({1735675200000,1767211200000}),
        )
        rows=[
            {"session_date":"2024-12-31","boundary_timestamp_ms":"1735675200000","causal_bid":"1","causal_ask":"2","causal_spread":"1","refresh_timestamp_ms":"","refresh_bid":"","refresh_ask":"","absolute_mid_displacement_points":"","state":"MISSING_POST_BOUNDARY_SIDE_EVENT"},
            {"session_date":"2025-12-31","boundary_timestamp_ms":"1767211200000","causal_bid":"1","causal_ask":"2","causal_spread":"1","refresh_timestamp_ms":"","refresh_bid":"","refresh_ask":"","absolute_mid_displacement_points":"","state":"MISSING_POST_BOUNDARY_SIDE_EVENT"},
        ]
        idx=from_c012_support_rows(rows)
        for boundary in C012_KNOWN_UNSUPPORTED_BOUNDARIES_MS:
            with self.assertRaises(CostEvidenceUnavailable):
                idx.evidence_for(boundary)

    def test_08_global_maxima_are_stress_diagnostics_only(self):
        a=load("evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json")
        self.assertEqual(C006_STRESS_DIAGNOSTIC["round_trip_points"],Decimal("13.3"))
        self.assertEqual(C012_STRESS_DIAGNOSTIC["transaction_points"],Decimal("95.3"))
        self.assertEqual(C012_STRESS_DIAGNOSTIC["nominal_round_trip_points"],Decimal("190.6"))
        self.assertEqual(a["candidates"]["V2-C006"]["worst_observed_stress_diagnostic"]["role"],"STRESS_DIAGNOSTIC_ONLY_NOT_PRIMARY_COST")
        self.assertEqual(a["candidates"]["V2-C012"]["worst_observed_stress_diagnostic"]["role"],"STRESS_DIAGNOSTIC_ONLY_NOT_PRIMARY_COST")
        self.assertEqual(a["candidates"]["V2-C006"]["primary_cost"],"TRANSACTION_LOCAL")
        self.assertEqual(a["candidates"]["V2-C012"]["primary_cost"],"TRANSACTION_LOCAL")

    def test_09_no_percentile_primary_rule_is_introduced(self):
        a=load("evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json")
        text=json.dumps(a).lower()
        self.assertFalse(a["primary_discovery_cost"]["percentile_selection_used"])
        self.assertTrue(a["stress_policy"]["percentile_primary_rule_forbidden"])
        self.assertNotIn('"p95"',text)
        self.assertNotIn('"p99"',text)
        self.assertNotIn('"p99_9"',text)

    def test_10_quote_refresh_is_not_fill_and_market_proxy_is_unchanged(self):
        a=load("evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json")
        x=a["execution_truth_separation"]
        self.assertFalse(x["quote_refresh_is_historical_fill_assertion"])
        self.assertFalse(x["candidate_market_proxy_timing_mutated"])
        self.assertFalse(x["candidate_market_proxy_price_mutated"])
        self.assertFalse(x["certification_execution_truth_established"])
        self.assertEqual(load("discovery/candidates/V2-C006.json")["spec_hash"],CANDIDATE_HASHES["V2-C006"])
        self.assertEqual(load("discovery/candidates/V2-C012.json")["spec_hash"],CANDIDATE_HASHES["V2-C012"])

    def test_11_first_stage_a_runner_is_prepared_hash_gated_and_not_run(self):
        verify_repository_authorities(ROOT)
        p=load("data/M6_STAGE_A_TIER1_RUNNER_PREP_V1.json")
        self.assertEqual(p["status"],"PREPARED_NOT_RUN")
        self.assertFalse(p["current_execution_authorized"])
        self.assertFalse(p["current_execution_performed"])
        self.assertFalse(p["result_files_created"])
        dummy=StageAInputPaths(*(Path("missing") for _ in range(5)))
        with self.assertRaises(StageAExecutionNotAuthorized):
            execute_stage_a_in_memory(ROOT,dummy,authorization_path=None)

    def test_12_current_state_remains_zero_economics_and_protected_unopened(self):
        s=load("CURRENT_STATE.json")
        ledger=[json.loads(x) for x in (ROOT/"discovery/ledger.jsonl").read_text().splitlines() if x.strip()]
        self.assertEqual(s["economic_outcomes_opened"],0)
        self.assertEqual(s["v2_attempts_used"],0)
        self.assertEqual(s["v2_evaluated_identities"],0)
        self.assertEqual(sum(x["entry_type"]=="RESULT_RECORDED" for x in ledger),0)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["m6"]["economics_run"])
        self.assertEqual(s["m6"]["status"],"PENDING")
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])

if __name__=="__main__":
    unittest.main(verbosity=2)
