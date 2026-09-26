import json
import tempfile
import unittest
from pathlib import Path

from research_v3.deterministic_operation_executor import (
    DeterministicOperationRejected,
    _run_epoch34_composite_screen,
)

ROOT = Path(__file__).resolve().parents[1]
OPERATION = ROOT / "research_v3/EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_DETERMINISTIC_OPERATION_V1.json"


class Epoch34DeterministicOperationTests(unittest.TestCase):
    def test_screen_waits_for_exact_head_green_and_hash_bound_transport(self):
        operation = json.loads(OPERATION.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            freeze_path = root / operation["freeze_ref"]
            freeze_path.parent.mkdir(parents=True)
            freeze_path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(DeterministicOperationRejected, "exact-head CI"):
                _run_epoch34_composite_screen(root, {"exact_head_green": False}, operation)
            with self.assertRaisesRegex(DeterministicOperationRejected, "transport-materialized"):
                _run_epoch34_composite_screen(root, {"exact_head_green": True}, operation)
            self.assertFalse((root / operation["result_ref"]).exists())


if __name__ == "__main__":
    unittest.main()
