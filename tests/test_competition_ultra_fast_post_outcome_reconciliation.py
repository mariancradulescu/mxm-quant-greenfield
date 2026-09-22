import hashlib,json,unittest
from pathlib import Path
from discovery.ledger import read_ledger
ROOT=Path(__file__).resolve().parents[1]
OPENED=("V2-C017","V2-C018","V2-C019","V2-C020","V2-C021","V2-C022")
HASHES={
 "V2-C017":"9870baf130d12e9864489c6d0ebe83a80b4fa3a38f1b2c5321ac03e1dc64029b",
 "V2-C018":"f1a647f633d46d26dfa2b9d971b72e4bf3c53dd4eef9971ed0503cd2018fe69c",
 "V2-C019":"65cf8e6358da6f304cce53a9f3ec3abfb922525c8de2f2a59ca0ce1fe637e9c6",
 "V2-C020":"28b9fac70c1b39e7d782103324327c5c6249452868293c5a9bcc4fa137a7b8c2",
 "V2-C021":"ab2b23edb01a913cc2aace95591bf004d6458cc3b3d254eca26625d211e5d1a2",
 "V2-C022":"e9ff00de31092034959980248779dde9b080482757a170bd3a8383081122c3d2",
}
ENTRY_HASHES={
 "V2-C017":"11a2166d19008b3899fe6299e0671d76cd6957580fd8ae2eab89a569cf332d44",
 "V2-C018":"62f570ff6063906274332750c946573895d194dfe15c6c44f7f42cb3d6877096",
 "V2-C019":"2ddf8e1846b3e8b91d9878053cbbbd61a83c953bce3f343a73787ba1fdc3262e",
 "V2-C020":"c24fc66ddfacb754442c654519408087c46be2d78938310122f9d226bc26a974",
 "V2-C021":"d75f44b6a85161fcb9745d58744925decca34a40c508afcd78adfb995496389b",
 "V2-C022":"5c93b265b44d1ceaa2897ddf62bf8630b8d3deee1823d20cbedd4575f096d7fb",
}
SPEC_HASHES={
 "V2-C017":"ac981d5475a0dbd1cd65d2a33d9e84f7035eb8fc9831179712e3d5a1c19d2b2a",
 "V2-C018":"bb806537478f880e0b7eab73734c824d7a47f815335b2d15f5f94c78e9dd6711",
 "V2-C019":"18a39ff07bead88e09067eefb13667ccf559d28b657f2a7e8d97f7025d6f91b1",
 "V2-C020":"326cdb9a4a14c752e71d256c9026ea0fd8efa9832cdf6a4f98afbc26158cc461",
 "V2-C021":"8e10fa83d33dfa69aa463cd1ead657a03b0f1d02cb7f68ab40fcacf4629dfa06",
 "V2-C022":"35ed3af139abb68bdb829da0ae90de78ddc80eb87aea1f20ae22d71d3ecb9d7f",
}
def load(p):return json.loads((ROOT/p).read_text())
def git_blob_sha1(data):
 return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
