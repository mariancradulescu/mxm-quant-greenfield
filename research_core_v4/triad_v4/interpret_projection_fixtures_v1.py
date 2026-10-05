from pathlib import Path
import gzip,json,hashlib,numpy as np
P=Path(__file__).resolve().parent;raw=json.loads(gzip.decompress((P/'PROJECTION_FIXTURE_RAW_V1.json.gz').read_bytes()));s=json.loads((P/'NUMERICAL_KERNEL_SPEC_V1.json').read_text());rows=[]
for fixture in raw['fixtures']:
 c=fixture['canonical'];o=fixture['cpp'];a=c['accepted'];b=o['accepted'];r={'id':fixture['id'],'n':fixture['n'],'canonical_accepted':a,'cpp_accepted':b,'cpp_status':o['status'],'eligibility_match':a==b,'cpp_orthogonality_error':o['orthogonality_error'],'cpp_singular_values':o['singular_values'],'canonical_singular_values':fixture['scaled_singular_values'],'failures':[]}
 if a!=b:r['failures'].append('ELIGIBILITY_MISMATCH')
 if a and b:
  r['max_normalized_RD_discrepancy']=float(np.max(np.abs(np.array(c['normalized'])-o['normalized'])))
  r['RMS_abs_discrepancy']=abs(c['rms']-o['rms']);r['RMS_tolerance']=1e-9*max(c['rms'],1e-10)
  if r['max_normalized_RD_discrepancy']>1e-7:r['failures'].append('NORMALIZED_RD_DISCREPANCY')
  if r['RMS_abs_discrepancy']>r['RMS_tolerance']:r['failures'].append('RESIDUAL_RMS_DISCREPANCY')
  r['orthogonality_gate']=bool(o['orthogonality_error']<1e-9*max(1,np.linalg.norm(fixture['D'])))
  if not r['orthogonality_gate']:r['failures'].append('ORTHOGONALITY_GATE')
 if 'historical_frozen_expected' in fixture:
  h=fixture['historical_frozen_expected'];r['historical_canonical_acceptance_unchanged']=h['canonical_accepted']==a
  if h['canonical_accepted'] and a:r['historical_reference_max_RD_difference']=float(np.max(np.abs(np.array(h['canonical_normalized'])-c['normalized'])))
  if not r['historical_canonical_acceptance_unchanged'] or r.get('historical_reference_max_RD_difference',0)>1e-7:r['failures'].append('HISTORICAL_REFERENCE_CHANGED')
 r['pass']=not r['failures'];rows.append(r)
result={'schema':'TRIAD_V4_PROJECTION_EQUIVALENCE_INTERPRETATION_V1','raw_gzip_sha256':hashlib.sha256((P/'PROJECTION_FIXTURE_RAW_V1.json.gz').read_bytes()).hexdigest(),'raw_uncompressed_sha256':hashlib.sha256(gzip.decompress((P/'PROJECTION_FIXTURE_RAW_V1.json.gz').read_bytes())).hexdigest(),'projection_kernel_sha256':raw['projection_kernel_sha256'],'fixture_count':len(rows),'historical_fixture_count':24,'adversarial_fixture_count':len(rows)-24,'historical_pass_count':sum(r['pass'] for r in rows[:24]),'adversarial_pass_count':sum(r['pass'] for r in rows[24:]),'eligibility_mismatch_count':sum(not r['eligibility_match'] for r in rows),'failure_count':sum(not r['pass'] for r in rows),'maximum_normalized_RD_discrepancy_both_accepted':max((r.get('max_normalized_RD_discrepancy',0) for r in rows),default=0),'maximum_CPP_orthogonality_error_all_fixtures':max(r['cpp_orthogonality_error'] for r in rows),'maximum_CPP_orthogonality_error_accepted':max((r['cpp_orthogonality_error'] for r in rows if r['cpp_accepted']),default=0),'all_pass':all(r['pass'] for r in rows),'fixtures':rows,'actual_predictor_audit_count':0,'actual_predictor_audit_status':'NOT_AUTHORIZED_UNLESS_COMPLETE_FIXTURE_GATE_PASSES','actual_predictor_eligibility_mismatch_count':None,'actual_predictor_maximum_normalized_RD_discrepancy':None,'full_null_trials':0,'full_power_trials':0,'real_response_openings':0,'kernel_modified_after_execution':False}
(P/'PROJECTION_EQUIVALENCE_INTERPRETATION_V1.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='fixtures'}));print(json.dumps({'first_failures':[r for r in rows if not r['pass']][:8]}))
