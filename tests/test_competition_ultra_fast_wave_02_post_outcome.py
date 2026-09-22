import hashlib,json,unittest
from pathlib import Path
from discovery.canonical import compute_result_hash
from discovery.accounting import assert_current_state_matches_repository
from discovery.ledger import read_ledger
from discovery.schema import validate_result
ROOT=Path(__file__).resolve().parents[1]
CID="V2-C023"
SPEC_HASH="c2b8ec06c54743b38168980c7746c50401f563ebee45c55b876654423807b34a"
RESULT_HASH="e11ea2b1d8b66a1dcae565e3067d5bbba2a49ab9fb401ebf476a6d14ec476d98"
FREEZE_ENTRY_HASH="53dca50e9a18769baf1ba4a6455c1fe1adb8cd6477bdee55b6e01a8cde93522a"
RESULT_ENTRY_HASH="7cf8e844e9771b3b01af8d134cda7ce1b5aa9bb42442d30d02893cdffa2fd2ed"
PRE_HEAD="60fef8e658c4c6c81bd3e3bc1f6f6ca587000930"
PRE_RUN=35726820195
CAP="dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d"
EVAL_SHA="0f82fe738963058923163403e73bf214c1c17bd45c954e90428b5202c0c2bb39"
COST_SHA="b7ca6191b5570c1cc22f644feb6b0124c6bec0f00fc5ad5a8c772419bcb481b9"
def load(p):return json.loads((ROOT/p).read_text())
class UltraFastWave02PostOutcomeTests(unittest.TestCase):
 def test_01_result_is_hash_valid_immutable_gross_fail(self):
  r=load('discovery/results/V2-C023_STAGE_A_V1.json');validate_result(r)
  self.assertEqual(r['candidate_id'],CID);self.assertEqual(r['spec_hash'],SPEC_HASH);self.assertEqual(r['result_hash'],RESULT_HASH);self.assertEqual(compute_result_hash(r),RESULT_HASH);self.assertEqual(r['status'],'GROSS_EDGE_FAIL')
  self.assertEqual(r['metrics']['event_count'],386);self.assertAlmostEqual(r['metrics']['gross_pnl'],-86.67661227016303);self.assertAlmostEqual(r['metrics']['coarse_net_pnl'],-199.02819006194892)
 def test_02_ledger_appends_result_once_and_preserves_freeze(self):
  led=read_ledger(ROOT/'discovery/ledger.jsonl');self.assertGreaterEqual(len(led),40);f=led[38];e=led[39]
  self.assertEqual((f['sequence'],f['entry_type'],f['candidate_id'],f['entry_hash']),(39,'CANDIDATE_FROZEN',CID,FREEZE_ENTRY_HASH))
  self.assertEqual((e['sequence'],e['entry_type'],e['candidate_id'],e['entry_hash']),(40,'RESULT_RECORDED',CID,RESULT_ENTRY_HASH));self.assertEqual(e['previous_entry_hash'],FREEZE_ENTRY_HASH);self.assertEqual(e['spec_hash'],SPEC_HASH)
  r=load('discovery/results/V2-C023_STAGE_A_V1.json');self.assertEqual(e['payload']['result_hash'],RESULT_HASH);self.assertEqual(e['payload']['result'],r)
  self.assertEqual(sum(x['entry_type']=='RESULT_RECORDED' and x['candidate_id']==CID for x in led),1)
 def test_03_pre_outcome_gate_and_immutable_inputs_are_exact(self):
  p=load('data/COMPETITION_ULTRA_FAST_WAVE_02_EXECUTION_PROGRESS_V1.json');g=p['pre_outcome_execution_gate'];self.assertEqual(g['head_sha'],PRE_HEAD);self.assertEqual(g['workflow_run_id'],PRE_RUN);self.assertEqual(g['conclusion'],'SUCCESS');self.assertEqual((g['tests_passed'],g['tests_failed']),(652,0))
  a=p['immutable_pre_outcome_authorities'];self.assertEqual(a['capture_zip_sha256'],CAP);self.assertEqual(a['candidate_spec_hash'],SPEC_HASH);self.assertEqual(a['evaluator_sha256'],EVAL_SHA);self.assertEqual(a['cost_authority_sha256'],COST_SHA)
 def test_04_completion_is_no_survivor_with_natural_hard21(self):
  c=load('data/COMPETITION_ULTRA_FAST_WAVE_02_COMPLETION_V1.json');self.assertEqual(c['status'],'COMPLETE_NO_STAGE_A_SURVIVOR');self.assertEqual(c['promotion']['stage_a_survivor_ids'],[]);self.assertEqual(c['promotion']["stage_b_26_week_extension_ids"],[])
  h=c['natural_hard21'];self.assertEqual(h['weeks_ge_21'],13);self.assertEqual(h['weeks_lt_21'],0);self.assertGreaterEqual(h['minimum_entries_week'],21)
  x=c['stage_a_results'][CID];self.assertEqual(x['result_hash'],RESULT_HASH);self.assertAlmostEqual(x['gross_pnl_eur'],-86.67661227016303);self.assertAlmostEqual(x['transaction_cost_eur'],112.35157779178611);self.assertAlmostEqual(x['coarse_net_pnl_eur'],-199.02819006194892)
 def test_05_live_accounting_is_repository_derived_after_later_corrections(self):
  d=assert_current_state_matches_repository(ROOT);s=load('CURRENT_STATE.json')
  self.assertIn(CID,d['evaluated_candidate_ids']);self.assertEqual(d['latest_economic_outcome']['candidate_id'],CID);self.assertEqual(d['latest_economic_outcome']['result_hash'],RESULT_HASH)
  self.assertFalse(s['protected_evidence_opened']);self.assertFalse(s['live_orders_authorized']);self.assertFalse(s['competition_start_authorized'])
if __name__=='__main__':unittest.main()
