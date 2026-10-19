import base64,copy,io,json,os,subprocess,tempfile,unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
from . import control as c,science as s,native,watch
from research_core_v4.delegated_bc_20261019.test_delegation import summary,accounting
SOURCE='a'*40;HEAD='b'*40

def predecessor():
    return json.loads(Path(__file__).with_name('PREDECESSOR_PUBLIC_STATE.json').read_text())

class Migration(unittest.TestCase):
    def test_exact_accepted_complete_head_only(self):
        state=predecessor();c.check_predecessor(state,c.PREDECESSOR['native_oid'])
        with self.assertRaises(Exception):c.check_predecessor(state,'f'*40)
        for k,v in [('revoked',True),('checkpoint_sha256','f'*64),('source_rule_id',1),('halt',None)]:
            x=copy.deepcopy(state);x[k]=v
            with self.assertRaises(Exception):c.check_predecessor(x,c.PREDECESSOR['native_oid'])

    def test_genesis_cannot_mutate_migration_anchor(self):
        state=c.genesis(SOURCE,1000);state['predecessor']['native_oid']='f'*40
        self.assertNotEqual(state['predecessor'],c.PREDECESSOR)
        with self.assertRaises(Exception):c.validate(state,SOURCE)
        self.assertFalse(c.POLICY['bootstrap_allowed'])

    def test_incomplete_or_foreign_archive_rejected(self):
        for archive in ({},{'public_state':predecessor(),'journal':{'schema':'wrong'}}):
            with self.assertRaises(Exception):c.check_archive(archive)

    def test_native_descriptor_cannot_select_another_predecessor(self):
        d={'schema':'mxm.native-admin-delegation.v1','source_sha':SOURCE,'policy_sha256':c.POLICY_SHA,
           'source_seal':{'id':7},'active_acl':{'id':25268790},'append_only':{'id':25222248},
           'predecessor':c.PREDECESSOR}
        with patch.dict(os.environ,{'GITHUB_SHA':SOURCE,'BC_NATIVE_DELEGATION':json.dumps(d)}):
            native.delegation_descriptor(7)
        d=copy.deepcopy(d);d['predecessor']['native_oid']='f'*40
        with patch.dict(os.environ,{'GITHUB_SHA':SOURCE,'BC_NATIVE_DELEGATION':json.dumps(d)}),self.assertRaises(Exception):
            native.delegation_descriptor(7)

    def test_actual_git_append_migration_preserves_predecessor_object_and_stale_cas(self):
        from research_core_v4.delegated_bc_20261019 import native as old
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);remote=root/'r.git'
            subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
            with patch.object(native,'REMOTE',str(remote)),patch.object(old,'REMOTE',str(remote)),patch('research_core_v4.p0_successor_a_20261017.publisher.REMOTE',str(remote)):
                a=old.Store(root/'a','LOCAL_FIXTURE',c.PREDECESSOR['source_sha'])
                original=b'OPAQUE_PREDECESSOR_CIPHER';a.cipher=original
                original_state=predecessor();original_state['checkpoint_sha256']=c.digest(original)
                first=a.cas(None,original_state)
                b=native.Store(root/'b','LOCAL_FIXTURE',SOURCE)
                state=c.genesis(SOURCE,1000);b.cipher=b'OPAQUE_MIGRATION_ARCHIVE';state['checkpoint_sha256']=c.digest(b.cipher)
                second=b.cas(first,state)
                self.assertEqual(b.git('rev-list','--parents','-n','1',second).stdout.decode().split(),[second,first])
                self.assertEqual(b.git('show',first+':checkpoint.mxmenc').stdout,original)
                stale=c.propose(state,SOURCE,first,1001,'renew')
                with self.assertRaises(Exception):b.cas(first,stale)
                cold=native.Store(root/'cold','LOCAL_FIXTURE',SOURCE)
                self.assertEqual(cold.read(),(second,state));self.assertEqual(cold.cipher,b.cipher)

class ScientificSensitivity(unittest.TestCase):
    def test_missing_mean_threshold_is_not_an_imputation(self):
        q=summary();q['accounting']['model']=accounting(n=4,missing=2,value=-3.)
        r=s.missingness(q)['arms']['model']
        self.assertEqual(r['missing_mean_required_for_total_above_zero_eur'],1.5)
        self.assertIsNone(r['point_total_eur']);self.assertTrue(r['unbounded_if_any_missing'])
        self.assertFalse(r['missing_outcome_model_assumed'])

    def test_incremental_charge_deducted_once_and_full_missing_stays_unknown(self):
        q=summary();q['accounting']['model']=accounting(n=4,missing=2,value=3.)
        a=s.cost_sensitivity(q)['arms']['model'];row=next(r for r in a['cases'] if r['additional_round_trip_charge_eur']==.5)
        self.assertEqual(row['observable_subset_net_eur'],2.)
        self.assertIsNone(row['full_net_eur']);self.assertEqual(a['incremental_charge_budget_on_observable_subset_eur_per_trade'],1.5)

    def test_zero_sample_cannot_qualify_from_zero_or_none(self):
        q=summary();q['accounting']={k:accounting(n=0,value=None) for k in ('model','midpoint','quote_count')}
        r=s.cost_sensitivity(q)
        self.assertTrue(all(not a['full_net_identifiable'] and a['cases'][0]['full_net_eur'] is None for a in r['arms'].values()))
        self.assertFalse(s.admission([s.missingness(q),r])['cbot_qualified'])

    def test_no_input_changes_or_synthetic_positive_promotion(self):
        q=summary();before=copy.deepcopy(q)
        a=s.missingness(q);b=s.cost_sensitivity(q)
        self.assertEqual(q,before);self.assertFalse(s.admission([a,b])['cbot_qualified'])

