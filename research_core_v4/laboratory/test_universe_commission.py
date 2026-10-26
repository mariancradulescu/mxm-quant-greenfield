import shutil,unittest
from decimal import Decimal as D
from .universe_commission_checks import terms,fee,run,reconcile,snapshot
class Commission(unittest.TestCase):
    def item(self,kind=1):
        return {'symbol_id':99,'quote_asset':'GBP','full':{'symbolId':99,'commissionType':kind,'preciseTradingCommissionRate':50000 if kind==3 else 3000000000,'minCommissionType':1,'preciseMinCommission':10000000,'minCommissionAsset':'EUR','minVolume':100,'maxVolume':100000000,'stepVolume':100,'lotSize':10000000},'fill':{'volume_cents':100000,'price':'1.25','usd_per_quote':'1.3','cost_eur_per_asset':{'USD':'0.9','GBP':'1.1','EUR':'1'}}}
    def test_percentage_is_percent_and_minimum_currency_compares_in_eur(self):
        item=self.item(3);p=fee(item,terms(item));self.assertEqual(p['BaseFee'],D('6.25'));self.assertEqual(p['UnroundedFeeEur'],D('6.875'))
        item=self.item(4);item['full']['preciseMinCommission']=100000000;self.assertEqual(fee(item,terms(item))['UnroundedFeeEur'],1)
    def test_existing_snapshot_all_identities_before_any_pricing(self):
        s,items=snapshot();self.assertEqual(len(items),1576)
        for i in items:self.assertGreater(terms(i)['LotSize'],0)
    @unittest.skipUnless(shutil.which('dotnet'),'local .NET absent')
    def test_actual_csharp_four_modes_and_adversarial_units(self):
        items=[self.item(k) for k in (1,2,3,4)];q=self.item(4);q['full']['minCommissionType']=2;q['full'].pop('minCommissionAsset');items.append(q)
        reconcile(items,run(items))
        invalid=[]
        for field in ('preciseTradingCommissionRate','preciseMinCommission','commissionType','minCommissionType','minVolume','lotSize'):
            i=self.item();i['full'].pop(field);invalid.append(i)
        for mutate in (lambda i:i['full'].update(symbolId=100),lambda i:i['full'].update(commissionType=5),lambda i:i['full'].update(stepVolume=3),lambda i:i['fill'].update(volume_cents=101),lambda i:i['fill'].update(usd_per_quote=None),lambda i:i['fill']['cost_eur_per_asset'].pop('USD'),lambda i:i['full'].update(preciseTradingCommissionRate=-1),lambda i:i['full'].update(minCommissionAsset='')):
            i=self.item();mutate(i);invalid.append(i)
        self.assertTrue(all(x['status']=='COST_UNRESOLVED' for x in run(invalid)))
if __name__=='__main__':unittest.main()
