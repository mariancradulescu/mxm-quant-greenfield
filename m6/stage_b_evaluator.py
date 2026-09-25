"""Frozen Stage-B EUR200 causal capital-realization primitives.

Stage B is the realizability layer for Stage-A survivors V2-C006/V2-C012.
It does not choose candidate parameters, signals, thresholds, costs, or a sizing optimizer.

The sizing law is intentionally simple and outcome-independent:
- start with EUR 200;
- use exactly the current broker minimum executable volume, frozen here as 10 cents
  (0.10 units under the cTrader Open API cents convention);
- no compounding, no resizing after gains/losses, no pyramiding and no rescue;
- admission additionally requires a separately frozen applicable margin authority.

Current broker-native expected-margin snapshots are diagnostic only and cannot satisfy the
historical causal margin gate by themselves.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

STARTING_CAPITAL_EUR = Decimal("200")
VOLUME_CENTS_PER_UNIT = Decimal("100")
FIXED_VOLUME_CENTS = {"V2-C006": 10, "V2-C012": 10}
CANDIDATE_SPEC_HASHES = {
    "V2-C006": "75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49",
    "V2-C012": "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845",
}
STAGE_B_EVALUATOR_VERSION = "MXM_STAGE_B_TIER1_EUR200_V1"


class StageBIntegrityError(ValueError):
    pass


class StageBMarginEvidenceUnavailable(StageBIntegrityError):
    pass


def _sign(direction: str) -> Decimal:
    if direction in {"LONG", "LONG_NAS100"}:
        return Decimal("1")
    if direction in {"SHORT", "SHORT_NAS100"}:
        return Decimal("-1")
    raise StageBIntegrityError(f"unsupported direction: {direction}")


def fixed_quantity(candidate_id: str) -> Decimal:
    if candidate_id not in FIXED_VOLUME_CENTS:
        raise StageBIntegrityError("candidate outside frozen Stage-B scope")
    return Decimal(FIXED_VOLUME_CENTS[candidate_id]) / VOLUME_CENTS_PER_UNIT


def validate_margin_authority(authority: Mapping[str, Any]) -> dict[str, Decimal]:
    """Validate a separately frozen conservative historical margin bound.

    The Stage-B evaluator deliberately does not infer historical margin from current leverage
    or current expected-margin snapshots.  The authority must bind a conservative applicable
    EUR margin amount for the frozen minimum volume of each candidate.
    """
    if authority.get("schema") != "mxm.greenfield.v2.m6-stage-b-margin-authority.v1":
        raise StageBMarginEvidenceUnavailable("missing/invalid Stage-B margin authority schema")
    if authority.get("status") != "FROZEN_CONSERVATIVE_HISTORICAL_MARGIN_BOUND":
        raise StageBMarginEvidenceUnavailable("historical Stage-B margin evidence is not sufficient")
    if authority.get("volume_cents") != FIXED_VOLUME_CENTS:
        raise StageBMarginEvidenceUnavailable("margin authority volume binding mismatch")
    if authority.get("candidate_spec_hashes") != CANDIDATE_SPEC_HASHES:
        raise StageBMarginEvidenceUnavailable("margin authority candidate binding mismatch")
    if authority.get("post_outcome_tuning") is not False:
        raise StageBMarginEvidenceUnavailable("margin authority may not be tuned to outcomes")
    bounds = authority.get("max_required_margin_eur")
    if not isinstance(bounds, Mapping):
        raise StageBMarginEvidenceUnavailable("margin authority missing conservative EUR bounds")
    out: dict[str, Decimal] = {}
    for cid in FIXED_VOLUME_CENTS:
        if cid not in bounds:
            raise StageBMarginEvidenceUnavailable(f"margin bound missing for {cid}")
        value = Decimal(str(bounds[cid]))
        if value <= 0:
            raise StageBMarginEvidenceUnavailable("margin bound must be positive")
        out[cid] = value
    return out


def settle_min_volume_trade(prepared_trade: Any) -> dict[str, Any]:
    intent = prepared_trade.intent
    cid = str(intent.candidate_id)
    if intent.spec_hash != CANDIDATE_SPEC_HASHES.get(cid):
        raise StageBIntegrityError("prepared trade candidate/spec binding mismatch")
    quantity = fixed_quantity(cid)
    entry_price = Decimal(str(intent.entry_price))
    exit_price = Decimal(str(intent.exit_price))
    entry_rate = Decimal(prepared_trade.entry_usd_to_eur_rate)
    exit_rate = Decimal(prepared_trade.exit_usd_to_eur_rate)
    if min(entry_price, exit_price, entry_rate, exit_rate) <= 0:
        raise StageBIntegrityError("prices and conversion rates must be positive")
    entry_points = prepared_trade.entry_cost_evidence.transaction_cost_proxy_points
    exit_points = prepared_trade.exit_cost_evidence.transaction_cost_proxy_points
    if entry_points is None or exit_points is None:
        raise StageBIntegrityError("transaction-local cost evidence missing")
    gross_eur = _sign(intent.direction) * (exit_price - entry_price) * quantity * exit_rate
    entry_cost_eur = Decimal(entry_points) * quantity * entry_rate
    exit_cost_eur = Decimal(exit_points) * quantity * exit_rate
    cost_eur = entry_cost_eur + exit_cost_eur
    net_eur = gross_eur - cost_eur
    entry_notional_eur = abs(entry_price * quantity * entry_rate)
    exit_notional_eur = abs(exit_price * quantity * exit_rate)
    hold_minutes = int((intent.exit_utc - intent.entry_utc).total_seconds() // 60)
    if hold_minutes <= 0:
        raise StageBIntegrityError("non-positive hold duration")
    return {
        "candidate_id": cid,
        "spec_hash": intent.spec_hash,
        "direction": intent.direction,
        "entry_utc": intent.entry_utc,
        "exit_utc": intent.exit_utc,
        "volume_cents": FIXED_VOLUME_CENTS[cid],
        "quantity_units": quantity,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "entry_usd_to_eur_rate": entry_rate,
        "exit_usd_to_eur_rate": exit_rate,
        "gross_pnl_eur": gross_eur,
        "transaction_cost_eur": cost_eur,
        "coarse_net_pnl_eur": net_eur,
        "entry_notional_eur": entry_notional_eur,
        "exit_notional_eur": exit_notional_eur,
        "turnover_eur": entry_notional_eur + exit_notional_eur,
        "hold_minutes": hold_minutes,
    }


@dataclass(frozen=True)
class CapitalRealization:
    candidate_id: str
    starting_capital_eur: Decimal
    final_equity_eur: Decimal
    executed_trades: int
    margin_blocked_trades: int
    path: tuple[dict[str, Any], ...]


def realize_continuous_capital(
    candidate: Any,
    *,
    margin_authority: Mapping[str, Any],
) -> CapitalRealization:
    if candidate.candidate_id not in CANDIDATE_SPEC_HASHES:
        raise StageBIntegrityError("candidate outside frozen Stage-B scope")
    if candidate.spec_hash != CANDIDATE_SPEC_HASHES[candidate.candidate_id]:
        raise StageBIntegrityError("candidate spec hash mismatch")
    if candidate.cost_state != "CONSERVATIVE_BOUND":
        raise StageBIntegrityError("Stage-B requires resolved frozen Discovery cost contexts")
    margin_bounds = validate_margin_authority(margin_authority)
    margin_required = margin_bounds[candidate.candidate_id]
    equity = STARTING_CAPITAL_EUR
    executed = 0
    blocked = 0
    path: list[dict[str, Any]] = [{
        "event": "START",
        "equity_eur": float(equity),
    }]
    last_exit: datetime | None = None
    for prepared in candidate.trades:
        trade = settle_min_volume_trade(prepared)
        entry = trade["entry_utc"].astimezone(timezone.utc)
        exit_ = trade["exit_utc"].astimezone(timezone.utc)
        if last_exit is not None and entry < last_exit:
            raise StageBIntegrityError("frozen candidate admission policy violated by overlap")
        if equity < margin_required:
            blocked += 1
            path.append({
                "event": "MARGIN_BLOCK",
                "entry_utc": entry.isoformat().replace("+00:00", "Z"),
                "required_margin_eur": float(margin_required),
                "equity_eur": float(equity),
            })
            continue
        equity += Decimal(trade["coarse_net_pnl_eur"])
        executed += 1
        last_exit = exit_
        path.append({
            "event": "TRADE_CLOSED",
            "entry_utc": entry.isoformat().replace("+00:00", "Z"),
            "exit_utc": exit_.isoformat().replace("+00:00", "Z"),
            "volume_cents": trade["volume_cents"],
            "net_pnl_eur": float(Decimal(trade["coarse_net_pnl_eur"])),
            "equity_eur": float(equity),
        })
    return CapitalRealization(
        candidate_id=candidate.candidate_id,
        starting_capital_eur=STARTING_CAPITAL_EUR,
        final_equity_eur=equity,
        executed_trades=executed,
        margin_blocked_trades=blocked,
        path=tuple(path),
    )
