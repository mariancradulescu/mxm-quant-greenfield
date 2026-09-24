"""Read-only minimal M5 capture selected by P-20260924-C031-GAP-WAVE-01."""
from __future__ import annotations
import csv, hashlib, json, shutil, time
from datetime import datetime
from pathlib import Path
from google.protobuf.json_format import MessageToDict
from competition.frontier_data_capture import (
    _deterministic_zip, _inspect_csv, _ms, _safe, _utc, _write_rows, normalize_m5,
)
from m6.ctrader_capture import (
    CaptureContractError, MappingError, account_fingerprint, atomic_write_json,
    live_account_candidates, redact_text, require_read_only_request, scan_bundle_for_secrets,
    select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq, ProtoOAApplicationAuthReq, ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTrendbarsReq, ProtoOASymbolByIdReq, ProtoOASymbolsListReq, ProtoOATraderReq,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport

PLAN_REL="data/C031_STRUCTURAL_EXTENSION_WAVE_01_M5_CAPTURE_PLAN_V1.json"
OUTPUT_FILENAME="MXM_C031_STRUCTURAL_EXTENSION_WAVE_01_M5_8W_CAPTURE.zip"
BUNDLE_DIR="MXM_C031_STRUCTURAL_EXTENSION_WAVE_01_M5_8W_CAPTURE"
TOOL_VERSION="MXM_C031_STRUCTURAL_EXTENSION_ANDROID_STDLIB_V1"
EXPECTED_PLAN_SHA="86cd4df00754f6a9a2032591fdfadd6bc5a16b7a25383cb206d2be77ee948aa0"
EXPECTED_SYMBOLS={
    "USTN2YR-F":7295,"TLT.US":4504,"NVDA.US-24":3003,"VIX":152,"HSTECH":7371,"ADAUSD":325,
    "Gasoline":309,"EURUSD":1,"USDCAD":8,"MXNJPY":2778,"IWM.US":4476,"DOTUSD":282,
}
RAW_HEADER=("time_utc","open","high","low","close","tick_volume")
MIN_REQUEST_INTERVAL=1.0/4.7

def _plain(m):
    return MessageToDict(m,preserving_proto_field_name=False,use_integers_for_enums=True)

def _sha_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def canonical_plan_sha(plan):
    body={k:v for k,v in plan.items() if k!="plan_sha256"}
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def validate_plan(plan):
    if plan.get("schema")!="mxm.greenfield.v2.c031-structural-extension-m5-capture-plan.v1":
        raise CaptureContractError("wrong C031 structural extension plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_PRE_SCREEN_NO_ECONOMICS":
        raise CaptureContractError("C031 structural extension plan is not prospectively frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or canonical_plan_sha(plan)!=EXPECTED_PLAN_SHA:
        raise CaptureContractError("C031 structural extension plan hash mismatch")
    if plan.get("resolution")!="M5":
        raise CaptureContractError("C031 structural extension collector is M5-only")
    observed={str(x["broker_symbol"]):int(x["symbol_id"]) for x in plan.get("symbols") or []}
    if observed!=EXPECTED_SYMBOLS:
        raise CaptureContractError("C031 structural extension symbol identities drift")
    if plan.get("economic_outcomes_opened")!=0 or plan.get("v2_attempts_consumed")!=0:
        raise CaptureContractError("capture plan must be non-economic")
    if plan.get("protected_evidence_opened") is not False:
        raise CaptureContractError("protected evidence must remain closed")
    start=_utc(plan["interval"]["start_utc"]); end=_utc(plan["interval"]["end_utc"]); protected=_utc(plan["protected_forward_start"])
    if not start<end<protected:
        raise CaptureContractError("capture interval/protected boundary invalid")
    law=plan.get("capture_law") or {}
    if law.get("read_only") is not True or law.get("orders_permitted") is not False or law.get("account_mutation_permitted") is not False:
        raise CaptureContractError("capture law is not read-only")
    return True

def _windows(start,end,days):
    from datetime import timedelta
    cur=_utc(start); stop=_utc(end); out=[]
    while cur<=stop:
        b=min(stop,cur+timedelta(days=int(days))-timedelta(milliseconds=1))
        out.append((_ms(cur),_ms(b))); cur=b+timedelta(milliseconds=1)
    return out

class C031StructuralExtensionCaptureRunner:
    def __init__(self,*,plan,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan)
        self.plan=dict(plan); self.client_id=client_id; self.client_secret=client_secret; self.access_token=access_token
        self.config=dict(config); self.root=Path(repo_root); self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/"c031_structural_extension_capture_output"/BUNDLE_DIR
        self.work=self.root/".c031_structural_extension_capture_work"/EXPECTED_PLAN_SHA[:16]
        self.zip_path=self.root/OUTPUT_FILENAME; self._app=False; self._account=None; self._last_hist=None

    def _request(self,request,historical=False):
        require_read_only_request(type(request).__name__)
        if historical:
            now=time.monotonic()
            if self._last_hist is not None:
                wait=MIN_REQUEST_INTERVAL-(now-self._last_hist)
                if wait>0: time.sleep(wait)
            self._last_hist=time.monotonic()
        response=self.transport.request(request,timeout=60)
        if type(response).__name__=="ProtoOAErrorRes":
            raise CaptureContractError(f"cTrader API error: {getattr(response,'errorCode','UNKNOWN')}")
        return response

    def _restore(self):
        self.transport.connect()
        if self._app:
            self._request(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
        if self._account is not None:
            self._request(ProtoOAAccountAuthReq(ctidTraderAccountId=self._account,accessToken=self.access_token))

    def _send(self,request,historical=False,retries=3):
        last=None
        for n in range(retries):
            try: return self._request(request,historical)
            except Exception as exc:
                last=exc
                if n+1==retries: break
                time.sleep(min(4.0,2**n))
                try: self.transport.close(); self._restore()
                except Exception as restore_exc: last=restore_exc
        raise CaptureContractError(f"{type(request).__name__} failed: {redact_text(str(last))}")

    def _capture_one(self,aid,spec,full):
        name=str(spec["broker_symbol"]); sid=int(spec["symbol_id"]); digits=int(full.get("digits",5))
        done=self.work/f"{sid}_{_safe(name)}_M5.csv"; meta=self.work/f"{sid}_{_safe(name)}_M5.meta.json"
        if done.is_file() and meta.is_file():
            m=json.loads(meta.read_text(encoding="utf-8"))
            if m.get("sha256")==_sha_file(done) and m.get("symbol_id")==sid and m.get("broker_symbol")==name:
                self.progress(f"[RESUME] {name} M5 {m.get('row_count',0):,} rows"); return done,m
        part=done.with_suffix(".part"); part.unlink(missing_ok=True)
        interval=self.plan["interval"]; windows=_windows(interval["start_utc"],interval["end_utc"],self.plan["capture_law"]["window_days"])
        all_rows={}
        for wi,(frm,to) in enumerate(windows):
            page_to=to; window_rows={}
            while page_to>=frm:
                q=ProtoOAGetTrendbarsReq(ctidTraderAccountId=aid,symbolId=sid,period=ProtoOATrendbarPeriod.Value("M5"),fromTimestamp=frm,toTimestamp=page_to,count=5000)
                response=self._send(q,historical=True); bars=[_plain(x) for x in response.trendbar]
                for row in normalize_m5(bars,digits=digits,start_utc=interval["start_utc"],end_utc=interval["end_utc"],protected_utc=self.plan["protected_forward_start"]):
                    key=row["time_utc"]
                    if key in all_rows and all_rows[key] != row:
                        raise CaptureContractError(f"{name}: conflicting duplicate M5 row at {key}")
                    window_rows[key]=row
                if not bool(getattr(response,"hasMore",False)): break
                if not bars: raise CaptureContractError(f"{name}: hasMore without trendbars")
                nxt=min(int(x.get("utcTimestampInMinutes"))*60000 for x in bars)-1
                if nxt>=page_to or nxt<frm: raise CaptureContractError(f"{name}: invalid M5 pagination")
                page_to=nxt
            all_rows.update(window_rows)
            self.progress(f"[DATA] {name} windows {wi+1}/{len(windows)} unique_rows={len(all_rows):,}")
        _write_rows(part,[all_rows[k] for k in sorted(all_rows)],"w")
        part.replace(done); stats=_inspect_csv(done)
        m={"broker_symbol":name,"symbol_id":sid,"digits":digits,"resolution":"M5","requested_interval":interval,
           "protected_forward_start":self.plan["protected_forward_start"],"classification":"DEVELOPMENT_ONLY",
           "completed_bars_only":True,"synthetic_fill":False,"forward_fill":False,**stats}
        atomic_write_json(meta,m); return done,m

    def run(self):
        self.work.mkdir(parents=True,exist_ok=True)
        if self.bundle.exists(): shutil.rmtree(self.bundle)
        self.bundle.mkdir(parents=True); self.zip_path.unlink(missing_ok=True)
        try: self.transport.connect(); self._workflow()
        finally: self.transport.close()
        return self.zip_path

    def _workflow(self):
        self.progress("[1/3] Pepperstone LIVE read-only auth + exact account binding")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret)); self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved=self.config.get("ctid_trader_account_id")
        try: account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector): raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]); self._account=aid
        if account_fingerprint(aid)!=self.plan["account_fingerprint_sha256"]:
            raise MappingError("LIVE account fingerprint differs from accepted V2 broker universe")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():
            raise MappingError("not verifiably Pepperstone")
        light=[_plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]
        light_by={int(x["symbolId"]):x for x in light}; ids=[int(x["symbol_id"]) for x in self.plan["symbols"]]; full={}
        for i in range(0,len(ids),64):
            q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid); q.symbolId.extend(ids[i:i+64])
            for x in self._send(q).symbol: full[int(x.symbolId)]=_plain(x)
        for spec in self.plan["symbols"]:
            sid=int(spec["symbol_id"]); name=str(spec["broker_symbol"]); li=light_by.get(sid); fu=full.get(sid)
            if li is None or fu is None or str(li.get("symbolName"))!=name:
                raise MappingError(f"selected symbol mapping mismatch {name}/{sid}")
            if li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0:
                raise MappingError(f"selected symbol not current new-entry tradable: {name}")
        self.progress("[2/3] Capturing exact AI-selected 12-symbol M5 / 8-week DEVELOPMENT scope")
        raw_dir=self.bundle/"raw"; raw_dir.mkdir(parents=True); results=[]
        for i,spec in enumerate(self.plan["symbols"],1):
            done,meta=self._capture_one(aid,spec,full[int(spec["symbol_id"])])
            target=raw_dir/done.name; shutil.copyfile(done,target); meta=dict(meta); meta["file"]=target.relative_to(self.bundle).as_posix(); results.append(meta)
            self.progress(f"[SERIES {i}/12 PASS] {spec['broker_symbol']} rows={meta['row_count']:,}")
        manifest={
            "schema":"mxm.greenfield.v2.c031-structural-extension-m5-capture-bundle.v1",
            "status":"M5_MINIMAL_STRUCTURAL_EXTENSION_CAPTURE_COMPLETE",
            "captured_utc":datetime.utcnow().isoformat(timespec="seconds")+"Z",
            "tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,
            "source_ai_proposal_id":self.plan["source_ai_proposal_id"],
            "source_broker_universe_zip_sha256":self.plan["source_capture_zip_sha256"],
            "account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],
            "source_environment":self.plan["source_environment"],"resolution":"M5",
            "requested_interval":self.plan["interval"],"classification":"DEVELOPMENT_ONLY","series":results,
            "orders_placed":False,"account_mutation":False,"protected_evidence_opened":False,
            "economic_outcomes_opened":0,"v2_attempts_consumed":0,
        }
        atomic_write_json(self.bundle/"capture_manifest.json",manifest)
        checks=[]
        for p in sorted(x for x in self.bundle.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256"):
            checks.append(f"{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}")
        (self.bundle/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8")
        scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])
        self.progress("[3/3] Deterministic transferable ZIP")
        digest=_deterministic_zip(self.bundle,self.zip_path)
        self.progress(f"[DONE] {self.zip_path.name} SHA256={digest}")
