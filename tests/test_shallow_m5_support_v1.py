from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_core_v4 import shallow_m5_support_v1 as m
from m6.ctrader_transport import runtime_transport_preflight


class ShallowM5PrearmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.master = json.loads((cls.root / m.MASTER_REL).read_bytes())

    def test_01_exact_master1576_hash_binding(self):
        checked = m.validate_master_value(self.master)
        self.assertEqual(len(checked), 1576)
        self.assertEqual(m.sha256_bytes(m.canonical(checked)), m.EXPECTED_MASTER_SHA256)

    def test_02_exact_auth_v3_fingerprint_binding(self):
        p = self.root / "adaptive_competition/state/MACHINE_SIDE_READ_ONLY_AUTH_PREFLIGHT_RESULT_V3.json"
        auth = json.loads(p.read_bytes())
        self.assertEqual(auth["status"], m.EXPECTED_AUTH_STATUS)
        self.assertEqual(
            auth["expected_account_fingerprint_sha256"],
            m.EXPECTED_ACCOUNT_FINGERPRINT_SHA256,
        )
        self.assertTrue(auth["explicit_view_only_scope_pass"])
        self.assertTrue(auth["matched_account_live"])
        self.assertFalse(auth["market_history_acquired"])
        self.assertFalse(auth["orders_placed"])
        self.assertFalse(auth["refresh_attempted"])

    def test_03_fixed_time_window_and_protected_forward(self):
        m.validate_fixed_calendar()
        self.assertLess(
            m.parse_utc(m.FIXED_WINDOW_END_UTC),
            m.parse_utc(m.PROTECTED_FORWARD_BOUNDARY_UTC),
        )
        self.assertEqual(m.THEORETICAL_M5_SLOTS_FULL_WINDOW, 8064)

    def test_04_deterministic_four_segment_calendar_and_breadth_order(self):
        manifest = m.build_request_manifest(self.master)
        self.assertEqual(len(manifest), 6304)
        self.assertEqual(manifest[0]["symbol_id"], self.master[0]["symbol_id"])
        self.assertEqual(manifest[1575]["symbol_id"], self.master[-1]["symbol_id"])
        self.assertEqual(manifest[1575]["segment_index"], 0)
        self.assertEqual(manifest[1576]["segment_index"], 1)
        self.assertEqual(len({x["request_id"] for x in manifest}), 6304)

    def test_05_deterministic_pagination_hasmore(self):
        d = m.decide_pagination(
            request_from_ms=0,
            request_to_ms=100,
            raw_open_times_ms=[50, 75, 100],
            has_more_exposed=True,
            has_more=True,
            page_size=3,
        )
        self.assertFalse(d.complete)
        self.assertFalse(d.fail_closed)
        self.assertEqual(d.next_to_ms, 49)
        d2 = m.decide_pagination(
            request_from_ms=0,
            request_to_ms=49,
            raw_open_times_ms=[0, 25, 49],
            has_more_exposed=True,
            has_more=False,
            page_size=3,
        )
        self.assertTrue(d2.complete)
        self.assertFalse(d2.fail_closed)
        bad = m.decide_pagination(
            request_from_ms=0,
            request_to_ms=100,
            raw_open_times_ms=[50, 100],
            has_more_exposed=True,
            has_more=True,
            page_size=3,
        )
        self.assertTrue(bad.fail_closed)

    def test_06_production_segment_request_bound_and_rate_limiter_law(self):
        self.assertEqual(m.PAGE_SIZE, 5000)
        self.assertGreater(m.PAGE_SIZE, m.THEORETICAL_M5_SLOTS_PER_SEGMENT)
        m.production_segment_response_guard([0, 300000, 600000])
        self.assertEqual(m.LOGICAL_REQUEST_BOUND, 6304)
        self.assertEqual(m.WIRE_ATTEMPT_BOUND, 18912)
        self.assertEqual(m.MAX_HISTORICAL_REQUEST_RATE_PER_CONNECTION, 4)
        self.assertEqual(m.MIN_HISTORICAL_REQUEST_INTERVAL_SECONDS, 0.25)

    def test_07_heartbeat_path_offline(self):
        pre = runtime_transport_preflight()
        self.assertTrue(pre["heartbeat_available"])
        self.assertEqual(pre["heartbeat_idle_seconds"], 10.0)
        self.assertFalse(pre["network_connection_attempted"])
        self.assertFalse(pre["credentials_used"])

    def test_08_atomic_checkpoint_resume_and_duplicate_prevention(self):
        cp = m.new_checkpoint("a" * 64)
        self.assertTrue(m.can_send_request(cp, "r1"))
        cp2 = m.mark_request_completed(
            cp, "r1", {"sha256": "b" * 64, "row_count": 1}
        )
        self.assertFalse(m.can_send_request(cp2, "r1"))
        with self.assertRaises(ValueError):
            m.mark_request_completed(
                cp2, "r1", {"sha256": "b" * 64, "row_count": 1}
            )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "checkpoint.json"
            body = m.verify_sealed_record(cp2)
            m.atomic_write_sealed_json(p, body)
            loaded = json.loads(p.read_bytes())
            self.assertEqual(m.verify_sealed_record(loaded), body)
            self.assertFalse((p.parent / "checkpoint.json.tmp").exists())

    def test_09_interruption_resume_equivalence(self):
        plan = "c" * 64
        uninterrupted = m.new_checkpoint(plan)
        for rid in ("r1", "r2", "r3"):
            uninterrupted = m.mark_request_completed(
                uninterrupted, rid, {"sha256": rid, "row_count": 1}
            )
        interrupted = m.new_checkpoint(plan)
        for rid in ("r1", "r2"):
            interrupted = m.mark_request_completed(
                interrupted, rid, {"sha256": rid, "row_count": 1}
            )
        self.assertFalse(m.can_send_request(interrupted, "r1"))
        self.assertFalse(m.can_send_request(interrupted, "r2"))
        self.assertTrue(m.can_send_request(interrupted, "r3"))
        interrupted = m.mark_request_completed(
            interrupted, "r3", {"sha256": "r3", "row_count": 1}
        )
        self.assertEqual(
            m.verify_sealed_record(interrupted),
            m.verify_sealed_record(uninterrupted),
        )

    def test_10_integrity_and_protected_forward_guards(self):
        rows = [
            {
                "time_utc": "2026-08-20T00:00:00Z",
                "open": "1",
                "high": "2",
                "low": "0.5",
                "close": "1.5",
                "tick_volume": "2",
            },
            {
                "time_utc": "2026-08-20T00:05:00Z",
                "open": "1.5",
                "high": "2",
                "low": "1",
                "close": "1.2",
                "tick_volume": "1",
            },
        ]
        met = m.inspect_csv_rows(
            rows, segment_start=m.SEGMENTS[0][0], segment_end=m.SEGMENTS[0][1]
        )
        m.validate_segment_integrity(met)
        self.assertEqual(met["protected_forward_row_count"], 0)
        bad = rows + [{
            "time_utc": m.PROTECTED_FORWARD_BOUNDARY_UTC,
            "open": "1",
            "high": "1",
            "low": "1",
            "close": "1",
            "tick_volume": "0",
        }]
        met2 = m.inspect_csv_rows(
            bad, segment_start=m.SEGMENTS[0][0], segment_end=m.SEGMENTS[0][1]
        )
        with self.assertRaises(ValueError):
            m.validate_segment_integrity(met2)

    def test_11_artifact_chunking_hash_reconstruction(self):
        self.assertEqual(m.shard_count(64), 25)
        manifest = m.deterministic_chunk_manifest([
            {
                "request_id": "b",
                "path": "raw/01/b.csv",
                "sha256": "2" * 64,
                "row_count": 2,
                "first_timestamp_utc": None,
                "last_timestamp_utc": None,
            },
            {
                "request_id": "a",
                "path": "raw/00/a.csv",
                "sha256": "1" * 64,
                "row_count": 1,
                "first_timestamp_utc": None,
                "last_timestamp_utc": None,
            },
        ])
        self.assertEqual(
            [x["request_id"] for x in manifest["chunks"]], ["a", "b"]
        )
        body = {"schema": manifest["schema"], "chunks": manifest["chunks"]}
        self.assertEqual(
            manifest["manifest_sha256"], m.sha256_bytes(m.canonical(body))
        )

    def test_12_security_redaction_and_private_value_scan(self):
        m.scan_for_private_values("safe compact manifest", ["secret123", "998877"])
        with self.assertRaises(ValueError):
            m.scan_for_private_values("access_token=secret123", ["secret123"])
        with self.assertRaises(ValueError):
            m.scan_for_private_values("safe text contains 998877", ["998877"])

    def test_13_zero_order_zero_subscription_zero_depth_guards(self):
        m.assert_zero_forbidden_operations([
            "ProtoOAGetTrendbarsReq",
            "ProtoOAApplicationAuthReq",
            "ProtoOAAccountAuthReq",
        ])
        for bad in [
            "ProtoOANewOrderReq",
            "ProtoOASubscribeSpotsReq",
            "ProtoOASubscribeDepthQuotesReq",
            "ProtoOAGetTickDataReq",
            "ProtoOARefreshTokenReq",
        ]:
            with self.assertRaises(ValueError):
                m.assert_zero_forbidden_operations([bad])

    def test_14_fail_closed_retry_and_no_refresh(self):
        self.assertEqual(
            m.retry_policy_for_error("OA_AUTH_TOKEN_EXPIRED"),
            "FAIL_CLOSED_NO_REFRESH",
        )
        self.assertEqual(
            m.retry_policy_for_error("TIMEOUT"),
            "RETRY_SAME_IMMUTABLE_REQUEST_BOUNDED",
        )
        self.assertEqual(
            m.retry_policy_for_error("REQUEST_FREQUENCY_EXCEEDED"),
            "FAIL_CLOSED",
        )

    def test_15_support_law(self):
        self.assertEqual(
            m.classify_support(
                mapping_failure=True,
                segment_complete=[False] * 4,
                row_count=0,
            ),
            "IDENTITY_OR_MAPPING_FAILURE",
        )
        self.assertEqual(
            m.classify_support(
                mapping_failure=False,
                segment_complete=[True] * 4,
                row_count=0,
            ),
            "NO_HISTORICAL_SUPPORT",
        )
        self.assertEqual(
            m.classify_support(
                mapping_failure=False,
                segment_complete=[True] * 4,
                row_count=1,
            ),
            "SHALLOW_SUPPORT_COMPLETE",
        )
        self.assertEqual(
            m.classify_support(
                mapping_failure=False,
                segment_complete=[True, True, False, True],
                row_count=1,
            ),
            "SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED",
        )

    def test_16_freeze_has_no_arm_contact_or_outcome(self):
        s = m.freeze_summary()
        self.assertFalse(s["arm_present"])
        self.assertFalse(s["broker_contact"])
        self.assertEqual(s["historical_requests_sent"], 0)
        self.assertEqual(s["economic_outcomes_opened"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
