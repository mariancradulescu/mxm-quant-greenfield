import json
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from m6.stage_b_evaluator import (
    FIXED_VOLUME_CENTS,
    STARTING_CAPITAL_EUR,
    StageBMarginEvidenceUnavailable,
    fixed_quantity,
    realize_continuous_capital,
)
from m6.stage_b_tier1_runner import EXPECTED_CURRENT_MARGIN_DIAGNOSTIC

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

@dataclass(frozen=True)
class Intent:
    candidate_id:str
    spec_hash:str
    direction:str
    entry_utc:datetime
    exit_utc:datetime
    entry_price:float
    exit_price:float

@dataclass(frozen=True)
class Cost:
    transaction_cost_proxy_points:Decimal
    boundary_timestamp_ms:int=0
    supported:bool=True

@dataclass(frozen=True)
class Prepared:
    intent:Intent
    entry_cost_evidence:Cost
    exit_cost_evidence:Cost
    entry_usd_to_eur_rate:Decimal
    exit_usd_to_eur_rate:Decimal

@dataclass(frozen=True)
class Candidate:
    candidate_id:str
    spec_hash:str
    cost_state:str
    trades:tuple

class StageBTier1PreparationTests(unittest.TestCase):
    def test_01_policy_is_frozen_pre_stage_b_outcome(self):
        p=load("data/M6_STAGE_B_TIER1_EVALUATOR_POLICY_V1.json")
        self.assertEqual(p["status"],"FROZEN_POST_STAGE_A_PRE_STAGE_B_OUTCOME")
        self.assertEqual(p["capital_law"]["starting_capital_eur"],200)
        self.assertTrue(p["capital_law"]["capital_continuous"])
        self.assertFalse(p["capital_law"]["reset_weekly"])
        self.assertFalse(p["capital_law"]["reset_monthly"])
        self.assertTrue(p["capital_law"]["no_scaling_after_gains"])
        self.assertEqual(p["sizing_law"]["volume_cents"],{"V2-C006":10,"V2-C012":10})
        self.assertFalse(p["sizing_law"]["optimization_used"])
        self.assertFalse(p["sizing_law"]["stage_a_outcome_magnitude_used_to_choose_sizing"])

    def test_02_minimum_volume_law_is_exact_and_shared(self):
        self.assertEqual(STARTING_CAPITAL_EUR,Decimal("200"))
        self.assertEqual(FIXED_VOLUME_CENTS,{"V2-C006":10,"V2-C012":10})
        self.assertEqual(fixed_quantity("V2-C006"),Decimal("0.1"))
        self.assertEqual(fixed_quantity("V2-C012"),Decimal("0.1"))

    def test_03_current_margin_snapshot_is_diagnostic_not_historical_authority(self):
        p=load("data/M6_STAGE_B_TIER1_EVALUATOR_POLICY_V1.json")
        m=p["margin_law"]
        self.assertEqual(m["state"],"HISTORICAL_CAUSAL_MARGIN_AUTHORITY_REQUIRED_BEFORE_STAGE_B_OUTCOME")
        self.assertTrue(m["current_broker_native_expected_margin_diagnostic_only"])
        self.assertTrue(m["approximate_leverage_arithmetic_forbidden"])
        self.assertEqual(m["current_snapshot"]["V2-C006"]["buy_margin_eur"],33.38)
        self.assertEqual(m["current_snapshot"]["V2-C012"]["buy_margin_eur"],129.04)
        self.assertEqual(EXPECTED_CURRENT_MARGIN_DIAGNOSTIC["V2-C006"]["volume_cents"],10)
        self.assertEqual(EXPECTED_CURRENT_MARGIN_DIAGNOSTIC["V2-C012"]["volume_cents"],10)

    def test_04_margin_authority_is_fail_closed(self):
        now=datetime(2026,1,2,15,0,tzinfo=timezone.utc)
        c=Candidate("V2-C006","75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49","CONSERVATIVE_BOUND",())
        with self.assertRaises(StageBMarginEvidenceUnavailable):
            realize_continuous_capital(c,margin_authority={})

    def test_05_synthetic_continuous_capital_never_resizes(self):
        now=datetime(2026,1,2,15,0,tzinfo=timezone.utc)
        spec="75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49"
        t1=Prepared(Intent("V2-C006",spec,"LONG",now,now+timedelta(minutes=180),100.0,110.0),Cost(Decimal("1")),Cost(Decimal("1")),Decimal("1"),Decimal("1"))
        later=now+timedelta(days=1)
        t2=Prepared(Intent("V2-C006",spec,"LONG",later,later+timedelta(minutes=180),100.0,110.0),Cost(Decimal("1")),Cost(Decimal("1")),Decimal("1"),Decimal("1"))
        c=Candidate("V2-C006",spec,"CONSERVATIVE_BOUND",(t1,t2))
        auth={
          "schema":"mxm.greenfield.v2.m6-stage-b-margin-authority.v1",
          "status":"FROZEN_CONSERVATIVE_HISTORICAL_MARGIN_BOUND",
          "volume_cents":{"V2-C006":10,"V2-C012":10},
          "candidate_spec_hashes":{
            "V2-C006":spec,
            "V2-C012":"3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845"
          },
          "post_outcome_tuning":False,
          "max_required_margin_eur":{"V2-C006":50,"V2-C012":150}
        }
        r=realize_continuous_capital(c,margin_authority=auth)
        self.assertEqual(r.executed_trades,2)
        self.assertEqual(r.margin_blocked_trades,0)
        self.assertEqual(r.final_equity_eur,Decimal("201.6"))
        closes=[x for x in r.path if x["event"]=="TRADE_CLOSED"]
        self.assertTrue(all(x["volume_cents"]==10 for x in closes))

    def test_06_pre_economic_materialization_opens_no_stage_b_outcome(self):
        m=load("evidence/M6_STAGE_B_TIER1_PRE_ECONOMIC_MATERIALIZATION_V1.json")
        self.assertEqual(m["status"],"PASS_FROZEN_STAGE_B_INPUT_BINDINGS_MARGIN_GATE_UNRESOLVED_NO_STAGE_B_ECONOMICS")
        f=m["forbidden_during_materialization"]
        self.assertFalse(f["stage_b_candidate_pnl_computed"])
        self.assertFalse(f["stage_b_capital_path_computed"])
        self.assertFalse(f["stage_b_terminal_status_computed"])
        self.assertFalse(f["new_attempt_consumed"])
        self.assertFalse(f["stage_b_result_recorded"])
        self.assertFalse(f["protected_evidence_opened"])

    def test_07_runner_prep_is_not_execution_authorization(self):
        p=load("data/M6_STAGE_B_TIER1_RUNNER_PREP_V1.json")
        self.assertEqual(p["status"],"PREPARED_NOT_RUN_MARGIN_GATE_UNRESOLVED")
        self.assertFalse(p["execution_authorized"])
        self.assertFalse(p["results_created"])
        self.assertEqual(p["stage_b_outcomes_opened"],0)
        self.assertEqual(p["new_attempts_consumed"],0)

    def test_08_live_total_includes_current_config_while_historical_track_stays_unrun(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(s["economic_outcomes_opened"],4)
        self.assertEqual(s["v2_attempts_used"],2)
        self.assertEqual(s["v2_evaluated_identities"],2)
        self.assertEqual(s["v2_search_budget_remaining"],82)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["m6"]["stage_b"]["execution_authorized"])
        self.assertFalse(s["m6"]["stage_b"]["economics_run"])
        self.assertFalse(s["m6"]["stage_b"]["results_created"])
        ledger=[json.loads(x) for x in (ROOT/"discovery/ledger.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertGreaterEqual(len(ledger),26)
        self.assertEqual(sum(x["entry_type"]=="RESULT_RECORDED" for x in ledger[:22]),2)
        self.assertFalse(any((ROOT/"discovery/results").glob("*STAGE_B*")))

if __name__=="__main__":
    unittest.main(verbosity=2)
