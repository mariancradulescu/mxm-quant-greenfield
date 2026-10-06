"""Post-supersession preservation guard; not part of the economic policy kernel."""
import hashlib,json,subprocess,sys
from pathlib import Path
BASE='f85abce6185027434c6c173c581db4fe30e589b4'
def git(*args):return subprocess.check_output(['git',*args])
head=git('rev-parse','HEAD').decode().strip()
paths=git('ls-tree','-r','--name-only',BASE,'research_core_v4/triad_v7').decode().splitlines()
for p in paths:assert Path(p).read_bytes()==git('show',BASE+':'+p),p
changed=git('diff','--name-only',BASE,head,'research_core_v3','research_core_v4','research_v3').decode().splitlines()
assert set(changed)<= {'research_core_v4/state/V4_STATE.json','research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json'},changed
p=Path('research_core_v4/triad_v7/distributed/FINAL_V7_RUNTIME_BLOCKER_AUTHORITY_V1.json');digest=hashlib.sha256(p.read_bytes()).hexdigest();assert digest=='c519897953ad361d6949a76f14cb0e374705b1d296378179f58ac375daf34fd8'
a=json.loads(p.read_text());assert a['exact_v7_parked'] and not any(a['authorization'].values()) and all(v==0 for v in a['counters'].values())
assert not Path('research_core_v4/triad_v7/EXECUTION_ARM_V1.json').exists()
allpaths=git('ls-tree','-r','--name-only','HEAD').decode().splitlines();assert not any('/triad_v8/' in p for p in allpaths)
s=json.loads(Path('adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json').read_text());assert s['triad_v7_parked_unchanged'] and not s['protected_forward_opened'] and not s['confirmation_opened']
raw=Path(s['raw_result_ref']);assert hashlib.sha256(raw.read_bytes()).hexdigest()==s['raw_result_sha256']
spec=Path('adaptive_competition/state/ADAPTIVE_COMPETITION_POLICY_V1_FROZEN_SPEC.json');assert hashlib.sha256(spec.read_bytes()).hexdigest()==s['exact_policy_spec_hash']
for p,h in json.loads(spec.read_text())['implementation_hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
v4=json.loads(Path('research_core_v4/state/V4_STATE.json').read_text());assert v4['current_authority']=='adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json'
assert v4['triad_v7_final_runtime_blocker_authority']==json.loads(git('show',BASE+':research_core_v4/state/V4_STATE.json'))['triad_v7_final_runtime_blocker_authority']
assert v4['current_next_action_type']==s['next_action']
result={'status':'PASS_V7_BYTE_PRESERVATION_WITH_AUTHORIZED_ADAPTIVE_OPERATIONAL_SUPERSESSION','validated_head':head,'baseline_head':BASE,'v7_files_compared':len(paths),'v7_authority_sha256':digest,'v7_mutations':0,'Monte_Carlo_trials':0,'broker_contacts':0,'orders':0,'raw_result_unchanged':True,'V8_present':False,'adaptive_authority_is_current':True}
if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,sort_keys=True))
