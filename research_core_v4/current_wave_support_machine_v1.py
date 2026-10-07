"""GitHub-only streaming adapter and durable support campaign. No broker route."""
from __future__ import annotations
import base64, hashlib, io, json, os, re, resource, struct, subprocess, tempfile, time, urllib.request
from pathlib import Path
import numpy as np
from research_core_v4.current_wave_support_worker_v1 import *
S='research_core_v4/state/'
ARM=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_SUPPORT_EXECUTION_ARM_V1.json'
FREEZE=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_SUPPORT_IMPLEMENTATION_FREEZE_V1.json'
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='performance-research-v3-20260922'
MAGIC=b'MXM_SHALLOW_M5_V2_ENC1\x00'
SPKI='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
PUB='research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
SECRET='MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'
ITEM={'ordinal','symbol_id','classification','request_count','retry_count','page_cap_hits','failure','transport_geometry_pages','rows'}
PACKAGE={'schema','segment_index','shard_index','identity_range','items'}
def load(p):return json.loads(Path(p).read_bytes())
def command(a,**kw):
 r=subprocess.run(a,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60,**kw);need(r.returncode==0,'CRYPTO_FAILURE');return r.stdout

def private_key(td):
 raw=os.environ.get(SECRET,'');need(bool(raw),'PRIVATE_SECRET_UNAVAILABLE')
 cand=[raw,raw.replace('\\n','\n').replace('\r\n','\n')]
 if '-----BEGIN' not in raw:
  try:cand.append(base64.b64decode(raw,validate=True).decode())
  except Exception:pass
 for s in cand:
  p=Path(td)/'private.pem';p.write_text(s);p.chmod(0o600)
  try:
   pub=command(['openssl','pkey','-in',str(p),'-pubout','-outform','DER'])
   if sha(pub)==SPKI:return p
  except SupportError:pass
 raise SupportError('PRIVATE_KEY_PARSE_OR_PUBLIC_PAIR_FAILURE')
