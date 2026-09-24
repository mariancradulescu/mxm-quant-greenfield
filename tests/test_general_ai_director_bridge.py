import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_reasoning_provider import reasoning_required
from research_v3.general_ai_autonomy_loop import run as autonomous_loop
from research_v3.general_ai_director_bridge import (
    AIProposalRejected,
    PROPOSAL_SCHEMA,
    _validate_authoritative_data_contract,
    _active_authoritative_data_contract,
    _reject_completed_outer_as_unseen,
    _reject_duplicate_accepted_capture,
    _validate_broker_native_selection,
    compile_runtime_plan,
    drain,
    materialize_proposal,
    proposal_hash,
    validate_proposal_shape,
)


def base_proposal(objective_class="ARBITRARY_NEW_RESEARCH_CLASS"):
    return {
        "schema": PROPOSAL_SCHEMA,
        "proposal_id": "test-proposal",
        "provider": {"kind": "TEST_AI"},
        "basis": {},
        "objective": {
            "class": objective_class,
            "goal": "Reason about a genuinely new research question.",
            "information_gain_rationale": "Test that no finite class mapping is required.",
        },
        "decision": {"novel_structure": {"anything": [1, 2, 3]}},
        "next_research_state": {"status": "TEST", "novel_action": "UNSEEN_ACTION_NAME"},
        "authority_refs": ["authority.json"],
        "economic_effect": {
            "open_economic_outcome": False,
            "consume_v2_attempt": 0,
            "create_new_v2_identity": False,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "competition_start_authorized": False,
        },
        "scope_law": {
            "rerun_exact_observed_identity": False,
            "refund_observed_attempts": False,
            "mechanism_family_closure_claims": [],
        },
        "data_policy": {
            "no_default_multi_year_download": True,
            "user_selects_symbols_or_horizon": False,
            "new_market_data_requested": False,
        },
        "causal_contract": {
            "chronological_incremental_replay": True,
            "causal_entry_admission": True,
            "future_information_forbidden": True,
            "protected_forward_leakage_forbidden": True,
            "learned_procedure_freeze_before_outer_outcome": True,
        },
        "publication": {"apply_to_next_state": False},
    }


