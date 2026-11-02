"""Isolated, reusable OWNER-authorized read-only -> existing C# pathway.

This module does not invoke or modify any legacy first-only operation.
admit runs without secrets; collect is restricted to the newly admitted run;
seal verifies the authentic original-to-quote-to-C# source chain.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from itertools import groupby
from pathlib import Path

from mxm_runtime.contract import validate_operation, _require as need

REPO = "mariancradulescu/mxm-quant-greenfield"
BRANCH = "mxm-runtime-isolated-20261102"
ROOT = Path("mxm_runtime/authorizations")
KEYS = ("R3_CTRADER_CLIENT_ID", "R3_CTRADER_CLIENT_SECRET", "R3_CTRADER_ACCESS_TOKEN")
PUB = Path("research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem")
FINGERPRINT = "464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"
WIRE = ("ProtoOAApplicationAuthReq", "ProtoOAGetAccountListByAccessTokenReq",
        "ProtoOAAccountAuthReq", "ProtoOASymbolsListReq", "ProtoOASymbolByIdReq",
        "ProtoOAGetTrendbarsReq", "ProtoOAGetTickDataReq")

def sha(b):
    return hashlib.sha256(b).hexdigest()

def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def millis(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)

def stamp(t):
    return dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")

def private():
    need(bool(os.getenv("RUNNER_TEMP")), "RUNNER_TEMP")
    return Path(os.environ["RUNNER_TEMP"]) / "mxm-runtime-private"

def output(op):
    return Path("verification/mxm-runtime") / op["operation_id"]

def scope(path):
    p = Path(path)
    need(p.parent == ROOT and p.suffix == ".json", "PATH")
    obj = validate_operation(json.loads(p.read_text()))
    need(p.stem == obj["operation_id"], "IDENTITY")
    for other in ROOT.glob("*.json"):
        if other == p:
            continue
        existing = validate_operation(json.loads(other.read_text()))
        need(existing["operation_id"] != obj["operation_id"] and
             (existing["broker"], existing["symbol"], existing["start_utc"], existing["end_utc"]) !=
             (obj["broker"], obj["symbol"], obj["start_utc"], obj["end_utc"]),
             "DUPLICATE_ID_OR_SOURCE_WINDOW")
    return obj

def context():
    need(os.getenv("GITHUB_REPOSITORY") == REPO, "REPO")
    need(os.getenv("GITHUB_REF") == "refs/heads/" + BRANCH, "BRANCH")
    need(os.getenv("GITHUB_EVENT_NAME") == "push", "PUSH")
    need(os.getenv("GITHUB_RUN_ATTEMPT") == "1", "FIRST_ATTEMPT_ONLY")
    need(os.getenv("GITHUB_JOB") == "collect-authenticated", "JOB")

def admit():
    context()
    need(not any(os.getenv(key) for key in KEYS), "PRE_SECRET_ADMISSION")
    before = os.getenv("MXM_BEFORE", "")
    after = os.getenv("GITHUB_SHA", "")
    need(re.fullmatch("[0-9a-f]{40}", before) is not None and before != "0"*40 and
         re.fullmatch("[0-9a-f]{40}", after) is not None, "COMMIT_IDS")
    changed = subprocess.check_output(
        ["git", "diff", "--name-status", before, after], text=True).splitlines()
    need(len(changed) == 1 and changed[0].startswith("A\t"), "ONLY_ONE_NEW_AUTH_FILE")
    file = changed[0].split("\t", 1)[1]
    need(re.fullmatch(r"mxm_runtime/authorizations/MXMRO-[0-9]{8}-[A-Z0-9]{8,24}\.json",
                      file) is not None, "AUTHORIZED_FILE")
    op = scope(file)
    need(os.getenv("GITHUB_RUN_ID", "").isdigit(), "RUN_ID")
    proof = {"operation_id": op["operation_id"], "authorization_sha256": sha(canon(op)),
             "commit_sha": after, "run_id": os.environ["GITHUB_RUN_ID"],
             "mode": "READ_ONLY_NO_ORDERS"}
    private().mkdir(parents=True, exist_ok=False, mode=0o700)
    (private() / "admission.json").write_bytes(canon(proof))
    with open(os.environ["GITHUB_OUTPUT"], "a") as handle:
        handle.write("operation=" + file + "\n")
    print("MXM_NEW_OPERATION_ADMITTED " + json.dumps(proof), file=sys.stderr)

def csharp_feed(op, ticks, qsha):
    events = []
    bid = ask = tb = ta = None
    policy = sha(("INTEGRATION_ONLY|" + op["operation_id"]).encode())
    sizing = sha(("NATIVE_SIZING_INTEGRATION_ONLY|" + op["operation_id"]).encode())
    for t, sample in groupby(ticks, lambda x: x["t"]):
        points = list(sample)
        bs = {x["raw"] for x in points if x["side"] == "bid"}
        asks = {x["raw"] for x in points if x["side"] == "ask"}
        if len(bs) > 1 or len(asks) > 1:
            continue
        if bs:
            bid, tb = next(iter(bs)), t
        if asks:
            ask, ta = next(iter(asks)), t
        if bid is None or ask is None or not 0 < bid < ask:
            continue
        if t - tb > 5000 or t - ta > 5000:
            continue
        b, a = round(bid / 100000, 5), round(ask / 100000, 5)
        if not 0 < b < a:
            continue
        events.append({"$feed": "quote", "Utc": stamp(t), "Symbol": op["symbol"],
            "Bid": b, "Ask": a, "QuoteToEur": round(1 / a, 12),
            "QuoteLossToEur": round(1 / b, 12), "ExecutableUnits": 1000,
            "InitialMarginEur": 50, "CommissionPerSideEur": 0.03,
            "SlipPerSideQuote": 0.00002, "EstimatedStopRiskEur": 1.2,
            "StopDistanceQuote": 0.0012, "BidSourceUtc": stamp(tb),
            "AskSourceUtc": stamp(ta), "NativeSizingScenarioSha256": sizing,
            "BrokerVolumeMinUnits": 1000, "BrokerVolumeMaxUnits": 1000,
            "BrokerVolumeStepUnits": 1000})
    start, end = millis(op["start_utc"]), millis(op["end_utc"])
    # These are fixed cash-bridge decisions, not a predictive model or alpha.
    for seq, (t, desired) in enumerate(
        ((start + (end-start)//3, 1), (start + 2*(end-start)//3, 0)), 1):
        events.append({"$feed": "explicit-decision", "Utc": stamp(t),
            "Symbol": op["symbol"], "Sequence": seq, "Desired": desired,
            "ValidFromUtc": stamp(t+1), "ExpiresUtc": stamp(t+240000),
            "PolicySha256": policy})
    events.sort(key=lambda x: (x["Utc"],
                0 if x["$feed"] == "explicit-decision" else 1))
    need(100 <= len(events) <= op["max_ticks"] + 2, "FEED_SIZE")
    return {"Schema": "mxm.shared-funded-account.request.v1",
        "SourceSha256": qsha, "Symbols": [op["symbol"]],
        "Parameters": {"Strategy": 0, "MaxMarginFraction": 0.4,
            "MaxPositions": 1, "MinimumFreeMarginReserveEur": 120,
            "MaxEstimatedStopRiskFraction": 0.01,
            "RoundTripRiskReserveEur": 0.2, "BarMinutes": 5,
            "MaxQuoteAgeSeconds": 300, "ExplicitPolicySha256": policy,
            "NativeSizingScenarioSha256": sizing},
        "ExpectedOrdinal": 0, "PriorSha256": None, "Events": events}

def collect(file):
    context()
    op = scope(file)
    proof = json.loads((private() / "admission.json").read_text())
    need(proof["operation_id"] == op["operation_id"] and
         proof["authorization_sha256"] == sha(canon(op)) and
         proof["commit_sha"] == os.environ["GITHUB_SHA"], "ADMISSION_SHA")
    need(all(os.getenv(k) for k in KEYS) and not os.getenv("CTRADER_REFRESH_TOKEN") and
         not os.getenv("R3_CUSTODY_PRIVATE_KEY_PEM"), "ISOLATED_SECRETS")
    from m6.ctrader_capture import require_read_only_request
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
    from m6.ctrader_transport import StdlibCTraderTransport
    from research_core_v4.shallow_m5_support_v2_production import (
        authenticate_segment, encrypt_shard, public_spki_sha256)
    from research_core_v4.laboratory.mxm_be_new_october_m5_20261101 import (
        require_complete_bars, decode_bars)
    from research_core_v4.laboratory.mxm_be_new_pepperstone_bidask_20261101 import decode_side
    need(public_spki_sha256(PUB) == FINGERPRINT, "CUSTODY_KEY")
    cap = 6 + 2*op["slices"]
    class ReadOnly:
        def __init__(self, tr):
            self.tr, self.calls = tr, []
        def request(self, req, **opts):
            typ = type(req).__name__
            need(typ in WIRE and len(self.calls) < cap, "WIRE_ALLOWLIST")
            require_read_only_request(typ)
            self.calls.append(typ)
            result = self.tr.request(req, **opts)
            need(not isinstance(result, m.ProtoOAErrorRes), "BROKER_ERROR")
            return result
    tr = StdlibCTraderTransport(connect_timeout=15, response_timeout=30)
    bound = ReadOnly(tr)
    credentials = tuple(os.environ.pop(k) for k in KEYS)
    try:
        tr.connect()
        account = authenticate_segment(bound, *credentials)
        credentials = None
        need(len(bound.calls) == 3, "BROKER_ACCOUNT_AUTH")
        symbols = bound.request(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account, includeArchivedSymbols=False), timeout=25)
        found = [x for x in symbols.symbol if x.symbolName.upper() == op["symbol"]]
        need(len(found) == 1 and int(found[0].symbolId) > 0, "EXACT_SYMBOL")
        sid = int(found[0].symbolId)
        detail_req = m.ProtoOASymbolByIdReq(ctidTraderAccountId=account)
        detail_req.symbolId.extend([sid])
        detail = bound.request(detail_req, timeout=25)
        matches = [x for x in detail.symbol if int(x.symbolId) == sid]
        need(len(matches) == 1 and 1 <= int(matches[0].digits) <= 8, "PRICE_DIGITS")
        start, end = millis(op["start_utc"]), millis(op["end_utc"])
        bar_req = m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
            symbolId=sid, period=ProtoOATrendbarPeriod.Value("M5"),
            fromTimestamp=start, toTimestamp=end, count=op["max_bars"])
        bar_res = bound.request(bar_req, timeout=30)
        require_complete_bars(bar_res, op["max_bars"], account, sid)
        bars = decode_bars(bar_res.trendbar, int(matches[0].digits), start, end)
        need(8 <= len(bars) <= op["max_bars"] and
         all(row["available_no_earlier_than_utc_ms"] <= end for row in bars),
         "COMPLETE_M5_BARS")
        ticks, windows = [], []
        step = (end - start) // op["slices"]
        for i in range(op["slices"]):
            lo, hi = start+i*step, start+(i+1)*step
            counts = {}
            for typ, side in ((1, "bid"), (2, "ask")):
                response = bound.request(m.ProtoOAGetTickDataReq(
                    ctidTraderAccountId=account, symbolId=sid, type=typ,
                    fromTimestamp=lo, toTimestamp=hi), timeout=30)
                need(isinstance(response, m.ProtoOAGetTickDataRes) and
                     int(response.ctidTraderAccountId) == account and
                     not response.hasMore, "INCOMPLETE_TICK_SIDE")
                rows = [(t, p) for t, p in decode_side(response.tickData, lo, hi)
                        if lo <= t < hi]
                counts[side] = len(rows)
                ticks.extend({"t": t, "side": side, "raw": p} for t,p in rows)
                need(len(ticks) <= op["max_ticks"], "TICK_LIMIT")
            windows.append({"slice": i, "from_ms": lo, "to_ms_exclusive": hi,
                "bid_count": counts["bid"], "ask_count": counts["ask"]})
        need(len(bound.calls) == cap and len(ticks) >= 100 and
             sum(x["bid_count"] for x in windows) > 0 and
             sum(x["ask_count"] for x in windows) > 0, "BROKER_EVIDENCE")
        ticks.sort(key=lambda x: (x["t"], x["side"], x["raw"]))
        qb = b"".join(canon(x) + b"\n" for x in ticks)
        raw = canon({"operation_id": op["operation_id"], "broker": op["broker"],
            "symbol": op["symbol"], "start": op["start_utc"],
            "end": op["end_utc"], "ohlcv_m5": bars, "bidask": ticks})
        p = private()
        (p / "source.json").write_bytes(raw)
        (p / "quotes.ndjson").write_bytes(qb)
        request = csharp_feed(op, ticks, sha(qb))
        (p / "account-request.json").write_bytes(canon(request))
        out = output(op)
        out.mkdir(parents=True, exist_ok=False)
        encrypt_shard(raw, public_key=PUB, output=out / "original.mxmenc")
        manifest = dict(proof, source_plain_sha256=sha(raw),
            quotes_sha256=sha(qb), csharp_request_sha256=sha(canon(request)),
            encrypted_original_sha256=sha((out/"original.mxmenc").read_bytes()),
            broker=op["broker"], symbol=op["symbol"], start=op["start_utc"],
            end=op["end_utc"], bars=len(bars), ticks=len(ticks),
            slices=windows, wire_calls=bound.calls, orders=0,
            demo_orders=0, cloud_activations=0, alpha_certified=False,
            broker_costs_certified=False)
        (out/"manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2)+"\n")
        print("MXM_BROKER_READONLY_SOURCE " + json.dumps(
            {"original_sha256": sha(raw), "bars": len(bars),
             "ticks": len(ticks), "orders": 0}))
    finally:
        credentials = None
        for k in KEYS:
            os.environ.pop(k, None)
        tr.close()

def seal(file):
    context()
    need(not any(os.getenv(k) for k in KEYS), "COLD_NO_SECRETS")
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
    op = scope(file)
    p, out = private(), output(op)
    manifest = json.loads((out/"manifest.json").read_text())
    raw = (p/"source.json").read_bytes()
    need(sha(raw) == manifest["source_plain_sha256"], "ORIGINAL_HASH")
    original = json.loads(raw)
    need(original["operation_id"] == op["operation_id"] and
         original["broker"] == op["broker"] and
         original["symbol"] == op["symbol"], "SOURCE_ID")
    q = b"".join(canon(x)+b"\n" for x in original["bidask"])
    need(q == (p/"quotes.ndjson").read_bytes() and
         sha(q) == manifest["quotes_sha256"], "ORIGINAL_TO_QUOTES")
    request = (p/"account-request.json").read_bytes()
    need(sha(request) == manifest["csharp_request_sha256"], "REQUEST_HASH")
    need(canon(csharp_feed(op, original["bidask"], sha(q))) == request,
         "REGENERATED_ORIGINAL_TO_CSHARP_EVENTS")
    x = json.loads(request)
    need(x["SourceSha256"] == sha(q) and x["ExpectedOrdinal"] == 0 and
         x["PriorSha256"] is None and
         x["Parameters"]["MaxMarginFraction"] <= .4 and
         x["Parameters"]["MaxEstimatedStopRiskFraction"] <= .01 and
         x["Parameters"]["MinimumFreeMarginReserveEur"] >= 120 and
         x["Parameters"]["NativeSizingScenarioSha256"], "CASH_AND_SOURCE_CONTRACT")
    report = (p/"account-report.json").read_bytes()
    result = json.loads(report)
    need(result["Schema"] == "mxm.shared-funded-account.result.v1" and
         result["SourceSha256"] == sha(q) and
         result["NextEventOrdinal"] == len(x["Events"]) and
         result["Orders"] == 0 and result["Cloud"] is False and
         result["BrokerFillsProven"] is False and
         result["HistoricalCostsProven"] is False, "ACTUAL_CSHARP_EVENT_CHAIN")
    a = result["Account"]
    need(a["InitialCapitalEur"] == 200 and a["UsedMarginEur"] <= 80 and
         a["OpenPositions"] == 0 and a["Hard21Proven"] is False and
         a["CostsBrokerVerified"] is False, "ONE_FUNDED_EUR200_MODEL")
    cash, entries, exits = Decimal("200"), 0, 0
    for e in a["Ledger"]:
        fee = Decimal(str(e["CommissionEur"]))
        if e["Kind"] == "ENTRY":
            need(Decimal(str(e["Units"])) == 1000 and
                 cash-fee-Decimal("50") >= Decimal("120"), "OWNER_ENTRY_RESERVE")
            cash -= fee
            entries += 1
        elif e["Kind"] == "EXIT":
            cash += Decimal(str(e["GrossEur"])) - fee
            exits += 1
        else:
            need(False, "CASH_EVENT_KIND")
        need(abs(cash-Decimal(str(e["CashEur"]))) <= Decimal("0.00002"),
             "COLD_LEDGER_MISMATCH")
    need(entries == a["AcceptedEntries"] and exits == a["ExecutedExits"] and
         abs(cash-Decimal(str(a["FinalCashEur"]))) <= Decimal("0.00002"),
         "COLD_FINAL_CASH")
    need(all(Decimal(str(z["UsedMarginEur"])) <= 80 for z in result["Observations"]),
         "TOTAL_ACCOUNT_MARGIN")
    encrypt_shard(report, public_key=PUB, output=out/"csharp-account.mxmenc")
    manifest.update(csharp_report_sha256=sha(report),
        csharp_report_encrypted_sha256=sha((out/"csharp-account.mxmenc").read_bytes()),
        original_to_csharp_sha_verified=True, cold_cash_reconciled=True,
        csharp_events=result["NextEventOrdinal"], entries=entries, exits=exits,
        final_model_cash_eur=a["FinalCashEur"])
    (out/"manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2)+"\n")
    print("MXM_ORIGINAL_TO_CSHARP_COLD_LEDGER_VERIFIED " + json.dumps({
        "events":result["NextEventOrdinal"], "entries":entries, "exits":exits,
        "final_model_cash_eur":a["FinalCashEur"]}))

if __name__ == "__main__":
    need(len(sys.argv) == 3 and sys.argv[1] in ("admit", "collect", "seal"), "CLI")
    {"admit": lambda: admit(),
     "collect": lambda: collect(sys.argv[2]),
     "seal": lambda: seal(sys.argv[2])}[sys.argv[1]]()
