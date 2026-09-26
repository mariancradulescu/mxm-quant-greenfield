import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_autonomy_loop import run
from research_v3.general_ai_implementation_executor import ImplementationRejected


def write_state(root: Path, **updates):
    state={
        "schema":"mxm.greenfield.runtime-v2-next-autonomous-state.v3",
        "status":"IMPLEMENTATION_REQUIRED",
        "next_action":"IMPLEMENT_X",
        "user_action_required":False,
        "external_data_required":False,
        "current_research_evidence_epoch":20,
        "evidence_epoch":20,
        "ai_reasoning_required":False,
        "research_judgment_required":False,
        "implementation_ai_required":True,
        "safety":{"live_orders_authorized":False,"protected_evidence_opened":False},
    }
    state.update(updates)
    path=root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(state),encoding="utf-8")
    return state


class GeneralAIAutonomyProviderRecoveryTests(unittest.TestCase):
    def test_quota_failure_is_checkpointed_as_retryable_not_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/ai_director").mkdir(parents=True)
            write_state(root,current_research_evidence_epoch=16,evidence_epoch=16)
            with patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=False), \
                 patch("research_v3.general_ai_autonomy_loop.implementation_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.implement",side_effect=ImplementationRejected("Copilot implementation failed: You have exceeded your monthly quota")), \
                 patch("research_v3.general_ai_autonomy_loop._request_fingerprint",return_value="a"*64), \
                 patch("research_v3.general_ai_autonomy_loop.GitCheckpointSink.checkpoint",return_value=None):
                out=run(root,max_cycles=1)
            self.assertEqual(out["status"],"PROVIDER_UNAVAILABLE")
            self.assertEqual(out["progress_class"],"PROVIDER_UNAVAILABLE")
            self.assertEqual(out["recovery"]["failure_class"],"MONTHLY_QUOTA_EXHAUSTED")
            self.assertEqual(len(out["recovery"]["request_fingerprint"]),64)
            with patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=False), \
                 patch("research_v3.general_ai_autonomy_loop.implementation_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.implement",side_effect=AssertionError("duplicate provider call")):
                again=run(root,max_cycles=1)
            self.assertEqual(again["status"],"PROVIDER_UNAVAILABLE")
            self.assertEqual(again["cycles"],0)
            self.assertEqual(out["recovery"]["current_evidence_epoch"],16)
            self.assertEqual(out["recovery"]["v2_attempts_consumed_delta"],0)

    def test_legacy_quota_checkpoint_blocks_provider_across_phases(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/ai_director").mkdir(parents=True)
            write_state(root)
            legacy={"status":"PROVIDER_RETRY_REQUIRED","phase":"GENERAL_AI_IMPLEMENTATION",
                    "current_evidence_epoch":20,"pending_status":"IMPLEMENTATION_REQUIRED",
                    "pending_next_action":"IMPLEMENT_X","detail":"You have exceeded your monthly quota"}
            (root/"research_v3/ai_director/PROVIDER_RECOVERY_STATE.json").write_text(json.dumps(legacy))
            with patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=False), \
                 patch("research_v3.general_ai_autonomy_loop.implementation_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.implement",side_effect=AssertionError("legacy quota must not call Copilot")):
                out=run(root,max_cycles=1)
            self.assertEqual(out["status"],"PROVIDER_UNAVAILABLE")
            write_state(root,status="FRESH_GENERAL_AI_REASONING_REQUIRED",next_action="AI_NEW_EPOCH_DECISION",
                        current_research_evidence_epoch=21,evidence_epoch=21,
                        ai_reasoning_required=True,research_judgment_required=True,implementation_ai_required=False)
            with patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.reason",side_effect=AssertionError("exhausted account must not be called")):
                across_phase=run(root,max_cycles=1)
            self.assertEqual(across_phase["status"],"PROVIDER_UNAVAILABLE")

    def test_transient_provider_failure_remains_retryable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/ai_director").mkdir(parents=True)
            write_state(root)
            with patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=False), \
                 patch("research_v3.general_ai_autonomy_loop.implementation_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.implement",side_effect=ImplementationRejected("temporarily unavailable")), \
                 patch("research_v3.general_ai_autonomy_loop._request_fingerprint",return_value="b"*64), \
                 patch("research_v3.general_ai_autonomy_loop.GitCheckpointSink.checkpoint",return_value=None):
                out=run(root,max_cycles=1)
            self.assertEqual(out["status"],"PROVIDER_RETRY_REQUIRED")

    def test_fresh_non_economic_reasoning_does_not_wait_for_exact_head_ci(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            write_state(root,status="FRESH_GENERAL_AI_REASONING_REQUIRED",next_action="AI_REASSESS",
                        current_research_evidence_epoch=21,evidence_epoch=21,
                        ai_reasoning_required=True,research_judgment_required=True,implementation_ai_required=False)
            with patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.reason",return_value={"status":"EXTERNAL_PROPOSAL_REUSED"}) as reason, \
                 patch("research_v3.general_ai_autonomy_loop.drain",return_value={"status":"PASS"}), \
                 patch("research_v3.general_ai_autonomy_loop._record_invocation",return_value=None):
                out=run(root,max_cycles=1)
            self.assertEqual(out["trace"][0]["kind"],"GENERAL_AI_REASONING")
            reason.assert_called_once()

    def test_semantic_implementation_rejection_remains_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            write_state(root)
            with patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=False), \
                 patch("research_v3.general_ai_autonomy_loop.implementation_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.implement",side_effect=ImplementationRejected("protected bytes changed")):
                with self.assertRaises(ImplementationRejected):
                    run(root,max_cycles=1)


if __name__=="__main__":
    unittest.main()
