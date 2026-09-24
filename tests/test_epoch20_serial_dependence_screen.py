import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research_v3.epoch20_serial_dependence_screen import run


class Epoch20StructuralScreenTests(unittest.TestCase):
    def test_hash_binding_and_gap_exclusion(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "capture.zip"
            with zipfile.ZipFile(path, "w") as archive:
                for i in range(40):
                    out = io.StringIO()
                    writer = csv.writer(out)
                    writer.writerow(("time_utc", "close"))
                    for k in range(12):
                        minute = k * 5 + (5 if k >= 6 else 0)
                        stamp=datetime(2026,6,15,tzinfo=timezone.utc)+timedelta(minutes=minute)
                        writer.writerow((stamp.isoformat().replace("+00:00","Z"), 100 + k))
                    archive.writestr(f"raw/{i}_S{i}_M5.csv", out.getvalue())
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                run(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with patch("research_v3.epoch20_serial_dependence_screen.SOURCE_SHA", digest):
                out = run(path)
            self.assertEqual(len(out["series"]), 40)
            self.assertEqual(out["series"]["raw/0_S0_M5.csv"]["1"]["observations"], 8)
            self.assertEqual(out["economic_effect"]["attempts_consumed"], 0)


if __name__ == "__main__":
    unittest.main()
