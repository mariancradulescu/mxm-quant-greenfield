import hashlib,json,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger
from m7.competition_ultra_fast_stage_a_frontier_v2_evaluator import CAP,COST_SHA,CID,EXPECTED_SPEC_HASH,generate_trades
ROOT=Path(__file__).resolve().parents[1]
EVAL_SHA="0f82fe738963058923163403e73bf214c1c17bd45c954e90428b5202c0c2bb39"

class UltraFastEconomicWave02FreezeTests(unittest.TestCase):
 def test_01_c023_spec_hash_and_wave_binding(self):
  s=json.loads((ROOT/"discovery/candidates/V2-C023.json").read_text())
  w=json.loads((ROOT/"discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_02_V1.json").read_text())
  self.assertTrue(verify_spec_hash(s));self.assertEqual(s["spec_hash"],EXPECTED_SPEC_HASH)
  self.assertEqual(w["candidate_ids"],[CID]);self.assertEqual(w["candidate_spec_hashes"][CID],EXPECTED_SPEC_HASH)
  self.assertTrue(s["provenance"]["frozen_before_candidate_own_economic_outcome"])
  self.assertFalse(s["provenance"]["candidate_own_return_or_pnl_used"])

 def test_02_evaluator_data_and_cost_are_exactly_prebound(self):
  w=json.loads((ROOT/"discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_02_V1.json").read_text())
  p=ROOT/w["evaluator_ref"];self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),EVAL_SHA)
  self.assertEqual(w["evaluator_sha256"],EVAL_SHA);self.assertEqual(w["capture_sha256"],CAP);self.assertEqual(w["cost_authority_sha256"],COST_SHA)
  a=json.loads((ROOT/w["capture_acceptance_ref"]).read_text());self.assertEqual(a["source"]["zip_sha256"],CAP)
  self.assertEqual(a["status"],"ACCEPTED_COMPLETE_PRE_ECONOMIC_STAGE_A_CAPTURE")
  self.assertEqual(a["validation"]["implementation_invalid_conditions"],0)
  c=json.loads((ROOT/w["cost_authority_ref"]).read_text());self.assertTrue(c["rule"]["candidate_independent"]);self.assertTrue(c["rule"]["outcome_blind"])

 def test_03_ledger_freezes_c023_without_consuming_attempt(self):
  led=read_ledger(ROOT/"discovery/ledger.jsonl");self.assertGreaterEqual(len(led),39);e=led[38]
  self.assertEqual(e["sequence"],39);self.assertEqual(e["entry_type"],"CANDIDATE_FROZEN");self.assertEqual(e["candidate_id"],CID);self.assertEqual(e["spec_hash"],EXPECTED_SPEC_HASH)
  self.assertEqual(e["previous_entry_hash"],"5c93b265b44d1ceaa2897ddf62bf8630b8d3deee1823d20cbedd4575f096d7fb")
  w=json.loads((ROOT/"discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_02_V1.json").read_text())
  a=w["accounting_before_execution"];self.assertEqual((a["v2_attempts_used"],a["v2_evaluated_identities"],a["remaining"]),(8,8,76));self.assertEqual(a["new_attempts_consumed"],0)
  self.assertFalse(w["safety"]["protected_evidence_opened"]);self.assertFalse(w["safety"]["live_orders"]);self.assertFalse(w["safety"]["competition_start"])

 def test_04_wave_is_materially_distinct_and_pre_outcome_gated(self):
  w=json.loads((ROOT/"discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_02_V1.json").read_text())
  self.assertEqual(w["status"],"FROZEN_BEFORE_C023_ECONOMIC_OUTCOME_PENDING_EXACT_HEAD_CI")
  self.assertTrue(w["material_distinction"]["not_a_symmetric_transform_batch"])
  self.assertFalse(w["material_distinction"]["wave01_realized_pnl_used_for_parameter_fit"])
  self.assertIn("REQUIRE_EXACT_HEAD",w["execution_gate"]);self.assertEqual(w["accounting_before_execution"]["new_attempts_consumed"],0)

 def test_05_synthetic_four_hour_cross_market_selection_is_causal_and_single(self):
  start=datetime(2026,6,15,tzinfo=timezone.utc)
  rows={}
  symbols=("USDJPY","GBPUSD","USDCHF","AUDUSD","US500","US2000","SpotCrude","SpotBrent","ETHUSD","Copper")
  for si,s in enumerate(symbols):
   q=[]
   strength=0.00001*(si+1)
   if s=="GBPUSD": strength=0.001
   for i in range(160):
    px=100.0*(1.0+strength*i)
    q.append({"t":start+timedelta(minutes=5*i),"o":px,"h":px*1.0001,"l":px*0.9999,"c":px})
   rows[s]=q
  t=generate_trades(rows)
  self.assertEqual(len(t),1);self.assertEqual(t[0]["s"],"GBPUSD");self.assertEqual(t[0]["e"],start+timedelta(hours=8));self.assertEqual(t[0]["x"],start+timedelta(hours=12))

if __name__=="__main__": unittest.main()
