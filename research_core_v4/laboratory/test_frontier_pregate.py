"""Focused tests for support measurement, not economic/reception replays."""
import ast,copy,unittest
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
class SupportContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse(Path(__file__).with_name('frontier_pregate.py').read_text())
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='analyze_rows']
        def need(value,code):
            if not value:raise ValueError(code)
        env={'need':need,'Counter':Counter,'datetime':datetime,'Decimal':Decimal}
        exec(compile(ast.Module(body=funcs,type_ignores=[]),'<support-contract>','exec'),env);cls.fn=staticmethod(env['analyze_rows'])
    def rows(self,n=14):
        return [{'time_utc':datetime.fromtimestamp(i*300,timezone.utc).isoformat().replace('+00:00','Z'),'open':'10','high':'11','low':'9','close':'10','tick_volume':'3'} for i in range(n)]
    def test_contiguous_support_without_outcomes_or_mutation(self):
        rows=self.rows();before=copy.deepcopy(rows);r=self.fn(rows,0,10000000,20000000)
        self.assertEqual(r['contiguous_13bar_windows'],2);self.assertFalse(r['economic_qualification']);self.assertEqual(rows,before)
    def test_gap_does_not_certify_session(self):
        rows=self.rows();del rows[6];r=self.fn(rows,0,10000000,20000000)
        self.assertEqual(r['contiguous_13bar_windows'],0);self.assertEqual(r['missing_grid_slots_between_observed_rows'],1);self.assertFalse(r['gap_is_broker_session_certificate'])
    def test_protected_and_duplicate_rows_fail(self):
        with self.assertRaisesRegex(ValueError,'PREGATE_ROW_TIME'):self.fn(self.rows(),0,10000000,300)
        with self.assertRaisesRegex(ValueError,'PREGATE_ROW_ORDER'):self.fn([self.rows()[0]]*2,0,10000000,20000000)
    def test_zero_volume_not_missing_or_profit_evidence(self):
        rows=self.rows();rows[0]['tick_volume']='0';r=self.fn(rows,0,10000000,20000000)
        self.assertEqual(r['zero_tick_volume_rows'],1);self.assertEqual(r['unique_tick_volumes'],2);self.assertNotIn('PnL',r)
if __name__=='__main__':unittest.main()
