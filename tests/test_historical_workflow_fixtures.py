import unittest
from pathlib import Path
from unittest.mock import patch
from tests.historical_workflow_fixtures import (
    FIXTURES, historical_workflow_source, assert_current_quarantined)

class HistoricalWorkflowFixtureTests(unittest.TestCase):
    def test_original_bytes_are_bound_to_both_sha256_and_git_blob(self):
        for name in FIXTURES:
            with self.subTest(name=name):
                self.assertTrue(historical_workflow_source(name))

    def test_live_legacy_routes_have_no_executable_job_or_credentials(self):
        for name in FIXTURES:
            with self.subTest(name=name):
                assert_current_quarantined(name)

    def test_changed_fixture_is_refused(self):
        with patch.object(Path,'read_bytes',return_value=b'changed historical workflow'):
            for name in FIXTURES:
                with self.subTest(name=name), self.assertRaisesRegex(AssertionError,'HISTORICAL_FIXTURE_SHA256'):
                    historical_workflow_source(name)
