"""Zero-market-row semantic audit; own-candidate-only certificates, frozen functional."""
import copy
import hashlib
import json
from pathlib import Path
from research_core_v4.strict_reselection_v2 import io_firewall, canonical, require
from research_core_v4 import strict_selection_functional_v1 as functional
S='research_core_v4/state/'
BASELINE=S+'STRICT_PREOUTCOME_V2_SHARED_OWN_INFORMATION_BASELINE_CERTIFICATE_V1.json'
FREEZE=S+'STRICT_PREOUTCOME_V2_SEMANTIC_CERTIFICATE_FREEZE_MANIFEST_V1.json'
REAPPLIED=S+'STRICT_PREOUTCOME_V2_SEMANTIC_FUNCTIONAL_REAPPLICATION_V1.json'
NEXT_PLAN=S+'STRICT_PREOUTCOME_V2_NEXT_MINIMUM_STRUCTURAL_DISCRIMINATOR_PLAN_V1.json'
NEXT='STRICT_PREOUTCOME_V2_SEMANTIC_CERTIFICATES_AND_FROZEN_FUNCTIONAL_REAPPLICATION_COMPLETE_NEXT_MINIMUM_STRUCTURAL_DISCRIMINATOR_FROZEN_PENDING_INDEPENDENT_AUDIT'
INPUT=functional.INPUT;PROPOSALS=functional.PROPOSALS;FUNCTIONAL=functional.FUNCTIONAL;GAP=functional.GAP;PLAN=functional.PLAN
ALLOWED={INPUT,PROPOSALS,FUNCTIONAL,GAP,PLAN}
HASHES={INPUT:'fa01029ed0ac8bee799594a4d08cc053ce55aaedce3b3c2a4375435a3048234b',PROPOSALS:'e1ab6c79c555b84e1edf0141c50f95c086c4c74b7e0188497cddf065f49d8396',FUNCTIONAL:'561e054658a4878008db10dbd6610408246756f5cabf7336a0c0b5088f4e1d2d',GAP:'9a7004185698062a4c549ae18a73d4fc180d008febd30c102e5fff3853d5be4a',PLAN:'0b72f4da21f38f2c0848de303c863a88368cee8165275bff56054ee93c3e97e6'}
SOURCES=('MULTISCALE_PRICE_STATE','VOLATILITY_AND_REALIZED_VARIANCE_STATE','BROKER_NATIVE_ACTIVITY_STATE','SESSION_AND_LIQUIDITY_STATE','TOP_OF_BOOK_QUOTE_STATE','CROSS_SECTIONAL_RELATIVE_STATE','FACTOR_OR_BASKET_RESIDUAL_STATE','CROSS_INSTRUMENT_RELATIONAL_STATE','CURVE_CASH_FORWARD_PERPETUAL_RELATIONSHIPS','BROKER_NATIVE_CARRY_FINANCING_SWAP','REGIME_AND_STRUCTURAL_BREAK_STATE')
CERT_FIELDS={'candidate_definition_sha256','information_source','exact_baseline_map_B_t','exact_feature_map_Phi_i','input_domain','units','preentry_information_readset','availability_timestamp_map','cohort_or_linkage_domain','synchronization_requirement','sigma_containment_verdict','constructive_nonredundancy_witness_or_redundancy_proof','semantic_equivalence_to_frozen_proposal_proof','formalization_status'}
def sha(data):return hashlib.sha256(data).hexdigest()
def cert_ref(source):return S+'STRICT_PREOUTCOME_V2_SEMANTIC_CERTIFICATE_'+source+'_V1.json'
def load_allowed(root,seen=None):
    seen=[] if seen is None else seen
    with io_firewall(root,ALLOWED,seen):raw={p:(Path(root)/p).read_bytes() for p in sorted(ALLOWED)}
    for p,h in HASHES.items():require(sha(raw[p])==h,'ACCEPTED_HASH_DRIFT:'+p)
    docs={p:json.loads(v) for p,v in raw.items()}
    require(docs[FUNCTIONAL]==functional.functional(),'FUNCTIONAL_SEMANTIC_DRIFT')
    require([c['information_source'] for c in docs[PROPOSALS]['candidates'][1:]]==list(SOURCES),'CONTENDER_DRIFT')
    return docs
