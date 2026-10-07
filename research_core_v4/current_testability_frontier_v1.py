"""Isolated operational current-testability classification; no ranking or market IO."""
import hashlib,json
from pathlib import Path
from research_core_v4.strict_reselection_v2 import canonical,io_firewall,require
from research_core_v4 import exact_candidate_certification_v3 as prior
S=prior.S;BASE=prior.BASE;BASE_HASH=prior.BASE_HASH;F_HASH=prior.F_HASH
START='f261771cadef7d1f9b5225fd02e7eeb68c767a18'
GOVERNANCE_COMMIT='c99a8f602fc6d33f00e9514e0c37686bd788b2b0'
GOV=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_RESPONSE_AND_CROSS_SECTIONAL_GOVERNANCE_V1.json'
PROTOCOL=S+'STRICT_PREOUTCOME_V2_CURRENT_TESTABILITY_FRONTIER_PROTOCOL_V1.json'
FRONTIER=S+'STRICT_PREOUTCOME_V2_CURRENT_TESTABILITY_FRONTIER_V1.json'
AUTH=S+'STRICT_PREOUTCOME_V2_CURRENT_TESTABILITY_FRONTIER_AUTHORITY_V1.json'
SUPPORT=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_SUPPORT_DEPENDENCE_PROTOCOL_V1.json'
PREFLIGHT=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_SUPPORT_DEPENDENCE_PREFLIGHT_V1.json'
ROUTE=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_ACCEPTED_M5_ASSET_ROUTE_V1.json'
NEXT='STRICT_PREOUTCOME_V2_CURRENT_TESTABLE_WAVE_AND_PRE_SUPPORT_PROTOCOL_FROZEN_PENDING_INDEPENDENT_AUDIT_NO_SUPPORT_EXECUTION'
SOURCES=('UNIVARIATE_PRICE_STATE',*prior.SOURCES)
GATES=('EXACT_FEATURE_SEMANTICS_FROZEN','EXACT_RESPONSE_SEMANTICS_FROZEN','EXACT_CAUSAL_TIMESTAMP_LAW','EXACT_MISSINGNESS_LAW','REQUIRED_INFORMATION_MODALITY_ALREADY_ACCEPTED','NO_UNRESOLVED_EXTERNAL_IDENTITY_OR_LINKAGE_CONTRACT','SUPPORT_MEASUREMENT_POSSIBLE_WITHOUT_NEW_EXTERNAL_CONTRACT','NO_HISTORICAL_OUTCOME_DEPENDENCY')
PARK={
'SESSION_AND_LIQUIDITY_STATE':('PARKED_CURRENT_WAVE_AUTHENTIC_HISTORY_UNAVAILABLE','Current schedule/timezone/holiday fields do not supply accepted historical known-at revision authority'),
'TOP_OF_BOOK_QUOTE_STATE':('PARKED_CURRENT_WAVE_AUTHENTIC_SUPPORT_UNVERIFIED','Historical BID/ASK route exists; Pepperstone support and exact sequencing contract unverified'),
'FACTOR_OR_BASKET_RESIDUAL_STATE':('PARKED_CURRENT_WAVE_EXTERNAL_LINKAGE_AUTHORITY_MISSING','Current asset IDs do not specify accepted historical basket membership, weights or rebalancing'),
'CROSS_INSTRUMENT_RELATIONAL_STATE':('PARKED_CURRENT_WAVE_EXTERNAL_LINKAGE_AUTHORITY_MISSING','No accepted authentic exact nontriad economic relationship history'),
'CURVE_CASH_FORWARD_PERPETUAL_RELATIONSHIPS':('PARKED_CURRENT_WAVE_CONTRACT_SPECIFICATION_MISSING','Complete underlying/maturity/settlement contract specification route unidentified in accepted authority'),
'BROKER_NATIVE_CARRY_FINANCING_SWAP':('PARKED_CURRENT_WAVE_AUTHENTIC_HISTORY_UNAVAILABLE','Current swap protocol fields exist, accepted snapshot omits required values, historical publication authority missing')}
def sha(b):return hashlib.sha256(b).hexdigest()
def packet_ref(s):return S+'STRICT_PREOUTCOME_V2_TESTABILITY_OWN_PACKET_'+s+'_V1.json'
def status_ref(s):return S+'STRICT_PREOUTCOME_V2_TESTABILITY_OWN_STATUS_'+s+'_V1.json'
def classify(packet):
 require(set(packet)=={'information_source','own_candidate','own_feature_authority','own_response_authority','own_capability_facts','own_nonredundancy_certificate','shared_laws','freeze_bindings'},'PACKET_SCHEMA')
 s=packet['information_source'];require(s in SOURCES,'SOURCE')
 for key in ['own_candidate','own_capability_facts','own_nonredundancy_certificate']:
  if packet[key] is not None:require(packet[key]['information_source']==s,'PEER_INPUT_DENIED')
 require(packet['freeze_bindings']['governance_commit']==GOVERNANCE_COMMIT,'FREEZE_DRIFT')
 gates={k:False for k in GATES};gates['NO_HISTORICAL_OUTCOME_DEPENDENCY']=True
 if s=='UNIVARIATE_PRICE_STATE':
  status='EXACT_BASELINE_REDUNDANT_CURRENT_EXACT_PROPOSAL';reason='Preserve accepted exact baseline redundancy only; family not global null'
 elif s in PARK:
  status,reason=PARK[s];require(packet['own_capability_facts'] is not None,'CAPABILITY_MISSING')
 else:
  require(packet['own_feature_authority'] is not None and packet['own_response_authority'] is not None,'SEMANTICS_NOT_FROZEN')
  require(packet['shared_laws']['canonical_M5_accepted'] is True and packet['shared_laws']['accepted_support_route_exists'] is True,'MODALITY_MISSING')
  require(packet['own_nonredundancy_certificate']['formalization_status']=='STRUCTURAL_NONREDUNDANCY_CERTIFIED','NONREDUNDANCY_MISSING')
  gates={k:True for k in GATES};status='ELIGIBLE_CURRENT_WAVE_PRE_SUPPORT';reason='Exact causal semantics, accepted M5 modality and finite support-mask route; empirical masks unmeasured'
 return {'schema':'mxm.v4.current-testability.own-status.v1','information_source':s,'current_wave_status':status,'reason':reason,'eligibility_gates':gates,'baseline_sha256':BASE_HASH,'governance_commit':GOVERNANCE_COMMIT,'global_candidate_status':'EXACT_BASELINE_REDUNDANT_PROPOSAL_FAMILY_NOT_NULL' if s=='UNIVARIATE_PRICE_STATE' else 'UNKNOWN_GLOBAL_SCIENTIFIC_AND_ECONOMIC_STATUS','parked_is_null':False,'parked_is_negative_edge':False,'parked_is_permanent_exclusion':False,'ranking_or_edge_claim':False,'global_functional_reapplied':False,'historical_causal_availability_certified':False,'empirical_support_certified':False,'power_ready':False,'market_rows_read':0,'broker_requests':0,'support_execution':False,'constructor_comparative_inputs':[]}
