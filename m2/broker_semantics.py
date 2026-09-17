"""Central broker-semantics registry for M2.

Authority: TRUTH_CAPSULE_V1.json only.  M2 does not resolve future real-market
execution unknowns.  Synthetic fixtures supply explicit mathematical inputs
without promoting those inputs to broker truth.
"""

VERIFIED = "VERIFIED"
CONSERVATIVE_BOUND = "CONSERVATIVE_BOUND"
UNRESOLVED = "UNRESOLVED"
_ALLOWED = {VERIFIED, CONSERVATIVE_BOUND, UNRESOLVED}

BROKER_SEMANTICS = {
    "account_environment": {
        "state": VERIFIED,
        "value": "Pepperstone - Europe LIVE",
    },
    "account_type": {
        "state": VERIFIED,
        "value": "HEDGED",
    },
    "account_leverage_observed": {
        "state": VERIFIED,
        "value": "1:30",
        "limitation": "Observed account leverage; symbol dynamic leverage is not substituted for effective account leverage.",
    },
    "total_margin_calculation_type": {
        "state": VERIFIED,
        "value": "MAX",
    },
    "swap_free": {
        "state": VERIFIED,
        "value": False,
    },
    "live_research_permission": {
        "state": VERIFIED,
        "value": "SCOPE_VIEW_ONLY_NO_ORDERS_NO_ACCOUNT_MUTATION",
    },
    "margin_feasibility_authority": {
        "state": VERIFIED,
        "value": "ProtoOAExpectedMarginReq/Res at relevant executable volume plus current price/conversion/cost truth",
    },
    "historical_spread": {
        "state": UNRESOLVED,
        "value": None,
    },
    "historical_commission": {
        "state": UNRESOLVED,
        "value": None,
    },
    "historical_swap_schedule_and_rate": {
        "state": UNRESOLVED,
        "value": None,
    },
    "historical_slippage_delay_and_gaps": {
        "state": UNRESOLVED,
        "value": None,
    },
    "symbol_volume_min_step_max": {
        "state": UNRESOLVED,
        "value": None,
    },
    "symbol_currency_conversion": {
        "state": UNRESOLVED,
        "value": None,
    },
    "symbol_sessions_and_holidays": {
        "state": UNRESOLVED,
        "value": None,
    },
    "symbol_level_eur200_feasibility": {
        "state": UNRESOLVED,
        "value": None,
    },
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