BASELINE_AMBIGUITIES={
 'last_completed_M5_projection':'The prose does not say whether the raw last bar, selected price fields or a derived M5 state enter B_t.',
 'hourly_price_location':'No unique location transformation, completed-hour anchor or treatment of flat high-low intervals is specified.',
 'range_projection':'Which M5/hour interval, price-unit versus normalized/log range representation and degeneracy law are not fixed.',
 'broker_activity_projection':'A last-bar count, completed-hour aggregate or full within-hour vector would define different baseline sigma-algebras; the prose does not choose.',
 'causal_clock_controls':'The exact clock variables, timezone/session semantics and encoding are not specified.',
 'aggregation_clock_domain':'Completed-hour alignment and interval boundary convention are not uniquely specified; neutral resolution alone is insufficient.'}

def baseline_certificate(own_baseline_text,neutral_schema):
    # Only the shared text and neutral modality schema are inputs. No comparative evidence.
    require(own_baseline_text=='Own last completed M5 and hourly price location, range and broker activity, with causal clock controls; incremental predictor excluded from baseline','BASELINE_TEXT_DRIFT')
    return {'schema':'mxm.v4.strict-preoutcome-v2.shared-baseline-certificate.v1','formalization_status':'FORMALIZATION_UNRESOLVED','frozen_baseline_text':own_baseline_text,'EXACT_MATHEMATICAL_MAP':None,'INPUT_VARIABLES':{'available_schema_fields':copy.deepcopy(neutral_schema['fields']),'baseline_inclusion_projection':None,'note':'Available raw fields are not automatically included in B_t.'},'DOMAIN':{'canonical_resolution_minutes':neutral_schema['resolution_minutes'],'exact_state_and_aggregation_domain':None},'UNITS':{'broker_price_fields':'Broker-native units; normalization and per-identity quote units not fixed here','broker_activity':'Reported count; inclusion and aggregation map not fixed','clock':'Exact clock coordinate/encoding not fixed'},'CAUSAL_AVAILABILITY_TIMESTAMPS':{'required':'Each authentic availability timestamp must precede or equal entry, with closed bars only','exact_map':None},'COMPLETED_BAR_LAW':'Use completed M5 and completed hourly observations only; no forming-bar or future response input. Exact hour anchoring remains unresolved.','CLOCK_CONTROLS':None,'MISSINGNESS_LAW':{'required':'No imputation; missing inputs make the feature window unavailable','exact_mask':None},'READ_SET':{'required_semantic_components':list(BASELINE_AMBIGUITIES),'exact_variables_and_timestamps':None},'OUTPUT_SIGMA_ALGEBRA_INTERPRETATION':'sigma(B_t) cannot be instantiated uniquely while the projection and clock maps are unspecified. No raw-path baseline or invented smaller projection is assumed.','component_formalization':{k:{'status':'FORMALIZATION_UNRESOLVED','map':None,'reason':v} for k,v in BASELINE_AMBIGUITIES.items()},'unique_semantic_constraints':['Shared own-information baseline as frozen','Completed observations causally available before entry','Incremental predictor excluded from baseline'],'new_design_choice_added':False,'market_rows_used':0}

