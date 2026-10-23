"""Independent Decimal cash and terminal BID/ASK mark for the existing C# portfolio
model. Verifies accounting against original quote stream; NOT independent
market evidence, cTrader broker fills, true costs, financing, or HARD21.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
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


def captured_fee_reference(path, report):
    """Independent Decimal interpretation of raw snapshot; never use C# fee output."""
    raw_bytes = Path(path).read_bytes()
    require(sha256(raw_bytes).hexdigest() == report['captured_terms_sha256'], 'CAPTURED_TERMS_HASH')
    snapshot = json.loads(raw_bytes)
    require(snapshot['schema'] == 'mxm.captured-native-symbol-terms.v1' and
            snapshot['symbol_id'] == 1 and not snapshot['historical_commission_proven'] and
            not snapshot['dated_historical_volume_rules_proven'], 'CAPTURED_TERMS_SCOPE')
    if report['classification']=='PINNED_PEPPERSTONE_WEEK35_BREAKOUT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED':
        require(snapshot['source_crypto_authenticated_by_week_native_replay'] is True and
                snapshot['source_run']==39946364621 and
                snapshot['source_code_sha']=='b54ee59548846ad8013b25965dbe4bcb19d4a978' and
                snapshot['source_private_sha256']=='2b37063a948d7b761a7f854e59649793ba1d5ff5e30a7e5255b03f4042cadb13' and
                snapshot['source_ciphertext_sha256']=='0d1badd1a944eeac7a67f1f7c87e05d26c1ea14ea016a0ea25fbb40ce7cb92ee',
                'CAPTURED_W35_NATIVE_BINDING')
    elif report['classification'] in (
        'PINNED_PEPPERSTONE_WEEK37_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED',
        'PINNED_PEPPERSTONE_WEEK37_PRODUCT_DEFAULT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED'):
        require(snapshot['source_crypto_authenticated_by_week_native_replay'] is True and
                snapshot['source_run'] == 39917922508 and snapshot['source_code_sha'] ==
                '120db3391ed1f4105120274b73a9259690eeeb64' and
                snapshot['source_private_sha256'] ==
                '8dde8355c79f3f379bf14f1fd47a8ed5815646cafbcfc287762fb68c2c2e7b51' and
                snapshot['source_ciphertext_sha256'] ==
                '2403c74dfd81ab410f9b9c3bdabf4f3d5a5a4df0133cd0adc03933a364d539b6',
                'CAPTURED_WEEK_NATIVE_BINDING')
    elif report['classification'] != 'ARTIFICIAL_QUOTE_STREAM_ONLY':
        require(snapshot['source_crypto_authenticated_by_original_native_replay'] is True and
                snapshot['source_run'] == 39660692230 and snapshot['source_ciphertext_sha256'] ==
                'f1d828d94b304e2af1f310701f92dcb31db935a8db7fc3f8772087adf5499346',
                'CAPTURED_NATIVE_BINDING')
    else:
        require(snapshot['classification'] == 'ARTIFICIAL_CAPTURED_TERMS_FIXTURE_ONLY', 'CAPTURED_FIXTURE_SCOPE')
    fields = snapshot['raw_optional_fields']
    def integer(key):
        v = fields.get(key)
        require(type(v) is int, 'CAPTURED_OPTIONAL_MISSING_' + key)
        return v
    low, high, step = (integer(k) for k in ('minVolume', 'maxVolume', 'stepVolume'))
    require(0 < low <= high and step > 0 and low % step == 0, 'CAPTURED_VOLUME_GEOMETRY')
    units = number(report['modeled_parameters']['units'])
    cents = units * 100
    require(cents == cents.to_integral_value() and low <= cents <= high and cents % step == 0,
            'CAPTURED_MODEL_VOLUME')
    kind, rate, minimum = (integer(k) for k in
        ('commissionType', 'preciseTradingCommissionRate', 'preciseMinCommission'))
    require(kind in (1, 2, 3) and rate >= 0 and minimum >= 0, 'CAPTURED_FEE_GEOMETRY')
    minimum_kind = integer('minCommissionType')
    asset = 'USD' if minimum_kind == 2 else fields.get('minCommissionAsset') if minimum_kind == 1 else None
    require(asset in ('EUR', 'USD'), 'CAPTURED_MINIMUM_ASSET')
    if kind == 2:
        require(integer('lotSize') > 0, 'CAPTURED_LOT_SIZE')
    def fee(size, price, bid, ask):
        if kind == 1:
            usd = size * price * D(rate) / D(10**14)
        elif kind == 2:
            usd = size * D(100) / D(integer('lotSize')) * D(rate) / D(10**8)
        else:
            usd = size * price * D(rate) / D(10**7)
        minimum_eur = D(minimum)/D(10**8)
        if asset == 'USD': minimum_eur /= bid
        return max(usd/bid, minimum_eur)
    return fee


