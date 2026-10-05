"""Phase-aware historical publication integrity. No evaluator/market imports."""
import json,subprocess,tempfile
from pathlib import Path
from research_core_v4 import publication_only_v1 as p
PUBLICATION='52152947d8f3b157c3750d1baf634cea014f6483'
def check_state(s):
 p.require(s['governance']['candidate_frozen_count']==0,'no candidate')
 p.require(s['governance']['protected_forward_opened'] is False,'forward closed')
 h=s['recovery_v4_preparation'];f=s['first_wave']
 p.require(h['accepted_canonical_result_count']==h['accepted_canonical_result_limit']==1,'singleton history')
 p.require(h['real_execution_authorized'] is False and h['automatic_retry'] is False,'recovery disabled')
 p.require(f['development_execution_completed'] is True and f['development_raw_result_persisted'] is True,'completed historical result')
 p.require(f['current_recovery_execution_authorized'] is False,'no new recovery')
 w=s.get('next_prospective_wave',{})
 for key in ('response_execution_authorized','real_response_authorized','candidate_promotion_authorized','new_acquisition_authorized','ARM_present','protected_forward_opened'):
  p.require(w.get(key) is False,'prospective boundary '+key)
def verify(root):
 root=Path(root).resolve();head=p.git(root,'rev-parse','HEAD').decode().strip()
 p.require(p.git(root,'merge-base',PUBLICATION,head).decode().strip()==PUBLICATION,'publication ancestor')
 p.require(p.git(root,'rev-list','--parents','-n','1',PUBLICATION).decode().split()==[PUBLICATION,p.FENCE],'original atomic publication')
 rels=[p.RESULT_REL,p.ARM_REL,p.FENCE_REL,p.PUB_REL,p.AUDIT_REL,p.PREPARED_REL,p.FAILURE_REL,'research_core_v4/publication_only_v1.py']
 audit=json.loads((root/p.AUDIT_REL).read_bytes());rels+=[n for n in audit['recovery_control_files_sha256'] if not n.startswith('.github/workflows/')]
 for rel in set(rels):p.require((root/rel).read_bytes()==p.git(root,'show',PUBLICATION+':'+rel),'preserved publication '+rel)
 for rel in (n for n in audit['recovery_control_files_sha256'] if n.startswith('.github/workflows/')):
  prior=p.git(root,'show','73e991a98db5c51e882118006d7359edf3348ec1:'+rel).decode()
  expected=prior.replace('python -m research_core_v4.publication_only_v1 --verify-canonical \"$PWD\"','python -m research_core_v4.post_publication_integrity_v1 \"$PWD\"\n            python -m unittest -q tests.test_v4_factor_residual tests.test_v4_post_quote_preoutcome')
  p.require((root/rel).read_text()==expected,'only phase routing change '+rel)
 # Preserve the original exact-parent/uninterpreted verifier, execute against its
 # immutable historical tree, then check current governance separately.
 with tempfile.TemporaryDirectory() as d:
  tree=Path(d)/'historical'
  p.git(root,'worktree','add','--detach',str(tree),PUBLICATION)
  try:old=p.verify_canonical(tree)
  finally:p.git(root,'worktree','remove','--force',str(tree))
 check_state(json.loads((root/p.STATE_REL).read_bytes()))
 return {'status':'PASS_HISTORICAL_PUBLICATION_CURRENT_GOVERNANCE','head':head,'historical_publication_head':PUBLICATION,'result_sha256':p.RAW_SHA,'historical_verifier_status':old['status'],'scientific_response_calls':0,'broker_contacts':0}
if __name__=='__main__':
 import sys
 print(json.dumps(verify(Path(sys.argv[1] if len(sys.argv)>1 else '.')),sort_keys=True))
