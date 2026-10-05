"""Timestamp-only support and disjoint-prefix feature/control fitting.
Never computes any real future signed response. Development price cells are
not converted or stored. No broker/network APIs are imported.
"""
import pathlib,json,hashlib,csv,datetime,math,sys,base64,io
import numpy as np
R=pathlib.Path('.');B=R/'research_core_v4/triad_v1';ROOT=pathlib.Path(sys.argv[1])
def read(p):return json.loads((R/p).read_bytes())
def h(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def minute(s):return int(datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()/60)
d=read(str(B/'EXACT_TRIAD_MECHANISM_DESIGN_V1.json'));inv=read(d['inventory_ref']);ledger=read(d['recovery_ledger_ref']);assert h(d['inventory_ref'])==d['inventory_sha256'] and ledger['all75_recovered'];rels=inv['complete_relations'];cohorts=d['cohorts'];start=minute(d['window']['development_start_utc']);ps=minute(d['window']['prefix_start_utc']);pe=minute(d['window']['prefix_end_exclusive_utc']);hours=d['causal_clock']['decision_UTC_hours'];horizons=d['horizons_minutes']
# Hash allfiles BEFORE parsing any cells; exact expected native byte hash.
for x in ledger['series']:assert hashlib.sha256((ROOT/(str(x['symbol_id'])+'_M5.csv')).read_bytes()).hexdigest()==x['series_sha256']
ts={};prefixprices={};meta=[];converted=0
for x in ledger['series']:
 sid=x['symbol_id'];times=[];prices={}
 with (ROOT/(str(sid)+'_M5.csv')).open(newline='') as f:
  for row in csv.DictReader(f):
   t=minute(row['time_utc']);times.append(t)
   # Only strict disjointPREFIX prices become floats; development values ignored.
   if ps<=t<pe:
    v=float(row['close']);assert math.isfinite(v) and v>0;prices[t]=math.log(v);converted+=1
 assert len(times)==x['row_count'] and times==sorted(set(times));assert times[0]==minute(x['first_timestamp_utc']) and times[-1]==minute(x['last_timestamp_utc']);ts[sid]=set(times);prefixprices[sid]=prices;meta.append({'symbol_id':sid,'timestamps_verified':len(times),'prefix_price_rows_only':len(prices)})
def weekday(t):return datetime.datetime.fromtimestamp(t*60,datetime.timezone.utc).weekday()<5
prefix_clocks=[day+hh*60 for day in range(ps,pe,1440) if weekday(day) for hh in hours]
# Exact realprefix C(q)-C(q-60), controls of the samepast-only ownleg.
fits=[];prefixfail=[]
for rr in rels:
 sid=rr['target_symbol_id'];sg=rr['target_canonical_sign'];XX=[];ff=[];own=[]
 for t in prefix_clocks:
  q=t-10;needed=[q,q-5,q-60]
  if not all(all(z in prefixprices[e['symbol_id']] for z in needed) for e in rr['closure_terms']):continue
  C=lambda z:sum(e['coefficient']*prefixprices[e['symbol_id']][z] for e in rr['closure_terms'])
  v1=sg*(prefixprices[sid][q]-prefixprices[sid][q-5]);v12=sg*(prefixprices[sid][q]-prefixprices[sid][q-60]);hh=(t%1440)//60;XX.append([1,v1,v12]+[int(hh==k) for k in hours[1:]]);ff.append(C(q)-C(q-60));own.append(v12)
 X=np.asarray(XX,dtype=float);F=np.asarray(ff);n=len(F);rank=int(np.linalg.matrix_rank(X)) if n else 0
 beta=np.linalg.pinv(X,rcond=1e-12)@F if n else np.zeros(10);res=F-X@beta if n else np.array([]);rms=float(np.sqrt(np.mean(res*res))) if n else 0;ownrms=float(np.sqrt(np.mean(np.asarray(own)**2))) if n else 0
 ok=n>=240 and rank==10 and rms>=1e-10 and ownrms>=1e-10
 fits.append({'relation_id':rr['relation_id'],'cohort':rr['cohort'],'complete_prefix_clocks':n,'design_rank':rank,'beta':beta.tolist(),'residual_RMS':rms,'ownleg60min_RMS':ownrms,'pass':ok})
 if not ok:prefixfail.append(rr['relation_id'])
# Mask encodes timestamps ONLY. Future endpoint prices are NEVER touched.
mask=np.zeros((210,8,len(rels),4),dtype=bool)
for day in range(210):
 t0=start+day*1440
 if not weekday(t0):continue
 for k,hh in enumerate(hours):
  t=t0+hh*60;q=t-10
  for ri,rr in enumerate(rels):
   causal=all(all(z in ts[e['symbol_id']] for z in [q,q-5,q-60]) for e in rr['closure_terms'])
   if not causal:continue
   sid=rr['target_symbol_id']
   for hi,hor in enumerate(horizons):mask[day,k,ri,hi]=all(z in ts[sid] for z in range(t-5,t+hor,5))
clock=np.zeros((210,8,3,4),bool);daily=np.zeros((210,3,4),bool);leaf=[]
for ci,c in enumerate(cohorts):
 ii=[i for i,x in enumerate(rels) if x['cohort']==c];targets=sorted(set(rels[i]['target_symbol_id'] for i in ii));rmin=math.ceil(.5*len(ii));tmin=max(3,math.ceil(.5*len(targets)))
 for day in range(210):
  for k in range(8):
   for hi in range(4):
    available=[i for i in ii if mask[day,k,i,hi]];at={rels[i]['target_symbol_id'] for i in available};clock[day,k,ci,hi]=len(available)>=rmin and len(at)>=tmin
 daily[:,ci,:]=clock[:,:,ci,:].sum(axis=1)>=4
 for hi,hor in enumerate(horizons):
  valid=daily[:,ci,hi];bc=[int(valid[a:a+14].sum()) for a in range(0,210,14)];blocks=sum(v>=7 for v in bc);thirds=[int(valid[a:a+70].sum()) for a in range(0,210,70)];passed=blocks>=12 and min(thirds)>=42
  leaf.append({'cohort':c,'horizon_minutes':hor,'eligible_decision_clocks':int(clock[:,:,ci,hi].sum()),'valid_days':int(valid.sum()),'block_valid_day_counts':bc,'supported_blocks':blocks,'fixed70day_third_counts':thirds,'calendar_days':210,'pass':passed,'unavailable_clock_or_weekend_count':int(210*8-clock[:,:,ci,hi].sum())})
buf=io.BytesIO();np.savez_compressed(buf,relation_clock_horizon=mask,cohort_clock_horizon=clock,cohort_daily_horizon=daily);payload=buf.getvalue();out={'schema':'mxm.v4.triad.exact-support-prefix-result.v1','design_sha256':h(str(B/'EXACT_TRIAD_MECHANISM_DESIGN_V1.json')),'implementation_sha256':h(str(B/'support_prefix_v1.py')),'inventory_sha256':h(d['inventory_ref']),'verified_series':75,'series_timestamp_integrity':meta,'prefix_price_rows_converted':converted,'development_price_rows_converted':0,'future_signed_response_computations':0,'real_response_openings':0,'broker_contacts':0,'historical_requests':0,'prefix_fits':fits,'prefix_failures':prefixfail,'leaf_support':leaf,'all_prefix_pass':not prefixfail,'complete_family_support_pass':all(x['pass'] for x in leaf),'all_support_preconditions_pass':not prefixfail and all(x['pass'] for x in leaf),'original_calendar_retained':True,'imputation':None,'no_cohort_or_horizon_removed':True,'actual_mask_npz_sha256':hashlib.sha256(payload).hexdigest(),'actual_mask_npz_base64':base64.b64encode(payload).decode(),'mask_shape':[210,8,107,4],'unobserved_price_latency':'No authentic historical receptiontimestamps; conservativeM5closeplus5min assumed availability law, not executionproof.'}
(B/'EXACT_SUPPORT_PREFIX_RAW_RESULT_V1.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['all_prefix_pass','prefix_failures','complete_family_support_pass','all_support_preconditions_pass','development_price_rows_converted','future_signed_response_computations']}));print(json.dumps(leaf))
