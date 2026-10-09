"""Fail-closed allowlist for new MASTER1576 public status JSON blobs.

This is deliberately NOT a general-purpose JSON sanitizer: the caller must
select a versioned, explicitly approved schema; every field and its value is
checked before blob creation. Sensitive scientific material goes only to
separately authorized encrypted storage, never through this function.
"""
import json
import re
from pathlib import PurePosixPath


class PublicDisclosureDenied(ValueError):
    pass


SCHEMA = "mxm.master1576.public.status.v1"
FIELDS = frozenset({
    "schema", "phase", "status", "source_head", "scientific_design_sha256",
    "worker_sha256", "input_manifest_sha256", "run_id", "job_id",
    "encrypted_artifact_sha256", "encrypted_artifact_name",
    "resource_cpu_seconds", "resource_wall_seconds",
    "resource_peak_ram_kib", "identity_count", "input_shard_count",
    "failure_code",
})
REQUIRED = frozenset({"schema", "phase", "status", "source_head"})
ENUM = {
    "phase": frozenset({"SECURITY_PREFLIGHT", "SYNTHETIC", "ARM_GATE",
                         "NUMERIC_DEVELOPMENT", "PUBLICATION", "FINAL"}),
    "status": frozenset({"PASS", "FAIL_CLOSED", "BLOCKED", "NOT_RUN",
                          "NOT_AUTHORIZED", "NOT_PERSISTED"}),
    "failure_code": frozenset({
        "NONE", "SOURCE_DRIFT", "ENCRYPTION_FAILURE",
        "PUBLIC_OUTPUT_REJECTED", "READBACK_FAILURE", "SCIENTIFIC_GATE",
        "RESOURCE_BUDGET", "MISSING_INDEPENDENT_APPROVAL", "UNSUPPORTED",
        "INTEGRITY_FAILURE", "DUPLICATE_INVOCATION",
    }),
}
HASHES = frozenset({
    "source_head", "scientific_design_sha256", "worker_sha256",
    "input_manifest_sha256", "encrypted_artifact_sha256",
})
INTEGERS = frozenset({"run_id", "job_id", "identity_count", "input_shard_count",
                       "resource_peak_ram_kib"})
NUMERICS = frozenset({"resource_cpu_seconds", "resource_wall_seconds"})
ROOT = "research_core_v4/numeric_development_v1/public_status/"


def validate_public_blob(path, document):
    """Return UTF-8 bytes only on an exact allowlist match; raise otherwise."""
    if not isinstance(path, str) or not path.startswith(ROOT):
        raise PublicDisclosureDenied("OUTPUT_DIRECTORY_DENIED")
    relative = path[len(ROOT):]
    if (not relative or "/" in relative or "\\" in relative or
            not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}_V1\.json", relative)):
        raise PublicDisclosureDenied("OUTPUT_PATH_DENIED")
    if type(document) is not dict:
        raise PublicDisclosureDenied("PUBLIC_ROOT_NOT_OBJECT")
    keys = set(document)
    if not REQUIRED.issubset(keys) or not keys.issubset(FIELDS):
        raise PublicDisclosureDenied("PUBLIC_FIELDS_NOT_ALLOWLISTED")
    if document.get("schema") != SCHEMA:
        raise PublicDisclosureDenied("PUBLIC_SCHEMA_UNAPPROVED")
    for key, value in document.items():
        if key in ENUM:
            if type(value) is not str or value not in ENUM[key]:
                raise PublicDisclosureDenied("PUBLIC_ENUM_DENIED")
        elif key in HASHES:
            if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64 if key != 'source_head' else 40}", value):
                # source_head is a Git SHA-1, other digests are SHA-256
                raise PublicDisclosureDenied("PUBLIC_DIGEST_DENIED")
        elif key == "encrypted_artifact_name":
            if type(value) is not str or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,95}\.mxmenc", value):
                raise PublicDisclosureDenied("PUBLIC_ENCRYPTED_ASSET_NAME_DENIED")
        elif key in INTEGERS:
            if type(value) is not int or value < 0 or value > 10**14:
                raise PublicDisclosureDenied("PUBLIC_INTEGER_DENIED")
        elif key in NUMERICS:
            if type(value) not in (int, float) or not 0 <= value <= 10**8:
                raise PublicDisclosureDenied("PUBLIC_RESOURCE_DENIED")
        elif key == "schema":
            pass
        else:
            raise PublicDisclosureDenied("PUBLIC_UNKNOWN_FIELD")
    if document.get("identity_count") not in (None, 1576):
        raise PublicDisclosureDenied("PUBLIC_FRONTIER_DRIFT")
    if document.get("input_shard_count") not in (None, 100):
        raise PublicDisclosureDenied("PUBLIC_SHARD_COUNT_DRIFT")
    raw = (json.dumps(document, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > 4096:
        raise PublicDisclosureDenied("PUBLIC_SIZE_DENIED")
    return raw


def safe_public_git_blob(path, document, create_blob):
    """Only call the supplied Git blob API after validation has succeeded."""
    raw = validate_public_blob(path, document)
    return create_blob(raw)
