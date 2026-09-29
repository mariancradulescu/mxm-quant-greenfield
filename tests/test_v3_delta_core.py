import json
import unittest
from pathlib import Path

from research_core_v3.delta_collector import frozen_scope, DeltaCollector


ROOT = Path(__file__).resolve().parents[1]


class FrozenDeltaContract(unittest.TestCase):
    def test_inclusive_core_and_delta_are_hash_bound_and_disjoint(self):
        frozen, quality, delta = frozen_scope(ROOT)
        self.assertEqual(len(json.loads(quality)['rows']), 1576)
        self.assertEqual(frozen['candidate_count'], 237)
        self.assertEqual(frozen['primary_count'], 145)
        self.assertEqual(frozen['reused_count'], 17)
        self.assertEqual(len(delta), 128)
        self.assertEqual(len({r['symbol_id'] for r in delta}), 128)
        self.assertTrue(all(r['reused_authentic_sha256'] is None for r in delta))
        self.assertEqual(set(frozen['delta_ids']), {r['symbol_id'] for r in delta})
        self.assertFalse(frozen['economic_outcomes_opened'])
        self.assertFalse(frozen['protected_forward_opened'])

    def test_only_deep_capture_is_in_delta_workflow(self):
        import inspect
        source = inspect.getsource(DeltaCollector._workflow)
        self.assertNotIn("FRONTIER_PROBE", source)
        self.assertNotIn("HISTORY_DEPTH_PREFLIGHT", source)
        self.assertIn("DEEP_DEVELOPMENT_CAPTURE", source)
        self.assertIn("self._unit(", source)

    def test_frozen_regime_reproduces_from_four_outcome_blind_dimensions(self):
        frozen, quality, _ = frozen_scope(ROOT)
        rows = {r['symbol_id']: r for r in json.loads(quality)['rows']}
        features = frozen['classification']['ordered_features']
        assignments = []
        for model in frozen['classification']['models']:
            chosen = set()
            for sid, row in rows.items():
                if row['depth_anchor_count'] != 4 or row['schedule_continuity_class'] not in (
                    'NEAR_24X5_MULTI_SESSION_SCHEDULE', 'NEAR_24X7_OR_WEEKEND_CAPABLE_SCHEDULE'):
                    continue
                scaled = [(float(row[k])-a)/b for k,a,b in zip(
                    features,model['scale_center'],model['scale_divisor'])]
                distances = [sum((x-y)**2 for x,y in zip(scaled, centroid))
                             for centroid in model['centroids']]
                if min(range(2), key=distances.__getitem__) == model['high_cluster_label']:
                    chosen.add(sid)
            self.assertEqual(len(chosen), model['selected_count'])
            assignments.append(chosen)
        self.assertEqual(len(assignments[0] & assignments[1]), 141)
        self.assertEqual(assignments[0] | assignments[1],
                         {x['symbol_id'] for x in frozen['primary_core']})


if __name__ == '__main__':
    unittest.main()
