from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAGetTrendbarsReq, ProtoOAGetTrendbarsRes
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbar
from research_core_v4 import shallow_m5_support_v2 as m


def minutes(value: str) -> int:
    return m.to_ms(value) // 60000


class ShallowM5V2ProtocolDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.digits_map = m.build_digits_map(cls.root)
        cls.lookup = m.digits_lookup(cls.digits_map)
        cls.ctx = m.RequestContext(
            client_msg_id="bfm5-v2-test-0001",
            authenticated_account_id=123456789,
            symbol_id=3,
            from_ms=m.to_ms(m.SEGMENTS[0][0]),
            to_ms=m.to_ms(m.SEGMENTS[0][1]),
        )

    def _response(self, *, account=None, period=m.M5_ENUM, symbol_marker="absent", has_more_marker="absent", bars=()):
        res = ProtoOAGetTrendbarsRes(
            ctidTraderAccountId=self.ctx.authenticated_account_id if account is None else account,
            period=period,
        )
        if symbol_marker != "absent":
            res.symbolId = int(symbol_marker)
        if has_more_marker != "absent":
            res.hasMore = bool(has_more_marker)
        res.trendbar.extend(bars)
        return res

    def _envelope(self, res, client_msg_id=None):
        return ProtoMessage(
            payloadType=int(res.payloadType),
            payload=res.SerializeToString(),
            clientMsgId=self.ctx.client_msg_id if client_msg_id is None else client_msg_id,
        )

    def _bar(self, timestamp, *, low=123456, dopen=0, dhigh=10, dclose=5, volume=7, set_period=False):
        b = ProtoOATrendbar(
            volume=volume,
            low=low,
            utcTimestampInMinutes=minutes(timestamp),
        )
        if dopen is not None:
            b.deltaOpen = int(dopen)
        if dhigh is not None:
            b.deltaHigh = int(dhigh)
        if dclose is not None:
            b.deltaClose = int(dclose)
        if set_period:
            b.period = m.M5_ENUM
        return b

    def test_01_symbol_digits_map_exact1576(self):
        self.assertEqual(len(self.digits_map["entries"]), 1576)
        self.assertEqual(len(self.lookup), 1576)
        self.assertEqual(self.digits_map["master_sha256"], m.MASTER_SHA256)
        self.assertEqual(self.digits_map["source_localization_sha256"], m.LOCALIZATION_SHA256)
        self.assertEqual(
            self.digits_map["digits_map_sha256"],
            m.sha256_bytes(m.canonical(self.digits_map["entries"])),
        )

    def test_02_exact_request_contract(self):
        req = ProtoOAGetTrendbarsReq(
            ctidTraderAccountId=self.ctx.authenticated_account_id,
            symbolId=self.ctx.symbol_id,
            period=m.M5_ENUM,
            fromTimestamp=self.ctx.from_ms,
            toTimestamp=self.ctx.to_ms,
            count=m.PAGE_REQUESTED_COUNT,
        )
        m.validate_request(req, self.ctx)
        self.assertEqual(int(req.period), 5)

    def test_03_exact_valid_response_binding(self):
        res = self._response(symbol_marker=self.ctx.symbol_id, has_more_marker=False)
        bound = m.bind_response_envelope(self._envelope(res), self.ctx)
        self.assertIs(type(bound), ProtoOAGetTrendbarsRes)

    def test_04_wrong_account_response_fails(self):
        res = self._response(account=self.ctx.authenticated_account_id + 1)
        with self.assertRaises(ValueError):
            m.bind_response_envelope(self._envelope(res), self.ctx)

    def test_05_wrong_period_response_fails(self):
        res = self._response(period=1)
        with self.assertRaises(ValueError):
            m.bind_response_envelope(self._envelope(res), self.ctx)

    def test_06_present_wrong_symbol_id_fails(self):
        res = self._response(symbol_marker=self.ctx.symbol_id + 1)
        with self.assertRaises(ValueError):
            m.bind_response_envelope(self._envelope(res), self.ctx)

    def test_07_absent_optional_symbol_id_allowed_by_frozen_rule(self):
        res = self._response(symbol_marker="absent")
        bound = m.bind_response_envelope(self._envelope(res), self.ctx)
        self.assertFalse(bound.HasField("symbolId"))

    def test_08_wrong_client_msg_id_not_accepted(self):
        res = self._response()
        with self.assertRaises(ValueError):
            m.bind_response_envelope(self._envelope(res, "wrong-client-id"), self.ctx)

    def test_09_hasmore_present_true(self):
        res = self._response(has_more_marker=True)
        self.assertEqual(m.response_has_more_presence(res), (True, True))

    def test_10_hasmore_present_false(self):
        res = self._response(has_more_marker=False)
        self.assertEqual(m.response_has_more_presence(res), (True, False))

    def test_11_hasmore_absent(self):
        res = self._response(has_more_marker="absent")
        self.assertEqual(m.response_has_more_presence(res), (False, None))

    def test_12_multipage_backward_progress_short_page_even_when_hasmore_true(self):
        rows = [
            {"time_utc": "2026-08-20T00:10:00Z"},
            {"time_utc": "2026-08-20T00:15:00Z"},
        ]
        d = m.pagination_decision(
            ctx=self.ctx,
            decoded_rows=rows,
            has_more_present=True,
            has_more_value=True,
            page_index=1,
        )
        self.assertFalse(d.complete)
        self.assertFalse(d.fail_closed)
        self.assertEqual(d.next_to_ms, m.to_ms("2026-08-20T00:10:00Z") - 1)
        nxt = m.next_context(self.ctx, d, next_client_msg_id="bfm5-v2-test-0002")
        self.assertLess(nxt.to_ms, self.ctx.to_ms)
        self.assertEqual(nxt.from_ms, self.ctx.from_ms)
        self.assertEqual(nxt.symbol_id, self.ctx.symbol_id)

    def test_13_page_cap_fail_closed(self):
        rows = [{"time_utc": "2026-08-20T00:10:00Z"}]
        d = m.pagination_decision(
            ctx=self.ctx,
            decoded_rows=rows,
            has_more_present=True,
            has_more_value=True,
            page_index=m.MAXIMUM_PAGES_PER_IDENTITY_SEGMENT,
        )
        self.assertTrue(d.fail_closed)
        self.assertEqual(d.reason, "PAGE_CAP_REACHED_WITH_MORE_REQUIRED")

    def test_14_low_and_zero_deltas_decoding(self):
        bar = self._bar("2026-08-20T00:00:00Z", low=123456, dopen=None, dhigh=None, dclose=None)
        row = m.decode_trendbar(bar, digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms)
        self.assertEqual(row["low"], "1.23456")
        self.assertEqual(row["open"], "1.23456")
        self.assertEqual(row["high"], "1.23456")
        self.assertEqual(row["close"], "1.23456")

    def test_15_nonzero_delta_open_high_close_decoding(self):
        bar = self._bar("2026-08-20T00:05:00Z", low=123450, dopen=5, dhigh=20, dclose=10)
        row = m.decode_trendbar(bar, digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms)
        self.assertEqual(row["low"], "1.23450")
        self.assertEqual(row["open"], "1.23455")
        self.assertEqual(row["high"], "1.23470")
        self.assertEqual(row["close"], "1.23460")

    def test_16_tick_volume_decoding_and_negative_rejection(self):
        bar = self._bar("2026-08-20T00:00:00Z", volume=123)
        row = m.decode_trendbar(bar, digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms)
        self.assertEqual(row["tick_volume"], "123")
        neg = self._bar("2026-08-20T00:00:00Z", volume=-1)
        with self.assertRaises(ValueError):
            m.decode_trendbar(neg, digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms)

    def test_17_exact_decimal_price_serialization(self):
        self.assertEqual(m.exact_price_string(123456, 5), "1.23456")
        self.assertEqual(m.exact_price_string(123456, 2), "1.23")
        self.assertEqual(m.exact_price_string(123500, 2), "1.24")
        self.assertEqual(m.exact_price_string(100000, 4), "1.0000")

    def test_18_bar_open_timestamp_conversion(self):
        value = "2026-08-20T12:35:00Z"
        self.assertEqual(m.utc_iso_from_unix_minutes(minutes(value)), value)

    def test_19_segment_end_2355_included(self):
        end = m.SEGMENTS[0][1]
        bar = self._bar(end)
        row = m.decode_trendbar(bar, digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms)
        self.assertEqual(row["time_utc"], end)

    def test_20_next_segment_0000_not_duplicated(self):
        next_open = m.SEGMENTS[1][0]
        bar = self._bar(next_open)
        with self.assertRaises(ValueError):
            m.decode_trendbar(bar, digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms)
        row = m.decode_trendbar(
            bar,
            digits=5,
            segment_from_ms=m.to_ms(m.SEGMENTS[1][0]),
            segment_to_ms=m.to_ms(m.SEGMENTS[1][1]),
        )
        self.assertEqual(row["time_utc"], next_open)

    def test_21_protected_forward_rejection(self):
        bar = self._bar("2026-09-17T12:05:00Z")
        with self.assertRaises(ValueError):
            m.decode_trendbar(
                bar,
                digits=5,
                segment_from_ms=m.to_ms("2026-09-17T12:00:00Z"),
                segment_to_ms=m.to_ms("2026-09-17T13:00:00Z"),
            )

    def test_22_response_decode_sorts_strictly_and_binds_before_rows(self):
        bars = [
            self._bar("2026-08-20T00:10:00Z"),
            self._bar("2026-08-20T00:00:00Z"),
            self._bar("2026-08-20T00:05:00Z"),
        ]
        res = self._response(symbol_marker=self.ctx.symbol_id, has_more_marker=False, bars=bars)
        bound = m.bind_response_envelope(self._envelope(res), self.ctx)
        rows = m.decode_bound_response(bound, ctx=self.ctx, digits=5)
        self.assertEqual([x["time_utc"] for x in rows], [
            "2026-08-20T00:00:00Z",
            "2026-08-20T00:05:00Z",
            "2026-08-20T00:10:00Z",
        ])

    def test_23_interruption_resume_byte_equivalence(self):
        rows = [
            m.decode_trendbar(self._bar("2026-08-20T00:00:00Z"), digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms),
            m.decode_trendbar(self._bar("2026-08-20T00:05:00Z"), digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms),
            m.decode_trendbar(self._bar("2026-08-20T00:10:00Z"), digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms),
        ]
        one_shot = m.serialize_rows(rows)
        interrupted_then_resumed = m.serialize_rows(rows[:2] + rows[2:])
        self.assertEqual(one_shot, interrupted_then_resumed)

    def test_24_shard_reconstruction_byte_equivalence(self):
        rows = [
            m.decode_trendbar(self._bar("2026-08-20T00:00:00Z"), digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms),
            m.decode_trendbar(self._bar("2026-08-20T00:05:00Z"), digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms),
            m.decode_trendbar(self._bar("2026-08-20T00:10:00Z"), digits=5, segment_from_ms=self.ctx.from_ms, segment_to_ms=self.ctx.to_ms),
        ]
        full = m.serialize_rows(rows)
        shard_a = m.serialize_rows(rows[:2])
        shard_b = m.serialize_rows(rows[2:])
        self.assertEqual(m.reconstruct_shards([shard_a, shard_b]), full)

    def test_25_page_and_true_wire_bounds(self):
        self.assertEqual(m.LOGICAL_IDENTITY_SEGMENT_COUNT, 6304)
        self.assertEqual(m.MAXIMUM_PAGES_PER_IDENTITY_SEGMENT, 3)
        self.assertEqual(m.MAXIMUM_PAGE_REQUEST_COUNT, 18912)
        self.assertEqual(m.MAXIMUM_RETRIES_AFTER_INITIAL_ATTEMPT, 2)
        self.assertEqual(m.MAXIMUM_WIRE_ATTEMPTS_PER_PAGE, 3)
        self.assertEqual(m.TRUE_ABSOLUTE_MAXIMUM_WIRE_ATTEMPTS, 56736)
        self.assertEqual(m.page_bound_explanation()["minimum_wire_send_hms_at_frozen_4rps"], "03:56:24")

    def test_26_no_arm_broker_history_or_credentials_in_summary(self):
        s = m.v2_summary()
        self.assertFalse(s["arm_present"])
        self.assertFalse(s["broker_contact"])
        self.assertEqual(s["historical_requests_sent"], 0)
        self.assertFalse(s["credentials_used"])
        self.assertEqual(s["economic_outcomes_opened"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
