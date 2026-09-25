"""Decision-relative evidence eligibility; immutable evidence stays readable historically."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Mapping
from research_v3.runtime_v2_primitives import sha256_file

ROLES = (
    "PROSPECTIVE_DEVELOPMENT_REUSABLE", "NON_ECONOMIC_STRUCTURAL_REUSABLE",
    "COST_AUTHORITY_ONLY", "HISTORICAL_CONTEXT_ONLY", "OUTCOME_EXPOSED",
    "CONSUMED_INDEPENDENT_OUTER", "PROTECTED_FORWARD",
    "FORBIDDEN_AS_NEW_PROSPECTIVE_INPUT",
)
C032_CAPTURE = "evidence/BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_CAPTURE_ACCEPTANCE_V1.json"
C032_RESULT = "discovery/results/V2-C032_STAGE_A_V1.json"
C032_EXECUTION = "research_v3/C032_EXECUTION_RESULT_V1.json"
CONSUMED = frozenset((C032_CAPTURE, C032_RESULT, C032_EXECUTION))
FORBIDDEN = frozenset(("OUTCOME_EXPOSED", "CONSUMED_INDEPENDENT_OUTER", "PROTECTED_FORWARD", "FORBIDDEN_AS_NEW_PROSPECTIVE_INPUT"))
AUTHORITY_REL = Path("research_v3/ai_director/EVIDENCE_ELIGIBILITY_V1.json")

class EvidenceIneligible(ValueError):
    pass

def role_for(ref: str, *, decision_class: str = "") -> str:
    ref = str(ref)
    if "PROTECTED_FORWARD" in ref.upper():
        return "PROTECTED_FORWARD"
    if ref in (C032_RESULT, C032_EXECUTION):
        return "CONSUMED_INDEPENDENT_OUTER"
    if ref == C032_CAPTURE:
        return "OUTCOME_EXPOSED"
    if ref.endswith("_RESULT_V1.json") and ("/results/" in ref or "OUTER" in ref):
        return "HISTORICAL_CONTEXT_ONLY"
    if "COST" in ref.upper() and ("CAPTURE" in ref.upper() or "FRICTION" in ref.upper()):
        return "COST_AUTHORITY_ONLY"
    if "SCREEN" in ref.upper() or "STRUCTURAL" in ref.upper():
        return "NON_ECONOMIC_STRUCTURAL_REUSABLE"
    return "PROSPECTIVE_DEVELOPMENT_REUSABLE"

def _prospective(proposal: Mapping) -> bool:
    decision = proposal.get("decision") or {}
    txt = json.dumps(decision, sort_keys=True).lower()
    goal = json.dumps(proposal.get("objective") or {}).lower()
    return any(x in txt + goal for x in (
        "go/no-go", "friction-adjusted", "post-event move", "pass/fail rate",
        "economic", "entry/exit", "candidate for a future", "prospectiv",
    ))

def validate_eligibility(proposal: Mapping) -> None:
    bindings = proposal.get("data_bindings") or []
    decision = proposal.get("decision") or {}
    sources = decision.get("source_evidence_used") or []
    if not isinstance(bindings, list) or not isinstance(sources, list):
        raise EvidenceIneligible("evidence references must be lists")
    prospective = _prospective(proposal)
    for binding in bindings:
        ref = binding.get("ref") if isinstance(binding, Mapping) else binding
        if not isinstance(ref, str) or not ref:
            raise EvidenceIneligible("data binding must name a concrete evidence ref")
        role = role_for(ref, decision_class=str((proposal.get("objective") or {}).get("class", "")))
        if role in FORBIDDEN or role == "HISTORICAL_CONTEXT_ONLY":
            raise EvidenceIneligible(f"{ref}: {role} is forbidden as a new prospective data binding")
    # Post-event directional magnitudes are observed outcomes for a new symbol-selection rule.
    procedure=" ".join(str(x) for x in (decision.get("candidate_construction_procedure") or [])).lower()
    if any("FOLLOWTHROUGH" in str((b.get("ref") if isinstance(b,Mapping) else b)).upper() for b in bindings) and ("retain only symbols" in procedure or "directional signal" in procedure):
        raise EvidenceIneligible("post-event directional followthrough cannot filter prospective symbols without independent selection evidence")
    nxt=proposal.get("next_research_state") or {}
    if ("minimum_breadth_threshold_symbols" in nxt or "minimum_structural_clusters" in nxt) and not decision.get("prospective_breadth_threshold_derivation_ref"):
        raise EvidenceIneligible("fixed symbol/cluster minima require a cited prospective structural derivation")
    if prospective:
        for ref in sources:
            if role_for(ref) in FORBIDDEN:
                raise EvidenceIneligible(f"{ref}: outcome-exposed or consumed evidence cannot inform a new prospective go/no-go decision")
    # Acknowledgment as historical authority remains legal; binding as input is not.

def packet(root: Path, *, evidence_epoch: int, decision_class: str, refs: list[str], accounting: Mapping, universe: Mapping, semantic_question: str, delta_refs: list[str]) -> dict:
    allowed, historical, forbidden = [], [], []
    for ref in dict.fromkeys(refs):
        path = root / ref
        if not path.is_file():
            continue
        role = role_for(ref, decision_class=decision_class)
        item = {"ref":ref, "sha256":sha256_file(path), "role":role}
        if role in FORBIDDEN:
            forbidden.append({**item, "reason_for_prohibition":"Previously opened C032 outcome or protected/consumed evidence; historical context only."})
            historical.append({"ref":ref,"role":role,"summary":"Previously observed exact outcome; no new prospective use."})
        elif role == "HISTORICAL_CONTEXT_ONLY":
            historical.append({**item,"summary":"Historical result; no prospective data binding."})
        else:
            if ref in delta_refs and ref.endswith("EPOCH20_SERIAL_DEPENDENCE_SCREEN_V1.json"):
                doc=json.loads(path.read_text(encoding="utf-8"))
                item["material_summary"]={"pooled":doc.get("pooled"),"series_count":len(doc.get("series") or {}),
                    "frozen_horizons_m5_bars":doc.get("frozen_horizons_m5_bars"),
                    "interpretation_boundary":doc.get("interpretation_boundary")}
            allowed.append(item)
    return {"schema":"mxm.greenfield.semantic-eligibility-packet.v1","evidence_epoch":evidence_epoch,
            "material_delta_since_last_accepted_reasoning":delta_refs,
            "accounting":dict(accounting),"open_universe_authority":dict(universe),
            "governing_research_contract":"research_v3/RESEARCH_CONTRACT_V3.json",
            "exact_semantic_question":semantic_question,"admissible_inputs":allowed,
            "historical_context":historical,"forbidden_inputs":forbidden}
