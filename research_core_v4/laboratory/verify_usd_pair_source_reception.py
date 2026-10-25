"""Verify exact original public native reception offline; never decode market inputs or execute a model."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REL=Path('docs/economic-development/20261025/usd-pair-source-40195796730')
MANIFEST_SHA='09291c35875671bb98a0e1a03223e99a7399400b29f6cdf37dffe7276ede641f'
ARCHIVE_SHA='a14210048993f5dab529d76033a8214ea6336e3975122b5e830a202a74bf9fb0'
def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('USD_PAIR_ORIGINAL_'+why)
def verify(root=ROOT):
    folder=root/REL;mraw=(folder/'MANIFEST.json').read_bytes();need(sha(mraw)==MANIFEST_SHA,'IMMUTABLE_MANIFEST')
    m=json.loads(mraw);path=folder/'artifact.zip.b64'
    need(not path.is_symlink() and path.stat().st_size<8192,'BOUNDED_ARCHIVE')
    archive=base64.b64decode(path.read_text().strip(),validate=True)
    need(len(archive)==1624 and sha(archive)==ARCHIVE_SHA==m['archive_sha256'],'EXACT_NATIVE_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        need(z.namelist()==['receipt.json'] and z.infolist()[0].file_size==4342,'EXACT_BOUNDED_MEMBER')
        raw=z.read('receipt.json')
    need(sha(raw)==m['receipt_sha256'] and (folder/'receipt.json').read_bytes()==raw,'ORIGINAL_RECEIPT_COPY')
    r=json.loads(raw);c=r['original_csharp_report'];p=r['independent_receipt'];a=c['result']
    need(r['schema']=='mxm.native.usd-pair-source-reception.v1' and r['run_id']==m['run_id']==40195796730 and
         m['job_id']==121176229062 and m['artifact_id']==12599821446 and
         r['source_sha']==m['native_source_sha']=='0f27a1716b84d5102dcd925be01d9fdb42f1e1fd' and
         r['native_custody_verified'] is True,'NATIVE_SOURCE_JOB')
    expected={'FX_MISSING':1,'FX_STALE':89182,'GBP_CROSSED':2,'GBP_STALE':4765,'READY_STRICT_PRIOR_FX':718405}
    need(a['Rows']==1960588 and a['Groups']==1214095 and a['SourceRows']=={'EURUSD':685474,'GBPUSD':1275114} and
         a['Routing']==p['routing']==expected and c['typed_routing_snapshots']==812355 and
         c['typed_valuation_snapshots']==408017 and a['FxOnlyMarkGroups']==401740 and
         p['every_state_routing_mark_group_checked'] is True and c['max_age_ms']==5000,'ALL_NATIVE_GROUPS_AND_TYPED_PURPOSES')
    for name in ('State','Routing','Mark'):
        need(a[name+'Sha256']==p[name.lower()+'_sha256'],'INDEPENDENT_GROUP_HASHES')
    for symbol,field,run,count in [('EURUSD','eur_file_sha256',39917922508,685474),('GBPUSD','gbp_file_sha256',40179011821,1275114)]:
        b=r['bridges'][symbol]
        need(b['source_run']==run and b['events']==count and b['derived_sha256']==c[field] and
             b['orders']==b['strategy_trials']==b['economic_outcomes']==0 and
             b['historical_arrival_order_proven'] is False and b['historical_costs_proven'] is False,'BOTH_ORIGINAL_BRIDGES')
    for value in (r,c,p):
        need(value['broker_orders']==value['strategy_trials']==value['economic_outcomes']==0 and
             all(value[k] is False for k in ('economic_edge_proven','hard21_proven','account_replay_executed')),'NO_ECONOMIC_PROMOTION')
    need(r['new_broker_requests']==0 and r['historical_costs_proven'] is False and r['native_ctrader_runtime_reception'] is False and
         c['historical_arrival_order_proven'] is False and c['historical_fills_proven'] is False and
         m['raw_derived_streams_uploaded'] is False and m['raw_csharp_json_separately_archived'] is False,'NO_NATIVE_OR_PRIVATE_DATA_PROMOTION')
    changed=[path for path,h in m['source_code_sha256'].items() if not (root/path).is_file() or sha((root/path).read_bytes())!=h]
    return {'original_public_archive_verified':True,'source_run_id':40195796730,'original_native_job':121176229062,
            'rows':1960588,'atomic_time_groups':1214095,'strict_prior_ready_groups':718405,'rejected_gbp_groups':93950,
            'fx_only_mark_groups':401740,'current_source_matches_original':not changed,'changed_source_paths':changed,
            'raw_market_inputs_replayed':False,'account_replay_executed':False,'economic_edge_proven':False,'hard21_proven':False,'broker_orders':0}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
