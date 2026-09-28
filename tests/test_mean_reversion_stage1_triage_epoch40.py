import base64
import gzip
import hashlib
import io
import json
import unittest
import zipfile
from pathlib import Path

from research_v3.mean_reversion_stage1_triage_epoch40 import _read_series

ROOT = Path(__file__).resolve().parents[1]
OP = "research_v3/EPOCH40_MEAN_REVERSION_STAGE1_TRIAGE_DETERMINISTIC_OPERATION_V1.json"


class Stage1TriageTests(unittest.TestCase):
    def test_bound_payload_preserves_full_frame_and_no_economic_promotion(self):
        op = json.loads((ROOT / OP).read_text())
        encoded = (ROOT / op["payload_ref"]).read_text().strip()
        self.assertEqual(hashlib.sha256(encoded.encode()).hexdigest(), op["payload_sha256"])
        result = json.loads(gzip.decompress(base64.b64decode(encoded, validate=True)))
        self.assertEqual(len(result["identities"]), 1576)
        self.assertEqual(result["coverage"]["identities_with_verified_m5_bars"], 45)
        self.assertEqual(sum(row["observed_m5_bars"] > 0 for row in result["identities"]), 45)
        self.assertFalse(result["interpretation_boundary"]["economic_promotion_authorized"])
        self.assertFalse(result["interpretation_boundary"]["candidate_identity_created"])
        self.assertFalse(result["interpretation_boundary"]["mechanism_family_closed"])
        self.assertEqual(result["accounting_effect"]["v2_attempts_consumed"], 0)
        self.assertEqual(result["accounting_effect"]["economic_outcomes_opened"], 0)
        self.assertEqual(len(result["source_authority"]["captures"]), 4)
        self.assertTrue(all(row["status"] == "HASH_VERIFIED_AND_READ" for row in result["source_authority"]["captures"]))

    def test_conflicting_duplicate_broker_bars_fail_closed(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("raw/1_test_M5.csv", "time_utc,close\n2026-06-15T00:00:00Z,1.0\n2026-06-15T00:00:00Z,2.0\n")
        buf.seek(0)
        with zipfile.ZipFile(buf) as archive:
            with self.assertRaisesRegex(ValueError, "conflicting duplicate timestamp"):
                _read_series(archive, "raw/1_test_M5.csv")


if __name__ == "__main__":
    unittest.main()
