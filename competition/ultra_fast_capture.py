"""Compact read-only friction qualification + 13-week M5 Stage-A capture."""
from __future__ import annotations
import csv,hashlib,json,math,shutil,statistics,time,zipfile
from collections import defaultdict
from datetime import date,datetime,time as dtime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from google.protobuf.json_format import MessageToDict
from m6.ctrader_capture import CaptureContractError,MappingError,account_fingerprint,atomic_write_json,live_account_candidates,redact_text,require_read_only_request,scan_bundle_for_secrets,select_live_pepperstone_account
from m6.cost_evidence import decode_ctrader_tick_page,next_tick_page_to_ms,causal_merge_bid_ask
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAAccountAuthReq,ProtoOAApplicationAuthReq,ProtoOAAssetListReq,ProtoOAGetAccountListByAccessTokenReq,ProtoOAGetTickDataReq,ProtoOAGetTrendbarsReq,ProtoOASymbolByIdReq,ProtoOASymbolsListReq,ProtoOATraderReq
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import LIVE_HOST,LIVE_PORT,StdlibCTraderTransport
from competition.frontier_data_capture import normalize_m5

PLAN_REL="data/COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V1.json"
PROTOCOL_REL="data/COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V1.json"
EXPECTED_PLAN_SHA="6197e26eb505f35e921ae3fe020f3c7010cb3b5b31a5055153e25327eaefc384"
OUTPUT_FILENAME="MXM_COMPETITION_ULTRA_FAST_STAGE_A_V1.zip"
TOOL_VERSION="MXM_COMPETITION_ULTRA_FAST_ANDROID_STDLIB_V1"
QUOTE_TYPES={"BID":1,"ASK":2}; RAW_HEADER=("time_utc","open","high","low","close","tick_volume"); MIN_INTERVAL=1/4.7

def _plain(m):return MessageToDict(m,preserving_proto_field_name=False,use_integers_for_enums=True)
def _utc(s):
    x=datetime.fromisoformat(s[:-1]+"+00:00" if s.endswith("Z") else s)
    if x.tzinfo is None or x.utcoffset()!=timedelta(0):raise CaptureContractError("explicit UTC required")
    return x.astimezone(timezone.utc)
