import hashlib
import json
import unittest
from pathlib import Path

from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_HASHES = {
    "V2-C006": "75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49",
    "V2-C007": "d0e35a07a4b947aee5114dbf8f8bdd226ae525781cc54be12cfbf2a18e1d2fba",
    "V2-C008": "2df6728c2a9fe135f5a6908301a5378234a2ab08cb0c93046c3290c38f766370",
    "V2-C009": "f276ade8d32e17957ab036676c14c913fa8825d8c1254c994249224c79f38856",
    "V2-C010": "810670fbe6ed57c704a499c32799e6750417a431928eb55f8766b1ff87e46fc1",
    "V2-C011": "6fcf1f3f665fe6412a434c8272b18c2a5156d70f723409bc1340810bea8080fd",
    "V2-C012": "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845",
}

RAW_HASHES = {
    "AAPL": "8aba1da1b93615a42cff96703eb2b83d118f8e19876c79b7a5b26c7174a5c1d9",
    "AMZN": "5b6b25e3b06492a9ed5dc93ffa4e115d87ab37510baafdb486f23a481451df99",
    "AUDJPY": "cc80a219a15c830b00ef843063886eb9dd41a17161f436fd7bfa12b951a51bc4",
    "BTCUSD": "ca8beb4f4766b3abaf183784edfeb35486ab60a90be040493756240e7c0be4f5",
    "META": "1220cab923627c6868ed3d07b85dc80b85c1c7101fefe50cad2723a79d991f38",
    "MSFT": "c9a6a105685c3ae8eb6896279d11ab10210e6961bd8bf3dcb538efd56ba93ec6",
    "NAS100": "f92330927b0f41c3f6502951dbe512aa11449184916634c80e8f67f3c217eb7c",
    "NVDA": "f0a20a093d3c23507c6a7db924d9c907a3f1bcacbb349dc232b449e25ed0ca93",
    "US500": "e62aff5634ee2c3b9f3cbea3766a68d7a4a68b64ec9727aaa8cc757e2834fe87",
    "WTIUSD": "9378565e093af5c4982c6fc9e74a1c30753a9b97523779caebb48ef29026ce9a",
    "XAUUSD": "1121a184f38aa8e30b4d093ae49e7f0bbdc5e5b3ed439a1d41ba5b0f3a74ec93",
}
AUX_HASHES = {
    "EURUSD": "bce32af6ef251115d0628d746af16849a7ac23d7185a716670b0b22a4f09adde",
    "EURJPY": "2f25be36c7599937e120f9bd1f5cf44a62b3edf383e8735214f3bd58370009cf",
}


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def git_blob_sha(path):
    data = (ROOT / path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class PreM6AuxiliaryEvidenceTests(unittest.TestCase):
    def test_01_accepted_capture_and_data_manifest_blobs_are_unchanged(self):
        self.assertEqual(
            git_blob_sha("data/PRIMARY_WAVE_02_CAPTURE_ACCEPTANCE_V1.json"),
            "1d59b64a8619d8c62de0a5564208cabd5c590bd0",
        )
        self.assertEqual(
            git_blob_sha("data/DATA_MANIFEST.json"),
            "5cb5cb837d18406153021a0d96e56ae91636716b",
        )

    def test_02_all_11_primary_and_2_auxiliary_raw_hashes_are_preserved(self):
        manifest = load("data/DATA_MANIFEST.json")
        actual_primary = {
            row["canonical_instrument"]: row["csv_sha256"]
            for row in manifest["datasets"]
            if row.get("state") == "MATERIALIZED_HASH_VERIFIED_RAW_COMPONENT"
        }
        actual_aux = {
            row["canonical_instrument"]: row["csv_sha256"]
            for row in manifest["datasets"]
            if row.get("state") == "MATERIALIZED_HASH_VERIFIED_AUXILIARY_RAW_COMPONENT"
        }
        self.assertEqual(actual_primary, RAW_HASHES)
        self.assertEqual(actual_aux, AUX_HASHES)

    def test_03_active_candidate_specs_unchanged_and_no_refreeze_appended(self):
        for cid, expected in ACTIVE_HASHES.items():
            spec = load(f"discovery/candidates/{cid}.json")
            self.assertEqual(spec["spec_hash"], expected)
            self.assertTrue(verify_spec_hash(spec))
        ledger = read_ledger(ROOT / "discovery/ledger.jsonl")
        self.assertEqual(len(ledger), 26)
        self.assertFalse(any(row["entry_type"] == "RESULT_RECORDED" for row in ledger[:20]))
        self.assertFalse(any(row["entry_type"] == "CANDIDATE_REFROZEN_PRE_OUTCOME" for row in ledger[20:]))
    def test_04_c008_historical_continuous_construction_remains_unresolved(self):
        e = load("evidence/C008_SPOTCRUDE_CONTINUOUS_CONSTRUCTION_V1.json")
        self.assertEqual(e["accepted_current_mapping"]["broker_symbol"], "SpotCrude")
        self.assertEqual(e["accepted_current_mapping"]["symbol_id"], 250)
        self.assertEqual(e["gate_state"], "UNRESOLVED_HISTORICAL_CONTINUOUS_CONSTRUCTION")
        self.assertFalse(e["economic_use_authorized"])
        self.assertIn("Crude-F", e["no_substitution"])
        self.assertGreaterEqual(len(e["evidence"]["unresolved_historical_facts"]), 4)

    def test_05_c010_current_swap_snapshot_never_becomes_historical_financing(self):
        e = load("evidence/C010_AUDJPY_FINANCING_V1.json")
        self.assertEqual(e["gate_state"], "UNRESOLVED_HISTORICAL_FINANCING")
        self.assertFalse(e["positive_financing_credit_authorized"])
        self.assertFalse(e["current_capture_evidence"]["current_metadata_is_historical_truth"])
        self.assertFalse(e["economic_use_authorized"])

    def test_06_c011_point_in_time_split_and_ticker_events_are_bound(self):
        e = load("evidence/C011_POINT_IN_TIME_CORPORATE_ACTIONS_V1.json")
        events = {(x["canonical"], x["event_type"]): x for x in e["verified_underlying_events"]}
        self.assertEqual(events[("NVDA", "TEN_FOR_ONE_SPLIT")]["split_adjusted_trading_date"], "2024-06-10")
        self.assertEqual(events[("NVDA", "TEN_FOR_ONE_SPLIT")]["split_factor"], 10)
        self.assertEqual(events[("AMZN", "TWENTY_FOR_ONE_SPLIT")]["split_adjusted_trading_date"], "2022-06-06")
        self.assertEqual(events[("AMZN", "TWENTY_FOR_ONE_SPLIT")]["split_factor"], 20)
        self.assertEqual(events[("META", "TICKER_CHANGE")]["old_ticker"], "FB")
        self.assertEqual(events[("META", "TICKER_CHANGE")]["new_ticker"], "META")
        self.assertEqual(events[("META", "TICKER_CHANGE")]["effective_before_market_open"], "2022-06-09")
        self.assertIn(("AAPL", "NO_SPLIT_DURING_DEVELOPMENT_INTERVAL"), events)
        self.assertIn(("MSFT", "NO_SPLIT_DURING_DEVELOPMENT_INTERVAL"), events)

    def test_07_c011_broker_specific_cash_short_financing_and_session_gates_stay_unresolved(self):
        e = load("evidence/C011_POINT_IN_TIME_CORPORATE_ACTIONS_V1.json")
        self.assertEqual(e["gate_state"], "UNRESOLVED_PARTIAL_POINT_IN_TIME_EVIDENCE")
        self.assertEqual(e["dividend_evidence_state"]["broker_cfd_adjustment_history"], "UNRESOLVED")
        self.assertEqual(e["historical_short_eligibility"]["point_in_time_2022_2026"], "UNRESOLVED")
        self.assertEqual(e["historical_financing"]["point_in_time_share_cfd_financing_rates"], "UNRESOLVED")
        self.assertEqual(e["historical_sessions"]["exact_pepperstone_share_cfd_session_holiday_versions"], "UNRESOLVED")
        self.assertFalse(e["economic_use_authorized"])

    def test_08_reference_exchange_calendars_do_not_promote_broker_historical_sessions(self):
        e = load("evidence/PRE_M6_SESSION_CONVERSION_STAGEB_V1.json")
        session = e["session_evidence"]
        self.assertEqual(session["reference_cash_session"]["regular_hours_et"], "09:30-16:00")
        self.assertEqual(
            set(session["reference_cash_session"]["historical_calendar_sources"]),
            {"2022", "2023", "2024", "2025", "2026"},
        )
        self.assertEqual(session["historical_pepperstone_product_specific_sessions"]["state"], "UNRESOLVED")

    def test_09_conversion_raw_bytes_are_bound_but_historical_chain_membership_is_not_invented(self):
        e = load("evidence/PRE_M6_SESSION_CONVERSION_STAGEB_V1.json")
        conv = e["conversion_evidence"]
        self.assertEqual(conv["historical_raw_constituents"]["EURUSD"]["csv_sha256"], AUX_HASHES["EURUSD"])
        self.assertEqual(conv["historical_raw_constituents"]["EURJPY"]["csv_sha256"], AUX_HASHES["EURJPY"])
        self.assertEqual(
            conv["point_in_time_chain_validity"]["state"],
            "UNRESOLVED_CURRENT_CHAIN_NOT_PROVEN_HISTORICALLY_EFFECTIVE",
        )
        self.assertFalse(conv["economic_conversion_authorized"])
        self.assertTrue(conv["no_synthetic_conversion"])

    def test_10_stage_b_eur200_is_deferred_not_silently_inferred_from_current_margin(self):
        e = load("evidence/PRE_M6_SESSION_CONVERSION_STAGEB_V1.json")
        b = e["stage_b_eur200"]
        self.assertEqual(
            b["applicability_state"],
            "DEFERRED_NOT_APPLICABLE_UNTIL_A_DISCOVERY_SURVIVOR_EXISTS",
        )
        self.assertEqual(b["exact_causal_eur200_feasibility"], "NOT_EVALUATED_PRE_STAGE_B")
        self.assertFalse(b["current_expected_margin_snapshot"]["approximate_leverage_arithmetic_used"])
        self.assertEqual(b["current_expected_margin_snapshot"]["economic_conclusion"], "NOT_EVALUATED")

    def test_11_discovery_cost_evidence_remains_unresolved_no_arbitrary_bound(self):
        e = load("evidence/PRE_M6_DISCOVERY_COST_EVIDENCE_V1.json")
        self.assertEqual(
            e["status"],
            "UNRESOLVED_NO_VERIFIED_HISTORICAL_PATH_OR_DEFENSIBLE_COMPLETE_CONSERVATIVE_BOUND",
        )
        self.assertTrue(all(state == "UNRESOLVED" for state in e["candidate_cost_confidence"].values()))
        self.assertEqual(e["evidence_review"]["spread"]["conservative_bound"], "NOT_FROZEN")
        self.assertEqual(e["evidence_review"]["slippage_delay_gap_effects"]["conservative_bound"], "NOT_FROZEN")
        self.assertFalse(e["attempt_consumed"])
        self.assertEqual(e["economic_outcomes_opened"], 0)

    def test_12_auxiliary_register_blocks_m6_economics_without_declaring_candidate_failure(self):
        r = load("data/PRIMARY_WAVE_02_AUXILIARY_EVIDENCE_REGISTER_V1.json")
        self.assertEqual(r["status"], "PARTIAL_EVIDENCE_BOUND_M6_ECONOMICS_BLOCKED")
        self.assertEqual(r["cross_candidate_gates"]["m6_stage_a_economics"], "NOT_AUTHORIZED")
        self.assertEqual(
            r["cross_candidate_gates"]["prospectively_frozen_defensible_conservative_cost_bound"],
            "NOT_AVAILABLE_NOT_INVENTED",
        )
        self.assertTrue(all(v["economic_readiness"] == "BLOCKED" for v in r["candidates"].values()))
        self.assertTrue(all(v["stage_b_eur200"] == "DEFERRED_NOT_APPLICABLE" for v in r["candidates"].values()))

    def test_13_zero_economics_attempts_results_and_protected_boundary_are_preserved(self):
        state = load("CURRENT_STATE.json")
        budget = load("V2_SEARCH_BUDGET_V1.json")
        protected = load("V2_PROTECTED_FORWARD_START.json")
        auth = load("data/M6_STAGE_A_EXECUTION_AUTHORIZATION_V1.json")
        self.assertEqual(auth["preconditions"]["economic_outcomes_opened"], 0)
        self.assertEqual(auth["preconditions"]["v2_attempts_used"], 0)
        self.assertEqual(auth["preconditions"]["v2_evaluated_identities"], 0)
        self.assertEqual(state["m6"]["status"], "PENDING")
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])
        self.assertEqual(budget["v2_attempts_used"], 0)
        self.assertEqual(budget["v2_budget"], 84)
        self.assertFalse(protected["protected_evidence_opened"])
        self.assertEqual(protected["V2_PROTECTED_FORWARD_START"], "2026-09-17T12:02:58Z")
    def test_14_source_registry_explicitly_prevents_current_to_historical_promotion(self):
        s = load("evidence/PRE_M6_AUXILIARY_EVIDENCE_SOURCES_V1.json")
        rules = " ".join(s["global_non_promotion_rules"])
        self.assertIn("Current Pepperstone", rules)
        self.assertIn("Issuer dividends", rules)
        self.assertIn("average spread", rules)
        ids = {row["source_id"] for row in s["sources"]}
        self.assertTrue({
            "PEPPERSTONE_SPOT_CRUDE_PRICING_GUIDE",
            "PEPPERSTONE_COSTS_CURRENT",
            "PEPPERSTONE_CORPORATE_ACTION_POLICY_CURRENT",
            "NASDAQ_TRADING_CALENDAR_2022",
            "NASDAQ_TRADING_CALENDAR_2026",
            "APPLE_SPLIT_AND_DIVIDEND_HISTORY",
            "MICROSOFT_SPLIT_DIVIDEND_HISTORY",
            "NVIDIA_2024_SPLIT",
            "AMAZON_2022_SPLIT_SEC",
            "META_2022_TICKER_CHANGE",
        } <= ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
