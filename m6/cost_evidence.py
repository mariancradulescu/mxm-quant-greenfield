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
POST_BOUNDARY_MAX_WAIT_MS = 15 * 60 * 1000
COST_PLAN_REL = "data/M6_TIER1_COST_EVIDENCE_PLAN_V2.json"
COST_CALENDAR_REL = "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json"

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
    "data/M6_TIER1_COST_EVIDENCE_PLAN_V2.json",
    "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json",
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
    """Decode cTrader's newest-first absolute+delta timestamp representation."""
    if not rows:
        return []
    decoded_newest_first: list[DecodedTick] = []
    current_ms: int | None = None
    for i, row in enumerate(rows):
        try:
            stamp = int(row.get("timestamp"))
            raw_tick = int(row.get("tick"))
        except (TypeError, ValueError) as exc:
            raise CaptureContractError("malformed cTrader historical tick row") from exc
        if i == 0:
            current_ms = stamp
        else:
            if stamp < 0:
                raise CaptureContractError("negative cTrader tick timestamp delta")
            assert current_ms is not None
            current_ms -= stamp
        if current_ms < 0:
            raise CaptureContractError("decoded cTrader tick timestamp before epoch")
        decoded_newest_first.append(DecodedTick(current_ms, raw_tick))
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


def first_fresh_two_sided_state_at_or_after(
    states: Sequence[CausalQuoteState],
    boundary_ms: int,
    *,
    max_wait_ms: int = POST_BOUNDARY_MAX_WAIT_MS,
) -> CausalQuoteState:
    """First executable two-sided state after a boundary with both sides refreshed.

    A stale pre-boundary side can never be carried into POST_BOUNDARY_EXECUTABLE.
    The frozen wait interval is [boundary, boundary + max_wait_ms).
    """
    if max_wait_ms <= 0:
        raise CaptureContractError("post-boundary maximum wait must be positive")
    cutoff = boundary_ms + max_wait_ms
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
        "no fresh causal two-sided executable quote within post-boundary wait"
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
        "schema": "mxm.greenfield.v2.m6-cost-resume-contract.v2",
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
        },
    }
    binding["binding_sha256"] = hashlib.sha256(
        canonical_json_bytes(binding)
    ).hexdigest()
    return binding


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
            or existing.get("schema") != "mxm.greenfield.v2.m6-cost-resume.v2"
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
            "schema": "mxm.greenfield.v2.m6-cost-resume.v2",
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
