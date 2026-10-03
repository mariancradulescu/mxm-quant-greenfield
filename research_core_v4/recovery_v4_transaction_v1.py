"""One fenced observation, idempotent publication, no recomputation recovery."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time
from research_core_v4 import asymmetric_recovery_v4_gate as g
from research_core_v4 import numeric_environment_v1 as n
ROOT=g.ROOT
PUBLICATION='research_core_v4/state/V4_CANONICAL_RESULT_PUBLICATION_V1.json'
FAILURE='failure-classification.json'
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True,stderr=subprocess.STDOUT).strip()
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def remote_head():
 git('fetch','--no-tags','origin','+refs/heads/'+g.BRANCH+':refs/remotes/origin/'+g.BRANCH)
 return git('rev-parse','origin/'+g.BRANCH)
def publish(expected,commit):
 # An ancestor reset must fail too; ordinary fast-forward alone is insufficient.
 for i in range(3):
  remote=remote_head()
  if remote==commit:return commit # acknowledgement loss; identical commit only
  if remote!=expected:raise PermissionError('REMOTE_REF_DRIFT_NO_REBASE_NO_RECOMPUTE')
  p=subprocess.run(['git','-C',str(ROOT),'push','--force-with-lease=refs/heads/'+g.BRANCH+':'+expected,'origin',commit+':refs/heads/'+g.BRANCH],capture_output=True,text=True)
  if p.returncode==0:
   if remote_head()!=commit:raise PermissionError('POST_PUBLICATION_REF_DRIFT')
   return commit
 # A final read may prove a successful push whose acknowledgement was lost.
 if remote_head()==commit:return commit
 raise PermissionError('PUBLICATION_UNCONFIRMED_NO_EXECUTION_RETRY')
def classify(lock_present,result_present,local_opening=False,local_result=False):
 if result_present:return 'RAW_CANONICAL_RESULT_DURABLE_NO_REEXECUTION_NO_INTERPRETATION'
 if not lock_present:return 'PRE_RESPONSE_INFRASTRUCTURE_FAILURE_NOT_A_SCIENTIFIC_RESULT'
 if local_result:return 'RAW_RESULT_RECOVERABLE_PUBLICATION_ONLY_NO_RECOMPUTATION'
 if local_opening:return 'RESPONSE_OPENING_STARTED_OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY'
 return 'OPENING_FENCE_DURABLE_RESPONSE_OPENING_UNKNOWN_NO_AUTOMATIC_RETRY'
def verify_science(science):
 assert git('-C',str(science),'rev-parse','HEAD')==g.SCI_HEAD
 for _,(rel,want) in g.FROZEN.items():assert digest(science/rel)==want
 # Hash-bind every source/support/authority artifact through the original runner
 # before fence creation in the offline numeric worker, never a weakened runner.
def invoke_worker(science,raw,temp,wheels,mode):
 subprocess.check_call(n.container_command(ROOT,science,raw,temp,wheels,mode))
def verify_candidate(candidate,prepared):
 # Verify the producer's original byte ordering; decoded integer keys are strings.
 from research_core_v4.publication_only_v1 import verify_candidate_metadata, SELF_FIELD
 x,_=verify_candidate_metadata(candidate.read_bytes(),prepared)
 x.pop(SELF_FIELD)
 return x

def persist_candidate(candidate,prepared,arm_head,fence,lock):
 verify_candidate(candidate,prepared)
 assert remote_head()==fence and git('rev-parse','HEAD')==fence
 result=ROOT/g.RESULT_REL;assert not result.exists()
 result.write_bytes(candidate.read_bytes())
 with result.open('rb') as f:os.fsync(f.fileno())
 publication={'schema':'mxm.v4.raw-canonical-publication.v1','arm_commit':arm_head,'fence_commit':fence,
    'result_sha256':digest(result),'owner_run_id':lock['owner_run_id'],
    'prepared':prepared,'attempt_fence':lock,'interpretation_performed':False,'accepted_canonical_result_count':1}
 write(ROOT/PUBLICATION,publication)
 st=g.load(g.STATE_REL);st['status']='FIRST_REAL_V4_RAW_CANONICAL_RESULT_PERSISTED_NOT_INTERPRETED'
 fw=st['first_wave'];fw['development_execution_completed']=True;fw['development_raw_result_persisted']=True;fw['development_result_interpreted']=False;fw['current_recovery_execution_authorized']=False
 p=st['recovery_v4_preparation'];p.update(status='RAW_CANONICAL_RESULT_PERSISTED_NOT_INTERPRETED',accepted_canonical_result_count=1,process_attempts_started=1,arm_present=True,attempt_lock_present=True,canonical_result_present=True,real_execution_authorized=False)
 (ROOT/g.STATE_REL).write_text(json.dumps(st,indent=2,sort_keys=True)+'\n')
 git('add',g.RESULT_REL,PUBLICATION,g.STATE_REL);git('commit','-m','v4: persist single raw result with exact transaction and numeric provenance')
 final=git('rev-parse','HEAD');publish(fence,final)
 assert subprocess.check_output(['git','-C',str(ROOT),'show',final+':'+g.RESULT_REL])==candidate.read_bytes()
 return {'status':'RAW_CANONICAL_RESULT_DURABLE_NOT_INTERPRETED','commit':final,'result_sha256':digest(result)}

def run_transaction(science,raw,temp,wheels,prelock):
 arm_head=git('rev-parse','HEAD');fence=None;fence_published=False;candidate=temp/'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json'
 try:
  assert os.environ.get('GITHUB_RUN_ATTEMPT')=='1'
  binding=g.validate_arm_binding(ROOT/g.ARM_REL)
  pre=json.loads(prelock.read_text())
  assert pre['status']=='PASS_RECOVERY_V4_PRELOCK_RUNTIME_VALIDATION' and pre['arm_commit']==arm_head
  assert pre['arm_document_sha256']==binding['arm_document_sha256']
  assert pre['all_18_sha256_match'] and pre['exact_plaintext_series_count']==18
  g.verify_plaintext_dir(raw,g.expected_series())
  assert not candidate.exists() and not candidate.with_suffix('.json.opening.lock').exists()
  verify_science(science)
  invoke_worker(science,raw,temp,wheels,'--prepare')
  prepared=json.loads((temp/'prepared.json').read_text());assert prepared['response_opened'] is False
  assert remote_head()==arm_head and git('rev-parse','HEAD')==arm_head
  lock={'schema':'mxm.v4.opening-fence.v1','arm_commit':arm_head,'arm_document_sha256':binding['arm_document_sha256'],
        'owner_run_id':os.environ['GITHUB_RUN_ID'],'owner_run_attempt':1,
        'phase':'OPENING_FENCED_RESPONSE_OPENING_UNKNOWN','scientific_attempt_status':'UNKNOWN_NOT_A_SCIENTIFIC_RESULT',
        'logical_computation_id':g.load(g.V4_ACTIVE_REL)['logical_computation_id'],
        'prelock_report_sha256':digest(prelock),'prepared_sha256':digest(temp/'prepared.json'),
        'environment':prepared['environment'],'automatic_retry':False,'canonical_result_limit':1}
  write(ROOT/g.LOCK_REL,lock)
  git('add',g.LOCK_REL);git('commit','-m','v4: fence single authorized response opening before worker invocation')
  fence=git('rev-parse','HEAD');publish(arm_head,fence);fence_published=True
  # Reverify ownership and ref immediately before launch. Replays never reach here.
  assert remote_head()==fence and git('rev-parse','HEAD')==fence
  assert not (ROOT/g.RESULT_REL).exists()
  invoke_worker(science,raw,temp,wheels,'--execute')
  verify_candidate(candidate,prepared)
  return persist_candidate(candidate,prepared,arm_head,fence,lock)
 except BaseException as exc:
  # This diagnostic never authorizes a second observation; absence of evidence is unknown.
  opening=candidate.with_suffix(candidate.suffix+'.opening.lock').exists()
  classification=classify(fence_published,False,opening,candidate.exists())
  if fence is not None and not fence_published:
   try:
    remote=remote_head()
    classification=classify(remote==fence,False,opening,candidate.exists()) if remote in (arm_head,fence) else 'LOCK_PUBLICATION_OR_REF_DRIFT_UNCONFIRMED_NO_AUTOMATIC_RETRY'
   except Exception: classification='LOCK_PUBLICATION_UNCONFIRMED_NO_AUTOMATIC_RETRY_NOT_A_SCIENTIFIC_RESULT'
  failure={'schema':'mxm.v4.runtime-failure-classification.v1','classification':classification,
     'arm_commit':arm_head,'fence_commit':fence,'owner_run_id':os.environ.get('GITHUB_RUN_ID'),
     'exception_type':type(exc).__name__,'automatic_retry':False,'market_outcome_interpreted':False}
  (temp/FAILURE).write_text(json.dumps(failure,sort_keys=True)+'\n')
  raise

def recover_completed_result(candidate:Path,prepared_file:Path,fence_head:str,decision:dict):
    # This path has no worker/decrypt call and cannot generate a second observation.
    assert decision.get('publication_only_authorized') is True
    assert decision.get('fence_commit')==fence_head and decision.get('result_sha256')==digest(candidate)
    assert isinstance(decision.get('decision_id'),str) and bool(decision['decision_id'])
    lock=json.loads(subprocess.check_output(['git','-C',str(ROOT),'show',fence_head+':'+g.LOCK_REL]))
    assert digest(prepared_file)==lock['prepared_sha256'],'recovered attestation differs from durable fence'
    prepared=json.loads(prepared_file.read_text());verify_candidate(candidate,prepared)
    remote=remote_head()
    # Completion whose acknowledgement was lost is already accepted, never rewritten.
    existing=subprocess.run(['git','-C',str(ROOT),'show',remote+':'+g.RESULT_REL],capture_output=True)
    if existing.returncode==0:
        assert existing.stdout==candidate.read_bytes(),'a different canonical result already exists'
        return {'status':'IDENTICAL_CANONICAL_RESULT_ALREADY_DURABLE','commit':remote}
    assert remote==fence_head and git('rev-parse','HEAD')==fence_head,'publication-only recovery requires exact surviving fence head; no rebase'
    assert g.load(g.STATE_REL)['recovery_v4_preparation']['accepted_canonical_result_count']==0
    return persist_candidate(candidate,prepared,lock['arm_commit'],fence_head,lock)

def main():
 a=argparse.ArgumentParser();a.add_argument('--science',type=Path,required=True);a.add_argument('--raw',type=Path,required=True);a.add_argument('--temporary',type=Path,required=True);a.add_argument('--wheels',type=Path,required=True);a.add_argument('--prelock',type=Path,required=True);x=a.parse_args()
 print(json.dumps(run_transaction(x.science,x.raw,x.temporary,x.wheels,x.prelock),sort_keys=True))
if __name__=='__main__':main()
