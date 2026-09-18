"""PRE-M6 Tier-1 historical BID/ASK cost-evidence helpers.

This module is pre-economic. It defines deterministic, signal-blind cash-session request
windows, cTrader historical tick decoding/pagination, causal asynchronous BID/ASK merge,
resume integrity and the separate Pydroid deployment package.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from .ctrader_capture import (
    PROTECTED_FORWARD_START,
    CaptureContractError,
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
)

TIER1_SYMBOLS = {
    "US500": {"symbol_id": 127, "product_family": "CASH_INDEX_CFD", "digits": 1},
    "NAS100": {"symbol_id": 126, "product_family": "CASH_INDEX_CFD", "digits": 1},
}
QUOTE_TYPES = {"BID": 1, "ASK": 2}
OFFICIAL_TICK_MAX_WINDOW_MS = 604_800_000
HISTORICAL_MIN_INTERVAL_SECONDS = 0.21
DEVELOPMENT_START_DATE = date(2022, 1, 3)
DEVELOPMENT_END_DATE = date(2026, 9, 16)
CASH_SESSION_TZ = ZoneInfo("America/New_York")
CASH_OPEN_LOCAL = dtime(9, 30)
CASH_CLOSE_LOCAL = dtime(16, 0)
QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS = 15 * 60 * 1000
COST_PLAN_REL = "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json"
COST_CALENDAR_REL = "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json"
CALIBRATION_PROTOCOL_REL = "data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json"

COST_PACKAGE_FILES = (
    "M6_COST_EVIDENCE_RUN.py",
    "m6/__init__.py",
    "m6/_ctrader_capture_base.py",
    "m6/ctrader_capture.py",
    "m6/ctrader_transport.py",
    "m6/cost_evidence.py",
    "m6/cost_evidence_openapi.py",
    "m6/session_replay.py",
    "m6/pydroid_cost_launcher.py",
    "m6/pydroid_oauth.py",
    "m6/ctrader_proto/__init__.py",
    "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
    "m6/ctrader_proto/OpenApiModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiMessages_pb2.py",
    "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
    "tools/requirements-m6-capture.txt",
    "data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json",
    "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json",
    "data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json",
    "evidence/PRE_M6_CTRADER_TICK_DELTA_DECODER_CORRECTION_V1.json",
    "evidence/PRE_M6_TIER1_PIPELINE_THROUGHPUT_OPTIMIZATION_V1.json",
    "evidence/PRE_M6_TIER1_PIPELINE_STABILITY_CORRECTION_V1.json",
    "README_COST_EVIDENCE.txt",
)


@dataclass(frozen=True)
class SessionWindow:
    session_date: str
    from_ms: int
    to_ms: int
    open_utc: str
    close_utc: str


@dataclass(frozen=True)
class DecodedTick:
    timestamp_ms: int
    raw_tick: int

    @property
    def price(self) -> float:
        return self.raw_tick / 100000.0


@dataclass(frozen=True)
class CausalQuoteState:
    timestamp_ms: int
    bid: float
    ask: float
    bid_timestamp_ms: int
    ask_timestamp_ms: int
    spread: float


@dataclass(frozen=True)
class BoundaryCausalState:
    boundary_ms: int
    bid: float | None
    ask: float | None
    bid_timestamp_ms: int | None
    ask_timestamp_ms: int | None
    bid_age_ms: int | None
    ask_age_ms: int | None
    spread: float | None
    availability: str


@dataclass(frozen=True)
class FirstAnyQuoteEvent:
    timestamp_ms: int
    side: str
    bid_price: float | None
    ask_price: float | None
    delay_ms: int


def _iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def signal_blind_cash_session_windows(
    start_date: date = DEVELOPMENT_START_DATE,
    end_date: date = DEVELOPMENT_END_DATE,
) -> list[SessionWindow]:
    """Generate every weekday regular-session envelope, independent of signals/returns.

    Holidays and early closes are intentionally not removed here. Requesting the regular
    envelope on such dates is adverse-safe and broker-observation-driven: no returned tick
    is fabricated, and no candidate outcome can influence which timestamps are queried.
    """
    if end_date < start_date:
        raise CaptureContractError("cost-evidence date interval inverted")
    protected = datetime.fromisoformat(PROTECTED_FORWARD_START.replace("Z", "+00:00"))
    out: list[SessionWindow] = []
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5:
            opened = datetime.combine(cursor, CASH_OPEN_LOCAL, CASH_SESSION_TZ).astimezone(timezone.utc)
            closed = datetime.combine(cursor, CASH_CLOSE_LOCAL, CASH_SESSION_TZ).astimezone(timezone.utc)
            from_ms, to_ms = _epoch_ms(opened), _epoch_ms(closed)
            if to_ms - from_ms > OFFICIAL_TICK_MAX_WINDOW_MS:
                raise AssertionError("cash-session tick window exceeds official one-week limit")
            if closed >= protected:
                raise CaptureContractError("cost-evidence window reaches protected-forward boundary")
            out.append(SessionWindow(
                session_date=cursor.isoformat(),
                from_ms=from_ms,
                to_ms=to_ms,
                open_utc=opened.isoformat(timespec="seconds").replace("+00:00", "Z"),
                close_utc=closed.isoformat(timespec="seconds").replace("+00:00", "Z"),
            ))
        cursor += timedelta(days=1)
    return out


def validate_tick_request_window(from_ms: int, to_ms: int) -> None:
    if from_ms < 0 or to_ms < from_ms:
        raise CaptureContractError("historical tick request boundaries invalid")
    if to_ms - from_ms > OFFICIAL_TICK_MAX_WINDOW_MS:
        raise CaptureContractError("historical tick request exceeds official one-week maximum")
    protected_ms = _epoch_ms(
        datetime.fromisoformat(PROTECTED_FORWARD_START.replace("Z", "+00:00"))
    )
    if to_ms >= protected_ms:
        raise CaptureContractError("historical tick request reaches protected-forward boundary")


def decode_ctrader_tick_page(rows: Sequence[Mapping[str, Any]]) -> list[DecodedTick]:
    """Decode cTrader historical tick absolute+signed-delta compression.

    ProtoOAGetTickDataRes is newest-first. The first element contains absolute timestamp
    and absolute raw price. Every later element is relative to the immediately previous
    encoded tick: timestamp is a signed millisecond delta (normally <= 0 because the list
    walks backward in time) and tick is a signed raw-price delta. Both deltas are therefore
    cumulatively ADDED, not treated as independent absolute values.

    The returned list is normalized to chronological oldest-first DecodedTick objects.
    """
    if not rows:
        return []
    decoded_newest_first: list[DecodedTick] = []
    current_ms: int | None = None
    current_raw_tick: int | None = None
    for i, row in enumerate(rows):
        try:
            stamp_or_delta = int(row.get("timestamp"))
            tick_or_delta = int(row.get("tick"))
        except (TypeError, ValueError) as exc:
            raise CaptureContractError("malformed cTrader historical tick row") from exc

        if i == 0:
            current_ms = stamp_or_delta
            current_raw_tick = tick_or_delta
            if current_ms < 0:
                raise CaptureContractError(
                    "first cTrader historical tick timestamp must be absolute Unix ms"
                )
        else:
            assert current_ms is not None and current_raw_tick is not None
            if stamp_or_delta > 0:
                raise CaptureContractError(
                    "positive cTrader tick timestamp delta violates newest-first encoding"
                )
            current_ms += stamp_or_delta
            current_raw_tick += tick_or_delta

        assert current_ms is not None and current_raw_tick is not None
        if current_ms < 0:
            raise CaptureContractError("decoded cTrader tick timestamp before epoch")
        decoded_newest_first.append(DecodedTick(current_ms, current_raw_tick))

    decoded = list(reversed(decoded_newest_first))
    if any(a.timestamp_ms > b.timestamp_ms for a, b in zip(decoded, decoded[1:])):
        raise CaptureContractError("decoded tick page is not chronological")
    return decoded


def next_tick_page_to_ms(
    decoded_page: Sequence[DecodedTick],
    *,
    current_from_ms: int,
    previous_oldest_ms: int | None = None,
) -> int | None:
    """Advance an inclusive time-boundary pagination window backwards.

    cTrader exposes no cursor. We overlap the oldest timestamp once to avoid arbitrarily
    discarding boundary-ms observations. If that boundary does not move on the next page,
    decrement by 1ms to guarantee progress; the fallback count is recorded by the runner.
    """
    if not decoded_page:
        return None
    oldest = min(x.timestamp_ms for x in decoded_page)
    if oldest < current_from_ms:
        return None
    if previous_oldest_ms is None or oldest < previous_oldest_ms:
        return oldest
    fallback = oldest - 1
    return fallback if fallback >= current_from_ms else None


def canonical_tick_rows(
    ticks: Iterable[DecodedTick],
    *,
    requested_from_ms: int,
    requested_to_ms: int,
) -> list[dict[str, str]]:
    """Canonicalize without fabricating ticks; exact duplicate quote states are de-duped."""
    seen: set[tuple[int, int]] = set()
    out: list[dict[str, str]] = []
    for tick in sorted(ticks, key=lambda x: (x.timestamp_ms, x.raw_tick)):
        if not (requested_from_ms <= tick.timestamp_ms <= requested_to_ms):
            continue
        key = (tick.timestamp_ms, tick.raw_tick)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "time_utc": _iso_ms(tick.timestamp_ms),
            "timestamp_ms": str(tick.timestamp_ms),
            "raw_tick": str(tick.raw_tick),
            "price": format(tick.price, ".10f").rstrip("0").rstrip("."),
        })
    return out


def causal_merge_bid_ask(
    bid_ticks: Sequence[DecodedTick],
    ask_ticks: Sequence[DecodedTick],
) -> list[CausalQuoteState]:
    """Merge asynchronous sides chronologically with no future-side filling."""
    events: list[tuple[int, int, str, float]] = []
    for order, tick in enumerate(bid_ticks):
        events.append((tick.timestamp_ms, order, "BID", tick.price))
    for order, tick in enumerate(ask_ticks):
        events.append((tick.timestamp_ms, order, "ASK", tick.price))
    # BID then ASK ordering for same ms is deterministic; a state is emitted after each
    # event only once both sides have been causally observed.
    events.sort(key=lambda x: (x[0], 0 if x[2] == "BID" else 1, x[1]))
    bid = ask = None
    bid_ts = ask_ts = None
    out: list[CausalQuoteState] = []
    for ts, _, side, price in events:
        if side == "BID":
            bid, bid_ts = price, ts
        else:
            ask, ask_ts = price, ts
        if bid is None or ask is None:
            continue
        if bid_ts is None or ask_ts is None or bid_ts > ts or ask_ts > ts:
            raise AssertionError("future side leaked into causal quote")
        spread = ask - bid
        out.append(CausalQuoteState(
            timestamp_ms=ts,
            bid=bid,
            ask=ask,
            bid_timestamp_ms=bid_ts,
            ask_timestamp_ms=ask_ts,
            spread=spread,
        ))
    return out


def quote_state_at_or_before(
    states: Sequence[CausalQuoteState],
    timestamp_ms: int,
) -> CausalQuoteState:
    eligible = [x for x in states if x.timestamp_ms <= timestamp_ms]
    if not eligible:
        raise CaptureContractError("no causal two-sided quote at or before boundary")
    return eligible[-1]


def latest_tick_at_or_before(
    ticks: Sequence[DecodedTick],
    boundary_ms: int,
) -> DecodedTick | None:
    """Latest observed one-sided quote at/before boundary; never consult a future event."""
    eligible = [x for x in ticks if x.timestamp_ms <= boundary_ms]
    if not eligible:
        return None
    return max(eligible, key=lambda x: x.timestamp_ms)


def causal_state_at_boundary(
    bid_ticks: Sequence[DecodedTick],
    ask_ticks: Sequence[DecodedTick],
    boundary_ms: int,
) -> BoundaryCausalState:
    """Candidate-independent causally known quote state exactly at a generic boundary.

    A side observed before the boundary remains the current causal state until that side
    changes. This is evidence only and is not an executed-fill assertion.
    """
    bid = latest_tick_at_or_before(bid_ticks, boundary_ms)
    ask = latest_tick_at_or_before(ask_ticks, boundary_ms)
    if bid is None and ask is None:
        availability = "MISSING_BOTH_SIDES"
    elif bid is None:
        availability = "MISSING_BID"
    elif ask is None:
        availability = "MISSING_ASK"
    else:
        availability = "CAUSAL_TWO_SIDED_AVAILABLE"
    return BoundaryCausalState(
        boundary_ms=boundary_ms,
        bid=None if bid is None else bid.price,
        ask=None if ask is None else ask.price,
        bid_timestamp_ms=None if bid is None else bid.timestamp_ms,
        ask_timestamp_ms=None if ask is None else ask.timestamp_ms,
        bid_age_ms=None if bid is None else boundary_ms-bid.timestamp_ms,
        ask_age_ms=None if ask is None else boundary_ms-ask.timestamp_ms,
        spread=None if bid is None or ask is None else ask.price-bid.price,
        availability=availability,
    )


def first_tick_at_or_after(
    ticks: Sequence[DecodedTick],
    boundary_ms: int,
) -> DecodedTick | None:
    """First observed one-sided quote event at/after boundary in the captured raw tape."""
    eligible = [x for x in ticks if x.timestamp_ms >= boundary_ms]
    if not eligible:
        return None
    return min(eligible, key=lambda x: x.timestamp_ms)


def first_any_quote_event_at_or_after(
    bid_ticks: Sequence[DecodedTick],
    ask_ticks: Sequence[DecodedTick],
    boundary_ms: int,
) -> FirstAnyQuoteEvent | None:
    """Earliest BID and/or ASK event at/after boundary, preserving same-ms simultaneity."""
    bid = first_tick_at_or_after(bid_ticks, boundary_ms)
    ask = first_tick_at_or_after(ask_ticks, boundary_ms)
    if bid is None and ask is None:
        return None
    stamps = [x.timestamp_ms for x in (bid, ask) if x is not None]
    stamp = min(stamps)
    bid_here = bid if bid is not None and bid.timestamp_ms == stamp else None
    ask_here = ask if ask is not None and ask.timestamp_ms == stamp else None
    side = (
        "BID_AND_ASK"
        if bid_here is not None and ask_here is not None
        else "BID"
        if bid_here is not None
        else "ASK"
    )
    return FirstAnyQuoteEvent(
        timestamp_ms=stamp,
        side=side,
        bid_price=None if bid_here is None else bid_here.price,
        ask_price=None if ask_here is None else ask_here.price,
        delay_ms=stamp-boundary_ms,
    )


def first_both_sides_refreshed_diagnostic(
    states: Sequence[CausalQuoteState],
    boundary_ms: int,
    *,
    diagnostic_window_ms: int = QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS,
) -> CausalQuoteState:
    """Quote-refresh diagnostic only; never a fill time or execution-delay authority."""
    if diagnostic_window_ms <= 0:
        raise CaptureContractError("quote-refresh diagnostic window must be positive")
    cutoff = boundary_ms + diagnostic_window_ms
    for state in states:
        if state.timestamp_ms < boundary_ms:
            continue
        if state.timestamp_ms >= cutoff:
            break
        if (
            state.bid_timestamp_ms >= boundary_ms
            and state.ask_timestamp_ms >= boundary_ms
        ):
            return state
    raise CaptureContractError(
        "both quote sides did not independently refresh within diagnostic window"
    )



def cost_resume_contract(
    plan_path: Path,
    *,
    tool_version: str,
) -> dict[str, Any]:
    """Build the immutable binding that controls whether historical chunks are reusable."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    interval = plan["development_interval"]
    acquisition = plan["acquisition_domain"]
    binding = {
        "schema": "mxm.greenfield.v2.m6-cost-resume-contract.v3",
        "plan_schema": plan["schema"],
        "plan_file_sha256": sha256_file(plan_path),
        "tool_version": str(tool_version),
        "development_interval": {
            "start_date": interval["start_date"],
            "end_date": interval["end_date"],
        },
        "protected_forward_boundary": interval["protected_forward_start"],
        "target_symbol_ids": {
            key: int(plan["targets"][key]["symbol_id"])
            for key in sorted(plan["targets"])
        },
        "quote_types": list(plan["quote_types"]),
        "acquisition_domain_rule": {
            "timezone": acquisition["timezone"],
            "weekday_envelope_local": list(acquisition["weekday_envelope_local"]),
            "weekday_rule": acquisition["weekday_rule"],
            "holidays": acquisition["holidays"],
            "early_closes": acquisition["early_closes"],
            "no_signal_conditioned_windows": bool(
                acquisition["no_signal_conditioned_windows"]
            ),
            "no_return_conditioned_windows": bool(
                acquisition["no_return_conditioned_windows"]
            ),
            "no_candidate_pnl_conditioned_windows": bool(
                acquisition.get("no_candidate_pnl_conditioned_windows", False)
            ),
        },
    }
    binding["binding_sha256"] = hashlib.sha256(
        canonical_json_bytes(binding)
    ).hexdigest()
    return binding


