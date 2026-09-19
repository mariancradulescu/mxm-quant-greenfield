import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from m6.cost_evidence import (
    QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS,
    BoundaryQuoteIndex,
    DecodedTick,
    COST_PACKAGE_FILES,
    causal_merge_bid_ask,
    causal_state_at_boundary,
    cost_resume_contract,
    migrate_compatible_resume_tool_version,
    prepare_contract_bound_resume,
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
        for key in ("timezone","weekday_envelope_local","weekday_rule","full_session_tape","no_signal_conditioned_windows","no_return_conditioned_windows"):
            self.assertEqual(v3["acquisition_domain"][key], v2["acquisition_domain"][key])
        self.assertIn("RAW ENVELOPE STILL REQUESTED", v3["acquisition_domain"]["holidays"])
        self.assertIn("RAW REGULAR ENVELOPE STILL REQUESTED", v3["acquisition_domain"]["early_closes"])

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

    def test_21_tick_decoder_correction_is_pre_outcome_and_tool_binding_bumped(self):
        e = load("evidence/PRE_M6_CTRADER_TICK_DELTA_DECODER_CORRECTION_V1.json")
        self.assertEqual(
            e["status"],
            "PRE_OUTCOME_IMPLEMENTATION_CORRECTION_AFTER_SAFE_CAPTURE_BLOCK",
        )
        self.assertEqual(e["research_state"]["economic_outcomes_opened"], 0)
        self.assertEqual(e["research_state"]["v2_attempts_used"], 0)
        self.assertFalse(e["research_state"]["protected_evidence_opened"])
        runtime = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        self.assertIn(
            'TOOL_VERSION = "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_COMPACT2_INDEXED"',
            runtime,
        )
        self.assertIn(
            "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_TICKDELTA1",
            runtime,
        )
        self.assertIn(
            "evidence/PRE_M6_CTRADER_TICK_DELTA_DECODER_CORRECTION_V1.json",
            COST_PACKAGE_FILES,
        )


    def test_22_pipeline_runtime_uses_one_live_connection_and_bounded_batch(self):
        runtime = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        transport = (ROOT / "m6/ctrader_transport.py").read_text(encoding="utf-8")
        self.assertIn("PIPELINE_BATCH_SIZE = 4", runtime)
        self.assertIn("self.transport.request_batch(", runtime)
        self.assertIn("min_interval_seconds=HISTORICAL_MIN_INTERVAL_SECONDS", runtime)
        self.assertIn("[PIPELINE FALLBACK]", runtime)
        self.assertIn("left=self._send_historical_batch", runtime)
        self.assertIn("right=self._send_historical_batch", runtime)
        self.assertIn("def request_batch(", transport)
        self.assertNotIn("ThreadPoolExecutor", runtime + transport)
        self.assertNotIn("multiprocessing", runtime + transport)

    def test_23_pipeline_tool_only_resume_migration_preserves_only_hash_verified_chunks(self):
        plan = ROOT / "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json"
        old_tool = "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_TICKDELTA1"
        new_tool = "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_COMPACT2_INDEXED"
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "tier1_us500_nas100_v3"
            old_binding = cost_resume_contract(plan, tool_version=old_tool)
            resume_path, state, archived = prepare_contract_bound_resume(work, old_binding)
            self.assertIsNone(archived)
            chunk = work / "chunks" / "US500" / "BID" / "2022-01-03.csv"
            chunk.parent.mkdir(parents=True, exist_ok=True)
            payload = b"time_utc,timestamp_ms,raw_tick,price\n"
            chunk.write_bytes(payload)
            sha = hashlib.sha256(payload).hexdigest()
            state["completed"]["US500:BID:2022-01-03"] = {
                "symbol": "US500",
                "quote_type": "BID",
                "session_date": "2022-01-03",
                "sha256": sha,
            }
            resume_path.write_text(json.dumps(state), encoding="utf-8")

            new_binding = cost_resume_contract(plan, tool_version=new_tool)
            migrated, count, previous = migrate_compatible_resume_tool_version(
                work,
                new_binding,
                allowed_previous_tool_versions=(old_tool,),
            )
            self.assertTrue(migrated)
            self.assertEqual(count, 1)
            self.assertEqual(previous, old_tool)
            after = json.loads(resume_path.read_text(encoding="utf-8"))
            self.assertEqual(after["contract"], new_binding)
            self.assertEqual(
                after["compatible_tool_migrations"][-1]["verified_chunk_count"], 1
            )

    def test_24_pipeline_resume_migration_refuses_bad_chunk_hash(self):
        plan = ROOT / "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json"
        old_tool = "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_TICKDELTA1"
        new_tool = "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_COMPACT1"
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "tier1_us500_nas100_v3"
            old_binding = cost_resume_contract(plan, tool_version=old_tool)
            resume_path, state, _ = prepare_contract_bound_resume(work, old_binding)
            chunk = work / "chunks" / "US500" / "BID" / "2022-01-03.csv"
            chunk.parent.mkdir(parents=True, exist_ok=True)
            chunk.write_bytes(b"actual")
            state["completed"]["US500:BID:2022-01-03"] = {
                "symbol": "US500",
                "quote_type": "BID",
                "session_date": "2022-01-03",
                "sha256": hashlib.sha256(b"different").hexdigest(),
            }
            resume_path.write_text(json.dumps(state), encoding="utf-8")
            new_binding = cost_resume_contract(plan, tool_version=new_tool)
            migrated, count, previous = migrate_compatible_resume_tool_version(
                work,
                new_binding,
                allowed_previous_tool_versions=(old_tool,),
            )
            self.assertFalse(migrated)
            self.assertEqual(count, 0)
            self.assertEqual(previous, old_tool)

    def test_25_pipeline_optimization_keeps_research_state_zero_and_raw_contract_unchanged(self):
        e = load("evidence/PRE_M6_TIER1_PIPELINE_THROUGHPUT_OPTIMIZATION_V1.json")
        self.assertFalse(e["raw_evidence_contract"]["acquisition_domain_changed"])
        self.assertFalse(e["raw_evidence_contract"]["target_symbols_changed"])
        self.assertFalse(e["raw_evidence_contract"]["quote_types_changed"])
        self.assertFalse(e["raw_evidence_contract"]["pagination_semantics_changed"])
        self.assertFalse(e["raw_evidence_contract"]["candidate_specs_changed"])
        self.assertEqual(e["research_state"]["economic_outcomes_opened"], 0)
        self.assertEqual(e["research_state"]["v2_attempts_used"], 0)
        self.assertEqual(e["research_state"]["result_recorded"], 0)
        self.assertFalse(e["research_state"]["protected_evidence_opened"])

    def test_26_pipeline_provenance_is_inside_pydroid_package_source_set(self):
        self.assertIn(
            "evidence/PRE_M6_TIER1_PIPELINE_THROUGHPUT_OPTIMIZATION_V1.json",
            COST_PACKAGE_FILES,
        )
        state = load("CURRENT_STATE.json")
        self.assertEqual(
            state["m6"]["auxiliary_evidence"]["tier1_cost_capture"]["tool_version"],
            "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_COMPACT2_INDEXED",
        )
        self.assertEqual(
            state["m6"]["auxiliary_evidence"]["tier1_cost_capture"]["pipeline_batch_size"],
            4,
        )


    def test_27_pipeline2_stability_correction_is_zero_economics_and_adaptive(self):
        e = load("evidence/PRE_M6_TIER1_PIPELINE_STABILITY_CORRECTION_V1.json")
        self.assertEqual(
            e["corrected_runtime"]["tool_version"],
            "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_PIPELINE2",
        )
        self.assertEqual(e["corrected_runtime"]["max_initial_batch_size"], 4)
        self.assertEqual(
            e["corrected_runtime"]["adaptive_fallback"],
            "4 -> 2 -> 1 on repeated batch failure",
        )
        self.assertFalse(e["corrected_runtime"]["raw_acquisition_contract_changed"])
        self.assertEqual(e["research_state"]["economic_outcomes_opened"], 0)
        self.assertEqual(e["research_state"]["v2_attempts_used"], 0)
        self.assertEqual(e["research_state"]["result_recorded"], 0)
        self.assertFalse(e["research_state"]["protected_evidence_opened"])
        self.assertIn(
            "evidence/PRE_M6_TIER1_PIPELINE_STABILITY_CORRECTION_V1.json",
            COST_PACKAGE_FILES,
        )


    def test_28_dns_resilient_pipeline3_preserves_v3_contract_and_zero_economics(self):
        e = load("evidence/PRE_M6_TIER1_DNS_RESILIENT_RECONNECT_CORRECTION_V1.json")
        self.assertEqual(
            e["corrected_runtime"]["tool_version"],
            "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_PIPELINE3_DNSCACHE1",
        )
        self.assertEqual(e["corrected_runtime"]["pipeline_batch_size"], 4)
        self.assertEqual(e["corrected_runtime"]["pipeline_fallback"], "4->2->1")
        self.assertEqual(
            e["corrected_runtime"]["automatic_network_recovery"]["maximum_seconds"],
            1800,
        )
        self.assertFalse(e["unchanged_research_contract"]["raw_acquisition_domain_changed"])
        self.assertFalse(e["unchanged_research_contract"]["candidate_specs_changed"])
        self.assertEqual(e["research_state"]["economic_outcomes_opened"], 0)
        self.assertEqual(e["research_state"]["v2_attempts_used"], 0)
        self.assertEqual(e["research_state"]["result_recorded"], 0)
        self.assertFalse(e["research_state"]["protected_evidence_opened"])
        self.assertIn(
            "evidence/PRE_M6_TIER1_DNS_RESILIENT_RECONNECT_CORRECTION_V1.json",
            COST_PACKAGE_FILES,
        )

    def test_29_current_state_activates_compact2_indexed_finalization(self):
        state = load("CURRENT_STATE.json")
        cap = state["m6"]["auxiliary_evidence"]["tier1_cost_capture"]
        self.assertEqual(
            cap["tool_version"],
            "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_COMPACT2_INDEXED",
        )
        self.assertEqual(
            cap["state"],
            "RAW_CAPTURE_COMPLETE_INDEXED_COMPACT_FINALIZATION_PENDING_USER_RUN",
        )
        self.assertEqual(
            cap["historical_bid_ask"],
            "CAPTURE_COMPLETE_4912_LOCAL_HASH_VERIFIED_CHUNKS",
        )
        self.assertFalse(cap["compact_transfer"]["raw_consolidated_csv_files_created"])
        self.assertTrue(cap["compact_transfer"]["raw_chunks_retained_locally"])
        self.assertFalse(cap["compact_transfer"]["raw_chunks_embedded_in_transfer_zip"])
        self.assertEqual(state["economic_outcomes_opened"], 0)
        self.assertEqual(state["v2_attempts_used"], 0)
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["m6"]["economics_run"])


    def test_30_compact2_accepts_hash_verified_compact1_resume_lineage(self):
        runtime = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        self.assertIn(
            '"MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_COMPACT1"',
            runtime,
        )
        state = load("CURRENT_STATE.json")
        self.assertIn(
            "COMPACT1",
            state["m6"]["auxiliary_evidence"]["tier1_cost_capture"]["resume_after_indexed_finalizer"],
        )


    def test_31_compact_finalizer_does_not_create_or_embed_multi_gb_raw_tapes(self):
        runtime = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        finalize = runtime[runtime.index("def _finalize"):runtime.index("def run(self)")]
        self.assertNotIn("_write_consolidated_tape(", finalize)
        self.assertNotIn('"raw_ticks"', finalize)
        self.assertIn('"raw_chunk_commitment.json"', finalize)
        self.assertIn('"raw_chunks_embedded_in_transfer_bundle":False', finalize)
        self.assertIn("[FINALIZE 1/4]", finalize)
        self.assertIn("[FINALIZE 4/4]", finalize)

    def test_32_compact_transfer_policy_is_pre_outcome_and_preserves_local_raw(self):
        e = load("evidence/PRE_M6_TIER1_COMPACT_TRANSFER_FINALIZATION_V1.json")
        self.assertTrue(e["corrected_transfer_contract"]["raw_chunks_retained_locally"])
        self.assertFalse(e["corrected_transfer_contract"]["raw_consolidated_csv_files_created"])
        self.assertFalse(e["corrected_transfer_contract"]["raw_bytes_embedded_in_transfer_zip"])
        self.assertEqual(e["corrected_transfer_contract"]["raw_capture_complete_chunks_expected"], 4912)
        self.assertEqual(e["research_state"]["economic_outcomes_opened"], 0)
        self.assertEqual(e["research_state"]["v2_attempts_used"], 0)
        self.assertFalse(e["research_state"]["protected_evidence_opened"])
        self.assertIn(
            "evidence/PRE_M6_TIER1_COMPACT_TRANSFER_FINALIZATION_V1.json",
            COST_PACKAGE_FILES,
        )

    def test_33_compact_finalizer_tool_version_is_active_and_pipeline3_is_migratable(self):
        runtime = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        self.assertIn(
            'TOOL_VERSION = "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_COMPACT1"',
            runtime,
        )
        self.assertIn(
            '"MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_PIPELINE3_DNSCACHE1"',
            runtime,
        )


    def test_34_indexed_boundary_lookup_matches_frozen_helpers(self):
        bids=[
            DecodedTick(900,1000000),
            DecodedTick(990,1005000),
            DecodedTick(1010,1010000),
            DecodedTick(1040,1015000),
        ]
        asks=[
            DecodedTick(850,1020000),
            DecodedTick(995,1025000),
            DecodedTick(1030,1030000),
            DecodedTick(1050,1035000),
        ]
        boundary=1000
        idx=BoundaryQuoteIndex(bids,asks)

        expected=causal_state_at_boundary(bids,asks,boundary)
        got=idx.causal_state_at_boundary(boundary)
        self.assertEqual(got,expected)

        self.assertEqual(
            idx.first_post_bid(boundary),
            first_tick_at_or_after(bids,boundary),
        )
        self.assertEqual(
            idx.first_post_ask(boundary),
            first_tick_at_or_after(asks,boundary),
        )
        self.assertEqual(
            idx.first_post_any(boundary),
            first_any_quote_event_at_or_after(bids,asks,boundary),
        )

        states=causal_merge_bid_ask(bids,asks)
        expected_refresh=first_both_sides_refreshed_diagnostic(
            states,boundary,diagnostic_window_ms=100
        )
        got_refresh=idx.both_sides_refreshed_diagnostic(
            boundary,diagnostic_window_ms=100
        )
        self.assertEqual(got_refresh,expected_refresh)

    def test_35_indexed_lookup_forbids_future_state_and_preserves_quote_age(self):
        idx=BoundaryQuoteIndex(
            [DecodedTick(900,1000000),DecodedTick(1100,1100000)],
            [DecodedTick(950,1020000),DecodedTick(1200,1200000)],
        )
        state=idx.causal_state_at_boundary(1000)
        self.assertEqual(state.bid_timestamp_ms,900)
        self.assertEqual(state.ask_timestamp_ms,950)
        self.assertEqual(state.bid_age_ms,100)
        self.assertEqual(state.ask_age_ms,50)
        self.assertNotEqual(state.bid_timestamp_ms,1100)
        self.assertNotEqual(state.ask_timestamp_ms,1200)

    def test_36_compact2_has_finalization_heartbeat_and_no_full_scan_helpers(self):
        runtime=(ROOT/"m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        writer=runtime[runtime.index("def _write_boundary_quotes"):runtime.index("def _finalize")]
        self.assertIn("BoundaryQuoteIndex(bid,ask)",writer)
        self.assertIn("[FINALIZE HEARTBEAT]",writer)
        self.assertIn("window_index%25==0",writer)
        self.assertNotIn("causal_merge_bid_ask(",writer)
        self.assertNotIn("causal_state_at_boundary(bid,ask,boundary)",writer)
        self.assertNotIn("first_tick_at_or_after(bid,boundary)",writer)

    def test_37_indexed_finalizer_correction_is_pre_outcome_and_packaged(self):
        e=load("evidence/PRE_M6_TIER1_COMPACT_FINALIZER_INDEXING_V1.json")
        self.assertEqual(
            e["corrected_runtime"]["tool_version"],
            "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_COMPACT2_INDEXED",
        )
        self.assertFalse(e["corrected_runtime"]["raw_reacquisition"])
        self.assertTrue(e["corrected_runtime"]["local_raw_chunks_reused"])
        self.assertEqual(
            e["corrected_runtime"]["boundary_lookup"],
            "BoundaryQuoteIndex using bisect",
        )
        self.assertEqual(e["research_state"]["economic_outcomes_opened"],0)
        self.assertEqual(e["research_state"]["v2_attempts_used"],0)
        self.assertFalse(e["research_state"]["protected_evidence_opened"])
        self.assertIn(
            "evidence/PRE_M6_TIER1_COMPACT_FINALIZER_INDEXING_V1.json",
            COST_PACKAGE_FILES,
        )



if __name__ == "__main__":
    unittest.main(verbosity=2)
