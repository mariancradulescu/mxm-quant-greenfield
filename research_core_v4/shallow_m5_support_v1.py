"""Outcome-blind pre-arm laws for breadth-first shallow M5 support V1.

This module is deliberately network-free. It freezes roster binding, request order,
pagination, checkpoint, integrity, artifact and post-capture support laws. It cannot
contact cTrader, authenticate, subscribe, request history, place orders, or arm a run.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

SCHEMA = "mxm.v4.breadth-first-shallow-m5-support-v1.prearm.v1"
STATUS = "PENDING_INDEPENDENT_AUDIT_OF_BREADTH_FIRST_SHALLOW_M5_SUPPORT_V1_PREARM_ARCHITECTURE_BEFORE_ANY_NEW_HISTORICAL_REQUEST"
MASTER_REL = "research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json"
EXPECTED_MASTER_COUNT = 1576
EXPECTED_MASTER_SHA256 = "2287445f9b8dbd61ef40a1d81756e1848c2b623a846bc968c4e214d9b2a874e1"
EXPECTED_ACCOUNT_FINGERPRINT_SHA256 = "b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636"
EXPECTED_AUTH_STATUS = "PROVEN_MACHINE_SIDE_READ_ONLY_AUTH_ONLY"
RESOLUTION = "M5"
PAGE_SIZE = 5000
MAX_HISTORICAL_REQUEST_RATE_PER_CONNECTION = 4
MIN_HISTORICAL_REQUEST_INTERVAL_SECONDS = 0.25
MAX_WIRE_ATTEMPTS_PER_LOGICAL_REQUEST = 3
HEARTBEAT_IDLE_SECONDS = 10.0
PROTECTED_FORWARD_BOUNDARY_UTC = "2026-09-17T12:02:58Z"
FIXED_WINDOW_START_UTC = "2026-08-20T00:00:00Z"
FIXED_WINDOW_END_UTC = "2026-09-16T23:55:00Z"
RAW_HEADER = ("time_utc", "open", "high", "low", "close", "tick_volume")
SEGMENTS = (
    ("2026-08-20T00:00:00Z", "2026-08-26T23:55:00Z"),
    ("2026-08-27T00:00:00Z", "2026-09-02T23:55:00Z"),
    ("2026-09-03T00:00:00Z", "2026-09-09T23:55:00Z"),
    ("2026-09-10T00:00:00Z", "2026-09-16T23:55:00Z"),
)
THEORETICAL_M5_SLOTS_PER_SEGMENT = 7 * 24 * 12
THEORETICAL_M5_SLOTS_FULL_WINDOW = 4 * THEORETICAL_M5_SLOTS_PER_SEGMENT
LOGICAL_REQUEST_BOUND = EXPECTED_MASTER_COUNT * len(SEGMENTS)
WIRE_ATTEMPT_BOUND = LOGICAL_REQUEST_BOUND * MAX_WIRE_ATTEMPTS_PER_LOGICAL_REQUEST
ALLOWED_SUPPORT_CLASSIFICATIONS = frozenset({
    "SHALLOW_SUPPORT_COMPLETE",
    "SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED",
    "NO_HISTORICAL_SUPPORT",
    "IDENTITY_OR_MAPPING_FAILURE",
})
FORBIDDEN_OPERATION_TOKENS = frozenset({
    "ProtoOANewOrderReq", "ProtoOAClosePositionReq", "ProtoOACancelOrderReq",
    "ProtoOAAmendOrderReq", "ProtoOASubscribeSpotsReq", "ProtoOASubscribeDepthQuotesReq",
    "ProtoOAGetTickDataReq", "ProtoOARefreshTokenReq",
})
ALLOWED_HISTORICAL_MESSAGE = "ProtoOAGetTrendbarsReq"
ALLOWED_HISTORICAL_RESPONSE = "ProtoOAGetTrendbarsRes"


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp must end in Z")
    dt = datetime.fromisoformat(value[:-1] + "+00:00")
    if dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)
    return dt


def to_ms(value: str) -> int:
    return int(parse_utc(value).timestamp() * 1000)


def validate_master_value(master: Sequence[Mapping]) -> list[dict]:
    data = [dict(x) for x in master]
    if len(data) != EXPECTED_MASTER_COUNT:
        raise ValueError("frontier must have exact1576 identities")
    if any(
        set(x) != {"symbol", "symbol_id", "asset_class"}
        or type(x["symbol_id"]) is not int
        or x["symbol_id"] <= 0
        or not isinstance(x["symbol"], str)
        or not x["symbol"]
        or not isinstance(x["asset_class"], str)
        or not x["asset_class"]
        for x in data
    ):
        raise ValueError("frontier shape invalid")
    if len({x["symbol_id"] for x in data}) != EXPECTED_MASTER_COUNT:
        raise ValueError("frontier symbol_id duplicates")
    if len({x["symbol"] for x in data}) != EXPECTED_MASTER_COUNT:
        raise ValueError("frontier symbol duplicates")
    if data != sorted(data, key=lambda x: x["symbol_id"]):
        raise ValueError("frontier order must be frozen ascending symbol_id")
    if sha256_bytes(canonical(data)) != EXPECTED_MASTER_SHA256:
        raise ValueError("authoritative identity hash mismatch")
    return data


def load_master(root: Path | str) -> list[dict]:
    return validate_master_value(json.loads((Path(root) / MASTER_REL).read_bytes()))


def validate_fixed_calendar() -> None:
    if len(SEGMENTS) != 4:
        raise ValueError("exact four calendar segments required")
    if SEGMENTS[0][0] != FIXED_WINDOW_START_UTC or SEGMENTS[-1][1] != FIXED_WINDOW_END_UTC:
        raise ValueError("fixed window edge mismatch")
    previous_end = None
    for start, end in SEGMENTS:
        s, e = parse_utc(start), parse_utc(end)
        if s.second or s.microsecond or e.second or e.microsecond or s.minute % 5 or e.minute % 5:
            raise ValueError("segment timestamps must be M5 aligned")
        slots = int((e - s).total_seconds() // 300) + 1
        if slots != THEORETICAL_M5_SLOTS_PER_SEGMENT:
            raise ValueError("segment must contain exactly seven calendar days of M5 slots")
        if previous_end is not None and s.timestamp() - previous_end.timestamp() != 300:
            raise ValueError("segments must be contiguous with one M5 step")
        previous_end = e
    if not parse_utc(FIXED_WINDOW_END_UTC) < parse_utc(PROTECTED_FORWARD_BOUNDARY_UTC):
        raise ValueError("fixed window must remain strictly before protected forward")


def build_request_manifest(master: Sequence[Mapping]) -> list[dict]:
    validate_fixed_calendar()
    checked = validate_master_value(master)
    out: list[dict] = []
    # Breadth-first is segment-major: all identities receive week one before week two.
    for segment_index, (start, end) in enumerate(SEGMENTS):
        for master_index, identity in enumerate(checked):
            out.append({
                "request_id": f"BFM5V1-S{segment_index + 1:02d}-I{master_index + 1:04d}-ID{identity['symbol_id']}",
                "segment_index": segment_index,
                "master_index": master_index,
                "symbol_id": identity["symbol_id"],
                "symbol": identity["symbol"],
                "asset_class": identity["asset_class"],
                "resolution": RESOLUTION,
                "from_utc": start,
                "to_utc_inclusive": end,
                "count": PAGE_SIZE,
                "status": "PLANNED",
            })
    if len(out) != LOGICAL_REQUEST_BOUND:
        raise ValueError("request manifest cardinality mismatch")
    if len({x["request_id"] for x in out}) != LOGICAL_REQUEST_BOUND:
        raise ValueError("request manifest uniqueness mismatch")
    if (
        out[0]["segment_index"] != 0
        or out[EXPECTED_MASTER_COUNT - 1]["segment_index"] != 0
        or out[EXPECTED_MASTER_COUNT]["segment_index"] != 1
    ):
        raise ValueError("request ordering is not breadth-first segment-major")
    return out


@dataclass(frozen=True)
class PageDecision:
    complete: bool
    fail_closed: bool
    reason: str
    next_to_ms: int | None = None


def decide_pagination(
    *,
    request_from_ms: int,
    request_to_ms: int,
    raw_open_times_ms: Sequence[int],
    has_more_exposed: bool,
    has_more: bool | None,
    page_size: int = PAGE_SIZE,
) -> PageDecision:
    if request_from_ms > request_to_ms:
        raise ValueError("invalid request bounds")
    if page_size <= 0:
        raise ValueError("invalid page size")
    times = [int(x) for x in raw_open_times_ms]
    if any(t < request_from_ms or t > request_to_ms for t in times):
        return PageDecision(False, True, "ROW_OUTSIDE_REQUEST_INTERVAL")
    if times != sorted(times):
        return PageDecision(False, True, "TIMESTAMP_ORDER_FAILURE")
    if len(set(times)) != len(times):
        return PageDecision(False, True, "DUPLICATE_TIMESTAMP_FAILURE")
    if len(times) > page_size:
        return PageDecision(False, True, "PAGE_SIZE_EXCEEDED")
    if not times:
        if has_more_exposed and has_more is True:
            return PageDecision(False, True, "EMPTY_PAGE_WITH_HASMORE_TRUE")
        return PageDecision(True, False, "EMPTY_INTERVAL_EXHAUSTED")
    oldest = times[0]
    if oldest <= request_from_ms:
        return PageDecision(True, False, "FROM_BOUNDARY_REACHED")
    if has_more_exposed:
        if has_more is False:
            return PageDecision(True, False, "HAS_MORE_FALSE")
        if has_more is not True:
            return PageDecision(False, True, "INVALID_HASMORE_VALUE")
        if len(times) < page_size:
            return PageDecision(False, True, "HAS_MORE_TRUE_ON_SHORT_PAGE")
    elif len(times) < page_size:
        return PageDecision(True, False, "SHORT_PAGE_INTERVAL_EXHAUSTED")
    nxt = oldest - 1
    if nxt >= request_to_ms or nxt < request_from_ms:
        return PageDecision(False, True, "NON_PROGRESSING_PAGINATION")
    return PageDecision(False, False, "CONTINUE_BACKWARD", next_to_ms=nxt)


def production_segment_response_guard(raw_open_times_ms: Sequence[int]) -> None:
    # Seven calendar days contain only 2016 aligned M5 slots. A valid production
    # response therefore cannot fill the frozen 5000-bar page.
    times = [int(x) for x in raw_open_times_ms]
    if len(times) > THEORETICAL_M5_SLOTS_PER_SEGMENT:
        raise ValueError("more bars than theoretical M5 slots in frozen seven-day segment")
    if any(t % 300000 for t in times):
        raise ValueError("trendbar timestamp not M5 aligned")
    if len(set(times)) != len(times):
        raise ValueError("duplicate trendbar timestamp")


def seal_record(record: Mapping) -> dict:
    if "checkpoint_sha256" in record:
        raise ValueError("record already sealed")
    body = dict(record)
    return {**body, "checkpoint_sha256": sha256_bytes(canonical(body))}


def verify_sealed_record(record: Mapping) -> dict:
    body = dict(record)
    given = body.pop("checkpoint_sha256", None)
    if given != sha256_bytes(canonical(body)):
        raise ValueError("checkpoint integrity failure")
    return body


def new_checkpoint(plan_sha256: str) -> dict:
    body = {
        "schema": "mxm.v4.breadth-first-shallow-m5-support-v1.checkpoint.v1",
        "plan_sha256": plan_sha256,
        "completed_request_ids": [],
        "inflight": None,
        "segments": {},
        "wire_attempts": {},
    }
    return seal_record(body)


def atomic_write_sealed_json(path: Path | str, body: Mapping) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sealed = seal_record(body)
    payload = canonical(sealed) + b"\n"
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except (OSError, AttributeError):
        pass


def mark_request_completed(checkpoint: Mapping, request_id: str, segment_meta: Mapping) -> dict:
    body = verify_sealed_record(checkpoint)
    completed = list(body["completed_request_ids"])
    if request_id in completed:
        raise ValueError("completed request cannot be repeated")
    completed.append(request_id)
    segments = dict(body["segments"])
    segments[request_id] = dict(segment_meta)
    body.update(completed_request_ids=completed, inflight=None, segments=segments)
    return seal_record(body)


def can_send_request(checkpoint: Mapping, request_id: str) -> bool:
    body = verify_sealed_record(checkpoint)
    return request_id not in set(body["completed_request_ids"])


def deterministic_shard_index(master_index: int, shard_size: int = 64) -> int:
    if master_index < 0 or master_index >= EXPECTED_MASTER_COUNT or shard_size <= 0:
        raise ValueError("invalid shard input")
    return master_index // shard_size


def shard_count(shard_size: int = 64) -> int:
    return math.ceil(EXPECTED_MASTER_COUNT / shard_size)


def inspect_csv_rows(
    rows: Sequence[Mapping], *, segment_start: str, segment_end: str
) -> dict:
    start_ms, end_ms = to_ms(segment_start), to_ms(segment_end)
    protected_ms = to_ms(PROTECTED_FORWARD_BOUNDARY_UTC)
    timestamps: list[int] = []
    duplicate_count = 0
    seen = set()
    ohlc_failures = 0
    protected_rows = 0
    out_of_interval = 0
    flat = 0
    volume_present = 0
    for row in rows:
        if set(row) != set(RAW_HEADER):
            raise ValueError("raw row schema mismatch")
        ts = to_ms(str(row["time_utc"]))
        timestamps.append(ts)
        if ts in seen:
            duplicate_count += 1
        seen.add(ts)
        if ts < start_ms or ts > end_ms:
            out_of_interval += 1
        if ts >= protected_ms:
            protected_rows += 1
        o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
        v = float(row["tick_volume"])
        if not (l <= min(o, c) <= max(o, c) <= h) or v < 0:
            ohlc_failures += 1
        flat += int(o == h == l == c)
        volume_present += int(v > 0)
    order_ok = timestamps == sorted(timestamps)
    return {
        "row_count": len(rows),
        "first_timestamp_utc": rows[0]["time_utc"] if rows else None,
        "last_timestamp_utc": rows[-1]["time_utc"] if rows else None,
        "duplicate_timestamp_count": duplicate_count,
        "timestamp_order_check": order_ok,
        "ohlc_invariant_failures": ohlc_failures,
        "protected_forward_row_count": protected_rows,
        "out_of_interval_row_count": out_of_interval,
        "flat_or_zero_activity_bar_count": flat,
        "positive_tick_volume_bar_count": volume_present,
    }


def validate_segment_integrity(metrics: Mapping) -> None:
    gates = {
        "duplicate_timestamp_count": 0,
        "ohlc_invariant_failures": 0,
        "protected_forward_row_count": 0,
        "out_of_interval_row_count": 0,
    }
    for key, expected in gates.items():
        if int(metrics.get(key, -1)) != expected:
            raise ValueError(f"segment integrity failed: {key}")
    if metrics.get("timestamp_order_check") is not True:
        raise ValueError("segment integrity failed: timestamp order")


def classify_support(
    *, mapping_failure: bool, segment_complete: Sequence[bool], row_count: int
) -> str:
    if mapping_failure:
        return "IDENTITY_OR_MAPPING_FAILURE"
    if len(segment_complete) != 4:
        raise ValueError("exact four segment completion states required")
    if all(segment_complete):
        return "NO_HISTORICAL_SUPPORT" if int(row_count) == 0 else "SHALLOW_SUPPORT_COMPLETE"
    return "SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED"


def support_metrics(rows: Sequence[Mapping]) -> dict:
    if not rows:
        return {
            "row_count": 0,
            "coverage_fraction": 0.0,
            "active_day_count": 0,
            "nonflat_bar_fraction": None,
            "tick_volume_presence": False,
            "gap_fraction": None,
            "median_interbar_gap_seconds": None,
            "realized_volatility_support_only": None,
            "coarse_multiscale_aggregation_availability": {
                "M15": False, "M30": False, "H1": False, "H4": False
            },
        }
    ordered = sorted(rows, key=lambda x: x["time_utc"])
    ts = [parse_utc(str(x["time_utc"])) for x in ordered]
    closes = [float(x["close"]) for x in ordered]
    gaps = [(b - a).total_seconds() for a, b in zip(ts, ts[1:])]
    missing_slots = sum(max(0, int(g // 300) - 1) for g in gaps)
    denom = len(ordered) + missing_slots
    flat = sum(
        float(x["open"]) == float(x["high"]) == float(x["low"]) == float(x["close"])
        for x in ordered
    )
    returns = []
    for a, b in zip(closes, closes[1:]):
        if a > 0 and b > 0:
            returns.append(math.log(b / a))
    rv = math.sqrt(sum(x * x for x in returns)) if returns else None
    median_gap = None
    if gaps:
        sg = sorted(gaps)
        n = len(sg)
        median_gap = sg[n // 2] if n % 2 else (sg[n // 2 - 1] + sg[n // 2]) / 2
    availability = {
        name: len(ordered) >= bars
        for name, bars in {"M15": 3, "M30": 6, "H1": 12, "H4": 48}.items()
    }
    return {
        "row_count": len(ordered),
        "coverage_fraction": len(ordered) / THEORETICAL_M5_SLOTS_FULL_WINDOW,
        "active_day_count": len({x["time_utc"][:10] for x in ordered}),
        "nonflat_bar_fraction": (len(ordered) - flat) / len(ordered),
        "tick_volume_presence": any(float(x["tick_volume"]) > 0 for x in ordered),
        "gap_fraction": (missing_slots / denom) if denom else None,
        "median_interbar_gap_seconds": median_gap,
        "realized_volatility_support_only": rv,
        "coarse_multiscale_aggregation_availability": availability,
    }


def deterministic_chunk_manifest(chunks: Sequence[Mapping]) -> dict:
    normalized = []
    for x in chunks:
        required = {
            "request_id", "path", "sha256", "row_count",
            "first_timestamp_utc", "last_timestamp_utc",
        }
        if not required.issubset(x):
            raise ValueError("chunk manifest entry incomplete")
        normalized.append({k: x[k] for k in sorted(x)})
    normalized.sort(key=lambda x: x["request_id"])
    body = {
        "schema": "mxm.v4.shallow-m5-support-v1.chunk-manifest.v1",
        "chunks": normalized,
    }
    return {**body, "manifest_sha256": sha256_bytes(canonical(body))}


def scan_for_private_values(payload: bytes | str, private_values: Iterable[str]) -> None:
    text_value = (
        payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
    )
    forbidden_key_pattern = re.compile(
        r"(?i)(client[_-]?secret|access[_-]?token|refresh[_-]?token|"
        r"ctid[_-]?trader[_-]?account[_-]?id|trader[_-]?login)\s*[:=]"
    )
    if forbidden_key_pattern.search(text_value):
        raise ValueError("private field name persisted")
    for value in private_values:
        value = str(value or "")
        if value and value in text_value:
            raise ValueError("known private value persisted")


def assert_zero_forbidden_operations(operation_names: Iterable[str]) -> None:
    names = set(str(x) for x in operation_names)
    bad = sorted(names & FORBIDDEN_OPERATION_TOKENS)
    if bad:
        raise ValueError(f"forbidden operation present: {bad}")


def retry_policy_for_error(error_code: str) -> str:
    code = str(error_code or "")
    if code in {"OA_AUTH_TOKEN_EXPIRED", "ACCOUNT_NOT_AUTHORIZED", "INVALID_TOKEN"}:
        return "FAIL_CLOSED_NO_REFRESH"
    if code in {"SERVER_UNAVAILABLE", "CONNECTION_RESET", "TIMEOUT"}:
        return "RETRY_SAME_IMMUTABLE_REQUEST_BOUNDED"
    if code in {"REQUEST_FREQUENCY_EXCEEDED", "SYMBOL_NOT_FOUND", "INCORRECT_BOUNDARIES"}:
        return "FAIL_CLOSED"
    return "FAIL_CLOSED_UNRECOGNIZED"


def freeze_summary() -> dict:
    validate_fixed_calendar()
    return {
        "schema": SCHEMA,
        "status": STATUS,
        "resolution": RESOLUTION,
        "master_count": EXPECTED_MASTER_COUNT,
        "master_sha256": EXPECTED_MASTER_SHA256,
        "account_fingerprint_sha256": EXPECTED_ACCOUNT_FINGERPRINT_SHA256,
        "auth_status": EXPECTED_AUTH_STATUS,
        "fixed_window": {
            "from_utc": FIXED_WINDOW_START_UTC,
            "to_utc_inclusive": FIXED_WINDOW_END_UTC,
        },
        "protected_forward_boundary_utc": PROTECTED_FORWARD_BOUNDARY_UTC,
        "segments": [
            {"segment_index": i, "from_utc": a, "to_utc_inclusive": b}
            for i, (a, b) in enumerate(SEGMENTS)
        ],
        "ordering": "SEGMENT_MAJOR_THEN_FROZEN_MASTER_ORDER",
        "page_size": PAGE_SIZE,
        "rate_limit_per_connection": MAX_HISTORICAL_REQUEST_RATE_PER_CONNECTION,
        "min_request_interval_seconds": MIN_HISTORICAL_REQUEST_INTERVAL_SECONDS,
        "max_wire_attempts_per_logical_request": MAX_WIRE_ATTEMPTS_PER_LOGICAL_REQUEST,
        "logical_historical_request_bound": LOGICAL_REQUEST_BOUND,
        "wire_attempt_bound_including_retries": WIRE_ATTEMPT_BOUND,
        "heartbeat_idle_seconds": HEARTBEAT_IDLE_SECONDS,
        "raw_shard_size_identities": 64,
        "raw_shard_count": shard_count(64),
        "arm_present": False,
        "broker_contact": False,
        "historical_requests_sent": 0,
        "economic_outcomes_opened": 0,
    }
