"""Artificial wire fixtures only; no connection, credential or market outcome."""
import base64,copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from m6.ctrader_proto import OpenApiMessages_pb2 as m
from m6.ctrader_transport import ProtoMessage
from . import week_chronology_reception as c
from .common import LabError

def receipt(req,res,index):
    msg='mxm-'+str(index).zfill(12)
    def wire(value):return base64.b64encode(ProtoMessage(payloadType=value.payloadType,
        payload=value.SerializePartialToString(),clientMsgId=msg).SerializeToString()).decode()
    return {'request_type':type(req).__name__,'request_b64':base64.b64encode(req.SerializeToString()).decode(),
        'request_envelope_b64':wire(req),'response_envelope_b64':wire(res),'state':'RECEIVED'}

def fixture():
    lo,hi=c.POLICY['from_ms'],c.POLICY['to_ms']-1;account=7
    catalogue=m.ProtoOASymbolsListRes(ctidTraderAccountId=account)
    catalogue.symbol.add(symbolId=1,symbolName='EURUSD')
    metadata=m.ProtoOASymbolByIdRes(ctidTraderAccountId=account)
    metadata.symbol.add(symbolId=1,digits=5,pipPosition=4)
    rows=[receipt(m.ProtoOASymbolsListReq(ctidTraderAccountId=account),catalogue,1),
          receipt(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[1]),metadata,2)]
    trees={}
    for name,side in (('BID',1),('ASK',2)):
        req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=1,type=side,fromTimestamp=lo,toTimestamp=hi)
        res=m.ProtoOAGetTickDataRes(ctidTraderAccountId=account,hasMore=False)
        res.tickData.add(timestamp=lo+10,tick=100000+side)
        index=len(rows);rows.append(receipt(req,res,index+1))
        trees[name]=[{'lo':lo,'hi':hi,'receipt_index':index,'state':'LEAF_COMPLETE'}]
    return {'policy':copy.deepcopy(c.POLICY),'account':account,'auth_requests':list(c.AUTH_TYPES),
            'capture_complete':True,'receipts':rows,'trees':trees}

