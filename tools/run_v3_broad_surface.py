"""Run every frozen V3 cell on each of the 145 hash-bound primary series."""
from __future__ import annotations
import argparse,concurrent.futures,csv,gzip,hashlib,io,json,os,zipfile
from pathlib import Path
from research_core_v3.model import Bar,Series,_dt
from research_core_v3.fast_engine import execute_one

def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def worker(item,original,delta,spec,out,spec_sha,input_sha):
 sid=item['symbol_id'];target=out/f'{sid}.json'
 if target.exists():
  current=json.loads(target.read_text())
  digest=current.pop('sha256',None)
  if digest!=sha(canonical(current)) or current['input_manifest_sha256']!=input_sha or current['spec_sha256']!=spec_sha or current['source_series_sha256']!=item['series_sha256'] or len(current['cells'])!=55:raise ValueError(f'corrupt completed symbol {sid}')
  return sid,len(current['cells']),'REUSED'
 p=Path(original if item['source_archive_sha256']==ORIGINAL_SHA else delta)
 with zipfile.ZipFile(p) as z:
  data=z.read(item['file'])
 if sha(data)!=item['series_sha256']:raise ValueError(f'input bytes changed {sid}')
 rows=csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
 bars=tuple(Bar(_dt(r['time_utc']),float(r['open']),float(r['high']),float(r['low']),float(r['close']),float(r['tick_volume'])) for r in rows)
 if len(bars)!=item['row_count'] or bars[0].ts!=_dt(item['first_timestamp_utc']) or bars[-1].ts!=_dt(item['last_timestamp_utc']):raise ValueError(f'input metadata changed {sid}')
 series=Series(item['symbol'],sid,f"{item['source_archive_sha256']}!{item['file']}",bars)
 cells=execute_one(series,spec)
 if len(cells)!=55 or {x['mechanism'] for x in cells}!={x['name'] for x in spec['mechanisms']}:raise ValueError(f'incomplete mechanism surface {sid}')
 record={'schema':'mxm.research-core-v3.primary-symbol-response.v1','input_manifest_sha256':input_sha,'spec_sha256':spec_sha,'source_series_sha256':item['series_sha256'],'symbol_id':sid,'symbol':item['symbol'],'cells':cells}
 record['sha256']=sha(canonical(record))
 temp=target.with_suffix('.tmp');temp.write_text(json.dumps(record,sort_keys=True,separators=(',',':')));os.replace(temp,target)
 return sid,len(cells),'DONE'
ORIGINAL_SHA='09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--original',required=True);ap.add_argument('--delta',required=True);ap.add_argument('--workers',type=int,default=5);ap.add_argument('--out',type=Path,default=Path('research_core_v3/state/development_surface_work'));a=ap.parse_args()
 root=Path(__file__).resolve().parents[1];data=json.loads((root/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());spec=json.loads((root/'research_core_v3/state/FROZEN_EXPERIMENT_SPEC_V1.json').read_text())
 digest=data.pop('sha256');assert sha(canonical(data))==digest;data['sha256']=digest
 assert data['primary_count']==145 and data['total_primary_M5_rows']==11406418 and not data['protected_forward_opened']
 spec_sha=sha(canonical(spec));a.out.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
  futures={pool.submit(worker,item,a.original,a.delta,spec,a.out,spec_sha,digest):item['symbol_id'] for item in data['primary_series']}
  done=0
  for future in concurrent.futures.as_completed(futures):
   sid,cells,status=future.result();done+=1
   print(f'[DEVELOPMENT] {done}/145 {sid} {cells} cells {status}',flush=True)
 records=[]
 for item in data['primary_series']:
  result=json.loads((a.out/f"{item['symbol_id']}.json").read_text())
  records.append({'symbol_id':item['symbol_id'],'symbol':item['symbol'],'series_sha256':item['series_sha256'],'result_sha256':result['sha256'],'cell_count':len(result['cells'])})
 if len(records)!=145 or sum(r['cell_count'] for r in records)!=7975:raise ValueError('incomplete primary response grid')
 # Transport shards are exhaustive storage units, never symbol selection or economic waves.
 shards=[]
 for offset in range(0,145,15):
  chosen=records[offset:offset+15];content={'schema':'mxm.research-core-v3.development-surface-shard.v1','input_manifest_sha256':digest,'spec_sha256':spec_sha,'symbols':[json.loads((a.out/f"{x['symbol_id']}.json").read_text()) for x in chosen]}
  name=f'BROAD_SURFACE_SHARD_{offset//15:02d}.json.gz';path=a.out.parent/name
  blob=gzip.compress(canonical(content),compresslevel=9,mtime=0);path.write_bytes(blob)
  shards.append({'path':name,'sha256':sha(blob),'symbol_ids':[x['symbol_id'] for x in chosen],'cell_count':sum(x['cell_count'] for x in chosen)})
 manifest={'schema':'mxm.research-core-v3.complete-broad-development-surface.v1','status':'COMPLETE_DEVELOPMENT_RESPONSE_SURFACE','primary_count':145,'cell_count':7975,'input_manifest_sha256':digest,'spec_sha256':spec_sha,'response_horizons_bars':spec['response_horizons_bars'],'protected_forward_opened':False,'final_pnl_certification':False,'report_all_cells':True,'records':records,'shards':shards}
 manifest['sha256']=sha(canonical(manifest));path=a.out.parent/'BROAD_145_DEVELOPMENT_SURFACE_MANIFEST_V1.json';path.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 print('COMPLETE',len(records),7975,manifest['sha256'],flush=True)
if __name__=='__main__':main()
