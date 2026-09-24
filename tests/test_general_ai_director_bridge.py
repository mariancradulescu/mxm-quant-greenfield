import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_director_bridge import (
    AIProposalRejected,
    PROPOSAL_SCHEMA,
    _validate_authoritative_data_contract,
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

    def test_authoritative_outer_contract_rejects_panel_substitution(self):
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
        with self.assertRaisesRegex(AIProposalRejected,"violates frozen outer panel"):
            _validate_authoritative_data_contract(Path("."), proposal)

    def test_authoritative_outer_contract_accepts_exact_frozen_scope(self):
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
        _validate_authoritative_data_contract(Path("."), proposal)

    def test_authoritative_outer_contract_rejects_interval_drift(self):
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
        with self.assertRaisesRegex(AIProposalRejected,"frozen outer interval"):
            _validate_authoritative_data_contract(Path("."), proposal)

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
            "symbols": ["FUTURE_SYMBOL"],
            "resolution": "M5",
            "start_utc": "2026-01-01T00:00:00Z",
            "end_utc": "2026-01-08T00:00:00Z",
            "fields": ["time", "open", "high", "low", "close"],
            "information_gain_justification": "Prospectively sufficient pilot.",
        }
        validate_proposal_shape(proposal)

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
        self.assertEqual((before,after),(19,19))

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

    def test_scheduled_liveness_wake_from_current_27_outcome_state_reaches_completion(self):
        out=materialize_proposal(".",self._real_historical_ref())
        self.assertEqual(out["status"],"ALREADY_MATERIALIZED")
        state=json.loads(Path("CURRENT_STATE.json").read_text())
        self.assertEqual(state["economic_outcomes_opened"],27)
        self.assertEqual(state["v2_attempts_used"],19)
        self.assertEqual(state["v2_search_budget_remaining"],65)


if __name__ == "__main__":
    unittest.main()
