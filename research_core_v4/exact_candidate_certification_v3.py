"""Own-packet-only constructors and unchanged prospective functional reapplication."""
import copy,json,hashlib
from pathlib import Path
from research_core_v4.strict_reselection_v2 import canonical,io_firewall,require
from research_core_v4 import strict_selection_functional_v1 as f
from research_core_v4 import compact_semantic_closure_v2 as old
from research_core_v4.prospective_exact_semantics_v3 import synthetic_witness
S=f.S;BASE=old.BASE;BASE_HASH=old.BASE_HASH;F_HASH=old.F_HASH;SOURCES=old.SOURCES
SEMANTIC_COMMIT='68f1227704cc607520dc25250c08bd6c6620d96a'
PROTOCOL_COMMIT='8de0976936de47e3816c426107e9579eb7dbf51e'
SEM=S+'STRICT_PREOUTCOME_V2_PROSPECTIVE_EXACT_SEMANTIC_AUTHORITIES_V3.json'
AUDIT=S+'STRICT_PREOUTCOME_V2_EXTERNAL_CONTRACT_CAPABILITY_AUDIT_V3.json'
PROTOCOL=S+'STRICT_PREOUTCOME_V2_EXACT_CERTIFICATION_PROTOCOL_V3.json'
MANIFEST=S+'STRICT_PREOUTCOME_V2_EXACT_CERTIFICATE_FREEZE_MANIFEST_V3.json'
RESULT=S+'STRICT_PREOUTCOME_V2_EXACT_FUNCTIONAL_REAPPLICATION_V3.json'
BOUNDARY=S+'STRICT_PREOUTCOME_V2_CONSOLIDATED_NONMARKET_BOUNDARY_PLAN_V3.json'
AUTH=S+'STRICT_PREOUTCOME_V2_EXACT_CLOSURE_AUTHORITY_V3.json'
NEXT='STRICT_PREOUTCOME_V2_EXACT_FEATURES_CERTIFIED_NONMARKET_CAPABILITY_AUDITED_MIXED_RESPONSE_GOVERNANCE_AND_AUTHENTIC_SUPPORT_BOUNDARY_PENDING_INDEPENDENT_AUDIT'
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(s):return S+'STRICT_PREOUTCOME_V2_SEMANTIC_CERTIFICATE_'+s+'_V3.json'
def packet_ref(s):return S+'STRICT_PREOUTCOME_V2_ISOLATED_PACKET_'+s+'_V3.json'
def certificate(packet,base):
    require(set(packet)=={'candidate','exact_semantic_authority','own_capability_fact','freeze_bindings'},'OWN_PACKET_SCHEMA')
    require(sha(canonical(base))==BASE_HASH,'BASELINE_HASH');c=packet['candidate'];s=c['information_source']
    require(s in SOURCES,'SOURCE');sem=packet['exact_semantic_authority'];fact=packet['own_capability_fact']
    if fact is not None:require(fact['information_source']==s,'PEER_CAPABILITY_DENIED')
    require((sem is None)==(fact is not None),'OWN_AUTHORITY_KIND')
    out={'schema':'mxm.v4.isolated-semantic-certificate.v3','information_source':s,'candidate_definition_sha256':sha(canonical(c)),'unchanged_definition':c,'baseline':{'ref':BASE,'sha256':BASE_HASH,'freeze_commit':old.FREEZE_COMMIT},'own_semantic_authority':sem,'own_certified_contract_facts':fact,'freeze_bindings':packet['freeze_bindings'],'exact_feature_map_Phi_i':None if sem is None else sem['Phi'],'sigma_containment_verdict':'UNKNOWN' if sem is None else 'NOT_CONTAINED_ON_LEGAL_STRUCTURAL_DOMAIN','formalization_status':'REQUIRED_AUTHENTIC_MODALITY_OR_LINKAGE_UNCERTIFIED' if sem is None else 'STRUCTURAL_NONREDUNDANCY_CERTIFIED','constructive_nonredundancy_witness_or_redundancy_proof':None,'response_function_unchanged':c['response_function'],'response_semantic_integrity':'EXTERNAL_EXACT_FEATURE_OR_RESPONSE_SEMANTICS_STILL_UNSPECIFIED' if sem is None else 'COMPATIBLE_PRICE_ADJUSTMENT','response_governance_blocker':None,'structural_contract':None,'remaining_required_facts':[],'constructor_peer_visibility':False,'constructor_comparative_visibility':False,'historical_outcome_files_read':0,'market_rows_used':0,'power_trials':0,'duration_selected':False}
    if sem is None:
        out['remaining_required_facts']=[fact['exact_required_contract'],*fact['semantic_fields_still_unspecified']]
        out['historical_support_authenticated']=False
        return out
    require(sem['mechanism'].rstrip('.')==c['materially_distinct_causal_mechanism'].rstrip('.'),'MECHANISM_DRIFT')
    out['constructive_nonredundancy_witness_or_redundancy_proof']=synthetic_witness(s)
    if s in ('VOLATILITY_AND_REALIZED_VARIANCE_STATE','REGIME_AND_STRUCTURAL_BREAK_STATE'):
        target='next-hour variation' if s.startswith('VOLATILITY') else 'subsequent state persistence'
        out['response_semantic_integrity']='PROSPECTIVE_RESPONSE_GOVERNANCE_REQUIRED'
        out['response_governance_blocker']={'mechanism_target':target,'frozen_response':c['response_function'],'conflict':'Signed future log price displacement is not a defined variation or state-persistence response. No outcome-free algebra uniquely identifies the intended response.','response_modified':False,'minimum_information':'Prospective independent response governance before response construction, support sampling or power; no comparative feedback'}
    features={'MULTISCALE_PRICE_STATE':{'intervals':['[h-75m,h-60m)','[h-60m,h)'],'required_M5_count':15,'computation':'15 OHLC reductions, 2 locations, 2 signs, one multiplication; O(15)'},'VOLATILITY_AND_REALIZED_VARIANCE_STATE':{'intervals':['[h-60m,h)'],'required_M5_count':12,'computation':'12 real logs and squares, two sums, 12 normalized squares; O(12); production real-log numerical certification remains separate'},'BROKER_NATIVE_ACTIVITY_STATE':{'intervals':['[h-60m,h)'],'required_M5_count':12,'computation':'12-count sum and 11 exact rational divisions; O(12)'},'REGIME_AND_STRUCTURAL_BREAK_STATE':{'intervals':['[h-120m,h-60m)','[h-60m,h)'],'required_M5_count':24,'computation':'24 locations, sort two 12-vectors, 12 absolute differences; O(24 log 12)'}}
    out['structural_contract']={'anchor':'h=floor(t/3600)*3600; t integer UTC seconds on M5 grid','feature_readset':features[s],'baseline_readset':'exact immutable B: immediate completed hour plus last completed M5 at [t-5m,t)','feature_availability':'Every input completed; original authentic available_at<=t; no revisions backdated','feature_missingness':'Any required missing, duplicated, invalid OHLC, nonfinite value, late availability or invalid nonnegative count => FEATURE_UNAVAILABLE; no fallback/imputation','response_horizon_family_M5':c['compact_horizon_family']['m5_bars'],'response_values_opened':False,'response_missingness':'Exclude incomplete response window; record mask/reason without interpreting missingness as null','overlap_law':'Two observations dependent whenever their required feature, baseline or prospective response identity-time readsets intersect; shared calendar/context dependence not eliminated by disjoint local intervals','dependence_unit':'Shared calendar-time blocks across identities and contexts as frozen; block partition/length not silently chosen','cohort':'All 1575 accepted eligible identities within each of the 29 frozen broker contexts; no outcome/support based subset','multiplicity':'Joint candidate/context/horizon selection remains unpaid; exact inferential estimator/control family not supplied by a semantic certificate','confirmation':'Genuinely disjoint authentic confirmation remains closed; no existing development rows can certify it','unmeasured':['authentic joint feature/response support mask','empirical dependence geometry','historical side-aware friction','calendar/provenance disjoint confirmation bounds','auditable complete economic test burden'],'no_duration_selection':True}
    out['remaining_required_facts']=out['structural_contract']['unmeasured']+(['prospective response governance'] if out['response_governance_blocker'] else [])
    return out

