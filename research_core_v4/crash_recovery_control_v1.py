from __future__ import annotations
import hashlib,json
from pathlib import Path
try:
 from research_core_v4 import development_execution_runner_v1 as R
except ModuleNotFoundError:
 import development_execution_runner_v1 as R
ROOT=Path(__file__).resolve().parents[1]
S='research_core_v4/state/'
P={
 'state':S+'V4_STATE.json','orig_auth':S+'FIRST_V4_DEVELOPMENT_RESPONSE_EXECUTION_AUTHORITY_V3.json',
 'rec_auth':S+'FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V1.json',
 'intr':S+'FIRST_V4_DEVELOPMENT_RESPONSE_OPENING_INTERRUPTION_V1.json','orig_lock':S+'FIRST_V4_DEVELOPMENT_RESPONSE_OPENING_LOCK_V1.txt',
 'rec_lock':S+'FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_LOCK_V1.txt','ready':S+'FIRST_V4_DEVELOPMENT_RESPONSE_PREINTERRUPTION_STATE_V1.json',
 'attempt':S+'FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_ATTEMPT_V1.json','failure':S+'FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_FAILURE_V1.json',
 'completion':S+'FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_COMPLETION_V1.json','result':S+'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json',
 'interpretation':S+'FIRST_V4_DEVELOPMENT_RESPONSE_INTERPRETATION_V1.json'}
