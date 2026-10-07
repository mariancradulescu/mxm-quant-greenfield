"""Isolated, zero-row certification against separately committed compact baseline."""
import copy
import hashlib
import json
from pathlib import Path
from research_core_v4.strict_reselection_v2 import io_firewall, canonical, require
from research_core_v4 import strict_selection_functional_v1 as f
from research_core_v4.strict_semantic_certification_v1 import SOURCES, FEATURE_GAPS, MODALITY
S=f.S
BASE=S+'STRICT_PREOUTCOME_V2_SHARED_OWN_INFORMATION_BASELINE_EXACT_SPECIFICATION_V2.json'
BASE_HASH='d57589c12af2a514903f3945c11bf87bd04ac70b880498806a75625f4095d2d1'
FREEZE_COMMIT='9254cd828b96bc1f31441010201bd7916d32560b'
PROTOCOL=S+'STRICT_PREOUTCOME_V2_COMPACT_CERTIFICATION_PROTOCOL_V2.json'
MANIFEST=S+'STRICT_PREOUTCOME_V2_COMPACT_CERTIFICATE_FREEZE_MANIFEST_V2.json'
RESULT=S+'STRICT_PREOUTCOME_V2_COMPACT_FUNCTIONAL_REAPPLICATION_V2.json'
BOUNDARY=S+'STRICT_PREOUTCOME_V2_COMPACT_SEMANTIC_BOUNDARY_V2.json'
AUTH=S+'STRICT_PREOUTCOME_V2_COMPACT_CLOSURE_AUTHORITY_V2.json'
NEXT='STRICT_PREOUTCOME_V2_COMPACT_BASELINE_CLOSED_CANDIDATE_FORMALIZATION_AND_AUTHENTIC_CONTRACT_BOUNDARY_PENDING_INDEPENDENT_AUDIT'
F_HASH='561e054658a4878008db10dbd6610408246756f5cabf7336a0c0b5088f4e1d2d'
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(s):return S+'STRICT_PREOUTCOME_V2_SEMANTIC_CERTIFICATE_'+s+'_V2.json'
def packet_ref(s):return S+'STRICT_PREOUTCOME_V2_ISOLATED_PACKET_'+s+'_V2.json'
def protocol():
 return {'schema':'mxm.v4.compact-semantic-protocol.v2','baseline_freeze_commit':FREEZE_COMMIT,'baseline_sha256':BASE_HASH,'functional_sha256':F_HASH,'candidate_changes_authorized':False,'stage_order':['freeze protocol before output','project one unchanged candidate and neutral modality flags per packet','isolated certificate construction from own packet and frozen baseline only','freeze all certificates','reapply byte-exact functional','audit remaining semantic underdetermination in isolation','materialize external and governance cut without choosing missing definitions'], 'candidate_builder_read_allowlist':'exact baseline plus own packet only','construction_peer_visibility':False,'historical_outcome_visibility':False,'external_gate':'Missing point-in-time modality/linkage cannot be authenticated by synthetic data','formalization_gate':'No unique Phi entailed by frozen prose: retain UNKNOWN, prove missing noninvertible choice without assigning either alternative','semantic_closure_scope':'Resolve all quantities uniquely entailed by accepted text and compact baseline; do not add a feature, window, operator, threshold or linkage','selection':'No pairwise economic/information preference manufactured from schema or synthetic witnesses','market_rows':0,'power_trials':0,'duration_selected':False}

