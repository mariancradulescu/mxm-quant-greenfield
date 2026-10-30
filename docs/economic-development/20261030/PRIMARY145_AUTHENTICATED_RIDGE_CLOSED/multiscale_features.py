"""One registered source-grounded annual pooled ML candidate. DEV only.
Fixed before outcome exposure here: 2026-06-01 train cutoff, 7d embargo,
Ridge alpha=1000, 8 observed M5-bar hold, one hourly account proposal;
no source/outcome-based market filtering, no cost/volume certification.
"""
import argparse,io,json,zipfile,hashlib
from pathlib import Path
import numpy as np,pandas as pd
P=Path('/mnt/data/mxm_primary145_originals')
Z={'base':'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip','delta':'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip'}
SUP={3004,3005,3009,3023,3028,5460,5462,5468,5474,5481,5562,7338}
q=argparse.ArgumentParser();q.add_argument('--zip',required=True,choices=Z);q.add_argument('--start',required=True,type=int);q.add_argument('--end',required=True,type=int);a=q.parse_args()
Xall=[];yall=[];tall=[];sall=[];support=[];grossbaseline=[];rawrows=0
with zipfile.ZipFile(P/Z[a.zip]) as z:
 p=json.loads(z.read('V3_CAPTURE_PAYLOAD.json'))
 for s in p['series'][a.start:a.end]:
  sid=int(s['symbol_id'])
  if sid in SUP:continue
  data=z.read(s['file'])
  assert hashlib.sha256(data).hexdigest()==s['sha256']
  f=pd.read_csv(io.BytesIO(data),usecols=['time_utc','open','close','tick_volume'])
  rawrows+=len(f)
  t=pd.to_datetime(f['time_utc'],format='%Y-%m-%dT%H:%M:%SZ',utc=True).astype('int64').to_numpy()//1_000_000_000
  O=f['open'].to_numpy(float);C=f['close'].to_numpy(float);V=f['tick_volume'].to_numpy(float)
  assert (C>0).all() and (O>0).all() and (V>=0).all() and np.all(np.diff(t)>0)
  lp=np.log(C);r=np.r_[0,np.diff(lp)]
  idx=np.arange(len(t),dtype=np.int32)
  run=np.maximum.accumulate(np.where(np.r_[True,np.diff(t)!=300],idx,0))
  indices=idx[(idx>=48)&((idx-run)>=48)&(t%3600==3300)]
  if not len(indices):continue
  variance=np.r_[0,np.cumsum(r*r)]
  sig=np.maximum(np.sqrt(np.maximum((variance[indices+1]-variance[indices-47])/48,0))*10000,0.05)
  sums=np.r_[0,np.cumsum(V)]
  relvol=np.log((1+(sums[indices+1]-sums[indices-5])/6)/(1+(sums[indices+1]-sums[indices-47])/48))
  def rnorm(l):return np.clip((lp[indices]-lp[indices-l])*10000/(sig*np.sqrt(l)),-8,8)
  r1,r6,r12,r48=rnorm(1),rnorm(6),rnorm(12),rnorm(48)
  x=np.column_stack([r1,r6,r12,r48,np.clip(relvol,-4,4),np.clip(np.log1p(sig)/5,0,4),
       np.clip(r12*relvol,-8,8),np.clip(r48*relvol,-8,8)])
  future=(indices+10<len(t));future[future]=(t[indices[future]+10]-t[indices[future]]==3000)
  y=np.full(len(indices),np.nan)
  J=indices[future]
  y[future]=10000*np.log(O[J+10]/O[J+2])
  assert np.isfinite(x).all() and np.all((t[indices]+600)<1799971200)
  Xall.append(x.astype('float32'));yall.append(y.astype('float32'))
  tall.append((t[indices]+600).astype('int64'));sall.append(np.full(len(indices),sid,dtype=np.int32));support.append(future)
  grossbaseline.append(np.sign(r12).astype('int8'))
assert Xall,'empty features'
out=P/f'features-{a.zip}-{a.start:03d}-{a.end:03d}.npz'
np.savez_compressed(out,X=np.concatenate(Xall),y=np.concatenate(yall),t=np.concatenate(tall),sid=np.concatenate(sall),future=np.concatenate(support),baseline=np.concatenate(grossbaseline))
print('FEATURES',out.name,'source_rows',rawrows,'proposals',sum(len(x) for x in Xall),'future_supported',sum(int(x.sum()) for x in support))
