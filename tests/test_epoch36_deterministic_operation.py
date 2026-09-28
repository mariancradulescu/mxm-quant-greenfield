import json
import unittest
from pathlib import Path

from research_v3.execution_router import RoutingError, load_authorized_deterministic_operation

ROOT = Path(__file__).resolve().parents[1]
OPERATION_REF = "research_v3/EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_DETERMINISTIC_OPERATION_V1.json"


class Epoch36DeterministicOperationTests(unittest.TestCase):
    def test_operation_binds_the_frozen_screen_and_requires_exact_head_green(self):
        operation = json.loads((ROOT / OPERATION_REF).read_text(encoding="utf-8"))
        state = {
            "current_research_evidence_epoch": 35,
            "next_action": operation["operation_name"],
            "next_deterministic_operation_ref": OPERATION_REF,
        }
        self.assertEqual(load_authorized_deterministic_operation(ROOT, state), operation)
        self.assertEqual(operation["development_zip_sha256"],
                         "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503")
        self.assertEqual(operation["replacement_zip_sha256"],
                         "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75")
        self.assertTrue(operation["execution_policy"]["exact_head_green_required_before_execution"])
        self.assertFalse(operation["execution_policy"]["new_semantic_judgment_required"])
        self.assertEqual(operation["result_validation"]["evidence_epoch"], 36)
        self.assertEqual(operation["accounting_effect"]["economic_outcomes"], 0)

    def test_operation_cannot_be_routed_under_a_different_action(self):
        operation = json.loads((ROOT / OPERATION_REF).read_text(encoding="utf-8"))
        state = {
            "current_research_evidence_epoch": 35,
            "next_action": "RUN_ANOTHER_SCREEN",
            "next_deterministic_operation_ref": OPERATION_REF,
        }
        with self.assertRaisesRegex(RoutingError, "next_action mismatch"):
            load_authorized_deterministic_operation(ROOT, state)


if __name__ == "__main__":
    unittest.main()