def build_one(root,s,trace):
 own=packet_ref(s)
 with io_firewall(root,{BASE,own},trace):raw=(Path(root)/BASE).read_bytes();p=json.loads((Path(root)/own).read_bytes())
 require(sha(raw)==BASE_HASH,'BASELINE_DRIFT');require(p['information_source']==s,'PEER_PACKET')
 with io_firewall(root,set(),trace):return classify(p)
def assemble(statuses):
 require(set(statuses)==set(SOURCES),'GLOBAL_SOURCE_SET')
 wave=[s for s in SOURCES if statuses[s]['current_wave_status']=='ELIGIBLE_CURRENT_WAVE_PRE_SUPPORT']
 parked=[s for s in SOURCES if statuses[s]['current_wave_status'].startswith('PARKED_')]
 return {'schema':'mxm.v4.current-testability-frontier.v1','protocol_ref':PROTOCOL,'governance_ref':GOV,'global_source_count':12,'global_unknown_source_count':11,'exact_redundant_proposals':1,'current_wave':wave,'current_wave_count':len(wave),'parked_sources':parked,'parked_count':len(parked),'global_candidate_ledger_preserved':[{'information_source':s,'global_status':statuses[s]['global_candidate_status']} for s in SOURCES],'own_statuses':[{'ref':status_ref(s),'sha256':sha(canonical(statuses[s])),'input_packet_ref':packet_ref(s),'constructor_read_trace':[BASE,packet_ref(s)]} for s in SOURCES],'current_wave_is_global_selection':False,'selected_source':None,'global_functional_sha256':F_HASH,'global_functional_reapplied':False,'global_prior_assessments_modified':False,'current_wave_ranking':None,'market_rows_read':0,'support_execution':False,'power_trials':0,'duration_selected':False,'next_action':NEXT}