FEATURE_GAPS={
'MULTISCALE_PRICE_STATE':['The aggregation-state map at 15 minutes and one hour is undefined.','Agreement operator and disjoint-window anchor are unspecified.'],
'VOLATILITY_AND_REALIZED_VARIANCE_STATE':['Variation measure and concentration operator across the twelve M5 bars are unspecified.','No exact unit/normalization or flat-hour rule is fixed.'],
'BROKER_NATIVE_ACTIVITY_STATE':['Distribution could mean the full count vector, normalized weights or a summary; no exact map is fixed.','Baseline activity granularity is unresolved, so additional information cannot be identified.'],
'SESSION_AND_LIQUIDITY_STATE':['The authoritative session schedule, effective revision timestamp and timezone contract are uncertified.','Boundary choice and distance encoding are not fixed.'],
'TOP_OF_BOOK_QUOTE_STATE':['Authentic timestamped bid/ask sequence contract is uncertified.','Recent sequence window and signed sequencing functional are unspecified.'],
'CROSS_SECTIONAL_RELATIVE_STATE':['Dispersion functional, peer aggregation and synchronized membership mask are unspecified.','Authoritative cohort/linkage availability is not certified in neutral inputs.'],
'FACTOR_OR_BASKET_RESIDUAL_STATE':['Basket membership, weights, relative-location map and causal timestamps are unspecified.','Authoritative basket contract is not certified in neutral inputs.'],
'CROSS_INSTRUMENT_RELATIONAL_STATE':['No exact non-triad economic relation, lag/readset or transmission feature is fixed.','Authoritative linkage contract is not certified in neutral inputs.'],
'CURVE_CASH_FORWARD_PERPETUAL_RELATIONSHIPS':['Underlying, settlement/maturity linkage, roll and price-unit contract are uncertified.','Term spread map and available timestamps are unspecified.'],
'BROKER_NATIVE_CARRY_FINANCING_SWAP':['Historical point-in-time financing schedule and effective cashflow contract are uncertified.','Schedule feature and cashflow units/encoding are unspecified.'],
'REGIME_AND_STRUCTURAL_BREAK_STATE':['Price-location distribution, reference interval and change functional are unspecified.','Exact online/prefix state and baseline clock map are not fixed.']}
MODALITY={
'SESSION_AND_LIQUIDITY_STATE':('sessions','historical_session_labels_certified'),
'TOP_OF_BOOK_QUOTE_STATE':('quotes','point_in_time_sequence_support_certified'),
'CROSS_SECTIONAL_RELATIVE_STATE':('relationships','authoritative_membership_and_linkage_certified'),
'FACTOR_OR_BASKET_RESIDUAL_STATE':('relationships','authoritative_membership_and_linkage_certified'),
'CROSS_INSTRUMENT_RELATIONAL_STATE':('relationships','authoritative_membership_and_linkage_certified'),
'CURVE_CASH_FORWARD_PERPETUAL_RELATIONSHIPS':('relationships','authoritative_membership_and_linkage_certified'),
'BROKER_NATIVE_CARRY_FINANCING_SWAP':('financing','point_in_time_historical_schedule_certified')}

def certificate(candidate,baseline,neutral_modalities):
    """Independent pure constructor: one candidate, shared baseline and modality flags only."""
    source=candidate['information_source'];require(source in SOURCES,'UNKNOWN_CONTENDER')
    extra=source in MODALITY
    if extra:
        modality,flag=MODALITY[source];require(neutral_modalities[modality][flag] is False,'UNEXPECTED_MODALITY_CERTIFICATION')
    status='REQUIRED_AUTHENTIC_MODALITY_OR_LINKAGE_UNCERTIFIED' if extra else 'FORMALIZATION_UNRESOLVED'
    require(baseline['EXACT_MATHEMATICAL_MAP'] is None,'UNEXPECTED_BASELINE_COMPLETION')
    return {'candidate_definition_sha256':sha(canonical(candidate)),'information_source':source,'exact_baseline_map_B_t':{'ref':BASELINE,'sha256':sha(canonical(baseline)),'map':None,'status':'FORMALIZATION_UNRESOLVED'},'exact_feature_map_Phi_i':None,'input_domain':{'frozen_observable_inputs':candidate['observable_inputs'],'exact_domain':None},'units':{'exact_feature_units':None,'reason':'The missing feature map and normalization prevent a unique unit specification.'},'preentry_information_readset':{'frozen_preentry_law':candidate['causal_timestamp_law'],'exact_readset':None},'availability_timestamp_map':{'exact_map':None,'additional_modality_already_certified':False if extra else None,'completed_M5_constraint':'No forming bars or post-entry inputs'},'cohort_or_linkage_domain':{'frozen_definition':copy.deepcopy(candidate['coherent_context_and_cohort']),'exact_linkage_contract':None,'authoritative_extra_contract_certified':False if extra else None},'synchronization_requirement':{'frozen_law':candidate['synchronization_requirement'],'exact_identity_time_mask':None},'sigma_containment_verdict':'UNRESOLVED_BASELINE_AND_FEATURE_MAPS_NOT_UNIQUELY_DETERMINED','constructive_nonredundancy_witness_or_redundancy_proof':{'status':'NOT_CERTIFIABLE','witness':None,'proof':None,'reason':'Two legal states with identical B_t and different Phi_i cannot be certified without choosing the unresolved maps and domain. No formula is invented.'},'semantic_equivalence_to_frozen_proposal_proof':{'status':'NO_NEW_FORMULA_OR_MECHANISM_ADDED','frozen_mechanism':candidate['materially_distinct_causal_mechanism'],'feature_formalization_gaps':FEATURE_GAPS[source],'shared_baseline_gaps':sorted(baseline['component_formalization']),'reason':'Certificate records the exact missing choices; it does not complete or improve the mechanism.'},'formalization_status':status}

