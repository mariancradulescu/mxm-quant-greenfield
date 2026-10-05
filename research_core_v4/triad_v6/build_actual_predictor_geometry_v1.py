"""Causal X/D only; timestamp masks preexist. No future price/Y/response access."""
from pathlib import Path
import json,hashlib,base64,io,csv,datetime,math,gzip
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[1];DATA=Path('/workspace/scratch/26645457fe1a/fx-verified-series')
def read(path):return json.loads((R/path).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def minute(s):return int(datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()//60)
def input_hash(X,D):return hashlib.sha256(np.asarray(X,dtype='<f8').tobytes()+np.asarray(D,dtype='<f8').tobytes()).hexdigest()
def build():
 design=read('research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json');ledger=read('research_core_v4/triad_v1/ACCEPTED_FX_ARCHIVE_RECOVERY_LEDGER_V1.json');inv=read('research_core_v4/triad_v1/CANONICAL_FX_RELATION_COHORT_INVENTORY_V1.json');prefix=read('research_core_v4/triad_v1/EXACT_SUPPORT_PREFIX_RAW_RESULT_V1.json');support=read('research_core_v4/triad_v2/EXACT_SUPPORT_RAW_RESULT_V1.json')
 maskbytes=base64.b64decode(support['actual_masks_npz_base64']);assert hashlib.sha256(maskbytes).hexdigest()==support['actual_masks_npz_sha256'];masks=np.load(io.BytesIO(maskbytes),allow_pickle=False)
 start=minute(design['window']['development_start_utc']);hours=design['causal_clock']['decision_UTC_hours'];coh=design['universe']['cohorts'];rels=inv['complete_relations'];fits={f['relation_id']:f for f in prefix['prefix_fits']};sg={a['symbol_id']:a['canonical_sign'] for a in inv['identities']};scales={t:float(np.median([fits[r['relation_id']]['ownleg60min_RMS'] for r in rels if r['target_symbol_id']==t])) for c in coh for t in design['universe']['cohort_target_ids'][c]}
 required=set()
 for day in range(210):
  for k,h in enumerate(hours):
   if masks['causal_cohort_clock'][90+day,k].any():
    q=start+day*1440+h*60-10;required.update([q,q-5,q-60])
 # Bytes hash first; CLOSE conversion restricted to precisely the scheduled past-feature labels.
 prices={};hashes={};converted=0
 for series in ledger['series']:
  sid=series['symbol_id'];f=DATA/f'{sid}_M5.csv';digest=sha(f);assert digest==series['series_sha256'];hashes[str(sid)]=digest;out={}
  with f.open(newline='') as fp:
   for row in csv.DictReader(fp):
    t=minute(row['time_utc'])
    if t in required:
     value=float(row['close']);assert math.isfinite(value) and value>0;out[t]=math.log(value);converted+=1
  prices[sid]=out
 geometries=[];full=[];lines=[]
 for day in range(210):
  for k,h in enumerate(hours):
   q=start+day*1440+h*60-10
   for ci,c in enumerate(coh):
    if not masks['causal_cohort_clock'][90+day,k,ci]:continue
    active_rel=[rr for ri,rr in enumerate(rels) if rr['cohort']==c and masks['causal_relation_membership'][90+day,k,ri]];targets=sorted({rr['target_symbol_id'] for rr in active_rel});x=[];d=[]
    for sid in targets:
     x.append([1.,sg[sid]*(prices[sid][q]-prices[sid][q-5])/scales[sid],sg[sid]*(prices[sid][q]-prices[sid][q-60])/scales[sid]])
     values=[]
     for rr in active_rel:
      if rr['target_symbol_id']!=sid:continue
      for term in rr['closure_terms']:assert all(z in prices[term['symbol_id']] for z in [q,q-5,q-60])
      cq=sum(term['coefficient']*prices[term['symbol_id']][q] for term in rr['closure_terms']);cq60=sum(term['coefficient']*prices[term['symbol_id']][q-60] for term in rr['closure_terms']);values.append(float(np.clip((cq-cq60)/fits[rr['relation_id']]['residual_RMS'],-3.,3.)))
     d.append(float(np.mean(values)))
    X=np.asarray(x,dtype=float);D=np.asarray(d,dtype=float);fi=len(full);full.append({'day':day,'clock':k,'cohort':ci,'targets':targets,'X':X.tolist(),'D':D.tolist(),'input_sha256':input_hash(X,D),'relation_membership':[rr['relation_id'] for rr in active_rel]})
    choices=[None]+design['universe']['cohort_target_ids'][c]
    for excluded in choices:
     keep=[i for i,t in enumerate(targets) if t!=excluded];A=X[keep];v=D[keep];record={'index':len(geometries),'full_index':fi,'day':day,'clock':k,'cohort':ci,'excluded_target':excluded,'n':len(A),'input_sha256':input_hash(A,v)};geometries.append(record);lines.append(str(len(A)));lines.extend(' '.join(format(float(z),'.17g') for z in [*A[i],v[i]]) for i in range(len(A)))
 raw={'schema':'TRIAD_V6_ACTUAL_CAUSAL_INPUT_GEOMETRY_V1','archive_series_hashes':hashes,'all75_bytes_verified':len(hashes)==75,'full_clock_geometries':full,'geometries':geometries,'total_geometries':len(geometries),'full_cohort_geometries':len(full),'leaveout_geometries':len(geometries)-len(full),'causal_price_cells_converted':converted,'future_Y_computed':0,'full_clock_timestamp_mask_sha256':support['actual_masks_npz_sha256'],'support_plan_sha256':sha(P/'ACTUAL_PREDICTOR_SUPPORT_AUDIT_PLAN_V1.json')}
 (P/'ACTUAL_CAUSAL_INPUT_GEOMETRY_V1.json.gz').write_bytes(gzip.compress((json.dumps(raw,separators=(',',':'),sort_keys=True)+'\n').encode(),mtime=0));(P/'actual_predictor_kernel_input.tmp').write_text('\n'.join(lines)+'\n');return raw,masks,design
if __name__=='__main__':
 r,_,_=build();print(json.dumps({k:r[k] for k in ['total_geometries','full_cohort_geometries','leaveout_geometries','all75_bytes_verified','causal_price_cells_converted','future_Y_computed']}),flush=True)
