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
    categories_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    asset_classes_by_id: Mapping[int, Mapping[str, Any]] | None = None,
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



C011_ACTIVE_SPEC_HASH = "6fcf1f3f665fe6412a434c8272b18c2a5156d70f723409bc1340810bea8080fd"
C011_SEMANTIC_REQUIREMENTS_SHA256 = "e36c32a8948342f8760164efc7e8b90ebbd54b01374537d50432a50039270e8f"
MAPPING_POLICY_GENERIC = "GENERIC_STRUCTURAL_IDENTITY"
MAPPING_POLICY_US_EQUITY_CASH = "COMMON_EXECUTABLE_US_EQUITY_CASH_SESSION"
MAPPING_POLICY_INDEX_CASH_CFD = "CASH_INDEX_CFD_FULL_FEED_WITH_CANDIDATE_CASH_SESSION_FILTER"
MAPPING_POLICY_NON_FUTURES_CFD = "NON_FUTURES_BROKER_PRODUCT"

C006_ACTIVE_SPEC_HASH = "75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49"
C012_ACTIVE_SPEC_HASH = "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845"
C006_SEMANTIC_REQUIREMENTS_SHA256 = "e24de813748d345e1a68cddb7253e5fc4f8279431b82c9e387d9a5e5f4215765"
C012_SEMANTIC_REQUIREMENTS_SHA256 = "9385ea17a8f3e1e5868f16b9c394b7207b7027330cd41e2e11ada2b17e0c7859"
C007_ACTIVE_SPEC_HASH = "d0e35a07a4b947aee5114dbf8f8bdd226ae525781cc54be12cfbf2a18e1d2fba"
C008_ACTIVE_SPEC_HASH = "2df6728c2a9fe135f5a6908301a5378234a2ab08cb0c93046c3290c38f766370"
C009_ACTIVE_SPEC_HASH = "f276ade8d32e17957ab036676c14c913fa8825d8c1254c994249224c79f38856"
C010_ACTIVE_SPEC_HASH = "810670fbe6ed57c704a499c32799e6750417a431928eb55f8766b1ff87e46fc1"
C007_SEMANTIC_REQUIREMENTS_SHA256 = "b2d60e44f97adf79a8ec52c65d397f871af4a7053601329816cb449070000d8a"
C008_SEMANTIC_REQUIREMENTS_SHA256 = "36e609794c17d82be08aa4dae94ec0e1962925b2c495a645d976ab8cf2afa79d"
C009_SEMANTIC_REQUIREMENTS_SHA256 = "2a326bc861506861c4446f81e45d30518dc6ddfa05df52ea955dce5d3487a6cc"
C010_SEMANTIC_REQUIREMENTS_SHA256 = "55ddef74a91dabeca749da4bd68e59d964e8223769ba90abf9ee0f4190221fc8"


def mapping_semantic_policy(plan: Mapping[str, Any], canonical: str) -> str:
    """Bind broker-product selection to frozen candidate semantics only."""
    bindings = [
        item
        for item in plan.get("candidate_dataset_bindings", [])
        if item.get("canonical_instrument") == canonical
    ]
    policies = set()
    for binding in bindings:
        candidate_id = binding.get("candidate_id")
        spec_hash = binding.get("spec_hash")
        semantic_hash = binding.get("semantic_requirements_sha256")

        if candidate_id == "V2-C011":
            if spec_hash != C011_ACTIVE_SPEC_HASH:
                raise CaptureContractError(
                    f"{canonical}: V2-C011 active spec hash mismatch during symbol mapping"
                )
            if semantic_hash != C011_SEMANTIC_REQUIREMENTS_SHA256:
                raise CaptureContractError(
                    f"{canonical}: V2-C011 semantic binding hash mismatch during symbol mapping"
                )
            policies.add(MAPPING_POLICY_US_EQUITY_CASH)
            continue

        if candidate_id == "V2-C006":
            if spec_hash != C006_ACTIVE_SPEC_HASH:
                raise CaptureContractError(
                    f"{canonical}: V2-C006 active spec hash mismatch during symbol mapping"
                )
            if semantic_hash != C006_SEMANTIC_REQUIREMENTS_SHA256:
                raise CaptureContractError(
                    f"{canonical}: V2-C006 semantic binding hash mismatch during symbol mapping"
                )
            policies.add(MAPPING_POLICY_INDEX_CASH_CFD)
            continue

        if candidate_id == "V2-C012":
            if spec_hash != C012_ACTIVE_SPEC_HASH:
                raise CaptureContractError(
                    f"{canonical}: V2-C012 active spec hash mismatch during symbol mapping"
                )
            if semantic_hash != C012_SEMANTIC_REQUIREMENTS_SHA256:
                raise CaptureContractError(
                    f"{canonical}: V2-C012 semantic binding hash mismatch during symbol mapping"
                )
            policies.add(MAPPING_POLICY_INDEX_CASH_CFD)
            continue

        if candidate_id in {"V2-C007", "V2-C008", "V2-C009", "V2-C010"}:
            expected = {
                "V2-C007": (C007_ACTIVE_SPEC_HASH, C007_SEMANTIC_REQUIREMENTS_SHA256),
                "V2-C008": (C008_ACTIVE_SPEC_HASH, C008_SEMANTIC_REQUIREMENTS_SHA256),
                "V2-C009": (C009_ACTIVE_SPEC_HASH, C009_SEMANTIC_REQUIREMENTS_SHA256),
                "V2-C010": (C010_ACTIVE_SPEC_HASH, C010_SEMANTIC_REQUIREMENTS_SHA256),
            }[candidate_id]
            if spec_hash != expected[0] or semantic_hash != expected[1]:
                raise CaptureContractError(
                    f"{canonical}: {candidate_id} frozen binding mismatch during symbol mapping"
                )
            policies.add(MAPPING_POLICY_NON_FUTURES_CFD)
            continue

    if not policies:
        return MAPPING_POLICY_GENERIC
    if len(policies) != 1:
        raise CaptureContractError(
            f"{canonical}: frozen candidate bindings imply conflicting broker-product policies"
        )
    return next(iter(policies))


