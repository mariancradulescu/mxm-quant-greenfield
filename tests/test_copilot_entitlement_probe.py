import tempfile
import unittest
from pathlib import Path
from research_v3.copilot_entitlement_probe import prepare, execute, PROBE_REL, RECOVERY_REL
from research_v3.runtime_v2_primitives import atomic_write_json, load_json

class CopilotEntitlementProbeTests(unittest.TestCase):
    def test_success_clears_old_latch_once(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            atomic_write_json(root/RECOVERY_REL,{"status":"PROVIDER_RETRY_REQUIRED",
                "detail":"You have exceeded your monthly quota",
                "consecutive_recoverable_failures":8})
            prepared=prepare(root,"run-1")
            self.assertEqual(prepared["action"],"PREPARED_MUST_PERSIST_BEFORE_EXECUTE")
            self.assertEqual(prepare(root,"run-1")["action"],"SKIP_ALREADY_PREPARED")
            doc=load_json(root/PROBE_REL,{})
            doc["status"]="CLAIMED_CALL_CONSUMED"
            atomic_write_json(root/PROBE_REL,doc)
            calls=[]
            def transport():
                calls.append(1)
                return 0,"MXM_COPILOT_PROBE_OK",""
            out=execute(root,"run-1","test-token",transport)
            self.assertEqual(out["status"],"AVAILABLE")
            self.assertEqual(execute(root,"run-1","test-token",transport)["action"],
                             "SKIP_PROBE_NOT_CLAIMED_OR_ALREADY_FINISHED")
            self.assertEqual(len(calls),1)
            self.assertEqual(load_json(root/RECOVERY_REL,{})["consecutive_recoverable_failures"],0)

    def test_quota_failure_stays_latched_without_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            prepare(root,"run-2")
            doc=load_json(root/PROBE_REL,{})
            doc["status"]="CLAIMED_CALL_CONSUMED"
            atomic_write_json(root/PROBE_REL,doc)
            calls=[]
            def transport():
                calls.append(1)
                return 1,"","You have exceeded your monthly quota"
            out=execute(root,"run-2","test-token",transport)
            self.assertEqual(out["status"],"PROVIDER_UNAVAILABLE")
            execute(root,"run-2","test-token",transport)
            self.assertEqual(len(calls),1)
            self.assertEqual(load_json(root/RECOVERY_REL,{})["retry_policy"],"NO_AUTOMATIC_RETRY")
