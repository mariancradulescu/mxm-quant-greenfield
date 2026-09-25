import json
import tempfile
import unittest
from pathlib import Path

from research_v3.general_ai_director_bridge import (
    AIProposalRejected,
    _validate_proposed_next_state_routeability,
)


def proposal(next_state, decision=None, epoch=25):
    return {
        "next_research_state": next_state,
        "decision": decision or {},
        "evidence_binding": {"evidence_epoch_seen": epoch},
        "data_policy": {"new_market_data_requested": False},
    }


class NextStateRouteabilityV1Tests(unittest.TestCase):
    def test_unrouted_nonempty_action_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(AIProposalRejected, "without executable routing authority"):
                _validate_proposed_next_state_routeability(
                    Path(td),
                    proposal({
                        "status": "READY",
                        "next_action": "DO_DETERMINISTIC_THING",
                        "implementation_ai_required": False,
                        "research_judgment_required": False,
                    }),
                )

    def test_semantic_route_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            _validate_proposed_next_state_routeability(
                Path(td),
                proposal({
                    "status": "FRESH_GENERAL_AI_REASONING_REQUIRED",
                    "next_action": "AI_SELECT_NEXT_FRONTIER_ACTION",
                    "ai_reasoning_required": True,
                    "implementation_ai_required": False,
                }),
            )

    def test_implementation_route_requires_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaisesRegex(AIProposalRejected, "without explicit implementation scope"):
                _validate_proposed_next_state_routeability(
                    root,
                    proposal({
                        "status": "IMPLEMENTATION_REQUIRED",
                        "next_action": "IMPLEMENT_NEW_EXECUTOR",
                        "implementation_ai_required": True,
                    }),
                )
            _validate_proposed_next_state_routeability(
                root,
                proposal({
                    "status": "IMPLEMENTATION_REQUIRED",
                    "next_action": "IMPLEMENT_NEW_EXECUTOR",
                    "implementation_ai_required": True,
                }, decision={"implementation_scope": {"deliverable": "executor"}}),
            )

    def test_deterministic_route_requires_real_matching_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            rel="research_v3/NEXT_DETERMINISTIC.json"
            path=root/rel
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "schema":"mxm.greenfield.deterministic-next-operation.v1",
                "status":"AUTHORIZED_DETERMINISTIC_NON_ECONOMIC_OPERATION",
                "evidence_epoch":25,
                "operation_name":"DO_DETERMINISTIC_THING",
                "execution_policy":{
                    "implementation_ai_required":False,
                    "copilot_reasoning_required":False,
                    "new_semantic_judgment_required":False,
                },
                "accounting_effect":{"v2_attempts":0,"economic_outcomes":0},
            }),encoding="utf-8")
            _validate_proposed_next_state_routeability(
                root,
                proposal({
                    "status":"READY",
                    "next_action":"DO_DETERMINISTIC_THING",
                    "next_deterministic_operation_ref":rel,
                    "implementation_ai_required":False,
                }),
            )


if __name__=="__main__":
    unittest.main()
