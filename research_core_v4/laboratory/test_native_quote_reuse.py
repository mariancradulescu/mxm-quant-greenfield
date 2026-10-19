import ast,copy,unittest
from collections import Counter,defaultdict
from pathlib import Path
from .test_frontier_cached_support import CachedSupport
class ReuseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CachedSupport.setUpClass();tree=ast.parse(Path(__file__).with_name('native_quote_reuse.py').read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='projection']
        def need(v,c):
            if not v:raise ValueError(c)
        e={'Counter':Counter,'defaultdict':defaultdict,'need':need,'quote_reason':CachedSupport.e['quote_reason']};exec(compile(ast.Module(body=nodes,type_ignores=[]),'<reuse>','exec'),e);cls.fn=staticmethod(e['projection'])
    def test_exact_window_preserves_source_and_identity(self):
        q=CachedSupport().quote();before=copy.deepcopy(q);m=[{'symbol_id':1,'symbol':'A','broker_native_context':'C'}];r=self.fn([q],m,0,20000,30000)
        self.assertEqual(r['B_period_valid_strict_bilateral'],1);self.assertEqual(q,before);self.assertEqual(r['economic_outcomes_opened'],0)
    def test_unmatched_or_other_window_does_not_repair_gap(self):
        q=CachedSupport().quote();m=[{'symbol_id':2,'symbol':'B','broker_native_context':'D'}];r=self.fn([q],m,0,20000,30000);self.assertEqual(r['B_period_boundaries'],0)
        m=[{'symbol_id':1,'symbol':'A','broker_native_context':'C'}];r=self.fn([q],m,20000,30000,40000);self.assertEqual(r['B_period_valid_strict_bilateral'],0)
    def test_conflicts_are_not_promoted(self):
        q=CachedSupport().quote();a=copy.deepcopy(q);a['sides']['ask']['price']=1.2;m=[{'symbol_id':1,'symbol':'A','broker_native_context':'C'}];r=self.fn([q,a],m,0,20000,30000)
        self.assertEqual(r['conflicts'],1);self.assertEqual(r['B_period_valid_strict_bilateral'],0)
if __name__=='__main__':unittest.main()
