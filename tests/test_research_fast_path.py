import json
import tempfile
import unittest
from pathlib import Path

from research_v3.research_spec_kernel import execute, load_spec

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "research_v3/EPOCH27_PROSPECTIVE_BREAKOUT_RESEARCH_SPEC_V1.json"
INPUT = ROOT / "research_v3/EPOCH27_BREAKOUT_EVENT_TABLE_V1.b64"
RESULT = ROOT / "evidence/EPOCH27_BREAKOUT_STABILITY_BREADTH_RESULT_V1.json"


class ResearchFastPathTests(unittest.TestCase):
    def test_frozen_real_input_reproduces_persisted_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            observed = execute(SPEC, INPUT, Path(tmp) / "result.json")
        persisted = json.loads(RESULT.read_text())
        self.assertEqual(observed, persisted)
        self.assertEqual(len(observed["symbol_results"]), 41)
        self.assertEqual(observed["economic_effect"]["v2_attempts_consumed"], 0)

    def test_mutated_semantic_spec_cannot_reuse_bound_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = json.loads(SPEC.read_text())
            spec["statistic"]["breadth_fraction_at_least"] = 0.01
            changed = Path(tmp) / "changed.json"
            changed.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, "not bound"):
                execute(changed, INPUT, Path(tmp) / "out.json")

    def test_unregistered_capability_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = json.loads(SPEC.read_text())
            spec["statistic"]["primitive"] = "UNKNOWN_EXECUTION_PRIMITIVE"
            changed = Path(tmp) / "changed.json"
            changed.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, "unregistered capability"):
                load_spec(changed)
