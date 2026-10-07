"""Offline categorical audit and adversarial successor-state regression checks."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from research_core_v4 import master1576_current_state_guard_v2 as g
ROOT=Path(__file__).resolve().parents[1]
class ReselectionTests(unittest.TestCase):
    def setUp(self):
        self.states=[g.read(ROOT,p) for p in g.STATES];self.a=g.read(ROOT,g.AUTH);self.m=g.read(ROOT,g.MATRIX);self.h=g.sha(ROOT/g.AUTH)
    def deny(self,code,states):
        with self.assertRaisesRegex(ValueError,code):g.validate(states,self.h)
    def test_01_successor_guard(self):g.validate_root(ROOT)
    def test_02_all_six_action_pointers(self):
        for i,k in [(0,'current_next_action_type'),(0,'next_action'),(0,'stop_boundary'),(1,'next_action'),(2,'next_action'),(2,'current_operation')]:
            d=copy.deepcopy(self.states);d[i][k]='OTHER';self.deny('CURRENT_ACTION_DRIFT',d)
    def test_03_authority_and_hash_all_current_paths(self):
        for i in range(3):
            for k,code in [('current_authority','CURRENT_AUTHORITY_DRIFT'),('current_authority_sha256','CURRENT_AUTHORITY_HASH_DRIFT')]:
                for nested in [False,True]:
                    d=copy.deepcopy(self.states);target=d[i]['project_wide_information_source_reselection'] if nested else d[i];target[k]='WRONG';self.deny(code,d)
    def test_04_stale_arm_regression(self):
        for i in range(3):
            d=copy.deepcopy(self.states);d[i]['current_execution_instruction']='PENDING_SEPARATE_REAL_SHALLOW_M5_ARM_AUTHORIZATION';self.deny('STALE_SHALLOW_ARM_STATE',d)
    def test_05_stale_V6_plan_regression(self):
        d=copy.deepcopy(self.states);d[0]['current_action_type']='CONTINUE_TRIAD';self.deny('STALE_V6_CURRENT_POINTER',d)
    def test_06_historical_namespace_exemption(self):
        d=copy.deepcopy(self.states);d[0]['historical_old_arm']={'current_authority':'old','current_action_type':'old','status':'PENDING_SHALLOW_M5_REAL_ARM'};g.validate(d,self.h)
    def test_07_budget_and_closed_boundary_injections(self):
        d=copy.deepcopy(self.states);d[1]['search_budget']['used']=22;self.deny('BUDGET_DRIFT',d)
        for k in ['protected_forward_opened','confirmation_opened']:
            d=copy.deepcopy(self.states);d[1][k]=True;self.deny('CLOSED_BOUNDARY_DRIFT',d)
    def test_08_current_status_drift(self):
        d=copy.deepcopy(self.states);d[0]['status']='BREADTH_COMPLETE_ACCEPTED_INFORMATION_DESIGN_AND_DURATION_UNRESOLVED';self.deny('V4_TOP_STATUS_DRIFT',d)
    def test_09_historical_states_recover_exact_prior_values(self):
        for p,d in zip(g.STATES,self.states):
            before=json.loads(subprocess.check_output(['git','show',g.BASE+':'+p],cwd=ROOT));hist=d['historical_current_state_before_project_wide_reselection_v1']
            for k,v in before.items():
                if k in hist:self.assertEqual(hist[k],v)
                else:self.assertEqual(d[k],v)
            for k in before:
                if k.startswith('historical_'):self.assertEqual(d[k],before[k])
    def test_10_every_immutable_binding_exact_at_audited_base(self):
        for b in self.a['immutable_bindings']:
            self.assertEqual((ROOT/b['ref']).read_bytes(),subprocess.check_output(['git','show',g.BASE+':'+b['ref']],cwd=ROOT))
    def test_11_every_catalog_source_and_closure_covered(self):
        cat=g.read(ROOT,g.S+'INFORMATION_SOURCE_CATALOG_V1.json');self.assertEqual([x['information_source'] for x in self.m['sources']],[x['id'] for x in cat['sources']])
        ledger=g.read(ROOT,g.S+'POST_QUOTE_V4_CLOSURE_LEDGER_V2.json');nodes=next(v for v in ledger.values() if isinstance(v,list) and len(v)==51)
        expected={x['id']:x.get('v4_classification',x.get('classification')) for x in nodes};actual={x['id']:x['classification'] for s in self.m['sources'] for x in s['categorical_closures']};self.assertEqual(actual,expected)
    def test_12_exact_11_comparison_dimensions(self):
        expected={'information_distinctness','scientific_identifiability','causal_availability','support_and_synchronization_feasibility','dependence_geometry_feasibility','compute_feasibility','acquisition_burden','execution_and_friction_observability','time_to_genuine_economic_information','generalization_path','confirmation_path'}
        for s in self.m['sources']:self.assertEqual(set(s['comparison_dimensions']),expected)
    def test_13_no_forbidden_fields_or_numeric_VOI(self):
        forbidden={'metrics','leaf_effects','leaf_pvalues','effect_signs','pnl','returns','priority','numeric_voi','symbol_ranking','context_ranking'}
        def visit(d):
            if isinstance(d,dict):
                self.assertFalse(set(d)&forbidden)
                for v in d.values():visit(v)
            elif isinstance(d,list):
                for v in d:visit(v)
        visit(self.m);visit(self.a);self.assertFalse(self.m['catalog_priority_used_as_selection']);self.assertEqual(self.m['forbidden_selection_inputs_used'],[])
    def test_14_unresolved_not_global_null_or_power_requirement(self):
        self.assertIsNone(self.a['selected_source']);self.assertIsNone(self.a['selected_mechanism']);self.assertFalse(self.a['complete_information_design_created']);self.assertTrue(self.a['not_power_prerequisite'])
        for s in self.m['sources']:self.assertFalse(s['broader_family_global_null']);self.assertTrue(s['blocking_design_uncertainty'])
    def test_15_no_execution_power_duration_or_budget_use(self):
        self.assertFalse(any(self.a['boundary'].values()));self.assertEqual(self.a['search_budget'],g.BUDGET);self.assertTrue(self.a['triad_v7_parked']);self.assertFalse(self.a['triad_v8_created']);self.assertFalse(self.a['fixed_top_k']);self.assertFalse(self.a['unknown_cost_assumed_zero'])
    def test_16_offline_guard_no_network(self):
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')),patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden')):g.validate_root(ROOT)
    def test_17_no_acquisition_design_or_new_selection_plan(self):
        for n in ['NEXT_INFORMATION_SOURCE_SELECTION_V7','MASTER1576_V2_DEEP_HISTORICAL_M5_DURATION_DECISION_V1','MASTER1576_V2_DEEP_M5_MISSING_INTERVAL_MATRIX_V1','MASTER1576_V2_DEEP_M5_ACQUISITION_DESIGN_V1','MASTER1576_V2_DEEP_M5_EXISTING_COVERAGE_RECONCILIATION_V1']:
            self.assertFalse((ROOT/(g.S+n+'.json')).exists())
    def test_18_workflow_no_secret_no_market_no_dispatch(self):
        t=(ROOT/'.github/workflows/project-wide-reselection-offline.yml').read_text();self.assertIn('contents: read',t)
        for x in ['secrets.','contents: write','workflow'+'_dispatch','ctrader','download_asset','decrypt','run_authorized']:self.assertNotIn(x,t.lower())
    def test_19_canonical_current_selection_absent(self):
        for d in self.states:
            self.assertNotIn('next_information_source_selection',d);self.assertEqual(d['project_wide_information_source_reselection']['status'],g.NEXT)
    def test_20_no_other_repository_changes(self):
        expected={*g.STATES,g.AUTH,g.MATRIX,'research_core_v4/master1576_current_state_guard_v2.py','research_core_v4/project_wide_reselection_preflight_v1.py','tests/test_project_wide_reselection_v1.py','.github/workflows/project-wide-reselection-offline.yml'}
        changed=set(subprocess.check_output(['git','diff','--name-only',g.BASE,'HEAD'],cwd=ROOT,text=True).splitlines())
        # Local precommit adds untracked files; CI checks the committed final head.
        changed.update(subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines());changed.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        self.assertEqual(changed,expected)
