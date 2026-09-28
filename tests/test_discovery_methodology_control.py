import json
import tempfile
import unittest
from pathlib import Path

from research_v3.discovery_methodology import (
    ARCH_REL,
    AUDIT_REL,
    EPOCH37_PROPOSAL_HASH,
    EPOCH37_PROPOSAL_ID,
    GATE_REL,
    DiscoveryMethodologyError,
    apply_pre_outcome_methodology_gate,
    validate_proposal_universe_methodology,
)


class DiscoveryMethodologyControlTests(unittest.TestCase):
    def _root(self, td):
        root = Path(td)
        (root / "research_v3/runtime_v2_acceptance").mkdir(parents=True)
        (root / "evidence").mkdir(parents=True)
        (root / "research_v3").mkdir(exist_ok=True)
        (root / "research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json").write_text(json.dumps({
            "schema": "mxm.greenfield.research-evidence-epoch.v1",
            "status": "CURRENT",
            "current_epoch": 36,
            "authoritative_evidence_refs": [],
            "provisional_research_artifacts": [],
            "history": [],
        }))
        (root / GATE_REL).write_text(json.dumps({
            "schema": "mxm.greenfield.epoch37-pre-outcome-methodology-validity-gate.v1",
            "status": "METHODOLOGY_INVALID_PRE_OUTCOME",
            "proposal": {"proposal_id": EPOCH37_PROPOSAL_ID, "proposal_hash": EPOCH37_PROPOSAL_HASH},
            "outcome_boundary": {"epoch37_structural_outcome_opened": False},
            "decision": {"economic_outcomes_delta": 0, "v2_attempts_delta": 0},
        }))
        (root / AUDIT_REL).write_text(json.dumps({
            "schema": "mxm.greenfield.research-discovery-methodology-audit.v1",
            "status": "MATERIAL_GAP_CONFIRMED",
        }))
        (root / ARCH_REL).write_text(json.dumps({
            "schema": "mxm.greenfield.adaptive-mechanism-discovery-architecture.v1",
            "status": "ACTIVE_PROSPECTIVE_DISCOVERY_POLICY",
        }))
        return root

    def test_epoch37_is_retired_pre_outcome_without_implementation_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            state = {
                "schema": "mxm.greenfield.runtime-v2-next-autonomous-state.v3",
                "status": "IMPLEMENTATION_REQUIRED",
                "next_action": "IMPLEMENT_CROSS_SECTIONAL_BREADTH_CONDITIONED_TREND_STRUCTURAL_SCREEN",
                "source_ai_proposal_id": EPOCH37_PROPOSAL_ID,
                "source_ai_proposal_hash": EPOCH37_PROPOSAL_HASH,
                "implementation_ai_required": True,
                "ai_reasoning_required": False,
                "research_judgment_required": False,
                "current_research_evidence_epoch": 36,
                "evidence_epoch": 36,
                "authorizing_evidence_epoch": 36,
                "accounting": {"economic_outcomes_opened": 28, "v2_attempts_used": 20, "v2_search_budget_remaining": 64},
                "safety": {"live_orders_authorized": False, "protected_evidence_opened": False},
            }
            (root / "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(json.dumps(state))
            out = apply_pre_outcome_methodology_gate(root, state)
            self.assertIsNotNone(out)
            self.assertEqual(out["status"], "FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_METHODOLOGY_RETIREMENT")
            self.assertTrue(out["ai_reasoning_required"])
            self.assertFalse(out["implementation_ai_required"])
            self.assertEqual(out["current_research_evidence_epoch"], 37)
            self.assertEqual(out["accounting"]["economic_outcomes_opened"], 28)
            self.assertEqual(out["accounting"]["v2_attempts_used"], 20)
            self.assertNotIn("source_ai_proposal_id", out)
            self.assertFalse(out["methodology_retired_proposal"]["structural_outcome_opened"])

    def test_nonmatching_state_does_not_advance(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            state = {"source_ai_proposal_id": "other", "source_ai_proposal_hash": "x", "implementation_ai_required": True}
            self.assertIsNone(apply_pre_outcome_methodology_gate(root, state))

    def test_rejects_41_topology_panel_as_cross_sectional_discovery_universe(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            proposal = {
                "decision": {
                    "mechanism_family": "CROSS_SECTIONAL_RANKING",
                    "scope": {"symbols": "All 41 current structural representatives"},
                    "universe_methodology": {
                        "role": "MECHANISM_SPECIFIC_DISCOVERY",
                        "structural_representatives_are_economic_equivalents": False,
                        "outcome_blind_selection": True,
                        "source_universe_ref": "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json",
                        "selection_features": ["schedule_overlap"],
                        "aligned_history_required": True,
                        "peer_coherence_basis": "same market",
                    },
                },
                "next_research_state": {},
            }
            with self.assertRaisesRegex(DiscoveryMethodologyError, "41 structural-coverage panel"):
                validate_proposal_universe_methodology(root, proposal)

    def test_accepts_outcome_blind_cross_sectional_mechanism_specific_universe(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            proposal = {
                "decision": {
                    "mechanism_family": "CROSS_SECTIONAL_RANKING",
                    "scope": {"symbols": "prospectively selected coherent peer cohorts"},
                    "universe_methodology": {
                        "role": "MECHANISM_SPECIFIC_DISCOVERY",
                        "structural_representatives_are_economic_equivalents": False,
                        "outcome_blind_selection": True,
                        "source_universe_ref": "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json",
                        "selection_features": ["asset_class", "schedule_overlap", "data_completeness", "capital_efficiency"],
                        "aligned_history_required": True,
                        "peer_coherence_basis": "shared asset/market cohort with overlapping executable session",
                    },
                },
                "next_research_state": {},
            }
            validate_proposal_universe_methodology(root, proposal)


if __name__ == "__main__":
    unittest.main()