class ReadOnlyIsolation(unittest.TestCase):
    def test_app_key_presence_stops_before_any_private_processing(self):
        from . import readonly
        env={'GITHUB_REPOSITORY':'mariancradulescu/mxm-quant-greenfield',
            'GITHUB_REF_NAME':'mxm-remediation-p0-p4-20261015-v1','GITHUB_EVENT_NAME':'push',
            'GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':'independent-evidence','SUCCESSOR_APP_PRIVATE_KEY':'FIXTURE'}
        with patch.dict(os.environ,env,clear=True),patch.object(readonly,'private_key') as key:
            with self.assertRaisesRegex(Exception,'BC_READONLY_NO_APP_KEY'):readonly.main()
            key.assert_not_called()

class Durability(unittest.TestCase):
    def test_fresh_runs_and_expired_lease_across_long_session_gap(self):
        state=c.genesis(SOURCE,1000);state['checkpoint_sha256']='d'*64
        for n in range(3):
            now=1001+n*86400;state=c.propose(state,SOURCE,HEAD,now,'renew')
            state=c.propose(state,SOURCE,HEAD,now,'claim',run_id=10+n)
            state=c.propose(state,SOURCE,HEAD,now+1,'complete',run_id=10+n,result_sha256='c'*64,checkpoint_sha256='d'*64)
        self.assertEqual(c.scheduling(state,SOURCE,9999999),'REGISTERED_RESEARCH_COMPLETE_INSUFFICIENT_EVIDENCE')

    def test_pending_expiry_and_revoke_cannot_reexecute(self):
        state=c.propose(c.genesis(SOURCE,1000),SOURCE,HEAD,1001,'renew')
        state=c.propose(state,SOURCE,HEAD,1001,'claim',run_id=1)
        self.assertEqual(c.scheduling(state,SOURCE,9000),'PENDING_STOP_NO_REEXECUTION')
        with self.assertRaises(Exception):c.propose(state,SOURCE,HEAD,9000,'renew')
        state=c.propose(state,SOURCE,HEAD,9000,'revoke');self.assertEqual(c.scheduling(state,SOURCE,9000),'REVOKED')

    def watch(self,state,active):
        calls=[]
        def http(path,token,method='GET',body=None):
            calls.append((path,method,body))
            if 'git/ref' in path:return 200,{'object':{'sha':SOURCE}}
            if 'contents/state' in path:return 200,{'size':1000,'encoding':'base64','content':base64.b64encode(c.canonical(state)).decode()}
            if 'actions/runs?' in path:return 200,{'workflow_runs':active}
            return 204,None
        env={'GITHUB_REPOSITORY':'mariancradulescu/mxm-quant-greenfield','GITHUB_REF_NAME':'main',
            'GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':'ordinary-recovery','BC_EXPECTED_SOURCE_SHA':SOURCE,'GH_TOKEN':'FIXTURE'}
        with patch.dict(os.environ,env,clear=True),patch.object(watch,'http',http),redirect_stdout(io.StringIO()) as output:
            watch.main()
        return calls,output.getvalue()

    def test_missed_handoff_dispatches_continue_only_without_keys(self):
        calls,output=self.watch(c.genesis(SOURCE,1000),[])
        post=[r for r in calls if r[1]=='POST'];self.assertEqual(len(post),1)
        self.assertEqual(post[0][2],{'ref':c.SOURCE,'inputs':{'command':'continue'}})
        self.assertIn('ORDINARY_CONTINUATION_DISPATCHED',output)

    def test_active_run_and_terminal_do_not_dispatch(self):
        state=c.genesis(SOURCE,1000)
        calls,output=self.watch(state,[{'path':c.WORKFLOW,'status':'in_progress'}])
        self.assertFalse(any(x[1]=='POST' for x in calls));self.assertIn('NO_DUPLICATE',output)
        state=c.propose(state,SOURCE,HEAD,1001,'revoke')
        calls,output=self.watch(state,[])
        self.assertFalse(any(x[1]=='POST' for x in calls));self.assertIn('REVOKED',output)

if __name__=='__main__':unittest.main()
