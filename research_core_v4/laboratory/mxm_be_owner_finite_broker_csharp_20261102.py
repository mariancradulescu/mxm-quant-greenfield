"""Owner-approved ONE finite Pepperstone LIVE VIEW-only new M5+BIDASK -> existing CSharp replay.
A source reception and CSharp capital integration check, not a scientific alpha trial.
The old first-only workflows and their historical source identities are untouched.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from decimal import Decimal
from m6.ctrader_capture import require_read_only_request
from m6.ctrader_proto import OpenApiMessages_pb2 as m
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import StdlibCTraderTransport
from research_core_v4.shallow_m5_support_v2_production import (
    authenticate_segment,encrypt_shard,public_spki_sha256)
from research_core_v4.laboratory.mxm_be_new_october_m5_20261101 import (
    require_complete_bars,decode_bars)
from research_core_v4.laboratory.mxm_be_new_pepperstone_bidask_20261101 import decode_side

REPO="mariancradulescu/mxm-quant-greenfield"
BRANCH="mxm-remediation-p0-p4-20261015-v1"
WORKFLOW="mxm-be-owner-finite-r3-source-csharp-20261102.yml"
SYMBOL="EURUSD"
START="2026-11-02T03:00:00Z"
END="2026-11-02T05:00:00Z"
SLICES=4
AUTH=("ProtoOAApplicationAuthReq","ProtoOAGetAccountListByAccessTokenReq","ProtoOAAccountAuthReq")
ALLOWED=AUTH+("ProtoOASymbolsListReq","ProtoOASymbolByIdReq",
              "ProtoOAGetTrendbarsReq","ProtoOAGetTickDataReq")
MAX_REQUESTS=3+1+1+1+2*SLICES
SECRETS=("R3_CTRADER_CLIENT_ID","R3_CTRADER_CLIENT_SECRET","R3_CTRADER_ACCESS_TOKEN")
PUB=Path("research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem")
PUB_FP="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"
OUT=Path("verification/mxm-be-owner-finite-r3-source-csharp-20261102")
def need(x,reason):
    if not x:raise ValueError("MXM_BE_OWNER_R3_"+reason)
def ms(s):
    v=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    need(v.tzinfo is not None and v.utcoffset()==dt.timedelta(0),"UTC")
    return int(v.timestamp()*1000)
def sha(data):return hashlib.sha256(data).hexdigest()
def private_dir():
    r=os.environ.get("RUNNER_TEMP")
    need(bool(r),"NO_RUNNER_TEMP")
    return Path(r)/"mxm-be-owner-r3-finite"

class ReadOnly:
    def __init__(self,tr):self.tr=tr;self.requests=[]
    def request(self,req,**kw):
        name=type(req).__name__
        need(name in ALLOWED and len(self.requests)<MAX_REQUESTS,"WIRE_ALLOWLIST")
        require_read_only_request(name)
        self.requests.append(name)
        ans=self.tr.request(req,**kw)
        need(not isinstance(ans,m.ProtoOAErrorRes),"BROKER_RESPONSE_ERROR")
        return ans

def selftest():
    need(SYMBOL=="EURUSD" and START=="2026-11-02T03:00:00Z" and
         END=="2026-11-02T05:00:00Z" and SLICES==4 and
         MAX_REQUESTS==14,"FIXED_ONE_SOURCE_IDENTITY")
    need(ms(END)-ms(START)==7200000,"TWO_HOURS")
    need("ProtoOANewOrderReq" not in ALLOWED and
         "ProtoOAClosePositionReq" not in ALLOWED and
         "ProtoOASubscribeSpotsReq" not in ALLOWED,"NO_TRADING_OR_SUBSCRIPTIONS")
    for name in ALLOWED:require_read_only_request(name)
    need(public_spki_sha256(PUB)==PUB_FP,"IMMUTABLE_PUBLIC_RECIPIENT")
    need(ProtoOATrendbarPeriod.Value("M5")>=0,"M5_NATIVE_ENUM")
    class T:
        def __init__(self,t,p):self.timestamp=t;self.tick=p
    start=ms(START)
    x=decode_side([T(start+4000,100005),T(-2000,-1)],start,start+5000)
    need(x==[(start+2000,100004),(start+4000,100005)],"NATIVE_SIGNED_DELTA")
    need(all((start+i*1800000)%300000==0 for i in range(5)),
         "COMPLETE_BAR_ALIGNMENT")
    print("MXM_OWNER_FINITE_R3_SOURCE_BLIND_SCOPE_PASS")


def iso_ms(t):
    return dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00","Z")

# A fixed scheduled EUR200 accounting bridge, not a new alpha hypothesis.
# The two decisions and the risk/fee model are fixed before live source access;
# never infer the decision from price movement or hindsight.
POLICY_BYTES=b"MXM-OWNER-20261102-EURUSD-FIXED-0320-LONG-0340-FLAT-READONLY-CASH-BRIDGE"
SIZING_BYTES=b"MXM-OWNER-20261102-1000UNITS-50EURMARGIN-120EURRESERVE-1PCTSTOP-READONLY"
POLICY_SHA=sha(POLICY_BYTES)
SIZING_SHA=sha(SIZING_BYTES)
DECISIONS=((ms("2026-11-02T03:20:00Z"),1),
           (ms("2026-11-02T03:40:00Z"),0))
def csharp_request(ticks,raw_sha):
    need(len(ticks)>0 and len(DECISIONS)==2,"FIXED_CSHARP_SOURCE")
    events=[]
    bid=ask=None; tb=ta=None
    seen=set()
    # Broker-native sampled sides are paired at or after their last source times,
    # never used as fictitious synchronous exchange quotes.
    from itertools import groupby
    for t,stream in groupby(ticks,key=lambda x:x["t"]):
        items=list(stream)
        bvalues={x["raw"] for x in items if x["side"]=="bid"}
        avalues={x["raw"] for x in items if x["side"]=="ask"}
        if len(bvalues)>1 or len(avalues)>1:continue
        if bvalues:bid=next(iter(bvalues));tb=t
        if avalues:ask=next(iter(avalues));ta=t
        if bid is None or ask is None or bid<=0 or ask<=bid:continue
        if t-tb>5000 or t-ta>5000:continue
        if t in seen:continue
        seen.add(t)
        qbid=round(bid/100000,5);qask=round(ask/100000,5)
        events.append({"$feed":"quote","Utc":iso_ms(t),"Symbol":SYMBOL,
          "Bid":qbid,"Ask":qask,"QuoteToEur":round(1/qask,12),
          "QuoteLossToEur":round(1/qbid,12),"ExecutableUnits":1000,
          "InitialMarginEur":50,"CommissionPerSideEur":0.03,
          "SlipPerSideQuote":0.00002,"EstimatedStopRiskEur":1.2,
          "StopDistanceQuote":0.0012,"BidSourceUtc":iso_ms(tb),
          "AskSourceUtc":iso_ms(ta),
          "NativeSizingScenarioSha256":SIZING_SHA,
          "BrokerVolumeMinUnits":1000,"BrokerVolumeMaxUnits":1000,
          "BrokerVolumeStepUnits":1000})
    for i,(t,side) in enumerate(DECISIONS,1):
        events.append({"$feed":"explicit-decision","Utc":iso_ms(t),
          "Symbol":SYMBOL,"Sequence":i,"Desired":side,
          "ValidFromUtc":iso_ms(t+1),"ExpiresUtc":iso_ms(t+240000),
          "PolicySha256":POLICY_SHA})
    events.sort(key=lambda x:(x["Utc"],0 if x["$feed"]=="explicit-decision" else 1))
    need(len(events)>=100 and
         sum(x["$feed"]=="explicit-decision" for x in events)==2 and
         len(events)<100000,"BOUNDED_NATIVE_CSHARP_FEED")
    return {"Schema":"mxm.shared-funded-account.request.v1",
      "SourceSha256":raw_sha,"Symbols":[SYMBOL],
      "Parameters":{"Strategy":0,"MaxMarginFraction":0.4,
        "MaxPositions":1,"MinimumFreeMarginReserveEur":120,
        "MaxEstimatedStopRiskFraction":0.01,"RoundTripRiskReserveEur":0.2,
        "BarMinutes":5,"MaxQuoteAgeSeconds":300,
        "ExplicitPolicySha256":POLICY_SHA,
        "NativeSizingScenarioSha256":SIZING_SHA},
      "ExpectedOrdinal":0,"PriorSha256":None,"Events":events}

def source():
    selftest()
    need(os.getenv("GITHUB_REPOSITORY")==REPO and
         os.getenv("GITHUB_REF")=="refs/heads/"+BRANCH and
         os.getenv("GITHUB_EVENT_NAME")=="push" and
         os.getenv("GITHUB_RUN_ATTEMPT")=="1" and
         os.getenv("GITHUB_JOB")=="first-official-original-and-csharp",
         "OFFICIAL_FIRST_PUSH_ONLY")
    need(all(os.getenv(x) for x in SECRETS) and
         not os.getenv("R3_CUSTODY_PRIVATE_KEY_PEM") and
         not os.getenv("CTRADER_REFRESH_TOKEN"),"ISOLATED_READONLY_SECRETS")
    vals=tuple(os.environ.pop(x) for x in SECRETS)
    tr=StdlibCTraderTransport(connect_timeout=15,response_timeout=30)
    bound=ReadOnly(tr)
    try:
        tr.connect()
        account=authenticate_segment(bound,*vals)
        vals=None
        need(bound.requests==list(AUTH),"AUTHORIZED_LIVE_VIEW_AUTH")
        sym=bound.request(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),timeout=25)
        need(isinstance(sym,m.ProtoOASymbolsListRes),"SYMBOL_LIST")
        found=[s for s in sym.symbol if str(s.symbolName).upper()==SYMBOL]
        need(len(found)==1 and int(found[0].symbolId)>0,"UNIQUE_EURUSD")
        sid=int(found[0].symbolId)
        req=m.ProtoOASymbolByIdReq(ctidTraderAccountId=account)
        req.symbolId.extend([sid])
        detail=bound.request(req,timeout=25)
        need(isinstance(detail,m.ProtoOASymbolByIdRes),"SYMBOL_DETAILS")
        full=[s for s in detail.symbol if int(s.symbolId)==sid]
        need(len(full)==1 and 1<=int(full[0].digits)<=8,"NATIVE_PRICE_DIGITS")
        precision=int(full[0].digits)
        start,end=ms(START),ms(END)
        bars_req=m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
            symbolId=sid,period=ProtoOATrendbarPeriod.Value("M5"),
            fromTimestamp=start,toTimestamp=end,count=5000)
        bar_res=bound.request(bars_req,timeout=30)
        require_complete_bars(bar_res,5000,account,sid)
        bars=decode_bars(bar_res.trendbar,precision,start,end)
        need(len(bars)>=18 and all(
            row["available_no_earlier_than_utc_ms"]<=end for row in bars),
            "INCOMPLETE_AUTHENTIC_M5_SUPPORT")
        ticks=[];boundaries=[]
        chunk=(end-start)//SLICES
        for i in range(SLICES):
            a=start+i*chunk;b=a+chunk
            counts={}
            for typ,side in ((1,"bid"),(2,"ask")):
                req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                    symbolId=sid,type=typ,fromTimestamp=a,toTimestamp=b)
                answer=bound.request(req,timeout=30)
                need(isinstance(answer,m.ProtoOAGetTickDataRes) and
                     int(answer.ctidTraderAccountId)==account and not answer.hasMore,
                     "TRUNCATED_OR_WRONG_TICK_SIDE")
                decoded=decode_side(answer.tickData,a,b)
                included=[(t,p) for t,p in decoded if a<=t<b]
                counts[side]=len(included)
                ticks.extend({"t":t,"side":side,"raw":p} for t,p in included)
            boundaries.append({"slice":i,"from_ms":a,"to_ms_exclusive":b,
                               "bid_events":counts["bid"],"ask_events":counts["ask"]})
        need(len(bound.requests)==MAX_REQUESTS and
             len(ticks)>=100 and
             sum(x["bid_events"] for x in boundaries)>0 and
             sum(x["ask_events"] for x in boundaries)>0,
             "MISSING_OR_EXCESS_BROKER_EVIDENCE")
        # Identical duplicate boundary quotes can be deduplicated; conflicts remain
        # in the native existing CSharp uncertainty accounting, never reordered as fills.
        ticks.sort(key=lambda x:(x["t"],x["side"],x["raw"]))
        lines=b"".join(json.dumps(row,separators=(",",":"),sort_keys=True).encode()+b"\n" for row in ticks)
        raw=json.dumps({"symbol":SYMBOL,"source":"PEPPERSTONE_EUROPE_LIVE_VIEW_OPENAPI",
             "start":START,"end":END,"ohlcv_m5":bars,"bidask":ticks},
             sort_keys=True,separators=(",",":")).encode()
        p=private_dir()
        p.mkdir(parents=True,exist_ok=False)
        (p/"quotes.ndjson").write_bytes(lines)
        request=csharp_request(ticks,sha(lines))
        (p/"account-request.json").write_text(json.dumps(request,separators=(",",":"),sort_keys=True))
        (p/"csharp").mkdir()
        (p/"bars.json").write_text(json.dumps(
             {"symbol":SYMBOL,"bars":bars},sort_keys=True))
        OUT.mkdir(parents=True,exist_ok=False)
        encrypt_shard(raw,public_key=PUB,output=OUT/"original.mxmenc")
        public={
          "schema":"mxm.be.owner.onefinite-r3-to-existing-csharp.v1",
          "classification":"AUTHENTIC_NEW_READONLY_SOURCE_NOT_ECONOMIC_CERTIFICATION",
          "broker":"PEPPERSTONE_EUROPE_LIVE_VIEW",
          "account_authenticated_by_existing_R3_segment":True,
          "window_start_utc":START,"window_end_utc":END,
          "native_m5_bars":len(bars),"bidask_events":len(ticks),
          "bounded_slices":boundaries,"wire_requests":bound.requests,
          "source_plain_sha256":sha(raw),
          "csharp_input_ndjson_sha256":sha(lines),
          "csharp_account_request_sha256":sha((p/"account-request.json").read_bytes()),
          "fixed_account_policy_sha256":POLICY_SHA,
          "fixed_account_sizing_sha256":SIZING_SHA,
          "csharp_feed_events":len(request["Events"]),
          "encrypted_source_sha256":sha((OUT/"original.mxmenc").read_bytes()),
          "orders":0,"demo_orders":0,"cloud_activations":0,
          "full_independent_alpha_confirmation":False,
          "historical_fills_or_swap_or_slippage_certified":False}
        (OUT/"source-public.json").write_text(json.dumps(public,sort_keys=True,indent=2)+"\n")
        print("MXM_OWNER_R3_AUTHENTIC_FINITE_SOURCE "+json.dumps({
          "ohlcv_bars":len(bars),"bidask_events":len(ticks),
          "source_sha256":public["source_plain_sha256"],
          "input_sha256":public["csharp_input_ndjson_sha256"],
          "broker_orders":0},sort_keys=True),flush=True)
    finally:
        vals=None
        for key in SECRETS:os.environ.pop(key,None)
        tr.close()


def seal():
    need(os.getenv("GITHUB_REPOSITORY")==REPO and
         os.getenv("GITHUB_REF")=="refs/heads/"+BRANCH and
         os.getenv("GITHUB_RUN_ATTEMPT")=="1","OFFICIAL_SEAL_ONLY")
    need(not any(os.getenv(x) for x in SECRETS) and
         not os.getenv("R3_CUSTODY_PRIVATE_KEY_PEM"),"ISOLATED_NO_SECRETS")
    p=private_dir()
    pub=json.loads((OUT/"source-public.json").read_text())
    quotes=(p/"quotes.ndjson").read_bytes()
    need(sha(quotes)==pub["csharp_input_ndjson_sha256"],"SOURCE_INPUT_SHA_BIND")
    request_bytes=(p/"account-request.json").read_bytes()
    need(sha(request_bytes)==pub["csharp_account_request_sha256"],"ACCOUNT_REQUEST_SHA_BIND")
    request=json.loads(request_bytes)
    need(request["SourceSha256"]==pub["csharp_input_ndjson_sha256"] and
         request["ExpectedOrdinal"]==0 and request["PriorSha256"] is None,
         "ONE_ACCOUNT_FRESH_ONLY")
    prm=request["Parameters"]
    need(prm["MaxMarginFraction"]<=.4 and prm["MaxPositions"]==1 and
         prm["MinimumFreeMarginReserveEur"]>=120 and
         prm["MaxEstimatedStopRiskFraction"]<=.01 and
         prm["ExplicitPolicySha256"]==POLICY_SHA and
         prm["NativeSizingScenarioSha256"]==SIZING_SHA,"OWNER_RISK_CAPITAL_CONTRACT")
    raw=(p/"csharp"/"account-report.json").read_bytes()
    x=json.loads(raw)
    need(x["Schema"]=="mxm.shared-funded-account.result.v1" and
         x["SourceSha256"]==pub["csharp_input_ndjson_sha256"] and
         x["ExpectedOrdinal"]==0 and
         x["NextEventOrdinal"]==len(request["Events"]) and
         x["Orders"]==0 and x["BrokerFillsProven"] is False and
         x["HistoricalCostsProven"] is False and x["Cloud"] is False,
         "EXISTING_CSHARP_SOURCE_TO_ACCOUNT_BIND")
    a=x["Account"]
    need(a["InitialCapitalEur"]==200 and
         a["UsedMarginEur"]<=80 and a["CompleteIsoUtcWeeks"]==0 and
         a["Hard21Proven"] is False and
         a["CostsBrokerVerified"] is False and
         a["BrokerFillsProven"] is False,"UNFUNDED_OR_MISLABELED_ACCOUNT")
    cash=Decimal("200")
    entries=exits=0
    for e in a["Ledger"]:
        kind=e["Kind"]
        fee=Decimal(str(e["CommissionEur"]))
        if kind=="ENTRY":
            need(Decimal(str(e["Units"]))==1000 and fee>=0 and
                 cash-fee-Decimal("50")>=Decimal("120"),
                 "OWNER_ENTRY_RESERVE_AND_BROKER_VOLUME_SCENARIO")
            cash-=fee;entries+=1
        elif kind=="EXIT":
            cash+=Decimal(str(e["GrossEur"]))-fee;exits+=1
        else:need(False,"UNAUTHORIZED_CASH_EVENT")
        need(abs(cash-Decimal(str(e["CashEur"])))<=Decimal("0.00002"),
             "INDEPENDENT_NATIVE_LEDGER_CASH_MISMATCH")
    need(entries==a["AcceptedEntries"] and exits==a["ExecutedExits"] and
         a["OpenPositions"]==0 and
         abs(cash-Decimal(str(a["FinalCashEur"])))<=Decimal("0.00002"),
         "CONTINUOUS_SINGLE_EUR200_CASH_CHECK")
    need(all(Decimal(str(z["UsedMarginEur"]))<=80 for z in x["Observations"]),
         "ACTUAL_CSHARP_ACCOUNT_MARGIN_CAP")
    encrypt_shard(raw,public_key=PUB,output=OUT/"csharp-account.mxmenc")
    pub.update({
      "csharp_account_report_plain_sha256":sha(raw),
      "csharp_account_report_encrypted_sha256":sha((OUT/"csharp-account.mxmenc").read_bytes()),
      "existing_csharp_shared_funded_account_executed":True,
      "cold_cash_reconciled":True,
      "csharp_account_events":x["NextEventOrdinal"],
      "csharp_entries":entries,"csharp_exits":exits,
      "final_cash_eur_model":a["FinalCashEur"],
      "owner_qualification":"AUTHENTIC_SOURCE_TO_EXISTING_CSHARP_DEVELOPMENT_ONLY",
      "full_independent_alpha_confirmation":False})
    (OUT/"source-public.json").write_text(json.dumps(pub,sort_keys=True,indent=2)+"\n")
    print("MXM_OWNER_R3_AUTHENTIC_SOURCE_TO_EXISTING_SHARED_CSHARP_RECONCILED "+json.dumps({
      "source_sha256":pub["source_plain_sha256"],
      "csharp_account_report_sha256":sha(raw),
      "account_events":x["NextEventOrdinal"],"entries":entries,
      "exits":exits,"final_cash_eur_model":a["FinalCashEur"],
      "orders":0},sort_keys=True),flush=True)

if __name__=="__main__":
    import sys
    need(len(sys.argv)==2 and sys.argv[1] in ("selftest","source","seal"),"CLI")
    {"selftest":selftest,"source":source,"seal":seal}[sys.argv[1]]()