class ChronologyReceptionTests(unittest.TestCase):
    def replay(self,private):
        from research_core_v4.shallow_m5_support_v2_production import ACCOUNT_FINGERPRINT_SHA256
        with patch('research_core_v4.shallow_m5_support_v2_production._fingerprint',return_value=ACCOUNT_FINGERPRINT_SHA256):
            return c.replay(private)
    def test_complete_fixture_preserves_order_ambiguity_and_does_not_certify_economics(self):
        r=self.replay(fixture());self.assertTrue(r['provider_window_complete'])
        self.assertEqual(r['chronological_events_processed'],2);self.assertEqual(r['same_ms_cross_side_order_unknown'],1)
        self.assertFalse(r['research_capability_accepted']);self.assertFalse(r['dated_costs_proven'])
        self.assertFalse(r['continuous_market_coverage_proven']);self.assertEqual(r['orders'],r['economic_outcomes'])
    def test_cross_request_response_swap_rejected_from_actual_wire_ids(self):
        p=fixture();a,b=p['receipts'][2:];a['response_envelope_b64'],b['response_envelope_b64']=b['response_envelope_b64'],a['response_envelope_b64']
        with self.assertRaisesRegex(LabError,'WIRE_CORRELATION'):self.replay(p)
    def test_future_out_of_window_or_nonpositive_tick_refused(self):
        for stamp,tick in ((c.POLICY['to_ms'],100000),(c.POLICY['from_ms']-1,100000),(c.POLICY['from_ms'],0)):
            p=fixture();req,res=c.decode_record(p['receipts'][2],7);res.tickData[0].timestamp=stamp;res.tickData[0].tick=tick
            p['receipts'][2]=receipt(req,res,3)
            with self.subTest(stamp=stamp,tick=tick),self.assertRaises(LabError):self.replay(p)
    def test_provider_partial_or_missing_hasmore_never_complete(self):
        for value in (True,None):
            p=fixture();req,res=c.decode_record(p['receipts'][2],7)
            if value is None:res.ClearField('hasMore')
            else:res.hasMore=value
            p['receipts'][2]=receipt(req,res,3)
            with self.subTest(value=value),self.assertRaises(LabError):self.replay(p)
    def test_missing_duplicated_or_gapped_receipt_inventory_refused(self):
        for mode in ('extra','index','window','missing'):
            p=fixture()
            if mode=='extra':p['receipts'].append(copy.deepcopy(p['receipts'][2]))
            if mode=='index':p['trees']['ASK'][0]['receipt_index']=2
            if mode=='window':p['trees']['BID'][0]['lo']+=1
            if mode=='missing':p['trees']['BID']=[]
            with self.subTest(mode=mode),self.assertRaises(LabError):self.replay(p)
    def test_native_catalogue_metadata_and_capture_status_required(self):
        for mode in ('name','symbol','capture'):
            p=fixture()
            if mode=='capture':p['capture_complete']=False
            else:
                i=0 if mode=='name' else 1;req,res=c.decode_record(p['receipts'][i],7)
                if mode=='name':res.symbol[0].symbolName='OTHER'
                else:res.symbol[0].symbolId=2
                p['receipts'][i]=receipt(req,res,i+1)
            with self.subTest(mode=mode),self.assertRaises(LabError):self.replay(p)
    def test_split_cap_retains_both_unresolved_children_in_replay_order(self):
        p=fixture();counter=[1]
        def send(req):
            res=m.ProtoOAGetTickDataRes(ctidTraderAccountId=7,hasMore=True)
            p['receipts']=[receipt(req,res,1)];counter[0]-=1;return 0,res
        tree=c.split_collect(send,7,1,c.POLICY['from_ms'],c.POLICY['to_ms']-1,lambda:counter[0])
        rows,complete,used=c.verify_tree(tree,p['receipts'],7,1)
        self.assertFalse(complete);self.assertEqual(rows,[]);self.assertEqual(used,[0])
        self.assertEqual(len(tree),3)
    def test_same_ms_provider_truncation_is_terminal_not_a_retry(self):
        calls=[]
        def send(req):calls.append(req);return 0,m.ProtoOAGetTickDataRes(ctidTraderAccountId=7,hasMore=True)
        tree=c.split_collect(send,7,1,1000,1000,lambda:1)
        self.assertEqual(len(calls),1);self.assertEqual(tree[0]['state'],'SAME_MS_TRUNCATION_UNRESOLVED')
    def test_workflow_has_only_existing_separated_roles_and_no_writer(self):
        wf=c.build_workflow('a'*40);self.assertEqual(set(wf['jobs']),{'chronology-collect','chronology-cold'})
        for name,j in wf['jobs'].items():
            self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
            env=next(s['env'] for s in j['steps'] if 'env' in s)
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',env)
            self.assertEqual('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env,name=='chronology-cold')
            self.assertEqual('R3_CTRADER_ACCESS_TOKEN' in env,name=='chronology-collect')
    def test_fixed_full_week_and_one_shot_native_history(self):
        from datetime import datetime,timezone
        start=datetime.fromtimestamp(c.POLICY['from_ms']/1000,timezone.utc)
        self.assertEqual((start.weekday(),start.hour,start.minute,start.isocalendar().week),(0,0,0,37))
        self.assertEqual(c.POLICY['to_ms']-c.POLICY['from_ms'],604800000)
        self.assertFalse(c.POLICY['confirmation_opened']);self.assertFalse(c.POLICY['automatic_retry'])
        self.assertEqual(c.POLICY['strategy_trials'],0)
        valid={'total_count':1,'workflow_runs':[{'id':7,'run_attempt':1}]}
        c.one_shot_history(valid,7)
        for bad in ({'total_count':2,'workflow_runs':valid['workflow_runs']},
                    {'total_count':1,'workflow_runs':[{'id':6,'run_attempt':1}]},
                    {'total_count':1,'workflow_runs':[{'id':7,'run_attempt':2}]}):
            with self.assertRaises(LabError):c.one_shot_history(bad,7)
    def test_actual_dual_checkout_and_exact_copy_closure(self):
        wf=c.build_workflow('a'*40)
        self.assertEqual(wf['on']['push']['paths'],[c.PATH])
        for job in wf['jobs'].values():
            checkouts=[s['with'] for s in job['steps'] if s.get('uses')==c.CHECKOUT]
            self.assertEqual(checkouts,[{'ref':c.NATIVE_SOURCE,'persist-credentials':False},
                {'ref':'a'*40,'path':'.week-code','persist-credentials':False}])
            self.assertIn({'run':'cp .week-code/'+c.MODULE+' '+c.MODULE},job['steps'])
            self.assertNotIn('R3_CHRONOLOGY_CONTROL_WITNESS',str(job))
    def test_failed_native_producer_cannot_receive_acceptance_from_favorable_metrics(self):
        metrics={'provider_window_complete':True,'bid_events':10000,'ask_events':10000,
                 'chronological_events_processed':20000,'native_producer_conclusion':'failure'}
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'capture.mxmenc').write_bytes(b'artificial encrypted artifact placeholder')
            with patch.object(c,'OUT',out),patch.object(c,'context',return_value={}),\
                 patch.object(c,'cold',return_value=metrics):
                self.assertEqual(c.main('chronology-cold'),1)
            self.assertFalse(json.loads((out/'cold.json').read_bytes())['accepted'])


