import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.adaptive_breadth_triage import run_triage, select_primary_family


class AdaptiveBreadthTriageTests(unittest.TestCase):
    def test_primary_family_selection_is_non_economic_and_preference_bound(self):
        root = Path(__file__).resolve().parents[1]
        triage = json.loads(
            (root / "evidence/BROKER_NATIVE_FRONTIER_40_ADAPTIVE_BREADTH_TRIAGE_V1.json").read_text()
        )
        selected = select_primary_family(
            triage,
            ["BREAKOUT_VOLATILITY_EXPANSION", "REGIME_CONTEXT_CONDITIONED", "MEAN_REVERSION"],
        )
        self.assertEqual(selected["primary_family"], "BREAKOUT_VOLATILITY_EXPANSION")
        self.assertEqual(selected["economic_evaluation"], "NOT_PERFORMED")
        self.assertFalse(selected["mechanism_family_closure_claimed"])

    def test_primary_family_selection_fails_closed_without_sufficient_candidate(self):
        triage = {
            "status": "COMPLETE_NON_ECONOMIC_ADAPTIVE_TRIAGE",
            "adaptive_selection": {"selected_families": []},
            "family_ranking": [],
        }
        with self.assertRaisesRegex(ValueError, "no preferred family"):
            select_primary_family(triage, ["BREAKOUT_VOLATILITY_EXPANSION"])

    def test_triage_is_hash_bound_causal_and_non_economic(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_PLAN_V1.json").read_text())
        symbols = plan["symbols"][:2]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.zip"
            manifest = {
                "plan_sha256": plan["plan_sha256"],
                "economic_outcomes_opened": 0,
                "v2_attempts_consumed": 0,
                "series": [],
            }
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                for index, spec in enumerate(plan["symbols"]):
                    name = f"{spec['symbol_id']}_{spec['broker_symbol']}_M5.csv"
                    stream = io.StringIO()
                    writer = csv.writer(stream)
                    writer.writerow(("time_utc", "open", "high", "low", "close", "tick_volume"))
                    if index < len(symbols):
                        origin = datetime(2026, 6, 15, tzinfo=timezone.utc)
                        for step in range(300):
                            timestamp = origin + timedelta(minutes=5 * step)
                            writer.writerow((timestamp.isoformat().replace("+00:00", "Z"), "1", "2", "1", "1.5", "1"))
                    archive.writestr(name, stream.getvalue())
                    manifest["series"].append({"broker_symbol": spec["broker_symbol"], "file": name})
                archive.writestr("capture_manifest.json", json.dumps(manifest))
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            out = run_triage(path, repository_root=root, accepted_sha256=observed)
            self.assertEqual(out["status"], "COMPLETE_NON_ECONOMIC_ADAPTIVE_TRIAGE")
            self.assertFalse(out["adaptive_selection"]["fixed_family_or_parameter_grid"])
            self.assertEqual(out["economic_effect"]["economic_outcomes_opened"], 0)
            self.assertFalse(out["economic_effect"]["pnl_or_returns_computed"])
            self.assertIn("TREND_MOMENTUM", out["adaptive_selection"]["selected_families"])
            self.assertEqual(out["scope"]["series_with_rows"], 2)

    def test_hash_mismatch_fails_closed(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.NamedTemporaryFile(suffix=".zip") as handle:
            with self.assertRaisesRegex(ValueError, "hash"):
                run_triage(handle.name, repository_root=root, accepted_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
