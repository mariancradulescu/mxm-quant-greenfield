import unittest
from datetime import date, datetime, timedelta, timezone

from research_v3.regime_context_data_sufficiency_audit import (
    audit_symbol,
    canonicalize_rows,
    _effective_n,
    validate_inputs,
)


def synthetic_rows(count=240):
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        close = 100.0 + 0.01 * index
        spread = 0.1 + (index % 17) * 0.005
        timestamp = start + timedelta(minutes=5 * index)
        rows.append({
            "time_utc": timestamp.isoformat().replace("+00:00", "Z"),
            "timestamp": timestamp,
            "open": close,
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "tick_volume": float(index % 23),
        })
    return rows


class RegimeContextDataSufficiencyAuditTests(unittest.TestCase):
    def test_identical_duplicates_collapse_but_conflicts_and_disorder_fail_closed(self):
        original = synthetic_rows(2)[0]
        canonical, removed = canonicalize_rows([original, dict(original)])
        self.assertEqual(len(canonical), 1)
        self.assertEqual(removed, 1)

        with self.assertRaises(ValueError):
            canonicalize_rows([original, dict(original, close=101.0)])
        with self.assertRaises(ValueError):
            canonicalize_rows([synthetic_rows(2)[1], original])

    def test_audit_reports_context_coverage_without_outcomes(self):
        result = audit_symbol(synthetic_rows())
        self.assertEqual(result["m5_rows"], 240)
        self.assertGreater(result["context_classified_observations"], 0)
        self.assertEqual(len(result["states"]), 8)
        self.assertIn("context_unclassified_observations", result)
        self.assertIn("context_effective_date_clusters", result)
        for report in result["states"].values():
            sensitivity = report["detectable_effect_sensitivity"]
            if report["effective_date_clusters"] > 0:
                self.assertGreater(
                    sensitivity["standardized_mean_shift_at_80pct_power_two_sided_alpha_0_05"],
                    0,
                )

    def test_timestamp_gap_restarts_context_warmup(self):
        rows = synthetic_rows()
        continuous = audit_symbol(rows)
        for row in rows[120:]:
            row["timestamp"] += timedelta(minutes=5)
            row["time_utc"] = row["timestamp"].isoformat().replace("+00:00", "Z")
        broken = audit_symbol(rows)
        self.assertEqual(broken["contiguous_segments"], 2)
        self.assertEqual(broken["timestamp_gap_count"], 1)
        self.assertLess(
            broken["context_classified_observations"],
            continuous["context_classified_observations"],
        )

    def test_effective_n_does_not_exceed_date_clusters_and_haircuts_persistence(self):
        independent = {date(2026, 1, 1) + timedelta(days=i): float(i % 2) for i in range(20)}
        persistent = {
            date(2026, 1, 1) + timedelta(days=i): float(i >= 10)
            for i in range(20)
        }
        independent_n = _effective_n(independent)
        persistent_n = _effective_n(persistent)
        self.assertEqual(independent_n["date_clusters"], 20)
        self.assertLessEqual(independent_n["effective_n"], 20)
        self.assertLess(persistent_n["effective_n"], independent_n["effective_n"])
        alternating_long_run = {
            date(2026, 1, 1) + timedelta(days=i): float((i // 5) % 2)
            for i in range(40)
        }
        self.assertLess(_effective_n(alternating_long_run)["effective_n"], 40)

    def test_freeze_violations_are_rejected_before_external_input_reads(self):
        freeze = {
            "schema": "mxm.greenfield.regime-context-data-sufficiency-freeze.v1",
            "status": "PROSPECTIVELY_FROZEN_NON_ECONOMIC_AUDIT",
            "authority": {
                "accepted_proposal_ref": "research_v3/ai_director/proposals/AUTO_reason_88b3d8ac3e0ad746ff188958465fbd36.json",
                "accepted_proposal_file_sha256": "20db9e7dcc5e3ff2ac4746f7fa81c82ded1598a2ab2bca078c266a037359a62e",
                "structural_registry_sha256": "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3",
                "development_capture_sha256": "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503",
                "replacement_capture_sha256": "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75",
            },
            "scope": {
                "resolution": "H1",
                "interval": {
                    "start_utc": "2026-06-15T00:00:00Z",
                    "end_utc": "2026-09-13T23:59:59Z",
                },
                "protected_forward_start_utc": "2026-09-17T12:02:58Z",
                "representative_count": 41,
                "structural_coverage_only": True,
                "structural_representatives_are_economic_equivalents": False,
            },
        }
        with self.assertRaises(ValueError):
            validate_inputs(freeze, "/missing/registry", "/missing/dev.zip", "/missing/replacement.zip")


if __name__ == "__main__":
    unittest.main()
