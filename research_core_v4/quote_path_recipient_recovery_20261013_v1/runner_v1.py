"""One recipient-verified summary recovery. Never calls market/science kernels."""
import json,os,pathlib,tempfile,subprocess,hashlib
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUBLIC_ROOT
e=rt.e
P='research_core_v4/quote_path_recipient_recovery_20261013_v1/'
WF='.github/workflows/mxm-quote-path-recipient-recovery-20261013-v1.yml'
PHASE='GATE'
def need(value,code):e.w.old.need(bool(value),code)
def inventory(ref):
 return dict(z.split('\t',1)[::-1] for z in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
def gate():
 head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head)
 auth=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
 need(auth['authority']=='EXPLICIT_OWNER_LIFT_STOP_SUMMARY_RECOVERY_20261013','AUTHORITY')
 need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','EVENT_ATTEMPT')
 need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/'+WF+'@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
 need(auth['broker_requests']==0 and auth['scientific_calculations']==0 and not auth['orders'] and not auth['protected_forward'],'RECOVERY_SCOPE')
 need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'EXPIRED')
 e.a.ancestor(auth['base_head'],head)
 old,new=inventory(auth['base_head']),inventory(head)
 need(all(new.get(path)==blob for path,blob in old.items()),'ALL_OLD_FILES_PRESERVED')
 for path,digest in auth['bindings'].items():need(e.w.old.filehash(path)==digest,'SOURCE_DRIFT')
 e.w.old.verify_science()
 run=e.w.old.api('actions/runs/'+str(auth['source_run']))
 need(run['conclusion']=='success' and run['head_sha']==auth['source_head'] and run['run_attempt']==1,'SOURCE_RUN')
 release=e.w.old.api('releases/'+str(auth['source']['release_id']))
 need(release['target_commitish']==auth['source_head'],'SOURCE_RELEASE')
 pub=e.a.ROOT/auth['recipient_public_path']
 spki=subprocess.run(['openssl','pkey','-pubin','-in',str(pub),'-outform','DER'],capture_output=True,check=True).stdout
 need(hashlib.sha256(spki).hexdigest()==auth['recipient_spki_sha256'],'RECIPIENT_PAIR_BINDING')
 need(not e.w.v2.existing_ref(auth['one_use_ref']),'CONSUMED')
 e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':head})
 return head,auth
def main():
 global PHASE
 os.umask(0o077);head,auth=gate()
 with tempfile.TemporaryDirectory(prefix='mxm-verified-summary-',dir=os.environ['RUNNER_TEMP']) as directory:
  tmp=pathlib.Path(directory);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY_BINDING')
  PHASE='OWNER_EXISTING_RESULT_READBACK';full,proof=load_asset(key,fp,tmp,auth['source'])
  need(type(full)==dict and type(full.get('summary'))==dict,'PRIMARY_SUMMARY_SCHEMA')
  summary=full['summary'];need(summary['schema']=='mxm.quote.path.empirical.summary.v1','SUMMARY_SCHEMA')
  need(summary['mechanism']=='PRICE_SPREAD_TEMPORAL_ORDER_RESPONSE_V1','MECHANISM_BINDING')
  need(summary['design_sha256']==auth['scientific_design_sha256'],'DESIGN_BINDING')
  need(summary['broker_requests']==0 and summary['orders']==0 and summary['protected_forward'] is False,'SUMMARY_SCOPE')
  summary_hash=e.a.sha(e.a.enc(summary))
  envelope={'schema':'mxm.verified.recipient.existing.summary.v1','source_run':auth['source_run'],'source_head':auth['source_head'],
            'original_primary':proof,'recipient_spki_sha256':auth['recipient_spki_sha256'],
            'summary_canonical_sha256':summary_hash,'summary':summary,
            'OWNER_READBACK_SUCCESS':True,'NUMERIC_SUCCESS':True,'DELIVERY_SUCCESS':False,
            'delivery_state':'PENDING_RECIPIENT_DECRYPTION','scientific_recalculation':False}
  PHASE='VERIFIED_RECIPIENT_CIPHERTEXT_PUBLICATION'
  status={'schema':e.w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'NOT_PERSISTED','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID'])}
  public_path=PUBLIC_ROOT+'OWNER_QUOTEPATH_RECIPIENT_RECOVERY_V1.json'
  release=e.w.old.api('releases',{'tag_name':'mxm-quotepath-recipient-recovery-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],
   'target_commitish':head,'name':'MXM owner readback completed; recipient delivery pending','prerelease':True,
   'body':validate_public_blob(public_path,status).decode()})
  delivered=e.upload_extra(release,tmp,e.a.ROOT/auth['recipient_public_path'],envelope,'quotepath-verified-recipient-summary.mxmenc')
  out=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');out.release=release
  out.encrypted({'schema':'mxm.recipient.summary.recovery.attestation.v1','source':proof,'delivered':delivered,
                 'recipient_spki_sha256':auth['recipient_spki_sha256'],'summary_canonical_sha256':summary_hash,
                 'source_run':auth['source_run'],'source_head':auth['source_head'],'owner_readback_success':True,
                 'recipient_delivery_success':False,'scientific_calculations':0},'quotepath-recipient-recovery-attestation.mxmenc')
  status.update(status='PASS',encrypted_artifact_name=delivered['name'],encrypted_artifact_sha256=delivered['ciphertext_sha256'])
  body=validate_public_blob(public_path,status)
  e.w.old.api('releases/'+str(release['id']),{'body':body.decode()},method='PATCH')
  need(e.w.old.api('releases/'+str(release['id']))['body'].encode()==body,'PUBLIC_STATUS_READBACK')
  e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['owner_readback_completion_ref'],'sha':head})
  print(body.decode().strip(),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
