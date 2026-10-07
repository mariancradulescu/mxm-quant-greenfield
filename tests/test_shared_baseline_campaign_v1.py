import ast
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from research_core_v4 import shared_baseline_campaign_v1 as b
from research_core_v4 import master1576_current_state_guard_v6 as g
from research_core_v4.shared_baseline_campaign_preflight_v1 import freeze_stage
ROOT=Path(__file__).resolve().parents[1]
FUNCTIONAL=b.S+'STRICT_PREOUTCOME_V2_PROSPECTIVE_SELECTION_FUNCTIONAL_V1.json'
NEW=[b.PROTOCOL,b.SPEC,b.AUTH,'research_core_v4/shared_baseline_campaign_v1.py',g.GUARD,'research_core_v4/shared_baseline_campaign_preflight_v1.py','tests/test_shared_baseline_campaign_v1.py','.github/workflows/shared-baseline-campaign-offline.yml']
class CampaignTests(unittest.TestCase):
    def states(self):return [g.read(ROOT,p) for p in g.STATES]
    def result(self):return b.build_root(ROOT,[])
    def test_exact_two_input_reads(self):
        seen=[];b.build_root(ROOT,seen);self.assertEqual(seen,[b.CERT,b.INPUT])
    def test_candidate_file_denied(self):
        with b.read_compartment(ROOT,[]):
            with self.assertRaises(ValueError):open(ROOT/(b.S+'STRICT_PREOUTCOME_RESELECTION_V2_RESULT_V1.json'))
    def test_closure_file_denied(self):
        with b.read_compartment(ROOT,[]):
            with self.assertRaises(ValueError):io.open(ROOT/(b.S+'POST_QUOTE_V4_CLOSURE_LEDGER_V2.json'))
    def test_os_open_history_denied(self):
        with b.read_compartment(ROOT,[]):
            with self.assertRaises(ValueError):os.open(ROOT/(b.S+'NEXT_INFORMATION_SOURCE_SELECTION_V6.json'),os.O_RDONLY)
    def test_protocol_not_scientific_input(self):
        with b.read_compartment(ROOT,[]):
            with self.assertRaises(ValueError):open(ROOT/b.PROTOCOL)
    def test_write_denied(self):
        with b.read_compartment(ROOT,[]):
            with self.assertRaises(ValueError):open(ROOT/b.INPUT,'w')
    def test_outside_path_denied(self):
        with b.read_compartment(ROOT,[]):
            with self.assertRaises(ValueError):open('/etc/passwd')
    def test_candidate_fields_never_dereferenced(self):
        class Neutral(dict):
            def __getitem__(self,k):
                if k!='modalities':raise AssertionError('NONBASELINE_FIELD_VISIBLE')
                return super().__getitem__(k)
        n=Neutral(g.read(ROOT,b.INPUT));p=b.project(g.read(ROOT,b.CERT),n)
        self.assertEqual(b.derive(p),self.result())
    def test_ignored_fields_poison_invariant(self):
        n=g.read(ROOT,b.INPUT);c=g.read(ROOT,b.CERT);a=b.derive(b.project(c,n))
        for k in list(n):
            if k!='modalities':n[k]={'outcome':'POISON','candidate':'POISON','priority':-999}
        self.assertEqual(a,b.derive(b.project(c,n)))
    def test_no_research_module_import(self):
        tree=ast.parse((ROOT/'research_core_v4/shared_baseline_campaign_v1.py').read_text())
        for x in ast.walk(tree):
            if isinstance(x,ast.ImportFrom):self.assertNotIn('research_core',x.module or '')
            if isinstance(x,ast.Import):self.assertTrue(all(not y.name.startswith('research_core') for y in x.names))
    def test_protocol_byte_frozen(self):self.assertEqual((ROOT/b.PROTOCOL).read_bytes(),b.canonical(b.protocol()))
    def test_specification_repeatability(self):self.assertEqual((ROOT/b.SPEC).read_bytes(),b.canonical(self.result()))
    def test_hash_drift_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for p in b.ALLOWED:
                q=Path(d)/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes((ROOT/p).read_bytes())
            (Path(d)/b.INPUT).write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'INPUT_HASH_DRIFT'):b.build_root(d,[])
    def test_freeze_order(self):
        with tempfile.TemporaryDirectory() as d:
            for p in b.ALLOWED:
                q=Path(d)/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes((ROOT/p).read_bytes())
            original=b.build_root
            def wrapped(root,seen):
                self.assertTrue((Path(root)/b.PROTOCOL).exists());self.assertFalse((Path(root)/b.SPEC).exists())
                return original(root,seen)
            with patch.object(b,'build_root',side_effect=wrapped):trace,reads=freeze_stage(d)
            self.assertEqual(trace,['PROTOCOL_FROZEN','TWO_INPUT_COMPARTMENT_OPENED','NONUNIQUENESS_PROVED','OUTPUT_FROZEN'])
            with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_PRESENT'):freeze_stage(d)
    def test_witness_same_coarse(self):
        p=self.result()['proof'];self.assertEqual(b.total_projection(p['left_counts']),b.total_projection(p['right_counts']))
    def test_witness_different_fine(self):
        p=self.result()['proof'];self.assertNotEqual(b.vector_projection(p['left_counts']),b.vector_projection(p['right_counts']))
    def test_coarse_is_function_of_fine(self):
        for v in [[0]*12,[1]*12,list(range(12))]:
            last,vector=b.vector_projection(v);self.assertEqual((last,sum(vector)),b.total_projection(v))
    def test_zero_degenerate_valid(self):self.assertEqual(b.total_projection([0]*12),(0,0))
    def test_missing_not_imputed(self):
        with self.assertRaisesRegex(ValueError,'COUNT_DOMAIN'):b.total_projection([None]*12)
    def test_negative_invalid(self):
        with self.assertRaises(ValueError):b.total_projection([-1]*12)
    def test_no_map_assigned(self):
        r=self.result();self.assertIsNone(r['exact_baseline_map_B_t']);self.assertTrue(all(x['exact_map'] is None for x in r['components'].values()))
    def test_governance_not_empirical_boundary(self):
        r=self.result();self.assertFalse(r['empirical_or_external_blocker_reached']);self.assertEqual(r['boundary_kind'],'NONDEFENSIBLE_FREE_DESIGN_CHOICE_STAGE_1_STOP')
    def test_downstream_not_executed(self):
        r=self.result();self.assertFalse(r['stage_2_executed']);self.assertFalse(r['stage_3_executed']);self.assertFalse(r['complete_design_selected'])
    def test_functional_preserved(self):self.assertEqual(g.sha(ROOT,FUNCTIONAL),'561e054658a4878008db10dbd6610408246756f5cabf7336a0c0b5088f4e1d2d')
    def test_all_immutable_bindings(self):
        for x in g.read(ROOT,b.AUTH)['immutable_bindings']:self.assertEqual(g.sha(ROOT,x['ref']),x['sha256'],x['ref'])
    def test_guard_valid(self):self.assertEqual(g.validate_root(ROOT)['next_action'],b.NEXT)
    def test_action_drift_fails(self):
        for index,key in [(0,'current_next_action_type'),(0,'next_action'),(0,'stop_boundary'),(1,'next_action'),(2,'next_action'),(2,'current_operation')]:
            states=self.states();states[index][key]='DRIFT'
            with self.assertRaises(ValueError):g.validate(states,g.sha(ROOT,b.AUTH))
    def test_authority_hash_drift_fails(self):
        for i in range(3):
            states=self.states();states[i]['current_authority_sha256']='0'*64
            with self.assertRaises(ValueError):g.validate(states,g.sha(ROOT,b.AUTH))
    def test_stale_arm_fails(self):
        states=self.states();states[0]['current_unexpected']='SHALLOW_M5_PREARM_PENDING'
        with self.assertRaisesRegex(ValueError,'STALE_ARM'):g.validate(states,g.sha(ROOT,b.AUTH))
    def test_budget_and_economic_count_preserved(self):
        states=self.states();self.assertEqual(states[1]['search_budget'],g.BUDGET);self.assertEqual(states[2]['search_budget_after'],g.BUDGET)
        states[1]['search_budget']['economic_outcomes_opened']=30
        with self.assertRaises(ValueError):g.validate(states,g.sha(ROOT,b.AUTH))
    def test_protected_and_confirmation_closed(self):
        for key in ['protected_forward_opened','confirmation_opened']:
            for d in self.states():
                if key in d:self.assertFalse(d[key])
    def test_old_canonical_values_archived_exactly(self):
        for p in g.STATES:
            old=json.loads(subprocess.check_output(['git','show',b.BASE+':'+p],cwd=ROOT));new=g.read(ROOT,p)
            history=new['historical_current_state_before_shared_baseline_campaign_v1']
            for k,v in history.items():self.assertEqual(v,old[k],(p,k))
            self.assertEqual(new['historical_strict_v2_semantic_certification'],old['strict_v2_semantic_certification'])
            for k,v in old.items():
                if k not in history and k!='strict_v2_semantic_certification':self.assertEqual(new[k],v,(p,k))
    def test_change_allowlist(self):
        changed=subprocess.check_output(['git','diff',b.BASE,'--name-only'],cwd=ROOT,text=True).splitlines()
        untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
        self.assertEqual(set(changed+untracked),set(NEW+g.STATES))
    def test_workflow_no_market_secret_or_dispatch(self):
        text=(ROOT/'.github/workflows/shared-baseline-campaign-offline.yml').read_text()
        for forbidden in ['secrets.','CTRADER','workflow_dispatch','curl ','gh release','download-artifact']:self.assertNotIn(forbidden,text)
        self.assertIn('contents: read',text);self.assertIn('ref: ${{ github.sha }}',text)
    def test_no_rows_power_duration_or_outcomes(self):
        r=self.result();self.assertEqual(r['market_rows_used'],0);self.assertEqual(r['power_trials'],0);self.assertFalse(r['duration_selected']);self.assertFalse(r['response_opened'])
        self.assertFalse(any(g.read(ROOT,b.AUTH)['boundary'].values()))
if __name__=='__main__':unittest.main()