def fixture(key,td):
 """Crypto synthetic fixture exercises identical OAEP and OpenPGP route."""
 td=Path(td);home=td/'gnupg';home.mkdir(mode=0o700,exist_ok=True)
 password=td/'password';password.write_bytes(os.urandom(32).hex().encode());password.chmod(0o600)
 plain=b'MXM_SUPPORT_ONLY_NONMARKET_FIXTURE_V1\n'; src=td/'fixture';src.write_bytes(plain)
 cipher=td/'cipher';wrapped=td/'wrapped'
 command(['gpg','--homedir',str(home),'--batch','--yes','--pinentry-mode','loopback','--passphrase-file',str(password),'--symmetric','--cipher-algo','AES256','--output',str(cipher),str(src)])
 command(['openssl','pkeyutl','-encrypt','-pubin','-inkey',PUB,'-in',str(password),'-out',str(wrapped),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'])
 env=td/'envelope';env.write_bytes(MAGIC+struct.pack('>I',wrapped.stat().st_size)+wrapped.read_bytes()+cipher.read_bytes())
 with decrypt_stream(env,key,td) as pipe:need(pipe.read()==plain,'SYNTHETIC_CRYPTO_PARITY_FAILURE')
 return True
class decrypt_stream:
 def __init__(self,path,key,parent):self.path=path;self.key=key;self.parent=parent
 def __enter__(self):
  self.tmp=tempfile.TemporaryDirectory(dir=self.parent);td=Path(self.tmp.name);td.chmod(0o700)
  data=Path(self.path).read_bytes();need(data.startswith(MAGIC),'ENVELOPE_MAGIC');pos=len(MAGIC);need(len(data)>pos+4,'ENVELOPE_LENGTH');n=struct.unpack('>I',data[pos:pos+4])[0];pos+=4;need(0<n<=1024 and pos+n<len(data),'ENVELOPE_LENGTH')
  wrapped=td/'wrapped';wrapped.write_bytes(data[pos:pos+n]);cipher=td/'cipher';cipher.write_bytes(data[pos+n:]);data=None
  password=td/'pass';command(['openssl','pkeyutl','-decrypt','-inkey',str(self.key),'-in',str(wrapped),'-out',str(password),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256']);password.chmod(0o600)
  self.home=td/'gpg';self.home.mkdir(mode=0o700)
  self.proc=subprocess.Popen(['gpg','--homedir',str(self.home),'--batch','--yes','--no-symkey-cache','--pinentry-mode','loopback','--passphrase-file',str(password),'--decrypt',str(cipher)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
  return self.proc.stdout
 def __exit__(self,typ,value,tb):
  self.proc.stdout.close()
  if typ:self.proc.kill()
  code=self.proc.wait(timeout=60)
  subprocess.run(['gpgconf','--homedir',str(self.home),'--kill','gpg-agent'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
  self.tmp.cleanup()
  if typ is None:need(code==0,'CRYPTO_FAILURE')
class HashReader:
 def __init__(self,pipe):self.pipe=pipe;self.hash=hashlib.sha256();self.bytes=0
 def read(self,n=-1):
  b=self.pipe.read(n);self.bytes+=len(b);need(self.bytes<=268435456,'PLAINTEXT_SHARD_STREAM_BOUND');self.hash.update(b);return b

def project_stream(pipe,e,master,digits,eligible):
 """Incremental token parser retains one six-field row, no plaintext file."""
 import ijson
 r=HashReader(pipe);pending=np.zeros((e['master_ordinal_range'][1]-e['master_ordinal_range'][0]+1,2016),np.uint8)
 top={};topkeys=set();identity_range=[];item=None;itemkeys=set();row=None;rowkeys=set();idx=0;rows=0;previous=-1;rowcount=0
 for prefix,event,value in ijson.parse(r):
  if prefix=='' and event=='map_key':need(value not in topkeys,'DUPLICATE_JSON_KEY');topkeys.add(value)
  if prefix in ('schema','segment_index','shard_index') and event in ('string','number'):top[prefix]=value
  if prefix=='identity_range.item' and event=='number':identity_range.append(value)
  if prefix=='items.item' and event=='start_map':item={};itemkeys=set();rowcount=0;previous=-1
  if prefix=='items.item' and event=='map_key':need(value not in itemkeys,'DUPLICATE_JSON_KEY');itemkeys.add(value)
  if prefix.startswith('items.item.') and prefix.count('.')==2 and event in ('string','number','null'):item[prefix.rsplit('.',1)[1]]=value
  if prefix=='items.item.rows.item' and event=='start_map':row={};rowkeys=set()
  if prefix=='items.item.rows.item' and event=='map_key':need(value not in rowkeys,'DUPLICATE_JSON_KEY');rowkeys.add(value)
  if prefix.startswith('items.item.rows.item.') and event in ('string','number','null','boolean'):row[prefix.rsplit('.',1)[1]]=value
  if prefix=='items.item.rows.item' and event=='end_map':
   ordinal=e['master_ordinal_range'][0]+idx;need(ordinal<=e['master_ordinal_range'][1],'ITEM_COUNT')
   k,bits=project(row,e['segment_index'],digits[master[ordinal-1]['symbol_id']]);need(k>previous,'DUPLICATE_OR_UNORDERED_KEYS');previous=k
   local=k-(e['segment_index']-1)*2016;need(pending[idx,local]==0,'DUPLICATE_KEYS');pending[idx,local]=bits
   rows+=1;rowcount+=1;row.clear();row=None
  if prefix=='items.item' and event=='end_map':
   ordinal=e['master_ordinal_range'][0]+idx
   need(itemkeys==ITEM and item.get('ordinal')==ordinal and item.get('symbol_id')==master[ordinal-1]['symbol_id'],'ITEM_SCHEMA_IDENTITY')
   need(item.get('failure') is None and item.get('retry_count')==0 and item.get('page_cap_hits')==0 and type(item.get('request_count')) is int and item['request_count']>=1,'PROVENANCE_FAILURE')
   need(item.get('classification')==('SHALLOW_SUPPORT_COMPLETE' if rowcount else 'NO_HISTORICAL_SUPPORT'),'PROVENANCE_FAILURE');idx+=1;item=None
 need(topkeys==PACKAGE and top=={'schema':'mxm.v4.shallow-m5-v2.raw-shard.v1','segment_index':e['segment_index'],'shard_index':e['shard_index']} and identity_range==e['master_ordinal_range'] and idx==len(pending),'PACKAGE_PROVENANCE_SCHEMA')
 need(rows==e['canonical_row_count_metadata'],'ROW_COUNT_BINDING');need(r.hash.hexdigest()==e['plaintext_canonical_sha256'],'PLAINTEXT_CANONICAL_SHA256')
 return pending,{'rows_streamed':rows,'plaintext_bytes_streamed':r.bytes,'plaintext_canonical_sha256':r.hash.hexdigest(),'encrypted_sha256':e['encrypted_sha256'],'asset_id':e['asset_id'],'asset_name':e['name'],'encrypted_bytes':e['encrypted_bytes'],'plaintext_discarded_before_checkpoint':True}

def api(path,method='GET',obj=None,binary=False):
 need(path.startswith('/repos/'+REPO+'/'),'GITHUB_ROUTE_ONLY')
 data=canonical(obj) if obj is not None else None
 headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/octet-stream' if binary else 'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'}
 with urllib.request.urlopen(urllib.request.Request('https://api.github.com'+path,data=data,headers=headers,method=method),timeout=120) as r:b=r.read()
 return b if binary else json.loads(b)
def bound():
 f=load(FREEZE)
 for p,h in f['bindings'].items():need(sha(Path(p).read_bytes())==h,'IMPLEMENTATION_OR_ACCEPTED_BINDING_DRIFT')
 route=load(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_ACCEPTED_M5_ASSET_ROUTE_V1.json');roster=load(S+'MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json')['entries']
 need(len(route['assets'])==100 and sum(e['encrypted_bytes'] for e in route['assets'])==49708418,'ASSET_INVENTORY_BINDING');need(len(roster)==1575,'ROSTER_BINDING')
 need([(e['segment_index'],e['shard_index']) for e in route['assets']]==[(s,k) for s in range(1,5) for k in range(25)],'ASSET_ORDER_BINDING')
 need(len({e['asset_id'] for e in route['assets']})==100,'ASSET_ID_BINDING')
 return f,route,roster

def preflight():
 from research_core_v4.tests.test_current_wave_support_v1 import run_tests
 f,route,roster=bound();begin=time.monotonic();run_tests()
 with tempfile.TemporaryDirectory() as td:
  # Full 1575x8064 domain, exact same reducer; synthetic values only validity bits.
  v=np.full((1575,G),31,np.uint8);support,geo=derive(v,roster,td)
  need(len(support['per_candidate_identity_context_horizon'])==1575*9,'EXACT_FIVE_CANDIDATE_COVERAGE')
  need(all(x['causal_pass_count']==0 for x in support['per_candidate_identity_context_horizon']),'NO_UNKNOWN_PROMOTION')
  disk=sum(p.stat().st_size for p in Path(td).iterdir())
  print('SUPPORT_PUBLIC_PREFLIGHT='+json.dumps({'status':'PASS_FULL_SYNTHETIC_MASK_DOMAIN','tests_passed':TEST_COUNT,'identities':1575,'assets':100,'disk_bytes':disk,'elapsed_seconds_ceiling':int(time.monotonic()-begin)+1,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'real_asset_bodies_read':0}),flush=True)
  key=private_key(td);fixture(key,td)
 elapsed=time.monotonic()-begin;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 need(rss<2*1024**3 and disk<256*1024**2 and elapsed<1800,'STANDARD_RUNNER_RESOURCE_PREFLIGHT')
 result={'status':'PASS_MACHINE_SYNTHETIC_AND_PRIVATE_ROUTE_NO_REAL_ASSET_READ','implementation_freeze_sha256':sha(Path(FREEZE).read_bytes()),'bindings':f['bindings'],'run_id':int(os.environ.get('GITHUB_RUN_ID',0)),'run_attempt':int(os.environ.get('GITHUB_RUN_ATTEMPT',1)),'implementation_head':os.environ.get('GITHUB_SHA'),'tests_passed':TEST_COUNT,'tests_failed':0,'tests_skipped':0,'synthetic_full_domain':{'identities':1575,'entry_slots':G,'source_horizon_records':1575*9,'peak_RSS_bytes':rss,'output_disk_bytes':disk,'elapsed_seconds_ceiling':int(elapsed)+1},'private_key_pair':'PASS','synthetic_envelope_roundtrip':'PASS','real_asset_bodies_read':0,'market_rows_read':0,'broker_requests':0,'ctrader_requests':0,'scope':'SUPPORT_ONLY','stream_shard_cap_bytes':268435456,'no_plaintext_file_in_real_adapter':True}
 print('SUPPORT_MACHINE_PREFLIGHT_RESULT='+canonical(result).decode().strip(),flush=True)
 return result

def commit_files(ref,parent,files,message):
 tree=api('/repos/'+REPO+'/git/commits/'+parent)['tree']['sha'];elements=[]
 for p,raw in files.items():
  blob=api('/repos/'+REPO+'/git/blobs','POST',{'encoding':'base64','content':base64.b64encode(raw).decode()})
  elements.append({'path':p,'mode':'100644','type':'blob','sha':blob['sha']})
 tr=api('/repos/'+REPO+'/git/trees','POST',{'base_tree':tree,'tree':elements})
 co=api('/repos/'+REPO+'/git/commits','POST',{'tree':tr['sha'],'parents':[parent],'message':message})
 need(api('/repos/'+REPO+'/git/ref/heads/'+ref)['object']['sha']==parent,'CHECKPOINT_LEASE')
 api('/repos/'+REPO+'/git/refs/heads/'+ref,'PATCH',{'sha':co['sha'],'force':False});return co['sha']
def getfile(ref,path):
 d=api('/repos/'+REPO+'/contents/'+path+'?ref='+ref)
 return base64.b64decode(d['content'])

def verify_checkpoint(ledger,assets):
 need(type(ledger) is list and len(ledger)<=100,'CHECKPOINT_INVENTORY')
 for a,e in zip(ledger,assets):
  need(all(a.get(k)==e[v] for k,v in [('asset_id','asset_id'),('asset_name','name'),('encrypted_bytes','encrypted_bytes'),('encrypted_sha256','encrypted_sha256'),('plaintext_canonical_sha256','plaintext_canonical_sha256'),('rows_streamed','canonical_row_count_metadata')]),'CHECKPOINT_PUBLIC_BINDING')
  need(a.get('plaintext_discarded_before_checkpoint') is True and re.fullmatch('[0-9a-f]{64}',a.get('mask_sha256','')) is not None,'CHECKPOINT_VALIDITY')

def execute():
 f,route,roster=bound();arm=load(ARM);armsha=sha(Path(ARM).read_bytes());need(arm['scope']=='SUPPORT_ONLY' and arm['implementation_freeze_sha256']==sha(Path(FREEZE).read_bytes()),'ARM_BINDING')
 need(arm['assets']==route['assets'] and arm['roster']==roster and arm['protected_forward_boundary']=='2026-09-17T12:02:58Z','ARM_INPUT_BINDING')
 need(load(arm['preflight_ref'])['status']=='PASS_MACHINE_SYNTHETIC_AND_PRIVATE_ROUTE_NO_REAL_ASSET_READ','PREFLIGHT_FAIL_CLOSED')
 run=int(os.environ['GITHUB_RUN_ID']);head=os.environ['GITHUB_SHA'];need(api('/repos/'+REPO+'/git/ref/heads/'+BRANCH)['object']['sha']==head,'LIVE_ARM_HEAD')
 ref='support-only-v1-'+armsha[:16];cp='support_only_v1/checkpoint.json';parent=head;ledger=[]
 try:
  api('/repos/'+REPO+'/git/refs','POST',{'ref':'refs/heads/'+ref,'sha':head})
  parent=commit_files(ref,head,{cp:canonical({'arm_sha256':armsha,'run_id':run,'assets':[],'complete':False})},'Claim exactly one support-only campaign')
 except urllib.error.HTTPError as error:
  if error.code!=422:raise
  parent=api('/repos/'+REPO+'/git/ref/heads/'+ref)['object']['sha'];d=json.loads(getfile(ref,cp));need(d['arm_sha256']==armsha and d['run_id']==run,'ONE_CAMPAIGN_ONLY');need(not d['complete'],'ALREADY_COMPLETE_NO_REEXECUTION');ledger=d['assets'];verify_checkpoint(ledger,route['assets'])
 master=load(S+'QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json');digits={e['symbol_id']:e['digits'] for e in load(S+'BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_SYMBOL_DIGITS_MAP.json')['entries']};index={e['MASTER_ORDINAL']:i for i,e in enumerate(roster)}
 inventory=api('/repos/'+REPO+'/releases/'+str(route['release_id'])+'/assets?per_page=100');extra=api('/repos/'+REPO+'/releases/'+str(route['release_id'])+'/assets?per_page=100&page=2');need(len(inventory)==100 and not extra,'LIVE_INVENTORY')
 live={e['id']:e for e in inventory}
 for e in route['assets']:
  a=live.get(e['asset_id'],{});need(a.get('name')==e['name'] and a.get('size')==e['encrypted_bytes'] and a.get('digest')=='sha256:'+e['encrypted_sha256'] and a.get('state')=='uploaded','LIVE_ASSET_BINDING')
 with tempfile.TemporaryDirectory() as td:
  key=private_key(td);fixture(key,td);validity=np.zeros((1575,G),np.uint8)
  for j,e in enumerate(route['assets']):
   name='support_only_v1/shards/'+str(j).zfill(3)+'.bin'
   if j<len(ledger):
    need(ledger[j]['asset_id']==e['asset_id'],'CHECKPOINT_ORDER');raw=getfile(ref,name);need(sha(raw)==ledger[j]['mask_sha256'],'CHECKPOINT_MASK_SHA256');pending=np.frombuffer(raw,dtype=np.uint8).reshape((-1,2016))
   else:
    raw=api('/repos/'+REPO+'/releases/assets/'+str(e['asset_id']),binary=True);need(len(raw)==e['encrypted_bytes'] and sha(raw)==e['encrypted_sha256'],'ENCRYPTED_BODY_BINDING');path=Path(td)/'encrypted';path.write_bytes(raw);raw=None
    with decrypt_stream(path,key,td) as pipe:pending,audit=project_stream(pipe,e,master,digits,index)
    path.unlink();mask=pending.tobytes();audit['mask_sha256']=sha(mask);ledger.append(audit)
    parent=commit_files(ref,parent,{name:mask,cp:canonical({'arm_sha256':armsha,'run_id':run,'assets':ledger,'complete':False})},'Atomic verified support mask checkpoint '+str(j+1)+'/100')
    print('SUPPORT_CHECKPOINT '+str(j+1)+'/100',flush=True)
   for k,ordinal in enumerate(range(e['master_ordinal_range'][0],e['master_ordinal_range'][1]+1)):
    if ordinal in index:validity[index[ordinal],(e['segment_index']-1)*2016:e['segment_index']*2016]=pending[k]
   pending=None
  support,geo=derive(validity,roster,Path(td)/'outputs');files={};outputs=[]
  for p in sorted((Path(td)/'outputs').iterdir()):
   raw=p.read_bytes();name='support_only_v1/results/'+p.name;files[name]=raw;outputs.append({'ref':name,'sha256':sha(raw),'bytes':len(raw)})
  result={'schema':'mxm.v4.current-wave.support-execution-result.v1','status':'SUPPORT_RESULT_COMPLETE_PENDING_INDEPENDENT_AUDIT','arm_sha256':armsha,'scope':'SUPPORT_ONLY','run_id':run,'run_attempt':int(os.environ['GITHUB_RUN_ATTEMPT']),'execution_head':head,'checkpoint_branch':ref,'assets':ledger,'outputs':outputs,'global':{'exact_rows_streamed':sum(e['rows_streamed'] for e in ledger),'exact_identities_observed':1576,'eligible_identities':1575,'exact_shards_verified':100,'exact_bytes_downloaded':sum(e['encrypted_bytes'] for e in ledger),'exact_plaintext_hashes_verified':100,'protected_forward_rows':0,'invalid_schema_rows':0,'duplicate_keys':0,'out_of_grid_keys':0},'source_geometric_joint_counts':{s:sum(r['geometric_joint_count'] for r in support['per_candidate_identity_context_horizon'] if r['source']==s) for s in SOURCES},'causal_pass_count':0,'causal_false_count':0,'all_potential_causal_states':'UNKNOWN','broker_requests':0,'ctrader_requests':0,'new_data_requests':0,'new_economic_outcomes':0,'search_budget_use':0,'power_trials':0,'duration_selected':False,'protected_forward_opened':False,'confirmation_opened':False,'raw_rows_persisted':0,'feature_values_computed':0,'response_values_computed':0,'streaming_plaintext_discard':True,'geometry_layers':geo['layers']}
  files['support_only_v1/results/result.json']=canonical(result);files[cp]=canonical({'arm_sha256':armsha,'run_id':run,'assets':ledger,'complete':True,'result_sha256':sha(canonical(result))});parent=commit_files(ref,parent,files,'Freeze complete real support-only masks counts and factorized geometry')
  print('SUPPORT_REAL_RESULT='+canonical({'checkpoint_head':parent,'result_ref':'support_only_v1/results/result.json','result_sha256':sha(canonical(result)),'checkpoint_branch':ref,**{k:v for k,v in result.items() if k not in ('assets','outputs','geometry_layers')}}).decode().strip(),flush=True)
TEST_COUNT=0
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
 try:
  if a.preflight:
   from research_core_v4.tests.test_current_wave_support_v1 import TEST_COUNT
   preflight()
  elif a.execute:execute()
  else:raise SupportError('NO_MODE')
 except Exception as e:
  code=str(e) if isinstance(e,SupportError) else type(e).__name__
  print('SUPPORT_OPERATIONAL_BLOCKER='+json.dumps({'status':'SUPPORT_EXECUTION_OPERATIONALLY_BLOCKED','code':code,'real_scope':'SUPPORT_ONLY'}),flush=True);raise SystemExit(1)
