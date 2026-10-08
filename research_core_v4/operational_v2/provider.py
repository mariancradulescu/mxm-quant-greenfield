"""Durable nonoutcome-only Git checkpoint provider. Scoped repository/branch."""
import base64,json,os,urllib.request,urllib.error
from bank import canonical
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='support-only-depth-v2-211b733174627e49'
def api(path,method='GET',data=None):
 assert path.startswith('/repos/'+REPO+'/')
 req=urllib.request.Request('https://api.github.com'+path,data=canonical(data) if data is not None else None,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'},method=method)
 with urllib.request.urlopen(req,timeout=90) as f:return json.loads(f.read())
def ensure(head):
 try:return api('/repos/'+REPO+'/git/ref/heads/'+BRANCH)['object']['sha']
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
  api('/repos/'+REPO+'/git/refs','POST',{'ref':'refs/heads/'+BRANCH,'sha':head});return head

def put(parent,files,message):
 assert files and all(p.startswith('support_depth_v2/') for p in files)
 base=api('/repos/'+REPO+'/git/commits/'+parent)['tree']['sha'];entries=[]
 for path,b in files.items():
  assert isinstance(b,bytes)
  h=api('/repos/'+REPO+'/git/blobs','POST',{'content':base64.b64encode(b).decode(),'encoding':'base64'})['sha'];entries.append({'path':path,'mode':'100644','type':'blob','sha':h})
 tree=api('/repos/'+REPO+'/git/trees','POST',{'base_tree':base,'tree':entries})['sha'];commit=api('/repos/'+REPO+'/git/commits','POST',{'message':message+' [skip ci]','tree':tree,'parents':[parent]})['sha']
 assert api('/repos/'+REPO+'/git/ref/heads/'+BRANCH)['object']['sha']==parent,'DURABLE_REF_DRIFT'
 api('/repos/'+REPO+'/git/refs/heads/'+BRANCH,'PATCH',{'sha':commit,'force':False});return commit
