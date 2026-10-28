import copy,json,unittest
from .common import LabError
from .quote_innovation_recovery import ROOT,FAILED,FAILED_JOB,FAILED_HEAD,plan,workflow,no_original_outcome
from .three_week_source_recovery import FOLDERS,SIDE_COUNTS,validate_counts
class RecoveryTests(unittest.TestCase):
 def test_existing_adapter_validates_all_actual_original_schemas(self):
  for profile,folder in FOLDERS.items():
   m=json.loads((ROOT/folder/'MANIFEST.json').read_bytes());b,a=SIDE_COUNTS[profile]
   self.assertTrue(validate_counts(profile,m,{'bid_events':b,'ask_events':a}))
   with self.assertRaises(LabError):validate_counts(profile,m,{'bid_events':b+1,'ask_events':a})
  self.assertNotIn('bid_events',json.loads((ROOT/FOLDERS['W37']/'MANIFEST.json').read_bytes()))
 def test_no_reexecution_after_any_original_evaluation(self):
  r={'id':FAILED,'head_sha':FAILED_HEAD,'run_attempt':1,'status':'completed','conclusion':'failure'}
  steps=[{'name':'Reauthenticate and decode only the three exact originals in existing custody','conclusion':'failure'},
   {'name':'Execute one causal learner and one continuous account; reconcile forecasts and cash without keys','conclusion':'skipped'},
   {'name':'Cold read original result without rerunning the model','conclusion':'skipped'},
   {'name':'Preserve exact original ciphertext and evaluator without decryption','conclusion':'skipped'}]
  j={'total_count':1,'jobs':[{'id':FAILED_JOB,'conclusion':'failure','steps':steps}]};a={'total_count':0,'artifacts':[]}
  no_original_outcome(r,j,a)
  for mode in ('executed','artifact','source','attempt'):
   rr,jj,aa=copy.deepcopy((r,j,a))
   if mode=='executed':jj['jobs'][0]['steps'][1]['conclusion']='failure'
   if mode=='artifact':aa={'total_count':1,'artifacts':[{}]}
   if mode=='source':rr['head_sha']='0'*40
   if mode=='attempt':rr['run_attempt']=2
   with self.subTest(mode=mode),self.assertRaises(LabError):no_original_outcome(rr,jj,aa)
 def test_unchanged_science_one_finite_technical_attempt_and_readonly_roles(self):
  p=plan();self.assertEqual(p['additional_technical_attempts'],1);self.assertEqual(p['new_scientific_models'],0)
  w=workflow();self.assertEqual(len(w['jobs']),1);j=w['jobs']['quote-innovation-recovery']
  self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
  self.assertIn('three_week_source_recovery',j['steps'][4]['run'])
  self.assertNotIn('R3_CTRADER_ACCESS_TOKEN',json.dumps(w));self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(w))
if __name__=='__main__':unittest.main()
