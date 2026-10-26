import base64,hashlib,json,shutil,subprocess,unittest
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROJECT='research_core_v4/laboratory/csharp/commission_account/MxmCommissionAccount.csproj'
@unittest.skipUnless(shutil.which('dotnet'),'local .NET absent')
class BoundAccount(unittest.TestCase):
    def test_actual_existing_account_costs_risk_and_three_cold_processes(self):
        p=subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build'],capture_output=True,text=True,check=True)
        original_stdout=p.stdout; r=json.loads(original_stdout,parse_float=D);self.assertEqual(r['classification'],'ARTIFICIAL_QUOTES_AND_FX_ONLY');self.assertEqual(r['cold_processes'],3)
        self.assertEqual(r['funding_count'],1);self.assertFalse(r['market_account_replay']);self.assertEqual(r['orders'],0)
        a=r['account'];self.assertEqual(a['InitialCapitalEur'],200);self.assertEqual(a['AcceptedEntries'],a['ExecutedExits']);self.assertEqual(a['AcceptedEntries'],1)
        cash=D(200);entry=None
        for row in a['Ledger']:
            self.assertEqual(row['CommissionEur'],D('.27'))
            if row['Kind']=='ENTRY':entry=row['Price'];cash-=row['CommissionEur'];self.assertEqual(entry,D('1.20022'))
            else:
                self.assertEqual(row['Price'],D('1.20048'));gross=(row['Price']-entry)*1000*D('.9');self.assertEqual(row['GrossEur'],gross);cash+=gross-row['CommissionEur']
            self.assertEqual(row['CashEur'],cash)
        self.assertEqual(cash,a['FinalCashEur']);self.assertEqual(cash,D('199.694'))
        p=r['percent_bound'];buy=D(1000)*D('1.20022')*D('.01')/100*D('.9');sell=D(1000)*D('1.19998')*D('.01')/100*D('.9')
        self.assertEqual(p['BuyCost']['UnroundedFeeEur'],buy);self.assertEqual(p['SellCost']['UnroundedFeeEur'],sell)
        self.assertEqual(p['ChargedPerSideCeilingEur'],max(buy,sell));self.assertLessEqual(2*max(buy,sell),r['parameters']['RoundTripRiskReserveEur'])
        self.assertFalse(a['CostsBrokerVerified']);self.assertFalse(a['Hard21Proven'])
        raw=original_stdout.encode();print('MXM_COMMISSION_ACCOUNT_ORIGINAL '+json.dumps({'classification':'ARTIFICIAL_QUOTES_AND_FX_ONLY','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'original_stdout_b64':base64.b64encode(raw).decode()},sort_keys=True))
if __name__=='__main__':unittest.main()
