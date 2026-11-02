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
         not os.getenv("R3_CUSTODY_PRIVATE_KEY_PEM"),"NO_BROKER_OR_CUSTODY_SECRETS_IN_CSHARP")
    p=private_dir()
    pub=json.loads((OUT/"source-public.json").read_text())
    quotes=(p/"quotes.ndjson").read_bytes()
    need(sha(quotes)==pub["csharp_input_ndjson_sha256"],"SOURCE_TO_CSHARP_SHA_BIND")
    raw=(p/"csharp"/"reference-report.json").read_bytes()
    report=json.loads(raw)
    model=report["modeled_assumptions"]
    need(report["schema"]=="mxm.csharp.reference-replay.v1" and
         report["initial_equity_eur"]==200 and
         report["raw_events"]==pub["bidask_events"] and
         model["position_units"]==1000 and model["margin_eur"]<=80 and
         model["minimum_free_margin_reserve_eur"]>=120 and
         0<model["max_estimated_account_stop_risk_fraction"]<=.01 and
         model["max_margin_fraction_of_free_margin"]<=.4 and
         report["cTrader_native_backtest"] is False and
         report["pepperstone_historical_fills_proven"] is False,
         "OWNER_CAPITAL_OR_CAUSAL_SOURCE_NOT_BOUND")
    # Cold verify the exact event cash ledger independently of CSharp without
    # re-running its signal policy or using market prices for selection.
    from decimal import Decimal
    cash=Decimal("200")
    open_positions=0
    for ev in report["ledger"]:
        commission=Decimal(str(ev["charged_commission_eur"]))
        if ev["kind"]=="ENTRY":
            need(open_positions==0 and Decimal(str(ev["margin_eur"]))<=80,
                 "POSITION_OR_MARGIN_VIOLATION")
            need(cash-commission-Decimal(str(ev["margin_eur"]))>=120,
                 "OWNER_FREE_RESERVE_ENTRY_VIOLATION")
            cash-=commission;open_positions=1
        elif ev["kind"]=="EXIT":
            need(open_positions==1,"UNMATCHED_EXIT")
            cash+=Decimal(str(ev["gross_price_pnl_eur"]))-commission
            open_positions=0
        else:need(False,"UNRECOGNIZED_LEDGER_EVENT")
        need(abs(cash-Decimal(str(ev["balance_eur"])))<Decimal("0.00003"),
             "INDEPENDENT_CSHARP_CASH_MISMATCH")
    need(open_positions==0 and
         abs(cash-Decimal(str(report["final_equity_eur"])))<Decimal("0.00003"),
         "CONTINUOUS_ACCOUNT_RECONCILIATION")
    need(report["economic_entries"]==report["economic_exits"]==
         sum(1 for e in report["ledger"] if e["kind"]=="ENTRY"),
         "ENTRY_EXIT_COUNT")
    # CSharp completed-bar decisions must not precede the authentic M5 bar close.
    bars=json.loads((p/"bars.json").read_text())["bars"]
    available={row["available_no_earlier_than_utc_ms"] for row in bars}
    for signal in report["causal_signals"]:
        need(signal["decision_ms"] in available,
             "DECISION_WITHOUT_CLOSED_NATIVE_M5_BAR")
    encrypt_shard(raw,public_key=PUB,output=OUT/"csharp-ledger.mxmenc")
    pub["csharp_report_plain_sha256"]=sha(raw)
    pub["csharp_report_cipher_sha256"]=sha((OUT/"csharp-ledger.mxmenc").read_bytes())
    pub["cold_cash_reconciled"]=True
    pub["csharp_entries"]=report["economic_entries"]
    pub["csharp_exits"]=report["economic_exits"]
    pub["csharp_decisions"]=report["bar_decisions"]
    pub["final_model_equity_eur"]=report["final_equity_eur"]
    pub["model_is_not_broker_execution"]=True
    pub["owner_qualification"]="SOURCE_TO_EXISTING_CSHARP_EXECUTED_DEVELOPMENT_ONLY"
    (OUT/"source-public.json").write_text(json.dumps(pub,sort_keys=True,indent=2)+"\n")
    print("MXM_OWNER_R3_AUTHENTIC_TO_EXISTING_CSHARP_COLD_RECONCILED "+json.dumps({
        "source_sha256":pub["source_plain_sha256"],
        "csharp_report_sha256":sha(raw),"economic_entries":report["economic_entries"],
        "account_final_model_eur":report["final_equity_eur"],
        "no_orders":True},sort_keys=True),flush=True)

if __name__=="__main__":
    import sys
    need(len(sys.argv)==2 and sys.argv[1] in ("selftest","source","seal"),"CLI")
    {"selftest":selftest,"source":source,"seal":seal}[sys.argv[1]]()
