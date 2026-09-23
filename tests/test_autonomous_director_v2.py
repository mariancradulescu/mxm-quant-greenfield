import tempfile
import unittest
from pathlib import Path

from research_v3.autonomous_director_v2 import _candidate_score
from research_v3.autonomous_runtime_v2 import RuntimeV2
from research_v3.runtime_v2_primitives import load_json


class AutonomousDirectorV2UnitTests(unittest.TestCase):
    def test_candidate_score_prefers_sufficient_broad_observation(self):
        a = {
            "data_completeness": {"state": "SUFFICIENT"},
            "metrics": {"active_weeks": 13, "event_count": 100, "coarse_net_pnl": 1.0},
        }
        b = {
            "data_completeness": {"state": "SUFFICIENT"},
            "metrics": {"active_weeks": 12, "event_count": 500, "coarse_net_pnl": 99.0},
        }
        self.assertGreater(_candidate_score(a), _candidate_score(b))

    def test_runtime_non_economic_plan_does_not_open_runtime_economics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = {
                "operation_kind": "NON_ECONOMIC_DIRECTOR",
                "candidate_spec_hash": "a" * 64,
                "dataset_hash": "b" * 64,
                "evaluator_hash": "c" * 64,
                "cost_authority_hash": "d" * 64,
                "execution_semantics_version": "DIRECTOR_TEST",
                "lifecycle_phase": "AUTONOMY_ACCEPTANCE_NON_ECONOMIC",
                "evaluator": {"kind": "synthetic", "payload": {"decision": "PASS"}},
                "pre_outcome_gate": {"status": "PASS"},
                "safety": {"live_orders_authorized": False, "protected_evidence_opened": False},
                "external_data": {"required": False},
            }
            rt = RuntimeV2(root, lease_seconds=1)
            op, _ = rt.submit_operation(plan)
            result = rt.run(max_operations=1)
            self.assertEqual(result.status, "BOUNDED_CHECKPOINT")
            self.assertTrue(rt.journal.has(op, "NON_ECONOMIC_RESULT_AVAILABLE"))
            self.assertFalse(rt.journal.has(op, "ECONOMIC_RESULT_AVAILABLE"))
            accounting = load_json(root / "research_v3/runtime_v2/accounting.json", {})
            self.assertEqual(accounting.get("economic_outcomes_opened"), 0)


if __name__ == "__main__":
    unittest.main()