def _full_field(full_symbol: Mapping[str, Any], camel: str, snake: str | None = None, default: Any = None) -> Any:
    if camel in full_symbol:
        return full_symbol[camel]
    if snake and snake in full_symbol:
        return full_symbol[snake]
    return default


def _normalized_schedule(full_symbol: Mapping[str, Any]) -> tuple[list[dict[str, int]], bool]:
    raw = _full_field(full_symbol, "schedule", default=[]) or []
    intervals: list[dict[str, int]] = []
    valid = True
    for item in raw:
        try:
            start = int(item.get("startSecond", item.get("start_second")))
            end = int(item.get("endSecond", item.get("end_second")))
        except (AttributeError, TypeError, ValueError):
            valid = False
            continue
        if start < 0 or end <= start or end > 7 * 24 * 60 * 60:
            valid = False
            continue
        intervals.append({"start_second": start, "end_second": end})
    intervals.sort(key=lambda x: (x["start_second"], x["end_second"]))
    if not intervals:
        valid = False
    return intervals, valid


def build_symbol_category_catalog(
    categories: Sequence[Mapping[str, Any]],
) -> dict[int, Mapping[str, Any]]:
    out: dict[int, Mapping[str, Any]] = {}
    for item in categories:
        try:
            cid = int(item.get("id", 0) or 0)
        except (TypeError, ValueError):
            continue
        if cid > 0:
            out[cid] = item
    return out


def build_asset_class_catalog(
    asset_classes: Sequence[Mapping[str, Any]],
) -> dict[int, Mapping[str, Any]]:
    out: dict[int, Mapping[str, Any]] = {}
    for item in asset_classes:
        try:
            aid = int(item.get("id", 0) or 0)
        except (TypeError, ValueError):
            continue
        if aid > 0:
            out[aid] = item
    return out


def _contract_family(
    light_symbol: Mapping[str, Any],
    *,
    categories_by_id: Mapping[int, Mapping[str, Any]],
    asset_classes_by_id: Mapping[int, Mapping[str, Any]],
) -> tuple[str, list[str]]:
    name = _symbol_name(light_symbol)
    description = str(light_symbol.get("description", "") or "")
    try:
        category_id = int(
            light_symbol.get(
                "symbolCategoryId",
                light_symbol.get("symbol_category_id", 0),
            )
            or 0
        )
    except (TypeError, ValueError):
        category_id = 0
    category = categories_by_id.get(category_id, {})
    category_name = str(category.get("name", "") or "")
    try:
        asset_class_id = int(
            category.get("assetClassId", category.get("asset_class_id", 0)) or 0
        )
    except (TypeError, ValueError):
        asset_class_id = 0
    asset_class_name = str(asset_classes_by_id.get(asset_class_id, {}).get("name", "") or "")

    evidence_text = " ".join([name, description, category_name, asset_class_name]).upper()
    reasons: list[str] = []
    if any(token in evidence_text for token in ("FUTURE", "FUTURES", "FORWARD", "FORWARDS")):
        reasons.append("BROKER_CATEGORY_OR_DESCRIPTION_FUTURES_FORWARD")
    upper_name = name.upper()
    if upper_name.endswith("-F") or upper_name.endswith("_F") or upper_name.endswith(".F"):
        reasons.append("BROKER_F_SUFFIX_FUTURES_FORWARD")
    if reasons:
        return "FUTURES_FORWARD_LIKE", sorted(set(reasons))

    if "INDEX" in evidence_text or "INDICES" in evidence_text:
        reasons.append("BROKER_CATEGORY_OR_ASSET_CLASS_INDEX")
        return "CASH_SPOT_INDEX_CFD_LIKE", reasons

    return "UNKNOWN", reasons


