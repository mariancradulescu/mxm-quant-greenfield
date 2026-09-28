import copy
import csv
import io
import json
import math
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.trend_momentum_parameter_region_epoch37_screen import (
    DEVELOPMENT_ACCEPTANCE_REF,
    FREEZE_REF,
    PROPOSAL_REF,
    PROPOSAL_REGISTRY_REF,
    REGISTRY_REF,
    REPLACEMENT_ACCEPTANCE_REF,
    TrendMomentumScanError,
    _read_symbol,
    evaluate_symbol_rows,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / FREEZE_REF
BOUND_REFS = [
    PROPOSAL_REF,
    PROPOSAL_REGISTRY_REF,
    DEVELOPMENT_ACCEPTANCE_REF,
    REPLACEMENT_ACCEPTANCE_REF,
    REGISTRY_REF,
]


def synthetic_rows(count=420):
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        close = 100.0 * math.exp(0.0008 * i + 0.015 * math.sin(i / 11.0))
        rows.append({
            "time_utc": (start + timedelta(minutes=5 * i)).isoformat().replace("+00:00", "Z"),
            "timestamp": start + timedelta(minutes=5 * i),
            "open": close, "high": close * 1.0001, "low": close * 0.9999,
            "close": close, "tick_volume": 1.0,
        })
    return rows


def temp_bound_root():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    for rel in BOUND_REFS:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    return temp, root


class TrendMomentumParameterRegionTests(unittest.TestCase):
    def test_frozen_authority_and_exact_grid(self):
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        validate_freeze(freeze, ROOT)
        self.assertEqual(freeze["parameter_grid"]["lookback_bars_M5"], [12, 24, 48, 96, 192])
        self.assertEqual(freeze["parameter_grid"]["momentum_threshold_zscore"], [0.5, 1.0, 1.5, 2.0])
        self.assertEqual(freeze["parameter_grid"]["hold_horizon"], ["15m", "1h", "4h", "1d"])
        self.assertEqual(freeze["parameter_grid"]["cells_per_symbol"], 80)
        self.assertNotEqual(
            freeze["authority"]["development_capture_plan_sha256"],
            freeze["authority"]["replacement_capture_plan_sha256"],
        )

        wrong_grid = copy.deepcopy(freeze)
        wrong_grid["parameter_grid"]["lookback_bars_M5"] = [12, 24, 48]
        with self.assertRaisesRegex(TrendMomentumScanError, "wrong parameter grid"):
            validate_freeze(wrong_grid, ROOT)

        wrong_symbols = copy.deepcopy(freeze)
        wrong_symbols["scope"]["symbols"] = wrong_symbols["scope"]["symbols"][:-1]
        with self.assertRaisesRegex(TrendMomentumScanError, "wrong symbol set"):
            validate_freeze(wrong_symbols, ROOT)

    def test_mutated_proposal_fails_closed(self):
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        temp, root = temp_bound_root()
        try:
            path = root / PROPOSAL_REF
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["objective"]["goal"] = doc["objective"]["goal"] + " MUTATED"
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(TrendMomentumScanError, "accepted proposal hash mismatch"):
                validate_freeze(freeze, root)
        finally:
            temp.cleanup()

    def test_mutated_capture_authority_fails_closed(self):
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        temp, root = temp_bound_root()
        try:
            path = root / DEVELOPMENT_ACCEPTANCE_REF
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["source"]["plan_sha256"] = "0" * 64
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(TrendMomentumScanError, "development capture authority"):
                validate_freeze(freeze, root)
        finally:
            temp.cleanup()

    def test_all_80_cells_emitted_and_required_metrics_present(self):
        result = evaluate_symbol_rows(synthetic_rows(), "SYNTH", 1, "Forex (Spot)")
        self.assertEqual(result["cells_emitted"], 80)
        self.assertEqual(len(result["cells"]), 80)
        for cell in result["cells"].values():
            for key in (
                "symbol", "asset_class", "lookback", "momentum_threshold_zscore", "hold_horizon",
                "effect_size", "uncertainty", "effective_independent_sample_size", "event_density",
                "chronological_half_stability", "censoring", "missingness", "coverage",
                "robust_neighborhood_metrics",
            ):
                self.assertIn(key, cell)
        raw = json.dumps(result).lower()
        self.assertNotIn('"pnl"', raw)
        self.assertNotIn('"profit"', raw)
        self.assertNotIn('"economic_outcome"', raw)

    def test_gaps_start_new_segments_and_conflicting_duplicates_fail_closed(self):
        rows = synthetic_rows(420)
        for row in rows[210:]:
            row["timestamp"] += timedelta(minutes=15)
            row["time_utc"] = row["timestamp"].isoformat().replace("+00:00", "Z")
        result = evaluate_symbol_rows(rows, "SYNTH", 1, "Forex (Spot)")
        any_cell = next(iter(result["cells"].values()))
        self.assertEqual(any_cell["missingness"]["contiguous_segments"], 2)
        self.assertEqual(any_cell["missingness"]["gap_count"], 1)

        duplicate = copy.deepcopy(rows[100])
        duplicate["close"] *= 1.01
        with self.assertRaisesRegex(TrendMomentumScanError, "duplicate conflicting bars"):
            evaluate_symbol_rows(rows + [duplicate], "SYNTH", 1, "Forex (Spot)")

    def test_future_or_protected_rows_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            zpath = Path(td) / "future.zip"
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["time_utc", "open", "high", "low", "close", "tick_volume"])
            writer.writeheader()
            writer.writerow({
                "time_utc": "2026-09-14T00:00:00Z", "open": 100, "high": 101,
                "low": 99, "close": 100, "tick_volume": 1,
            })
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("raw/146_JPYX_M5.csv", output.getvalue())
            with zipfile.ZipFile(zpath) as zf:
                with self.assertRaisesRegex(TrendMomentumScanError, "future/protected"):
                    _read_symbol(zf, 146, "JPYX")

    def test_uncertainty_is_bounded_or_explicitly_unavailable(self):
        result = evaluate_symbol_rows(synthetic_rows(), "SYNTH", 1, "Forex (Spot)")
        for cell in result["cells"].values():
            uncertainty = cell["uncertainty"]
            for field in ("standard_error_bps", "ci95_half_width_bps"):
                value = uncertainty[field]
                if value is not None:
                    self.assertTrue(math.isfinite(value))
                    self.assertGreaterEqual(value, 0.0)


if __name__ == "__main__":
    unittest.main()
