import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.relative_value_epoch32_pair_structure import (
    _fit_development, linked_pairs, screen_pair, validate_freeze,
)


LAW = json.loads(Path("research_v3/EPOCH32_RELATIVE_VALUE_PAIR_STRUCTURE_FRONTIER_FREEZE_V1.json").read_text())["law"]


def series(scale=1, shifted_after=None):
    start=datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows=[]
    for i in range(400):
        value=10+0.004*i+0.05*((i%11)-5)
        if shifted_after is not None and i>=shifted_after:
            value*=2
        rows.append({"timestamp":start+timedelta(minutes=5*i),"time_utc":(start+timedelta(minutes=5*i)).isoformat(),
                     "open":value*scale,"high":value*scale,"low":value*scale,
                     "close":value*scale,"tick_volume":1.0})
    return rows


class RelativeValueEpoch32PairStructureTests(unittest.TestCase):
    def test_freeze_binds_existing_proposal_and_registry(self):
        freeze=json.loads(Path("research_v3/EPOCH32_RELATIVE_VALUE_PAIR_STRUCTURE_FRONTIER_FREEZE_V1.json").read_text())
        validate_freeze(Path("."),freeze)
        self.assertFalse(freeze["interpretation_boundary"]["economic_promotion_authorized"])

    def test_linkage_uses_asset_class_before_outcomes(self):
        registry=json.loads(Path("research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json").read_text())
        pairs=linked_pairs(registry["representatives"])
        self.assertEqual(len(pairs),22)
        self.assertTrue(all(left["signature"][0]==right["signature"][0] for left,right in pairs))

    def test_fit_is_invariant_to_test_partitions(self):
        left,right=series(),series(1.5)
        baseline=screen_pair(left,right,"A|B",LAW)
        changed=screen_pair(left,series(1.5,shifted_after=200),"A|B",LAW)
        self.assertEqual(baseline["development_beta"],changed["development_beta"])
        self.assertEqual(baseline["development_intercept"],changed["development_intercept"])

    def test_gaps_do_not_create_transitions(self):
        left,right=series(),series(1.5)
        for row in left[200:]: row["timestamp"]+=timedelta(days=1)
        result=screen_pair(left,right,"A|B",LAW)
        self.assertLess(result["aligned_rows"],400)


if __name__=="__main__": unittest.main()
