"""Recover checkpoint 512 and its orphan raw receipt; finite fresh campaign."""
import os,json,pathlib,tempfile,gzip,base64,datetime,urllib.error
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as v1
from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2 as storage,archive_v2 as ar
from research_core_v4.critical_frontier_repair_20261014_v2.preserve_stop_v2 import api
E=v1.E;need=v1.need
P='research_core_v4/checkpoint_512_resume_20261014_v1/'
def check_anchor(a):
 b=json.loads(api('releases/'+str(a['anchor_release']))['body'])
 need((b['generation'],b['identities_evaluated'],b['remaining'])==(512,51,1511),'CHECKPOINT_DRIFT')
 need(b['state']=='STOP_EXPLICIT_OPERATIONAL_LIMIT' and b['pending_request_count']==0,'CHECKPOINT_STOP_STATE')
 need(b['current_journal']['ciphertext_sha256']==a['checkpoint_ciphertext_sha256'],'CHECKPOINT_HASH')
 need(b['actual_orders']==0 and not b['HARD21'] and not b['pilot_executed'],'GOVERNANCE_FENCE')
 need(b['new_requests']['BID_ASK']<450000 and b['new_requests']['M5']<12000,'REQUEST_CAP')
 return b
def main():
 os.umask(0o077);a=json.loads((E.a.ROOT/(P+'AUTHORITY_V1.json')).read_text());head=os.environ['GITHUB_SHA']
 need(os.environ['GITHUB_RUN_ATTEMPT']=='1','NO_UNCONTROLLED_RETRY')
 need(os.environ['GITHUB_REF']=='refs/heads/'+E.w.old.BRANCH,'BRANCH_SCOPE')
 need(os.environ['GITHUB_WORKFLOW_REF']==E.w.old.REPO+'/'+a['workflow']+'@refs/heads/'+E.w.old.BRANCH,'WORKFLOW_SCOPE')
 need(a['authority']=='EXPLICIT_OWNER_FULL_NATIVE_FRONTIER_AUTONOMOUS_20261014' and a['broker_requests']==0,'AUTHORITY')
 need(datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(a['expires_utc']),'EXPIRED')
 E.a.ancestor(a['base_head'],head)
 for p,h in a['bindings'].items():need(E.w.old.filehash(p)==h,'SOURCE_BINDING')
 for file in (v1.P+'EXECUTION_V1.json','research_core_v4/critical_frontier_repair_20261014_v2/REPAIR_AUTHORITY_V2.json'):
  for p,h in json.loads((E.a.ROOT/file).read_text())['bindings'].items():need(E.w.old.filehash(p)==h,'SCIENTIFIC_AND_REPAIR_FREEZE')
 previous=api('actions/runs/'+str(a['previous_run']));need(previous['status']=='completed' and previous['conclusion']=='failure','PREVIOUS_TERMINAL')
 anchor=check_anchor(a)
 with tempfile.TemporaryDirectory(prefix='mxm-checkpoint512-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY')
  store=storage.RotatingStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp)
  manifest=store.restore(anchor['current_journal']);need(manifest['generation']==512,'OWNER_MANIFEST_GENERATION')
  db=ar.dbopen(tmp/'native.sqlite');storage.track(db);state=storage.restore(db,store)
  need(state['generation']==512 and state['identity_cursor']==51,'RESTORED_CURSOR')
  need(state['errors'][-1]['cause']=='REMOTE_DOWNLOAD_FAILURE','DIFFERENT_CAUSE_NO_BLIND_RESUME')
  orphan=api('releases/assets/'+str(a['orphan_asset_id']));need(orphan['digest']=='sha256:'+a['orphan_ciphertext_sha256'],'ORPHAN_DIGEST')
  blob=E.w.old.download(orphan['browser_download_url'],orphan['size']);need(E.a.sha(blob)==a['orphan_ciphertext_sha256'],'ORPHAN_CIPHER_READBACK')
  packed=E.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp);raw=gzip.decompress(packed);delta=E.w.old.crypto.strict_json(raw);need(v1.encode(delta)==raw,'ORPHAN_CANONICAL')
  receipts=delta.get('raw',[]);need(len(receipts)==16,'ORPHAN_RECEIPT_COUNT')
  for z in receipts:
   req=z['request'];wire=db.execute('SELECT z,h FROM wire WHERE s=? AND k=? AND a=? AND b=?',(req['s'],req['k'],req['a'],req['b'])).fetchone()
   need(wire is not None and wire[1]==E.a.sha(base64.b64decode(z['response_b64'])),'RESTORED_WIRE_RESPONSE_SHA')
   need(not ar.actionable(db,req['s'],req['k'],req['a'],req['b']),'NO_DUPLICATE_REQUEST_MASK')
  # Keep an immutable OWNER-verified locator to the previously uploaded raw
  # response delta that had not become the anchor's ledger head on download failure.
  proof={'schema':'mxm.checkpoint512.independent.owner.recovery.v1','observer_run':int(os.environ['GITHUB_RUN_ID']),'source_head':head,'previous_failed_run':a['previous_run'],'checkpoint':anchor['current_journal'],'generation':512,'identity_cursor':51,'remaining':1511,'bars':db.execute('SELECT count(*) FROM bar').fetchone()[0],'ticks':db.execute('SELECT count(*) FROM tick').fetchone()[0],'wire_rows':db.execute('SELECT count(*) FROM wire').fetchone()[0],'coverage_states':ar.proof_table(db),'recovered_orphan_raw':{'id':orphan['id'],'name':orphan['name'],'size':orphan['size'],'ciphertext_sha256':a['orphan_ciphertext_sha256'],'gzip_sha256':E.a.sha(packed),'canonical_sha256':E.a.sha(raw),'authenticated_response_count':len(receipts),'all_wire_sha_matched':True,'all_blocked_from_resend':True},'cause':'TRANSIENT_GITHUB_REMOTE_DOWNLOAD_FAILURE_RESOLVED_BY_NEW_OWNER_READBACK','broker_requests':0,'actual_orders':0,'pilot_executed':False,'HARD21':False,'alpha_certified':False}
  out=v1.FrontierStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,'real')
  out.release=api('releases','POST',{'tag_name':'mxm-checkpoint512-recovery-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM verified checkpoint 512 recovery and raw provenance','prerelease':True,'body':json.dumps({'state':'OWNER_PROOF_PENDING','broker_requests':0})})
  meta=out.encrypted(json.loads(v1.encode(proof)),'checkpoint512-owner-recovery-proof.mxmenc')
  safe={k:proof[k] for k in ('schema','observer_run','source_head','previous_failed_run','generation','identity_cursor','remaining','bars','ticks','wire_rows','coverage_states','cause','broker_requests','actual_orders','pilot_executed','HARD21','alpha_certified')}
  safe.update(state='CHECKPOINT512_OWNER_READBACK_AND_RAW_RECOVERY_PASS',OWNER_READBACK_SUCCESS=True,recovered_raw_count=16,primary=meta)
  api('releases/'+str(out.release['id']),'PATCH',{'body':json.dumps(safe,sort_keys=True)})
  check_anchor(a);need(api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==head,'LIVE_HEAD_DRIFT')
  for status in ('in_progress','queued'):
   runs=api('actions/workflows/mxm-native-frontier-repaired-20261014-v2.yml/runs?status='+status+'&per_page=100')['workflow_runs'];need(not runs,'OTHER_WRITER_ACTIVE')
  claim='mxm-native-frontier-next-from-512'
  try:api('git/ref/tags/'+claim)
  except urllib.error.HTTPError as ex:need(ex.code==404,'CLAIM_READ_ERROR')
  else:raise RuntimeError('GENERATION_ALREADY_DISPATCHED_NO_RETRY')
  api('git/refs','POST',{'ref':'refs/tags/'+claim,'sha':head})
  api('actions/workflows/mxm-native-frontier-repaired-20261014-v2.yml/dispatches','POST',{'ref':E.w.old.BRANCH,'inputs':{'previous_generation':'512'}})
  safe.update(state='VERIFIED_NEW_FINITE_CAMPAIGN_DISPATCH_ACCEPTED',claim=claim,proof_release_id=out.release['id'])
  api('releases/'+str(out.release['id']),'PATCH',{'body':json.dumps(safe,sort_keys=True)});print(json.dumps(safe,sort_keys=True),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as ex:
  import re
  code=str(ex) if re.fullmatch('[A-Z0-9_]{1,100}',str(ex)) else type(ex).__name__
  print('FAIL_CLOSED_CHECKPOINT512_RECOVERY_'+code,flush=True);raise SystemExit(1) from None
