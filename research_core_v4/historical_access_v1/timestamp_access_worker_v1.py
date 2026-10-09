"""Standing-scope one-invocation historical access. Timestamp structure only.
No numerical feature, direction, return, label value, PnL or broker operation.
"""
import base64,gzip,hashlib,json,os,pathlib,resource,signal,subprocess,tempfile,time,urllib.request
from datetime import datetime,timezone
from research_core_v4 import master1576_screen_v2 as crypto
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
ROOT=pathlib.Path(__file__).resolve().parents[2];DIR=ROOT/'research_core_v4/historical_access_v1'
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='performance-research-v3-20260922'
START=int(datetime(2026,8,20,tzinfo=timezone.utc).timestamp());END=START+28*86400
N=8064;LAGS=(0,300,900);FP='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
PARENT=None;SOURCE=None;RELEASE=None;BEGAN=None;CHECKPOINTS=[];VERIFIED=[];KEY_READY=False;PHASE='PRESECRET'
class Failure(Exception):
 def __init__(self,code):self.code=code;super().__init__(code)
def need(x,c):
 if not x:raise Failure(c)
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def api(path,body=None,method=None):
 req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,data=None if body is None else enc(body),method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'})
 try:
  with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
 except Exception:raise Failure('GITHUB_CONTROL_API_FAILURE') from None
def resource_state():
 c=resource.getrusage(resource.RUSAGE_CHILDREN);s=resource.getrusage(resource.RUSAGE_SELF)
 return {'wall_seconds':time.monotonic()-BEGAN,'cpu_seconds_including_children':time.process_time()+c.ru_utime+c.ru_stime,'main_peak_rss_kib':s.ru_maxrss,'child_peak_rss_kib':c.ru_maxrss}
def budget():
 r=resource_state();need(r['wall_seconds']<1800,'WALL_BUDGET');need(r['cpu_seconds_including_children']<900,'CPU_BUDGET');need(max(r['main_peak_rss_kib'],r['child_peak_rss_kib'])<1048576,'MEMORY_BUDGET')
