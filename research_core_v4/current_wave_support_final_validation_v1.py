"""Exact final-head support delivery validator; synthetic or metadata only."""
import hashlib,json,subprocess,unittest
from pathlib import Path
from research_core_v4.tests.test_current_wave_support_v1 import Parity,Checkpoints
S='research_core_v4/state/';P='STRICT_PREOUTCOME_V2_';START='6f776c535b8df9cf87aaeddbafc0f47c643e77f5'
AUTH=S+P+'CURRENT_WAVE_SUPPORT_EXECUTION_AUTHORITY_V1.json'
REPORT=S+P+'CURRENT_WAVE_SUPPORT_EXECUTION_DELIVERY_REPORT_V1.json'
STATE=['research_core_v4/state/V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def git(*a):return subprocess.check_output(['git',*a])
class Delivery(unittest.TestCase):
 def test_immutable_accepted_bindings(self):
  f=load(S+P+'CURRENT_WAVE_SUPPORT_IMPLEMENTATION_FREEZE_V1.json')
  for p,h in f['bindings'].items():self.assertEqual(sha(p),h,p)
 def test_implementation_commit_ancestry(self):
  a=load(AUTH)
  for h in a['commit_ancestry_before_delivery']:
   self.assertEqual(subprocess.run(['git','merge-base','--is-ancestor',h,'HEAD']).returncode,0)
 def test_report_changed_file_hashes(self):
  r=load(REPORT)
  for p,h in r['changed_files_sha256'].items():self.assertEqual(sha(p),h,p)
  changed=set(git('diff','--name-only',START,'HEAD').decode().splitlines())
  self.assertEqual(changed,set(r['changed_files_sha256'])|{REPORT})
 def test_historical_canonical_fields_preserved(self):
  allowed={'current_authority','current_authority_sha256','current_next_action_type','current_operational_status','current_operation','current_state_guard_ref','next_action','stop_boundary','status','strict_v2_current_testability_wave','strict_v2_current_wave_support_execution','historical_strict_v2_current_testability_wave','as_of_date'}
  for p in STATE:
   before=json.loads(git('show',START+':'+p));after=load(p)
   for k,v in before.items():
    if k not in allowed:self.assertEqual(json.dumps(after.get(k),sort_keys=True,separators=(',',':')).encode(),json.dumps(v,sort_keys=True,separators=(',',':')).encode(),(p,k))
   self.assertEqual(after['historical_strict_v2_current_testability_wave'],before['strict_v2_current_testability_wave'])
   if p!=STATE[0]:self.assertEqual(after['status'],before['status'])
 def test_exact_wave_and_no_global_selection(self):
  a=load(AUTH);self.assertEqual(a['current_wave_count'],5);self.assertTrue(a['global_ledgers_unchanged']);self.assertFalse(a['global_functional_reapplied'])
  changes=git('diff','--name-only',START,'HEAD').decode().splitlines()
  for p in changes:
   if p.endswith('.json') and p not in STATE:self.assertTrue('CURRENT_WAVE_SUPPORT_' in p or p.endswith('STRICT_PREOUTCOME_V2_CURRENT_WAVE_DEPENDENCE_GEOMETRY_RESULT_V1.json'))
 def test_no_boundary_crossing(self):
  a=load(AUTH)
  for k in ('new_economic_outcomes','search_budget_use','power_trials','broker_requests','ctrader_requests','new_data_requests'):self.assertEqual(a[k],0)
  for k in ('duration_selected','protected_forward_opened','confirmation_opened'):self.assertFalse(a[k])
 def test_result_or_true_blocker(self):
  a=load(AUTH)
  self.assertIn(a['status'],['SUPPORT_RESULT_COMPLETE_PENDING_INDEPENDENT_AUDIT','SUPPORT_EXECUTION_OPERATIONALLY_BLOCKED'])
  if a['status']=='SUPPORT_RESULT_COMPLETE_PENDING_INDEPENDENT_AUDIT':
   d=load(S+P+'CURRENT_WAVE_SUPPORT_RESULT_V1.json')
   g=d['global'];self.assertEqual(g['exact_shards_verified'],100);self.assertEqual(g['exact_bytes_downloaded'],49708418);self.assertEqual(g['exact_rows_streamed'],3355389);self.assertEqual(g['exact_plaintext_hashes_verified'],100);self.assertEqual(g['protected_forward_rows'],0);self.assertEqual(d['causal_pass_count'],0)
   route=load(S+P+'CURRENT_WAVE_ACCEPTED_M5_ASSET_ROUTE_V1.json')['assets']
   from research_core_v4.current_wave_support_machine_v1 import verify_checkpoint
   verify_checkpoint(d['assets'],route);self.assertEqual(len(d['assets']),100)
  else:self.assertEqual(a['support_arm_created'],False);self.assertEqual(a['real_asset_bodies_read'],0)
 def test_separate_arm_after_machine_preflight(self):
  a=load(AUTH)
  if a['support_arm_created']:
   arm=load(S+P+'CURRENT_WAVE_SUPPORT_EXECUTION_ARM_V1.json');p=load(arm['preflight_ref'])
   self.assertEqual(p['status'],'PASS_MACHINE_SYNTHETIC_AND_PRIVATE_ROUTE_NO_REAL_ASSET_READ');self.assertEqual(arm['scope'],'SUPPORT_ONLY');self.assertEqual(sha(arm['preflight_ref']),arm['preflight_sha256']);self.assertEqual(sha(S+P+'CURRENT_WAVE_SUPPORT_IMPLEMENTATION_FREEZE_V1.json'),arm['implementation_freeze_sha256'])
 def test_current_authority_alignment(self):
  h=sha(AUTH)
  for p in STATE:
   d=load(p);self.assertEqual(d['current_authority'],AUTH);self.assertEqual(d['current_authority_sha256'],h);self.assertEqual(d['strict_v2_current_wave_support_execution']['authority_sha256'],h)
if __name__=='__main__':
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(x) for x in [Parity,Checkpoints,Delivery]])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 raise SystemExit(not result.wasSuccessful())
