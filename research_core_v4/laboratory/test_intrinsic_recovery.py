import copy,json,unittest
from .common import LabError
from .three_week_source_recovery import FOLDERS,ROWS,SIDE_COUNTS,validate_counts
from .intrinsic_recovery import ROOT,FAILED,FAILED_HEAD,FAILED_JOB,no_original_outcome,workflow,plan
class RecoveryTests(unittest.TestCase):
    def test_all_three_actual_manifest_schemas_before_custody(self):
        for profile,folder in FOLDERS.items():
            m=json.loads((ROOT/folder/'MANIFEST.json').read_bytes());bid,ask=SIDE_COUNTS[profile]
            self.assertTrue(validate_counts(profile,m,{'bid_events':bid,'ask_events':ask}))
            self.assertEqual(bid+ask,ROWS[profile])
            with self.assertRaises(LabError):validate_counts(profile,m,{'bid_events':bid+1,'ask_events':ask})
            bad=copy.deepcopy(m);bad['bid_events']=bid+1
            with self.assertRaises(LabError):validate_counts(profile,bad,{'bid_events':bid,'ask_events':ask})
        self.assertNotIn('bid_events',json.loads((ROOT/FOLDERS['W37']/'MANIFEST.json').read_bytes()))
    def test_recovery_never_reexecutes_observed_economics(self):
        run={'id':FAILED,'head_sha':FAILED_HEAD,'run_attempt':1,'status':'completed','conclusion':'failure'}
        steps=[{'name':'Reauthenticate and decode only the three exact originals in existing custody','conclusion':'failure'},
          {'name':'Execute one fixed account across fresh processes and independently reconcile then encrypt','conclusion':'skipped'},
          {'name':'Run actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02','conclusion':'skipped'}]
        jobs={'total_count':1,'jobs':[{'id':FAILED_JOB,'conclusion':'failure','steps':steps}]};artifacts={'total_count':0,'artifacts':[]}
        no_original_outcome(run,jobs,artifacts)
        for mode in ('executed','artifact','source','retry'):
            r,j,a=copy.deepcopy((run,jobs,artifacts))
            if mode=='executed':j['jobs'][0]['steps'][1]['conclusion']='failure'
            if mode=='artifact':a={'total_count':1,'artifacts':[{}]}
            if mode=='source':r['head_sha']='0'*40
            if mode=='retry':r['run_attempt']=2
            with self.subTest(mode=mode),self.assertRaises(LabError):no_original_outcome(r,j,a)
    def test_exact_new_scope_keeps_original_policy_and_roles(self):
        # Historical technical recovery cannot be re-admitted with later
        # shared account code. This is expected and protective; the preserved
        # encrypted original receipt remains independently verifiable.
        with self.assertRaisesRegex(LabError,'INTRINSIC_FROZEN_IMPLEMENTATION'):
            plan()
        p=json.loads((ROOT/'research_core_v4/laboratory/INTRINSIC_TECHNICAL_RECOVERY_V1.json').read_bytes())
        self.assertEqual(p['additional_technical_attempts'],1);self.assertEqual(p['new_scientific_models'],0)
        w=workflow();self.assertEqual(len(w['jobs']),1)
        j=w['jobs']['intrinsic-account-recovery'];self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
        self.assertEqual(len([s for s in j['steps'] if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in s.get('env',{})]),1)
        self.assertNotIn('R3_CTRADER_ACCESS_TOKEN',json.dumps(w));self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(w))
if __name__=='__main__':unittest.main()