def derive_certificates(root,seen=None):
    docs=load_allowed(root,seen);candidates=docs[PROPOSALS]['candidates'];baseline_text=candidates[0]['own_information_baseline']
    require(all(c['own_information_baseline']==baseline_text for c in candidates),'NONSHARED_BASELINE')
    with io_firewall(root,set(),[]):
        base=baseline_certificate(baseline_text,copy.deepcopy(docs[INPUT]['modalities']['canonical_m5']))
        # Independent calls receive no registry, assessment, comparison, other certificate or result reason.
        certs={cert_ref(c['information_source']):certificate(copy.deepcopy(c),copy.deepcopy(base),copy.deepcopy(docs[INPUT]['modalities'])) for c in candidates[1:]}
    return base,certs

def freeze_certificates(root,seen=None):
    """Authorized zero-row semantic execution: baseline disk freeze precedes every certificate."""
    root=Path(root);docs=load_allowed(root,seen);candidates=docs[PROPOSALS]['candidates']
    baseline_text=candidates[0]['own_information_baseline'];require(all(c['own_information_baseline']==baseline_text for c in candidates),'NONSHARED_BASELINE')
    with io_firewall(root,set(),[]):base=baseline_certificate(baseline_text,copy.deepcopy(docs[INPUT]['modalities']['canonical_m5']))
    (root/BASELINE).write_bytes(canonical(base))
    certs={}
    for candidate in candidates[1:]:
        with io_firewall(root,set(),[]):c=certificate(copy.deepcopy(candidate),copy.deepcopy(base),copy.deepcopy(docs[INPUT]['modalities']))
        p=cert_ref(c['information_source']);require(set(c)==CERT_FIELDS,'CERTIFICATE_SCHEMA');(root/p).write_bytes(canonical(c));certs[p]=c
    manifest={'schema':'mxm.v4.strict-preoutcome-v2.semantic-certificate-freeze.v1','status':'ALL_ELEVEN_CERTIFICATES_FROZEN_BEFORE_FUNCTIONAL_REAPPLICATION','baseline':{'ref':BASELINE,'sha256':sha(canonical(base))},'certificates':[{'ref':p,'sha256':sha(canonical(c)),'information_source':c['information_source']} for p,c in certs.items()],'freeze_sequence':[BASELINE,*certs],'independence':'Each candidate constructor received only its frozen definition, shared baseline and neutral modality flags; no peer certificate or comparative position.','market_rows_used':0,'historical_outcome_files_read':0}
    (root/FREEZE).write_bytes(canonical(manifest));return manifest

