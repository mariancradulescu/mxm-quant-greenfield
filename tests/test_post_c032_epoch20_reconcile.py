import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from research_v3.post_c032_epoch20_reconcile import reconcile, REFS, EPOCH_REL, NEXT_REL, RECOVERY_REL
from research_v3.runtime_v2_primitives import atomic_write_json, load_json

ACCOUNTING={"economic_outcomes_opened":28,"v2_attempts_used":20,"v2_search_budget_remaining":64}

class PostC032ReconciliationTests(unittest.TestCase):
    def test_binds_existing_evidence_once_without_changing_accounting(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            atomic_write_json(root/EPOCH_REL,{"schema":"mxm.greenfield.research-evidence-epoch.v1",
                "current_epoch":20,"authoritative_evidence_refs":[],"history":[]})
            atomic_write_json(root/NEXT_REL,{"status":"C032_RESULT_RECORDED_PENDING_EXACT_HEAD_GREEN",
                "accounting":ACCOUNTING,"current_research_evidence_epoch":20})
            atomic_write_json(root/RECOVERY_REL,{"status":"PROVIDER_AVAILABLE_AFTER_ENTITLEMENT_PROBE"})
            for rel in REFS:
                atomic_write_json(root/rel,{})
            atomic_write_json(root/REFS[0],{"evidence_epoch_seen":20,
                "provider":{"kind":"EXTERNAL_CHATGPT_GENERAL_REASONING"}})
            atomic_write_json(root/REFS[3],{"source_zip_sha256":
                "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503",
                "series":{str(i):{} for i in range(40)},
                "economic_effect":{"outcomes_opened":0,"attempts_consumed":0,"budget_change":0}})
            with patch("research_v3.post_c032_epoch20_reconcile.validate_repository_state",
                       return_value={"accounting":ACCOUNTING}):
                first=reconcile(root)
                second=reconcile(root)
            self.assertEqual(first["evidence_epoch"],21)
            self.assertEqual(second["status"],"ALREADY_RECONCILED")
            state=load_json(root/NEXT_REL,{})
            self.assertEqual(state["status"],"FRESH_GENERAL_AI_REASONING_REQUIRED")
            self.assertEqual(state["accounting"],ACCOUNTING)
            self.assertEqual(len(load_json(root/EPOCH_REL,{})["history"]),1)

    def test_refuses_unproven_entitlement(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            atomic_write_json(root/EPOCH_REL,{"current_epoch":20})
            atomic_write_json(root/RECOVERY_REL,{"status":"PROVIDER_UNAVAILABLE"})
            with self.assertRaisesRegex(RuntimeError,"not proven"):
                reconcile(root)
