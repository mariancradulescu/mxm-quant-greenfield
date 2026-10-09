"""Success and negative branches of actual V2 authority/store callsites."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from research_core_v4.numeric_development_v2 import machine_v2 as m
from research_core_v4.numeric_development_v3 import authority_v3 as a
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.numeric_development_v1.public_output_guard_v1 import PublicDisclosureDenied

class Successor(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{"GITHUB_RUN_ID":"123","GITHUB_SHA":"a"*40});self.env.start()
        self.arm=a.candidate("a"*40,{});self.arm["mode"]="synthetic"
        self.approval={"schema":"mxm.numeric.independent.acceptance.v3","status":"INDEPENDENT_ACCEPTANCE_PASS",
          "mode":"synthetic","role":"FABRICATED_TEST_AUTHORITY","arm_sha256":a.sha(a.enc(self.arm)),
          "source_head":"a"*40,"arm_commit":"b"*40,"audit_receipt_sha256":"c"*64,"explicit_acceptance":True}
    def tearDown(self):self.env.stop()
    def validate(self):
        with patch.object(a,"verify_bindings"):
            return a.validate(self.arm,self.approval,"c"*40,"synthetic",a.enc(self.arm),artifacts=False)
    def store(self):return m.Store("a"*40,None,None,None,self.arm,a.sha(a.enc(self.approval)),"d"*64)
    def test_valid_non_self_referential_arm(self):
        self.assertEqual(self.validate()["source_head"],"a"*40)
        self.assertNotIn("exact_head",self.arm)
    def test_actual_git_parent_arm_approval_chain_success_and_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            def git(*args):return subprocess.check_output(["git",*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
            git("init","-q");git("config","user.name","Fabricated Test");git("config","user.email","test@example.invalid")
            paths=[old.WORKER_PATH,old.GUARD_PATH]+[f"fixture/source{i}.py" for i in range(15)]
            bindings={}
            for path in paths:
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b"FABRICATED SOURCE\n")
                bindings[path]=a.sha(p.read_bytes())
            p=root/a.BINDINGS;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(a.enc({"bindings":bindings}))
            git("add",".");git("commit","-qm","fabricated immutable source");source=git("rev-parse","HEAD")
            arm=a.candidate(source,bindings);arm["mode"]="synthetic"
            (root/a.ARM).write_bytes(a.enc(arm));git("add",a.ARM);git("commit","-qm","fabricated candidate arm")
            armcommit=git("rev-parse","HEAD")
            approval={**self.approval,"arm_sha256":a.sha(a.enc(arm)),"source_head":source,"arm_commit":armcommit}
            (root/a.APPROVAL).write_bytes(a.enc(approval));git("add",a.APPROVAL);git("commit","-qm","fabricated independent approval only")
            head=git("rev-parse","HEAD")
            with patch.object(a,"ROOT",root):
                self.assertEqual(a.validate(arm,approval,head,"synthetic",a.enc(arm)),arm)
                (root/old.WORKER_PATH).write_bytes(b"SOURCE DRIFT\n")
                with self.assertRaisesRegex(n.NumericalStop,"BOUND_SOURCE_DRIFT"):
                    a.validate(arm,approval,head,"synthetic",a.enc(arm))
    def test_wrong_arm_hash(self):
        self.approval["arm_sha256"]="0"*64
        with self.assertRaisesRegex(n.NumericalStop,"APPROVAL_BINDING"):self.validate()
    def test_absent_explicit_independent_acceptance(self):
        self.approval["explicit_acceptance"]=False
        with self.assertRaisesRegex(n.NumericalStop,"INDEPENDENT_APPROVAL_REQUIRED"):self.validate()
    def test_fabricated_approval_cannot_authorize_real(self):
        with patch.object(a,"verify_bindings"),self.assertRaises(n.NumericalStop):
            a.validate(self.arm,self.approval,"c"*40,"real",a.enc(self.arm),artifacts=False)
    def test_stale_arm(self):
        self.arm["expires_UTC"]="2026-01-01T00:00:00Z"
        with self.assertRaisesRegex(n.NumericalStop,"STALE_ARM"):self.validate()
    def test_wider_scope_rejected(self):
        self.arm["scope"]={**a.SCOPE,"new_alpha":True}
        with self.assertRaisesRegex(n.NumericalStop,"ARM_SCOPE"):self.validate()
    def test_source_hash_drift(self):
        bindings={old.WORKER_PATH:"a"*64,old.GUARD_PATH:"b"*64,**{f"test{i}.py":"d"*64 for i in range(15)}}
        with patch.object(a,"ancestor"),patch.object(a,"read",return_value={"bindings":bindings}),\
             patch.object(a,"digest",return_value="c"*64),self.assertRaisesRegex(n.NumericalStop,"BOUND_SOURCE_DRIFT"):
            a.verify_bindings("a"*40,"b"*40,bindings)
    def test_approval_isolated_from_source_commit(self):
        with patch.object(a,"verify_bindings"),patch.object(a,"ancestor"),\
             patch.object(a,"git",side_effect=[a.enc(self.arm),b"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"]),\
             self.assertRaisesRegex(n.NumericalStop,"APPROVAL_SEPARATION"):
            a.validate(self.arm,self.approval,"c"*40,"synthetic",a.enc(self.arm),artifacts=True)
    def test_actual_new_claim_consumed_before_release(self):
        with patch.object(m,"runtime"),patch.object(m,"existing_ref",return_value=[{}]),\
             patch.object(old,"api") as api,self.assertRaisesRegex(n.NumericalStop,"CONSUMED_ARM"):
            self.store().claim()
        api.assert_not_called()
    def test_inventory_preflight_rejects_before_claim(self):
        master,entries,digits,manifest=old.verify_science()
        with patch.object(old,"api",return_value={"id":0,"body":"{}"}),\
             self.assertRaisesRegex(n.NumericalStop,"INPUT_RELEASE_DRIFT"):
            a.preflight_inventory(manifest,entries)
    def test_valid_inventory_preflight(self):
        master,entries,digits,manifest=old.verify_science()
        exp=a.read("research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_CAMPAIGN_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json")["exact_release_inventory"]
        with patch.object(old,"api",side_effect=[{"id":exp["release_id"],"body":json.dumps(exp["body"])},exp["assets"],[]]):
            self.assertEqual(len(a.preflight_inventory(manifest,entries)),100)
    def test_public_release_body_confidential_output_rejected_before_api(self):
        s=self.store();s.release={"id":1}
        with patch.object(old,"api") as api,self.assertRaises(PublicDisclosureDenied):
            s.body({**m.safe_status("a"*40,"FINAL","PASS"),"identity_results":[1]})
        api.assert_not_called()
    def test_public_git_confidential_output_rejected(self):
        s=self.store()
        with patch.object(old,"api",return_value={"object":{"sha":"a"*40}}) as api,\
             self.assertRaises(PublicDisclosureDenied):
            s.publish({**m.safe_status("a"*40,"FINAL","PASS"),"response":[1]},m.PROOF_STATUS)
        self.assertEqual(api.call_count,1)
    def test_public_final_write_failure(self):
        s=self.store()
        with patch.object(old,"api",side_effect=[{"object":{"sha":"a"*40}},n.NumericalStop("PUBLICATION_FAILURE")]),\
             self.assertRaisesRegex(n.NumericalStop,"PUBLICATION_FAILURE"):
            s.publish(m.safe_status("a"*40,"FINAL","PASS"),m.PROOF_STATUS)
    def test_encrypted_final_upload_failure(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td);s=self.store();s.tmp=tmp;s.release={"id":1}
            def enc(raw,public_key,output):output.write_bytes(b"fabricated ciphertext")
            with patch.object(old,"encrypt_shard",enc),patch.object(old.urllib.request,"urlopen",side_effect=OSError("fault")),\
                 self.assertRaisesRegex(n.NumericalStop,"ENCRYPTED_REMOTE_UPLOAD"):
                s.encrypted({"fabricated":True},"complete-development-result.mxmenc")
    def test_encrypted_readback_rejected(self):
        s=self.store();s.release={"id":1}
        with patch.object(old,"api",return_value=[]),self.assertRaisesRegex(n.NumericalStop,"CIPHERTEXT_REMOTE_METADATA_DRIFT"):
            s.restore({"id":1,"name":"prefix-050.mxmenc","size":5,"ciphertext_sha256":"a"*64})
    def test_wrong_recovery_authorization(self):
        with self.assertRaisesRegex(n.NumericalStop,"RECOVERY_FIELDS"):
            a.recovery_gate({},self.arm,"c"*64,123,{})
    def test_wrong_processed_source_rejected(self):
        master,entries,digits,manifest=old.verify_science()
        prefix={"processed_sources":[{"ordinal":999,"ciphertext_sha256":"a"*64}],"expected_rows":0}
        with self.assertRaisesRegex(n.NumericalStop,"RECOVERY_COMPLETED_SOURCE_DRIFT"):
            m.verify_processed(prefix,"synthetic",master,digits,entries)
    def test_fail_closed_main_nonzero(self):
        env={**os.environ,"GITHUB_REPOSITORY":"DENIED"}
        p=subprocess.run([sys.executable,"-m","research_core_v4.numeric_development_v3.machine_v3","--mode","real"],
                         env=env,capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertIn("EVENT_OR_RETRY_DENIED",p.stdout)
    def test_missing_real_arm_before_archive_opening(self):
        with patch.object(a,"ARM","nonexistent-arm.json"),patch.object(old,"download") as download,\
             self.assertRaisesRegex(n.NumericalStop,"MISSING_INDEPENDENT_APPROVAL"):
            a.real_gate("a"*40)
        download.assert_not_called()
    def test_exact_real_workflow_event(self):
        with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"push","GITHUB_WORKFLOW_REF":old.REPO+"/"+a.REAL_WORKFLOW+"@refs/heads/"+old.BRANCH}):
            a.real_event_gate()
        with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"push","GITHUB_WORKFLOW_REF":"wrong"}),\
             self.assertRaisesRegex(n.NumericalStop,"REAL_WORKFLOW_EVENT_BINDING"):
            a.real_event_gate()
    def test_recovery_original_actions_run_must_be_stopped(self):
        arm={**self.arm,"mode":"real"}
        name="mxm-numeric-v2-claim-real-"+arm["invocation_id"]
        refs=[{"ref":"refs/tags/"+name,"object":{"sha":"a"*40}}]
        run={"id":123,"head_sha":"a"*40,"run_attempt":1,"path":a.REAL_WORKFLOW,"status":"completed","conclusion":"failure"}
        with patch.object(old,"api",side_effect=[refs,run]):a.stopped_original_preflight(arm,123)
        with patch.object(old,"api",side_effect=[refs,{**run,"status":"in_progress","conclusion":None}]),\
             self.assertRaisesRegex(n.NumericalStop,"ORIGINAL_RUN_MUST_BE_STOPPED_AND_FAILED"):
            a.stopped_original_preflight(arm,123)
    def test_recovery_original_wrong_workflow_or_source_rejected(self):
        arm={**self.arm,"mode":"real"};name="mxm-numeric-v2-claim-real-"+arm["invocation_id"]
        refs=[{"ref":"refs/tags/"+name,"object":{"sha":"a"*40}}]
        run={"id":123,"head_sha":"b"*40,"run_attempt":1,"path":"wrong","status":"completed","conclusion":"failure"}
        with patch.object(old,"api",side_effect=[refs,run]),self.assertRaises(n.NumericalStop):
            a.stopped_original_preflight(arm,123)

if __name__=="__main__":unittest.main(verbosity=2)
