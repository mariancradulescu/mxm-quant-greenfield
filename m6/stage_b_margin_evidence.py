"""Pure helpers for the read-only Stage-B historical margin evidence supplement."""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ctrader_capture import CaptureContractError, sha256_file

DEVELOPMENT_START_UTC = datetime(2022, 1, 3, tzinfo=timezone.utc)
DEVELOPMENT_END_UTC = datetime(2026, 9, 16, 23, 59, 59, 999000, tzinfo=timezone.utc)
PROTECTED_FORWARD_START_UTC = datetime(2026, 9, 17, 12, 2, 58, tzinfo=timezone.utc)
TARGET_SYMBOLS = {"US500": 127, "NAS100": 126}
TARGET_BY_ID = {value: key for key, value in TARGET_SYMBOLS.items()}
FILLED_DEAL_STATUSES = frozenset({2, 3})
MAX_ROWS = 1000
INITIAL_WINDOW_DAYS = 31
HISTORICAL_MIN_INTERVAL_SECONDS = 0.21
PLAN_REL = "data/M6_STAGE_B_MARGIN_HISTORY_SUPPLEMENT_PLAN_V1.json"
PLAN_SCHEMA = "mxm.greenfield.v2.m6-stage-b-margin-history-supplement-plan.v1"
BUNDLE_SCHEMA = "mxm.greenfield.v2.m6-stage-b-margin-history-evidence-bundle.v1"
TOOL_VERSION = "MXM_M6_STAGE_B_MARGIN_HISTORY_ANDROID_STDLIB_V1"

MARGIN_HISTORY_PACKAGE_FILES = (
    "M6_STAGE_B_MARGIN_HISTORY_RUN.py",
    "m6/__init__.py",
    "m6/_ctrader_capture_base.py",
    "m6/ctrader_capture.py",
    "m6/ctrader_transport.py",
    "m6/stage_b_margin_evidence.py",
    "m6/stage_b_margin_openapi.py",
    "m6/pydroid_stage_b_margin_launcher.py",
    "m6/pydroid_oauth.py",
    "m6/ctrader_proto/__init__.py",
    "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
    "m6/ctrader_proto/OpenApiModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiMessages_pb2.py",
    "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
    "tools/requirements-m6-capture.txt",
    PLAN_REL,
    "evidence/M6_STAGE_B_MARGIN_EVIDENCE_RESOLUTION_V1.json",
    "README_STAGE_B_MARGIN_HISTORY.txt",
)


@dataclass(frozen=True)
class HistoryWindow:
    from_ms: int
    to_ms: int

    def __post_init__(self):
        if self.from_ms < 0 or self.to_ms < self.from_ms:
            raise CaptureContractError("invalid historical deal window")


def epoch_ms(value: datetime) -> int:
    if value.tzinfo is None:
        raise CaptureContractError("timestamp must be timezone-aware")
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


DEVELOPMENT_START_MS = epoch_ms(DEVELOPMENT_START_UTC)
DEVELOPMENT_END_MS = epoch_ms(DEVELOPMENT_END_UTC)
PROTECTED_FORWARD_START_MS = epoch_ms(PROTECTED_FORWARD_START_UTC)


def validate_plan(plan: Mapping[str, Any]) -> bool:
    if plan.get("schema") != PLAN_SCHEMA:
        raise CaptureContractError("Stage-B margin supplement plan schema mismatch")
    if plan.get("status") != "FROZEN_READ_ONLY_MINIMAL_GENERIC_EXTENSION_PRE_STAGE_B_OUTCOME":
        raise CaptureContractError("Stage-B margin supplement plan is not frozen/active")
    if plan.get("oauth_scope") != "accounts" or plan.get("orders") is not False:
        raise CaptureContractError("Stage-B margin supplement violates view-only contract")
    targets = plan.get("target_products") or {}
    for name, symbol_id in TARGET_SYMBOLS.items():
        if int((targets.get(name) or {}).get("symbol_id", -1)) != symbol_id:
            raise CaptureContractError(f"{name} target symbolId drift")
    interval = plan.get("development_interval") or {}
    if interval.get("protected_forward_start") != "2026-09-17T12:02:58Z":
        raise CaptureContractError("protected-forward boundary drift")
    return True


def initial_windows(
    start_ms: int = DEVELOPMENT_START_MS,
    end_ms: int = DEVELOPMENT_END_MS,
    *,
    days: int = INITIAL_WINDOW_DAYS,
) -> list[HistoryWindow]:
    if end_ms < start_ms or days <= 0:
        raise CaptureContractError("invalid Stage-B history range")
    width = days * 24 * 60 * 60 * 1000
    out = []
    cursor = start_ms
    while cursor <= end_ms:
        right = min(end_ms, cursor + width - 1)
        out.append(HistoryWindow(cursor, right))
        cursor = right + 1
    return out


