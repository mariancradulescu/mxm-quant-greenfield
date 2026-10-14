"""Copy an existing encrypted receipt into Git; no plaintext or broker access."""
import os,json,pathlib,urllib.request,time,base64,hashlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
P='research_core_v4/full_native_frontier_checkpoint_20261014_v1/'
def need(x,c):
 if not x:raise RuntimeError(c)
def api(path,data=None,method=None):
 req=urllib.request.Request('https://api.github.com/repos/mariancradulescu/mxm-quant-greenfield/'+path,data=None if data is None else json.dumps(data).encode(),method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=90) as response:return json.load(response)
def main():
 a=json.loads((ROOT/(P+'DELIVERY_V1.json')).read_text());head=os.environ['GITHUB_SHA'];need(os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_REF']=='refs/heads/'+a['branch'],'DELIVERY_SCOPE')
 need(os.environ['GITHUB_WORKFLOW_REF']=='mariancradulescu/mxm-quant-greenfield/'+a['workflow']+'@refs/heads/'+a['branch'],'DELIVERY_WORKFLOW')
 need(a['authority']=='EXPLICIT_OWNER_FULL_NATIVE_FRONTIER_AUTONOMOUS_20261014' and a['broker_requests']==0,'DELIVERY_AUTHORITY')
 subprocess.run(['git','merge-base','--is-ancestor',a['observer_head'],head],check=True)
 for p,sha in a['bindings'].items():need(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha,'DELIVERY_SOURCE_BINDING')
 claim='mxm-full-frontier-cipher-delivery-'+os.environ['GITHUB_RUN_ID'];api('git/refs',{'ref':'refs/tags/'+claim,'sha':head})
 deadline=time.monotonic()+1800
 while True:
  run=api('actions/runs/'+str(a['observer_run']))
  need(run['head_sha']==a['observer_head'] and run['run_attempt']==1,'OBSERVER_SOURCE_RUN')
  if run['status']=='completed':need(run['conclusion']=='success','OBSERVER_FAILED');break
  need(time.monotonic()<deadline,'DELIVERY_WAIT_BOUND');time.sleep(15)
 release=api('releases/tags/mxm-full-frontier-readback-'+str(a['observer_run'])+'-result');body=json.loads(release['body']);need(body['state']=='VERIFIED_INCREMENTAL_SNAPSHOT' and body['OWNER_READBACK_SUCCESS'],'OWNER_RECEIPT')
 meta=body['recipient'];asset=api('releases/assets/'+str(meta['id']));need(asset['digest']=='sha256:'+meta['ciphertext_sha256'] and asset['size']==meta['size'] and asset['size']<10000000,'RECIPIENT_METADATA')
 with urllib.request.urlopen(asset['browser_download_url'],timeout=90) as response:blob=response.read(meta['size']+1)
 need(len(blob)==meta['size'] and hashlib.sha256(blob).hexdigest()==meta['ciphertext_sha256'],'RECIPIENT_CIPHER_READBACK')
 need(api('git/ref/heads/'+a['branch'])['object']['sha']==head,'DELIVERY_BRANCH_LEASE')
 files=[(P+'INCREMENTAL_RECIPIENT_V1.mxmenc.b64',base64.b64encode(blob).decode()+'\n'),(P+'INCREMENTAL_PUBLIC_SAFE_V1.json',json.dumps(body,sort_keys=True,indent=2)+'\n')]
 entries=[{'path':p,'mode':'100644','type':'blob','sha':api('git/blobs',{'content':base64.b64encode(content.encode()).decode(),'encoding':'base64'})['sha']} for p,content in files]
 tree=api('git/trees',{'base_tree':api('git/commits/'+head)['tree']['sha'],'tree':entries});commit=api('git/commits',{'message':'Preserve already encrypted incremental receipt and safe coverage counts [skip ci]','parents':[head],'tree':tree['sha']})
 need(api('git/ref/heads/'+a['branch'])['object']['sha']==head,'DELIVERY_CAS');api('git/refs/heads/'+a['branch'],{'sha':commit['sha'],'force':False},method='PATCH')
 body.update(cipher_delivery_head=commit['sha'],cipher_delivery_run=int(os.environ['GITHUB_RUN_ID']));api('releases/'+str(release['id']),{'body':json.dumps(body,sort_keys=True)},method='PATCH');print(json.dumps({'cipher_delivery_head':commit['sha'],'release_id':release['id'],'recipient':meta,'broker_requests':0,'plaintext_published':False}))
if __name__=='__main__':
 try:main()
 except Exception as ex:
  import re
  code=str(ex) if re.fullmatch('[A-Z0-9_]{1,100}',str(ex)) else type(ex).__name__
  print('FAIL_CLOSED_CIPHER_DELIVERY_'+code);raise SystemExit(1) from None
