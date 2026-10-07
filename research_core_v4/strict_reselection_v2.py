"""Prospective selection compartment: normalized structural inputs only, no history."""
import builtins
import copy
import hashlib
import io
import json
import os
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
S='research_core_v4/state/'
INPUT=S+'STRICT_PREOUTCOME_RESELECTION_V2_INPUTS_V1.json'
RESULT=S+'STRICT_PREOUTCOME_RESELECTION_V2_RESULT_V1.json'
READS={S+'INFORMATION_SOURCE_CATALOG_V1.json',S+'MASTER1576_QUALIFICATION_V2_POST_SCREEN_STRUCTURAL_SUMMARY_V1.json',S+'MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json'}
SOURCE_IDS=('UNIVARIATE_PRICE_STATE','MULTISCALE_PRICE_STATE','VOLATILITY_AND_REALIZED_VARIANCE_STATE','BROKER_NATIVE_ACTIVITY_STATE','SESSION_AND_LIQUIDITY_STATE','TOP_OF_BOOK_QUOTE_STATE','CROSS_SECTIONAL_RELATIVE_STATE','FACTOR_OR_BASKET_RESIDUAL_STATE','CROSS_INSTRUMENT_RELATIONAL_STATE','CURVE_CASH_FORWARD_PERPETUAL_RELATIONSHIPS','BROKER_NATIVE_CARRY_FINANCING_SWAP','REGIME_AND_STRUCTURAL_BREAK_STATE')
DEFINITIONS=('Past price observations of one identity','Price observations at distinct causal aggregation scales','Price variation and realized dispersion within completed intervals','Broker reported activity counts with timestamped bars','Authoritative session timing and market open or closed state','Timestamped bid and ask quote observations','Simultaneous relative observations across a coherent cohort','Own observations relative to an independently specified basket','Observations linked by an authoritative economic relationship','Contracts for the same underlying at different settlement or maturity terms','Point in time financing and carry cashflow observations','Causally observable state changes in a time series')
MECHANISMS=('Price location inside the completed hourly high-low range conditions next-hour adjustment','Agreement between disjoint completed 15 minute and hourly aggregation states conditions subsequent adjustment','Completed-hour variation concentration across its twelve M5 bars conditions next-hour variation','Distribution of broker activity across a completed hour provides information beyond its price path','Distance to the authoritative next session boundary conditions subsequent price adjustment','Recent signed quote revision sequencing contributes information beyond contemporaneous midpoint change','Contemporaneous within-cohort price-location dispersion conditions next-hour peer adjustment','Own price location relative to a structurally defined basket conditions next-hour adjustment','Authoritative non-triad economic linkage permits observable peer-to-own information transmission','Authoritatively linked settlement-term spread state conditions later term-relationship adjustment','A published financing cashflow schedule conditions behavior around its effective timestamp','Change in completed-hour price-location distribution conditions subsequent state persistence')
FIELDS={'information_source','materially_distinct_causal_mechanism','why_information_exists_before_entry','observable_inputs','own_information_baseline','incremental_information_claim','coherent_context_and_cohort','causal_timestamp_law','compact_horizon_family','response_function','synchronization_requirement','missingness_law','dependence_unit','compute_geometry','execution_information_path','confirmation_path'}
NEXT='STRICT_PREOUTCOME_INFORMATION_SOURCE_RESELECTION_V2_UNRESOLVED_PENDING_INDEPENDENT_GOVERNANCE'
FORBIDDEN=('CLASSIFICATION','RESULT_DERIVED','CLOSURE_OUTCOME','EFFECT_SIZE','P_VALUE','PVALUES','PNL','WINNER','LOSER','NEAR_MISS','CARRY_FORWARD_HARD_CLOSURE','AUTHENTIC_FRICTION_CLOSED','EXACT_SPECIFICATION_CLOSED_BROADER_CONCEPT_OPEN','METHOD_DEPENDENT_REINTERPRETATION_REQUIRED','POST_QUOTE_V4_CLOSURE_LEDGER','V3_CLOSURE_DEPENDENCY_GRAPH','NEXT_INFORMATION_SOURCE_SELECTION_V6','TRIAD_V7','PRIORITY','HISTORICAL_EFFECT','HISTORICAL_RETURN','PASS_FAIL','ECONOMIC_SUCCESS','ECONOMIC_FAILURE')
def require(ok,code):
    if not ok:raise ValueError(code)
