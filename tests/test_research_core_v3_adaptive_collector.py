from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from m6.ctrader_capture import CaptureContractError, require_read_only_request
from research_core_v3.adaptive_collector import (
    AdaptiveCollector, CONTINUOUS_CLASSES, DEPTH_ANCHORS, PROTECTED, RECENT,
    WINDOW_DAYS, continuity, frontier, select_core, validate_rows,
)
from research_core_v3.engine import evaluate_cell
from research_core_v3.model import Bar, Series
from datetime import datetime, timedelta, timezone

ROOT=Path(__file__).resolve().parents[1]


def row(symbol, sid, *, cls='NEAR_24X5_MULTI_SESSION_SCHEDULE', rows=4000,
        coverage=0.9, longest=1000, gaps=0.001, anchors=3, margin=2):
    return {'symbol':symbol,'symbol_id':sid,'identity_status':'VERIFIED',
            'schedule_continuity_class':cls,'recent_probe_rows':rows,
            'schedule_adjusted_coverage_proxy':coverage,'longest_contiguous_run':longest,
            'depth_anchor_count':anchors,'effective_sample_potential':rows+anchors*100,
            'gap_fraction':gaps,'minimum_margin_estimate_for_EUR200':margin,
            'initial_core_selected':False,'selection_or_deferral_reason':None}