class WeekRoleIsolationTests(unittest.TestCase):
    def test_wrong_role_credentials_rejected_before_any_git_or_network_read(self):
        source='a'*40;trigger='b'*40
        for phase,bad_key in (('chronology-collect','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'),
                              ('chronology-cold','R3_CTRADER_ACCESS_TOKEN'),
                              ('chronology-collect','SUCCESSOR_APP_PRIVATE_KEY'),
                              ('chronology-cold','R3_CTRADER_REFRESH_TOKEN')):
            env={'GITHUB_REPOSITORY':c.REPO,'GITHUB_REF_NAME':c.BRANCH,
                 'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':phase,
                 'GITHUB_WORKFLOW_SHA':trigger,'GITHUB_SHA':trigger,
                 'GITHUB_WORKFLOW_REF':c.REPO+'/'+c.PATH+'@refs/heads/'+c.BRANCH,
                 'LAB_CHRONOLOGY_SOURCE':source,bad_key:'ARTIFICIAL_NOT_A_CREDENTIAL'}
            with patch.dict(c.os.environ,env,clear=True),self.assertRaises(LabError):
                c.context(SimpleNamespace(json=lambda _:self.fail('unexpected network read')),phase)
    def test_failed_native_producer_rejected_before_any_custody_key_import(self):
        identity={'source_sha':'a'*40,'native_decoder_source_sha':c.NATIVE_SOURCE,
                  'engine_source_sha':c.ENGINE,'trigger_sha':'b'*40,'run_id':7,'attempt':1}
        job={'id':8,'name':'chronology-collect','run_id':7,'status':'completed','conclusion':'failure',
             'steps':[{'name':'Run '+c.CHECKOUT,'conclusion':'success'}]*2}
        route=SimpleNamespace(json=lambda _: {'total_count':2,'jobs':[job,{'name':'chronology-cold'}]},
            data=lambda _: ('a'*40+' '+c.NATIVE_SOURCE+' git log -1 --format=%H').encode())
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'producer.json').write_text('{}');(out/'capture.mxmenc').write_bytes(b'fixture')
            with patch.object(c,'OUT',out),self.assertRaisesRegex(LabError,'NATIVE_PRODUCER_RECEIPT'):
                c.cold(route,identity)

class InstalledWorkflowTests(unittest.TestCase):
    def test_actual_installed_workflow_is_exact_generated_contract_if_present(self):
        path=Path('..')/c.PATH
        if not path.exists():self.skipTest('Broker workflow not installed by source-only change')
        wf=json.loads(path.read_bytes())
        source=next(s['env']['LAB_CHRONOLOGY_SOURCE'] for s in wf['jobs']['chronology-collect']['steps'] if 'env' in s)
        self.assertEqual(wf,c.build_workflow(source))

class NativeAuthorityReferenceTests(unittest.TestCase):
    def test_each_code_and_owner_authority_reference_is_a_hard_admission_condition(self):
        source='a'*40;trigger='b'*40
        refs={c.SOURCE_BRANCH:c.ENGINE,c.BRANCH:trigger,c.SOURCE_REF:source,
          'mxm-o04-active-v1':c.AUTHORITY,
          'mxm-o04-accepted-owner-1807-v1':'a830c132521bd4348454653f713e04f6107484fe'}
        route=SimpleNamespace(json=lambda p:{'object':{'sha':refs[p.removeprefix('git/ref/heads/')]}})
        c.verify_refs(route,source,trigger)
        for name in list(refs):
            old=refs[name];refs[name]='f'*40
            with self.subTest(name=name),self.assertRaisesRegex(LabError,'AUTHORITY_REF_MOVED'):
                c.verify_refs(route,source,trigger)
            refs[name]=old

if __name__=='__main__':unittest.main()
