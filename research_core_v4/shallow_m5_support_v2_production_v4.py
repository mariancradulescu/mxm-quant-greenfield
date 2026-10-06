"""V4 production successor for confirmed lower-boundary overfetch.

Historical V1/V2/V3 modules remain immutable. V4 reuses accepted V2/V3 execution
components directly and changes only response normalization and raw-geometry pagination.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

from research_core_v4 import shallow_m5_support_v2 as decoder
from research_core_v4 import shallow_m5_support_v2_boundary_v4 as boundary
from research_core_v4 import shallow_m5_support_v2_production as v1
from research_core_v4 import shallow_m5_support_v2_production_v2 as v2
from research_core_v4 import shallow_m5_support_v2_production_v3 as v3

ROOT = Path(__file__).resolve().parents[1]
REPO = v2.REPO
BRANCH = v2.BRANCH

ARM_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V4.json"
ARM_SCHEMA = "mxm.v4.breadth-first-shallow-m5-support-v2.production-arm.v4"
RUNNER_REL = "research_core_v4/shallow_m5_support_v2_production_v4.py"
WORKFLOW_REL = ".github/workflows/breadth-first-shallow-m5-support-v2-production-v4.yml"
ARCH_FREEZE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_MACHINE_SIDE_PRODUCTION_ARCHITECTURE_FREEZE_V4.json"
BOUNDARY_DECODER_REL = "research_core_v4/shallow_m5_support_v2_boundary_v4.py"
FORENSIC_ACCEPTANCE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_BOUNDARY_FORENSIC_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json"

FAILED_V3_RELEASE = "mxm-shallow-m5-v2-5a15b55ce82e12889139e74a1b213d146fcf36a97ceb763fa0a321a83721d115"
FAILED_V3_ARM_SHA256 = "756544d1778262228017739f5c1dd914ca969c9c15cd4b02d077bd3171f6621f"
FAILED_V3_AUTH_SHA256 = "e4bae388149e78391561115e0fb64b8b5417622103cfb4fed472ccbfa89a9b8e"
FORENSIC_RESULT_SHA256 = "5ff5ee46fe9b5483cfe11077abcabdcd77f50b4f3a4df5329a73e19b80bb013b"
FORENSIC_RESULT_AUTH_SHA256 = "00e1a23b958ca6da0d0f58e71ad4a7be8245a221d4586ae78d9360438bbf336e"
FORENSIC_ACCEPTANCE_SHA256 = "536d29a23f13caf176fa594be59b98fe4861f0edcd1a8bf09682f7d99d74adff"
BOUNDARY_DECODER_SHA256 = "7f148effd792052e367ce892781123fedc8d9083bfbad27ec9cf8065c48eef52"

V2_RUNNER_SHA256 = "a1aa8ba8bd104639c2758bf4bc14096565e41c897bceda2d343e0ba68c840de7"
V2_WORKFLOW_SHA256 = "208b26c10b0b3f5750512d126b4fa5a33ffbaa4c085985a64c7ca23a0706e7af"
V2_ARCH_SHA256 = "ca19f43ebd3e8e5d1de4b87226a4820ccc58616e2e18fe0e46721800c8db0230"
V2_OUTPUT_SHA256 = "90cad3fad2fa92951c2257f74011dd980b4f95b3801614a2ff2f89881b8c0ea2"
V3_RUNNER_SHA256 = "c6897e3847cd88b1641f32e011d3b8b9f0397b8ef40c974db4f227b59978a0af"
V3_WORKFLOW_SHA256 = "2774bb2e43335589b89846bf745afef6bfd77ddd19be1bbf7b7d566c8c5d6ae1"
V3_ARCH_SHA256 = "769fd7d09c49ef0ac23675801239d5ee8e018e219e9c73d8ce4a8a584b381d84"

CaptureError = v2.CaptureError
SystemicFailure = v2.SystemicFailure
SoftStop = v2.SoftStop
TransientPageFailure = v1.TransientPageFailure
RateLimiter = v1.RateLimiter

HEX64 = frozenset("0123456789abcdef")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PermissionError("V4_PREARM_BINDING_FAILURE")
    return value


def validate_forensic_acceptance() -> dict:
    p = ROOT / FORENSIC_ACCEPTANCE_REL
    if not p.is_file() or sha256_file(p) != FORENSIC_ACCEPTANCE_SHA256:
        raise PermissionError("V4_FORENSIC_ACCEPTANCE_BINDING_FAILURE")
    value = load_json(p)
    if value.get("status") != "INDEPENDENTLY_ACCEPTED_LOWER_BOUNDARY_OVERFETCH_CONFIRMED":
        raise PermissionError("V4_FORENSIC_ACCEPTANCE_BINDING_FAILURE")
    if value.get("accepted_classification") != "LOWER_BOUNDARY_OVERFETCH_CONFIRMED":
        raise PermissionError("V4_FORENSIC_ACCEPTANCE_BINDING_FAILURE")
    return value


def execution_equivalence_proof() -> dict:
    expected = {
        v2.RUNNER_REL: V2_RUNNER_SHA256,
        v2.WORKFLOW_REL: V2_WORKFLOW_SHA256,
        v2.ARCH_FREEZE_REL: V2_ARCH_SHA256,
        v2.OUTPUT_AUTH_REL: V2_OUTPUT_SHA256,
        v3.RUNNER_REL: V3_RUNNER_SHA256,
        v3.WORKFLOW_REL: V3_WORKFLOW_SHA256,
        v3.ARCH_FREEZE_REL: V3_ARCH_SHA256,
        BOUNDARY_DECODER_REL: BOUNDARY_DECODER_SHA256,
        "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V3.json": FAILED_V3_ARM_SHA256,
        "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_FAILED_EXECUTION_AUTHORITY_V1.json": FAILED_V3_AUTH_SHA256,
        "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_BOUNDARY_FORENSIC_RESULT_V1.json": FORENSIC_RESULT_SHA256,
        "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_BOUNDARY_FORENSIC_RESULT_AUTHORITY_V1.json": FORENSIC_RESULT_AUTH_SHA256,
        FORENSIC_ACCEPTANCE_REL: FORENSIC_ACCEPTANCE_SHA256,
    }
    for rel, digest in expected.items():
        if sha256_file(ROOT / rel) != digest:
            raise PermissionError("V4_HISTORICAL_OR_EVIDENCE_HASH_DRIFT")

    v3.validate_provider_authority()
    validate_forensic_acceptance()
    proof_keys = (
        "SAME_MASTER1576_IDENTITY_AND_ORDER",
        "SAME_FOUR_FIXED_SEGMENTS",
        "SAME_M5_REQUEST_FIELDS",
        "SAME_AUTH_V3_ACCOUNT_SELECTION",
        "SAME_VIEW_SCOPE",
        "SAME_NO_TOKEN_REFRESH",
        "SAME_RAW_ENVELOPE_CLIENT_MSG_ID_BINDING",
        "SAME_RESPONSE_ACCOUNT_PERIOD_SYMBOL_BINDING",
        "SAME_PRICE_DECIMAL_SERIALIZATION_FOR_CANONICAL_ROWS",
        "SAME_DIGITS_MAP",
        "SAME_SHARD_GEOMETRY",
        "SAME_CHECKPOINTING",
        "SAME_ENCRYPTION",
        "SAME_GITHUB_RELEASE_PROVIDER",
        "SAME_STRICT_MANIFEST_VALIDATION",
        "SAME_ALL25_PREVIOUS_SEGMENT_GATE",
        "SAME_CAMPAIGN_BRANCH_DRIFT_GUARD",
        "SAME_RECOVERY_GOVERNANCE",
        "SAME_SOFT_RUNTIME_STOP",
        "SAME_ZERO_TICKS",
        "SAME_ZERO_SUBSCRIPTIONS",
        "SAME_ZERO_DEPTH",
        "SAME_ZERO_ORDERS",
        "SAME_ZERO_ACCOUNT_MUTATION",
    )
    return {
        "only_allowed_behavioral_changes": [
            "LOWER_BOUNDARY_OVERFETCH_NORMALIZATION",
            "RAW_GEOMETRY_AWARE_PAGINATION_COMPLETION",
        ],
        "proof": {key: True for key in proof_keys},
    }


def derive_release_identity(source_head: str) -> str:
    if not isinstance(source_head, str) or len(source_head) != 40 or any(c not in HEX64 for c in source_head):
        raise CaptureError("invalid source head")
    payload = {
        "domain": "mxm.v4.shallow-m5-v2.production-v4.release-identity.v1",
        "source_head": source_head,
        "architecture_freeze_sha256": sha256_file(ROOT / ARCH_FREEZE_REL),
    }
    digest = v2.sha256_bytes(v2.canonical_json_bytes(payload))
    identity = f"mxm-shallow-m5-v2-v4-{digest}"
    if identity == FAILED_V3_RELEASE:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    return identity


def expected_release_body(campaign: Mapping[str, Any]) -> str:
    return v2.canonical_json_bytes({
        "schema": "mxm.v4.shallow-m5-v2.production-v4.release-binding.v1",
        "SOURCE_HEAD": campaign["SOURCE_HEAD"],
        "ARM_COMMIT": campaign["ARM_COMMIT"],
        "DURABLE_RELEASE_IDENTITY": campaign["DURABLE_RELEASE_IDENTITY"],
        "ARCHITECTURE_FREEZE_SHA256": sha256_file(ROOT / ARCH_FREEZE_REL),
    }).decode("utf-8")


class GitHubReleaseStoreV4(v2.GitHubReleaseStoreV2):
    def validate_existing_release(self, release: Mapping[str, Any]) -> int:
        if (
            release.get("tag_name") != self.tag
            or release.get("target_commitish") != self.campaign["ARM_COMMIT"]
            or release.get("body") != expected_release_body(self.campaign)
            or release.get("draft") is not False
        ):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        rid = release.get("id")
        if type(rid) is not int or rid <= 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return rid

    def ensure_release(self, *, create_allowed: bool) -> int:
        self.verify_branch()
        existing = self.release_json()
        if existing is not None:
            return self.validate_existing_release(existing)
        if not create_allowed:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        run = self._gh([
            "api", "--method", "POST", f"repos/{REPO}/releases",
            "-f", f"tag_name={self.tag}",
            "-f", f"target_commitish={self.campaign['ARM_COMMIT']}",
            "-f", f"name={self.tag}",
            "-f", f"body={expected_release_body(self.campaign)}",
            "-F", "draft=false", "-F", "prerelease=false",
        ], check=False)
        if run.returncode != 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        release = self.release_json()
        if release is None:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return self.validate_existing_release(release)


def _expected_arm_bindings() -> dict:
    bindings = dict(v2._expected_arm_bindings())
    bindings.update({
        "PROVIDER_PREFLIGHT_RESULT_SHA256": v3.PROVIDER_RESULT_SHA256,
        "PROVIDER_PREFLIGHT_ACCEPTANCE_AUTHORITY_SHA256": v3.PROVIDER_ACCEPTANCE_SHA256,
        "V3_GATE_RUNNER_SHA256": V3_RUNNER_SHA256,
        "V3_GATE_WORKFLOW_SHA256": V3_WORKFLOW_SHA256,
        "V3_GATE_ARCHITECTURE_FREEZE_SHA256": V3_ARCH_SHA256,
        "FORENSIC_INDEPENDENT_ACCEPTANCE_AUTHORITY_SHA256": FORENSIC_ACCEPTANCE_SHA256,
        "V4_BOUNDARY_DECODER_SHA256": sha256_file(ROOT / BOUNDARY_DECODER_REL),
        "V4_PRODUCTION_RUNNER_SHA256": sha256_file(ROOT / RUNNER_REL),
        "V4_PRODUCTION_WORKFLOW_SHA256": sha256_file(ROOT / WORKFLOW_REL),
        "V4_ARCHITECTURE_FREEZE_SHA256": sha256_file(ROOT / ARCH_FREEZE_REL),
    })
    return bindings


def validate_arm(arm_path: Path = ROOT / ARM_REL) -> dict:
    execution_equivalence_proof()
    if not arm_path.is_file():
        raise PermissionError("PRODUCTION_ARM_V4_ABSENT")
    arm = load_json(arm_path)
    if set(arm) != {"schema", "status", "exact_source_head", "durable_release_identity", "bindings"}:
        raise PermissionError("ARM_V4_UNKNOWN_OR_MISSING_FIELDS")
    if arm.get("schema") != ARM_SCHEMA or arm.get("status") != "ARMED_NOT_EXECUTED":
        raise PermissionError("ARM_V4_SCHEMA_OR_STATUS_MISMATCH")
    source = arm.get("exact_source_head")
    if not isinstance(source, str) or len(source) != 40 or any(c not in HEX64 for c in source):
        raise PermissionError("INVALID_EXACT_SOURCE_HEAD")
    if arm.get("durable_release_identity") != derive_release_identity(source):
        raise PermissionError("WRONG_V4_RELEASE_IDENTITY")
    if arm.get("durable_release_identity") == FAILED_V3_RELEASE:
        raise PermissionError("FAILED_V3_RELEASE_REUSE_FORBIDDEN")
    if arm.get("bindings") != _expected_arm_bindings():
        raise PermissionError("ARM_V4_BINDING_MISMATCH")
    return arm


def validate_arm_git_event(arm: Mapping[str, Any]) -> str:
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if os.environ.get("GITHUB_SHA") and os.environ["GITHUB_SHA"] != head:
        raise PermissionError("GITHUB_SHA_MISMATCH")
    parents = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-list", "--parents", "-n", "1", "HEAD"], text=True
    ).split()
    changed = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], text=True
    ).splitlines()
    if len(parents) != 2 or parents[1] != arm.get("exact_source_head"):
        raise PermissionError("ARM_PARENT_MISMATCH")
    if changed != [ARM_REL]:
        raise PermissionError("ARM_V4_COMMIT_MUST_CHANGE_ONLY_EXACT_ARM_FILE")
    return head


def campaign_from_arm(arm: Mapping[str, Any], arm_commit: str) -> dict:
    expected = derive_release_identity(str(arm["exact_source_head"]))
    if arm["durable_release_identity"] != expected or expected == FAILED_V3_RELEASE:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    return {
        "MASTER_SHA256": v2.MASTER_SHA256,
        "ACCOUNT_FINGERPRINT_SHA256": v2.ACCOUNT_FINGERPRINT_SHA256,
        "PROTOCOL_FREEZE_SHA256": v2.PROTOCOL_FREEZE_SHA256,
        "DIGITS_MAP_SHA256": v2.DIGITS_MAP_FILE_SHA256,
        "SOURCE_HEAD": str(arm["exact_source_head"]),
        "ARM_COMMIT": arm_commit,
        "DURABLE_RELEASE_IDENTITY": expected,
    }


def decode_history_envelope(envelope, *, ctx: decoder.RequestContext, digits: int):
    try:
        return boundary.bind_and_normalize_response(envelope, ctx=ctx, digits=digits)
    except boundary.BoundaryProtocolError as exc:
        if exc.classification == "PROTECTED_FORWARD_LEAK":
            raise SystemicFailure("PROTECTED_FORWARD_LEAK") from exc
        raise SystemicFailure("RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE") from exc
    except ValueError as exc:
        raise SystemicFailure("RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE") from exc


def send_history_page(transport, *, ctx: decoder.RequestContext, digits: int, limiter: RateLimiter):
    from m6.ctrader_proto import OpenApiMessages_pb2 as legacy
    from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
    from m6.ctrader_transport import ProtoHeartbeatEvent, encode_envelope

    req = v1.build_history_request(ctx)
    envelope = ProtoMessage(
        payloadType=decoder.PROTO_OA_GET_TRENDBARS_REQ_PAYLOAD_TYPE,
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


def _page_with_retries(
    transport, *, ctx, digits: int, limiter: RateLimiter,
    credentials: tuple[str, str, str], counters,
):
    last: Exception | None = None
    tr = transport
    for attempt in range(v2.MAX_WIRE_ATTEMPTS_PER_PAGE):
        counters.request_count += 1
        if attempt:
            counters.retry_count += 1
        try:
            if not tr.connected:
                tr.close()
                tr, account_id = v1._connect_and_auth(credentials)
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
    *, segment: int, ordinal: int, symbol_id: int, digits: int, account_id: int,
    transport, limiter: RateLimiter, credentials: tuple[str, str, str],
    checkpoint_path: Path, soft_deadline: float,
):
    from_ms = decoder.to_ms(v2.SEGMENTS[segment - 1][0])
    to_ms = decoder.to_ms(v2.SEGMENTS[segment - 1][1])
    page = 1
    rows: list[dict] = []
    transport_geometry_pages: list[dict] = []
    counters = v1.CaptureCounters()
    classification = None
    failure = None
    tr = transport
    ctx = decoder.RequestContext(
        client_msg_id=f"mxm-m5v4-s{segment}-i{ordinal}-p1",
        authenticated_account_id=account_id,
        symbol_id=symbol_id,
        from_ms=from_ms,
        to_ms=to_ms,
    )
    while True:
        if time.monotonic() >= soft_deadline:
            raise SoftStop("soft runtime boundary reached before next page")
        try:
            tr, normalized = _page_with_retries(
                tr, ctx=ctx, digits=digits, limiter=limiter,
                credentials=credentials, counters=counters,
            )
        except TransientPageFailure as exc:
            classification = "SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED"
            failure = {"code": "EXHAUSTED_TRANSIENT_RETRIES", "detail": str(exc)}
            break

        page_rows = list(normalized.canonical_rows)
        rows.extend(page_rows)
        transport_geometry_pages.append({
            "page": page,
            **normalized.geometry.as_dict(),
            "hasMore_present": normalized.has_more_present,
            "hasMore_value": normalized.has_more_value,
        })
        v1.atomic_json(checkpoint_path, {
            "segment": segment,
            "ordinal": ordinal,
            "symbol_id": symbol_id,
            "page": page,
            "rows_in_incomplete_shard": rows,
            "transport_geometry_pages": transport_geometry_pages,
            "request_count": counters.request_count,
            "retry_count": counters.retry_count,
        })
        decision = boundary.pagination_decision_v4(
            ctx=ctx,
            geometry=normalized.geometry,
            has_more_present=normalized.has_more_present,
            has_more_value=normalized.has_more_value,
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
        ctx = boundary.next_context_v4(
            ctx, decision,
            next_client_msg_id=f"mxm-m5v4-s{segment}-i{ordinal}-p{page}",
        )

    rows = sorted(rows, key=lambda x: x["time_utc"])
    if len({x["time_utc"] for x in rows}) != len(rows):
        raise SystemicFailure("RAW_ENVELOPE_PROTOCOL_BINDING_FAILURE")
    if any(decoder.to_ms(x["time_utc"]) >= decoder.to_ms(decoder.PROTECTED_FORWARD_BOUNDARY_UTC) for x in rows):
        raise SystemicFailure("PROTECTED_FORWARD_LEAK")
    result = {
        "ordinal": ordinal,
        "symbol_id": symbol_id,
        "classification": classification,
        "request_count": counters.request_count,
        "retry_count": counters.retry_count,
        "page_cap_hits": counters.page_cap_hits,
        "failure": failure,
        "transport_geometry_pages": transport_geometry_pages,
        "rows": rows,
    }
    v1.atomic_json(checkpoint_path, {
        "segment": segment,
        "ordinal": ordinal,
        "symbol_id": symbol_id,
        "identity_complete": True,
        "classification": classification,
        "row_count": len(rows),
        "request_count": counters.request_count,
        "retry_count": counters.retry_count,
        "lower_overfetch_count": sum(int(x["lower_overfetch_count"]) for x in transport_geometry_pages),
    })
    return tr, result


def production_plan() -> dict:
    plan = copy.deepcopy(v2.production_plan())
    plan.update({
        "architecture_version": 4,
        "historical_v3_failed_closed": True,
        "lower_boundary_overfetch": "DISCARD_BEFORE_PRICE_OR_VOLUME_DECODING",
        "pagination_basis": "RAW_TEMPORAL_GEOMETRY",
        "release_identity_version": 4,
        "failed_v3_release_reuse": False,
        "global_historical_monkey_patching": False,
        "workflow_dispatch": False,
    })
    return plan


def run_segment(segment: int, *, workdir: Path) -> dict:
    if segment not in (1, 2, 3, 4):
        raise CaptureError("segment must be 1..4")
    arm = validate_arm()
    arm_commit = validate_arm_git_event(arm)
    static = v2.validate_static_bindings()
    campaign = campaign_from_arm(arm, arm_commit)

    store = GitHubReleaseStoreV4(
        tag=campaign["DURABLE_RELEASE_IDENTITY"],
        campaign=campaign,
        branch_name=BRANCH,
        base_commit=arm_commit,
        allowed_paths=v2.ALLOWED_POST_ARM_CAMPAIGN_PATHS,
    )
    store.verify_branch()
    store.ensure_release(create_allowed=(segment == 1))
    if segment > 1:
        store.validate_complete_segment_assets(segment - 1)
    store.verify_branch()

    required = ("CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET", "CTRADER_ACCESS_TOKEN")
    if any(not os.environ.get(x) for x in required):
        raise SystemicFailure("TOKEN_INVALID_OR_EXPIRED")
    if os.environ.get("CTRADER_REFRESH_TOKEN"):
        raise PermissionError("REFRESH_TOKEN_MUST_NOT_BE_IN_PRODUCTION_SEGMENT_ENVIRONMENT")
    credentials = tuple(os.environ[x] for x in required)

    master = static["master"]
    digits = static["digits"]
    workdir.mkdir(parents=True, exist_ok=True)
    checkpoint = workdir / "local-checkpoint.json"
    soft_deadline = time.monotonic() + v2.SOFT_STOP_MINUTES * 60
    limiter = RateLimiter()
    transport, account_id = v1._connect_and_auth(credentials)

    captured_shards = 0
    skipped_shards = 0
    try:
        for shard_index in range(v2.SHARD_COUNT_PER_SEGMENT):
            identity_range = v2.deterministic_identity_range(shard_index)
            existing = store.recoverable_entry(segment, shard_index, identity_range)
            if existing is not None:
                skipped_shards += 1
                continue
            if time.monotonic() >= soft_deadline:
                raise SoftStop("soft runtime boundary reached before new shard")
            items = []
            for ordinal in range(identity_range[0], identity_range[1] + 1):
                row = master[ordinal - 1]
                try:
                    symbol_id = int(row["symbol_id"])
                    symbol_digits = int(digits[symbol_id])
                except Exception as exc:
                    items.append({
                        "ordinal": ordinal,
                        "symbol_id": row.get("symbol_id"),
                        "classification": "IDENTITY_OR_MAPPING_FAILURE",
                        "request_count": 0,
                        "retry_count": 0,
                        "page_cap_hits": 0,
                        "failure": {"code": "IDENTITY_OR_MAPPING_FAILURE", "detail": type(exc).__name__},
                        "transport_geometry_pages": [],
                        "rows": [],
                    })
                    continue
                transport, item = _identity_result(
                    segment=segment, ordinal=ordinal, symbol_id=symbol_id,
                    digits=symbol_digits, account_id=account_id, transport=transport,
                    limiter=limiter, credentials=credentials,
                    checkpoint_path=checkpoint, soft_deadline=soft_deadline,
                )
                items.append(item)

            plaintext = v1._shard_plaintext(segment, shard_index, items)
            package = workdir / v2.shard_asset_name(segment, shard_index)
            enc = v2.encrypt_shard(plaintext, public_key=ROOT / v2.PUBLIC_KEY_REL, output=package)
            entry = v2._manifest_entry_v2(
                campaign=campaign, segment=segment, shard_index=shard_index,
                items=items, plaintext_sha=enc["plaintext_sha256"],
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

    manifest = store.load_segment_manifest(segment, require_complete=True)
    if len(manifest["entries"]) != v2.SHARD_COUNT_PER_SEGMENT:
        raise SoftStop("segment incomplete after graceful boundary")
    final = store.publish_final_manifest() if segment == 4 else None
    return {
        "segment": segment,
        "status": "COMPLETE",
        "captured_shards": captured_shards,
        "skipped_durable_shards": skipped_shards,
        "segment_manifest_ref": v2.segment_manifest_rel(segment),
        "final_manifest_ref": v2.FINAL_MANIFEST_REL if final else None,
        "durable_release_identity": campaign["DURABLE_RELEASE_IDENTITY"],
        "arm_commit": campaign["ARM_COMMIT"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    sub.add_parser("validate-arm")
    sub.add_parser("prove-equivalence")
    rs = sub.add_parser("run-segment")
    rs.add_argument("--segment", type=int, choices=[1,2,3,4], required=True)
    rs.add_argument("--workdir", type=Path, required=True)
    args = ap.parse_args()
    if args.command == "plan":
        print(json.dumps(production_plan(), sort_keys=True))
        return 0
    if args.command == "prove-equivalence":
        print(json.dumps(execution_equivalence_proof(), sort_keys=True))
        return 0
    if args.command == "validate-arm":
        arm = validate_arm()
        arm_commit = validate_arm_git_event(arm)
        v2.validate_static_bindings()
        campaign = campaign_from_arm(arm, arm_commit)
        store = GitHubReleaseStoreV4(
            tag=campaign["DURABLE_RELEASE_IDENTITY"],
            campaign=campaign, branch_name=BRANCH, base_commit=arm_commit,
        )
        store.verify_branch()
        print(json.dumps({"status":"PASS_ARM_V4_CORRECTED_BOUNDARY_AND_HISTORICAL_BINDINGS"}, sort_keys=True))
        return 0
    try:
        print(json.dumps(run_segment(args.segment, workdir=args.workdir), sort_keys=True))
        return 0
    except SoftStop as exc:
        print(json.dumps({"status":"SOFT_STOP_INCOMPLETE_RECOVER_FROM_DURABLE_SHARDS","detail":str(exc)}, sort_keys=True))
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
