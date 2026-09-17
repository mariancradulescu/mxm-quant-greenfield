"""Final pre-run hardening layer for the read-only cTrader M6 capture client.

The accepted capture implementation from checkpoint 45fa613c is preserved byte-for-byte
in ``m6._ctrader_capture_base``. This active module re-exports that implementation and
narrows the final pre-run contracts: causal bar-completion cutoff, plan self-hash,
user-visible progress formatting, deterministic deployment packaging, and final
transferable-bundle completeness checks. No economic logic is present here.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import _ctrader_capture_base as _base
from ._ctrader_capture_base import *  # noqa: F401,F403 - deliberate accepted-base re-export

HISTORICAL_MIN_INTERVAL = 0.21
HISTORICAL_TARGET_RPS = 1.0 / HISTORICAL_MIN_INTERVAL

PYDROID_PACKAGE_FILES = (
    "M6_CAPTURE_RUN.py",
    "M6_CAPTURE_RUN_BASE.py",
    "m6/__init__.py",
    "m6/ctrader_capture.py",
    "m6/_ctrader_capture_base.py",
    "m6/ctrader_openapi.py",
    "m6/_ctrader_openapi_base.py",
    "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json",
    "tools/requirements-m6-capture.txt",
    "README_RUN.txt",
)

TRANSFERABLE_REQUIRED_FILES = frozenset({
    "provenance_manifest.json",
    "bundle_manifest.json",
    "CHECKSUMS.sha256",
    "evidence/account.json",
    "evidence/broker_mapping.json",
    "evidence/symbol_metadata_current.json",
    "evidence/assets.json",
    "evidence/expected_margin.json",
    "evidence/auxiliary_status.json",
    "evidence/gap_diagnostics.json",
    "evidence/candidate_bindings.json",
})
FORBIDDEN_TRANSFER_PATH_PARTS = frozenset({
    "m6_capture_local.json", ".m6_secrets", ".m6_capture_work", "token_cache.json",
})


def canonical_plan_sha256(plan: Mapping[str, Any]) -> str:
    """Reproduce the frozen acquisition canonical hash exactly (no terminal newline)."""
    payload = {key: value for key, value in plan.items() if key != "plan_sha256"}
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(raw)


def validate_capture_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    result = _base.validate_capture_plan(plan)
    if canonical_plan_sha256(plan) != EXPECTED_PLAN_SHA:
        raise CaptureContractError("active materialization plan canonical hash mismatch")
    return result


def normalize_trendbars(
    trendbars: Sequence[Mapping[str, Any]], *, resolution: str, digits: int,
    requested_start_utc: str, requested_end_utc: str,
    protected_start_utc: str = PROTECTED_FORWARD_START,
) -> list[dict[str, str]]:
    """Normalize only bars completed inside the frozen DEVELOPMENT interval.

    cTrader trendbar timestamps denote the bar OPEN. A bar becomes causally usable only
    at OPEN + timeframe. Therefore completion must be <= the exact requested DEVELOPMENT
    end and strictly < protected-forward start. This rule is generic for M15/H1/H4/D1.
    """
    start = _base._utc(requested_start_utc)
    end = _base._utc(requested_end_utc)
    protected = _base._utc(protected_start_utc)
    minutes = period_minutes(resolution)
    seen: dict[str, dict[str, str]] = {}
    for bar in trendbars:
        try:
            open_min = int(_base._bar_field(bar, "utcTimestampInMinutes", "utc_timestamp_in_minutes"))
            low = int(_base._bar_field(bar, "low", default=None))
            d_open = int(_base._bar_field(bar, "deltaOpen", "delta_open", 0))
            d_high = int(_base._bar_field(bar, "deltaHigh", "delta_high", 0))
            d_close = int(_base._bar_field(bar, "deltaClose", "delta_close", 0))
            volume = int(_base._bar_field(bar, "volume", default=0))
        except (TypeError, ValueError) as exc:
            raise ResponseError("malformed trendbar numeric field") from exc
        opened = datetime.fromtimestamp(open_min * 60, tz=timezone.utc)
        completed = opened + timedelta(minutes=minutes)
        if opened < start:
            continue
        if completed > end:
            continue
        if completed >= protected:
            continue
        row = {
            "time_utc": iso_z(opened),
            "open": _base._format_price(low + d_open, digits),
            "high": _base._format_price(low + d_high, digits),
            "low": _base._format_price(low, digits),
            "close": _base._format_price(low + d_close, digits),
            "tick_volume": str(volume),
        }
        key = row["time_utc"]
        if key in seen and seen[key] != row:
            raise ResponseError(f"conflicting duplicate trendbar at {key}")
        seen[key] = row
    return [seen[key] for key in sorted(seen)]


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_capture_progress(
    *, overall_percent: float, stage: str, instrument: str, resolution: str,
    series_percent: float, completed_windows: int, total_windows: int,
    completed_chunks: int, historical_requests_completed: int,
    rows_captured: int, elapsed_seconds: float, effective_rps: float,
    reused_chunks: int, eta_seconds: float | None = None,
) -> str:
    overall = max(0.0, min(100.0, float(overall_percent)))
    series = max(0.0, min(100.0, float(series_percent)))
    text = (
        f"[CAPTURE {overall:5.1f}%] {stage} | {instrument} {resolution} | "
        f"series {series:5.1f}% | windows {completed_windows}/{total_windows} | "
        f"chunks {completed_chunks} | rows {rows_captured:,} | "
        f"hist req {historical_requests_completed} | {effective_rps:.2f} req/s | "
        f"elapsed {format_elapsed(elapsed_seconds)} | resume {reused_chunks}"
    )
    if eta_seconds is not None and eta_seconds >= 0:
        text += f" | ETA {format_elapsed(eta_seconds)}"
    return text


def build_pydroid_package(repo_root: Path | str, zip_path: Path | str) -> str:
    root = Path(repo_root)
    target = Path(zip_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    missing = [rel for rel in PYDROID_PACKAGE_FILES if not (root / rel).is_file()]
    if missing:
        raise CaptureContractError(f"Pydroid package source files missing: {missing}")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in PYDROID_PACKAGE_FILES:
            path = root / rel
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target, "r") as zf:
        names = set(zf.namelist())
    if names != set(PYDROID_PACKAGE_FILES):
        raise CaptureContractError("Pydroid deployment package contains unexpected or missing files")
    for name in names:
        if any(part in FORBIDDEN_TRANSFER_PATH_PARTS for part in name.replace("\\", "/").split("/")):
            raise CaptureContractError(f"local-only path leaked into Pydroid package: {name}")
    return sha256_file(target)


def _validate_transfer_names(names: Iterable[str]) -> dict[str, int]:
    normalized = {str(name).replace("\\", "/").lstrip("/") for name in names}
    missing = sorted(TRANSFERABLE_REQUIRED_FILES - normalized)
    if missing:
        raise CaptureContractError(f"final evidence bundle missing transferable artifacts: {missing}")
    raw_files = sorted(name for name in normalized if name.startswith("raw/") and name.endswith(".csv"))
    if len(raw_files) != 11:
        raise CaptureContractError(
            f"final evidence bundle must contain exactly 11 primary raw CSV files, found {len(raw_files)}"
        )
    for name in normalized:
        if set(name.split("/")).intersection(FORBIDDEN_TRANSFER_PATH_PARTS):
            raise CaptureContractError(f"local-only secret/work/cache path leaked into final evidence bundle: {name}")
    return {
        "primary_raw_files": len(raw_files),
        "auxiliary_raw_files": len([n for n in normalized if n.startswith("auxiliary/") and n.endswith(".csv")]),
        "required_transferable_files": len(TRANSFERABLE_REQUIRED_FILES),
    }


def validate_transferable_bundle(bundle_dir: Path | str) -> dict[str, int]:
    root = Path(bundle_dir)
    names = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]
    return _validate_transfer_names(names)


def validate_transferable_zip(zip_path: Path | str) -> dict[str, int]:
    with zipfile.ZipFile(Path(zip_path), "r") as zf:
        names = zf.namelist()
    return _validate_transfer_names(names)
