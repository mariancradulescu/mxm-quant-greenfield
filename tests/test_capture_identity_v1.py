import json,tempfile,unittest,zipfile
from pathlib import Path

from research_v3.capture_identity import (
    CaptureIdentityError,build_capture_manifest,evidence_identity,inspect_transfer_zip,
)

class CaptureIdentityV1Tests(unittest.TestCase):
    def _zip(self,root,name,entries):
        p=Path(root)/name
        with zipfile.ZipFile(p,"w") as z:
            for path,data in entries:z.writestr(path,data)
        return p

    def test_repacking_and_wrapper_directories_do_not_change_canonical_payload_identity(self):
        payload=b'{"schema":"s","status":"COMPLETE","value":1}\n'
        with tempfile.TemporaryDirectory() as td:
            a=self._zip(td,"a.zip",[("PAYLOAD.json",payload)])
            b=self._zip(td,"b.zip",[("wrapper/PAYLOAD.json",payload),("notes.txt",b"transport note")])
            ia=inspect_transfer_zip(a,logical_payload_name="PAYLOAD.json",expected_schema="s",expected_status="COMPLETE")
            ib=inspect_transfer_zip(b,logical_payload_name="PAYLOAD.json",expected_schema="s",expected_status="COMPLETE")
            self.assertNotEqual(ia["transport_sha256"],ib["transport_sha256"])
            self.assertEqual(ia["canonical_payload_sha256"],ib["canonical_payload_sha256"])
            self.assertEqual(len(ib["unknown_extra_files_inspected"]),1)

    def test_identical_duplicate_canonical_payloads_are_allowed_and_canonicalized(self):
        payload=b'{"schema":"s","status":"COMPLETE"}'
        with tempfile.TemporaryDirectory() as td:
            p=self._zip(td,"x.zip",[("PAYLOAD.json",payload),("wrapper/PAYLOAD.json",payload)])
            i=inspect_transfer_zip(p,logical_payload_name="PAYLOAD.json")
            self.assertEqual(i["candidate_payload_count"],2)
            self.assertTrue(i["duplicate_payloads_byte_identical"])

    def test_conflicting_duplicate_payloads_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=self._zip(td,"x.zip",[("PAYLOAD.json",b'{"a":1}'),("wrapper/PAYLOAD.json",b'{"a":2}')])
            with self.assertRaises(CaptureIdentityError):inspect_transfer_zip(p,logical_payload_name="PAYLOAD.json")

    def test_secret_scan_remains_mandatory(self):
        with tempfile.TemporaryDirectory() as td:
            p=self._zip(td,"x.zip",[("PAYLOAD.json",b'{"access_token":"do-not-transfer"}')])
            with self.assertRaises(CaptureIdentityError):inspect_transfer_zip(p,logical_payload_name="PAYLOAD.json")

    def test_manifest_identity_excludes_outer_zip_bytes(self):
        payload={"PAYLOAD.json":b'{"x":1}\n'}
        kwargs=dict(
            capture_session_id="c1",capture_schema="schema",tool_version="tool",
            account_fingerprint="fp",source_environment="env",
            capture_start_utc="2026-09-25T00:00:00Z",capture_end_utc="2026-09-25T00:01:00Z",
            completion_state="COMPLETE",canonical_payloads=payload,
            original_collector_package_sha256="package",read_only_assertion=True,
            economic_outcomes_opened=0,orders_placed=False,account_mutation=False,
            protected_evidence_opened=False,
        )
        a=build_capture_manifest(**kwargs);b=build_capture_manifest(**kwargs)
        self.assertEqual(evidence_identity(a),evidence_identity(b))
        self.assertEqual(a["sha256_per_canonical_payload"],b["sha256_per_canonical_payload"])

    def test_manifest_rejects_case_insensitive_payload_name_collision(self):
        kwargs=dict(
            capture_session_id="c1",capture_schema="schema",tool_version="tool",
            account_fingerprint="fp",source_environment="env",
            capture_start_utc="2026-09-25T00:00:00Z",capture_end_utc="2026-09-25T00:01:00Z",
            completion_state="COMPLETE",canonical_payloads={"capture_manifest.json":b'{"x":1}\n'},
            original_collector_package_sha256=None,read_only_assertion=True,
            economic_outcomes_opened=0,orders_placed=False,account_mutation=False,
            protected_evidence_opened=False,
        )
        with self.assertRaisesRegex(CaptureIdentityError,"collides case-insensitively"):
            build_capture_manifest(**kwargs)

if __name__=="__main__":unittest.main()
