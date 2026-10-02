from __future__ import annotations
import copy,json,tempfile,unittest
from pathlib import Path
from research_core_v4.recovery_v3_prearm_gate import ARM_REL,ENCRYPTION_FORMAT,INPUT_PREFIX,validate_arm_document,validate_staging_certificate_document,parse_json_object_bytes

class RecoveryV3PreArmGateTests(unittest.TestCase):
    def setUp(self):
        self.series=[{"context":"FX_SPOT","symbol":"EURGBP","symbol_id":9,"row_count":74768,"series_sha256":"e"*64,"first_timestamp_utc":"2025-09-16T00:00:00Z","last_timestamp_utc":"2026-09-16T23:50:00Z","source_archive_sha256":"d"*64}]
        self.expected={"canonical_repository":"mariancradulescu/mxm-quant-greenfield","research_branch":"performance-research-v3-20260922","scientific_source_head":"68bdee4b51244ae50acd56fe868468b96106450f","frozen_hashes":{"design":"1"*64,"evaluator":"2"*64,"runner":"3"*64,"semantics":"4"*64},"recovery_v3_authority_sha256":"5"*64,"canonical_v4_state_sha256":"6"*64,"installed_runtime_workflow_sha256":"7"*64,"staging_certificate_sha256":"8"*64,"exact_18_series_manifest_sha256":"9"*64,"exact_18_series":self.series,"source_archives":{"original_sha256":"a"*64,"delta_sha256":"d"*64}}
        self.head="a"*40; self.parent="b"*40
        self.arm={"schema":"mxm.research-core-v4.recovery-v3-arm.v1","status":"ARMED_NOT_EXECUTED","arm_commit":self.head,"pre_arm_parent_head":self.parent,"canonical_repository":self.expected["canonical_repository"],"research_branch":self.expected["research_branch"],"scientific_source_head":self.expected["scientific_source_head"],"frozen_hashes":self.expected["frozen_hashes"],"recovery_v3_authority_sha256":self.expected["recovery_v3_authority_sha256"],"canonical_v4_state_sha256":self.expected["canonical_v4_state_sha256"],"installed_runtime_workflow_sha256":self.expected["installed_runtime_workflow_sha256"],"staging_certificate_sha256":self.expected["staging_certificate_sha256"],"exact_18_series_manifest_sha256":self.expected["exact_18_series_manifest_sha256"],"seed":20261002,"permutations":1023,"accepted_canonical_result_count":0,"no_prior_recovery_v3_attempt_lock":True,"no_canonical_result_present":True}
        self.parts=[{"filename":INPUT_PREFIX+"000","sha256":"c"*64,"size_bytes":123}]
        self.cert={"schema":"mxm.research-core-v4.recovery-v3-greenfield-input-staging-certificate.v1","status":"STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED","canonical_repository":self.expected["canonical_repository"],"research_branch":self.expected["research_branch"],"staging_commit":"c"*40,"scientific_source_head":self.expected["scientific_source_head"],"recovery_v3_authority_sha256":self.expected["recovery_v3_authority_sha256"],"installed_runtime_workflow_sha256":self.expected["installed_runtime_workflow_sha256"],"accepted_canonical_result_count":0,"arm_present_at_staging":False,"real_execution_authorized_at_staging":False,"encryption_format":ENCRYPTION_FORMAT,"source_archives":self.expected["source_archives"],"exact_18_series":self.series,"exact_18_series_manifest_sha256":self.expected["exact_18_series_manifest_sha256"],"encrypted_parts":self.parts,"encrypted_part_order":[self.parts[0]["filename"]],"encrypted_bundle_sha256":"f"*64}

    def _arm_fail(self,mutate=None,**kwargs):
        arm=copy.deepcopy(self.arm); exp=copy.deepcopy(self.expected)
        if mutate: mutate(arm,exp)
        args={"actual_head":self.head,"actual_parent":self.parent,"changed_paths":[ARM_REL],"result_present":False,"lock_present":False}; args.update(kwargs)
        with tempfile.TemporaryDirectory() as td:
            lock=Path(td)/"attempt.lock"
            with self.assertRaises(PermissionError): validate_arm_document(arm,exp,**args)
            self.assertFalse(lock.exists())

    def test_empty_and_malformed_arm_fail_before_lock(self):
        with self.assertRaises(PermissionError): parse_json_object_bytes(b"","ARM")
        with self.assertRaises(PermissionError): parse_json_object_bytes(b"{","ARM")
    def test_wrong_parent_head_fails(self): self._arm_fail(actual_parent="c"*40)
    def test_stale_arm_fails(self): self._arm_fail(lambda a,e:a.__setitem__("pre_arm_parent_head","0"*40))
    def test_unrelated_arm_commit_mutation_fails(self): self._arm_fail(changed_paths=[ARM_REL,"research_core_v4/response_evaluator_v3.py"])
    def test_wrong_authority_hash_fails(self): self._arm_fail(lambda a,e:a.__setitem__("recovery_v3_authority_sha256","0"*64))
    def test_wrong_state_hash_fails(self): self._arm_fail(lambda a,e:a.__setitem__("canonical_v4_state_sha256","0"*64))
    def test_wrong_workflow_hash_fails(self): self._arm_fail(lambda a,e:a.__setitem__("installed_runtime_workflow_sha256","0"*64))
    def test_wrong_certificate_hash_fails(self): self._arm_fail(lambda a,e:a.__setitem__("staging_certificate_sha256","0"*64))
    def test_wrong_exact_series_identity_fails(self): self._arm_fail(lambda a,e:a.__setitem__("exact_18_series_manifest_sha256","0"*64))
    def test_existing_result_fails(self): self._arm_fail(result_present=True)
    def test_existing_attempt_lock_fails(self): self._arm_fail(lock_present=True)
    def test_changed_frozen_science_fails(self): self._arm_fail(lambda a,e:e["frozen_hashes"].__setitem__("evaluator","f"*64))
    def test_wrong_seed_and_permutation_fail(self):
        self._arm_fail(lambda a,e:a.__setitem__("seed",1)); self._arm_fail(lambda a,e:a.__setitem__("permutations",127))

    def _cert_fail(self,mutate):
        cert=copy.deepcopy(self.cert); exp=copy.deepcopy(self.expected); parts=copy.deepcopy(self.parts); mutate(cert,exp,parts)
        with self.assertRaises(PermissionError): validate_staging_certificate_document(cert,exp,part_records=parts,reconstructed_bundle_sha256="f"*64)

    def test_staging_certificate_identity_fields_are_mechanical(self):
        cases=[
            lambda c,e,p:c.__setitem__("canonical_repository","x/y"),lambda c,e,p:c.__setitem__("research_branch","main"),
            lambda c,e,p:c.__setitem__("staging_commit","bad"),lambda c,e,p:c.__setitem__("scientific_source_head","0"*40),
            lambda c,e,p:c.__setitem__("recovery_v3_authority_sha256","0"*64),lambda c,e,p:c.__setitem__("installed_runtime_workflow_sha256","0"*64),
            lambda c,e,p:c.__setitem__("accepted_canonical_result_count",1),lambda c,e,p:c.__setitem__("arm_present_at_staging",True),
            lambda c,e,p:c.__setitem__("real_execution_authorized_at_staging",True),lambda c,e,p:c.__setitem__("encryption_format","PLAINTEXT"),
            lambda c,e,p:c.__setitem__("source_archives",{"original_sha256":"0"*64,"delta_sha256":"d"*64}),
            lambda c,e,p:c["exact_18_series"][0].__setitem__("symbol","WRONG"),lambda c,e,p:c["exact_18_series"][0].__setitem__("symbol_id",999),
            lambda c,e,p:c["exact_18_series"][0].__setitem__("series_sha256","0"*64),lambda c,e,p:c["exact_18_series"][0].__setitem__("row_count",1),
            lambda c,e,p:c["exact_18_series"][0].__setitem__("first_timestamp_utc","2026-01-01T00:00:00Z"),lambda c,e,p:c["exact_18_series"][0].__setitem__("last_timestamp_utc","2026-01-02T00:00:00Z"),
            lambda c,e,p:c["exact_18_series"][0].__setitem__("source_archive_sha256","0"*64),lambda c,e,p:c.__setitem__("exact_18_series_manifest_sha256","0"*64)]
        for fn in cases:
            with self.subTest(fn=repr(fn)): self._cert_fail(fn)

    def test_staging_encrypted_part_digest_order_and_bundle_are_mechanical(self):
        self._cert_fail(lambda c,e,p:c["encrypted_parts"][0].__setitem__("sha256","0"*64))
        self._cert_fail(lambda c,e,p:c.__setitem__("encrypted_part_order",["wrong"]))
        self._cert_fail(lambda c,e,p:c.__setitem__("encrypted_bundle_sha256","0"*64))

    def test_installed_workflow_is_inert_and_prelock_preopen(self):
        p=Path(__file__).resolve().parents[1]/".github/workflows/v4-greenfield-recovery-v3.yml"; t=p.read_text()
        self.assertIn('paths: ["research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V3_ARM_V1.json"]',t)
        self.assertNotIn("workflow_dispatch",t)
        gate=t.index("--validate-runtime"); lock=t.index("Persist exactly-once attempt lock"); decrypt=t.index("Decrypt exact staged input bundle"); plain=t.index("--verify-plaintext-dir"); execute=t.index("--execute-authorized-development")
        self.assertLess(gate,lock); self.assertLess(lock,decrypt); self.assertLess(decrypt,plain); self.assertLess(plain,execute)

if __name__=="__main__": unittest.main()
