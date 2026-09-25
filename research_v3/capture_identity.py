"""Transport-independent evidence identity for repack-safe research captures.

Canonical payload bytes + CAPTURE_MANIFEST.json semantics define evidence identity.
Outer ZIP bytes are transport provenance only and may change when Android, Drive,
file managers, or chat upload systems repack an otherwise identical capture.
"""
from __future__ import annotations
import hashlib, json, re, zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping

MANIFEST_NAME="CAPTURE_MANIFEST.json"
MANIFEST_SCHEMA="mxm.greenfield.capture-manifest.v1"
_SECRET_KEY_RE=re.compile(rb'(?i)"(?:access_?token|refresh_?token|client_?secret|authorization)"\s*:')
_SECRET_VALUE_PATTERNS=(
    re.compile(rb'gh[pousr]_[A-Za-z0-9_]{20,}'),
    re.compile(rb'(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}'),
    re.compile(rb'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
)

class CaptureIdentityError(RuntimeError):
    pass

def sha256_bytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path:str|Path)->str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def canonical_json_bytes(value:Any)->bytes:
    return (json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()

def scan_bytes_for_secrets(data:bytes, *, secret_literals:Iterable[str]=())->None:
    if _SECRET_KEY_RE.search(data):
        raise CaptureIdentityError("transfer bundle contains a credential-like JSON key")
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(data):
            raise CaptureIdentityError("transfer bundle contains a credential-like value")
    for secret in secret_literals:
        if secret and secret.encode() in data:
            raise CaptureIdentityError("transfer bundle contains supplied secret literal")

def inspect_transfer_zip(
    path:str|Path,
    *,
    logical_payload_name:str,
    expected_payload_sha256:str|None=None,
    expected_schema:str|None=None,
    expected_status:str|None=None,
    secret_literals:Iterable[str]=(),
)->dict[str,Any]:
    path=Path(path)
    transport_sha=sha256_file(path)
    with zipfile.ZipFile(path) as z:
        regular=[i for i in z.infolist() if not i.is_dir()]
        if not regular:
            raise CaptureIdentityError("transfer ZIP has no files")
        all_files=[]
        candidates=[]
        for info in regular:
            data=z.read(info)
            scan_bytes_for_secrets(data,secret_literals=secret_literals)
            row={"path":info.filename,"sha256":sha256_bytes(data),"size_bytes":len(data)}
            all_files.append(row)
            if Path(info.filename).name==logical_payload_name:
                candidates.append((info.filename,data,row["sha256"]))
        if not candidates:
            raise CaptureIdentityError(f"canonical payload missing: {logical_payload_name}")
        hashes={x[2] for x in candidates}
        byte_values={x[1] for x in candidates}
        if len(hashes)!=1 or len(byte_values)!=1:
            raise CaptureIdentityError("conflicting duplicate canonical payloads")
        payload_path,payload_bytes,payload_sha=candidates[0]
        if expected_payload_sha256 and payload_sha!=expected_payload_sha256:
            raise CaptureIdentityError(
                f"canonical payload SHA256 mismatch: {payload_sha} != {expected_payload_sha256}"
            )
        try:
            payload=json.loads(payload_bytes)
        except Exception as exc:
            raise CaptureIdentityError("canonical payload is not valid JSON") from exc
        if expected_schema and payload.get("schema")!=expected_schema:
            raise CaptureIdentityError("canonical payload schema mismatch")
        if expected_status and payload.get("status")!=expected_status:
            raise CaptureIdentityError("canonical payload completion state mismatch")
        unknown=[x for x in all_files if Path(x["path"]).name not in {logical_payload_name,MANIFEST_NAME}]
        return {
            "transport_sha256":transport_sha,
            "logical_payload_name":logical_payload_name,
            "canonical_payload_sha256":payload_sha,
            "candidate_payload_paths":[x[0] for x in candidates],
            "candidate_payload_count":len(candidates),
            "duplicate_payloads_byte_identical":True,
            "canonical_payload_path_selected":payload_path,
            "canonical_payload_size_bytes":len(payload_bytes),
            "payload":payload,
            "unknown_extra_files_inspected":unknown,
            "all_regular_files":all_files,
        }

def build_capture_manifest(
    *,
    capture_session_id:str,
    capture_schema:str,
    tool_version:str,
    account_fingerprint:str,
    source_environment:str,
    capture_start_utc:str,
    capture_end_utc:str,
    completion_state:str,
    canonical_payloads:Mapping[str,bytes],
    original_collector_package_sha256:str|None,
    read_only_assertion:bool,
    economic_outcomes_opened:int,
    orders_placed:bool,
    account_mutation:bool,
    protected_evidence_opened:bool,
)->dict[str,Any]:
    if completion_state!="COMPLETE":
        raise CaptureIdentityError("only COMPLETE captures may receive authoritative manifests")
    if not canonical_payloads:
        raise CaptureIdentityError("manifest requires at least one canonical payload")
    for rel in canonical_payloads:
        if Path(str(rel)).name.casefold()==MANIFEST_NAME.casefold():
            raise CaptureIdentityError(
                "canonical payload filename collides case-insensitively with CAPTURE_MANIFEST.json"
            )
    return {
        "schema":MANIFEST_SCHEMA,
        "capture_session_id":capture_session_id,
        "capture_schema":capture_schema,
        "tool_version":tool_version,
        "account_fingerprint":account_fingerprint,
        "source_environment":source_environment,
        "capture_start_utc":capture_start_utc,
        "capture_end_utc":capture_end_utc,
        "completion_state":completion_state,
        "canonical_payload_paths":sorted(canonical_payloads),
        "sha256_per_canonical_payload":{
            p:sha256_bytes(canonical_payloads[p]) for p in sorted(canonical_payloads)
        },
        "original_collector_package_sha256":original_collector_package_sha256,
        "read_only_assertion":bool(read_only_assertion),
        "economic_outcomes_opened":int(economic_outcomes_opened),
        "orders_placed":bool(orders_placed),
        "account_mutation":bool(account_mutation),
        "protected_evidence_opened":bool(protected_evidence_opened),
        "evidence_identity_law":"CANONICAL_PAYLOAD_HASHES_PLUS_MANIFEST_SEMANTICS; OUTER_TRANSPORT_ZIP_HASH_EXCLUDED",
    }

def evidence_identity(manifest:Mapping[str,Any])->str:
    if manifest.get("schema")!=MANIFEST_SCHEMA:
        raise CaptureIdentityError("unsupported capture manifest schema")
    identity={
        "capture_session_id":manifest.get("capture_session_id"),
        "capture_schema":manifest.get("capture_schema"),
        "tool_version":manifest.get("tool_version"),
        "account_fingerprint":manifest.get("account_fingerprint"),
        "source_environment":manifest.get("source_environment"),
        "capture_start_utc":manifest.get("capture_start_utc"),
        "capture_end_utc":manifest.get("capture_end_utc"),
        "completion_state":manifest.get("completion_state"),
        "canonical_payload_paths":manifest.get("canonical_payload_paths"),
        "sha256_per_canonical_payload":manifest.get("sha256_per_canonical_payload"),
        "read_only_assertion":manifest.get("read_only_assertion"),
        "economic_outcomes_opened":manifest.get("economic_outcomes_opened"),
        "orders_placed":manifest.get("orders_placed"),
        "account_mutation":manifest.get("account_mutation"),
        "protected_evidence_opened":manifest.get("protected_evidence_opened"),
    }
    return sha256_bytes(canonical_json_bytes(identity))
