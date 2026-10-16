"""Isolated trusted issuer. App key never leaves this one approved job.

Custody mode has no App key. Issuer mode is closed until custody acceptance
has been independently collected and a private key provisioned in the same
protected GitHub Environment. No caller can supply a role, ref, URL or token.
"""
import base64,copy,json,os,pathlib,subprocess,tempfile,time
from . import identity as i
from research_core_v4.writer_fencing_o04_20261016 import git_fence_lab as lab
from research_core_v4.writer_staging_o04_20261016.protocol import FixtureProtocol,SyntheticIssuer,ROOT,digest
CANARY_HASH='5abe544f417f242049b2c28f67b308a6583b5e2c137322fd1d131641fcb18ffa'
REMOTE='https://github.com/'+i.REPO+'.git'

def output(name,obj):
 p=pathlib.Path('verification');p.mkdir(exist_ok=True);(p/(name+'.json')).write_bytes(i.canonical(obj)+b'\n');print(i.canonical(obj).decode())

def custody():
 workload=i.authenticated_workload()
 i.need(i.sha(os.environ.get('CUSTODY_CANARY','').encode())==CANARY_HASH,'CUSTODY_CANARY_NOT_AVAILABLE')
 # The fixed, single-job reusable file is part of the frozen code tree.
 i.need(os.environ['GITHUB_JOB']=='acceptor','WORKLOAD_JOB')
 output('o042-custody',{'schema':'mxm.o042.custody.v1','workload':workload,'canary_matched':True,'key_generated_by_this_job':False,'App_key_present_in_approved_job':bool(os.environ.get('APP_PRIVATE_KEY')),
  'new_APP_token_issued':False,'OWNER_ACCEPTS_NEW_CHECKPOINTS':False,'PRODUCTION_GO':False})
 return workload

class Signer:
 def __init__(self,key,directory):
  self.key=pathlib.Path(directory)/'app-private.pem';self.key.write_text(key);self.key.chmod(0o600)
  self.public=subprocess.check_output(['openssl','pkey','-in',str(self.key),'-pubout'],stderr=subprocess.DEVNULL)
 def sign(self,data):
  p=self.key.parent/'sign-input';p.write_bytes(data)
  return subprocess.check_output(['openssl','dgst','-sha256','-sign',str(self.key),str(p)],stderr=subprocess.DEVNULL)
 def jwt(self,expired=False):
  now=int(time.time());payload={'iss':str(i.APP_ID),'iat':now-1200 if expired else now-30,'exp':now-600 if expired else now+300}
  message=(i.b64(i.canonical({'alg':'RS256','typ':'JWT'}))+'.'+i.b64(i.canonical(payload))).encode()
  return message.decode()+'.'+i.b64(self.sign(message))

class Transport(lab.GitFenceLab):
 def __init__(self,workspace,token,signer,workload):
  i.need(lab.REF==i.AUTH_REF,'SYNTHETIC_AUTHORITY_ONLY')
  self.workspace=pathlib.Path(workspace);self.workspace.mkdir();self.remote=REMOTE
  self.env={k:v for k,v in os.environ.items() if not k.startswith(('GIT_','GH_','GITHUB_','SSH_','APP_','CUSTODY_','ACTIONS_'))}
  self.env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_AUTHOR_NAME='MXM O04 staging acceptor',GIT_AUTHOR_EMAIL='synthetic@example.invalid',GIT_COMMITTER_NAME='MXM O04 staging acceptor',GIT_COMMITTER_EMAIL='synthetic@example.invalid',GIT_TERMINAL_PROMPT='0',GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode())
  self.git('init','-q');self.signer=signer;self.workload=workload
 def _publish(self,expected,state,lose_ack=False):
  i.need(state['marker']=='SYNTHETIC_ONLY' and state['root']==ROOT,'SYNTHETIC_ROOT')
  state=copy.deepcopy(state);state.pop('server_grant',None)
  envelope={'app_id':i.APP_ID,'installation_id':i.INSTALLATION_ID,'repository_id':i.REPO_ID,'authority_ref':i.AUTH_REF,'expected_old_oid':expected,'state_sha256':i.sha(i.canonical(state)),'workload':self.workload,'public_key_pem':self.signer.public.decode()}
  state['server_grant']={'envelope':envelope,'signature':base64.b64encode(self.signer.sign(i.canonical(envelope))).decode()}
  return super()._publish(expected,state,lose_ack)

def verify_state(state):
 state=copy.deepcopy(state);g=state.pop('server_grant');e=g['envelope']
 i.need(e['app_id']==i.APP_ID and e['repository_id']==i.REPO_ID and e['authority_ref']==i.AUTH_REF and e['state_sha256']==i.sha(i.canonical(state)),'READER_GRANT')
 i.need(i.openssl_verify(e['public_key_pem'].encode(),i.canonical(e),base64.b64decode(g['signature'])),'READER_SIGNATURE')
 return 'STAGING_ONLY_APP_ATTESTED_NEVER_OWNER'

