"""Post-attempt validation only; no network, secret environment or broker APIs."""
import hashlib,json,subprocess,argparse
from pathlib import Path
from .read_only_auth_preflight_v3 import validate_safe,EXPECTED_FINGERPRINT,ALLOWED,FORBIDDEN_FLAGS
STATE=Path('adaptive_competition/state')
BASE='10c244a6767d466e019c0b13ce80c444210db090'
def git(*args):return subprocess.check_output(['git',*args])
def digest(b):return hashlib.sha256(b).hexdigest()
def validate():
 r=json.loads((STATE/'MACHINE_SIDE_READ_ONLY_AUTH_PREFLIGHT_RESULT_V3.json').read_text());validate_safe(r)
 v=json.loads((STATE/'MACHINE_SIDE_READ_ONLY_AUTH_PREFLIGHT_V3_VALIDATION.json').read_text())
 a=json.loads((STATE/'READ_ONLY_AUTH_PREFLIGHT_ARM_V3.json').read_text())
 assert r['arm_sha256']==digest((STATE/'READ_ONLY_AUTH_PREFLIGHT_ARM_V3.json').read_bytes())
 assert r['exact_source_head']==a['exact_source_head'];execution=r['execution_head']
 assert git('rev-parse',execution+'^').decode().strip()==r['exact_source_head']
 assert git('diff','--name-only',r['exact_source_head'],execution).decode().splitlines()==['adaptive_competition/state/READ_ONLY_AUTH_PREFLIGHT_ARM_V3.json']
 for p,h in a['implementation_hashes'].items():
  assert digest(git('show',r['exact_source_head']+':'+p))==h,p
  if p!='adaptive_competition/state/MACHINE_SIDE_READ_ONLY_AUTH_PREFLIGHT_V3_AUTHORITY.json':assert digest(Path(p).read_bytes())==h,p
 assert r['broker_text_used_as_identity_or_region_gate'] is False
 assert r['implementation_sha256']==a['implementation_sha256'] and r['workflow_sha256']==a['workflow_sha256']
 assert digest((STATE/'MACHINE_SIDE_READ_ONLY_AUTH_PREFLIGHT_RESULT_V3.json').read_bytes())==v['authentic_result_sha256']
 assert set(r['request_contact_flags'])==ALLOWED and not any(r[k] for k in FORBIDDEN_FLAGS)
 assert r['refresh_token_present'] and not r['refresh_token_used'] and all(r['required_runtime_secret_presence'].values())
 for p,h in v['historical_preservation_hashes'].items():assert digest(Path(p).read_bytes())==h and Path(p).read_bytes()==git('show',BASE+':'+p),p
 budget=json.loads(Path('research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json').read_text())['current'];assert budget=={'total':84,'used':21,'remaining':63,'refunds':0,'economic_outcomes_opened':29}
 paths=git('ls-tree','-r','--name-only',BASE,'research_core_v4/triad_v7').decode().splitlines()
 for p in paths:assert Path(p).read_bytes()==git('show',BASE+':'+p),p
 current=json.loads((STATE/'ADAPTIVE_COMPETITION_CURRENT_STATE.json').read_text());assert current['classification']=='MIXED_FORECAST_AND_FRICTION_LIMITATION' and current['triad_v7_parked_unchanged']
 assert not current['protected_forward_opened'] and not current['confirmation_opened'] and not current['new_identity_authorized'] and not current['new_acquisition']
 expected='PENDING_INDEPENDENT_AUDIT_OF_MACHINE_SIDE_READ_ONLY_AUTH_V3_BEFORE_ANY_MARKET_DATA_ACQUISITION' if r['auth_proven'] else 'PENDING_INDEPENDENT_AUDIT_OF_MACHINE_SIDE_READ_ONLY_AUTH_V3_FAILURE'
 assert current['next_action']==expected and current['machine_side_auth_status']==r['status']
 root=json.loads(Path('CURRENT_STATE.json').read_text());v4=json.loads(Path('research_core_v4/state/V4_STATE.json').read_text());authority=json.loads((STATE/'ADAPTIVE_COMPETITION_AUTHORITY_V1.json').read_text())
 assert root['next_action']==v4['current_next_action_type']==v4['next_action']==authority['current_operation']==expected
 return {'status':'PASS_POST_ATTEMPT_AUTH_V3_INTEGRITY','validated_publication_head':git('rev-parse','HEAD').decode().strip(),'execution_head':execution,'auth_status':r['status'],'authentic_result_sha256':v['authentic_result_sha256'],'safe_schema_pass':True,'historical_V1_raw_and_frozen_spec_byte_identical':True,'historical_V2_preflight_files_byte_identical':True,'budget_byte_identical':True,'search_budget_used':21,'search_budget_remaining':63,'triad_v7_files_byte_identical':len(paths),'protected_forward_closed':True,'confirmation_closed':True,'history_order_refresh_subscription_requests':False,'network_contact_by_this_validator':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path);args=p.parse_args();result=validate()
 if args.out:args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
 print(json.dumps(result,sort_keys=True))
