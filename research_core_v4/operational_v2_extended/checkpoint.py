"""Per-cell durable provider; no broker credentials and no replay."""
import argparse,base64,hashlib,json,os,pathlib,urllib.request,urllib.error
REPO='mariancradulescu/mxm-quant-greenfield'
def canonical(x):return (json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
def api(p,method='GET',data=None):
 assert p.startswith('/repos/'+REPO+'/')
 req=urllib.request.Request('https://api.github.com'+p,method=method,data=canonical(data) if data is not None else None,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=90) as f:return json.loads(f.read())
def main(mode,profile,case):
 p=pathlib.Path('research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_DOMAIN_CERTIFICATION_PROTOCOL_V1.json');h=hashlib.sha256(p.read_bytes()).hexdigest();branch='extended-k15-p'+str(profile)+'-'+case.lower().replace('_','-')+'-'+h[:12];root='/repos/'+REPO
 if mode=='intent':
  try:api(root+'/git/ref/heads/'+branch)
  except urllib.error.HTTPError as e:assert e.code==404
  else:raise RuntimeError('CELL_ALREADY_ATTEMPTED_NO_REPLAY')
  target=os.environ['EXACT_TARGET'];api(root+'/git/refs','POST',{'ref':'refs/heads/'+branch,'sha':target});parent=target;path='extended_certification/intent.json';data={'protocol_sha256':h,'profile':profile,'case':case,'run_id':int(os.environ['GITHUB_RUN_ID']),'exact_target':target,'status':'FROZEN_BEFORE_FIRST_NEW_SYNTHETIC_TRIAL','no_automatic_retry':True}
 else:
  parent=api(root+'/git/ref/heads/'+branch)['object']['sha'];intent=api(root+'/contents/extended_certification/intent.json?ref='+parent);j=json.loads(base64.b64decode(intent['content']));assert j['run_id']==int(os.environ['GITHUB_RUN_ID']);path='extended_certification/result.json';data=json.loads(pathlib.Path('cell.json').read_bytes());data['machine_run_id']=int(os.environ['GITHUB_RUN_ID']);data['intent_commit']=parent
 blob=api(root+'/git/blobs','POST',{'content':base64.b64encode(canonical(data)).decode(),'encoding':'base64'})['sha'];tree=api(root+'/git/trees','POST',{'base_tree':api(root+'/git/commits/'+parent)['tree']['sha'],'tree':[{'path':path,'mode':'100644','type':'blob','sha':blob}]})['sha'];commit=api(root+'/git/commits','POST',{'tree':tree,'parents':[parent],'message':'Fixed k15 extended cell '+mode+' '+str(profile)+' '+case+' [skip ci]'})['sha'];assert api(root+'/git/ref/heads/'+branch)['object']['sha']==parent;api(root+'/git/refs/heads/'+branch,'PATCH',{'sha':commit,'force':False});print('DURABLE_CELL='+json.dumps({'branch':branch,'head':commit,'path':path,'sha256':hashlib.sha256(canonical(data)).hexdigest()},sort_keys=True),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--mode',choices=['intent','result'],required=True);a.add_argument('--profile',type=int,required=True);a.add_argument('--case',required=True);x=a.parse_args();main(x.mode,x.profile,x.case)
