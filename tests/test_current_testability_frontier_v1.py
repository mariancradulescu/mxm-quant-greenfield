import copy,json,unittest
from pathlib import Path
from fractions import Fraction as F
from research_core_v4 import current_testability_frontier_v1 as c
from research_core_v4 import current_wave_presupport_geometry_v1 as g
from research_core_v4.strict_reselection_v2 import canonical,io_firewall
from research_core_v4.master1576_current_state_guard_v9 import validate_root
class FrontierTests(unittest.TestCase):
 def load(self,p):return json.loads(Path(p).read_bytes())
 def test_all_own_classifications_reproduce_isolated(self):
  for s in c.SOURCES:
   seen=[];v=c.build_one('.',s,seen);self.assertEqual(canonical(v),Path(c.status_ref(s)).read_bytes());self.assertEqual(seen,[c.BASE,c.packet_ref(s)])
 def test_frontier_reproduces(self):self.assertEqual(c.assemble({s:self.load(c.status_ref(s)) for s in c.SOURCES}),self.load(c.FRONTIER))
 def test_global_twelve_preserved(self):
  f=self.load(c.FRONTIER);self.assertEqual(len(f['global_candidate_ledger_preserved']),12);self.assertEqual({x['information_source'] for x in f['global_candidate_ledger_preserved']},set(c.SOURCES));self.assertEqual(f['global_unknown_source_count'],11)
 def test_five_members_six_parked(self):
  f=self.load(c.FRONTIER);self.assertEqual(set(f['current_wave']),set(g.SOURCES));self.assertEqual(set(f['parked_sources']),set(c.PARK))
 def test_parked_not_negative_null_or_permanent(self):
  for s in c.PARK:
   v=self.load(c.status_ref(s));self.assertEqual(v['current_wave_status'],c.PARK[s][0]);self.assertEqual(v['global_candidate_status'],'UNKNOWN_GLOBAL_SCIENTIFIC_AND_ECONOMIC_STATUS')
   for k in ['parked_is_null','parked_is_negative_edge','parked_is_permanent_exclusion','ranking_or_edge_claim']:self.assertFalse(v[k])
 def test_univariate_exact_only_no_family_null(self):self.assertEqual(self.load(c.status_ref('UNIVARIATE_PRICE_STATE'))['global_candidate_status'],'EXACT_BASELINE_REDUNDANT_PROPOSAL_FAMILY_NOT_NULL')
 def test_no_global_selection_or_reapplication(self):
  f=self.load(c.FRONTIER);self.assertIsNone(f['selected_source']);self.assertFalse(f['current_wave_is_global_selection']);self.assertFalse(f['global_functional_reapplied']);self.assertFalse(f['global_prior_assessments_modified']);self.assertIsNone(f['current_wave_ranking'])
 def test_every_member_satisfies_structural_gate(self):
  for s in g.SOURCES:self.assertTrue(all(self.load(c.status_ref(s))['eligibility_gates'].values()))
 def test_no_empirical_certification_from_membership(self):
  for s in c.SOURCES:
   d=self.load(c.status_ref(s));self.assertFalse(d['historical_causal_availability_certified']);self.assertFalse(d['empirical_support_certified']);self.assertFalse(d['power_ready'])
 def test_missing_semantics_denied(self):
  p=self.load(c.packet_ref(g.SOURCES[0]));p['own_response_authority']=None
  with self.assertRaises(ValueError):c.classify(p)
 def test_no_external_route_denied(self):
  p=self.load(c.packet_ref(g.SOURCES[0]));p['shared_laws']['accepted_support_route_exists']=False
  with self.assertRaises(ValueError):c.classify(p)
 def test_peer_packet_injection_denied(self):
  p=self.load(c.packet_ref(g.SOURCES[0]));p['own_candidate']['information_source']='TOP_OF_BOOK_QUOTE_STATE'
  with self.assertRaises(ValueError):c.classify(p)
 def test_comparative_extra_field_denied(self):
  p=self.load(c.packet_ref(g.SOURCES[0]));p['comparison_rank']=1
  with self.assertRaises(ValueError):c.classify(p)
 def test_foreign_files_and_market_rows_denied(self):
  for p in [c.status_ref(g.SOURCES[1]),c.prior.RESULT,'data/bars.json','shallow-m5-v2-seg1-shard00.mxmenc']:
   with io_firewall('.',{c.BASE,c.packet_ref(g.SOURCES[0])},[]):
    with self.assertRaises(ValueError):Path(p).read_bytes()
 def test_baseline_and_global_functional_hashes(self):
  self.assertEqual(c.sha(Path(c.BASE).read_bytes()),c.BASE_HASH);self.assertEqual(c.sha(Path(c.prior.f.FUNCTIONAL).read_bytes()),c.F_HASH)
 def test_four_frozen_maps_in_own_packets(self):
  authority=self.load(c.prior.SEM)
  for s,a in authority['authorities'].items():self.assertEqual(self.load(c.packet_ref(s))['own_feature_authority'],a)
 def test_governance_packet_projection(self):
  a=self.load(c.GOV)
  for s in g.SOURCES:
   p=self.load(c.packet_ref(s));self.assertEqual(p['own_response_authority'],a['cross_sectional_exact_semantics'] if s=='CROSS_SECTIONAL_RELATIVE_STATE' else a['response_authorities'][s])
 def test_cross_sectional_exact_nonredundancy_realization(self):
  loc=lambda close:F(close-1,2)
  peersA=[loc(1),loc(3)];peersB=[loc(2),loc(2)];variance=lambda v:sum((x-sum(v)/len(v))**2 for x in v)/len(v)
  self.assertEqual(variance(peersA),F(1,4));self.assertEqual(variance(peersB),0)
 def test_response_horizons_match_governance(self):
  d=self.load(c.SUPPORT)
  for s in g.SOURCES:self.assertEqual(d['per_candidate'][s]['response_horizons_M5'],[12] if s=='REGIME_AND_STRUCTURAL_BREAK_STATE' else [1,12])
 def test_regime_hour_schedule_and_complete_future(self):
  w=g.required_windows('REGIME_AND_STRUCTURAL_BREAK_STATE',10800,12);self.assertEqual(w['feature'],list(range(3600,10800,300)));self.assertEqual(w['future'],list(range(10800,14400,300)))
  with self.assertRaises(ValueError):g.required_windows('REGIME_AND_STRUCTURAL_BREAK_STATE',11100,12)
  with self.assertRaises(ValueError):g.required_windows('REGIME_AND_STRUCTURAL_BREAK_STATE',10800,1)
 def test_multiscale_exact_disjoint_readset(self):
  w=g.required_windows('MULTISCALE_PRICE_STATE',10800,12);self.assertEqual(len(w['feature']),15);self.assertEqual(w['feature'][:3],[6300,6600,6900]);self.assertFalse(set(w['feature'])&set(w['future']))
 def test_baseline_latest_hour_plus_last(self):
  w=g.required_windows('BROKER_NATIVE_ACTIVITY_STATE',11100,12);self.assertEqual(len(w['baseline']),13);self.assertIn(10800,w['baseline']);self.assertEqual(w['feature'],list(range(7200,10800,300)))
 def test_future_horizon_endpoints_no_feature_leak(self):
  for s in g.SOURCES:
   w=g.required_windows(s,10800,12);self.assertEqual(w['future'][0],10800);self.assertEqual(w['future'][-1]+300,14400);self.assertFalse(set(w['future'])&set(w['feature']))
 def test_unknown_original_availability_not_promoted(self):
  self.assertIsNone(g.causal_conjunction([True,None]));self.assertFalse(g.causal_conjunction([False,None]));self.assertTrue(g.causal_conjunction([True,True]))
 def test_frozen_peers_exclude_own_and_unknown(self):self.assertEqual(g.frozen_synthetic_peers(1,[1,2,3,4],{1:True,2:True,3:True,4:None}),(2,3))
 def test_response_subset_cannot_add_peer(self):
  p=(2,3,4);self.assertEqual(g.response_synthetic_subset(p,{2:True,3:False,4:True}),(2,4))
  with self.assertRaises(ValueError):g.response_synthetic_subset(p,{2:True,3:True,4:False,5:True})
 def test_two_peer_minimum_is_frozen(self):
  a=self.load(c.GOV)['cross_sectional_exact_semantics'];self.assertEqual(a['minimum_fresh_peers'],2);self.assertEqual(a['minimum_valid_peer_responses'],2)
 def test_overlap_uses_identity_and_time(self):
  self.assertTrue(g.symbolic_overlap([(1,300),(1,600)],[(1,600)]));self.assertFalse(g.symbolic_overlap([(1,300)],[(2,300)]))
 def test_cross_midnight_calendar_dates_preserved(self):self.assertEqual(g.shared_dates([86100,86400]),[0,1])
 def test_inherited_domain_not_new_duration(self):
  p=self.load(c.SUPPORT);self.assertIsNone(p['source_domain']['chosen_new_duration']);self.assertEqual(p['source_domain']['M5_entry_grid_slots'],8064);self.assertTrue(p['source_domain']['all_archive_segments_required'])
 def test_protocol_covers_all_required_fields(self):
  p=self.load(c.SUPPORT)
  for s in g.SOURCES:
   d=p['per_candidate'][s]
   for k in ['feature_readset','baseline_readset','response_availability_mask_only','timestamp_masks','identity_context_mask','missingness_mask','feature_window_length_M5','response_window_lengths_M5','execution_friction_later']:self.assertIn(k,d)
  for k in ['overlap_graph','shared_calendar_block_unit','required_outputs','compute_operation_bound']:self.assertIn(k,p)
 def test_effective_calendar_not_independent_N(self):self.assertIn('never ESS',self.load(c.SUPPORT)['required_outputs']['effective_calendar_support'])
 def test_operation_bound_is_derived_not_empirical(self):
  b=self.load(c.SUPPORT)['compute_operation_bound'];self.assertEqual(b['bound_value'],20*b['accepted_master_rows_metadata']+4000*b['eligible_identities']*b['entry_grid_slots']+100*b['context_count']*b['entry_grid_slots']);self.assertLessEqual(242*12+1000,4000)
 def test_route_assets_hash_and_size_bound(self):
  d=self.load(c.ROUTE);self.assertEqual(len(d['assets']),100);self.assertEqual(sum(x['encrypted_bytes'] for x in d['assets']),49708418);self.assertEqual(d['exact_minimum_files_required']['encrypted_assets'],100);self.assertTrue(d['redecryption_required_for_later_stage']);self.assertFalse(d['new_broker_contact_required_for_reuse'])
 def test_archive_availability_not_invented(self):
  d=self.load(c.ROUTE);self.assertFalse(d['archive_original_availability_field_present']);self.assertNotIn('available_at',d['archive_schema']);self.assertFalse(d['shallow_data_contiguous_enough_for_all_five_candidates_certified'])
 def test_support_not_executed(self):
  p=self.load(c.SUPPORT);self.assertFalse(p['execution_in_this_task']);self.assertIsNone(p['authorization_for_future_execution']);q=self.load(c.PREFLIGHT);self.assertIsNone(q['real_support_counts']);self.assertIsNone(q['real_dependence_geometry'])
 def test_all_zero_activity(self):
  p=self.load(c.SUPPORT)
  for k in ['market_rows_read','broker_requests','redecryptions','support_measurements','power_trials','new_economic_outcomes','search_budget_use']:self.assertEqual(p[k],0)
  for k in ['duration_selected','protected_forward_opened','confirmation_opened']:self.assertFalse(p[k])
 def test_current_canonical_guard(self):self.assertEqual(validate_root('.')['status'],'PASS_CURRENT_TESTABILITY_PRE_SUPPORT')
