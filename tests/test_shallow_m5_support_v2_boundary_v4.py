from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

from research_core_v4 import shallow_m5_support_v2 as v2
from research_core_v4 import shallow_m5_support_v2_boundary_v4 as b4
from research_core_v4 import shallow_m5_support_v2_production_v4 as p4

ROOT = Path(__file__).resolve().parents[1]


def minute(iso: str) -> int:
    return v2.to_ms(iso) // 60000


class BoundaryV4Tests(unittest.TestCase):
    def ctx(self, from_utc="2026-08-20T00:00:00Z", to_utc="2026-08-26T23:55:00Z"):
        return v2.RequestContext(
            client_msg_id="test-v4",
            authenticated_account_id=12345,
            symbol_id=3,
            from_ms=v2.to_ms(from_utc),
            to_ms=v2.to_ms(to_utc),
        )

    def response(self, minutes, *, has_more=True, symbol=True, malformed_lower=False):
        r = v2.ProtoOAGetTrendbarsResV2(
            ctidTraderAccountId=12345,
            period=v2.M5_ENUM,
        )
        if symbol:
            r.symbolId = 3
        if has_more is not None:
            r.hasMore = bool(has_more)
        for idx, m in enumerate(minutes):
            bar = r.trendbar.add()
            bar.volume = 10
            bar.period = v2.M5_ENUM
            bar.utcTimestampInMinutes = int(m)
            if not (malformed_lower and idx == 0):
                bar.low = 100000
                bar.deltaOpen = 1
                bar.deltaHigh = 2
                bar.deltaClose = 1
        return r

    def test_exact_forensic_5000_3561_1439_hasmore_true_completes_one_page(self):
        lower_start = minute("2026-08-03T14:55:00Z")
        lower = [lower_start + 5*i for i in range(3561)]
        inside_end = minute("2026-08-26T23:55:00Z")
        inside = [inside_end - 5*(1438-i) for i in range(1439)]
        page = b4.normalize_bound_response(self.response(lower + inside), ctx=self.ctx(), digits=3)
        g = page.geometry
        self.assertEqual(g.raw_response_count, 5000)
        self.assertEqual(g.lower_overfetch_count, 3561)
        self.assertEqual(g.canonical_inside_count, 1439)
        self.assertEqual(g.raw_min_open_ms, v2.to_ms("2026-08-03T14:55:00Z"))
        self.assertEqual(g.raw_max_open_ms, v2.to_ms("2026-08-26T23:55:00Z"))
        self.assertTrue(page.has_more_present)
        self.assertTrue(page.has_more_value)
        self.assertEqual(len(page.canonical_rows), 1439)
        d = b4.pagination_decision_v4(
            ctx=self.ctx(), geometry=g,
            has_more_present=page.has_more_present,
            has_more_value=page.has_more_value,
            page_index=1,
        )
        self.assertTrue(d.complete)
        self.assertFalse(d.fail_closed)
        self.assertEqual(d.reason, "RAW_LOWER_BOUNDARY_REACHED")

    def test_lower_overfetch_filtered_before_price_decoding(self):
        c = self.ctx()
        lower = c.from_ms // 60000 - 5
        inside = c.from_ms // 60000
        page = b4.normalize_bound_response(
            self.response([lower, inside], malformed_lower=True),
            ctx=c, digits=3,
        )
        self.assertEqual(page.geometry.lower_overfetch_count, 1)
        self.assertEqual(len(page.canonical_rows), 1)

    def test_inside_interval_invalid_ohlc_still_fails(self):
        r = self.response([self.ctx().from_ms // 60000])
        r.trendbar[0].ClearField("low")
        with self.assertRaises(ValueError):
            b4.normalize_bound_response(r, ctx=self.ctx(), digits=3)

    def test_upper_boundary_overfetch_fails_closed(self):
        upper = self.ctx().to_ms // 60000 + 5
        with self.assertRaises(b4.BoundaryProtocolError) as cm:
            b4.normalize_bound_response(self.response([upper]), ctx=self.ctx(), digits=3)
        self.assertEqual(cm.exception.classification, "UPPER_BOUNDARY_OVERFETCH_PROTOCOL_FAILURE")

    def test_protected_forward_overfetch_fails_closed(self):
        protected = minute("2026-09-17T12:05:00Z")
        c = self.ctx(to_utc="2026-09-18T00:00:00Z")
        with self.assertRaises(b4.BoundaryProtocolError) as cm:
            b4.normalize_bound_response(self.response([protected]), ctx=c, digits=3)
        self.assertEqual(cm.exception.classification, "PROTECTED_FORWARD_LEAK")

    def test_raw_duplicate_timestamp_fails_closed(self):
        m = self.ctx().from_ms // 60000
        with self.assertRaises(b4.BoundaryProtocolError):
            b4.normalize_bound_response(self.response([m, m]), ctx=self.ctx(), digits=3)

    def test_raw_non_m5_aligned_timestamp_fails_closed(self):
        m = self.ctx().from_ms // 60000 + 1
        with self.assertRaises(b4.BoundaryProtocolError):
            b4.normalize_bound_response(self.response([m]), ctx=self.ctx(), digits=3)

    def test_exact_from_and_to_bars_included(self):
        c = self.ctx()
        p = b4.normalize_bound_response(
            self.response([c.from_ms//60000, c.to_ms//60000], has_more=False),
            ctx=c, digits=3,
        )
        self.assertEqual(len(p.canonical_rows), 2)
        self.assertEqual(p.geometry.lower_overfetch_count, 0)

    def test_lower_only_page_completes_as_no_historical_support(self):
        c = self.ctx()
        p = b4.normalize_bound_response(
            self.response([c.from_ms//60000-10, c.from_ms//60000-5]),
            ctx=c, digits=3,
        )
        d = b4.pagination_decision_v4(
            ctx=c, geometry=p.geometry,
            has_more_present=p.has_more_present, has_more_value=p.has_more_value,
            page_index=1,
        )
        self.assertTrue(d.complete)
        self.assertEqual(len(p.canonical_rows), 0)
        classification = "NO_HISTORICAL_SUPPORT" if not p.canonical_rows else "SHALLOW_SUPPORT_COMPLETE"
        self.assertEqual(classification, "NO_HISTORICAL_SUPPORT")

    def test_hasmore_true_with_raw_min_above_from_continues_backward(self):
        c = self.ctx()
        mins = [c.from_ms//60000+10, c.from_ms//60000+15]
        p = b4.normalize_bound_response(self.response(mins, has_more=True), ctx=c, digits=3)
        d = b4.pagination_decision_v4(
            ctx=c, geometry=p.geometry, has_more_present=True, has_more_value=True, page_index=1
        )
        self.assertFalse(d.complete)
        self.assertFalse(d.fail_closed)
        self.assertEqual(d.next_to_ms, p.geometry.raw_min_open_ms - 1)

    def test_hasmore_false_with_raw_min_above_from_completes(self):
        c = self.ctx()
        p = b4.normalize_bound_response(
            self.response([c.from_ms//60000+10], has_more=False), ctx=c, digits=3
        )
        d = b4.pagination_decision_v4(
            ctx=c, geometry=p.geometry, has_more_present=True, has_more_value=False, page_index=1
        )
        self.assertTrue(d.complete)

    def test_hasmore_absent_short_raw_page_completes(self):
        c = self.ctx()
        p = b4.normalize_bound_response(
            self.response([c.from_ms//60000+10], has_more=None), ctx=c, digits=3
        )
        d = b4.pagination_decision_v4(
            ctx=c, geometry=p.geometry, has_more_present=False, has_more_value=None, page_index=1
        )
        self.assertTrue(d.complete)

    def test_hasmore_absent_full_raw_page_continues(self):
        c = self.ctx()
        start = c.from_ms//60000+5
        mins = [start + 5*i for i in range(5000)]
        c2 = self.ctx(to_utc="2026-09-30T00:00:00Z")
        p = b4.normalize_bound_response(self.response(mins, has_more=None), ctx=c2, digits=3)
        d = b4.pagination_decision_v4(
            ctx=c2, geometry=p.geometry, has_more_present=False, has_more_value=None, page_index=1
        )
        self.assertFalse(d.complete)
        self.assertFalse(d.fail_closed)
        self.assertEqual(d.next_to_ms, p.geometry.raw_min_open_ms - 1)

    def test_page_cap_three_unchanged(self):
        c = self.ctx(to_utc="2026-09-30T00:00:00Z")
        start = c.from_ms//60000+5
        p = b4.normalize_bound_response(self.response([start], has_more=True), ctx=c, digits=3)
        d = b4.pagination_decision_v4(
            ctx=c, geometry=p.geometry, has_more_present=True, has_more_value=True, page_index=3
        )
        self.assertTrue(d.fail_closed)
        self.assertTrue(d.reason.startswith("PAGE_CAP_"))
        self.assertEqual(v2.MAXIMUM_PAGES_PER_IDENTITY_SEGMENT, 3)

    def test_retry_and_rate_laws_unchanged(self):
        self.assertEqual(p4.v2.RETRY_CAP_AFTER_INITIAL, 2)
        self.assertEqual(p4.v2.MAX_WIRE_ATTEMPTS_PER_PAGE, 3)
        self.assertEqual(p4.v2.RATE_LIMIT_RPS, 4)

    def test_execution_equivalence_proof(self):
        proof = p4.execution_equivalence_proof()
        self.assertEqual(
            proof["only_allowed_behavioral_changes"],
            ["LOWER_BOUNDARY_OVERFETCH_NORMALIZATION", "RAW_GEOMETRY_AWARE_PAGINATION_COMPLETION"],
        )
        self.assertTrue(all(proof["proof"].values()))

    def test_no_global_monkey_patching(self):
        src = inspect.getsource(p4)
        self.assertNotIn("v2.validate_arm =", src)
        self.assertNotIn("v3.validate_arm =", src)

    def test_future_v4_release_identity_cannot_reuse_failed_v3(self):
        identity = p4.derive_release_identity("0"*40)
        self.assertTrue(identity.startswith("mxm-shallow-m5-v2-v4-"))
        self.assertNotEqual(identity, p4.FAILED_V3_RELEASE)

    def test_zero_v4_arm_prearm(self):
        self.assertFalse((ROOT / p4.ARM_REL).exists())


if __name__ == "__main__":
    unittest.main()
