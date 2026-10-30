import argparse,hashlib,io,json,zipfile,datetime as dt
from pathlib import Path
import numpy as np,pandas as pd
p=argparse.ArgumentParser();p.add_argument('--zip',choices=('base','delta'),required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);a=p.parse_args()
ROOT=Path('/mnt/data/mxm_primary145_originals')
Z={'base':('MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip','09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259'),
   'delta':('MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip','37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e')}
file,sha=Z[a.zip];sup={3004,3005,3009,3023,3028,5460,5462,5468,5474,5481,5562,7338}
path=ROOT/file
assert path.exists() and path.stat().st_size>1000
with zipfile.ZipFile(path) as z:
 payload=json.loads(z.read('V3_CAPTURE_PAYLOAD.json'))
 assert a.end<=len(payload['series']) and a.start<a.end
 checksums={p:n for p,n in (line.split('  ',1) for line in z.read('CHECKSUMS.sha256').decode().splitlines())}
 rows=0;series=[];selected=0;seen=[]
 for entry in payload['series'][a.start:a.end]:
  sid=int(entry['symbol_id']); fn=entry['file']; seen.append(sid)
  data=z.read(fn);digest=hashlib.sha256(data).hexdigest()
  assert digest==entry['sha256'] and checksums[digest]==fn,(sid,'HASH')
  frame=pd.read_csv(io.BytesIO(data),usecols=['time_utc','open','high','low','close','tick_volume']);n=len(frame)
  assert n==entry['row_count'] and n>0
  t=pd.to_datetime(frame['time_utc'],utc=True,format='%Y-%m-%dT%H:%M:%SZ').astype('int64').to_numpy()//1_000_000_000
  assert t[0]%300==0 and t[-1]%300==0 and t[-1]<1799971200 and np.all(t[1:]>t[:-1]) and np.all(t%300==0)
  assert frame['time_utc'].iat[0]==entry['first_timestamp_utc'] and frame['time_utc'].iat[-1]==entry['last_timestamp_utc']
  prices=frame[['open','high','low','close']].to_numpy(float)
  assert np.isfinite(prices).all() and (prices>0).all() and np.all(prices[:,1]>=np.maximum(prices[:,0],prices[:,3])) and np.all(prices[:,2]<=np.minimum(prices[:,0],prices[:,3]))
  assert np.isfinite(frame['tick_volume']).all() and np.all(frame['tick_volume'].to_numpy()>=0)
  rows+=n
  if sid in sup:continue
  selected+=n
  idx=np.arange(n,dtype=np.int32);first=np.maximum.accumulate(np.where(np.r_[True,np.diff(t)!=300],idx,0))
  prior=(idx-first)>=11
  next8=np.zeros(n,dtype=bool);next8[:-8]=(t[8:]-t[:-8])==2400
  future=next8[prior];weeks=pd.to_datetime(t[prior],unit='s',utc=True).isocalendar()
  raw=(weeks['year'].to_numpy()*100+weeks['week'].to_numpy()).astype(np.int32)
  uniq,inv,cnt=np.unique(raw,return_inverse=True,return_counts=True)
  complete=np.bincount(inv,weights=future.astype(int),minlength=len(uniq)).astype(int)
  per={f'{w//100}-W{w%100:02d}':{'features':int(c),'future_observable':int(o),'censored':int(c-o)} for w,c,o in zip(uniq,cnt,complete)}
  series.append({'symbol_id':sid,'symbol':entry['broker_symbol'],'row_count':n,'source_archive_sha256':sha,
   'csv_sha256':digest,'first':entry['first_timestamp_utc'],'last':entry['last_timestamp_utc'],'weeks':per})
 result={'zip_id':a.zip,'sha256':sha,'start':a.start,'end':a.end,'series_in_part':a.end-a.start,
 'all_series_ids':seen,'all_rows_verified':rows,'primary_rows_verified':selected,'primary_series':series,'protected_forward':False,'orders':0}
 out=ROOT/f'verified-{a.zip}-{a.start:03d}-{a.end:03d}.json';out.write_text(json.dumps(result,separators=(',',':'),sort_keys=True)+'\n')
 print('VERIFIED',a.zip,a.start,a.end,'all_rows',rows,'primary_rows',selected,'primary_series',len(series),'out',out)
