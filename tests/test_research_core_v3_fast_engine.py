"""A complete frozen grid equivalence check, including gaps and regime context."""
import json,random,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from research_core_v3.model import Bar,Series
from research_core_v3.engine import execute_spec
from research_core_v3.fast_engine import execute_one

class FrozenGridEquivalence(unittest.TestCase):
 def test_all_cells_and_horizons_match_generic_reference(self):
  spec=json.loads((Path(__file__).resolve().parents[1]/'research_core_v3/state/FROZEN_EXPERIMENT_SPEC_V1.json').read_text())
  rng=random.Random(7);t=datetime(2025,9,16,tzinfo=timezone.utc);price=100;bars=[]
  for i in range(700):
   if i in (160,400):t+=timedelta(hours=2)
   o=price;price*=1+rng.uniform(-.004,.004);c=price
   bars.append(Bar(t,o,max(o,c)+rng.random()*.1,min(o,c)-rng.random()*.1,c,2))
   t+=timedelta(minutes=5)
  s=Series('TEST',1,'fixture',tuple(bars))
  reference=execute_spec([s],spec)['cells'];fast=execute_one(s,spec)
  self.assertEqual(len(reference),55);self.assertEqual(len(fast),55)
  for old,new in zip(reference,fast):
   self.assertEqual((old['symbol'],old['mechanism'],old['context'],old['params']),
                    (new['symbol'],new['mechanism'],new['context'],new['params']))
   for k in ('event_count','independent_event_clusters','independent_date_clusters'):
    self.assertEqual(old[k],new[k],(old['mechanism'],old['params'],k))
   self.assertEqual(old['missingness_sensitivity']['gap_count'],new['missingness_sensitivity']['gap_count'])
   for h in ('1','3','6','12'):
    for k in ('n','mean_response','median_response','robust_effect_estimate','response_concentration_top10_abs_share'):
     a,b=old['horizons'][h][k],new['horizons'][h][k]
     if isinstance(a,float):self.assertAlmostEqual(a,b,places=9)
     else:self.assertEqual(a,b)
    for k in ('baseline_n','retained_n','sign_stable'):
     self.assertEqual(old['missingness_sensitivity']['response_sensitivity_by_horizon'][h][k],new['missingness_sensitivity']['response_sensitivity_by_horizon'][h][k])
if __name__=='__main__':unittest.main()
