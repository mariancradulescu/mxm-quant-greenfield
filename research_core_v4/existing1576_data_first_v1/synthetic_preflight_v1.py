"""One bounded fabricated-only feasibility campaign and safe remote publication."""
import base64,hashlib,json,math,os,pathlib,resource,subprocess,time,urllib.request
from research_core_v4.existing1576_data_first_v1.coupling_response_kernel_v1 import directions,response
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=ROOT/'research_core_v4/existing1576_data_first_v1'
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='performance-research-v3-20260922';OUT='research_core_v4/existing1576_data_first_v1/SYNTHETIC_MACHINE_RESULT_V1.json'
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return (json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def api(p,body=None,method=None):
 req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+p,data=None if body is None else enc(body),method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def bar(ts,o=100.,c=101.,v=1):return dict(timestamp=ts,available_at=ts+300,open=o,high=max(o,c),low=min(o,c),close=c,tick_volume=v)
def checks():
 ledger=[]
 def check(name,fn):
  try:fn();ledger.append({'name':name,'status':'PASS'})
  except Exception as e:ledger.append({'name':name,'status':'FAIL','class':type(e).__name__})
 def must(x):
  if not x:raise AssertionError('FIXTURE_EXPECTATION')
 def raises(fn):
  try:fn()
  except ValueError:return
  raise AssertionError('FAULT_NOT_REJECTED')
 bars={k:bar(k,v=2) for k in range(0,7200,300)};bars[3300]=bar(3300,101.,100.,1)
 check('known_direction_and_response',lambda:must(directions(bars,3600,0)[0]==(1,-1) and abs(response(bars,3600,0,7200,7200)[0]-math.log(1.01))<1e-12))
 check('no_premature_label',lambda:raises(lambda:response(bars,3600,0,7199,7200)))
 check('right_domain_censor',lambda:must(response(bars,3600,900,8100,7200)[1]=='DOMAIN_CENSOR'))
 missing=dict(bars);missing.pop(0);check('missing_feature_not_zero',lambda:must(directions(missing,3600,0)[0] is None))
 missing=dict(bars);missing.pop(3900);check('missing_label_not_zero',lambda:must(response(missing,3600,0,7200,7200)[0] is None))
 late={k:dict(v) for k,v in bars.items()};late[0]['available_at']=4000;check('late_receipt_abstains',lambda:must(directions(late,3600,0)[1]=='FEATURE_RECEIPT'))
 zero={k:dict(v,tick_volume=0) for k,v in bars.items()};check('zero_volume_abstains',lambda:must(directions(zero,3600,0)[1]=='ZERO_ACTIVITY'))
 bad={k:dict(v) for k,v in bars.items()};bad[0]['tick_volume']=-1;check('negative_volume_fails',lambda:raises(lambda:directions(bad,3600,0)))
 bad={k:dict(v) for k,v in bars.items()};bad[0]['close']=float('nan');check('nonfinite_fails',lambda:raises(lambda:directions(bad,3600,0)))
 check('wrong_grid_fails',lambda:raises(lambda:directions(bars,3601,0)))
 check('unknown_lag_fails',lambda:raises(lambda:directions(bars,3600,1)))
 # Publication mock faults: exact bytes, partial writes and wrong-parent controls.
 def readback(expected,actual):
  if sha(expected)!=sha(actual):raise ValueError('NOT_PERSISTED')
 check('publication_readback_fault_rejected',lambda:raises(lambda:readback(b'complete',b'partial')))
 check('exact_readback_accepted',lambda:readback(b'complete',b'complete'))
 return ledger

def main():
 began=time.monotonic();a=json.loads((HERE/'SYNTHETIC_PREFLIGHT_AUTHORITY_V1.json').read_text());head=os.environ['GITHUB_SHA']
 assert os.environ['GITHUB_REPOSITORY']==REPO and os.environ['GITHUB_RUN_ATTEMPT']=='1'
 assert api('git/ref/heads/'+BRANCH)['object']['sha']==head
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==head
 for p,h in a['source_sha256'].items():assert sha((ROOT/p).read_bytes())==h,'SOURCE_HASH'
 tag='mxm-existing1576-synthetic-v1-'+head;api('git/refs',{'ref':'refs/tags/'+tag,'sha':head})
 ledger=checks();synthetic_cpu=time.process_time();fixtures={k:bar(k,100.,101.,1) for k in range(-7200,28*86400+3600,300)}
 # Process full declared frontier dimensions with fabricated constant bars only.
 supported=0;abstained=0;label_ok=0
 for sid in range(1576):
  for t in range(0,28*86400,3600):
   for lag in (0,300,900):
    d,why=directions(fixtures,t,lag)
    if d is None:abstained+=1
    else:supported+=1
    y,why=response(fixtures,t,lag,t+3600+lag,28*86400)
    if y is not None:
     assert y==0.;label_ok+=1
  assert time.monotonic()-began<300,'RESOURCE_WALL'
  assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<524288,'RESOURCE_MEMORY'
 fixture_cpu=time.process_time()-synthetic_cpu
 corpus=json.loads((ROOT/a['corpus_path']).read_text());rel=api('releases/tags/'+corpus['DURABLE_RELEASE_IDENTITY']);assets={x['name']:x for x in rel['assets']}
 assert len(corpus['entries'])==100
 for e in corpus['entries']:assert assets[e['ENCRYPTED_ASSET_NAME']]['digest']=='sha256:'+e['ENCRYPTED_ASSET_SHA256']
 passed=all(x['status']=='PASS' for x in ledger)
 report={'schema':'mxm.existing1576.synthetic.preflight.result.v1','status':'SYNTHETIC_KERNEL_PASS_REAL_DATA_ACCESS_NOT_PROVEN' if passed else 'SYNTHETIC_KERNEL_FAIL','source_commit':head,'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':1,'one_use_claim_tag':tag,'source_sha256':a['source_sha256'],'fault_checks':ledger,'fabricated_dimensions':{'identities':1576,'calendar_hours':672,'lags':3,'feature_calls':3177216,'supported_feature_calls':supported,'feature_abstentions':abstained,'mature_supported_fabricated_labels':label_ok,'synthetic_input':'constant manufactured bars; all response values0; no market evidence','stored_bar_objects':len(fixtures)},'resources':{'wall_seconds_before_publication':time.monotonic()-began,'cpu_seconds':time.process_time(),'fixture_cpu_seconds':fixture_cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'budget_wall_seconds':300,'memory_budget_kib':524288,'real_payload_benchmark':False},'current_release_metadata':{'tag':corpus['DURABLE_RELEASE_IDENTITY'],'all100_declared_digest_matches':True,'max_ciphertext_asset_bytes':max(assets[e['ENCRYPTED_ASSET_NAME']]['size'] for e in corpus['entries']),'bytes_downloaded':0,'shards_decrypted':0},'scientific_boundary':{'real_numeric_responses':0,'broker_requests':0,'private_key_access':False,'real_ARM':False,'protected_forward':False,'host_layout_v2_pass':False,'actual_timestamp_common_masks':'UNAVAILABLE_NO_NEW_AUTHORIZED_DECRYPTION'},'future_real_route':'No real entrypoint supplied. Pure kernel needs separately audited input adapter, exact data-access/response authorization and durable host/publication controls.'}
 data=enc(report);(ROOT/OUT).write_bytes(data)
 assert api('git/ref/heads/'+BRANCH)['object']['sha']==head,'PUBLICATION_HEAD_DRIFT'
 blob=api('git/blobs',{'encoding':'base64','content':base64.b64encode(data).decode()});tree=api('git/trees',{'base_tree':api('git/commits/'+head)['tree']['sha'],'tree':[{'path':OUT,'mode':'100644','type':'blob','sha':blob['sha']}]});commit=api('git/commits',{'message':'Preserve one existing-data fabricated preflight and exact secure-access boundary [skip ci]','tree':tree['sha'],'parents':[head]})
 assert api('git/ref/heads/'+BRANCH)['object']['sha']==head
 api('git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False},'PATCH')
 read=api('contents/'+OUT+'?ref='+commit['sha']);assert sha(base64.b64decode(read['content']))==sha(data),'NOT_PERSISTED'
 receipt={'status':'PERSISTED_EXACT_READBACK_SYNTHETIC_ONLY' if passed else 'PERSISTED_SYNTHETIC_FAILURE','publication_commit':commit['sha'],'output_sha256':sha(data),'wall_seconds_total':time.monotonic()-began,'cpu_seconds_total':time.process_time(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss};(HERE/'RUN_RECEIPT_V1.json').write_bytes(enc(receipt));print(json.dumps(receipt));return 0 if passed else 1
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:
  (HERE/'RUN_FAILURE_V1.json').write_bytes(enc({'status':'FAIL_CLOSED_NOT_PERSISTED_OR_NOT_VERIFIED','class':type(e).__name__,'message':str(e)[:160]}));raise
