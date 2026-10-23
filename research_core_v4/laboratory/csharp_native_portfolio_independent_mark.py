"""Independent Decimal cash and terminal BID/ASK mark for the existing C# portfolio
model. Verifies accounting against original quote stream; NOT independent
market evidence, cTrader broker fills, true costs, financing, or HARD21.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal as D, getcontext
from hashlib import sha256
from itertools import groupby
import json
from pathlib import Path

getcontext().prec = 50
TOL = D("0.000001")


class MarkParityError(ValueError):
    pass


def require(ok, label):
    if not ok:
        raise MarkParityError("MXM_CSHARP_NATIVE_MARK_PARITY_" + label)


def number(value):
    result = D(str(value))
    require(result.is_finite(), "NONFINITE_NUMBER")
    return result


def equal(actual, expected, why, tolerance=TOL):
    require(abs(number(actual) - number(expected)) <= tolerance, why)


def tick_ms(stamp):
    require(isinstance(stamp, str), "TRADE_TIMESTAMP")
    t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    require(t.tzinfo is not None, "TIMESTAMP_TIMEZONE")
    return round(t.astimezone(timezone.utc).timestamp() * 1000)


def authenticated_shape_quotes(path):
    seq = []
    last = -1
    original = Path(path).read_bytes()
    for line in original.splitlines():
        row = json.loads(line)
        require(set(row) == {"t", "side", "raw"}, "SOURCE_SCHEMA")
        t, side, raw = row["t"], row["side"], row["raw"]
        require(type(t) is int and type(raw) is int and t >= last and
                t > 0 and raw > 0 and side in ("bid", "ask"), "SOURCE_CHRONOLOGY")
        last = t
        seq.append((t, side, raw))
    require(seq, "EMPTY_NATIVE_SOURCE")
    book = {}
    bid = ask = None
    bid_at = ask_at = -1
    ambiguous = crossed = stale = 0
    for ts, it in groupby(seq, key=lambda x: x[0]):
        group = list(it)
        if any(len({x[2] for x in group if x[1] == side}) > 1
               for side in ("bid", "ask")):
            ambiguous += 1
            continue
        for _, side, raw in group:
            if side == "bid":
                bid = D(raw) / D(100000)
                bid_at = ts
            else:
                ask = D(raw) / D(100000)
                ask_at = ts
        if bid is None or ask is None:
            continue
        if ask < bid:
            crossed += 1
            continue
        if ts - bid_at > 300000 or ts - ask_at > 300000:
            stale += 1
            continue
        book[ts] = (bid, ask)
    return book, dict(ambiguous=ambiguous, crossed=crossed, stale=stale,
                      source_events=len(seq), sha256=sha256(original).hexdigest())


def independent_terminal_mark(tick_file, report):
    require(report["schema"] == "mxm.csharp.native-exposed-quote-to-one-account.v1",
            "REPORT_SCHEMA")
    require(report["classification"] in (
        "ARTIFICIAL_QUOTE_STREAM_ONLY",
        "ORIGINAL_PEPPERSTONE_QUOTES_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED"
    ), "REPORT_CLASSIFICATION")
    book, source = authenticated_shape_quotes(tick_file)
    require(report["derived_stream_sha256"] == source["sha256"], "SOURCE_HASH")
    require(report["quote_events"] == source["source_events"], "EVENT_COUNT")
    require(report["grouped_atomic_usable_snapshots"] == len(book),
            "ATOMIC_SNAPSHOT_COUNT")
    for field, label in (("ambiguous_same_side_ms_revisions_skipped", "ambiguous"),
                         ("crossed_snapshots_skipped", "crossed"),
                         ("stale_side_snapshots_skipped", "stale")):
        require(report[field] == source[label], "FILTER_" + label.upper())
    require(report["actual_symbols"] == 1 and
            not report["multi_instrument_native_data_available"],
            "SINGLE_SOURCE_SYMBOL")
    require(report["new_broker_requests"] == report["live_orders"] == 0 and
            not report["historical_broker_fills_proven"] and
            not report["hard21_proven"], "NO_EXECUTION_OR_PROMOTION")
    terms = report["modeled_parameters"]
    units = number(terms["units"])
    fx = number(terms["quote_to_eur"])
    fee = number(terms["commission_eur_per_side"])
    slip = number(terms["slip_price_per_side"])
    margin = number(terms["margin_eur"])
    require(units > 0 and fx > 0 and fee >= 0 and slip >= 0 and margin > 0 and
            not terms["historical_broker_terms_verified"],
            "UNVERIFIED_MONETARY_TERMS")
    account = report["account"]
    require(account["initial_capital_eur"] == 200 and
            account["complete_iso_utc_weeks"] == 0 and
            not account["hard21_proven"] and not account["broker_fills_proven"] and
            not account["costs_broker_verified"], "NO_FULL_WEEK_OR_BROKER_FILL")
    require(not account["rejections"] or
            "SIMULATED_EQUITY_OR_MARGIN_HALT_NOT_BROKER_STOPOUT"
            not in account["rejections"], "MODEL_HALTED_PREMATURELY")
    cash = D(200)
    positions = {}
    counts = defaultdict(int)
    prior = -1
    for event in account["ledger"]:
        require(set(event) == {
            "kind", "utc", "symbol", "direction", "price", "units",
            "cash_eur", "commission_eur", "gross_eur"
        }, "LEDGER_SCHEMA")
        ts = tick_ms(event["utc"])
        require(ts >= prior, "LEDGER_CHRONOLOGY")
        prior = ts
        require(ts in book, "TRADE_HAS_NO_EXECUTION_SIDE_BIDASK")
        require(event["symbol"] == "EURUSD", "FOREIGN_LEDGER_SYMBOL")
        require(event["direction"] in (-1, 1), "BAD_DIRECTION")
        require(number(event["units"]) == units, "VOLUME_DRIFT")
        equal(event["commission_eur"], fee, "FEE_DRIFT")
        bid, ask = book[ts]
        direction = event["direction"]
        price = number(event["price"])
        if event["kind"] == "ENTRY":
            require("EURUSD" not in positions, "DUPLICATE_OPEN")
            expected = ask + slip if direction == 1 else bid - slip
            equal(price, expected, "WRONG_SIDE_OF_SPREAD_ENTRY", D("0.0000000001"))
            equal(event["gross_eur"], 0, "ENTRY_GROSS_NONZERO")
            cash -= fee
            positions["EURUSD"] = (direction, price, units)
            counts["entries"] += 1
        elif event["kind"] == "EXIT":
            require("EURUSD" in positions, "EXIT_WITHOUT_ENTRY")
            original_direction, initial, size = positions["EURUSD"]
            require(direction == original_direction, "EXIT_DIRECTION_CHANGED")
            expected = bid - slip if direction == 1 else ask + slip
            equal(price, expected, "WRONG_SIDE_OF_SPREAD_EXIT", D("0.0000000001"))
            gross = (price - initial) * size * fx * D(direction)
            equal(event["gross_eur"], gross, "GROSS_PNL_DRIFT")
            cash += gross - fee
            del positions["EURUSD"]
            counts["exits"] += 1
        else:
            raise MarkParityError("MXM_CSHARP_NATIVE_MARK_PARITY_UNKNOWN_KIND")
        equal(event["cash_eur"], cash, "CASH_AFTER_EACH_LEDGER_EVENT")
    require(counts["entries"] == account["accepted_entries"] and
            counts["exits"] == account["executed_exits"] and
            len(positions) == account["open_positions"], "LIFECYCLE_COUNTS")
    equal(account["final_cash_eur"], cash, "TERMINAL_CASH")
    require(book, "NO_EXECUTABLE_LIQUIDATION_MARKS")
    last_ts = max(book)
    last_bid, last_ask = book[last_ts]
    equity = cash
    for direction, entry, size in positions.values():
        equity += ((last_bid - entry) if direction == 1 else
                   (entry - last_ask)) * size * fx
    used_margin = margin * len(positions)
    equal(account["marked_equity_eur"], equity, "TERMINAL_LIQUIDATION_MTM")
    equal(account["used_margin_eur"], used_margin, "SHARED_MARGIN")
    equal(account["free_margin_eur"], equity - used_margin, "SHARED_FREE_MARGIN")
    return {
        "schema": "mxm.csharp.single-account.independent-authentic-quote-mark-parity.v1",
        "classification": "INDEPENDENT_ARITHMETIC_SAME_EXPOSED_NATIVE_QUOTES_UNVERIFIED_EXECUTION",
        "market_source_sha256": source["sha256"],
        "source_native_quote_events": source["source_events"],
        "independent_quote_snapshots": len(book),
        "independent_cash_eur": str(cash),
        "independent_liquidation_side_equity_eur": str(equity),
        "independent_used_margin_eur": str(used_margin),
        "ledger_entry_count": counts["entries"],
        "ledger_exit_count": counts["exits"],
        "open_positions": len(positions),
        "cash_abs_difference_eur": str(abs(cash-number(account["final_cash_eur"]))),
        "equity_abs_difference_eur": str(abs(equity-number(account["marked_equity_eur"]))),
        "full_iso_weeks_verified": 0,
        "hard21": False,
        "independent_native_broker_execution": False,
        "broker_historical_costs_verified": False,
        "new_broker_requests": 0,
        "orders": 0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("native_quotes")
    p.add_argument("portfolio_report")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    report = json.loads(Path(args.portfolio_report).read_text(), parse_float=D)
    result = independent_terminal_mark(args.native_quotes, report)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, sort_keys=True, separators=(",", ":"))+"\n")
    print("MXM_NATIVE_SINGLE_EUR200_INDEPENDENT_CASH_AND_LIQUIDATION_MTM_PASS_NO_BROKER_FILL")


if __name__ == "__main__":
    main()
