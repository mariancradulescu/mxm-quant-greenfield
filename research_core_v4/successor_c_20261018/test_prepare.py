"""New C adapter checks with fabricated inputs only; no accepted suite replay."""
import copy
import unittest
from .prepare import method_plan, prepare_saved, describe_result, FORWARD

def corpus():
    return {'all_identity_status': [{'sid': 7}], 'catalog': {'full': {'7': {}}},
            'raw_quote_receipts': [], 'events': [
                {'sid': 7, 't': 1700000000+i*900, 'h': 15, 'entry': {'eligible': False},
                 'historical_target': 'DO_NOT_READ'} for i in range(4)]}

class Preparation(unittest.TestCase):
    def test_pinned_method_is_inactive(self):
        plan = method_plan()
        self.assertFalse(plan['campaign_armed'])
        self.assertIsNone(plan['net_eur'])

    def test_missing_denominator_and_no_outcomes(self):
        data = corpus(); before = copy.deepcopy(data)
        p = prepare_saved(data)
        self.assertEqual(data, before)
        self.assertEqual(p['candidate_boundaries'], 4)
        self.assertEqual(p['missing_quote_boundaries'], 4)
        self.assertEqual(p['halves'], {'first': 2, 'second': 2})
        self.assertEqual(p['outcomes_evaluated'], 0)
        self.assertNotIn('historical_target', p['events'][0])

    def test_conflicting_inputs_stop(self):
        for table, value in (
                ('events', {**corpus()['events'][0], 'entry': {'eligible': True}}),
                ('all_identity_status', {'sid': 7, 'other': 'conflict'})):
            d = corpus(); d[table].append(value)
            with self.subTest(table=table), self.assertRaises(ValueError):
                prepare_saved(d)
        d=corpus(); d['raw_quote_receipts']=[
            {'symbol_id': 7, 'boundary_ms': 1700000000000, 'pages': []},
            {'symbol_id': 7, 'boundary_ms': 1700000000000, 'pages': ['conflict']}]
        with self.assertRaisesRegex(ValueError, 'C_QUOTE_CONFLICT'):
            prepare_saved(d)

    def test_no_forward_or_foreign_identity(self):
        for field,value in (('t',FORWARD-900), ('sid',99)):
            d=corpus();d['events'][0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare_saved(d)

    def test_partial_result_never_becomes_complete_net(self):
        prepared=prepare_saved(corpus()); t=prepared['events'][0]['t']
        p={'selected':[{'sid':7,'entry':t}], 'closed':[], 'halt':'FIRST_SELECTED_UNKNOWN_EXIT',
           'complete_net_eur':None,'shadow_comparator_net_eur':{'cash':None,'midpoint':None}}
        result={'portfolio':p,'weekly_support':{}}
        out=describe_result(prepared,result)
        self.assertIsNone(out['complete_net_eur'])
        self.assertIsNone(out['matched_increment_eur']['midpoint'])
        p.update(halt='END',complete_net_eur=12.)
        self.assertIsNone(describe_result(prepared,result)['complete_net_eur'])
        p['closed']=[{'sid':7,'entry':t,'exit':t+900,'net_eur':12.}]
        p['shadow_comparator_net_eur']={'cash':0.,'midpoint':None}
        out=describe_result(prepared,result)
        self.assertEqual(out['matched_increment_eur']['cash'],12.)
        self.assertIsNone(out['matched_increment_eur']['midpoint'])
        p['closed'][0]['sid']=8
        with self.assertRaisesRegex(ValueError,'C_FOREIGN_CLOSE'):
            describe_result(prepared,result)

if __name__ == '__main__':
    unittest.main()
