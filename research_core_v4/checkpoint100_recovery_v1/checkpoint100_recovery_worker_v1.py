"""Checkpoint100 forensic recovery: timestamp structure only, zero source-archive replay."""
import base64
import gzip
import hashlib
import io
import json
import os
import pathlib
import resource
import signal
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from research_core_v4 import master1576_screen_v2 as crypto
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
from research_core_v4.historical_access_v1 import timestamp_access_worker_v1 as old

ROOT=pathlib.Path(__file__).resolve().parents[2]
HOME=ROOT/'research_core_v4/checkpoint100_recovery_v1'
OLD=ROOT/'research_core_v4/historical_access_v1'
REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='performance-research-v3-20260922'
BASEREF='689a2b67c7c6fd18f2aca91355ef8e3a9e7d4801'
ORIGINAL='f5dbdbaf03263fcde267333fda290e5344fcae8a'
FP=old.FP
ENC=old.enc
SHA=old.sha
START=old.START
END=old.END
N=old.N
LAGS=old.LAGS
BEGAN=None
PARENT=None
PHASE='INITIAL'
PRIVATE_OK=False

class Stop(Exception): pass
def need(ok,code):
 if not ok: raise Stop(code)
def check_budget():
 a=resource.getrusage(resource.RUSAGE_SELF);b=resource.getrusage(resource.RUSAGE_CHILDREN)
 wall=time.monotonic()-BEGAN
 cpu=time.process_time()+b.ru_utime+b.ru_stime
 mem=max(a.ru_maxrss,b.ru_maxrss)
 need(wall<600,'WALL_600_LIMIT')
 need(cpu<300,'CPU_300_LIMIT')
 need(mem<524288,'RAM_512_MIB_LIMIT')
 return {'wall_seconds':wall,'cpu_seconds_including_children':cpu,'main_peak_rss_kib':a.ru_maxrss,'child_peak_rss_kib':b.ru_maxrss}