class UltraFastPostOutcomeReconciliationTests(unittest.TestCase):
 def test_01_all_wave_01_result_files_are_exact(self):
  for cid in OPENED:
   r=load(f'discovery/results/{cid}_STAGE_A_V1.json')
   self.assertEqual(r['candidate_id'],cid);self.assertEqual(r['result_hash'],HASHES[cid]);self.assertEqual(r['spec_hash'],SPEC_HASHES[cid])
  self.assertEqual(load('discovery/results/V2-C017_STAGE_A_V1.json')['status'],'GROSS_EDGE_FAIL')
  self.assertEqual(load('discovery/results/V2-C018_STAGE_A_V1.json')['status'],'COARSE_NET_FAIL')
  for cid in ('V2-C019','V2-C020','V2-C021','V2-C022'):
   self.assertEqual(load(f'discovery/results/{cid}_STAGE_A_V1.json')['status'],'GROSS_EDGE_FAIL')
 def test_02_ledger_prefix_is_immutable_and_wave_results_append_once(self):
  raw=(ROOT/'discovery/ledger.jsonl').read_bytes().splitlines(keepends=True);self.assertEqual(len(raw),38)
  self.assertEqual(git_blob_sha1(b''.join(raw[:32])),'b6f9d9b5e9ed26cd3497ac5ed4d5ac1387bc5d79')
  led=read_ledger(ROOT/'discovery/ledger.jsonl');tail=led[32:38]
  self.assertEqual([e['sequence'] for e in tail],list(range(33,39)))
  self.assertEqual([e['candidate_id'] for e in tail],list(OPENED))
  self.assertTrue(all(e['entry_type']=='RESULT_RECORDED' for e in tail))
  for e in tail:
   cid=e['candidate_id'];self.assertEqual(e['spec_hash'],SPEC_HASHES[cid]);self.assertEqual(e['payload']['result_hash'],HASHES[cid]);self.assertEqual(e['payload']['result']['result_hash'],HASHES[cid]);self.assertEqual(e['entry_hash'],ENTRY_HASHES[cid])
 def test_03_frozen_pre_outcome_authorities_and_gate_remain_authoritative(self):
  p=load('data/COMPETITION_ULTRA_FAST_WAVE_01_EXECUTION_PROGRESS_V1.json');g=p['pre_outcome_execution_gate']
  self.assertEqual(g['head_sha'],'ad072b5929479d4215c07924534a098ec4b176f0');self.assertEqual(g['workflow_run_id'],35716960856);self.assertEqual(g['conclusion'],'SUCCESS');self.assertTrue(g['exact_head'])
  self.assertEqual(p['immutable_pre_outcome_authorities']['capture_zip_sha256'],'dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d')
  self.assertEqual(p['immutable_pre_outcome_authorities']['evaluator_sha256'],'b9b8fdecd7b415116149e611ff09961fe92793c66ec3d42796afa12946a46c6d')
 def test_04_final_wave_accounting_and_safety_are_exact(self):
  s=load('CURRENT_STATE.json');p=load('data/COMPETITION_ULTRA_FAST_WAVE_01_EXECUTION_PROGRESS_V1.json')
  self.assertEqual((s['v2_evaluated_identities'],s['v2_attempts_used'],s['v2_search_budget_remaining']),(8,8,76))
  self.assertEqual((s['global_attempts_seen'],s['economic_outcomes_opened']),(24,10))
  self.assertEqual((s['discovery_ledger_entries'],s['discovery_result_recorded_entries']),(38,8))
  self.assertEqual(s['latest_economic_outcome']['candidate_id'],'V2-C022');self.assertEqual(s['latest_economic_outcome']['result_hash'],HASHES['V2-C022'])
  self.assertEqual((p['accounting_after_reconciliation']['v2_evaluated_identities'],p['accounting_after_reconciliation']['v2_attempts_used'],p['accounting_after_reconciliation']['v2_search_budget_remaining']),(8,8,76))
  self.assertEqual(p['accounting_after_reconciliation']['double_counted_attempts'],0)
  self.assertFalse(s['protected_evidence_opened']);self.assertFalse(s['live_orders_authorized']);self.assertFalse(s['competition_start_authorized'])
 def test_05_wave_01_closes_with_no_survivor_or_26_week_extension(self):
  s=load('CURRENT_STATE.json');c=load('data/COMPETITION_ULTRA_FAST_WAVE_01_COMPLETION_V1.json')
  self.assertEqual(c['status'],'COMPLETE_NO_STAGE_A_SURVIVOR')
  self.assertEqual(c['promotion']['stage_a_survivor_ids'],[])
  self.assertEqual(c['promotion']['stage_b_26_week_extension_ids'],[])
  self.assertEqual(s['competition_ultra_fast_economic_wave']['completion_ref'],'data/COMPETITION_ULTRA_FAST_WAVE_01_COMPLETION_V1.json')
  self.assertEqual(s['competition_ultra_fast_economic_wave']['stage_a_survivor_ids'],[])
  self.assertEqual(c['natural_hard21']['weeks_ge_21'],13)
  self.assertEqual(c['shared_eur200']['state'],'NOT_EVALUATED')
if __name__=='__main__':unittest.main()
