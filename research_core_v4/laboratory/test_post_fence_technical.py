"""Artificial policy adversaries; native retirement requires separate real jobs."""
import copy,os,unittest
from unittest.mock import patch
from .common import digest,encoded,LabError
from .post_fence_technical import eligible,retire,refuse_replay,inject,POINTS,verify_inventory

def fixture():
    admission={'mode':'TECHNICAL_NONOUTCOME','economic_release':False,'programmes':[
        {'id':'finite_report','mode':'TECHNICAL_NONOUTCOME','orders':0,
         'budget':{'new_identities':0,'broker_requests':0},
         'tasks':{'once':{'operator':'report','trial_units':0}}}]}
    base={'pending':None,'sequence':27,'ciphertext_sha256':'a'*64,'safe_stop':True,
          'accounting':{'charged':21,'held':1,'observations':29,'refunds':0}}
    pending={'phase':'PRE_EXPOSURE','run_id':17,'preflight_sha256':'b'*64}
    intent={'pending':pending,'base_state':base,'preflight':{
        'admission_sha256':digest(admission),'source_sha':'c'*40,'trigger_sha':'d'*40,
        'admission_ref':'e'*40,'admission_path':'research_programs/admissions/FINITE.json'}}
    state={**copy.deepcopy(base),'pending':{**pending,'phase':'EXECUTION_FENCED'}}
    names={'source-controls':'success','preflight':'success','segment-intent':'success',
           'execution-fence':'success','investigation':'failure','durable-archive':'skipped'}
    jobs=[{'id':i+1,'run_id':17,'name':n,'status':'completed','conclusion':v} for i,(n,v) in enumerate(names.items())]
    run={'id':17,'run_attempt':1,'head_branch':'mxm-remediation-p0-p4-20261015-v1',
         'path':'.github/workflows/mxm-integrated-p0.yml','head_sha':'d'*40}
    return state,intent,admission,jobs,run

