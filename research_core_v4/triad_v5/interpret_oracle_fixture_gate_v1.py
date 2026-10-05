"""Interpret durable fixture raw under unchanged prospectively frozen V5 law."""
from pathlib import Path
import json,gzip,hashlib
from decimal import Decimal as D,localcontext
P=Path(__file__).resolve().parent
raw=json.loads(gzip.decompress((P/'ORACLE_FIXTURE_RAW_V1.json.gz').read_bytes()))
with localcontext() as ctx:
 ctx.prec=180
 rows=[]
 for f in raw['fixtures']:
  a=f['oracles']['100'];b=f['oracles']['160'];c=f['Jacobi'];r={'id':f['id'],'n':f['n'],'oracle100_status':a['status'],'oracle160_status':b['status'],'oracle_accept':b['accepted'],'Python_accept':f['historical_Python']['accepted'],'Jacobi_accept':c['accepted'],'candidate_output_bit_identical_to_V4':f['candidate_output_bit_identical_to_V4'],'failures':[]}
  r['oracle_stable']=False;r['ambiguity']=False;r['production_accept']=False;r['oracle_prospective_accept']=False
  if 'singular_values' not in a or 'singular_values' not in b:
   r['failures'].append('NUMERICAL_ORACLE_AMBIGUOUS')
  else:
   stability_s=max(abs(D(x)-D(y))/max(D(1),abs(D(y))) for x,y in zip(a['singular_values'],b['singular_values']))
   stability_rms=abs(D(a['residual_RMS'])-D(b['residual_RMS']))/max(D(1),abs(D(b['residual_RMS'])))
   stability_rd=max((abs(D(x)-D(y)) for x,y in zip(a['normalized'],b['normalized'])),default=D(0))
   r.update(oracle_singular_precision_difference=str(stability_s),oracle_RMS_precision_difference=str(stability_rms),oracle_normalized_precision_difference=str(stability_rd))
   stable=a['accepted']==b['accepted'] and a['rank']==b['rank'] and a['retained']==b['retained'] and stability_s<=D('1e-60') and stability_rms<=D('1e-60') and (not b['accepted'] or stability_rd<=D('1e-60'))
   r['oracle_stable']=stable
   if not stable:r['failures'].append('NUMERICAL_ORACLE_AMBIGUOUS')
   n=f['n'];u=D(2)**(-53);K=3*n+6+300*(6*n+32)+12*n+30;gamma=D(K)*u/(1-D(K)*u);delta=gamma*D(b['Z_Frobenius']);r.update(rounding_budget_K=K,spectral_error_radius=str(delta))
   ss=[D(x) for x in b['singular_values']];cs=[D.from_float(float(x)) for x in c['singular_values']]
   ambiguity=False
   for sv in [ss,cs]:
    ambiguity=ambiguity or any(abs(x-D('1e-12'))<=2*delta or abs(x-D('1e-12')*sv[0])<=2*(1+D('1e-12'))*delta for x in sv)
   gs=D(2*n+5)*u/(1-D(2*n+5)*u)
   ambiguity=ambiguity or any(abs(D(s)-D('1e-12'))<=2*gs*D(s) for s in b['scale'])
   r['ambiguity']=ambiguity;r['ambiguity_status']='NUMERICAL_SUPPORT_AMBIGUOUS_UNTESTED_NOT_NULL' if ambiguity else 'NONAMBIGUOUS'
   sigmaerr=max(abs(x-y) for x,y in zip(ss,cs));r['max_singular_value_discrepancy']=str(sigmaerr)
   r['singular_backward_budget_pass']=sigmaerr<=delta
   # Eligibility is mathematical support plus independently frozen numerical wrapper.
   r['oracle_prospective_accept']=bool(stable and b['accepted'] and not ambiguity)
   r['production_accept']=bool(c['accepted'] and not ambiguity)
   if not ambiguity and r['oracle_prospective_accept']!=r['production_accept']:r['failures'].append('NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH')
   if not ambiguity and sigmaerr>delta:r['failures'].append('SINGULAR_BACKWARD_ERROR_BOUND_FAILURE')
   if c['accepted'] and not ambiguity:
    cv=[D.from_float(float(x)) for x in c['normalized']];ov=[D(x) for x in b['normalized']]
    err=max(abs(x-y) for x,y in zip(cv,ov));r['production_oracle_normalized_RD_error']=str(err)
    rmserr=abs(D.from_float(float(c['rms']))-D(b['residual_RMS']));rmstol=D('1e-9')*max(D(b['residual_RMS']),D('1e-10'));r['RMS_abs_discrepancy']=str(rmserr);r['RMS_tolerance']=str(rmstol)
    # Independently reconstruct the candidate residual and mathematical RMS-normalized Z.
    x=[[D.from_float(float(v)) for v in row] for row in f['X']];z=[[row[j]/D(b['scale'][j]) for j in range(3)] for row in x]
    rd=[v*D.from_float(float(c['rms'])) for v in cv];orth=max(abs(sum((row[j]*rd[i] for i,row in enumerate(z)),D(0))) for j in range(3));dn=sum((D.from_float(float(v))**2 for v in f['D']),D(0)).sqrt();bound=D('1e-9')*max(D(1),dn);eta=orth/(D(b['Z_Frobenius'])*max(D(1),dn));r.update(reconstructed_orthogonality_error=str(orth),backward_error_eta=str(eta),orthogonality_gate_pass=orth<bound)
    if err>D('1e-7'):r['failures'].append('NORMALIZED_RD_ORACLE_ERROR')
    if rmserr>rmstol:r['failures'].append('RMS_ORACLE_ERROR')
    if not orth<bound:r['failures'].append('BINARY64_RELIABILITY_ORTHOGONALITY')
    if not b['accepted']:r['failures'].append('PRODUCTION_ACCEPTS_MATHEMATICAL_REJECTION')
  if not f['candidate_output_bit_identical_to_V4']:r['failures'].append('UNCHANGED_CANDIDATE_REEXECUTION_DIFFERENCE')
  r['pass']=not r['failures'];rows.append(r)
 summary={'schema':'TRIAD_V5_ORACLE_FIXTURE_GATE_INTERPRETATION_V1','raw_gzip_sha256':hashlib.sha256((P/'ORACLE_FIXTURE_RAW_V1.json.gz').read_bytes()).hexdigest(),'fixture_count':537,'oracle_precision_stable_count':sum(r['oracle_stable'] for r in rows),'oracle_precision_failure_count':sum(not r['oracle_stable'] for r in rows),'historical_Python_reject_oracle_accept_count':sum(not r['Python_accept'] and r['oracle_accept'] and r['oracle_stable'] for r in rows),'historical_Python_reject_nonambiguous_oracle_accept_count':sum(not r['Python_accept'] and r['oracle_prospective_accept'] for r in rows),'raw_Jacobi_oracle_eligibility_disagreement_count':sum(r['Jacobi_accept']!=r['oracle_accept'] for r in rows if r['oracle_stable']),'nonambiguous_production_oracle_eligibility_mismatch_count':sum(r['production_accept']!=r['oracle_prospective_accept'] for r in rows if not r['ambiguity'] and r['oracle_stable']),'ambiguity_rejection_count':sum(r['ambiguity'] for r in rows),'failed_fixtures':sum(not r['pass'] for r in rows),'maximum_production_oracle_normalized_RD_error':max((D(r.get('production_oracle_normalized_RD_error','0')) for r in rows),default=D(0)).to_eng_string(),'maximum_oracle100_vs160_singular_discrepancy':max((D(r.get('oracle_singular_precision_difference','0')) for r in rows),default=D(0)).to_eng_string(),'maximum_oracle100_vs160_normalized_RD_discrepancy_eligible':max((D(r.get('oracle_normalized_precision_difference','0')) for r in rows if r['oracle_accept']),default=D(0)).to_eng_string(),'all_pass':all(r['pass'] for r in rows),'actual_predictor_XD_audit_count':0,'actual_predictor_XD_mismatch_count':None,'actual_predictor_ambiguity_count':None,'complete_family_numerical_support':'NOT_RECOMPUTED_FIXTURE_GATE_PENDING_OR_BLOCKED','full_null_trials':0,'full_power_trials':0,'fixtures':rows}
 payload=(json.dumps(summary,indent=2,sort_keys=True)+'\n').encode();(P/'ORACLE_FIXTURE_INTERPRETATION_V1.json').write_bytes(payload);(P/'ORACLE_FIXTURE_INTERPRETATION_V1.json.gz').write_bytes(gzip.compress(payload,mtime=0));(P/'ORACLE_GATE_SUMMARY_V1.json').write_text(json.dumps({k:v for k,v in summary.items() if k!='fixtures'},indent=2,sort_keys=True)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k!='fixtures'}));print(json.dumps({'first_failures':[r for r in rows if not r['pass']][:5]}))
