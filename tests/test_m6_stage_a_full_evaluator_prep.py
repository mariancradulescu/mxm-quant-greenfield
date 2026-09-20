import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from discovery.schema import STAGE_A_METRIC_KEYS, validate_result
from m6.session_replay import NasdaqCashCalendar
from m6.stage_a_evaluator import (
    EVALUATOR_VERSION,
    evaluate_prepared_candidate,
    settle_prepared_trade,
)
from m6.stage_a_tier1_runner import (
    CANDIDATE_HASHES,
    EVALUATOR_POLICY_GIT_BLOB,
    EVALUATOR_RUNTIME_GIT_BLOB,
    EVALUATOR_RUNTIME_SHA256,
    EXPECTED_COMBINED_INTENT_MANIFEST_SHA256,
    PRE_ECONOMIC_MATERIALIZATION_GIT_BLOB,
    TRANSACTION_LOCAL_COST_RULE_GIT_BLOB,
    PreparedCandidate,
    PreparedTrade,
    StageAExecutionNotAuthorized,
    _load_execution_authorization,
    verify_repository_authorities,
)
from m6.tier1_candidate_replay import ReplayIntent
from m6.transaction_local_cost import TransactionCostEvidence

ROOT=Path(__file__).resolve().parents[1]
RUNNER_SOURCE_SHA256="84a4e588300053fe8583ff36dde3db885d77727f811212d161bdac770c5919df"


def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))


def evidence(instrument, stamp, points):
    ms=int(stamp.timestamp()*1000)
    return TransactionCostEvidence(
        instrument=instrument,
        session_date=stamp.date().isoformat(),
        boundary_timestamp_ms=ms,
        causal_bid=Decimal("100"),
        causal_ask=Decimal("100.1"),
        causal_spread_points=Decimal("0.1"),
        refresh_timestamp_ms=ms+1,
        refresh_bid=Decimal("100"),
        refresh_ask=Decimal("100.1"),
        absolute_mid_displacement_points=Decimal("0"),
        transaction_cost_proxy_points=Decimal(str(points)),
        availability_state="VALID_GENERIC_COST_SUPPORT",
    )


def prepared_trade(
    *,
    entry_price=100.0,
    exit_price=101.0,
    direction="LONG",
    entry_rate="1",
    exit_rate="1",
    entry_cost="0.1",
    exit_cost="0.1",
    entry=None,
    exit_=None,
):
    entry=entry or datetime(2024,1,2,14,45,tzinfo=timezone.utc)
    exit_=exit_ or datetime(2024,1,2,17,45,tzinfo=timezone.utc)
    intent=ReplayIntent(
        candidate_id="V2-C006",
        spec_hash=CANDIDATE_HASHES["V2-C006"],
        direction=direction,
        decision_utc=entry,
        entry_utc=entry,
        entry_price=entry_price,
        exit_utc=exit_,
        exit_price=exit_price,
        evidence={},
    )
    return PreparedTrade(
        intent=intent,
        entry_cost_evidence=evidence("US500",entry,entry_cost),
        exit_cost_evidence=evidence("US500",exit_,exit_cost),
        entry_usd_to_eur_rate=Decimal(entry_rate),
        exit_usd_to_eur_rate=Decimal(exit_rate),
    )


def candidate(trades):
    return PreparedCandidate(
        candidate_id="V2-C006",
        spec_hash=CANDIDATE_HASHES["V2-C006"],
        cost_state="CONSERVATIVE_BOUND",
        trades=tuple(trades),
        unresolved_reason=None,
    )


def evaluate(trades):
    return evaluate_prepared_candidate(
        candidate(trades),
        calendar=NasdaqCashCalendar([],[]),
        evaluator_sha256=EVALUATOR_RUNTIME_SHA256,
    )


