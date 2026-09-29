import copy
import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.commodity_breakout_epoch44_screen import (
    _benjamini_yekutieli,
    _evaluate_cell,
    _read_symbol,
    validate_freeze,
    CommodityBreakoutScanError,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "research_v3/EPOCH44_COMMODITY_BREAKOUT_DISCOVERY_FREEZE_V1.json"


def synthetic_rows(count=32):
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        close = 100.0 + 0.01 * index
        rows.append({
            "timestamp": start + timedelta(minutes=5 * index),
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "tick_volume": 1.0,
        })
    rows[12].update({"open": 100.6, "high": 101.0, "low": 100.0, "close": 100.6})
    return rows


def csv_bytes(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "time_utc", "open", "high", "low", "close", "tick_volume",
    ])
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "time_utc": row["timestamp"].isoformat().replace("+00:00", "Z"),
            **{key: row[key] for key in ("open", "high", "low", "close", "tick_volume")},
        })
    return output.getvalue().encode()


class CommodityBreakoutEpoch44Tests(unittest.TestCase):
    def test_freeze_binds_exact_accepted_decision_symbols_and_grid(self):
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        registry = validate_freeze(freeze, ROOT)
        self.assertEqual(len(registry["representatives"]), 41)
        self.assertEqual(len(freeze["scope"]["symbols"]), 4)
        self.assertEqual(freeze["parameter_grid"]["cells_per_symbol"], 27)
        self.assertEqual(freeze["scope"]["total_parameter_cells"], 108)

        changed_grid = copy.deepcopy(freeze)
        changed_grid["parameter_grid"]["range_expansion_multiple"] = [1.0, 1.5, 2.0]
        with self.assertRaises(CommodityBreakoutScanError):
            validate_freeze(changed_grid, ROOT)

        changed_scope = copy.deepcopy(freeze)
        changed_scope["scope"]["symbols"].pop()
        with self.assertRaises(CommodityBreakoutScanError):
            validate_freeze(changed_scope, ROOT)

    def test_future_bars_do_not_change_event_admission(self):
        rows = synthetic_rows(16)
        baseline = _evaluate_cell(rows, 12, 1.25, 3)
        changed_future = copy.deepcopy(rows)
        changed_future[15]["close"] = 100.8
        changed_future[15]["high"] = 100.9
        changed = _evaluate_cell(changed_future, 12, 1.25, 3)
        self.assertEqual(baseline["event_accounting"]["event_candidates"], 1)
        self.assertEqual(
            baseline["event_accounting"]["event_candidates"],
            changed["event_accounting"]["event_candidates"],
        )
        self.assertNotEqual(baseline["effect_size"], changed["effect_size"])

    def test_only_first_complete_event_per_utc_date_is_retained(self):
        rows = synthetic_rows(28)
        rows[22].update({"open": 101.5, "high": 102.0, "low": 101.0, "close": 101.5})
        result = _evaluate_cell(rows, 12, 1.25, 3)
        self.assertEqual(result["event_accounting"]["event_candidates"], 2)
        self.assertEqual(result["event_accounting"]["retained_independent_date_events"], 1)
        self.assertEqual(result["event_accounting"]["excluded_events"]["duplicate_utc_date_event"], 1)

    def test_gapped_followthrough_is_not_repaired_or_retained(self):
        rows = synthetic_rows(20)
        rows[15]["timestamp"] += timedelta(minutes=5)
        result = _evaluate_cell(rows, 12, 1.25, 3)
        self.assertEqual(result["event_accounting"]["event_candidates"], 1)
        self.assertEqual(result["event_accounting"]["retained_independent_date_events"], 0)
        self.assertEqual(
            result["event_accounting"]["excluded_events"]["noncontiguous_or_incomplete_followthrough"],
            1,
        )

    def test_manifest_identity_and_member_hash_are_required(self):
        rows = synthetic_rows(20)
        raw = csv_bytes(rows)
        manifest = {
            "series": [{
                "broker_symbol": "Lead",
                "symbol_id": 2791,
                "capture_status": "SERIES_CAPTURE_COMPLETE",
                "synthetic_fill": False,
                "forward_fill": False,
                "file": "raw/2791_Lead_M5.csv",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "row_count": len(rows),
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "capture.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("capture_manifest.json", json.dumps(manifest))
                archive.writestr("raw/2791_Lead_M5.csv", raw)
            with zipfile.ZipFile(archive_path) as archive:
                parsed, attestation = _read_symbol(archive, 2791, "Lead")
            self.assertEqual(len(parsed), 20)
            self.assertEqual(attestation["row_count"], 20)

            manifest["series"][0]["sha256"] = "0" * 64
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("capture_manifest.json", json.dumps(manifest))
                archive.writestr("raw/2791_Lead_M5.csv", raw)
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaises(CommodityBreakoutScanError):
                    _read_symbol(archive, 2791, "Lead")

    def test_by_adjustment_covers_the_complete_declared_family(self):
        adjusted = _benjamini_yekutieli({"a": 0.01, "b": 0.02, "c": 1.0})
        self.assertEqual(set(adjusted), {"a", "b", "c"})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in adjusted.values()))


if __name__ == "__main__":
    unittest.main()
