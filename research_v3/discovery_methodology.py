"""Prospective research-methodology controls for adaptive mechanism discovery.

This module separates broker-topology coverage from inferential/economic discovery.
It contains no strategy outcome logic and cannot open economics or consume V2 attempts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from research_v3.evidence_epoch import advance_evidence_epoch, current_evidence_epoch
from research_v3.runtime_v2_primitives import atomic_write_json, iso

GATE_REL = Path("evidence/EPOCH37_PRE_OUTCOME_METHODOLOGY_VALIDITY_GATE_V1.json")
AUDIT_REL = Path("evidence/RESEARCH_DISCOVERY_METHODOLOGY_AUDIT_V1.json")
ARCH_REL = Path("research_v3/ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE_V1.json")
NEXT_REL = Path("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")

EPOCH37_PROPOSAL_ID = "epoch37_breadth_conditioned_trend"
EPOCH37_PROPOSAL_HASH = "fc6de8225a27f1a9bedbb4bff5e06ce5fb030299f47f3f1e5b95d3e1138b8a91"

CROSS_SYMBOL_FAMILIES = frozenset({
    "CROSS_SECTIONAL_RANKING",
    "RELATIVE_VALUE_COINTEGRATION",
    "CROSS_MARKET_LEAD_LAG",
})


class DiscoveryMethodologyError(ValueError):
    pass


def _load(root: Path, rel: Path) -> dict[str, Any]:
    path = root / rel
    if not path.is_file():
        raise DiscoveryMethodologyError(f"required methodology authority missing: {rel}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DiscoveryMethodologyError(f"methodology authority must be a JSON object: {rel}")
    return value


def architecture_active(root_value: str | Path = ".") -> bool:
    root = Path(root_value).resolve()
    path = root / ARCH_REL
    if not path.is_file():
        return False
    doc = json.loads(path.read_text(encoding="utf-8"))
    return (
        doc.get("schema") == "mxm.greenfield.adaptive-mechanism-discovery-architecture.v1"
        and doc.get("status") == "ACTIVE_PROSPECTIVE_DISCOVERY_POLICY"
    )


def apply_pre_outcome_methodology_gate(
    root_value: str | Path,
    state: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Retire the exact frozen Epoch37 scope before any outcome/provider retry.

    The accepted semantic hypothesis remains historical authority.  Only its invalid
    topology-panel inferential scope is retired.  The transition advances material
    evidence exactly once and returns a fresh semantic frontier under the adaptive
    discovery architecture.
    """
    root = Path(root_value).resolve()
    if state.get("source_ai_proposal_id") != EPOCH37_PROPOSAL_ID:
        return None
    if state.get("source_ai_proposal_hash") != EPOCH37_PROPOSAL_HASH:
        return None
    if state.get("implementation_ai_required") is not True:
        return None

    gate = _load(root, GATE_REL)
    audit = _load(root, AUDIT_REL)
    architecture = _load(root, ARCH_REL)
    if (
        gate.get("schema") != "mxm.greenfield.epoch37-pre-outcome-methodology-validity-gate.v1"
        or gate.get("status") != "METHODOLOGY_INVALID_PRE_OUTCOME"
        or gate.get("proposal", {}).get("proposal_id") != EPOCH37_PROPOSAL_ID
        or gate.get("proposal", {}).get("proposal_hash") != EPOCH37_PROPOSAL_HASH
        or gate.get("outcome_boundary", {}).get("epoch37_structural_outcome_opened") is not False
        or gate.get("decision", {}).get("economic_outcomes_delta") != 0
        or gate.get("decision", {}).get("v2_attempts_delta") != 0
    ):
        raise DiscoveryMethodologyError("Epoch37 methodology gate is not a valid pre-outcome retirement authority")
    if (
        audit.get("schema") != "mxm.greenfield.research-discovery-methodology-audit.v1"
        or audit.get("status") != "MATERIAL_GAP_CONFIRMED"
        or architecture.get("schema") != "mxm.greenfield.adaptive-mechanism-discovery-architecture.v1"
        or architecture.get("status") != "ACTIVE_PROSPECTIVE_DISCOVERY_POLICY"
    ):
        raise DiscoveryMethodologyError("adaptive discovery methodology authority is not active")

    before_epoch = current_evidence_epoch(root)
    epoch_doc = advance_evidence_epoch(
        root,
        event_class="MATERIAL_EVIDENCE_SUPERSESSION",
        refs=[str(GATE_REL), str(AUDIT_REL), str(ARCH_REL)],
        reason=(
            "Epoch37 frozen 41-representative cross-sectional breadth scope retired pre-outcome; "
            "structural broker coverage is superseded as the default inferential discovery universe "
            "by active mechanism-specific adaptive discovery methodology."
        ),
        advanced_utc=iso(),
    )
    new_epoch = int(epoch_doc["current_epoch"])
    if new_epoch <= before_epoch:
        raise DiscoveryMethodologyError("methodology supersession did not advance material evidence")

    nxt = dict(state)
    retired = {
        "proposal_id": EPOCH37_PROPOSAL_ID,
        "proposal_hash": EPOCH37_PROPOSAL_HASH,
        "proposal_ref": "research_v3/ai_director/proposals/AUTO_reason_903ddbd7947594b44fb221d07f58f067.json",
        "retirement_class": "METHODOLOGY_INVALID_PRE_OUTCOME",
        "structural_outcome_opened": False,
        "economic_outcome_opened": False,
        "v2_attempt_consumed": False,
        "semantic_hypothesis_preserved": True,
        "semantic_reasoning_repeated": False,
    }
    for key in (
        "source_ai_proposal_id",
        "source_ai_proposal_hash",
        "source_runtime_operation_id",
        "implementation_scope",
        "implementation_ai_scope",
        "implementation_task_scope",
        "next_deterministic_operation_ref",
        "deterministic_next_operation",
        "eligibility_retry",
    ):
        nxt.pop(key, None)
    nxt.update({
        "status": "FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_METHODOLOGY_RETIREMENT",
        "next_action": "AI_SELECT_HIGHEST_INFORMATION_LEGAL_NEXT_ACTION_UNDER_ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE",
        "ai_reasoning_required": True,
        "research_judgment_required": True,
        "implementation_ai_required": False,
        "implementation_satisfied": False,
        "implementation_scope_complete": False,
        "user_action_required": False,
        "external_data_required": False,
        "external_gate": None,
        "external_data_gate": None,
        "current_research_evidence_epoch": new_epoch,
        "evidence_epoch": new_epoch,
        "authorizing_evidence_epoch": before_epoch,
        "methodology_gate_ref": str(GATE_REL),
        "methodology_audit_ref": str(AUDIT_REL),
        "discovery_architecture_ref": str(ARCH_REL),
        "methodology_retired_proposal": retired,
        "semantic_question": (
            "Select the highest-information legal next research action under the active adaptive "
            "mechanism-discovery architecture. Keep the 41 structural representatives for topology "
            "coverage only unless a hypothesis explicitly targets structural signatures as units. "
            "Derive mechanism-specific discovery scope prospectively from the full feasible broker "
            "frontier using outcome-blind features; preserve false-positive control and quantify power."
        ),
        "decision_contract": {
            "methodology_policy_ref": str(ARCH_REL),
            "methodology_audit_ref": str(AUDIT_REL),
            "structural_panel_default_inferential_role_forbidden": True,
            "mechanism_specific_candidate_universe_required": True,
            "statistical_power_audit_required": True,
            "promotion_path_required_for_material_structural_evidence": True,
            "economic_authorization": False,
        },
    })
    atomic_write_json(root / NEXT_REL, nxt)
    return nxt