def valid_auth():
    return {
        "schema":"mxm.greenfield.v2.m6-stage-a-execution-authorization.v1",
        "status":"AUTHORIZED",
        "stage":"A",
        "candidate_spec_hashes":CANDIDATE_HASHES,
        "transaction_local_cost_rule_git_blob_sha":TRANSACTION_LOCAL_COST_RULE_GIT_BLOB,
        "evaluator_policy_git_blob_sha":EVALUATOR_POLICY_GIT_BLOB,
        "evaluator_runtime_git_blob_sha":EVALUATOR_RUNTIME_GIT_BLOB,
        "evaluator_runtime_sha256":EVALUATOR_RUNTIME_SHA256,
        "pre_economic_materialization_git_blob_sha":PRE_ECONOMIC_MATERIALIZATION_GIT_BLOB,
        "combined_intent_manifest_sha256":EXPECTED_COMBINED_INTENT_MANIFEST_SHA256,
        "runner_source_sha256":RUNNER_SOURCE_SHA256,
        "protected_evidence_opened":False,
    }


class FullStageAEvaluatorPrepTests(unittest.TestCase):
    def test_01_repository_and_new_pre_outcome_authorities_are_hash_gated(self):
        verify_repository_authorities(ROOT)
        policy=load("data/M6_STAGE_A_TIER1_EVALUATOR_POLICY_V1.json")
        material=load("evidence/M6_STAGE_A_TIER1_PRE_ECONOMIC_MATERIALIZATION_V1.json")
        prep=load("data/M6_STAGE_A_TIER1_RUNNER_PREP_V2.json")
        self.assertEqual(policy["evaluator"]["runtime_sha256"],EVALUATOR_RUNTIME_SHA256)
        self.assertTrue(policy["frozen_before_any_v2_economic_outcome"])
        self.assertEqual(material["replay_materialization"]["V2-C006"]["intent_count"],108)
        self.assertEqual(material["replay_materialization"]["V2-C012"]["intent_count"],35)
        self.assertEqual(material["replay_materialization"]["transaction_cost_context_count"],286)
        self.assertEqual(material["replay_materialization"]["V2-C006"]["unresolved_transaction_cost_contexts"],0)
        self.assertEqual(material["replay_materialization"]["V2-C012"]["unresolved_transaction_cost_contexts"],0)
        self.assertEqual(prep["status"],"FULL_STAGE_A_EVALUATOR_PREPARED_NOT_RUN")
        self.assertFalse(prep["current_execution_authorized"])
        self.assertFalse(prep["current_execution_performed"])

    def test_02_fixed_1000_eur_entry_normalization_and_causal_exit_conversion(self):
        t=prepared_trade(
            entry_price=100.0,
            exit_price=110.0,
            entry_rate="0.9",
            exit_rate="0.8",
            entry_cost="0.2",
            exit_cost="0.3",
        )
        s=settle_prepared_trade(t)
        expected_q=Decimal("1000")/(Decimal("100")*Decimal("0.9"))
        self.assertEqual(s["quantity"],expected_q)
        self.assertEqual(s["entry_notional_eur"],Decimal("1000"))
        expected_gross=(Decimal("110")-Decimal("100"))*expected_q*Decimal("0.8")
        self.assertEqual(s["gross_pnl_eur"],expected_gross)
        expected_cost=Decimal("0.2")*expected_q*Decimal("0.9")+Decimal("0.3")*expected_q*Decimal("0.8")
        self.assertEqual(s["transaction_cost_eur"],expected_cost)
        self.assertEqual(s["coarse_net_pnl_eur"],expected_gross-expected_cost)

    def test_03_direction_never_reduces_transaction_cost(self):
        long=settle_prepared_trade(prepared_trade(direction="LONG",entry_price=100,exit_price=101))
        short=settle_prepared_trade(prepared_trade(direction="SHORT",entry_price=100,exit_price=99))
        self.assertEqual(long["transaction_cost_eur"],short["transaction_cost_eur"])

    def test_04_status_law_gross_edge_fail(self):
        r=evaluate([prepared_trade(entry_price=100,exit_price=99,entry_cost="0",exit_cost="0")])
        self.assertEqual(r["status"],"GROSS_EDGE_FAIL")
        self.assertTrue(validate_result(r))

    def test_05_status_law_coarse_net_fail(self):
        r=evaluate([prepared_trade(entry_price=100,exit_price=101,entry_cost="1",exit_cost="1")])
        self.assertGreater(r["metrics"]["gross_pnl"],0)
        self.assertLessEqual(r["metrics"]["coarse_net_pnl"],0)
        self.assertEqual(r["status"],"COARSE_NET_FAIL")
        self.assertTrue(validate_result(r))

    def test_06_status_law_survivor(self):
        r=evaluate([prepared_trade(entry_price=100,exit_price=101,entry_cost="0.01",exit_cost="0.01")])
        self.assertGreater(r["metrics"]["coarse_net_pnl"],0)
        self.assertEqual(r["status"],"DISCOVERY_SURVIVOR")
        self.assertTrue(validate_result(r))

    def test_07_all_21_stage_a_metrics_are_present_and_schema_valid(self):
        r=evaluate([prepared_trade()])
        self.assertEqual(set(r["metrics"]),set(STAGE_A_METRIC_KEYS))
        self.assertTrue(validate_result(r))
        self.assertEqual(r["eur200_feasibility"]["state"],"NOT_EVALUATED")
        self.assertEqual(r["regime_contribution"] if "regime_contribution" in r else None,None)
        self.assertEqual(r["metrics"]["regime_contribution"]["state"],"NOT_APPLICABLE")

    def test_08_weekly_zero_weeks_and_full_boundary_inactive_gap_are_retained(self):
        r=evaluate([prepared_trade()])
        weeks=r["metrics"]["weekly_events"]
        self.assertGreater(len(weeks),r["metrics"]["active_weeks"])
        self.assertTrue(any(v==0 for v in weeks.values()))
        trailing=(date(2026,9,16)-date(2024,1,2)).days
        self.assertGreaterEqual(r["metrics"]["longest_inactive_gap"],trailing)

    def test_09_drawdown_uses_fixed_unit_coarse_net_path(self):
        t1=prepared_trade(entry_price=100,exit_price=102,entry_cost="0",exit_cost="0",
                          entry=datetime(2024,1,2,14,45,tzinfo=timezone.utc),
                          exit_=datetime(2024,1,2,17,45,tzinfo=timezone.utc))
        t2=prepared_trade(entry_price=100,exit_price=99,entry_cost="0",exit_cost="0",
                          entry=datetime(2024,1,3,14,45,tzinfo=timezone.utc),
                          exit_=datetime(2024,1,3,17,45,tzinfo=timezone.utc))
        r=evaluate([t1,t2])
        self.assertAlmostEqual(r["metrics"]["drawdown"],10.0,places=10)

    def test_10_provenance_binds_data_cost_and_evaluator(self):
        r=evaluate([prepared_trade()])
        self.assertEqual(r["provenance"]["data_evidence"]["binding"]["sha256"],
                         "88c68f1724eba71ef58fe02a929c935dc1cbf4be432897db599be7b37fd4ae72")
        self.assertEqual(r["provenance"]["cost_evidence"]["sha256"],
                         "601eedcb147021fff54f4d3bd2a43d831c455a821ddafa01a0036afe5c5485d6")
        self.assertEqual(r["provenance"]["evaluator"]["version"],EVALUATOR_VERSION)
        self.assertEqual(r["provenance"]["evaluator"]["sha256"],EVALUATOR_RUNTIME_SHA256)

    def test_11_authorization_is_fail_closed_on_evaluator_or_materialization_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"auth.json"
            a=valid_auth(); a["evaluator_runtime_sha256"]="0"*64
            p.write_text(json.dumps(a),encoding="utf-8")
            with self.assertRaises(StageAExecutionNotAuthorized):
                _load_execution_authorization(p,runner_source_sha256=RUNNER_SOURCE_SHA256)
            a=valid_auth(); a["combined_intent_manifest_sha256"]="0"*64
            p.write_text(json.dumps(a),encoding="utf-8")
            with self.assertRaises(StageAExecutionNotAuthorized):
                _load_execution_authorization(p,runner_source_sha256=RUNNER_SOURCE_SHA256)

    def test_12_authorization_absence_blocks_economics(self):
        with self.assertRaises(StageAExecutionNotAuthorized):
            _load_execution_authorization(None,runner_source_sha256=RUNNER_SOURCE_SHA256)

    def test_13_valid_authorization_binds_full_pre_outcome_stack(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"auth.json"; p.write_text(json.dumps(valid_auth()),encoding="utf-8")
            a=_load_execution_authorization(p,runner_source_sha256=RUNNER_SOURCE_SHA256)
            self.assertEqual(a["status"],"AUTHORIZED")
            self.assertFalse(a["protected_evidence_opened"])

    def test_14_materialization_commitments_are_exact_and_no_pnl_was_opened(self):
        m=load("evidence/M6_STAGE_A_TIER1_PRE_ECONOMIC_MATERIALIZATION_V1.json")
        x=m["replay_materialization"]
        self.assertEqual(x["V2-C006"]["full_intent_manifest_sha256"],
                         "6e320849ba49136b5491ecab75bc0ce5c36715a2c2202ade9d97443b41b9a515")
        self.assertEqual(x["V2-C012"]["full_intent_manifest_sha256"],
                         "f9d0ba61346bbd9a1602fe84e73d4d374d27e9fdec0217906b2ac29f24218c8d")
        self.assertEqual(x["combined_full_intent_manifest_sha256"],EXPECTED_COMBINED_INTENT_MANIFEST_SHA256)
        self.assertFalse(m["forbidden_during_materialization"]["candidate_pnl_computed"])
        self.assertFalse(m["forbidden_during_materialization"]["candidate_returns_computed"])
        self.assertFalse(m["forbidden_during_materialization"]["outcome_status_computed"])

    def test_15_candidate_specs_and_transaction_local_methodology_unchanged(self):
        self.assertEqual(load("discovery/candidates/V2-C006.json")["spec_hash"],CANDIDATE_HASHES["V2-C006"])
        self.assertEqual(load("discovery/candidates/V2-C012.json")["spec_hash"],CANDIDATE_HASHES["V2-C012"])
        self.assertEqual(
            load("evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json")["primary_discovery_cost"]["name"],
            "TRANSACTION_LOCAL_SAME_ROW_ADVERSE_PROXY",
        )

    def test_16_current_state_is_structural_ready_but_still_zero_economics(self):
        s=load("CURRENT_STATE.json")
        ledger=[json.loads(x) for x in (ROOT/"discovery/ledger.jsonl").read_text().splitlines() if x.strip()]
        self.assertEqual(s["m6_stage_a_tier1_evaluator_policy_authority"],
                         "data/M6_STAGE_A_TIER1_EVALUATOR_POLICY_V1.json")
        self.assertEqual(s["m6_stage_a_tier1_pre_economic_materialization_authority"],
                         "evidence/M6_STAGE_A_TIER1_PRE_ECONOMIC_MATERIALIZATION_V1.json")
        self.assertEqual(s["m6_stage_a_tier1_runner_prep_authority"],
                         "data/M6_STAGE_A_TIER1_RUNNER_PREP_V2.json")
        self.assertEqual(s["economic_outcomes_opened"],0)
        self.assertEqual(s["v2_attempts_used"],0)
        self.assertEqual(s["v2_evaluated_identities"],0)
        self.assertEqual(sum(x["entry_type"]=="RESULT_RECORDED" for x in ledger),0)
        self.assertEqual(len(ledger),20)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertEqual(s["m6"]["status"],"PENDING")
        self.assertFalse(s["m6"]["economics_run"])
        self.assertEqual(s["m6"]["first_stage_a_runner"]["state"],"PREPARED_NOT_RUN")
        self.assertEqual(s["m6"]["first_stage_a_runner"]["preparation_detail"],"FULL_EVALUATOR_PREPARED_NOT_RUN")
        self.assertFalse(s["m6"]["first_stage_a_runner"]["execution_authorized"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])


if __name__=="__main__":
    unittest.main(verbosity=2)
