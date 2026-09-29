import gzip,json,unittest,zipfile
from pathlib import Path
from tools.run_v3_broad_surface import canonical,sha
from research_core_v3.corrected_semantics import VARIANTS
ROOT=Path(__file__).resolve().parents[1]/'research_core_v3/state'
class CorrectedSurfaceIntegrity(unittest.TestCase):
 def test_exhaustive_binding_original_parity_and_continuity(self):
  m=json.loads((ROOT/'CORRECTED_145_DEVELOPMENT_MANIFEST_V2.json').read_text());d=m.pop('sha256');self.assertEqual(d,sha(canonical(m)))
  old=json.loads((ROOT/'BROAD_145_DEVELOPMENT_SURFACE_MANIFEST_V1.json').read_text());original={}
  for s in old['shards']:
   b=(ROOT/s['path']).read_bytes();self.assertEqual(sha(b),s['sha256'])
   for rec in json.loads(gzip.decompress(b))['symbols']:
    for c in rec['cells']:original[(c['symbol_id'],c['mechanism'],json.dumps(c['params'],sort_keys=True),json.dumps(c['context'],sort_keys=True))]=c
  total=0;ids=set()
  for shard in m['shards']:
   b=(ROOT/shard['path']).read_bytes();self.assertEqual(sha(b),shard['sha256'])
   for rec in json.loads(gzip.decompress(b))['symbols']:
    rd=rec.pop('sha256');self.assertEqual(rd,sha(canonical(rec)));self.assertEqual(rec['binding'],m['binding']);ids.add(rec['symbol_id'])
    for c in rec['cells']:
     total+=1;key=(c['symbol_id'],c['mechanism'],json.dumps(c['params'],sort_keys=True),json.dumps(c['context'],sort_keys=True));o=original[key]
     self.assertEqual(c['original_event_count'],o['event_count'])
     self.assertLessEqual(c['strict_dependency_event_count'],c['original_event_count'])
     self.assertEqual(c['events_removed_for_backward_dependency_gap'],c['original_event_count']-c['strict_dependency_event_count'])
     self.assertEqual(set(c['variants']),set(VARIANTS))
     for h in ('1','3','6','12'):
      a=c['variants'][VARIANTS[0]]['horizons'][h];z=o['horizons'][h]
      self.assertEqual(a['n'],z['n'])
      if a['mean_response'] is None:self.assertIsNone(z['mean_response'])
      else:self.assertAlmostEqual(a['mean_response'],z['mean_response'],places=12)
  self.assertEqual(total,7975);self.assertEqual(len(ids),145);self.assertFalse(m['protected_forward_opened'])
 def test_region_gate_remains_closed_without_authentic_costs(self):
  a=json.loads((ROOT/'CORRECTED_REGION_ASSESSMENT_V2.json').read_text());d=a.pop('sha256');self.assertEqual(d,sha(canonical(a)))
  self.assertEqual(a['frozen_candidates'],[]);self.assertFalse(a['protected_forward_opened']);self.assertFalse(a['sizing_scaling_optimization_opened'])
  for r in a['regions']:
   self.assertGreaterEqual(r['plateau_cell_count'],3);self.assertEqual(r['friction_status'],'COST_UNRESOLVED');self.assertIsNone(r['net_margin_bps']);self.assertFalse(r['candidate_frozen'])
 def test_friction_scope_only_gross_survivors_and_no_protected_windows(self):
  from research_core_v3.model import _dt
  p=json.loads((ROOT/'CORRECTED_MINIMAL_FRICTION_EVIDENCE_PLAN_V2.json').read_text());d=p.pop('sha256');self.assertEqual(d,sha(canonical(p)))
  a=json.loads((ROOT/'CORRECTED_REGION_ASSESSMENT_V2.json').read_text());allowed={r['region_sha256'] for r in a['regions']};symbols={r['symbol_id'] for r in a['regions']}
  m=json.loads((ROOT/'CORRECTED_145_DEVELOPMENT_MANIFEST_V2.json').read_text());cutoff=int(_dt(m['binding']['protected_forward_start']).timestamp()*1000)
  total=0
  for shard in p['shards']:
   self.assertIn(shard['symbol_id'],symbols);b=zipfile.ZipFile(ROOT/shard['archive']).read(shard['path']);self.assertEqual(sha(b),shard['sha256']);r=json.loads(gzip.decompress(b));total+=len(r['events'])
   for e in r['events']:self.assertTrue({r['region_sha256_dictionary'][i] for i in e[2]}<=allowed)
   previous=0
   for delta,duration in r['quote_windows_delta_ms']:
    start=previous+delta;end=start+duration;previous=start;self.assertLess(end,cutoff);self.assertLessEqual(start,end)
  self.assertEqual(total,p['unique_symbol_decision_direction_events']);self.assertFalse(p['acquisition_performed'])
if __name__=='__main__':unittest.main()
