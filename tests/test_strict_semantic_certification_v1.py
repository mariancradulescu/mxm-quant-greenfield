"""Semantic isolation, freeze sequence, unresolved-map integrity and frozen functional tests."""
import builtins
import copy
import inspect
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from research_core_v4 import strict_semantic_certification_v1 as s
from research_core_v4 import master1576_current_state_guard_v5 as g
ROOT=Path(__file__).resolve().parents[1]
class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.docs=s.load_allowed(ROOT);self.base=g.read(ROOT,s.BASELINE);self.result=g.read(ROOT,s.REAPPLIED);self.states=[g.read(ROOT,p) for p in g.STATES];self.h=g.sha(ROOT,g.AUTH)
    def copy_sources(self,root):
        for p in s.ALLOWED:f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((ROOT/p).read_bytes())
    def test_01_exact_five_builder_reads(self):
        seen=[];s.derive_certificates(ROOT,seen);self.assertEqual(set(seen),s.ALLOWED);self.assertEqual(len(seen),5)
    def test_02_historical_outcome_files_denied(self):
        paths=[s.S+'PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_MATRIX_V1.json',s.S+'POST_QUOTE_V4_CLOSURE_LEDGER_V2.json',s.S+'V3_CLOSURE_DEPENDENCY_GRAPH_V1.json',s.S+'NEXT_INFORMATION_SOURCE_SELECTION_V6.json','research_core_v4/triad_v7/distributed/FINAL_V7_RUNTIME_BLOCKER_AUTHORITY_V1.json',s.S+'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json']
        for p in paths:
            with s.io_firewall(ROOT,s.ALLOWED,[]):
                with self.assertRaisesRegex(ValueError,'READ_FIREWALL_DENIED'):(ROOT/p).read_bytes()
    def test_03_io_routes_blocked(self):
        p=ROOT/(s.S+'POST_QUOTE_V4_CLOSURE_LEDGER_V2.json')
        for op in [lambda:builtins.open(p),lambda:io.open(p),lambda:os.open(p,os.O_RDONLY)]:
            with s.io_firewall(ROOT,s.ALLOWED,[]):
                with self.assertRaises(ValueError):op()
    def test_04_constructor_cannot_read_any_file(self):
        candidate=self.docs[s.PROPOSALS]['candidates'][1]
        with s.io_firewall(ROOT,set(),[]):
            s.certificate(candidate,self.base,self.docs[s.INPUT]['modalities'])
            with self.assertRaises(ValueError):(ROOT/s.cert_ref(s.SOURCES[1])).read_bytes()
    def test_05_constructor_input_capability_isolation(self):
        self.assertEqual(list(inspect.signature(s.certificate).parameters),['candidate','baseline','neutral_modalities'])
        for c in self.docs[s.PROPOSALS]['candidates'][1:]:
            # Give the function only the current candidate's feature-gap entry.
            with patch.object(s,'FEATURE_GAPS',{c['information_source']:s.FEATURE_GAPS[c['information_source']]}):
                got=s.certificate(copy.deepcopy(c),copy.deepcopy(self.base),copy.deepcopy(self.docs[s.INPUT]['modalities']))
            self.assertEqual(got,g.read(ROOT,s.cert_ref(c['information_source'])))
    def test_06_other_candidate_poison_cannot_change_own_certificate(self):
        candidates=copy.deepcopy(self.docs[s.PROPOSALS]['candidates']);c=candidates[1];first=s.certificate(c,self.base,self.docs[s.INPUT]['modalities'])
        for peer in candidates[2:]:peer.update(materially_distinct_causal_mechanism='WINNER',comparative_position='BEST_PNL')
        self.assertEqual(first,s.certificate(c,self.base,self.docs[s.INPUT]['modalities']))
    def test_07_no_comparative_reason_in_certificate_inputs(self):
        self.assertNotIn('comparison',inspect.signature(s.certificate).parameters)
        for c in self.docs[s.PROPOSALS]['candidates'][1:]:
            cert=s.certificate(c,self.base,self.docs[s.INPUT]['modalities']);self.assertEqual(cert['candidate_definition_sha256'],s.sha(s.canonical(c)))
    def test_08_baseline_freeze_precedes_each_constructor(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.copy_sources(root);original=s.certificate;seen=[];writes=[];write_original=Path.write_bytes
            def written(path,data):
                writes.append((str(path.relative_to(root)),data));return write_original(path,data)
            def checked(c,b,m):
                self.assertTrue(writes);self.assertEqual(writes[0],(s.BASELINE,s.canonical(b)));seen.append(c['information_source']);return original(c,b,m)
            with patch.object(Path,'write_bytes',written),patch.object(s,'certificate',checked),patch.object(s.functional,'select',side_effect=AssertionError('No comparison before freeze')):s.freeze_certificates(root)
            self.assertEqual(seen,list(s.SOURCES));self.assertTrue((root/s.FREEZE).exists())
    def test_09_all_eleven_frozen_before_reapplication(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.copy_sources(root);s.freeze_certificates(root);original=s.functional.select
            def checked(rows,pairs):
                self.assertTrue((root/s.FREEZE).exists())
                for source in s.SOURCES:self.assertTrue((root/s.cert_ref(source)).exists())
                return original(rows,pairs)
            with patch.object(s.functional,'select',checked):self.assertIsNone(s.reapply_root(root)['selected_source'])
    def test_10_missing_certificate_rejects_before_functional(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.copy_sources(root);s.freeze_certificates(root);(root/s.cert_ref(s.SOURCES[-1])).unlink()
            with patch.object(s.functional,'select',side_effect=AssertionError('Must not run')):
                with self.assertRaises(FileNotFoundError):s.reapply_root(root)
    def test_11_modified_certificate_hash_fails_before_functional(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.copy_sources(root);s.freeze_certificates(root);p=root/s.cert_ref(s.SOURCES[0]);p.write_bytes(p.read_bytes()+b' ')
            with patch.object(s.functional,'select',side_effect=AssertionError('Must not run')):
                with self.assertRaisesRegex(ValueError,'FROZEN_CERTIFICATE_HASH_DRIFT'):s.reapply_root(root)
    def test_12_resealed_invented_nonredundancy_fails_semantic_derivation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.copy_sources(root);s.freeze_certificates(root);ref=s.cert_ref(s.SOURCES[0]);c=g.read(root,ref);c['formalization_status']='STRUCTURAL_NONREDUNDANCY_CERTIFIED';(root/ref).write_bytes(s.canonical(c));m=g.read(root,s.FREEZE);m['certificates'][0]['sha256']=s.sha(s.canonical(c));(root/s.FREEZE).write_bytes(s.canonical(m))
            with self.assertRaisesRegex(ValueError,'SEMANTIC_DERIVATION_DRIFT'):s.reapply_root(root)
    def test_13_shared_baseline_all_components_unresolved(self):
        self.assertEqual(self.base['formalization_status'],'FORMALIZATION_UNRESOLVED');self.assertIsNone(self.base['EXACT_MATHEMATICAL_MAP']);self.assertEqual(len(self.base['component_formalization']),6)
        for x in self.base['component_formalization'].values():self.assertIsNone(x['map']);self.assertEqual(x['status'],'FORMALIZATION_UNRESOLVED');self.assertTrue(x['reason'])
    def test_14_no_raw_path_added_to_baseline(self):
        self.assertIsNone(self.base['INPUT_VARIABLES']['baseline_inclusion_projection']);self.assertFalse(self.base['new_design_choice_added']);self.assertIsNone(self.base['CLOCK_CONTROLS']);self.assertEqual(self.base['market_rows_used'],0)
    def test_15_exact_fourteen_fields_eleven_certificates(self):
        for source in s.SOURCES:self.assertEqual(set(g.read(ROOT,s.cert_ref(source))),s.CERT_FIELDS)
    def test_16_all_candidate_definition_hashes_unchanged(self):
        for c in self.docs[s.PROPOSALS]['candidates'][1:]:self.assertEqual(g.read(ROOT,s.cert_ref(c['information_source']))['candidate_definition_sha256'],s.sha(s.canonical(c)))
    def test_17_no_invented_feature_or_witness(self):
        for source in s.SOURCES:
            c=g.read(ROOT,s.cert_ref(source));self.assertIsNone(c['exact_feature_map_Phi_i']);self.assertIsNone(c['constructive_nonredundancy_witness_or_redundancy_proof']['witness']);self.assertIsNone(c['constructive_nonredundancy_witness_or_redundancy_proof']['proof']);self.assertEqual(c['sigma_containment_verdict'],'UNRESOLVED_BASELINE_AND_FEATURE_MAPS_NOT_UNIQUELY_DETERMINED')
    def test_18_four_formalization_unresolved(self):
        actual=[source for source in s.SOURCES if g.read(ROOT,s.cert_ref(source))['formalization_status']=='FORMALIZATION_UNRESOLVED'];self.assertEqual(actual,['MULTISCALE_PRICE_STATE','VOLATILITY_AND_REALIZED_VARIANCE_STATE','BROKER_NATIVE_ACTIVITY_STATE','REGIME_AND_STRUCTURAL_BREAK_STATE'])
    def test_19_seven_authentic_modality_uncertified(self):
        actual=[source for source in s.SOURCES if g.read(ROOT,s.cert_ref(source))['formalization_status']=='REQUIRED_AUTHENTIC_MODALITY_OR_LINKAGE_UNCERTIFIED'];self.assertEqual(set(actual),set(s.MODALITY));self.assertEqual(len(actual),7)
    def test_20_neutral_flags_not_promoted_to_available(self):
        for source,(modality,flag) in s.MODALITY.items():self.assertFalse(self.docs[s.INPUT]['modalities'][modality][flag]);self.assertFalse(g.read(ROOT,s.cert_ref(source))['availability_timestamp_map']['additional_modality_already_certified'])
    def test_21_functional_json_and_code_byte_exact(self):
        self.assertEqual(s.sha((ROOT/s.FUNCTIONAL).read_bytes()),'561e054658a4878008db10dbd6610408246756f5cabf7336a0c0b5088f4e1d2d')
        p='research_core_v4/strict_selection_functional_v1.py';self.assertEqual((ROOT/p).read_bytes(),subprocess.check_output(['git','show',g.BASE+':'+p],cwd=ROOT))
    def test_22_reapplication_thirteen_dimensions_and_all12(self):
        self.assertEqual((self.result['candidate_count'],self.result['semantic_certificate_count'],self.result['admissible_count'],self.result['exact_semantic_fail_count'],self.result['unknown_admissibility_count']),(12,11,0,1,11))
        for row in self.result['assessments']:self.assertEqual(set(row['dimensions']),set(s.functional.DIMENSIONS))
    def test_23_unknown_candidates_stay_competitors_no_selection(self):
        self.assertFalse(self.result['unknown_candidates_discarded']);self.assertIsNone(self.result['selected_source']);self.assertIsNone(self.result['selected_mechanism']);self.assertFalse(self.result['complete_information_design'])
    def test_24_accepted_univariate_redundancy_not_rescued(self):
        row=self.result['assessments'][0];self.assertEqual(row['information_source'],'UNIVARIATE_PRICE_STATE');self.assertEqual(row['hard_gates']['identifiable_incremental_claim'],'FAIL');self.assertFalse((ROOT/s.cert_ref('UNIVARIATE_PRICE_STATE')).exists())
    def test_25_next_gate_is_shared_map_not_more_history(self):
        p=g.read(ROOT,s.NEXT_PLAN);self.assertEqual(p['EXACT_REMAINING_CANDIDATES'],list(s.SOURCES));self.assertIn('shared B_t',p['EXACT_NEXT_BLOCKING_GATE']);self.assertEqual(len(p['EXACT_MISSING_STRUCTURAL_QUANTITY']['unresolved_components']),6)
    def test_26_next_plan_one_shared_record_zero_rows_no_execution(self):
        p=g.read(ROOT,s.NEXT_PLAN);q=p['MINIMUM_INFORMATION_NEEDED'];self.assertEqual(q['shared_prospective_specification_records'],1);self.assertEqual(q['authentic_market_rows'],0);self.assertIsNone(q['historical_window']);self.assertEqual(q['new_candidate_formulas_requested_at_this_stage'],0)
        for k in ['execution_in_this_task','new_design_choices_made','WHETHER_MARKET_ROWS_WOULD_BE_REQUIRED','WHETHER_BROKER_CONTACT_WOULD_BE_REQUIRED','WHETHER_REDECRYPTION_WOULD_BE_REQUIRED','duration_selected']:self.assertFalse(p[k])
    def test_27_independent_roundtrip_no_network_or_process(self):
        with patch('socket.socket',side_effect=AssertionError('Offline')),patch('urllib.request.urlopen',side_effect=AssertionError('Offline')),patch('subprocess.Popen',side_effect=AssertionError('No process')):
            base,certs=s.derive_certificates(ROOT);r=s.reapply_root(ROOT)
        self.assertEqual(s.canonical(base),(ROOT/s.BASELINE).read_bytes())
        for p,c in certs.items():self.assertEqual(s.canonical(c),(ROOT/p).read_bytes())
        self.assertEqual(s.canonical(r),(ROOT/s.REAPPLIED).read_bytes())
    def test_28_accepted_artifacts_and_prior_guards_immutable(self):
        for x in g.read(ROOT,g.AUTH)['immutable_bindings']:self.assertEqual((ROOT/x['ref']).read_bytes(),subprocess.check_output(['git','show',g.BASE+':'+x['ref']],cwd=ROOT))
    def test_29_historical_state_snapshot_exact(self):
        for p,d in zip(g.STATES,self.states):
            before=json.loads(subprocess.check_output(['git','show',g.BASE+':'+p],cwd=ROOT));hist=d['historical_current_state_before_semantic_certification_v1']
            for k,v in before.items():self.assertEqual(hist[k] if k in hist else d[k],v)
    def test_30_current_state_guard_six_pointer_regressions(self):
        g.validate_root(ROOT)
        for i,k in [(0,'current_next_action_type'),(0,'next_action'),(0,'stop_boundary'),(1,'next_action'),(2,'next_action'),(2,'current_operation')]:
            d=copy.deepcopy(self.states);d[i][k]='OLD'
            with self.assertRaisesRegex(ValueError,'ACTION_DRIFT'):g.validate(d,self.h)
    def test_31_nested_authority_and_hash_regressions(self):
        for i in range(3):
            for nested in [False,True]:
                for k,code in [('current_authority','AUTHORITY_DRIFT'),('current_authority_sha256','AUTHORITY_HASH_DRIFT')]:
                    d=copy.deepcopy(self.states);q=d[i]['strict_v2_semantic_certification'] if nested else d[i];q[k]='WRONG'
                    with self.assertRaisesRegex(ValueError,code):g.validate(d,self.h)
    def test_32_next_execution_and_closed_boundary_regressions(self):
        d=copy.deepcopy(self.states);d[0]['strict_v2_semantic_certification']['next_plan_executed']=True
        with self.assertRaisesRegex(ValueError,'BOUNDARY_DRIFT'):g.validate(d,self.h)
        for k in ['confirmation_opened','protected_forward_opened']:
            d=copy.deepcopy(self.states);d[1][k]=True
            with self.assertRaisesRegex(ValueError,'CLOSED_BOUNDARY_DRIFT'):g.validate(d,self.h)
    def test_33_budget_route_and_zero_execution(self):
        a=g.read(ROOT,g.AUTH);self.assertEqual(a['search_budget'],g.BUDGET);self.assertFalse(any(a['boundary'].values()));self.assertEqual(a['preservation']['plan'],'BREADTH_FIRST_THEN_DEPTH_SECOND');self.assertEqual(a['preservation']['eligible_roster_count'],1575);self.assertFalse(a['preservation']['support_limited_identity']['global_null']);self.assertEqual(a['downstream_order'][-2:],['DEMO','LIVE_ONLY_AFTER_EXPLICIT_USER_APPROVAL'])
    def test_34_workflow_read_only_no_secret_no_dispatch(self):
        t=(ROOT/'.github/workflows/strict-semantic-certification-offline.yml').read_text();self.assertIn('contents: read',t)
        for x in ['secrets.','contents: write','workflow'+'_dispatch','ctrader','download_asset','run_authorized']:self.assertNotIn(x,t.lower())
    def test_35_exact_change_allowlist(self):
        expected={*g.STATES,g.AUTH,s.BASELINE,s.FREEZE,s.REAPPLIED,s.NEXT_PLAN,*[s.cert_ref(x) for x in s.SOURCES],'research_core_v4/strict_semantic_certification_v1.py','research_core_v4/master1576_current_state_guard_v5.py','research_core_v4/strict_semantic_certification_preflight_v1.py','tests/test_strict_semantic_certification_v1.py','.github/workflows/strict-semantic-certification-offline.yml'}
        changed=set(subprocess.check_output(['git','diff','--name-only',g.BASE,'HEAD'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines());self.assertEqual(changed,expected)
