"""Synthetic C# risk research contracts, never original Pepperstone data."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from .equity_risk_research import PROJECT, fixed_policies

def tape():
    return {
     'Schema':'mxm.cold-risk-research.tape.v1','InitialCapitalEur':'200',
     'Policies':fixed_policies(),
     'Episodes':[
      dict(Symbol='AUDUSD',EntryUtc='2026-08-04T08:00:00Z',
           ExitUtc='2026-08-04T09:00:00Z',Units='1000',MarginEur='35',
           StopRiskEur='1.2',EntryFeeEur='0.05',ExitFeeEur='0.05',GrossEur='2'),
      dict(Symbol='AUDUSD',EntryUtc='2026-08-04T09:00:00Z',
           ExitUtc='2026-08-04T10:00:00Z',Units='1000',MarginEur='35',
           StopRiskEur='1.2',EntryFeeEur='0.05',ExitFeeEur='0.05',GrossEur='-2')
      ]}

def run(r):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)
        (path/'in.json').write_text(json.dumps(r))
        cp=subprocess.run(['dotnet','run','--no-build','-c','Release',
                           '--project',str(PROJECT),'--',
                           str(path/'in.json'),str(path/'out.json')],
                          text=True,capture_output=True,timeout=60)
        return cp,(json.loads((path/'out.json').read_bytes()) if cp.returncode==0 else None)

class NativeResearch(unittest.TestCase):
    def test_causal_cash_and_explicit_stresses(self):
        cp,r=run(tape())
        self.assertEqual(cp.returncode,0,cp.stderr)
        self.assertEqual(len(r['Scenarios']),12)
        by={(x['Policy'],x['Stress']):x for x in r['Scenarios']}
        legacy=by[('HISTORICAL_DIRECTOR_CONFIG','RECORDED_CSHARP')]
        self.assertEqual(legacy['Accepted'],2)
        self.assertEqual(legacy['Skipped'],0)
        self.assertAlmostEqual(float(legacy['FinalCashEur']),199.8)
        self.assertAlmostEqual(float(legacy['MaximumClosedDrawdownEur']),2.1)
        self.assertEqual(legacy['EntryCountsByIsoWeek']['2026-W32'],2)
        self.assertEqual(by[('ADAPTIVE_EQUITY_CONSERVATIVE','RECORDED_CSHARP')]['Accepted'],0)
        self.assertAlmostEqual(float(by[('HISTORICAL_DIRECTOR_CONFIG','DOUBLE_COMMISSION')]['FinalCashEur']),199.6)
        self.assertAlmostEqual(float(by[('HISTORICAL_DIRECTOR_CONFIG','ALL_ESTIMATED_STOPS')]['FinalCashEur']),197.4)
        self.assertAlmostEqual(float(by[('HISTORICAL_DIRECTOR_CONFIG','ALL_STOP_GAP_2X')]['FinalCashEur']),194.8)
        self.assertFalse(r['OriginalModelRerun'])
        self.assertFalse(r['HistoricalBrokerRiskCertified'])
        self.assertFalse(r['OperationalProtectionChanged'])

    def test_historical_absolute_ceiling_not_owner_law(self):
        r=tape()
        r['Episodes'][0]['MarginEur']='81'
        cp,s=run(r)
        self.assertEqual(cp.returncode,0,cp.stderr)
        by={(x['Policy'],x['Stress']):x for x in s['Scenarios']}
        self.assertEqual(by[('HISTORICAL_DIRECTOR_CONFIG','RECORDED_CSHARP')]['Accepted'],1)
        self.assertEqual(by[('ADAPTIVE_EQUITY_BALANCED','RECORDED_CSHARP')]['Accepted'],2)
        # No operational robot code is invoked, all paths are hypothetical.

    def test_unverified_order_rejected_without_result(self):
        r=tape()
        r['Episodes'][1]['EntryUtc']='2026-08-04T08:30:00Z'
        cp,_=run(r)
        self.assertNotEqual(cp.returncode,0)

    def test_cloned_policy_cannot_masquerade_as_independent(self):
        r=tape()
        r['Policies'][1]['Id']='HISTORICAL_DIRECTOR_CONFIG'
        cp,_=run(r)
        self.assertNotEqual(cp.returncode,0)

    def test_zero_margin_and_cost_fail_closed(self):
        for key,value in [('MarginEur','0'),('StopRiskEur','0'),('EntryFeeEur','-1')]:
            r=tape();r['Episodes'][0][key]=value
            cp,_=run(r)
            self.assertNotEqual(cp.returncode,0)

if __name__=='__main__':
    unittest.main()
