"""Adversarial file-flow, field-flow and semantic-only nonduplication tests."""
import ast
import builtins
import copy
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch
from research_core_v4 import strict_reselection_v2 as b
from research_core_v4 import master1576_current_state_guard_v3 as g
ROOT=Path(__file__).resolve().parents[1]
class StrictFirewallTests(unittest.TestCase):
    def setUp(self):self.d=g.read(ROOT,b.INPUT);self.r=g.read(ROOT,b.RESULT);self.states=[g.read(ROOT,p) for p in g.STATES];self.h=g.sha(ROOT,g.AUTH)
    def deny(self,d):
        with self.assertRaises(ValueError):b.build(d)
    def test_01_exact_input_projection(self):self.assertEqual(b.canonical(b.project_root(ROOT)),(ROOT/b.INPUT).read_bytes())
    def test_02_projector_reads_only_exact_allowlist(self):
        seen=[];b.project_root(ROOT,seen);self.assertEqual(set(seen),b.READS);self.assertEqual(len(seen),3)
    def test_03_selection_reads_only_neutral_input(self):
        seen=[];b.build_root(ROOT,seen);self.assertEqual(seen,[b.INPUT])
    def test_04_forbidden_files_blocked(self):
        paths=[b.S+'POST_QUOTE_V4_CLOSURE_LEDGER_V2.json',b.S+'V3_CLOSURE_DEPENDENCY_GRAPH_V1.json',b.S+'NEXT_INFORMATION_SOURCE_SELECTION_V6.json','research_core_v4/triad_v7/distributed/FINAL_V7_RUNTIME_BLOCKER_AUTHORITY_V1.json',b.S+'PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_MATRIX_V1.json',b.S+'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json']
        for p in paths:
            with self.subTest(path=p),b.io_firewall(ROOT,{b.INPUT},[]):
                with self.assertRaisesRegex(ValueError,'READ_FIREWALL_DENIED'):(ROOT/p).read_bytes()
    def test_05_builtin_io_and_os_read_routes_blocked(self):
        p=ROOT/(b.S+'POST_QUOTE_V4_CLOSURE_LEDGER_V2.json')
        for reader in [lambda:builtins.open(p),lambda:io.open(p),lambda:os.open(p,os.O_RDONLY)]:
            with b.io_firewall(ROOT,{b.INPUT},[]):
                with self.assertRaisesRegex(ValueError,'READ_FIREWALL_DENIED'):reader()
    def test_06_write_denied(self):
        with b.io_firewall(ROOT,{b.INPUT},[]):
            with self.assertRaisesRegex(ValueError,'READ_FIREWALL_DENIED'):open(ROOT/b.INPUT,'w')
    def test_07_catalog_priority_and_outcome_status_poison_do_not_flow(self):
        cat=g.read(ROOT,b.S+'INFORMATION_SOURCE_CATALOG_V1.json');s=g.read(ROOT,b.S+'MASTER1576_QUALIFICATION_V2_POST_SCREEN_STRUCTURAL_SUMMARY_V1.json');r=g.read(ROOT,b.S+'MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json')
        before=b.project(cat,s,r)
        for x in cat['sources']:x.update(priority='WINNER_FIRST',v3_status='CARRY_FORWARD_HARD_CLOSURE',v4_role='BEST_PNL',note='P_VALUE_0.001')
        cat['first_wave_selected_source']='TRIAD_V7';self.assertEqual(before,b.project(cat,s,r))
    def test_08_summary_classification_poison_does_not_flow(self):
        c=g.read(ROOT,b.S+'INFORMATION_SOURCE_CATALOG_V1.json');s=g.read(ROOT,b.S+'MASTER1576_QUALIFICATION_V2_POST_SCREEN_STRUCTURAL_SUMMARY_V1.json');r=g.read(ROOT,b.S+'MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json')
        s['classification_counts']={'WINNER':1576};s['status']='ECONOMIC_SUCCESS';s['support_limited_records']=[{'PNL':999}];r['status']='BEST_PAST_SYMBOL';self.assertEqual(self.d,b.project(c,s,r))
    def test_09_closure_classes_rejected_if_injected_into_comparison(self):
        for x in ['CARRY_FORWARD_HARD_CLOSURE','AUTHENTIC_FRICTION_CLOSED','EXACT_SPECIFICATION_CLOSED_BROADER_CONCEPT_OPEN','METHOD_DEPENDENT_REINTERPRETATION_REQUIRED']:
            d=copy.deepcopy(self.d);d['source_definitions'][0]['definition']=x;self.deny(d)
    def test_10_catalog_priority_rejected_after_projection(self):
        d=copy.deepcopy(self.d);d['source_definitions'][0]['priority']='HIGH';self.deny(d)
    def test_11_result_fields_and_nested_taints_rejected(self):
        for k in ['classification','historical_pvalues','historical_returns','historical_pnl','winner_status','near_miss','effect_size','pass_fail']:
            d=copy.deepcopy(self.d);d['context_geometry'][next(iter(d['context_geometry']))][k]=1;self.deny(d)
    def test_12_unknown_fields_fail_closed(self):
        d=copy.deepcopy(self.d);d['modalities']['canonical_m5']['arbitrary_status']='DATA_LIMITED';self.deny(d)
    def test_13_no_V6_or_triad_automatic_continuation(self):
        for x in ['NEXT_INFORMATION_SOURCE_SELECTION_V6','TRIAD_V7']:
            d=copy.deepcopy(self.d);d['automatic_selection']=x;self.deny(d)
        self.assertIsNone(self.r['selection']['selected_source']);self.assertIsNone(self.r['selection']['selected_mechanism'])
    def test_14_all12_candidate_definitions_all16_fields(self):
        self.assertEqual([x['information_source'] for x in self.r['candidates']],list(b.SOURCE_IDS))
        for x in self.r['candidates']:self.assertEqual(set(x),b.FIELDS);self.assertTrue(all(x.values()))
    def test_15_deterministic_repeatability(self):
        self.assertEqual(b.canonical(b.build(self.d)),b.canonical(b.build_root(ROOT)));self.assertEqual(b.canonical(b.build_root(ROOT)),(ROOT/b.RESULT).read_bytes())
    def test_16_no_network_or_process_in_selection(self):
        with patch('socket.socket',side_effect=AssertionError('No network')),patch('urllib.request.urlopen',side_effect=AssertionError('No network')),patch('subprocess.Popen',side_effect=AssertionError('No processes')):b.build_root(ROOT);b.project_root(ROOT)
    def test_17_selector_has_no_network_or_subprocess_imports(self):
        tree=ast.parse((ROOT/'research_core_v4/strict_reselection_v2.py').read_text())
        imports=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):imports.extend(x.name.split('.')[0] for x in n.names)
            if isinstance(n,ast.ImportFrom):imports.append(n.module.split('.')[0])
        self.assertFalse(set(imports)&{'socket','urllib','requests','http','subprocess'})
    def semantics(self):return {'mechanism_identity':'TRIAD_V7','feature_definition':'Causal identity relation','context_cohort_definition':'Prospective declared cohort','horizon_family':[1,12],'response_function':'Future closed bar displacement definition only','parameterization':'Fixed prospective specification'}
    def test_18_registry_semantics_only_accepts_historical_identity(self):b.validate_registry([self.semantics()])
    def test_19_registry_result_fields_rejected(self):
        for k in ['result','pass_fail','p_value','effect_size','return','pnl','winner_status','near_miss_status','economic_success']:
            r=self.semantics();r[k]=1
            with self.assertRaisesRegex(ValueError,'REGISTRY_NON_SEMANTIC_FIELD'):b.validate_registry([r])
    def test_20_registry_result_values_rejected(self):
        r=self.semantics();r['feature_definition']='AUTHENTIC_FRICTION_CLOSED'
        with self.assertRaisesRegex(ValueError,'REGISTRY_RESULT_VALUE'):b.validate_registry([r])
    def test_21_exact_collision_only_blocks_identical_semantics(self):
        r=self.semantics();self.assertTrue(b.exact_collision(r,[r]));other=copy.deepcopy(r);other['feature_definition']='Different causal extraction';self.assertFalse(b.exact_collision(other,[r]))
    def test_22_collision_cannot_rank_other_sources(self):
        before=b.build(self.d);r=self.semantics();b.exact_collision(r,[r]);self.assertEqual(before,b.build(self.d));self.assertFalse(before['selection']['historical_design_registry_used'])
    def test_23_V1_semantic_correction_exact_fact(self):
        d=g.read(ROOT,g.CORRECTION);self.assertIn('NOT_STRICT_OUTCOME_BLIND',d['status']);self.assertIsNone(d['selected_source']);self.assertIsNone(d['selected_mechanism']);self.assertFalse(d['new_response_opened']);self.assertEqual(d['search_budget_use'],0)
    def test_24_all_historical_files_byte_identical(self):
        protocol=g.read(ROOT,g.AUTH)
        for x in protocol['immutable_bindings']:
            self.assertEqual((ROOT/x['ref']).read_bytes(),subprocess.check_output(['git','show',g.BASE+':'+x['ref']],cwd=ROOT))
    def test_25_preserved_state_history_exact(self):
        for p,d in zip(g.STATES,self.states):
            before=json.loads(subprocess.check_output(['git','show',g.BASE+':'+p],cwd=ROOT));hist=d['historical_current_state_before_strict_reselection_v2']
            for k,v in before.items():self.assertEqual(hist[k] if k in hist else d[k],v)
    def test_26_successor_current_state_guard(self):g.validate_root(ROOT)
    def test_27_each_action_pointer_drift_denied(self):
        for i,k in [(0,'current_next_action_type'),(0,'next_action'),(0,'stop_boundary'),(1,'next_action'),(2,'next_action'),(2,'current_operation')]:
            d=copy.deepcopy(self.states);d[i][k]='OLD'
            with self.assertRaisesRegex(ValueError,'CURRENT_ACTION_DRIFT'):g.validate(d,self.h)
    def test_28_current_authority_and_hash_drift_denied(self):
        for i in range(3):
            for nested in [False,True]:
                for k,code in [('current_authority','CURRENT_AUTHORITY_DRIFT'),('current_authority_sha256','CURRENT_AUTHORITY_HASH_DRIFT')]:
                    d=copy.deepcopy(self.states);q=d[i]['strict_preoutcome_reselection_v2'] if nested else d[i];q[k]='OLD'
                    with self.assertRaisesRegex(ValueError,code):g.validate(d,self.h)
    def test_29_stale_V1_and_shallow_current_pointers_denied(self):
        d=copy.deepcopy(self.states);d[0]['project_wide_information_source_reselection']={}
        with self.assertRaisesRegex(ValueError,'STALE_CURRENT_STAGE'):g.validate(d,self.h)
        d=copy.deepcopy(self.states);d[0]['execution_instruction']='PENDING_SHALLOW_M5_REAL_ARM'
        with self.assertRaisesRegex(ValueError,'STALE_SHALLOW_ARM'):g.validate(d,self.h)
    def test_30_budget_closed_boundaries_and_no_response(self):
        p=g.read(ROOT,g.AUTH);self.assertEqual(p['search_budget'],g.BUDGET);self.assertFalse(any(p['boundary'].values()))
        self.assertTrue(self.r['no_claim_of_erased_project_adaptivity']);self.assertFalse(self.r['market_response_opened']);self.assertFalse(self.r['duration_selected']);self.assertEqual(self.r['power_trials'],0)
        for k in ['confirmation_opened','protected_forward_opened']:
            d=copy.deepcopy(self.states);d[1][k]=True
            with self.assertRaisesRegex(ValueError,'CLOSED_BOUNDARY_DRIFT'):g.validate(d,self.h)
    def test_31_workflow_no_secret_no_dispatch_no_write(self):
        s=(ROOT/'.github/workflows/strict-reselection-v2-offline.yml').read_text();self.assertIn('contents: read',s)
        for x in ['secrets.','contents: write','workflow'+'_dispatch','download_asset','ctrader','run_authorized']:self.assertNotIn(x,s.lower())
    def test_32_exact_change_allowlist(self):
        expected={*g.STATES,g.AUTH,g.CORRECTION,b.INPUT,b.RESULT,'research_core_v4/strict_reselection_v2.py','research_core_v4/master1576_current_state_guard_v3.py','research_core_v4/strict_reselection_v2_preflight_v1.py','tests/test_strict_reselection_v2.py','.github/workflows/strict-reselection-v2-offline.yml'}
        changed=set(subprocess.check_output(['git','diff','--name-only',g.BASE,'HEAD'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines());self.assertEqual(changed,expected)
