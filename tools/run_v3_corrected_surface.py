"""All 7975 cells, immutable authenticated input archives, no forward access."""
import argparse,concurrent.futures,csv,gzip,io,json,os,zipfile
from pathlib import Path
from research_core_v3.model import Bar,Series,_dt
from research_core_v3.corrected_semantics import execute_corrected
from tools.run_v3_broad_surface import canonical,sha,ORIGINAL_SHA
SOURCE='32a6faaa5c5a74bb7ecfabd388aeced7d50794898c4a24b0c861229d475aa9b6'
def worker(item,original,delta,spec,out,binding):
    target=out/f"{item['symbol_id']}.json"
    if target.exists():
        r=json.loads(target.read_text());d=r.pop('sha256');assert d==sha(canonical(r)) and r['binding']==binding
        return item['symbol_id']
    with zipfile.ZipFile(original if item['source_archive_sha256']==ORIGINAL_SHA else delta) as z:data=z.read(item['file'])
    assert sha(data)==item['series_sha256']
    bars=tuple(Bar(_dt(r['time_utc']),*(float(r[k]) for k in ('open','high','low','close','tick_volume'))) for r in csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
    assert len(bars)==item['row_count'] and bars[-1].ts<_dt(binding['protected_forward_start'])
    assert all((b.ts-a.ts).total_seconds()>=300 and (b.ts-a.ts).total_seconds()%300==0 for a,b in zip(bars,bars[1:]))
    cells=execute_corrected(Series(item['symbol'],item['symbol_id'],item['series_sha256'],bars),spec);assert len(cells)==55
    r={'schema':'mxm.research-core-v3.corrected-symbol-development.v2','binding':binding,'source_series_sha256':item['series_sha256'],'symbol_id':item['symbol_id'],'symbol':item['symbol'],'cells':cells}
    r['sha256']=sha(canonical(r));tmp=target.with_suffix('.tmp');tmp.write_bytes(canonical(r));os.replace(tmp,target);return item['symbol_id']
def main():
    p=argparse.ArgumentParser();p.add_argument('--original',required=True);p.add_argument('--delta',required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];state=root/'research_core_v3/state';out=state/'corrected_surface_work_v2';out.mkdir(exist_ok=True)
    inputs=json.loads((state/'PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());digest=inputs.pop('sha256');assert sha(canonical(inputs))==digest
    spec=json.loads((state/'FROZEN_EXPERIMENT_SPEC_V1.json').read_text());scope=json.loads((state/'INCLUSIVE_FULL_DEPTH_DISCOVERY_CORE_V1.json').read_text())
    original=json.loads((state/'BROAD_145_DEVELOPMENT_SURFACE_MANIFEST_V1.json').read_text());s=original.pop('sha256');assert s==SOURCE and sha(canonical(original))==s
    for shard in original['shards']:assert sha((state/shard['path']).read_bytes())==shard['sha256']
    for archive,expected in [(a.original,inputs['original_capture_sha256']),(a.delta,inputs['delta_capture_sha256'])]:assert sha(Path(archive).read_bytes())==expected
    binding={'original_surface_sha256':SOURCE,'input_manifest_sha256':digest,'spec_sha256':sha(canonical(spec)),'implementation_sha256':sha((root/'research_core_v3/corrected_semantics.py').read_bytes()),'protected_forward_start':scope['protected_forward_start']}
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        fs=[pool.submit(worker,item,a.original,a.delta,spec,out,binding) for item in inputs['primary_series']]
        for j,f in enumerate(concurrent.futures.as_completed(fs)):print('CORRECTED',j+1,'/145',f.result(),flush=True)
    records=[];shards=[]
    for offset in range(0,145,10):
        symbols=[]
        for item in inputs['primary_series'][offset:offset+10]:
            r=json.loads((out/f"{item['symbol_id']}.json").read_text());r['full_compute_checkpoint_sha256']=r.pop('sha256')
            for cell in r['cells']:
                for variant,vdata in cell['variants'].items():
                    for horizon,metrics in vdata['horizons'].items():
                        if variant!='CORRECTED_NEXT_OPEN_PLUS_STRICT_FULL_DEPENDENCY_CONTINUITY' or horizon!='6':metrics.pop('week_cluster_means',None)
            r['sha256']=sha(canonical(r));symbols.append(r);records.append({'symbol_id':item['symbol_id'],'symbol':item['symbol'],'result_sha256':r['sha256'],'source_series_sha256':item['series_sha256'],'cells':55})
        name=f'CORRECTED_SURFACE_V2_SHARD_{offset//10:02d}.json.gz';blob=gzip.compress(canonical({'binding':binding,'symbols':symbols}),mtime=0);(state/name).write_bytes(blob);shards.append({'path':name,'sha256':sha(blob),'cell_count':len(symbols)*55})
    r={'schema':'mxm.research-core-v3.corrected-complete-development.v2','binding':binding,'assembly_implementation_sha256':sha(Path(__file__).read_bytes()),'primary_count':145,'cell_count':7975,'variants_per_cell':4,'horizons':[1,3,6,12],'protected_forward_opened':False,'final_pnl_certification':False,'outcome_informed_methodology_change':True,'original_artifacts_unchanged':True,'old_next_open_label':'H_PLUS_ONE_HOLDING_SENSITIVITY','cohort_policy':'ORIGINAL_MAX12_FORWARD_VALID_REARMED_EVENTS;STRICT_SUBSET_NO_REARM','records':records,'shards':shards}
    r['sha256']=sha(canonical(r));(state/'CORRECTED_145_DEVELOPMENT_MANIFEST_V2.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print('COMPLETE',r['sha256'],flush=True)
if __name__=='__main__':main()
