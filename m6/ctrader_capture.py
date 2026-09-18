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


def _account_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def live_account_candidates(accounts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    unique: dict[int, Mapping[str, Any]] = {}
    for account in accounts:
        aid = int(
            account.get(
                "ctidTraderAccountId",
                account.get("ctid_trader_account_id", 0),
            )
            or 0
        )
        if aid <= 0 or not _account_bool(
            account.get("isLive", account.get("is_live", False))
        ):
            continue
        unique[aid] = account
    return [unique[key] for key in sorted(unique)]


def select_live_pepperstone_account(
    accounts: Sequence[Mapping[str, Any]], *, account_override: int | None = None,
) -> Mapping[str, Any]:
    """Select the persisted authorized LIVE account without relying on lightweight title metadata.

    Pepperstone broker identity is verified immediately afterwards from ProtoOATraderRes
    before any market-data acquisition is accepted.
    """
    live = live_account_candidates(accounts)

    if account_override is not None:
        selected = [
            account
            for account in live
            if int(
                account.get(
                    "ctidTraderAccountId",
                    account.get("ctid_trader_account_id", 0),
                )
                or 0
            )
            == int(account_override)
        ]
        if len(selected) != 1:
            raise MappingError(
                "saved LIVE account is no longer authorized; one-time local reselection required"
            )
        return selected[0]

    pepperstone_named = [
        account
        for account in live
        if "pepperstone"
        in str(
            account.get(
                "brokerTitleShort",
                account.get("broker_title_short", ""),
            )
        ).lower()
    ]
    if len(pepperstone_named) == 1:
        return pepperstone_named[0]

    # Some account-list responses omit brokerTitleShort. One authorized LIVE account is
    # still unambiguous; the full trader response must then prove Pepperstone identity.
    if len(pepperstone_named) == 0 and len(live) == 1:
        return live[0]

    raise MappingError(
        f"authorized LIVE account selection is ambiguous ({len(live)} LIVE candidates); "
        "one-time local account selection required"
    )

PYDROID_PACKAGE_FILES = (
    "M6_CAPTURE_RUN.py",
    "m6/__init__.py",
    "m6/ctrader_capture.py",
    "m6/pydroid_oauth.py",
    "m6/pydroid_launcher.py",
    "m6/pydroid_symbol_mapping.py",
    "m6/_ctrader_capture_base.py",
    "m6/ctrader_openapi.py",
    "m6/ctrader_transport.py",
    "m6/ctrader_proto/__init__.py",
    "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
    "m6/ctrader_proto/OpenApiModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiMessages_pb2.py",
    "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
    "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json",
    "tools/requirements-m6-capture.txt",
    "README_RUN.txt",
)


SYMBOL_MAPPING_SOURCE_ENVIRONMENT = "Pepperstone - Europe LIVE"


def _symbol_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _symbol_name(symbol: Mapping[str, Any]) -> str:
    return str(symbol.get("symbolName", symbol.get("symbol_name", "")) or "").strip()


def _symbol_id(symbol: Mapping[str, Any]) -> int:
    try:
        return int(symbol.get("symbolId", symbol.get("symbol_id", 0)) or 0)
    except (TypeError, ValueError):
        return 0


def _symbol_enabled(symbol: Mapping[str, Any]) -> bool:
    return _symbol_bool(symbol.get("enabled", False))


def _symbol_parts(value: str) -> list[str]:
    return [part for part in __import__("re").findall(r"[A-Z0-9]+", str(value).upper()) if part]


def build_asset_catalog(assets: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    out: dict[int, Mapping[str, Any]] = {}
    for asset in assets:
        try:
            aid = int(asset.get("assetId", asset.get("asset_id", 0)) or 0)
        except (TypeError, ValueError):
            continue
        if aid > 0:
            out[aid] = asset
    return out


def _asset_norms(asset_id: Any, assets_by_id: Mapping[int, Mapping[str, Any]]) -> set[str]:
    try:
        asset = assets_by_id.get(int(asset_id or 0), {})
    except (TypeError, ValueError):
        asset = {}
    out = set()
    for key in ("name", "displayName", "display_name"):
        value = str(asset.get(key, "") or "").strip()
        if value:
            out.add(_base._norm_symbol(value))
    return {value for value in out if value}


def _candidate_row(
    symbol: Mapping[str, Any],
    *,
    support: Sequence[str],
    assets_by_id: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    base_id = symbol.get("baseAssetId", symbol.get("base_asset_id"))
    quote_id = symbol.get("quoteAssetId", symbol.get("quote_asset_id"))
    base = assets_by_id.get(int(base_id), {}) if str(base_id or "").isdigit() else {}
    quote = assets_by_id.get(int(quote_id), {}) if str(quote_id or "").isdigit() else {}
    return {
        "symbol_id": _symbol_id(symbol),
        "symbol_name": _symbol_name(symbol),
        "description": str(symbol.get("description", "") or ""),
        "enabled": _symbol_enabled(symbol),
        "base_asset_id": base_id,
        "base_asset_name": base.get("name") or base.get("displayName"),
        "quote_asset_id": quote_id,
        "quote_asset_name": quote.get("name") or quote.get("displayName"),
        "symbol_category_id": symbol.get("symbolCategoryId", symbol.get("symbol_category_id")),
        "support": sorted(set(str(x) for x in support if x)),
    }


def discover_symbol_mapping(
    canonical: str,
    light_symbols: Sequence[Mapping[str, Any]],
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Discover structural LIVE mapping candidates without aliases or economic information."""
    assets_by_id = assets_by_id or {}
    canonical_text = str(canonical).strip().upper()
    canonical_norm = _base._norm_symbol(canonical_text)
    exact: list[tuple[Mapping[str, Any], list[str]]] = []
    relaxed: list[tuple[Mapping[str, Any], list[str]]] = []
    related_scored: list[tuple[int, Mapping[str, Any], list[str]]] = []
    disabled_supported: list[tuple[Mapping[str, Any], list[str]]] = []

    for symbol in light_symbols:
        name = _symbol_name(symbol)
        if not name or _symbol_id(symbol) <= 0:
            continue
        name_upper = name.upper()
        name_norm = _base._norm_symbol(name)
        parts = _symbol_parts(name)
        base_norms = _asset_norms(
            symbol.get("baseAssetId", symbol.get("base_asset_id")), assets_by_id
        )
        quote_norms = _asset_norms(
            symbol.get("quoteAssetId", symbol.get("quote_asset_id")), assets_by_id
        )
        enabled = _symbol_enabled(symbol)
        reasons: list[str] = []
        is_exact = name_upper == canonical_text

        if not is_exact and name_norm == canonical_norm:
            reasons.append("PUNCTUATION_EQUIVALENT")
        if not is_exact and parts and _base._norm_symbol(parts[0]) == canonical_norm:
            reasons.append("CANONICAL_FIRST_BROKER_TOKEN")
        if canonical_norm in base_norms:
            reasons.append("BASE_ASSET_IDENTITY")
        if any(base + quote == canonical_norm for base in base_norms for quote in quote_norms):
            reasons.append("BASE_QUOTE_ASSET_IDENTITY")

        if is_exact:
            exact_reasons = ["EXACT_SYMBOL_NAME"]
            if enabled:
                exact.append((symbol, exact_reasons))
            else:
                disabled_supported.append((symbol, exact_reasons))
            continue

        if reasons:
            if enabled:
                relaxed.append((symbol, reasons))
            else:
                disabled_supported.append((symbol, reasons))
            continue

        # Related candidates are never auto-selected. They exist only to give the local
        # user a short structural LIVE list when the strict automatic evidence is zero.
        score = 0
        related_reasons: list[str] = []
        description_norm = _base._norm_symbol(str(symbol.get("description", "") or ""))
        if canonical_norm and canonical_norm in name_norm:
            score += 5
            related_reasons.append("CANONICAL_IN_BROKER_NAME")
        if canonical_norm and canonical_norm in description_norm:
            score += 3
            related_reasons.append("CANONICAL_IN_DESCRIPTION")
        for asset_norm in base_norms:
            if len(asset_norm) >= 3 and (
                asset_norm in canonical_norm or canonical_norm in asset_norm
            ):
                score += 4
                related_reasons.append("BASE_ASSET_TEXT_OVERLAP")
                break
        for base in base_norms:
            for quote in quote_norms:
                pair = base + quote
                if len(pair) >= 4 and (
                    pair in canonical_norm or canonical_norm in pair
                ):
                    score += 4
                    related_reasons.append("BASE_QUOTE_TEXT_OVERLAP")
                    break
            if "BASE_QUOTE_TEXT_OVERLAP" in related_reasons:
                break
        if enabled and score > 0:
            related_scored.append((score, symbol, related_reasons))

    def unique_rows(items):
        seen = set()
        rows = []
        for symbol, reasons in items:
            sid = _symbol_id(symbol)
            if sid in seen:
                continue
            seen.add(sid)
            rows.append(
                _candidate_row(symbol, support=reasons, assets_by_id=assets_by_id)
            )
        return rows

    exact_rows = unique_rows(exact)
    relaxed_rows = unique_rows(relaxed)
    credible_ids = {row["symbol_id"] for row in exact_rows + relaxed_rows}
    related_rows = []
    seen_related = set()
    for score, symbol, reasons in sorted(
        related_scored,
        key=lambda item: (-item[0], _symbol_name(item[1]).upper(), _symbol_id(item[1])),
    ):
        sid = _symbol_id(symbol)
        if sid in credible_ids or sid in seen_related:
            continue
        seen_related.add(sid)
        row = _candidate_row(symbol, support=reasons, assets_by_id=assets_by_id)
        row["related_score"] = score
        related_rows.append(row)
        if len(related_rows) >= 12:
            break

    disabled_rows = unique_rows(disabled_supported)
    credible_rows = sorted(
        exact_rows + relaxed_rows,
        key=lambda row: (row["symbol_name"].upper(), row["symbol_id"]),
    )
    return {
        "canonical": canonical,
        "exact_candidates": exact_rows,
        "relaxed_candidates": relaxed_rows,
        "credible_candidates": credible_rows,
        "related_candidates": related_rows,
        "disabled_supported_candidates": disabled_rows,
    }


def _find_symbol_by_id(
    light_symbols: Sequence[Mapping[str, Any]], symbol_id: int
) -> Mapping[str, Any] | None:
    for symbol in light_symbols:
        if _symbol_id(symbol) == int(symbol_id):
            return symbol
    return None


def validate_saved_symbol_override(
    canonical: str,
    saved_override: Mapping[str, Any],
    light_symbols: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    if str(saved_override.get("source_environment") or "") != SYMBOL_MAPPING_SOURCE_ENVIRONMENT:
        raise MappingError(f"{canonical}: saved mapping environment mismatch")
    try:
        sid = int(saved_override.get("symbol_id"))
    except (TypeError, ValueError):
        raise MappingError(f"{canonical}: saved mapping symbolId invalid") from None
    expected_name = str(saved_override.get("broker_symbol") or "")
    current = _find_symbol_by_id(light_symbols, sid)
    if current is None:
        raise MappingError(f"{canonical}: saved mapping symbolId no longer exists")
    if not _symbol_enabled(current):
        raise MappingError(f"{canonical}: saved mapping symbol is no longer enabled")
    if expected_name and _symbol_name(current) != expected_name:
        raise MappingError(f"{canonical}: saved mapping broker symbol name changed")
    return current


def resolve_symbol_mapping(
    canonical: str,
    light_symbols: Sequence[Mapping[str, Any]],
    *,
    exact_override: str | None = None,
    saved_override: Mapping[str, Any] | None = None,
    assets_by_id: Mapping[int, Mapping[str, Any]] | None = None,
) -> Mapping[str, Any]:
    if saved_override is not None:
        return validate_saved_symbol_override(canonical, saved_override, light_symbols)

    if exact_override:
        matches = [
            symbol
            for symbol in light_symbols
            if _symbol_name(symbol) == exact_override and _symbol_enabled(symbol)
        ]
        if len(matches) != 1:
            raise MappingError(
                f"{canonical}: exact local override {exact_override!r} is not one enabled LIVE symbol"
            )
        return matches[0]

    discovery = discover_symbol_mapping(
        canonical, light_symbols, assets_by_id=assets_by_id
    )
    candidates = discovery["credible_candidates"]
    if len(candidates) != 1:
        raise MappingError(
            f"{canonical}: automatic LIVE mapping unresolved; "
            f"exact={len(discovery['exact_candidates'])} "
            f"relaxed={len(discovery['relaxed_candidates'])}"
        )
    selected = _find_symbol_by_id(light_symbols, candidates[0]["symbol_id"])
    if selected is None:
        raise MappingError(f"{canonical}: selected LIVE symbol disappeared")
    return selected


def resolve_or_select_symbol_mapping(
    canonical: str,
    light_symbols: Sequence[Mapping[str, Any]],
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    saved_override: Mapping[str, Any] | None = None,
    selector: Any = None,
    clear_saved: Any = None,
) -> tuple[Mapping[str, Any], str, dict[str, Any]]:
    discovery = discover_symbol_mapping(
        canonical, light_symbols, assets_by_id=assets_by_id
    )

    stale_saved_override = False
    if saved_override is not None:
        try:
            return (
                validate_saved_symbol_override(canonical, saved_override, light_symbols),
                "PERSISTED_LOCAL_OVERRIDE",
                discovery,
            )
        except MappingError:
            stale_saved_override = True
            if callable(clear_saved):
                clear_saved(canonical)

    if not stale_saved_override:
        try:
            return (
                resolve_symbol_mapping(
                    canonical,
                    light_symbols,
                    assets_by_id=assets_by_id,
                ),
                "AUTO_LIVE_STRUCTURAL",
                discovery,
            )
        except MappingError:
            pass

    if not callable(selector):
        raise MappingError(
            f"{canonical}: local broker identity selection is required"
        )

    selected_id = selector(canonical, discovery)
    if selected_id in (None, 0, "0"):
        raise MappingError(f"{canonical}: local user selected BLOCK / none")

    try:
        selected_id = int(selected_id)
    except (TypeError, ValueError):
        raise MappingError(f"{canonical}: invalid local mapping selection") from None

    allowed_rows = (
        discovery["credible_candidates"]
        if discovery["credible_candidates"]
        else discovery["related_candidates"]
    )
    allowed_ids = {int(row["symbol_id"]) for row in allowed_rows}
    if selected_id not in allowed_ids:
        raise MappingError(
            f"{canonical}: local selection was not among current LIVE structural candidates"
        )
    selected = _find_symbol_by_id(light_symbols, selected_id)
    if selected is None or not _symbol_enabled(selected):
        raise MappingError(f"{canonical}: locally selected symbol is not currently enabled")
    return selected, "LOCAL_USER_SELECTION", discovery


def format_symbol_mapping_diagnostic(discovery: Mapping[str, Any]) -> list[str]:
    canonical = discovery["canonical"]
    lines = [
        f"[MAPPING DIAG] {canonical} | "
        f"exact={len(discovery['exact_candidates'])} | "
        f"relaxed={len(discovery['relaxed_candidates'])} | "
        f"related={len(discovery['related_candidates'])} | "
        f"disabled-supported={len(discovery['disabled_supported_candidates'])}"
    ]
    rows = (
        discovery["credible_candidates"]
        or discovery["related_candidates"]
        or discovery["disabled_supported_candidates"]
    )
    for row in rows:
        lines.append(
            "  - "
            f"{row['symbol_name']} | {row['description'] or '-'} | "
            f"symbolId {row['symbol_id']} | enabled={row['enabled']} | "
            f"base={row.get('base_asset_name') or '-'} | "
            f"quote={row.get('quote_asset_name') or '-'} | "
            f"support={','.join(row.get('support') or []) or '-'}"
        )
    if not rows:
        lines.append("  - no structurally related LIVE broker symbols found")
    return lines


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
