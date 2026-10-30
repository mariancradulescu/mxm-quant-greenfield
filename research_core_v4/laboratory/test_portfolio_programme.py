import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from decimal import Decimal as D
from unittest.mock import patch
from .common import digest,encoded,LabError
from .portfolio_programme import (START,END,H,ROSTER,ROOT,SPEC,support,reference,compile_targets,
                                 build_feed,programme,account_checks,specification)
from .funded_account import execute,validate_feed
from .programs import Laboratory,freeze_portfolio_policy
from .budgets import TrialBook

def artificial():
    corp={s:{} for s in (1,*ROSTER)};prices={1:D('1.1'),5:D('.7'),111:D('4'),250:D('70')}
    for i,t in enumerate(range(START-13*H,END,H)):
        phase=(i//12)%3
        for sid in corp:
            start=prices[sid]
            change=D(0) if sid==1 else D('.0005') if sid==5 and phase==0 else D('.002') if sid==111 and phase==1 else D('-.002') if sid==250 and phase==2 else D('.0001')*(1 if i%2 else -1)
            close=(start*(1+change)).quantize(D('.00000001'));prices[sid]=close
            corp[sid][t]=(start,max(start,close)*D('1.0001'),min(start,close)*D('.9999'),close)
    return corp

class Admission(unittest.TestCase):
    def test_frozen_implementation_and_captured_minimum_units(self):specification()
    def test_full_priceblind_exposure_support_and_missing_cell_stop(self):
        c=artificial();self.assertEqual(support(c)['classification'],'SOURCE_ADMITTED')
        c[111].pop(START+8*H)
        self.assertEqual(support(c)['classification'],'DATA_LIMITED_SOURCE_BEFORE_POLICY')
    def test_past_clock_gaps_are_not_bar_index_compressed(self):
        c=artificial();end=START+12*H
        for sid in ROSTER:c[sid].pop(end-13*H)
        self.assertEqual(reference(c)[end],(None,0))
    def test_v4_policy_one_trial_and_preserve_v2_budget(self):
        spec=json.loads(SPEC.read_bytes());m=programme(spec)
        history={'reconciled':True,'V2':{'remaining':63,'charged':[]}}
        book=TrialBook({'V4':1,'V2':84},{'V4':0,'V2':21})
        lab=Laboratory(m,history,book);lab.execute('register')
        self.assertEqual(lab.book.used,{'V4':1,'V2':21})
        lab=Laboratory.restore(json.loads(encoded(lab.checkpoint())),history)
        self.assertEqual(lab.next(),'account')
        with self.assertRaisesRegex(LabError,'FUNDED_AUTHENTIC_SOURCE_UNAVAILABLE'):lab.execute('account')
    def test_inline_market_claim_cannot_replace_authenticated_adapter(self):
        m=programme(json.loads(SPEC.read_bytes()));m['tasks']['account']['input']['feed']={'synthetic':False}
        with self.assertRaisesRegex(LabError,'FUNDED_AUTHENTIC_ADAPTER_REQUIRED'):
            Laboratory(m,{'reconciled':True,'V2':{'remaining':63}},TrialBook({'V4':1,'V2':84}))
    def test_native_policy_cannot_reach_trading_path(self):
        main=(ROOT/'research_core_v4/native_tick_replay_v1/csharp/MxmReferenceProductBot.cs').read_text()
        observation=(ROOT/'research_core_v4/native_tick_replay_v1/csharp/MxmRelativeStrengthNativeObservation.cs').read_text()
        self.assertIn('ObserveRelativeStrengthPolicy && !NativeObservationOnly',main)
        self.assertIn('if(!nativeRun.IsObserving||observedPortfolioPolicy==null)return;',observation)
        for forbidden in ('ExecuteMarketOrder','ClosePosition','ModifyPosition','LocalStorage','causalIntents','entryCheckpoint','Timer.Start'):
            self.assertNotIn(forbidden,observation)
        self.assertIn('DefaultValue=false',observation)

class CompiledProgramme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS'):raise AssertionError('C# required in CI')
            raise unittest.SkipTest('C# execution is provided by GitHub CI')
    def test_joint_policy_parity_feed_and_recovered_shared_account(self):
        c=artificial();spec=json.loads(SPEC.read_bytes());m=programme(spec)
        frozen=freeze_portfolio_policy(spec,m)
        with tempfile.TemporaryDirectory() as directory:
            originals=[];targets,raw=compile_targets(c,Path(directory),originals.append)
        self.assertEqual(originals[0]['phase'],'POLICY_ORIGINAL_BEFORE_PARITY')
        names={t['Symbol'] for t in targets if t['Symbol']}
        self.assertGreaterEqual(len(names),2)
        feed=build_feed(c,targets,frozen['spec_hash'],spec,synthetic=True)
        validate_feed(feed,frozen['spec_hash'],True)
        journal=[];result=execute(frozen,feed,True,observer=journal.append)
        metrics=account_checks(result)
        self.assertGreater(metrics['entries'],0);self.assertGreater(result['process_count'],1)
        self.assertEqual(len(journal),result['process_count'])
        self.assertEqual(result['account']['OpenPositions'],0)
        self.assertEqual(result['deposit_count'],1);self.assertEqual(result['reset_count'],0)
        for chunk in result['chunks']:
            self.assertIn('original_result_base64',chunk);self.assertIn('original_capsule_base64',chunk)
        # Same original artificial feed, alternate technical chunking only.
        whole=execute(frozen,feed,True,chunk_size=100000)
        self.assertEqual(result['account'],whole['account'])
        self.assertEqual(result['observations'],whole['observations'])
    def test_future_prices_cannot_change_prior_decisions(self):
        first=artificial();second=copy.deepcopy(first);cutoff=START+5*24*H
        for sid in ROSTER:
            for t,bar in list(second[sid].items()):
                if t>=cutoff:second[sid][t]=tuple(p*D('1.5') for p in bar)
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            old,_=compile_targets(first,Path(a));new,_=compile_targets(second,Path(b))
        # UTC lexicographical order is chronological for these canonical strings.
        from .portfolio_programme import iso
        self.assertEqual([x for x in old if x['BoundaryUtc']<iso(cutoff)],
                         [x for x in new if x['BoundaryUtc']<iso(cutoff)])

if __name__=='__main__':unittest.main()
