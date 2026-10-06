"""Single-request forensic probe for the failed real V3 shallow-M5 boundary.

This module does not correct the production decoder. It authenticates read-only,
sends exactly one frozen ProtoOAGetTrendbarsReq for EURJPY symbolId=3, and scans
the response wire format only for protocol identity plus temporal geometry.
OHLC, delta, volume and raw trendbar payloads are never persisted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from research_core_v4 import shallow_m5_support_v2 as decoder
from research_core_v4 import shallow_m5_support_v2_production as production

ROOT = Path(__file__).resolve().parents[1]
REPO = "mariancradulescu/mxm-quant-greenfield"
BRANCH = "performance-research-v3-20260922"

FAILED_ARM_COMMIT = "639df8f3a252c63fbec52765f142e5d5cfe3a589"
FAILED_ARM_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V3.json"
FAILED_ARM_SHA256 = "756544d1778262228017739f5c1dd914ca969c9c15cd4b02d077bd3171f6621f"
FAILURE_AUTH_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_FAILED_EXECUTION_AUTHORITY_V1.json"
FORENSIC_ARM_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_BOUNDARY_FORENSIC_ARM_V1.json"
RUNNER_REL = "research_core_v4/shallow_m5_support_v2_v3_boundary_forensic_probe.py"
WORKFLOW_REL = ".github/workflows/breadth-first-shallow-m5-v2-v3-boundary-forensic-probe.yml"
RESULT_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_BOUNDARY_FORENSIC_RESULT_V1.json"
RESULT_AUTH_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_BOUNDARY_FORENSIC_RESULT_AUTHORITY_V1.json"

ARM_SCHEMA = "mxm.v4.breadth-first-shallow-m5-support-v2.v3-boundary-forensic-arm.v1"
ARM_STATUS = "ARMED_SINGLE_REQUEST_FORENSIC_NOT_EXECUTED"
FINAL_STATE = "PENDING_INDEPENDENT_AUDIT_OF_FIRST_REAL_V3_BOUNDARY_FORENSIC_PROBE_BEFORE_ANY_CAPTURE_SUCCESSOR"

SYMBOL = "EURJPY"
SYMBOL_ID = 3
PERIOD = decoder.M5_ENUM
FROM_UTC = "2026-08-20T00:00:00Z"
TO_UTC = "2026-08-26T23:55:00Z"
FROM_MS = decoder.to_ms(FROM_UTC)
TO_MS = decoder.to_ms(TO_UTC)
COUNT = decoder.PAGE_REQUESTED_COUNT
PROTECTED_FORWARD_UTC = "2026-09-17T12:02:58Z"
PROTECTED_FORWARD_MS = decoder.to_ms(PROTECTED_FORWARD_UTC)
CLIENT_MSG_ID = "mxm-v3-boundary-forensic-eurjpy-3-request-1"

FORBIDDEN_PERSISTED_KEYS = {
    "open", "high", "low", "close", "volume", "tick_volume",
    "deltaOpen", "deltaHigh", "deltaClose", "raw_payload",
    "ctidTraderAccountId", "access_token", "client_secret",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("JSON_OBJECT_REQUIRED")
    return value


def _arm_bindings() -> dict:
    return {
        "FAILED_ARM_COMMIT": FAILED_ARM_COMMIT,
        "FAILED_ARM_SHA256": FAILED_ARM_SHA256,
        "FAILED_EXECUTION_AUTHORITY_SHA256": sha256_file(ROOT / FAILURE_AUTH_REL),
        "FORENSIC_RUNNER_SHA256": sha256_file(ROOT / RUNNER_REL),
        "FORENSIC_WORKFLOW_SHA256": sha256_file(ROOT / WORKFLOW_REL),
        "ACCOUNT_FINGERPRINT_SHA256": production.ACCOUNT_FINGERPRINT_SHA256,
        "EXACT_SYMBOL_ID": SYMBOL_ID,
        "EXACT_PERIOD_ENUM": PERIOD,
        "EXACT_FROM_UTC": FROM_UTC,
        "EXACT_TO_UTC": TO_UTC,
        "EXACT_REQUESTED_COUNT": COUNT,
        "EXACT_HISTORY_REQUEST_COUNT": 1,
        "EXACT_HISTORY_RETRY_COUNT": 0,
        "PROTECTED_FORWARD_BOUNDARY_UTC": PROTECTED_FORWARD_UTC,
        "PERSIST_OHLC": False,
        "PERSIST_VOLUME": False,
        "PERSIST_RAW_TRENDBAR_PAYLOAD": False,
    }


def validate_arm() -> dict:
    path = ROOT / FORENSIC_ARM_REL
    if not path.is_file():
        raise PermissionError("FORENSIC_ARM_ABSENT")
    arm = load_json(path)
    if set(arm) != {"schema", "status", "exact_source_head", "failed_arm_commit", "bindings"}:
        raise PermissionError("FORENSIC_ARM_UNKNOWN_OR_MISSING_FIELDS")
    if arm["schema"] != ARM_SCHEMA or arm["status"] != ARM_STATUS:
        raise PermissionError("FORENSIC_ARM_SCHEMA_OR_STATUS_MISMATCH")
    if arm["failed_arm_commit"] != FAILED_ARM_COMMIT:
        raise PermissionError("FORENSIC_FAILED_ARM_BINDING_MISMATCH")
    if arm["bindings"] != _arm_bindings():
        raise PermissionError("FORENSIC_ARM_BINDING_MISMATCH")
    source = arm["exact_source_head"]
    if not isinstance(source, str) or len(source) != 40:
        raise PermissionError("FORENSIC_SOURCE_HEAD_INVALID")
    return arm


def validate_arm_git_event(arm: Mapping[str, Any]) -> str:
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    parents = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-list", "--parents", "-n", "1", "HEAD"], text=True
    ).split()
    changed = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], text=True
    ).splitlines()
    if os.environ.get("GITHUB_SHA") and os.environ["GITHUB_SHA"] != head:
        raise PermissionError("FORENSIC_GITHUB_SHA_MISMATCH")
    if len(parents) != 2 or parents[1] != arm["exact_source_head"]:
        raise PermissionError("FORENSIC_ARM_PARENT_MISMATCH")
    if changed != [FORENSIC_ARM_REL]:
        raise PermissionError("FORENSIC_ARM_COMMIT_MUST_CHANGE_ONLY_ARM_FILE")
    return head


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if pos >= len(buf) or shift >= 70:
            raise ValueError("MALFORMED_PROTOBUF_VARINT")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, pos
        shift += 7


def _skip_value(buf: bytes, pos: int, wire_type: int) -> int:
    if wire_type == 0:
        _, pos = _read_varint(buf, pos)
        return pos
    if wire_type == 1:
        pos += 8
    elif wire_type == 2:
        size, pos = _read_varint(buf, pos)
        pos += size
    elif wire_type == 5:
        pos += 4
    else:
        raise ValueError("UNSUPPORTED_PROTOBUF_WIRE_TYPE")
    if pos > len(buf):
        raise ValueError("TRUNCATED_PROTOBUF_FIELD")
    return pos


def _scan_trendbar_temporal_only(raw: bytes) -> tuple[int, int | None]:
    pos = 0
    minute = None
    present_period = None
    while pos < len(raw):
        key, pos = _read_varint(raw, pos)
        field = key >> 3
        wire = key & 7
        if field in (4, 9):
            if wire != 0:
                raise ValueError("FORENSIC_TRENDBAR_FIELD_WIRE_MISMATCH")
            value, pos = _read_varint(raw, pos)
            if field == 4:
                present_period = int(value)
            else:
                minute = int(value)
        else:
            pos = _skip_value(raw, pos, wire)
    if minute is None:
        raise ValueError("FORENSIC_TRENDBAR_TIMESTAMP_ABSENT")
    return minute, present_period


def extract_temporal_geometry(payload: bytes, *, expected_account_id: int) -> dict:
    pos = 0
    account = None
    period = None
    symbol_present = False
    symbol = None
    has_more_present = False
    has_more_value = None
    minutes: list[int] = []
    all_present_bar_periods_m5 = True

    while pos < len(payload):
        key, pos = _read_varint(payload, pos)
        field = key >> 3
        wire = key & 7
        if field in (1, 2, 3, 6, 7):
            if wire != 0:
                raise ValueError("FORENSIC_RESPONSE_FIELD_WIRE_MISMATCH")
            value, pos = _read_varint(payload, pos)
            if field == 2:
                account = int(value)
            elif field == 3:
                period = int(value)
            elif field == 6:
                symbol_present = True
                symbol = int(value)
            elif field == 7:
                has_more_present = True
                has_more_value = bool(value)
        elif field == 5:
            if wire != 2:
                raise ValueError("FORENSIC_TRENDBAR_WIRE_MISMATCH")
            size, pos = _read_varint(payload, pos)
            end = pos + size
            if end > len(payload):
                raise ValueError("FORENSIC_TRENDBAR_TRUNCATED")
            minute, bar_period = _scan_trendbar_temporal_only(payload[pos:end])
            minutes.append(minute)
            if bar_period is not None and bar_period != PERIOD:
                all_present_bar_periods_m5 = False
            pos = end
        else:
            pos = _skip_value(payload, pos, wire)

    account_match = account == expected_account_id
    period_match = period == PERIOD and all_present_bar_periods_m5
    symbol_match_if_present = (symbol == SYMBOL_ID) if symbol_present else None
    if not account_match:
        raise ValueError("FORENSIC_RESPONSE_ACCOUNT_MISMATCH")
    if not period_match:
        raise ValueError("FORENSIC_RESPONSE_PERIOD_MISMATCH")
    if symbol_present and not symbol_match_if_present:
        raise ValueError("FORENSIC_RESPONSE_SYMBOL_MISMATCH")

    open_ms = [m * 60_000 for m in minutes]
    below = sum(x < FROM_MS for x in open_ms)
    inside = sum(FROM_MS <= x <= TO_MS for x in open_ms)
    above = sum(x > TO_MS for x in open_ms)
    protected = sum(x >= PROTECTED_FORWARD_MS for x in open_ms)
    non_m5 = sum(x % decoder.M5_MILLISECONDS != 0 for x in open_ms)
    duplicates = len(minutes) - len(set(minutes))

    def iso(ms: int | None) -> str | None:
        if ms is None:
            return None
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if protected > 0:
        classification = "PROTECTED_FORWARD_TRANSPORT_LEAK_OBSERVED"
    elif below > 0 and above == 0:
        classification = "LOWER_BOUNDARY_OVERFETCH_CONFIRMED"
    elif above > 0:
        classification = "UPPER_BOUNDARY_OVERFETCH_OBSERVED"
    elif below == 0 and above == 0:
        classification = "PRIOR_BOUNDARY_FAILURE_NOT_REPRODUCED"
    else:
        raise ValueError("FORENSIC_CLASSIFICATION_UNREACHABLE")

    return {
        "response_trendbar_count": len(minutes),
        "hasMore_field_present": has_more_present,
        "hasMore_value_if_present": has_more_value,
        "minimum_raw_open_timestamp_utc": iso(min(open_ms) if open_ms else None),
        "maximum_raw_open_timestamp_utc": iso(max(open_ms) if open_ms else None),
        "exact_count_below_fromTimestamp": below,
        "exact_count_inside_requested_interval": inside,
        "exact_count_above_toTimestamp": above,
        "exact_count_at_or_after_protected_forward_boundary": protected,
        "exact_count_non_M5_aligned": non_m5,
        "exact_duplicate_open_timestamp_count": duplicates,
        "response_account_match": account_match,
        "response_period_match": period_match,
        "response_symbol_present": symbol_present,
        "response_symbol_match_if_present": symbol_match_if_present,
        "clientMsgId_match": True,
        "forensic_classification": classification,
    }


def _assert_no_forbidden_persistence(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PERSISTED_KEYS:
                raise ValueError(f"FORBIDDEN_PERSISTED_FIELD:{key}")
            _assert_no_forbidden_persistence(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_forbidden_persistence(child)


def run_probe(output: Path) -> dict:
    arm = validate_arm()
    validate_arm_git_event(arm)
    if os.environ.get("CTRADER_REFRESH_TOKEN"):
        raise PermissionError("REFRESH_TOKEN_MUST_NOT_BE_INJECTED")
    credentials = tuple(os.environ.get(k, "") for k in (
        "CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET", "CTRADER_ACCESS_TOKEN"
    ))
    if not all(credentials):
        raise PermissionError("REQUIRED_READ_ONLY_CREDENTIAL_MISSING")

    from m6.ctrader_proto import OpenApiMessages_pb2 as legacy
    from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
    from m6.ctrader_transport import ProtoHeartbeatEvent, StdlibCTraderTransport, encode_envelope

    transport = StdlibCTraderTransport(connect_timeout=15, response_timeout=30)
    history_request_count = 0
    try:
        account_id = production.authenticate_segment(transport, *credentials)
        ctx = decoder.RequestContext(
            client_msg_id=CLIENT_MSG_ID,
            authenticated_account_id=account_id,
            symbol_id=SYMBOL_ID,
            from_ms=FROM_MS,
            to_ms=TO_MS,
            count=COUNT,
            period=PERIOD,
        )
        req = production.build_history_request(ctx)
        envelope = ProtoMessage(
            payloadType=decoder.PROTO_OA_GET_TRENDBARS_REQ_PAYLOAD_TYPE,
            payload=req.SerializeToString(),
            clientMsgId=CLIENT_MSG_ID,
        )
        history_request_count += 1
        if history_request_count != 1:
            raise RuntimeError("FORENSIC_HISTORY_REQUEST_CARDINALITY_FAILURE")
        transport._send_bytes(encode_envelope(envelope))

        deadline = transport._clock() + float(transport.response_timeout)
        heartbeat_type = int(ProtoHeartbeatEvent().payloadType)
        error_type = int(legacy.ProtoOAErrorRes().payloadType)
        while True:
            raw = transport.receive_envelope(deadline=deadline)
            if int(raw.payloadType) == heartbeat_type:
                continue
            client_match = raw.HasField("clientMsgId") and str(raw.clientMsgId) == CLIENT_MSG_ID
            if not client_match:
                raise ValueError("FORENSIC_CLIENT_MSG_ID_MISMATCH")
            if int(raw.payloadType) == error_type:
                raise RuntimeError("FORENSIC_HISTORY_ERROR_RESPONSE_FAIL_CLOSED")
            if int(raw.payloadType) != decoder.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE:
                raise ValueError("FORENSIC_RESPONSE_TYPE_MISMATCH")
            geometry = extract_temporal_geometry(raw.payload, expected_account_id=account_id)
            break
    finally:
        transport.close()

    result = {
        "schema": "mxm.v4.breadth-first-shallow-m5-support-v2.v3-boundary-forensic-result.v1",
        "status": "SINGLE_FORENSIC_RESPONSE_CAPTURED",
        "failed_arm_commit": FAILED_ARM_COMMIT,
        "forensic_arm_commit": os.environ.get("GITHUB_SHA"),
        "request": {
            "master_ordinal": 1,
            "symbol": SYMBOL,
            "symbol_id": SYMBOL_ID,
            "resolution": "M5",
            "period_enum": PERIOD,
            "from_utc": FROM_UTC,
            "to_utc": TO_UTC,
            "requested_count": COUNT,
        },
        "history_request_count": history_request_count,
        "history_retry_count": 0,
        "protected_forward_boundary_utc": PROTECTED_FORWARD_UTC,
        "geometry": geometry,
        "persistence": {
            "raw_trendbar_payload_persisted": False,
            "ohlc_persisted": False,
            "volume_persisted": False,
            "token_material_persisted": False,
            "raw_account_id_persisted": False,
        },
        "economic_response": False,
        "candidate_selection": False,
        "profitability_test": False,
        "search_budget_consumed": 0,
    }
    _assert_no_forbidden_persistence(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(result) + b"\n")
    return result


def _api(method: str, path: str, token: str, payload: Any | None = None) -> Any:
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mxm-v3-boundary-forensic-publisher",
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GITHUB_API_{method}_{path}_{exc.code}") from exc
    return json.loads(raw) if raw else {}


def _publication_states(result_ref: str, result_sha: str, authority_ref: str, authority_sha: str,
                        run_id: int, job_id: int, classification: str) -> dict[str, bytes]:
    v4_path = ROOT / "research_core_v4/state/V4_STATE.json"
    cur_path = ROOT / "adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json"
    auth_path = ROOT / "adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json"
    v4, cur, auth = load_json(v4_path), load_json(cur_path), load_json(auth_path)

    v4["current_authority"] = authority_ref
    v4["current_next_action_type"] = FINAL_STATE
    v4["next_action"] = FINAL_STATE
    op = dict(v4.get("shallow_m5_v2_current_operation", {}))
    op.update({
        "status": "FIRST_REAL_V3_BOUNDARY_FORENSIC_PROBE_COMPLETE_PENDING_INDEPENDENT_AUDIT",
        "failed_v3_arm_status": "HISTORICAL_FAILED_CLOSED_DO_NOT_RERUN",
        "failed_v3_execution_authority_ref": FAILURE_AUTH_REL,
        "failed_v3_execution_authority_sha256": sha256_file(ROOT / FAILURE_AUTH_REL),
        "forensic_result_ref": result_ref,
        "forensic_result_sha256": result_sha,
        "forensic_result_authority_ref": authority_ref,
        "forensic_result_authority_sha256": authority_sha,
        "forensic_run_id": run_id,
        "forensic_job_id": job_id,
        "forensic_classification": classification,
        "forensic_history_request_count": 1,
        "forensic_history_retry_count": 0,
        "forensic_prices_persisted": False,
        "forensic_volume_persisted": False,
        "arm_present": True,
        "broker_acquisition_authorized": False,
        "real_historical_request_authorized": False,
        "protected_forward_opened": False,
        "confirmation_opened": False,
    })
    v4["shallow_m5_v2_current_operation"] = op

    cur["next_action"] = FINAL_STATE
    rb = dict(cur.get("shallow_m5_v2_operational_rebind", {}))
    rb.update({
        "failed_v3_arm_status": "HISTORICAL_FAILED_CLOSED_DO_NOT_RERUN",
        "failed_v3_execution_authority_ref": FAILURE_AUTH_REL,
        "forensic_result_ref": result_ref,
        "forensic_result_sha256": result_sha,
        "forensic_result_authority_ref": authority_ref,
        "forensic_result_authority_sha256": authority_sha,
        "forensic_classification": classification,
        "forensic_history_request_count": 1,
        "forensic_prices_persisted": False,
        "forensic_volume_persisted": False,
        "acquisition_authorized": False,
    })
    cur["shallow_m5_v2_operational_rebind"] = rb

    auth["next_action"] = FINAL_STATE
    auth["current_operation"] = FINAL_STATE
    rb2 = dict(auth.get("shallow_m5_v2_operational_rebind", {}))
    rb2.update({
        "failed_v3_arm_status": "HISTORICAL_FAILED_CLOSED_DO_NOT_RERUN",
        "failed_v3_execution_authority_ref": FAILURE_AUTH_REL,
        "forensic_result_ref": result_ref,
        "forensic_result_sha256": result_sha,
        "forensic_result_authority_ref": authority_ref,
        "forensic_result_authority_sha256": authority_sha,
        "forensic_classification": classification,
        "forensic_history_request_count": 1,
        "forensic_prices_persisted": False,
        "forensic_volume_persisted": False,
        "new_economic_outcome_authorized": False,
        "orders_authorized": False,
    })
    auth["shallow_m5_v2_operational_rebind"] = rb2

    return {
        "research_core_v4/state/V4_STATE.json": json.dumps(v4, indent=2, ensure_ascii=False).encode("utf-8") + b"\n",
        "adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json": json.dumps(cur, indent=2, ensure_ascii=False).encode("utf-8") + b"\n",
        "adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json": json.dumps(auth, indent=2, ensure_ascii=False).encode("utf-8") + b"\n",
    }


def publish(result_base: Path) -> dict:
    token = os.environ.get("GH_TOKEN", "")
    run_id = int(os.environ["GITHUB_RUN_ID"])
    base_commit = os.environ["GITHUB_SHA"]
    repository = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ["GITHUB_REF_NAME"]
    if not token or repository != REPO or branch != BRANCH:
        raise PermissionError("FORENSIC_PUBLICATION_CONTEXT_INVALID")

    result = load_json(result_base)
    _assert_no_forbidden_persistence(result)
    if result.get("history_request_count") != 1 or result.get("history_retry_count") != 0:
        raise RuntimeError("FORENSIC_HISTORY_CARDINALITY_NOT_EXACT")

    jobs = _api("GET", f"/repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100", token)
    candidates = [j for j in jobs.get("jobs", []) if j.get("name") == "forensic-probe"]
    if len(candidates) != 1:
        raise RuntimeError("FORENSIC_JOB_ID_NOT_UNIQUE")
    job_id = int(candidates[0]["id"])

    result["workflow_run_id"] = run_id
    result["workflow_job_id"] = job_id
    result["forensic_arm_commit"] = base_commit
    result_bytes = canonical_bytes(result) + b"\n"
    result_sha = sha256_bytes(result_bytes)
    classification = result["geometry"]["forensic_classification"]

    authority = {
        "schema": "mxm.v4.breadth-first-shallow-m5-support-v2.v3-boundary-forensic-result-authority.v1",
        "status": "FORENSIC_RESPONSE_MATERIALIZED_PENDING_INDEPENDENT_AUDIT",
        "failed_v3_execution_authority_ref": FAILURE_AUTH_REL,
        "failed_v3_execution_authority_sha256": sha256_file(ROOT / FAILURE_AUTH_REL),
        "failed_arm_commit": FAILED_ARM_COMMIT,
        "failed_arm_sha256": FAILED_ARM_SHA256,
        "failed_v3_arm_status": "HISTORICAL_FAILED_CLOSED_DO_NOT_RERUN",
        "failed_v3_workflow_rerun_count": 0,
        "forensic_arm_commit": base_commit,
        "forensic_workflow_run_id": run_id,
        "forensic_workflow_job_id": job_id,
        "forensic_result_ref": RESULT_REL,
        "forensic_result_sha256": result_sha,
        "forensic_classification": classification,
        "exact_forensic_history_request_count": 1,
        "exact_forensic_history_retry_count": 0,
        "prices_persisted": False,
        "volume_persisted": False,
        "raw_trendbar_payload_persisted": False,
        "economic_outcomes_opened": 0,
        "orders": 0,
        "protected_forward_used": False,
        "confirmation_opened": False,
        "next_state": FINAL_STATE,
    }
    authority_bytes = canonical_bytes(authority) + b"\n"
    authority_sha = sha256_bytes(authority_bytes)

    files: dict[str, bytes] = {
        RESULT_REL: result_bytes,
        RESULT_AUTH_REL: authority_bytes,
    }
    files.update(_publication_states(
        RESULT_REL, result_sha, RESULT_AUTH_REL, authority_sha, run_id, job_id, classification
    ))

    ref = _api("GET", f"/repos/{REPO}/git/ref/heads/{urllib.parse.quote(branch, safe='')}", token)
    if ref.get("object", {}).get("sha") != base_commit:
        raise RuntimeError("FORENSIC_PUBLICATION_BRANCH_DRIFT")
    base_git_commit = _api("GET", f"/repos/{REPO}/git/commits/{base_commit}", token)
    base_tree = base_git_commit["tree"]["sha"]

    tree_entries = []
    for path, data in files.items():
        blob = _api("POST", f"/repos/{REPO}/git/blobs", token, {
            "content": data.decode("utf-8"), "encoding": "utf-8"
        })
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree = _api("POST", f"/repos/{REPO}/git/trees", token, {
        "base_tree": base_tree, "tree": tree_entries
    })
    commit = _api("POST", f"/repos/{REPO}/git/commits", token, {
        "message": "Materialize first real V3 boundary forensic response",
        "tree": tree["sha"],
        "parents": [base_commit],
    })
    _api("PATCH", f"/repos/{REPO}/git/refs/heads/{urllib.parse.quote(branch, safe='')}", token, {
        "sha": commit["sha"], "force": False
    })
    summary = {
        "publication_commit": commit["sha"],
        "result_ref": RESULT_REL,
        "result_sha256": result_sha,
        "result_authority_ref": RESULT_AUTH_REL,
        "result_authority_sha256": authority_sha,
        "run_id": run_id,
        "job_id": job_id,
        "classification": classification,
    }
    print(json.dumps(summary, sort_keys=True))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-arm")
    run = sub.add_parser("run")
    run.add_argument("--output", type=Path, required=True)
    pub = sub.add_parser("publish")
    pub.add_argument("--result-base", type=Path, required=True)
    args = ap.parse_args()

    if args.command == "validate-arm":
        arm = validate_arm()
        validate_arm_git_event(arm)
        if sha256_file(ROOT / FAILED_ARM_REL) != FAILED_ARM_SHA256:
            raise PermissionError("FAILED_ARM_BYTES_CHANGED")
        print(json.dumps({"status": "PASS_EXACT_SINGLE_REQUEST_FORENSIC_ARM"}, sort_keys=True))
        return 0
    if args.command == "run":
        result = run_probe(args.output)
        print(json.dumps({
            "status": result["status"],
            "classification": result["geometry"]["forensic_classification"],
            "history_request_count": result["history_request_count"],
        }, sort_keys=True))
        return 0
    publish(args.result_base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
