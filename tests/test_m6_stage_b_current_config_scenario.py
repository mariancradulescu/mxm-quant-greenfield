import hashlib
import json
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from m6.stage_b_evaluator import StageBMarginEvidenceUnavailable, validate_margin_authority
from m6.stage_b_current_config_evaluator import (
    CURRENT_CONFIG_AUTHORITY_STATUS,
    CurrentConfigMarginAuthorityError,
    current_margin_for_direction,
    realize_current_configuration_capital,
    validate_current_configuration_authority,
)
from m6.stage_b_current_config_tier1_runner import (
    CurrentConfigExecutionNotAuthorized,
    git_blob_sha1,
    validate_execution_authorization,
    verify_repository_current_config_authorities,
)

ROOT = Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Intent:
    candidate_id: str
    spec_hash: str
    direction: str
    entry_utc: datetime
    exit_utc: datetime
    entry_price: float
    exit_price: float


@dataclass(frozen=True)
class Cost:
    transaction_cost_proxy_points: Decimal
    boundary_timestamp_ms: int = 0
    supported: bool = True


@dataclass(frozen=True)
class Prepared:
    intent: Intent
    entry_cost_evidence: Cost
    exit_cost_evidence: Cost
    entry_usd_to_eur_rate: Decimal
    exit_usd_to_eur_rate: Decimal


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    spec_hash: str
    cost_state: str
    trades: tuple