def _iso(x):return x.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
def _ms(x):return int(x.timestamp()*1000)
def _sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def _canon(o):return hashlib.sha256(json.dumps({k:v for k,v in o.items() if k!="plan_sha256"},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def margin_pct_eur200(v):return float(Decimal(str(v))/Decimal("2"))
def validate_plan(plan,protocol):
    if plan.get("schema")!="mxm.greenfield.v2.ultra-fast-competition-capture-plan.v1" or plan.get("status")!="FROZEN_PRE_CAPTURE_PRE_OUTCOME":raise CaptureContractError("invalid ultra-fast plan authority")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or _canon(plan)!=EXPECTED_PLAN_SHA:raise CaptureContractError("ultra-fast plan hash mismatch")
    if protocol.get("status")!="FROZEN_PRE_FRICTION_PRE_STAGE_A_OUTCOME":raise CaptureContractError("ultra-fast protocol not frozen")
    if len(plan.get("shortlist") or [])!=32 or plan.get("max_stage_a_markets")!=12:raise CaptureContractError("unexpected shortlist/Stage-A cap")
    if any(abs(margin_pct_eur200(x["accepted_min_margin_eur"])-float(x["accepted_min_margin_pct_eur200"]))>1e-9 for x in plan["shortlist"]):raise CaptureContractError("factor-100 margin regression")
    if plan.get("economic_outcomes_opened") or plan.get("v2_attempts_consumed") or plan.get("protected_evidence_opened") is not False:raise CaptureContractError("capture plan economically contaminated")
    return True

def _q(xs,q):
    xs=sorted(float(x) for x in xs)
    if not xs:return None
    p=(len(xs)-1)*q;a=int(math.floor(p));b=int(math.ceil(p))
    return xs[a] if a==b else xs[a]+(xs[b]-xs[a])*(p-a)
def _med(xs):return statistics.median(xs) if xs else None
def _window(ds,start,end,label):
    d=date.fromisoformat(ds);a=datetime.combine(d,dtime.fromisoformat(start),timezone.utc);b=datetime.combine(d,dtime.fromisoformat(end),timezone.utc)
    return {"label":label,"from_ms":_ms(a),"to_ms":_ms(b),"start_utc":_iso(a),"end_utc":_iso(b)}
def friction_windows(protocol,profile):
    p=protocol["friction_screen"]["profiles"]
    if profile in {"GLOBAL_24X5","US_REGIONAL"}:
        z=p[profile];return [_window(d,w["start"],w["end"],w["label"]) for d in z["sample_dates"] for w in z["utc_windows"]]
    if profile=="CRYPTO_24X7":
        out=friction_windows(protocol,"GLOBAL_24X5")
        for ds in p["GLOBAL_24X5"]["sample_dates"]:
            d=date.fromisoformat(ds);mon=d-timedelta(days=d.weekday())
            for w in p[profile]["weekend_windows_per_week"]:
                x=mon+timedelta(days=5 if w["weekday"]=="SATURDAY" else 6);out.append(_window(x.isoformat(),w["start"],w["end"],w["label"]))
        return sorted(out,key=lambda x:(x["from_ms"],x["label"]))
    raise CaptureContractError("unknown friction profile")
def qualify_friction(m,rules):
    def ok(r):return m.get("two_sided_window_coverage",0)>=r["min_two_sided_window_coverage"] and m.get("quote_state_count",0)>=r["min_quote_states"] and (m.get("median_m5_range") or 0)>0 and (m.get("p75_spread_over_median_range") or math.inf)<=r["max_p75_spread_over_median_m5_range"] and (m.get("p95_spread_over_median_range") or math.inf)<=r["max_p95_spread_over_median_m5_range"] and (m.get("median_spread_over_mid") or math.inf)<=r["max_median_spread_over_mid"]
    if ok(rules["FRICTION_PASS"]):return "FRICTION_PASS"
    if ok(rules["FRICTION_WATCH"]):return "FRICTION_WATCH"
    return "FRICTION_FAIL"
def _rank(x):
    tier={"FRICTION_PASS":0,"FRICTION_WATCH":1}.get(x.get("friction_state"),2);move=x.get("movement_to_effective_p75_friction") or x.get("movement_to_p75_spread") or 0
    return (tier,-float(move),float(x["accepted_min_margin_pct_eur200"]),-float(x["schedule_minutes_per_week"]),float(x.get("p95_spread_over_median_range") or math.inf),x["broker_symbol"])
def select_stage_a(results,law):
    by=defaultdict(list)
    for x in results:
        if x["friction_state"]=="FRICTION_PASS" or (x["friction_state"]=="FRICTION_WATCH" and float(x.get("movement_to_p75_spread") or 0)>=2):by[x["family"]].append(x)
    for xs in by.values():xs.sort(key=_rank)
    chosen=[];variants=set();counts=defaultdict(int)
    def add(x):
        if x["variant_family"] in variants:return False
        chosen.append(x);variants.add(x["variant_family"]);counts[x["family"]]+=1;return True
    for fam,quota in law["family_target_quotas"].items():
        for x in by.get(fam,[]):
            if counts[fam]>=quota:break
            add(x)
    pool=sorted([x for xs in by.values() for x in xs if x["friction_state"]=="FRICTION_PASS"],key=_rank)
    for x in pool:
        if len(chosen)>=law["max_stage_a_markets"]:break
        if x in chosen or counts[x["family"]]>=4:continue
        add(x)
    return chosen[:law["max_stage_a_markets"]],{f:[x["broker_symbol"] for x in xs if x not in chosen] for f,xs in by.items()}

def _commission(full,asset_names,mid,minvol):
    rate=float(full.get("preciseTradingCommissionRate") or 0)/1e8;minimum=float(full.get("preciseMinCommission") or 0)/1e8;lot=float(full.get("lotSize") or 0);lots=minvol/lot if lot else None
    one=max(rate*(lots or 0),minimum);rt=2*one;quote=asset_names.get(str(full.get("quoteAssetId")));base=asset_names.get(str(full.get("baseAssetId")));ca=asset_names.get(str(full.get("minCommissionAsset")));units=minvol/100
    qcost=None;status="UNRESOLVED_CROSS_CURRENCY_COMMISSION"
    if ca==quote:qcost=rt;status="RESOLVED_SAME_AS_QUOTE"
    elif ca=="USD" and quote=="USD":qcost=rt;status="RESOLVED_USD_QUOTE"
    elif ca=="USD" and base=="USD" and mid:qcost=rt*mid;status="RESOLVED_USD_BASE_VIA_MID"
    return {"commission_rate_per_lot":rate,"minimum_commission":minimum,"commission_asset":ca,"base_asset":base,"quote_asset":quote,"approx_roundtrip_commission":rt,"approx_roundtrip_commission_quote":qcost,"approx_roundtrip_commission_price_equivalent":qcost/units if qcost is not None and units else None,"commission_conversion_status":status,"pnl_conversion_fee_rate":full.get("pnlConversionFeeRate")}

class UltraFastCaptureRunner:
    def __init__(self,*,plan,protocol,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan,protocol);self.plan=dict(plan);self.protocol=dict(protocol);self.client_id=client_id;self.client_secret=client_secret;self.access_token=access_token;self.config=dict(config);self.root=Path(repo_root);self.progress=progress;self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60);self.bundle=self.root/"competition_ultra_fast_output"/"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V1";self.zip_path=self.root/OUTPUT_FILENAME;self._app=False;self._account=None;self._last=None;self._requests=0
    def _request(self,r,historical=False):
        require_read_only_request(type(r).__name__)
        if historical:
            now=time.monotonic();wait=0 if self._last is None else MIN_INTERVAL-(now-self._last)
            if wait>0:time.sleep(wait)
            self._last=time.monotonic()
        x=self.transport.request(r,timeout=60)
        if type(x).__name__=="ProtoOAErrorRes":raise CaptureContractError(f"cTrader API error: {getattr(x,'errorCode','UNKNOWN')}")
        if historical:self._requests+=1
        return x
    def _restore(self):
        self.transport.connect()
        if self._app:self._request(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
        if self._account is not None:self._request(ProtoOAAccountAuthReq(ctidTraderAccountId=self._account,accessToken=self.access_token))
    def _send(self,r,historical=False,retries=4):
        last=None
        for n in range(retries):
            try:return self._request(r,historical)
            except Exception as e:
                last=e
                if n+1==retries:break
                time.sleep(min(8,2**n))
                try:self.transport.close();self._restore()
                except Exception as e2:last=e2
        raise CaptureContractError(f"{type(r).__name__} failed: {redact_text(str(last))}")
    def _ticks(self,aid,sid,side,w):
        to=w["to_ms"];prev=None;out=[];pages=0;limit=self.plan["capture_law"]["max_tick_pages_per_side_window"]
        while to>=w["from_ms"]:
            if pages>=limit:raise CaptureContractError("friction tick page limit exceeded")
            r=self._send(ProtoOAGetTickDataReq(ctidTraderAccountId=aid,symbolId=sid,type=QUOTE_TYPES[side],fromTimestamp=w["from_ms"],toTimestamp=to),historical=True);pages+=1
            page=decode_ctrader_tick_page([{"timestamp":int(x.timestamp),"tick":int(x.tick)} for x in r.tickData]);out.extend(page)
            if not r.hasMore:break
            nxt=next_tick_page_to_ms(page,current_from_ms=w["from_ms"],previous_oldest_ms=prev)
            if nxt is None:break
            oldest=min(x.timestamp_ms for x in page);prev=oldest;to=min(nxt,to-1)
        return out
    def _sample_bars(self,aid,sid,digits,w):
        r=self._send(ProtoOAGetTrendbarsReq(ctidTraderAccountId=aid,symbolId=sid,period=ProtoOATrendbarPeriod.Value("M5"),fromTimestamp=w["from_ms"],toTimestamp=w["to_ms"],count=100),historical=True)
        return normalize_m5([_plain(x) for x in r.trendbar],resolution="M5",digits=digits,requested_start_utc=w["start_utc"],requested_end_utc=w["end_utc"],protected_start_utc="2026-09-17T12:02:58Z")
    def _friction(self,aid,c,full,assets):
        stats=[];qcount=0
        for w in friction_windows(self.protocol,c["friction_profile"]):
            try:
                states=causal_merge_bid_ask(self._ticks(aid,c["symbol_id"],"BID",w),self._ticks(aid,c["symbol_id"],"ASK",w));bars=self._sample_bars(aid,c["symbol_id"],int(full.get("digits",5)),w);sp=[x.spread for x in states if x.spread>=0];mid=[(x.bid+x.ask)/2 for x in states if x.bid+x.ask>0];rg=[float(x["high"])-float(x["low"]) for x in bars if float(x["high"])>=float(x["low"])];qcount+=len(states);stats.append({"label":w["label"],"quote_states":len(states),"median_spread":_med(sp),"median_mid":_med(mid),"median_m5_range":_med(rg)})
            except Exception as e:stats.append({"label":w["label"],"quote_states":0,"error":redact_text(str(e))})
        obs=[x for x in stats if x.get("median_spread") is not None];sp=[x["median_spread"] for x in obs];mids=[x["median_mid"] for x in obs if x.get("median_mid")];ranges=[x["median_m5_range"] for x in stats if (x.get("median_m5_range") or 0)>0];med=_med(sp);p75=_q(sp,.75);p90=_q(sp,.9);p95=_q(sp,.95);mid=_med(mids);rng=_med(ranges);comm=_commission(full,assets,mid,int(full.get("minVolume") or 0));eff=(p75 or 0)+(comm.get("approx_roundtrip_commission_price_equivalent") or 0)
        m={**c,"planned_windows":len(stats),"observed_two_sided_windows":len(obs),"two_sided_window_coverage":len(obs)/len(stats) if stats else 0,"quote_state_count":qcount,"median_spread":med,"p75_spread":p75,"p90_spread":p90,"p95_spread":p95,"median_mid":mid,"median_m5_range":rng,"median_spread_over_mid":med/mid if med is not None and mid else None,"p95_spread_over_mid":p95/mid if p95 is not None and mid else None,"p75_spread_over_median_range":p75/rng if p75 is not None and rng else None,"p95_spread_over_median_range":p95/rng if p95 is not None and rng else None,"movement_to_p75_spread":rng/p75 if rng and p75 else None,"movement_to_p95_spread":rng/p95 if rng and p95 else None,"movement_to_effective_p75_friction":rng/eff if rng and eff else None,"commission":comm}
        m["friction_state"]=qualify_friction(m,self.protocol["friction_screen"]["qualification"]);return m
    def _stage_rows(self,aid,c,full):
        s=self.plan["stage_a_interval"];frm=_ms(_utc(s["start_utc"]));to=_ms(_utc(s["end_utc"]));page_to=to;rows={};pages=0
        while page_to>=frm:
            if pages>=self.plan["capture_law"]["max_stage_a_pages_per_symbol"]:raise CaptureContractError("Stage-A page limit exceeded")
            r=self._send(ProtoOAGetTrendbarsReq(ctidTraderAccountId=aid,symbolId=c["symbol_id"],period=ProtoOATrendbarPeriod.Value("M5"),fromTimestamp=frm,toTimestamp=page_to,count=5000),historical=True);pages+=1;bars=[_plain(x) for x in r.trendbar]
            for x in normalize_m5(bars,resolution="M5",digits=int(full.get("digits",5)),requested_start_utc=s["start_utc"],requested_end_utc=s["end_utc"],protected_start_utc="2026-09-17T12:02:58Z"):rows[x["time_utc"]]=x
            if not r.hasMore:break
            if not bars:raise CaptureContractError("Stage-A hasMore with empty page")
            nxt=min(int(x["utcTimestampInMinutes"])*60000 for x in bars)-1
            if nxt>=page_to:raise CaptureContractError("Stage-A pagination did not advance")
            page_to=nxt
        return [rows[k] for k in sorted(rows)]
    def _write_rows(self,c,rows):
        d=self.bundle/"stage_a_m5";d.mkdir(parents=True,exist_ok=True);p=d/(c["broker_symbol"].replace("/","_")+"_M5.csv")
        with p.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=RAW_HEADER,lineterminator="\n");w.writeheader();w.writerows([{k:x[k] for k in RAW_HEADER} for x in rows])
        return {"broker_symbol":c["broker_symbol"],"symbol_id":c["symbol_id"],"family":c["family"],"row_count":len(rows),"first_timestamp_utc":rows[0]["time_utc"] if rows else None,"last_timestamp_utc":rows[-1]["time_utc"] if rows else None,"sha256":_sha(p),"file":p.relative_to(self.bundle).as_posix()}
    def _workflow(self):
        self.progress("[1/5] Pepperstone LIVE read-only account binding");self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret));self._app=True;accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount];saved=self.config.get("ctid_trader_account_id")
        try:a=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            sel=self.config.get("account_selector")
            if saved is not None or not callable(sel):raise
            a=select_live_pepperstone_account(accounts,account_override=int(sel(live_account_candidates(accounts))))
        aid=int(a["ctidTraderAccountId"]);self._account=aid
        if account_fingerprint(aid)!=self.plan["account_fingerprint_sha256"]:raise MappingError("account fingerprint mismatch")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token));tr=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(tr.get("brokerName","")).lower() and "pepperstone" not in str(a.get("brokerTitleShort","")).lower():raise MappingError("not Pepperstone")
        assets={str(x.get("assetId")):x.get("name") for x in [_plain(y) for y in self._send(ProtoOAAssetListReq(ctidTraderAccountId=aid)).asset]};light={int(x["symbolId"]):x for x in [_plain(y) for y in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]};q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.extend([x["symbol_id"] for x in self.plan["shortlist"]]);full={int(x.symbolId):_plain(x) for x in self._send(q).symbol}
        for c in self.plan["shortlist"]:
            li=light.get(c["symbol_id"]);fu=full.get(c["symbol_id"])
            if not li or not fu or li.get("symbolName")!=c["broker_symbol"] or li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0:raise MappingError(f"shortlist mapping/tradability mismatch {c['broker_symbol']}")
        self.progress("[2/5] 4-week stratified friction; raw ticks discarded locally");fr=[]
        for i,c in enumerate(self.plan["shortlist"],1):
            m=self._friction(aid,c,full[c["symbol_id"]],assets);fr.append(m);self.progress(f"[FRICTION {i}/32] {c['broker_symbol']} {m['friction_state']} coverage={m['two_sided_window_coverage']:.0%}")
        initial,alternates=select_stage_a(fr,self.protocol["selection_law"]);self.progress(f"[3/5] selector admitted {len(initial)}/12 initial markets")
        ranked=sorted([x for x in fr if x["friction_state"] in {"FRICTION_PASS","FRICTION_WATCH"}],key=_rank);queue=initial+[x for x in ranked if x not in initial];chosen=[];series=[];repl=[];used=set();minrows=self.plan["capture_law"]["min_stage_a_m5_rows"]
        for c in queue:
            if len(chosen)>=12:break
            if c["broker_symbol"] in used or (c["friction_state"]=="FRICTION_WATCH" and float(c.get("movement_to_p75_spread") or 0)<2):continue
            try:
                rows=self._stage_rows(aid,c,full[c["symbol_id"]])
                if len(rows)<minrows:raise CaptureContractError(f"only {len(rows)} M5 rows < {minrows}")
                series.append(self._write_rows(c,rows));chosen.append(c);used.add(c["broker_symbol"]);self.progress(f"[STAGE-A {len(chosen)}/12] {c['broker_symbol']} rows={len(rows):,}")
            except Exception as e:used.add(c["broker_symbol"]);repl.append({"broker_symbol":c["broker_symbol"],"family":c["family"],"reason":redact_text(str(e)),"alpha_consulted":False})
        self.progress("[4/5] compact evidence only");atomic_write_json(self.bundle/"friction_summary.json",{"schema":"mxm.greenfield.v2.ultra-fast-friction-summary.v1","raw_ticks_transferred":False,"source_weeks":"2026-W34..2026-W37","results":fr});atomic_write_json(self.bundle/"selection.json",{"schema":"mxm.greenfield.v2.ultra-fast-stage-a-selection.v1","initial_selected":[x["broker_symbol"] for x in initial],"final_selected":[x["broker_symbol"] for x in chosen],"alternates":alternates,"data_availability_replacements":repl,"alpha_outcomes_used":False,"user_manual_replacements":False})
        atomic_write_json(self.bundle/"capture_manifest.json",{"schema":"mxm.greenfield.v2.ultra-fast-stage-a-capture-bundle.v1","status":"COMPACT_FRICTION_AND_STAGE_A_DEVELOPMENT_CAPTURE_COMPLETE","captured_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,"source_broker_universe_zip_sha256":self.plan["source_broker_universe_zip_sha256"],"account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],"source_environment":self.plan["source_environment"],"friction_shortlist_count":len(fr),"stage_a_selected_count":len(chosen),"stage_a_interval":self.plan["stage_a_interval"],"latest_4_week_diagnostic":self.plan["latest_4_week_diagnostic"],"series":series,"historical_requests":self._requests,"raw_ticks_transferred":False,"orders_placed":False,"account_mutation":False,"protected_evidence_opened":False,"economic_outcomes_opened":0,"v2_attempts_consumed":0})
        checks=[f"{_sha(p)}  {p.relative_to(self.bundle).as_posix()}" for p in sorted(x for x in self.bundle.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256")];(self.bundle/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8");scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token]);self.progress("[5/5] deterministic phone-friendly ZIP")
        with zipfile.ZipFile(self.zip_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for p in sorted(x for x in self.bundle.rglob("*") if x.is_file()):i=zipfile.ZipInfo(p.relative_to(self.bundle).as_posix(),(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o644<<16;z.writestr(i,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        self.progress(f"[DONE] {self.zip_path.name} bytes={self.zip_path.stat().st_size:,} SHA256={_sha(self.zip_path)}")
    def run(self):
        if self.bundle.exists():shutil.rmtree(self.bundle)
        self.bundle.mkdir(parents=True);self.zip_path.unlink(missing_ok=True)
        try:self.transport.connect();self._workflow()
        finally:self.transport.close()
        return self.zip_path
