"""Strict functional, partial-order invariants, discriminator bounds and anti-drift tests."""
import builtins
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from research_core_v4 import strict_selection_functional_v1 as f
from research_core_v4 import master1576_current_state_guard_v4 as g
ROOT=Path(__file__).resolve().parents[1]
class FunctionalTests(unittest.TestCase):
    def setUp(self):
        self.outputs={p:g.read(ROOT,p) for p in [f.ASSESSMENT,f.GAP,f.PLAN]};self.a=self.outputs[f.ASSESSMENT];self.states=[g.read(ROOT,p) for p in g.STATES];self.h=g.sha(ROOT,g.AUTH)
    def allpass(self,source):return {'information_source':source,'hard_gates':{k:'PASS' for k in f.GATES}}
    def equal(self):return {k:'CERTIFIED_EQUAL' for k in f.DIMENSIONS}
    def test_01_functional_frozen_before_comparison(self):self.assertEqual((ROOT/f.FUNCTIONAL).read_bytes(),f.canonical(f.functional()));self.assertEqual(self.a['functional_sha256'],f.sha((ROOT/f.FUNCTIONAL).read_bytes()))
    def test_02_exact_three_selection_reads(self):
        seen=[];f.build_root(ROOT,seen);self.assertEqual(set(seen),f.ALLOWLIST);self.assertEqual(len(seen),3)
    def test_03_historical_files_all_denied(self):
        for p in ['PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_MATRIX_V1.json','POST_QUOTE_V4_CLOSURE_LEDGER_V2.json','V3_CLOSURE_DEPENDENCY_GRAPH_V1.json','NEXT_INFORMATION_SOURCE_SELECTION_V6.json','FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json']:
            with f.io_firewall(ROOT,f.ALLOWLIST,[]):
                with self.assertRaisesRegex(ValueError,'READ_FIREWALL_DENIED'):(ROOT/(f.S+p)).read_bytes()
        p=ROOT/'research_core_v4/triad_v7/distributed/FINAL_V7_RUNTIME_BLOCKER_AUTHORITY_V1.json'
        with f.io_firewall(ROOT,f.ALLOWLIST,[]):
            with self.assertRaisesRegex(ValueError,'READ_FIREWALL_DENIED'):p.read_bytes()
    def test_04_all_open_routes_deny_historical_file(self):
        p=ROOT/(f.S+'POST_QUOTE_V4_CLOSURE_LEDGER_V2.json')
        for reader in [lambda:builtins.open(p),lambda:io.open(p),lambda:os.open(p,os.O_RDONLY)]:
            with f.io_firewall(ROOT,f.ALLOWLIST,[]):
                with self.assertRaises(ValueError):reader()
    def test_05_unknown_gate_blocks_admissibility(self):
        d=self.allpass('A')['hard_gates'];d['support_measurable']='UNKNOWN';self.assertEqual(f.admissibility(d),'UNKNOWN')
    def test_06_failed_gate_blocks_exact_proposal(self):
        d=self.allpass('A')['hard_gates'];d['identifiable_incremental_claim']='FAIL';self.assertEqual(f.admissibility(d),'FAIL')
    def test_07_all_hard_constraints_required(self):
        d=self.allpass('A')['hard_gates'];d.pop('execution_friction_path')
        with self.assertRaisesRegex(ValueError,'HARD_GATE_SCHEMA'):f.admissibility(d)
    def test_08_single_fully_admissible_can_be_selected_synthetic(self):self.assertEqual(f.select([self.allpass('A')],{}),'A')
    def test_09_two_equal_candidates_no_tiebreak(self):self.assertIsNone(f.select([self.allpass('A'),self.allpass('B')],{('A','B'):self.equal(),('B','A'):self.equal()}))
    def test_10_unknown_pairwise_not_equal(self):self.assertFalse(f.dominates({k:'UNKNOWN' for k in f.DIMENSIONS}))
    def test_11_certified_scientific_dominance_selects_synthetic(self):
        p=self.equal();p['CAUSAL_IDENTIFIABILITY']='CERTIFIED_BETTER';q=self.equal();q['CAUSAL_IDENTIFIABILITY']='CERTIFIED_WORSE'
        self.assertEqual(f.select([self.allpass('A'),self.allpass('B')],{('A','B'):p,('B','A'):q}),'A')
    def test_12_convenience_only_cannot_win(self):
        for k in ['COMPUTE_FEASIBILITY','REQUIRED_MODALITY_ALREADY_AVAILABLE','ADDITIONAL_DATA_BURDEN','TIME_TO_GENUINE_ECONOMIC_TEST']:
            p=self.equal();p[k]='CERTIFIED_BETTER';self.assertFalse(f.dominates(p));self.assertIsNone(f.select([self.allpass('A'),self.allpass('B')],{('A','B'):p}))
    def test_13_scientific_tradeoff_incomparable(self):
        p=self.equal();p['CAUSAL_IDENTIFIABILITY']='CERTIFIED_BETTER';p['DISJOINT_CONFIRMATION_PATH']='CERTIFIED_WORSE';self.assertFalse(f.dominates(p))
    def test_14_unresolved_competitor_not_silently_discarded(self):
        a=self.allpass('A');b=self.allpass('B');b['hard_gates']['identifiable_incremental_claim']='UNKNOWN';self.assertIsNone(f.select([a,b],{}))
    def test_15_unknown_not_zero_cost(self):self.assertFalse(self.a['unknown_cost_is_zero']);self.assertIsNone(self.a['selection_rate_numeric_estimate'])
    def test_16_source_order_never_breaks_tie(self):
        rows=[self.allpass('Z'),self.allpass('A')];self.assertIsNone(f.select(rows,{}));self.assertIsNone(f.select(rows[::-1],{}))
    def test_17_all12_frozen_candidates_byte_identical(self):
        p=g.read(ROOT,f.PROPOSALS);self.assertEqual(self.a['candidate_definitions_sha256'],f.sha(f.canonical(p['candidates'])))
        self.assertEqual([x['information_source'] for x in self.a['assessments']],[x['information_source'] for x in p['candidates']])
        for x,c in zip(self.a['assessments'],p['candidates']):self.assertEqual(x['frozen_mechanism_sha256'],f.sha(f.canonical(c)))
    def test_18_required_13_dimensions_all_candidates(self):
        for x in self.a['assessments']:self.assertEqual(set(x['dimensions']),set(f.DIMENSIONS));self.assertTrue(x['EXACT_UNRESOLVED_STRUCTURAL_QUANTITIES'])
    def test_19_zero_admissible_exact_accounting(self):
        self.assertEqual((self.a['candidate_count'],self.a['currently_admissible_count'],self.a['exact_semantic_fail_count'],self.a['unknown_admissibility_count']),(12,0,1,11));self.assertIsNone(self.a['selected_source']);self.assertIsNone(self.a['selected_mechanism'])
    def test_20_baseline_redundancy_semantic_not_outcome(self):
        p=g.read(ROOT,f.PROPOSALS)['candidates'][0];self.assertIn('hourly high-low range',p['materially_distinct_causal_mechanism']);self.assertIn('hourly price location',p['own_information_baseline']);self.assertEqual(self.a['assessments'][0]['hard_gates']['identifiable_incremental_claim'],'FAIL');self.assertFalse(self.outputs[f.GAP]['known_exact_redundancy']['history_used'])
    def test_21_old_comparison_and_reason_not_used(self):
        d=g.read(ROOT,f.INPUT);p=g.read(ROOT,f.PROPOSALS);p['comparison']=[{'classification':'WINNER','pnl':999}];p['selection']['reason']='HISTORICAL_NEAR_MISS';self.assertEqual(f.assess(d,p,f.functional()),self.a)
    def test_22_discriminator_exact_semantic_quantity(self):
        p=self.outputs[f.PLAN];self.assertIn('sigma(Phi_i)',p['EXACT_MISSING_STRUCTURAL_QUANTITY']);self.assertEqual(len(p['WHICH_CURRENT_CANDIDATES_IT_CAN_DISTINGUISH']),11);self.assertEqual(len(p['certificate_fields']),10)
    def test_23_no_market_volume_or_time_window(self):
        d=self.outputs[f.PLAN]['MINIMUM_DATA_VOLUME_OR_TIME_WINDOW_IF_STRUCTURALLY_DERIVABLE'];self.assertEqual((d['authentic_market_rows'],d['shared_baseline_records'],d['candidate_certificate_records_maximum']),(0,1,11));self.assertIsNone(d['historical_time_window'])
    def test_24_no_discriminator_execution_or_broker(self):
        p=self.outputs[f.PLAN]
        for k in ['execution_in_this_task','WHETHER_RAW_MARKET_RESPONSE_IS_REQUIRED','WHETHER_BROKER_CONTACT_WOULD_BE_REQUIRED','WHETHER_REDECRYPTION_WOULD_BE_REQUIRED','new_structural_information_acquired','new_market_data_acquired','duration_selected']:self.assertFalse(p[k])
        self.assertEqual(p['power_trials'],0)
    def test_25_minimum_is_first_stage_not_guaranteed_winner(self):
        self.assertIn('not a proven globally minimal guaranteed',self.outputs[f.GAP]['minimum_claim_scope']);self.assertGreaterEqual(len(self.outputs[f.PLAN]['STOP_RULE']),4)
    def test_26_deterministic_no_network_or_process(self):
        with patch('socket.socket',side_effect=AssertionError('Offline')),patch('urllib.request.urlopen',side_effect=AssertionError('Offline')),patch('subprocess.Popen',side_effect=AssertionError('No subprocess')):
            one=f.build_root(ROOT);two=f.build_root(ROOT)
        for p in one:self.assertEqual(f.canonical(one[p]),f.canonical(two[p]));self.assertEqual(f.canonical(one[p]),(ROOT/p).read_bytes())
    def test_27_all_immutable_authorities_preserved(self):
        for x in g.read(ROOT,g.AUTH)['immutable_bindings']:self.assertEqual((ROOT/x['ref']).read_bytes(),subprocess.check_output(['git','show',g.BASE+':'+x['ref']],cwd=ROOT))
    def test_28_prior_current_state_history_preserved(self):
        for p,d in zip(g.STATES,self.states):
            before=json.loads(subprocess.check_output(['git','show',g.BASE+':'+p],cwd=ROOT));hist=d['historical_current_state_before_selection_functional_v1']
            for k,v in before.items():self.assertEqual(hist[k] if k in hist else d[k],v)
    def test_29_current_guard_and_six_pointers(self):
        g.validate_root(ROOT)
        for i,k in [(0,'current_next_action_type'),(0,'next_action'),(0,'stop_boundary'),(1,'next_action'),(2,'next_action'),(2,'current_operation')]:
            d=copy.deepcopy(self.states);d[i][k]='OLD'
            with self.assertRaisesRegex(ValueError,'ACTION_DRIFT'):g.validate(d,self.h)
    def test_30_all_current_authority_paths_fail_closed(self):
        for i in range(3):
            for nested in [False,True]:
                for k,code in [('current_authority','AUTHORITY_DRIFT'),('current_authority_sha256','AUTHORITY_HASH_DRIFT')]:
                    d=copy.deepcopy(self.states);q=d[i]['strict_v2_selection_functional'] if nested else d[i];q[k]='WRONG'
                    with self.assertRaisesRegex(ValueError,code):g.validate(d,self.h)
    def test_31_budget_closed_boundaries_unchanged(self):
        a=g.read(ROOT,g.AUTH);self.assertEqual(a['search_budget'],g.BUDGET);self.assertFalse(any(a['boundary'].values()));self.assertEqual(a['preservation']['eligible_roster_count'],1575);self.assertFalse(a['preservation']['support_limited_identity']['global_null']);self.assertEqual(a['preservation']['power_lower95_target'],.8)
    def test_32_workflow_no_secret_no_write_no_dispatch(self):
        t=(ROOT/'.github/workflows/strict-selection-functional-offline.yml').read_text();self.assertIn('contents: read',t)
        for token in ['secrets.','contents: write','workflow'+'_dispatch','ctrader','download_asset','run_authorized']:self.assertNotIn(token,t.lower())
    def test_33_exact_change_allowlist(self):
        expected={*g.STATES,g.AUTH,f.FUNCTIONAL,f.ASSESSMENT,f.GAP,f.PLAN,'research_core_v4/strict_selection_functional_v1.py','research_core_v4/master1576_current_state_guard_v4.py','research_core_v4/strict_selection_functional_preflight_v1.py','tests/test_strict_selection_functional_v1.py','.github/workflows/strict-selection-functional-offline.yml'}
        changed=set(subprocess.check_output(['git','diff','--name-only',g.BASE,'HEAD'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines());self.assertEqual(changed,expected)
