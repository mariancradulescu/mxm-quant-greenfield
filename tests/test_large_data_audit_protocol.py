import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from m6.large_data_audit import (
    AUTHORITY_SCHEMA,
    LargeDataAuditError,
    audit_dataset,
    canonical_authority_object_sha256,
    canonical_json_bytes,
    load_authority_file,
    main,
    validate_authority,
    validate_output_path,
    write_capsule,
)

ROOT = Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def make_authority(root: Path):
    files = []
    for key, name, stream in (("A", "a.csv", "S1"), ("B", "b.csv", "S1")):
        data = (root / name).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        rows = max(0, data.count(b"\n") - 1)
        files.append({
            "identity": key,
            "relative_path": name,
            "byte_size": len(data),
            "sha256": sha,
            "row_count": rows,
            "row_count_mode": "CSV_DATA_ROWS_HEADER_ONE",
            "stream": stream,
            "commitment_record": {
                "key": key, "row_count": rows, "sha256": sha
            },
        })
    canonical = {
        "sort_field": "key",
        "sort_keys": True,
        "separators": [",", ":"],
        "ensure_ascii": False,
        "terminal_newline": True,
        "encoding": "utf-8",
        "commitment_sha256_field": "sha256",
        "commitment_row_count_field": "row_count",
    }
    records = sorted(
        [x["commitment_record"] for x in files],
        key=lambda x: x["key"],
    )
    agg = hashlib.sha256(
        canonical_json_bytes(records, canonical)
    ).hexdigest()
    return {
        "schema": AUTHORITY_SCHEMA,
        "dataset_id": "fixture",
        "dataset_version": "v1",
        "files": files,
        "canonicalization": canonical,
        "aggregate_commitment": {
            "sha256": agg,
            "file_count": 2,
            "byte_total": sum(x["byte_size"] for x in files),
            "row_total": sum(x["row_count"] for x in files),
        },
        "streams": {
            "S1": {
                "selector": {"field": "stream", "equals": "S1"},
                "sha256": agg,
                "file_count": 2,
                "byte_total": sum(x["byte_size"] for x in files),
                "row_total": sum(x["row_count"] for x in files),
            }
        },
        "retention": {"deletion_authorized": False},
        "provenance": {"source": "fixture"},
    }


