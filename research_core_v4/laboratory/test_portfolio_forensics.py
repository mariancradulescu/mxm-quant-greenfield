"""Synthetic algebra tests only; NEVER replay the closed authentic policy."""
import unittest
from decimal import Decimal
from .portfolio_forensics import analyze, EXPECTED_RUN, EXPECTED_HEAD, EXPECTED_CIPHER


def fixture():
    # One 1000-unit long: flat mid-price, -0.4000 execution, -0.08 commission.
    entry={'$feed':'quote','Utc':'2026-08-04T08:00:00Z','Symbol':'AUDUSD',
           'Bid':0.9999,'Ask':1.0001,'SlipPerSideQuote':0.0001,
           'ExecutableUnits':1000,'QuoteToEur':1,'QuoteLossToEur':1}
    out=dict(entry,Utc='2026-08-04T09:00:00Z')
    ledger=[{'Kind':'ENTRY','Utc':entry['Utc'],'Symbol':'AUDUSD','Direction':1,
             'Price':1.0002,'Units':1000,'GrossEur':0,'CommissionEur':0.04,'CashEur':199.96},
            {'Kind':'EXIT','Utc':out['Utc'],'Symbol':'AUDUSD','Direction':1,
             'Price':0.9998,'Units':1000,'GrossEur':-0.4,'CommissionEur':0.04,
             'CashEur':199.52,'Reason':'OBSERVED_QUOTE_STOP'}]
    account={'InitialCapitalEur':200,'FinalCashEur':199.52,'OpenPositions':0,
             'AcceptedEntries':1,'ExecutedExits':1,'Ledger':ledger,
             'MaxDrawdownEur':0.48,'RejectedEntries':0}
    result={'account':account,'deposit_count':1,'reset_count':0,'orders':0,
            'economic_qualification':False}
    original={'run_id':EXPECTED_RUN,'head':EXPECTED_HEAD,'economic_outcomes':1,
              'metrics':{'initial_eur':200,'classification':'NET_FAIL_FUNDED_PORTFOLIO_SCENARIO',
                         'net_eur':-0.48},'feed':{'schema':'mxm.funded-programme-feed.v1',
                         'partition':'DEVELOPMENT','orders':0,'cloud':False,
                         'synthetic':False,'events':[entry,out]},
              'programme_checkpoint':{'progress':{'results':{'account':{'value':result}}}}}
    receipt={'schema':'mxm.integrated-portfolio-first-result.v1','run_id':EXPECTED_RUN,
             'head':EXPECTED_HEAD,'private_cipher_sha256':EXPECTED_CIPHER,
             'economic_outcomes':1,'orders':0,'cloud':False}
    return original,receipt


class Forensics(unittest.TestCase):
    def test_exact_decomposition_and_shared_cash(self):
        original,receipt=fixture()
        x=analyze(original,receipt)
        self.assertEqual(Decimal(x['gross_to_net']['net_eur']),Decimal('-0.48'))
        self.assertEqual(Decimal(x['gross_to_net']['modeled_execution_drag_eur']),Decimal('0.4000'))
        self.assertEqual(Decimal(x['gross_to_net']['ex_post_mid_reference_eur']),Decimal('0.0000'))
        self.assertEqual(x['gross_to_net']['round_trips'],1)
        self.assertEqual(x['by_week']['2026-W32']['round_trips'],1)
        self.assertEqual(x['new_policy_evaluations'],0)
    def test_source_or_receipt_tamper_denied(self):
        original,receipt=fixture()
        receipt['head']='untrusted'
        with self.assertRaisesRegex(ValueError,'PINNED_AUTHORITY'):
            analyze(original,receipt)
    def test_ex_ante_fill_and_ledger_cash_must_match(self):
        original,receipt=fixture()
        original['programme_checkpoint']['progress']['results']['account']['value']['account']['Ledger'][1]['Price']=0.9999
        with self.assertRaisesRegex(ValueError,'FILL_DISAGREEMENT'):
            analyze(original,receipt)
    def test_insufficient_or_duplicate_original_quote_fails_closed(self):
        original,receipt=fixture()
        original['feed']['events']*=2
        with self.assertRaisesRegex(ValueError,'AMBIGUOUS_EXECUTION_QUOTE'):
            analyze(original,receipt)
    def test_account_reconciliation_denies_fictitious_deposit(self):
        original,receipt=fixture()
        original['programme_checkpoint']['progress']['results']['account']['value']['account']['Ledger'][1]['CashEur']=299.52
        with self.assertRaisesRegex(ValueError,'LEDGER_CASH_MISMATCH'):
            analyze(original,receipt)
    def test_no_live_or_demo_conversion_of_development_source(self):
        original,receipt=fixture()
        original['feed']['cloud']=True
        with self.assertRaisesRegex(ValueError,'UNFUNDED_OR_UNBOUND'):
            analyze(original,receipt)

if __name__=='__main__': unittest.main()
