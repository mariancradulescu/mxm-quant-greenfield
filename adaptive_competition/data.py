from __future__ import annotations
import base64, gzip, hashlib, io, json, zipfile, zlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'adaptive_competition/state'
START=pd.Timestamp('2025-09-16T00:00:00Z')
INNER_END=START+pd.Timedelta(days=91)
END=pd.Timestamp('2026-09-17T00:00:00Z')
HORIZONS=(3,6,12,48)
HASHES={
'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip':'09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259',
'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip':'37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e',
'MXM_V3_GLOBAL_FRICTION_TRIAGE_EVIDENCE_V1.zip':'44c3d7a9ab68d712714175b6d6e776e4d8a8a2fa6f47c54869d133e7cb8dd13a',
'MXM_V3_WAVE2_GLOBAL_FRICTION_TRIAGE_EVIDENCE_V1.zip':'8773ebe0224a92d5236146b40bedef83617e7927e60a076fccddabb8dca4c0fe'}
def sha(b): return hashlib.sha256(b).hexdigest()
def save(name,obj):
 STATE.mkdir(parents=True,exist_ok=True)
 p=STATE/name; p.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n'); return sha(p.read_bytes())
def metadata():
 j=json.loads(zlib.decompress(base64.b64decode((ROOT/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64').read_bytes())))
 return j,{x['symbol_id']:x for x in j['rows']}
def rolling(a,w,kind='mean'):
 s=pd.Series(a)
 return getattr(s.rolling(w,min_periods=w),kind)().to_numpy()
def features(o,h,l,c,v):
 # Grid NaNs interrupt windows. No forward fill or future fitted scaler.
 r=np.r_[np.nan,np.diff(np.log(c))]
 sig=np.sqrt(rolling(r*r,48)); sig=np.maximum(sig,1e-7)
 x=[np.ones(len(c))]
 for w in (3,6,12,48): x.append((np.log(c)-np.log(np.roll(c,w)))/(sig*np.sqrt(w)))
 x.append(rolling(r,12)*12/(rolling(abs(r),12)*12+1e-12))
 x.append((c-rolling(c,12))/(c*sig*np.sqrt(12)))
 x.append((c-(pd.Series(h).rolling(12).max().to_numpy()+pd.Series(l).rolling(12).min().to_numpy())/2)/(c*sig*np.sqrt(12)))
 rv=np.sqrt(rolling(r*r,12))
 x.append(np.log(np.maximum(rv,1e-9)/sig))
 x.append(rolling(np.minimum(r,0)**2,12)/(rolling(r*r,12)+1e-12)-.5)
 x.append((r/sig))
 x.append(np.log((v+1)/(rolling(v,48)+1)))
 x.append(np.sqrt(rolling(np.log(h/l)**2,12)/(4*np.log(2)))/sig)
 x.append(rolling((r*r-rolling(r*r,12))**2,12)/(sig**4+1e-20))
 # session primitive (UTC; honestly rolling 60m/240m, not native H1/H4)
 hour=(np.arange(len(c))%288)/288*2*np.pi
 x.extend([np.sin(hour),np.cos(hour)])
 a=np.column_stack(x)
 a[:48]=np.nan
 return np.clip(a,-4,4),sig

def verify_zip(p):
 b=p.read_bytes(); assert sha(b)==HASHES[p.name],f'archive SHA256 mismatch {p.name}'
 z=zipfile.ZipFile(io.BytesIO(b)); assert z.testzip() is None
 # Bundles include byte-identical nested duplicates; canonical root members only.
 for line in z.read('CHECKSUMS.sha256').decode().splitlines():
  if not line.strip(): continue
  digest,name=line.split('  ',1); assert sha(z.read(name))==digest,(p.name,name)
 return z

def build(data_dir,cache):
 cache.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((ROOT/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json').read_text())
 records=sorted(manifest['primary_series'],key=lambda s:s['symbol_id']); n=len(records)
 loc,md=metadata(); contexts=sorted({md[s['symbol_id']]['asset_class'] for s in records})
 # Half-open development grid. At each timestamp raw bar is not yet complete.
 times=pd.date_range(START,END,freq='5min',inclusive='left'); T=len(times)
 arrays={}
 for name,shape in [('ohlcv',(T,n,5)),('X',(T,n,19)),('sigma',(T,n)),('Y',(T,n,4))]:
  a=np.lib.format.open_memmap(cache/(name+'.npy'),mode='w+',dtype='float64',shape=shape);a[:]=np.nan;arrays[name]=a
 archives={HASHES[name]:verify_zip(data_dir/name) for name in list(HASHES)[:2]}
 rows=[]; total=0
 for sidx,s in enumerate(records):
  raw=archives[s['source_archive_sha256']].read(s['file']);assert sha(raw)==s['series_sha256'],s['symbol']
  df=pd.read_csv(io.BytesIO(raw));ts=pd.to_datetime(df.time_utc,utc=True)
  assert len(df)==s['row_count'] and ts.is_monotonic_increasing and not ts.duplicated().any()
  ns=ts.astype('int64').to_numpy();assert np.all(ns%300_000_000_000==0)
  assert ts.min()>=START and ts.max()<END
  ix=((ns-START.value)//300_000_000_000).astype(int)
  values=df[['open','high','low','close','tick_volume']].to_numpy(float)
  assert np.isfinite(values).all() and (values[:,:4]>0).all() and (values[:,4]>=0).all()
  assert (values[:,1]>=values[:,[0,2,3]].max(axis=1)-1e-10).all()
  assert (values[:,2]<=values[:,[0,1,3]].min(axis=1)+1e-10).all()
  arrays['ohlcv'][ix,sidx]=values
  o,h,l,c,v=arrays['ohlcv'][:,sidx].T
  x,sig=features(o,h,l,c,v)
  # discontinuity detection available at completion, quarantine next 48 bars;
  # no potentially discontinuous label may teach the model or count as alpha.
  jump=abs(np.r_[np.nan,np.diff(np.log(c))])
  threshold=np.maximum(.05,12*np.roll(sig,1))
  bad=(jump>threshold)
  quarantine=pd.Series(bad.astype(int)).rolling(49,min_periods=1).max().to_numpy().astype(bool)
  x[quarantine]=np.nan
  arrays['X'][:,sidx,:16]=x;arrays['sigma'][:,sidx]=sig
  for hi,w in enumerate(HORIZONS):
   future=np.roll(c,-w);label=np.log(future/c)/(sig*np.sqrt(w))
   count=pd.Series(np.isfinite(c).astype(int)).rolling(w+1,min_periods=w+1).sum().shift(-w).to_numpy()
   badfuture=pd.Series(bad.astype(int)).rolling(w+1,min_periods=w+1).max().shift(-w).to_numpy()
   label[(count!=w+1)|(badfuture>0)|~np.isfinite(x).all(axis=1)]=np.nan;label[-w:]=np.nan
   arrays['Y'][:,sidx,hi]=label
  total+=len(df);rows.append({**s,'verified_rows':len(df),'discontinuity_events':int(bad.sum()),'quarantine_bars':int(quarantine.sum()),'context':md[s['symbol_id']]['asset_class']})
  if sidx%20==0: print('verified series',sidx+1,'/',n,flush=True)
 assert n==145 and total==11406418
 # contemporaneous freshness mask only. Context factors exclude own leg;
 # no arbitrarily stale relational series; sufficient breadth means >=2 peers.
 r1=arrays['X'][:,:,10].copy()
 for ci,ctx in enumerate(contexts):
  si=[i for i,s in enumerate(records) if md[s['symbol_id']]['asset_class']==ctx]
  f=r1[:,si];valid=np.isfinite(f);count=valid.sum(axis=1);totalr=np.nansum(f,axis=1)
  for i in si:
   own=r1[:,i];num=count-np.isfinite(own)
   peer=(totalr-np.nan_to_num(own))/np.maximum(num,1);peer[num<2]=np.nan
   # singleton contexts have explicit neutral unavailable state, never invented relation.
   arrays['X'][:,i,16]=np.nan_to_num(peer)
   arrays['X'][:,i,17]=np.where(np.isfinite(peer),np.clip(own-peer,-4,4),0)
   arrays['X'][:,i,18]=(num>=2).astype(float)
 # Canonical symbol state and cost summaries use only prefix friction timestamps.
 costs={}
 for name in list(HASHES)[2:]:
  z=verify_zip(data_dir/name)
  for fn in z.namelist():
   if not fn.startswith('derived/') or not fn.endswith('.jsonl.gz'):continue
   for line in gzip.decompress(z.read(fn)).splitlines():
    j=json.loads(line);symbol=j['symbol'];d=costs.setdefault(symbol,{'fresh_prefix_spreads_bps':[],'files':[]})
    if name not in d['files']:d['files'].append(name)
    for row in j['rows']:
     if row['boundary_ms']>=INNER_END.value//1_000_000:continue
     for key in ('d0s','d1s','d5s','d30s'):
      q=row[key]
      if q.get('fresh') and q.get('spread_bps') is not None and q['spread_bps']>=0:d['fresh_prefix_spreads_bps'].append(q['spread_bps'])
 cost_inventory=[]
 for s in records:
  vals=costs.get(s['symbol'],{}).get('fresh_prefix_spreads_bps',[])
  cost_inventory.append({'symbol':s['symbol'],'prefix_fresh_sample_count':len(vals),'spread_bound_bps':2*max(vals) if len(vals)>=10 else None,'state':'PREFIX_SAMPLE_MAX_X2_DISCOVERY_BOUND_NOT_HISTORICAL_TRUTH' if len(vals)>=10 else 'COST_UNRESOLVED'})
 info={'records':records,'metadata':[md[s['symbol_id']] for s in records],'assets':{a['assetId']:a['name'] for a in loc['asset_metadata']},'contexts':contexts,'costs':cost_inventory,'T':T,'inner_end_index':91*288,'outer_end_index':T,'source_archive_hashes':{k:v for k,v in HASHES.items()}}
 (cache/'info.json').write_text(json.dumps(info))
 save('PRIMARY145_DATA_INTEGRITY_RESULT.json',{'status':'PASS_RAW_BYTES_VERIFIED','series_count':n,'total_m5_rows':total,'archive_hashes':{k:v for k,v in HASHES.items() if 'M5_' in k},'series':rows,'protected_forward_opened':False,'supplementary_primary_inference':False})
 save('REUSABLE_DATA_AND_FRICTION_INVENTORY_V1.json',{'costs':cost_inventory,'cost_admissible_symbols':sum(c['spread_bound_bps'] is not None for c in cost_inventory),'source_hashes':HASHES,'prefix_only':True,'supplementary_count':len(manifest['supplementary_original_series']),'late_join':'materialized; transfer diagnostic separate from primary chronological replay; not fresh temporal evidence','present_metadata':'DISCOVERY_SCENARIO_ONLY_NOT_EXACT_HISTORICAL_AUTHORITY'})
 for a in arrays.values():a.flush()
 print('integrity complete rows',total,flush=True)
 return info
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);a=p.parse_args();build(a.data,a.cache)
