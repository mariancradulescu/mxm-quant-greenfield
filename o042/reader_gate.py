"""Read-only fixed authority gate. No key, App token or caller-selected authority."""
import base64,copy,hashlib,json,os,pathlib,subprocess
from . import identity as i
AUTH='refs/heads/mxm-o04-stage-authority-v1'
SPOOF='refs/heads/mxm-o04-stage-spoof-20261016-v1'
SOURCE='639ebc99ab2237f1b68cc152537fe919900f338a'
NEW='SHA256:if9s0/vBUMyiKrKc5p6RJoXtcI2sL6HGIWRjNhpRKpk='
STOP='a830c132521bd4348454653f713e04f6107484fe'

def get(path):
 status,body=i.api(path,os.environ['GH_TOKEN']);i.need(status==200,'READ_HTTP_'+str(status));return body

def gate(ref,oid,state,selected_oid,parent):
 i.need(ref==AUTH and oid==selected_oid,'REFERENCE_NOT_AUTHORIZED')
 s=copy.deepcopy(state);grant=s.pop('server_grant');e=grant['envelope']
 i.need(e['app_id']==5343530 and e['installation_id']==172030470 and e['repository_id']==1374181010 and e['authority_ref']==AUTH,'GRANT_AUTHORITY')
 i.need(e['expected_old_oid']==parent and e['state_sha256']==i.sha(i.canonical(s)),'GRANT_PARENT_DIGEST')
 der=subprocess.run(['openssl','pkey','-pubin','-outform','DER'],input=e['public_key_pem'].encode(),capture_output=True,check=True).stdout
 fp='SHA256:'+base64.b64encode(hashlib.sha256(der).digest()).decode()
 i.need(fp==NEW,'PINNED_NEW_PUBLIC_KEY')
 i.need(i.openssl_verify(e['public_key_pem'].encode(),i.canonical(e),base64.b64decode(grant['signature'])),'APP_SIGNATURE')
 w=e['workload'];i.need(w['sha']==SOURCE and w['job_workflow_sha']==SOURCE and w['repository_id']=='1374181010' and w['ref']=='refs/heads/mxm-o04-issuer-code-v3','WORKLOAD_BINDING')
 i.need(s['root']['root_o04_stop_oid']==STOP and s['root']['owner_generation']==1807 and s['marker']=='SYNTHETIC_ONLY','ROOT')
 i.need(s['source_SHA']==SOURCE and s['status']=='ACCEPTED' and s['mode']=='STAGED_READY_STOP_ONLY' and s['lease_until']==0 and s['owner'] is None and s['pending'] is None,'STOP_ONLY_STATE')
 i.need(s['OWNER_ACCEPTS_NEW_CHECKPOINTS'] is False and s['CAMPAIGN_RESTART_ALLOWED'] is False and s['PRODUCTION_GO'] is False,'OWNER_CLOSED')
 for item in s['accepted'].values():
  p=item['proposal'];r=p['record']
  for f in ['manifest','ciphertext']:
   raw=base64.b64decode(p[f]);i.need(i.sha(raw)==r[f+'_sha256'] and s['evidence'][r[f+'_sha256']]==p[f],'CONTENT_DIGEST')
 return 'DRY_RUN_VERIFIED_STAGING_STOP_ONLY_NEVER_OWNER'

def main():
 ref=get('git/ref/'+AUTH.removeprefix('refs/'));oid=ref['object']['sha']
 commit=get('git/commits/'+oid);parent=commit['parents'][0]['sha'];tree=get('git/trees/'+commit['tree']['sha'])
 entry=[x for x in tree['tree'] if x['path']=='state.json'];i.need(len(entry)==1,'STATE_PATH')
 blob=get('git/blobs/'+entry[0]['sha']);state=json.loads(base64.b64decode(blob['content']))
 accepted=gate(AUTH,oid,state,oid,parent)
 spoof=get('git/ref/'+SPOOF.removeprefix('refs/'));i.need(spoof['object']['sha']==oid,'SPOOF_IDENTICAL_CONTENT')
 results={}
 for name,ref,test in [('side_branch_spoof',SPOOF,copy.deepcopy(state)),('invalid_digest',AUTH,copy.deepcopy(state)),('invalid_signature',AUTH,copy.deepcopy(state)),('wrong_app_identity',AUTH,copy.deepcopy(state))]:
  if name=='invalid_digest':test['version']+=1
  elif name=='invalid_signature':test['server_grant']['signature']=base64.b64encode(b'invalid').decode()
  elif name=='wrong_app_identity':test['server_grant']['envelope']['app_id']=1
  try:gate(ref,oid,test,oid,parent)
  except (i.Refused,ValueError,KeyError) as ex:results[name]={'decision':'REJECTED','reason':str(ex),'before':oid,'after':get('git/ref/'+AUTH.removeprefix('refs/'))['object']['sha']}
  else:raise i.Refused('READER_NEGATIVE_ACCEPTED')
 final=get('git/ref/'+AUTH.removeprefix('refs/'))['object']['sha'];i.need(final==oid,'AUTHORITY_CHANGED')
 receipt={'schema':'mxm.o042.reader-proof.v1','run':os.environ['GITHUB_RUN_ID'],'attempt':os.environ['GITHUB_RUN_ATTEMPT'],'job':os.environ['GITHUB_JOB'],'source_SHA':os.environ['GITHUB_SHA'],'fixed_authority_ref':AUTH,'authority_oid':oid,'positive':accepted,'public_key_fingerprint':NEW,'results':results,'contents_permission':'read','environment_used':False,'App_token_used':False,'authority_mutations':0,'OWNER_ACCEPTS_NEW_CHECKPOINTS':False,'CAMPAIGN_RESTART_ALLOWED':False,'PRODUCTION_GO':False}
 pathlib.Path('verification').mkdir(exist_ok=True);pathlib.Path('verification/o042-reader.json').write_bytes(i.canonical(receipt)+b'\n');print(i.canonical(receipt).decode())
if __name__=='__main__':main()
