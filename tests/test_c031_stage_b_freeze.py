import json, pathlib, unittest
from m7.c031_stage_b_frozen_v1 import C031StageBError, FROZEN, SPEC_HASH, execute_after_authorization
class C031FreezeTests(unittest.TestCase):
 def test_frozen_hashes_and_scope(self):
  self.assertEqual(len(FROZEN),4); self.assertEqual(len(SPEC_HASH),64)
  for gz,raw in FROZEN.values(): self.assertEqual((len(gz),len(raw)),(64,64))
 def test_execution_fails_closed_without_authorization(self):
  with self.assertRaises(C031StageBError): execute_after_authorization('.',authorization={})
 def test_freeze_document_is_pre_economic(self):
  d=json.loads(pathlib.Path('evidence/C031_STAGE_B_PRE_ECONOMIC_FREEZE_V1.json').read_text())
  self.assertEqual(d['status'],'FROZEN_PENDING_EXACT_HEAD_GREEN'); self.assertFalse(d['execution_authorized']); self.assertEqual(d['accounting_effect']['economic_outcomes_opened'],0); self.assertEqual(d['accounting_effect']['v2_attempts_consumed'],0)
  self.assertEqual(d['materialization']['counts']['intents'],129); self.assertEqual(d['materialization']['counts']['market_path_bars'],1666); self.assertEqual(d['financing']['rollover_crossings'],0)
if __name__=='__main__': unittest.main()
