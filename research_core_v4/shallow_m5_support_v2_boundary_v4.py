"""V4 lower-boundary normalization for shallow M5 support.

This successor preserves the accepted V2 protocol identity and economic field decoder.
Only raw lower-boundary overfetch normalization and raw-geometry pagination change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from research_core_v4 import shallow_m5_support_v2 as v2

PROTECTED_FORWARD_MS = v2.to_ms(v2.PROTECTED_FORWARD_BOUNDARY_UTC)


class BoundaryProtocolError(ValueError):
    def __init__(self, classification: str):
        self.classification = classification
        super().__init__(classification)


@dataclass(frozen=True)
class RawTemporalGeometry:
    raw_response_count: int
    raw_min_open_ms: int | None
    raw_max_open_ms: int | None
    raw_lower_boundary_reached: bool
    lower_overfetch_count: int
    canonical_inside_count: int
    upper_overfetch_count: int
    protected_forward_count: int
    raw_duplicate_count: int
    raw_non_M5_aligned_count: int

    def as_dict(self) -> dict:
        return {
            "raw_response_count": self.raw_response_count,
            "raw_min_open_ms": self.raw_min_open_ms,
            "raw_max_open_ms": self.raw_max_open_ms,
            "raw_lower_boundary_reached": self.raw_lower_boundary_reached,
            "lower_overfetch_count": self.lower_overfetch_count,
            "canonical_inside_count": self.canonical_inside_count,
            "upper_overfetch_count": self.upper_overfetch_count,
            "protected_forward_count": self.protected_forward_count,
            "raw_duplicate_count": self.raw_duplicate_count,
            "raw_non_M5_aligned_count": self.raw_non_M5_aligned_count,
        }


@dataclass(frozen=True)
class NormalizedPage:
    canonical_rows: tuple[dict, ...]
    geometry: RawTemporalGeometry
    has_more_present: bool
    has_more_value: bool | None


def bind_and_normalize_response(envelope, *, ctx: v2.RequestContext, digits: int) -> NormalizedPage:
    response = v2.bind_response_envelope(envelope, ctx)
    return normalize_bound_response(response, ctx=ctx, digits=digits)


def normalize_bound_response(response, *, ctx: v2.RequestContext, digits: int) -> NormalizedPage:
    if type(response) is not v2.ProtoOAGetTrendbarsResV2:
        raise BoundaryProtocolError("RESPONSE_IDENTITY_FAILURE")

    has_more_present, has_more_value = v2.response_has_more_presence(response)
    raw_open_ms: list[int] = []
    seen: set[int] = set()
    canonical_rows: list[dict] = []
    lower = 0

    for bar in response.trendbar:
        if not bar.HasField("utcTimestampInMinutes"):
            raise BoundaryProtocolError("MALFORMED_TEMPORAL_GEOMETRY")
        minute = int(bar.utcTimestampInMinutes)
        open_ms = minute * 60_000
        if open_ms % v2.M5_MILLISECONDS:
            raise BoundaryProtocolError("MALFORMED_TEMPORAL_GEOMETRY")
        if open_ms in seen:
            raise BoundaryProtocolError("MALFORMED_TEMPORAL_GEOMETRY")
        seen.add(open_ms)
        raw_open_ms.append(open_ms)

        if open_ms >= PROTECTED_FORWARD_MS:
            raise BoundaryProtocolError("PROTECTED_FORWARD_LEAK")
        if open_ms > ctx.to_ms:
            raise BoundaryProtocolError("UPPER_BOUNDARY_OVERFETCH_PROTOCOL_FAILURE")
        if open_ms < ctx.from_ms:
            lower += 1
            # Critical V4 law: lower overfetch is discarded before OHLC/volume decoding.
            continue

        canonical_rows.append(
            v2.decode_trendbar(
                bar,
                digits=digits,
                segment_from_ms=ctx.from_ms,
                segment_to_ms=ctx.to_ms,
            )
        )

    canonical_rows.sort(key=lambda x: x["time_utc"])
    if len({x["time_utc"] for x in canonical_rows}) != len(canonical_rows):
        raise BoundaryProtocolError("MALFORMED_TEMPORAL_GEOMETRY")

    raw_min = min(raw_open_ms) if raw_open_ms else None
    raw_max = max(raw_open_ms) if raw_open_ms else None
    geometry = RawTemporalGeometry(
        raw_response_count=len(raw_open_ms),
        raw_min_open_ms=raw_min,
        raw_max_open_ms=raw_max,
        raw_lower_boundary_reached=(raw_min is not None and raw_min <= ctx.from_ms),
        lower_overfetch_count=lower,
        canonical_inside_count=len(canonical_rows),
        upper_overfetch_count=0,
        protected_forward_count=0,
        raw_duplicate_count=0,
        raw_non_M5_aligned_count=0,
    )
    return NormalizedPage(tuple(canonical_rows), geometry, has_more_present, has_more_value)


def pagination_decision_v4(
    *,
    ctx: v2.RequestContext,
    geometry: RawTemporalGeometry,
    has_more_present: bool,
    has_more_value: bool | None,
    page_index: int,
):
    if page_index < 1 or page_index > v2.MAXIMUM_PAGES_PER_IDENTITY_SEGMENT:
        return v2.PaginationDecision(False, True, "PAGE_CAP_EXCEEDED")
    if geometry.raw_response_count > ctx.count:
        return v2.PaginationDecision(False, True, "RETURNED_COUNT_EXCEEDS_REQUEST_COUNT")
    if has_more_present and has_more_value is None:
        return v2.PaginationDecision(False, True, "INVALID_HASMORE_STATE")
    if not has_more_present and has_more_value is not None:
        return v2.PaginationDecision(False, True, "INVALID_HASMORE_ABSENCE_STATE")
    if geometry.raw_response_count == 0:
        if has_more_present and has_more_value is True:
            return v2.PaginationDecision(False, True, "EMPTY_PAGE_WITH_EXPLICIT_HASMORE_TRUE")
        return v2.PaginationDecision(True, False, "EMPTY_AVAILABLE_HISTORY")

    if geometry.raw_lower_boundary_reached:
        return v2.PaginationDecision(True, False, "RAW_LOWER_BOUNDARY_REACHED")

    if has_more_present and has_more_value is False:
        return v2.PaginationDecision(True, False, "EXPLICIT_HASMORE_FALSE")

    if not has_more_present and geometry.raw_response_count < ctx.count:
        return v2.PaginationDecision(True, False, "ABSENT_HASMORE_SHORT_RAW_PAGE")

    if page_index >= v2.MAXIMUM_PAGES_PER_IDENTITY_SEGMENT:
        return v2.PaginationDecision(False, True, "PAGE_CAP_REACHED_BEFORE_RAW_LOWER_BOUNDARY")

    raw_min = geometry.raw_min_open_ms
    if raw_min is None:
        return v2.PaginationDecision(False, True, "MALFORMED_TEMPORAL_GEOMETRY")
    next_to = raw_min - 1
    if next_to >= ctx.to_ms or next_to < ctx.from_ms:
        return v2.PaginationDecision(False, True, "NON_PROGRESSING_RAW_PAGINATION")
    return v2.PaginationDecision(False, False, "CONTINUE_FROM_RAW_MIN_MINUS_1", next_to)


def next_context_v4(ctx: v2.RequestContext, decision, *, next_client_msg_id: str) -> v2.RequestContext:
    if decision.complete or decision.fail_closed or decision.next_to_ms is None:
        raise ValueError("pagination continuation not authorized")
    if decision.next_to_ms >= ctx.to_ms or decision.next_to_ms < ctx.from_ms:
        raise ValueError("non-progressing raw pagination")
    return v2.RequestContext(
        client_msg_id=next_client_msg_id,
        authenticated_account_id=ctx.authenticated_account_id,
        symbol_id=ctx.symbol_id,
        from_ms=ctx.from_ms,
        to_ms=decision.next_to_ms,
        count=ctx.count,
        period=ctx.period,
    )


def v4_boundary_contract() -> dict:
    return {
        "only_behavioral_changes": [
            "LOWER_BOUNDARY_OVERFETCH_NORMALIZATION",
            "RAW_GEOMETRY_AWARE_PAGINATION_COMPLETION",
        ],
        "lower_overfetch": "DISCARD_BEFORE_PRICE_OR_VOLUME_DECODING",
        "inside_interval": "DECODE_WITH_EXISTING_EXACT_V2_PRICE_AND_VOLUME_LAW",
        "upper_boundary": "FAIL_CLOSED",
        "protected_forward": "FAIL_CLOSED",
        "duplicates": "FAIL_CLOSED",
        "non_m5_alignment": "FAIL_CLOSED",
        "pagination": {
            "completion_first": "RAW_LOWER_BOUNDARY_REACHED",
            "explicit_hasMore_false": "COMPLETE",
            "absent_hasMore_short_raw_page": "COMPLETE",
            "continuation_cursor": "RAW_MIN_OPEN_MS_MINUS_1",
            "page_count_basis": "RAW_RESPONSE_COUNT",
            "page_cap": v2.MAXIMUM_PAGES_PER_IDENTITY_SEGMENT,
        },
    }
