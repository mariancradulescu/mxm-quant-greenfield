"""Mechanical frozen-plan interpretation. No oracle/kernel execution or Y access.

Persist source and INTERPRETER_FREEZE_V1 before invocation. Certificate booleans
alone govern availability; rounded numeric strings only report diagnostics.
"""
from pathlib import Path
import json, hashlib, gzip, pickle, base64, io, argparse
from decimal import Decimal
import numpy as np
P=Path(__file__).resolve().parent; R=P.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def write(p,o):
 with p.open('x') as f: f.write(json.dumps(o,indent=2,sort_keys=True)+'\n')
def main(cache=None):
 out=P/'ACTUAL_NUMERICAL_SUPPORT_RAW_RESULT_V1.json'
 assert not out.exists(),'Support result already exists; refuse repeat execution'
 freeze=read(P/'INTERPRETER_FREEZE_V1.json'); integrity=read(P/'INTERRUPTED_SESSION_RECOVERY_INTEGRITY_V1.json')
 assert freeze['interpreter_sha256']==sha(Path(__file__))
 for f,s in freeze['input_bindings'].items(): assert sha(R/f)==s,f
 chunks=[]
 for x in integrity['parts']:
  b=(R/x['path']).read_bytes();assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256'];chunks.append(b)
 payload=b''.join(chunks)
 assert len(payload)==integrity['reconstructed_bytes'] and hashlib.sha256(payload).hexdigest()==integrity['reconstructed_sha256']
 if cache:
  assert sha(Path(cache))==integrity['cache_sha256']
  data=pickle.loads(Path(cache).read_bytes())
 else:
  raw=json.loads(gzip.decompress(payload));g=json.loads(gzip.decompress((P/'ACTUAL_CAUSAL_INPUT_GEOMETRY_V1.json.gz').read_bytes()))
  support=read(R/'research_core_v4/triad_v2/EXACT_SUPPORT_RAW_RESULT_V1.json')
  mb=base64.b64decode(support['actual_masks_npz_base64']);assert hashlib.sha256(mb).hexdigest()==integrity['mask_sha256']
  masks={k:v for k,v in np.load(io.BytesIO(mb),allow_pickle=False).items()}
  data=dict(raw=raw,geometry=g,support=support,masks=masks,design=read(R/'research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json'))
 raw=data['raw'];g=data['geometry'];masks=data['masks'];design=data['design'];support=data['support'];plan=read(P/'ACTUAL_PREDICTOR_SUPPORT_AUDIT_PLAN_V1.json')
 records={x['input_sha256']:x for x in raw['measurements']}
 assert len(records)==len(raw['measurements'])==raw['unique_geometries']
 assert len(raw['requested_to_exact_input_hash'])==len(g['geometries'])==55648
 certs=[records[k]['observed_certificate'] for k in raw['requested_to_exact_input_hash']]
 def hard(c): return not c['oracle_certified'] or c['unsafe_accept'] or not c['pass'] or bool(c['failures'])
 def usable(c):
  assert type(c['production_accept']) is bool and type(c['production_support']['accepted']) is bool
  assert c['production_accept']==c['production_support']['accepted']
  return c['production_support']['accepted'] and not hard(c)
 # Every requested occurrence counted; separate distinct-input accounting.
 def summary(rows):
  accepted=[c for c in rows if usable(c)]
  return {'geometries':len(rows),'oracle_uncertified':sum(not c['oracle_certified'] for c in rows),'unsafe_production_accepts':sum(c['unsafe_accept'] for c in rows),'hard_safety_failures':sum(hard(c) for c in rows),'oracle_mathematically_eligible':sum(c['oracle_certified'] and c['oracle_eligible'] for c in rows),'production_safe_accepted':len(accepted),'conservative_numerical_rejections':sum(c['conservative_rejection'] for c in rows),'threshold_ambiguities':sum(c['production_support']['threshold_ambiguous'] for c in rows),'maximum_accepted_normalized_RD_discrepancy_display_only':str(max((Decimal(c.get('normalized_RD_error','0')) for c in accepted),default=Decimal(0))),'maximum_accepted_backward_error_eta_display_only':max((c['production_support'].get('backward_error_eta',0) for c in accepted),default=0),'maximum_accepted_independent_orthogonality_display_only':max((c['production_support'].get('independent_orthogonality_error',0) for c in accepted),default=0)}
 availability=np.zeros((210,8,3),dtype=bool);groups={i:[] for i in range(len(g['full_clock_geometries']))};audit=[]
 for x,c,k in zip(g['geometries'],certs,raw['requested_to_exact_input_hash']):
  assert x['input_sha256']==k
  groups[x['full_index']].append((x,c))
 for fi,f in enumerate(g['full_clock_geometries']):
  rows=groups[fi];expected=[None]+design['universe']['cohort_target_ids'][design['universe']['cohorts'][f['cohort']]]
  assert [x['excluded_target'] for x,c in rows]==expected
  assert all(all(x[k]==f[k] for k in ['day','clock','cohort']) for x,c in rows)
  safe=all(usable(c) for x,c in rows);availability[f['day'],f['clock'],f['cohort']]=safe
  audit.append({'full_index':fi,'day':f['day'],'clock':f['clock'],'cohort':f['cohort'],'required_geometries':len(rows),'production_safe_geometries':sum(usable(c) for x,c in rows),'numerically_usable':safe})
 causal=masks['causal_cohort_clock'][90:];timestamp=masks['full_clock_horizon'][90:]
 assert causal.shape==(210,8,3) and timestamp.shape==(210,8,3,4)
 assert not (availability & ~causal).any()
 leaves=[]
 for ci,cohort in enumerate(design['universe']['cohorts']):
  for hi,horizon in enumerate(design['horizons_minutes']):
   complete=availability[:,:,ci]&timestamp[:,:,ci,hi]
   clocks_by_day=complete.sum(axis=1);days=clocks_by_day>=plan['daily_minimum_complete_clocks']
   blocks=[int(days[i:i+14].sum()) for i in range(0,210,14)]
   thirds=[int(days[i:i+70].sum()) for i in range(0,210,70)]
   supported=sum(v>=plan['minimum_days_per14day_block'] for v in blocks)
   failed=[]
   if supported<plan['minimum_supported_blocks_per_leaf']: failed.append('SUPPORTED_14DAY_BLOCKS')
   if any(v<plan['minimum_valid_days_each70day_third'] for v in thirds): failed.append('VALID_DAYS_EACH_70DAY_THIRD')
   inherited=next(x for x in support['leaf_support'] if x['cohort']==cohort and x['horizon_minutes']==horizon)
   leaves.append({'cohort':cohort,'horizon_minutes':horizon,'valid_complete_clocks':int(complete.sum()),'valid_days':int(days.sum()),'daily_complete_clock_counts':clocks_by_day.tolist(),'block_day_counts':blocks,'supported_blocks':supported,'third_day_counts':thirds,'pass':not failed,'failed_gates':failed,'inherited_minimum90day_matured_training_rows':inherited['minimum90day_matured_training_rows'],'inherited_maximum90day_matured_training_rows':inherited['maximum90day_matured_training_rows']})
 assert len(leaves)==plan['leaves']==12
 requested=summary(certs);unique=summary([r['observed_certificate'] for r in raw['measurements']])
 result={'schema':'TRIAD_V6_ACTUAL_NUMERICAL_SUPPORT_RAW_RESULT_V1','interpreter_sha256':freeze['interpreter_sha256'],'freeze_sha256':sha(P/'INTERPRETER_FREEZE_V1.json'),'integrity_record_sha256':sha(P/'INTERRUPTED_SESSION_RECOVERY_INTEGRITY_V1.json'),'input_bindings':freeze['input_bindings'],'raw_gzip_sha256':integrity['reconstructed_sha256'],'requested_accounting':requested,'unique_exact_input_accounting':unique,'full_cohort_geometries':len(g['full_clock_geometries']),'leaveout_geometries':g['leaveout_geometries'],'whole_cohort_clock_support':[{'cohort':c,'causal_cohort_clocks':int(causal[:,:,ci].sum()),'numerically_usable':int(availability[:,:,ci].sum()),'numerically_unavailable':int((causal[:,:,ci]&~availability[:,:,ci]).sum()),'original_calendar_clocks':1680} for ci,c in enumerate(design['universe']['cohorts'])],'whole_clock_audit':audit,'leaf_support':leaves,'all_actual_safety_certificates_pass':requested['hard_safety_failures']==0,'complete_12_leaf_support_pass':all(x['pass'] for x in leaves),'nuisance_law_and_inherited_support_unchanged':True,'rounded_diagnostics_used_for_decisions':False,'support_interpretation_execution_count':1,'final_classification':'PENDING_DURABLE_RAW_SUPPORT_RESULT','full_null_trials':0,'full_power_trials':0,'future_Y_reads':0,'future_real_signed_response_computations':0,'real_response_openings':0,'broker_contacts':0,'historical_requests':0,'new_acquisition':0,'candidate_frozen_count':0,'confirmation':'CLOSED','protected_forward':'CLOSED','orders':0,'trading':'NOT_STARTED'}
 write(out,result)
 print(json.dumps({k:result[k] for k in ['requested_accounting','unique_exact_input_accounting','whole_cohort_clock_support','all_actual_safety_certificates_pass','complete_12_leaf_support_pass']}))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--verified-parsed-cache');args=a.parse_args();main(args.verified_parsed_cache)
