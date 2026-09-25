import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class RelativeValuePrerequisiteTests(unittest.TestCase):
    def test_alignment_inventory_is_complete_and_non_economic(self):
        doc = json.loads((ROOT / "evidence/EPOCH24_RELATIVE_VALUE_ALIGNMENT_PREREQUISITE_V1.json").read_text())
        registry = json.loads((ROOT / "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json").read_text())
        symbols = {row["broker_symbol"] for row in registry["representatives"]}
        self.assertEqual(len(symbols), 41)
        self.assertEqual(set(doc["representatives"]), symbols)
        self.assertEqual(doc["pair_count"], 820)
        self.assertEqual(len(doc["pairs"]), 820)
        self.assertEqual(len({tuple(p["symbols"]) for p in doc["pairs"]}), 820)
        self.assertTrue(all(p["symbols"][0] < p["symbols"][1] for p in doc["pairs"]))
        self.assertEqual(sum(p["common_m5_timestamps"] > 0 for p in doc["pairs"]), doc["pairs_with_any_common_bar"])
        self.assertEqual(doc["pairs_with_any_common_bar"], 793)
        self.assertFalse(doc["economic_effect"]["returns_or_pnl_computed"])
        self.assertFalse(doc["economic_effect"]["protected_forward_opened"])
        self.assertEqual(doc["economic_effect"]["v2_attempts"], 0)
        self.assertEqual(doc["economic_effect"]["economic_outcomes"], 0)
        self.assertNotIn("selected_pair", doc)

if __name__ == "__main__":
    unittest.main()