def certificate(packet, baseline):
 c=packet['candidate'];s=c['information_source'];require(s in SOURCES,'SOURCE')
 require(sha(canonical(baseline))==BASE_HASH,'BASELINE_HASH')
 extra=s in MODALITY
 if extra:
  modality,flag=MODALITY[s];require(packet['modalities'][modality][flag] is False,'MODALITY_DRIFT')
 gaps=list(FEATURE_GAPS[s])
 if s=='BROKER_NATIVE_ACTIVITY_STATE':gaps=[gaps[0],'Compact baseline is now exact: activity level is retained; the unspecified distribution map remains unresolved.']
 if s=='REGIME_AND_STRUCTURAL_BREAK_STATE':gaps=[gaps[0],'Exact online/reference interval and distribution change functional remain unspecified; UTC baseline clock is now fixed.']
 return {'schema':'mxm.v4.isolated-semantic-certificate.v2','information_source':s,'candidate_definition_sha256':sha(canonical(c)),'baseline':{'ref':BASE,'sha256':BASE_HASH,'freeze_commit':FREEZE_COMMIT},'exact_feature_map_Phi_i':None,'sigma_containment_verdict':'UNRESOLVED_FEATURE_MAP_NOT_UNIQUELY_DEFINED','formalization_status':'REQUIRED_AUTHENTIC_MODALITY_OR_LINKAGE_UNCERTIFIED' if extra else 'FORMALIZATION_UNRESOLVED','constructive_nonredundancy_witness_or_redundancy_proof':None,'why_no_exact_witness':'A witness for one invented feature would not certify the frozen unresolved candidate. Compact B resolves only the shared baseline.','frozen_mechanism':c['materially_distinct_causal_mechanism'],'unchanged_definition':c,'resolved_shared_components':baseline['exact_B_t_information_vector'],'unresolved_candidate_quantities':gaps,'causal_timestamp_law':c['causal_timestamp_law'],'missingness_law':c['missingness_law'],'synchronization_requirement':c['synchronization_requirement'],'feature_specific_readset':None,'market_rows_used':0,'no_definition_change':True,'constructor_inputs':['own unchanged candidate','shared frozen baseline','neutral modality flags'],'peer_certificate_visibility':False}

def build_one(root,s,reads):
 own=packet_ref(s)
 with io_firewall(root,{BASE,own},reads):
  raw=(Path(root)/BASE).read_bytes();packet=json.loads((Path(root)/own).read_bytes())
 require(sha(raw)==BASE_HASH,'BASELINE_DRIFT')
 with io_firewall(root,set(),reads):return certificate(packet,json.loads(raw))

def derive_packets(root):
 reads=[]
 with io_firewall(root,{f.INPUT,f.PROPOSALS},reads):raw={p:(Path(root)/p).read_bytes() for p in [f.INPUT,f.PROPOSALS]}
 for p,h in f.BINDINGS.items():require(sha(raw[p])==h,'ACCEPTED_INPUT_DRIFT')
 d=json.loads(raw[f.INPUT]);candidates=json.loads(raw[f.PROPOSALS])['candidates'][1:]
 return {packet_ref(c['information_source']):{'candidate':c,'modalities':d['modalities']} for c in candidates},reads

def reapply(root,certs):
 reads=[]
 with io_firewall(root,{f.INPUT,f.PROPOSALS,f.FUNCTIONAL},reads):raw={p:(Path(root)/p).read_bytes() for p in [f.INPUT,f.PROPOSALS,f.FUNCTIONAL]}
 require(sha(raw[f.FUNCTIONAL])==F_HASH,'FUNCTIONAL_DRIFT')
 for p,h in f.BINDINGS.items():require(sha(raw[p])==h,'SOURCE_DRIFT')
 with io_firewall(root,set(),reads):
  a=f.assess(json.loads(raw[f.INPUT]),json.loads(raw[f.PROPOSALS]),json.loads(raw[f.FUNCTIONAL]));rows=copy.deepcopy(a['assessments'])
  for row in rows[1:]:
   cert=certs[ref(row['information_source'])];row['semantic_certificate_status']=cert['formalization_status'];row['baseline_sha256']=BASE_HASH
  selected=f.select(rows,{})
 require(selected is None,'UNEXPECTED_SELECTION')
 return {'schema':'mxm.v4.compact-functional-reapplication.v2','functional_sha256':F_HASH,'baseline_sha256':BASE_HASH,'assessments':rows,'selected_source':selected,'admissible_count':0,'exact_failed_count':1,'unknown_count':11,'unknown_remains_competitor':True,'pairwise_certificates':[],'complete_information_design':False,'market_rows_used':0,'power_trials':0,'duration_selected':False},reads

