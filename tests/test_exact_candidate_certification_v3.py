import copy,json,unittest
from pathlib import Path
from fractions import Fraction as F
from research_core_v4 import exact_candidate_certification_v3 as c
from research_core_v4.prospective_exact_semantics_v3 import feature,synthetic_witness
from research_core_v4.compact_baseline_v2 import baseline
from research_core_v4.strict_reselection_v2 import canonical,io_firewall
from research_core_v4.master1576_current_state_guard_v8 import validate_root
OWN=('MULTISCALE_PRICE_STATE','VOLATILITY_AND_REALIZED_VARIANCE_STATE','BROKER_NATIVE_ACTIVITY_STATE','REGIME_AND_STRUCTURAL_BREAK_STATE')
class ExactTests(unittest.TestCase):
 def cert(self,s):return json.loads(Path(c.ref(s)).read_bytes())
 def witness(self,s):return synthetic_witness(s)
 def test_all_eleven_reproduce_own_packet_only(self):
  for s in c.SOURCES:
   with self.subTest(s=s):
    seen=[];self.assertEqual(canonical(c.build_one('.',s,seen)),Path(c.ref(s)).read_bytes());self.assertEqual(seen,[c.BASE,c.packet_ref(s)])
 def test_packet_contains_no_peer_authority(self):
  sem=json.loads(Path(c.SEM).read_bytes());audit=json.loads(Path(c.AUDIT).read_bytes())
  facts={x['information_source']:x for x in audit['audit_records']}
  for s in c.SOURCES:
   p=json.loads(Path(c.packet_ref(s)).read_bytes());self.assertEqual(p['exact_semantic_authority'],sem['authorities'].get(s));self.assertEqual(p['own_capability_fact'],facts.get(s));self.assertNotIn('authorities',p)
 def test_baseline_same_in_eleven(self):
  for s in c.SOURCES:self.assertEqual(self.cert(s)['baseline']['sha256'],c.BASE_HASH)
 def test_manifest_hashes(self):
  m=json.loads(Path(c.MANIFEST).read_bytes());self.assertEqual(len(m['certificates']),11)
  for x in m['certificates']:
   self.assertEqual(c.sha(Path(x['ref']).read_bytes()),x['sha256']);self.assertEqual(c.sha(Path(x['packet_ref']).read_bytes()),x['packet_sha256'])
 def test_candidate_definitions_unchanged(self):
  for d in json.loads(Path(c.f.PROPOSALS).read_bytes())['candidates'][1:]:self.assertEqual(self.cert(d['information_source'])['unchanged_definition'],d)
 def test_functional_and_baseline_byte_exact(self):
  self.assertEqual(c.sha(Path(c.f.FUNCTIONAL).read_bytes()),c.F_HASH);self.assertEqual(c.sha(Path(c.BASE).read_bytes()),c.BASE_HASH)
 def test_reapplication_reproducible(self):self.assertEqual(c.reapply('.',[]),json.loads(Path(c.RESULT).read_bytes()))
 def test_no_selection_unknown_competitors(self):
  r=json.loads(Path(c.RESULT).read_bytes());self.assertIsNone(r['selected_source']);self.assertEqual((r['admissible_count'],r['exact_failed_count'],r['unknown_count']),(0,1,11))
 def test_exact_feature_gates_progress(self):
  r=json.loads(Path(c.RESULT).read_bytes());passed=[x['information_source'] for x in r['assessments'] if x['hard_gates']['identifiable_incremental_claim']=='PASS'];self.assertEqual(set(passed),set(OWN))
 def test_four_nonredundancy_pairs(self):
  for s in OWN:
   w=self.witness(s);self.assertEqual(baseline(w['t'],w['bars_A']),baseline(w['t'],w['bars_B']));self.assertNotEqual(feature(s,w['t'],w['bars_A']),feature(s,w['t'],w['bars_B']))
 def test_multiscale_disjoint_interval_and_product(self):
  w=self.witness(OWN[0]);self.assertEqual(feature(OWN[0],w['t'],w['bars_A']),1);self.assertEqual(feature(OWN[0],w['t'],w['bars_B']),-1)
 def test_variation_analytic_scale_cancellation(self):
  w=self.witness(OWN[1]);self.assertEqual(feature(OWN[1],w['t'],w['bars_A']),1);self.assertEqual(feature(OWN[1],w['t'],w['bars_B']),F(1,2))
 def test_activity_order_not_histogram(self):
  w=self.witness(OWN[2]);self.assertEqual(feature(OWN[2],w['t'],w['bars_A'])[0],F(1,24));self.assertEqual(feature(OWN[2],w['t'],w['bars_B'])[0],F(3,24))
 def test_wasserstein_empirical_exact(self):
  w=self.witness(OWN[3]);self.assertEqual(feature(OWN[3],w['t'],w['bars_A']),0);self.assertEqual(feature(OWN[3],w['t'],w['bars_B']),F(2,3))
 def test_zero_variation(self):
  w=self.witness(OWN[1]);a=w['bars_A']
  for b in a:b['close']=b['open']
  self.assertEqual(feature(OWN[1],w['t'],a),0)
 def test_zero_activity_vector(self):
  w=self.witness(OWN[2]);a=w['bars_A']
  for b in a:b['tick_volume']=0
  self.assertEqual(feature(OWN[2],w['t'],a),(F(0),)*11)
 def test_flat_locations(self):
  for s in [OWN[0],OWN[3]]:
   w=self.witness(s)
   for b in w['bars_A']:b.update(open=2,high=2,low=2,close=2)
   self.assertEqual(feature(s,w['t'],w['bars_A']),0)
 def test_missing_required_bar(self):
  for s in OWN:
   w=self.witness(s);a=w['bars_A'];a.pop(-1);self.assertIsNone(feature(s,w['t'],a))
 def test_duplicate_required_bar(self):
  for s in OWN:
   w=self.witness(s);a=w['bars_A'];a.append(dict(a[-1]));self.assertIsNone(feature(s,w['t'],a))
 def test_delayed_required_bar(self):
  for s in OWN:
   w=self.witness(s);a=w['bars_A'];a[-1]['available_at']=w['t']+1;self.assertIsNone(feature(s,w['t'],a))
 def test_nonpositive_log_prices(self):
  w=self.witness(OWN[1]);w['bars_A'][-1].update(open=0,low=0);self.assertIsNone(feature(OWN[1],w['t'],w['bars_A']))
 def test_future_bar_not_visible(self):
  for s in OWN:
   w=self.witness(s);a=w['bars_A'];before=feature(s,w['t'],a);future=dict(a[-1]);future['timestamp']=w['t'];future['available_at']=w['t']+300;future['close']=999;a.append(future);self.assertEqual(feature(s,w['t'],a),before)
 def test_bad_grid(self):
  with self.assertRaises(ValueError):feature(OWN[0],10801,[])
 def test_response_conflicts_preserve_response(self):
  for s in [OWN[1],OWN[3]]:
   v=self.cert(s);self.assertEqual(v['response_semantic_integrity'],'PROSPECTIVE_RESPONSE_GOVERNANCE_REQUIRED');self.assertFalse(v['response_governance_blocker']['response_modified']);self.assertEqual(v['response_function_unchanged'],v['unchanged_definition']['response_function'])
 def test_peer_and_history_reads_denied(self):
  for p in [c.ref(c.SOURCES[1]),c.old.ref(c.SOURCES[0]),'research_core_v4/triad_v7/RESULT.json','data/market.csv']:
   with io_firewall('.',{c.BASE,c.packet_ref(c.SOURCES[0])},[]):
    with self.assertRaises(ValueError):Path(p).read_bytes()
 def test_peer_fact_injection_denied(self):
  p=json.loads(Path(c.packet_ref('SESSION_AND_LIQUIDITY_STATE')).read_bytes());p['own_capability_fact']['information_source']='TOP_OF_BOOK_QUOTE_STATE'
  with self.assertRaises(ValueError):c.certificate(p,json.loads(Path(c.BASE).read_bytes()))
 def test_baseline_tamper_denied(self):
  b=json.loads(Path(c.BASE).read_bytes());b['status']='changed'
  with self.assertRaises(ValueError):c.certificate(json.loads(Path(c.packet_ref(OWN[0])).read_bytes()),b)
 def test_no_external_phi_invented(self):
  for s in set(c.SOURCES)-set(OWN):self.assertIsNone(self.cert(s)['exact_feature_map_Phi_i']);self.assertFalse(self.cert(s)['historical_support_authenticated'])
 def test_capability_uses_only_authorities(self):
  a=json.loads(Path(c.AUDIT).read_bytes());self.assertEqual(len(a['audit_records']),7)
  for x in a['sources']:self.assertIn(x['authority_class'],a['allowed_authority_classes']);self.assertEqual(c.sha(Path(x['ref']).read_bytes()),x['sha256'])
  for x in a['audit_records']:self.assertFalse(x['authentic_support_certified']);self.assertFalse(x['historical_point_in_time_authority_already_present'])
 def test_optional_swap_absent_not_zero(self):
  p=json.loads(Path('research_core_v4/nonmarket_contract_v3/METADATA_CAPABILITY_PROJECTION_V3.json').read_bytes());self.assertEqual(p['current_field_presence_counts']['swapLong'],0);self.assertEqual(p['current_field_presence_counts']['swapShort'],0);self.assertFalse(p['historical_asof_revision_archive_certified'])
 def test_boundary_honest_about_governance(self):
  b=json.loads(Path(c.BOUNDARY).read_bytes());self.assertTrue(b['not_purely_broker_empirical_boundary']);self.assertFalse(b['complete_information_design']);self.assertIsNone(b['prepower_structural_contract']);self.assertEqual(len(b['candidate_plans']),11)
 def test_all_prohibitions(self):
  b=json.loads(Path(c.BOUNDARY).read_bytes())
  for k in ['new_market_rows','historical_outcome_files_read_by_inference','broker_contacts','ctrader_auth_or_requests','redecryptions','empirical_support_measurements','empirical_dependence_estimations','power_trials','new_economic_outcomes','search_budget_use']:self.assertEqual(b[k],0)
  for k in ['duration_selected','protected_forward_opened','confirmation_opened','ARM_created']:self.assertFalse(b[k])
 def test_current_canonical_state(self):self.assertEqual(validate_root('.')['status'],'PASS_EXACT_CANDIDATE_CLOSURE')
