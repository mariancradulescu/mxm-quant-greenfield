from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from research_core_v4 import shallow_m5_support_v2 as decoder
from research_core_v4 import shallow_m5_support_v2_v3_boundary_forensic_probe as probe


class BoundaryForensicProbeTests(unittest.TestCase):
    def synthetic_payload(self, minutes):
        response = decoder.ProtoOAGetTrendbarsResV2(
            ctidTraderAccountId=12345,
            period=decoder.M5_ENUM,
            symbolId=3,
            hasMore=False,
        )
        for minute in minutes:
            bar = response.trendbar.add()
            bar.volume = 777
            bar.period = decoder.M5_ENUM
            bar.low = 123456
            bar.deltaOpen = 1
            bar.deltaHigh = 2
            bar.deltaClose = 1
            bar.utcTimestampInMinutes = minute
        return response.SerializeToString()

    def test_wire_scanner_persists_temporal_geometry_only(self):
        from_min = probe.FROM_MS // 60000
        inside = from_min + 5
        payload = self.synthetic_payload([from_min - 5, inside, inside])
        result = probe.extract_temporal_geometry(payload, expected_account_id=12345)
        self.assertEqual(result["response_trendbar_count"], 3)
        self.assertEqual(result["exact_count_below_fromTimestamp"], 1)
        self.assertEqual(result["exact_count_inside_requested_interval"], 2)
        self.assertEqual(result["exact_duplicate_open_timestamp_count"], 1)
        self.assertEqual(result["forensic_classification"], "LOWER_BOUNDARY_OVERFETCH_CONFIRMED")
        probe._assert_no_forbidden_persistence(result)

    def test_source_never_calls_canonical_price_decoder(self):
        src = inspect.getsource(probe)
        self.assertNotIn(".decode_bound_response(", src)
        self.assertNotIn(".decode_trendbar(", src)

    def test_single_direct_history_send_surface(self):
        src = inspect.getsource(probe.run_probe)
        self.assertEqual(src.count("transport._send_bytes("), 1)
        self.assertNotIn("for attempt in", src)
        self.assertNotIn("ProtoOARefreshTokenReq", src)

    def test_failed_arm_is_read_only_historical(self):
        authority = probe.load_json(probe.ROOT / probe.FAILURE_AUTH_REL)
        self.assertEqual(authority["status"], "HISTORICAL_FAILED_CLOSED_DO_NOT_RERUN")
        self.assertFalse(authority["failed_arm"]["rerun_authorized"])
        self.assertFalse(authority["failed_arm"]["rewrite_authorized"])
        self.assertFalse(authority["failed_campaign_durable_state"]["reuse_for_successor_authorized"])

    def test_forensic_arm_absent_before_arm_commit(self):
        self.assertFalse((probe.ROOT / probe.FORENSIC_ARM_REL).exists())


if __name__ == "__main__":
    unittest.main()
