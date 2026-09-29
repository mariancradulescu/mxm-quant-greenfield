"""Lossless compact persistence of exact event indices and quote windows.

Entry/exit timestamps are reconstructible from authenticated source bars.
No cost values, outcomes, or scope decisions are changed by this encoding.
"""
import gzip,json,zipfile
from pathlib import Path
from tools.run_v3_broad_surface import canonical,sha

def main():
 state=Path(__file__).resolve().parents[1]/'research_core_v3/state';target=state/'CORRECTED_MINIMAL_FRICTION_EVIDENCE_PLAN_V2.json';plan=json.loads(target.read_text());old=plan.pop('sha256');assert sha(canonical(plan))==old
 if 'scope_archives' in plan:raise ValueError('already packed')
 blobs={}
 for shard in plan['shards']:
  raw=(state/shard['path']).read_bytes();assert sha(raw)==shard['sha256'];doc=json.loads(gzip.decompress(raw));regions=sorted({r for e in doc['events'] for r in e['region_sha256s']});lookup={r:i for i,r in enumerate(regions)}
  doc['events']=[[e['decision_index'],e['direction'],[lookup[r] for r in e['region_sha256s']]] for e in doc['events']];doc['event_encoding']=['decision_index','direction','region_indices'];doc['region_sha256_dictionary']=regions;doc['timestamp_reconstruction']='entry=source_bar[i+1].time_utc; exit=source_bar[i+6].time_utc+300 seconds';doc['expanded_scope_sha256']=shard['sha256']
  # Delta-code windows to reduce repetitive timestamp bytes without loss.
  previous=0;encoded=[]
  for start,end in doc.pop('bid_and_ask_request_windows_ms'):
   encoded.append([start-previous,end-start]);previous=start
  doc['quote_windows_delta_ms']=encoded;doc['window_encoding']='successive start deltas from 0, duration; exact milliseconds'
  blob=gzip.compress(canonical(doc),mtime=0);blobs[shard['path']]=blob;shard['sha256']=sha(blob)
 archives=[]
 for offset in range(0,len(plan['shards']),14):
  name=f'CORRECTED_FRICTION_SCOPE_V2_PACK_{offset//14:02d}.zip';path=state/name
  with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED) as z:
   for shard in plan['shards'][offset:offset+14]:
    info=zipfile.ZipInfo(shard['path']);info.date_time=(1980,1,1,0,0,0);info.external_attr=0o100644<<16;z.writestr(info,blobs[shard['path']]);shard['archive']=name
  archives.append({'path':name,'sha256':sha(path.read_bytes()),'size_bytes':path.stat().st_size})
 plan['expanded_scope_plan_sha256']=old;plan['scope_archives']=archives;plan['packing_implementation_sha256']=sha(Path(__file__).read_bytes());plan['sha256']=sha(canonical(plan));target.write_text(json.dumps(plan,sort_keys=True,indent=2)+'\n');print(json.dumps({'sha256':plan['sha256'],'archive_bytes':sum(x['size_bytes'] for x in archives),'archives':len(archives)}))
if __name__=='__main__':main()