def build_one(root,s,reads):
    own=packet_ref(s)
    with io_firewall(root,{BASE,own},reads):
        b=(Path(root)/BASE).read_bytes();p=json.loads((Path(root)/own).read_bytes())
    require(sha(b)==BASE_HASH,'BASELINE_DRIFT');require(p['candidate']['information_source']==s,'PEER_PACKET_DENIED')
    with io_firewall(root,set(),reads):return certificate(p,json.loads(b))
def reapply(root,reads):
    allowed={f.INPUT,f.PROPOSALS,f.FUNCTIONAL,MANIFEST,*[ref(s) for s in SOURCES]}
    with io_firewall(root,allowed,reads):raw={p:(Path(root)/p).read_bytes() for p in sorted(allowed)}
    require(sha(raw[f.FUNCTIONAL])==F_HASH,'FUNCTIONAL_DRIFT')
    for p,h in f.BINDINGS.items():require(sha(raw[p])==h,'ACCEPTED_INPUT_DRIFT')
    m=json.loads(raw[MANIFEST]);require(len(m['certificates'])==11,'MANIFEST_COUNT')
    for x in m['certificates']:require(sha(raw[x['ref']])==x['sha256'],'CERTIFICATE_DRIFT')
    with io_firewall(root,set(),reads):
        rows=copy.deepcopy(f.assess(json.loads(raw[f.INPUT]),json.loads(raw[f.PROPOSALS]),json.loads(raw[f.FUNCTIONAL]))['assessments'])
        for row in rows[1:]:
            cert=json.loads(raw[ref(row['information_source'])]);require(cert['baseline']['sha256']==BASE_HASH,'BASELINE_CERT_DRIFT')
            require(cert['candidate_definition_sha256']==row['frozen_mechanism_sha256'],'CANDIDATE_DRIFT')
            row['hard_gates']['identifiable_incremental_claim']='PASS' if cert['formalization_status']=='STRUCTURAL_NONREDUNDANCY_CERTIFIED' else 'UNKNOWN'
            row['semantic_certificate_status']=cert['formalization_status'];row['sigma_containment_verdict']=cert['sigma_containment_verdict'];row['response_semantic_integrity']=cert['response_semantic_integrity'];row['baseline_sha256']=BASE_HASH
            row['HARD_ADMISSIBILITY_STATUS']=f.admissibility(row['hard_gates'])
            row['CAUSAL_IDENTIFIABILITY_STATUS']='DOMAIN_NONREDUNDANCY_PROVED_NOT_PREDICTIVE_INFORMATION' if cert['formalization_status']=='STRUCTURAL_NONREDUNDANCY_CERTIFIED' else 'UNKNOWN_AUTHENTIC_CONTRACT_OR_SEMANTICS'
            row['dimensions']['INCREMENTAL_INFORMATION_DISTINCTNESS']=row['CAUSAL_IDENTIFIABILITY_STATUS']
            row['EXACT_UNRESOLVED_STRUCTURAL_QUANTITIES']=cert['remaining_required_facts']
        selected=f.select(rows,{})
    return {'schema':'mxm.v4.exact-functional-reapplication.v3','functional_sha256':F_HASH,'baseline_sha256':BASE_HASH,'manifest_sha256':sha(raw[MANIFEST]),'assessments':rows,'selected_source':selected,'complete_information_design':False,'admissible_count':sum(r['HARD_ADMISSIBILITY_STATUS']=='PASS' for r in rows),'exact_failed_count':sum(r['HARD_ADMISSIBILITY_STATUS']=='FAIL' for r in rows),'unknown_count':sum(r['HARD_ADMISSIBILITY_STATUS']=='UNKNOWN' for r in rows),'nonredundancy_certified_count':4,'unknown_remains_competitor':True,'pairwise_certificates':[],'market_rows_used':0,'power_trials':0,'duration_selected':False,'input_read_trace':reads}
