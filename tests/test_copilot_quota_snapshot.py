import tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from research_v3.copilot_quota_snapshot import normalize, record

class QuotaSnapshotTests(unittest.TestCase):
    def test_missing_quota_is_explicitly_unknown(self):
        row=normalize(None)
        self.assertTrue(all(value is None for value in row.values()))
    def test_supported_fields_are_copied_without_credit_estimation(self):
        q=normalize(SimpleNamespace(entitlement_requests=1500,used_requests=148,
             remaining_percentage=90.1,reset_date="2026-10-01"))
        with tempfile.TemporaryDirectory() as directory:
            doc=record(Path(directory),q,run_id="test")
            self.assertEqual(doc["quota"]["used_requests"],148)
            self.assertTrue(doc["session_cost_not_inferred"])
