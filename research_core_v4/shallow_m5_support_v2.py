"""Corrected offline-only pre-arm protocol/decoder closure for shallow M5 support V2.

No networking, credential access, broker contact, history acquisition, orders,
subscriptions, depth, ticks, token refresh, or ARM creation is implemented here.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage

MASTER_REL = "research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json"
LOCALIZATION_REL = "research_core_v4/state/NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64"
INTAKE_REL = "research_core_v4/state/NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_INTAKE_V1.json"

MASTER_COUNT = 1576
MASTER_SHA256 = "2287445f9b8dbd61ef40a1d81756e1848c2b623a846bc968c4e214d9b2a874e1"
ACCOUNT_FINGERPRINT_SHA256 = "b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636"
LOCALIZATION_SHA256 = "4ceb988206c6caf5c0077d12201e9043c5bd640c63fd645c20273fafa9fcb63f"

OFFICIAL_PROTO_COMMIT = "3fd8bddfbe0cfc2ecfda079623dc4e498af11e66"
OFFICIAL_PROTO_DIR = "research_core_v4/protocol_v2/spotware_openapi_proto_3fd8bddfbe0c"
OFFICIAL_PROTO_GIT_BLOB_SHA1 = {
    "OpenApiMessages.proto": "e862a857e741e95208791e75a805d9b0cbdfa124",
    "OpenApiModelMessages.proto": "1a11cf767b4fc0e8093eabf72154c7ac4fff2807",
    "OpenApiCommonMessages.proto": "a21699b17c0101f4fc230710743449aab92e9685",
    "OpenApiCommonModelMessages.proto": "a420d2bea7a92c9e31a97c3a67d3553f97b1e21d",
}
PROTO_OA_GET_TRENDBARS_REQ_PAYLOAD_TYPE = 2137
PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE = 2138

M5_ENUM = 5
M5_MILLISECONDS = 300_000
PAGE_REQUESTED_COUNT = 5000
SEGMENT_COUNT = 4
THEORETICAL_M5_SLOTS_PER_SEGMENT = 2016
LOGICAL_IDENTITY_SEGMENT_COUNT = MASTER_COUNT * SEGMENT_COUNT
MAXIMUM_PAGES_PER_IDENTITY_SEGMENT = 3
MAXIMUM_PAGE_REQUEST_COUNT = LOGICAL_IDENTITY_SEGMENT_COUNT * MAXIMUM_PAGES_PER_IDENTITY_SEGMENT
MAXIMUM_RETRIES_AFTER_INITIAL_ATTEMPT = 2
MAXIMUM_WIRE_ATTEMPTS_PER_PAGE = 1 + MAXIMUM_RETRIES_AFTER_INITIAL_ATTEMPT
TRUE_ABSOLUTE_MAXIMUM_WIRE_ATTEMPTS = MAXIMUM_PAGE_REQUEST_COUNT * MAXIMUM_WIRE_ATTEMPTS_PER_PAGE

MAXIMUM_HISTORICAL_REQUESTS_PER_SECOND = 4
MINIMUM_INTER_REQUEST_SECONDS = 0.25
HEARTBEAT_IDLE_SECONDS = 10

FIXED_WINDOW_START_UTC = "2026-08-20T00:00:00Z"
FIXED_WINDOW_END_UTC_INCLUSIVE = "2026-09-16T23:55:00Z"
PROTECTED_FORWARD_BOUNDARY_UTC = "2026-09-17T12:02:58Z"
SEGMENTS = (
    ("2026-08-20T00:00:00Z", "2026-08-26T23:55:00Z"),
    ("2026-08-27T00:00:00Z", "2026-09-02T23:55:00Z"),
    ("2026-09-03T00:00:00Z", "2026-09-09T23:55:00Z"),
    ("2026-09-10T00:00:00Z", "2026-09-16T23:55:00Z"),
)
RAW_HEADER = ("time_utc", "open", "high", "low", "close", "tick_volume")


def _add_field(msg, name, number, label, field_type, type_name=None, default_value=None):
    field = msg.field.add()
    field.name = name
    field.number = number
    field.label = label
    field.type = field_type
    if type_name is not None:
        field.type_name = type_name
    if default_value is not None:
        field.default_value = str(default_value)
    return field


def _build_current_trendbar_protocol_types():
    fd = descriptor_pb2.FileDescriptorProto()
    fd.name = "mxm_spotware_openapi_trendbars_v2.proto"
    fd.package = "mxm.spotware.v2"
    fd.syntax = "proto2"

    payload_enum = fd.enum_type.add()
    payload_enum.name = "ProtoOAPayloadType"
    for name, value in (
        ("PROTO_OA_GET_TRENDBARS_REQ", PROTO_OA_GET_TRENDBARS_REQ_PAYLOAD_TYPE),
        ("PROTO_OA_GET_TRENDBARS_RES", PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE),
    ):
        item = payload_enum.value.add()
        item.name = name
        item.number = value

    period_enum = fd.enum_type.add()
    period_enum.name = "ProtoOATrendbarPeriod"
    for name, value in (
        ("M1", 1), ("M2", 2), ("M3", 3), ("M4", 4), ("M5", 5),
        ("M10", 6), ("M15", 7), ("M30", 8), ("H1", 9), ("H4", 10),
        ("H12", 11), ("D1", 12), ("W1", 13), ("MN1", 14),
    ):
        item = period_enum.value.add()
        item.name = name
        item.number = value

    trend = fd.message_type.add()
    trend.name = "ProtoOATrendbar"
    _add_field(trend, "volume", 3, 2, 3)
    _add_field(trend, "period", 4, 1, 14, ".mxm.spotware.v2.ProtoOATrendbarPeriod", "M1")
    _add_field(trend, "low", 5, 1, 3)
    _add_field(trend, "deltaOpen", 6, 1, 4)
    _add_field(trend, "deltaClose", 7, 1, 4)
    _add_field(trend, "deltaHigh", 8, 1, 4)
    _add_field(trend, "utcTimestampInMinutes", 9, 1, 13)

    req = fd.message_type.add()
    req.name = "ProtoOAGetTrendbarsReq"
    _add_field(req, "payloadType", 1, 1, 14, ".mxm.spotware.v2.ProtoOAPayloadType", "PROTO_OA_GET_TRENDBARS_REQ")
    _add_field(req, "ctidTraderAccountId", 2, 2, 3)
    _add_field(req, "fromTimestamp", 3, 1, 3)
    _add_field(req, "toTimestamp", 4, 1, 3)
    _add_field(req, "period", 5, 2, 14, ".mxm.spotware.v2.ProtoOATrendbarPeriod")
    _add_field(req, "symbolId", 6, 2, 3)
    _add_field(req, "count", 7, 1, 13)

    res = fd.message_type.add()
    res.name = "ProtoOAGetTrendbarsRes"
    _add_field(res, "payloadType", 1, 1, 14, ".mxm.spotware.v2.ProtoOAPayloadType", "PROTO_OA_GET_TRENDBARS_RES")
    _add_field(res, "ctidTraderAccountId", 2, 2, 3)
    _add_field(res, "period", 3, 2, 14, ".mxm.spotware.v2.ProtoOATrendbarPeriod")
    _add_field(res, "timestamp", 4, 1, 3)
    _add_field(res, "trendbar", 5, 3, 11, ".mxm.spotware.v2.ProtoOATrendbar")
    _add_field(res, "symbolId", 6, 1, 3)
    _add_field(res, "hasMore", 7, 1, 8)

    pool = descriptor_pool.DescriptorPool()
    pool.Add(fd)
    req_cls = message_factory.GetMessageClass(pool.FindMessageTypeByName("mxm.spotware.v2.ProtoOAGetTrendbarsReq"))
    res_cls = message_factory.GetMessageClass(pool.FindMessageTypeByName("mxm.spotware.v2.ProtoOAGetTrendbarsRes"))
    bar_cls = message_factory.GetMessageClass(pool.FindMessageTypeByName("mxm.spotware.v2.ProtoOATrendbar"))
    return req_cls, res_cls, bar_cls


ProtoOAGetTrendbarsReqV2, ProtoOAGetTrendbarsResV2, ProtoOATrendbarV2 = _build_current_trendbar_protocol_types()


def git_blob_sha1_bytes(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def verify_vendored_protocol_sources(root: Path | str) -> dict:
    root = Path(root)
    result = {}
    for name, expected_blob in OFFICIAL_PROTO_GIT_BLOB_SHA1.items():
        raw = (root / OFFICIAL_PROTO_DIR / name).read_bytes()
        actual_blob = git_blob_sha1_bytes(raw)
        if actual_blob != expected_blob:
            raise ValueError(f"vendored official protocol source mismatch: {name}")
        result[name] = {
            "git_blob_sha1": actual_blob,
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
        }
    return result


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp must end in Z")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)


def utc_iso_from_unix_minutes(minutes: int) -> str:
    if type(minutes) is not int or minutes < 0:
        raise ValueError("invalid unix minutes")
    dt = datetime.fromtimestamp(minutes * 60, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_ms(value: str) -> int:
    return int(parse_utc(value).timestamp() * 1000)


def validate_master(master: Sequence[Mapping]) -> list[dict]:
    data = [dict(x) for x in master]
    if len(data) != MASTER_COUNT:
        raise ValueError("exact MASTER1576 required")
    if data != sorted(data, key=lambda x: x["symbol_id"]):
        raise ValueError("master order mismatch")
    if len({int(x["symbol_id"]) for x in data}) != MASTER_COUNT:
        raise ValueError("duplicate symbol ids")
    if sha256_bytes(canonical(data)) != MASTER_SHA256:
        raise ValueError("master hash mismatch")
    return data


def load_master(root: Path | str) -> list[dict]:
    return validate_master(json.loads((Path(root) / MASTER_REL).read_bytes()))


def load_accepted_localization(root: Path | str) -> dict:
    root = Path(root)
    intake = json.loads((root / INTAKE_REL).read_bytes())
    if intake.get("localization_sha256") != LOCALIZATION_SHA256:
        raise ValueError("intake localization hash mismatch")
    encoded = (root / LOCALIZATION_REL).read_bytes()
    try:
        compact = b"".join(encoded.split())
        compressed = base64.b64decode(compact, validate=True)
        raw = zlib.decompress(compressed)
    except Exception as exc:
        raise ValueError("accepted localization decode failure") from exc
    if sha256_bytes(raw) != LOCALIZATION_SHA256:
        raise ValueError("accepted localization byte hash mismatch")
    obj = json.loads(raw)
    if obj.get("frontier_identity_sha256") != MASTER_SHA256:
        raise ValueError("localization master binding mismatch")
    if obj.get("historical_requests_sent") != 0 or obj.get("orders_sent") != 0:
        raise ValueError("localization is not metadata-only")
    return obj


def build_digits_map(root: Path | str) -> dict:
    master = load_master(root)
    loc = load_accepted_localization(root)
    rows = loc.get("rows")
    if not isinstance(rows, list) or len(rows) != MASTER_COUNT:
        raise ValueError("localization rows must cover exact1576")
    by_id = {int(x["symbol_id"]): x for x in rows}
    if set(by_id) != {int(x["symbol_id"]) for x in master}:
        raise ValueError("digits source identity set mismatch")
    entries = []
    for ident in master:
        sid = int(ident["symbol_id"])
        row = by_id[sid]
        if row.get("symbol") != ident["symbol"] or row.get("asset_class") != ident["asset_class"]:
            raise ValueError(f"localization identity mismatch for {sid}")
        full = row.get("current_full_metadata")
        if not isinstance(full, dict):
            raise ValueError(f"full metadata missing for {sid}")
        if int(full.get("symbolId", -1)) != sid:
            raise ValueError(f"full metadata symbolId mismatch for {sid}")
        digits = full.get("digits")
        if type(digits) is not int or digits < 0 or digits > 15:
            raise ValueError(f"exact digits missing or invalid for {sid}")
        entries.append({"symbol_id": sid, "digits": digits})
    digest = sha256_bytes(canonical(entries))
    return {
        "schema": "mxm.v4.breadth-first-shallow-m5-support-v2.symbol-digits-map.v1",
        "master_count": MASTER_COUNT,
        "master_sha256": MASTER_SHA256,
        "source_localization_sha256": LOCALIZATION_SHA256,
        "entries": entries,
        "digits_map_sha256": digest,
    }


def write_digits_map(root: Path | str, output: Path | str) -> dict:
    result = build_digits_map(root)
    Path(output).write_bytes(canonical(result) + b"\n")
    return result


def digits_lookup(digits_map: Mapping) -> dict[int, int]:
    entries = digits_map.get("entries")
    if not isinstance(entries, list) or len(entries) != MASTER_COUNT:
        raise ValueError("exact digits map required")
    lookup = {int(x["symbol_id"]): int(x["digits"]) for x in entries}
    if len(lookup) != MASTER_COUNT:
        raise ValueError("digits map duplicate symbol ids")
    if digits_map.get("digits_map_sha256") != sha256_bytes(canonical(entries)):
        raise ValueError("digits map hash mismatch")
    return lookup


def exact_price_string(relative_value: int, digits: int) -> str:
    if type(relative_value) is not int:
        raise ValueError("relative price must be integer")
    if type(digits) is not int or digits < 0 or digits > 15:
        raise ValueError("invalid digits")
    value = Decimal(relative_value) / Decimal(100000)
    quantum = Decimal(1).scaleb(-digits)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        rounded = abs(rounded)
    return format(rounded, f".{digits}f")


@dataclass(frozen=True)
class RequestContext:
    client_msg_id: str
    authenticated_account_id: int
    symbol_id: int
    from_ms: int
    to_ms: int
    count: int = PAGE_REQUESTED_COUNT
    period: int = M5_ENUM

    def __post_init__(self):
        if not self.client_msg_id:
            raise ValueError("clientMsgId required")
        if type(self.authenticated_account_id) is not int or self.authenticated_account_id <= 0:
            raise ValueError("authenticated account required in memory")
        if type(self.symbol_id) is not int or self.symbol_id <= 0:
            raise ValueError("symbol id required")
        if self.period != M5_ENUM or self.count != PAGE_REQUESTED_COUNT:
            raise ValueError("frozen M5/count mismatch")
        if type(self.from_ms) is not int or type(self.to_ms) is not int or self.from_ms > self.to_ms:
            raise ValueError("invalid request interval")


def validate_request(req, ctx: RequestContext) -> None:
    if type(req) is not ProtoOAGetTrendbarsReqV2 or not req.IsInitialized():
        raise ValueError("exact initialized ProtoOAGetTrendbarsReq required")
    for field in ("fromTimestamp", "toTimestamp", "count"):
        if not req.HasField(field):
            raise ValueError(f"frozen request field absent: {field}")
    if int(req.ctidTraderAccountId) != ctx.authenticated_account_id:
        raise ValueError("request account mismatch")
    if int(req.symbolId) != ctx.symbol_id:
        raise ValueError("request symbol mismatch")
    if int(req.period) != M5_ENUM or int(req.period) != ctx.period:
        raise ValueError("request period mismatch")
    if int(req.fromTimestamp) != ctx.from_ms or int(req.toTimestamp) != ctx.to_ms:
        raise ValueError("request interval mismatch")
    if int(req.count) != PAGE_REQUESTED_COUNT or int(req.count) != ctx.count:
        raise ValueError("request count mismatch")


def response_has_more_presence(response) -> tuple[bool, bool | None]:
    if type(response) is not ProtoOAGetTrendbarsResV2:
        raise ValueError("wrong response type")
    present = response.HasField("hasMore")
    return present, (bool(response.hasMore) if present else None)


def bind_response_envelope(envelope: ProtoMessage, ctx: RequestContext):
    if type(envelope) is not ProtoMessage:
        raise ValueError("exact ProtoMessage envelope required")
    if not envelope.HasField("clientMsgId") or str(envelope.clientMsgId) != ctx.client_msg_id:
        raise ValueError("wrong or absent response clientMsgId")
    expected_payload_type = PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE
    if int(envelope.payloadType) != expected_payload_type:
        raise ValueError("wrong response payload type")
    response = ProtoOAGetTrendbarsResV2()
    response.ParseFromString(envelope.payload)
    if not response.IsInitialized():
        raise ValueError("uninitialized trendbars response")
    if int(response.ctidTraderAccountId) != ctx.authenticated_account_id:
        raise ValueError("wrong response account")
    if int(response.period) != M5_ENUM or int(response.period) != ctx.period:
        raise ValueError("wrong response period")
    if response.HasField("symbolId") and int(response.symbolId) != ctx.symbol_id:
        raise ValueError("wrong present response symbolId")
    for bar in response.trendbar:
        if bar.HasField("period") and int(bar.period) != M5_ENUM:
            raise ValueError("wrong present trendbar period")
    return response


def decode_trendbar(bar, *, digits: int, segment_from_ms: int, segment_to_ms: int) -> dict:
    if type(bar) is not ProtoOATrendbarV2 or not bar.IsInitialized():
        raise ValueError("initialized ProtoOATrendbar required")
    if not bar.HasField("utcTimestampInMinutes"):
        raise ValueError("trendbar open timestamp absent")
    if not bar.HasField("low"):
        raise ValueError("trendbar low absent")
    if bar.HasField("period") and int(bar.period) != M5_ENUM:
        raise ValueError("trendbar period mismatch")
    volume = int(bar.volume)
    if volume < 0:
        raise ValueError("negative tick volume")
    minute = int(bar.utcTimestampInMinutes)
    open_ms = minute * 60_000
    if open_ms % M5_MILLISECONDS:
        raise ValueError("bar open timestamp is not M5 aligned")
    if open_ms < segment_from_ms or open_ms > segment_to_ms:
        raise ValueError("bar open timestamp outside exact frozen segment")
    if open_ms >= to_ms(PROTECTED_FORWARD_BOUNDARY_UTC):
        raise ValueError("protected forward bar rejected")
    low = int(bar.low)
    d_open = int(bar.deltaOpen) if bar.HasField("deltaOpen") else 0
    d_high = int(bar.deltaHigh) if bar.HasField("deltaHigh") else 0
    d_close = int(bar.deltaClose) if bar.HasField("deltaClose") else 0
    rel_open, rel_high, rel_low, rel_close = low + d_open, low + d_high, low, low + d_close
    if not (rel_low <= rel_open <= rel_high and rel_low <= rel_close <= rel_high):
        raise ValueError("relative OHLC invariant failure")
    row = {
        "time_utc": utc_iso_from_unix_minutes(minute),
        "open": exact_price_string(rel_open, digits),
        "high": exact_price_string(rel_high, digits),
        "low": exact_price_string(rel_low, digits),
        "close": exact_price_string(rel_close, digits),
        "tick_volume": str(volume),
    }
    dec = {k: Decimal(row[k]) for k in ("open", "high", "low", "close")}
    if not (dec["low"] <= dec["open"] <= dec["high"] and dec["low"] <= dec["close"] <= dec["high"]):
        raise ValueError("canonical OHLC invariant failure")
    return row


def decode_bound_response(response, *, ctx: RequestContext, digits: int) -> list[dict]:
    rows = [
        decode_trendbar(
            bar,
            digits=digits,
            segment_from_ms=ctx.from_ms,
            segment_to_ms=ctx.to_ms,
        )
        for bar in response.trendbar
    ]
    by_ts: dict[str, dict] = {}
    for row in rows:
        ts = row["time_utc"]
        if ts in by_ts:
            if by_ts[ts] != row:
                raise ValueError("conflicting duplicate trendbar timestamp")
            raise ValueError("duplicate trendbar timestamp")
        by_ts[ts] = row
    return [by_ts[k] for k in sorted(by_ts)]


@dataclass(frozen=True)
class PaginationDecision:
    complete: bool
    fail_closed: bool
    reason: str
    next_to_ms: int | None = None


def pagination_decision(
    *,
    ctx: RequestContext,
    decoded_rows: Sequence[Mapping],
    has_more_present: bool,
    has_more_value: bool | None,
    page_index: int,
) -> PaginationDecision:
    if page_index < 1 or page_index > MAXIMUM_PAGES_PER_IDENTITY_SEGMENT:
        return PaginationDecision(False, True, "PAGE_CAP_EXCEEDED")
    if len(decoded_rows) > PAGE_REQUESTED_COUNT:
        return PaginationDecision(False, True, "RETURNED_COUNT_EXCEEDS_REQUEST_COUNT")
    if has_more_present and has_more_value is None:
        return PaginationDecision(False, True, "INVALID_HASMORE_STATE")
    if not has_more_present and has_more_value is not None:
        return PaginationDecision(False, True, "INVALID_HASMORE_ABSENCE_STATE")
    if not decoded_rows:
        if has_more_present and has_more_value is True:
            return PaginationDecision(False, True, "EMPTY_PAGE_WITH_EXPLICIT_HASMORE_TRUE")
        return PaginationDecision(True, False, "EMPTY_FILTER_EXHAUSTED")
    open_times = [to_ms(str(x["time_utc"])) for x in decoded_rows]
    if open_times != sorted(open_times) or len(set(open_times)) != len(open_times):
        return PaginationDecision(False, True, "DECODED_TIMESTAMP_ORDER_OR_DUPLICATE_FAILURE")
    oldest = open_times[0]
    if oldest <= ctx.from_ms:
        return PaginationDecision(True, False, "FROM_BOUNDARY_REACHED")
    if has_more_present:
        if has_more_value is False:
            return PaginationDecision(True, False, "EXPLICIT_HASMORE_FALSE")
        if has_more_value is True:
            if page_index >= MAXIMUM_PAGES_PER_IDENTITY_SEGMENT:
                return PaginationDecision(False, True, "PAGE_CAP_REACHED_WITH_MORE_REQUIRED")
            return PaginationDecision(False, False, "EXPLICIT_HASMORE_TRUE_CONTINUE", oldest - 1)
    else:
        if len(decoded_rows) < PAGE_REQUESTED_COUNT:
            return PaginationDecision(True, False, "ABSENT_HASMORE_SHORT_PAGE_COMPLETE")
        if len(decoded_rows) == PAGE_REQUESTED_COUNT:
            if page_index >= MAXIMUM_PAGES_PER_IDENTITY_SEGMENT:
                return PaginationDecision(False, True, "PAGE_CAP_REACHED_WITH_AMBIGUOUS_FULL_PAGE")
            return PaginationDecision(False, False, "ABSENT_HASMORE_FULL_PAGE_CONTINUE", oldest - 1)
    return PaginationDecision(False, True, "UNREACHABLE_PAGINATION_STATE")


def next_context(ctx: RequestContext, decision: PaginationDecision, *, next_client_msg_id: str) -> RequestContext:
    if decision.complete or decision.fail_closed or decision.next_to_ms is None:
        raise ValueError("pagination continuation not authorized")
    if decision.next_to_ms >= ctx.to_ms or decision.next_to_ms < ctx.from_ms:
        raise ValueError("non-progressing pagination")
    return RequestContext(
        client_msg_id=next_client_msg_id,
        authenticated_account_id=ctx.authenticated_account_id,
        symbol_id=ctx.symbol_id,
        from_ms=ctx.from_ms,
        to_ms=decision.next_to_ms,
        count=ctx.count,
        period=ctx.period,
    )


def page_bound_explanation() -> dict:
    rate_floor_seconds = TRUE_ABSOLUTE_MAXIMUM_WIRE_ATTEMPTS / MAXIMUM_HISTORICAL_REQUESTS_PER_SECOND
    return {
        "logical_identity_segment_count": LOGICAL_IDENTITY_SEGMENT_COUNT,
        "theoretical_m5_open_slots_per_seven_day_segment": THEORETICAL_M5_SLOTS_PER_SEGMENT,
        "requested_count": PAGE_REQUESTED_COUNT,
        "backend_has_more_may_require_pagination_even_on_short_page": True,
        "maximum_pages_per_identity_segment": MAXIMUM_PAGES_PER_IDENTITY_SEGMENT,
        "maximum_page_request_count": MAXIMUM_PAGE_REQUEST_COUNT,
        "maximum_retries_after_initial_attempt_per_page": MAXIMUM_RETRIES_AFTER_INITIAL_ATTEMPT,
        "maximum_wire_attempts_per_page": MAXIMUM_WIRE_ATTEMPTS_PER_PAGE,
        "true_absolute_maximum_wire_attempts": TRUE_ABSOLUTE_MAXIMUM_WIRE_ATTEMPTS,
        "minimum_wire_send_seconds_at_frozen_4rps": rate_floor_seconds,
        "minimum_wire_send_hms_at_frozen_4rps": "03:56:24",
        "runtime_law": "PAGE_CAP_3_IS_OUTCOME_BLIND_AND_FAIL_CLOSED;IT_DOES_NOT_CLASSIFY_EXCEEDED_BACKEND_CHUNKING_AS_NO_HISTORICAL_SUPPORT",
    }


def serialize_rows(rows: Sequence[Mapping]) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=RAW_HEADER, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in RAW_HEADER})
    return out.getvalue().encode("utf-8")


def reconstruct_shards(shards: Sequence[bytes]) -> bytes:
    if not shards:
        return b""
    head = None
    body: list[bytes] = []
    for raw in shards:
        lines = raw.splitlines(keepends=True)
        if not lines:
            continue
        if head is None:
            head = lines[0]
        elif lines[0] != head:
            raise ValueError("shard header mismatch")
        body.extend(lines[1:])
    return (head or b"") + b"".join(body)


def v2_summary() -> dict:
    return {
        "schema": "mxm.v4.breadth-first-shallow-m5-support-v2.protocol-decoder-prearm.v1",
        "status": "PENDING_INDEPENDENT_AUDIT_OF_CORRECTED_BREADTH_FIRST_SHALLOW_M5_SUPPORT_V1_PREARM_PROTOCOL_AND_DECODER_BEFORE_ANY_ARM",
        "master_count": MASTER_COUNT,
        "master_sha256": MASTER_SHA256,
        "account_fingerprint_sha256": ACCOUNT_FINGERPRINT_SHA256,
        "period_enum": M5_ENUM,
        "fixed_window": [FIXED_WINDOW_START_UTC, FIXED_WINDOW_END_UTC_INCLUSIVE],
        "protected_forward_boundary_utc": PROTECTED_FORWARD_BOUNDARY_UTC,
        "page_bound": page_bound_explanation(),
        "arm_present": False,
        "broker_contact": False,
        "historical_requests_sent": 0,
        "credentials_used": False,
        "economic_outcomes_opened": 0,
    }
