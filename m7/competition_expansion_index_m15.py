"""Competition Performance Expansion Wave 01: causal M15 index replay and Stage-A screen.

Prospectively frozen identities:
- V2-C013 US500 one-hour sign continuation
- V2-C014 US500 one-hour sign reversal
- V2-C015 US500 first-hour opening-range breakout
- V2-C016 NAS100 relative-return dispersion reversion vs US500 context

This module never reads protected evidence and never mutates accepted M6 Stage-B artifacts.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.schema import validate_result
from m6.causal_conversion import CausalConversionSeries, quote_to_eur_rate
from m6.session_replay import M15, NY, NasdaqCashCalendar, cash_session_observations
from m6.stage_a_evaluator import settle_prepared_trade
from m6.tier1_candidate_replay import ReplayIntent
from m6.transaction_local_cost import (
    TransactionCostEvidence,
    load_c012_transaction_local_index,
    load_us500_transaction_local_index,
)

VERSION = "MXM_COMPETITION_EXPANSION_INDEX_M15_WAVE01_V1"
DEVELOPMENT_START = date(2022, 1, 3)
DEVELOPMENT_END = date(2026, 9, 16)
DATA_BUNDLE_SHA256 = "88c68f1724eba71ef58fe02a929c935dc1cbf4be432897db599be7b37fd4ae72"
US500_SHA256 = "e62aff5634ee2c3b9f3cbea3766a68d7a4a68b64ec9727aaa8cc757e2834fe87"
NAS100_SHA256 = "f92330927b0f41c3f6502951dbe512aa11449184916634c80e8f67f3c217eb7c"
EURUSD_SHA256 = "bce32af6ef251115d0628d746af16849a7ac23d7185a716670b0b22a4f09adde"
US500_COST_SHA256 = "601eedcb147021fff54f4d3bd2a43d831c455a821ddafa01a0036afe5c5485d6"
NAS100_COST_SHA256 = "dd4f6be917773fc580d4725d7c30ef4aabd5ec4ce19a30fdced8c5a85f4bd999"
CANDIDATE_HASHES = {
    "V2-C013": "cd91f3b0008fef672fd5722ed44db23046fb516ad174b60205a55cd0c54cfea1",
    "V2-C014": "7bb7a21f40dd742357f4800f7762314724b73609c34c2de04b10329df2221e6d",
    "V2-C015": "aa067cc4aa807731ec3a0caa9029b574eeae43e068e241790d994d55a1f8ff64",
    "V2-C016": "fdd6286d1a8fdbbe53610af45c91e3f949bb75805b7cc7ab790b997c77458783",
}
RESULT_FILENAMES = {
    cid: f"{cid}_STAGE_A_COMPETITION_EXPANSION_V1.json" for cid in CANDIDATE_HASHES
}


class CompetitionExpansionIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedTrade:
    intent: ReplayIntent
    entry_cost_evidence: TransactionCostEvidence
    exit_cost_evidence: TransactionCostEvidence
    entry_usd_to_eur_rate: Decimal
    exit_usd_to_eur_rate: Decimal


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_file(path: Path | str, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise CompetitionExpansionIntegrityError(
            f"{Path(path)} sha256 mismatch: expected {expected}, got {actual}"
        )


def read_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _utc(value: Any) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise CompetitionExpansionIntegrityError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _et_boundary_allowed(ts: datetime) -> bool:
    local = ts.astimezone(NY)
    minute = local.hour * 60 + local.minute
    return 9 * 60 + 45 <= minute <= 14 * 60 + 45


def _session_bars(rows: Sequence[Mapping[str, Any]], calendar: NasdaqCashCalendar):
    return cash_session_observations(rows, calendar)


def sign_replay_intents(
    rows: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
    *,
    candidate_id: str,
    spec_hash: str,
    reverse: bool,
) -> list[ReplayIntent]:
    observations = _session_bars(rows, calendar)
    out: list[ReplayIntent] = []
    for day in sorted(observations):
        obs = observations[day]
        if not obs.complete_grid:
            continue
        bars = obs.ordered_expected_bars()
        opens = obs.expected_opens
        active_until: datetime | None = None
        for i in range(4, len(bars)):
            decision = opens[i] + M15
            if active_until is not None and decision <= active_until:
                continue
            entry_i = i + 1
            exit_i = entry_i + 3
            if exit_i >= len(bars):
                continue
            entry_utc = opens[entry_i]
            exit_utc = opens[exit_i] + M15
            if not (_et_boundary_allowed(entry_utc) and _et_boundary_allowed(exit_utc)):
                continue
            base = float(bars[i - 4]["close"])
            current = float(bars[i]["close"])
            if base <= 0:
                raise CompetitionExpansionIntegrityError("non-positive lookback close")
            ret4 = current / base - 1.0
            if ret4 == 0:
                continue
            continuation_long = ret4 > 0
            long_signal = (not continuation_long) if reverse else continuation_long
            direction = "LONG" if long_signal else "SHORT"
            out.append(ReplayIntent(
                candidate_id=candidate_id,
                spec_hash=spec_hash,
                direction=direction,
                decision_utc=decision,
                entry_utc=entry_utc,
                entry_price=float(bars[entry_i]["open"]),
                exit_utc=exit_utc,
                exit_price=float(bars[exit_i]["close"]),
                evidence={"return_4": ret4, "session_date": day.isoformat()},
            ))
            active_until = exit_utc
    return out


def opening_range_breakout_intents(
    rows: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
) -> list[ReplayIntent]:
    cid = "V2-C015"
    spec_hash = CANDIDATE_HASHES[cid]
    observations = _session_bars(rows, calendar)
    out: list[ReplayIntent] = []
    for day in sorted(observations):
        obs = observations[day]
        if not obs.complete_grid:
            continue
        bars = obs.ordered_expected_bars()
        opens = obs.expected_opens
        if len(bars) < 9:
            continue
        opening_high = max(float(x["high"]) for x in bars[:4])
        opening_low = min(float(x["low"]) for x in bars[:4])
        for i in range(4, len(bars)):
            close = float(bars[i]["close"])
            if close > opening_high:
                direction = "LONG"
            elif close < opening_low:
                direction = "SHORT"
            else:
                continue
            entry_i = i + 1
            exit_i = entry_i + 3
            if exit_i >= len(bars):
                break
            entry_utc = opens[entry_i]
            exit_utc = opens[exit_i] + M15
            if not (_et_boundary_allowed(entry_utc) and _et_boundary_allowed(exit_utc)):
                break
            out.append(ReplayIntent(
                candidate_id=cid,
                spec_hash=spec_hash,
                direction=direction,
                decision_utc=opens[i] + M15,
                entry_utc=entry_utc,
                entry_price=float(bars[entry_i]["open"]),
                exit_utc=exit_utc,
                exit_price=float(bars[exit_i]["close"]),
                evidence={
                    "opening_range_high": opening_high,
                    "opening_range_low": opening_low,
                    "breakout_close": close,
                    "session_date": day.isoformat(),
                },
            ))
            break
    return out


def relative_value_intents(
    us500_rows: Sequence[Mapping[str, Any]],
    nas100_rows: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
) -> list[ReplayIntent]:
    cid = "V2-C016"
    spec_hash = CANDIDATE_HASHES[cid]
    us_obs = _session_bars(us500_rows, calendar)
    nas_obs = _session_bars(nas100_rows, calendar)
    out: list[ReplayIntent] = []
    for day in sorted(set(us_obs) & set(nas_obs)):
        u = us_obs[day]
        n = nas_obs[day]
        if not u.complete_grid or not n.complete_grid or u.expected_opens != n.expected_opens:
            continue
        ub = u.ordered_expected_bars()
        nb = n.ordered_expected_bars()
        opens = u.expected_opens
        active_until: datetime | None = None
        for i in range(4, len(opens)):
            decision = opens[i] + M15
            if active_until is not None and decision <= active_until:
                continue
            entry_i = i + 1
            exit_i = entry_i + 3
            if exit_i >= len(opens):
                continue
            entry_utc = opens[entry_i]
            exit_utc = opens[exit_i] + M15
            if not (_et_boundary_allowed(entry_utc) and _et_boundary_allowed(exit_utc)):
                continue
            ur0 = float(ub[i - 4]["close"])
            nr0 = float(nb[i - 4]["close"])
            if ur0 <= 0 or nr0 <= 0:
                raise CompetitionExpansionIntegrityError("non-positive cross-index lookback close")
            ur = float(ub[i]["close"]) / ur0 - 1.0
            nr = float(nb[i]["close"]) / nr0 - 1.0
            rel = nr - ur
            if rel == 0:
                continue
            direction = "SHORT_NAS100" if rel > 0 else "LONG_NAS100"
            out.append(ReplayIntent(
                candidate_id=cid,
                spec_hash=spec_hash,
                direction=direction,
                decision_utc=decision,
                entry_utc=entry_utc,
                entry_price=float(nb[entry_i]["open"]),
                exit_utc=exit_utc,
                exit_price=float(nb[exit_i]["close"]),
                evidence={
                    "us500_return_4": ur,
                    "nas100_return_4": nr,
                    "relative_return_4": rel,
                    "session_date": day.isoformat(),
                },
            ))
            active_until = exit_utc
    return out


def _prepare(
    intents: Sequence[ReplayIntent],
    *,
    cost_index: Any,
    eurusd: CausalConversionSeries,
) -> list[PreparedTrade]:
    out: list[PreparedTrade] = []
    for intent in intents:
        entry_cost = cost_index.evidence_for(intent.entry_utc)
        exit_cost = cost_index.evidence_for(intent.exit_utc)
        entry_rate, _ = quote_to_eur_rate("USD", intent.entry_utc, eurusd=eurusd)
        exit_rate, _ = quote_to_eur_rate("USD", intent.exit_utc, eurusd=eurusd)
        out.append(PreparedTrade(
            intent=intent,
            entry_cost_evidence=entry_cost,
            exit_cost_evidence=exit_cost,
            entry_usd_to_eur_rate=Decimal(str(entry_rate)),
            exit_usd_to_eur_rate=Decimal(str(exit_rate)),
        ))
    return out


def _weeks() -> list[str]:
    out: list[str] = []
    cursor = DEVELOPMENT_START
    seen: set[str] = set()
    while cursor <= DEVELOPMENT_END:
        iso = cursor.isocalendar()
        key = f"{iso.year:04d}-W{iso.week:02d}"
        if key not in seen:
            seen.add(key)
            out.append(key)
        cursor += timedelta(days=1)
    return out


def _contrib_add(bucket: dict[str, dict[str, Decimal | int]], key: str, trade: Mapping[str, Any]) -> None:
    node = bucket.setdefault(key, {
        "event_count": 0,
        "gross_pnl_eur": Decimal("0"),
        "transaction_cost_eur": Decimal("0"),
        "coarse_net_pnl_eur": Decimal("0"),
    })
    node["event_count"] = int(node["event_count"]) + 1
    for field in ("gross_pnl_eur", "transaction_cost_eur", "coarse_net_pnl_eur"):
        node[field] = Decimal(node[field]) + Decimal(trade[field])


def _contrib_float(bucket: Mapping[str, Mapping[str, Decimal | int]]) -> dict[str, Any]:
    return {
        key: {
            "event_count": int(node["event_count"]),
            "gross_pnl_eur": float(Decimal(node["gross_pnl_eur"])),
            "transaction_cost_eur": float(Decimal(node["transaction_cost_eur"])),
            "coarse_net_pnl_eur": float(Decimal(node["coarse_net_pnl_eur"])),
        }
        for key, node in sorted(bucket.items())
    }


def _reference_minutes(calendar: NasdaqCashCalendar) -> int:
    total = 0
    cursor = DEVELOPMENT_START
    while cursor <= DEVELOPMENT_END:
        session = calendar.session(cursor)
        if session is not None:
            total += int((session.close_utc - session.open_utc).total_seconds() // 60)
        cursor += timedelta(days=1)
    return total


def _longest_inactive_gap(entry_dates: set[date]) -> int:
    if not entry_dates:
        return (DEVELOPMENT_END - DEVELOPMENT_START).days + 1
    ordered = sorted(entry_dates)
    gaps = [(ordered[0] - DEVELOPMENT_START).days]
    gaps += [(b - a).days - 1 for a, b in zip(ordered, ordered[1:])]
    gaps.append((DEVELOPMENT_END - ordered[-1]).days)
    return max(gaps)


def evaluate(
    candidate_id: str,
    prepared: Sequence[PreparedTrade],
    *,
    traded_symbol: str,
    cost_sha256: str,
    calendar: NasdaqCashCalendar,
    evaluator_sha256: str,
) -> dict[str, Any]:
    if not prepared:
        raise CompetitionExpansionIntegrityError(f"{candidate_id}: no executable events")
    trades = [settle_prepared_trade(x) for x in prepared]
    gross = sum((Decimal(x["gross_pnl_eur"]) for x in trades), Decimal("0"))
    costs = sum((Decimal(x["transaction_cost_eur"]) for x in trades), Decimal("0"))
    net = sum((Decimal(x["coarse_net_pnl_eur"]) for x in trades), Decimal("0"))
    n = len(trades)
    entry_notional = Decimal("1000") * n
    turnover = sum((Decimal(x["turnover_eur"]) for x in trades), Decimal("0"))
    weekly = {key: 0 for key in _weeks()}
    weekdays = {name: 0 for name in ("MON","TUE","WED","THU","FRI","SAT","SUN")}
    sessions = Counter()
    entry_dates: set[date] = set()
    holds: list[int] = []
    by_symbol: dict[str, dict[str, Decimal | int]] = {}
    by_direction: dict[str, dict[str, Decimal | int]] = {}
    by_year: dict[str, dict[str, Decimal | int]] = {}
    cumulative = Decimal("0")
    peak = Decimal("0")
    drawdown = Decimal("0")
    for trade in trades:
        entry = trade["entry_utc"].astimezone(timezone.utc)
        iso = entry.date().isocalendar()
        weekly[f"{iso.year:04d}-W{iso.week:02d}"] += 1
        weekdays[("MON","TUE","WED","THU","FRI","SAT","SUN")[entry.weekday()]] += 1
        local = entry.astimezone(NY)
        sessions[f"ET_{local.hour:02d}:{local.minute:02d}"] += 1
        entry_dates.add(entry.date())
        holds.append(int(trade["hold_minutes"]))
        _contrib_add(by_symbol, traded_symbol, trade)
        _contrib_add(by_direction, str(trade["direction"]), trade)
        _contrib_add(by_year, f"{entry.year:04d}", trade)
        cumulative += Decimal(trade["coarse_net_pnl_eur"])
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    status = "GROSS_EDGE_FAIL" if gross <= 0 else ("COARSE_NET_FAIL" if net <= 0 else "DISCOVERY_SURVIVOR")
    metrics = {
        "event_count": n,
        "gross_pnl": float(gross),
        "coarse_net_pnl": float(net),
        "gross_return": float(gross / entry_notional),
        "coarse_net_return": float(net / entry_notional),
        "gross_per_event": float(gross / n),
        "net_per_event": float(net / n),
        "cost_burden": float(costs / entry_notional),
        "turnover": float(turnover),
        "weekly_events": weekly,
        "active_weeks": sum(v > 0 for v in weekly.values()),
        "longest_inactive_gap": _longest_inactive_gap(entry_dates),
        "weekday_distribution": weekdays,
        "session_distribution": dict(sorted(sessions.items())),
        "hold_duration": {
            "min_minutes": float(min(holds)),
            "median_minutes": float(median(holds)),
            "mean_minutes": float(sum(holds) / len(holds)),
            "max_minutes": float(max(holds)),
        },
        "exposure": float(Decimal(sum(holds)) / Decimal(_reference_minutes(calendar))),
        "drawdown": float(drawdown),
        "symbol_contribution": _contrib_float(by_symbol),
        "direction_contribution": _contrib_float(by_direction),
        "subperiod_contribution": _contrib_float(by_year),
        "regime_contribution": {
            "state": "NOT_APPLICABLE",
            "reason": "No prospectively frozen regime taxonomy applies to Competition Expansion Wave 01 Stage-A.",
        },
    }
    result = {
        "candidate_id": candidate_id,
        "spec_hash": CANDIDATE_HASHES[candidate_id],
        "stage": "A",
        "status": status,
        "implementation_validity": {"state": "VALID", "reason": "Frozen Wave 01 replay and fail-closed evidence gates passed."},
        "metrics": metrics,
        "eur200_feasibility": {"state": "NOT_EVALUATED", "reason": "Stage A is fixed EUR1000 analytic normalization; shared/current EUR200 realization is later Stage B for survivors."},
        "cost_confidence": {"state": "CONSERVATIVE_BOUND", "reason": "Frozen candidate-independent exact-boundary adverse Discovery proxy; no Certification fill-truth claim."},
        "data_completeness": {"state": "SUFFICIENT", "reason": "Hash-bound DEVELOPMENT M15 inputs and every required transaction-local cost row were available."},
        "provenance": {
            "data_evidence": {"identity": "PRIMARY_WAVE_02_RECONCILED_DEVELOPMENT_CAPTURE", "binding": {"type": "DATASET_SHA256", "sha256": DATA_BUNDLE_SHA256}},
            "cost_evidence": {"identity": f"COMPETITION_EXPANSION_{traded_symbol}_M15_TRANSACTION_LOCAL_COST", "state": "CONSERVATIVE_BOUND", "sha256": cost_sha256},
            "evaluator": {"version": VERSION, "sha256": evaluator_sha256},
        },
    }
    validate_result(result)
    result["result_hash"] = compute_result_hash(result)
    validate_result(result)
    return result


def load_specs(repo_root: Path) -> dict[str, dict[str, Any]]:
    out = {}
    for cid, expected in CANDIDATE_HASHES.items():
        path = repo_root / "discovery" / "candidates" / f"{cid}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        verify_spec_hash(value)
        if value.get("spec_hash") != expected:
            raise CompetitionExpansionIntegrityError(f"{cid}: spec hash drift")
        out[cid] = value
    return out


def execute_wave(
    repo_root: Path | str,
    *,
    us500_m15: Path | str,
    nas100_m15: Path | str,
    eurusd_m15: Path | str,
    us500_cost: Path | str,
    nas100_cost: Path | str,
) -> dict[str, dict[str, Any]]:
    root = Path(repo_root)
    load_specs(root)
    _verify_file(us500_m15, US500_SHA256)
    _verify_file(nas100_m15, NAS100_SHA256)
    _verify_file(eurusd_m15, EURUSD_SHA256)
    _verify_file(us500_cost, US500_COST_SHA256)
    _verify_file(nas100_cost, NAS100_COST_SHA256)
    us = read_csv(us500_m15)
    nas = read_csv(nas100_m15)
    eur = read_csv(eurusd_m15)
    calendar = NasdaqCashCalendar.from_artifact(root / "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json")
    eurusd = CausalConversionSeries.from_rows("EURUSD", eur)
    us_cost_index = load_us500_transaction_local_index(us500_cost)
    nas_cost_index = load_c012_transaction_local_index(nas100_cost)
    evaluator_sha = sha256_file(Path(__file__))

    intent_sets = {
        "V2-C013": sign_replay_intents(us, calendar, candidate_id="V2-C013", spec_hash=CANDIDATE_HASHES["V2-C013"], reverse=False),
        "V2-C014": sign_replay_intents(us, calendar, candidate_id="V2-C014", spec_hash=CANDIDATE_HASHES["V2-C014"], reverse=True),
        "V2-C015": opening_range_breakout_intents(us, calendar),
        "V2-C016": relative_value_intents(us, nas, calendar),
    }
    results: dict[str, dict[str, Any]] = {}
    for cid in ("V2-C013","V2-C014","V2-C015","V2-C016"):
        cost_index = nas_cost_index if cid == "V2-C016" else us_cost_index
        traded_symbol = "NAS100" if cid == "V2-C016" else "US500"
        cost_sha = NAS100_COST_SHA256 if cid == "V2-C016" else US500_COST_SHA256
        prepared = _prepare(intent_sets[cid], cost_index=cost_index, eurusd=eurusd)
        results[cid] = evaluate(
            cid, prepared, traded_symbol=traded_symbol, cost_sha256=cost_sha,
            calendar=calendar, evaluator_sha256=evaluator_sha,
        )
    return results


def persist_results(results: Mapping[str, Mapping[str, Any]], output_dir: Path | str) -> tuple[Path, ...]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for cid in ("V2-C013","V2-C014","V2-C015","V2-C016"):
        result = dict(results[cid])
        if result.get("result_hash") != compute_result_hash(result):
            raise CompetitionExpansionIntegrityError(f"{cid}: result hash mismatch")
        path = out / RESULT_FILENAMES[cid]
        if path.exists():
            raise CompetitionExpansionIntegrityError(f"refusing to overwrite {path}")
        path.write_text(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False), encoding="utf-8")
        written.append(path)
    return tuple(written)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--us500-m15", required=True)
    p.add_argument("--nas100-m15", required=True)
    p.add_argument("--eurusd-m15", required=True)
    p.add_argument("--us500-cost", required=True)
    p.add_argument("--nas100-cost", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--execution-head", required=True)
    p.add_argument("--execution-ci-run-id", required=True, type=int)
    args = p.parse_args(argv)
    results = execute_wave(
        args.repo_root,
        us500_m15=args.us500_m15,
        nas100_m15=args.nas100_m15,
        eurusd_m15=args.eurusd_m15,
        us500_cost=args.us500_cost,
        nas100_cost=args.nas100_cost,
    )
    paths = persist_results(results, args.output_dir)
    print(json.dumps({
        "status": "COMPETITION_EXPANSION_WAVE_01_STAGE_A_EXECUTED",
        "execution_head": args.execution_head,
        "execution_ci_run_id": args.execution_ci_run_id,
        "protected_evidence_opened": False,
        "results": {
            cid: {
                "status": results[cid]["status"],
                "event_count": results[cid]["metrics"]["event_count"],
                "active_weeks": results[cid]["metrics"]["active_weeks"],
                "gross_pnl": results[cid]["metrics"]["gross_pnl"],
                "coarse_net_pnl": results[cid]["metrics"]["coarse_net_pnl"],
                "result_hash": results[cid]["result_hash"],
                "path": str(path),
            }
            for cid, path in zip(("V2-C013","V2-C014","V2-C015","V2-C016"), paths)
        },
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
