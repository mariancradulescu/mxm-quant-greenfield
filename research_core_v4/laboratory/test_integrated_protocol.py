"""New integration regressions; no accepted strategy/reception replay."""
import unittest
from copy import deepcopy
from .protocol import identity_budget,accounting,check_accounting,can_recover_before_exposure,require_jobs
from .test_admission import fixture
from .custody import chunk_ciphertext,restore_ciphertext
from .common import digest

def jobs(claim='failure',fence='skipped',worker='skipped'):
    return [{'name':n,'status':'completed','conclusion':c} for n,c in [('segment-intent',claim),('execution-fence',fence),('investigation',worker)]]

class ProtocolTests(unittest.TestCase):
    def test_budget_schema_compatibility(self):
        self.assertEqual(identity_budget({'schema':'mxm.laboratory-program.v1','budget':{'new_V2_identities':1}}),1)
        self.assertEqual(identity_budget({'schema':'mxm.laboratory-program.v2','budget':{'new_identities':0}}),0)
        for budget in ({'new_V2_identities':1},{'new_identities':True},{'new_identities':-1},{'new_identities':1,'new_V2_identities':1}):
            with self.assertRaises(Exception):identity_budget({'schema':'mxm.laboratory-program.v2','budget':budget})
    def test_legacy_and_typed_reports_do_not_infer_same_units(self):
        b=fixture();legacy=b.baseline['legacy_snapshot'];self.assertEqual(accounting(legacy)['lanes']['V2']['encumbered'],22)
        self.assertTrue(accounting(legacy)['outcomes_not_inferred_from_legacy_used']);self.assertEqual(accounting(b.export())['lanes']['V2']['outcome_charged'],21)
    def test_technical_run_conserves_every_accounting_field(self):
        view=fixture().view();check_accounting(view,view,{'mode':'TECHNICAL_NONOUTCOME'})
        bad=deepcopy(view);bad['economic_observations']+=1
        with self.assertRaises(Exception):check_accounting(bad,view,{'mode':'TECHNICAL_NONOUTCOME'})
    def test_c033_hold_cannot_be_erased_from_public_report(self):
        old=fixture().view();bad=deepcopy(old);bad['lanes']['V2'].update(reservation_holds=0,encumbered=21)
        with self.assertRaises(Exception):check_accounting(bad,old,{'mode':'TECHNICAL_NONOUTCOME'})
    def test_only_proven_pre_fence_crash_recoverable(self):
        s={'pending':{'phase':'PRE_EXPOSURE'}};self.assertTrue(can_recover_before_exposure(s,jobs()))
        for j in (jobs(claim='success'),jobs(fence='success'),jobs(worker='success'),jobs()[:-1]):self.assertFalse(can_recover_before_exposure(s,j))
        self.assertFalse(can_recover_before_exposure({'pending':{'phase':'EXECUTION_FENCED'}},jobs()))
    def test_running_or_duplicate_job_is_not_proof_of_no_exposure(self):
        j=jobs();j[2]['status']='in_progress';self.assertFalse(can_recover_before_exposure({'pending':{'phase':'PRE_EXPOSURE'}},j))
        self.assertFalse(can_recover_before_exposure({'pending':{'phase':'PRE_EXPOSURE'}},jobs()+[jobs()[0]]))
    def test_workflow_success_cannot_substitute_skipped_worker(self):
        with self.assertRaises(Exception):require_jobs(jobs(),['investigation'])
        require_jobs(jobs(worker='success'),['investigation'])
    def test_checkpoint_roundtrip_and_incomplete_part_rejected(self):
        files,m=chunk_ciphertext(b'A'*300000,'typed-successor/test');self.assertEqual(restore_ciphertext(m,files.__getitem__),b'A'*300000)
        bad=deepcopy(m);bad['parts'].pop()
        with self.assertRaises(Exception):restore_ciphertext(bad,files.__getitem__)
        files[m['parts'][0]['path']]=b'!'+files[m['parts'][0]['path']]
        with self.assertRaises(Exception):restore_ciphertext(m,files.__getitem__)
    def test_path_escape_and_reordered_parts_rejected(self):
        files,m=chunk_ciphertext(b'A'*300000,'typed-successor/test');bad=deepcopy(m);bad['parts'].reverse()
        with self.assertRaises(Exception):restore_ciphertext(bad,files.__getitem__)
        with self.assertRaises(Exception):chunk_ciphertext(b'A','../escape')

class LaboratoryIntegrationTests(unittest.TestCase):
    def setup_programme(self):
        from .programs import AUTHORITY
        b=fixture();m={'schema':'mxm.laboratory-program.v2','id':'INTEGRATION_FIXTURE','version':1,'authority':AUTHORITY,'partition':'DEVELOPMENT','orders':0,'mode':'TECHNICAL_NONOUTCOME','economic_lane':'V2','family_id':'TECH_FIXTURE',
          'budget':{'steps':2,'broker_requests':0,'new_identities':0},'prospective_at_ms':1792440000000,'provenance':{'purpose':'ARTIFICIAL_INTEGRATION_FIXTURE'},'source_sha256':'0'*64,
          'tasks':{'first':{'operator':'classify','priority':1,'trial_units':0,'dependencies':[],'input':{'result':{'classification':'PROGRAMME_REPORT_SAVED','fixture_only':True}}},'second':{'operator':'report','priority':2,'trial_units':0,'dependencies':['first'],'input':{'previous':{'result_of':'first'}}}}}
        b.register_family({'id':'TECH_FIXTURE','mode':'TECHNICAL_NONOUTCOME','lane':'V2','lane_cap':84,'identity_cap':0,'observation_cap':0,'decision_sha256':'d'*64,'novelty_justification':'Technical accounting path fixture only; no economic hypothesis is admitted.','selection_history_ref':'fixture','adaptive_exposure':'fixture-only'})
        b.register_programme({'id':m['id'],'family':'TECH_FIXTURE','lane':'V2','identity_cap':0,'observation_cap':0,'manifest_sha256':digest(m)})
        return b,m,{'reconciled':True,'V2':{'remaining':63,'charged':[]}}
    def test_actual_laboratory_cold_restart_with_typed_book(self):
        from .programs import Laboratory
        b,m,h=self.setup_programme();before=b.view();lab=Laboratory(m,h,b);lab.execute(lab.next());saved=lab.checkpoint()
        restored=Laboratory.restore(saved,h);restored.execute(restored.next());self.assertIsNone(restored.next());self.assertEqual(restored.book.view(),before)
    def test_invalid_dag_and_technical_economic_operator_rejected_preclaim(self):
        from .programs import validate_manifest
        for mutate in ('cycle','economic'):
            b,m,h=self.setup_programme()
            if mutate=='cycle':m['tasks']['first']['dependencies']=['second']
            else:m['tasks']['first']['operator']='native_screen'
            b.programmes[m['id']]['manifest_sha256']=digest(m)
            with self.assertRaises(Exception):validate_manifest(m,h,b)

if __name__=='__main__':unittest.main()
