"""Outcome-informed DEVELOPMENT sensitivity on all 7975 frozen cells.

Signal is known at M5 bar close i. Entry is the recorded open of bar i+1,
exit the recorded close of bar i+1+h. Both are gross OHLC proxies; no spread,
execution guarantee, or confirmation is claimed.
"""
from __future__ import annotations
import argparse,concurrent.futures,csv,gzip,hashlib,io,json,math,os,statistics,zipfile
from collections import defaultdict
from pathlib import Path
import numpy as np
from research_core_v3.model import Bar,Series,_dt
from research_core_v3.fast_engine import Features
from research_core_v3.engine import _grid,_ci
from research_core_v3.signals import mean,median

def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def worker(item,original,delta,spec,work,source_sha):
 sid=item['symbol_id'];path=work/f'{sid}.json'
 if path.exists():
  x=json.loads(path.read_text());d=x.pop('sha256',None)
  if d!=sha(canonical(x)) or x['source_surface_sha256']!=source_sha or len(x['cells'])!=55:raise ValueError('corrupt lag checkpoint')
  return sid
 with zipfile.ZipFile(original if item['source_archive_sha256']==ORIGINAL_SHA else delta) as z:data=z.read(item['file'])
 if sha(data)!=item['series_sha256']:raise ValueError('changed raw series')
 bars=tuple(Bar(_dt(r['time_utc']),*(float(r[k]) for k in ('open','high','low','close','tick_volume'))) for r in csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
 f=Features(Series(item['symbol'],sid,item['series_sha256'],bars));opens=np.array([b.open for b in bars],dtype=float);hs=spec['response_horizons_bars'];mh=max(hs);results=[]
 for m in spec['mechanisms']:
  for params in _grid(m.get('parameter_grid',{})):
   for ctx in m.get('contexts') or [{'kind':'ALL'}]:
    sig=f.signals(m['name'],params);mask=(sig!=0)&f.context(ctx);mask[max(0,f.n-mh-1):]=False
    if f.n>mh+1:mask[:f.n-mh-1]&=f.seg[:f.n-mh-1]==f.seg[mh+1:]
    candidates=np.flatnonzero(mask);indices=[];last=-10**12;rearm=int(m.get('rearm_bars',1))
    for rawi in candidates:
     i=int(rawi)
     if i-last<rearm:continue
     indices.append(i);last=i
    horizons={}
    for h in hs:
     date_vals=defaultdict(list);vals=[]
     for i in indices:
      if f.seg[i]!=f.seg[i+1+h] or opens[i+1]==0:continue
      r=int(sig[i])*(f.c[i+1+h]/opens[i+1]-1)
      vals.append(r);date_vals[bars[i].ts.date().isoformat()].append(r)
     dm=[statistics.fmean(v) for _,v in sorted(date_vals.items())]
     horizons[str(h)]={'n':len(vals),'independent_date_clusters':len(dm),'mean_response':mean(vals),'median_response':median(vals),'date_cluster_uncertainty':_ci(dm)}
    results.append({'symbol_id':sid,'symbol':item['symbol'],'mechanism':m['name'],'context':ctx,'params':params,'horizons':horizons})
 record={'schema':'mxm.research-core-v3.next-open-gross-sensitivity.v1','source_surface_sha256':source_sha,'symbol_id':sid,'source_series_sha256':item['series_sha256'],'cells':results,'costs_included':False,'economic_outcomes_opened':'DEVELOPMENT_ONLY'}
 record['sha256']=sha(canonical(record));tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(record,sort_keys=True,separators=(',',':')));os.replace(tmp,path);return sid
ORIGINAL_SHA='09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--original',required=True);ap.add_argument('--delta',required=True);ap.add_argument('--workers',type=int,default=5);a=ap.parse_args()
 root=Path(__file__).resolve().parents[1]/'research_core_v3/state';input=json.loads((root/'PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());spec=json.loads((root/'FROZEN_EXPERIMENT_SPEC_V1.json').read_text());surface=json.loads((root/'BROAD_145_DEVELOPMENT_SURFACE_MANIFEST_V1.json').read_text());work=root/'next_open_sensitivity_work';work.mkdir(exist_ok=True)
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
  tasks=[pool.submit(worker,x,a.original,a.delta,spec,work,surface['sha256']) for x in input['primary_series']]
  for i,task in enumerate(concurrent.futures.as_completed(tasks),1):print('[NEXT_OPEN]',i,'/145',task.result(),flush=True)
 shards=[]
 for offset in range(0,145,15):
  items=input['primary_series'][offset:offset+15];records=[json.loads((work/f"{x['symbol_id']}.json").read_text()) for x in items]
  assert all(len(x['cells'])==55 for x in records)
  blob=gzip.compress(canonical({'schema':'mxm.research-core-v3.next-open-shard.v1','source_surface_sha256':surface['sha256'],'symbols':records}),compresslevel=9,mtime=0)
  name=f'NEXT_OPEN_SHARD_{offset//15:02d}.json.gz';(root/name).write_bytes(blob);shards.append({'path':name,'sha256':sha(blob),'cell_count':sum(len(r['cells']) for r in records),'symbol_ids':[r['symbol_id'] for r in records]})
 doc={'schema':'mxm.research-core-v3.next-open-gross-sensitivity-index.v1','source_surface_sha256':surface['sha256'],'primary_input_sha256':input['sha256'],'primary_count':145,'cell_count':7975,'shards':shards,'entry':'BAR_I_PLUS_ONE_OPEN_GROSS_PROXY','exit':'BAR_I_PLUS_ONE_PLUS_H_CLOSE','costs_included':False,'confirmation':False};doc['sha256']=sha(canonical(doc));(root/'NEXT_OPEN_GROSS_SENSITIVITY_MANIFEST_V1.json').write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n');print('COMPLETE',doc['sha256'])
if __name__=='__main__':main()
