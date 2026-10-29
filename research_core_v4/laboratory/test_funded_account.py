import copy
import shutil
import unittest
from unittest.mock import patch
from .common import digest, LabError
from .fixtures import programme
from .funded_account import execute, validate_feed, observed_periods
from .programs import Laboratory, validate_manifest
from .budgets import TrialBook
from discovery.engine import DiscoveryEngine

def feed(policy):
    def stamp(second):return f'2025-01-06T12:00:{second:02d}Z'
    events=[]
    for second,desired in [(0,1),(2,0)]:
        for symbol in ['A','B']:
            events.append({'$feed':'explicit-decision','Utc':stamp(second),'Symbol':symbol,
                           'Sequence':second//2+1,'Desired':desired,'ValidFromUtc':stamp(second+1),
                           'ExpiresUtc':stamp(second+2),'PolicySha256':policy})
        for symbol in ['A','B']:
            events.append({'$feed':'quote','Utc':stamp(second+1),'Symbol':symbol,
                           'Bid':100+second//2,'Ask':100.1+second//2,'QuoteToEur':1,
                           'ExecutableUnits':1,'InitialMarginEur':20,'CommissionPerSideEur':.04,
                           'SlipPerSideQuote':0,'EstimatedStopRiskEur':.5,'StopDistanceQuote':.5,
                           'BidSourceUtc':stamp(second+1),'AskSourceUtc':stamp(second+1),
                           'NativeSizingScenarioSha256':policy,
                           'BrokerVolumeMinUnits':1,'BrokerVolumeMaxUnits':1,'BrokerVolumeStepUnits':1})
    return {'schema':'mxm.funded-programme-feed.v1','partition':'DEVELOPMENT','orders':0,'cloud':False,
            'synthetic':True,'policy_sha256':policy,'events':events,'events_sha256':digest(events),
            'source_sha256':digest('artificial-two-symbol-source'),'symbols':['A','B'],
            'parameters':{'Strategy':0,'MaxMarginFraction':.4,'MaxPositions':2,
                          'MinimumFreeMarginReserveEur':120,'MaxEstimatedStopRiskFraction':.01,
                          'RoundTripRiskReserveEur':.4,'MaxQuoteAgeSeconds':120,
                          'ExplicitPolicySha256':policy,'NativeSizingScenarioSha256':policy}}

class FundedAccountTests(unittest.TestCase):
    def test_changed_events_and_owner_limits_rejected_before_process(self):
        for mutation in ('price','risk','future','lane'):
            f=feed('a'*64)
            if mutation=='price':f['events'][2]['Bid']=99
            if mutation=='risk':f['parameters']['MaxEstimatedStopRiskFraction']=.02
            if mutation=='future':
                f['events'][0]['Utc']='2026-09-18T00:00:00Z';f['events_sha256']=digest(f['events'])
            if mutation=='lane':f['synthetic']=False
            with self.assertRaises(LabError):validate_feed(f,'a'*64,True)

    def test_no_calendar_equity_invented(self):
        rows=[{'Utc':'2025-01-06T12:00:00Z','MarkedEquityEur':200},
              {'Utc':'2025-02-03T12:00:00Z','MarkedEquityEur':198}]
        periods=observed_periods(rows)
        self.assertEqual(set(periods['iso_weeks']),{'2025-W02','2025-W06'})
        self.assertFalse(periods['utc_months']['2025-02']['exact_calendar_boundary_equity_proven'])

    @unittest.skipUnless(shutil.which('dotnet'),'C# host required (mandatory in CI)')
    def test_two_symbols_one_account_three_cold_processes(self):
        result=execute({'spec_hash':'a'*64},feed('a'*64),True,chunk_size=3)
        self.assertEqual(result['account']['AcceptedEntries'],2)
        self.assertEqual(result['account']['ExecutedExits'],2)
        self.assertAlmostEqual(result['account']['FinalCashEur'],201.64)
        self.assertEqual(result['account']['OpenPositions'],0)
        self.assertEqual((result['deposit_count'],result['reset_count'],result['process_count']),(1,0,3))
        self.assertEqual([x['next_ordinal'] for x in result['chunks']],[3,6,8])
        uninterrupted=execute({'spec_hash':'a'*64},feed('a'*64),True,chunk_size=100)
        self.assertEqual(result['account'],uninterrupted['account'])
        self.assertEqual(result['observations'],uninterrupted['observations'])

    def manifest(self):
        m=programme();c=m['tasks']['admit_candidate']['input']['candidate']
        frozen=DiscoveryEngine().freeze_candidate(c,persist=False)
        m['tasks']={'admit_candidate':m['tasks']['admit_candidate']}
        m['tasks']['admit_candidate']['dependencies']=[];m['tasks']['admit_candidate']['when']={}
        m['tasks']['funded']={'operator':'funded_csharp','priority':2,'trial_units':0,
          'dependencies':['admit_candidate'],'when':{},
          'input':{'candidate':{'result_of':'admit_candidate'},'feed':feed(frozen['spec_hash'])}}
        return m

    def test_scheduler_routes_registered_candidate_and_cold_checkpoint(self):
        history={'reconciled':True,'V2':{'remaining':63,'charged':[],'existing_candidate_ids':[]}}
        lab=Laboratory(self.manifest(),history,TrialBook({'RECEPTION':0,'V2':84}))
        lab.execute(lab.next())
        lab=Laboratory.restore(lab.checkpoint(),history)
        result={'classification':'SYNTHETIC_FUNDED_RECEPTION','deposit_count':1,'reset_count':0}
        with patch('research_core_v4.laboratory.funded_account.execute',return_value=result) as run:
            lab.execute(lab.next());self.assertEqual(run.call_count,1)
        self.assertIsNone(lab.next());self.assertTrue(lab.state['safe_stop'])
        self.assertEqual(next(iter(lab.book.identities.values()))['state'],'OBSERVED')

    def test_source_failure_stops_without_retry(self):
        history={'reconciled':True,'V2':{'remaining':63,'charged':[],'existing_candidate_ids':[]}}
        lab=Laboratory(self.manifest(),history,TrialBook({'RECEPTION':0,'V2':84}))
        lab.execute(lab.next())
        with patch('research_core_v4.laboratory.funded_account.execute',side_effect=RuntimeError('fault')):
            with self.assertRaises(RuntimeError):lab.execute(lab.next())
        self.assertEqual(lab.state['stop_reason'],'EXECUTION_AMBIGUOUS_NO_AUTOMATIC_RETRY')
        self.assertIsNotNone(lab.state['pending'])

    def test_programme_cannot_fund_independent_accounts_per_mechanism(self):
        m=self.manifest();m['tasks']['second_account']=copy.deepcopy(m['tasks']['funded'])
        history={'reconciled':True,'V2':{'remaining':63,'charged':[],'existing_candidate_ids':[]}}
        with self.assertRaisesRegex(LabError,'ONE_CONTINUOUS_CSHARP_ACCOUNT'):
            Laboratory(m,history,TrialBook({'RECEPTION':0,'V2':84}))
