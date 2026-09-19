import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from m6.cost_evidence import (
    QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS,
    DecodedTick,
    causal_merge_bid_ask,
    causal_state_at_boundary,
    cost_resume_contract,
    first_both_sides_refreshed_diagnostic,
    prepare_contract_bound_resume,
)
from m6.session_replay import (
    NasdaqCashCalendar,
    cash_session_observations,
    exact_session_close_price,
    full_session_true_range_pct,
    prior_valid_true_ranges,
    synchronized_observed_cash_bars,
)
from m6.tier1_candidate_replay import c006_replay_intents

ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def session_rows(calendar, day, *, open_price=100.0, close_price=100.0):
    session = calendar.session(day)
    if session is None:
        return []
    rows = []
    opens = calendar.expected_m15_opens(day)
    for i, opened in enumerate(opens):
        op = open_price if i == 0 else 100.0
        cl = close_price if i == len(opens) - 1 else 100.0
        rows.append({
            "time_utc": iso(opened),
            "open": str(op),
            "high": str(max(op, cl, 101.0)),
            "low": str(min(op, cl, 99.0)),
            "close": str(cl),
        })
    return rows


def weekday_sessions(calendar, start, count):
    out = []
    cursor = start
    while len(out) < count:
        if calendar.session(cursor) is not None:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