def broker_product_profile(
    light_symbol: Mapping[str, Any],
    full_symbol: Mapping[str, Any] | None,
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    categories_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    asset_classes_by_id: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    assets_by_id = assets_by_id or {}
    categories_by_id = categories_by_id or {}
    asset_classes_by_id = asset_classes_by_id or {}
    sid = _symbol_id(light_symbol)
    base_id = light_symbol.get("baseAssetId", light_symbol.get("base_asset_id"))
    quote_id = light_symbol.get("quoteAssetId", light_symbol.get("quote_asset_id"))
    base = assets_by_id.get(int(base_id), {}) if str(base_id or "").isdigit() else {}
    quote = assets_by_id.get(int(quote_id), {}) if str(quote_id or "").isdigit() else {}
    name = _symbol_name(light_symbol)
    description = str(light_symbol.get("description", "") or "")
    try:
        category_id = int(
            light_symbol.get(
                "symbolCategoryId",
                light_symbol.get("symbol_category_id", 0),
            )
            or 0
        )
    except (TypeError, ValueError):
        category_id = 0
    category = categories_by_id.get(category_id, {})
    try:
        asset_class_id = int(
            category.get("assetClassId", category.get("asset_class_id", 0)) or 0
        )
    except (TypeError, ValueError):
        asset_class_id = 0
    category_name = str(category.get("name", "") or "")
    asset_class_name = str(asset_classes_by_id.get(asset_class_id, {}).get("name", "") or "")
    contract_family, contract_family_support = _contract_family(
        light_symbol,
        categories_by_id=categories_by_id,
        asset_classes_by_id=asset_classes_by_id,
    )

    if full_symbol is None:
        return {
            "symbol_id": sid,
            "symbol_name": name,
            "description": description,
            "light_enabled": _symbol_enabled(light_symbol),
            "full_metadata_available": False,
            "trading_mode": None,
            "enable_short_selling": None,
            "schedule_timezone": None,
            "schedule": [],
            "weekly_open_hours": None,
            "max_interval_hours": None,
            "session_class": "UNKNOWN_FULL_METADATA_MISSING",
            "explicit_24h_marker": False,
            "base_asset_id": base_id,
            "base_asset_name": base.get("name") or base.get("displayName"),
            "quote_asset_id": quote_id,
            "quote_asset_name": quote.get("name") or quote.get("displayName"),
            "symbol_category_id": category_id,
            "symbol_category_name": category_name,
            "asset_class_id": asset_class_id,
            "asset_class_name": asset_class_name,
            "contract_family": contract_family,
            "contract_family_support": contract_family_support,
            "session_fingerprint_sha256": None,
            "product_semantic_fingerprint_sha256": None,
        }

    intervals, schedule_valid = _normalized_schedule(full_symbol)
    weekly_seconds = sum(item["end_second"] - item["start_second"] for item in intervals)
    max_seconds = max((item["end_second"] - item["start_second"] for item in intervals), default=0)
    weekly_hours = weekly_seconds / 3600.0 if schedule_valid else None
    max_hours = max_seconds / 3600.0 if schedule_valid else None
    marker_text = (name + " " + description).upper()
    explicit_24h_marker = (
        "-24" in name.upper()
        or "(24 HOURS)" in marker_text
        or "24 HOURS" in marker_text
        or "24/5" in marker_text
    )

    if not schedule_valid:
        session_class = "UNKNOWN_SCHEDULE"
    elif weekly_hours is not None and (weekly_hours >= 80.0 or max_hours >= 18.0):
        session_class = "EXTENDED_24_5_LIKE"
    elif (
        weekly_hours is not None
        and 20.0 <= weekly_hours <= 50.0
        and max_hours is not None
        and max_hours <= 12.0
        and not explicit_24h_marker
    ):
        session_class = "US_CASH_SESSION_LIKE"
    else:
        session_class = "OTHER_SESSION_PROFILE"

    trading_mode = _full_field(full_symbol, "tradingMode", "trading_mode")
    short_enabled = _full_field(full_symbol, "enableShortSelling", "enable_short_selling")
    session_identity = {
        "schedule_timezone": _full_field(full_symbol, "scheduleTimeZone", "schedule_time_zone"),
        "schedule": intervals,
        "trading_mode": trading_mode,
    }
    product_identity = {
        "base_asset_id": base_id,
        "quote_asset_id": quote_id,
        "symbol_category_id": category_id,
        "symbol_category_name": category_name,
        "asset_class_id": asset_class_id,
        "asset_class_name": asset_class_name,
        "contract_family": contract_family,
        "session_identity": session_identity,
    }
    return {
        "symbol_id": sid,
        "symbol_name": name,
        "description": description,
        "light_enabled": _symbol_enabled(light_symbol),
        "full_metadata_available": True,
        "trading_mode": trading_mode,
        "enable_short_selling": short_enabled,
        "schedule_timezone": session_identity["schedule_timezone"],
        "schedule": intervals,
        "weekly_open_hours": round(weekly_hours, 4) if weekly_hours is not None else None,
        "max_interval_hours": round(max_hours, 4) if max_hours is not None else None,
        "session_class": session_class,
        "explicit_24h_marker": explicit_24h_marker,
        "base_asset_id": base_id,
        "base_asset_name": base.get("name") or base.get("displayName"),
        "quote_asset_id": quote_id,
        "quote_asset_name": quote.get("name") or quote.get("displayName"),
        "symbol_category_id": category_id,
        "symbol_category_name": category_name,
        "asset_class_id": asset_class_id,
        "asset_class_name": asset_class_name,
        "contract_family": contract_family,
        "contract_family_support": contract_family_support,
        "min_volume": _full_field(full_symbol, "minVolume", "min_volume"),
        "max_volume": _full_field(full_symbol, "maxVolume", "max_volume"),
        "step_volume": _full_field(full_symbol, "stepVolume", "step_volume"),
        "holiday_count": len(_full_field(full_symbol, "holiday", default=[]) or []),
        "session_fingerprint_sha256": sha256_bytes(canonical_json_bytes(session_identity)),
        "product_semantic_fingerprint_sha256": sha256_bytes(canonical_json_bytes(product_identity)),
    }


def _profile_is_enabled_tradable(profile: Mapping[str, Any]) -> bool:
    if not profile.get("light_enabled") or not profile.get("full_metadata_available"):
        return False
    return profile.get("trading_mode") in (0, "0", "ENABLED", None)


def profiled_mapping_candidates(
    discovery: Mapping[str, Any],
    light_symbols: Sequence[Mapping[str, Any]],
    full_by_id: Mapping[int, Mapping[str, Any]],
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    categories_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    asset_classes_by_id: Mapping[int, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = discovery.get("credible_candidates") or discovery.get("related_candidates") or []
    profiles = []
    for row in rows:
        sid = int(row["symbol_id"])
        light = _find_symbol_by_id(light_symbols, sid)
        if light is None:
            continue
        profiles.append(
            broker_product_profile(
                light,
                full_by_id.get(sid),
                assets_by_id=assets_by_id,
                categories_by_id=categories_by_id,
                asset_classes_by_id=asset_classes_by_id,
            )
        )
    return profiles


def format_broker_product_profiles(
    canonical: str,
    policy: str,
    profiles: Sequence[Mapping[str, Any]],
) -> list[str]:
    lines = [
        f"[PRODUCT PROFILE] {canonical} | policy={policy} | current LIVE variants={len(profiles)}"
    ]
    for profile in profiles:
        hours = profile.get("weekly_open_hours")
        max_hours = profile.get("max_interval_hours")
        hours_text = "?" if hours is None else f"{hours:.2f}h/week"
        max_text = "?" if max_hours is None else f"{max_hours:.2f}h max-session"
        lines.append(
            "  - "
            f"{profile.get('symbol_name')} | {profile.get('description') or '-'} | "
            f"symbolId {profile.get('symbol_id')} | "
            f"session={profile.get('session_class')} | "
            f"{hours_text} | {max_text} | "
            f"tz={profile.get('schedule_timezone') or '-'} | "
            f"category={profile.get('symbol_category_name') or '-'} | "
            f"assetClass={profile.get('asset_class_name') or '-'} | "
            f"family={profile.get('contract_family') or '-'} | "
            f"short={profile.get('enable_short_selling')} | "
            f"tradingMode={profile.get('trading_mode')}"
        )
    return lines


def resolve_profiled_broker_product(
    canonical: str,
    plan: Mapping[str, Any],
    discovery: Mapping[str, Any],
    light_symbols: Sequence[Mapping[str, Any]],
    full_by_id: Mapping[int, Mapping[str, Any]],
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    categories_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    asset_classes_by_id: Mapping[int, Mapping[str, Any]] | None = None,
    saved_override: Mapping[str, Any] | None = None,
    selector: Any = None,
    clear_saved: Any = None,
) -> tuple[Mapping[str, Any], Mapping[str, Any], str, str, list[dict[str, Any]]]:
    policy = mapping_semantic_policy(plan, canonical)
    profiles = profiled_mapping_candidates(
        discovery,
        light_symbols,
        full_by_id,
        assets_by_id=assets_by_id,
        categories_by_id=categories_by_id,
        asset_classes_by_id=asset_classes_by_id,
    )
    by_id = {int(profile["symbol_id"]): profile for profile in profiles}

    if saved_override is not None:
        try:
            saved_light = validate_saved_symbol_override(canonical, saved_override, light_symbols)
            saved_id = _symbol_id(saved_light)
            saved_profile = by_id.get(saved_id)
            if saved_profile is None or not _profile_is_enabled_tradable(saved_profile):
                raise MappingError(f"{canonical}: saved broker product full metadata invalid")
            if policy == MAPPING_POLICY_US_EQUITY_CASH:
                if saved_profile.get("session_class") != "US_CASH_SESSION_LIKE":
                    raise MappingError(
                        f"{canonical}: saved broker product violates frozen cash-session semantics"
                    )
            elif policy in {MAPPING_POLICY_INDEX_CASH_CFD, MAPPING_POLICY_NON_FUTURES_CFD}:
                if saved_profile.get("contract_family") == "FUTURES_FORWARD_LIKE":
                    raise MappingError(
                        f"{canonical}: saved broker product is futures/forward-like but frozen "
                        "raw identity requires a non-futures broker product"
                    )
            else:
                current_fp = saved_profile.get("product_semantic_fingerprint_sha256")
                saved_fp = saved_override.get("product_semantic_fingerprint_sha256")
                distinct = {
                    p.get("product_semantic_fingerprint_sha256")
                    for p in profiles
                    if _profile_is_enabled_tradable(p)
                }
                distinct.discard(None)
                if len(distinct) > 1 and saved_fp != current_fp:
                    raise MappingError(
                        f"{canonical}: saved mapping lacks current product-semantic binding"
                    )
            return saved_light, saved_profile, "PERSISTED_LOCAL_OVERRIDE", policy, profiles
        except MappingError:
            if callable(clear_saved):
                clear_saved(canonical)

    valid_profiles = [p for p in profiles if _profile_is_enabled_tradable(p)]

    if policy == MAPPING_POLICY_US_EQUITY_CASH:
        if any(not p.get("full_metadata_available") for p in profiles):
            raise MappingError(
                f"{canonical}: full LIVE metadata missing for at least one same-underlying "
                "broker product; cash-session semantic selection cannot be proven"
            )
        compatible = [
            p for p in valid_profiles
            if p.get("session_class") == "US_CASH_SESSION_LIKE"
        ]
        if len(compatible) != 1:
            raise MappingError(
                f"{canonical}: frozen V2-C011 requires one current LIVE "
                f"US cash-session share-CFD product; found {len(compatible)}"
            )
        profile = compatible[0]
        light = _find_symbol_by_id(light_symbols, int(profile["symbol_id"]))
        if light is None:
            raise MappingError(f"{canonical}: selected cash-session product disappeared")
        return light, profile, "AUTO_FROZEN_C011_CASH_SESSION", policy, profiles

    if policy == MAPPING_POLICY_INDEX_CASH_CFD:
        if any(not p.get("full_metadata_available") for p in profiles):
            raise MappingError(
                f"{canonical}: full LIVE metadata missing for at least one same-underlying "
                "index broker product; cash-index selection cannot be proven"
            )
        non_futures = [
            p
            for p in valid_profiles
            if p.get("contract_family") != "FUTURES_FORWARD_LIKE"
        ]
        explicit_cash_index = [
            p
            for p in non_futures
            if p.get("contract_family") == "CASH_SPOT_INDEX_CFD_LIKE"
        ]
        compatible = explicit_cash_index or non_futures
        exact_name = [
            p
            for p in compatible
            if str(p.get("symbol_name", "")).upper() == str(canonical).upper()
        ]
        if len(exact_name) == 1:
            compatible = exact_name
        if len(compatible) != 1:
            raise MappingError(
                f"{canonical}: frozen index-CFD requirements require one current LIVE "
                f"non-futures broker product; found {len(compatible)}"
            )
        profile = compatible[0]
        light = _find_symbol_by_id(light_symbols, int(profile["symbol_id"]))
        if light is None:
            raise MappingError(f"{canonical}: selected cash index product disappeared")
        return (
            light,
            profile,
            "AUTO_FROZEN_INDEX_CASH_CFD",
            policy,
            profiles,
        )

    if policy == MAPPING_POLICY_NON_FUTURES_CFD:
        if any(not p.get("full_metadata_available") for p in profiles):
            raise MappingError(
                f"{canonical}: full LIVE metadata missing for at least one same-underlying "
                "broker product; non-futures selection cannot be proven"
            )
        compatible = [
            p
            for p in valid_profiles
            if p.get("contract_family") != "FUTURES_FORWARD_LIKE"
        ]
        exact_name = [
            p
            for p in compatible
            if str(p.get("symbol_name", "")).upper() == str(canonical).upper()
        ]
        if len(exact_name) == 1:
            compatible = exact_name
        if len(compatible) != 1:
            raise MappingError(
                f"{canonical}: frozen requirements require one current LIVE non-futures "
                f"broker product; found {len(compatible)}"
            )
        profile = compatible[0]
        light = _find_symbol_by_id(light_symbols, int(profile["symbol_id"]))
        if light is None:
            raise MappingError(f"{canonical}: selected non-futures product disappeared")
        return (
            light,
            profile,
            "AUTO_FROZEN_NON_FUTURES_PRODUCT",
            policy,
            profiles,
        )

    credible_ids = {
        int(row["symbol_id"]) for row in discovery.get("credible_candidates", [])
    }
    valid_credible = [
        p for p in valid_profiles if int(p["symbol_id"]) in credible_ids
    ]
    if len(valid_credible) == 1:
        profile = valid_credible[0]
        light = _find_symbol_by_id(light_symbols, int(profile["symbol_id"]))
        return light, profile, "AUTO_LIVE_STRUCTURAL", policy, profiles

    candidates_for_choice = valid_credible or valid_profiles
    fingerprints = {
        p.get("product_semantic_fingerprint_sha256")
        for p in candidates_for_choice
        if p.get("product_semantic_fingerprint_sha256")
    }
    if len(fingerprints) > 1:
        raise MappingError(
            f"{canonical}: multiple LIVE broker products have different execution/session "
            "semantics; frozen requirements do not select one"
        )

    if not candidates_for_choice:
        raise MappingError(
            f"{canonical}: no enabled/tradable LIVE broker product has sufficient structural support"
        )
    if not callable(selector):
        raise MappingError(f"{canonical}: equivalent broker identity selection required")

    context = dict(discovery)
    context["candidate_product_profiles"] = candidates_for_choice
    selected_id = selector(canonical, context)
    if selected_id in (None, 0, "0"):
        raise MappingError(f"{canonical}: local user selected BLOCK / none")
    try:
        selected_id = int(selected_id)
    except (TypeError, ValueError):
        raise MappingError(f"{canonical}: invalid local mapping selection") from None
    profile = next(
        (p for p in candidates_for_choice if int(p["symbol_id"]) == selected_id),
        None,
    )
    if profile is None:
        raise MappingError(
            f"{canonical}: local selection was not among semantically equivalent LIVE products"
        )
    light = _find_symbol_by_id(light_symbols, selected_id)
    if light is None:
        raise MappingError(f"{canonical}: locally selected product disappeared")
    return light, profile, "LOCAL_EQUIVALENT_PRODUCT_SELECTION", policy, profiles


TRANSFERABLE_REQUIRED_FILES = frozenset({
    "provenance_manifest.json",
    "bundle_manifest.json",
    "CHECKSUMS.sha256",
    "evidence/account.json",
    "evidence/broker_mapping.json",
    "evidence/symbol_metadata_current.json",
    "evidence/assets.json",
    "evidence/symbol_categories.json",
    "evidence/asset_classes.json",
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
