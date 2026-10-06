"""Hash-bound production acquisition runner for BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2.

This module is inert unless a separately-created exact ARM exists.  The production
history path deliberately never calls the legacy parsed ProtoOAGetTrendbarsRes path:
it retains the raw ProtoMessage envelope and decodes payload bytes with the accepted
V2 current protocol descriptor before accepting any row.

No token refresh, ticks, spot subscriptions, depth, orders, or account mutation are
implemented.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from research_core_v4 import shallow_m5_support_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
REPO = "mariancradulescu/mxm-quant-greenfield"
BRANCH = "performance-research-v3-20260922"

ARM_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V1.json"
RUNNER_REL = "research_core_v4/shallow_m5_support_v2_production.py"
WORKFLOW_REL = ".github/workflows/breadth-first-shallow-m5-support-v2-production.yml"
ARCH_FREEZE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_MACHINE_SIDE_PRODUCTION_ARCHITECTURE_FREEZE_V1.json"
ACCEPTANCE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json"
OUTPUT_AUTH_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_OUTPUT_TRANSPORT_AUTHORITY_V1.json"
PROTOCOL_FREEZE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PREARM_PROTOCOL_DECODER_FREEZE.json"
DIGITS_MAP_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_SYMBOL_DIGITS_MAP.json"
PUBLIC_KEY_REL = "research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"

PROTOCOL_FREEZE_SHA256 = "aae769ffb41f8e29e978305ba2e6b85395f70d3c5c4c9b9780a56e601489d98c"
V2_IMPLEMENTATION_SHA256 = "7ee289e2c2abaa48cdde334689308165aa6a81fc31d271104da9b2f47f6f9d1e"
DIGITS_MAP_FILE_SHA256 = "2a8f29795ba49f3a79e96fb2bf9cf6d7f2e5f880d736cd7ba4726ff729feab4a"
CANONICAL_DIGITS_MAP_SHA256 = "4657c1cea348479afa198b005ae1da3b3f788fb2b33bd2c35f07034bfba2ce7a"
MASTER_SHA256 = "2287445f9b8dbd61ef40a1d81756e1848c2b623a846bc968c4e214d9b2a874e1"
ACCOUNT_FINGERPRINT_SHA256 = "b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636"
PUBLIC_SPKI_SHA256 = "464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"

SEGMENTS = (
    ("2026-08-20T00:00:00Z", "2026-08-26T23:55:00Z"),
    ("2026-08-27T00:00:00Z", "2026-09-02T23:55:00Z"),
    ("2026-09-03T00:00:00Z", "2026-09-09T23:55:00Z"),
    ("2026-09-10T00:00:00Z", "2026-09-16T23:55:00Z"),
)
MASTER_COUNT = 1576
IDENTITIES_PER_SHARD = 64
SHARD_COUNT_PER_SEGMENT = 25
MAX_PAGES = 3
RETRY_CAP_AFTER_INITIAL = 2
MAX_WIRE_ATTEMPTS_PER_PAGE = 3
RATE_LIMIT_RPS = 4
MIN_INTER_REQUEST_SECONDS = 0.25
HEARTBEAT_MAX_IDLE_SECONDS = 10
SOFT_STOP_MINUTES = 270
GITHUB_JOB_TIMEOUT_MINUTES = 330
SHUTDOWN_UPLOAD_MARGIN_MINUTES = 60
PACKAGE_MAGIC = b"MXM_SHALLOW_M5_V2_ENC1\x00"

ALLOWED_OUTBOUND_MESSAGE_NAMES = frozenset(
    {
        "ProtoOAApplicationAuthReq",
        "ProtoOAGetAccountListByAccessTokenReq",
        "ProtoOAAccountAuthReq",
        "ProtoOAGetTrendbarsReq",
        "ProtoHeartbeatEvent",
    }
)
FORBIDDEN_OUTBOUND_MESSAGE_NAMES = frozenset(
    {
        "ProtoOAGetTickDataReq",
        "ProtoOASubscribeSpotsReq",
        "ProtoOASubscribeDepthQuotesReq",
        "ProtoOANewOrderReq",
        "ProtoOAClosePositionReq",
        "ProtoOACancelOrderReq",
        "ProtoOAAmendOrderReq",
        "ProtoOARefreshTokenReq",
    }
)
SYSTEMIC_CODES = frozenset(
    {
        "TOKEN_INVALID_OR_EXPIRED",
        "SCOPE_NOT_EXPLICIT_VIEW",
        "ACCOUNT_FINGERPRINT_MISMATCH",
        "ACCOUNT_NOT_LIVE",
        "ACCOUNT_AUTH_MISMATCH",
        "REQUEST_FREQUENCY_EXCEEDED",
        "RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE",
        "PROTECTED_FORWARD_LEAK",
        "HASH_BOUND_IMPLEMENTATION_MISMATCH",
        "DIGITS_MAP_MISMATCH",
        "MASTER1576_MISMATCH",
        "DURABLE_STORAGE_INTEGRITY_FAILURE",
    }
)


class CaptureError(RuntimeError):
    pass


class SystemicFailure(CaptureError):
    def __init__(self, code: str):
        if code not in SYSTEMIC_CODES:
            code = "RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE"
        self.code = code
        super().__init__(code)


class TransientPageFailure(CaptureError):
    pass


class SoftStop(CaptureError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CaptureError(f"object required: {path}")
    return value


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(canonical_json_bytes(value) + b"\n")
    os.replace(tmp, path)


def require_file_hash(rel: str, expected: str, code: str) -> None:
    path = ROOT / rel
    if not path.is_file() or sha256_file(path) != expected:
        raise SystemicFailure(code)


def public_spki_sha256(public_key: Path = ROOT / PUBLIC_KEY_REL) -> str:
    run = subprocess.run(
        ["openssl", "pkey", "-pubin", "-in", str(public_key), "-outform", "DER"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return sha256_bytes(run.stdout)


def validate_static_bindings() -> dict:
    require_file_hash(PROTOCOL_FREEZE_REL, PROTOCOL_FREEZE_SHA256, "HASH_BOUND_IMPLEMENTATION_MISMATCH")
    require_file_hash("research_core_v4/shallow_m5_support_v2.py", V2_IMPLEMENTATION_SHA256, "HASH_BOUND_IMPLEMENTATION_MISMATCH")
    require_file_hash(DIGITS_MAP_REL, DIGITS_MAP_FILE_SHA256, "DIGITS_MAP_MISMATCH")
    master = v2.load_master(ROOT)
    if len(master) != MASTER_COUNT:
        raise SystemicFailure("MASTER1576_MISMATCH")
    digits = load_json(ROOT / DIGITS_MAP_REL)
    if digits.get("digits_map_sha256") != CANONICAL_DIGITS_MAP_SHA256:
        raise SystemicFailure("DIGITS_MAP_MISMATCH")
    lookup = v2.digits_lookup(digits)
    if len(lookup) != MASTER_COUNT:
        raise SystemicFailure("DIGITS_MAP_MISMATCH")
    if public_spki_sha256() != PUBLIC_SPKI_SHA256:
        raise SystemicFailure("HASH_BOUND_IMPLEMENTATION_MISMATCH")
    return {"master": master, "digits": lookup}


def production_plan() -> dict:
    return {
        "master_count": MASTER_COUNT,
        "segments": [list(x) for x in SEGMENTS],
        "exact_segment_jobs": 4,
        "strict_job_order": ["segment-1", "segment-2", "segment-3", "segment-4"],
        "identities_per_shard": IDENTITIES_PER_SHARD,
        "shard_count_per_segment": SHARD_COUNT_PER_SEGMENT,
        "page_cap": MAX_PAGES,
        "retry_cap_after_initial": RETRY_CAP_AFTER_INITIAL,
        "wire_attempts_per_page": MAX_WIRE_ATTEMPTS_PER_PAGE,
        "rate_limit_rps": RATE_LIMIT_RPS,
        "min_inter_request_seconds": MIN_INTER_REQUEST_SECONDS,
        "heartbeat_max_idle_seconds": HEARTBEAT_MAX_IDLE_SECONDS,
        "soft_stop_minutes": SOFT_STOP_MINUTES,
        "github_job_timeout_minutes": GITHUB_JOB_TIMEOUT_MINUTES,
        "reserved_shutdown_upload_margin_minutes": SHUTDOWN_UPLOAD_MARGIN_MINUTES,
        "one_active_live_historical_connection_globally": True,
        "concurrent_historical_connections": 0,
        "allowed_outbound_messages": sorted(ALLOWED_OUTBOUND_MESSAGE_NAMES),
        "forbidden_outbound_messages": sorted(FORBIDDEN_OUTBOUND_MESSAGE_NAMES),
    }


def _expected_arm_bindings() -> dict:
    return {
        "V2_PROTOCOL_DECODER_FREEZE_SHA256": PROTOCOL_FREEZE_SHA256,
        "V2_IMPLEMENTATION_SHA256": V2_IMPLEMENTATION_SHA256,
        "V2_DIGITS_MAP_SHA256": DIGITS_MAP_FILE_SHA256,
        "MASTER1576_SHA256": MASTER_SHA256,
        "AUTH_V3_ACCOUNT_FINGERPRINT_SHA256": ACCOUNT_FINGERPRINT_SHA256,
        "FOUR_SEGMENT_GEOMETRY": [list(x) for x in SEGMENTS],
        "PAGE_CAP_3": MAX_PAGES,
        "RETRY_CAP_2_AFTER_INITIAL": RETRY_CAP_AFTER_INITIAL,
        "RATE_LIMIT_4RPS": RATE_LIMIT_RPS,
        "OUTPUT_ENCRYPTION_AUTHORITY_SHA256": sha256_file(ROOT / OUTPUT_AUTH_REL),
        "PRODUCTION_RUNNER_SHA256": sha256_file(ROOT / RUNNER_REL),
        "PRODUCTION_WORKFLOW_SHA256": sha256_file(ROOT / WORKFLOW_REL),
        "ARCHITECTURE_FREEZE_SHA256": sha256_file(ROOT / ARCH_FREEZE_REL),
        "ACCEPTANCE_AUTHORITY_SHA256": sha256_file(ROOT / ACCEPTANCE_REL),
    }


def validate_arm(arm_path: Path = ROOT / ARM_REL) -> dict:
    if not arm_path.is_file():
        raise PermissionError("PRODUCTION_ARM_ABSENT")
    arm = load_json(arm_path)
    if arm.get("schema") != "mxm.v4.breadth-first-shallow-m5-support-v2.production-arm.v1":
        raise PermissionError("WRONG_ARM_SCHEMA")
    if arm.get("status") != "ARMED_NOT_EXECUTED":
        raise PermissionError("WRONG_ARM_STATUS")
    expected = _expected_arm_bindings()
    bound = arm.get("bindings")
    if bound != expected:
        raise PermissionError("ARM_HASH_OR_PLAN_BINDING_MISMATCH")
    release = arm.get("durable_release_identity")
    if not isinstance(release, str) or not release.startswith("mxm-shallow-m5-v2-"):
        raise PermissionError("INVALID_DURABLE_RELEASE_IDENTITY")
    source = arm.get("exact_source_head")
    if not isinstance(source, str) or len(source) != 40:
        raise PermissionError("INVALID_EXACT_SOURCE_HEAD")
    return arm


def validate_arm_git_event(arm: Mapping[str, Any]) -> None:
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if os.environ.get("GITHUB_SHA") and os.environ["GITHUB_SHA"] != head:
        raise PermissionError("GITHUB_SHA_MISMATCH")
    parents = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-list", "--parents", "-n", "1", "HEAD"], text=True
    ).split()
    if len(parents) != 2 or parents[1] != arm.get("exact_source_head"):
        raise PermissionError("ARM_PARENT_MISMATCH")
    changed = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        text=True,
    ).splitlines()
    if changed != [ARM_REL]:
        raise PermissionError("ARM_COMMIT_MUST_CHANGE_ONLY_EXACT_ARM_FILE")


class RateLimiter:
    def __init__(
        self,
        min_interval: float = MIN_INTER_REQUEST_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.min_interval = float(min_interval)
        self.clock = clock
        self.sleeper = sleeper
        self.last = None

    def before_send(self) -> None:
        now = self.clock()
        if self.last is not None:
            delay = self.min_interval - (now - self.last)
            if delay > 0:
                self.sleeper(delay)
        self.last = self.clock()


def _fingerprint(account_id: int) -> str:
    return hashlib.sha256(f"ctrader-account:{int(account_id)}".encode("ascii")).hexdigest()


def authenticate_segment(transport, client_id: str, client_secret: str, access_token: str) -> int:
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from m6.ctrader_proto import OpenApiModelMessages_pb2 as e

    app = transport.request(m.ProtoOAApplicationAuthReq(clientId=client_id, clientSecret=client_secret), timeout=20)
    if not isinstance(app, m.ProtoOAApplicationAuthRes):
        raise SystemicFailure("TOKEN_INVALID_OR_EXPIRED")

    accounts = transport.request(m.ProtoOAGetAccountListByAccessTokenReq(accessToken=access_token), timeout=20)
    if isinstance(accounts, m.ProtoOAErrorRes):
        raise SystemicFailure("TOKEN_INVALID_OR_EXPIRED")
    if not isinstance(accounts, m.ProtoOAGetAccountListByAccessTokenRes):
        raise SystemicFailure("ACCOUNT_FINGERPRINT_MISMATCH")
    if not accounts.HasField("permissionScope") or accounts.permissionScope != e.SCOPE_VIEW:
        raise SystemicFailure("SCOPE_NOT_EXPLICIT_VIEW")

    matches = [
        a for a in accounts.ctidTraderAccount
        if _fingerprint(a.ctidTraderAccountId) == ACCOUNT_FINGERPRINT_SHA256
    ]
    if len(matches) != 1:
        raise SystemicFailure("ACCOUNT_FINGERPRINT_MISMATCH")
    account = matches[0]
    if not account.HasField("isLive") or not account.isLive:
        raise SystemicFailure("ACCOUNT_NOT_LIVE")
    account_id = int(account.ctidTraderAccountId)

    auth = transport.request(
        m.ProtoOAAccountAuthReq(ctidTraderAccountId=account_id, accessToken=access_token),
        timeout=20,
    )
    if not isinstance(auth, m.ProtoOAAccountAuthRes):
        raise SystemicFailure("ACCOUNT_AUTH_MISMATCH")
    if not auth.HasField("ctidTraderAccountId") or int(auth.ctidTraderAccountId) != account_id:
        raise SystemicFailure("ACCOUNT_AUTH_MISMATCH")
    return account_id


def build_history_request(ctx: v2.RequestContext):
    req = v2.ProtoOAGetTrendbarsReqV2(
        ctidTraderAccountId=ctx.authenticated_account_id,
        symbolId=ctx.symbol_id,
        period=v2.M5_ENUM,
        fromTimestamp=ctx.from_ms,
        toTimestamp=ctx.to_ms,
        count=v2.PAGE_REQUESTED_COUNT,
    )
    v2.validate_request(req, ctx)
    return req


def decode_history_envelope(envelope, *, ctx: v2.RequestContext, digits: int) -> tuple[list[dict], bool, bool | None]:
    try:
        response = v2.bind_response_envelope(envelope, ctx)
        rows = v2.decode_bound_response(response, ctx=ctx, digits=digits)
        present, value = v2.response_has_more_presence(response)
        return rows, present, value
    except ValueError as exc:
        if "protected forward" in str(exc).lower():
            raise SystemicFailure("PROTECTED_FORWARD_LEAK") from exc
        raise SystemicFailure("RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE") from exc


def send_history_page(transport, *, ctx: v2.RequestContext, digits: int, limiter: RateLimiter):
    from m6.ctrader_proto import OpenApiMessages_pb2 as legacy
    from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
    from m6.ctrader_transport import ProtoHeartbeatEvent, encode_envelope

    req = build_history_request(ctx)
    envelope = ProtoMessage(
        payloadType=v2.PROTO_OA_GET_TRENDBARS_REQ_PAYLOAD_TYPE,
        payload=req.SerializeToString(),
        clientMsgId=ctx.client_msg_id,
    )
    if not transport.connected:
        raise TransientPageFailure("transport not authenticated/connected")
    limiter.before_send()
    try:
        transport._send_bytes(encode_envelope(envelope))
        deadline = transport._clock() + float(transport.response_timeout)
        heartbeat_type = int(ProtoHeartbeatEvent().payloadType)
        error_type = int(legacy.ProtoOAErrorRes().payloadType)
        while True:
            raw = transport.receive_envelope(deadline=deadline)
            if int(raw.payloadType) == heartbeat_type:
                transport.send_heartbeat()
                continue
            if not raw.HasField("clientMsgId") or str(raw.clientMsgId) != ctx.client_msg_id:
                continue
            if int(raw.payloadType) == error_type:
                err = legacy.ProtoOAErrorRes()
                err.ParseFromString(raw.payload)
                code = str(getattr(err, "errorCode", ""))
                if code in {"OA_AUTH_TOKEN_EXPIRED", "OA_AUTH_TOKEN_INVALID", "CH_ACCESS_TOKEN_INVALID", "CH_ACCESS_TOKEN_EXPIRED"}:
                    raise SystemicFailure("TOKEN_INVALID_OR_EXPIRED")
                if "FREQUENCY" in code.upper() or "TOO_MANY" in code.upper():
                    raise SystemicFailure("REQUEST_FREQUENCY_EXCEEDED")
                raise SystemicFailure("RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE")
            return decode_history_envelope(raw, ctx=ctx, digits=digits)
    except SystemicFailure:
        raise
    except Exception as exc:
        raise TransientPageFailure(type(exc).__name__) from exc


@dataclass
class CaptureCounters:
    request_count: int = 0
    retry_count: int = 0
    page_cap_hits: int = 0


def _connect_and_auth(credentials: tuple[str, str, str]):
    from m6.ctrader_transport import StdlibCTraderTransport

    tr = StdlibCTraderTransport(connect_timeout=15, response_timeout=30)
    try:
        account_id = authenticate_segment(tr, *credentials)
        return tr, account_id
    except Exception:
        tr.close()
        raise


def _page_with_retries(
    transport,
    *,
    ctx: v2.RequestContext,
    digits: int,
    limiter: RateLimiter,
    credentials: tuple[str, str, str],
    counters: CaptureCounters,
):
    last: Exception | None = None
    tr = transport
    for attempt in range(MAX_WIRE_ATTEMPTS_PER_PAGE):
        counters.request_count += 1
        if attempt:
            counters.retry_count += 1
        try:
            if not tr.connected:
                tr.close()
                tr, account_id = _connect_and_auth(credentials)
                if account_id != ctx.authenticated_account_id:
                    raise SystemicFailure("ACCOUNT_AUTH_MISMATCH")
            return tr, send_history_page(tr, ctx=ctx, digits=digits, limiter=limiter)
        except SystemicFailure:
            tr.close()
            raise
        except TransientPageFailure as exc:
            last = exc
            tr.close()
    raise TransientPageFailure(f"retry cap exhausted: {last}")


def _identity_result(
    *,
    segment: int,
    ordinal: int,
    symbol_id: int,
    digits: int,
    account_id: int,
    transport,
    limiter: RateLimiter,
    credentials: tuple[str, str, str],
    checkpoint_path: Path,
    soft_deadline: float,
) -> tuple[Any, dict]:
    from_ms = v2.to_ms(SEGMENTS[segment - 1][0])
    to_ms = v2.to_ms(SEGMENTS[segment - 1][1])
    page = 1
    rows: list[dict] = []
    counters = CaptureCounters()
    classification = None
    failure = None
    tr = transport
    ctx = v2.RequestContext(
        client_msg_id=f"mxm-m5v2-s{segment}-i{ordinal}-p1",
        authenticated_account_id=account_id,
        symbol_id=symbol_id,
        from_ms=from_ms,
        to_ms=to_ms,
    )
    while True:
        if time.monotonic() >= soft_deadline:
            raise SoftStop("soft runtime boundary reached before next page")
        try:
            tr, (page_rows, has_more_present, has_more_value) = _page_with_retries(
                tr,
                ctx=ctx,
                digits=digits,
                limiter=limiter,
                credentials=credentials,
                counters=counters,
            )
        except TransientPageFailure as exc:
            classification = "SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED"
            failure = {"code": "EXHAUSTED_TRANSIENT_RETRIES", "detail": str(exc)}
            break

        rows.extend(page_rows)
        atomic_json(
            checkpoint_path,
            {
                "segment": segment,
                "ordinal": ordinal,
                "symbol_id": symbol_id,
                "page": page,
                "rows_in_incomplete_shard": rows,
                "request_count": counters.request_count,
                "retry_count": counters.retry_count,
            },
        )
        decision = v2.pagination_decision(
            ctx=ctx,
            decoded_rows=page_rows,
            has_more_present=has_more_present,
            has_more_value=has_more_value,
            page_index=page,
        )
        if decision.fail_closed:
            if decision.reason.startswith("PAGE_CAP_"):
                counters.page_cap_hits += 1
                classification = "SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED"
                failure = {"code": decision.reason}
                break
            raise SystemicFailure("RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE")
        if decision.complete:
            classification = "NO_HISTORICAL_SUPPORT" if not rows else "SHALLOW_SUPPORT_COMPLETE"
            break
        page += 1
        ctx = v2.next_context(
            ctx,
            decision,
            next_client_msg_id=f"mxm-m5v2-s{segment}-i{ordinal}-p{page}",
        )

    rows = sorted(rows, key=lambda x: x["time_utc"])
    if len({x["time_utc"] for x in rows}) != len(rows):
        raise SystemicFailure("RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE")
    protected = sum(
        1 for x in rows if v2.to_ms(x["time_utc"]) >= v2.to_ms(v2.PROTECTED_FORWARD_BOUNDARY_UTC)
    )
    if protected:
        raise SystemicFailure("PROTECTED_FORWARD_LEAK")
    result = {
        "ordinal": ordinal,
        "symbol_id": symbol_id,
        "classification": classification,
        "request_count": counters.request_count,
        "retry_count": counters.retry_count,
        "page_cap_hits": counters.page_cap_hits,
        "failure": failure,
        "rows": rows,
    }
    atomic_json(
        checkpoint_path,
        {
            "segment": segment,
            "ordinal": ordinal,
            "symbol_id": symbol_id,
            "identity_complete": True,
            "classification": classification,
            "row_count": len(rows),
            "request_count": counters.request_count,
            "retry_count": counters.retry_count,
        },
    )
    return tr, result


def _shard_plaintext(segment: int, shard_index: int, items: Sequence[Mapping[str, Any]]) -> bytes:
    start = shard_index * IDENTITIES_PER_SHARD + 1
    end = min(MASTER_COUNT, start + IDENTITIES_PER_SHARD - 1)
    value = {
        "schema": "mxm.v4.shallow-m5-v2.raw-shard.v1",
        "segment_index": segment,
        "shard_index": shard_index,
        "identity_range": [start, end],
        "items": list(items),
    }
    return canonical_json_bytes(value) + b"\n"


def _package_cipher(wrapped: bytes, cipher: bytes) -> bytes:
    return PACKAGE_MAGIC + struct.pack(">I", len(wrapped)) + wrapped + cipher


def _unpackage_cipher(raw: bytes) -> tuple[bytes, bytes]:
    if not raw.startswith(PACKAGE_MAGIC) or len(raw) < len(PACKAGE_MAGIC) + 4:
        raise CaptureError("invalid encrypted package")
    pos = len(PACKAGE_MAGIC)
    n = struct.unpack(">I", raw[pos:pos + 4])[0]
    pos += 4
    if n <= 0 or pos + n >= len(raw):
        raise CaptureError("invalid wrapped-key length")
    return raw[pos:pos + n], raw[pos + n:]


def encrypt_shard(plaintext: bytes, *, public_key: Path, output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mxm-m5v2-enc-") as td:
        td = Path(td)
        plain = td / "plain"
        cipher = td / "cipher.gpg"
        passfile = td / "bundle.pass"
        wrapped = td / "bundle.rsa"
        gpghome = td / "gnupg"
        gpghome.mkdir(mode=0o700)
        plain.write_bytes(plaintext)
        passphrase = base64.urlsafe_b64encode(os.urandom(32)) + b"\n"
        passfile.write_bytes(passphrase)
        passfile.chmod(0o600)
        subprocess.run(
            [
                "gpg", "--homedir", str(gpghome), "--batch", "--yes", "--no-symkey-cache",
                "--pinentry-mode", "loopback", "--passphrase-file", str(passfile),
                "--symmetric", "--cipher-algo", "AES256", "--force-mdc",
                "--output", str(cipher), str(plain),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", str(public_key),
                "-in", str(passfile), "-out", str(wrapped),
                "-pkeyopt", "rsa_padding_mode:oaep",
                "-pkeyopt", "rsa_oaep_md:sha256",
                "-pkeyopt", "rsa_mgf1_md:sha256",
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        package = _package_cipher(wrapped.read_bytes(), cipher.read_bytes())
        tmp = output.with_name(output.name + ".tmp")
        tmp.write_bytes(package)
        os.replace(tmp, output)
        subprocess.run(
            ["gpgconf", "--homedir", str(gpghome), "--kill", "gpg-agent"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    return {
        "plaintext_sha256": sha256_bytes(plaintext),
        "encrypted_asset_sha256": sha256_file(output),
        "fresh_random_bundle_key": True,
        "bundle_key_min_entropy_bits": 256,
        "bulk_cipher": "OPENPGP_AES256_WITH_INTEGRITY_PROTECTION",
        "key_wrap": "RSA_OAEP_SHA256_MGF1_SHA256",
    }


def decrypt_synthetic_package(package: bytes, *, private_key: Path) -> bytes:
    wrapped, cipher = _unpackage_cipher(package)
    with tempfile.TemporaryDirectory(prefix="mxm-m5v2-dec-") as td:
        td = Path(td)
        wrapped_path = td / "wrapped"
        cipher_path = td / "cipher.gpg"
        passfile = td / "bundle.pass"
        out = td / "plain"
        gpghome = td / "gnupg"
        gpghome.mkdir(mode=0o700)
        wrapped_path.write_bytes(wrapped)
        cipher_path.write_bytes(cipher)
        subprocess.run(
            [
                "openssl", "pkeyutl", "-decrypt", "-inkey", str(private_key),
                "-in", str(wrapped_path), "-out", str(passfile),
                "-pkeyopt", "rsa_padding_mode:oaep",
                "-pkeyopt", "rsa_oaep_md:sha256",
                "-pkeyopt", "rsa_mgf1_md:sha256",
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "gpg", "--homedir", str(gpghome), "--batch", "--yes", "--no-symkey-cache",
                "--pinentry-mode", "loopback", "--passphrase-file", str(passfile),
                "--output", str(out), "--decrypt", str(cipher_path),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        raw = out.read_bytes()
        subprocess.run(
            ["gpgconf", "--homedir", str(gpghome), "--kill", "gpg-agent"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return raw


def shard_asset_name(segment: int, shard_index: int) -> str:
    return f"shallow-m5-v2-seg{segment}-shard{shard_index:02d}.mxmenc"


def segment_manifest_rel(segment: int) -> str:
    return f"research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_SEGMENT_{segment}_DURABLE_MANIFEST.json"


FINAL_MANIFEST_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_DURABLE_MANIFEST_V1.json"


class GitHubReleaseStore:
    def __init__(self, *, tag: str, arm: Mapping[str, Any]):
        self.tag = tag
        self.arm = dict(arm)
        if not os.environ.get("GH_TOKEN"):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")

    def _gh(self, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["gh", *args],
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def ensure_release(self, *, create_allowed: bool) -> None:
        found = self._gh(["release", "view", self.tag, "--repo", REPO], check=False)
        if found.returncode == 0:
            return
        if not create_allowed:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        self._gh(
            [
                "release", "create", self.tag, "--repo", REPO,
                "--target", os.environ.get("GITHUB_SHA", ""),
                "--title", self.tag,
                "--notes", "Encrypted shallow M5 V2 capture staging. No plaintext market rows.",
            ]
        )

    def _asset_names(self) -> set[str]:
        run = self._gh(["release", "view", self.tag, "--repo", REPO, "--json", "assets"])
        data = json.loads(run.stdout)
        return {str(x["name"]) for x in data.get("assets", [])}

    def _download_asset(self, name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        self._gh(["release", "download", self.tag, "--repo", REPO, "--pattern", name, "--dir", str(dest)])

    def _delete_asset(self, name: str) -> None:
        self._gh(["release", "delete-asset", self.tag, name, "--repo", REPO, "--yes"])

    def load_segment_manifest(self, segment: int) -> dict:
        rel = segment_manifest_rel(segment)
        run = self._gh(
            ["api", "--method", "GET", f"repos/{REPO}/contents/{rel}", "-f", f"ref={BRANCH}"],
            check=False,
        )
        if run.returncode != 0:
            if "404" in run.stderr or "Not Found" in run.stderr:
                return {
                    "schema": "mxm.v4.shallow-m5-v2.segment-durable-manifest.v1",
                    "MASTER_SHA256": MASTER_SHA256,
                    "ACCOUNT_FINGERPRINT_SHA256": ACCOUNT_FINGERPRINT_SHA256,
                    "PROTOCOL_FREEZE_SHA256": PROTOCOL_FREEZE_SHA256,
                    "DIGITS_MAP_SHA256": DIGITS_MAP_FILE_SHA256,
                    "SEGMENT_INDEX": segment,
                    "SOURCE_HEAD": self.arm["exact_source_head"],
                    "ARM_COMMIT": os.environ.get("GITHUB_SHA"),
                    "entries": [],
                    "status": "PARTIAL",
                }
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        payload = json.loads(run.stdout)
        raw = base64.b64decode(str(payload["content"]).replace("\n", ""))
        manifest = json.loads(raw)
        if manifest.get("SEGMENT_INDEX") != segment or manifest.get("SOURCE_HEAD") != self.arm["exact_source_head"]:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return manifest

    def _put_repo_json(self, rel: str, value: Mapping[str, Any], message: str) -> None:
        existing = self._gh(
            ["api", "--method", "GET", f"repos/{REPO}/contents/{rel}", "-f", f"ref={BRANCH}"],
            check=False,
        )
        args = [
            "api", "--method", "PUT", f"repos/{REPO}/contents/{rel}",
            "-f", f"message={message}",
            "-f", "content=" + base64.b64encode(canonical_json_bytes(value) + b"\n").decode("ascii"),
            "-f", f"branch={BRANCH}",
        ]
        if existing.returncode == 0:
            args += ["-f", "sha=" + str(json.loads(existing.stdout)["sha"])]
        elif "404" not in existing.stderr and "Not Found" not in existing.stderr:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        run = self._gh(args, check=False)
        if run.returncode != 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")

    def recoverable_entry(self, segment: int, shard_index: int, identity_range: list[int]) -> dict | None:
        manifest = self.load_segment_manifest(segment)
        matches = [x for x in manifest.get("entries", []) if x.get("SHARD_INDEX") == shard_index]
        if len(matches) > 1:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        name = shard_asset_name(segment, shard_index)
        names = self._asset_names()
        if not matches:
            if name in names:
                self._delete_asset(name)
            return None
        entry = matches[0]
        if entry.get("IDENTITY_RANGE") != identity_range or name not in names:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        with tempfile.TemporaryDirectory(prefix="mxm-m5v2-asset-") as td:
            self._download_asset(name, Path(td))
            actual = sha256_file(Path(td) / name)
        if actual != entry.get("ENCRYPTED_ASSET_SHA256"):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return entry

    def publish_shard(self, segment: int, shard_index: int, package: Path, entry: Mapping[str, Any]) -> None:
        name = package.name
        if name in self._asset_names():
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        self._gh(["release", "upload", self.tag, str(package), "--repo", REPO])
        with tempfile.TemporaryDirectory(prefix="mxm-m5v2-verify-") as td:
            self._download_asset(name, Path(td))
            observed = sha256_file(Path(td) / name)
        if observed != entry.get("ENCRYPTED_ASSET_SHA256"):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        manifest = self.load_segment_manifest(segment)
        if any(x.get("SHARD_INDEX") == shard_index for x in manifest.get("entries", [])):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        entries = list(manifest.get("entries", [])) + [dict(entry)]
        entries.sort(key=lambda x: x["SHARD_INDEX"])
        manifest["entries"] = entries
        manifest["status"] = "COMPLETE" if len(entries) == SHARD_COUNT_PER_SEGMENT else "PARTIAL"
        self._put_repo_json(
            segment_manifest_rel(segment),
            manifest,
            f"Publish shallow M5 V2 segment {segment} shard {shard_index:02d} durable manifest",
        )

    def publish_final_manifest(self) -> dict:
        manifests = [self.load_segment_manifest(i) for i in range(1, 5)]
        final = reconstruct_final_manifest(manifests)
        self._put_repo_json(FINAL_MANIFEST_REL, final, "Publish shallow M5 V2 final compact durable manifest")
        return final


def reconstruct_final_manifest(manifests: Sequence[Mapping[str, Any]]) -> dict:
    if len(manifests) != 4:
        raise CaptureError("exact four segment manifests required")
    by_segment = {int(x["SEGMENT_INDEX"]): x for x in manifests}
    if set(by_segment) != {1, 2, 3, 4}:
        raise CaptureError("segment manifest set mismatch")
    entries = []
    for segment in range(1, 5):
        m = by_segment[segment]
        if m.get("status") != "COMPLETE" or len(m.get("entries", [])) != SHARD_COUNT_PER_SEGMENT:
            raise CaptureError("segment not durably complete")
        entries.extend(m["entries"])
    return {
        "schema": "mxm.v4.shallow-m5-v2.final-durable-manifest.v1",
        "MASTER_SHA256": MASTER_SHA256,
        "ACCOUNT_FINGERPRINT_SHA256": ACCOUNT_FINGERPRINT_SHA256,
        "PROTOCOL_FREEZE_SHA256": PROTOCOL_FREEZE_SHA256,
        "DIGITS_MAP_SHA256": DIGITS_MAP_FILE_SHA256,
        "segment_count": 4,
        "encrypted_shard_count": len(entries),
        "entries": entries,
        "PROTECTED_FORWARD_ROW_COUNT": sum(int(x["PROTECTED_FORWARD_ROW_COUNT"]) for x in entries),
        "status": "COMPLETE",
    }


def _manifest_entry(
    *,
    arm: Mapping[str, Any],
    segment: int,
    shard_index: int,
    identity_range: list[int],
    items: Sequence[Mapping[str, Any]],
    plaintext_sha: str,
    encrypted_sha: str,
) -> dict:
    rows = [r for item in items for r in item.get("rows", [])]
    failures = Counter(
        str(item.get("failure", {}).get("code"))
        for item in items
        if item.get("failure")
    )
    protected = sum(
        1 for row in rows if v2.to_ms(row["time_utc"]) >= v2.to_ms(v2.PROTECTED_FORWARD_BOUNDARY_UTC)
    )
    if protected:
        raise SystemicFailure("PROTECTED_FORWARD_LEAK")
    return {
        "MASTER_SHA256": MASTER_SHA256,
        "ACCOUNT_FINGERPRINT_SHA256": ACCOUNT_FINGERPRINT_SHA256,
        "PROTOCOL_FREEZE_SHA256": PROTOCOL_FREEZE_SHA256,
        "DIGITS_MAP_SHA256": DIGITS_MAP_FILE_SHA256,
        "SOURCE_HEAD": arm["exact_source_head"],
        "ARM_COMMIT": os.environ.get("GITHUB_SHA"),
        "SEGMENT_INDEX": segment,
        "SHARD_INDEX": shard_index,
        "IDENTITY_RANGE": identity_range,
        "ENCRYPTED_ASSET_NAME": shard_asset_name(segment, shard_index),
        "ENCRYPTED_ASSET_SHA256": encrypted_sha,
        "PLAINTEXT_CANONICAL_SHA256": plaintext_sha,
        "ROW_COUNT": len(rows),
        "FIRST_TIMESTAMP": min((x["time_utc"] for x in rows), default=None),
        "LAST_TIMESTAMP": max((x["time_utc"] for x in rows), default=None),
        "REQUEST_COUNT": sum(int(x.get("request_count", 0)) for x in items),
        "RETRY_COUNT": sum(int(x.get("retry_count", 0)) for x in items),
        "PAGE_CAP_HITS": sum(int(x.get("page_cap_hits", 0)) for x in items),
        "FAILURE_LEDGER": dict(sorted(failures.items())),
        "PROTECTED_FORWARD_ROW_COUNT": protected,
    }


def run_segment(segment: int, *, workdir: Path) -> dict:
    if segment not in (1, 2, 3, 4):
        raise CaptureError("segment must be 1..4")
    arm = validate_arm()
    if segment == 1:
        validate_arm_git_event(arm)
    static = validate_static_bindings()
    master = static["master"]
    digits = static["digits"]

    required = ("CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET", "CTRADER_ACCESS_TOKEN")
    if any(not os.environ.get(x) for x in required):
        raise SystemicFailure("TOKEN_INVALID_OR_EXPIRED")
    if os.environ.get("CTRADER_REFRESH_TOKEN"):
        raise PermissionError("REFRESH_TOKEN_MUST_NOT_BE_IN_PRODUCTION_SEGMENT_ENVIRONMENT")
    credentials = tuple(os.environ[x] for x in required)

    store = GitHubReleaseStore(tag=arm["durable_release_identity"], arm=arm)
    store.ensure_release(create_allowed=(segment == 1))

    workdir.mkdir(parents=True, exist_ok=True)
    checkpoint = workdir / "local-checkpoint.json"
    soft_deadline = time.monotonic() + SOFT_STOP_MINUTES * 60
    limiter = RateLimiter()
    transport, account_id = _connect_and_auth(credentials)

    captured_shards = 0
    skipped_shards = 0
    try:
        for shard_index in range(SHARD_COUNT_PER_SEGMENT):
            start = shard_index * IDENTITIES_PER_SHARD + 1
            end = min(MASTER_COUNT, start + IDENTITIES_PER_SHARD - 1)
            identity_range = [start, end]
            existing = store.recoverable_entry(segment, shard_index, identity_range)
            if existing is not None:
                skipped_shards += 1
                continue
            if time.monotonic() >= soft_deadline:
                raise SoftStop("soft runtime boundary reached before new shard")
            items = []
            for ordinal in range(start, end + 1):
                row = master[ordinal - 1]
                try:
                    symbol_id = int(row["symbol_id"])
                    symbol_digits = int(digits[symbol_id])
                except Exception as exc:
                    items.append(
                        {
                            "ordinal": ordinal,
                            "symbol_id": row.get("symbol_id"),
                            "classification": "IDENTITY_OR_MAPPING_FAILURE",
                            "request_count": 0,
                            "retry_count": 0,
                            "page_cap_hits": 0,
                            "failure": {"code": "IDENTITY_OR_MAPPING_FAILURE", "detail": type(exc).__name__},
                            "rows": [],
                        }
                    )
                    continue
                transport, item = _identity_result(
                    segment=segment,
                    ordinal=ordinal,
                    symbol_id=symbol_id,
                    digits=symbol_digits,
                    account_id=account_id,
                    transport=transport,
                    limiter=limiter,
                    credentials=credentials,
                    checkpoint_path=checkpoint,
                    soft_deadline=soft_deadline,
                )
                items.append(item)

            plaintext = _shard_plaintext(segment, shard_index, items)
            package = workdir / shard_asset_name(segment, shard_index)
            enc = encrypt_shard(plaintext, public_key=ROOT / PUBLIC_KEY_REL, output=package)
            entry = _manifest_entry(
                arm=arm,
                segment=segment,
                shard_index=shard_index,
                identity_range=identity_range,
                items=items,
                plaintext_sha=enc["plaintext_sha256"],
                encrypted_sha=enc["encrypted_asset_sha256"],
            )
            store.publish_shard(segment, shard_index, package, entry)
            package.unlink(missing_ok=True)
            checkpoint.unlink(missing_ok=True)
            captured_shards += 1
    finally:
        transport.close()
        for p in workdir.glob("*.mxmenc"):
            p.unlink(missing_ok=True)
        checkpoint.unlink(missing_ok=True)

    manifest = store.load_segment_manifest(segment)
    if manifest.get("status") != "COMPLETE" or len(manifest.get("entries", [])) != SHARD_COUNT_PER_SEGMENT:
        raise SoftStop("segment incomplete after graceful boundary")
    final = None
    if segment == 4:
        final = store.publish_final_manifest()
        if final.get("PROTECTED_FORWARD_ROW_COUNT") != 0:
            raise SystemicFailure("PROTECTED_FORWARD_LEAK")
    return {
        "segment": segment,
        "status": "COMPLETE",
        "captured_shards": captured_shards,
        "skipped_durable_shards": skipped_shards,
        "segment_manifest_ref": segment_manifest_rel(segment),
        "final_manifest_ref": FINAL_MANIFEST_REL if final else None,
    }


def synthetic_durable_resume_decision(
    manifest: Mapping[str, Any],
    *,
    shard_index: int,
    identity_range: list[int],
    observed_asset_sha256: str | None,
) -> str:
    entries = [x for x in manifest.get("entries", []) if x.get("SHARD_INDEX") == shard_index]
    if len(entries) > 1:
        return "FAIL_CLOSED"
    if not entries:
        return "RECAPTURE_UNPUBLISHED"
    e = entries[0]
    if e.get("IDENTITY_RANGE") != identity_range or observed_asset_sha256 != e.get("ENCRYPTED_ASSET_SHA256"):
        return "FAIL_CLOSED"
    return "SKIP_WITHOUT_BROKER_REQUERY"


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("plan")

    va = sub.add_parser("validate-arm")
    va.add_argument("--segment", type=int, choices=[1, 2, 3, 4], default=1)

    rs = sub.add_parser("run-segment")
    rs.add_argument("--segment", type=int, choices=[1, 2, 3, 4], required=True)
    rs.add_argument("--workdir", type=Path, required=True)

    args = ap.parse_args()
    if args.command == "plan":
        print(json.dumps(production_plan(), sort_keys=True))
        return 0
    if args.command == "validate-arm":
        arm = validate_arm()
        validate_static_bindings()
        if args.segment == 1:
            validate_arm_git_event(arm)
        print(json.dumps({"status": "PASS_ARM_AND_STATIC_BINDINGS", "segment": args.segment}, sort_keys=True))
        return 0
    try:
        result = run_segment(args.segment, workdir=args.workdir)
        print(json.dumps(result, sort_keys=True))
        return 0
    except SoftStop as exc:
        print(json.dumps({"status": "SOFT_STOP_INCOMPLETE_RECOVER_FROM_DURABLE_SHARDS", "detail": str(exc)}, sort_keys=True))
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
