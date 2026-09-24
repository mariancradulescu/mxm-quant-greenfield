import csv
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research_v3.cross_market_lead_lag_screen import (
    LeadLagScreenError,
    _read_series,
    execute,
)


class CrossMarketLeadLagScreenTests(unittest.TestCase):
    def test_series_uses_single_price_ohlc_and_rejects_invalid_invariant(self):
        raw = io.StringIO()
        writer = csv.writer(raw)
        writer.writerow(["timestamp_utc", "open", "high", "low", "close", "tick_volume"])
        writer.writerow(["2026-07-20T00:00:00Z", 2, 1, 2, 2, 100])
        with self.assertRaises(LeadLagScreenError):
            _read_series(raw.getvalue().encode(), "AUDJPY")

    def test_screen_counts_only_strictly_consecutive_common_pairs(self):
        start = datetime(2026, 7, 20, tzinfo=timezone.utc)
        symbols = ("AUDJPY", "AUS200", "Brent-F", "BCHUSD")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "capture.zip"
            manifest = {
                "economic_outcomes_opened": 0,
                "v2_attempts_consumed": 0,
                "resolution": "M5",
                "requested_interval": {
                    "start_utc": "2026-07-20T00:00:00Z",
                    "end_utc": "2026-09-13T23:59:59Z",
                },
                "series": [],
            }
            files = {}
            for index, symbol in enumerate(symbols):
                rel = f"raw/{symbol}.csv"
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["timestamp_utc", "open", "high", "low", "close", "tick_volume"])
                for offset in (0, 5, 15):
                    timestamp = start + timedelta(minutes=offset)
                    close = 10 + index + offset
                    writer.writerow([timestamp.isoformat().replace("+00:00", "Z"),
                                     close, close, close, close, 1])
                files[rel] = output.getvalue().encode()
                manifest["series"].append({
                    "broker_symbol": symbol,
                    "capture_status": "SERIES_CAPTURE_COMPLETE",
                    "file": rel,
                })
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "MXM_CROSSALIGN_FOUR_SYMBOL_M5_NON_ECONOMIC_V1/capture_manifest.json",
                    json.dumps(manifest),
                )
                for rel, data in files.items():
                    archive.writestr(
                        "MXM_CROSSALIGN_FOUR_SYMBOL_M5_NON_ECONOMIC_V1/" + rel, data
                    )
            with patch(
                "research_v3.cross_market_lead_lag_screen.SOURCE_CAPTURE_SHA256",
                __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
            ):
                result = execute(path, expected_common_timestamps=3, expected_pairs=1)
            self.assertEqual(result["pairs"], 1)
            self.assertEqual(result["contiguous_valid_segments"], 1)
            self.assertEqual(len(result["ordered_pair_reports"]), 12)
            self.assertEqual(result["economic_effect"]["economic_outcomes_opened"], 0)


if __name__ == "__main__":
    unittest.main()