class AdaptiveCollectorTests(unittest.TestCase):
    def test_full_frontier_and_broker_semantic_classes(self):
        identities,_=frontier(ROOT)
        self.assertEqual(len(identities),1576)
        self.assertEqual(len({x['symbol_id'] for x in identities}),1576)
        self.assertEqual(sum(x['peer_coherence_metadata']['coverage_bucket'] in CONTINUOUS_CLASSES for x in identities),267)
        self.assertEqual(WINDOW_DAYS,14)
        self.assertLess(14*288,5000)

    def test_selection_is_outcome_blind_pareto_and_data_dependent(self):
        a=row('A',1); b=row('B',2,coverage=.7,longest=300,gaps=.02,anchors=2,margin=3)
        c=row('C',3,cls='REGIONAL_OR_CASH_SESSION_SCHEDULE',coverage=1.0)
        d=row('D',4,cls='NEAR_24X7_OR_WEEKEND_CAPABLE_SCHEDULE')
        self.assertEqual([r['symbol'] for r in select_core([a,b,c,d])],['A','D'])
        self.assertEqual(b['selection_or_deferral_reason'],'PARETO_DOMINATED_WITHIN_BROKER_SCHEDULE_CLASS')
        self.assertEqual(c['selection_or_deferral_reason'],'LIMITED_SESSION_COMPLEMENTARY_FRONTIER')
        self.assertEqual(len(select_core([row('A',1)])),1)
        self.assertEqual(len(select_core([row('A',1),row('D',4,cls='NEAR_24X7_OR_WEEKEND_CAPABLE_SCHEDULE')])),2)
        # Economic response fields have no access path into the selector.
        a2=row('A',1);a2['strategy_return']=-1000;a2['winner_symbol']=False
        self.assertEqual([r['symbol'] for r in select_core([a2])],['A'])
        self.assertLess(RECENT['end_utc'],PROTECTED)
        self.assertTrue(all(end<PROTECTED for _,end in DEPTH_ANCHORS))

    def _runner(self, root):
        runner=AdaptiveCollector(client_id='client',client_secret='secret',access_token='token',
            config={},repo_root=ROOT,transport=SimpleNamespace(close=lambda:None),progress=lambda *a,**k:None)
        runner.work=Path(root);runner.state_path=runner.work/'progress.json'
        runner.state={'plan_sha256':runner.plan_sha,'completed_units':[],
            'phase':'FRONTIER_PROBE','phase_total_work_units':2,
            'phase_total_symbols':2,'rows_total':0,'current_symbol_rows':0,
            'successful_requests':0,'failed_requests':0,'retry_count':0,
            'reconnection_count':0,'timeout_count':0,'throttle_count':0}
        return runner

    def test_checkpoint_reuse_and_corruption_fail_closed(self):
        bar={'time_utc':'2026-09-02T00:00:00Z','open':'1','high':'2','low':'0.5','close':'1.5','tick_volume':'1'}
        with tempfile.TemporaryDirectory() as root:
            runner=self._runner(root)
            with patch.object(runner,'_fetch_window',return_value=([bar],1)) as fetch:
                args=('recent_1',1,1,5,0,1,RECENT['start_utc'],RECENT['end_utc'])
                self.assertEqual(runner._unit(*args),[bar])
                runner._unit(*args)
                self.assertEqual(fetch.call_count,1)
                self.assertEqual(runner.state['phase_percent'],50)
            resumed=self._runner(root)
            resumed.state=json.loads(runner.state_path.read_text())
            with patch.object(resumed,'_fetch_window',side_effect=AssertionError('recollected')):
                self.assertEqual(resumed._unit(*args),[bar])
            (Path(root)/'units'/'recent_1.csv').write_text('corrupt')
            with self.assertRaises(CaptureContractError):resumed._unit(*args)

    def test_progress_phase_denominator_does_not_claim_overall(self):
        with tempfile.TemporaryDirectory() as root:
            runner=self._runner(root)
            runner._save()
            self.assertEqual(runner.state['phase_percent'],0)
            runner.state['completed_units']=['recent_1']
            runner._save();self.assertEqual(runner.state['phase_percent'],50)
            runner._phase('HISTORY_DEPTH_PREFLIGHT',4,1)
            self.assertEqual(runner.state['phase_percent'],0)
            runner.state['completed_units'].append('depth_1_00')
            runner._save();self.assertEqual(runner.state['phase_percent'],25)
            runner._phase('DEEP_DEVELOPMENT_CAPTURE',2,1)
            self.assertEqual(runner.state['phase_percent'],0)

    def test_retry_counts_actual_attempt_even_on_success(self):
        with tempfile.TemporaryDirectory() as root:
            runner=self._runner(root)
            request=object()
            with patch.object(runner,'_request',side_effect=[TimeoutError('timeout'),object()]) as send, \
                 patch.object(runner,'_restore'):
                with patch('research_core_v3.adaptive_collector.time.sleep'):
                    runner._send(request,retries=3)
            self.assertEqual(send.call_count,2)
            self.assertEqual(runner.state['retry_count'],1)
            self.assertEqual(runner.state['reconnection_count'],1)

    def test_history_preflight_freezes_scope_before_deep_capture(self):
        identities,_=frontier(ROOT)
        active=next(x for x in identities if x['peer_coherence_metadata']['coverage_bucket']=='NEAR_24X7_OR_WEEKEND_CAPABLE_SCHEDULE')
        limited=next(x for x in identities if x['peer_coherence_metadata']['coverage_bucket']=='REGIONAL_OR_CASH_SESSION_SCHEDULE')
        with tempfile.TemporaryDirectory() as root:
            runner=self._runner(root)
            runner.identities=[active,limited]
            runner.bundle=Path(root)/'bundle'
            runner.zip_path=Path(root)/'output.zip'
            light={int(x['symbol_id']):{'symbolName':x['broker_symbol'],'enabled':True} for x in runner.identities}
            full={int(x['symbol_id']):{'tradingMode':0,'digits':5} for x in runner.identities}
            runner._auth=lambda:(123,light,full)
            calls=[]
            def fake_fetch(aid,sid,digits,start,end,scope_start,scope_end):
                calls.append((sid,scope_start))
                ts=datetime.fromtimestamp(start/1000,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
                bars=[{'time_utc':(datetime.fromtimestamp(start/1000,timezone.utc)+timedelta(minutes=5*i)).isoformat(timespec='seconds').replace('+00:00','Z'),
                       'open':'1','high':'2','low':'0.5','close':'1.5','tick_volume':'1'} for i in range(60)]
                return (bars,1)
            runner._fetch_window=fake_fetch
            runner._workflow()
            table=json.loads((runner.bundle/'DATA_QUALITY_TABLE.json').read_text())['rows']
            self.assertEqual(len(table),2)
            self.assertEqual(sum(x['initial_core_selected'] for x in table),1)
            selected=json.loads((runner.bundle/'SELECTED_IDENTITY_MANIFEST.json').read_text())
            self.assertEqual(selected['symbols'][0]['development_start_utc'],DEPTH_ANCHORS[0][0])
            self.assertFalse(selected['selection_law']['market_outcomes_used'])
            self.assertEqual(selected['selection_law']['numerical_quality_cutoffs'][0]['minimum_bars'],60)
            self.assertTrue(runner.zip_path.is_file())
            self.assertTrue(all(sid==int(active['symbol_id']) for sid,_ in calls[2:]))

    def test_gap_integrity_sensitivity_and_read_only(self):
        bar={'time_utc':'2026-09-02T00:00:00Z','open':'1','high':'2','low':'0.5','close':'1.5'}
        next_bar={**bar,'time_utc':'2026-09-02T00:15:00Z'}
        metrics=continuity([bar,next_bar])
        self.assertEqual(metrics['estimated_missing_grid_bars'],2)
        self.assertEqual(metrics['longest_contiguous_run'],1)
        validate_rows([bar,next_bar],RECENT['start_utc'],RECENT['end_utc'])
        with self.assertRaises(CaptureContractError):validate_rows([next_bar,bar],RECENT['start_utc'],RECENT['end_utc'])
        require_read_only_request('ProtoOAGetTrendbarsReq')
        with self.assertRaises(CaptureContractError):require_read_only_request('ProtoOANewOrderReq')
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        bars=[Bar(start+timedelta(minutes=5*i),1,1.01,.99,1+0.0001*i) for i in range(40)]
        series=Series('TEST',1,'authentic',tuple(bars))
        result=evaluate_cell(series,'SESSION_TIME_SEASONALITY',{'kind':'ALL'}, {'hour_utc':0},[1])
        sensitivity=result['missingness_sensitivity']['response_sensitivity_by_horizon']['1']
        self.assertIn('retained_n',sensitivity)
        self.assertIn('mean_delta',sensitivity)
        self.assertIn('sign_stable',sensitivity)

if __name__=='__main__':unittest.main()
