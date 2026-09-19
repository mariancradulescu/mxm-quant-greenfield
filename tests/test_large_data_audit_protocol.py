import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from m6.large_data_audit import (
    AUTHORITY_SCHEMA,
    LargeDataAuditError,
    audit_dataset,
    canonical_json_bytes,
    validate_authority,
    write_capsule,
)

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

def make_authority(root: Path):
    files=[]
    for key,name,stream in (("A","a.csv","S1"),("B","b.csv","S1")):
        data=(root/name).read_bytes()
        sha=hashlib.sha256(data).hexdigest()
        rows=max(0,data.count(b"\n")-1)
        files.append({
            "identity":key,
            "relative_path":name,
            "byte_size":len(data),
            "sha256":sha,
            "row_count":rows,
            "row_count_mode":"CSV_DATA_ROWS_HEADER_ONE",
            "stream":stream,
            "commitment_record":{"key":key,"row_count":rows,"sha256":sha},
        })
    canonical={
        "sort_field":"key","sort_keys":True,"separators":[",",":"],
        "ensure_ascii":False,"terminal_newline":True,"encoding":"utf-8",
        "commitment_sha256_field":"sha256","commitment_row_count_field":"row_count",
    }
    records=sorted([x["commitment_record"] for x in files],key=lambda x:x["key"])
    agg=hashlib.sha256(canonical_json_bytes(records,canonical)).hexdigest()
    return {
        "schema":AUTHORITY_SCHEMA,
        "dataset_id":"fixture",
        "dataset_version":"v1",
        "files":files,
        "canonicalization":canonical,
        "aggregate_commitment":{
            "sha256":agg,"file_count":2,
            "byte_total":sum(x["byte_size"] for x in files),
            "row_total":sum(x["row_count"] for x in files),
        },
        "streams":{
            "S1":{
                "selector":{"field":"stream","equals":"S1"},
                "sha256":agg,"file_count":2,
                "byte_total":sum(x["byte_size"] for x in files),
                "row_total":sum(x["row_count"] for x in files),
            }
        },
        "retention":{"deletion_authorized":False},
        "provenance":{"source":"fixture"},
    }

