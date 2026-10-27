import json,os,shutil,unittest
from . import current_margin_public_components as n
class ComponentArithmetic(unittest.TestCase):
    def test_native_current_terms_distinguish_known_zero_commission_from_unknown_total_costs(self):
        n.verify();panel=json.loads((n.FOLDER/'receipt.json').read_bytes())['panel'];r=n.reference(panel)
        self.assertEqual([x['declared_base_per_fill'] for x in r],[n.D('.03'),n.D('.03'),n.D(0)])
        self.assertEqual([x['no_fx_no_price_floor']['CompleteFeeKnownWithoutPrice'] for x in r],[False,False,True])
        self.assertTrue(all(not x['total_trading_cost_proven'] for x in r))
    def test_actual_existing_csharp_floor_matches_all_original_public_terms(self):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required CSharp component runtime absent')
            self.skipTest('Required in CI')
        r=n.main();self.assertTrue(r['original_receipt_verified']);self.assertFalse(r['economic_edge_proven'])
if __name__=='__main__':unittest.main()