def canonical(d):return (json.dumps(d,sort_keys=True,indent=2)+'\n').encode()
def digest(b):return hashlib.sha256(b).hexdigest()
def neutral_numbers(d):
    if isinstance(d,dict):return {k:neutral_numbers(v) for k,v in d.items() if not isinstance(v,str)}
    if isinstance(d,list):return [neutral_numbers(x) for x in d if not isinstance(x,str)]
    require(isinstance(d,(int,float,bool)) or d is None,'NONSTRUCTURAL_GEOMETRY');return d
def project(catalog,summary,roster):
    require([x['id'] for x in catalog['sources']]==list(SOURCE_IDS),'SOURCE_UNIVERSE_DRIFT')
    geometry=('identity_count','total_row_count','row_count_by_segment','row_count_quantiles','active_day_geometry','gap_geometry','segment_presence_counts','tick_volume_descriptive')
    entries=[{k:x[k] for k in ('MASTER_ORDINAL','SYMBOL_ID','BROKER_NATIVE_CONTEXT')} for x in roster['entries']]
    return {'schema':'mxm.v4.strict-reselection-v2.neutral-inputs.v1','source_definitions':[{'id':i,'definition':d} for i,d in zip(SOURCE_IDS,DEFINITIONS)],'modalities':{'canonical_m5':{'fields':['identity','timestamp','open','high','low','close','tick_volume'],'resolution_minutes':5,'availability':'Completed bar only; close time before entry','provenance':'Accepted broker native historical M5; structural summary only in this task'},'quotes':{'point_in_time_sequence_support_certified':False},'sessions':{'historical_session_labels_certified':False},'relationships':{'authoritative_membership_and_linkage_certified':False},'financing':{'point_in_time_historical_schedule_certified':False}},'global_geometry':{k:neutral_numbers(summary['global'][k]) for k in geometry},'context_geometry':{k:{f:neutral_numbers(v[f]) for f in geometry} for k,v in summary['by_broker_native_context'].items()},'identities':entries,'current_structural_execution':{'account_equity_eur':200,'identity_count_with_accepted_current_structural_gates':len(entries),'historical_cost_observable':False},'exact_synchronized_masks_certified':False}
@contextmanager
def io_firewall(root,allowed,reads):
    root=Path(root).resolve();paths={str((root/x).resolve()) for x in allowed};original=builtins.open
    def safe(file,mode='r',*a,**kw):
        path=str(Path(file).resolve());require(path in paths and not any(c in mode for c in 'wax+'),'READ_FIREWALL_DENIED:'+path)
        reads.append(str(Path(path).relative_to(root)));return original(file,mode,*a,**kw)
    original_fd=os.open
    def safe_fd(file,flags,*a,**kw):
        path=str(Path(file).resolve());require(path in paths and flags==os.O_RDONLY,'READ_FIREWALL_DENIED:'+path)
        reads.append(str(Path(path).relative_to(root)));return original_fd(file,flags,*a,**kw)
    with patch.object(builtins,'open',safe),patch.object(io,'open',safe),patch.object(os,'open',safe_fd):yield

def project_root(root,reads=None):
    reads=[] if reads is None else reads
    with io_firewall(root,READS,reads):
        docs={x:json.loads((Path(root)/x).read_bytes()) for x in READS}
    return project(docs[S+'INFORMATION_SOURCE_CATALOG_V1.json'],docs[S+'MASTER1576_QUALIFICATION_V2_POST_SCREEN_STRUCTURAL_SUMMARY_V1.json'],docs[S+'MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json'])
