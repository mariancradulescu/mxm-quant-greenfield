import unittest

from research_v3.general_ai_director_bridge import (
    AIProposalRejected,
    PROPOSAL_SCHEMA,
    compile_runtime_plan,
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


if __name__ == "__main__":
    unittest.main()