COUNTERCHOICES={
 'MULTISCALE_PRICE_STATE':{'unfixed':'Aggregation-state and agreement operator, plus disjoint interval anchor','alternatives':['agreement of signs of close-open','agreement of signs of close versus high-low midpoint'],'noninvertibility_example':{'OHLC':[5,10,0,6],'sign_close_minus_open':1,'sign_close_minus_midpoint':1,'alternative_OHLC':[7,10,0,6],'sign_close_minus_open_alternative':-1,'sign_close_minus_midpoint_alternative':1},'reason':'Each is a causal aggregation price state but induces different agreement partitions. Frozen text orders neither.'},
 'VOLATILITY_AND_REALIZED_VARIANCE_STATE':{'unfixed':'Variation increments, concentration operator, units and flat law','alternatives':['maximum squared-increment share','sum of squared squared-increment shares'],'noninvertibility_example':{'normalized_variation_weights_A':['1/2','1/2','0'],'normalized_variation_weights_B':['1/2','1/4','1/4'],'same_max':'1/2','different_sum_squares':['1/2','3/8']},'reason':'Both concentration summaries are scale invariant and causal; they generate different information sets. No choice is licensed.'},
 'BROKER_NATIVE_ACTIVITY_STATE':{'unfixed':'Ordered full counts, normalized distribution or a distributional summary','alternatives':['ordered normalized weights','unordered empirical count distribution'],'noninvertibility_example':{'counts_A':[1,3]+[2]*10,'counts_B':[3,1]+[2]*10,'same_compact_baseline_activity':[2,24],'same_unordered_distribution':True,'different_ordered_weights':True},'reason':'Compact baseline exclusion of a raw path does not define the candidate distribution. Identical B and different ordered path is not a witness for every permitted distribution summary.'},
 'REGIME_AND_STRUCTURAL_BREAK_STATE':{'unfixed':'Distribution domain, reference interval, change operator','alternatives':['change in empirical location mean','change in empirical location distribution'],'noninvertibility_example':{'locations_A':['0','1'],'locations_B':['1/2','1/2'],'equal_means':'1/2','different_distributions':True},'reason':'Both causal changes fit unspecified distribution change prose, but information differs; interval remains unfixed.'}}

def closure_one(cert):
 s=cert['information_source']
 if s in COUNTERCHOICES:return {'source':s,'status':'FORMALIZATION_UNRESOLVED_PROVED','exact_baseline_resolved':True,'no_candidate_assignment':True,'counterchoices_not_new_candidates':COUNTERCHOICES[s],'next_required_information':'Prospective exact candidate semantic authority, independent of candidate comparison and any outcomes. No amount of empirical data identifies intended operator.'}
 modality,flag=MODALITY[s]
 return {'source':s,'status':'TRUE_EXTERNAL_AUTHENTIC_CONTRACT_BOUNDARY','required_authentic_contract':modality+':'+flag,'accepted_contract_certified':False,'synthetic_authentication_forbidden':True,'also_unfixed':cert['unresolved_candidate_quantities'],'next_required_information':'Authoritative point-in-time modality/linkage contract; not historical response, names, current-only metadata or synthetic values.'}

def boundary(certs):
 with io_firewall('.',set(),[]):cuts=[closure_one(certs[ref(s)]) for s in SOURCES]
 return {'schema':'mxm.v4.compact-semantic-boundary.v2','status':'SAFE_ENTAILED_ZERO_OUTCOME_CLOSURE_EXHAUSTED_WITH_MIXED_GOVERNANCE_AND_EXTERNAL_CUT','baseline_closed':True,'candidate_count':11,'candidate_definition_changes':0,'cuts':cuts,'first_external_cut':'SESSION_AND_LIQUIDITY_STATE requires point-in-time authoritative session schedule, effective revision and timezone contract; not present in accepted neutral authority','ordering_is_not_candidate_ranking':True,'why_no_unique_selection':'Four own-M5 mechanisms have nonunique exact Phi definitions, seven require authentic external contracts; all remain UNKNOWN. There are no admissible candidates or 13-dimension dominance certificates.','governance_blocker_is_not_empirical':True,'required_final_stop_A_met':False,'required_final_stop_B_interpretation':'All closure uniquely entailed by frozen definitions is exhausted; authentic external cuts materialized. Four semantic choices also require governance, so do not mislabel them empirical or assert a complete design.','complete_information_design':False,'prepower_contract':None,'selected_source':None,'new_market_rows':0,'historical_response_values_used':0,'broker_contacts':0,'redecryptions':0,'empirical_support_measurements':0,'empirical_dependence_estimations':0,'power_trials':0,'duration_selected':False,'deep_acquisition':False,'new_economic_outcomes':0,'search_budget_use':0,'protected_forward_opened':False,'confirmation_opened':False,'next_action':NEXT}
