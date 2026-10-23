"""Artificial ledger/book counterexamples. No decryption, market or C# outcomes.

Mock only the already-tested source parser to isolate full ledger verification;
these miniature synthetic books do not claim native data or crypto custody.
"""
import hashlib,json,tempfile,unittest
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
from .csharp_native_portfolio_independent_mark import independent_terminal_mark,MarkParityError
from .test_csharp_week_source_routing import snapshot

LABEL='PINNED_PEPPERSTONE_WEEK35_BREAKOUT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED'

def fixture(direction=1,touch=True,terminal_touch=False):
    t=1787529601000
    bid,ask=D('1.0999'),D('1.1000')
    entry=ask+D('.00002') if direction==1 else bid-D('.00002')
    stop=entry-D(direction)*D('.0012')
    safe=(D('1.1002'),D('1.1003')) if direction==1 else (D('1.0996'),D('1.0997'))
    if direction==1:touched=(stop,stop+D('.0001'))
    else:touched=(stop-D('.0001'),stop)
    middle=touched if touch else safe
    last=touched if terminal_touch else safe
    book={t:(bid,ask),t+1000:middle,t+2000:last}
    pnl=(last[0]-entry)*1000 if direction==1 else (entry-last[1])*1000
    equity=D(200)+pnl/(last[1] if pnl>=0 else last[0])
    stamp=datetime.fromtimestamp(t/1000,timezone.utc).isoformat().replace('+00:00','Z')
    report={'schema':'mxm.csharp.native-exposed-quote-to-one-account.v1','classification':LABEL,
      'original_native_run_id':39946364621,'authenticated_requested_iso_week_input':'2026-W35',
      'weekly_provider_pages_broker_execution_proof':False,'one_full_iso_utc_week_proven':False,
      'derived_stream_sha256':'a'*64,'quote_events':683022,'grouped_atomic_usable_snapshots':3,
      'ambiguous_same_side_ms_revisions_skipped':0,'crossed_snapshots_skipped':0,'stale_side_snapshots_skipped':0,
      'actual_symbols':1,'multi_instrument_native_data_available':False,'new_broker_requests':0,'live_orders':0,
      'historical_broker_fills_proven':False,'hard21_proven':False,
      'valuation_mode':'CAPTURED_COMMISSION_AND_QUOTE_SIDE_FX_COMPONENTS_ONLY',
      'captured_terms_are_historical':False,'all_cost_components_verified':False,
      'modeled_parameters':{'strategy':'Breakout','units':1000,'slip_price_per_side':D('.00002'),
        'margin_eur':50,'historical_broker_terms_verified':False,'product_default_stop12':True,
        'product_stop_pips':12,'product_stop_distance_quote':D('.0012'),
        'product_stop_geometry_source':'CAPTURED_EURUSD_SNAPSHOT_PIP_POSITION_4_CTRADER_DEFAULT_12_PIPS'},
      'account':{'initial_capital_eur':200,'complete_iso_utc_weeks':0,'hard21_proven':False,
        'broker_fills_proven':False,'costs_broker_verified':False,'rejections':[],
        'accepted_entries':1,'executed_exits':0,'open_positions':1,'final_cash_eur':200,
        'marked_equity_eur':equity,'used_margin_eur':50,'free_margin_eur':equity-50,
        'ledger':[{'kind':'ENTRY','utc':stamp,'symbol':'EURUSD','direction':direction,
          'price':entry,'units':1000,'cash_eur':200,'commission_eur':0,'gross_eur':0}]}}
    source={'sha256':'a'*64,'source_events':683022,'ambiguous':0,'crossed':0,'stale':0}
    terms=snapshot();terms.update(source_run=39946364621,
      source_code_sha='b54ee59548846ad8013b25965dbe4bcb19d4a978',
      source_private_sha256='2b37063a948d7b761a7f854e59649793ba1d5ff5e30a7e5255b03f4042cadb13',
      source_ciphertext_sha256='0d1badd1a944eeac7a67f1f7c87e05d26c1ea14ea016a0ea25fbb40ce7cb92ee')
    terms['raw_optional_fields'].update(preciseTradingCommissionRate=0,preciseMinCommission=0)
    return book,source,terms,report

def verify_fixture(direction=1,touch=True,terminal_touch=False):
    book,source,terms,report=fixture(direction,touch,terminal_touch)
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'synthetic-terms.json';raw=json.dumps(terms).encode();path.write_bytes(raw)
        report['captured_terms_sha256']=hashlib.sha256(raw).hexdigest()
        with patch('research_core_v4.laboratory.csharp_native_portfolio_independent_mark.authenticated_shape_quotes',return_value=(book,source)):
            return independent_terminal_mark('synthetic-parser-mocked',report,path)

class TerminalStopCompletenessTests(unittest.TestCase):
    def test_no_touch_terminal_position_remains_valid_both_sides(self):
        for direction in (1,-1):
            with self.subTest(direction=direction):
                self.assertEqual(verify_fixture(direction,False)['open_positions'],1)
    def test_missed_stop_then_recovery_must_fail_both_sides(self):
        for direction in (1,-1):
            with self.subTest(direction=direction),self.assertRaisesRegex(MarkParityError,'PRODUCT_STOP_OPEN_POSITION_MISSED_OBSERVED_TOUCH'):
                verify_fixture(direction,True)
    def test_exact_terminal_quote_touch_must_also_fail_both_sides(self):
        for direction in (1,-1):
            with self.subTest(direction=direction),self.assertRaisesRegex(MarkParityError,'PRODUCT_STOP_OPEN_POSITION_MISSED_OBSERVED_TOUCH'):
                verify_fixture(direction,False,True)

if __name__=='__main__':unittest.main()
