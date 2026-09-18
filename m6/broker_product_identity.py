"""Structural Pepperstone broker-product identity resolution for frozen PRIMARY_WAVE_02.

This module is deliberately pre-economic. It consumes current cTrader broker metadata plus
frozen research requirements and returns a fail-closed product bridge. It never reads PnL,
returns, ranks, legacy winners, or protected-forward evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

PRODUCT_FAMILIES = frozenset({
    "FX_SPOT_OR_MARGIN_CFD",
    "SPOT_METAL_CFD",
    "SPOT_ENERGY_CFD",
    "SPOT_CRYPTO_CFD",
    "CASH_INDEX_CFD",
    "INDEX_FORWARD_OR_FUTURES_CFD",
    "COMMODITY_FORWARD_OR_FUTURES_CFD",
    "STANDARD_CASH_SHARE_CFD",
    "EXTENDED_HOURS_SHARE_CFD",
    "PERPETUAL_INDEX_CFD",
    "PERPETUAL_SHARE_CFD",
    "PERPETUAL_COMMODITY_CFD",
    "OTHER_PERPETUAL_CFD",
    "OTHER_CFD",
    "UNKNOWN",
})

CANONICAL_ORDER = (
    "US500", "NAS100", "XAUUSD", "WTIUSD", "BTCUSD", "AUDJPY",
    "AAPL", "MSFT", "NVDA", "AMZN", "META",
)

# The preferred names are current public Pepperstone corroboration, not a substitute for
# LIVE account metadata. They are used only to disambiguate two otherwise structurally
# eligible current products. If absent, one unique structurally eligible product still passes.
CANONICAL_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "US500": {
        "expected_family": "CASH_INDEX_CFD",
        "candidate_ids": ["V2-C006", "V2-C012"],
        "preferred_broker_symbols": ["US500"],
        "aliases": ["US500", "SP500", "S&P500", "S&P 500"],
        "source_ids": ["PEPPERSTONE_INDEX_CURRENT", "PEPPERSTONE_PERPETUAL_CURRENT"],
        "mapping_policy": "FROZEN_CASH_INDEX_CFD_FULL_FEED_CANDIDATE_SESSION_FILTER_LATER",
    },
    "NAS100": {
        "expected_family": "CASH_INDEX_CFD",
        "candidate_ids": ["V2-C012"],
        "preferred_broker_symbols": ["NAS100"],
        "aliases": ["NAS100", "NASDAQ100", "NASDAQ 100"],
        "source_ids": ["PEPPERSTONE_INDEX_CURRENT", "PEPPERSTONE_PERPETUAL_CURRENT"],
        "mapping_policy": "FROZEN_CASH_INDEX_CFD_FULL_FEED_CANDIDATE_SESSION_FILTER_LATER",
    },
    "XAUUSD": {
        "expected_family": "SPOT_METAL_CFD",
        "candidate_ids": ["V2-C007"],
        "preferred_broker_symbols": ["XAUUSD"],
        "aliases": ["XAUUSD", "XAU/USD", "GOLD"],
        "source_ids": ["PEPPERSTONE_COMMODITIES_CURRENT", "PEPPERSTONE_FORWARD_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_SPOT_GOLD_CFD",
    },
    "WTIUSD": {
        "expected_family": "SPOT_ENERGY_CFD",
        "candidate_ids": ["V2-C008"],
        "preferred_broker_symbols": ["SPOTCRUDE", "WTIUSD"],
        "aliases": ["WTIUSD", "WTI/USD", "WTI", "SPOTCRUDE", "CRUDE"],
        "source_ids": ["PEPPERSTONE_COMMODITIES_CURRENT", "PEPPERSTONE_SPOTCRUDE_CURRENT_SYMBOL_CORROBORATION", "PEPPERSTONE_FORWARD_CURRENT", "PEPPERSTONE_PERPETUAL_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_SPOT_WTI_CRUDE_CFD_CURRENT_MAPPING_ONLY",
    },
    "BTCUSD": {
        "expected_family": "SPOT_CRYPTO_CFD",
        "candidate_ids": ["V2-C009"],
        "preferred_broker_symbols": ["BTCUSD"],
        "aliases": ["BTCUSD", "BTC/USD", "BITCOIN"],
        "source_ids": ["PEPPERSTONE_BTCUSD_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_BTCUSD_CRYPTO_CFD",
    },
    "AUDJPY": {
        "expected_family": "FX_SPOT_OR_MARGIN_CFD",
        "candidate_ids": ["V2-C010"],
        "preferred_broker_symbols": ["AUDJPY"],
        "aliases": ["AUDJPY", "AUD/JPY"],
        "source_ids": ["PEPPERSTONE_FX_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_AUDJPY_MARGIN_FX",
    },
    "AAPL": {
        "expected_family": "STANDARD_CASH_SHARE_CFD",
        "candidate_ids": ["V2-C011"],
        "preferred_broker_symbols": ["AAPL.US"],
        "aliases": ["AAPL"],
        "source_ids": ["PEPPERSTONE_US_SHARES_CURRENT", "PEPPERSTONE_SHARE_24H_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_US_SHARE_CASH_SESSION_PRODUCT",
    },
    "MSFT": {
        "expected_family": "STANDARD_CASH_SHARE_CFD",
        "candidate_ids": ["V2-C011"],
        "preferred_broker_symbols": ["MSFT.US"],
        "aliases": ["MSFT"],
        "source_ids": ["PEPPERSTONE_US_SHARES_CURRENT", "PEPPERSTONE_SHARE_24H_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_US_SHARE_CASH_SESSION_PRODUCT",
    },
    "NVDA": {
        "expected_family": "STANDARD_CASH_SHARE_CFD",
        "candidate_ids": ["V2-C011"],
        "preferred_broker_symbols": ["NVDA.US"],
        "aliases": ["NVDA"],
        "source_ids": ["PEPPERSTONE_US_SHARES_CURRENT", "PEPPERSTONE_SHARE_24H_CURRENT", "PEPPERSTONE_PERPETUAL_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_US_SHARE_CASH_SESSION_PRODUCT",
    },
    "AMZN": {
        "expected_family": "STANDARD_CASH_SHARE_CFD",
        "candidate_ids": ["V2-C011"],
        "preferred_broker_symbols": ["AMZN.US"],
        "aliases": ["AMZN"],
        "source_ids": ["PEPPERSTONE_US_SHARES_CURRENT", "PEPPERSTONE_SHARE_24H_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_US_SHARE_CASH_SESSION_PRODUCT",
    },
    "META": {
        "expected_family": "STANDARD_CASH_SHARE_CFD",
        "candidate_ids": ["V2-C011"],
        "preferred_broker_symbols": ["META.US"],
        "aliases": ["META"],
        "source_ids": ["PEPPERSTONE_US_SHARES_CURRENT", "PEPPERSTONE_SHARE_24H_CURRENT"],
        "mapping_policy": "FROZEN_STANDARD_US_SHARE_CASH_SESSION_PRODUCT",
    },
}

ECONOMIC_FIELD_NAMES = frozenset({
    "pnl", "return", "returns", "sharpe", "rank", "ranking", "winner", "loser",
    "legacy_rank", "legacy_winner", "candidate_rank", "expected_return", "profit",
    "performance", "score",
})


def _json_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _field(row: Mapping[str, Any], camel: str, snake: str | None = None, default: Any = None) -> Any:
    if camel in row:
        return row[camel]
    if snake and snake in row:
        return row[snake]
    return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_catalog(rows: Sequence[Mapping[str, Any]], id_fields: Sequence[str]) -> dict[int, Mapping[str, Any]]:
    out: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        value = 0
        for key in id_fields:
            if key in row:
                value = _int(row.get(key))
                if value:
                    break
        if value > 0:
            out[value] = row
    return out


def _asset_text(asset_id: Any, assets_by_id: Mapping[int, Mapping[str, Any]]) -> str:
    row = assets_by_id.get(_int(asset_id), {})
    return " ".join(str(row.get(k) or "") for k in ("name", "displayName", "display_name")).strip()


def structural_text(
    light: Mapping[str, Any],
    full: Mapping[str, Any] | None,
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]],
    categories_by_id: Mapping[int, Mapping[str, Any]],
    asset_classes_by_id: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    category_id = _int(_field(light, "symbolCategoryId", "symbol_category_id"))
    category = categories_by_id.get(category_id, {})
    asset_class_id = _int(_field(category, "assetClassId", "asset_class_id"))
    asset_class = asset_classes_by_id.get(asset_class_id, {})
    base_id = _field(light, "baseAssetId", "base_asset_id")
    quote_id = _field(light, "quoteAssetId", "quote_asset_id")
    name = str(_field(light, "symbolName", "symbol_name", "") or "")
    description = str(light.get("description") or "")
    category_name = str(category.get("name") or "")
    asset_class_name = str(asset_class.get("name") or "")
    base_text = _asset_text(base_id, assets_by_id)
    quote_text = _asset_text(quote_id, assets_by_id)
    measurement = str(_field(full or {}, "measurementUnits", "measurement_units", "") or "")
    joined = " | ".join((name, description, category_name, asset_class_name, base_text, quote_text, measurement))
    return {
        "name": name,
        "description": description,
        "category_id": category_id,
        "category_name": category_name,
        "asset_class_id": asset_class_id,
        "asset_class_name": asset_class_name,
        "base_asset_id": base_id,
        "base_asset_name": base_text,
        "quote_asset_id": quote_id,
        "quote_asset_name": quote_text,
        "measurement_units": measurement,
        "joined_upper": joined.upper(),
    }


def classify_product_family(
    light: Mapping[str, Any],
    full: Mapping[str, Any] | None,
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]],
    categories_by_id: Mapping[int, Mapping[str, Any]],
    asset_classes_by_id: Mapping[int, Mapping[str, Any]],
) -> tuple[str, list[str], list[str]]:
    s = structural_text(
        light, full,
        assets_by_id=assets_by_id,
        categories_by_id=categories_by_id,
        asset_classes_by_id=asset_classes_by_id,
    )
    text = s["joined_upper"]
    name = s["name"].upper()
    evidence: list[str] = []
    conflicts: list[str] = []

    perpetual = "PERPETUAL" in text or "-PERP" in name or name.endswith("PERP")
    forward = (
        name.endswith("-F") or name.endswith("_F") or name.endswith(".F")
        or " FORWARD" in text or " FORWARDS" in text
        or " FUTURE" in text or " FUTURES" in text
    )
    if perpetual:
        evidence.append("PERPETUAL_MARKER")
    if forward:
        evidence.append("FORWARD_OR_FUTURES_MARKER")
    if perpetual and forward:
        conflicts.append("CONTRADICTORY_PERPETUAL_AND_FORWARD_MARKERS")
        return "UNKNOWN", evidence, conflicts

    share = any(x in text for x in ("SHARE", "STOCK", "EQUIT"))
    index = any(x in text for x in ("INDEX", "INDICES", "US500", "NAS100", "SP500", "S&P 500"))
    metal = any(x in text for x in ("XAU", "GOLD", "SILVER", "METAL"))
    energy = any(x in text for x in ("WTI", "CRUDE", "BRENT", "NATGAS", "NATURAL GAS", "GASOLINE", "ENERGY"))
    crypto = any(x in text for x in ("BTC", "BITCOIN", "CRYPTO"))
    fx = any(x in text for x in ("FOREX", " FX ", "FOREIGN EXCHANGE"))

    # Broker naming can be more specific than category labels. Shares are resolved before
    # generic index/commodity words if the broker symbol itself has the known share suffix.
    if re.search(r"\.(US|N)$", name) or ".US-24" in name or ".US-PERP" in name:
        share = True

    if perpetual:
        if index and not share:
            return "PERPETUAL_INDEX_CFD", evidence + ["INDEX_STRUCTURE"], conflicts
        if share:
            return "PERPETUAL_SHARE_CFD", evidence + ["SHARE_STRUCTURE"], conflicts
        if energy or metal:
            return "PERPETUAL_COMMODITY_CFD", evidence + ["COMMODITY_STRUCTURE"], conflicts
        return "OTHER_PERPETUAL_CFD", evidence, conflicts

    if forward:
        if index and not share:
            return "INDEX_FORWARD_OR_FUTURES_CFD", evidence + ["INDEX_STRUCTURE"], conflicts
        if energy or metal:
            return "COMMODITY_FORWARD_OR_FUTURES_CFD", evidence + ["COMMODITY_STRUCTURE"], conflicts
        return "OTHER_CFD", evidence, conflicts

    extended_share = "-24" in name or "24 HOURS" in text or "24/5" in text
    if share:
        if extended_share:
            return "EXTENDED_HOURS_SHARE_CFD", evidence + ["SHARE_STRUCTURE", "EXTENDED_HOURS_MARKER"], conflicts
        return "STANDARD_CASH_SHARE_CFD", evidence + ["SHARE_STRUCTURE"], conflicts
    if index:
        return "CASH_INDEX_CFD", evidence + ["INDEX_STRUCTURE"], conflicts
    if metal:
        return "SPOT_METAL_CFD", evidence + ["METAL_STRUCTURE"], conflicts
    if energy:
        return "SPOT_ENERGY_CFD", evidence + ["ENERGY_STRUCTURE"], conflicts
    if crypto:
        return "SPOT_CRYPTO_CFD", evidence + ["CRYPTO_STRUCTURE"], conflicts

    base = _norm(s["base_asset_name"])
    quote = _norm(s["quote_asset_name"])
    name_norm = _norm(name)
    if fx or (len(base) == 3 and len(quote) == 3 and name_norm.startswith(base + quote)):
        return "FX_SPOT_OR_MARGIN_CFD", evidence + ["FX_BASE_QUOTE_STRUCTURE"], conflicts
    return "UNKNOWN", evidence, conflicts


def _normalized_schedule(full: Mapping[str, Any] | None) -> list[dict[str, int]]:
    out: list[dict[str, int]] = []
    for item in (_field(full or {}, "schedule", default=[]) or []):
        start = _int(item.get("startSecond", item.get("start_second")), -1) if isinstance(item, Mapping) else -1
        end = _int(item.get("endSecond", item.get("end_second")), -1) if isinstance(item, Mapping) else -1
        if 0 <= start < end <= 7 * 86400:
            out.append({"start_second": start, "end_second": end})
    return sorted(out, key=lambda x: (x["start_second"], x["end_second"]))


def product_profile(
    light: Mapping[str, Any],
    full: Mapping[str, Any] | None,
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]],
    categories_by_id: Mapping[int, Mapping[str, Any]],
    asset_classes_by_id: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    s = structural_text(
        light, full,
        assets_by_id=assets_by_id,
        categories_by_id=categories_by_id,
        asset_classes_by_id=asset_classes_by_id,
    )
    family, classification_evidence, conflicts = classify_product_family(
        light, full,
        assets_by_id=assets_by_id,
        categories_by_id=categories_by_id,
        asset_classes_by_id=asset_classes_by_id,
    )
    schedule = _normalized_schedule(full)
    trading_mode = _field(full or {}, "tradingMode", "trading_mode")
    structural_identity = {
        "symbol_name": s["name"],
        "product_family": family,
        "base_asset_id": s["base_asset_id"],
        "quote_asset_id": s["quote_asset_id"],
        "symbol_category_id": s["category_id"],
        "asset_class_id": s["asset_class_id"],
        "trading_mode": trading_mode,
        "schedule_time_zone": _field(full or {}, "scheduleTimeZone", "schedule_time_zone"),
        "schedule": schedule,
        "measurement_units": s["measurement_units"],
        "lot_size": _field(full or {}, "lotSize", "lot_size"),
        "min_volume": _field(full or {}, "minVolume", "min_volume"),
        "max_volume": _field(full or {}, "maxVolume", "max_volume"),
        "step_volume": _field(full or {}, "stepVolume", "step_volume"),
    }
    return {
        "symbol_id": _int(_field(light, "symbolId", "symbol_id")),
        "symbol_name": s["name"],
        "description": s["description"],
        "enabled": _bool(light.get("enabled")),
        "full_metadata_available": full is not None,
        "product_family": family,
        "classification_evidence": classification_evidence,
        "classification_conflicts": conflicts,
        "base_asset_id": s["base_asset_id"],
        "base_asset_name": s["base_asset_name"],
        "quote_asset_id": s["quote_asset_id"],
        "quote_asset_name": s["quote_asset_name"],
        "symbol_category_id": s["category_id"],
        "category_name": s["category_name"],
        "asset_class_id": s["asset_class_id"],
        "asset_class_name": s["asset_class_name"],
        "trading_mode": trading_mode,
        "schedule_time_zone": structural_identity["schedule_time_zone"],
        "schedule": schedule,
        "measurement_units": s["measurement_units"],
        "min_volume": structural_identity["min_volume"],
        "max_volume": structural_identity["max_volume"],
        "step_volume": structural_identity["step_volume"],
        "lot_size": structural_identity["lot_size"],
        "schedule_fingerprint_sha256": _json_hash({
            "schedule_time_zone": structural_identity["schedule_time_zone"],
            "schedule": schedule,
            "trading_mode": trading_mode,
        }) if full is not None else None,
        "structural_execution_fingerprint_sha256": _json_hash(structural_identity) if full is not None else None,
    }


def _base_quote_match(canonical: str, profile: Mapping[str, Any]) -> bool:
    base = _norm(profile.get("base_asset_name"))
    quote = _norm(profile.get("quote_asset_name"))
    if canonical == "AUDJPY":
        return base == "AUD" and quote == "JPY"
    if canonical == "BTCUSD":
        return base in {"BTC", "BITCOIN"} and quote == "USD"
    if canonical == "XAUUSD":
        return base in {"XAU", "GOLD"} and quote == "USD"
    return False


def identity_match(canonical: str, profile: Mapping[str, Any]) -> bool:
    req = CANONICAL_REQUIREMENTS[canonical]
    name = str(profile.get("symbol_name") or "").upper()
    name_norm = _norm(name)
    text_norm = _norm(" ".join([
        name,
        str(profile.get("description") or ""),
        str(profile.get("base_asset_name") or ""),
    ]))

    if canonical in {"AAPL", "MSFT", "NVDA", "AMZN", "META"}:
        return (
            name_norm == canonical
            or name_norm.startswith(canonical + "US")
            or name_norm.startswith(canonical + "N")
            or _norm(profile.get("base_asset_name")) == canonical
        )
    if _base_quote_match(canonical, profile):
        return True
    if canonical == "WTIUSD":
        if any(x in text_norm for x in ("BRENT", "GASOLINE", "NATGAS", "NATURALGAS")):
            return False
        return any(_norm(alias) in text_norm for alias in req["aliases"])
    return any(_norm(alias) in text_norm for alias in req["aliases"])


def structurally_relevant(
    canonical: str,
    profile: Mapping[str, Any],
) -> bool:
    if identity_match(canonical, profile):
        return True
    family = str(profile.get("product_family") or "")
    text = _norm(" ".join([
        str(profile.get("symbol_name") or ""),
        str(profile.get("description") or ""),
        str(profile.get("asset_class_name") or ""),
        str(profile.get("category_name") or ""),
    ]))
    if canonical == "WTIUSD":
        return family in {
            "SPOT_ENERGY_CFD", "COMMODITY_FORWARD_OR_FUTURES_CFD",
            "PERPETUAL_COMMODITY_CFD", "OTHER_PERPETUAL_CFD",
        } and any(x in text for x in ("WTI", "CRUDE", "BRENT", "GASOLINE", "NATGAS", "NATURALGAS"))
    return False


def relevant_symbol_ids(
    light_symbols: Sequence[Mapping[str, Any]],
    *,
    assets_by_id: Mapping[int, Mapping[str, Any]],
    categories_by_id: Mapping[int, Mapping[str, Any]],
    asset_classes_by_id: Mapping[int, Mapping[str, Any]],
) -> set[int]:
    ids: set[int] = set()
    for light in light_symbols:
        profile = product_profile(
            light, None,
            assets_by_id=assets_by_id,
            categories_by_id=categories_by_id,
            asset_classes_by_id=asset_classes_by_id,
        )
        if any(structurally_relevant(canonical, profile) for canonical in CANONICAL_ORDER):
            sid = _int(profile["symbol_id"])
            if sid > 0:
                ids.add(sid)
    return ids


def _tradable(profile: Mapping[str, Any]) -> bool:
    if not profile.get("enabled") or not profile.get("full_metadata_available"):
        return False
    # ProtoOATradingMode.ENABLED is 0. Some server JSON/default-field serializers omit it.
    return profile.get("trading_mode") in (None, 0, "0", "ENABLED")


def _exclusion_reasons(canonical: str, profile: Mapping[str, Any]) -> list[str]:
    req = CANONICAL_REQUIREMENTS[canonical]
    reasons: list[str] = []
    if not profile.get("enabled"):
        reasons.append("NOT_CURRENTLY_ENABLED")
    if not profile.get("full_metadata_available"):
        reasons.append("FULL_CURRENT_METADATA_MISSING")
    if profile.get("classification_conflicts"):
        reasons.append("CONTRADICTORY_BROKER_METADATA")
    if not identity_match(canonical, profile):
        reasons.append("DIFFERENT_UNDERLYING_OR_CANONICAL_IDENTITY")
    if profile.get("product_family") != req["expected_family"]:
        reasons.append("MATERIALLY_DIFFERENT_PRODUCT_FAMILY")
    if not _tradable(profile):
        reasons.append("NOT_CURRENTLY_TRADABLE_BY_STRUCTURAL_METADATA")
    return sorted(set(reasons))


def resolve_all_11(
    light_symbols: Sequence[Mapping[str, Any]],
    full_by_id: Mapping[int, Mapping[str, Any]],
    *,
    archived_symbols: Sequence[Mapping[str, Any]] = (),
    assets_by_id: Mapping[int, Mapping[str, Any]],
    categories_by_id: Mapping[int, Mapping[str, Any]],
    asset_classes_by_id: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    profiles_by_id = {
        _int(_field(light, "symbolId", "symbol_id")): product_profile(
            light,
            full_by_id.get(_int(_field(light, "symbolId", "symbol_id"))),
            assets_by_id=assets_by_id,
            categories_by_id=categories_by_id,
            asset_classes_by_id=asset_classes_by_id,
        )
        for light in light_symbols
        if _int(_field(light, "symbolId", "symbol_id")) > 0
    }

    bridge: dict[str, Any] = {}
    matrix: list[dict[str, Any]] = []
    for canonical in CANONICAL_ORDER:
        req = CANONICAL_REQUIREMENTS[canonical]
        candidates = [
            p for p in profiles_by_id.values()
            if structurally_relevant(canonical, p)
        ]
        candidates.sort(key=lambda x: (str(x.get("symbol_name")), int(x.get("symbol_id") or 0)))
        eligible = [
            p for p in candidates
            if not _exclusion_reasons(canonical, p)
        ]

        preferred_norms = {_norm(x) for x in req["preferred_broker_symbols"]}
        preferred = [p for p in eligible if _norm(p.get("symbol_name")) in preferred_norms]
        selected: Mapping[str, Any] | None = None
        selection_basis = None
        if len(preferred) == 1:
            selected = preferred[0]
            selection_basis = "UNIQUE_OFFICIAL_CURRENT_NAME_PLUS_LIVE_STRUCTURAL_MATCH"
        elif len(eligible) == 1:
            selected = eligible[0]
            selection_basis = "UNIQUE_LIVE_STRUCTURAL_PRODUCT_MATCH"

        exclusions = []
        for p in candidates:
            if selected is not None and int(p["symbol_id"]) == int(selected["symbol_id"]):
                continue
            reasons = _exclusion_reasons(canonical, p)
            if not reasons and len(eligible) > 1:
                reasons = ["AMBIGUOUS_MULTIPLE_STRUCTURALLY_ELIGIBLE_CURRENT_PRODUCTS"]
            exclusions.append({
                "symbol_id": p["symbol_id"],
                "broker_symbol": p["symbol_name"],
                "product_family": p["product_family"],
                "reasons": reasons or ["NOT_SELECTED_AFTER_STRUCTURAL_DISAMBIGUATION"],
            })

        archived_related = []
        for archived in archived_symbols:
            name = str(_field(archived, "symbolName", "symbol_name", archived.get("name", "")) or "")
            pseudo = {
                "symbol_name": name,
                "description": archived.get("description", ""),
                "base_asset_name": "",
                "quote_asset_name": "",
                "product_family": "UNKNOWN",
            }
            if any(_norm(alias) in _norm(name + " " + str(archived.get("description", ""))) for alias in req["aliases"]):
                archived_related.append({
                    "symbol_id": _int(_field(archived, "symbolId", "symbol_id")),
                    "broker_symbol": name,
                    "description": archived.get("description"),
                    "utc_last_update_timestamp": _field(archived, "utcLastUpdateTimestamp", "utc_last_update_timestamp"),
                    "role": "ARCHIVED_LINEAGE_EVIDENCE_ONLY_NOT_CURRENT_MAPPING",
                })

        if selected is None:
            status = "BLOCKED"
            row = {
                "canonical": canonical,
                "broker_symbol": None,
                "symbol_id": None,
                "product_family": req["expected_family"],
                "category": None,
                "asset_class": None,
                "enabled": None,
                "trading_mode": None,
                "mapping_policy": req["mapping_policy"],
                "mapping_evidence": (
                    f"eligible={len(eligible)}; preferred={len(preferred)}; "
                    "fail-closed structural identity ambiguity/missing product"
                ),
                "status": status,
            }
            confidence = "UNRESOLVED"
        else:
            status = "PASS"
            row = {
                "canonical": canonical,
                "broker_symbol": selected["symbol_name"],
                "symbol_id": selected["symbol_id"],
                "product_family": selected["product_family"],
                "category": selected["category_name"],
                "asset_class": selected["asset_class_name"],
                "enabled": selected["enabled"],
                "trading_mode": selected["trading_mode"],
                "mapping_policy": req["mapping_policy"],
                "mapping_evidence": selection_basis,
                "status": status,
            }
            confidence = "HIGH_CURRENT_STRUCTURAL"

        bridge[canonical] = {
            "canonical_instrument": canonical,
            "expected_product_family": req["expected_family"],
            "frozen_candidate_ids": req["candidate_ids"],
            "frozen_mapping_policy": req["mapping_policy"],
            "supporting_official_public_source_ids": req["source_ids"],
            "selected_current_product": dict(selected) if selected is not None else None,
            "selection_basis": selection_basis,
            "excluded_materially_different_products": exclusions,
            "archived_lineage_evidence": archived_related,
            "confidence": confidence,
            "status": status,
            "current_mapping_is_not_historical_metadata": True,
            "economic_fields_consulted": False,
            "legacy_fields_consulted": False,
        }
        matrix.append(row)

    passed = sum(1 for row in matrix if row["status"] == "PASS")
    return {
        "schema": "mxm.greenfield.v2.current-broker-product-bridge.v1",
        "canonical_order": list(CANONICAL_ORDER),
        "pass_count": passed,
        "required_count": len(CANONICAL_ORDER),
        "all_current_mappings_pass": passed == len(CANONICAL_ORDER),
        "historical_capture_authorized_by_preflight": passed == len(CANONICAL_ORDER),
        "matrix": matrix,
        "bridge": bridge,
        "economic_information_used": False,
        "legacy_information_used": False,
        "protected_evidence_used": False,
    }


def format_preflight_matrix(result: Mapping[str, Any]) -> list[str]:
    rows = list(result["matrix"])
    lines = []
    passed = int(result["pass_count"])
    total = int(result["required_count"])
    if passed == total:
        lines.append(f"BROKER PRODUCT PREFLIGHT: {passed}/{total} PASS")
    else:
        lines.append(f"BROKER PRODUCT PREFLIGHT: {passed}/{total} PASS — CAPTURE NOT STARTED")
    headers = (
        "CANONICAL", "BROKER SYMBOL", "SYMBOL ID", "PRODUCT FAMILY", "CATEGORY",
        "ASSET CLASS", "ENABLED", "TRADING MODE", "MAPPING POLICY", "MAPPING EVIDENCE", "STATUS",
    )
    lines.append(" | ".join(headers))
    for row in rows:
        lines.append(" | ".join(str(row.get(key.lower().replace(" ", "_")) if row.get(key.lower().replace(" ", "_")) is not None else "-") for key in headers))
    return lines


def build_current_catalog_artifact(
    *,
    account_environment: str,
    broker: str,
    account_fingerprint_sha256: str | None,
    assets: Sequence[Mapping[str, Any]],
    asset_classes: Sequence[Mapping[str, Any]],
    symbol_categories: Sequence[Mapping[str, Any]],
    light_symbols: Sequence[Mapping[str, Any]],
    archived_symbols: Sequence[Mapping[str, Any]],
    full_by_id: Mapping[int, Mapping[str, Any]],
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    relevant_ids: set[int] = set()
    for item in preflight["bridge"].values():
        selected = item.get("selected_current_product")
        if selected:
            relevant_ids.add(_int(selected.get("symbol_id")))
        for ex in item.get("excluded_materially_different_products", []):
            relevant_ids.add(_int(ex.get("symbol_id")))

    relevant_current = []
    for light in light_symbols:
        sid = _int(_field(light, "symbolId", "symbol_id"))
        if sid in relevant_ids:
            relevant_current.append(dict(light))

    return {
        "schema": "mxm.greenfield.v2.broker-product-catalog-current.v1",
        "capture_timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "account_environment": account_environment,
        "broker": broker,
        "account_fingerprint_sha256": account_fingerprint_sha256,
        "assets": list(assets),
        "asset_classes": list(asset_classes),
        "symbol_categories": list(symbol_categories),
        "relevant_current_symbols": relevant_current,
        "relevant_archived_symbol_records": list(archived_symbols),
        "full_metadata_for_relevant_current_products": {
            str(sid): dict(full_by_id[sid]) for sid in sorted(relevant_ids) if sid in full_by_id
        },
        "current_product_bridge": preflight["bridge"],
        "preflight_matrix": preflight["matrix"],
        "preflight_pass_count": preflight["pass_count"],
        "preflight_required_count": preflight["required_count"],
        "all_current_mappings_pass": preflight["all_current_mappings_pass"],
        "current_schedule_not_historical_schedule": True,
        "current_structural_metadata_not_historical_metadata": True,
        "economic_information_used": False,
        "legacy_information_used": False,
        "protected_evidence_used": False,
    }


def reject_economic_mapping_inputs(value: Mapping[str, Any]) -> None:
    lowered = {str(k).lower() for k in value}
    found = sorted(lowered & ECONOMIC_FIELD_NAMES)
    if found:
        raise ValueError("economic/legacy mapping inputs forbidden: " + ",".join(found))
