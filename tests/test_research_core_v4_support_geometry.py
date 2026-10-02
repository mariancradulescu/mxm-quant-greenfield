from __future__ import annotations
import json,unittest
from pathlib import Path
from research_core_v4 import exact_geometry_calibration_v3 as cal

ROOT=Path(__file__).resolve().parents[1]

def load_json(rel):return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class SupportGeometryTests(unittest.TestCase):
 def test_lossless_v2_geometry_transport_and_context_rows(self):
    a=load_json("research_core_v4/state/V4_REAL_SUPPORT_SKELETON_AUDIT_V2.json")
    rows=cal.load_rows(ROOT/"research_core_v4/support_v2")
    self.assertEqual(len(rows),3753)
    self.assertEqual(a["skeleton"]["row_count"],118262)
    self.assertEqual(a["skeleton"]["canonical_sha256"],"e3f8de0012e2bcdd2005d72afef73f738de11fca404675689a8f00422ba0918b")
    for ctx,cfg in a["count_geometry_hashes"].items():
        self.assertEqual(sum(r["context"]==ctx for r in rows),cfg["data_rows"])

 def test_all_leaf_geometry_matches_persisted_v2_counts(self):
    a=load_json("research_core_v4/state/V4_REAL_SUPPORT_SKELETON_AUDIT_V2.json")
    g=cal.all_geometries(cal.load_rows(ROOT/"research_core_v4/support_v2"))
    for ctx,state,h,eligible,paired,loss,full,base,blocks in a["leaf_support"]:
        x=g[(ctx,state,h)]
        self.assertEqual(len([r for r in cal.load_rows(ROOT/"research_core_v4/support_v2") if r["context"]==ctx and r["vol_state"]==state]),eligible)
        self.assertEqual(len(x.units),paired)
        self.assertEqual(len(x.block_ids),blocks)
    self.assertGreaterEqual(min(len(x.block_ids) for x in g.values()),25)

 def test_all_24_leaves_feasible(self):
    a=load_json("research_core_v4/state/V4_REAL_SUPPORT_SKELETON_AUDIT_V2.json")
    self.assertEqual(len(a["leaf_support"]),24)
    self.assertTrue(a["support_verdict"]["all_24_leaves_meet_v2_min_12_blocks"])
    self.assertGreaterEqual(a["support_verdict"]["minimum_valid_two_week_blocks"],25)

if __name__=="__main__":unittest.main()
