"""Live-equivalent same-identity implementation corrections for C006/C012/C023/C025.

Frozen candidate semantics are unchanged.  This module changes only historical replay
control flow so entry admission never depends on a future exit row.  Post-entry
settlement is processed after causal admission; sample-end censoring and missing
post-entry settlement data are reported explicitly instead of retroactively deleting
an entry.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence
import hashlib, json, math, statistics

from discovery.canonical import compute_result_hash
from discovery.schema import validate_result
from m6.session_replay import (
    NasdaqCashCalendar, cash_session_observations, exact_session_close_price,
    prior_valid_true_ranges, synchronized_observed_cash_bars,
)
from m6.tier1_candidate_replay import (
    C006_HASH, C012_HASH, ReplayIntent, _f, _prior_finite_window, _sample_std, _utc,
)
from m7 import competition_performance_v3_wave02_evaluator as wave02

VERSION = "MXM_SAME_IDENTITY_LIVE_EQUIVALENT_CORRECTION_V1"
IDS = ("V2-C006", "V2-C012", "V2-C023", "V2-C025")


def sha256_file(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ReplayCorrection:
    settled_intents: tuple[ReplayIntent, ...]
    admitted_entries: int
    right_censored_entries: int
    post_entry_settlement_invalid_entries: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class TradeCorrection:
    settled_trades: tuple[dict[str, Any], ...]
    admitted_entries: int
    right_censored_entries: int
    post_entry_settlement_invalid_entries: tuple[dict[str, Any], ...]
    diagnostics: dict[str, Any]


def c006_live_equivalent_replay(
    us500_rows: Sequence[Mapping[str, Any]], calendar: NasdaqCashCalendar,
) -> ReplayCorrection:
    observations = cash_session_observations(us500_rows, calendar)
    settled: list[ReplayIntent] = []
    admitted = right_censored = 0
    for day in sorted(observations):
        current = observations[day]
        open_bar = current.exact_open_bar
        if open_bar is None:
            continue
        prior_session = calendar.previous_session(day)
        if prior_session is None:
            continue
        prior_close = exact_session_close_price(observations, prior_session.session_date)
        if prior_close is None or prior_close <= 0:
            continue
        trp = prior_valid_true_ranges(observations, calendar, day, count=20)
        if len(trp) != 20:
            continue
        atr20 = sum(trp) / 20.0
        if atr20 <= 0:
            continue
        cash_open = _f(open_bar, "open")
        gap = cash_open / prior_close - 1.0
        ratio = gap / atr20
        direction = "LONG" if ratio <= -0.75 else ("SHORT" if ratio >= 0.75 else None)
        if direction is None:
            continue

        decision = current.session.open_utc + timedelta(minutes=15)
        # Admission requires only the first actually observed executable event at/after T.
        executable = [row for row in current.ordered_expected_bars() if _utc(row["time_utc"]) >= decision]
        if not executable:
            continue
        entry_bar = executable[0]
        entry_time = _utc(entry_bar["time_utc"])
        if entry_time < decision:
            raise ValueError("C006 entry event precedes frozen decision")
        admitted += 1

        # The fixed 12-executable-bar settlement is evaluated only after admission.
        if len(executable) < 12:
            right_censored += 1
            continue
        exit_bar = executable[11]
        exit_time = _utc(exit_bar["time_utc"]) + timedelta(minutes=15)
        if exit_time > current.session.close_utc:
            right_censored += 1
            continue
        settled.append(ReplayIntent(
            candidate_id="V2-C006", spec_hash=C006_HASH, direction=direction,
            decision_utc=decision, entry_utc=entry_time, entry_price=_f(entry_bar, "open"),
            exit_utc=exit_time, exit_price=_f(exit_bar, "close"),
            evidence={
                "overnight_gap_pct": gap, "prior_atr20_pct": atr20, "gap_atr_ratio": ratio,
                "cash_session_open_utc": current.session.open_utc.isoformat(),
                "prior_cash_session_close_utc": prior_session.close_utc.isoformat(),
                "prior_cash_session_close": prior_close,
                "atr20_valid_completed_sessions": "20",
            },
        ))
    return ReplayCorrection(tuple(settled), admitted, right_censored)


def c012_live_equivalent_replay(
    us500_rows: Sequence[Mapping[str, Any]], nas100_rows: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
) -> ReplayCorrection:
    pairs = synchronized_observed_cash_bars(us500_rows, nas100_rows, calendar, bar_minutes=15)
    if not pairs:
        return ReplayCorrection((), 0, 0)
    leader_ret2: list[float] = []
    lagger_ret2: list[float] = []
    settled: list[ReplayIntent] = []
    admitted = right_censored = 0
    active_until_index = -1
    for i, (leader, lagger) in enumerate(pairs):
        if i < 2:
            leader_ret2.append(float("nan")); lagger_ret2.append(float("nan")); continue
        lr = _f(leader, "close") / _f(pairs[i-2][0], "close") - 1.0
        rr = _f(lagger, "close") / _f(pairs[i-2][1], "close") - 1.0
        leader_ret2.append(lr); lagger_ret2.append(rr)
        valid_l = _prior_finite_window(leader_ret2, i, 520)
        valid_r = _prior_finite_window(lagger_ret2, i, 520)
        if len(valid_l) < 520 or len(valid_r) < 520:
            continue
        lstd = _sample_std(valid_l); rstd = _sample_std(valid_r)
        if lstd <= 0 or rstd <= 0:
            continue
        lz = lr / lstd; rz = rr / rstd
        if i <= active_until_index:
            continue
        direction = "LONG_NAS100" if lz >= 1.5 and rz <= 0.5 else (
            "SHORT_NAS100" if lz <= -1.5 and rz >= -0.5 else None
        )
        if direction is None:
            continue
        decision = _utc(lagger["time_utc"]) + timedelta(minutes=15)
        entry_index = i + 1
        # No execution event => no executed entry.  No exit-row query participates here.
        if entry_index >= len(pairs):
            continue
        entry_lagger = pairs[entry_index][1]
        entry_time = _utc(entry_lagger["time_utc"])
        if entry_time < decision:
            raise ValueError("C012 entry event precedes decision")
        admitted += 1
        exit_index = entry_index + 3
        if exit_index >= len(pairs):
            right_censored += 1
            active_until_index = len(pairs) - 1
            continue
        exit_lagger = pairs[exit_index][1]
        settled.append(ReplayIntent(
            candidate_id="V2-C012", spec_hash=C012_HASH, direction=direction,
            decision_utc=decision, entry_utc=entry_time, entry_price=_f(entry_lagger, "open"),
            exit_utc=_utc(exit_lagger["time_utc"]) + timedelta(minutes=15),
            exit_price=_f(exit_lagger, "close"),
            evidence={"leader_ret2": lr, "lagger_ret2": rr, "leader_z": lz, "lagger_z": rz},
        ))
        active_until_index = exit_index
    return ReplayCorrection(tuple(settled), admitted, right_censored)


def _contiguous(rows: Sequence[Mapping[str, Any]], a: int, b: int, m5) -> bool:
    return a >= 0 and b < len(rows) and all(rows[j+1]["t"] - rows[j]["t"] == m5 for j in range(a, b))


def c023_live_equivalent_trades(rows_by_symbol, costs, start, end, m5) -> TradeCorrection:
    markets = tuple(rows_by_symbol)
    maps = {s: {r["t"]: i for i, r in enumerate(rows_by_symbol[s])} for s in markets}
    settled: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    admitted = right_censored = 0
    d = start
    while d < end:
        # Frozen C023 says the scheduled exit remains pending until the first observed M5 open.
        if active is not None and d >= active["exit_intent"]:
            symbol = active["s"]
            j = maps[symbol].get(d)
            if j is not None:
                row = rows_by_symbol[symbol][j]
                trade = dict(active)
                trade.pop("exit_intent")
                trade.update({"x": d, "q": row["o"]})
                settled.append(trade)
                active = None

        # Exit-first then allow the same timestamp to become a new decision boundary,
        # matching the frozen C023 global-active policy.
        if d.minute == 0 and d.second == 0 and d.hour in (0, 4, 8, 12, 16, 20) and active is None:
            signal_open = d - m5
            ranked = []
            for symbol in markets:
                q = rows_by_symbol[symbol]; m = maps[symbol]
                i = m.get(signal_open); ei = m.get(d)
                if i is None or ei is None or ei != i + 1 or not _contiguous(q, i-48, i, m5):
                    continue
                ret = q[i]["c"] / q[i-48]["c"] - 1.0
                if ret == 0:
                    continue
                ranked.append((abs(ret) / costs[symbol], symbol, ret, ei))
            if ranked:
                ranked.sort(key=lambda x: (-x[0], x[1]))
                score, symbol, ret, ei = ranked[0]
                q = rows_by_symbol[symbol]
                admitted += 1
                active = {
                    "cid": "V2-C023", "s": symbol,
                    "d": "LONG" if ret > 0 else "SHORT", "e": d,
                    "p": q[ei]["o"], "costf": costs[symbol], "score": score,
                    "exit_intent": d + timedelta(hours=4),
                }
        d += m5
    if active is not None:
        right_censored += 1
    return TradeCorrection(tuple(settled), admitted, right_censored, (), {
        "admitted_entries": admitted, "settled_entries": len(settled),
        "right_censored_entries": right_censored,
    })


def c025_live_equivalent_trades(rows_by_symbol, costs) -> TradeCorrection:
    all_settled: list[dict[str, Any]] = []
    invalid_entries: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    total_admitted = total_right = 0
    for symbol, rows in rows_by_symbol.items():
        index = {r["t"]: i for i, r in enumerate(rows)}
        hist = defaultdict(deque)
        pending_training: list[dict[str, Any]] = []
        active: dict[str, Any] | None = None
        settled: list[dict[str, Any]] = []
        decisions = eligible_states = cost_hurdle_passes = admitted = right_censored = 0
        training_settlement_invalid = 0
        for i in range(147, len(rows)):
            if not wave02.decision_boundary(rows[i]["t"]):
                continue
            dtime = rows[i]["t"] + wave02.M5

            # Realize training examples only after their target could have become observable.
            remaining = []
            for ex in pending_training:
                if ex["availability"] > dtime:
                    remaining.append(ex); continue
                ei = index.get(ex["entry_time"]); xi = index.get(ex["target_bar_time"])
                if ei is not None and xi is not None and xi == ei + 2 and wave02.contiguous(rows, ei, xi):
                    hist[ex["state"]].append((ex["decision_time"], rows[xi]["c"] / ex["entry_price"] - 1.0))
                else:
                    training_settlement_invalid += 1
            pending_training = remaining

            # Settle an already-admitted economic trade before considering this timestamp's signal.
            suppress_same_timestamp_entry = False
            if active is not None and active["availability"] <= dtime:
                ei = index.get(active["entry_time"]); xi = index.get(active["target_bar_time"])
                if ei is not None and xi is not None and xi == ei + 2 and wave02.contiguous(rows, ei, xi):
                    q = rows[xi]
                    settled.append({
                        "cid": "V2-C025", "s": symbol, "d": active["direction"],
                        "e": active["entry_time"], "x": q["t"] + wave02.M5,
                        "p": active["entry_price"], "q": q["c"], "costf": costs[symbol],
                        "meta": active["meta"],
                    })
                else:
                    invalid_entries.append({
                        "symbol": symbol,
                        "entry_time": active["entry_time"].isoformat(),
                        "expected_target_bar_time": active["target_bar_time"].isoformat(),
                        "classification": "POST_ENTRY_SETTLEMENT_DATA_INVALID",
                    })
                active = None
                suppress_same_timestamp_entry = True

            cutoff = dtime - timedelta(days=28)
            for state in list(hist):
                dq = hist[state]
                while dq and dq[0][0] < cutoff:
                    dq.popleft()
                if not dq:
                    del hist[state]
            state = wave02._c025_state(rows, i)
            if state is None:
                continue
            decisions += 1

            # A training observation is born at T only if the exact entry event is observable;
            # the future target remains pending and is not queried now.
            ei = index.get(dtime)
            if ei is not None and rows[ei]["o"] > 0:
                pending_training.append({
                    "availability": dtime + 3 * wave02.M5,
                    "decision_time": dtime, "state": state,
                    "entry_time": dtime, "entry_price": rows[ei]["o"],
                    "target_bar_time": dtime + 2 * wave02.M5,
                })

            vals = [x[1] for x in hist.get(state, ())]
            if len(vals) < 2:
                continue
            eligible_states += 1
            mean = statistics.mean(vals); se = statistics.stdev(vals) / math.sqrt(len(vals))
            if mean == 0 or abs(mean) - se <= costs[symbol]:
                continue
            cost_hurdle_passes += 1
            if suppress_same_timestamp_entry or active is not None or ei is None:
                continue
            admitted += 1
            active = {
                "entry_time": dtime, "entry_price": rows[ei]["o"],
                "target_bar_time": dtime + 2 * wave02.M5,
                "availability": dtime + 3 * wave02.M5,
                "direction": "LONG" if mean > 0 else "SHORT",
                "meta": {"state": list(state), "train_n": len(vals), "mean": mean,
                         "se": se, "lower_abs_edge": abs(mean) - se},
            }

        if active is not None:
            right_censored += 1
        total_admitted += admitted; total_right += right_censored
        all_settled.extend(settled)
        diagnostics[symbol] = {
            "decisions": decisions,
            "states_with_at_least_2_prior_examples": eligible_states,
            "cost_hurdle_passes": cost_hurdle_passes,
            "admitted_entries": admitted,
            "settled_entries": len(settled),
            "right_censored_entries": right_censored,
            "training_examples_with_invalid_post_entry_settlement": training_settlement_invalid,
            "pending_training_examples_at_end": len(pending_training),
        }
    return TradeCorrection(
        tuple(all_settled), total_admitted, total_right, tuple(invalid_entries), diagnostics
    )


def unavailable_metrics(reason: str) -> dict[str, Any]:
    from discovery.schema import STAGE_A_METRIC_KEYS
    return {key: {"state": "UNAVAILABLE", "reason": reason} for key in STAGE_A_METRIC_KEYS}


def finalize_corrected_result(result: dict[str, Any], evaluator_sha256: str, reason: str) -> dict[str, Any]:
    result = json.loads(json.dumps(result))
    result["implementation_validity"] = {"state": "VALID", "reason": reason}
    result["provenance"]["evaluator"] = {"version": VERSION, "sha256": evaluator_sha256}
    result.pop("result_hash", None)
    validate_result(result)
    result["result_hash"] = compute_result_hash(result)
    validate_result(result)
    return result


def c025_data_insufficient_result(spec: Mapping[str, Any], evaluator_sha256: str,
                                  diagnostics: TradeCorrection) -> dict[str, Any]:
    reason = (
        f"{len(diagnostics.post_entry_settlement_invalid_entries)} causally admitted C025 entries "
        "lack the exact post-entry contiguous target grid required by the frozen exit semantics; "
        "they cannot be retroactively suppressed or economically settled from this DEVELOPMENT corpus."
    )
    result = {
        "candidate_id": "V2-C025", "spec_hash": spec["spec_hash"], "stage": "A",
        "status": "DATA_INSUFFICIENT",
        "implementation_validity": {"state": "VALID", "reason": "Live-equivalent admission correction passed; future target availability is never queried before entry."},
        "metrics": unavailable_metrics(reason),
        "eur200_feasibility": {"state": "NOT_EVALUATED", "reason": "Stage A cannot promote while corrected settlement data are insufficient."},
        "cost_confidence": {"state": "CONSERVATIVE_BOUND", "reason": "Unchanged pre-outcome V6 per-symbol coarse roundtrip cost authority."},
        "data_completeness": {"state": "INSUFFICIENT", "reason": reason},
        "provenance": {
            "data_evidence": {"identity": "MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6", "binding": {"type": "DATASET_SHA256", "sha256": wave02.CAP}},
            "cost_evidence": {"identity": "COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1", "state": "CONSERVATIVE_BOUND", "sha256": wave02.COST_SHA},
            "evaluator": {"version": VERSION, "sha256": evaluator_sha256},
        },
    }
    validate_result(result)
    result["result_hash"] = compute_result_hash(result)
    validate_result(result)
    return result
