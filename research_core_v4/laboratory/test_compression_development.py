import unittest,copy,json,subprocess
from pathlib import Path
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from .compression_reference import reference,reconcile
from .compression_development import validate_spec,decide,ROOT,PROJECT

def artificial(sign=1):
    result=[];start=datetime(2026,8,20,tzinfo=timezone.utc)
    for i in range(70):
        op,hi,lo,cl=(100,102,98,100) if i<42 else (100,100.1,99.9,100) if i<48 else (100,103,100,103) if i==48 else (104,106,102,104)
        if i==62:op=105
        if sign<0:op,hi,lo,cl=200-op,200-lo,200-hi,200-cl
        result.append(dict(time_utc=(start+timedelta(minutes=5*i)).strftime('%Y-%m-%dT%H:%M:%SZ'),
             open=op,high=hi,low=lo,close=cl,tick_volume=10))
    return result
class CompressionDevelopmentTests(unittest.TestCase):
    def test_one_fixed_mechanism_no_new_cost_authority(self):
        s=validate_spec();self.assertEqual(s['model_leaves'],1)
        self.assertEqual(s['reference_roundtrip_bps'],[0,5,10,20])
        self.assertFalse(s['eur200_account']);self.assertFalse(s['historical_costs'])
    def test_prior_compression_direction_and_delayed_nonoverlapping_episode(self):
        for direction in (-1,1):
            r=reference(artificial(direction),trace=True)
            self.assertEqual(r['Complete'],1);self.assertEqual(r['Censored'],0)
            self.assertEqual(r['SignalTrace'][48],direction)
            self.assertEqual(r['EpisodeSignatures'],[f'50,62,{direction}\n'])
            self.assertGreater(r['SumGrossBps'],0)
    def test_later_changes_cannot_change_earlier_signals(self):
        a=artificial();b=copy.deepcopy(a)
        for row in b[55:]:row.update(high=111,low=100,close=110,open=110)
        self.assertEqual(reference(a,trace=True)['SignalTrace'][:55],reference(b,trace=True)['SignalTrace'][:55])
    def test_gap_and_terminal_observation_are_censored_not_invented_exits(self):
        a=artificial();r=reference(a[:60]);self.assertEqual((r['Complete'],r['Censored']),(0,1))
        for row in a[61:]:
            t=datetime.fromisoformat(row['time_utc'].replace('Z','+00:00'))+timedelta(minutes=5)
            row['time_utc']=t.strftime('%Y-%m-%dT%H:%M:%SZ')
        r=reference(a);self.assertEqual((r['Complete'],r['Censored']),(0,1))
    def test_protected_or_bad_clock_cannot_be_observed(self):
        for value in ('2026-09-17T00:00:00Z','2026-08-19T23:55:00Z','2026-08-20T00:00:01Z'):
            rows=artificial();rows[0]['time_utc']=value
            with self.assertRaises(ValueError):reference(rows)
    def test_altered_episode_signature_or_bps_cannot_reconcile(self):
        e=reference(artificial());a=copy.deepcopy(e);a['LedgerSha256']='0'*64
        with self.assertRaises(ValueError):reconcile(a,e)
        a=copy.deepcopy(e);a['SumGrossBps']+=1
        with self.assertRaises(ValueError):reconcile(a,e)
    def test_reference_pass_is_never_confirmed_edge(self):
        outputs=[]
        for _ in range(12):outputs.append({'Complete':100,'Censored':0,'SumGrossBps':'1000',
           'BySegment':{str(k):{'Complete':25,'SumGrossBps':'250'} for k in range(1,5)}})
        self.assertEqual(decide(outputs)[0],'REFERENCE_SCREEN_SURVIVOR_UNCONFIRMED')
        outputs[0]['SumGrossBps']='-20000';self.assertEqual(decide(outputs)[0],'GROSS_FAIL')
    def test_built_csharp_and_independent_array_reference(self):
        assembly=ROOT/'research_core_v4/native_tick_replay_v1/csharp/bin/Release/net8.0/MxmCompressionDevelopment.dll'
        if not assembly.exists():self.skipTest('C# build is required and performed before this test in CI')
        for direction in (-1,1):
            rows=artificial(direction)
            packets=[{'ordinal':i,'rows':rows if i==1 else []} for i in range(1,1577)]
            proc=subprocess.run(['dotnet',str(assembly),'--development-stream'],input=''.join(json.dumps(p)+'\n' for p in packets),
                                text=True,capture_output=True,check=True)
            result=json.loads(proc.stdout,parse_float=D);self.assertEqual(len(result),1576)
            reconcile(result[0],reference(rows));reconcile(result[-1],reference([]))
if __name__=='__main__':unittest.main()