def main():
 workload=custody()
 private=os.environ.get('APP_PRIVATE_KEY','')
 if not private:return
 # Key is available only after the canary and immutable-source boundary were
 # proven. This process is the issuer, not an untrusted writer holding a key.
 prior_binding=os.environ.get('CUSTODY_ACCEPTANCE_RUN','').split(':')
 i.need(len(prior_binding)==2 and all(x.isdigit() for x in prior_binding) and prior_binding[0]==workload['run_id'] and int(prior_binding[1])<int(workload['run_attempt']),'CUSTODY_RECEIPT_REQUIRED')
 status,prior=i.api('actions/runs/'+prior_binding[0]+'/attempts/'+prior_binding[1],os.environ['GH_TOKEN'])
 i.need(status==200 and prior['head_sha']==workload['sha'] and prior['head_branch']==i.CODE_BRANCH and prior['conclusion']=='success','CUSTODY_RECEPTION')
 lab.REF=i.AUTH_REF;results={};app_token=None
 with tempfile.TemporaryDirectory() as tmp:
  d=pathlib.Path(tmp);signer=Signer(private,d);del private
  # An actually expired App JWT must fail at GitHub, not in a local if.
  status,_=i.http('https://api.github.com/app/installations/'+str(i.INSTALLATION_ID)+'/access_tokens',signer.jwt(True),'POST',{'repository_ids':[i.REPO_ID],'permissions':{'contents':'write'}})
  i.need(status==401,'EXPIRED_APP_JWT_NOT_REJECTED');results['expired_app_jwt']={'server_HTTP':status,'tokens_issued':0}
  status,grant=i.http('https://api.github.com/app/installations/'+str(i.INSTALLATION_ID)+'/access_tokens',signer.jwt(),'POST',{'repository_ids':[i.REPO_ID],'permissions':{'contents':'write'}})
  i.need(status==201 and grant['permissions'].get('contents')=='write' and set(grant['permissions'])<={'contents','metadata'},'APP_TOKEN_ISSUANCE');app_token=grant['token'];expires=grant['expires_at'];del grant
  status,scope=i.http('https://api.github.com/installation/repositories',app_token)
  i.need(status==200 and [r['id'] for r in scope['repositories']]==[i.REPO_ID],'APP_REPOSITORY_SCOPE')
  results['token_scope']={'repository_ids':[i.REPO_ID],'permissions':{'contents':'write','metadata':'read'},'token_exported':False}
  try:
   native=os.environ['GH_TOKEN'];status,owner=i.api('releases/412686323',native);before=owner['body']
   i.need(i.sha(before.encode())==ROOT['owner_release_body_sha256'],'OWNER_ANCHOR')
   status,stop=i.api('git/ref/heads/mxm-o04-accepted-owner-1807-v1',native);i.need(stop['object']['sha']==ROOT['root_o04_stop_oid'],'STOP_OID')
   fixture_signer=SyntheticIssuer(d/'fixture');t=Transport(d/'transport',app_token,signer,workload);p=FixtureProtocol(t,fixture_signer,workload['sha'],lambda:int(time.time()))
   status,ref=i.api('git/ref/'+i.AUTH_REF.removeprefix('refs/'),native)
   if status==404:genesis=p.genesis();results['app_create_CAS']={'server_oid':genesis,'principal_app_id':i.APP_ID}
   else:i.need(status==200,'AUTH_REF_READ')
   oid,s=p.read();claimed=p.claim(oid,'approved-'+workload['run_id']+'-'+workload['run_attempt']);proposal=p.proposal(claimed,'SYNTHETIC_ONLY-'+workload['run_id']+'-'+workload['run_attempt'])
   mutations={'manifest':lambda q:q.update(manifest=base64.b64encode(b'SYNTHETIC_ONLY altered').decode()),'ciphertext':lambda q:q.update(ciphertext=base64.b64encode(b'SYNTHETIC_ONLY altered').decode()),'signature':lambda q:q.update(signature=base64.b64encode(b'bad').decode()),'source_SHA':lambda q:q['record'].update(source_SHA='0'*40),'version':lambda q:q['record'].update(version=99),'epoch':lambda q:q['record'].update(epoch=0),'expired_lease':lambda q:q['record'].update(lease_until=1)}
   for name,mutation in mutations.items():
    q=copy.deepcopy(proposal);mutation(q);old=p.read()[0]
    try:p.pending(claimed,q)
    except lab.Denied as ex:
     i.need(p.read()[0]==old,'REJECTION_MUTATED_REF');results[name]={'frontier':'PROTECTED_ISSUER_PROCESS_ONLY_KEY_HOLDER','reason':str(ex),'before':old,'after':old,'principal':i.APP_ID}
    else:raise i.Refused('INVALID_PROPOSAL_ACCEPTED')
   pending=p.pending(claimed,proposal)
   try:p.accept_fixture(pending,lose_ack=True)
   except lab.Unknown:pass
   else:raise i.Refused('ACK_FAULT_NOT_APPLIED')
   result=p.resolve(proposal['record']['operation_id'],proposal['record']['manifest_sha256']);i.need(result['status']=='SYNTHETIC_ACCEPTED_READBACK_NO_REPLAY','ACK_READBACK')
   accepted,state=p.read();results['valid_APP_CAS_lost_ACK']={'oid':accepted,'resolution':result,'principal':i.APP_ID,'reader':verify_state(state)}
   for name,fn in [('replay',lambda:p.accept_fixture(pending)),('old_OID',lambda:p.pending(claimed,proposal))]:
    old=p.read()[0]
    try:fn()
    except lab.Denied as ex:i.need(p.read()[0]==old,'REPLAY_MUTATED');results[name]={'before':old,'after':old,'frontier_refused':str(ex)}
    else:raise i.Refused('REPLAY_ACCEPTED')
   accepted_epoch=state['epoch'];current=p.claim(accepted,'expiry-session');valid_expiring=p.proposal(current,'SYNTHETIC_ONLY-expiry-'+workload['run_id']+'-'+workload['run_attempt'])
   duplicate=p.proposal(current,proposal['record']['operation_id']);old=p.read()[0]
   try:p.pending(current,duplicate)
   except lab.Denied as ex:i.need(str(ex)=='OPERATION_REPLAY' and p.read()[0]==old,'DUPLICATE_CONTROL');results['duplicate_operation']={'reason':str(ex),'before':old,'after':old}
   else:raise i.Refused('DUPLICATE_ACCEPTED')
   deadline=p.read()[1]['lease_until'];time.sleep(max(0,deadline-int(time.time())+1))
   try:p.pending(current,valid_expiring)
   except lab.Denied as ex:i.need(str(ex)=='LEASE_EXPIRED' and p.read()[0]==old,'EXPIRY_CONTROL');results['valid_signed_lease_expired']={'reason':str(ex),'deadline':deadline,'checked_at':int(time.time()),'before':old,'after':old}
   else:raise i.Refused('EXPIRED_LEASE_ACCEPTED')
   fresh=p.claim(old,'new-epoch-session');old_epoch=p.read()[1]['epoch'];i.need(old_epoch==accepted_epoch+2,'EPOCH_RECOVERY')
   try:p.pending(current,valid_expiring)
   except lab.Denied as ex:i.need(p.read()[0]==fresh,'STALE_SESSION_CHANGED');results['previous_epoch']={'reason':str(ex),'before':fresh,'after':fresh,'epoch':old_epoch}
   else:raise i.Refused('STALE_SESSION_ACCEPTED')
   # Finish in a durable no-lease STOP-only staging state. No new OWNER accepts.
   _,final_state=p.read();final_state.update(status='ACCEPTED',owner=None,session=None,lease_until=0,pending=None,mode='STAGED_READY_STOP_ONLY',OWNER_ACCEPTS_NEW_CHECKPOINTS=False,CAMPAIGN_RESTART_ALLOWED=False,PRODUCTION_GO=False)
   accepted=t._publish(fresh,final_state);results['stop_only_finalization']={'oid':accepted,'reader':verify_state(p.read()[1]),'mode':'STAGED_READY_STOP_ONLY'}
   # Existing independent no-bypass atomic rule must still apply to App token.
   genesis_oid=t.git('rev-list','--max-parents=0',accepted).decode().strip()
   for name,args in [('force_rollback',['push','--force',REMOTE,genesis_oid+':'+i.AUTH_REF]),('delete',['push',REMOTE,':'+i.AUTH_REF])]:
    r=t.git(*args,check=False);i.need(r.returncode!=0 and p.read()[0]==accepted and b'GH013' in r.stderr,'APP_BYPASSED_ATOMIC_RULE');results[name]={'before':accepted,'after':accepted,'server':'GH013'}
   status,owner=i.api('releases/412686323',native);i.need(owner['body']==before,'OWNER_CHANGED')
   status,stop=i.api('git/ref/heads/mxm-o04-accepted-owner-1807-v1',native);i.need(stop['object']['sha']==ROOT['root_o04_stop_oid'],'STOP_CHANGED')
   output('o042-app-proof',{'schema':'mxm.o042.app-proof.v1','app_id':i.APP_ID,'installation_id':i.INSTALLATION_ID,'workload':workload,'results':results,'authority_ref':i.AUTH_REF,'final_oid':accepted,'token_expires_at':expires,'token_exported':False,'OWNER_ACCEPTS_NEW_CHECKPOINTS':False,'CAMPAIGN_RESTART_ALLOWED':False,'PRODUCTION_GO':False})
  finally:
   if app_token:
    status,_=i.http('https://api.github.com/installation/token',app_token,'DELETE');i.need(status==204,'TOKEN_REVOCATION')
    status,_=i.api('git/ref/'+i.AUTH_REF.removeprefix('refs/'),app_token);i.need(status==401,'REVOKED_TOKEN_NOT_REJECTED')
    output('o042-revoked-token',{'server_HTTP':status,'revoked':True,'app_id':i.APP_ID,'authority_ref':i.AUTH_REF});app_token=None
if __name__=='__main__':main()