REAPPLICATION_READS={INPUT,PROPOSALS,FUNCTIONAL,BASELINE,FREEZE,*[cert_ref(s) for s in SOURCES]}
def reapply_root(root,seen=None):
    seen=[] if seen is None else seen
    with io_firewall(root,REAPPLICATION_READS,seen):raw={p:(Path(root)/p).read_bytes() for p in sorted(REAPPLICATION_READS)}
    for p in [INPUT,PROPOSALS,FUNCTIONAL]:require(sha(raw[p])==HASHES[p],'REAPPLICATION_ACCEPTED_HASH_DRIFT')
    docs={p:json.loads(v) for p,v in raw.items()};m=docs[FREEZE]
    require(m['status']=='ALL_ELEVEN_CERTIFICATES_FROZEN_BEFORE_FUNCTIONAL_REAPPLICATION','FREEZE_STATUS')
    require(m['freeze_sequence']==[BASELINE,*[cert_ref(s) for s in SOURCES]],'FREEZE_SEQUENCE')
    require(len(m['certificates'])==11 and len({x['ref'] for x in m['certificates']})==11,'FREEZE_COUNT')
    for x in [m['baseline'],*m['certificates']]:require(sha(raw[x['ref']])==x['sha256'],'FROZEN_CERTIFICATE_HASH_DRIFT')
    proposals=docs[PROPOSALS]['candidates'];require([x['information_source'] for x in m['certificates']]==list(SOURCES),'CERTIFICATE_ORDER')
    with io_firewall(root,set(),[]):
        old=functional.assess(docs[INPUT],docs[PROPOSALS],docs[FUNCTIONAL]);rows=copy.deepcopy(old['assessments'])
        for row,c in zip(rows[1:],proposals[1:]):
            cert=docs[cert_ref(c['information_source'])];require(set(cert)==CERT_FIELDS,'CERTIFICATE_SCHEMA')
            require(cert['candidate_definition_sha256']==sha(canonical(c)),'CANDIDATE_BINDING_DRIFT')
            require(cert==certificate(copy.deepcopy(c),copy.deepcopy(docs[BASELINE]),copy.deepcopy(docs[INPUT]['modalities'])),'SEMANTIC_DERIVATION_DRIFT')
            status=cert['formalization_status']
            require(status in {'EXACT_REDUNDANT_WITH_BASELINE','STRUCTURAL_NONREDUNDANCY_CERTIFIED','FORMALIZATION_UNRESOLVED','REQUIRED_AUTHENTIC_MODALITY_OR_LINKAGE_UNCERTIFIED'},'CERTIFICATE_STATUS')
            row['hard_gates']['identifiable_incremental_claim']='FAIL' if status=='EXACT_REDUNDANT_WITH_BASELINE' else ('PASS' if status=='STRUCTURAL_NONREDUNDANCY_CERTIFIED' else 'UNKNOWN')
            if status=='REQUIRED_AUTHENTIC_MODALITY_OR_LINKAGE_UNCERTIFIED':row['hard_gates']['causal_preentry_availability']='UNKNOWN'
            row['semantic_certificate_status']=status;row['sigma_containment_verdict']=cert['sigma_containment_verdict'];row['HARD_ADMISSIBILITY_STATUS']=functional.admissibility(row['hard_gates'])
        selected=functional.select(rows,{})
        require(selected is None,'UNEXPECTED_COMPLETE_SELECTION')
    counts={status:sum(docs[cert_ref(s)]['formalization_status']==status for s in SOURCES) for status in ['EXACT_REDUNDANT_WITH_BASELINE','STRUCTURAL_NONREDUNDANCY_CERTIFIED','FORMALIZATION_UNRESOLVED','REQUIRED_AUTHENTIC_MODALITY_OR_LINKAGE_UNCERTIFIED']}
    return {'schema':'mxm.v4.strict-preoutcome-v2.semantic-functional-reapplication.v1','status':'REAPPLIED_UNCHANGED_FUNCTIONAL_SELECTION_UNRESOLVED','functional':{'ref':FUNCTIONAL,'sha256':HASHES[FUNCTIONAL]},'freeze_manifest':{'ref':FREEZE,'sha256':sha(raw[FREEZE])},'baseline_formalization_status':docs[BASELINE]['formalization_status'],'semantic_certificate_count':11,'certificate_status_counts':counts,'assessments':rows,'candidate_count':12,'admissible_count':sum(x['HARD_ADMISSIBILITY_STATUS']=='PASS' for x in rows),'exact_semantic_fail_count':sum(x['HARD_ADMISSIBILITY_STATUS']=='FAIL' for x in rows),'unknown_admissibility_count':sum(x['HARD_ADMISSIBILITY_STATUS']=='UNKNOWN' for x in rows),'selected_source':None,'selected_mechanism':None,'complete_information_design':False,'unknown_candidates_discarded':False,'comparison_evidence':'No new certified robust pairwise dominance; missing formalization is not evidence of inferiority.','historical_outcomes_used':False,'market_rows_used':0,'power_trials':0,'duration_selected':False,'next_action':NEXT}