def clean_tree(x):
    if isinstance(x,dict):
        for k,v in x.items():
            require(not any(t in k.upper() for t in FORBIDDEN),'FORBIDDEN_SELECTION_FIELD:'+k);clean_tree(v)
    elif isinstance(x,list):
        for v in x:clean_tree(v)
    elif isinstance(x,str):require(not any(t in x.upper() for t in FORBIDDEN),'FORBIDDEN_SELECTION_VALUE')
EXPECTED_INPUT_SHA256='fa01029ed0ac8bee799594a4d08cc053ce55aaedce3b3c2a4375435a3048234b'
def validate_inputs(d):
    clean_tree(d)
    require(digest(canonical(d))==EXPECTED_INPUT_SHA256,'NEUTRAL_INPUT_HASH_DRIFT')
    require(set(d)=={'schema','source_definitions','modalities','global_geometry','context_geometry','identities','current_structural_execution','exact_synchronized_masks_certified'},'UNKNOWN_INPUT_FIELD')
    require(d['schema']=='mxm.v4.strict-reselection-v2.neutral-inputs.v1','INPUT_SCHEMA')
    require(d['source_definitions']==[{'id':i,'definition':x} for i,x in zip(SOURCE_IDS,DEFINITIONS)],'SOURCE_DEFINITION_DRIFT')
    require(len(d['identities'])==1575 and all(set(x)=={'MASTER_ORDINAL','SYMBOL_ID','BROKER_NATIVE_CONTEXT'} for x in d['identities']),'ROSTER_SCHEMA')
    for x in d['identities']:require(x['BROKER_NATIVE_CONTEXT'] in d['context_geometry'],'CONTEXT_IDENTITY')
    # Entire normalized structure must equal the prospectively frozen schema shape.
    require(set(d['modalities'])=={'canonical_m5','quotes','sessions','relationships','financing'},'MODALITY_SCHEMA')
    require(set(d['current_structural_execution'])=={'account_equity_eur','identity_count_with_accepted_current_structural_gates','historical_cost_observable'},'STRUCTURAL_SCHEMA')
    require(d['current_structural_execution']['account_equity_eur']==200,'EQUITY_DRIFT')
    for scope in [d['global_geometry'],*d['context_geometry'].values()]:
        require(set(scope)=={'identity_count','total_row_count','row_count_by_segment','row_count_quantiles','active_day_geometry','gap_geometry','segment_presence_counts','tick_volume_descriptive'},'GEOMETRY_SCHEMA')
        clean_tree(scope)

def candidates(d):
    validate_inputs(d);out=[]
    contexts=sorted(d['context_geometry'])
    for i,(source,mechanism) in enumerate(zip(SOURCE_IDS,MECHANISMS)):
        relation=i in (6,7,8,9);extra=i in (4,5,9,10)
        out.append({'information_source':source,'materially_distinct_causal_mechanism':mechanism,'why_information_exists_before_entry':'Completed observations and effective metadata precede entry; no response data used to construct features','observable_inputs':'Completed canonical M5 OHLC'+('; broker tick volume' if i==3 else '')+('; independently authenticated point in time modality required' if extra or relation else ''),'own_information_baseline':'Own last completed M5 and hourly price location, range and broker activity, with causal clock controls; incremental predictor excluded from baseline','incremental_information_claim':'Additional conditional information beyond the declared own-information baseline; no historical effect asserted','coherent_context_and_cohort':{'context_policy':'Every broker native context evaluated as its own structural cohort; no support or activity ranking','available_contexts':contexts,'membership_rule':'All eligible identities in a context; authoritative linkage required for basket, peer or contract relations; no name-only linkage'},'causal_timestamp_law':'Use only observations with authentic availability <= entry timestamp; completed intervals only; effective metadata known by entry','compact_horizon_family':{'m5_bars':[1,12],'prospective_rationale':'One authentic M5 update and one full hour for immediate versus hourly propagation; paired planned family, no best-horizon choice','selected_for_real_test':False},'response_function':'Future closed-bar log price displacement at each declared horizon, conditionally incremental to own baseline; financing or term candidates additionally require authenticated cashflow or term response. Definition only: no values calculated','synchronization_requirement':'Exact authentic common timestamps for related identities; no forward-filled prices; own interval requires all twelve M5 observations','missingness_law':'Exclude incompletely observed feature or response windows; retain masks and reasons; no imputation, no missingness-as-null','dependence_unit':'Shared calendar-time blocks with within-context and cross-context simultaneous dependence; identities are not independent trials','compute_geometry':'One causal streaming feature pass per identity plus cohort reductions; finite feature families, no parameter search or automatic mechanism optimization','execution_information_path':'Current EUR200 structural eligibility only; side-aware historical spread and slippage remain unknown and require later authentic certification','confirmation_path':'Development and selection payment followed by genuinely disjoint confirmation; existing development data cannot certify confirmation'})
    require(all(set(x)==FIELDS for x in out),'CANDIDATE_SCHEMA');return out
