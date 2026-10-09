"""Metadata-only accepted-evidence reconciliation. No market archive opening."""
import base64,gzip,hashlib,json,os,pathlib,resource,subprocess,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
DIR=ROOT/'research_core_v4/master_frontier_v1'
REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='performance-research-v3-20260922'
def sha(b): return hashlib.sha256(b).hexdigest()
def encode(x): return (json.dumps(x,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode()
def api(path,body=None,method=None):
 req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def main():
 start=time.monotonic(); authority=json.loads((DIR/'METADATA_RECONCILIATION_AUTHORITY_V1.json').read_text()); source=os.environ['GITHUB_SHA']
 assert os.environ['GITHUB_REPOSITORY']==REPO
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==source
 assert api('git/ref/heads/'+BRANCH)['object']['sha']==source,'HEAD_CHANGED'
 claim='mxm-master1576-metadata-v1-'+source
 api('git/refs',{'ref':'refs/tags/'+claim,'sha':source}) # atomic one-use metadata invocation; not a scientific ARM
 docs={}
 for p,h in authority['inputs_sha256'].items():
  b=(ROOT/p).read_bytes();assert sha(b)==h,'SOURCE_DIGEST_MISMATCH '+p
  if p.endswith('.json'):docs[p]=json.loads(b)
 def d(name):return docs[authority['roles'][name]]
 master=d('master'); result=d('result'); roster=d('roster'); reg=d('representatives'); primary=d('primary'); corpus=d('corpus'); summary=d('summary')
 assert len(master)==1576 and len({x['symbol_id'] for x in master})==1576
 expected=[(i+1,x['symbol_id'],x['asset_class']) for i,x in enumerate(master)]
 actual=[(x['MASTER_ORDINAL'],x['SYMBOL_ID'],x['BROKER_NATIVE_CONTEXT']) for x in result['identities']]
 assert actual==expected and result['identity_count']==1576 and result['eligible_count']==1575
 eligible=[x for x in result['identities'] if x['V2_CLASSIFICATION']=='QUALIFIED_FOR_DEEP_HISTORICAL_M5']
 assert len(eligible)==1575
 triples=[(x['MASTER_ORDINAL'],x['SYMBOL_ID'],x['BROKER_NATIVE_CONTEXT']) for x in eligible]
 assert triples==[(x['MASTER_ORDINAL'],x['SYMBOL_ID'],x['BROKER_NATIVE_CONTEXT']) for x in roster['entries']]
 support=[x for x in result['identities'] if x not in eligible];assert len(support)==1 and support[0]['SYMBOL_ID']==3741 and support[0]['TOTAL_ROW_COUNT']==0 and support[0]['V2_CLASSIFICATION']=='SUPPORT_LIMITED_NOT_REJECTED'
 ids={x['symbol_id'] for x in master}; reps={x['symbol_id'] for x in reg['representatives']}; prim={x['symbol_id'] for x in primary['primary_series']}
 assert len(reps)==41 and len(prim)==145 and reps<=ids and prim<=ids
 assert primary['total_primary_M5_rows']==11406418 and result['processed_canonical_row_count']==3355389
 release=api('releases/tags/'+corpus['DURABLE_RELEASE_IDENTITY']);assets={x['name']:x for x in release['assets']}
 shards=[]
 for e in corpus['entries']:
  a=assets[e['ENCRYPTED_ASSET_NAME']];assert a['digest']=='sha256:'+e['ENCRYPTED_ASSET_SHA256']
  shards.append({k:e[k] for k in ['ENCRYPTED_ASSET_NAME','ENCRYPTED_ASSET_SHA256','PLAINTEXT_CANONICAL_SHA256','SEGMENT_INDEX','SHARD_INDEX','IDENTITY_RANGE','ROW_COUNT','REQUEST_COUNT','FIRST_TIMESTAMP','LAST_TIMESTAMP'] }|{'release_asset_id':a['id'],'encrypted_bytes':a['size']})
 assert len(shards)==100 and sum(x['ROW_COUNT'] for x in shards)==3355389 and sum(x['REQUEST_COUNT'] for x in shards)==6304
 assert result['final_manifest_sha256']==authority['inputs_sha256'][authority['roles']['corpus']]
 tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')[:-1]
 inv=[{'path':p,'sha256':sha((ROOT/p).read_bytes()),'bytes':(ROOT/p).stat().st_size} for p in tracked]
 invbytes=gzip.compress(encode({'source_commit':source,'files':inv}),mtime=0)
 membership=[]
 for m,r in zip(master,result['identities']):
  membership.append({'master_ordinal':r['MASTER_ORDINAL'],'symbol_id':m['symbol_id'],'symbol':m['symbol'],'broker_native_context':m['asset_class'],'accepted_structural_classification':r['V2_CLASSIFICATION'],'stored_row_count':r['TOTAL_ROW_COUNT'],'active_calendar_days':r['ACTIVE_CALENDAR_DAY_COUNT'],'historical_primary145':m['symbol_id'] in prim,'structural_representative41':m['symbol_id'] in reps})
 out={'schema':'mxm.master1576.metadata.reconciliation.v1','status':'CHECKS_PASS_REMOTE_PUBLICATION_REQUIRES_READBACK','source_commit':source,'historical_checkpoint':authority['checkpoint'],'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':os.environ['GITHUB_RUN_ATTEMPT'],'invocation_claim_tag':claim,'no_real_numeric_market_response':True,'no_archive_opening_or_decryption':True,'broker_requests':0,'qualification_replay':False,'source_bindings_sha256':authority['inputs_sha256'],'frontier_membership':membership,'eligible_roster_exact_order_match':True,'support_limited':membership[514],'representative41_subset':True,'primary145_subset':True,'accepted_corpus_release_tag':corpus['DURABLE_RELEASE_IDENTITY'],'encrypted_shards_verified_by_release_metadata':shards,'release_metadata_verification_not_bytes_downloaded':True,'source_inventory':{'path':'SOURCE_INVENTORY_V1.json.gz','sha256':sha(invbytes),'tracked_file_count':len(inv)},'historical_row_counts_not_recomputed':{'shallow':3355389,'primary145':11406418},'source_snapshot_resource_use':{'elapsed_seconds_before_publication':time.monotonic()-start,'process_cpu_seconds':time.process_time(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},'scientific_status':'METADATA_JOIN_ONLY_NO_NEW_EDGE_OR_POWER_EVIDENCE'}
 assert time.monotonic()-start<120,'RESOURCE_BUDGET'; assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<524288,'MEMORY_BUDGET'
 outputs={'research_core_v4/master_frontier_v1/MACHINE_METADATA_RECONCILIATION_RESULT_V1.json':encode(out),'research_core_v4/master_frontier_v1/SOURCE_INVENTORY_V1.json.gz':invbytes}
 entries=[]
 for p,b in outputs.items():
  (ROOT/p).write_bytes(b)
  blob=api('git/blobs',{'encoding':'base64','content':base64.b64encode(b).decode()})
  entries.append({'path':p,'mode':'100644','type':'blob','sha':blob['sha']})
 assert api('git/ref/heads/'+BRANCH)['object']['sha']==source,'HEAD_CHANGED_BEFORE_PUBLICATION'
 tree=api('git/trees',{'base_tree':api('git/commits/'+source)['tree']['sha'],'tree':entries})
 commit=api('git/commits',{'message':'Persist MASTER1576 metadata-only reconciliation [skip ci]','tree':tree['sha'],'parents':[source]})
 api('git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False},'PATCH')
 for p,b in outputs.items():
  obj=api('contents/'+p+'?ref='+commit['sha']);read=base64.b64decode(obj['content']);assert sha(read)==sha(b),'READBACK_MISMATCH'
 receipt={'status':'PASS_WITH_EXACT_REMOTE_READBACK','publication_commit':commit['sha'],'output_sha256':{p:sha(b) for p,b in outputs.items()},'total_elapsed_seconds':time.monotonic()-start,'cpu_seconds':time.process_time(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 (DIR/'RUN_READBACK_RECEIPT_V1.json').write_bytes(encode(receipt));print(json.dumps(receipt,sort_keys=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  (DIR/'RUN_FAILURE_V1.json').write_bytes(encode({'status':'NOT_PERSISTED_OR_NOT_VERIFIED','failure_class':type(e).__name__,'message':str(e)[:300]}));raise