READY='FIRST_REAL_MARKET_DESIGN_V2_AUTHORITY_V3_CRASH_RECOVERY_AUTHORIZED_LOCKED_NOT_EXECUTED'
ATTEMPT='FIRST_REAL_MARKET_DESIGN_V2_AUTHORITY_V3_CRASH_RECOVERY_ATTEMPT_STARTED_NO_CANONICAL_RESULT'
RAW='FIRST_REAL_MARKET_DESIGN_V2_AUTHORITY_V3_CRASH_RECOVERY_RAW_RESULT_PERSISTED_NOT_INTERPRETED'
FINAL0='FIRST_REAL_MARKET_DESIGN_V2_DEVELOPMENT_RECOVERED_INTERPRETED_NO_CONTEXT_PASSES_EXACT_SPEC_CLOSED'
FINALL='FIRST_REAL_MARKET_DESIGN_V2_DEVELOPMENT_RECOVERED_INTERPRETED_DEVELOPMENT_LEAD_ONLY'
FAIL='FIRST_REAL_MARKET_DESIGN_V2_CRASH_RECOVERY_SECOND_INFRASTRUCTURE_FAILURE_STOPPED'
def j(k): return json.loads((ROOT/P[k]).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def eq(n,a,b):
 if a!=b: raise PermissionError(f'CRASH_RECOVERY_CONTROL_FAIL {n}: {a!r} != {b!r}')
def must(c,m):
 if not c: raise PermissionError('CRASH_RECOVERY_CONTROL_FAIL '+m)
def exists(k): return (ROOT/P[k]).exists()
def result_like():
 out={str(x.relative_to(ROOT)) for x in (ROOT/S).glob('*FIRST_V4*DEVELOPMENT*RESULT*') if x.is_file()}
 out|={str(x.relative_to(ROOT)) for x in ROOT.glob('V4_FIRST_DEVELOPMENT_RESPONSE_RESULT*') if x.is_file()}
 return out
def validate_current_control_plane():
 o=j('orig_auth'); a=j('rec_auth'); s=j('state'); f=s['first_wave']; g=s['governance']; b=o['bindings']; fs=a['frozen_scientific_computation']
 eq('original Authority V3 sha',sha(ROOT/P['orig_auth']),a['original_authority']['sha256'])
 eq('Authority V3 sha frozen','2bf73c2492833463fa942c78c62126db0edc85e0763e468039eaa905390f48bc',a['original_authority']['sha256'])
 eq('original interruption sha',sha(ROOT/P['intr']),a['original_interruption']['sha256'])
 eq('original lock sha',sha(ROOT/P['orig_lock']),a['historical_original_opening_lock']['sha256'])
 eq('original lock content',(ROOT/P['orig_lock']).read_text(),a['original_authority']['sha256']+'\n')
 intr=j('intr'); op=intr['opening']; og=intr['outcome_governance']
 must(op['started'] and op['durable_o_excl_lock_created_before_response_read'],'original opening/lock evidence invalid')
 must(not op['process_completed'] and not op['canonical_raw_result_written'] and op['canonical_raw_result_sha256'] is None,'interruption contains a result')
 must(not op['evaluator_rerun_performed'] and not op['lock_deleted_or_bypassed'],'original attempt was rerun or lock bypassed')
 for k in ('human_interpretation_performed','frozen_gate_interpretation_performed','confirmation_availability_preflight_run','confirmation_response_opened','broker_acquisition_run','quote_revision_v2_run','protected_forward_opened','candidate_promotion_performed','live_trading_started'): must(not og[k],'interruption downstream invariant '+k)
 # Keep the original READY gate fully alive on an immutable pre-interruption snapshot.
 hist=j('ready'); eq('historical READY status',hist['status'],'FIRST_REAL_MARKET_DESIGN_V2_AUTHORITY_V3_READY_NOT_EXECUTED')
 eq('historical READY binding',R.state_binding_sha256(hist),b['canonical_state_binding_sha256'])
 R.verify_static_bindings(o,hist,R.load_json(ROOT/R.DESIGN_REL),R.load_json(ROOT/R.MANIFEST_REL),R.load_json(ROOT/R.SUPPORT_REL))
 expected={'scientific_design_sha256':b['canonical_design_content_sha256'],'evaluator_sha256':b['evaluator_content_sha256'],'runner_sha256':b['execution_runner_content_sha256'],'shared_semantics_sha256':b['shared_semantics_content_sha256'],'primary_manifest_sha256':b['canonical_primary_manifest_content_sha256'],'support_v2_audit_sha256':b['support_audit_content_sha256'],'support_skeleton_sha256':b['support_skeleton_sha256'],'support_skeleton_row_count':b['support_skeleton_row_count'],'calibration_v3_result_sha256':b['exact_geometry_calibration_content_sha256'],'calibration_v3_full_sha256':b['exact_geometry_calibration_full_content_sha256'],'seed':20261002,'permutations':1023,'contexts':o['development_scope']['contexts'],'volatility_states':o['development_scope']['volatility_states'],'response_horizons_m5':o['development_scope']['response_horizons_m5'],'estimand':o['development_scope']['estimand'],'development_series':b['development_series'],'accepted_source_archives':{'original_archive_sha256':b['original_archive_sha256'],'delta_archive_sha256':b['delta_archive_sha256']}}
 for k,v in expected.items(): eq('frozen '+k,fs[k],v)
 for ref,h in ((fs['scientific_design_ref'],fs['scientific_design_sha256']),(fs['evaluator_ref'],fs['evaluator_sha256']),(fs['runner_ref'],fs['runner_sha256']),(fs['shared_semantics_ref'],fs['shared_semantics_sha256']),(fs['primary_manifest_ref'],fs['primary_manifest_sha256']),(fs['support_v2_ref'],fs['support_v2_audit_sha256']),(fs['calibration_v3_result_ref'],fs['calibration_v3_result_sha256']),(fs['calibration_v3_full_ref'],fs['calibration_v3_full_sha256'])): eq('file '+ref,sha(ROOT/ref),h)
 cp=a['recovery_control_plane']; eq('allowed attempts',cp['allowed_attempts'],1)
 for k in ('new_hypothesis_authorized','parameter_change_authorized','context_change_authorized','symbol_change_authorized','horizon_change_authorized','volatility_state_change_authorized','estimand_change_authorized','selection_law_change_authorized','multiplicity_change_authorized','diagnostic_selection_change_authorized'): must(not cp[k],'forbidden change '+k)
 ash=sha(ROOT/P['rec_auth']); eq('recovery lock',(ROOT/P['rec_lock']).read_text(),ash+'\n')
 must(f['development_outcomes_opened'] and not f['evaluator_execution_authorized'],'interrupted/opened fail-closed state lost')
 must(f['original_opening_lock_preserved'] and f['original_interruption_record_preserved'],'history not preserved')
 must(f['deterministic_crash_recovery_authorized'] and f['deterministic_crash_recovery_attempt_limit']==1,'recovery authority state invalid')
 must(not f['confirmation_execution_authorized'] and not f['confirmation_outcomes_opened'] and not f['new_market_acquisition_started'],'downstream first-wave opened')
 must(not g['broker_acquisition_authorized'] and not g['quote_revision_v2_execution_authorized'] and not g['protected_forward_opened'] and not g['candidate_promotion_authorized'] and not g['live_trading_started'] and g['candidate_frozen_count']==0,'downstream governance opened')
 phase=s['status']; rl=result_like(); ce=exists('result'); ae=exists('attempt'); fe=exists('failure'); co=exists('completion'); ie=exists('interpretation')
 if phase==READY:
  eq('ready state sha',sha(ROOT/P['state']),cp['ready_state_sha256']); eq('attempts started',f['deterministic_crash_recovery_attempts_started'],0); eq('attempts completed',f['deterministic_crash_recovery_attempts_completed'],0); must(not any((ae,fe,co,ie,ce)) and not rl,'unexpected result/attempt record before recovery'); must(not f['development_raw_result_persisted'] and not f['development_result_interpreted'],'premature result flags')
 elif phase==ATTEMPT:
  eq('attempts started',f['deterministic_crash_recovery_attempts_started'],1); eq('attempts completed',f['deterministic_crash_recovery_attempts_completed'],0); must(ae and not any((fe,co,ie,ce)) and not rl,'attempt phase file invariant'); x=j('attempt'); eq('attempt authority',x['recovery_authority_sha256'],ash); eq('attempt number',x['attempt_number'],1); eq('attempt source head',x['original_execution_source_head'],a['original_execution_source_head'])
 elif phase==RAW:
  eq('attempts started',f['deterministic_crash_recovery_attempts_started'],1); eq('attempts completed',f['deterministic_crash_recovery_attempts_completed'],1); must(ae and ce and co and not fe and not ie,'raw phase file invariant'); eq('only canonical result',rl,{P['result']}); must(f['development_raw_result_persisted'] and not f['development_result_interpreted'],'raw phase state flags'); x=j('completion'); eq('completion authority',x['recovery_authority_sha256'],ash); eq('completion raw sha',x['canonical_raw_result_sha256'],sha(ROOT/P['result']))
 elif phase in (FINAL0,FINALL):
  eq('attempts started',f['deterministic_crash_recovery_attempts_started'],1); eq('attempts completed',f['deterministic_crash_recovery_attempts_completed'],1); must(ae and ce and co and ie and not fe,'final phase file invariant'); eq('only canonical result',rl,{P['result']}); must(f['development_raw_result_persisted'] and f['development_result_interpreted'],'final state flags'); x=j('interpretation'); eq('interpretation authority',x['recovery_authority_sha256'],ash); eq('interpretation raw sha',x['canonical_raw_result_sha256'],sha(ROOT/P['result'])); must((phase==FINAL0 and x['development_lead_count']==0 and x['classification']=='NO_CONTEXT_PASSES_CLOSE_ONLY_EXACT_TESTED_V4_SPECIFICATION') or (phase==FINALL and x['development_lead_count']>=1 and x['classification']=='DEVELOPMENT_LEAD_ONLY'),'final classification mismatch')
 elif phase==FAIL:
  eq('attempts started',f['deterministic_crash_recovery_attempts_started'],1); eq('attempts completed',f['deterministic_crash_recovery_attempts_completed'],0); must(ae and fe and not any((ce,co,ie)) and not rl,'failure phase invariant'); must(not f['development_raw_result_persisted'] and not f['development_result_interpreted'],'failure state result flags')
 else: raise PermissionError('CRASH_RECOVERY_CONTROL_FAIL unsupported phase '+repr(phase))
 return {'status':'PASS','phase':phase,'original_authority_sha256':a['original_authority']['sha256'],'recovery_authority_sha256':ash,'original_interruption_sha256':a['original_interruption']['sha256'],'historical_original_opening_lock_sha256':a['historical_original_opening_lock']['sha256'],'allowed_attempts':1,'scientific_design_changed':False,'evaluator_changed':False,'runner_changed':False,'seed':20261002,'permutations':1023}
if __name__=='__main__': print(json.dumps(validate_current_control_plane(),sort_keys=True))
