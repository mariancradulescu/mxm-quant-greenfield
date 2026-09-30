import csv
import gzip
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from research_core_v3.v3_friction_evidence import (
    FrictionEvidenceError,
    _dist,
    assess_bundle,
)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def bound(value):
    result = dict(value)
    result["binding_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result

class V3FrictionEvidenceTests(unittest.TestCase):
    def test_distribution_nearest_rank(self):
        d = _dist([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(d["median"], 3.0)
        self.assertEqual(d["p90"], 5.0)
        self.assertEqual(d["n"], 5)

    def _fixture(self, root: Path, *, tamper=False):
        plan = bound({
            "status": "FROZEN_READ_ONLY_AUTHENTIC_QUOTE_ACQUISITION_PLAN",
            "selection": {
                "selected_regions": 1,
                "selected_exact_quote_windows": 1,
                "gross_robust_regions_total": 88,
                "other_gross_regions_remaining_COST_UNRESOLVED": 87,
            },
            "authority": {
                "corrected_surface_sha256": "a" * 64,
                "corrected_region_assessment_sha256": "b" * 64,
                "corrected_friction_scope_plan_sha256": "c" * 64,
            },
            "broker_identity": {"accepted_account_fingerprint_sha256": "d" * 64},
            "acquisition": {"delay_sensitivity_seconds": [0, 1, 5, 30], "quote_age_limit_seconds": 2},
            "freeze_gate": {"remaining_required_components": ["commission"]},
            "targets": [{
                "symbol": "TEST", "symbol_id": 7, "windows": 1,
                "region_sha256": "e" * 64, "minimum_mean_response_bps": 1.25,
            }],
        })
        plan_path = root / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        fieldnames = [
            "symbol", "symbol_id", "exact_window_index", "window_start_ms",
            "boundary_ms", "window_end_ms", "region_sha256",
        ]
        for delay in [0, 1, 5, 30]:
            p = f"d{delay}s"
            fieldnames += [
                f"{p}_bid", f"{p}_ask", f"{p}_spread", f"{p}_bid_timestamp_ms",
                f"{p}_ask_timestamp_ms", f"{p}_bid_age_ms", f"{p}_ask_age_ms", f"{p}_availability",
            ]
        fieldnames += [
            "first_post_boundary_timestamp_ms", "first_post_boundary_side",
            "first_post_boundary_bid", "first_post_boundary_ask", "first_post_boundary_delay_ms",
        ]
        row = {
            "symbol": "TEST", "symbol_id": "7", "exact_window_index": "0",
            "window_start_ms": "1000", "boundary_ms": "3000", "window_end_ms": "33000",
            "region_sha256": "e" * 64,
            "first_post_boundary_timestamp_ms": "", "first_post_boundary_side": "",
            "first_post_boundary_bid": "", "first_post_boundary_ask": "",
            "first_post_boundary_delay_ms": "",
        }
        for delay in [0, 1, 5, 30]:
            p = f"d{delay}s"
            checkpoint = 3000 + delay * 1000
            row.update({
                f"{p}_bid": "1.0000", f"{p}_ask": "1.0002", f"{p}_spread": "0.0002",
                f"{p}_bid_timestamp_ms": str(checkpoint), f"{p}_ask_timestamp_ms": str(checkpoint),
                f"{p}_bid_age_ms": "0", f"{p}_ask_age_ms": "0",
                f"{p}_availability": "CAUSAL_TWO_SIDED_AVAILABLE",
            })
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader(); writer.writerow(row)
        derived = gzip.compress(buf.getvalue().encode(), compresslevel=9)
        derived_path = "derived/TEST_EXACT_WINDOW_QUOTES.csv.gz"
        meta = {
            "path": derived_path, "rows": 1, "sha256": hashlib.sha256(derived).hexdigest(),
            "missing_two_sided_at_boundary": 0,
            "two_sided_but_older_than_2s_at_boundary": 0,
            "negative_spread_states_across_delays": 0,
        }
        manifest = bound({
            "schema": "mxm.research-core-v3.maxt14-friction-evidence-bundle.v1",
            "plan_binding_sha256": plan["binding_sha256"],
            "source_corrected_region_assessment_sha256": "b" * 64,
            "source_corrected_friction_scope_plan_sha256": "c" * 64,
            "account_fingerprint_sha256": "d" * 64,
            "protected_forward_opened": False, "candidate_outcomes_opened": False,
            "orders": False, "account_mutation": False, "fill_authority": False,
            "economic_certification": False, "candidate_freeze_authority": False,
            "raw_ticks_embedded_in_transfer_bundle": False,
            "geometry": {"symbols": 1, "exact_windows": 1},
            "derived_exact_window_evidence": {"TEST": meta},
        })
        files = {
            derived_path: derived,
            "evidence/provenance_manifest.json": json.dumps(manifest, sort_keys=True).encode(),
        }
        checksums = "".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
        ).encode()
        files["CHECKSUMS.sha256"] = checksums
        bundle = root / "bundle.zip"
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in files.items():
                zf.writestr(name, data + (b"X" if tamper and name == derived_path else b""))
        return plan_path, bundle

    def test_accepts_integrity_bound_quote_bundle_without_net_claim(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan, bundle = self._fixture(root)
            result = assess_bundle(root, bundle, plan_path=plan)
            self.assertTrue(result["historical_bid_ask_component_accepted"])
            self.assertFalse(result["candidate_frozen"])
            self.assertFalse(result["net_certification"])
            self.assertEqual(result["historical_bid_ask_exact_windows"], 1)
            self.assertEqual(result["symbols"]["TEST"]["delays"]["d0s"]["fresh_two_sided"], 1)

    def test_rejects_tampered_derived_payload(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan, bundle = self._fixture(root, tamper=True)
            with self.assertRaises(FrictionEvidenceError):
                assess_bundle(root, bundle, plan_path=plan)

if __name__ == "__main__":
    unittest.main(verbosity=2)