def next_plan(base,result):
    return {'schema':'mxm.v4.strict-preoutcome-v2.next-minimum-structural-discriminator.v1','status':'FROZEN_NOT_EXECUTED_PENDING_INDEPENDENT_AUDIT','semantic_result_sha256':sha(canonical(result)),'EXACT_REMAINING_CANDIDATES':list(SOURCES),'EXACT_NEXT_BLOCKING_GATE':'IDENTIFIABLE_INCREMENTAL_CLAIM: shared B_t is not a uniquely defined mathematical map. This necessary gate is still open; do not skip to support acquisition.','EXACT_MISSING_STRUCTURAL_QUANTITY':{'shared_baseline_map_B_t':None,'unresolved_components':copy.deepcopy(BASELINE_AMBIGUITIES),'required_resolution':'A separately authorized prospective baseline-map specification resolving precisely these six projection/clock choices, with domain, units, readset, availability and missingness. A unique completion is not entailed by current prose.'},'WHY_IT_PRECEDES_DEEP_HISTORY':'No number of observations can choose an unspecified baseline projection or define its sigma-algebra. All eleven comparisons depend on the same baseline; changing it while comparing candidates would create selection leakage.','WHETHER_EXISTING_NEUTRAL_DATA_CAN_RESOLVE_IT':'NO: schema names and frozen prose admit multiple distinct maps. They can constrain a future specification, but cannot uniquely choose it. No new historical sample resolves this semantic absence.','WHETHER_MARKET_ROWS_WOULD_BE_REQUIRED':False,'WHETHER_BROKER_CONTACT_WOULD_BE_REQUIRED':False,'WHETHER_REDECRYPTION_WOULD_BE_REQUIRED':False,'MINIMUM_INFORMATION_NEEDED':{'shared_prospective_specification_records':1,'semantic_decision_entries':list(BASELINE_AMBIGUITIES),'authentic_market_rows':0,'historical_window':None,'new_candidate_formulas_requested_at_this_stage':0,'scope':'Only common B_t specification first; candidate-specific Phi ambiguities and absent authentic modalities remain explicitly downstream. Not a guaranteed unique selection.'},'COMPUTE_BOUND_IF_DERIVABLE':{'record_count':1,'component_decisions':6,'operation_bound':None,'reason':'Finite specification audit; algebraic complexity cannot be bounded before a formula is authorized. No Monte Carlo or empirical response.'},'STOP_RULE':['Do not execute or choose the six unresolved components in this task.','Do not silently relax, replace or reinterpret the accepted frozen baseline. If completion requires a new design choice, obtain separate prospective governance for a versioned specification.','Any authorized completion must be frozen globally before candidate-specific certificate construction or comparison, without outcome data and without broadening the baseline information beyond frozen semantics.','If no faithful authorized completion can be specified, stop FORMALIZATION_UNRESOLVED. Do not acquire bars, select a duration, or substitute an empirical return-based criterion.','After a separately audited complete B_t specification, reassess the next necessary Phi_i and modality-contract gaps; do not automatically execute them or promise a winner.'],'execution_in_this_task':False,'new_design_choices_made':False,'power_trials':0,'duration_selected':False,'next_action':NEXT}
