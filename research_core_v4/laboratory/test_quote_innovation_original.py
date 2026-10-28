import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_quote_innovation_result import verify,FOLDER
class Originals(unittest.TestCase):
 def test_exact_original_closed_first_outcome(self):
  self.assertEqual(verify()['disposition'],'NET_FAIL_SCENARIO')
  r=json.loads((FOLDER/'receipt.json').read_bytes());g=r['gates']
  self.assertEqual(r['source_rows_verified'],2129692);self.assertEqual(r['forecasts'],21418);self.assertEqual(r['signals'],0)
  self.assertTrue(g['complete_continuous_account']);self.assertIsNone(r['account_fault'])
  self.assertEqual(g['causal_signal_upper_bound_by_week'],{'35':0,'36':0,'37':0})
  self.assertFalse(any(g['predictive_by_week'].values()));self.assertFalse(g['all_three_weeks_21_modeled_entries'])
  self.assertEqual(r['next_action'],'STOP_FIXED_MODEL_NO_RETUNE_NO_AUTOMATIC_FOLLOWUP')
 def test_corruption_is_not_repaired_or_replayed(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'copy';shutil.copytree(FOLDER,p);part=p/'parts/000.b64';raw=part.read_text();part.write_text(('A' if raw[0]!='A' else 'B')+raw[1:])
   with self.assertRaises(ValueError):verify(p)
 def test_cold_original_bytes_without_evaluator_execution(self):
  r=verify();self.assertFalse(r['algorithm_reexecuted']);self.assertEqual(r['orders'],0)
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'copy';shutil.copytree(FOLDER,p);(p/'receipt.json').write_text('{}')
   with self.assertRaises(ValueError):verify(p)
if __name__=='__main__':unittest.main()