def bisect_window(window: HistoryWindow) -> tuple[HistoryWindow, HistoryWindow]:
    if window.from_ms == window.to_ms:
        raise CaptureContractError("cannot bisect one-millisecond deal window")
    midpoint = (window.from_ms + window.to_ms) // 2
    return (
        HistoryWindow(window.from_ms, midpoint),
        HistoryWindow(midpoint + 1, window.to_ms),
    )


def sanitize_deal(deal: Mapping[str, Any]) -> dict[str, Any] | None:
    try:
        symbol_id = int(deal["symbolId"])
        execution_ms = int(deal["executionTimestamp"])
    except (KeyError, TypeError, ValueError):
        return None
    symbol = TARGET_BY_ID.get(symbol_id)
    if symbol is None or not (DEVELOPMENT_START_MS <= execution_ms <= DEVELOPMENT_END_MS):
        return None
    status = int(deal.get("dealStatus", 0))
    margin_raw = deal.get("marginRate")
    margin_rate = None
    if margin_raw is not None:
        try:
            candidate = float(margin_raw)
            if candidate > 0:
                margin_rate = candidate
        except (TypeError, ValueError):
            margin_rate = None
    return {
        "execution_utc": iso_ms(execution_ms),
        "execution_timestamp_ms": execution_ms,
        "symbol": symbol,
        "symbol_id": symbol_id,
        "volume_cents": int(deal.get("volume", 0)),
        "filled_volume_cents": int(deal.get("filledVolume", 0)),
        "execution_price": float(deal["executionPrice"]) if deal.get("executionPrice") is not None else None,
        "trade_side": int(deal.get("tradeSide", 0)),
        "deal_status": status,
        "margin_rate": margin_rate,
        "margin_rate_state": (
            "PRESENT" if margin_rate is not None and status in FILLED_DEAL_STATUSES
            else "MISSING_OR_NOT_APPLICABLE"
        ),
        "base_to_usd_conversion_rate": (
            float(deal["baseToUsdConversionRate"])
            if deal.get("baseToUsdConversionRate") is not None else None
        ),
        "money_digits": int(deal["moneyDigits"]) if deal.get("moneyDigits") is not None else None,
    }


def summarize_observations(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out = {}
    for symbol in TARGET_SYMBOLS:
        selected = [x for x in rows if x.get("symbol") == symbol]
        filled = [x for x in selected if int(x.get("deal_status", 0)) in FILLED_DEAL_STATUSES]
        with_margin = [x for x in filled if x.get("margin_rate") is not None]
        rates = [float(x["margin_rate"]) for x in with_margin]
        if not filled:
            state = "UNRESOLVED_NO_ACCOUNT_NATIVE_HISTORICAL_MARGIN_OBSERVATIONS"
        elif not with_margin:
            state = "UNRESOLVED_MARGIN_RATE_NOT_RECORDED"
        else:
            state = "OBSERVATIONS_CAPTURED_REQUIRES_SEPARATE_FAIL_CLOSED_AUTHORITY_ASSESSMENT"
        out[symbol] = {
            "target_deal_records": len(selected),
            "filled_or_partially_filled_records": len(filled),
            "records_with_margin_rate": len(with_margin),
            "margin_rate_min": min(rates) if rates else None,
            "margin_rate_max": max(rates) if rates else None,
            "first_margin_observation_utc": with_margin[0]["execution_utc"] if with_margin else None,
            "last_margin_observation_utc": with_margin[-1]["execution_utc"] if with_margin else None,
            "state": state,
        }
    return out


FORBIDDEN_EXPORTED_KEYS = frozenset({
    "ctidtraderaccountid", "traderlogin", "dealid", "orderid", "positionid",
    "label", "comment", "accesstoken", "refreshtoken", "clientsecret", "password",
})


def assert_transferable_privacy(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if normalized in FORBIDDEN_EXPORTED_KEYS:
                raise CaptureContractError(f"forbidden account/trade identity field in transferable evidence: {key}")
            assert_transferable_privacy(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_transferable_privacy(item)


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


def build_margin_history_pydroid_package(repo_root: Path | str, zip_path: Path | str) -> str:
    root, target = Path(repo_root), Path(zip_path)
    missing = [rel for rel in MARGIN_HISTORY_PACKAGE_FILES if not (root / rel).is_file()]
    if missing:
        raise CaptureContractError(f"Stage-B margin package source files missing: {missing}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in MARGIN_HISTORY_PACKAGE_FILES:
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, (root / rel).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target) as zf:
        if set(zf.namelist()) != set(MARGIN_HISTORY_PACKAGE_FILES):
            raise CaptureContractError("Stage-B margin Pydroid package member mismatch")
    return sha256_file(target)
