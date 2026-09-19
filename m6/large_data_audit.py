"""Content-addressed large-data audit capsule verifier V2.

Stdlib-only and Android/Pydroid-safe.

Safety invariants:
* RAW_ROOT is read-only by construction: capsule output must resolve outside RAW_ROOT,
  outside every manifest raw path, and must not equal the authority file.
* Capsule output uses exclusive no-clobber creation; existing outputs are rejected.
* A certified PASS requires an exact frozen SHA256 binding to the raw authority-file bytes.
  Unbound successful runs are explicitly UNBOUND_LOCAL_CHECK, never certified PASS.
* Whole-dataset and per-stream file/byte/row totals are part of the fail-closed law.
* Aggregate commitments are reconstructed from SHA256 values recalculated from raw bytes.

The verifier never asserts that a quote/economic dataset is correct economically; it verifies
only the frozen content-addressed evidence contract supplied by its authority.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import time
from typing import Any, Mapping, Sequence
import zipfile

TOOL_VERSION = "MXM_CONTENT_ADDRESSED_LARGE_DATA_AUDIT_V2"
AUTHORITY_SCHEMA = "mxm.greenfield.v2.large-data-audit-dataset-authority.v1"
REPORT_SCHEMA = "mxm.greenfield.v2.large-data-audit-capsule.v2"
_CHUNK = 8 * 1024 * 1024
_SUPPORTED_ROW_MODES = frozenset({"NONE", "CSV_DATA_ROWS_HEADER_ONE", "TEXT_LINES"})
_FORBIDDEN_REPORT_KEYS = {
    "access_token", "refresh_token", "client_secret", "password", "authorization",
    "bearer", "api_key", "private_key", "secret",
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
        "sort_keys", "separators", "ensure_ascii", "terminal_newline", "encoding",
        "sort_field", "commitment_sha256_field", "commitment_row_count_field",
    }
    missing = required - set(spec)
    if missing:
        raise LargeDataAuditError(f"canonicalization missing fields: {sorted(missing)}")
    if list(spec["separators"]) != [",", ":"]:
        raise LargeDataAuditError(
            "only explicit compact JSON separators [',', ':'] are supported"
        )
    if str(spec["encoding"]).lower() != "utf-8":
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


def canonical_authority_object_sha256(authority: Mapping[str, Any]) -> str:
    """Canonical parsed-object digest; informational, NOT the frozen external binding."""
    raw = (
        json.dumps(
            authority, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        + "\n"
    ).encode("utf-8")
    return _sha256_bytes(raw)


def _source_sha256() -> str:
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except Exception:
        return "UNAVAILABLE"


def _safe_relpath(value: str) -> str:
    p = PurePosixPath(str(value))
    if p.is_absolute() or not p.parts or any(x in ("", ".", "..") for x in p.parts):
        raise LargeDataAuditError(
            f"unsafe/non-deterministic relative path: {value!r}"
        )
    if "\\" in str(value):
        raise LargeDataAuditError(
            f"relative paths must use '/' separators: {value!r}"
        )
    return p.as_posix()


def _valid_sha256(value: Any) -> bool:
    text = str(value)
    return (
        len(text) == 64
        and all(c in "0123456789abcdef" for c in text)
    )


def _scan_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for k, v in value.items():
            low = str(k).lower()
            if (
                low in _FORBIDDEN_REPORT_KEYS
                or any(
                    token in low
                    for token in ("token", "secret", "password", "private_key")
                )
            ):
                raise LargeDataAuditError(
                    f"forbidden sensitive key in transferable capsule at {path}.{k}"
                )
            _scan_forbidden_keys(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _scan_forbidden_keys(v, f"{path}[{i}]")


def validate_heartbeat_seconds(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise LargeDataAuditError(
            "heartbeat_seconds must be finite and greater than zero"
        )
    return value


def validate_authority(authority: Mapping[str, Any]) -> None:
    if authority.get("schema") != AUTHORITY_SCHEMA:
        raise LargeDataAuditError("unsupported dataset authority schema")
    for key in (
        "dataset_id", "dataset_version", "files", "canonicalization",
        "aggregate_commitment", "streams", "retention",
    ):
        if key not in authority:
            raise LargeDataAuditError(f"authority missing {key}")
    if authority["retention"].get("deletion_authorized") is not False:
        raise LargeDataAuditError(
            "large-data authority must be fail-closed on deletion"
        )

    canonical = authority["canonicalization"]
    canonical_json_bytes([], canonical)
    row_field = canonical["commitment_row_count_field"]

    files = authority["files"]
    if not isinstance(files, list) or not files:
        raise LargeDataAuditError("authority files must be a non-empty list")
    seen_paths, seen_ids = set(), set()
    for item in files:
        for key in (
            "identity", "relative_path", "byte_size", "sha256",
            "commitment_record",
        ):
            if key not in item:
                raise LargeDataAuditError(f"manifest item missing {key}")
        rel = _safe_relpath(item["relative_path"])
        identity = str(item["identity"])
        if rel in seen_paths or identity in seen_ids:
            raise LargeDataAuditError("duplicate relative_path or identity")
        seen_paths.add(rel)
        seen_ids.add(identity)
        if int(item["byte_size"]) < 0:
            raise LargeDataAuditError("negative byte_size")
        if not _valid_sha256(item["sha256"]):
            raise LargeDataAuditError(f"invalid SHA256 for {rel}")

        row_mode = str(item.get("row_count_mode", "NONE"))
        if row_mode not in _SUPPORTED_ROW_MODES:
            raise LargeDataAuditError(
                f"unsupported row_count_mode {row_mode!r} for {rel}"
            )
        if row_field is not None:
            if "row_count" not in item:
                raise LargeDataAuditError(
                    f"row_count required by canonicalization for {rel}"
                )
            if int(item["row_count"]) < 0:
                raise LargeDataAuditError(f"negative row_count for {rel}")
            if row_mode == "NONE":
                raise LargeDataAuditError(
                    f"row_count_mode must independently verify rows for {rel}"
                )

        rec = item["commitment_record"]
        sort_field = canonical["sort_field"]
        sha_field = canonical["commitment_sha256_field"]
        if sort_field not in rec:
            raise LargeDataAuditError(
                f"commitment_record missing sort field {sort_field}"
            )
        if sha_field not in rec:
            raise LargeDataAuditError(
                f"commitment_record missing SHA field {sha_field}"
            )
        if row_field is not None and row_field not in rec:
            raise LargeDataAuditError(
                f"commitment_record missing row-count field {row_field}"
            )

    aggregate = authority["aggregate_commitment"]
    for key in ("sha256", "file_count", "byte_total"):
        if key not in aggregate:
            raise LargeDataAuditError(f"aggregate_commitment missing {key}")
    if not _valid_sha256(aggregate["sha256"]):
        raise LargeDataAuditError("invalid aggregate commitment SHA256")
    if row_field is not None and "row_total" not in aggregate:
        raise LargeDataAuditError(
            "aggregate_commitment.row_total required when rows are applicable"
        )

    if not isinstance(authority["streams"], Mapping) or not authority["streams"]:
        raise LargeDataAuditError("authority streams must be a non-empty mapping")
    for name, spec in authority["streams"].items():
        for key in ("selector", "sha256", "file_count", "byte_total"):
            if key not in spec:
                raise LargeDataAuditError(f"stream {name} missing {key}")
        if not _valid_sha256(spec["sha256"]):
            raise LargeDataAuditError(f"invalid stream SHA256 for {name}")
        if row_field is not None and "row_total" not in spec:
            raise LargeDataAuditError(
                f"stream {name}.row_total required when rows are applicable"
            )


def _expected_commitment(
    items: Sequence[Mapping[str, Any]],
    canonicalization: Mapping[str, Any],
) -> str:
    sort_field = canonicalization["sort_field"]
    records = [x["commitment_record"] for x in items]
    records = sorted(records, key=lambda x: str(x[sort_field]))
    return _sha256_bytes(canonical_json_bytes(records, canonicalization))


def _matches_selector(
    item: Mapping[str, Any],
    selector: Mapping[str, Any],
) -> bool:
    field = selector.get("field")
    if not field:
        raise LargeDataAuditError("stream selector missing field")
    if "equals" in selector:
        return item.get(field) == selector["equals"]
    if "in" in selector:
        return item.get(field) in selector["in"]
    raise LargeDataAuditError("stream selector requires equals or in")


def _authority_internal_consistency(
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    """Check declared totals/commitments against the frozen per-file manifest itself."""
    entries = list(authority["files"])
    canonical = authority["canonicalization"]
    row_field = canonical["commitment_row_count_field"]
    errors: list[str] = []

    aggregate = authority["aggregate_commitment"]
    expected_files = len(entries)
    expected_bytes = sum(int(x["byte_size"]) for x in entries)
    expected_rows = (
        sum(int(x["row_count"]) for x in entries)
        if row_field is not None else None
    )
    expected_sha = _expected_commitment(entries, canonical)

    if int(aggregate["file_count"]) != expected_files:
        errors.append("aggregate file_count != per-file manifest count")
    if int(aggregate["byte_total"]) != expected_bytes:
        errors.append("aggregate byte_total != per-file manifest byte total")
    if row_field is not None and int(aggregate["row_total"]) != expected_rows:
        errors.append("aggregate row_total != per-file manifest row total")
    if aggregate["sha256"] != expected_sha:
        errors.append("aggregate sha256 != per-file commitment reconstruction")

    stream_details = {}
    for name, spec in sorted(authority["streams"].items()):
        subset = [x for x in entries if _matches_selector(x, spec["selector"])]
        files = len(subset)
        bytes_ = sum(int(x["byte_size"]) for x in subset)
        rows = (
            sum(int(x["row_count"]) for x in subset)
            if row_field is not None else None
        )
        sha = _expected_commitment(subset, canonical)
        stream_errors = []
        if int(spec["file_count"]) != files:
            stream_errors.append("file_count")
        if int(spec["byte_total"]) != bytes_:
            stream_errors.append("byte_total")
        if row_field is not None and int(spec["row_total"]) != rows:
            stream_errors.append("row_total")
        if spec["sha256"] != sha:
            stream_errors.append("sha256")
        if stream_errors:
            errors.append(
                f"stream {name} inconsistent fields: {','.join(stream_errors)}"
            )
        stream_details[name] = {
            "manifest_file_count": files,
            "manifest_byte_total": bytes_,
            "manifest_row_total": rows,
            "manifest_reconstructed_sha256": sha,
            "consistent": not stream_errors,
        }

    return {
        "pass": not errors,
        "errors": errors,
        "manifest_file_count": expected_files,
        "manifest_byte_total": expected_bytes,
        "manifest_row_total": expected_rows,
        "manifest_reconstructed_sha256": expected_sha,
        "streams": stream_details,
    }


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        return os.path.commonpath(
            [os.fspath(candidate), os.fspath(root)]
        ) == os.fspath(root)
    except ValueError:
        return False


def _resolved_manifest_paths(
    raw_root: Path,
    authority: Mapping[str, Any],
    *,
    require_existing: bool,
) -> set[Path]:
    paths: set[Path] = set()
    for item in authority["files"]:
        rel = _safe_relpath(item["relative_path"])
        path = raw_root.joinpath(*PurePosixPath(rel).parts)
        resolved = path.resolve(strict=require_existing)
        if not _is_within(resolved, raw_root):
            raise LargeDataAuditError(
                f"manifest path escapes RAW_ROOT after resolution: {rel}"
            )
        paths.add(resolved)
    return paths


def validate_output_path(
    raw_root: Path | str,
    authority_path: Path | str,
    output_path: Path | str,
    authority: Mapping[str, Any],
    *,
    require_output_absent: bool = True,
) -> Path:
    """Prove capsule output cannot target raw evidence or the authority."""
    root = Path(raw_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise LargeDataAuditError("RAW_ROOT is not a directory")
    auth = Path(authority_path).expanduser().resolve(strict=True)
    output_arg = Path(output_path).expanduser()
    output = output_arg.resolve(strict=False)

    if output == root or _is_within(output, root):
        raise LargeDataAuditError(
            "output must resolve outside RAW_ROOT and all descendants"
        )
    if output == auth:
        raise LargeDataAuditError("output must not equal the authority file")

    manifest_paths = _resolved_manifest_paths(
        root, authority, require_existing=False
    )
    if output in manifest_paths:
        raise LargeDataAuditError("output must not equal a manifest raw file")

    if require_output_absent and (output.exists() or output.is_symlink()):
        raise LargeDataAuditError(
            "output already exists; certified capsule creation is no-clobber"
        )
    return output


def load_authority_file(
    authority_path: Path | str,
    *,
    expected_file_sha256: str | None,
) -> tuple[dict[str, Any], str, str, str]:
    """Load authority and establish raw-file binding before any RAW_ROOT audit.

    The frozen external binding is SHA256 over the exact authority-file bytes.
    The canonical parsed-object SHA256 is separately recorded for diagnostics.
    """
    path = Path(authority_path).expanduser().resolve(strict=True)
    authority_bytes = path.read_bytes()
    file_sha = _sha256_bytes(authority_bytes)

    if expected_file_sha256 is not None:
        if not _valid_sha256(expected_file_sha256):
            raise LargeDataAuditError("invalid expected authority SHA256")
        if file_sha != expected_file_sha256:
            raise LargeDataAuditError(
                "authority file SHA256 mismatch before raw audit: "
                f"expected {expected_file_sha256}, got {file_sha}"
            )
        binding_state = "FROZEN_AUTHORITY_BOUND"
    else:
        binding_state = "UNBOUND_LOCAL_CHECK"

    authority = json.loads(authority_bytes)
    validate_authority(authority)
    canonical_sha = canonical_authority_object_sha256(authority)
    return authority, file_sha, canonical_sha, binding_state


def audit_dataset(
    raw_root: Path | str,
    authority: Mapping[str, Any],
    *,
    heartbeat_seconds: float = 5.0,
    verify_unexpected_files: bool = True,
    authority_file_sha256: str | None = None,
    expected_authority_file_sha256: str | None = None,
) -> dict[str, Any]:
    validate_authority(authority)
    heartbeat_seconds = validate_heartbeat_seconds(heartbeat_seconds)

    if (authority_file_sha256 is None) != (
        expected_authority_file_sha256 is None
    ):
        raise LargeDataAuditError(
            "authority binding requires both actual and expected file SHA256"
        )
    if authority_file_sha256 is not None:
        if not _valid_sha256(authority_file_sha256) or not _valid_sha256(
            expected_authority_file_sha256
        ):
            raise LargeDataAuditError("invalid authority binding SHA256")
        if authority_file_sha256 != expected_authority_file_sha256:
            raise LargeDataAuditError(
                "authority file SHA256 mismatch before raw audit"
            )
        binding_state = "FROZEN_AUTHORITY_BOUND"
    else:
        binding_state = "UNBOUND_LOCAL_CHECK"

    root = Path(raw_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise LargeDataAuditError(f"RAW_ROOT is not a directory: {root}")

    internal = _authority_internal_consistency(authority)
    entries = list(authority["files"])
    expected_paths = {_safe_relpath(x["relative_path"]) for x in entries}
    total_expected_bytes = sum(int(x["byte_size"]) for x in entries)
    canonical = authority["canonicalization"]
    row_field = canonical["commitment_row_count_field"]

    processed_bytes = 0
    started = time.monotonic()
    last_heartbeat = started
    results = []
    mismatch_count = 0
    missing_count = 0
    row_mismatch_count = 0

    for index, item in enumerate(
        sorted(entries, key=lambda x: _safe_relpath(x["relative_path"])), 1
    ):
        rel = _safe_relpath(item["relative_path"])
        unresolved = root.joinpath(*PurePosixPath(rel).parts)
        if not unresolved.exists():
            missing_count += 1
            mismatch_count += 1
            results.append({
                "identity": item["identity"],
                "relative_path": rel,
                "expected_bytes": int(item["byte_size"]),
                "actual_bytes": None,
                "expected_sha256": item["sha256"],
                "actual_sha256": None,
                "sha256_match": False,
                "byte_size_match": False,
                "expected_row_count": item.get("row_count"),
                "actual_row_count": None,
                "row_count_match": None,
                "state": "MISSING",
            })
            continue

        path = unresolved.resolve(strict=True)
        if not _is_within(path, root):
            raise LargeDataAuditError(
                f"manifest raw path escapes RAW_ROOT after resolution: {rel}"
            )
        if not path.is_file():
            raise LargeDataAuditError(f"manifest path is not a file: {rel}")

        row_mode = str(item.get("row_count_mode", "NONE"))
        count_lines = row_mode in (
            "CSV_DATA_ROWS_HEADER_ONE", "TEXT_LINES"
        )
        actual_sha, actual_bytes, line_count = sha256_file(
            path, count_lines=count_lines
        )
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
            raise LargeDataAuditError(
                f"unsupported row_count_mode {row_mode!r}"
            )

        if row_match is False:
            row_mismatch_count += 1
        ok = sha_match and bytes_match and row_match is not False
        if not ok:
            mismatch_count += 1
        results.append({
            "identity": item["identity"],
            "relative_path": rel,
            "expected_bytes": int(item["byte_size"]),
            "actual_bytes": actual_bytes,
            "expected_sha256": item["sha256"],
            "actual_sha256": actual_sha,
            "sha256_match": sha_match,
            "byte_size_match": bytes_match,
            "expected_row_count": item.get("row_count"),
            "actual_row_count": actual_rows,
            "row_count_match": row_match,
            "state": "PASS" if ok else "MISMATCH",
        })

        now = time.monotonic()
        if (
            index == 1
            or index == len(entries)
            or now - last_heartbeat >= heartbeat_seconds
        ):
            elapsed = max(0.001, now - started)
            rate = processed_bytes / elapsed
            remaining = max(0, total_expected_bytes - processed_bytes)
            eta = remaining / rate if rate > 0 else None
            print(
                f"[LARGE-DATA AUDIT] {index}/{len(entries)} files | "
                f"{processed_bytes}/{total_expected_bytes} bytes | "
                f"{100.0 * processed_bytes / max(1, total_expected_bytes):.2f}% | "
                f"ETA {'?' if eta is None else f'{eta / 60.0:.1f}m'}"
            )
            last_heartbeat = now

    unexpected = []
    if verify_unexpected_files:
        for p in root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                if rel not in expected_paths:
                    unexpected.append(rel)

    result_by_identity = {
        str(x["identity"]): x for x in results
    }
    actual_entries = []
    for item in entries:
        result = result_by_identity[str(item["identity"])]
        if result["actual_sha256"] is None:
            continue
        actual_item = json.loads(json.dumps(item))
        actual_item["byte_size"] = int(result["actual_bytes"])
        actual_item["sha256"] = result["actual_sha256"]
        actual_item["commitment_record"][
            canonical["commitment_sha256_field"]
        ] = result["actual_sha256"]
        if (
            row_field is not None
            and result["actual_row_count"] is not None
        ):
            actual_item["row_count"] = int(result["actual_row_count"])
            actual_item["commitment_record"][row_field] = int(
                result["actual_row_count"]
            )
        actual_entries.append(actual_item)

    aggregate = authority["aggregate_commitment"]
    aggregate_expected_sha = aggregate["sha256"]
    aggregate_actual_sha = (
        _expected_commitment(actual_entries, canonical)
        if len(actual_entries) == len(entries)
        else None
    )
    aggregate_sha_match = aggregate_actual_sha == aggregate_expected_sha

    aggregate_actual_files = len(actual_entries)
    aggregate_expected_files = int(aggregate["file_count"])
    aggregate_file_count_match = (
        aggregate_actual_files == aggregate_expected_files
    )
    aggregate_actual_bytes = sum(
        int(x["byte_size"]) for x in actual_entries
    )
    aggregate_expected_bytes = int(aggregate["byte_total"])
    aggregate_byte_total_match = (
        aggregate_actual_bytes == aggregate_expected_bytes
    )

    if row_field is not None:
        aggregate_actual_rows = sum(
            int(x["row_count"]) for x in actual_entries
        )
        aggregate_expected_rows = int(aggregate["row_total"])
        aggregate_row_total_match = (
            len(actual_entries) == len(entries)
            and aggregate_actual_rows == aggregate_expected_rows
        )
    else:
        aggregate_actual_rows = None
        aggregate_expected_rows = None
        aggregate_row_total_match = True

    stream_results = {}
    stream_failures = 0
    for name, spec in sorted(authority["streams"].items()):
        subset = [
            x for x in actual_entries
            if _matches_selector(x, spec["selector"])
        ]
        expected_files = int(spec["file_count"])
        actual_sha = (
            _expected_commitment(subset, canonical)
            if len(subset) == expected_files
            else None
        )
        file_count = len(subset)
        byte_total = sum(int(x["byte_size"]) for x in subset)
        rows = (
            sum(int(x["row_count"]) for x in subset)
            if row_field is not None else None
        )
        expected_rows = (
            int(spec["row_total"])
            if row_field is not None else None
        )
        ok = (
            actual_sha == spec["sha256"]
            and file_count == expected_files
            and byte_total == int(spec["byte_total"])
            and (
                row_field is None
                or rows == expected_rows
            )
        )
        if not ok:
            stream_failures += 1
        stream_results[name] = {
            "file_count": file_count,
            "expected_file_count": expected_files,
            "byte_total": byte_total,
            "expected_byte_total": int(spec["byte_total"]),
            "row_total": rows,
            "expected_row_total": expected_rows,
            "reconstructed_sha256_from_rehashed_raw": actual_sha,
            "expected_sha256": spec["sha256"],
            "match": ok,
        }

    data_checks_pass = (
        internal["pass"]
        and mismatch_count == 0
        and missing_count == 0
        and row_mismatch_count == 0
        and not unexpected
        and aggregate_sha_match
        and aggregate_file_count_match
        and aggregate_byte_total_match
        and aggregate_row_total_match
        and stream_failures == 0
    )
    certified_pass = (
        data_checks_pass
        and binding_state == "FROZEN_AUTHORITY_BOUND"
    )
    status = (
        "FROZEN_AUTHORITY_BOUND_PASS"
        if certified_pass
        else "UNBOUND_LOCAL_CHECK"
        if data_checks_pass
        else "FAIL_CLOSED"
    )

    report = {
        "schema": REPORT_SCHEMA,
        "status": status,
        "certified_pass": certified_pass,
        "dataset_id": authority["dataset_id"],
        "dataset_version": authority["dataset_version"],
        "authority_binding": {
            "state": binding_state,
            "frozen_external_binding_semantics": (
                "SHA256_OVER_EXACT_AUTHORITY_FILE_BYTES"
            ),
            "authority_file_sha256": authority_file_sha256,
            "expected_authority_file_sha256": expected_authority_file_sha256,
            "authority_canonical_object_sha256": (
                canonical_authority_object_sha256(authority)
            ),
            "canonical_object_digest_is_external_binding": False,
        },
        "authority_internal_consistency": internal,
        "verifier": {
            "version": TOOL_VERSION,
            "source_sha256": _source_sha256(),
        },
        "raw_storage_location_is_identity": False,
        "raw_bytes_transferred_in_capsule": False,
        "raw_files_expected": len(entries),
        "raw_files_hashed": sum(
            x["actual_sha256"] is not None for x in results
        ),
        "raw_bytes_expected": total_expected_bytes,
        "raw_bytes_read_and_hashed": sum(
            int(x["actual_bytes"] or 0) for x in results
        ),
        "missing_count": missing_count,
        "unexpected_count": len(unexpected),
        "unexpected_paths": sorted(unexpected),
        "file_mismatch_count": mismatch_count,
        "row_mismatch_count": row_mismatch_count,
        "aggregate_commitment": {
            "expected_sha256": aggregate_expected_sha,
            "reconstructed_sha256": aggregate_actual_sha,
            "sha256_match": aggregate_sha_match,
            "expected_file_count": aggregate_expected_files,
            "actual_file_count": aggregate_actual_files,
            "file_count_match": aggregate_file_count_match,
            "expected_byte_total": aggregate_expected_bytes,
            "actual_byte_total": aggregate_actual_bytes,
            "byte_total_match": aggregate_byte_total_match,
            "expected_row_total": aggregate_expected_rows,
            "actual_row_total": aggregate_actual_rows,
            "row_total_match": aggregate_row_total_match,
            "match": (
                aggregate_sha_match
                and aggregate_file_count_match
                and aggregate_byte_total_match
                and aggregate_row_total_match
            ),
            "canonicalization": canonical,
        },
        "streams": stream_results,
        "per_file_results": results,
        "retention": {
            "raw_bytes_remain_user_controlled": True,
            "deletion_authorized": False,
        },
        "provenance_commitment_sha256": _sha256_bytes(
            (
                json.dumps(
                    authority.get("provenance", {}),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8")
        ),
    }
    _scan_forbidden_keys(report)
    return report


def _capsule_bytes(report: Mapping[str, Any]) -> bytes:
    payload = (
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        + "\n"
    ).encode("utf-8")
    report_sha = _sha256_bytes(payload)
    checksums = f"{report_sha}  AUDIT_REPORT.json\n".encode("ascii")

    buf = io.BytesIO()
    with zipfile.ZipFile(
        buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for name, data in (
            ("AUDIT_REPORT.json", payload),
            ("CHECKSUMS.sha256", checksums),
        ):
            info = zipfile.ZipInfo(
                name, date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data)
    return buf.getvalue()


def write_capsule(
    report: Mapping[str, Any],
    output_zip: Path | str,
    *,
    raw_root: Path | str,
    authority_path: Path | str,
    authority: Mapping[str, Any],
) -> str:
    """Write capsule with defense-in-depth path safety and exclusive no-clobber."""
    output = validate_output_path(
        raw_root, authority_path, output_zip, authority,
        require_output_absent=True,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output = validate_output_path(
        raw_root, authority_path, output, authority,
        require_output_absent=True,
    )

    data = _capsule_bytes(report)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(os.fspath(output), flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fd = -1
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        if fd >= 0:
            os.close(fd)
        try:
            output.unlink()
        except OSError:
            pass
        raise
    return _sha256_bytes(data)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", required=True)
    ap.add_argument("--authority", required=True)
    ap.add_argument(
        "--authority-sha256",
        help=(
            "Frozen SHA256 over exact authority-file bytes. If omitted, "
            "a successful audit is UNBOUND_LOCAL_CHECK, not certified PASS."
        ),
    )
    ap.add_argument("--output", required=True)
    ap.add_argument("--heartbeat-seconds", type=float, default=5.0)
    args = ap.parse_args(argv)

    heartbeat = validate_heartbeat_seconds(args.heartbeat_seconds)
    raw_root = Path(args.raw_root).expanduser().resolve(strict=True)
    authority_path = Path(args.authority).expanduser().resolve(strict=True)

    authority, authority_file_sha, canonical_sha, binding_state = (
        load_authority_file(
            authority_path,
            expected_file_sha256=args.authority_sha256,
        )
    )
    # Path safety is proven before any raw audit starts.
    output = validate_output_path(
        raw_root, authority_path, args.output, authority,
        require_output_absent=True,
    )

    report = audit_dataset(
        raw_root,
        authority,
        heartbeat_seconds=heartbeat,
        authority_file_sha256=(
            authority_file_sha
            if binding_state == "FROZEN_AUTHORITY_BOUND"
            else None
        ),
        expected_authority_file_sha256=(
            args.authority_sha256
            if binding_state == "FROZEN_AUTHORITY_BOUND"
            else None
        ),
    )
    if (
        report["authority_binding"]["authority_canonical_object_sha256"]
        != canonical_sha
    ):
        raise LargeDataAuditError(
            "internal authority canonical-object digest inconsistency"
        )

    capsule_sha = write_capsule(
        report,
        output,
        raw_root=raw_root,
        authority_path=authority_path,
        authority=authority,
    )
    print(f"CAPSULE_SHA256={capsule_sha}")
    print(f"STATUS={report['status']}")
    print(
        "AUTHORITY_FILE_SHA256="
        f"{report['authority_binding']['authority_file_sha256']}"
    )
    print(
        "AUTHORITY_CANONICAL_OBJECT_SHA256="
        f"{report['authority_binding']['authority_canonical_object_sha256']}"
    )
    return 2 if report["status"] == "FAIL_CLOSED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
