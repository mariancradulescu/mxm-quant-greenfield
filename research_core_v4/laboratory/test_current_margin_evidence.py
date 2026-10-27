import copy,json,os,random,shutil,unittest
from . import current_margin_evidence as n

def item(buy=8000,sell=8001,digits=2):
    return dict(symbol_id=1,deposit_asset='EUR',quote_asset='USD',minimum_volume=100000,
      full=dict(symbolId=1,minVolume=100000,maxVolume=10000000,stepVolume=100000,lotSize=10000000,
       commissionType=2,minCommissionType=1,minCommissionAsset='USD',preciseTradingCommissionRate=350000000,preciseMinCommission=0),
      margin=dict(volume=100000,buy=buy,sell=sell,money_digits=digits))
class CompiledMarginEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required margin runtime absent')
            raise unittest.SkipTest('Actual CSharp current margin required in CI')
    def check(self,items):
        for framework in ('net6.0','net8.0'):self.assertEqual(n.run(items,framework),n.reference(items))
    def test_fixed_owner_boundary_at_both_sides_and_scaled_money(self):
        self.check([item(),item(79,80,0),item(8000000000,8000000001,8),item(1,1,28)])
    def test_optional_units_identity_and_nonpositive_values_never_default(self):
        bad=[]
        for field,val in [('money_digits',None),('money_digits',29),('buy',0),('sell',-1),('volume',99999)]:
            i=item();i['margin'][field]=val;bad.append(i)
        i=item();i['deposit_asset']='USD';bad.append(i)
        i=item();i['minimum_volume']=200000;bad.append(i)
        self.check(bad);self.assertTrue(all(x['margin'] is None for x in n.reference(bad)))
    def test_missing_fee_terms_do_not_erase_margin_or_become_free_trading(self):
        i=item();del i['full']['commissionType'];self.check([i]);r=n.reference([i])[0]
        self.assertIsNotNone(r['margin']);self.assertIsNone(r['terms']);self.assertIsNone(r['round_trip_fee_eur'])
    def test_seeded_arithmetic_and_all_fee_modes_use_existing_decoder(self):
        rng=random.Random(216);items=[]
        for _ in range(200):
            i=item(rng.randint(1,10**12),rng.randint(1,10**12),rng.randrange(9));i['full']['commissionType']=rng.randrange(1,5);items.append(i)
        self.check(items)
class ArithmeticReference(unittest.TestCase):
    def test_margin_is_necessary_only_and_no_price_or_fx_is_invented(self):
        r=n.reference([item()])[0]
        self.assertEqual(r['margin']['BuyEur'],80);self.assertEqual(r['margin']['SellEur'],n.D('80.01'))
        self.assertFalse(r['full_entry_admission']);self.assertIsNone(r['round_trip_fee_eur'])
        self.assertIn('NOT_ENTRY_ADMISSION',r['margin']['BuyMarginOnlyGate']);self.assertIn('FAILS',r['margin']['SellMarginOnlyGate'])
if __name__=='__main__':unittest.main()