class PreM6FinalIntegrityCorrectionTests(unittest.TestCase):
    def test_01_calendar_v2_full_2025_corrections_and_carter(self):
        c = load("data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json")
        self.assertTrue(c["audit_summary"]["full_interval_reaudited"])
        for day in ("2025-11-27", "2025-12-25", "2025-01-09"):
            self.assertIn(day, c["closures"])
        for day in ("2025-11-28", "2025-12-24"):
            self.assertIn(day, c["early_closes"])

    def test_02_calendar_representative_early_closes_2022_2025(self):
        c = load("data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json")
        expected = {
            "2022-11-25",
            "2023-07-03",
            "2023-11-24",
            "2024-07-03",
            "2024-11-29",
            "2024-12-24",
            "2025-07-03",
            "2025-11-28",
            "2025-12-24",
        }
        self.assertTrue(expected <= set(c["early_closes"]))

    def test_03_calendar_all_2026_holidays_through_development_end(self):
        c = load("data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json")
        expected = {
            "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
            "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
        }
        actual = {x for x in c["closures"] if x.startswith("2026-")}
        self.assertEqual(actual, expected)
        self.assertFalse(any(x.startswith("2026-") for x in c["early_closes"]))

    def _calendar_v2(self):
        return NasdaqCashCalendar.from_artifact(
            ROOT / "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json"
        )

    def _c006_rows(self, *, session_count=23, gap_pct=0.03):
        cal = self._calendar_v2()
        days = weekday_sessions(cal, date(2024, 1, 2), session_count)
        rows = []
        for i, day in enumerate(days):
            rows.extend(session_rows(
                cal,
                day,
                open_price=(100.0 * (1.0 + gap_pct) if i == len(days) - 1 else 100.0),
                close_price=100.0,
            ))
        return cal, days, rows

    def test_04_c006_missing_exact_0930_open_blocks_current_session(self):
        cal, days, rows = self._c006_rows()
        current = cal.session(days[-1])
        rows = [r for r in rows if r["time_utc"] != iso(current.open_utc)]
        intents = c006_replay_intents(rows, cal)
        self.assertFalse(any(x.decision_utc.date() == current.open_utc.date() for x in intents))

    def test_05_c006_missing_1545_regular_prior_close_blocks_gap(self):
        cal, days, rows = self._c006_rows()
        prior = cal.session(days[-2])
        self.assertFalse(prior.early_close)
        rows = [r for r in rows if r["time_utc"] != iso(prior.final_m15_open_utc)]
        intents = c006_replay_intents(rows, cal)
        current = cal.session(days[-1])
        self.assertFalse(any(x.decision_utc == current.open_utc + timedelta(minutes=15) for x in intents))

    def test_06_c006_missing_1245_early_close_prior_bar_blocks_gap(self):
        # 2024-11-29 is an official 13:00 ET early close; 2024-12-02 is next session.
        cal = self._calendar_v2()
        days = weekday_sessions(cal, date(2024, 10, 24), 32)
        self.assertIn(date(2024, 11, 29), days)
        current_day = date(2024, 12, 2)
        self.assertIn(current_day, days)
        rows = []
        for day in days:
            rows.extend(session_rows(
                cal, day,
                open_price=103.0 if day == current_day else 100.0,
                close_price=100.0,
            ))
        prior = cal.session(date(2024, 11, 29))
        self.assertTrue(prior.early_close)
        self.assertEqual(prior.final_m15_open_utc.astimezone(NY).strftime("%H:%M"), "12:45")
        rows = [r for r in rows if r["time_utc"] != iso(prior.final_m15_open_utc)]
        intents = c006_replay_intents(rows, cal)
        current = cal.session(current_day)
        self.assertFalse(any(x.decision_utc == current.open_utc + timedelta(minutes=15) for x in intents))

    def test_07_incomplete_prior_session_cannot_contribute_atr_true_range(self):
        cal, days, rows = self._c006_rows(session_count=6)
        obs = cash_session_observations(rows, cal)
        target = days[3]
        internal = cal.expected_m15_opens(target)[7]
        rows2 = [r for r in rows if r["time_utc"] != iso(internal)]
        obs2 = cash_session_observations(rows2, cal)
        self.assertIsNotNone(full_session_true_range_pct(obs, cal, target))
        self.assertIsNone(full_session_true_range_pct(obs2, cal, target))

    def test_08_c006_can_look_farther_back_for_20_valid_complete_sessions(self):
        cal, days, rows = self._c006_rows(session_count=25)
        # Make one historical ATR session incomplete while retaining enough older complete sessions.
        bad_day = days[-10]
        internal = cal.expected_m15_opens(bad_day)[5]
        rows = [r for r in rows if r["time_utc"] != iso(internal)]
        obs = cash_session_observations(rows, cal)
        values = prior_valid_true_ranges(obs, cal, days[-1], count=20)
        self.assertEqual(len(values), 20)
        self.assertIsNone(full_session_true_range_pct(obs, cal, bad_day))

    def test_09_complete_regular_and_early_close_expected_grids(self):
        cal = self._calendar_v2()
        regular = date(2024, 11, 27)
        early = date(2024, 11, 29)
        rows = session_rows(cal, regular) + session_rows(cal, early)
        obs = cash_session_observations(rows, cal)
        self.assertEqual(len(obs[regular].expected_opens), 26)
        self.assertTrue(obs[regular].complete_grid)
        self.assertEqual(len(obs[early].expected_opens), 14)
        self.assertTrue(obs[early].complete_grid)
        self.assertEqual(obs[regular].session.final_m15_open_utc.astimezone(NY).strftime("%H:%M"), "15:45")
        self.assertEqual(obs[early].session.final_m15_open_utc.astimezone(NY).strftime("%H:%M"), "12:45")
        self.assertEqual(exact_session_close_price(obs, regular), 100.0)
        self.assertEqual(exact_session_close_price(obs, early), 100.0)

    def test_10_c012_sync_respects_corrected_closure_and_early_close(self):
        cal = self._calendar_v2()
        rows = [
            {"time_utc": iso(datetime(2025,11,27,9,30,tzinfo=NY)), "open":"1","high":"1","low":"1","close":"1"},
            {"time_utc": iso(datetime(2025,11,28,9,30,tzinfo=NY)), "open":"1","high":"1","low":"1","close":"1"},
            {"time_utc": iso(datetime(2025,11,28,12,45,tzinfo=NY)), "open":"1","high":"1","low":"1","close":"1"},
            {"time_utc": iso(datetime(2025,11,28,13,0,tzinfo=NY)), "open":"1","high":"1","low":"1","close":"1"},
        ]
        got = synchronized_observed_cash_bars(rows, rows, cal)
        stamps = [a["time_utc"] for a,_ in got]
        self.assertEqual(stamps, [rows[1]["time_utc"], rows[2]["time_utc"]])

    def test_11_boundary_state_can_keep_pre_boundary_sides(self):
        bids = [DecodedTick(900, 1000000), DecodedTick(1010, 1010000)]
        asks = [DecodedTick(950, 1020000), DecodedTick(1020, 1030000)]
        state = causal_state_at_boundary(bids, asks, 1000)
        self.assertEqual(state.bid_timestamp_ms, 900)
        self.assertEqual(state.ask_timestamp_ms, 950)
        self.assertEqual(state.bid_age_ms, 100)
        self.assertEqual(state.ask_age_ms, 50)
        self.assertEqual(state.availability, "CAUSAL_TWO_SIDED_AVAILABLE")

    def test_12_both_sides_refresh_is_diagnostic_only(self):
        bids = [DecodedTick(900, 1000000), DecodedTick(1010, 1010000)]
        asks = [DecodedTick(950, 1020000), DecodedTick(1020, 1030000)]
        states = causal_merge_bid_ask(bids, asks)
        diagnostic = first_both_sides_refreshed_diagnostic(
            states, 1000, diagnostic_window_ms=100
        )
        self.assertEqual(diagnostic.timestamp_ms, 1020)
        plan = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json")
        d = plan["generic_boundary_evidence"]["BOTH_SIDES_REFRESHED_AFTER_BOUNDARY"]
        self.assertEqual(d["classification"], "QUOTE_REFRESH_DIAGNOSTIC_ONLY")
        self.assertFalse(d["economic_fill_authority"])

    def test_13_refresh_window_is_diagnostic_not_fill_authority(self):
        self.assertEqual(QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS, 900000)
        plan = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json")
        d = plan["generic_boundary_evidence"]["BOTH_SIDES_REFRESHED_AFTER_BOUNDARY"]
        self.assertEqual(d["diagnostic_window_ms"], 900000)
        self.assertFalse(d["candidate_entry_time"])
        self.assertFalse(d["fill_time"])
        self.assertFalse(d["mandatory_delay_assumption"])

    def test_14_0930_boundary_and_close_evidence_are_implemented_without_fill_claim(self):
        source = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        self.assertIn("boundary=int(session.open_utc.timestamp()*1000)", source)
        self.assertIn("CAUSAL_TWO_SIDED_AVAILABLE", source)
        self.assertIn("QUOTE_REFRESH_DIAGNOSTIC_ONLY", source)
        self.assertIn('"SESSION_CLOSE_BOUNDARY" if boundary==close_ms', source)
        self.assertNotIn("POST_BOUNDARY_EXECUTABLE_FRESH_TWO_SIDED", source)

    def test_15_resume_contract_contains_all_required_binding_fields(self):
        binding = cost_resume_contract(
            ROOT / "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json",
            tool_version="TEST_TOOL_V3",
        )
        required = {
            "schema","plan_schema","plan_file_sha256","tool_version","development_interval",
            "protected_forward_boundary","target_symbol_ids","quote_types",
            "acquisition_domain_rule","binding_sha256",
        }
        self.assertEqual(set(binding), required)
        self.assertEqual(binding["schema"], "mxm.greenfield.v2.m6-cost-resume-contract.v3")
        self.assertEqual(binding["target_symbol_ids"], {"NAS100":126,"US500":127})

    def test_16_resume_contract_mismatch_archives_and_starts_empty(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "tier1_v3"
            plan = ROOT / "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json"
            first = cost_resume_contract(plan, tool_version="TOOL_A")
            resume_path, state, archived = prepare_contract_bound_resume(work, first)
            self.assertIsNone(archived)
            state["completed"]["US500:BID:2024-01-02"] = {"sha256":"x"}
            resume_path.write_text(json.dumps(state), encoding="utf-8")
            (work / "chunks").mkdir()
            (work / "chunks" / "old").write_text("stale", encoding="utf-8")

            second = cost_resume_contract(plan, tool_version="TOOL_B")
            resume_path2, state2, archived2 = prepare_contract_bound_resume(work, second)
            self.assertIsNotNone(archived2)
            self.assertTrue((archived2 / "chunks" / "old").is_file())
            self.assertEqual(state2["completed"], {})
            self.assertEqual(state2["contract"], second)
            self.assertTrue(resume_path2.is_file())

    def test_17_success_output_directory_is_recreated_clean(self):
        source = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        finalize = source[source.index("def _finalize"):source.index("def run(self)")]
        self.assertIn("shutil.rmtree(self.output_dir)", finalize)
        self.assertIn("self.output_dir.mkdir(parents=True)", finalize)

    def test_18_commission_continuity_is_not_overclaimed(self):
        e = load("evidence/TIER1_COST_EVIDENCE_SOURCES_V2.json")
        for symbol in ("US500","NAS100"):
            state = e["commission_continuity_assessment"][symbol]
            self.assertEqual(
                state["state"],
                "PARTIAL_VERIFIED_DOCUMENTED_2022_2023_2024_2025_CURRENT",
            )
            self.assertEqual(
                state["exact_intervening_point_in_time_continuity"],
                "UNRESOLVED",
            )
            self.assertEqual(state["conservative_unknown_period_commission_bound"], "NOT_FROZEN")

    def test_19_timestamp_provenance_correction_binds_git_authority(self):
        e = load("evidence/PRE_M6_ARTIFACT_TIMESTAMP_PROVENANCE_CORRECTION_V1.json")
        by_path = {x["artifact_path"]: x for x in e["correction_entries"]}
        expected = {
            "discovery/FUTURE_WAVE_OPPORTUNITY_COVERAGE_POLICY_V1.json":
                ("7842cdfcb1d0ce2a3f5f631a0a52593a4c8fa2f5","2026-09-18T09:08:25Z"),
            "data/FUTURE_BROKER_STRUCTURAL_UNIVERSE_V1.json":
                ("5e65ebbbea9a0e25824e44d7c5418d00a1f093a6","2026-09-18T09:11:42Z"),
            "data/M6_TIER1_COST_EVIDENCE_PLAN_V1.json":
                ("0a9a0ba31182e263effad9c739d1a75ebaa9cd8b","2026-09-18T09:16:08Z"),
            "evidence/TIER1_COST_EVIDENCE_SOURCES_V1.json":
                ("cc24424d3fab1e7d0e1a6d0f3e9b2cc897d23b5f","2026-09-18T09:20:29Z"),
            "data/PRIMARY_WAVE_02_PRE_M6_READINESS_V1.json":
                ("5fdf9dde9dfc32b1b711c3054b4da7c10a9c6e3d","2026-09-18T09:23:43Z"),
        }
        self.assertEqual(set(by_path), set(expected))
        for path, (sha, when) in expected.items():
            self.assertEqual(by_path[path]["introducing_commit_sha"], sha)
            self.assertEqual(by_path[path]["actual_git_commit_utc"], when)
            self.assertEqual(by_path[path]["semantic_order_authority"], "GIT_COMMIT_HISTORY")
        self.assertEqual(e["research_integrity"]["economic_outcomes_seen"], 0)
        self.assertEqual(e["research_integrity"]["attempts_consumed"], 0)

    def test_20_current_state_points_only_to_corrected_active_pre_m6_authorities(self):
        s = load("CURRENT_STATE.json")
        self.assertEqual(s["phase"], "PRIMARY_WAVE_FROZEN_PRE_M6")
        self.assertEqual(s["pre_m6_operational_state"], "C006_READY_C012_PREOPEN_SUPPLEMENT_REQUIRED_NO_ECONOMICS")
        self.assertEqual(
            s["future_wave_opportunity_coverage_authority"],
            "discovery/FUTURE_WAVE_OPPORTUNITY_COVERAGE_POLICY_V1.json",
        )
        self.assertEqual(
            s["future_broker_structural_universe_authority"],
            "data/FUTURE_BROKER_STRUCTURAL_UNIVERSE_V1.json",
        )
        self.assertEqual(
            s["reference_cash_session_calendar_authority"],
            "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json",
        )
        self.assertEqual(
            s["pre_m6_readiness_authority"],
            "data/PRIMARY_WAVE_02_PRE_M6_READINESS_V5.json",
        )
        self.assertEqual(
            s["tier1_cost_evidence_plan_authority"],
            "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json",
        )
        self.assertEqual(
            s["tier1_cost_evidence_sources_authority"],
            "evidence/TIER1_COST_EVIDENCE_SOURCES_V2.json",
        )
        self.assertEqual(
            s["pre_m6_timestamp_provenance_correction_authority"],
            "evidence/PRE_M6_ARTIFACT_TIMESTAMP_PROVENANCE_CORRECTION_V1.json",
        )
        self.assertEqual(
            s["pre_m6_final_integrity_correction_authority"],
            "data/PRE_M6_FINAL_INTEGRITY_CORRECTION_V1.json",
        )
        self.assertFalse(s["m6"]["auxiliary_evidence"]["m6_stage_a_economics_authorized"])
        self.assertFalse(s["m6"]["economics_run"])
        self.assertEqual(s["economic_outcomes_opened"], 0)
        self.assertEqual(s["v2_attempts_used"], 0)
        self.assertEqual(s["v2_evaluated_identities"], 0)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])

    def test_21_active_readiness_uses_corrected_calendar_cost_plan_and_commission_state(self):
        r = load("data/PRIMARY_WAVE_02_PRE_M6_READINESS_V4.json")
        self.assertEqual(
            r["authorities"]["reference_calendar"],
            "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json",
        )
        self.assertEqual(
            r["authorities"]["tier1_cost_plan"],
            "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json",
        )
        self.assertEqual(
            r["authorities"]["tier1_cost_sources"],
            "evidence/TIER1_COST_EVIDENCE_SOURCES_V2.json",
        )
        self.assertEqual(
            r["candidates"]["V2-C006"]["session_event_semantics"],
            "PASS_EXACT_0930_OPEN_EXACT_PRIOR_SCHEDULED_CLOSE_FULL_26_OR_14_BAR_ATR_SESSIONS_NO_SYNTHETIC_FILL",
        )
        self.assertEqual(
            r["candidates"]["V2-C006"]["discovery_cost_evidence"]["commission"],
            "BLOCKED_EXACT_INTERVENING_HISTORICAL_CONTINUITY_UNRESOLVED",
        )
        self.assertEqual(
            r["candidates"]["V2-C012"]["m6_stage_a_readiness"],
            "BLOCKED_DISCOVERY_COST_RULE",
        )
        self.assertEqual(r["ready_candidates"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
