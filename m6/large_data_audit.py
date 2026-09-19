"""Content-addressed large-data audit capsule verifier.

Stdlib-only, Android/Pydroid-safe, read-only over RAW_ROOT.
It verifies every manifest file byte-for-byte by SHA-256, optional row counts,
deterministic identities/paths, exact canonical aggregate commitments and stream
commitments, then writes only a compact deterministic audit capsule outside RAW_ROOT.

Storage location is not identity. The cryptographic authority is.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import time
from typing import Any, Mapping, Sequence
import zipfile

TOOL_VERSION = "MXM_CONTENT_ADDRESSED_LARGE_DATA_AUDIT_V1"
AUTHORITY_SCHEMA = "mxm.greenfield.v2.large-data-audit-dataset-authority.v1"
REPORT_SCHEMA = "mxm.greenfield.v2.large-data-audit-capsule.v1"
_CHUNK = 8 * 1024 * 1024
_FORBIDDEN_REPORT_KEYS = {
    "access_token","refresh_token","client_secret","password","authorization",
    "bearer","api_key","private_key","secret"
}


class LargeDataAuditError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str, *, count_lines: bool = False) -> tuple[str, int, int | None]:
    h = hashlib.sha256()
    size = 0
    lines = 0
    last = b""
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
            if count_lines:
                lines += chunk.count(b"\n")
                last = chunk[-1:]
    if count_lines and size and last != b"\n":
        lines += 1
    return h.hexdigest(), size, lines if count_lines else None


def canonical_json_bytes(value: Any, spec: Mapping[str, Any]) -> bytes:
    required = {
        "sort_keys","separators","ensure_ascii","terminal_newline","encoding","sort_field",
        "commitment_sha256_field","commitment_row_count_field"
    }
    missing = required - set(spec)
    if missing:
        raise LargeDataAuditError(f"canonicalization missing fields: {sorted(missing)}")
    if list(spec["separators"]) != [",", ":"]:
        raise LargeDataAuditError("only explicit compact JSON separators [',', ':'] are supported")
    if spec["encoding"].lower() != "utf-8":
        raise LargeDataAuditError("only UTF-8 canonicalization is supported")
    raw = json.dumps(
        value,
        sort_keys=bool(spec["sort_keys"]),
        separators=(",", ":"),
        ensure_ascii=bool(spec["ensure_ascii"]),
    )
    if bool(spec["terminal_newline"]):
        raw += "\n"
    return raw.encode("utf-8")


def _safe_relpath(value: str) -> str:
    p = PurePosixPath(str(value))
    if p.is_absolute() or not p.parts or any(x in ("", ".", "..") for x in p.parts):
        raise LargeDataAuditError(f"unsafe/non-deterministic relative path: {value!r}")
    if "\\" in str(value):
        raise LargeDataAuditError(f"relative paths must use '/' separators: {value!r}")
    return p.as_posix()


def _authority_sha(authority: Mapping[str, Any]) -> str:
    raw = (json.dumps(authority, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    return _sha256_bytes(raw)


def _source_sha() -> str:
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except Exception:
        return "UNAVAILABLE"


def _scan_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for k, v in value.items():
            low = str(k).lower()
            if low in _FORBIDDEN_REPORT_KEYS or any(token in low for token in ("token","secret","password","private_key")):
                raise LargeDataAuditError(f"forbidden sensitive key in transferable capsule at {path}.{k}")
            _scan_forbidden_keys(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _scan_forbidden_keys(v, f"{path}[{i}]")


def validate_authority(authority: Mapping[str, Any]) -> None:
    if authority.get("schema") != AUTHORITY_SCHEMA:
        raise LargeDataAuditError("unsupported dataset authority schema")
    for key in ("dataset_id","dataset_version","files","canonicalization","aggregate_commitment","streams","retention"):
        if key not in authority:
            raise LargeDataAuditError(f"authority missing {key}")
    if authority["retention"].get("deletion_authorized") is not False:
        raise LargeDataAuditError("large-data authority must be fail-closed on deletion")
    files = authority["files"]
    if not isinstance(files, list) or not files:
        raise LargeDataAuditError("authority files must be a non-empty list")
    seen_paths, seen_ids = set(), set()
    for item in files:
        for key in ("identity","relative_path","byte_size","sha256","commitment_record"):
            if key not in item:
                raise LargeDataAuditError(f"manifest item missing {key}")
        rel = _safe_relpath(item["relative_path"])
        identity = str(item["identity"])
        if rel in seen_paths or identity in seen_ids:
            raise LargeDataAuditError("duplicate relative_path or identity")
        seen_paths.add(rel); seen_ids.add(identity)
        if int(item["byte_size"]) < 0:
            raise LargeDataAuditError("negative byte_size")
        sha = str(item["sha256"])
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise LargeDataAuditError(f"invalid SHA256 for {rel}")
        rec = item["commitment_record"]
        canonical = authority["canonicalization"]
        sort_field = canonical["sort_field"]
        sha_field = canonical["commitment_sha256_field"]
        row_field = canonical["commitment_row_count_field"]
        if sort_field not in rec:
            raise LargeDataAuditError(f"commitment_record missing sort field {sort_field}")
        if sha_field not in rec:
            raise LargeDataAuditError(f"commitment_record missing SHA field {sha_field}")
        if row_field is not None and row_field not in rec:
            raise LargeDataAuditError(f"commitment_record missing row-count field {row_field}")
    canonical_json_bytes([], authority["canonicalization"])


def _expected_commitment(items: Sequence[Mapping[str, Any]], canonicalization: Mapping[str, Any]) -> str:
    sort_field = canonicalization["sort_field"]
    records = [x["commitment_record"] for x in items]
    records = sorted(records, key=lambda x: str(x[sort_field]))
    return _sha256_bytes(canonical_json_bytes(records, canonicalization))


def _matches_selector(item: Mapping[str, Any], selector: Mapping[str, Any]) -> bool:
    field = selector.get("field")
    if not field:
        raise LargeDataAuditError("stream selector missing field")
    if "equals" in selector:
        return item.get(field) == selector["equals"]
    if "in" in selector:
        return item.get(field) in selector["in"]
    raise LargeDataAuditError("stream selector requires equals or in")


def audit_dataset(
    raw_root: Path | str,
    authority: Mapping[str, Any],
    *,
    heartbeat_seconds: float = 5.0,
    verify_unexpected_files: bool = True,
) -> dict[str, Any]:
    validate_authority(authority)
    root = Path(raw_root)
    if not root.is_dir():
        raise LargeDataAuditError(f"raw root is not a directory: {root}")

    entries = list(authority["files"])
    expected_paths = {_safe_relpath(x["relative_path"]) for x in entries}
    total_expected_bytes = sum(int(x["byte_size"]) for x in entries)
    processed_bytes = 0
    started = time.monotonic()
    last_heartbeat = started
    results = []
    mismatch_count = 0
    missing_count = 0
    row_mismatch_count = 0

    for index, item in enumerate(sorted(entries, key=lambda x: _safe_relpath(x["relative_path"])), 1):
        rel = _safe_relpath(item["relative_path"])
        path = root.joinpath(*PurePosixPath(rel).parts)
        if not path.is_file():
            missing_count += 1
            mismatch_count += 1
            results.append({
                "identity": item["identity"], "relative_path": rel,
                "expected_bytes": int(item["byte_size"]), "actual_bytes": None,
                "expected_sha256": item["sha256"], "actual_sha256": None,
                "sha256_match": False, "row_count_match": None, "state": "MISSING"
            })
            continue

        row_mode = item.get("row_count_mode", "NONE")
        count_lines = row_mode in ("CSV_DATA_ROWS_HEADER_ONE", "TEXT_LINES")
        actual_sha, actual_bytes, line_count = sha256_file(path, count_lines=count_lines)
        processed_bytes += actual_bytes
        sha_match = actual_sha == item["sha256"]
        bytes_match = actual_bytes == int(item["byte_size"])
        actual_rows = None
        row_match = None
        if row_mode == "CSV_DATA_ROWS_HEADER_ONE":
            actual_rows = max(0, int(line_count or 0) - 1)
            row_match = actual_rows == int(item["row_count"])
        elif row_mode == "TEXT_LINES":
            actual_rows = int(line_count or 0)
            row_match = actual_rows == int(item["row_count"])
        elif row_mode != "NONE":
            raise LargeDataAuditError(f"unsupported row_count_mode {row_mode!r}")
        if row_match is False:
            row_mismatch_count += 1
        ok = sha_match and bytes_match and row_match is not False
        if not ok:
            mismatch_count += 1
        results.append({
            "identity": item["identity"], "relative_path": rel,
            "expected_bytes": int(item["byte_size"]), "actual_bytes": actual_bytes,
            "expected_sha256": item["sha256"], "actual_sha256": actual_sha,
            "sha256_match": sha_match, "byte_size_match": bytes_match,
            "expected_row_count": item.get("row_count"),
            "actual_row_count": actual_rows, "row_count_match": row_match,
            "state": "PASS" if ok else "MISMATCH"
        })

        now = time.monotonic()
        if index == 1 or index == len(entries) or now - last_heartbeat >= heartbeat_seconds:
            elapsed = max(0.001, now - started)
            rate = processed_bytes / elapsed
            remaining = max(0, total_expected_bytes - processed_bytes)
            eta = remaining / rate if rate > 0 else None
            print(
                f"[LARGE-DATA AUDIT] {index}/{len(entries)} files | "
                f"{processed_bytes}/{total_expected_bytes} bytes | "
                f"{100.0*processed_bytes/max(1,total_expected_bytes):.2f}% | "
                f"ETA {'?' if eta is None else f'{eta/60.0:.1f}m'}"
            )
            last_heartbeat = now

    unexpected = []
    if verify_unexpected_files:
        for p in root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                if rel not in expected_paths:
                    unexpected.append(rel)

    canonical = authority["canonicalization"]
    result_by_identity = {str(x["identity"]): x for x in results}
    actual_entries = []
    for item in entries:
        result = result_by_identity[str(item["identity"])]
        if result["actual_sha256"] is None:
            continue
        actual_item = json.loads(json.dumps(item))
        actual_item["byte_size"] = int(result["actual_bytes"])
        actual_item["sha256"] = result["actual_sha256"]
        actual_item["commitment_record"][canonical["commitment_sha256_field"]] = result["actual_sha256"]
        row_field = canonical["commitment_row_count_field"]
        if row_field is not None and result["actual_row_count"] is not None:
            actual_item["row_count"] = int(result["actual_row_count"])
            actual_item["commitment_record"][row_field] = int(result["actual_row_count"])
        actual_entries.append(actual_item)

    aggregate_expected = authority["aggregate_commitment"]["sha256"]
    aggregate_actual = (
        _expected_commitment(actual_entries, canonical)
        if len(actual_entries) == len(entries) else None
    )
    aggregate_match = aggregate_actual == aggregate_expected
    stream_results = {}
    stream_failures = 0
    for name, spec in sorted(authority["streams"].items()):
        subset = [x for x in actual_entries if _matches_selector(x, spec["selector"])]
        actual_sha = (
            _expected_commitment(subset, canonical)
            if len(subset) == int(spec["file_count"]) else None
        )
        file_count = len(subset)
        byte_total = sum(int(x["byte_size"]) for x in subset)
        row_total = sum(int(x.get("row_count", 0)) for x in subset)
        ok = (
            actual_sha == spec["sha256"]
            and file_count == int(spec["file_count"])
            and byte_total == int(spec["byte_total"])
            and row_total == int(spec.get("row_total", row_total))
        )
        if not ok:
            stream_failures += 1
        stream_results[name] = {
            "file_count": file_count,
            "byte_total": byte_total,
            "row_total": row_total,
            "reconstructed_sha256_from_rehashed_raw": actual_sha,
            "expected_sha256": spec["sha256"],
            "match": ok,
        }

    passed = (
        mismatch_count == 0 and missing_count == 0 and row_mismatch_count == 0
        and not unexpected and aggregate_match and stream_failures == 0
        and len(results) == int(authority["aggregate_commitment"]["file_count"])
        and total_expected_bytes == int(authority["aggregate_commitment"]["byte_total"])
    )
    report = {
        "schema": REPORT_SCHEMA,
        "status": "PASS" if passed else "FAIL_CLOSED",
        "dataset_id": authority["dataset_id"],
        "dataset_version": authority["dataset_version"],
        "authority_sha256": _authority_sha(authority),
        "verifier": {"version": TOOL_VERSION, "source_sha256": _source_sha()},
        "raw_storage_location_is_identity": False,
        "raw_bytes_transferred_in_capsule": False,
        "raw_files_expected": len(entries),
        "raw_files_hashed": sum(x["actual_sha256"] is not None for x in results),
        "raw_bytes_expected": total_expected_bytes,
        "raw_bytes_read_and_hashed": sum(int(x["actual_bytes"] or 0) for x in results),
        "missing_count": missing_count,
        "unexpected_count": len(unexpected),
        "unexpected_paths": sorted(unexpected),
        "file_mismatch_count": mismatch_count,
        "row_mismatch_count": row_mismatch_count,
        "aggregate_commitment": {
            "expected_sha256": aggregate_expected,
            "reconstructed_sha256": aggregate_actual,
            "match": aggregate_match,
            "canonicalization": authority["canonicalization"],
        },
        "streams": stream_results,
        "per_file_results": results,
        "retention": {
            "raw_bytes_remain_user_controlled": True,
            "deletion_authorized": False,
        },
        "provenance_commitment_sha256": _sha256_bytes(
            canonical_json_bytes(authority.get("provenance", {}), {
                "sort_keys": True, "separators": [",", ":"], "ensure_ascii": False,
                "terminal_newline": True, "encoding": "utf-8", "sort_field": "unused",
                "commitment_sha256_field": "unused", "commitment_row_count_field": None
            })
        ),
    }
    _scan_forbidden_keys(report)
    return report


def write_capsule(report: Mapping[str, Any], output_zip: Path | str) -> str:
    output = Path(output_zip)
    payload = (json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    report_sha = _sha256_bytes(payload)
    checksums = f"{report_sha}  AUDIT_REPORT.json\n".encode("ascii")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, data in (("AUDIT_REPORT.json", payload), ("CHECKSUMS.sha256", checksums)):
            info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", required=True)
    ap.add_argument("--authority", required=True)
    ap.add_argument("--authority-sha256")
    ap.add_argument("--output", required=True)
    ap.add_argument("--heartbeat-seconds", type=float, default=5.0)
    args = ap.parse_args(argv)

    authority_path = Path(args.authority)
    authority_bytes = authority_path.read_bytes()
    if args.authority_sha256:
        actual = hashlib.sha256(authority_bytes).hexdigest()
        if actual != args.authority_sha256:
            raise LargeDataAuditError(
                f"authority file SHA256 mismatch: expected {args.authority_sha256}, got {actual}"
            )
    authority = json.loads(authority_bytes)
    report = audit_dataset(
        args.raw_root, authority, heartbeat_seconds=args.heartbeat_seconds
    )
    capsule_sha = write_capsule(report, args.output)
    print(f"CAPSULE_SHA256={capsule_sha}")
    print(f"STATUS={report['status']}")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
