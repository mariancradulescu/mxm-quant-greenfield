import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research_core_v3.model import load_csv
from research_core_v3.capture_ingest import load_capture


class AuthenticCsvContract(unittest.TestCase):
    def test_authentic_collector_header_is_lossless(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.csv'
            path.write_text('time_utc,open,high,low,close,tick_volume\n'
                            '2026-01-01T00:00:00Z,1,2,0.5,1.5,7\n'
                            '2026-01-01T00:05:00Z,1.5,2,1,1.75,8\n')
            series = load_csv(path)
            self.assertEqual(len(series.bars), 2)
            self.assertEqual(series.bars[0].open, 1)
            self.assertEqual(series.bars[1].close, 1.75)
            self.assertEqual([b.ts.minute for b in series.bars], [0, 5])

    def test_no_silent_fabrication_for_broken_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.csv'
            path.write_text('time_utc,open,high,low,close,tick_volume\n'
                            '2026-01-01T00:00:00Z,1,0.5,2,1.5,7\n')
            self.assertIsNone(load_csv(path))


if __name__ == '__main__':
    unittest.main()
