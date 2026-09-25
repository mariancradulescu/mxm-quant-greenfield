"""Prospective economic experiment envelope and breadth gate.

One frozen envelope consumes one identity when its FIRST economic outcome opens.
Rows for its predeclared symbols do not become separate search attempts.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Mapping

AUDIT=Path("research_v3/EPOCH21_OUTCOME_BLIND_CAPACITY_AUDIT_V1.json")
REQUIRED_FREEZE=("mechanism_semantics","eligible_universe_or_panel","inclusion_exclusion_law",
 "parameter_law","event_law","entry_law","exit_law","right_censoring_law",
 "cost_law","margin_capital_law","concurrency_law","aggregation_law",
 "primary_success_fail_criterion","subgroup_reporting_law","independent_validation_plan")
REQUIRED_GATES=("CAUSALITY_PASS","DATA_SUFFICIENCY_PASS","COST_AUTHORITY_PASS",
 "EUR200_ACCOUNT_FEASIBILITY_PASS","BREADTH_SUFFICIENCY_PASS",
 "PROSPECTIVE_FREEZE_COMPLETE","EXACT_HEAD_CI_GREEN")
BREADTH_UNITS={
 "TREND_MOMENTUM":"INSTRUMENTS_ACROSS_STRUCTURAL_HETEROGENEITY",
 "MEAN_REVERSION":"INSTRUMENTS_ACROSS_STRUCTURAL_HETEROGENEITY",
 "BREAKOUT_VOLATILITY_EXPANSION":"INSTRUMENTS_AND_EVENT_REGIMES",
 "CARRY_TERM_STRUCTURE":"TERM_STRUCTURES_AND_METADATA_REGIMES",
 "SEASONALITY_SESSION_TIME":"INSTRUMENTS_SESSIONS_SCHEDULES_AND_REGIMES",
 "RELATIVE_VALUE_COINTEGRATION":"PAIRS_RELATIONSHIP_GRAPHS_OR_CLUSTERS",
 "CROSS_SECTIONAL_RANKING":"BASKETS_AND_CROSS_SECTIONAL_REGIMES",
 "CROSS_MARKET_LEAD_LAG":"PAIRS_RELATIONSHIP_GRAPHS_OR_CLUSTERS",
 "REGIME_CONTEXT_CONDITIONED":"INSTRUMENTS_AND_INDEPENDENT_REGIMES",
 "CAUSAL_ML_PREDICTIVE_OR_STATE_MODEL":"SYMBOLS_REGIMES_SAMPLES_FEATURES_AND_TEMPORAL_INDEPENDENCE",
}
BREADTH_DIMENSIONS=("asset_class","product_type","broker_native_structural_signature",
 "trading_schedule","long_short_feasibility","minimum_volume_lattice","margin_signature",
 "transaction_cost_regime","volatility_opportunity_regime","event_availability",
 "independent_event_count","redundancy_correlation","data_availability",
 "expected_information_gain")

class EnvelopeIneligible(ValueError):
    pass

def capacity(root:Path)->dict:
    audit=json.loads((root/AUDIT).read_text(encoding="utf-8"))
    rows=audit["per_identity"]
    eligible=[row["candidate_id"] for row in rows if row["replacement_eligible"]]
    if len(rows)!=20 or len(set(eligible))!=len(eligible):
        raise EnvelopeIneligible("replacement audit incomplete or duplicate")
    if audit["lifetime_economic_exposure"]!={"distinct_consumed_v2_identities":20,
             "economic_outcomes_opened":28,"immutable":True,"refunds":0}:
        raise EnvelopeIneligible("historical exposure cannot be refunded")
    if audit["methodology_replacement_capacity"]["total"]!=len(eligible):
        raise EnvelopeIneligible("replacement authority mismatch")
    return audit

def validate(root:Path,envelope:Mapping,*,previously_opened_identities:set[str]|None=None)->dict:
    authority=capacity(root)
    if envelope.get("evidence_epoch",0)<21:
        raise EnvelopeIneligible("new envelope must bind current evidence epoch")
    identity=envelope.get("new_candidate_id")
    if not isinstance(identity,str) or not identity.startswith("V2-C"):
        raise EnvelopeIneligible("fresh economic identity required")
    if identity in (previously_opened_identities or set()) or identity in {r["candidate_id"] for r in authority["per_identity"]}:
        raise EnvelopeIneligible("consumed candidate identity cannot be reused")
    replacement=envelope.get("replacement_for")
    if replacement is not None and replacement not in authority["methodology_replacement_capacity"]["eligible_legacy_identity_ids"]:
        raise EnvelopeIneligible("replacement_for is not in frozen outcome-blind authority")
    freeze=envelope.get("prospective_freeze") or {}
    missing=[key for key in REQUIRED_FREEZE if not freeze.get(key)]
    if missing:
        raise EnvelopeIneligible("incomplete prospective economic freeze: "+",".join(missing))
    gates=envelope.get("prerequisites") or {}
    failed=[key for key in REQUIRED_GATES if gates.get(key) is not True]
    if failed:
        raise EnvelopeIneligible("economic prerequisite not proven: "+",".join(failed))
    breadth=envelope.get("breadth_proof") or {}
    family=str(envelope.get("mechanism_family") or "")
    if family not in BREADTH_UNITS or breadth.get("unit")!=BREADTH_UNITS[family]:
        raise EnvelopeIneligible("mechanism-specific breadth unit missing")
    if not breadth.get("prospective_selection_law") or not breadth.get("information_sufficiency_stopping_law"):
        raise EnvelopeIneligible("prospective breadth selection and stopping law required")
    if not breadth.get("structural_heterogeneity") or not breadth.get("independent_event_evidence"):
        raise EnvelopeIneligible("breadth must bind structural and event coverage")
    panel=envelope.get("eligible_symbols_or_relationships") or []
    if not isinstance(panel,list) or not panel:
        raise EnvelopeIneligible("economic panel or relationship graph missing")
    if len(panel)==1 and not breadth.get("intrinsic_single_unit_justification"):
        raise EnvelopeIneligible("single-unit economic envelope requires a frontier-relative intrinsic exception")
    if envelope.get("selection_uses_opened_economic_outcomes") is not False:
        raise EnvelopeIneligible("outcome-driven symbol selection forbidden")
    return {"status":"ELIGIBLE_PRE_OUTCOME","attempt_units_at_first_economic_outcome":1,
            "per_symbol_rows_additional_attempts":0,
            "independent_stage_b_additional_search_identities":0,
            "replacement_for":replacement,"breadth_unit":BREADTH_UNITS[family]}

def account_first_open(root:Path,envelope:Mapping,*,opened:set[str])->dict:
    row=validate(root,envelope,previously_opened_identities=opened)
    if envelope["new_candidate_id"] in opened:
        raise EnvelopeIneligible("economic identity already opened")
    return {**row,"new_candidate_id":envelope["new_candidate_id"],
            "economic_attempt_delta":1,"lifetime_exposure_delta":1,
            "per_symbol_outcomes_do_not_mint_identities":True}
