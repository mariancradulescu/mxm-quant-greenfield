"""Second-symbol full-week transport profile: artificial native wires, never a broker connection."""
import copy, importlib, json, os, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from m6.ctrader_proto import OpenApiMessages_pb2 as m
from . import week_chronology_reception as c
from .common import LabError
from .test_week_chronology_reception import fixture, receipt

def gbp_fixture():
    value=fixture()
    for index,row in enumerate(value['receipts']):
        req,res=c.decode_record(row,7)
        if index==0:
            res.symbol[0].symbolId=2;res.symbol[0].symbolName='GBPUSD'
        elif index==1:
            req.symbolId[:]=[2];res.symbol[0].symbolId=2
        else:req.symbolId=2
        value['receipts'][index]=receipt(req,res,index+1)
    return value

class GbpWeekProfile(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'LAB_CHRONOLOGY_PROFILE':'GBPUSD_W37'})
        self.env.start();importlib.reload(c)
    def tearDown(self):
        self.env.stop();importlib.reload(c)
    def test_only_registered_identity_week_and_limits(self):
        self.assertEqual((c.POLICY['symbol_id'],c.POLICY['symbol_name']),(2,'GBPUSD'))
        lo=datetime.fromtimestamp(c.POLICY['from_ms']/1000,timezone.utc)
        hi=datetime.fromtimestamp(c.POLICY['to_ms']/1000,timezone.utc)
        self.assertEqual(lo.isoformat(),'2026-09-07T00:00:00+00:00')
        self.assertEqual(hi.isoformat(),'2026-09-14T00:00:00+00:00')
        self.assertEqual(c.POLICY['history_request_cap'],4096)
        self.assertEqual(c.POLICY['max_wire_bytes'],70000000)
        self.assertEqual(c.POLICY['max_private_bytes'],120000000)
        self.assertEqual(c.POLICY['max_collection_seconds'],1200)
        self.assertEqual(c.POLICY['orders'],c.POLICY['strategy_trials'])
        self.assertEqual(c.POLICY['strategy_trials'],0)
        self.assertFalse(c.POLICY['confirmation_opened']);self.assertFalse(c.POLICY['automatic_retry'])
    def test_actual_second_symbol_wire_redecode(self):
        from research_core_v4.shallow_m5_support_v2_production import ACCOUNT_FINGERPRINT_SHA256
        with patch('research_core_v4.shallow_m5_support_v2_production._fingerprint',return_value=ACCOUNT_FINGERPRINT_SHA256):
            value=gbp_fixture();out=c.replay(value)
            self.assertEqual(out['chronological_events_processed'],2)
            self.assertTrue(out['provider_window_complete'])
            self.assertFalse(out['hard21_proven']);self.assertFalse(out['dated_costs_proven'])
            for mode in ('symbol','week','side','missing'):
                bad=copy.deepcopy(value)
                if mode=='symbol':bad['policy']['symbol_id']=1
                elif mode=='week':bad['policy']['from_ms']-=1
                elif mode=='missing':bad['trees']['ASK']=[]
                else:
                    req,res=c.decode_record(bad['receipts'][2],7);req.symbolId=1
                    bad['receipts'][2]=receipt(req,res,3)
                with self.subTest(mode=mode),self.assertRaises(LabError):c.replay(bad)
    def test_catalogue_identity_cannot_be_guessed_or_duplicated(self):
        for mode in ('missing','wrong_name','wrong_id','duplicate_id','duplicate_name'):
            res=m.ProtoOASymbolsListRes(ctidTraderAccountId=7)
            if mode!='missing':res.symbol.add(symbolId=2,symbolName='GBPUSD')
            if mode=='wrong_name':res.symbol[0].symbolName='EURUSD'
            if mode=='wrong_id':res.symbol[0].symbolId=1
            if mode=='duplicate_id':res.symbol.add(symbolId=2,symbolName='OTHER')
            if mode=='duplicate_name':res.symbol.add(symbolId=9,symbolName='GBPUSD')
            with self.subTest(mode=mode),self.assertRaisesRegex(LabError,'NATIVE_SYMBOL_NAME'):c.validate_catalogue(res)
    def test_identity_is_checked_before_symbol_specific_collection(self):
        import inspect
        source=inspect.getsource(c.collect)
        self.assertLess(source.index('validate_catalogue(catalogue)'),source.index('send(m.ProtoOASymbolByIdReq'))
        self.assertLess(source.index('validate_catalogue(catalogue)'),source.index('split_collect(send'))
    def test_exact_workflow_separates_roles_and_uses_finite_native_history(self):
        workflow=c.build_workflow('a'*40)
        self.assertEqual(c.SOURCE_REF,'mxm-gbpusd-week37-chronology-code-20261025')
        self.assertEqual(c.PATH,'.github/workflows/mxm-gbpusd-week37-chronology-reception.yml')
        self.assertEqual(str(c.OUT),'verification/gbpusd-week37-chronology')
        for phase,job in workflow['jobs'].items():
            self.assertEqual(job['env'],{'LAB_CHRONOLOGY_PROFILE':'GBPUSD_W37'})
            self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
            env=next(s['env'] for s in job['steps'] if 'env' in s)
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',env)
            self.assertEqual('R3_CTRADER_ACCESS_TOKEN' in env,phase=='chronology-collect')
            self.assertEqual('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env,phase=='chronology-cold')
        good={'total_count':1,'workflow_runs':[{'id':7,'run_attempt':1}]}
        c.one_shot_history(good,7)
        for bad in ({'total_count':0,'workflow_runs':[]},{'total_count':2,'workflow_runs':good['workflow_runs']},
                    {'total_count':1,'workflow_runs':[{'id':7,'run_attempt':2}]}):
            with self.assertRaisesRegex(LabError,'ONE_SHOT'):c.one_shot_history(bad,7)
    def test_new_installed_workflow_matches_exact_source_and_profile(self):
        root=Path(__file__).resolve().parents[2]
        installed=root.parent/c.PATH
        if not installed.exists():installed=root/c.PATH
        if not installed.exists():return  # source-only commit precedes installation
        workflow=json.loads(installed.read_bytes())
        source=workflow['jobs']['chronology-collect']['steps'][1]['with']['ref']
        self.assertEqual(c.build_workflow(source),workflow)
    def test_old_installed_workflows_retain_exact_generated_contract(self):
        for profile,name in [('W37','mxm-week-chronology-reception.yml'),('W35','mxm-week35-chronology-reception.yml')]:
            with patch.dict(os.environ,{'LAB_CHRONOLOGY_PROFILE':profile}):
                importlib.reload(c)
                root=Path(__file__).resolve().parents[2]
                installed=root.parent/'.github/workflows'/name
                if not installed.exists():installed=root/'.github/workflows'/name
                workflow=json.loads(installed.read_bytes())
                source=workflow['jobs']['chronology-collect']['steps'][1]['with']['ref']
                self.assertEqual(c.build_workflow(source),workflow)
        importlib.reload(c)
if __name__=='__main__':unittest.main()
