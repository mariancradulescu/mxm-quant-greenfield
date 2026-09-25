"""Deterministic complete Stage-A evaluator for the first Tier-1 Discovery screen.

This module is frozen before the first V2 economic outcome.  It does not choose signals,
cost rows, parameters, thresholds, or candidate identities.  It consumes a prepared
candidate whose frozen replay intents and transaction-local cost contexts have already
passed fail-closed applicability checks.

Stage-A is fixed-unit analytic screening, not EUR200 capital realization.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from typing import Any, Mapping, Sequence

from .session_replay import NY, NasdaqCashCalendar

EVALUATOR_VERSION = "MXM_STAGE_A_TIER1_EVALUATOR_V1"
DEVELOPMENT_START = date(2022, 1, 3)
DEVELOPMENT_END = date(2026, 9, 16)
ENTRY_NOTIONAL_EUR = Decimal("1000")

CANDIDATE_BINDINGS = {
    "V2-C006": {
        "spec_hash": "75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49",
        "traded_symbol": "US500",
        "cost_identity": "US500_M15_TRANSACTION_LOCAL_SAME_ROW_DISCOVERY_COST",
        "cost_sha256": "601eedcb147021fff54f4d3bd2a43d831c455a821ddafa01a0036afe5c5485d6",
    },
    "V2-C012": {
        "spec_hash": "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845",
        "traded_symbol": "NAS100",
        "cost_identity": "NAS100_C012_TRANSACTION_LOCAL_SAME_ROW_DISCOVERY_COST",
        "cost_sha256": "dd4f6be917773fc580d4725d7c30ef4aabd5ec4ce19a30fdced8c5a85f4bd999",
    },
}
DATA_EVIDENCE_IDENTITY = "PRIMARY_WAVE_02_RECONCILED_US500_NAS100_EURUSD_M15_CAPTURE"
DATA_EVIDENCE_SHA256 = "88c68f1724eba71ef58fe02a929c935dc1cbf4be432897db599be7b37fd4ae72"


class StageAEvaluatorError(ValueError):
    pass


def _sign(direction: str) -> Decimal:
    if direction in {"LONG", "LONG_NAS100"}:
        return Decimal("1")
    if direction in {"SHORT", "SHORT_NAS100"}:
        return Decimal("-1")
    raise StageAEvaluatorError(f"unsupported direction: {direction}")


def _float(value: Decimal | int | float) -> float:
    return float(value)


def _iso_week_key(ts: datetime) -> str:
    iso = ts.astimezone(timezone.utc).isocalendar()
    return f"{iso.year:04d}-W{iso.week:02d}"


def _all_iso_weeks(start: date, end: date) -> list[str]:
    cursor = start
    out = []
    seen = set()
    while cursor <= end:
        iso = cursor.isocalendar()
        key = f"{iso.year:04d}-W{iso.week:02d}"
        if key not in seen:
            out.append(key)
            seen.add(key)
        cursor += timedelta(days=1)
    return out


def _reference_cash_session_minutes(
    calendar: NasdaqCashCalendar,
    start: date,
    end: date,
) -> int:
    total = 0
    cursor = start
    while cursor <= end:
        session = calendar.session(cursor)
        if session is not None:
            total += int((session.close_utc - session.open_utc).total_seconds() // 60)
        cursor += timedelta(days=1)
    return total


def _longest_zero_entry_day_streak(
    entry_dates: set[date],
    start: date,
    end: date,
) -> int:
    longest = current = 0
    cursor = start
    while cursor <= end:
        if cursor in entry_dates:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
        cursor += timedelta(days=1)
    return longest


def _contribution_add(bucket: dict[str, dict[str, Decimal | int]], key: str, trade: Mapping[str, Any]) -> None:
    node = bucket.setdefault(
        key,
        {
            "event_count": 0,
            "gross_pnl_eur": Decimal("0"),
            "transaction_cost_eur": Decimal("0"),
            "coarse_net_pnl_eur": Decimal("0"),
        },
    )
    node["event_count"] = int(node["event_count"]) + 1
    for field in ("gross_pnl_eur", "transaction_cost_eur", "coarse_net_pnl_eur"):
        node[field] = Decimal(node[field]) + Decimal(trade[field])


def _contribution_float(bucket: Mapping[str, Mapping[str, Decimal | int]]) -> dict[str, dict[str, float | int]]:
    out = {}
    for key in sorted(bucket):
        node = bucket[key]
        out[key] = {
            "event_count": int(node["event_count"]),
            "gross_pnl_eur": _float(Decimal(node["gross_pnl_eur"])),
            "transaction_cost_eur": _float(Decimal(node["transaction_cost_eur"])),
            "coarse_net_pnl_eur": _float(Decimal(node["coarse_net_pnl_eur"])),
        }
    return out


def settle_prepared_trade(prepared_trade: Any) -> dict[str, Any]:
    intent = prepared_trade.intent
    entry_price = Decimal(str(intent.entry_price))
    exit_price = Decimal(str(intent.exit_price))
    entry_rate = Decimal(prepared_trade.entry_usd_to_eur_rate)
    exit_rate = Decimal(prepared_trade.exit_usd_to_eur_rate)
    if entry_price <= 0 or exit_price <= 0 or entry_rate <= 0 or exit_rate <= 0:
        raise StageAEvaluatorError("prices and conversion rates must be positive")

    entry_points = prepared_trade.entry_cost_evidence.transaction_cost_proxy_points
    exit_points = prepared_trade.exit_cost_evidence.transaction_cost_proxy_points
    if entry_points is None or exit_points is None:
        raise StageAEvaluatorError("supported transaction-local evidence missing proxy points")

    quantity = ENTRY_NOTIONAL_EUR / (entry_price * entry_rate)
    gross_quote = _sign(intent.direction) * (exit_price - entry_price) * quantity
    gross_eur = gross_quote * exit_rate
    entry_cost_eur = Decimal(entry_points) * quantity * entry_rate
    exit_cost_eur = Decimal(exit_points) * quantity * exit_rate
    cost_eur = entry_cost_eur + exit_cost_eur
    net_eur = gross_eur - cost_eur
    # The Stage-A economic unit is exactly EUR 1000 by frozen definition.
    # Do not re-multiply a repeating Decimal quotient and introduce representational drift.
    entry_notional_eur = ENTRY_NOTIONAL_EUR
    exit_notional_eur = abs(exit_price * quantity * exit_rate)
    hold_minutes = int((intent.exit_utc - intent.entry_utc).total_seconds() // 60)
    if hold_minutes <= 0:
        raise StageAEvaluatorError("non-positive hold duration")

    return {
        "candidate_id": intent.candidate_id,
        "spec_hash": intent.spec_hash,
        "direction": intent.direction,
        "entry_utc": intent.entry_utc,
        "exit_utc": intent.exit_utc,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": quantity,
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


def _status(gross: Decimal, net: Decimal) -> str:
    if gross <= 0:
        return "GROSS_EDGE_FAIL"
    if net <= 0:
        return "COARSE_NET_FAIL"
    return "DISCOVERY_SURVIVOR"


def evaluate_prepared_candidate(
    candidate: Any,
    *,
    calendar: NasdaqCashCalendar,
    evaluator_sha256: str,
) -> dict[str, Any]:
    if candidate.candidate_id not in CANDIDATE_BINDINGS:
        raise StageAEvaluatorError("candidate is outside the frozen Tier-1 evaluator scope")
    binding = CANDIDATE_BINDINGS[candidate.candidate_id]
    if candidate.spec_hash != binding["spec_hash"]:
        raise StageAEvaluatorError("candidate spec hash mismatch")
    if candidate.cost_state != "CONSERVATIVE_BOUND":
        raise StageAEvaluatorError("economic evaluation forbidden unless cost applicability is fully resolved")
    if not candidate.trades:
        raise StageAEvaluatorError("Stage-A economic evaluation requires at least one event")
    if len(evaluator_sha256) != 64 or any(c not in "0123456789abcdef" for c in evaluator_sha256):
        raise StageAEvaluatorError("evaluator_sha256 must be lowercase SHA256 hex")

    trades = [settle_prepared_trade(x) for x in candidate.trades]
    gross = sum((Decimal(x["gross_pnl_eur"]) for x in trades), Decimal("0"))
    costs = sum((Decimal(x["transaction_cost_eur"]) for x in trades), Decimal("0"))
    net = sum((Decimal(x["coarse_net_pnl_eur"]) for x in trades), Decimal("0"))
    total_entry_notional = sum((Decimal(x["entry_notional_eur"]) for x in trades), Decimal("0"))
    turnover = sum((Decimal(x["turnover_eur"]) for x in trades), Decimal("0"))
    n = len(trades)

    weekly = {key: 0 for key in _all_iso_weeks(DEVELOPMENT_START, DEVELOPMENT_END)}
    weekdays = {name: 0 for name in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")}
    sessions = Counter()
    entry_dates: set[date] = set()
    hold_minutes = []
    by_symbol: dict[str, dict[str, Decimal | int]] = {}
    by_direction: dict[str, dict[str, Decimal | int]] = {}
    by_year: dict[str, dict[str, Decimal | int]] = {}

    cumulative = Decimal("0")
    peak = Decimal("0")
    max_drawdown = Decimal("0")

    for trade in trades:
        entry = trade["entry_utc"].astimezone(timezone.utc)
        weekly[_iso_week_key(entry)] += 1
        weekdays[("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")[entry.weekday()]] += 1
        local = entry.astimezone(NY)
        sessions[f"ET_{local.hour:02d}:{local.minute:02d}"] += 1
        entry_dates.add(entry.date())
        hold_minutes.append(int(trade["hold_minutes"]))
        _contribution_add(by_symbol, str(binding["traded_symbol"]), trade)
        _contribution_add(by_direction, str(trade["direction"]), trade)
        _contribution_add(by_year, f"{entry.year:04d}", trade)

        cumulative += Decimal(trade["coarse_net_pnl_eur"])
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    reference_minutes = _reference_cash_session_minutes(
        calendar, DEVELOPMENT_START, DEVELOPMENT_END
    )
    total_hold_minutes = sum(hold_minutes)
    exposure = (
        Decimal(total_hold_minutes) / Decimal(reference_minutes)
        if reference_minutes > 0 else Decimal("0")
    )

    holds_sorted = sorted(hold_minutes)
    hold_metric = {
        "min_minutes": float(holds_sorted[0]),
        "median_minutes": float(median(holds_sorted)),
        "mean_minutes": float(sum(holds_sorted) / len(holds_sorted)),
        "max_minutes": float(holds_sorted[-1]),
    }

    metrics = {
        "event_count": n,
        "gross_pnl": _float(gross),
        "coarse_net_pnl": _float(net),
        "gross_return": _float(gross / total_entry_notional),
        "coarse_net_return": _float(net / total_entry_notional),
        "gross_per_event": _float(gross / Decimal(n)),
        "net_per_event": _float(net / Decimal(n)),
        "cost_burden": _float(costs / total_entry_notional),
        "turnover": _float(turnover),
        "weekly_events": weekly,
        "active_weeks": sum(1 for value in weekly.values() if value > 0),
        "longest_inactive_gap": _longest_zero_entry_day_streak(
            entry_dates, DEVELOPMENT_START, DEVELOPMENT_END
        ),
        "weekday_distribution": weekdays,
        "session_distribution": dict(sorted(sessions.items())),
        "hold_duration": hold_metric,
        "exposure": _float(exposure),
        "drawdown": _float(max_drawdown),
        "symbol_contribution": _contribution_float(by_symbol),
        "direction_contribution": _contribution_float(by_direction),
        "subperiod_contribution": _contribution_float(by_year),
        "regime_contribution": {
            "state": "NOT_APPLICABLE",
            "reason": "No prospectively frozen regime taxonomy applies to the first Tier-1 Stage-A screen; no post-outcome regime binning is introduced.",
        },
    }

    return {
        "candidate_id": candidate.candidate_id,
        "spec_hash": candidate.spec_hash,
        "stage": "A",
        "status": _status(gross, net),
        "implementation_validity": {
            "state": "VALID",
            "reason": "Frozen candidate replay and evaluator integrity gates passed.",
        },
        "metrics": metrics,
        "eur200_feasibility": {
            "state": "NOT_EVALUATED",
            "reason": "Stage A is fixed-unit primitive screening; EUR200 continuous causal realization is Stage B only for a Stage-A survivor.",
        },
        "cost_confidence": {
            "state": "CONSERVATIVE_BOUND",
            "reason": "Primary Discovery cost is the frozen transaction-local same-row adverse proxy; Certification execution truth remains unestablished.",
        },
        "data_completeness": {
            "state": "SUFFICIENT",
            "reason": "Hash-bound DEVELOPMENT OHLC/conversion inputs and all required transaction-local cost contexts are available.",
        },
        "provenance": {
            "data_evidence": {
                "identity": DATA_EVIDENCE_IDENTITY,
                "binding": {
                    "type": "DATASET_SHA256",
                    "sha256": DATA_EVIDENCE_SHA256,
                },
            },
            "cost_evidence": {
                "identity": binding["cost_identity"],
                "state": "CONSERVATIVE_BOUND",
                "sha256": binding["cost_sha256"],
            },
            "evaluator": {
                "version": EVALUATOR_VERSION,
                "sha256": evaluator_sha256,
            },
        },
    }
