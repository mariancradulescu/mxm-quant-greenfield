"""Read-only M5 DEVELOPMENT capture for the accepted broad competition frontier."""
from __future__ import annotations
import csv,hashlib,json,shutil,time,zipfile
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from google.protobuf.json_format import MessageToDict
from m6.ctrader_capture import (
    CaptureContractError,MappingError,account_fingerprint,atomic_write_json,
    live_account_candidates,redact_text,require_read_only_request,scan_bundle_for_secrets,
    select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,ProtoOAApplicationAuthReq,ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTrendbarsReq,ProtoOASymbolByIdReq,ProtoOASymbolsListReq,ProtoOATraderReq,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import LIVE_HOST,LIVE_PORT,StdlibCTraderTransport

PLAN_REL="data/COMPETITION_FRONTIER_WAVE_01_V2_DATA_CAPTURE_PLAN.json"
OUTPUT_FILENAME="MXM_COMPETITION_FRONTIER_WAVE_01_V2_M5_DEVELOPMENT.zip"
TOOL_VERSION="MXM_COMPETITION_FRONTIER_M5_ANDROID_STDLIB_V1"
EXPECTED_PLAN_SHA="04fba61fce3f17136c856a238168d4ba06662299a884387fec1752ede8f555db"
RAW_HEADER=("time_utc","open","high","low","close","tick_volume")
M5_MINUTES=5
MIN_REQUEST_INTERVAL=1.0/4.7

def _plain(m):
    return MessageToDict(m,preserving_proto_field_name=False,use_integers_for_enums=True)

def _utc(s):
    x=datetime.fromisoformat(s[:-1]+"+00:00" if s.endswith("Z") else s)
    if x.tzinfo is None or x.utcoffset()!=timedelta(0):raise CaptureContractError("explicit UTC required")
    return x.astimezone(timezone.utc)

def _iso(x):return x.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
def _ms(x):return int(x.timestamp()*1000)
def _sha_bytes(b):return hashlib.sha256(b).hexdigest()
def _sha_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def canonical_plan_sha(plan):
    x={k:v for k,v in plan.items() if k!="plan_sha256"}
    return _sha_bytes(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())

def validate_plan(plan):
    if plan.get("schema")!="mxm.greenfield.v2.competition-frontier-development-capture-plan.v1":raise CaptureContractError("wrong frontier data plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_PRE_OUTCOME":raise CaptureContractError("frontier data plan is not frozen")
    if plan.get("resolution")!="M5":raise CaptureContractError("this collector is M5-only")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or canonical_plan_sha(plan)!=EXPECTED_PLAN_SHA:raise CaptureContractError("frontier data plan hash mismatch")
    if plan.get("economic_outcomes_opened")!=0 or plan.get("v2_attempts_consumed")!=0 or plan.get("protected_evidence_opened") is not False:raise CaptureContractError("frontier data plan is economically contaminated")
    start,end,protected=map(_utc,(plan["interval"]["start_utc"],plan["interval"]["end_utc"],plan["protected_forward_start"]))
    if not start<end<protected:raise CaptureContractError("DEVELOPMENT interval/protected boundary invalid")
    syms=plan.get("symbols") or []
    ids=[int(x["symbol_id"]) for x in syms]; names=[str(x["broker_symbol"]) for x in syms]
    if len(syms)!=16 or len(ids)!=len(set(ids)) or len(names)!=len(set(names)):raise CaptureContractError("frontier symbol set must be exact 16 unique identities")
    return True

def _windows(start,end,days=14):
    cur=_utc(start); stop=_utc(end); out=[]
    while cur<=stop:
        b=min(stop,cur+timedelta(days=days)-timedelta(milliseconds=1))
        out.append((_ms(cur),_ms(b)));cur=b+timedelta(milliseconds=1)
    return out

def _price(v,digits):
    q=Decimal(1).scaleb(-int(digits))
    return str((Decimal(int(v))/Decimal(100000)).quantize(q))

def normalize_m5(trendbars,*,digits,start_utc,end_utc,protected_utc):
    start,end,protected=map(_utc,(start_utc,end_utc,protected_utc)); by={}
    for b in trendbars:
        try:
            om=int(b.get("utcTimestampInMinutes",b.get("utc_timestamp_in_minutes")))
            low=int(b["low"]);do=int(b.get("deltaOpen",b.get("delta_open",0)));dh=int(b.get("deltaHigh",b.get("delta_high",0)));dc=int(b.get("deltaClose",b.get("delta_close",0)));vol=int(b.get("volume",0))
        except (TypeError,ValueError,KeyError) as e:raise CaptureContractError("malformed M5 trendbar") from e
        opened=datetime.fromtimestamp(om*60,tz=timezone.utc);completed=opened+timedelta(minutes=M5_MINUTES)
        if opened<start or completed>end or completed>=protected:continue
        row={"time_utc":_iso(opened),"open":_price(low+do,digits),"high":_price(low+dh,digits),"low":_price(low,digits),"close":_price(low+dc,digits),"tick_volume":str(vol)}
        k=row["time_utc"]
        if k in by and by[k]!=row:raise CaptureContractError(f"conflicting M5 duplicate {k}")
        by[k]=row
    return [by[k] for k in sorted(by)]

def _safe(name):return "".join(c if c.isalnum() else "_" for c in name)
def _write_rows(path,rows,mode):
    with Path(path).open(mode,encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=RAW_HEADER,lineterminator="\n")
        if mode=="w":w.writeheader()
        for row in rows:w.writerow(row)

def _inspect_csv(path):
    rows=0;first=last=None;prev=None;gaps=0
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            t=_utc(row["time_utc"]);rows+=1
            if first is None:first=row["time_utc"]
            if prev is not None and (t-prev).total_seconds()>M5_MINUTES*60:gaps+=1
            prev=t;last=row["time_utc"]
    return {"row_count":rows,"first_timestamp_utc":first,"last_timestamp_utc":last,"gap_count_24x7_reference":gaps,"sha256":_sha_file(path)}

def _deterministic_zip(root,target):
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(x for x in Path(root).rglob("*") if x.is_file()):
            i=zipfile.ZipInfo(p.relative_to(root).as_posix(),(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o644<<16
            z.writestr(i,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return _sha_file(target)

class FrontierDataCaptureRunner:
    def __init__(self,*,plan,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan);self.plan=dict(plan);self.client_id=client_id;self.client_secret=client_secret;self.access_token=access_token;self.config=dict(config);self.root=Path(repo_root);self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/"competition_frontier_capture_output"/"MXM_COMPETITION_FRONTIER_WAVE_01_V2_M5_DEVELOPMENT"
        self.work=self.root/".competition_frontier_capture_work"/EXPECTED_PLAN_SHA[:16]
        self.zip_path=self.root/OUTPUT_FILENAME;self._app=False;self._account=None;self._last_hist=None
    def _request(self,r,historical=False):
        require_read_only_request(type(r).__name__)
        if historical:
            now=time.monotonic()
            if self._last_hist is not None:
                wait=MIN_REQUEST_INTERVAL-(now-self._last_hist)
                if wait>0:time.sleep(wait)
            self._last_hist=time.monotonic()
        x=self.transport.request(r,timeout=60)
        if type(x).__name__=="ProtoOAErrorRes":raise CaptureContractError(f"cTrader API error: {getattr(x,'errorCode','UNKNOWN')}")
        return x
    def _restore(self):
        self.transport.connect()
        if self._app:self._request(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
        if self._account is not None:self._request(ProtoOAAccountAuthReq(ctidTraderAccountId=self._account,accessToken=self.access_token))
    def _send(self,r,historical=False,retries=3):
        last=None
        for n in range(retries):
            try:return self._request(r,historical)
            except Exception as e:
                last=e
                if n+1==retries:break
                time.sleep(min(4.0,2**n))
                try:self.transport.close();self._restore()
                except Exception as e2:last=e2
        raise CaptureContractError(f"{type(r).__name__} failed: {redact_text(str(last))}")
    def run(self):
        self.work.mkdir(parents=True,exist_ok=True)
        if self.bundle.exists():shutil.rmtree(self.bundle)
        self.bundle.mkdir(parents=True);self.zip_path.unlink(missing_ok=True)
        try:self.transport.connect();self._workflow()
        finally:self.transport.close()
        return self.zip_path
    def _capture_one(self,aid,spec,full):
        name=spec["broker_symbol"];sid=int(spec["symbol_id"]);digits=int(full.get("digits",5));safe=_safe(name)
        done=self.work/f"{sid}_{safe}_M5.csv";meta=self.work/f"{sid}_{safe}_M5.meta.json"
        if done.is_file() and meta.is_file():
            m=json.loads(meta.read_text())
            if m.get("sha256")==_sha_file(done) and m.get("symbol_id")==sid and m.get("broker_symbol")==name:
                self.progress(f"[RESUME] {name} M5 {m.get('row_count',0):,} rows");return done,m
        part=done.with_suffix(".part");part.unlink(missing_ok=True)
        interval=self.plan["interval"];windows=_windows(interval["start_utc"],interval["end_utc"],self.plan["capture_law"]["window_days"])
        for wi,(frm,to) in enumerate(windows):
            page_to=to;window_rows={}
            while page_to>=frm:
                q=ProtoOAGetTrendbarsReq(ctidTraderAccountId=aid,symbolId=sid,period=ProtoOATrendbarPeriod.Value("M5"),fromTimestamp=frm,toTimestamp=page_to,count=5000)
                r=self._send(q,historical=True);bars=[_plain(x) for x in r.trendbar]
                for row in normalize_m5(bars,digits=digits,start_utc=interval["start_utc"],end_utc=interval["end_utc"],protected_utc=self.plan["protected_forward_start"]):window_rows[row["time_utc"]]=row
                if not bool(getattr(r,"hasMore",False)):break
                if not bars:raise CaptureContractError(f"{name}: hasMore without trendbars")
                nxt=min(int(x.get("utcTimestampInMinutes"))*60000 for x in bars)-1
                if nxt>=page_to or nxt<frm:raise CaptureContractError(f"{name}: invalid M5 pagination")
                page_to=nxt
            _write_rows(part,[window_rows[k] for k in sorted(window_rows)],"w" if wi==0 else "a")
            if (wi+1)%20==0 or wi+1==len(windows):self.progress(f"[DATA] {name} M5 windows {wi+1}/{len(windows)}")
        part.replace(done);stats=_inspect_csv(done)
        m={"broker_symbol":name,"symbol_id":sid,"digits":digits,"resolution":"M5","requested_interval":interval,"protected_forward_start":self.plan["protected_forward_start"],"classification":"DEVELOPMENT_ONLY","completed_bars_only":True,"synthetic_fill":False,"forward_fill":False,**stats}
        atomic_write_json(meta,m);return done,m
    def _workflow(self):
        self.progress("[1/3] Pepperstone LIVE view-only auth + exact account binding")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret));self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved=self.config.get("ctid_trader_account_id")
        try:account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector):raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]);self._account=aid
        if account_fingerprint(aid)!=self.plan["account_fingerprint_sha256"]:raise MappingError("LIVE account fingerprint differs from accepted exhaustive universe")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():raise MappingError("not verifiably Pepperstone")
        light=[_plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]
        L={int(x["symbolId"]):x for x in light};ids=[int(x["symbol_id"]) for x in self.plan["symbols"]];full={}
        for i in range(0,len(ids),64):
            q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.extend(ids[i:i+64])
            for x in self._send(q).symbol:full[int(x.symbolId)]=_plain(x)
        for spec in self.plan["symbols"]:
            sid=int(spec["symbol_id"]);name=spec["broker_symbol"];li=L.get(sid);fu=full.get(sid)
            if li is None or fu is None or str(li.get("symbolName"))!=name:raise MappingError(f"frontier mapping mismatch {name}/{sid}")
            if li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0:raise MappingError(f"frontier symbol not new-entry tradable: {name}")
        self.progress("[2/3] Capturing exact 16-symbol M5 DEVELOPMENT frontier")
        results=[]
        raw_dir=self.bundle/"raw";raw_dir.mkdir(parents=True)
        for i,spec in enumerate(self.plan["symbols"],1):
            done,meta=self._capture_one(aid,spec,full[int(spec["symbol_id"])])
            target=raw_dir/done.name;shutil.copyfile(done,target);meta=dict(meta);meta["file"]=target.relative_to(self.bundle).as_posix();results.append(meta)
            self.progress(f"[SERIES {i}/16 PASS] {spec['broker_symbol']} rows={meta['row_count']:,}")
        manifest={"schema":"mxm.greenfield.v2.competition-frontier-development-capture-bundle.v1","status":"M5_DEVELOPMENT_CAPTURE_COMPLETE","captured_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,"source_frontier":self.plan["frontier_authority"],"source_broker_universe_zip_sha256":self.plan["source_capture_zip_sha256"],"account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],"source_environment":self.plan["source_environment"],"resolution":"M5","classification":"DEVELOPMENT_ONLY","series":results,"orders_placed":False,"account_mutation":False,"protected_evidence_opened":False,"economic_outcomes_opened":0,"v2_attempts_consumed":0}
        atomic_write_json(self.bundle/"capture_manifest.json",manifest)
        checks=[]
        for p in sorted(x for x in self.bundle.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256"):checks.append(f"{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}")
        (self.bundle/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8")
        scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])
        self.progress("[3/3] Deterministic transferable ZIP")
        digest=_deterministic_zip(self.bundle,self.zip_path);self.progress(f"[DONE] {self.zip_path.name} SHA256={digest}")