class TechnicalPostFence(unittest.TestCase):
    def test_retirement_preserves_cipher_ledger_and_does_not_claim_completion(self):
        args=fixture();before=copy.deepcopy(args)
        new,record=retire(*args,'f'*40)
        self.assertEqual(args,before)
        self.assertIsNone(new['pending'])
        self.assertEqual(new['ciphertext_sha256'],args[0]['ciphertext_sha256'])
        self.assertEqual(new['accounting'],args[0]['accounting'])
        self.assertFalse(record['programme_complete'])
        self.assertEqual(record['state'],'TECHNICAL_EXECUTION_UNCERTAIN_RETIRED_WITHOUT_REPLAY')
        self.assertEqual(record['economic_outcomes'],record['orders'])
        self.assertEqual(new['retired_technical_admissions']['17']['record_sha256'],digest(record))

    def test_unknown_exposure_cannot_be_declared_technical(self):
        for field,value in [('mode','DEVELOPMENT_RESEARCH'),('economic_release',True)]:
            args=list(fixture());args[2][field]=value
            with self.subTest(field=field),self.assertRaises(LabError):eligible(*args)
        for field,value in [('operator','native_replay'),('trial_units',1)]:
            args=list(fixture());args[2]['programmes'][0]['tasks']['once'][field]=value
            with self.subTest(field=field),self.assertRaises(LabError):eligible(*args)
        for field in ('new_identities','broker_requests'):
            args=list(fixture());args[2]['programmes'][0]['budget'][field]=1
            with self.subTest(field=field),self.assertRaises(LabError):eligible(*args)

    def test_real_terminal_graph_is_required(self):
        for name in ('source-controls','preflight','segment-intent','execution-fence'):
            args=list(fixture());next(j for j in args[3] if j['name']==name)['conclusion']='failure'
            with self.subTest(name=name),self.assertRaises(LabError):eligible(*args)
        for name,field,value in [('investigation','status','in_progress'),
                ('investigation','conclusion','success'),('investigation','conclusion','skipped'),
                ('durable-archive','status','queued'),('durable-archive','conclusion','success')]:
            args=list(fixture());next(j for j in args[3] if j['name']==name)[field]=value
            with self.subTest(name=name,field=field,value=value),self.assertRaises(LabError):eligible(*args)
        args=list(fixture());args[3].append(copy.deepcopy(args[3][0]))
        with self.assertRaises(LabError):eligible(*args)

    def test_changed_native_identity_or_base_cannot_clear_fence(self):
        for field,value in [('id',18),('head_sha','0'*40),('run_attempt',2),('head_branch','main'),('path','OTHER')]:
            args=list(fixture());args[4][field]=value
            with self.subTest(field=field),self.assertRaises(LabError):eligible(*args)
        for field,value in [('ciphertext_sha256','0'*64),('sequence',28),('accounting',{})]:
            args=list(fixture());args[0][field]=value
            with self.subTest(field=field),self.assertRaises(LabError):eligible(*args)
        args=list(fixture());args[0]['pending']['phase']='PRE_EXPOSURE'
        with self.assertRaises(LabError):eligible(*args)

    def test_uncertain_task_is_retired_even_under_a_new_admission_hash(self):
        args=fixture();new,_=retire(*args,'f'*40)
        with self.assertRaises(LabError):refuse_replay(new,args[2])
        changed=copy.deepcopy(args[2]);changed['another_label']='cosmetic-new-hash'
        with self.assertRaises(LabError):refuse_replay(new,changed)
        changed['programmes'][0]['id']='new_distinct_technical_task'
        with self.assertRaises(LabError):refuse_replay(new,changed)
        changed['programmes'][0]['tasks']['once']['input']={'purpose':'new independent maintenance task'}
        refuse_replay(new,changed)

    def test_finite_fault_points_never_apply_to_an_economic_admission(self):
        admission=fixture()[2]
        for point in POINTS:
            with patch.dict(os.environ,{'LAB_FAULT_AFTER_FENCE':point}),self.assertRaises(LabError):inject(point,admission)
            changed=copy.deepcopy(admission);changed['mode']='DEVELOPMENT_RESEARCH'
            with patch.dict(os.environ,{'LAB_FAULT_AFTER_FENCE':point}),self.assertRaises(LabError):inject('OTHER',changed)
        with patch.dict(os.environ,{'LAB_FAULT_AFTER_FENCE':''}):inject('BEFORE_DECRYPT',admission)
        with patch.dict(os.environ,{'LAB_FAULT_AFTER_FENCE':'UNKNOWN'}),self.assertRaises(LabError):inject('BEFORE_DECRYPT',admission)

    def inventory_fixture(self):
        from types import SimpleNamespace
        state,intent,admission,jobs,run=fixture()
        public,record=retire(state,intent,admission,jobs,run,'f'*40)
        run.update(status='completed',conclusion='failure')
        files={'typed-successor/post-fence-retirements/17.json':record,
               'typed-successor/intents/17.json':intent,
               'research_programs/admissions/FINITE.json':admission,
               'typed-successor/program-state.json':state}
        answers={'contents/typed-successor/post-fence-retirements?ref='+'9'*40:[{'type':'file','name':'17.json'}],
                 'actions/runs/17':run,
                 'actions/runs/17/attempts/1/jobs?per_page=100':{'total_count':len(jobs),'jobs':jobs}}
        return public,record,files,answers,SimpleNamespace(json=lambda path:answers[path])

    def check_inventory(self,public,files,route):
        with patch('research_core_v4.laboratory.runtime.file_at',side_effect=lambda r,p,o:encoded(files[p])), \
             patch('research_core_v4.laboratory.attest_v3.native_checkout_provenance'):
            return verify_inventory(route,'9'*40,public)

    def test_inventory_cannot_drop_a_retirement_or_relabel_completion(self):
        public,record,files,answers,route=self.inventory_fixture()
        self.assertEqual(self.check_inventory(public,files,route),1)
        with self.assertRaises(LabError):self.check_inventory({},files,route)
        record['programme_complete']=True
        public['retired_technical_admissions']['17']['record_sha256']=digest(record)
        with self.assertRaises(LabError):self.check_inventory(public,files,route)

    def test_retirement_requires_independent_native_graph_after_rehashing(self):
        for field,value in [('conclusion','success'),('status','in_progress')]:
            public,record,files,answers,route=self.inventory_fixture()
            answers['actions/runs/17'][field]=value
            with self.subTest(field=field),self.assertRaises(LabError):self.check_inventory(public,files,route)
        public,record,files,answers,route=self.inventory_fixture()
        next(j for j in answers['actions/runs/17/attempts/1/jobs?per_page=100']['jobs']
             if j['name']=='investigation')['conclusion']='success'
        with self.assertRaises(LabError):self.check_inventory(public,files,route)

    def test_cross_run_or_duplicate_job_id_is_rejected(self):
        for field,value in [('run_id',18),('id',2)]:
            args=list(fixture());args[3][0][field]=value
            with self.subTest(field=field),self.assertRaises(LabError):eligible(*args)

if __name__=='__main__':unittest.main()