class LargeDataAuditProtocolTests(unittest.TestCase):
    def test_01_current_tier1_rehash_reconciliation_is_exact(self):
        e=load("evidence/TIER1_LOCAL_FULL_RAW_BYTE_REHASH_RECONCILIATION_V1.json")
        self.assertEqual(e["status"],"LOCAL_FULL_RAW_BYTE_REHASH_PASS_COMPACT_EXTERNAL_RECONCILIATION_PASS")
        p=e["reconciliation"]["per_file"]
        self.assertEqual(p["raw_chunks_expected"],9824)
        self.assertEqual(p["raw_chunks_matched_to_original_resume_completed_records"],9824)
        self.assertEqual(p["sha256_matches"],9824)
        self.assertEqual(p["sha256_mismatches"],0)
        self.assertEqual(p["missing_chunks"],0)
        self.assertEqual(p["unexpected_chunks"],0)
        self.assertEqual(p["key_path_inconsistencies"],0)

    def test_02_current_aggregate_and_stream_reconstructions_match_frozen_authorities(self):
        e=load("evidence/TIER1_LOCAL_FULL_RAW_BYTE_REHASH_RECONCILIATION_V1.json")
        a=e["reconciliation"]["tier1_original"]
        b=e["reconciliation"]["tier1_preopen"]
        self.assertEqual(a["reconstructed_ordered_manifest_sha256"],"119d05376bf4f5e67ddea6553221f80c01e9b137762c7df3cc3804d0e1633cd3")
        self.assertTrue(a["aggregate_match"])
        self.assertEqual(b["reconstructed_ordered_manifest_sha256"],"3b472e6a6a2ebd0ffc4e228f834e28ff8d09e2cd9a1812c2ee8ecfa2d2c876d3")
        self.assertTrue(b["aggregate_match"])
        self.assertTrue(all(x["match"] for x in a["streams"].values()))
        self.assertTrue(all(x["match"] for x in b["streams"].values()))
        self.assertEqual(a["canonicalization"]["ensure_ascii"],True)
        self.assertEqual(a["canonicalization"]["terminal_newline"],False)
        self.assertEqual(b["canonicalization"]["ensure_ascii"],False)
        self.assertEqual(b["canonicalization"]["terminal_newline"],True)

    def test_03_truthful_local_vs_external_distinction_is_preserved(self):
        e=load("evidence/TIER1_LOCAL_FULL_RAW_BYTE_REHASH_RECONCILIATION_V1.json")
        t=e["truthful_status"]
        self.assertEqual(t["LOCAL_FULL_RAW_BYTE_REHASH"],"PASS")
        self.assertEqual(t["LOCAL_REHASH_VS_ORIGINAL_PER_CHUNK_SHA256"],"9824/9824 PASS")
        self.assertEqual(t["RAW_BYTES_EXTERNALLY_TRANSFERRED"],"NO")
        self.assertEqual(t["EXTERNAL_FULL_15GB_RAW_BYTE_REHASH"],"NO")

    def test_04_permanent_protocol_binds_pydroid_safe_read_only_verifier(self):
        p=load("data/CONTENT_ADDRESSED_LARGE_DATA_AUDIT_PROTOCOL_V1.json")
        self.assertEqual(p["status"],"FROZEN_APPEND_ONLY_PROJECT_AUTHORITY")
        self.assertEqual(p["verifier"]["version"],"MXM_CONTENT_ADDRESSED_LARGE_DATA_AUDIT_V1")
        self.assertEqual(p["verifier"]["runtime_git_blob_sha1"],"e724980d7f672220e05b567cdf0db27797de3e2d")
        self.assertEqual(p["verifier"]["dependencies"],"PYTHON_STDLIB_ONLY")
        self.assertEqual(p["verifier"]["raw_access"],"READ_ONLY")
        self.assertTrue(p["verifier"]["heartbeat_progress_eta"])
        self.assertTrue(p["verifier"]["fail_closed"])
        self.assertIn("ACTUAL_REHASHED_RAW_SHA256",p["verifier"]["aggregate_reconstruction_source"])

    def test_05_verifier_passes_and_reconstructs_from_rehashed_raw(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"raw"; root.mkdir()
            (root/"a.csv").write_bytes(b"x\n1\n2\n")
            (root/"b.csv").write_bytes(b"x\n3\n")
            a=make_authority(root)
            r=audit_dataset(root,a,heartbeat_seconds=999)
            self.assertEqual(r["status"],"PASS")
            self.assertEqual(r["raw_files_hashed"],2)
            self.assertEqual(r["file_mismatch_count"],0)
            self.assertTrue(r["aggregate_commitment"]["match"])
            self.assertTrue(r["streams"]["S1"]["match"])

    def test_06_raw_byte_mutation_fails_per_file_and_aggregate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"raw"; root.mkdir()
            (root/"a.csv").write_bytes(b"x\n1\n2\n")
            (root/"b.csv").write_bytes(b"x\n3\n")
            a=make_authority(root)
            (root/"a.csv").write_bytes(b"x\n9\n2\n")
            r=audit_dataset(root,a,heartbeat_seconds=999)
            self.assertEqual(r["status"],"FAIL_CLOSED")
            self.assertGreater(r["file_mismatch_count"],0)
            self.assertFalse(r["aggregate_commitment"]["match"])
            self.assertFalse(r["streams"]["S1"]["match"])

    def test_07_missing_and_unexpected_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"raw"; root.mkdir()
            (root/"a.csv").write_bytes(b"x\n1\n2\n")
            (root/"b.csv").write_bytes(b"x\n3\n")
            a=make_authority(root)
            (root/"b.csv").unlink()
            (root/"extra.csv").write_bytes(b"x\n4\n")
            r=audit_dataset(root,a,heartbeat_seconds=999)
            self.assertEqual(r["status"],"FAIL_CLOSED")
            self.assertEqual(r["missing_count"],1)
            self.assertEqual(r["unexpected_count"],1)

    def test_08_unsafe_paths_and_implicit_canonicalization_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"a.csv").write_bytes(b"x\n1\n"); (root/"b.csv").write_bytes(b"x\n2\n")
            a=make_authority(root)
            a["files"][0]["relative_path"]="../a.csv"
            with self.assertRaises(LargeDataAuditError):
                validate_authority(a)
            a=make_authority(root)
            del a["canonicalization"]["terminal_newline"]
            with self.assertRaises(LargeDataAuditError):
                validate_authority(a)

    def test_09_capsule_is_deterministic_and_contains_no_raw_bulk(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"raw"; root.mkdir()
            (root/"a.csv").write_bytes(b"x\n1\n2\n")
            (root/"b.csv").write_bytes(b"x\n3\n")
            a=make_authority(root)
            r=audit_dataset(root,a,heartbeat_seconds=999)
            z1=Path(td)/"a.zip"; z2=Path(td)/"b.zip"
            h1=write_capsule(r,z1); h2=write_capsule(r,z2)
            self.assertEqual(h1,h2)
            self.assertEqual(z1.read_bytes(),z2.read_bytes())
            import zipfile
            with zipfile.ZipFile(z1) as z:
                self.assertEqual(sorted(z.namelist()),["AUDIT_REPORT.json","CHECKSUMS.sha256"])

    def test_10_current_state_changes_only_integrity_infrastructure_not_research_outcomes(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(s["large_data_audit_protocol_authority"],"data/CONTENT_ADDRESSED_LARGE_DATA_AUDIT_PROTOCOL_V1.json")
        self.assertEqual(s["tier1_local_full_raw_byte_rehash_reconciliation_authority"],"evidence/TIER1_LOCAL_FULL_RAW_BYTE_REHASH_RECONCILIATION_V1.json")
        self.assertEqual(s["economic_outcomes_opened"],0)
        self.assertEqual(s["v2_attempts_used"],0)
        self.assertEqual(s["v2_evaluated_identities"],0)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertEqual(s["m6"]["status"],"PENDING")
        self.assertFalse(s["m6"]["economics_run"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])
        self.assertEqual(s["tier1_discovery_transaction_local_cost_rule_authority"],"evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json")
        ledger=[json.loads(x) for x in (ROOT/"discovery/ledger.jsonl").read_text().splitlines() if x.strip()]
        self.assertEqual(sum(x["entry_type"]=="RESULT_RECORDED" for x in ledger),0)
        self.assertEqual(len(ledger),20)

if __name__=="__main__":
    unittest.main(verbosity=2)