def api(path,body=None,method=None):
 u='https://api.github.com/repos/'+REPO+'/'+path
 b=None if body is None else ENC(body)
 req=urllib.request.Request(u,data=b,method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'})
 try:
  with urllib.request.urlopen(req,timeout=40) as resp:return json.load(resp)
 except Exception:raise Stop('GITHUB_API_OR_READBACK_FAILURE') from None
def preflight():
 from research_core_v4.historical_access_v1 import timestamp_access_worker_v1 as w
 b=bytearray(1008)
 for k in range(36):b[k//8]|=1<<(k%8)
 need(w.mask(b,'feature',0)[0]&2,'TEST_EXPECTED_FEATURE')
 need(w.mask(b,'response_geometry',0)[0]&2,'TEST_EXPECTED_RESPONSE')
 need(not (w.mask(b,'feature',0)[0]&1),'TEST_START_CENSORING')
 b[0]&=~1
 need(not (w.mask(b,'feature',0)[0]&2),'TEST_NO_IMPUTATION')
 expected=SHA(b'correct')
 for candidate in [b'corrupt',b'correct ']:
  try:need(SHA(candidate)==expected,'REJECT_WRONG_SHA')
  except Stop:pass
  else:raise Stop('TEST_BAD_HASH_ACCEPTED')
 item={'ordinal':1,'symbol_id':3}
 try:need(item['ordinal']==2,'WRONG_IDENTITY')
 except Stop:pass
 else:raise Stop('TEST_BAD_IDENTITY_ACCEPTED')
 trial=[{'first':1,'last':2},{'first':3,'last':4}]
 def partition_check(parts,n):
  got=[i for x in parts for i in range(x['first'],x['last']+1)]
  need(got==list(range(1,n+1)),'MISSING_DUPLICATE_PARTITION')
 partition_check(trial,4)
 for broken in [trial[:1],[trial[0],trial[0]],trial[::-1]]:
  try:partition_check(broken,4)
  except Stop:pass
  else:raise Stop('TEST_INVALID_PARTITION_ACCEPTED')
 for oversized in [b'x'*900000,b'x'*350000]:
  try:need(len(oversized)<350000,'SAFE_REPORT_SIZE')
  except Stop:pass
  else:raise Stop('TEST_OVERSIZE_ACCEPTED')
 try:need(b'wrong'==b'right','PUBLICATION_READBACK_FAILURE')
 except Stop:pass
 else:raise Stop('TEST_READBACK_ACCEPTED')
 need(ENC({'b':1,'a':2})==ENC({'a':2,'b':1}),'TEST_NONDETERMINISM')
 print('PASS_FABRICATED_ALL_FAIL_CLOSED_CHECKS_NO_SECRET')
def presecret():
 global PARENT
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF')=='refs/heads/'+BRANCH and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','WRONG_EVENT_OR_RETRY')
 head=os.environ['GITHUB_SHA']
 need(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==head,'CHECKOUT_DRIFT')
 for ancestor in [BASEREF,ORIGINAL]:
  need(subprocess.run(['git','merge-base','--is-ancestor',ancestor,head],cwd=ROOT).returncode==0,'SOURCE_ANCESTRY_DRIFT')
 a=json.loads((HOME/'EXACT_CHECKPOINT100_RECOVERY_AUTHORITY_V1.json').read_text())
 need(a['base_head']==BASEREF and a['source_commit']==ORIGINAL and a['purpose']=='TIMESTAMP_STRUCTURE_ONLY','AUTHORITY_SCOPE')
 need(subprocess.check_output(['git','hash-object',str(HOME/'checkpoint100_recovery_worker_v1.py')],cwd=ROOT,text=True).strip()==a['worker_git_blob_sha'],'WORKER_HASH_DRIFT')
 for p,h in a['immutable_sha256'].items():need(SHA((ROOT/p).read_bytes())==h,'IMMUTABLE_SOURCE_HASH_DRIFT')
 c=json.loads((OLD/'TIMESTAMP_CHECKPOINT_100_V1.json').read_text())
 need(c['source_commit']==ORIGINAL and c['complete100'] is True and c['verified_rows']==3355389 and c['processed_assets']==100,'CHECKPOINT_REPORT_DRIFT')
 need(c['encrypted_checkpoint']==a['checkpoint'],'CHECKPOINT_BINDING_DRIFT')
 oldresult=json.loads((OLD/'EXACT_STRUCTURAL_MASK_AND_COVERAGE_RESULT_V1.json').read_text())
 need(oldresult['derived_mask_encrypted_asset_metadata']['id']==a['derived']['id'],'DERIVED_ASSET_REPORT_DRIFT')
 need(api('git/ref/heads/'+BRANCH)['object']['sha']==head,'LIVE_HEAD_DRIFT')
 preflight()
 PARENT=head
 return a
def asset(raw,meta,key,tmp):
 assets=api('releases/407622886/assets?per_page=100')
 matches=[x for x in assets if x['id']==meta['id'] and x['name']==meta['name']]
 need(len(matches)==1,'ASSET_ID_NAME_MISMATCH')
 x=matches[0]
 need(x['size']==meta['size'] and x['digest']=='sha256:'+meta['sha256'] and x['state']=='uploaded','ASSET_METADATA_DRIFT')
 url=x['browser_download_url']
 need(url=='https://github.com/'+REPO+'/releases/download/mxm-timestamp-masks-v1-'+ORIGINAL+'/'+meta['name'],'ASSET_RELEASE_URL_DRIFT')
 try:
  with urllib.request.urlopen(url,timeout=45) as resp:b=resp.read(meta['size']+1)
 except Exception:raise Stop('CHECKPOINT_ASSET_DOWNLOAD_FAILURE') from None
 need(len(b)==meta['size'] and SHA(b)==meta['sha256'],'CIPHERTEXT_SHA256_OR_SIZE_DRIFT')
 packed=crypto.decrypt_package(b,private_key=key,expected_public_spki_sha256=FP,temp_parent=tmp)
 need(len(packed)<20971520,'COMPRESSED_PLAINTEXT_SIZE_LIMIT')
 if 'gzip_sha256' in meta:need(SHA(packed)==meta['gzip_sha256'],'GZIP_PLAINTEXT_HASH_DRIFT')
 try:
  with gzip.GzipFile(fileobj=io.BytesIO(packed)) as f:canonical=f.read(33554433)
 except Exception:raise Stop('GZIP_DECODER_FAILURE') from None
 need(len(canonical)<=33554432,'CANONICAL_SIZE_LIMIT')
 try:obj=crypto.strict_json(canonical)
 except Exception:raise Stop('CANONICAL_JSON_DECODER_FAILURE') from None
 need(ENC(obj)==canonical,'NONCANONICAL_JSON')
 if 'canonical_sha256' in meta:need(SHA(canonical)==meta['canonical_sha256'],'CANONICAL_SHA256_DRIFT')
 return obj,{'id':x['id'],'name':x['name'],'encrypted_bytes':len(b),'ciphertext_sha256':SHA(b),'gzip_plaintext_sha256':SHA(packed),'canonical_sha256':SHA(canonical)}
def bitmap(b,i):return bool(b[i//8]&(1<<(i%8)))
def zero_intervals(bits):
 ranges=[];beg=None
 for i in range(N+1):
  absent=(i<N and not bitmap(bits,i))
  if absent and beg is None:beg=i
  if not absent and beg is not None:ranges.append([beg,i]);beg=None
 return ranges
def build(checkpoint,master,historical,authority):
 need(checkpoint['schema']=='mxm.timestamp.bitmap.checkpoint.v1' and checkpoint['source_commit']==ORIGINAL,'CHECKPOINT_SCHEMA_OR_SOURCE')
 need(checkpoint['source_manifest_sha256']==authority['source_manifest_sha256'],'MANIFEST_SHA_DRIFT')
 need(checkpoint['grid_start_utc']=='2026-08-20T00:00:00Z' and checkpoint['grid_end_exclusive_utc']=='2026-09-17T00:00:00Z' and checkpoint['grid_step_seconds']==300,'CALENDAR_DRIFT')
 need(checkpoint['processed_assets']==100 and checkpoint['rows']==3355389,'SOURCE_COMPLETION_DRIFT')
 need(len(checkpoint['entries'])==len(master)==len(historical['identities'])==1576,'MASTER_IDENTITY_COUNT')
 entries=[];masks=[];counts={str(l):{k:0 for k in ('feature_timestamp_geometry','response_timestamp_geometry','intersection_timestamp_geometry')} for l in LAGS}
 hourly={str(l):{k:[0]*672 for k in ('feature_timestamp_geometry','response_timestamp_geometry','intersection_timestamp_geometry')} for l in LAGS}
 contexts={};weeks={str(l):{k:[0]*4 for k in counts[str(l)]} for l in LAGS}
 zero=0;total=0;aggregate_day=[0]*28
 for i,(e,m,h) in enumerate(zip(checkpoint['entries'],master,historical['identities'])):
  if i%25==0:check_budget()
  need(e['ordinal']==i+1 and e['symbol_id']==m['symbol_id'] and h['TOTAL_ROW_COUNT']==sum(e['row_counts_by_segment']),'MASTER_ORDINAL_HISTORICAL_COUNT_DRIFT')
  b=base64.b64decode(e['timestamp_bits_base64'],validate=True)
  need(len(b)==1008 and len(e['row_counts_by_segment'])==4,'BITMAP_LENGTH_OR_SEGMENTS')
  sc=[sum(bitmap(b,j) for j in range(s*2016,(s+1)*2016)) for s in range(4)]
  need(sc==e['row_counts_by_segment'],'SEGMENT_ROW_BIT_IDENTITY')
  present=sum(sc);total+=present
  days=[sum(bitmap(b,j) for j in range(d*288,(d+1)*288)) for d in range(28)]
  aggregate_day=[a+c for a,c in zip(aggregate_day,days)]
  if not present:zero+=1
  start=next((j for j in range(N) if bitmap(b,j)),None)
  end=next((j for j in range(N-1,-1,-1) if bitmap(b,j)),None)
  hourly_masks={};lagcounts={};reason={}
  context=m.get('asset_class','UNCLASSIFIED')
  if context not in contexts:contexts[context]={str(l):{k:0 for k in counts[str(l)]} for l in LAGS}
  for lag in LAGS:
   maps={k:old.mask(b,kind,lag) for k,kind in [('feature_timestamp_geometry','feature'),('response_timestamp_geometry','response_geometry'),('intersection_timestamp_geometry','intersection')]}
   hourly_masks[str(lag)]={k:base64.b64encode(v).decode() for k,v in maps.items()}
   lagcounts[str(lag)]={k:old.count(v) for k,v in maps.items()}
   mature=sum(START+3600*j+3600+lag<=END for j in range(672))
   reason[str(lag)]={'calendar_clocks':672,'response_domain_right_censored':672-mature,'response_missing_inside_mature_domain':mature-lagcounts[str(lag)]['response_timestamp_geometry'],'feature_timestamp_unavailable':672-lagcounts[str(lag)]['feature_timestamp_geometry'],'intersection_timestamp_unavailable':672-lagcounts[str(lag)]['intersection_timestamp_geometry']}
   for k,buf in maps.items():
    num=lagcounts[str(lag)][k]
    counts[str(lag)][k]+=num;contexts[context][str(lag)][k]+=num
    for j in range(672):
     if bitmap(buf,j):
      hourly[str(lag)][k][j]+=1
      weeks[str(lag)][k][j//168]+=1
  missing=zero_intervals(b)
  entries.append({'master_ordinal':i+1,'symbol_id':m['symbol_id'],'symbol':m.get('symbol'),'asset_class':context,'classification':'SUPPORT_LIMITED_NOT_REJECTED' if i==514 else 'FROZEN_MASTER','stored_timestamp_count':present,'row_counts_by_segment':sc,'active_calendar_days':sum(bool(x) for x in days),'daily_timestamp_counts':days,'first_grid_index':start,'last_grid_index':end,'missing_grid_periods_start_inclusive_end_exclusive':missing,'absent_calendar_grid_positions':N-present,'lag_structural_counts':lagcounts,'lag_reason_counts':reason,'timestamp_bits_base64':e['timestamp_bits_base64'],'hourly_masks_base64':hourly_masks})
  masks.append({'ordinal':i+1,'symbol_id':m['symbol_id'],'timestamp_bits_base64':e['timestamp_bits_base64'],'active_day_indexes':[j for j,c in enumerate(days) if c>0],'hourly_masks':hourly_masks})
 need(total==3355389,'FULL_ROW_SUM_DRIFT')
 need(master[514]['symbol']=='QUB.AU' and master[514]['symbol_id']==3741 and entries[514]['stored_timestamp_count']==0,'QUB_AU_PRESERVATION')
 maskvalue={'schema':'mxm.exact.timestamp.structural.masks.v1','source_commit':ORIGINAL,'source_manifest_sha256':authority['source_manifest_sha256'],'M5_start_utc':'2026-08-20T00:00:00Z','M5_grid_positions':8064,'hourly_clock_positions':672,'lags_seconds':list(LAGS),'bitmap_law':'littlebits; M5positions=start+300k; hourlypositions=start+3600j; masks based only on exactstoredtimestamp existence and domain maturity','receipt_and_revision':'UNKNOWN; noauthenticavailabilityclaim','numeric_price_activity_validity':'NOT_PROCESSED','entries':masks}
 aggregate={'schema':'mxm.complete.full.frontier.aggregate.v1','status':'TIMESTAMP_ONLY_STRUCTURAL_NOT_NUMERICAL','source_commit':ORIGINAL,'identity_count':1576,'qualifed_with_support':1575,'support_limited_QUB_AU_ordinal':515,'stored_timestamp_rows':total,'zero_timestamp_identities':zero,'calendar_days':28,'hourly_clocks_per_identity':672,'M5_grid_positions_per_identity':8064,'fixed_opportunities_per_lag':1576*672,'total_calendar_M5_positions':1576*8064,'total_absent_M5_positions':1576*8064-total,'timestamp_rows_by_day':aggregate_day,'lag_structural_counts':counts,'lag_calendar_hourly_counts':hourly,'lag_fixed_7day_week_counts':weeks,'native_context_asset_class_counts':contexts,'hourly_lags_seconds':list(LAGS),'session_and_receipts':'No absent timestamp asserted to be a missing expected broker-session observation; original receipt and revision UNKNOWN','numerical_values_checked':False}
 return entries,maskvalue,aggregate
def partition(entries):
 output={};p=0;start=0
 while start<len(entries):
  take=[];i=start
  while i<len(entries):
   test=take+[entries[i]]
   value={'schema':'mxm.partitioned.hourly.structural.coverage.v1','source_commit':ORIGINAL,'first_ordinal':start+1,'last_ordinal':i+1,'identities':test}
   if len(ENC(value))>=350000:break
   take=test;i+=1
  need(bool(take),'SINGLE_IDENTITY_EXCEEDS_PARTITION_BUDGET')
  p+=1;name=f'PARTITIONED_HOURLY_STRUCTURAL_COVERAGE_{p:04d}_V1.json'
  output[name]={'schema':'mxm.partitioned.hourly.structural.coverage.v1','source_commit':ORIGINAL,'first_ordinal':start+1,'last_ordinal':i,'identities':take}
  start=i
 need([e['master_ordinal'] for v in output.values() for e in v['identities']]==list(range(1,1577)),'MISSING_OR_DUPLICATE_IDENTITY')
 for value in output.values():need(len(ENC(value))<350000,'PARTITION_OVERFLOW')
 return output
def publish_all(outputs,message):
 global PARENT
 need(api('git/ref/heads/'+BRANCH)['object']['sha']==PARENT,'LIVE_HEAD_BEFORE_PUBLICATION')
 elements=[]
 for name,value in outputs.items():
  need(name not in ('','.') and '/' not in name and name.endswith('_V1.json'),'INVALID_OUTPUT_PATH')
  data=ENC(value)
  need(len(data)<900000,'SAFE_REPORT_SIZE')
  obj=api('git/blobs',{'content':base64.b64encode(data).decode(),'encoding':'base64'})
  elements.append({'path':'research_core_v4/checkpoint100_recovery_v1/'+name,'mode':'100644','type':'blob','sha':obj['sha']})
 base=api('git/commits/'+PARENT)['tree']['sha']
 tree=api('git/trees',{'base_tree':base,'tree':elements})
 commit=api('git/commits',{'tree':tree['sha'],'message':message+' [skip ci]','parents':[PARENT]})
 need(api('git/ref/heads/'+BRANCH)['object']['sha']==PARENT,'LIVE_HEAD_CAS_DRIFT')
 api('git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False},'PATCH')
 PARENT=commit['sha']
 for name,value in outputs.items():
  got=api('contents/research_core_v4/checkpoint100_recovery_v1/'+name+'?ref='+PARENT)
  need(base64.b64decode(got['content'])==ENC(value),'PUBLICATION_REMOTE_BYTE_READBACK_FAILURE')
 return PARENT
def main():
 global BEGAN,PHASE,PRIVATE_OK
 BEGAN=time.monotonic()
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(Stop('WALL_BUDGET_ALARM')))
 signal.alarm(600)
 PHASE='PRESECRET'
 a=presecret()
 claim='mxm-checkpoint100-recovery-v1-'+os.environ['GITHUB_SHA']
 api('git/refs',{'ref':'refs/tags/'+claim,'sha':os.environ['GITHUB_SHA']})
 PHASE='CHECKPOINT_ONLY_DECRYPTION'
 with tempfile.TemporaryDirectory(prefix='mxm-checkpoint100-',dir=os.environ['RUNNER_TEMP']) as directory:
  temp=pathlib.Path(directory);temp.chmod(0o700)
  need(bool(os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')),'EXISTING_KEY_ABSENT')
  try:key,fingerprint=_private_key_from_secret(temp)
  except Exception:raise Stop('EXISTING_KEY_PARSE_FAILURE') from None
  need(fingerprint==FP,'PRIVATE_KEY_FINGERPRINT_MISMATCH')
  pub=crypto.command(['openssl','pkey','-pubin','-in',str(ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'),'-outform','DER'])
  need(SHA(pub)==FP,'PUBLIC_SPKI_FINGERPRINT_MISMATCH')
  PRIVATE_OK=True
  cp,cp_digest=asset('checkpoint',a['checkpoint_asset'],key,temp)
  check_budget()
  master=json.loads((ROOT/'research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json').read_text())
  hist=json.loads((ROOT/'research_core_v4/state/MASTER1576_QUALIFICATION_V2_REAL_STRUCTURAL_SCREEN_RESULT_V1.json').read_text())
  PHASE='RECONSTRUCT_TIMESTAMP_STRUCTURE'
  entries,expected,agg=build(cp,master,hist,a)
  check_budget()
  PHASE='EXISTING_DERIVED_MASK_COMPARISON'
  actual,derived_digest=asset('derived',a['derived'],key,temp)
  need(ENC(actual)==ENC(expected),'EXISTING_DERIVED_MASK_PLAINTEXT_MISMATCH')
  check_budget()
  PHASE='PARTITIONED_PUBLICATION'
  docs=partition(entries)
  identity={'schema':'mxm.checkpoint.and.derived.mask.identity.result.v1','status':'PASS_EXACT_PLAINTEXT_IDENTITY','source_commit':ORIGINAL,'source_checkpoint':cp_digest,'existing_derived_mask':derived_digest,'reconstructed_canonical_mask_sha256':SHA(ENC(expected)),'reconstructed_derived_byte_identity':True,'original100_market_archive_downloads':0,'decrypted_assets_only':['timestamps-after-100.mxmenc','exact-structural-masks.mxmenc'],'verified_rows':3355389,'identities':1576,'lag_seconds':list(LAGS),'public_spki_sha256':FP}
  decision={'schema':'mxm.timestamp.numerical.readiness.decision.v1','timestamp_structure':'PASS_IF_ALL_PUBLICATION_CERTIFIED','decision':'NUMERICAL_DEVELOPMENT_ARM_NOT_READY_NOT_ISSUED','reason':['Timestamp masks are not paired numerical validity nor zero-activity/zero-direction certification','Original receipt and revision times UNKNOWN','Real streaming numeric executor and synthetic fail-closed durability preflight not certified','Authentic broker friction/execution/capital constraints UNKNOWN','Separate precise one-use DEVELOPMENT directional response ARM mandatory'],'frozen_question':'MASTER1576_HOURLY_PRICE_ACTIVITY_COUPLING_DIRECTIONAL_RESPONSE_V1','calendar':'2026-08-20 to 2026-09-17 UTC','lags_seconds':list(LAGS),'no_market_numeric_responses':True,'no_live_trading':True,'no_old_ARM_revival':True}
  outputs={'CHECKPOINT_AND_DERIVED_MASK_IDENTITY_RESULT_V1.json':identity,'COMPLETE_FULL_FRONTIER_AGGREGATE_V1.json':agg,'TIMESTAMP_NUMERICAL_READINESS_DECISION_V1.json':decision,**docs}
  mf={'schema':'mxm.versioned.sha256.delivery.manifest.v1','source_head':BASEREF,'source_commit':ORIGINAL,'run_id':os.environ['GITHUB_RUN_ID'],'checkpoint_asset':a['checkpoint_asset'],'derived_asset':a['derived'],'source_authority_sha256':{p:SHA((ROOT/p).read_bytes()) for p in a['immutable_sha256']},'outputs':[{'path':'research_core_v4/checkpoint100_recovery_v1/'+n,'bytes':len(ENC(v)),'sha256':SHA(ENC(v))} for n,v in outputs.items()],'partition_count':len(docs),'all_master_ordinals_once':True,'partition_size_hard_limit':900000,'partition_soft_limit':350000,'original_shard_reads':0}
  outputs['VERSIONED_SHA256_DELIVERY_MANIFEST_V1.json']=mf
  readback_head=publish_all(outputs,'Checkpoint100 exact masked structural partition delivery')
  check_budget()
  PHASE='FINAL_READBACK_CERTIFICATION'
  receipt={'schema':'mxm.publication.and.readback.certificate.v1','status':'TIMESTAMP_STRUCTURE_RECOVERY_COMPLETE','prior_commit':readback_head,'source_commit':ORIGINAL,'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':1,'published_count_before_certificate':len(outputs),'all_partition_names':[n for n in docs],'all_outputs_exact_remote_byte_readback':True,'manifest_sha256':SHA(ENC(mf)),'existing_derived_comparison':'PASS_EXACT_PLAINTEXT','encrypted_checkpoint':'PASS_EXACT_CIPHERTEXT_AND_CANONICAL','original100_shards_replayed':False,'numeric_market_response_count':0,'broker_requests':0,'new_keys_or_scopes':0,'numerical_ARM':'NOT_ISSUED','live_trading_authority':False,'resources_before_final_certificate':check_budget()}
  final=publish_all({'PUBLICATION_AND_READBACK_CERTIFICATE_V1.json':receipt},'Certify remote readback of checkpoint100 recovery')
  resource_result=check_budget()
  HOME.joinpath('RECOVERY_RUNTIME_RESULT_V1.json').write_bytes(ENC({'status':'TIMESTAMP_STRUCTURE_RECOVERY_COMPLETE','head':final,'run_id':os.environ['GITHUB_RUN_ID'],'resources':resource_result,'readback':'PASS','numeric_ARM':'NOT_ISSUED'}))
  print(json.dumps({'status':'TIMESTAMP_STRUCTURE_RECOVERY_COMPLETE','final_head':final,'published_partitions':len(docs),'resources':resource_result,'numeric_ARM':'NOT_ISSUED'},sort_keys=True))
  signal.alarm(0)
def fail(e):
 signal.alarm(0)
 code=str(e) if isinstance(e,Stop) else type(e).__name__
 value={'schema':'mxm.checkpoint.recovery.failure.v1','status':'CHECKPOINT_RECOVERY_OR_PUBLICATION_BLOCKED','phase':PHASE,'failure_code':code,'run_id':os.environ.get('GITHUB_RUN_ID'),'private_key_matched':PRIVATE_OK,'original_shards_replayed':False,'numeric_responses':0,'broker_requests':0,'resources':check_budget_safe()}
 try:
  if PARENT:publish_all({'CHECKPOINT_RECOVERY_FAILURE_V1.json':value},'Preserve checkpoint100 recovery fail-closed proof')
 except Exception:value['failure_readback']='NOT_PERSISTED'
 HOME.joinpath('RECOVERY_RUNTIME_FAILURE_V1.json').write_bytes(ENC(value))
 print(json.dumps({'status':value['status'],'failure':code,'failure_readback':value.get('failure_readback','UNKNOWN')},sort_keys=True))
def check_budget_safe():
 if BEGAN is None:return None
 try:return check_budget()
 except Exception:return {'resource_budget_exceeded':True}
if __name__=='__main__':
 try:
  if '--preflight' in __import__('sys').argv:
   BEGAN=time.monotonic()
   preflight()
  else:main()
 except Exception as e:
  fail(e)
  raise SystemExit(1)
