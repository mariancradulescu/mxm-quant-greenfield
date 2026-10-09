"""Fabricated disclosure fixtures; no historical data and no credentials."""
import unittest

from research_core_v4.numeric_development_v1.public_output_guard_v1 import (
    PublicDisclosureDenied, validate_public_blob, safe_public_git_blob
)

PATH = "research_core_v4/numeric_development_v1/public_status/SECURITY_RESULT_V1.json"
BASE = {
    "schema": "mxm.master1576.public.status.v1",
    "phase": "SECURITY_PREFLIGHT",
    "status": "PASS",
    "source_head": "a" * 40,
    "identity_count": 1576,
    "input_shard_count": 100,
}

class TestPublicGuard(unittest.TestCase):
    def test_approved_exact_schema(self):
        self.assertIn(b'"identity_count":1576', validate_public_blob(PATH, BASE))

    def test_publication_occurs_only_after_validation(self):
        called = []
        safe_public_git_blob(PATH, dict(BASE), lambda raw: called.append(raw))
        self.assertEqual(len(called), 1)
        with self.assertRaises(PublicDisclosureDenied):
            safe_public_git_blob(PATH, {**BASE, "ohlcv": [1, 2]}, lambda raw: called.append(raw))
        self.assertEqual(len(called), 1)

    def test_fabricated_sensitive_fields_rejected(self):
        fixtures = {
            "timestamp_bitmap": "10101",
            "hourly_mask": "11100",
            "per_bar_ohlcv": [{"open": 42, "close": 43}],
            "return_observations": [0.001, -0.002],
            "identity_event_vector": {"ordinal": 1, "events": [1, 0]},
            "private_key": "-----BEGIN PRIVATE KEY----- FAKE ONLY",
            "credential": "fake-password",
            "per_identity_responses": [1, -1],
            "nested_structure": {"safe": {"not": "approved"}},
            "feature_lag_vector": [0, 300, 900],
            "exact_event_timestamps": ["2026-08-20T00:00:00Z"],
        }
        for k, v in fixtures.items():
            with self.subTest(fixture=k), self.assertRaises(PublicDisclosureDenied):
                validate_public_blob(PATH, {**BASE, k: v})

    def test_scope_and_malformed_values_rejected(self):
        bads = [
            ("/tmp/result.json", BASE),
            ("research_core_v4/numeric_development_v1/public_status/../X_V1.json", BASE),
            (PATH, {**BASE, "schema": "mxm.private.numeric.response.v1"}),
            (PATH, {**BASE, "phase": "GROSS_RESULTS"}),
            (PATH, {**BASE, "source_head": "not-a-sha"}),
            (PATH, {**BASE, "identity_count": 145}),
            (PATH, {**BASE, "input_shard_count": 101}),
            (PATH, {**BASE, "resource_cpu_seconds": float("nan")}),
            (PATH, {**BASE, "encrypted_artifact_name": "../plaintext.json"}),
            (PATH, {**BASE, "encrypted_artifact_sha256": "xyz"}),
            (PATH, {**BASE, "run_id": True}),
            (PATH, {**BASE, "status": ["PASS"]}),
            (PATH, {**BASE, "nested_structure": {"a": 1}}),
        ]
        for p, v in bads:
            with self.subTest(path=p, payload=v), self.assertRaises(PublicDisclosureDenied):
                validate_public_blob(p, v)

if __name__ == "__main__":
    unittest.main()
