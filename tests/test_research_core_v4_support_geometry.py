from __future__ import annotations
import csv,json,unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ANCHOR=datetime(2025,9,15,tzinfo=timezone.utc)

def load_json(rel):return json.loads((ROOT/rel).read_text(encoding="utf-8"))
def week_index(wk):
    y=int(wk[:4]);w=int(wk[-2:]);m=datetime.fromisocalendar(y,w,1).replace(tzinfo=timezone.utc)
    return (m-ANCHOR).days//7

class SupportGeometryTests(unittest.TestCase):
 def test_count_files_and_context_totals(self):
    a=load_json("research_core_v4/state/V4_REAL_SUPPORT_SKELETON_AUDIT_V1.json")
    self.assertEqual(sum(x["events"] for x in a["context_event_counts"].values()),a["skeleton"]["row_count"])
    for f in a["exact_counts"]:
        p=ROOT/f["ref"];self.assertEqual(p.stat().st_size,f["size_bytes"])
        with p.open(newline="",encoding="utf-8") as h:rows=list(csv.DictReader(h))
        self.assertEqual(len(rows),f["data_rows"])
        self.assertEqual(sum(int(r["full"]) for r in rows),a["context_event_counts"][f["context"]]["full"])
        self.assertEqual(sum(int(r["baseline"]) for r in rows),a["context_event_counts"][f["context"]]["baseline"])
 def test_all_leaf_geometry_matches_persisted_counts(self):
    a=load_json("research_core_v4/state/V4_REAL_SUPPORT_SKELETON_AUDIT_V1.json")
    byctx={}
    for f in a["exact_counts"]:
        with (ROOT/f["ref"]).open(newline="",encoding="utf-8") as h:byctx[f["context"]]=list(csv.DictReader(h))
    for ctx,state,h,eligible,paired,loss,full,base,blocks in a["leaf_support"]:
        rows=[r for r in byctx[ctx] if r["vol_state"]==state]
        fk=f"full_h{h}";bk=f"baseline_h{h}"
        self.assertEqual(len(rows),eligible)
        self.assertEqual(sum(int(r[fk]) for r in rows),full)
        self.assertEqual(sum(int(r[bk]) for r in rows),base)
        paired_rows=[r for r in rows if int(r[fk])>0 and int(r[bk])>0]
        self.assertEqual(len(paired_rows),paired)
        valid_by_week={}
        for r in paired_rows:valid_by_week.setdefault(r["week_key"],set()).add(r["symbol"])
        valid={week_index(wk) for wk,syms in valid_by_week.items() if len(syms)>=4}
        b=sum((2*i in valid and 2*i+1 in valid) for i in range(27))
        self.assertEqual(b,blocks)
        self.assertAlmostEqual(1-paired/eligible,loss,places=10)
 def test_all_24_leaves_feasible(self):
    a=load_json("research_core_v4/state/V4_REAL_SUPPORT_SKELETON_AUDIT_V1.json")
    self.assertEqual(len(a["leaf_support"]),24)
    self.assertTrue(a["support_verdict"]["all_24_leaves_meet_v2_min_12_blocks"])
    self.assertGreaterEqual(min(x[-1] for x in a["leaf_support"]),24)

if __name__=="__main__":unittest.main()
