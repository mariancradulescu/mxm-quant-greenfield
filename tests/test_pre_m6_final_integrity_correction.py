import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from m6.cost_evidence import (
    POST_BOUNDARY_MAX_WAIT_MS,
    DecodedTick,
    causal_merge_bid_ask,
    cost_resume_contract,
    first_fresh_two_sided_state_at_or_after,
    prepare_contract_bound_resume,
    quote_state_at_or_before,
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
        days = weekday_sessions(cal, date(2024, 10, 24), 25)
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

    def test_11_pre_boundary_and_post_boundary_executable_are_distinct(self):
        bids = [DecodedTick(900, 1000000), DecodedTick(1010, 1010000)]
        asks = [DecodedTick(950, 1020000), DecodedTick(1020, 1030000)]
        states = causal_merge_bid_ask(bids, asks)
        pre = quote_state_at_or_before(states, 1000)
        self.assertEqual(pre.bid_timestamp_ms, 900)
        self.assertEqual(pre.ask_timestamp_ms, 950)
        post = first_fresh_two_sided_state_at_or_after(states, 1000, max_wait_ms=100)
        self.assertEqual(post.timestamp_ms, 1020)
        self.assertGreaterEqual(post.bid_timestamp_ms, 1000)
        self.assertGreaterEqual(post.ask_timestamp_ms, 1000)

    def test_12_stale_opposite_side_cannot_make_post_boundary_execution(self):
        bids = [DecodedTick(900, 1000000), DecodedTick(1010, 1010000)]
        asks = [DecodedTick(950, 1020000)]
        states = causal_merge_bid_ask(bids, asks)
        with self.assertRaisesRegex(Exception, "fresh causal two-sided"):
            first_fresh_two_sided_state_at_or_after(states, 1000, max_wait_ms=100)

    def test_13_post_boundary_wait_is_prospectively_frozen_one_m15(self):
        self.assertEqual(POST_BOUNDARY_MAX_WAIT_MS, 900000)
        plan = load("data/M6_TIER1_COST_EVIDENCE_PLAN_V2.json")
        self.assertEqual(
            plan["spread_reconstruction"]["POST_BOUNDARY_EXECUTABLE"]["maximum_wait_ms"],
            900000,
        )
        self.assertEqual(
            plan["spread_reconstruction"]["POST_BOUNDARY_EXECUTABLE"]["interval_semantics"],
            "[boundary, boundary+15m)",
        )

    def test_14_0930_boundary_and_completed_close_distinction_are_implemented(self):
        source = (ROOT / "m6/cost_evidence_openapi.py").read_text(encoding="utf-8")
        self.assertIn("boundary=int(session.open_utc.timestamp()*1000)", source)
        self.assertIn('POST_BOUNDARY_EXECUTABLE_FRESH_TWO_SIDED', source)
        self.assertIn('NOT_USED_COMPLETED_BAR_CLOSE', source)
        self.assertIn("if boundary==close_ms", source)

    def test_15_resume_contract_contains_all_required_binding_fields(self):
        binding = cost_resume_contract(
            ROOT / "data/M6_TIER1_COST_EVIDENCE_PLAN_V2.json",
            tool_version="TEST_TOOL_V2",
        )
        required = {
            "plan_schema","plan_file_sha256","tool_version","development_interval",
            "protected_forward_boundary","target_symbol_ids","quote_types",
            "acquisition_domain_rule","binding_sha256",
        }
        self.assertEqual(set(binding), required)
        self.assertEqual(binding["target_symbol_ids"], {"NAS100":126,"US500":127})

    def test_16_resume_contract_mismatch_archives_and_starts_empty(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "tier1_v2"
            plan = ROOT / "data/M6_TIER1_COST_EVIDENCE_PLAN_V2.json"
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
