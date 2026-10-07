"""Regression injections prove canonical drift fails closed, not merely equality."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from research_core_v4 import master1576_current_state_guard_v1 as g
ROOT=Path(__file__).resolve().parents[1]
BASE='b0ef47f444acca931e6b0da599be7d3b05314e25'
class CurrentStateGuardTests(unittest.TestCase):
    def setUp(self):self.states=[json.loads((ROOT/p).read_bytes()) for p in g.STATES]
    def denied(self,code,states):
        with self.assertRaisesRegex(ValueError,code):g.validate(states)
    def test_01_repaired_current_state(self):g.validate_root(ROOT)
    def test_02_original_stale_status_regression(self):
        d=copy.deepcopy(self.states);d[0]['status']='SHALLOW_M5_V2_V4_PREARM_INDEPENDENTLY_ACCEPTED_PENDING_SEPARATE_REAL_ARM_AUTHORIZATION';self.denied('V4_TOP_STATUS_DRIFT',d)
    def test_03_each_of_six_action_pointers_fails_closed(self):
        for i,key in [(0,'current_next_action_type'),(0,'next_action'),(0,'stop_boundary'),(1,'next_action'),(2,'next_action'),(2,'current_operation')]:
            with self.subTest(state=i,field=key):
                d=copy.deepcopy(self.states);d[i][key]='OTHER';self.denied('CURRENT_ACTION_DRIFT',d)
    def test_04_current_authority_and_hash_everywhere(self):
        for i in range(3):
            for key,value,code in [('current_authority','wrong.json','CURRENT_AUTHORITY_DRIFT'),('current_authority_sha256','0'*64,'CURRENT_AUTHORITY_HASH_DRIFT')]:
                with self.subTest(state=i,field=key):
                    d=copy.deepcopy(self.states);d[i][key]=value;self.denied(code,d)
    def test_05_nested_current_authority_cannot_be_stale(self):
        d=copy.deepcopy(self.states);d[1]['shallow_m5_v2_operational_rebind']['current_authority']='prearm.json';self.denied('CURRENT_AUTHORITY_DRIFT',d)
    def test_06_new_unrecognized_current_field_arm_pending_rejected(self):
        for i in range(3):
            d=copy.deepcopy(self.states);d[i]['current_execution_instruction']='PENDING_SEPARATE_REAL_SHALLOW_M5_ARM_AUTHORIZATION';self.denied('SUPERSEDED_SHALLOW_ARM_STATE',d)
    def test_07_explicit_historical_namespace_preserved(self):
        d=copy.deepcopy(self.states);d[0]['historical_test_record']={'next_action':'PENDING_SEPARATE_REAL_SHALLOW_M5_ARM_AUTHORIZATION','current_authority':'old.json'};g.validate(d)
    def test_08_diagnostic_statuses_are_explicit_records(self):
        for i in [1,2]:
            d=copy.deepcopy(self.states);d[i]['canonical_status_semantics']['status']='CURRENT_OPERATION';self.denied('DIAGNOSTIC_STATUS_SEMANTICS_DRIFT',d)
    def test_09_original_record_fields_budget_and_history_unchanged(self):
        permitted={'current_operational_status','canonical_status_semantics','canonical_current_state_repair_ref','canonical_current_state_repair_sha256'}
        for path,d in zip(g.STATES,self.states):
            before=json.loads(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT))
            changed={k for k in set(before)|set(d) if before.get(k)!=d.get(k)}
            self.assertEqual(changed,permitted|({'status'} if path==g.STATES[0] else set()))
            for key in before:
                if key not in permitted and not(path==g.STATES[0] and key=='status'):self.assertEqual(before[key],d[key])
    def test_10_all_five_accepted_artifacts_byte_identical(self):
        from research_core_v4 import master1576_post_screen_v1 as p
        for path in [p.ACCEPT,p.SUMMARY,p.ROSTER,p.DESIGN,p.POWER,p.RESULT,p.DISCOVERY,p.SELECTION,p.PRIMARY,p.PARK,p.PROTO]:
            self.assertEqual((ROOT/path).read_bytes(),subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT))
