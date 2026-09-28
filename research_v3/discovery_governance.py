"""Machine-enforced discovery-scope and parameter-governance invariants."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

AUDIT_REF=Path("evidence/RETROSPECTIVE_EVIDENCE_SCOPE_AUDIT_V1.json")
PARAM_REF=Path("research_v3/PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1.json")
MULTI_REF=Path("research_v3/MULTI_FRONTIER_DISCOVERY_GOVERNOR_V1.json")
LEDGER_REF=Path("research_v3/DISCOVERY_COVERAGE_LEDGER_V1.json")
LEGACY_ACCEPTED_EXEMPT=frozenset({"post_index_extended_hours_cross_sectional_alignment_v1"})
LEGACY_LOCAL_NULL_FIELD="families_exhausted_non_economically"

def active_open_families(state:Mapping[str,Any], families:Sequence[str])->list[str]:
    """Historical local-null labels have no family or scheduler authority."""
    closure=state.get("family_level_closure") or {}
    if closure.get("status")=="FAMILY_LEVEL_CLOSED_WITH_EVIDENCE":
        raise DiscoveryGovernanceError("explicit family closure requires modern closure audit")
    return list(families)

class DiscoveryGovernanceError(ValueError):
    pass

def _load(root:Path,rel:Path)->dict[str,Any]:
    obj=json.loads((root/rel).read_text(encoding="utf-8"))
    if not isinstance(obj,dict):
        raise DiscoveryGovernanceError(f"governance authority must be object: {rel}")
    return obj

def evidence_class_can_close_family(evidence_class:str|None, *, explicit_closure_audit:bool=False, adequate_power:bool=False, parameter_region_coverage:bool=False, meaningful_universe_breadth:bool=False, asset_class_coverage:bool=False, horizon_coverage:bool=False, plausible_unexplored_frontier:bool=True)->bool:
    return bool(evidence_class=="FAMILY_LEVEL_NULL" and explicit_closure_audit and adequate_power and parameter_region_coverage and meaningful_universe_breadth and asset_class_coverage and horizon_coverage and not plausible_unexplored_frontier)

def validate_parameter_discovery_plan(plan:Mapping[str,Any])->None:
    if plan.get("protected_forward_used") is True or plan.get("protected_evidence_used_for_selection") is True:
        raise DiscoveryGovernanceError("protected evidence cannot be used for parameter discovery")
    if plan.get("ranges_frozen_before_development_surface") is not True:
        raise DiscoveryGovernanceError("parameter ranges must be frozen before reading the development response surface")
    if plan.get("record_all_probes") is not True:
        raise DiscoveryGovernanceError("parameter discovery must record all probes, not only the winner")
    if plan.get("blind_large_cartesian_grid") is True or plan.get("threshold_spam") is True:
        raise DiscoveryGovernanceError("blind parameter mining is forbidden")
    if int(plan.get("parameter_search_breadth") or 0)==1 and plan.get("family_exhaustion_claim") is True:
        raise DiscoveryGovernanceError("one parameter point cannot create family exhaustion authority")

def classify_parameter_surface(points:Sequence[Mapping[str,Any]])->str:
    good=[p for p in points if p.get("development_only") is True and float(p.get("effect",0.0))>0 and p.get("neighbor_consistent") is True]
    if len(points)==1 and good:
        return "ISOLATED_POINT_NOT_REGION"
    if len(good)>=3:
        return "ROBUST_PARAMETER_REGION_CANDIDATE"
    return "NO_ROBUST_REGION_ESTABLISHED"

def validate_confirmation_freeze(before:Mapping[str,Any],after:Mapping[str,Any],*,outcome_observed:bool)->None:
    if outcome_observed and dict(before)!=dict(after):
        raise DiscoveryGovernanceError("confirmatory parameters cannot change after outcome")

def validate_proposal_discovery_governance(root_value:str|Path,proposal:Mapping[str,Any])->None:
    root=Path(root_value).resolve()
    audit=_load(root,AUDIT_REF)
    param=_load(root,PARAM_REF)
    multi=_load(root,MULTI_REF)
    ledger=_load(root,LEDGER_REF)
    if audit.get("family_exhaustion",{}).get("mechanism_family_closed_count")!=0:
        raise DiscoveryGovernanceError("unexpected family closure requires successor explicit closure-audit validator")
    closure=(proposal.get("scope_law") or {}).get("mechanism_family_closure_claims")
    if closure is None:
        closure=proposal.get("mechanism_family_closure_claims") or []
    if closure:
        raise DiscoveryGovernanceError("no mechanism family currently has family-level closure authority")
    decision=proposal.get("decision") or {}
    if decision.get("family_exhaustion") is True or decision.get("close_mechanism_family") is True:
        raise DiscoveryGovernanceError("proposal cannot burn a mechanism family without explicit family-level closure audit")
    if decision.get("close_asset_class") is True and not decision.get("prospective_cross_asset_estimand_authority"):
        raise DiscoveryGovernanceError("one asset class cannot close another without prospective cross-asset estimand authority")
    pid=str(proposal.get("proposal_id") or "")
    if pid not in LEGACY_ACCEPTED_EXEMPT and (decision.get("selected_mechanism_family") or decision.get("mechanism_family")):
        dg=decision.get("discovery_governance")
        if not isinstance(dg,Mapping):
            raise DiscoveryGovernanceError("new semantic frontier decisions require discovery_governance")
        if dg.get("parameter_governor_ref")!=str(PARAM_REF) or dg.get("coverage_ledger_ref")!=str(LEDGER_REF):
            raise DiscoveryGovernanceError("new frontier decision must bind active parameter and coverage governors")
        if dg.get("structural_41_default_inferential_authority") is not False:
            raise DiscoveryGovernanceError("41 structural representatives cannot regain default inferential authority")
        if dg.get("local_parked_scope_is_family_exhaustion") is not False:
            raise DiscoveryGovernanceError("local parked scope must remain local")
        if not dg.get("alternatives_considered"):
            raise DiscoveryGovernanceError("multi-frontier selection must record alternatives considered")
        plan=decision.get("parameter_discovery")
        if plan is not None:
            if not isinstance(plan,Mapping):
                raise DiscoveryGovernanceError("parameter_discovery must be an object")
            validate_parameter_discovery_plan(plan)
    if param.get("prospective_search_space_requirements",{}).get("all_evaluated_points_or_regions_recorded") is not True:
        raise DiscoveryGovernanceError("active parameter governor must require all probes")
    if multi.get("anti_starvation",{}).get("fixed_quota") is not False:
        raise DiscoveryGovernanceError("anti-starvation must not use an arbitrary fixed quota")
    if ledger.get("source_frontier",{}).get("structural_representatives_default_inferential_authority") is not False:
        raise DiscoveryGovernanceError("coverage ledger restored 41-panel default authority")
