"""Offline exact original encrypted spot evidence restore; no decryption/broker/model."""
import base64,hashlib,io,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261027/native-spot-40455704891'
MANIFEST_SHA='39f224020b15d9a2128411c6a218c08fa709dfbecc6fb74f525b0518727cc93f'
def need(ok,why):
    if not ok:raise ValueError('DURABLE_SPOT_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path,limit):
    path=Path(path);need(path.is_file() and not path.is_symlink() and path.stat().st_size<=limit,'BOUNDED_REGULAR_FILE')
    return path.read_bytes()
def verify(folder=FOLDER,destination=None):
    folder=Path(folder);need(not folder.is_symlink(),'REGULAR_FOLDER')
    raw=read(folder/'MANIFEST.json',40000);need(sha(raw)==MANIFEST_SHA,'IMMUTABLE_MANIFEST')
    m=json.loads(raw);need(m['run_id']==40455704891 and m['attempt']==1 and m['head']=='d16db0a9e40ca2f48f8b9f0d483ca3b131d173e1','ORIGINAL_NATIVE_PROVENANCE')
    files={}
    for role,names in [('producer',{'capture.mxmenc','producer.json'}),('cold',{'cold.json'})]:
        a=m['artifacts'][role];blob=base64.b64decode(read(folder/(role+'-artifact.zip.b64'),64_000_000).strip(),validate=True)
        need(len(blob)==a['zip_bytes'] and sha(blob)==a['zip_sha256'],'ORIGINAL_'+role.upper()+'_ARCHIVE')
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            info=z.infolist();need(len(info)==len(names) and set(z.namelist())==names and sum(i.file_size for i in info)<=32_000_000,'EXACT_ZIP_MEMBER_ROSTER')
            for name in sorted(names):
                data=z.read(name);need(sha(data)==m['members'][name]['sha256'] and len(data)==m['members'][name]['bytes'],'ORIGINAL_MEMBER_'+name)
                files[name]=data
    p=json.loads(files['producer.json']);c=json.loads(files['cold.json'])
    for role,r in [('spot-collect',p),('spot-cold',c)]:
        need(r['schema']=='mxm.native-spot-observation-public.v1' and r['role']==role and r['accepted'] is True and
          r['source_sha']==m['head'] and r['run_id']==m['run_id'] and r['attempt']==1 and
          r['policy_sha256']==m['policy_sha256'] and r['partition_sha256']==m['partition_sha256'] and
          r['native_source']=='d2fae5641b759b1c8c24161d83d62d39e104eafd' and
          r['cipher_sha256']==sha(files['capture.mxmenc']) and r['private_sha256']==m['private_sha256'],
          'ACTUAL_NATIVE_IDENTITY_AND_CUSTODY_'+role)
        need(r['classification']=='DEVELOPMENT_SOURCE_QUALITY_ONLY' and r['orders']==r['strategy_trials']==0 and
          r['historical_costs_proven'] is False and r['economic_edge_proven'] is False and r['hard21_proven'] is False,
          'NO_ECONOMIC_PROMOTION_'+role)
    need(p['profile']==c['profile']==m['profile'] and set(c['profile'])=={'1','2','250'},'ALL_FIXED_INSTRUMENTS')
    for key,r in c['profile'].items():
        need(r['events']==r['healthy']+r['unavailable'] and r['initial_snapshot_not_promoted'] is True and
          r['between_receipt_liquidity_proven'] is False and r['broker_fills_proven'] is False and
          r['economic_model_executed'] is False,'FULL_SOURCE_RECONCILIATION_'+key)
    need(c['native_producer_job']==m['jobs']['spot-collect'] and c['independently_redecoded_original_wire'] is True and
      c['profile_algorithm_independent'] is False and c['current_metadata_observed_not_historical_terms'] is True and
      c['entire_contact_interval_excluded_from_confirmation'] is True and
      [c['contact_start_utc'],c['contact_end_utc']]==m['contact_interval_utc'],'INDEPENDENT_COLD_NATIVE_SCOPE')
    for name in ('producer.json','cold.json'):need(read(folder/name,40000)==files[name],'BYTE_EXACT_PUBLIC_RECEIPT_'+name)
    if destination is not None:
        destination=Path(destination);need(not destination.is_symlink(),'REGULAR_DESTINATION')
        for name,data in files.items():
            path=destination/name;need(not path.is_symlink() and (not path.exists() or path.read_bytes()==data),'NO_OUTPUT_CONFLICT')
        destination.mkdir(parents=True,exist_ok=True)
        for name,data in files.items():
            path=destination/name
            if not path.exists():
                with path.open('xb') as f:f.write(data)
    return {'schema':'mxm.durable-native-spot-source-verification.v1','run_id':m['run_id'],'head':m['head'],
      'original_artifacts':{k:v['id'] for k,v in m['artifacts'].items()},'cipher_sha256':sha(files['capture.mxmenc']),
      'profile':c['profile'],'source_decrypted':False,'new_broker_requests':0,'economic_edge_proven':False,
      'hard21_proven':False,'native_robot_operational_reception_proven':False,'orders':0}
if __name__=='__main__':
    args=sys.argv[1:];need(not args or len(args)==2 and args[0]=='--out','EXACT_ARGUMENTS')
    print('MXM_DURABLE_NATIVE_SPOT '+json.dumps(verify(destination=args[1] if args else None),sort_keys=True))