SEMANTIC_KEYS={'mechanism_identity','feature_definition','context_cohort_definition','horizon_family','response_function','parameterization'}
def validate_registry(registry):
    require(isinstance(registry,list),'REGISTRY_SCHEMA')
    for x in registry:
        require(set(x)==SEMANTIC_KEYS,'REGISTRY_NON_SEMANTIC_FIELD')
        for k in ['mechanism_identity','feature_definition','context_cohort_definition','response_function','parameterization']:
            require(isinstance(x[k],str),'REGISTRY_SEMANTIC_TYPE')
            require(not any(t in x[k].upper() for t in ('P_VALUE','EFFECT_SIZE','PNL','WINNER_STATUS','NEAR_MISS_STATUS','PASS_FAIL','CARRY_FORWARD_HARD_CLOSURE','AUTHENTIC_FRICTION_CLOSED','EXACT_SPECIFICATION_CLOSED_BROADER_CONCEPT_OPEN','METHOD_DEPENDENT_REINTERPRETATION_REQUIRED')),'REGISTRY_RESULT_VALUE')
        require(isinstance(x['horizon_family'],list) and all(type(h) is int and h>0 for h in x['horizon_family']),'REGISTRY_HORIZON_SCHEMA')
def exact_collision(candidate_semantics,registry):
    require(set(candidate_semantics)==SEMANTIC_KEYS,'SEMANTIC_SCHEMA');validate_registry(registry)
    return any(canonical(x)==canonical(candidate_semantics) for x in registry)
def build(d):
    c=candidates(d)
    # Nonduplication registry is deliberately not loaded: no candidate is selected.
    return {'schema':'mxm.v4.strict-preoutcome-reselection.v2.result.v1','status':NEXT,'normalized_input_sha256':digest(canonical(d)),'candidates':c,'selection':{'selected_source':None,'selected_mechanism':None,'historical_design_registry_used':False,'exact_nonduplication_certified':False,'reason':'Observable M5 supports several different causal questions. Structural summaries do not certify exact common masks, causal incremental identifiability or a mechanism-specific path to a genuine test. The permitted evidence establishes no single defensible preference among M5 candidates; extra-modality candidates need authenticated timestamp or linkage contracts. No historical outcome or catalog order breaks this unresolved comparison. Power calibration is not a prerequisite for selection.'},'comparison':[{'information_source':x['information_source'],'own_m5_observable':True,'additional_modality_or_linkage_required':i in (4,5,6,7,8,9,10),'exact_synchronization_certified':False,'causal_identifiability_certified':False,'finite_streaming_compute_possible':True,'historical_execution_cost_observable':False,'generalization_confirmation_path':'Prospective coherent cohort and genuinely disjoint confirmation required','preference':'UNRESOLVED_NO_OUTCOME_TIEBREAK'} for i,x in enumerate(c)],'no_claim_of_erased_project_adaptivity':True,'complete_design_selected':False,'power_trials':0,'duration_selected':False,'market_response_opened':False,'search_budget_use':0,'protected_forward_opened':False,'confirmation_opened':False,'next_action':NEXT}
def build_root(root,reads=None):
    reads=[] if reads is None else reads
    with io_firewall(root,{INPUT},reads):d=json.loads((Path(root)/INPUT).read_bytes())
    # No file reader is provided to the pure selector.
    with io_firewall(root,set(),reads):return build(d)
