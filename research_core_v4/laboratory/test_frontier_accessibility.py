"""Artificial metadata fixtures, never market or economic observations."""
import ast,unittest
from pathlib import Path
from collections import Counter,defaultdict
from .common import need

tree=ast.parse(Path(__file__).with_name('frontier_accessibility.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='projection')
env={'Counter':Counter,'defaultdict':defaultdict,'need':need};exec(compile(ast.Module(body=[node],type_ignores=[]),'<exact-metadata-projection>','exec'),env)

class AccessibilityTests(unittest.TestCase):
    def run_projection(self,light,archived=None,full=None):
        hist=[{'symbol_id':1,'symbol':'A','broker_native_context':'X','historical_primary145':True}]
        return env['projection'](light,archived or [],hist,full or {},hist)
    def test_current_enabled_does_not_qualify_execution(self):
        r=self.run_projection([{'symbolId':'1','symbolName':'A','enabled':True}])['summary']
        self.assertEqual(r['historical_accessibility_states'],{'CURRENT_LISTED_ENABLED_NOT_EXECUTION_QUALIFIED':1});self.assertFalse(r['list_enabled_is_execution_or_liquidity_proof'])
    def test_id_reuse_name_drift_not_same_identity(self):
        r=self.run_projection([{'symbolId':1,'symbolName':'OTHER','enabled':True}])['summary']
        self.assertEqual(r['historical_accessibility_states'],{'IDENTITY_NAME_CHANGED_OR_MISSING':1});self.assertEqual(r['current_ids_with_same_historical_name'],0)
    def test_new_ids_are_not_filtered_out_by_historical_cap(self):
        r=self.run_projection([{'symbolId':2,'symbolName':'NEW','enabled':True}])['summary']
        self.assertEqual(r['current_ids_outside_historical_roster'],1);self.assertFalse(r['historical_frontier_is_permanent_cap'])
    def test_missing_disabled_archived_are_distinct(self):
        self.assertEqual(self.run_projection([])['historical_membership_join'][0]['state'],'NOT_LISTED_IN_THIS_ACCOUNT_SNAPSHOT')
        self.assertEqual(self.run_projection([{'symbolId':1,'symbolName':'A','enabled':False}])['historical_membership_join'][0]['state'],'CURRENT_LISTED_DISABLED')
        self.assertEqual(self.run_projection([],archived=[{'symbolId':1}])['historical_membership_join'][0]['state'],'ARCHIVED_ONLY_NOT_CURRENT')
    def test_current_and_archived_is_ambiguous(self):
        r=self.run_projection([{'symbolId':1,'symbolName':'A','enabled':True}],archived=[{'symbolId':1}])
        self.assertEqual(r['historical_membership_join'][0]['state'],'CURRENT_AND_ARCHIVED_AMBIGUOUS')
    def test_terms_reference_not_dated_cost_or_margin_certificate(self):
        r=self.run_projection([{'symbolId':1,'symbolName':'A','enabled':True}],full={'1':{'commission':0}})['summary']['sample_current_detail_support'][0]
        self.assertTrue(r['field_presence']['commission']);self.assertFalse(r['historical_terms_certified']);self.assertFalse(r['EUR200_margin_certified'])
    def test_duplicate_native_ids_rejected(self):
        with self.assertRaises(Exception):self.run_projection([{'symbolId':1},{'symbolId':1}])

if __name__=='__main__':unittest.main()
