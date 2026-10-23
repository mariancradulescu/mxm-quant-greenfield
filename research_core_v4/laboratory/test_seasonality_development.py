import copy,datetime as dt,json,subprocess,unittest,os,tempfile
from pathlib import Path
from unittest.mock import patch
from decimal import Decimal as D
from .seasonality_reference import reference,reconcile
from .seasonality_development import validate_spec,decide,ROOT,context,SPEC

def rows(days=11):
    result=[];start=dt.datetime(2026,8,20,tzinfo=dt.timezone.utc)
    for day in range(days):
        for hour in range(24):
            direction=1 if hour%2==0 else -1;base=D(100 if direction>0 else 101)
            for bar in range(12):
                op=base+D(direction)*bar/12;cl=base+D(direction)*(bar+1)/12
                result.append(dict(time_utc=(start+dt.timedelta(days=day,hours=hour,minutes=bar*5)).isoformat().replace('+00:00','Z'),
                    open=str(op),close=str(cl),high=str(max(op,cl)),low=str(min(op,cl)),tick_volume=4))
    return result

class SeasonalityDevelopmentTests(unittest.TestCase):
    def test_finite_immutable_scope(self):
        s=validate_spec(active=True)
        self.assertEqual(s['slot_samples'],5);self.assertEqual(s['model_leaves'],1)
        self.assertEqual(s['dependent_reference_friction_leaves'],4)
        self.assertFalse(s['confirmation_opened']);self.assertFalse(s['protected_opened'])
        self.assertEqual(s['orders'],0)

    def test_spec_mutation_and_non_custody_execution_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed=Path(tmp)/'spec.json';changed.write_bytes(SPEC.read_bytes()+b' ')
            with patch('research_core_v4.laboratory.seasonality_development.SPEC',changed):
                with self.assertRaises(Exception):validate_spec(active=True)
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(Exception,'SEASONALITY_PROTECTED_CONTEXT'):context()

    def test_matching_prior_utc_slot_warmup_hourly_nonoverlap(self):
        source=rows();v=reference(source,trace=True)
        self.assertGreater(v['Complete'],30);self.assertGreater(v['SumGrossBps'],0)
        first=7*288+11 # First eligible boundary: Aug27 00:55, forecasts hour01 negative.
        self.assertTrue(all(x==0 for x in v['SignalTrace'][:first]))
        self.assertEqual(v['SignalTrace'][first],-1)
        self.assertEqual(v['SignalTrace'][first+12],1)
        a,b,direction=map(int,v['EpisodeSignatures'][0].split(','))
        self.assertEqual(a,first+2);self.assertEqual(b-a,10);self.assertEqual(direction,-1)
        self.assertEqual(v['BySegment']['1']['Complete'],0)
        self.assertEqual(v['TrainingHours'],11*24)
        entries=[int(x.split(',')[0]) for x in v['EpisodeSignatures']]
        self.assertTrue(all(b-a==12 for a,b in zip(entries,entries[1:])))

    def test_missing_bar_prevents_hour_training_and_censors_exposure(self):
        source=rows();cut=7*288+15
        baseline=reference(source);damaged=reference(source[:cut]+source[cut+1:])
        self.assertEqual(damaged['TrainingHours'],baseline['TrainingHours']-1)
        self.assertGreater(damaged['Censored'],baseline['Censored'])
        truncated=reference(source[:7*288+14])
        self.assertEqual(truncated['Complete'],0);self.assertEqual(truncated['Censored'],1)

    def test_future_does_not_change_prefix_decisions(self):
        source=rows();before=reference(source,trace=True);cut=8*288
        changed=copy.deepcopy(source)
        for row in changed[cut:]:
            for k in ('open','high','low','close'):row[k]=str(D(row[k])*2)
        after=reference(changed,trace=True)
        self.assertEqual(before['SignalTrace'][:cut],after['SignalTrace'][:cut])
        self.assertEqual(before['EpisodeSignatures'][:20],after['EpisodeSignatures'][:20])

    def test_wrong_or_protected_clock_invalid_prices_refused(self):
        for field,value in [('time_utc','2026-09-17T00:00:00Z'),('time_utc','2026-08-20T00:01:00Z'),('open','NaN'),('time_utc','2026-08-20T00:00:00.500Z')]:
            bad=rows(1);bad[0][field]=value
            with self.assertRaises(ValueError):reference(bad)
        source=rows(1)
        with self.assertRaises(ValueError):reference([source[0],source[0]])

    def test_all_channels_reconciliation_refuses_changed_signature_counts_or_gross(self):
        v=reference(rows());reconcile(v,v)
        for key,value in [('SignalSha256','0'*64),('LedgerSha256','0'*64),('SumGrossBps',D(999)),('TrainingHours',-1),('ReadyForecasts',-1)]:
            bad=copy.deepcopy(v);bad[key]=value
            with self.assertRaises(ValueError):reconcile(bad,v)

    def test_reference_gate_failure_and_pass_never_confirm_edge(self):
        def output(gross,n=1000):
            return dict(Complete=n,Censored=0,SumGrossBps=gross,
                BySegment={str(i):dict(Complete=n//3,SumGrossBps=D(gross)/3) for i in range(2,5)})
        self.assertEqual(decide([output(-1)])[0],'GROSS_FAIL')
        self.assertEqual(decide([output(1000)])[0],'REFERENCE_FRICTION_FAIL')
        self.assertEqual(decide([output(10000)])[0],'REFERENCE_CONCENTRATION_FAIL')
        self.assertEqual(decide([output(1000,n=100)] )[0],'REFERENCE_SUPPORT_FAIL')
        verdict,metrics=decide([output(1000,n=100) for _ in range(20)])
        self.assertEqual(verdict,'REFERENCE_SCREEN_SURVIVOR_UNCONFIRMED')
        self.assertEqual(set(metrics['by_entry_segment']),{'2','3','4'})

    def test_built_csharp_against_independent_arrays(self):
        assembly=ROOT/'research_core_v4/laboratory/csharp/seasonality/bin/Release/net8.0/MxmSeasonalityDevelopment.dll'
        if not assembly.exists():self.skipTest('C# build required and performed before test in CI')
        source=rows();damaged=source[:7*288+15]+source[7*288+16:]
        packets=[dict(ordinal=i,rows=source if i==1 else damaged if i==2 else []) for i in range(1,1577)]
        result=subprocess.run(['dotnet',str(assembly),'--development-stream'],input=''.join(json.dumps(p)+'\n' for p in packets),
            text=True,capture_output=True,check=True)
        actual=json.loads(result.stdout,parse_float=D)
        self.assertEqual(len(actual),1576)
        for p,a in zip(packets,actual):reconcile(a,reference(p['rows']))
        # Protected rows and incomplete ordinal streams are rejected in the real CLI too.
        bad=copy.deepcopy(packets);bad[0]['rows'][0]['time_utc']='2026-09-17T00:00:00Z'
        for contents in (bad,packets[:-1]):
            fail=subprocess.run(['dotnet',str(assembly),'--development-stream'],
              input=''.join(json.dumps(p)+'\n' for p in contents),text=True,capture_output=True)
            self.assertNotEqual(fail.returncode,0)
