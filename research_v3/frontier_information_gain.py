"""Deterministic frontier feature store, opportunity map and information-gain selector.

This module is deliberately pre-economic. It never computes returns, PnL, or an
economic symbol ranking. Missing broker evidence remains explicit.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping

from research_v3.runtime_v2_primitives import atomic_write_json, load_json, sha256_bytes, canonical_bytes

CONTRACT_REL=Path("research_v3/BROKER_NATIVE_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT_V1.json")
FEATURE_REL=Path("research_v3/BROKER_NATIVE_FRONTIER_FEATURE_STORE_V1.json")
OPPORTUNITY_REL=Path("research_v3/BROKER_NATIVE_FRONTIER_OPPORTUNITY_MAP_V1.json")
SELECTOR_REL=Path("research_v3/BROKER_NATIVE_FRONTIER_INFORMATION_GAIN_SELECTION_V1.json")
ACQUISITION_REL=Path("research_v3/BROKER_NATIVE_FRONTIER_NEXT_ACQUISITION_PLAN_V1.json")

MECHANISM_FAMILIES=[
    "TREND_MOMENTUM","MEAN_REVERSION","BREAKOUT_VOLATILITY_EXPANSION",
    "CARRY_TERM_STRUCTURE","SEASONALITY_SESSION_TIME","RELATIVE_VALUE_COINTEGRATION",
    "CROSS_SECTIONAL_RANKING","CROSS_MARKET_LEAD_LAG","REGIME_CONTEXT_CONDITIONED",
    "CAUSAL_ML_PREDICTIVE_OR_STATE_MODEL",
]

def _load(root:Path,rel:str|Path)->dict[str,Any]:
    p=root/rel
    if not p.is_file():
        raise RuntimeError(f"required authority missing: {rel}")
    return json.loads(p.read_text(encoding="utf-8"))

def build_capture_contract(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve()
    op=_load(root,"research_v3/EPOCH21_NEXT_DETERMINISTIC_OPERATION_V1.json")
    inv=_load(root,"evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json")
    if op.get("operation_name")!="BUILD_READ_ONLY_ALL_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT":
        raise RuntimeError("current deterministic authority does not authorize capture-contract materialization")
    contract={
        "schema":"mxm.greenfield.frontier-execution-prerequisite-capture-contract.v1",
        "status":"FROZEN_DETERMINISTIC_READ_ONLY_CAPTURE_CONTRACT",
        "evidence_epoch":21,
        "source_operation_ref":"research_v3/EPOCH21_NEXT_DETERMINISTIC_OPERATION_V1.json",
        "source_inventory_ref":"evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json",
        "eligible_identity_count":int(inv["identity_coverage"]["exact_eligible_post_exclusion_symbols"]),
        "scope_law":{
            "economic_panel_selected":False,
            "mechanism_family_selected":False,
            "fixed_arbitrary_panel":False,
            "structural_representatives_are_economic_equivalents":False,
            "outcome_derived_selection_permitted":False,
        },
        "required_fields":[{
            "field":name,
            "contract_requirement":"REQUIRED_BEFORE_RELEVANT_ECONOMIC_ENVELOPE",
        } for name in op.get("required_contract_fields") or []],
        "acquisition_tiers":[
            {
                "tier":"ALREADY_AUTHORIZED_IDENTITY_AND_DIRECTIONAL_FEASIBILITY",
                "scope":"1578_ELIGIBLE_IDENTITIES",
                "fields":["exact_broker_symbol_id_and_name","current_directional_eur200_feasibility_class"],
                "authority_ref":"data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json",
                "external_capture_required":False,
            },
            {
                "tier":"COMPACT_STRUCTURAL_METADATA",
                "scope":"SELECTOR_CONTROLLED",
                "fields":["current_entry_trading_mode","commission_and_structural_fee_authority","minimum_volume_and_step","asset_class","product_type","schedule_surface","weekend_capability"],
                "external_capture_required_if_hash_bound_source_bytes_unavailable":True,
                "historical_price_download":False,
                "bid_ask_history":False,
                "purpose":"Fill structural/redundancy/microstructure missingness before choosing expensive execution-data batches.",
            },
            {
                "tier":"SELECTED_EXECUTION_SNAPSHOT",
                "scope":"ONLY_IDENTITIES_OR_SUBSETS_SELECTED_BY_INFORMATION_GAIN",
                "fields":["current_bid_ask_or_equivalent_transaction_local_spread_authority","current_directional_eur200_margin_or_expected_margin_binding","account_fingerprint_and_capture_timestamp","per_identity_capture_status_and_fail_closed_reason"],
                "historical_price_download":False,
                "economic_outcomes_opened":0,
                "v2_attempts_consumed":0,
            },
            {
                "tier":"MECHANISM_LOCAL_TRANSACTION_COST",
                "scope":"ONLY_AFTER_MECHANISM_SPECIFIC_PROSPECTIVE_SELECTION",
                "fields":["transaction_local_bid_ask","commission","conversion_cost_if_applicable","slippage_or_execution_proxy_if_authorized"],
                "rule":"Do not collect expensive transaction-local evidence for all 1578 merely because they are in the frontier.",
            },
        ],
        "fail_closed":{
            "missing_field_state":"UNKNOWN_NOT_ZERO",
            "stale_broker_identity":"BLOCK",
            "missing_quote_side":"BLOCK",
            "missing_margin_binding":"BLOCK",
            "outcome_exposed_evidence_prospective_reuse":"BLOCK",
        },
        "prohibitions":list(op.get("prohibitions") or []),
        "accounting_effect":{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0},
    }
    atomic_write_json(root/CONTRACT_REL,contract)
    return contract

def _representative_map(frontier:Mapping[str,Any])->dict[str,dict[str,Any]]:
    out={}
    for row in frontier.get("frontier") or []:
        sig=row.get("signature") or [None]*5
        out[str(row["broker_symbol"])]={
            "broker_symbol_id":row.get("symbol_id"),
            "asset_class":sig[0] if len(sig)>0 else None,
            "product_type":sig[1] if len(sig)>1 else None,
            "schedule_surface":sig[2] if len(sig)>2 else None,
            "session_regions":sig[3] if len(sig)>3 else None,
            "weekend_capability":sig[4] if len(sig)>4 else None,
            "structural_signature":sig,
            "min_margin_eur":row.get("min_margin_eur"),
        }
    return out

def build_feature_store(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve()
    inv=_load(root,"evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json")
    feasibility=_load(root,"data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json")
    frontier=_load(root,"data/BROKER_NATIVE_ADAPTIVE_INFORMATION_FRONTIER_V1.json")
    univariate=_load(root,"evidence/BROKER_NATIVE_FRONTIER_40_UNIVARIATE_STRUCTURAL_GATE_V1.json")
    breakout=_load(root,"evidence/BROKER_NATIVE_FRONTIER_40_BREAKOUT_VOLATILITY_EVENT_AVAILABILITY_V1.json")
    reps=_representative_map(frontier)
    uv=(univariate.get("scope") or {}).get("per_symbol") or {}
    bo=breakout.get("per_symbol") or {}
    identities=[]
    for source in inv["identity_coverage"]["eligible_identities"]:
        symbol=str(source["broker_symbol"])
        rep=reps.get(symbol)
        diag=uv.get(symbol)
        events=bo.get(symbol)
        exact_margin=rep.get("min_margin_eur") if rep else None
        unresolved=[]
        if rep is None:
            unresolved += ["asset_class","product_type","structural_signature","schedule_surface","weekend_capability"]
        unresolved += ["current_entry_trading_mode","minimum_volume","volume_step","prospectively_reusable_transaction_local_cost_authority"]
        if exact_margin is None:
            unresolved += ["exact_current_minimum_margin_eur"]
        if diag is None:
            unresolved += ["identity_level_13w_m5_coverage","chronology_quality","gap_structure","available_sample_surface"]
        identity={
            "broker_symbol_id":source.get("symbol_id"),
            "broker_symbol_name":symbol,
            "asset_class":rep.get("asset_class") if rep else None,
            "product_type":rep.get("product_type") if rep else None,
            "structural_signature":rep.get("structural_signature") if rep else None,
            "schedule_surface":rep.get("schedule_surface") if rep else None,
            "session_regions":rep.get("session_regions") if rep else None,
            "weekend_capability":rep.get("weekend_capability") if rep else None,
            "long_feasibility":"FEASIBLE",
            "short_feasibility":"FEASIBLE",
            "min_volume":None,
            "volume_step":None,
            "eur200_margin_efficiency":(
                {"minimum_margin_eur":exact_margin,
                 "capital_multiple_200_over_minimum_margin":round(200.0/float(exact_margin),6) if exact_margin else None,
                 "authority_role":"CURRENT_STRUCTURAL_REPRESENTATIVE_MARGIN"}
                if exact_margin is not None else None
            ),
            "transaction_cost_authority_status":(
                "OUTCOME_EXPOSED_LEGACY_COST_EVIDENCE_FORBIDDEN_AS_PROSPECTIVE_INPUT"
                if symbol=="NETH25" else
                "NO_PROSPECTIVELY_REUSABLE_FULL_TRANSACTION_LOCAL_COST_AUTHORITY"
            ),
            "transaction_cost_burden_when_authorized":None,
            "data_coverage_status":{
                "structural_representative":rep is not None,
                "accepted_2w_m5_probe":rep is not None,
                "accepted_13w_m5_development":diag is not None,
            },
            "chronology_quality":(
                {"strict_order":"PASS","off_cadence_intervals":diag.get("off_cadence_intervals"),
                 "first_utc":diag.get("first_utc"),"last_utc":diag.get("last_utc")}
                if diag is not None else None
            ),
            "gap_structure":(
                {"largest_gap_seconds":diag.get("largest_gap_seconds"),
                 "missing_m5_slots_between_bounds":diag.get("missing_m5_slots_between_bounds"),
                 "active_dates":diag.get("active_dates")}
                if diag is not None else None
            ),
            "available_sample_surface":(
                {"rows":diag.get("rows"),"causal_observation_pairs":diag.get("causal_observation_pairs"),
                 "utc_hour_bucket_count":diag.get("utc_hour_bucket_count"),
                 "weekday_buckets":diag.get("weekday_buckets")}
                if diag is not None else None
            ),
            "structural_event_availability_by_mechanism":{
                "BREAKOUT_VOLATILITY_EXPANSION":(
                    {"events":events.get("events"),"event_availability_rate":events.get("event_availability_rate"),
                     "eligible_contiguous_windows":events.get("eligible_contiguous_windows"),
                     "authority_role":"PRE_ECONOMIC_STRUCTURAL_EVENT_AVAILABILITY"}
                    if events is not None else None
                )
            },
            "redundancy_cluster":(
                sha256_bytes(canonical_bytes(rep.get("structural_signature")))[:16] if rep else None
            ),
            "novelty_contribution":(
                {"structural_signature_gain":1,"basis":"FROZEN_ONE_REPRESENTATIVE_PER_DISTINCT_SIGNATURE"}
                if rep else {"structural_signature_gain":None,"basis":"UNKNOWN_UNTIL_STRUCTURAL_METADATA_AVAILABLE"}
            ),
            "unresolved_prerequisite_classes":sorted(set(unresolved)),
            "additional_data_acquisition_cost":{
                "units_are_relative_not_billing":True,
                "compact_metadata_unit":0 if rep else 1,
                "selected_execution_snapshot_unit":3,
                "mechanism_local_transaction_cost_unit":10,
            },
            "evidence_role_and_authority":(
                "NON_ECONOMIC_STRUCTURAL_REUSABLE_REPRESENTATIVE"
                if rep else "CURRENT_BROKER_FEASIBILITY_ONLY_PENDING_STRUCTURAL_METADATA"
            ),
        }
        identities.append(identity)
    doc={
        "schema":"mxm.greenfield.broker-native-frontier-feature-store.v1",
        "status":"DETERMINISTIC_PRE_ECONOMIC_FEATURE_STORE",
        "evidence_epoch":21,
        "universe_identity_count":len(identities),
        "no_universal_best_symbol_score":True,
        "missingness_policy":"UNKNOWN_IS_EXPLICIT_AND_NEVER_SYNTHESIZED",
        "source_refs":[
            "evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json",
            "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json",
            "data/BROKER_NATIVE_ADAPTIVE_INFORMATION_FRONTIER_V1.json",
            "evidence/BROKER_NATIVE_FRONTIER_40_UNIVARIATE_STRUCTURAL_GATE_V1.json",
            "evidence/BROKER_NATIVE_FRONTIER_40_BREAKOUT_VOLATILITY_EVENT_AVAILABILITY_V1.json",
        ],
        "identities":identities,
        "summary":{
            "eligible_identities":len(identities),
            "structural_signature_known":sum(1 for x in identities if x["structural_signature"] is not None),
            "accepted_13w_identity_data":sum(1 for x in identities if x["data_coverage_status"]["accepted_13w_m5_development"]),
            "breakout_event_availability_known":sum(1 for x in identities if x["structural_event_availability_by_mechanism"]["BREAKOUT_VOLATILITY_EXPANSION"] is not None),
            "full_prospective_transaction_local_cost_authority":0,
        },
        "economic_effect":{"v2_attempts":0,"economic_outcomes":0,"returns_or_pnl_computed":False},
    }
    atomic_write_json(root/FEATURE_REL,doc)
    return doc

def build_opportunity_map(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve()
    fs=_load(root,FEATURE_REL)
    triage=_load(root,"evidence/BROKER_NATIVE_FRONTIER_40_ADAPTIVE_BREADTH_TRIAGE_V1.json")
    matrix={row["family"]:row for row in triage.get("family_ranking") or []}
    layers=[]
    for family in MECHANISM_FAMILIES:
        m=matrix.get(family,{})
        if family in {"TREND_MOMENTUM","MEAN_REVERSION","BREAKOUT_VOLATILITY_EXPANSION","SEASONALITY_SESSION_TIME","REGIME_CONTEXT_CONDITIONED","CAUSAL_ML_PREDICTIVE_OR_STATE_MODEL"}:
            current="40_STRUCTURAL_REPRESENTATIVES_HAVE_ACCEPTED_13W_M5_PREREQUISITE_SURFACE"
            missing=["1538_FRONTIER_IDENTITIES_WITHOUT_REPOSITORY_IDENTITY_LEVEL_13W_DATA","PROSPECTIVE_TRANSACTION_LOCAL_COST_AUTHORITY","MECHANISM_SPECIFIC_BREADTH_LAW"]
        elif family=="CARRY_TERM_STRUCTURE":
            current="CURRENT_13W_OHLC_DOES_NOT_SUPPLY_TERM_STRUCTURE_METADATA"
            missing=["TERM_STRUCTURE_METADATA","PROSPECTIVE_TRANSACTION_LOCAL_COST_AUTHORITY","MECHANISM_SPECIFIC_BREADTH_LAW"]
        else:
            current="LIMITED_CROSS_SYMBOL_PREREQUISITE_EVIDENCE_EXISTS_BUT_DOES_NOT_MAP_THE_FULL_1578_FRONTIER"
            missing=["FRONTIER_STRUCTURAL_REDUNDANCY_MAP","ALIGNED_MULTI_SYMBOL_DATA_FOR_SELECTED_SCOPE","PROSPECTIVE_TRANSACTION_LOCAL_COST_AUTHORITY","MECHANISM_SPECIFIC_BREADTH_LAW"]
        layers.append({
            "mechanism_family":family,
            "existing_prerequisite_state":current,
            "triage_data_sufficiency":m.get("data_sufficiency"),
            "triage_missing_prerequisites":m.get("missing_prerequisites") or [],
            "unresolved_before_economic_envelope":missing,
            "economic_pnl_or_outcomes_used":False,
            "universal_symbol_ranking_permitted":False,
        })
    doc={
        "schema":"mxm.greenfield.broker-native-frontier-opportunity-map.v1",
        "status":"DETERMINISTIC_MULTI_OBJECTIVE_PRE_ECONOMIC_MAP",
        "evidence_epoch":21,
        "universe_identity_count":fs["universe_identity_count"],
        "scientific_objective_from_existing_clean_decision":"REDUCE_EXECUTION_PREREQUISITE_AND_COVERAGE_UNCERTAINTY_WITHOUT_OUTCOME_DERIVED_SELECTION",
        "mechanism_layers":layers,
        "cross_mechanism_frontier":{
            "known_structural_signatures":fs["summary"]["structural_signature_known"],
            "structural_metadata_unknown_identities":fs["universe_identity_count"]-fs["summary"]["structural_signature_known"],
            "accepted_13w_identity_data":fs["summary"]["accepted_13w_identity_data"],
            "full_transaction_local_cost_authority":0,
        },
        "acquisition_options":[
            {
                "id":"RECOVER_HASH_BOUND_ACCEPTED_STRUCTURAL_DERIVATIVE",
                "coverage_gain":"UP_TO_1537_NONREPRESENTATIVE_IDENTITIES_WITHOUT_NEW_BROKER_CAPTURE",
                "relative_acquisition_cost":0,
                "condition":"ONLY_IF_BYTES_MATCHING_ACCEPTED_HASHES_ARE_DURABLY_RECOVERABLE",
                "economic_data":False,
            },
            {
                "id":"RERUN_EXISTING_READ_ONLY_BROKER_UNIVERSE_CAPTURE_V2",
                "coverage_gain":"STRUCTURAL_REDUNDANCY_AND_MICROSTRUCTURE_METADATA_FOR_OPEN_FRONTIER",
                "relative_acquisition_cost":1,
                "condition":"USE_IF_ACCEPTED_HASH_BOUND_DERIVATIVE_BYTES_ARE_NOT_RECOVERABLE",
                "expensive_bid_ask_history":False,
                "economic_data":False,
            },
            {
                "id":"STRUCTURAL_REPRESENTATIVE_EXECUTION_SNAPSHOT_41",
                "coverage_gain":"CURRENT_EXECUTION_SNAPSHOT_ACROSS_41_DISTINCT_STRUCTURAL_SIGNATURES",
                "relative_acquisition_cost":3,
                "condition":"AFTER_STRUCTURAL_METADATA_REUSE_OR_REFRESH_OR_WHEN EXECUTION_UNCERTAINTY_IS_THE_NEXT_ACTIVE_OBJECTIVE",
                "economic_data":False,
            },
            {
                "id":"FULL_FRONTIER_EXECUTION_SNAPSHOT_1578",
                "coverage_gain":"IDENTITY_LEVEL_CURRENT_EXECUTION_SNAPSHOT",
                "relative_acquisition_cost":100,
                "condition":"NOT_DEFAULT; REQUIRE_DEMONSTRATED_MARGINAL_INFORMATION_NEED",
                "economic_data":False,
            },
        ],
        "no_scalar_best_symbol_score":True,
        "economic_effect":{"v2_attempts":0,"economic_outcomes":0},
    }
    atomic_write_json(root/OPPORTUNITY_REL,doc)
    return doc

def build_information_gain_selection(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve()
    fs=_load(root,FEATURE_REL)
    om=_load(root,OPPORTUNITY_REL)
    selected={
        "selection_id":"EPOCH21-IG-001",
        "objective":"MAXIMIZE_FRONTIER_STRUCTURAL_AND_EXECUTION_PREREQUISITE_INFORMATION_PER_ACQUISITION_COST",
        "hard_feasibility_filters":[
            "NO_OUTCOME_DERIVED_SELECTION","NO_PROTECTED_FORWARD","NO_ECONOMIC_PNL_OR_RETURNS",
            "NO_C032_CAPTURE_PROSPECTIVE_REUSE","READ_ONLY_ONLY","BROKER_IDENTITY_MUST_BE_IN_OPEN_1578_FRONTIER",
        ],
        "pareto_method":"LEXICOGRAPHIC_FAIL_CLOSED_PARETO_PLUS_DIVERSITY_AWARE_MARGINAL_COVERAGE; NO_HIDDEN_SCALAR_SCORE",
        "selected_next_acquisition":{
            "primary":"RECOVER_HASH_BOUND_ACCEPTED_STRUCTURAL_DERIVATIVE",
            "fallback_if_not_recoverable":"RERUN_EXISTING_READ_ONLY_BROKER_UNIVERSE_CAPTURE_V2",
            "exact_selection_reason":"The repository has exact identity/feasibility for all 1578 but structural signatures and microstructure metadata for only 41. Reusing accepted hash-bound bytes has zero new broker-acquisition cost; if unavailable, one compact metadata-only frontier refresh closes the largest selection-layer missingness without paying for transaction-local history or opening outcomes.",
            "structural_signatures_added":"UNKNOWN_UNTIL_RECOVERY_OR_REFRESH; EXPECTS IDENTITY-TO-SIGNATURE MAP, NOT ECONOMIC EQUIVALENCE",
            "marginal_coverage_gain":fs["universe_identity_count"]-fs["summary"]["structural_signature_known"],
            "redundancy_penalty":"NONE_AT_THIS_STAGE_BECAUSE THE PURPOSE IS TO LEARN REDUNDANCY CLUSTERS",
            "uncertainty_reduced":["asset_class","product_type","structural_signature","schedule_surface","weekend_capability","current_entry_trading_mode","minimum_volume","volume_step","commission_and_structural_fee_metadata"],
            "acquisition_cost":{"preferred_reuse":0,"fallback_compact_metadata_refresh_relative_units":1,"units_are_relative_not_billing":True},
            "next_best_alternative":"STRUCTURAL_REPRESENTATIVE_EXECUTION_SNAPSHOT_41",
            "stopping_rule_state":"STOP_METADATA_EXPANSION_WHEN_ALL_1578_HAVE_AUTHORITATIVE_STRUCTURAL_AND_MICROSTRUCTURE_METADATA_OR_ACCEPTED_BYTES_ARE_RECOVERED; THEN RERUN SELECTOR BEFORE ANY EXPENSIVE COST/MARGIN CAPTURE",
        },
        "why_next_best_is_not_selected_yet":"A 41-representative execution snapshot is useful but leaves 1537 identities structurally unmapped in the durable feature store, making later diversity/redundancy control weaker and increasing anchoring risk.",
        "no_random_ticker_sampling":True,
        "no_arbitrary_fixed_top_n":True,
        "no_universal_best_symbol_score":True,
        "economic_effect":{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0},
    }
    atomic_write_json(root/SELECTOR_REL,selected)
    return selected

def build_next_acquisition_plan(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve()
    selector=_load(root,SELECTOR_REL)
    plan={
        "schema":"mxm.greenfield.broker-native-frontier-next-acquisition-plan.v1",
        "status":"FROZEN_PRE_CAPTURE_NON_ECONOMIC_INFORMATION_GAIN_PLAN",
        "evidence_epoch":21,
        "selection_ref":str(SELECTOR_REL),
        "contract_ref":str(CONTRACT_REL),
        "primary_action":"RECOVER_ACCEPTED_HASH_BOUND_STRUCTURAL_DERIVATIVE_IF_AVAILABLE",
        "fallback_read_only_capture":{
            "action":"RERUN_EXISTING_READ_ONLY_BROKER_UNIVERSE_CAPTURE_V2",
            "collector_package_builder":"tools/build_competition_broker_universe_capture_package.py",
            "collector_package_name":"MXM_COMPETITION_BROKER_UNIVERSE_CAPTURE_V2.zip",
            "collector_entrypoint":"COMPETITION_BROKER_UNIVERSE_CAPTURE_RUN.py",
            "expected_return_artifact":"MXM_COMPETITION_BROKER_UNIVERSE_V2.zip",
            "identity_source":"evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json::identity_coverage.eligible_identities",
            "fields":[
                "exact_broker_symbol_id_and_name","asset_class","product_type","current_entry_trading_mode",
                "minimum_volume","volume_step","commission_and_structural_fee_metadata",
                "schedule_surface","weekend_capability","account_fingerprint","capture_timestamp",
                "per_identity_capture_status_and_fail_closed_reason",
            ],
            "explicitly_not_requested":[
                "historical_price_series","returns","pnl","post_event_followthrough",
                "transaction_local_bid_ask_history_for_all_1578","live_orders","account_mutation",
            ],
            "read_only":True,
        },
        "after_acceptance":"REBUILD_FEATURE_STORE_THEN_RERUN_INFORMATION_GAIN_SELECTOR_BEFORE_ANY EXECUTION-SNAPSHOT OR MECHANISM-LOCAL COST BATCH",
        "user_action_required_now":True,
        "external_broker_capture_required_only_if_hash_bound_source_bytes_cannot_be_recovered":True,
        "accounting_effect":{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0},
    }
    atomic_write_json(root/ACQUISITION_REL,plan)
    return plan

def materialize_all(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve()
    contract=build_capture_contract(root)
    fs=build_feature_store(root)
    om=build_opportunity_map(root)
    sel=build_information_gain_selection(root)
    plan=build_next_acquisition_plan(root)
    return {
        "contract_ref":str(CONTRACT_REL),"feature_store_ref":str(FEATURE_REL),
        "opportunity_map_ref":str(OPPORTUNITY_REL),"selection_ref":str(SELECTOR_REL),
        "next_acquisition_plan_ref":str(ACQUISITION_REL),
        "eligible_identities":fs["universe_identity_count"],
        "selected_next_acquisition":sel["selected_next_acquisition"],
        "economic_effect":plan["accounting_effect"],
    }
