import unittest
from .report import reconcile
def pilot():return {'selected_accounting':[{'sid':1,'t':10,'accounts':{'model':None,'midpoint':{'net_eur':1},'quote_count':{'net_eur':0}}}]}
class Reconciliation(unittest.TestCase):
    def test_unresolved_stays_unknown(self):
        v=reconcile(pilot(),{'targets':[]});self.assertEqual(v['classification'],'DATA_INSUFFICIENT');self.assertIsNone(v['arms']['model']['complete_prefix_reference_net_eur'])
    def test_only_original_missing_can_complete(self):
        v=reconcile(pilot(),{'targets':[{'symbol_id':1,'entry_second':10,'scheduled_exit_second':910,'recovered':{'model':{'net_eur':3}}}]});self.assertEqual(v['paired']['midpoint']['complete_prefix_increment_eur'],2);self.assertTrue(v['original_prefix_current_terms_identifiable']);self.assertFalse(v['selection_extended_after_original_stop'])
    def test_known_account_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError,'REPLACEMENT'):reconcile(pilot(),{'targets':[{'symbol_id':1,'entry_second':10,'scheduled_exit_second':910,'recovered':{'midpoint':{'net_eur':100}}}]})
    def test_empty_population_not_identified(self):
        v=reconcile({'selected_accounting':[]},{'targets':[]});self.assertFalse(v['original_prefix_current_terms_identifiable'])
if __name__=='__main__':unittest.main()
