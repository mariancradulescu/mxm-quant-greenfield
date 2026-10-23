import copy
import unittest
from decimal import Decimal as D
from .csharp_week_account_attribution import attribute

def sample():
    return {
      'schema':'mxm.csharp.native-exposed-quote-to-one-account.v1',
      'classification':'PINNED_PEPPERSTONE_WEEK37_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED',
      'original_native_run_id':39917922508,'quote_events':685474,
      'authenticated_requested_iso_week_input':'2026-W37',
      'historical_broker_fills_proven':False,'hard21_proven':False,
      'all_cost_components_verified':False,'new_broker_requests':0,
      'live_orders':0,'modeled_entries_in_requested_iso_week':1,
      'modeled_21_entry_threshold_met':False,
      'account':{'initial_capital_eur':200,'hard21_proven':False,
        'broker_fills_proven':False,'costs_broker_verified':False,
        'accepted_entries':1,'executed_exits':1,'open_positions':0,
        'entries_by_iso_week':{'2026-W37':1},'final_cash_eur':D('199.4'),
        'marked_equity_eur':D('199.4'),'max_drawdown_eur':D('0.6'),
        'ledger':[
          {'kind':'ENTRY','utc':'2026-09-08T10:00:00Z',
           'symbol':'EURUSD','direction':1,
           'commission_eur':D('0.1'),'gross_eur':0,'cash_eur':D('199.9')},
          {'kind':'EXIT','utc':'2026-09-08T10:10:00Z',
           'symbol':'EURUSD','direction':1,'commission_eur':D('0.1'),
           'gross_eur':D('-0.4'),'cash_eur':D('199.4')}]}
    }

class AttributionTests(unittest.TestCase):
 def test_exact_account_identity(self):
    r=attribute(sample())
    self.assertEqual(r['net_modeled_marked_equity_pnl_eur'],'-0.6')
    self.assertEqual(r['modeled_total_commissions_eur'],'0.2')
    self.assertEqual(r['realized_gross_pnl_eur'],'-0.4')
    self.assertEqual(r['modeled_entry_counts_by_utc_date'],{'2026-09-08':1})
    self.assertFalse(r['hard21_proven'])
 def test_altered_source_or_promotion_fails(self):
    for path,val in [('original_native_run_id',1),('hard21_proven',True),
                     ('quote_events',200),('new_broker_requests',1)]:
      with self.subTest(path=path):
        a=sample();a[path]=val
        with self.assertRaisesRegex(ValueError,'PROVENANCE_AND_LIMITATIONS'):
          attribute(a)
 def test_false_cash_and_charged_fee_rejected(self):
    for field,wrong in [('cash_eur',D('201')),('commission_eur',D('-1'))]:
      a=sample();a['account']['ledger'][0][field]=wrong
      with self.assertRaises(ValueError):attribute(a)
 def test_one_open_position_is_marked_separately(self):
    a=sample()
    a['account']['ledger'].pop()
    a['account'].update(executed_exits=0,open_positions=1,
      final_cash_eur=D('199.9'),marked_equity_eur=D('199.25'))
    r=attribute(a)
    self.assertEqual(D(r['unrealized_liquidation_mark_pnl_eur']),D('-0.65'))
    self.assertEqual(D(r['net_modeled_marked_equity_pnl_eur']),D('-0.75'))
    self.assertEqual(D(r['modeled_total_commissions_eur']),D('0.1'))
 def test_outside_week_rejected(self):
    a=sample();a['account']['ledger'][0]['utc']='2026-09-14T00:00:00Z'
    with self.assertRaisesRegex(ValueError,'OUT_OF_WEEK_EVENT'):attribute(a)

if __name__=='__main__':unittest.main()