def validate_proposal_universe_methodology(
    root_value: str | Path,
    proposal: Mapping[str, Any],
) -> None:
    """Fail closed on new semantic proposals that recreate the structural-panel conflation."""
    root = Path(root_value).resolve()
    if not architecture_active(root):
        return

    decision = proposal.get("decision") or {}
    next_state = proposal.get("next_research_state") or {}
    status = str(decision.get("status") or next_state.get("status") or "").upper()
    if "ADDITIONAL_AUTHORITY_REQUIRED" in status:
        return

    family = (
        decision.get("mechanism_family")
        or decision.get("selected_mechanism_family")
        or next_state.get("selected_family")
    )
    if not family:
        return

    methodology = decision.get("universe_methodology")
    if not isinstance(methodology, Mapping):
        raise DiscoveryMethodologyError(
            "active adaptive discovery policy requires decision.universe_methodology"
        )
    if methodology.get("structural_representatives_are_economic_equivalents") is not False:
        raise DiscoveryMethodologyError(
            "structural representatives must explicitly remain non-equivalent economically"
        )

    role = str(methodology.get("role") or "")
    if role not in {"STRUCTURAL_COVERAGE_ONLY", "MECHANISM_SPECIFIC_DISCOVERY"}:
        raise DiscoveryMethodologyError(
            "universe_methodology.role must be STRUCTURAL_COVERAGE_ONLY or MECHANISM_SPECIFIC_DISCOVERY"
        )

    scope_text = json.dumps(decision.get("scope") or {}, sort_keys=True).lower()
    topology_panel_claim = (
        "all 41 current structural representatives" in scope_text
        or "all_41_current_structural_representatives" in scope_text
        or methodology.get("candidate_count") == 41
        and methodology.get("selection_law") == "ONE_PER_BROKER_NATIVE_STRUCTURAL_SIGNATURE"
    )
    if topology_panel_claim and role != "STRUCTURAL_COVERAGE_ONLY":
        raise DiscoveryMethodologyError(
            "the 41 structural-coverage panel may not be the default inferential discovery universe"
        )

    if role == "STRUCTURAL_COVERAGE_ONLY":
        if methodology.get("inferential_discovery") is not False:
            raise DiscoveryMethodologyError(
                "STRUCTURAL_COVERAGE_ONLY must explicitly disable inferential discovery"
            )
        return

    if methodology.get("outcome_blind_selection") is not True:
        raise DiscoveryMethodologyError("mechanism-specific candidate selection must be outcome-blind")
    if not methodology.get("source_universe_ref"):
        raise DiscoveryMethodologyError("mechanism-specific discovery requires a source universe authority")
    features = methodology.get("selection_features")
    if not isinstance(features, list) or not features:
        raise DiscoveryMethodologyError("mechanism-specific discovery requires outcome-blind selection features")

    if family in CROSS_SYMBOL_FAMILIES:
        if methodology.get("aligned_history_required") is not True:
            raise DiscoveryMethodologyError(f"{family} requires aligned-history methodology")
        if not str(methodology.get("peer_coherence_basis") or "").strip():
            raise DiscoveryMethodologyError(f"{family} requires an explicit peer-coherence basis")