def make_fixture(td):
    base = Path(td)
    raw = base / "raw"
    raw.mkdir()
    (raw / "a.csv").write_bytes(b"x\n1\n2\n")
    (raw / "b.csv").write_bytes(b"x\n3\n")
    authority = make_authority(raw)
    authority_path = base / "authority.json"
    authority_bytes = (
        json.dumps(authority, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    authority_path.write_bytes(authority_bytes)
    authority_sha = hashlib.sha256(authority_bytes).hexdigest()
    return raw, authority, authority_path, authority_sha


def bound_report(raw, authority_path, authority_sha):
    authority, file_sha, canonical_sha, state = load_authority_file(
        authority_path, expected_file_sha256=authority_sha
    )
    assert state == "FROZEN_AUTHORITY_BOUND"
    report = audit_dataset(
        raw,
        authority,
        heartbeat_seconds=999,
        authority_file_sha256=file_sha,
        expected_authority_file_sha256=authority_sha,
    )
    assert (
        report["authority_binding"]["authority_canonical_object_sha256"]
        == canonical_sha
    )
    return report


class LargeDataAuditProtocolTests(unittest.TestCase):
    def test_01_accepted_tier1_reconciliation_is_preserved_exactly(self):
        e = load(
            "evidence/TIER1_LOCAL_FULL_RAW_BYTE_REHASH_RECONCILIATION_V1.json"
        )
        self.assertEqual(
            e["status"],
            "LOCAL_FULL_RAW_BYTE_REHASH_PASS_COMPACT_EXTERNAL_RECONCILIATION_PASS",
        )
        p = e["reconciliation"]["per_file"]
        self.assertEqual(p["raw_chunks_expected"], 9824)
        self.assertEqual(
            p["raw_chunks_matched_to_original_resume_completed_records"], 9824
        )
        self.assertEqual(p["sha256_matches"], 9824)
        self.assertEqual(p["sha256_mismatches"], 0)
        self.assertEqual(p["missing_chunks"], 0)
        self.assertEqual(p["unexpected_chunks"], 0)
        self.assertEqual(p["key_path_inconsistencies"], 0)
        self.assertTrue(
            e["reconciliation"]["tier1_original"]["aggregate_match"]
        )
        self.assertTrue(
            e["reconciliation"]["tier1_preopen"]["aggregate_match"]
        )
        self.assertEqual(
            e["truthful_status"]["RAW_BYTES_EXTERNALLY_TRANSFERRED"], "NO"
        )
        self.assertEqual(
            e["truthful_status"]["EXTERNAL_FULL_15GB_RAW_BYTE_REHASH"], "NO"
        )

    def test_02_v2_protocol_supersedes_verifier_only_not_reconciliation(self):
        p = load("data/CONTENT_ADDRESSED_LARGE_DATA_AUDIT_PROTOCOL_V2.json")
        self.assertEqual(
            p["supersedes"],
            "data/CONTENT_ADDRESSED_LARGE_DATA_AUDIT_PROTOCOL_V1.json",
        )
        self.assertEqual(
            p["verifier"]["version"],
            "MXM_CONTENT_ADDRESSED_LARGE_DATA_AUDIT_V2",
        )
        self.assertEqual(
            p["verifier"]["runtime_git_blob_sha1"],
            "f5f53196bddcab8a8a0198d004bffae4bb5db8d6",
        )
        self.assertTrue(
            p["historical_reconciliation_preserved"]["reopened"] is False
        )
        self.assertFalse(
            p["safety_correction"]["accepted_tier1_reconciliation_changed"]
        )
        self.assertEqual(
            p["verifier"]["raw_access"], "READ_ONLY_BY_CONSTRUCTION"
        )

    def test_03_output_inside_raw_root_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            raw, _, authority_path, authority_sha = make_fixture(td)
            before = {
                p.name: p.read_bytes() for p in raw.iterdir() if p.is_file()
            }
            authority_before = authority_path.read_bytes()
            with self.assertRaises(LargeDataAuditError):
                main([
                    "--raw-root", str(raw),
                    "--authority", str(authority_path),
                    "--authority-sha256", authority_sha,
                    "--output", str(raw / "capsule.zip"),
                ])
            self.assertEqual(
                before,
                {p.name: p.read_bytes() for p in raw.iterdir() if p.is_file()},
            )
            self.assertEqual(authority_before, authority_path.read_bytes())
            self.assertFalse((raw / "capsule.zip").exists())

    def test_04_output_exactly_existing_raw_file_is_rejected_and_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            raw, _, authority_path, authority_sha = make_fixture(td)
            raw_file = raw / "a.csv"
            raw_before = raw_file.read_bytes()
            authority_before = authority_path.read_bytes()
            with self.assertRaises(LargeDataAuditError):
                main([
                    "--raw-root", str(raw),
                    "--authority", str(authority_path),
                    "--authority-sha256", authority_sha,
                    "--output", str(raw_file),
                ])
            self.assertEqual(raw_before, raw_file.read_bytes())
            self.assertEqual(authority_before, authority_path.read_bytes())

    def test_05_output_exactly_authority_file_is_rejected_and_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            raw, _, authority_path, authority_sha = make_fixture(td)
            raw_before = {
                p.name: p.read_bytes() for p in raw.iterdir() if p.is_file()
            }
            authority_before = authority_path.read_bytes()
            with self.assertRaises(LargeDataAuditError):
                main([
                    "--raw-root", str(raw),
                    "--authority", str(authority_path),
                    "--authority-sha256", authority_sha,
                    "--output", str(authority_path),
                ])
            self.assertEqual(authority_before, authority_path.read_bytes())
            self.assertEqual(
                raw_before,
                {p.name: p.read_bytes() for p in raw.iterdir() if p.is_file()},
            )

    def test_06_existing_output_is_no_clobber(self):
        with tempfile.TemporaryDirectory() as td:
            raw, _, authority_path, authority_sha = make_fixture(td)
            output = Path(td) / "existing.zip"
            output.write_bytes(b"KEEP")
            with self.assertRaises(LargeDataAuditError):
                main([
                    "--raw-root", str(raw),
                    "--authority", str(authority_path),
                    "--authority-sha256", authority_sha,
                    "--output", str(output),
                ])
            self.assertEqual(output.read_bytes(), b"KEEP")

    def test_07_wrong_aggregate_row_total_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, _, _ = make_fixture(td)
            authority["aggregate_commitment"]["row_total"] += 1
            r = audit_dataset(raw, authority, heartbeat_seconds=999)
            self.assertEqual(r["status"], "FAIL_CLOSED")
            self.assertFalse(r["certified_pass"])
            self.assertFalse(r["authority_internal_consistency"]["pass"])
            self.assertEqual(
                r["aggregate_commitment"]["actual_row_total"], 3
            )
            self.assertEqual(
                r["aggregate_commitment"]["expected_row_total"], 4
            )
            self.assertFalse(
                r["aggregate_commitment"]["row_total_match"]
            )

    def test_08_correct_aggregate_row_total_certified_bound_pass(self):
        with tempfile.TemporaryDirectory() as td:
            raw, _, authority_path, authority_sha = make_fixture(td)
            r = bound_report(raw, authority_path, authority_sha)
            self.assertEqual(r["status"], "FROZEN_AUTHORITY_BOUND_PASS")
            self.assertTrue(r["certified_pass"])
            self.assertTrue(
                r["aggregate_commitment"]["row_total_match"]
            )
            self.assertEqual(
                r["aggregate_commitment"]["actual_row_total"],
                r["aggregate_commitment"]["expected_row_total"],
            )

    def test_09_wrong_frozen_authority_sha_fails_before_raw_audit(self):
        with tempfile.TemporaryDirectory() as td:
            raw, _, authority_path, _ = make_fixture(td)
            wrong = "0" * 64
            with patch(
                "m6.large_data_audit.audit_dataset"
            ) as audit_mock:
                with self.assertRaises(LargeDataAuditError):
                    main([
                        "--raw-root", str(raw),
                        "--authority", str(authority_path),
                        "--authority-sha256", wrong,
                        "--output", str(Path(td) / "out.zip"),
                    ])
                audit_mock.assert_not_called()

    def test_10_certified_pass_requires_and_records_authority_binding(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, authority_path, authority_sha = make_fixture(td)
            unbound = audit_dataset(raw, authority, heartbeat_seconds=999)
            self.assertEqual(unbound["status"], "UNBOUND_LOCAL_CHECK")
            self.assertFalse(unbound["certified_pass"])
            self.assertEqual(
                unbound["authority_binding"]["state"],
                "UNBOUND_LOCAL_CHECK",
            )
            bound = bound_report(raw, authority_path, authority_sha)
            self.assertEqual(
                bound["authority_binding"]["state"],
                "FROZEN_AUTHORITY_BOUND",
            )
            self.assertEqual(
                bound["authority_binding"]["authority_file_sha256"],
                authority_sha,
            )
            self.assertEqual(
                bound["authority_binding"]["expected_authority_file_sha256"],
                authority_sha,
            )
            self.assertTrue(bound["certified_pass"])

    def test_11_formatting_changes_follow_file_byte_binding_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, _, _ = make_fixture(td)
            pretty = Path(td) / "pretty.json"
            compact = Path(td) / "compact.json"
            pretty.write_text(
                json.dumps(authority, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            compact.write_text(
                json.dumps(
                    authority,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ) + "\n",
                encoding="utf-8",
            )
            pretty_sha = hashlib.sha256(pretty.read_bytes()).hexdigest()
            compact_sha = hashlib.sha256(compact.read_bytes()).hexdigest()
            self.assertNotEqual(pretty_sha, compact_sha)

            ap, _, cp, _ = load_authority_file(
                pretty, expected_file_sha256=pretty_sha
            )
            ac, _, cc, _ = load_authority_file(
                compact, expected_file_sha256=compact_sha
            )
            self.assertEqual(
                canonical_authority_object_sha256(ap),
                canonical_authority_object_sha256(ac),
            )
            self.assertEqual(cp, cc)
            with self.assertRaises(LargeDataAuditError):
                load_authority_file(
                    compact, expected_file_sha256=pretty_sha
                )

    def test_12_raw_mutation_fails_file_aggregate_and_stream(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, _, _ = make_fixture(td)
            (raw / "a.csv").write_bytes(b"x\n9\n2\n")
            r = audit_dataset(raw, authority, heartbeat_seconds=999)
            self.assertEqual(r["status"], "FAIL_CLOSED")
            self.assertGreater(r["file_mismatch_count"], 0)
            self.assertFalse(r["aggregate_commitment"]["sha256_match"])
            self.assertFalse(r["streams"]["S1"]["match"])

    def test_13_missing_and_unexpected_files_remain_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, _, _ = make_fixture(td)
            (raw / "b.csv").unlink()
            (raw / "extra.csv").write_bytes(b"x\n4\n")
            r = audit_dataset(raw, authority, heartbeat_seconds=999)
            self.assertEqual(r["status"], "FAIL_CLOSED")
            self.assertEqual(r["missing_count"], 1)
            self.assertEqual(r["unexpected_count"], 1)

    def test_14_wrong_stream_row_total_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, _, _ = make_fixture(td)
            authority["streams"]["S1"]["row_total"] += 1
            r = audit_dataset(raw, authority, heartbeat_seconds=999)
            self.assertEqual(r["status"], "FAIL_CLOSED")
            self.assertFalse(r["authority_internal_consistency"]["pass"])
            self.assertFalse(r["streams"]["S1"]["match"])

    def test_15_unsafe_paths_and_implicit_canonicalization_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, authority_path, _ = make_fixture(td)
            authority["files"][0]["relative_path"] = "../a.csv"
            with self.assertRaises(LargeDataAuditError):
                validate_authority(authority)

            authority = make_authority(raw)
            del authority["canonicalization"]["terminal_newline"]
            with self.assertRaises(LargeDataAuditError):
                validate_authority(authority)

            authority = make_authority(raw)
            with self.assertRaises(LargeDataAuditError):
                validate_output_path(
                    raw, authority_path, raw, authority
                )

    def test_16_capsule_is_deterministic_and_excludes_raw_bulk(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, authority_path, authority_sha = make_fixture(td)
            r = bound_report(raw, authority_path, authority_sha)
            z1 = Path(td) / "one.zip"
            z2 = Path(td) / "two.zip"
            h1 = write_capsule(
                r, z1, raw_root=raw,
                authority_path=authority_path, authority=authority
            )
            h2 = write_capsule(
                r, z2, raw_root=raw,
                authority_path=authority_path, authority=authority
            )
            self.assertEqual(h1, h2)
            self.assertEqual(z1.read_bytes(), z2.read_bytes())
            import zipfile
            with zipfile.ZipFile(z1) as z:
                self.assertEqual(
                    sorted(z.namelist()),
                    ["AUDIT_REPORT.json", "CHECKSUMS.sha256"],
                )
                self.assertNotIn("a.csv", z.namelist())
                self.assertNotIn("b.csv", z.namelist())

    def test_17_invalid_heartbeat_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            raw, authority, _, _ = make_fixture(td)
            for value in (0, -1, float("inf"), float("nan")):
                with self.assertRaises(LargeDataAuditError):
                    audit_dataset(
                        raw, authority, heartbeat_seconds=value
                    )

    def test_18_current_state_remains_integrity_only_zero_economics(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["large_data_audit_protocol_authority"], "data/CONTENT_ADDRESSED_LARGE_DATA_AUDIT_PROTOCOL_V2.json")
        self.assertEqual(state["large_data_audit_verifier_safety_correction_authority"], "evidence/LARGE_DATA_AUDIT_VERIFIER_SAFETY_CORRECTION_V1.json")
        self.assertEqual(state["tier1_local_full_raw_byte_rehash_reconciliation_authority"], "evidence/TIER1_LOCAL_FULL_RAW_BYTE_REHASH_RECONCILIATION_V1.json")
        audit = state["large_data_audit_state"]
        self.assertEqual(audit["current_tier1_local_full_raw_byte_rehash"], "PASS_UNCHANGED_NOT_RERUN")
        self.assertEqual(audit["current_raw_chunks_reconciled"], "9824/9824")
        self.assertFalse(audit["external_full_raw_byte_rehash"])
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])
if __name__ == "__main__":
    unittest.main(verbosity=2)