def publish(outputs,message):
 global PARENT
 need(api('git/ref/heads/'+BRANCH)['object']['sha']==PARENT,'LIVE_HEAD_DRIFT')
 elements=[]
 for name,value in outputs.items():
  need(name.endswith('_V1.json') and '/' not in name,'OUTPUT_PATH')
  p='research_core_v4/historical_access_v1/'+name;b=enc(value);need(len(b)<900000,'SAFE_REPORT_SIZE')
  (ROOT/p).write_bytes(b);blob=api('git/blobs',{'encoding':'base64','content':base64.b64encode(b).decode()});elements.append({'path':p,'mode':'100644','type':'blob','sha':blob['sha']})
 tree=api('git/trees',{'base_tree':api('git/commits/'+PARENT)['tree']['sha'],'tree':elements});commit=api('git/commits',{'message':message+' [skip ci]','tree':tree['sha'],'parents':[PARENT]})
 need(api('git/ref/heads/'+BRANCH)['object']['sha']==PARENT,'PUBLICATION_PARENT_DRIFT');api('git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False},'PATCH');PARENT=commit['sha']
 for name,value in outputs.items():
  p='research_core_v4/historical_access_v1/'+name;got=api('contents/'+p+'?ref='+PARENT);need(base64.b64decode(got['content'])==enc(value),'PUBLICATION_READBACK_FAILURE')
 return PARENT

def download(url,maxbytes):
 need(url.startswith('https://github.com/'+REPO+'/releases/download/'),'ASSET_URL_SCOPE')
 try:
  with urllib.request.urlopen(url,timeout=60) as r:b=r.read(maxbytes+1)
 except Exception:raise Failure('ASSET_DOWNLOAD_FAILURE') from None
 need(len(b)<=maxbytes,'ASSET_SIZE_LIMIT');return b

def store_encrypted(value,name,key,tmp):
 need(name.endswith('.mxmenc') and '/' not in name,'ENCRYPTED_OUTPUT_NAME')
 packed=gzip.compress(enc(value),mtime=0);need(len(packed)<20971520,'ENCRYPTED_OUTPUT_BUDGET')
 p=tmp/name;info=encrypt_shard(packed,public_key=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem',output=p);b=p.read_bytes()
 url='https://uploads.github.com/repos/'+REPO+'/releases/'+str(RELEASE['id'])+'/assets?name='+name
 req=urllib.request.Request(url,data=b,method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':'application/octet-stream','Accept':'application/vnd.github+json'})
 try:
  with urllib.request.urlopen(req,timeout=60) as r:a=json.load(r)
 except Exception:raise Failure('ENCRYPTED_UPLOAD_FAILURE') from None
 got=download(a['browser_download_url'],len(b));need(got==b,'ENCRYPTED_REMOTE_BYTE_READBACK_FAILURE')
 plain=crypto.decrypt_package(got,private_key=key,expected_public_spki_sha256=FP,temp_parent=tmp);need(plain==packed,'ENCRYPTED_REMOTE_PLAINTEXT_READBACK_FAILURE')
 p.unlink();return {'release_id':RELEASE['id'],'release_tag':RELEASE['tag_name'],'asset_id':a['id'],'asset_name':name,'encrypted_bytes':len(b),'ciphertext_sha256':sha(b),'gzip_plaintext_sha256':sha(packed),'canonical_mask_sha256':sha(enc(value)),'remote_ciphertext_and_decrypted_readback':'PASS'}

def has(bits,index):return 0<=index<N and bool(bits[index//8]&(1<<(index%8)))
def mask(bits,kind,lag):
 out=bytearray(84)
 for j in range(672):
  t=START+3600*j;q=t-lag;hour=q//3600*3600-3600
  feature=set(range((hour-START)//300,(hour-START)//300+12))|{(q-START)//300-1}
  response=range(j*12-1,j*12+12)
  f=all(has(bits,x) for x in feature);r=(t+3600+lag<=END and all(has(bits,x) for x in response))
  ok=f if kind=='feature' else r if kind=='response_geometry' else f and r
  if ok:out[j//8]|=1<<(j%8)
 return bytes(out)
def count(b):return sum(x.bit_count() for x in b)
def presecret(root):
 a=json.loads((DIR/'TIMESTAMP_ONLY_ACCESS_INVOCATION_V1.json').read_text())
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF')=='refs/heads/'+BRANCH and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','EVENT_OR_RETRY_DENIED')
 head=os.environ.get('GITHUB_SHA');need(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==head,'CHECKOUT_HEAD')
 for p,h in a['bindings_sha256'].items():need(sha((ROOT/p).read_bytes())==h,'SOURCE_HASH_DRIFT')
 need(api('git/ref/heads/'+BRANCH)['object']['sha']==head,'LIVE_HEAD_DRIFT')
 # Small manufactured timestamp-only semantic checks, no price/volume values.
 b=bytearray(N//8)
 for k in range(36):b[k//8]|=1<<(k%8)
 need(not has(b,-1) and not has(b,N),'MASK_BOUNDARY_FAULT')
 need(mask(b,'feature',0)[0]&2 and mask(b,'response_geometry',0)[0]&2,'MASK_KNOWN_HOUR')
 need(not(mask(b,'feature',0)[0]&1),'NO_PREWINDOW_FILL')
 b[0]&=~1;need(not(mask(b,'feature',0)[0]&2),'MISSING_TIMESTAMP_NOT_IMPUTED')
 return a,head

def consume(raw,e,master,bits,counts,lasts):
 need(sha(raw)==e['PLAINTEXT_CANONICAL_SHA256'],'PLAINTEXT_SHA256_FAILURE');obj=crypto.strict_json(raw);need(crypto.canonical(obj)==raw,'NONCANONICAL_PLAINTEXT')
 need(set(obj)==crypto.PACKAGE_KEYS and obj['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1','PACKAGE_SCHEMA')
 s=e['SEGMENT_INDEX'];k=e['SHARD_INDEX'];lo=k*64+1;hi=min(1576,lo+63)
 need(obj['segment_index']==s and obj['shard_index']==k and obj['identity_range']==e['IDENTITY_RANGE']==[lo,hi],'PACKAGE_IDENTITY')
 need(isinstance(obj['items'],list) and len(obj['items'])==hi-lo+1,'ITEM_COUNT')
 total=0;requests=0;first=None;last=None
 seglo=(s-1)*2016;seghi=s*2016
 for ordinal,item in zip(range(lo,hi+1),obj['items']):
  need(isinstance(item,dict) and set(item)==crypto.ITEM_KEYS and item['ordinal']==ordinal and item['symbol_id']==master[ordinal-1]['symbol_id'],'ITEM_IDENTITY')
  need(item['failure'] is None and item['retry_count']==0 and item['page_cap_hits']==0 and type(item['request_count']) is int and item['request_count']>=1 and isinstance(item['transport_geometry_pages'],list),'ACQUISITION_STRUCTURE')
  rows=item['rows'];need(isinstance(rows,list) and item['classification']==('SHALLOW_SUPPORT_COMPLETE' if rows else 'NO_HISTORICAL_SUPPORT'),'ROW_CONTAINER')
  previous=-1
  for row in rows:
   need(isinstance(row,dict) and set(row)==crypto.ROW_KEYS,'ROW_SCHEMA')
   # Intentionally read only time_utc. No numeric OHLC/tick_volume value inspected.
   ts=crypto.timestamp(row['time_utc']);need(START<=ts<END and (ts-START)%300==0,'TIMESTAMP_DOMAIN_OR_GRID');index=(ts-START)//300
   need(seglo<=index<seghi and index>previous and not has(bits[ordinal-1],index) and index>lasts[ordinal-1],'DUPLICATE_OR_NONMONOTONE_TIMESTAMP')
   bits[ordinal-1][index//8]|=1<<(index%8);previous=index;lasts[ordinal-1]=index;counts[ordinal-1][s-1]+=1;total+=1
   first=min(first or row['time_utc'],row['time_utc']);last=max(last or row['time_utc'],row['time_utc'])
  requests+=item['request_count']
 need(total==e['ROW_COUNT'] and requests==e['REQUEST_COUNT'] and first==e['FIRST_TIMESTAMP'] and last==e['LAST_TIMESTAMP'],'SOURCE_MANIFEST_COUNTS_OR_ENDPOINTS')
 return total

def main():
 global PARENT,SOURCE,RELEASE,BEGAN,KEY_READY,PHASE
 os.umask(0o077);BEGAN=time.monotonic();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(Failure('WALL_BUDGET')));signal.alarm(1800)
 a,SOURCE=presecret(ROOT);PARENT=SOURCE
 claim='mxm-timestamp-access-v1-'+SOURCE;api('git/refs',{'ref':'refs/tags/'+claim,'sha':SOURCE})
 master=json.loads((ROOT/a['master_path']).read_text());manifest=json.loads((ROOT/a['manifest_path']).read_text());acceptance=json.loads((ROOT/a['acceptance_path']).read_text());entries=manifest['entries'];expected=acceptance['exact_release_inventory']
 rel=api('releases/tags/'+manifest['DURABLE_RELEASE_IDENTITY']);need(rel['id']==expected['release_id'] and rel['tag_name']==expected['tag_name'],'SOURCE_RELEASE_IDENTITY')
 need(json.loads(rel['body'])==expected['body'],'SOURCE_RELEASE_BODY_DRIFT')
 assets=api('releases/'+str(rel['id'])+'/assets?per_page=100&page=1');need(api('releases/'+str(rel['id'])+'/assets?per_page=100&page=2')==[],'EXTRA_SOURCE_ASSETS');byname={x['name']:x for x in assets}
 need(len(assets)==100 and len(entries)==100 and len(master)==1576,'SOURCE_INVENTORY')
 for exp in expected['assets']:need(exp['name'] in byname and all(byname[exp['name']].get(k)==v for k,v in exp.items()),'SOURCE_ASSET_METADATA_DRIFT')
 need([(e['SEGMENT_INDEX'],e['SHARD_INDEX']) for e in entries]==[(s,k) for s in range(1,5) for k in range(25)],'SOURCE_ORDER')
 PHASE='KEY_READINESS'
 with tempfile.TemporaryDirectory(prefix='mxm-standing-access-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);tmp.chmod(0o700)
  need(bool(os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')),'EXISTING_SECRET_ABSENT')
  try:key,fingerprint=_private_key_from_secret(tmp)
  except Exception:raise Failure('EXISTING_KEY_PARSE_OR_FINGERPRINT_MISMATCH') from None
  need(fingerprint==FP,'KEY_FINGERPRINT');KEY_READY=True
  pub=crypto.command(['openssl','pkey','-pubin','-in',str(ROOT/a['public_key_path']),'-outform','DER']);need(sha(pub)==FP,'COMMITTED_PUBLIC_KEY_MISMATCH')
  tag='mxm-timestamp-masks-v1-'+SOURCE
  PHASE='ENCRYPTED_STORAGE_PROBE';RELEASE=api('releases',{'tag_name':tag,'target_commitish':SOURCE,'name':'MXM timestamp-only encrypted checkpoints V1','body':json.dumps({'scope':'timestamp_structure_only_no_prices_or_responses','source_commit':SOURCE,'source_release':rel['tag_name'],'standing_governance_sha256':a['bindings_sha256']['research_core_v4/historical_access_v1/STANDING_HISTORICAL_DATA_ACCESS_GOVERNANCE_V1.json']},sort_keys=True),'draft':False,'prerelease':True})
  probe=store_encrypted({'schema':'mxm.timestamp.storage.probe.v1','source_commit':SOURCE,'manufactured_no_market_data':True},'storage-probe.mxmenc',key,tmp)
  keyreport={'schema':'mxm.existing.key.scope.verification.v1','status':'PASS_CURRENT_EXISTING_KEY_AND_ENCRYPTED_REMOTE_STORAGE_PROBE','source_commit':SOURCE,'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':1,'secret_present':True,'private_parse':'VALID','public_fingerprint':'MATCH','public_spki_sha256':FP,'existing_secret_wiring':'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM; values never printed','new_credentials_or_key_installation':False,'old_ARM_revived':False,'standing_scope':'Existingacceptedhistoricaldataaccess only; scientificresponseauthority separate','encrypted_storage_probe':probe,'resource_use':resource_state(),'no_market_input_opened_yet':True}
  publish({'EXISTING_KEY_READINESS_AND_SCOPE_VERIFICATION_V1.json':keyreport},'Preserve current existing-key and encrypted remote-storage proof')
  bits=[bytearray(N//8) for _ in master];counts=[[0]*4 for _ in master];lasts=[-1]*1576;total=0
  PHASE='TIMESTAMP_INPUT_ACCESS'
  for number,e in enumerate(entries,1):
   budget();asset=byname[e['ENCRYPTED_ASSET_NAME']];b=download(asset['browser_download_url'],asset['size']);need(len(b)==asset['size'] and sha(b)==e['ENCRYPTED_ASSET_SHA256'],'SOURCE_CIPHERTEXT_SHA256_OR_SIZE')
   raw=crypto.decrypt_package(b,private_key=key,expected_public_spki_sha256=FP,temp_parent=tmp);need(len(raw)<=67108864,'PLAINTEXT_SIZE_BUDGET');rows=consume(raw,e,master,bits,counts,lasts);raw=None;b=None
   VERIFIED.append({'number':number,'name':e['ENCRYPTED_ASSET_NAME'],'ciphertext_sha256':e['ENCRYPTED_ASSET_SHA256'],'canonical_plaintext_sha256':e['PLAINTEXT_CANONICAL_SHA256'],'ciphertext_bytes':asset['size'],'rows_timestamp_verified':rows,'status':'PASS_CURRENT_WHOLE_BYTE_AND_TIMESTAMP_VERIFICATION'});total+=rows
   if number in (2,25,50,75,100):
    PHASE='REMOTE_TIMESTAMP_CHECKPOINT'
    value={'schema':'mxm.timestamp.bitmap.checkpoint.v1','source_commit':SOURCE,'source_manifest_sha256':a['bindings_sha256'][a['manifest_path']],'processed_assets':number,'rows':total,'grid_start_utc':'2026-08-20T00:00:00Z','grid_end_exclusive_utc':'2026-09-17T00:00:00Z','grid_step_seconds':300,'bit_law':'littlebitindexwithinbyte; 8064positions;1 means storedtimestamp exists; no price/activity/receipt claim','entries':[{'ordinal':i+1,'symbol_id':m['symbol_id'],'row_counts_by_segment':counts[i],'timestamp_bits_base64':base64.b64encode(bits[i]).decode()} for i,m in enumerate(master)]}
    encrypted=store_encrypted(value,'timestamps-after-'+str(number).zfill(3)+'.mxmenc',key,tmp);CHECKPOINTS.append({'processed_assets':number,'rows':total,**encrypted})
    checkpoint={'schema':'mxm.timestamp.safe.checkpoint.v1','status':'PERSISTED_TIMESTAMP_PREFIX_WITH_REMOTE_CIPHERTEXT_AND_PLAINTEXT_READBACK','source_commit':SOURCE,'run_id':os.environ['GITHUB_RUN_ID'],'processed_assets':number,'verified_rows':total,'encrypted_checkpoint':CHECKPOINTS[-1],'complete100':number==100,'resource_use':resource_state(),'numeric_support_certified':False}
    publish({'TIMESTAMP_CHECKPOINT_'+str(number).zfill(3)+'_V1.json':checkpoint},'Persist exact timestamp-only checkpoint after'+str(number)+' accepted assets')
    if number==2:print(json.dumps({'phase':'TWO_DETERMINISTIC_SHARDS_AND_ENCRYPTED_CHECKPOINT_PASS_CONTINUE_BOUNDED100','processed_assets':2,'publication_commit':PARENT}))
    PHASE='TIMESTAMP_INPUT_ACCESS'
  need(total==3355389 and len(VERIFIED)==100,'COMPLETE100_COUNT')
  historical=json.loads((ROOT/a['historical_result_path']).read_text());need([sum(c) for c in counts]==[x['TOTAL_ROW_COUNT'] for x in historical['identities']],'ACCEPTED_HISTORICAL_ROW_IDENTITY_DRIFT')
  PHASE='STRUCTURAL_TIMESTAMP_MASKS';summaries=[];private_masks=[];totals={str(l):{'feature_timestamp_geometry':0,'response_timestamp_geometry':0,'intersection_timestamp_geometry':0} for l in LAGS}
  for i,m in enumerate(master):
   present=[k for k in range(N) if has(bits[i],k)];days=sorted({k//288 for k in present});lags={};plags={}
   for lag in LAGS:
    maps={'feature_timestamp_geometry':mask(bits[i],'feature',lag),'response_timestamp_geometry':mask(bits[i],'response_geometry',lag),'intersection_timestamp_geometry':mask(bits[i],'intersection',lag)}
    lags[str(lag)]={k:count(v) for k,v in maps.items()};plags[str(lag)]={k:base64.b64encode(v).decode() for k,v in maps.items()}
    for k,v in lags[str(lag)].items():totals[str(lag)][k]+=v
   summaries.append({'master_ordinal':i+1,'symbol_id':m['symbol_id'],'stored_timestamp_count':len(present),'counts_by_segment':counts[i],'active_calendar_days':len(days),'first_utc':datetime.fromtimestamp(START+present[0]*300,timezone.utc).isoformat().replace('+00:00','Z') if present else None,'last_utc':datetime.fromtimestamp(START+present[-1]*300,timezone.utc).isoformat().replace('+00:00','Z') if present else None,'absent_calendar_grid_positions':N-len(present),'lag_structural_counts':lags})
   private_masks.append({'ordinal':i+1,'symbol_id':m['symbol_id'],'timestamp_bits_base64':base64.b64encode(bits[i]).decode(),'active_day_indexes':days,'hourly_masks':plags})
  maskvalue={'schema':'mxm.exact.timestamp.structural.masks.v1','source_commit':SOURCE,'source_manifest_sha256':a['bindings_sha256'][a['manifest_path']],'M5_start_utc':'2026-08-20T00:00:00Z','M5_grid_positions':8064,'hourly_clock_positions':672,'lags_seconds':list(LAGS),'bitmap_law':'littlebits; M5positions=start+300k; hourlypositions=start+3600j; masks based only on exactstoredtimestamp existence and domain maturity','receipt_and_revision':'UNKNOWN; noauthenticavailabilityclaim','numeric_price_activity_validity':'NOT_PROCESSED','entries':private_masks}
  maskref=store_encrypted(maskvalue,'exact-structural-masks.mxmenc',key,tmp);budget()
  coverage={'schema':'mxm.exact.timestamp.coverage.v1','status':'PASS_COMPLETE_TIMESTAMP_ONLY_STRUCTURE_NOT_NUMERICAL_PAIRED_SUPPORT','source_commit':SOURCE,'run_id':os.environ['GITHUB_RUN_ID'],'identity_count':1576,'calendar_days':28,'M5_grid_positions_per_identity':8064,'hourly_clock_positions_per_identity':672,'fixed_opportunities_per_lag':1059072,'rows_timestamp_verified':total,'structural_counts_all_identities':totals,'identities':summaries,'exact_encrypted_masks':maskref,'support_limited_QUB_AU':summaries[514],'absent_calendar_positions':'Descriptiveabsentstoredtimestamps; includesbrokerclosures/weekends; noassertionmissingexpectedmarketdata withoutauthoritativehistoricalschedule','receipts_and_revisions':'UNKNOWN; as-iflags are only indexgeometry, not authenticreceipt evidence','numerical_paired_support':'NOT_CERTIFIED; zeroactivity/zerodirection/OHLCvalidity and numericalresponsevalidity unexamined','no_direction_activity_return_PnL_computation':True}
  result={'schema':'mxm.master1576.secure.timestamp.access.result.v1','status':'PASS_CURRENT100_ARCHIVE_ACCESS_AND_TIMESTAMP_STRUCTURE_NOT_RESPONSE_AUTHORIZATION','source_commit':SOURCE,'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':1,'invocation_claim_tag':claim,'standing_governance_sha256':a['bindings_sha256']['research_core_v4/historical_access_v1/STANDING_HISTORICAL_DATA_ACCESS_GOVERNANCE_V1.json'],'source_bindings_sha256':a['bindings_sha256'],'source_release_id':rel['id'],'source_release_tag':rel['tag_name'],'current_existing_key_readiness':'PASS','public_spki_sha256':FP,'verified100assets':VERIFIED,'source_ciphertext_bytes_total':sum(x['ciphertext_bytes'] for x in VERIFIED),'canonical_rows_timestamp_verified':total,'checks':['exactciphertextbytesSHA256','authenticateddecrypt','exactcanonicalplaintextSHA256','duplicateJSONkeys','canonicalencoding','package/identity/segment/schema','strictM5UTCtimestamps/no duplicates/domain','manifestrows/requestcounts/endpoints','acceptedhistoricalrowidentitycomparison'],'checkpoints':CHECKPOINTS,'final_masks':maskref,'resources_before_final_publication':resource_state(),'numerical_values_not_inspected':True,'broker_requests':0,'numeric_responses':0,'real_experiment_ARM':False,'protected_forward':False,'old_scientific_invocation_replayed':False,'approved_remote_storage':'ExistingGitHubrelease route; newversioned encryptedoutputrelease, sourceacceptedrelease unchanged','failure_rule':'Mandatoryhash/schema/storage/checkpointfailures neverPASS; noautomaticretry; acceptedstate persistsremotely.'}
  commit=publish({'MASTER1576_SECURE_TIMESTAMP_ACCESS_RESULT_V1.json':result,'EXACT_STRUCTURAL_MASK_AND_COVERAGE_RESULT_V1.json':coverage},'Publish complete100 timestamp-only access and exact structural masks')
  receipt={'status':'PASS_COMPLETE100_REMOTE_OUTPUT_READBACK_TIMESTAMP_ONLY','final_machine_publication_commit':commit,'run_id':os.environ['GITHUB_RUN_ID'],'resources_total':resource_state(),'safe_outputs_sha256':{'MASTER1576_SECURE_TIMESTAMP_ACCESS_RESULT_V1.json':sha(enc(result)),'EXACT_STRUCTURAL_MASK_AND_COVERAGE_RESULT_V1.json':sha(enc(coverage))},'encrypted_masks_ciphertext_sha256':maskref['ciphertext_sha256']}
  (DIR/'RUN_READBACK_RECEIPT_V1.json').write_bytes(enc(receipt));print(json.dumps(receipt,sort_keys=True));signal.alarm(0)

def fail(e):
 signal.alarm(0);code=e.code if isinstance(e,Failure) else e.code if isinstance(e,crypto.ScreenError) else 'UNEXPECTED_FAIL_CLOSED'
 value={'schema':'mxm.timestamp.access.failure.v1','status':'FAIL_CLOSED','phase':PHASE,'failure_code':code,'exception_class':type(e).__name__,'source_commit':SOURCE,'current_existing_key_ready':KEY_READY,'verified_input_assets':len(VERIFIED),'completed_remote_checkpoints':CHECKPOINTS,'numeric_responses':0,'broker_requests':0,'resources':resource_state() if BEGAN else None,'no_retry':True}
 try:
  if PARENT:publish({'TIMESTAMP_ACCESS_FAILURE_V1.json':value},'Preserve failed timestamp-only access forensic evidence')
  value['failure_publication']='PERSISTED_EXACT_READBACK' if PARENT else 'NOT_PERSISTED'
 except Exception:value['failure_publication']='NOT_PERSISTED'
 (DIR/'RUN_FAILURE_V1.json').write_bytes(enc(value));print(json.dumps({'status':'FAIL_CLOSED','failure_code':code,'failure_publication':value['failure_publication']},sort_keys=True))
if __name__=='__main__':
 try:
  if '--presecret-only' in __import__('sys').argv:
   BEGAN=time.monotonic();a,h=presecret(ROOT);print(json.dumps({'status':'PASS_PRESECRET_TIMESTAMP_ONLY_AUTHORITY_AND_SOURCE','source_commit':h}))
  else:main()
 except Exception as e:fail(e);raise SystemExit(1)
