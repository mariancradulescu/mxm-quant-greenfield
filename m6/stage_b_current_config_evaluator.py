"""Stage-B EUR200 capital realization under the verified CURRENT Pepperstone configuration.

This is a scenario/deployment-feasibility evaluator, not a historical-margin authority.

It reuses the frozen Stage-B settlement/cost path, fixed 0.1-unit sizing, candidate identities,
signals, and transaction-local cost evidence. The only distinct law is margin admission:
the exact broker-native current ExpectedMargin captured for the frozen symbol/side/volume is
applied to every DEVELOPMENT entry in this explicitly labeled current-configuration scenario.

Historical point-in-time margin remains unresolved and this module must never be cited as proof
that Pepperstone applied these same margin requirements in 2022-2026.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from .stage_b_evaluator import (
    CANDIDATE_SPEC_HASHES,
    FIXED_VOLUME_CENTS,
    STARTING_CAPITAL_EUR,
    CapitalRealization,
    StageBIntegrityError,
    settle_min_volume_trade,
)

CURRENT_CONFIG_AUTHORITY_SCHEMA = "mxm.greenfield.v2.m6-stage-b-current-broker-configuration-authority.v1"
CURRENT_CONFIG_AUTHORITY_STATUS = "VERIFIED_CURRENT_BROKER_CONFIGURATION_SCENARIO"
CURRENT_CONFIG_EVALUATOR_VERSION = "MXM_STAGE_B_CURRENT_CONFIG_EUR200_V1"
EXPECTED_MARGIN_SHA256 = "08a5643687d4be0fb4f97422e13104c5b9eb08357932bad2463388c368140c9d"
SYMBOL_METADATA_SHA256 = "6427658afc8e3c7e710e843f4b1b2421dca4da9984f427dd966888f15314a583"
EXPECTED_CURRENT_MARGIN_MINOR = {
    "V2-C006": {
        "symbol": "US500",
        "symbol_id": 127,
        "volume_cents": 10,
        "buy_margin_minor": 3338,
        "sell_margin_minor": 3338,
        "money_digits": 2,
    },
    "V2-C012": {
        "symbol": "NAS100",
        "symbol_id": 126,
        "volume_cents": 10,
        "buy_margin_minor": 12904,
        "sell_margin_minor": 12903,
        "money_digits": 2,
    },
}


class CurrentConfigMarginAuthorityError(StageBIntegrityError):
    pass


def _money_value(minor: int, digits: int) -> Decimal:
    return Decimal(minor) / (Decimal(10) ** Decimal(digits))


def validate_current_configuration_authority(
    authority: Mapping[str, Any],
) -> dict[str, dict[str, Decimal]]:
    if authority.get("schema") != CURRENT_CONFIG_AUTHORITY_SCHEMA:
        raise CurrentConfigMarginAuthorityError("invalid current-configuration authority schema")
    if authority.get("status") != CURRENT_CONFIG_AUTHORITY_STATUS:
        raise CurrentConfigMarginAuthorityError("current broker configuration is not verified")
    if authority.get("candidate_spec_hashes") != CANDIDATE_SPEC_HASHES:
        raise CurrentConfigMarginAuthorityError("candidate/spec binding mismatch")
    if authority.get("volume_cents") != FIXED_VOLUME_CENTS:
        raise CurrentConfigMarginAuthorityError("frozen volume binding mismatch")
    if authority.get("post_outcome_tuning") is not False:
        raise CurrentConfigMarginAuthorityError("post-outcome tuning is forbidden")
    if authority.get("protected_evidence_opened") is not False:
        raise CurrentConfigMarginAuthorityError("protected evidence must remain unopened")

    source = authority.get("source_evidence", {})
    if source.get("expected_margin_sha256") != EXPECTED_MARGIN_SHA256:
        raise CurrentConfigMarginAuthorityError("ExpectedMargin source hash mismatch")
    if source.get("symbol_metadata_sha256") != SYMBOL_METADATA_SHA256:
        raise CurrentConfigMarginAuthorityError("symbol metadata source hash mismatch")

    history = authority.get("historical_boundary", {})
    if history.get("historical_invariance_verified") is not False:
        raise CurrentConfigMarginAuthorityError("authority must not claim historical invariance")
    if history.get("historical_point_in_time_margin_state") != "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND":
        raise CurrentConfigMarginAuthorityError("historical unresolved state was not preserved")
    if history.get("current_configuration_is_historical_fact") is not False:
        raise CurrentConfigMarginAuthorityError("current scenario must not become historical fact")

    chronology = authority.get("post_stage_a_chronology", {})
    if chronology.get("stage_a_outcomes_already_known") is not True:
        raise CurrentConfigMarginAuthorityError("post-Stage-A chronology must be explicit")
    if chronology.get("current_config_stage_b_outcomes_opened_at_freeze") != 0:
        raise CurrentConfigMarginAuthorityError("authority must precede current-config outcomes")

    nodes = authority.get("current_expected_margin")
    if not isinstance(nodes, Mapping):
        raise CurrentConfigMarginAuthorityError("missing current ExpectedMargin bindings")

    out: dict[str, dict[str, Decimal]] = {}
    for cid, expected in EXPECTED_CURRENT_MARGIN_MINOR.items():
        node = nodes.get(cid)
        if not isinstance(node, Mapping):
            raise CurrentConfigMarginAuthorityError(f"missing current margin node for {cid}")
        for key, value in expected.items():
            if node.get(key) != value:
                raise CurrentConfigMarginAuthorityError(f"current ExpectedMargin drift for {cid}.{key}")
        digits = int(node["money_digits"])
        out[cid] = {
            "BUY": _money_value(int(node["buy_margin_minor"]), digits),
            "SELL": _money_value(int(node["sell_margin_minor"]), digits),
        }
    return out


def current_margin_for_direction(
    candidate_id: str,
    direction: str,
    authority: Mapping[str, Any],
) -> tuple[str, Decimal]:
    margins = validate_current_configuration_authority(authority)
    if candidate_id not in margins:
        raise CurrentConfigMarginAuthorityError("candidate outside current-config scope")
    if direction in {"LONG", "LONG_NAS100"}:
        return "BUY", margins[candidate_id]["BUY"]
    if direction in {"SHORT", "SHORT_NAS100"}:
        return "SELL", margins[candidate_id]["SELL"]
    raise StageBIntegrityError(f"unsupported direction: {direction}")


def realize_current_configuration_capital(
    candidate: Any,
    *,
    current_margin_authority: Mapping[str, Any],
) -> CapitalRealization:
    """Replay frozen DEVELOPMENT under verified CURRENT broker margin only."""
    if candidate.candidate_id not in CANDIDATE_SPEC_HASHES:
        raise StageBIntegrityError("candidate outside frozen Stage-B scope")
    if candidate.spec_hash != CANDIDATE_SPEC_HASHES[candidate.candidate_id]:
        raise StageBIntegrityError("candidate spec hash mismatch")
    if candidate.cost_state != "CONSERVATIVE_BOUND":
        raise StageBIntegrityError("Stage-B requires resolved frozen Discovery cost contexts")

    validate_current_configuration_authority(current_margin_authority)
    equity = STARTING_CAPITAL_EUR
    executed = 0
    blocked = 0
    path: list[dict[str, Any]] = [{
        "event": "START",
        "equity_eur": float(equity),
        "scenario": "STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
        "historical_margin_claim": False,
    }]
    last_exit = None
    for prepared in candidate.trades:
        trade = settle_min_volume_trade(prepared)
        entry = trade["entry_utc"]
        exit_ = trade["exit_utc"]
        if last_exit is not None and entry < last_exit:
            raise StageBIntegrityError("frozen candidate admission policy violated by overlap")

        margin_side, margin_required = current_margin_for_direction(
            candidate.candidate_id,
            trade["direction"],
            current_margin_authority,
        )
        if equity < margin_required:
            blocked += 1
            path.append({
                "event": "MARGIN_BLOCK",
                "entry_utc": entry.isoformat().replace("+00:00", "Z"),
                "direction": trade["direction"],
                "margin_side": margin_side,
                "required_margin_eur": float(margin_required),
                "equity_eur": float(equity),
                "scenario": "STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
                "historical_margin_claim": False,
            })
            continue

        equity += Decimal(trade["coarse_net_pnl_eur"])
        executed += 1
        last_exit = exit_
        path.append({
            "event": "TRADE_CLOSED",
            "entry_utc": entry.isoformat().replace("+00:00", "Z"),
            "exit_utc": exit_.isoformat().replace("+00:00", "Z"),
            "direction": trade["direction"],
            "margin_side": margin_side,
            "required_margin_eur": float(margin_required),
            "volume_cents": trade["volume_cents"],
            "net_pnl_eur": float(Decimal(trade["coarse_net_pnl_eur"])),
            "equity_eur": float(equity),
            "scenario": "STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
            "historical_margin_claim": False,
        })

    return CapitalRealization(
        candidate_id=candidate.candidate_id,
        starting_capital_eur=STARTING_CAPITAL_EUR,
        final_equity_eur=equity,
        executed_trades=executed,
        margin_blocked_trades=blocked,
        path=tuple(path),
    )
