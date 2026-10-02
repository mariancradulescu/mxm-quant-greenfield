from __future__ import annotations

import inspect
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from m6.ctrader_capture import CaptureContractError, require_read_only_request
from research_core_v3.quote_revision_sequence_raw_capture_v2 import (
    EXPECTED_PLAN_GIT_BLOB_SHA,
    _git_blob_sha,
    _write_raw_gzip,
    decode_tick_response,
    load_plan,
)


class QuoteRevisionSequenceV2OfflineTests(unittest.TestCase):
    def test_plan_binding_calendar_and_scope(self):
        root = Path(__file__).resolve().parents[1]
        raw = (root / "research_core_v3/state/QUOTE_REVISION_SEQUENCE_PRESSURE_ACQUISITION_PLAN_V2.json").read_bytes()
        self.assertEqual(_git_blob_sha(raw), EXPECTED_PLAN_GIT_BLOB_SHA)
        plan = load_plan(root)
        self.assertEqual(len(plan["signal_symbols"]), 5)
        dates = plan["calendar"]["dates_utc"]
        self.assertEqual(len(dates), 30)
        counts = [0, 0, 0, 0, 0]
        months = set()
        for value in dates:
            d = datetime.fromisoformat(value).date()
            self.assertLess(d.weekday(), 5)
            counts[d.weekday()] += 1
            months.add((d.year, d.month))
        self.assertEqual(counts, [6, 6, 6, 6, 6])
        self.assertEqual(len(months), 12)
        self.assertFalse(plan["execution_authorized"])
        self.assertFalse(plan["governance"]["outcomes_opened"])
        self.assertFalse(plan["governance"]["protected_forward_opened"])

    def test_tick_delta_decode_preserves_chronology_and_equal_timestamp_events(self):
        ticks = [
            SimpleNamespace(timestamp=1000, tick=123450),
            SimpleNamespace(timestamp=100, tick=123440),
            SimpleNamespace(timestamp=0, tick=123430),
            SimpleNamespace(timestamp=50, tick=123420),
        ]
        rows = decode_tick_response(ticks, 800, 1000)
        self.assertEqual(rows, [(850, 123420), (900, 123430), (900, 123440), (1000, 123450)])
        self.assertEqual(len(rows), 4)

    def test_tick_decode_rejects_out_of_range(self):
        ticks = [SimpleNamespace(timestamp=1001, tick=123450)]
        with self.assertRaises(CaptureContractError):
            decode_tick_response(ticks, 800, 1000)

    def test_raw_gzip_is_deterministic_and_lossless_integer_text(self):
        rows = [(900, 123430), (900, 123440), (1000, 123450)]
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "a.csv.gz"
            p2 = Path(td) / "b.csv.gz"
            m1 = _write_raw_gzip(p1, rows)
            m2 = _write_raw_gzip(p2, rows)
            self.assertEqual(m1["sha256"], m2["sha256"])
            self.assertEqual(m1["rows"], 3)
            self.assertEqual(m1["first_timestamp_ms"], 900)
            self.assertEqual(m1["last_timestamp_ms"], 1000)

    def test_only_read_only_protocol_requests_are_used(self):
        allowed = {
            "ProtoOAApplicationAuthReq",
            "ProtoOAGetAccountListByAccessTokenReq",
            "ProtoOAAccountAuthReq",
            "ProtoOATraderReq",
            "ProtoOAAssetListReq",
            "ProtoOASymbolsListReq",
            "ProtoOASymbolByIdReq",
            "ProtoOAExpectedMarginReq",
            "ProtoOAGetTickDataReq",
        }
        for name in allowed:
            self.assertEqual(require_read_only_request(name), name)
        import research_core_v3.quote_revision_sequence_raw_capture_v2 as mod
        source = inspect.getsource(mod)
        for forbidden in (
            "ProtoOANewOrderReq",
            "ProtoOACancelOrderReq",
            "ProtoOAClosePositionReq",
            "ProtoOAAmendOrderReq",
            "ProtoOAAmendPositionSLTPReq",
            "ProtoOASubscribeSpotsReq",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