def independent_terminal_mark(tick_file, report, captured_terms=None):
    require(report["schema"] == "mxm.csharp.native-exposed-quote-to-one-account.v1",
            "REPORT_SCHEMA")
    require(report["classification"] in (
        "ARTIFICIAL_QUOTE_STREAM_ONLY",
        "PINNED_PEPPERSTONE_WEEK35_BREAKOUT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED",
        "ORIGINAL_PEPPERSTONE_QUOTES_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED",
        "PINNED_PEPPERSTONE_WEEK37_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED",
        "PINNED_PEPPERSTONE_WEEK37_PRODUCT_DEFAULT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED"
    ), "REPORT_CLASSIFICATION")
    week35=report["classification"]=="PINNED_PEPPERSTONE_WEEK35_BREAKOUT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED"
    product_stop12=week35 or (report["classification"] ==
        "PINNED_PEPPERSTONE_WEEK37_PRODUCT_DEFAULT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED")
    if product_stop12:
        p=report["modeled_parameters"]
        require(p["product_default_stop12"] is True and
                p["product_stop_pips"]==12 and
                number(p["product_stop_distance_quote"])==D("0.0012") and
                p["product_stop_geometry_source"]==
                "CAPTURED_EURUSD_SNAPSHOT_PIP_POSITION_4_CTRADER_DEFAULT_12_PIPS",
                "PRODUCT_STOP12_DECLARED_EXACT_GEOMETRY")
    book, source = authenticated_shape_quotes(tick_file)
    require(report["derived_stream_sha256"] == source["sha256"], "SOURCE_HASH")
    require(report["quote_events"] == source["source_events"], "EVENT_COUNT")
    if report["classification"] in (
        "PINNED_PEPPERSTONE_WEEK37_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED",
        "PINNED_PEPPERSTONE_WEEK37_PRODUCT_DEFAULT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED"):
        require(source["source_events"] == 685474 and
                report["original_native_run_id"] == 39917922508 and
                report["authenticated_requested_iso_week_input"] == "2026-W37" and
                not report["weekly_provider_pages_broker_execution_proof"] and
                not report["one_full_iso_utc_week_proven"] and
                all(1788739200000 <= ts < 1789344000000 for ts in book),
                "WEEK_DEVELOPMENT_ONLY_INTERVAL")
    if week35:
        require(source['source_events']==683022 and report['original_native_run_id']==39946364621 and
                report['authenticated_requested_iso_week_input']=='2026-W35' and
                all(1787529600000<=ts<1788134400000 for ts in book) and
                report['modeled_parameters']['strategy']=='Breakout' and
                number(report['modeled_parameters']['slip_price_per_side']) in (D('.00002'),D('.00004')) and
                not report['one_full_iso_utc_week_proven'] and
                not report['weekly_provider_pages_broker_execution_proof'], 'W35_FIXED_DEVELOPMENT_SCOPE')
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
    dynamic = report.get('valuation_mode') == 'CAPTURED_COMMISSION_AND_QUOTE_SIDE_FX_COMPONENTS_ONLY'
    if dynamic:
        require(captured_terms is not None and not report['all_cost_components_verified'] and
                not report['captured_terms_are_historical'], 'CAPTURED_COMPONENTS_ONLY')
        fee_reference = captured_fee_reference(captured_terms, report)
        fx = fee = None
    else:
        require(captured_terms is None, 'UNEXPECTED_CAPTURED_TERMS')
        fx = number(terms["quote_to_eur"])
        fee = number(terms["commission_eur_per_side"])
    slip = number(terms["slip_price_per_side"])
    margin = number(terms["margin_eur"])
    require(units > 0 and (dynamic or (fx > 0 and fee >= 0)) and slip >= 0 and margin > 0 and
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
    stop_entry_time=None
    snapshot_times=sorted(book) if product_stop12 else []
    observed_stop_exits=0
    for event in account["ledger"]:
        ledger_columns={
            "kind", "utc", "symbol", "direction", "price", "units",
            "cash_eur", "commission_eur", "gross_eur"
        }
        if product_stop12:
            require(set(event) in (ledger_columns,ledger_columns|{"reason"}),
                    "LEDGER_SCHEMA")
        else:
            require(set(event)==ledger_columns,"LEDGER_SCHEMA")
        ts = tick_ms(event["utc"])
        require(ts >= prior, "LEDGER_CHRONOLOGY")
        prior = ts
        require(ts in book, "TRADE_HAS_NO_EXECUTION_SIDE_BIDASK")
        require(event["symbol"] == "EURUSD", "FOREIGN_LEDGER_SYMBOL")
        require(event["direction"] in (-1, 1), "BAD_DIRECTION")
        require(number(event["units"]) == units, "VOLUME_DRIFT")
        bid, ask = book[ts]
        direction = event["direction"]
        price = number(event["price"])
        actual_fee = fee_reference(units, price, bid, ask) if dynamic else fee
        equal(event["commission_eur"], actual_fee, "FEE_DRIFT")
        if event["kind"] == "ENTRY":
            require("EURUSD" not in positions, "DUPLICATE_OPEN")
            expected = ask + slip if direction == 1 else bid - slip
            equal(price, expected, "WRONG_SIDE_OF_SPREAD_ENTRY", D("0.0000000001"))
            equal(event["gross_eur"], 0, "ENTRY_GROSS_NONZERO")
            cash -= actual_fee
            if product_stop12:
                stop_price=price-D(direction)*D("0.0012")
                require(stop_price>0 and
                        (bid>stop_price if direction==1 else ask<stop_price),
                        "PRODUCT_STOP_ALREADY_TOUCHED_AT_ENTRY")
                stop_entry_time=ts
            positions["EURUSD"] = (direction, price, units)
            counts["entries"] += 1
        elif event["kind"] == "EXIT":
            require("EURUSD" in positions, "EXIT_WITHOUT_ENTRY")
            original_direction, initial, size = positions["EURUSD"]
            require(direction == original_direction, "EXIT_DIRECTION_CHANGED")
            if product_stop12:
                reason=event.get("reason")
                require(reason in ("REVERSAL","NEUTRAL_FLAT","HORIZON12",
                                  "OBSERVED_QUOTE_STOP"),"PRODUCT_STOP_EXIT_REASON")
                stop_price=initial-D(direction)*D("0.0012")
                require(stop_entry_time is not None,"PRODUCT_STOP_MISSING_ENTRY_CLOCK")
                first_touch=None
                lo=bisect_right(snapshot_times,stop_entry_time)
                hi=bisect_right(snapshot_times,ts)
                for observed in snapshot_times[lo:hi]:
                    touch_bid,touch_ask=book[observed]
                    if (touch_bid<=stop_price if direction==1 else touch_ask>=stop_price):
                        first_touch=observed
                        break
                if first_touch is not None:
                    require(first_touch==ts and reason=="OBSERVED_QUOTE_STOP",
                            "PRODUCT_STOP_MUST_TRIGGER_ON_FIRST_OBSERVED_SIDE")
                    observed_stop_exits+=1
                else:
                    require(reason!="OBSERVED_QUOTE_STOP",
                            "PRODUCT_STOP_WITHOUT_OBSERVED_SIDE_TRIGGER")
            expected = bid - slip if direction == 1 else ask + slip
            equal(price, expected, "WRONG_SIDE_OF_SPREAD_EXIT", D("0.0000000001"))
            quote_gross = (price - initial) * size * D(direction)
            gross = quote_gross/(ask if quote_gross >= 0 else bid) if dynamic else quote_gross*fx
            equal(event["gross_eur"], gross, "GROSS_PNL_DRIFT")
            cash += gross - actual_fee
            del positions["EURUSD"]
            stop_entry_time=None
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
    terminal_open_stop_checks=0
    for direction, entry, size in positions.values():
        if product_stop12:
            require(stop_entry_time is not None, "PRODUCT_STOP_MISSING_ENTRY_CLOCK")
            stop_price=entry-D(direction)*D("0.0012")
            # An omitted EXIT has no ledger row on which to run the earlier
            # first-touch check. Scan the entire remaining observed suffix,
            # including the terminal quote: recovery cannot erase a stop touch.
            lo=bisect_right(snapshot_times,stop_entry_time)
            for observed in snapshot_times[lo:]:
                stop_bid,stop_ask=book[observed]
                require(stop_bid>stop_price if direction==1 else stop_ask<stop_price,
                        "PRODUCT_STOP_OPEN_POSITION_MISSED_OBSERVED_TOUCH")
            terminal_open_stop_checks+=1
        quote_pnl = ((last_bid - entry) if direction == 1 else (entry - last_ask)) * size
        equity += quote_pnl/(last_ask if quote_pnl >= 0 else last_bid) if dynamic else quote_pnl*fx
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
        "product_default_stop12_replayed": product_stop12,
        "product_first_observed_stop_exits_independently_checked": observed_stop_exits,
        "terminal_open_stop_paths_independently_checked": terminal_open_stop_checks,
        "cash_abs_difference_eur": str(abs(cash-number(account["final_cash_eur"]))),
        "equity_abs_difference_eur": str(abs(equity-number(account["marked_equity_eur"]))),
        "full_iso_weeks_verified": 0,
        "hard21": False,
        "independent_native_broker_execution": False,
        "broker_historical_costs_verified": False,
        "captured_commission_component_checked": dynamic,
        "quote_side_fx_conversion_checked": dynamic,
        "all_cost_components_verified": False,
        "new_broker_requests": 0,
        "orders": 0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("native_quotes")
    p.add_argument("portfolio_report")
    p.add_argument("--out", required=True)
    p.add_argument("--captured-terms")
    args = p.parse_args()
    report = json.loads(Path(args.portfolio_report).read_text(), parse_float=D)
    result = independent_terminal_mark(args.native_quotes, report, args.captured_terms)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, sort_keys=True, separators=(",", ":"))+"\n")
    print("MXM_NATIVE_SINGLE_EUR200_INDEPENDENT_CASH_AND_LIQUIDATION_MTM_PASS_NO_BROKER_FILL")


if __name__ == "__main__":
    main()
