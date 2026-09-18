import json
import unittest
from pathlib import Path

from m6.cost_evidence import (
    QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS,
    DecodedTick,
    COST_PACKAGE_FILES,
    causal_merge_bid_ask,
    causal_state_at_boundary,
    cost_resume_contract,
    first_any_quote_event_at_or_after,
    first_both_sides_refreshed_diagnostic,
    first_tick_at_or_after,
)

ROOT = Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class PreM6QuoteEvidenceExecutionAuthorityTests(unittest.TestCase):
    def test_01_bid_observed_before_boundary_remains_causal_bid(self):
        bids = [DecodedTick(900, 1000000), DecodedTick(1100, 1100000)]
        asks = [DecodedTick(995, 1020000), DecodedTick(1200, 1200000)]
        state = causal_state_at_boundary(bids, asks, 1000)
        self.assertEqual(state.bid_timestamp_ms, 900)
        self.assertAlmostEqual(state.bid, 10.0)
        self.assertEqual(state.bid_age_ms, 100)

    def test_02_ask_observed_before_boundary_remains_causal_ask(self):
        bids = [DecodedTick(990, 1000000), DecodedTick(1100, 1100000)]
        asks = [DecodedTick(850, 1020000), DecodedTick(1200, 1200000)]
        state = causal_state_at_boundary(bids, asks, 1000)
        self.assertEqual(state.ask_timestamp_ms, 850)
        self.assertAlmostEqual(state.ask, 10.2)
        self.assertEqual(state.ask_age_ms, 150)

    def test_03_quote_ages_and_spread_are_recorded(self):
        state = causal_state_at_boundary(
            [DecodedTick(900, 1000000)],
            [DecodedTick(950, 1020000)],
            1000,
        )
        self.assertEqual(state.bid_age_ms, 100)
        self.assertEqual(state.ask_age_ms, 50)
        self.assertAlmostEqual(state.spread, 0.2)
        self.assertEqual(state.availability, "CAUSAL_TWO_SIDED_AVAILABLE")

    def test_04_future_events_never_populate_causal_state_at_boundary(self):
        state = causal_state_at_boundary(
            [DecodedTick(1010, 1000000)],
            [DecodedTick(1020, 1020000)],
            1000,
        )
        self.assertIsNone(state.bid)
        self.assertIsNone(state.ask)
        self.assertEqual(state.availability, "MISSING_BOTH_SIDES")

    def test_05_first_post_boundary_bid_and_ask_are_independent(self):
        bids = [DecodedTick(900, 1000000), DecodedTick(1007, 1010000)]
        asks = [DecodedTick(950, 1020000), DecodedTick(1040, 1030000)]
        bid = first_tick_at_or_after(bids, 1000)
        ask = first_tick_at_or_after(asks, 1000)
        self.assertEqual(bid.timestamp_ms, 1007)
        self.assertEqual(ask.timestamp_ms, 1040)
        self.assertAlmostEqual(bid.price, 10.1)
        self.assertAlmostEqual(ask.price, 10.3)
        self.assertEqual(bid.timestamp_ms - 1000, 7)
        self.assertEqual(ask.timestamp_ms - 1000, 40)

    def test_06_first_post_boundary_any_is_independent(self):
        bids = [DecodedTick(1015, 1010000)]
        asks = [DecodedTick(1004, 1020000)]
        any_event = first_any_quote_event_at_or_after(bids, asks, 1000)
        self.assertEqual(any_event.timestamp_ms, 1004)
        self.assertEqual(any_event.side, "ASK")
        self.assertIsNone(any_event.bid_price)
        self.assertAlmostEqual(any_event.ask_price, 10.2)
        self.assertEqual(any_event.delay_ms, 4)

    def test_07_same_ms_first_any_preserves_both_sides(self):
        any_event = first_any_quote_event_at_or_after(
            [DecodedTick(1010, 1010000)],
            [DecodedTick(1010, 1020000)],
            1000,
        )
        self.assertEqual(any_event.side, "BID_AND_ASK")
        self.assertAlmostEqual(any_event.bid_price, 10.1)
        self.assertAlmostEqual(any_event.ask_price, 10.2)

    def test_08_both_sides_refreshed_is_diagnostic_only(self):
        bids = [DecodedTick(900, 1000000), DecodedTick(1010, 1010000)]
        asks = [DecodedTick(950, 1020000), DecodedTick(1030, 1030000)]
        states = causal_merge_bid_ask(bids, asks)
        diagnostic = first_both_sides_refreshed_diagnostic(
            states, 1000, diagnostic_window_ms=100
        )
        self.assertEqual(diagnostic.timestamp_ms, 1030)
        plan = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json")
        d = plan["generic_boundary_evidence"]["BOTH_SIDES_REFRESHED_AFTER_BOUNDARY"]
        self.assertEqual(d["classification"], "QUOTE_REFRESH_DIAGNOSTIC_ONLY")
        for key in (
            "candidate_entry_time",
            "fill_time",
            "stage_a_execution_truth",
            "mandatory_delay_assumption",
            "economic_fill_authority",
        ):
            self.assertFalse(d[key])

    def test_09_fifteen_minute_window_cannot_be_fill_authority(self):
        self.assertEqual(QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS, 900000)
        plan = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json")
        d = plan["generic_boundary_evidence"]["BOTH_SIDES_REFRESHED_AFTER_BOUNDARY"]
        self.assertEqual(d["diagnostic_window_ms"], 900000)
        self.assertFalse(d["economic_fill_authority"])
        self.assertEqual(
            plan["numeric_execution_rule_pre_capture"]["fill_delay_rule"],
            "NOT_FROZEN",
        )
        protocol = load("data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json")
        self.assertEqual(
            protocol["pre_capture_numeric_rules"]["both_sides_refresh_15m_window"],
            "DIAGNOSTIC_OBSERVATION_WINDOW_ONLY_NOT_FILL_AUTHORITY",
        )
        self.assertEqual(
            protocol["pre_capture_numeric_rules"]["mandatory_fill_delay"],
            "NONE_FROZEN",
        )

    def test_10_market_proxy_candidate_timing_and_hashes_unchanged(self):
        c006 = load("discovery/candidates/V2-C006.json")
        c012 = load("discovery/candidates/V2-C012.json")
        self.assertEqual(
            c006["spec_hash"],
            "75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49",
        )
        self.assertEqual(c006["entry"]["price"], "next_valid_M15_open")
        self.assertEqual(c006["entry"]["type"], "MARKET_PROXY")
        self.assertEqual(c006["timing"]["entry"], "NEXT_VALID_M15_OPEN")
        self.assertEqual(
            c012["spec_hash"],
            "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845",
        )
        self.assertEqual(c012["entry"]["price"], "NAS100_next_common_valid_M15_open")
        self.assertEqual(c012["entry"]["type"], "SINGLE_LEG_MARKET_PROXY")
        self.assertEqual(c012["timing"]["entry"], "NEXT_COMMON_VALID_M15_OPEN")

    def test_11_calibration_protocol_is_frozen_pre_outcome_and_forbids_candidate_inputs(self):
        p = load("data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json")
        self.assertEqual(p["status"], "FROZEN_PRE_OUTCOME_BEFORE_TIER1_V3_CAPTURE")
        self.assertEqual(
            p["allowed_conclusion_states"],
            ["VERIFIED_APPLICABLE_RULE", "CONSERVATIVE_BOUND", "UNRESOLVED"],
        )
        forbidden = set(p["forbidden_inputs"])
        for required in (
            "C006_SIGNALS","C012_SIGNALS","C006_RETURNS","C012_RETURNS",
            "C006_PNL","C012_PNL","ANY_CANDIDATE_OUTCOME","PROTECTED_FORWARD_EVIDENCE",
        ):
            self.assertIn(required, forbidden)
        self.assertEqual(p["research_state_at_freeze"]["economic_outcomes_opened"], 0)
        self.assertEqual(p["research_state_at_freeze"]["v2_attempts_used"], 0)
        self.assertFalse(p["research_state_at_freeze"]["protected_evidence_opened"])

    def test_12_protocol_requires_adverse_bound_or_unresolved(self):
        p = load("data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json")
        rules = "\n".join(p["conservative_rule_requirements"])
        self.assertIn("cannot falsely promote", rules)
        self.assertIn("reasonable uncertainty can change sign", rules)
        self.assertIn("UNRESOLVED", rules)
        self.assertIn(
            "If reasonable execution-cost uncertainty can change economic sign, classify COST_UNRESOLVED.",
            p["selection_process"],
        )

    def test_13_runtime_is_quote_evidence_only_not_candidate_economic_replay(self):
        runtime = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        self.assertNotIn("c006_replay_intents", runtime)
        self.assertNotIn("c012_replay_intents", runtime)
        self.assertNotIn("tier1_candidate_replay", runtime)
        self.assertIn("EVIDENCE_ONLY_NO_EXECUTION_FILL_AUTHORITY", runtime)
        self.assertIn("QUOTE_REFRESH_DIAGNOSTIC_ONLY", runtime)
        self.assertIn('"execution_fill_rule_frozen":False', runtime)
        self.assertIn('"candidate_market_proxy_mutated":False', runtime)

    def test_14_close_boundary_evidence_is_preserved_but_not_mixed_into_proxy(self):
        plan = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json")
        close = plan["generic_boundary_evidence"]["completed_bar_close_boundary"]
        self.assertTrue(close["causal_state_at_or_before_close"])
        self.assertTrue(close["quote_ages"])
        self.assertTrue(close["first_bid_event_at_or_after_close_boundary"])
        self.assertTrue(close["first_ask_event_at_or_after_close_boundary"])
        self.assertFalse(close["post_close_quote_mixed_into_frozen_close_proxy"])
        self.assertFalse(close["evidence_is_fill_rule"])

    def test_15_v3_raw_acquisition_preserves_v2_core_domain(self):
        v2 = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V2.json")
        v3 = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json")
        self.assertEqual(v3["targets"], v2["targets"])
        self.assertEqual(v3["quote_types"], v2["quote_types"])
        self.assertEqual(v3["development_interval"], v2["development_interval"])
        for key in ("timezone","weekday_envelope_local","weekday_rule","holidays","early_closes","full_session_tape","no_signal_conditioned_windows","no_return_conditioned_windows"):
            self.assertEqual(v3["acquisition_domain"][key], v2["acquisition_domain"][key])

    def test_16_active_plan_is_v3_and_resume_binding_changes(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(
            state["tier1_cost_evidence_plan_authority"],
            "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json",
        )
        v2 = cost_resume_contract(
            ROOT / "data/M6_TIER1_COST_EVIDENCE_PLAN_V2.json",
            tool_version="MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V2",
        )
        v3 = cost_resume_contract(
            ROOT / "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json",
            tool_version="MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3",
        )
        self.assertNotEqual(v2["plan_file_sha256"], v3["plan_file_sha256"])
        self.assertNotEqual(v2["binding_sha256"], v3["binding_sha256"])
        self.assertEqual(v3["schema"], "mxm.greenfield.v2.m6-cost-resume-contract.v3")

    def test_17_v3_package_source_set_contains_plan_and_protocol(self):
        self.assertIn("data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json", COST_PACKAGE_FILES)
        self.assertIn(
            "data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json",
            COST_PACKAGE_FILES,
        )
        self.assertNotIn("data/M6_TIER1_COST_EVIDENCE_PLAN_V2.json", COST_PACKAGE_FILES)

    def test_18_current_state_and_research_invariants_remain_zero(self):
        s = load("CURRENT_STATE.json")
        ledger = [
            json.loads(x) for x in (ROOT / "discovery/ledger.jsonl").read_text().splitlines()
            if x.strip()
        ]
        self.assertEqual(s["phase"], "PRIMARY_WAVE_FROZEN_PRE_M6")
        self.assertEqual(s["pre_m6_operational_state"], "TIER1_V3_QUOTE_CAPTURE_READY")
        self.assertEqual(s["economic_outcomes_opened"], 0)
        self.assertEqual(s["v2_attempts_used"], 0)
        self.assertEqual(s["v2_evaluated_identities"], 0)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["m6"]["economics_run"])
        self.assertEqual(s["m6"]["status"], "PENDING")
        self.assertFalse(any(x["entry_type"] == "RESULT_RECORDED" for x in ledger))

    def test_19_active_readiness_is_v3_and_still_blocks_tier1_on_cost(self):
        r = load("data/PRIMARY_WAVE_02_PRE_M6_READINESS_V3.json")
        self.assertEqual(
            r["tier1_cost_capture"]["active_plan"],
            "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json",
        )
        self.assertEqual(
            r["tier1_cost_capture"]["both_sides_refreshed_after_boundary"],
            "QUOTE_REFRESH_DIAGNOSTIC_ONLY",
        )
        self.assertFalse(r["tier1_cost_capture"]["diagnostic_window_is_fill_authority"])
        self.assertFalse(r["tier1_cost_capture"]["candidate_market_proxy_mutated"])
        self.assertEqual(
            r["candidates"]["V2-C006"]["m6_stage_a_readiness"],
            "BLOCKED_DISCOVERY_COST_EVIDENCE",
        )
        self.assertEqual(
            r["candidates"]["V2-C012"]["m6_stage_a_readiness"],
            "BLOCKED_DISCOVERY_COST_EVIDENCE",
        )

    def test_20_deployment_output_is_v3_and_v2_work_is_not_migrated(self):
        source = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        self.assertIn('tier1_us500_nas100_v3', source)
        self.assertIn('MXM_M6_TIER1_COST_EVIDENCE_V3', source)
        plan = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json")
        self.assertEqual(
            plan["resume_contract_binding"]["v2_migration"],
            "DISABLED_USER_HAS_NOT_RUN_V2_START_V3_CLEAN",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