class StageBCurrentConfigurationScenarioTests(unittest.TestCase):
    def test_01_current_authority_is_verified_but_history_stays_unresolved(self):
        a = load("evidence/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json")
        self.assertEqual(a["status"], CURRENT_CONFIG_AUTHORITY_STATUS)
        self.assertEqual(
            a["historical_boundary"]["historical_point_in_time_margin_state"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertFalse(a["historical_boundary"]["historical_invariance_verified"])
        self.assertFalse(a["historical_boundary"]["current_configuration_is_historical_fact"])
        self.assertFalse(a["historical_boundary"]["absence_of_found_change_promoted_to_invariance"])
        validate_current_configuration_authority(a)

    def test_02_exact_broker_native_expected_margin_values_are_frozen_and_side_specific(self):
        a = load("evidence/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json")
        side, value = current_margin_for_direction("V2-C006", "LONG", a)
        self.assertEqual((side, value), ("BUY", Decimal("33.38")))
        side, value = current_margin_for_direction("V2-C006", "SHORT", a)
        self.assertEqual((side, value), ("SELL", Decimal("33.38")))
        side, value = current_margin_for_direction("V2-C012", "LONG_NAS100", a)
        self.assertEqual((side, value), ("BUY", Decimal("129.04")))
        side, value = current_margin_for_direction("V2-C012", "SHORT_NAS100", a)
        self.assertEqual((side, value), ("SELL", Decimal("129.03")))
        self.assertEqual(a["source_evidence"]["expected_margin_sha256"],
                         "08a5643687d4be0fb4f97422e13104c5b9eb08357932bad2463388c368140c9d")
        self.assertFalse(a["source_evidence"]["manual_leverage_reconstruction_used"])

    def test_03_current_and_historical_authority_types_cannot_cross_promote(self):
        current = load("evidence/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json")
        historical = load("evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json")
        with self.assertRaises(StageBMarginEvidenceUnavailable):
            validate_margin_authority(current)
        with self.assertRaises(CurrentConfigMarginAuthorityError):
            validate_current_configuration_authority(historical)

    def test_04_historical_v2_and_old_stage_b_stack_are_byte_identical(self):
        expected = {
            "evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json":
                "63a959ef9c767956d92772102f3aae3ab3b58237",
            "data/M6_STAGE_B_TIER1_EVALUATOR_POLICY_V1.json":
                "c0538732cd8a51c309d663baccbd919462aff4a2",
            "m6/stage_b_evaluator.py":
                "8996a683a28ef84d5e7c91db870f0e8a1aca8fe1",
            "m6/stage_b_tier1_runner.py":
                "89b6f59e41c000afca81036b20ecde9fd9ee2a18",
        }
        for rel, blob in expected.items():
            self.assertEqual(git_blob_sha1(ROOT / rel), blob)

    def test_05_candidates_and_transaction_local_cost_methodology_are_unchanged(self):
        expected = {
            "discovery/candidates/V2-C006.json":
                "a5a6e4865206a0f85afcae28a65004e1e24a8277",
            "discovery/candidates/V2-C012.json":
                "a9a8464d9cf161c3dcae39536280089058e882d9",
            "evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json":
                "64bc7a000e750cd29710b372c4e5587f1610668a",
        }
        for rel, blob in expected.items():
            self.assertEqual(git_blob_sha1(ROOT / rel), blob)
        self.assertEqual(load("discovery/candidates/V2-C006.json")["spec_hash"],
                         "75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49")
        self.assertEqual(load("discovery/candidates/V2-C012.json")["spec_hash"],
                         "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845")

    def test_06_synthetic_capital_path_uses_current_margin_without_resizing_or_future_pnl(self):
        a = load("evidence/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json")
        spec = "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845"
        t0 = datetime(2024, 1, 2, 15, 0, tzinfo=timezone.utc)
        first = Prepared(
            Intent("V2-C012", spec, "LONG_NAS100", t0, t0 + timedelta(hours=1), 1000.0, 200.0),
            Cost(Decimal("0")), Cost(Decimal("0")), Decimal("1"), Decimal("1"),
        )
        t1 = t0 + timedelta(days=1)
        second = Prepared(
            Intent("V2-C012", spec, "LONG_NAS100", t1, t1 + timedelta(hours=1), 1000.0, 2000.0),
            Cost(Decimal("0")), Cost(Decimal("0")), Decimal("1"), Decimal("1"),
        )
        c = Candidate("V2-C012", spec, "CONSERVATIVE_BOUND", (first, second))
        r = realize_current_configuration_capital(c, current_margin_authority=a)
        self.assertEqual(r.executed_trades, 1)
        self.assertEqual(r.margin_blocked_trades, 1)
        self.assertEqual(r.final_equity_eur, Decimal("120.0"))
        close = [x for x in r.path if x["event"] == "TRADE_CLOSED"][0]
        block = [x for x in r.path if x["event"] == "MARGIN_BLOCK"][0]
        self.assertEqual(close["volume_cents"], 10)
        self.assertEqual(close["required_margin_eur"], 129.04)
        self.assertEqual(block["required_margin_eur"], 129.04)
        self.assertFalse(close["historical_margin_claim"])
        self.assertFalse(block["historical_margin_claim"])

    def test_07_policy_records_post_stage_a_chronology_and_result_label(self):
        p = load("data/M6_STAGE_B_CURRENT_CONFIG_TIER1_EVALUATOR_POLICY_V1.json")
        self.assertEqual(p["status"], "FROZEN_POST_STAGE_A_PRE_CURRENT_CONFIG_STAGE_B_OUTCOME")
        self.assertTrue(p["chronology"]["stage_a_outcomes_already_known"])
        self.assertTrue(p["chronology"]["this_policy_is_not_claimed_pre_stage_a"])
        self.assertEqual(p["result_semantics"]["required_label"],
                         "STAGE_B_CURRENT_CONFIGURATION_SCENARIO")
        self.assertEqual(
            p["result_semantics"]["survival_conclusion"],
            "SURVIVES EUR200 CAPITAL REALIZATION UNDER VERIFIED CURRENT PEPPERSTONE CONFIGURATION APPLIED TO DEVELOPMENT SEQUENCE",
        )
        self.assertEqual(p["result_semantics"]["historical_certification_effect"], "NONE")

    def test_08_repository_validation_binds_new_track_and_preserves_history(self):
        result = verify_repository_current_config_authorities(ROOT)
        self.assertEqual(result["authority_status"], CURRENT_CONFIG_AUTHORITY_STATUS)
        self.assertEqual(
            result["historical_margin_state"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertEqual(result["current_config_outcomes_opened"], 0)

    def test_09_single_use_authorization_is_frozen_but_inactive_before_audit(self):
        a = load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V1.json")
        self.assertEqual(a["status"], "FROZEN_SINGLE_USE_PENDING_INDEPENDENT_AUDIT")
        self.assertTrue(a["single_use"])
        self.assertFalse(a["consumed"])
        self.assertFalse(a["execution_authorized"])
        self.assertFalse(a["independent_audit_pass"])
        with self.assertRaises(CurrentConfigExecutionNotAuthorized):
            validate_execution_authorization(a)

    def test_10_accounting_and_protected_boundary_remain_unchanged(self):
        s = load("CURRENT_STATE.json")
        self.assertEqual(s["economic_outcomes_opened"], 2)
        self.assertEqual(s["v2_attempts_used"], 2)
        self.assertEqual(s["v2_evaluated_identities"], 2)
        self.assertEqual(s["v2_search_budget"], 84)
        self.assertEqual(s["v2_search_budget_remaining"], 82)
        self.assertFalse(s["protected_evidence_opened"])
        track = s["m6"]["stage_b_current_configuration"]
        self.assertFalse(track["execution_authorized"])
        self.assertFalse(track["economics_run"])
        self.assertFalse(track["results_created"])
        self.assertEqual(track["stage_b_current_config_outcomes_opened"], 0)
        ledger = [
            json.loads(x) for x in (ROOT / "discovery/ledger.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        self.assertEqual(len(ledger), 22)
        self.assertEqual(sum(x["entry_type"] == "RESULT_RECORDED" for x in ledger), 2)
        self.assertFalse(any((ROOT / "discovery/results").glob("*STAGE_B_CURRENT_CONFIG*")))

    def test_11_pre_economic_materialization_contains_no_scenario_outcome(self):
        m = load("evidence/M6_STAGE_B_CURRENT_CONFIG_PRE_ECONOMIC_MATERIALIZATION_V1.json")
        f = m["forbidden_during_materialization"]
        self.assertFalse(f["current_config_candidate_pnl_computed"])
        self.assertFalse(f["current_config_capital_path_computed"])
        self.assertFalse(f["current_config_terminal_status_computed"])
        self.assertFalse(f["new_attempt_consumed"])
        self.assertFalse(f["result_recorded"])
        self.assertFalse(f["protected_evidence_opened"])

    def test_12_current_track_does_not_require_broker_email_to_be_prepared(self):
        s = load("CURRENT_STATE.json")
        self.assertFalse(s["user_action_required"])
        track = s["m6"]["stage_b_current_configuration"]
        self.assertTrue(track["historical_broker_confirmation_optional_non_blocking"])
        self.assertTrue(track["historical_margin_non_blocking_for_current_scenario"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
