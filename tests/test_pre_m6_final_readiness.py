import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from m6._ctrader_capture_base import (
    PROTECTED_FORWARD_START,
    READ_ONLY_PROTO_REQUESTS,
    FORBIDDEN_MUTATION_PROTO_REQUESTS,
)
from m6.causal_conversion import (
    CausalConversionSeries,
    MissingCausalConversion,
    convert_to_eur,
)
from m6.cost_evidence import (
    HISTORICAL_MIN_INTERVAL_SECONDS,
    OFFICIAL_TICK_MAX_WINDOW_MS,
    COST_PACKAGE_FILES,
    DecodedTick,
    build_cost_pydroid_package,
    causal_merge_bid_ask,
    decode_ctrader_tick_page,
    next_tick_page_to_ms,
    quote_state_at_or_before,
    signal_blind_cash_session_windows,
    validate_tick_request_window,
    verified_resume_chunk,
)
from m6.session_replay import (
    NasdaqCashCalendar,
    observed_cash_bars,
    synchronized_observed_cash_bars,
)

ROOT=Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8"))


class PreM6FinalReadinessTests(unittest.TestCase):
    def test_01_usd_to_eur_uses_latest_completed_m15_only(self):
        s=CausalConversionSeries.from_rows("EURUSD",[
            {"time_utc":"2024-01-02T10:00:00Z","close":"1.25"},
            {"time_utc":"2024-01-02T10:15:00Z","close":"1.20"},
        ])
        result=convert_to_eur(100,"USD","2024-01-02T10:15:00Z",eurusd=s)
        self.assertAlmostEqual(result.amount_eur,80.0)
        self.assertEqual(result.source_bar_open_utc.isoformat(),"2024-01-02T10:00:00+00:00")
        self.assertEqual(result.source_completed_utc.isoformat(),"2024-01-02T10:15:00+00:00")

    def test_02_jpy_to_eur_uses_causal_eurjpy(self):
        s=CausalConversionSeries.from_rows("EURJPY",[
            {"time_utc":"2024-01-02T10:00:00Z","close":"130.0"},
        ])
        result=convert_to_eur(13000,"JPY","2024-01-02T10:15:00Z",eurjpy=s)
        self.assertAlmostEqual(result.amount_eur,100.0)
        self.assertEqual(result.source_symbol,"EURJPY")

    def test_03_future_conversion_observation_is_forbidden(self):
        s=CausalConversionSeries.from_rows("EURUSD",[
            {"time_utc":"2024-01-02T10:00:00Z","close":"1.25"},
        ])
        with self.assertRaises(MissingCausalConversion):
            convert_to_eur(100,"USD","2024-01-02T10:14:59Z",eurusd=s)

    def test_04_missing_causal_conversion_blocks(self):
        with self.assertRaises(MissingCausalConversion):
            convert_to_eur(100,"USD","2024-01-02T10:15:00Z",eurusd=None)

    def test_05_current_conversion_chain_membership_not_mandatory_when_series_passes(self):
        e=load("evidence/PRE_M6_SESSION_CONVERSION_STAGEB_V2.json")
        self.assertEqual(e["conversion_evidence"]["price_conversion_gate"]["USD_to_EUR"],"PASS")
        self.assertEqual(e["conversion_evidence"]["price_conversion_gate"]["JPY_to_EUR"],"PASS")
        self.assertEqual(
            e["conversion_evidence"]["historical_current_chain_membership_requirement"],
            "NOT_REQUIRED_WHEN_FROZEN_CAUSAL_SERIES_ALTERNATIVE_IS_SATISFIED",
        )
        self.assertTrue(e["conversion_evidence"]["economic_conversion_adapter_ready"])

    def test_06_tick_page_absolute_plus_delta_decoding(self):
        rows=[
            {"timestamp":1000,"tick":1000000},
            {"timestamp":100,"tick":999000},
            {"timestamp":200,"tick":998000},
        ]
        got=decode_ctrader_tick_page(rows)
        self.assertEqual([x.timestamp_ms for x in got],[700,900,1000])
        self.assertEqual([x.raw_tick for x in got],[998000,999000,1000000])

    def test_07_tick_hasmore_pagination_moves_backward_and_stall_falls_back_1ms(self):
        page=[DecodedTick(700,1),DecodedTick(900,2),DecodedTick(1000,3)]
        self.assertEqual(next_tick_page_to_ms(page,current_from_ms=500),700)
        older=[DecodedTick(600,1),DecodedTick(700,2)]
        self.assertEqual(next_tick_page_to_ms(older,current_from_ms=500,previous_oldest_ms=700),600)
        stall=[DecodedTick(600,1),DecodedTick(650,2)]
        self.assertEqual(next_tick_page_to_ms(stall,current_from_ms=500,previous_oldest_ms=600),599)

    def test_08_official_tick_window_maximum_enforced(self):
        validate_tick_request_window(0,OFFICIAL_TICK_MAX_WINDOW_MS)
        with self.assertRaisesRegex(Exception,"one-week"):
            validate_tick_request_window(0,OFFICIAL_TICK_MAX_WINDOW_MS+1)

    def test_09_cost_windows_are_signal_blind_cash_session_envelopes_and_preprotected(self):
        windows=signal_blind_cash_session_windows(date(2026,9,14),date(2026,9,16))
        self.assertEqual([x.session_date for x in windows],["2026-09-14","2026-09-15","2026-09-16"])
        protected=int(datetime.fromisoformat(PROTECTED_FORWARD_START.replace("Z","+00:00")).timestamp()*1000)
        self.assertTrue(all(x.to_ms<protected for x in windows))
        self.assertTrue(all(x.to_ms-x.from_ms<OFFICIAL_TICK_MAX_WINDOW_MS for x in windows))

    def test_10_request_crossing_protected_boundary_is_rejected(self):
        protected=int(datetime.fromisoformat(PROTECTED_FORWARD_START.replace("Z","+00:00")).timestamp()*1000)
        with self.assertRaisesRegex(Exception,"protected-forward"):
            validate_tick_request_window(protected-1000,protected)

    def test_11_async_bid_ask_merge_is_strictly_causal(self):
        bids=[DecodedTick(1000,1000000),DecodedTick(2000,1100000)]
        asks=[DecodedTick(1500,1200000)]
        states=causal_merge_bid_ask(bids,asks)
        self.assertEqual(states[0].timestamp_ms,1500)
        self.assertAlmostEqual(states[0].bid,10.0)
        self.assertAlmostEqual(states[0].ask,12.0)
        self.assertEqual(states[0].bid_timestamp_ms,1000)
        self.assertEqual(states[0].ask_timestamp_ms,1500)
        self.assertEqual(states[-1].timestamp_ms,2000)
        self.assertEqual(states[-1].ask_timestamp_ms,1500)
        with self.assertRaises(Exception):
            quote_state_at_or_before(states,1499)

    def test_12_resume_reuse_requires_exact_sha(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"chunk.csv"
            p.write_bytes(b"abc")
            import hashlib
            h=hashlib.sha256(b"abc").hexdigest()
            self.assertTrue(verified_resume_chunk(p,h))
            self.assertFalse(verified_resume_chunk(p,"0"*64))

    def test_13_historical_tick_is_read_only_and_rate_pacing_is_below_official_ceiling(self):
        self.assertIn("ProtoOAGetTickDataReq",READ_ONLY_PROTO_REQUESTS)
        self.assertNotIn("ProtoOAGetTickDataReq",FORBIDDEN_MUTATION_PROTO_REQUESTS)
        self.assertGreaterEqual(HISTORICAL_MIN_INTERVAL_SECONDS,0.2)
        self.assertGreater(HISTORICAL_MIN_INTERVAL_SECONDS,1/5)

    def test_14_cost_runtime_contains_no_trading_request_tokens_and_fixed_targets_only(self):
        runtime=(ROOT/"m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        launcher=(ROOT/"m6/pydroid_cost_launcher.py").read_text(encoding="utf-8")
        for token in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"):
            self.assertNotIn(token,runtime)
            self.assertNotIn(token,launcher)
        self.assertIn("scope=accounts",launcher)
        self.assertNotIn("symbol_selector",launcher)
        plan=load("data/M6_TIER1_COST_EVIDENCE_PLAN_V1.json")
        self.assertEqual(plan["targets"]["US500"]["symbol_id"],127)
        self.assertEqual(plan["targets"]["NAS100"]["symbol_id"],126)

    def test_15_cash_session_replay_filters_calendar_but_never_fabricates_broker_events(self):
        cal=NasdaqCashCalendar(["2025-01-09"],["2025-07-03"])
        rows=[
            {"time_utc":"2025-01-08T14:15:00Z","open":"1","high":"1","low":"1","close":"1"}, # premarket
            {"time_utc":"2025-01-08T14:30:00Z","open":"1","high":"1","low":"1","close":"1"},
            {"time_utc":"2025-01-08T15:00:00Z","open":"1","high":"1","low":"1","close":"1"}, # gap at 09:45 remains absent
            {"time_utc":"2025-01-09T14:30:00Z","open":"1","high":"1","low":"1","close":"1"}, # official closure
        ]
        got=observed_cash_bars(rows,cal)
        self.assertEqual([x["time_utc"] for x in got],["2025-01-08T14:30:00Z","2025-01-08T15:00:00Z"])

    def test_16_c012_sync_replay_is_strict_observed_timestamp_intersection(self):
        cal=NasdaqCashCalendar([],[])
        left=[
            {"time_utc":"2025-01-08T14:30:00Z","open":"1","high":"1","low":"1","close":"1"},
            {"time_utc":"2025-01-08T14:45:00Z","open":"1","high":"1","low":"1","close":"1"},
        ]
        right=[
            {"time_utc":"2025-01-08T14:30:00Z","open":"2","high":"2","low":"2","close":"2"},
        ]
        got=synchronized_observed_cash_bars(left,right,cal)
        self.assertEqual(len(got),1)
        self.assertEqual(got[0][0]["time_utc"],"2025-01-08T14:30:00Z")

    def test_17_reference_calendar_contains_special_closure_and_early_close(self):
        c=load("data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V1.json")
        self.assertIn("2025-01-09",c["closures"])
        self.assertIn("2022-11-25",c["early_closes"])
        self.assertIn("2025-07-03",c["early_closes"])
        self.assertNotIn("2026-09-17",c["closures"]+c["early_closes"])

    def test_18_candidate_specific_readiness_has_no_global_all_seven_gate(self):
        r=load("data/PRIMARY_WAVE_02_PRE_M6_READINESS_V1.json")
        self.assertEqual(r["status"],"CANDIDATE_SPECIFIC_NO_GLOBAL_ALL_SEVEN_GATE")
        self.assertEqual(r["candidates"]["V2-C006"]["m6_stage_a_readiness"],"BLOCKED_DISCOVERY_COST_EVIDENCE")
        self.assertEqual(r["candidates"]["V2-C012"]["m6_stage_a_readiness"],"BLOCKED_DISCOVERY_COST_EVIDENCE")
        self.assertEqual(r["candidates"]["V2-C008"]["m6_stage_a_readiness"],"BLOCKED_C008_HISTORICAL_CONTINUOUS_CONSTRUCTION")
        self.assertEqual(r["ready_candidates"],[])

    def test_19_c008_c010_c011_blockers_do_not_change_c006_c012_gate_state(self):
        r=load("data/PRIMARY_WAVE_02_PRE_M6_READINESS_V1.json")["candidates"]
        self.assertNotIn("C008",r["V2-C006"]["m6_stage_a_readiness"])
        self.assertNotIn("C010",r["V2-C012"]["m6_stage_a_readiness"])
        self.assertNotIn("C011",r["V2-C006"]["m6_stage_a_readiness"])

    def test_20_future_wave_policy_frozen_before_first_outcome_and_creates_no_candidates(self):
        p=load("discovery/FUTURE_WAVE_OPPORTUNITY_COVERAGE_POLICY_V1.json")
        self.assertEqual(p["status"],"FROZEN_BEFORE_FIRST_V2_ECONOMIC_OUTCOME")
        self.assertFalse(p["evidence_and_attempt_accounting"]["new_candidate_identity_created_by_this_artifact"])
        self.assertFalse(p["evidence_and_attempt_accounting"]["economic_outcome_opened_by_this_artifact"])
        self.assertIn("PRIMARY_WAVE_02_IS_NOT_FINAL_BOT_UNIVERSE",p["anti_anchor_law"])
        self.assertTrue(p["hard21"]["not_per_candidate_quota"])

    def test_21_future_structural_universe_has_no_economic_ranking_fields(self):
        u=load("data/FUTURE_BROKER_STRUCTURAL_UNIVERSE_V1.json")
        self.assertFalse(u["scope"]["full_broker_universe_claimed"])
        self.assertEqual(u["scope"]["enabled_products"],49)
        self.assertFalse(u["scope"]["contains_economic_fields"])
        banned={"pnl","return","returns","sharpe","rank","ranking","performance","score","expected_return"}
        def walk(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    self.assertNotIn(str(k).lower(),banned)
                    walk(v)
            elif isinstance(value,list):
                for x in value: walk(x)
        walk(u["products"])

    def test_22_no_additional_candidate_identity_or_attempt_result_created(self):
        candidates=sorted((ROOT/"discovery/candidates").glob("V2-C*.json"))
        ids=[json.loads(p.read_text())["id"] for p in candidates]
        self.assertEqual(ids,[f"V2-C{i:03d}" for i in range(1,13)])
        state=load("CURRENT_STATE.json")
        ledger=[json.loads(x) for x in (ROOT/"discovery/ledger.jsonl").read_text().splitlines() if x.strip()]
        self.assertEqual(state["economic_outcomes_opened"],0)
        self.assertEqual(state["v2_attempts_used"],0)
        self.assertEqual(state["v2_evaluated_identities"],0)
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(any(x["entry_type"]=="RESULT_RECORDED" for x in ledger))

    def test_23_cost_pydroid_package_is_deterministic_and_secret_free_source_set(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"a.zip"; b=Path(td)/"b.zip"
            ha=build_cost_pydroid_package(ROOT,a)
            hb=build_cost_pydroid_package(ROOT,b)
            self.assertEqual(ha,hb)
            import zipfile
            with zipfile.ZipFile(a) as zf:
                self.assertEqual(set(zf.namelist()),set(COST_PACKAGE_FILES))
                self.assertNotIn(".m6_cost_evidence_work", "\n".join(zf.namelist()))

    def test_24_cost_source_provenance_has_2022_official_commission_policy_and_tick_api(self):
        s=load("evidence/TIER1_COST_EVIDENCE_SOURCES_V1.json")
        ids={x["source_id"] for x in s["sources"]}
        self.assertIn("PEPPERSTONE_EU_COSTS_2022_V2",ids)
        self.assertIn("CTRADER_HISTORICAL_TICK_DATA_CURRENT",ids)
        self.assertEqual(
            s["tier1_component_states_before_tick_capture"]["US500"]["separate_commission"],
            "VERIFIED_NO_SEPARATE_INDEX_COMMISSION_EMBEDDED_IN_SPREAD_POLICY_2022_AND_CURRENT",
        )
        self.assertEqual(
            s["tier1_component_states_before_tick_capture"]["NAS100"]["historical_spread"],
            "PENDING_BID_ASK_CAPTURE",
        )


if __name__=="__main__":
    unittest.main(verbosity=2)
