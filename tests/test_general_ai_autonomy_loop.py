import tempfile, unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_autonomy_loop import run
from research_v3.general_ai_implementation_executor import ImplementationRejected


class GeneralAIAutonomyProviderRecoveryTests(unittest.TestCase):
    def test_quota_failure_is_checkpointed_as_retryable_not_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            (root/"research_v3/ai_director").mkdir(parents=True)
            (root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(
                '{"status":"IMPLEMENTATION_REQUIRED","next_action":"IMPLEMENT_X","user_action_required":false,"current_research_evidence_epoch":16}'
            )
            with patch("research_v3.general_ai_autonomy_loop.validate_repository_state",return_value={}), \
                 patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=False), \
                 patch("research_v3.general_ai_autonomy_loop.implementation_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.implement",side_effect=ImplementationRejected("Copilot implementation failed: You have exceeded your monthly quota")), \
                 patch("research_v3.general_ai_autonomy_loop.GitCheckpointSink.checkpoint",return_value=None):
                out=run(root,max_cycles=1)
            self.assertEqual(out["status"],"PROVIDER_UNAVAILABLE")
            self.assertEqual(out["recovery"]["failure_class"],"MONTHLY_QUOTA_EXHAUSTED")
            self.assertEqual(len(out["recovery"]["request_fingerprint"]),64)
            with patch("research_v3.general_ai_autonomy_loop.validate_repository_state",return_value={}), patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=False), patch("research_v3.general_ai_autonomy_loop.implementation_required",return_value=True), patch("research_v3.general_ai_autonomy_loop.implement",side_effect=AssertionError("duplicate provider call")):
                again=run(root,max_cycles=1)
            self.assertEqual(again["status"],"PROVIDER_UNAVAILABLE")
            self.assertEqual(again["cycles"],0)
            self.assertEqual(out["recovery"]["current_evidence_epoch"],16)
            self.assertEqual(out["recovery"]["v2_attempts_consumed_delta"],0)
            self.assertTrue((root/"research_v3/ai_director/PROVIDER_RECOVERY_STATE.json").is_file())

    def test_semantic_implementation_rejection_remains_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            (root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(
                '{"status":"IMPLEMENTATION_REQUIRED","next_action":"IMPLEMENT_X","user_action_required":false}'
            )
            with patch("research_v3.general_ai_autonomy_loop.validate_repository_state",return_value={}), \
                 patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.reasoning_required",return_value=False), \
                 patch("research_v3.general_ai_autonomy_loop.implementation_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.implement",side_effect=ImplementationRejected("protected bytes changed")):
                with self.assertRaises(ImplementationRejected):
                    run(root,max_cycles=1)