def migrate_compatible_resume_tool_version(
    work_dir: Path,
    new_binding: Mapping[str, Any],
    *,
    allowed_previous_tool_versions: Sequence[str],
) -> tuple[bool, int, str | None]:
    """Explicitly migrate verified chunks when ONLY the tool version changed.

    This is intentionally narrow. The exact plan SHA, DEVELOPMENT interval, protected
    boundary, target IDs, quote types and acquisition-domain contract must match. Every
    completed chunk referenced by resume state must pass SHA256 verification. No V2/V3
    plan migration and no acquisition-semantic migration is performed here.
    """
    resume_path = work_dir / "resume.json"
    if not resume_path.is_file():
        return False, 0, None
    try:
        state = json.loads(resume_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, 0, None
    if not isinstance(state, dict) or state.get("schema") != "mxm.greenfield.v2.m6-cost-resume.v3":
        return False, 0, None
    old = state.get("contract")
    completed = state.get("completed")
    if not isinstance(old, dict) or not isinstance(completed, dict):
        return False, 0, None
    old_tool = str(old.get("tool_version") or "")
    if old_tool not in set(allowed_previous_tool_versions):
        return False, 0, None

    def semantic_contract(value: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: value.get(key)
            for key in (
                "schema",
                "plan_schema",
                "plan_file_sha256",
                "development_interval",
                "protected_forward_boundary",
                "target_symbol_ids",
                "quote_types",
                "acquisition_domain_rule",
            )
        }

    if semantic_contract(old) != semantic_contract(new_binding):
        return False, 0, old_tool

    verified = 0
    for key, record in completed.items():
        if not isinstance(record, dict):
            return False, 0, old_tool
        try:
            symbol = str(record["symbol"])
            quote_type = str(record["quote_type"])
            session_date = str(record["session_date"])
            expected_sha = str(record["sha256"])
        except KeyError:
            return False, 0, old_tool
        expected_key = f"{symbol}:{quote_type}:{session_date}"
        if key != expected_key:
            return False, 0, old_tool
        path = work_dir / "chunks" / symbol / quote_type / f"{session_date}.csv"
        if not verified_resume_chunk(path, expected_sha):
            return False, 0, old_tool
        verified += 1

    state["contract"] = dict(new_binding)
    migrations = state.setdefault("compatible_tool_migrations", [])
    migrations.append({
        "from_tool_version": old_tool,
        "to_tool_version": str(new_binding.get("tool_version")),
        "verified_chunk_count": verified,
        "plan_file_sha256": str(new_binding.get("plan_file_sha256")),
        "semantic_contract_identical": True,
    })
    atomic_write_json(resume_path, state)
    return True, verified, old_tool


def prepare_contract_bound_resume(
    work_dir: Path,
    binding: Mapping[str, Any],
) -> tuple[Path, dict[str, Any], Path | None]:
    """Initialize/reuse resume state only under an exact contract binding.

    Any malformed or mismatched work directory is archived atomically to a versioned
    sibling path and a fresh empty state is created. Chunks from the old contract are
    therefore physically outside the active work directory.
    """
    import shutil

    resume_path = work_dir / "resume.json"
    archived: Path | None = None
    existing: dict[str, Any] | None = None
    if resume_path.is_file():
        try:
            candidate = json.loads(resume_path.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                existing = candidate
        except (OSError, json.JSONDecodeError):
            existing = None

    expected = dict(binding)
    mismatch = False
    if work_dir.exists():
        mismatch = (
            existing is None
            or existing.get("schema") != "mxm.greenfield.v2.m6-cost-resume.v3"
            or existing.get("contract") != expected
            or not isinstance(existing.get("completed"), dict)
        )

    if mismatch:
        parent = work_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        old_tag = "unknown"
        if isinstance(existing, dict):
            old_tag = str(
                (existing.get("contract") or {}).get("binding_sha256") or "unknown"
            )[:12]
        archived = parent / f"{work_dir.name}.stale_{old_tag}"
        suffix = 1
        while archived.exists():
            archived = parent / f"{work_dir.name}.stale_{old_tag}_{suffix}"
            suffix += 1
        work_dir.rename(archived)
        existing = None

    work_dir.mkdir(parents=True, exist_ok=True)
    if existing is None:
        existing = {
            "schema": "mxm.greenfield.v2.m6-cost-resume.v3",
            "contract": expected,
            "completed": {},
        }
        atomic_write_json(resume_path, existing)
    return resume_path, existing, archived


def tick_csv_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=("time_utc", "timestamp_ms", "raw_tick", "price"),
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def verified_resume_chunk(path: Path, expected_sha256: str) -> bool:
    return path.is_file() and sha256_file(path) == expected_sha256


def deterministic_zip_directory(root: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return sha256_file(target)


def build_cost_pydroid_package(repo_root: Path | str, zip_path: Path | str) -> str:
    root = Path(repo_root)
    target = Path(zip_path)
    missing = [rel for rel in COST_PACKAGE_FILES if not (root / rel).is_file()]
    if missing:
        raise CaptureContractError(f"cost-evidence package source files missing: {missing}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in COST_PACKAGE_FILES:
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, (root / rel).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target) as zf:
        if set(zf.namelist()) != set(COST_PACKAGE_FILES):
            raise CaptureContractError("cost-evidence Pydroid package member mismatch")
    return sha256_file(target)
