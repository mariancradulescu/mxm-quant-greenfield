"""Exact V2 causal-membership/full-clock timestamp geometry, no price parsing.
Requires committed semantic PASS. No alpha, coefficient or signedreturn read.
"""
import pathlib,json,csv,hashlib,datetime,base64,io
import numpy as np
R=pathlib.Path('.');B='research_core_v4/triad_v2/';V1='research_core_v4/triad_v1/';ROOT=pathlib.Path('/workspace/scratch/26645457fe1a/fx-verified-series')
def read(p):return json.loads((R/p).read_bytes())
def h(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def minute(s):return int(datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()/60)
p=read(B+'EXACT_SUPPORT_CERTIFICATION_PLAN_V1.json');d=read(p['design_ref']);a=read(p['semantic_ref']);assert a['all648_analytic_nulls_pass'] and h(p['semantic_ref'])==p['semantic_sha256'];assert h(p['implementation_ref'])==p['implementation_sha256'];assert h(p['design_ref'])==p['design_sha256']
i=read(V1+'CANONICAL_FX_RELATION_COHORT_INVENTORY_V1.json');l=read(V1+'ACCEPTED_FX_ARCHIVE_RECOVERY_LEDGER_V1.json');rels=i['complete_relations'];cohorts=d['universe']['cohorts'];hh=d['horizons_minutes'];targets=d['universe']['cohort_target_ids']
ts={}
for x in l['series']:
 f=ROOT/(str(x['symbol_id'])+'_M5.csv');assert hashlib.sha256(f.read_bytes()).hexdigest()==x['series_sha256']
 with f.open(newline='') as fp:aa=[minute(z['time_utc']) for z in csv.DictReader(fp)]
 assert len(aa)==x['row_count'] and aa==sorted(set(aa));ts[x['symbol_id']]=set(aa)
ps=minute(d['window']['prefix_start_utc']);dev=minute(d['window']['development_start_utc']);end=dev+210*1440
# Include90dayprefix for exact g initial/update availability, alltimestamp-only.
causal=np.zeros((300,8,107),bool);complete=np.zeros((300,8,3,4),bool);causal_cohort=np.zeros((300,8,3),bool);n_targets=np.zeros((300,8,3),np.int16);n_training_targets=np.zeros((300,8,3,4),np.int16);all_missing={c:{str(h):0 for h in hh} for c in cohorts}
for day in range(300):
 t0=ps+day*1440
 if datetime.datetime.fromtimestamp(t0*60,datetime.timezone.utc).weekday()>=5:continue
 for k,hour in enumerate(range(8,16)):
  t=t0+hour*60;q=t-10
  for ri,rr in enumerate(rels):causal[day,k,ri]=all(all(z in ts[e['symbol_id']] for z in [q,q-5,q-60]) for e in rr['closure_terms'])
  for ci,c in enumerate(cohorts):
   ids=[ri for ri,r in enumerate(rels) if r['cohort']==c and causal[day,k,ri]];active=sorted({rels[ri]['target_symbol_id'] for ri in ids});n_targets[day,k,ci]=len(active)
   valid=len(ids)>=int(np.ceil(.5*d['universe']['cohort_relation_counts'][c])) and len(active)>=max(5,int(np.ceil(.5*len(targets[c]))));causal_cohort[day,k,ci]=valid
   if not valid:continue
   for hi,hor in enumerate(hh):
    # FitcurrentQmembership has already been fixed bypasttimestamps ONLY.
    # No future-selected survivor set is allowed to replace it.
    missing=[sid for sid in active if not all(z in ts[sid] for z in range(t-5,t+hor,5))]
    complete[day,k,ci,hi]=not missing
    if not missing:n_training_targets[day,k,ci,hi]=len(active)
    elif day>=90:all_missing[c][str(hor)]+=1
mask=complete[90:];daily=mask.sum(axis=1)>=4;rows=[]
for ci,c in enumerate(cohorts):
 for hi,hor in enumerate(hh):
  valid=daily[:,ci,hi];counts=[int(valid[k:k+14].sum()) for k in range(0,210,14)];blocks=sum(n>=7 for n in counts);thirds=[int(valid[k:k+70].sum()) for k in range(0,210,70)]
  updates=[]
  for day in range(90,300):
   T=ps+day*1440;total=0
   for prior in range(max(0,day-90),day):
    for k,hour in enumerate(range(8,16)):
     t=ps+prior*1440+hour*60
     # Timestamp availability: labelclose/horizonend plus5minbuffer, then240purge.
     if t+hor+5+240<T:total+=int(n_training_targets[prior,k,ci,hi])
   updates.append(total)
  passed=blocks>=12 and min(thirds)>=42 and min(updates)>=240
  rows.append({'cohort':c,'horizon_minutes':hor,'valid_complete_clocks':int(mask[:,:,ci,hi].sum()),'valid_days':int(valid.sum()),'calendar_days':210,'block_day_counts':counts,'supported_blocks':blocks,'third_day_counts':thirds,'minimum90day_matured_training_rows':min(updates),'maximum90day_matured_training_rows':max(updates),'whole_clocks_discarded_for_any_future_target_gap':all_missing[c][str(hor)],'pass':passed,'failed_gates':([] if blocks>=12 else ['MIN12_SUPPORTED_BLOCKS'])+([] if min(thirds)>=42 else ['MIN42_DAYS_EACH_THIRD'])+([] if min(updates)>=240 else ['MIN240_MATURED_TRAINING_ROWS'])})
buf=io.BytesIO();np.savez_compressed(buf,causal_relation_membership=causal,causal_cohort_clock=causal_cohort,causal_target_count=n_targets,full_clock_horizon=complete,cohort_daily_horizon=daily,matured_training_target_count=n_training_targets);payload=buf.getvalue()
out={'schema':'mxm.v4.triad-v2.exact-support-raw.v1','plan_sha256':h(B+'EXACT_SUPPORT_CERTIFICATION_PLAN_V1.json'),'design_sha256':p['design_sha256'],'implementation_sha256':p['implementation_sha256'],'semantic_sha256':p['semantic_sha256'],'accepted75_content_hashes_reverified':True,'all107_relations_retained':True,'all12_leaves_declared':True,'cohort_membership_changed':False,'prefix_and_dev_calendar_days':300,'causal_target_membership_uses_no_futureavailability':True,'no_future_selected_subset_refit':True,'fullclockmask_original_calendar_retained':True,'leaf_support':rows,'all_exact_timestamp_support_gates_pass':all(x['pass'] for x in rows),'actual_masks_npz_sha256':hashlib.sha256(payload).hexdigest(),'actual_masks_npz_base64':base64.b64encode(payload).decode(),'numerical_current_X_rank_and_D_variance_status':'No realdevelopmentpredictor coefficient/scorerun; rank/variance stillrequire failclosedexactsyntheticandfuturecausalchecks, neverguaranteedbytimestamponly.','real_price_fields_parsed':0,'real_Y_or_relational_scores_computed':0,'future_real_signed_response_computations':0,'real_response_openings':0,'broker_contacts':0,'historical_requests':0,'interpretation_present':False}
(R/(B+'EXACT_SUPPORT_RAW_RESULT_V1.json')).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'all_exact_timestamp_support_gates_pass':out['all_exact_timestamp_support_gates_pass'],'leaf_support':rows}))
