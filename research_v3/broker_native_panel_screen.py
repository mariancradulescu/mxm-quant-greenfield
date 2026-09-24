"""Deterministic non-economic breadth screen for the accepted broker universe.

The screen uses only the accepted account-native feasibility index. It does not
read market observations, infer alpha, or create an economic identity.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "MXM_BROKER_NATIVE_PANEL_SCREEN_V1"
DEFAULT_PANEL_SIZE = 8

CONSUMED_SYMBOLS = frozenset({
    "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "US500", "US2000",
    "SpotCrude", "SpotBrent", "ETHUSD", "Copper",
    "USTN2YR-F", "TLT.US", "NVDA.US-24", "VIX", "HSTECH", "ADAUSD",
    "Gasoline", "EURUSD", "USDCAD", "MXNJPY", "IWM.US", "DOTUSD",
})


class PanelScreenError(ValueError):
    """Raised when the accepted universe cannot support a fail-closed screen."""


def _bucket(symbol: str) -> str:
    """Classify only by stable broker-name syntax; never treat this as authority."""
    if symbol.endswith("USD") and len(symbol) > 6:
        return "CRYPTO_OR_SPOT"
    if len(symbol) == 6 and symbol.isalpha():
        return "FX_OR_CROSS"
    if symbol.endswith((".US", ".US-24", ".GB", ".DE", ".AU", ".HK", ".FR", ".CH")):
        return "EQUITY_OR_ETF"
    return "OTHER_BROKER_PRODUCT"


def load_feasible_products(path: str | Path) -> dict[str, tuple[int, str, bool]]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    products = document.get("products")
    if not isinstance(products, Mapping):
        raise PanelScreenError("accepted feasibility index has no products mapping")
    result: dict[str, tuple[int, str, bool]] = {}
    for symbol, raw in products.items():
        if not isinstance(raw, list) or len(raw) < 3:
            raise PanelScreenError(f"malformed feasibility row: {symbol}")
        result[str(symbol)] = (int(raw[0]), str(raw[1]), bool(raw[2]))
    return result


def select_panel(
    products: Mapping[str, tuple[int, str, bool]],
    *,
    excluded_symbols: Iterable[str] = CONSUMED_SYMBOLS,
    panel_size: int = DEFAULT_PANEL_SIZE,
) -> dict[str, Any]:
    """Select a fixed, disjoint, feasibility-only diversity panel.

    The first pass takes one lexicographically smallest product from each
    broker-name bucket. Remaining slots are filled lexicographically. This
    makes the result reproducible without using market outcomes or hidden
    parameters, while callers can audit the exclusion set and source hash.
    """
    if panel_size < 1:
        raise PanelScreenError("panel_size must be positive")
    excluded = {str(symbol) for symbol in excluded_symbols}
    eligible = {
        symbol: row for symbol, row in products.items()
        if symbol not in excluded and row[1] == "BOTH_FEASIBLE" and not row[2]
    }
    if len(eligible) < panel_size:
        raise PanelScreenError("accepted index has fewer eligible products than panel size")

    buckets: dict[str, list[str]] = {}
    for symbol in sorted(eligible):
        buckets.setdefault(_bucket(symbol), []).append(symbol)
    selected: list[str] = []
    for bucket in sorted(buckets):
        if len(selected) == panel_size:
            break
        selected.append(buckets[bucket][0])
    for symbol in sorted(eligible):
        if len(selected) == panel_size:
            break
        if symbol not in selected:
            selected.append(symbol)

    return {
        "schema": "mxm.greenfield.broker-native-non-economic-panel-screen.v1",
        "status": "SCREENED_NON_ECONOMIC_FEASIBILITY_ONLY",
        "implementation": VERSION,
        "source": {
            "universe": "accepted_account_native_feasibility_index",
            "minimum_initial_equity_eur": 200,
            "resolution": "M5",
        },
        "policy": {
            "both_direction_feasible_required": True,
            "test_products_excluded": True,
            "consumed_identities_excluded": True,
            "market_data_read": False,
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
        },
        "excluded_symbol_count": len(excluded),
        "selected_symbols": [
            {"broker_symbol": symbol, "symbol_id": eligible[symbol][0], "bucket": _bucket(symbol)}
            for symbol in selected
        ],
        "eligible_count": len(eligible),
    }
