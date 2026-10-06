"""Resume the completed raw-series pass; bounded contiguous context writes.
The causal feature law is byte-equivalent to data.build's per-column loop.
No economic outcomes are interpreted or selected here.
"""
import io,json,mmap,zipfile
from pathlib import Path
import numpy as np,pandas as pd
from .data import ROOT,START,END,INNER_END,HASHES,sha,save,metadata,verify_zip

def finish(data_dir,cache):
 manifest=json.loads((ROOT/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());records=sorted(manifest['primary_series'],key=lambda s:s['symbol_id']);loc,md=metadata();contexts=sorted({md[s['symbol_id']]['asset_class'] for s in records})
 a=np.load(cache/'X.npy',mmap_mode='r+');sig=np.load(cache/'sigma.npy',mmap_mode='r');bars=np.load(cache/'ohlcv.npy',mmap_mode='r');labels=np.load(cache/'Y.npy',mmap_mode='r');T,n,d=a.shape
 assert n==145 and all(np.isfinite(sig[:,i]).sum()>0 for i in range(n))
 assert all(np.isfinite(labels[:,i,:]).sum()>0 for i in range(n))
 groups=[[i for i,s in enumerate(records) if md[s['symbol_id']]['asset_class']==ctx] for ctx in contexts]
 compared=0;partial_before=0;first16_hash=__import__('hashlib').sha256();first16_after=__import__('hashlib').sha256()
 for begin in range(0,T,2048):
  end=min(begin+2048,T);x=np.array(a[begin:end]);first16_hash.update(x[:,:,:16].tobytes());old=x[:,:,16:].copy();r1=x[:,:,10]
  for si in groups:
   f=r1[:,si];valid=np.isfinite(f);count=valid.sum(axis=1);totalr=np.nansum(f,axis=1)
   for i in si:
    own=r1[:,i];num=count-np.isfinite(own);peer=(totalr-np.nan_to_num(own))/np.maximum(num,1);peer[num<2]=np.nan
    x[:,i,16]=np.nan_to_num(peer);x[:,i,17]=np.where(np.isfinite(peer),np.clip(own-peer,-4,4),0);x[:,i,18]=(num>=2).astype(float)
  present=np.isfinite(old);partial_before+=int(present.sum());assert np.array_equal(old[present],x[:,:,16:][present]),f'partial context parity {begin}'
  compared+=int(present.sum());a[begin:end]=x;first16_after.update(x[:,:,:16].tobytes())
  a.flush();a._mmap.madvise(mmap.MADV_DONTNEED)
 assert first16_hash.hexdigest()==first16_after.hexdigest()
 save('CONTEXT_WRITE_LAYOUT_PARITY_V1.json',{'status':'PASS','completed_raw_feature_values_preserved':True,'primary_16_feature_hash':first16_hash.hexdigest(),'previously_computed_context_values_compared':compared,'numeric_domain':'IEEE754_DOUBLE','equality':'EXACT_ARRAY_EQUAL_NO_TOLERANCE','scientific_law_changed':False,'raw_series_pass_recomputed':False})
 # Reverify authority from raw archive/member bytes without repeating features.
 archives={HASHES[name]:verify_zip(data_dir/name) for name in list(HASHES)[:2]};rows=[];total=0
 for i,s in enumerate(records):
  raw=archives[s['source_archive_sha256']].read(s['file']);assert sha(raw)==s['series_sha256'];df=pd.read_csv(io.BytesIO(raw));ts=pd.to_datetime(df.time_utc,utc=True);ns=ts.astype('int64').to_numpy()
  assert len(df)==s['row_count'] and ts.is_monotonic_increasing and not ts.duplicated().any() and np.all(ns%300_000_000_000==0)
  assert ts.min()>=START and ts.max()<END
  ix=((ns-START.value)//300_000_000_000).astype(int);v=df[['open','high','low','close','tick_volume']].to_numpy(float)
  assert np.array_equal(v,np.asarray(bars[ix,i])),s['symbol'];assert np.isfinite(v).all() and (v[:,:4]>0).all() and (v[:,4]>=0).all()
  assert (v[:,1]>=v[:,[0,2,3]].max(axis=1)-1e-10).all() and (v[:,2]<=v[:,[0,1,3]].min(axis=1)+1e-10).all()
  c=np.asarray(bars[:,i,3]);jump=abs(np.r_[np.nan,np.diff(np.log(c))]);threshold=np.maximum(.05,12*np.roll(sig[:,i],1));bad=jump>threshold
  total+=len(df);rows.append({**s,'verified_rows':len(df),'discontinuity_events':int(bad.sum()),'discontinuity_event_indices':np.flatnonzero(bad).tolist(),'context':md[s['symbol_id']]['asset_class']})
 assert total==11406418
 costs={}
 for name in list(HASHES)[2:]:
  z=verify_zip(data_dir/name)
  for fn in z.namelist():
   if not fn.startswith('derived/') or not fn.endswith('.jsonl.gz'):continue
   for line in __import__('gzip').decompress(z.read(fn)).splitlines():
    j=json.loads(line);d=costs.setdefault(j['symbol'],[])
    for row in j['rows']:
     if row['boundary_ms']>=INNER_END.value//1_000_000:continue
     for key in ('d0s','d1s','d5s','d30s'):
      q=row[key]
      if q.get('fresh') and q.get('spread_bps') is not None and q['spread_bps']>=0:d.append(q['spread_bps'])
 cost_inventory=[]
 for s in records:
  vals=costs.get(s['symbol'],[]);cost_inventory.append({'symbol':s['symbol'],'prefix_fresh_sample_count':len(vals),'spread_bound_bps':2*max(vals) if len(vals)>=10 else None,'state':'PREFIX_SAMPLE_MAX_X2_DISCOVERY_BOUND_NOT_HISTORICAL_TRUTH' if len(vals)>=10 else 'COST_UNRESOLVED'})
 info={'records':records,'metadata':[md[s['symbol_id']] for s in records],'assets':{x['assetId']:x['name'] for x in loc['asset_metadata']},'contexts':contexts,'costs':cost_inventory,'T':T,'inner_end_index':91*288,'outer_end_index':T,'source_archive_hashes':HASHES}
 (cache/'info.json').write_text(json.dumps(info))
 save('PRIMARY145_DATA_INTEGRITY_RESULT.json',{'status':'PASS_RAW_BYTES_VERIFIED','series_count':n,'total_m5_rows':total,'archive_hashes':{k:v for k,v in HASHES.items() if 'M5_' in k},'series':rows,'protected_forward_opened':False,'supplementary_primary_inference':False})
 save('REUSABLE_DATA_AND_FRICTION_INVENTORY_V1.json',{'costs':cost_inventory,'cost_admissible_symbols':sum(c['spread_bound_bps'] is not None for c in cost_inventory),'source_hashes':HASHES,'prefix_only':True,'supplementary_count':len(manifest['supplementary_original_series']),'late_join':'MATERIALIZED_33_NEW_COHORT_INVENTORIED;NOT_FRESH_TEMPORAL_EVIDENCE','present_metadata':'DISCOVERY_SCENARIO_ONLY_NOT_EXACT_HISTORICAL_AUTHORITY'})
 print('RAW_INTEGRITY_COMPLETE',total,'cost_supported',sum(c['spread_bound_bps'] is not None for c in cost_inventory),flush=True)
if __name__=='__main__':finish(ROOT.parent/'data',ROOT.parent/'cache')
