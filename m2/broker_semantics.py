"""Central broker-semantics registry for M2/M2.1.

Authority: TRUTH_CAPSULE_V1.json only. M2.1 reconciles only reusable execution
semantics demonstrated by the frozen legacy evaluator-integrity audit. It does
not promote historical cost paths, rollover timing, slippage, symbol-specific
volume constraints, or EUR200 feasibility to verified broker truth.
"""

VERIFIED = "VERIFIED"
CONSERVATIVE_BOUND = "CONSERVATIVE_BOUND"
UNRESOLVED = "UNRESOLVED"
_ALLOWED = {VERIFIED, CONSERVATIVE_BOUND, UNRESOLVED}

BROKER_SEMANTICS = {
    "account_environment": {"state": VERIFIED, "value": "Pepperstone - Europe LIVE"},
    "account_type": {"state": VERIFIED, "value": "HEDGED"},
    "account_leverage_observed": {
        "state": VERIFIED,
        "value": "1:30",
        "limitation": "Observed account leverage; symbol dynamic leverage is not substituted for effective account leverage.",
    },
    "total_margin_calculation_type": {"state": VERIFIED, "value": "MAX"},
    "swap_free": {"state": VERIFIED, "value": False},
    "live_research_permission": {"state": VERIFIED, "value": "SCOPE_VIEW_ONLY_NO_ORDERS_NO_ACCOUNT_MUTATION"},
    "margin_feasibility_authority": {
        "state": VERIFIED,
        "value": "ProtoOAExpectedMarginReq/Res at relevant executable volume plus current price/conversion/cost truth",
    },
    "openapi_min_volume_protocol_conversion": {
        "state": VERIFIED,
        "value": "actual_units = raw_minVolume / 100",
        "limitation": "Only where the audited cTrader Open API volume field uses protocol cents semantics; this does not verify any symbol's current or historical min/step/max values.",
    },
    "actual_units_to_lots_conversion": {
        "state": VERIFIED,
        "value": "lots = actual_units / lotSize",
        "limitation": "Dimensional conversion only; lotSize must be the applicable broker metadata value for the symbol/context being evaluated.",
    },
    "precise_trading_commission_rate_scaling": {
        "state": VERIFIED,
        "value": "audited_usd_per_lot_one_way_rate = preciseTradingCommissionRate / 1e8",
        "limitation": "Verified only for the audited applicable USD-per-lot preciseTradingCommissionRate interpretation; do not generalize to other commission types or historical symbol/time rates.",
    },
    "commission_entry_exit_treatment": {
        "state": VERIFIED,
        "value": "applicable one-way commission is charged on entry and again on exit",
        "limitation": "Treatment semantics only; exact historical commission path/rate by symbol and time remains unresolved.",
    },
    "swap_calculation_formulas": {
        "state": VERIFIED,
        "value": {"PIPS": "AUDITED_FORMULA_SEMANTICS_VERIFIED", "PERCENTAGE": "AUDITED_FORMULA_SEMANTICS_VERIFIED"},
        "limitation": "Formula-type semantics only. Exact historical swap timing, charge schedule, rates, triple-weekend behavior, and exact same-timestamp rollover ordering remain unresolved.",
    },
    "historical_spread": {"state": UNRESOLVED, "value": None},
    "historical_commission": {"state": UNRESOLVED, "value": None},
    "historical_swap_schedule_and_rate": {"state": UNRESOLVED, "value": None},
    "historical_slippage_delay_and_gaps": {"state": UNRESOLVED, "value": None},
    "symbol_volume_min_step_max": {"state": UNRESOLVED, "value": None},
    "symbol_currency_conversion": {"state": UNRESOLVED, "value": None},
    "symbol_sessions_and_holidays": {"state": UNRESOLVED, "value": None},
    "symbol_level_eur200_feasibility": {"state": UNRESOLVED, "value": None},
}


def validate_registry():
    invalid = {k: v.get("state") for k, v in BROKER_SEMANTICS.items() if v.get("state") not in _ALLOWED}
    if invalid:
        raise ValueError(f"Invalid broker semantic states: {invalid}")
    return True


def state_counts():
    validate_registry()
    return {
        VERIFIED: sum(v["state"] == VERIFIED for v in BROKER_SEMANTICS.values()),
        CONSERVATIVE_BOUND: sum(v["state"] == CONSERVATIVE_BOUND for v in BROKER_SEMANTICS.values()),
        UNRESOLVED: sum(v["state"] == UNRESOLVED for v in BROKER_SEMANTICS.values()),
    }