class GeneralAIDirectorBridgeTests(unittest.TestCase):
    def _outer_fixture(self, root, *, completed):
        freeze = "research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json"
        plan = "data/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json"
        capture = "evidence/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CAPTURE_ACCEPTANCE_V1.json"
        result = "evidence/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CONFIRMATORY_RESULT_V1.json"
        interpretation = "evidence/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_INTERPRETATION_V1.json"
        for rel in (freeze, plan, capture, result, interpretation):
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(rel), dest)
        state = {
            "status": "WAITING_EXTERNAL_AUTHENTICATED_DATA",
            "next_action": "AWAIT_INDEPENDENT_OUTER_CAPTURE",
            "source_freeze_ref": freeze,
            "outer_capture_plan_ref": plan,
            "user_action_required": True,
        }
        if completed:
            state.update({
                "status": "AI_REASONING_REQUIRED_AFTER_COMPLETED_OUTER",
                "next_action": "AI_SELECT_HIGHEST_INFORMATION_LEGAL_NEXT_ACTION_FROM_COMPLETE_EVIDENCE",
                "ai_reasoning_required": True,
                "user_action_required": False,
                "outer_data_binding_ref": capture,
                "capture_acceptance_ref": capture,
                "result_ref": result,
                "interpretation_ref": interpretation,
            })
        dest = root / "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(state))
        return state

    def _new_broker_native_scope(self):
        proposal = base_proposal()
        proposal["data_policy"].update({
            "new_market_data_requested": True,
            "minimal_acquisition_request": {
                "source_domain": "PEPPERSTONE_ACCOUNT_VIA_CTRADER_OPEN_API",
                "symbols": ["FUTURE_BROKER_SYMBOL"],
                "resolution": "M15",
                "start_utc": "2026-08-03T00:00:00Z",
                "end_utc": "2026-08-17T23:59:59Z",
                "fields": ["time_utc", "open", "high", "low", "close"],
                "information_gain_justification": "Illustrative prospectively specified scope; no acquisition or alpha claim.",
            },
        })
        return proposal

    def test_objective_class_is_open_not_enum(self):
        for cls in (
            "TOTALLY_UNSEEN_CAUSAL_MODEL_FAMILY",
            "NOVEL_UNIVERSE_DISCOVERY_METHOD",
            "FUTURE_RESEARCH_CLASS_NOT_KNOWN_TODAY",
        ):
            validate_proposal_shape(base_proposal(cls))

    def test_free_form_decision_and_next_state_are_allowed(self):
        proposal = base_proposal()
        proposal["decision"]["new_future_method"] = {"alpha": "not hardcoded"}
        proposal["next_research_state"]["unseen_future_field"] = 42
        validate_proposal_shape(proposal)

    def test_pending_outer_rejects_panel_substitution(self):
        proposal = base_proposal()
        proposal["data_policy"]["new_market_data_requested"] = True
        proposal["data_policy"]["minimal_acquisition_request"] = {
            "symbols": ["USTN2YR-F","TLT.US","NVDA.US-24","VIX","HSTECH","ADAUSD"],
            "resolution": "M5",
            "start_utc": "2026-03-30T00:00:00Z",
            "end_utc": "2026-07-19T23:59:59Z",
            "fields": ["time_utc","open","high","low","close"],
            "information_gain_justification": "test",
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._outer_fixture(root, completed=False)
            with self.assertRaisesRegex(AIProposalRejected,"violates frozen outer panel"):
                _validate_authoritative_data_contract(root, proposal)

    def test_pending_outer_accepts_exact_frozen_scope(self):
        proposal = base_proposal()
        proposal["data_policy"]["new_market_data_requested"] = True
        proposal["data_policy"]["minimal_acquisition_request"] = {
            "symbols": ["MXNJPY","USDCAD","EURUSD","IWM.US","TLT.US","NVDA.US-24"],
            "resolution": "M5",
            "start_utc": "2026-03-30T00:00:00Z",
            "end_utc": "2026-07-19T23:59:59Z",
            "fields": ["time_utc","open","high","low","close"],
            "information_gain_justification": "test",
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._outer_fixture(root, completed=False)
            _validate_authoritative_data_contract(root, proposal)

    def test_pending_outer_rejects_interval_drift(self):
        proposal = base_proposal()
        proposal["data_policy"]["new_market_data_requested"] = True
        proposal["data_policy"]["minimal_acquisition_request"] = {
            "symbols": ["MXNJPY","USDCAD","EURUSD","IWM.US","TLT.US","NVDA.US-24"],
            "resolution": "M5",
            "start_utc": "2026-02-23T00:00:00Z",
            "end_utc": "2026-06-14T23:59:59Z",
            "fields": ["time_utc","open","high","low","close"],
            "information_gain_justification": "test",
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._outer_fixture(root, completed=False)
            with self.assertRaisesRegex(AIProposalRejected,"frozen outer interval"):
                _validate_authoritative_data_contract(root, proposal)

    def test_ai_cannot_open_economics_through_bridge(self):
        proposal = base_proposal()
        proposal["economic_effect"]["open_economic_outcome"] = True
        with self.assertRaises(AIProposalRejected):
            validate_proposal_shape(proposal)

    def test_ai_cannot_overwrite_protected_accounting_state(self):
        proposal = base_proposal()
        proposal["next_research_state"]["accounting"] = {"v2_attempts_used": 0}
        with self.assertRaises(AIProposalRejected):
            validate_proposal_shape(proposal)

    def test_new_data_request_requires_ai_selected_minimal_scope(self):
        proposal = base_proposal()
        proposal["data_policy"]["new_market_data_requested"] = True
        with self.assertRaises(AIProposalRejected):
            validate_proposal_shape(proposal)
        proposal["data_policy"]["minimal_acquisition_request"] = {
            "source_domain": "PEPPERSTONE_ACCOUNT_VIA_CTRADER_OPEN_API",
            "symbols": ["FUTURE_SYMBOL"],
            "resolution": "M5",
            "start_utc": "2026-01-01T00:00:00Z",
            "end_utc": "2026-01-08T00:00:00Z",
            "fields": ["time", "open", "high", "low", "close"],
            "information_gain_justification": "Prospectively sufficient pilot.",
        }
        validate_proposal_shape(proposal)

    def test_completed_outer_does_not_reopen_old_data_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._outer_fixture(root, completed=True)
            self.assertIsNone(_active_authoritative_data_contract(root))
            path = root / "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json"
            malformed = json.loads(path.read_text())
            malformed["interpretation_ref"] = "evidence/nonexistent.json"
            path.write_text(json.dumps(malformed))
            with self.assertRaises(AIProposalRejected):
                _active_authoritative_data_contract(root)

    def test_completed_outer_cannot_be_reused_as_unseen_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); state = self._outer_fixture(root, completed=True)
            proposal = base_proposal()
            proposal["data_bindings"] = [{"ref": state["result_ref"], "role": "UNSEEN_CONFIRMATION"}]
            with self.assertRaisesRegex(AIProposalRejected, "cannot be reused as unseen"):
                _reject_completed_outer_as_unseen(root, proposal)
            proposal["data_bindings"][0]["role"] = "OBSERVED_HISTORICAL_CONTEXT"
            _reject_completed_outer_as_unseen(root, proposal)

    def test_completed_outer_allows_new_prospective_broker_native_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._outer_fixture(root, completed=True)
            proposal = self._new_broker_native_scope()
            validate_proposal_shape(proposal)
            _validate_authoritative_data_contract(root, proposal)
            _reject_completed_outer_as_unseen(root, proposal)

    def test_new_scope_still_requires_prospective_causal_data_contract(self):
        proposal = self._new_broker_native_scope()
        del proposal["data_policy"]["minimal_acquisition_request"]["information_gain_justification"]
        with self.assertRaisesRegex(AIProposalRejected, "prospectively required field"):
            validate_proposal_shape(proposal)
        proposal = self._new_broker_native_scope()
        proposal["causal_contract"]["future_information_forbidden"] = False
        with self.assertRaisesRegex(AIProposalRejected, "causal contract"):
            validate_proposal_shape(proposal)
        proposal = self._new_broker_native_scope()
        proposal["data_policy"]["minimal_acquisition_request"]["source_domain"] = "YAHOO_FINANCE"
        with self.assertRaisesRegex(AIProposalRejected, "broker-native"):
            validate_proposal_shape(proposal)

    def test_accepted_structural_capture_cannot_be_requested_again(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); state = self._outer_fixture(root, completed=True)
            plan_ref = "data/C031_STRUCTURAL_EXTENSION_WAVE_01_M5_CAPTURE_PLAN_V1.json"
            capture_ref = "evidence/C031_STRUCTURAL_EXTENSION_WAVE_01_CAPTURE_ACCEPTANCE_V1.json"
            report_ref = "evidence/SESSION_GAP_STRUCTURAL_EXTENSION_WAVE_01_REPORT_V1.json"
            for rel in (plan_ref, capture_ref, report_ref):
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(rel), dest)
            state.update(completed_capture_plan_ref=plan_ref, completed_capture_ref=capture_ref,
                         completed_structural_report_ref=report_ref)
            (root / "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(json.dumps(state))
            plan = json.loads((root / plan_ref).read_text())
            proposal = self._new_broker_native_scope()
            request = proposal["data_policy"]["minimal_acquisition_request"]
            request.update(symbols=[x["broker_symbol"] for x in plan["symbols"]],
                           resolution=plan["resolution"], start_utc=plan["interval"]["start_utc"],
                           end_utc=plan["interval"]["end_utc"])
            with self.assertRaisesRegex(AIProposalRejected, "already accepted and screened"):
                _reject_duplicate_accepted_capture(root, proposal)
            request["symbols"] = ["DIFFERENT_BROKER_NATIVE_SYMBOL"]
            _reject_duplicate_accepted_capture(root, proposal)

    def test_broker_native_index_rejects_infeasible_and_unknown_ai_symbols(self):
        proposal = self._new_broker_native_scope()
        request = proposal["data_policy"]["minimal_acquisition_request"]
        request["symbols"] = ["BTCUSD"]
        with self.assertRaisesRegex(AIProposalRejected, "infeasible at initial EUR200"):
            _validate_broker_native_selection(Path("."), proposal)
        request["symbols"] = ["GER30"]
        with self.assertRaisesRegex(AIProposalRejected, "identity absent"):
            _validate_broker_native_selection(Path("."), proposal)
        request["symbols"] = ["GER40"]
        _validate_broker_native_selection(Path("."), proposal)
        request["symbols"] = ["BTCUSD"]
        proposal["data_policy"]["future_equity_only_scope"] = {
            "symbols": ["BTCUSD"],
            "prospective_rationale": "Observe broker-native structure for a future equity regime only.",
            "initial_eur200_tradable": False,
        }
        _validate_broker_native_selection(Path("."), proposal)

    def test_state_transition_preserves_outer_economics_and_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); state = self._outer_fixture(root, completed=True)
            files = [root / state[key] for key in ("capture_acceptance_ref", "result_ref", "interpretation_ref")]
            before = [x.read_bytes() for x in files]
            accounting = Path("CURRENT_STATE.json").read_bytes()
            ledger = Path("discovery/ledger.jsonl").read_bytes()
            proposal = self._new_broker_native_scope()
            _validate_authoritative_data_contract(root, proposal)
            _reject_completed_outer_as_unseen(root, proposal)
            self.assertEqual(before, [x.read_bytes() for x in files])
            self.assertEqual(accounting, Path("CURRENT_STATE.json").read_bytes())
            self.assertEqual(ledger, Path("discovery/ledger.jsonl").read_bytes())
            current = json.loads(accounting)
            persisted = json.loads(Path("CURRENT_STATE.json").read_text())
            self.assertEqual(
                (current["v2_attempts_used"], current["economic_outcomes_opened"]),
                (persisted["v2_attempts_used"], persisted["economic_outcomes_opened"]),
            )

    def test_liveness_from_completed_outer_reaches_general_ai_reasoning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); state = self._outer_fixture(root, completed=True)
            self.assertTrue(reasoning_required(state))
            with patch("research_v3.general_ai_autonomy_loop.validate_repository_state", return_value={}), \
                 patch("research_v3.general_ai_autonomy_loop.reason", return_value={"status": "PROPOSAL_GENERATED"}) as reason, \
                 patch("research_v3.general_ai_autonomy_loop.drain", return_value={"status": "PASS"}):
                out = autonomous_loop(root, max_cycles=1)
            self.assertEqual(out["trace"][0]["kind"], "GENERAL_AI_REASONING")
            reason.assert_called_once()

    def _real_historical_ref(self):
        return "research_v3/ai_director/proposals/C031_STAGE_B_EXECUTION_AUTHORIZATION_V1.json"

    def test_already_materialized_proposal_survives_later_accounting_change(self):
        ref=self._real_historical_ref()
        with patch("research_v3.general_ai_director_bridge.validate_proposal", side_effect=AssertionError("must not revalidate current accounting")):
            out=materialize_proposal(".",ref)
        self.assertEqual(out["status"],"ALREADY_MATERIALIZED")
        self.assertEqual(out["economic_outcome_opened"],False)
        self.assertEqual(out["v2_attempt_consumed"],0)

    def test_already_materialized_proposal_does_not_create_duplicate_runtime_ledger_entry(self):
        before=Path("research_v3/runtime_v2/runtime_ledger.jsonl").read_bytes()
        out=materialize_proposal(".",self._real_historical_ref())
        after=Path("research_v3/runtime_v2/runtime_ledger.jsonl").read_bytes()
        self.assertEqual(out["status"],"ALREADY_MATERIALIZED")
        self.assertEqual(before,after)

    def test_already_materialized_proposal_does_not_open_duplicate_economics(self):
        journal=Path("research_v3/runtime_v2/operation_journal.jsonl").read_text().splitlines()
        ref=self._real_historical_ref()
        proposal=json.loads(Path(ref).read_text())
        p_hash=proposal_hash(proposal)
        registry=json.loads(Path("research_v3/ai_director/PROPOSAL_REGISTRY_V1.json").read_text())
        row=next(x for x in registry["accepted"] if x["proposal_hash"]==p_hash)
        before=[json.loads(x) for x in journal if x.strip() and json.loads(x).get("operation_id")==row["operation_id"]]
        materialize_proposal(".",ref)
        after=[json.loads(x) for x in Path("research_v3/runtime_v2/operation_journal.jsonl").read_text().splitlines() if x.strip() and json.loads(x).get("operation_id")==row["operation_id"]]
        self.assertEqual(before,after)
        self.assertFalse(any(x.get("event")=="ECONOMIC_EXECUTION_STARTED" for x in after))

    def test_already_materialized_proposal_does_not_consume_attempt(self):
        before=json.loads(Path("CURRENT_STATE.json").read_text())["v2_attempts_used"]
        materialize_proposal(".",self._real_historical_ref())
        after=json.loads(Path("CURRENT_STATE.json").read_text())["v2_attempts_used"]
        self.assertEqual(after,before)

    def test_unaccepted_stale_basis_proposal_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            # We only need to prove the new/unaccepted path still invokes strict validation.
            root=Path(td); (root/"p.json").write_text(json.dumps(base_proposal()))
            with patch("research_v3.general_ai_director_bridge._registry",return_value={"accepted":[]}), \
                 patch("research_v3.general_ai_director_bridge.validate_proposal",side_effect=AIProposalRejected("proposal accounting basis drift")):
                with self.assertRaisesRegex(AIProposalRejected,"accounting basis drift"):
                    materialize_proposal(root,"p.json")

    def test_modified_previously_accepted_proposal_is_not_silently_treated_as_accepted(self):
        ref=self._real_historical_ref()
        accepted=json.loads(Path(ref).read_text())
        modified=copy.deepcopy(accepted); modified["objective"]["goal"] += " MODIFIED"
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"p.json").write_text(json.dumps(modified))
            historical_hash=proposal_hash(accepted)
            fake={"proposal_hash":historical_hash,"proposal_ref":"p.json"}
            with patch("research_v3.general_ai_director_bridge._registry",return_value={"accepted":[fake]}), \
                 patch("research_v3.general_ai_director_bridge.validate_proposal",side_effect=AIProposalRejected("strict validation reached")):
                with self.assertRaisesRegex(AIProposalRejected,"strict validation reached"):
                    materialize_proposal(root,"p.json")

    def test_drain_is_order_independent_across_historical_and_new_proposals(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=root/"research_v3/ai_director/proposals"; d.mkdir(parents=True)
            for name in ("Z.json","A.json"):
                (d/name).write_text(json.dumps(base_proposal(name)))
            with patch("research_v3.general_ai_director_bridge.materialize_proposal",side_effect=lambda root,rel,**k:{"status":"ALREADY_MATERIALIZED","proposal_ref":rel}):
                out=drain(root)
        self.assertEqual(out["count"],2)
        self.assertEqual({x["proposal_ref"] for x in out["processed"]},{"research_v3/ai_director/proposals/A.json","research_v3/ai_director/proposals/Z.json"})

    def test_scheduled_liveness_wake_from_current_state_reaches_completion(self):
        before=json.loads(Path("CURRENT_STATE.json").read_text())
        out=materialize_proposal(".",self._real_historical_ref())
        self.assertEqual(out["status"],"ALREADY_MATERIALIZED")
        state=json.loads(Path("CURRENT_STATE.json").read_text())
        for key in ("economic_outcomes_opened","v2_attempts_used","v2_search_budget_remaining"):
            self.assertEqual(state[key],before[key])


if __name__ == "__main__":
    unittest.main()
