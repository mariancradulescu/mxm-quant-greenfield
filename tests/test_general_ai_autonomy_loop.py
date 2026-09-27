import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_autonomy_loop import run, _park_authority, _blocked_scopes, _recoverable_provider_failure, _persist_provider_recovery, _current_authority_request, _park_current_local_authority, MAX_RECOVERABLE_PROVIDER_FAILURES
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
    def test_legacy_authority_is_parked_only_by_unambiguous_canonical_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            state=write_state(root,current_research_evidence_epoch=31,evidence_epoch=31,
                              families_blocked_on_data=["CARRY_TERM_STRUCTURE"],
                              broader_universe_remains_open=True,family_exhaustion=False)
            request={"status":"ADDITIONAL_AUTHORITY_REQUIRED","request_id":"old",
                     "blocked_scope_ids":["CARRY_TERM_STRUCTURE"],
                     "evidence_epoch":31,"requested_authority_or_class":"opaque provider text"}
            with patch("research_v3.general_ai_autonomy_loop.current_evidence_binding",return_value={"current_open_mechanism_families":["CARRY_TERM_STRUCTURE"]}), \
                 patch("research_v3.general_ai_autonomy_loop.GitCheckpointSink.checkpoint",return_value=None):
                self.assertTrue(_park_authority(root,state,request,git_checkpoint=False,git_push=False))
            parked=json.loads((root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json").read_text())
            self.assertEqual(parked["blocked_scope_ids"],["CARRY_TERM_STRUCTURE"])
            self.assertEqual(parked["scope_provenance"]["source_request_id"],"old")
            self.assertEqual(_blocked_scopes(root),["CARRY_TERM_STRUCTURE"])
            with patch("research_v3.general_ai_autonomy_loop.current_evidence_binding",return_value={"current_open_mechanism_families":["CARRY_TERM_STRUCTURE"]}):
                self.assertFalse(_park_authority(root,state,{**request,"blocked_scope_ids":["A","B"]},
                                                 git_checkpoint=False,git_push=False))

    def test_current_accepted_proposal_scope_overrides_stale_inherited_blocked_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/ai_director/proposals").mkdir(parents=True)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            proposal={
                "proposal_id":"P","decision":{"status":"ADDITIONAL_AUTHORITY_REQUIRED",
                    "blocked_scope_id":"SEASONALITY_SESSION_TIME",
                    "requested_authority_or_class":"distinct session authority","rationale":"prospective only"},
                "evidence_binding":{"reasoning_request_id":"reason_new"}
            }
            (root/"research_v3/ai_director/proposals/P.json").write_text(json.dumps(proposal))
            (root/"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json").write_text(json.dumps({"accepted":[{
                "proposal_id":"P","proposal_hash":"h","proposal_ref":"research_v3/ai_director/proposals/P.json"}]}))
            state=write_state(root,status="ADDITIONAL_AUTHORITY_REQUIRED",next_action="AUTHORIZE",
                current_research_evidence_epoch=34,evidence_epoch=34,source_ai_proposal_id="P",
                source_ai_proposal_hash="h",blocked_scope_id="RELATIVE_VALUE_COINTEGRATION",
                requested_authority_or_class="distinct session authority",broader_universe_remains_open=True)
            request=_current_authority_request(root,state)
            self.assertEqual(request["blocked_scope_ids"],["SEASONALITY_SESSION_TIME"])
            with patch("research_v3.general_ai_autonomy_loop.current_evidence_binding",
                       return_value={"current_open_mechanism_families":["SEASONALITY_SESSION_TIME","TREND_MOMENTUM"]}), \
                 patch("research_v3.general_ai_autonomy_loop.GitCheckpointSink.checkpoint",return_value=None):
                parked=_park_current_local_authority(root,state,git_checkpoint=False,git_push=False)
            self.assertIsNotNone(parked)
            self.assertTrue(parked["next_state"]["ai_reasoning_required"])
            self.assertFalse(parked["next_state"]["implementation_ai_required"])
            self.assertNotIn("blocked_scope_id",parked["next_state"])
            self.assertIn("SEASONALITY_SESSION_TIME",_blocked_scopes(root))

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

    def test_deterministic_exact_head_pending_is_machine_routable_without_provider(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            state=write_state(root,status="DETERMINISTIC_OPERATION_READY_AFTER_IMPLEMENTATION_GREEN",
                              next_action="RUN_FROZEN_EPOCH34",current_research_evidence_epoch=33,evidence_epoch=33,
                              ai_reasoning_required=False,research_judgment_required=False,implementation_ai_required=False)
            pending={"status":"PENDING_EXACT_HEAD_GREEN","operation_name":"RUN_FROZEN_EPOCH34",
                     "exact_head":{"green":False,"head":"a"*40},"next_state":state,
                     "provider_calls_delta":0,"state_persisted":False}
            with patch("research_v3.general_ai_autonomy_loop.current_evidence_epoch",return_value=33), \
                 patch("research_v3.general_ai_autonomy_loop.refresh_derived_views",return_value={}), \
                 patch("research_v3.general_ai_autonomy_loop.stale_reasoning_redirect",return_value=None), \
                 patch("research_v3.general_ai_autonomy_loop.deterministic_operation_required",return_value=True), \
                 patch("research_v3.general_ai_autonomy_loop.execute_deterministic_chain",return_value=pending), \
                 patch("research_v3.general_ai_autonomy_loop.reason",side_effect=AssertionError("CI recovery must not call provider")):
                out=run(root,max_cycles=1)
            self.assertEqual(out["status"],"PENDING_EXACT_HEAD_GREEN")
            self.assertEqual(out["result"]["exact_head"]["head"],"a"*40)
            self.assertEqual(out["trace"][0]["provider_calls_delta"],0)

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


    def test_provider_timeout_is_recoverable_and_bounded_per_semantic_request(self):
        self.assertGreaterEqual(MAX_RECOVERABLE_PROVIDER_FAILURES,2)
        exc=subprocess.TimeoutExpired(cmd=["copilot"],timeout=300)
        self.assertTrue(_recoverable_provider_failure(exc))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            write_state(root)
            (root/"research_v3/ai_director").mkdir(parents=True,exist_ok=True)
            with patch("research_v3.general_ai_autonomy_loop._request_fingerprint",return_value="f"*64), \
                 patch("research_v3.general_ai_autonomy_loop.GitCheckpointSink.checkpoint",return_value=None):
                first=_persist_provider_recovery(root,exc,phase="GENERAL_AI_IMPLEMENTATION",git_checkpoint=False,git_push=False)
                self.assertEqual(first["status"],"PROVIDER_RETRY_REQUIRED")
                last=first
                for _ in range(1,MAX_RECOVERABLE_PROVIDER_FAILURES):
                    last=_persist_provider_recovery(root,exc,phase="GENERAL_AI_IMPLEMENTATION",git_checkpoint=False,git_push=False)
                self.assertEqual(last["status"],"PROVIDER_RETRY_BUDGET_EXHAUSTED")
                self.assertEqual(last["consecutive_recoverable_failures"],MAX_RECOVERABLE_PROVIDER_FAILURES)

if __name__=="__main__":
    unittest.main()
