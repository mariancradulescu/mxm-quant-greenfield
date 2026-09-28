from __future__ import annotations
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.deterministic_operation_executor import _execute_epoch38_alignment_readiness
from research_v3.execution_router import load_authorized_deterministic_operation

ROOT=Path(__file__).resolve().parents[1]
OP_REF="research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_ACQUISITION_READINESS_OPERATION_V1.json"

class Epoch38DeterministicReadinessOperationTests(unittest.TestCase):
    def setUp(self):
        self.state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        self.op=json.loads((ROOT/OP_REF).read_text())

    def test_operation_routes_under_canonical_deterministic_schema(self):
        routed=load_authorized_deterministic_operation(ROOT,self.state)
        self.assertEqual(routed["schema"],"mxm.greenfield.deterministic-next-operation.v1")
        self.assertEqual(routed["operation_name"],self.state["next_action"])
        self.assertFalse(routed["execution_policy"]["implementation_ai_required"])
        self.assertTrue(routed["execution_policy"]["exact_head_green_required_before_execution"])

    def test_readiness_transition_is_zero_economic_and_returns_to_fresh_reasoning(self):
        fake={"status":"READY_FOR_FRESH_SEMANTIC_ACQUISITION_DECISION"}
        with patch("research_v3.epoch38_cross_sectional_aligned_history_scope_freeze.emit_readiness",return_value=fake):
            out=_execute_epoch38_alignment_readiness(ROOT,self.state,self.op)
        self.assertEqual(out["status"],"FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_EPOCH38_ALIGNMENT_READINESS")
        self.assertTrue(out["ai_reasoning_required"])
        self.assertTrue(out["implementation_satisfied"])
        self.assertFalse(out["implementation_ai_required"])
        self.assertIsNone(out["next_deterministic_operation_ref"])
        self.assertEqual(self.op["accounting_effect"],{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0})

    def test_operation_cannot_close_family_or_open_market_data(self):
        self.assertFalse(self.op["boundaries"]["family_exhaustion_authority"])
        self.assertFalse(self.op["boundaries"]["fetch_market_data"])
        self.assertFalse(self.op["boundaries"]["compute_predictive_outcome"])
        self.assertFalse(self.op["boundaries"]["compute_pnl"])

if __name__=="__main__":
    unittest.main()
