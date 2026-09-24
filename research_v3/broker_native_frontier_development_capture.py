"""Read-only 13-week M5 DEVELOPMENT capture across the accepted broker-native structural frontier."""
from __future__ import annotations
import csv, hashlib, json, shutil, time
from datetime import datetime
from pathlib import Path
from google.protobuf.json_format import MessageToDict
from competition.frontier_data_capture import _deterministic_zip, _inspect_csv, _ms, _safe, _utc, _write_rows, normalize_m5
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

PLAN_REL="data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_PLAN_V1.json"
OUTPUT_FILENAME="MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip"
BUNDLE_DIR="MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1"
TOOL_VERSION="MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ANDROID_V1"
EXPECTED_PLAN_SHA="b29e6f95dcd1adc3374f71124628388df7e235829fc019d31b1183166b9c7d6a"
RAW_HEADER=("time_utc","open","high","low","close","tick_volume")
MIN_REQUEST_INTERVAL=1.0/4.7
TRADING_MODE_NAMES={0:"ENABLED",1:"DISABLED_WITHOUT_PENDINGS_EXECUTION",2:"DISABLED_WITH_PENDINGS_EXECUTION",3:"CLOSE_ONLY_MODE"}

def _plain(m):
    return MessageToDict(m,preserving_proto_field_name=False,use_integers_for_enums=True)

def _sha_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def current_symbol_state(spec,light,full):
    name=str(spec["broker_symbol"]); sid=int(spec["symbol_id"])
    if light is None or full is None:
        return {
            "broker_symbol":name,"symbol_id":sid,
            "current_mapping_available":False,
            "current_light_enabled":None,
            "current_trading_mode":None,
            "current_trading_mode_name":"UNAVAILABLE",
            "current_entry_tradable":False,
            "classification":"CURRENT_MAPPING_UNAVAILABLE",
        }
    observed_name=str(light.get("symbolName",""))
    if observed_name!=name:
        raise MappingError(f"selected symbol identity conflict {name}/{sid} -> {observed_name}")
    mode=int(full.get("tradingMode",-1))
    enabled=light.get("enabled")
    entry=(enabled is not False and mode==0)
    return {
        "broker_symbol":name,"symbol_id":sid,
        "current_mapping_available":True,
        "current_light_enabled":enabled,
        "current_trading_mode":mode,
        "current_trading_mode_name":TRADING_MODE_NAMES.get(mode,f"UNKNOWN_{mode}"),
        "current_entry_tradable":entry,
        "classification":("CURRENT_ENTRY_TRADABLE" if entry else "CURRENT_ENTRY_UNAVAILABLE_NONFATAL_FOR_HISTORICAL_PROBE"),
    }

def canonical_plan_sha(plan):
    body={k:v for k,v in plan.items() if k!="plan_sha256"}
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def validate_plan(plan):
    if plan.get("schema")!="mxm.greenfield.broker-native-frontier-development-m5-plan.v1":
        raise CaptureContractError("wrong frontier development plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_NON_ECONOMIC":
        raise CaptureContractError("frontier development plan is not frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or canonical_plan_sha(plan)!=EXPECTED_PLAN_SHA:
        raise CaptureContractError("frontier development plan hash mismatch")
    if plan.get("resolution")!="M5": raise CaptureContractError("probe is M5-only")
    syms=plan.get("symbols") or []
    ids=[int(x["symbol_id"]) for x in syms]; names=[str(x["broker_symbol"]) for x in syms]
    if len(syms)!=40 or len(set(ids))!=40 or len(set(names))!=40:
        raise CaptureContractError("frontier development capture must contain exact 40 unique representatives")
    if "SHEIN.HK-PERP" in set(names) or "NAS100" in set(names):
        raise CaptureContractError("development capture contains an excluded symbol")
    law=plan.get("capture_law") or {}
    if law.get("read_only") is not True or law.get("orders_permitted") is not False or law.get("account_mutation_permitted") is not False:
        raise CaptureContractError("development capture law is not read-only")
    if plan.get("economic_outcomes_opened")!=0 or plan.get("v2_attempts_consumed")!=0 or plan.get("protected_evidence_opened") is not False:
        raise CaptureContractError("development plan is economically contaminated")
    if plan.get("probe_sufficiency",{}).get("schedule_adjusted_coverage_gate") is not False:
        raise CaptureContractError("historical schedule-model coverage gate is forbidden for this capture")
    start=_utc(plan["interval"]["start_utc"]); end=_utc(plan["interval"]["end_utc"]); protected=_utc(plan["protected_forward_start"])
    if not start<end<protected: raise CaptureContractError("development interval/protected boundary invalid")
    return True

class BrokerNativeFrontierDevelopmentRunner:
    def __init__(self,*,plan,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan)
        self.plan=dict(plan); self.client_id=client_id; self.client_secret=client_secret; self.access_token=access_token
        self.config=dict(config); self.root=Path(repo_root); self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/"broker_native_frontier_development_output"/BUNDLE_DIR
        self.work=self.root/".broker_native_frontier_development_work"/EXPECTED_PLAN_SHA[:16]
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
        if self._app: self._request(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
        if self._account is not None: self._request(ProtoOAAccountAuthReq(ctidTraderAccountId=self._account,accessToken=self.access_token))

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

    def _capture_one(self,aid,spec,full,current_state):
        name=str(spec["broker_symbol"]); sid=int(spec["symbol_id"]); digits=int(full.get("digits",5))
        target=self.work/f"{sid}_{_safe(name)}_M5.csv"; meta_path=self.work/f"{sid}_{_safe(name)}_M5.meta.json"
        if target.is_file() and meta_path.is_file():
            meta=json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sha256")==_sha_file(target) and meta.get("symbol_id")==sid and meta.get("broker_symbol")==name:
                self.progress(f"[RESUME] {name} M5 rows={meta.get('row_count',0):,}"); return target,meta
        start=self.plan["interval"]["start_utc"]; end=self.plan["interval"]["end_utc"]
        frm=_ms(_utc(start)); page_to=_ms(_utc(end)); all_rows={}
        while page_to>=frm:
            q=ProtoOAGetTrendbarsReq(ctidTraderAccountId=aid,symbolId=sid,period=ProtoOATrendbarPeriod.Value("M5"),fromTimestamp=frm,toTimestamp=page_to,count=5000)
            response=self._send(q,historical=True); bars=[_plain(x) for x in response.trendbar]
            for row in normalize_m5(bars,digits=digits,start_utc=start,end_utc=end,protected_utc=self.plan["protected_forward_start"]):
                key=row["time_utc"]
                if key in all_rows and all_rows[key]!=row: raise CaptureContractError(f"{name}: conflicting M5 duplicate {key}")
                all_rows[key]=row
            if not bool(getattr(response,"hasMore",False)): break
            if not bars: raise CaptureContractError(f"{name}: hasMore without trendbars")
            nxt=min(int(x.get("utcTimestampInMinutes"))*60000 for x in bars)-1
            if nxt>=page_to or nxt<frm: raise CaptureContractError(f"{name}: invalid M5 pagination")
            page_to=nxt
        _write_rows(target,[all_rows[k] for k in sorted(all_rows)],"w")
        stats=_inspect_csv(target)
        active_dates=len({row["time_utc"][:10] for row in all_rows.values()})
        meta={
            "broker_symbol":name,"symbol_id":sid,"structural_signature":spec["structural_signature"],
            "digits":digits,"resolution":"M5","requested_interval":self.plan["interval"],
            "classification":"DEVELOPMENT_ONLY_NON_ECONOMIC_BREADTH_CAPTURE",
            "row_count":stats["row_count"],"first_timestamp_utc":stats["first_timestamp_utc"],
            "last_timestamp_utc":stats["last_timestamp_utc"],"observed_active_dates":active_dates,
            "gap_count_24x7_reference":stats["gap_count_24x7_reference"],"sha256":stats["sha256"],
            "empty_series_classification":("NO_M5_ROWS_OBSERVED" if stats["row_count"]==0 else None),
            "synthetic_fill":False,"forward_fill":False,"schedule_adjusted_coverage_computed":False,
            "current_symbol_state":current_state,"capture_status":"SERIES_CAPTURE_COMPLETE",
        }
        atomic_write_json(meta_path,meta); return target,meta

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
            raise MappingError("LIVE account fingerprint differs from accepted broker universe")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():
            raise MappingError("not verifiably Pepperstone")
        light=[_plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]
        light_by={int(x["symbolId"]):x for x in light}; ids=[int(x["symbol_id"]) for x in self.plan["symbols"]]; full={}
        for i in range(0,len(ids),64):
            q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid); q.symbolId.extend(ids[i:i+64])
            for x in self._send(q).symbol: full[int(x.symbolId)]=_plain(x)
        states={}
        for spec in self.plan["symbols"]:
            sid=int(spec["symbol_id"]); name=str(spec["broker_symbol"])
            state=current_symbol_state(spec,light_by.get(sid),full.get(sid)); states[sid]=state
            if state["current_entry_tradable"] is False:
                self.progress(f"[SYMBOL STATE] {name}: {state['classification']} mode={state['current_trading_mode_name']}")
        self.progress("[2/3] Capturing 40 structural representatives / M5 / 13-week DEVELOPMENT breadth dataset")
        raw_dir=self.bundle/"raw"; raw_dir.mkdir(parents=True); results=[]; errors=0; unavailable=0
        for i,spec in enumerate(self.plan["symbols"],1):
            sid=int(spec["symbol_id"]); name=str(spec["broker_symbol"]); state=states[sid]
            if not state["current_mapping_available"]:
                unavailable+=1
                m={
                    "broker_symbol":name,"symbol_id":sid,"structural_signature":spec["structural_signature"],
                    "resolution":"M5","requested_interval":self.plan["interval"],
                    "classification":"DEVELOPMENT_ONLY_NON_ECONOMIC_BREADTH_CAPTURE",
                    "capture_status":"CURRENT_MAPPING_UNAVAILABLE_NO_REQUEST",
                    "current_symbol_state":state,"row_count":0,
                    "synthetic_fill":False,"forward_fill":False,"schedule_adjusted_coverage_computed":False,
                }
                results.append(m); self.progress(f"[SERIES {i}/40 SKIP] {name}: current mapping unavailable; preserved as observation")
                continue
            try:
                src,meta=self._capture_one(aid,spec,full[sid],state)
            except Exception as exc:
                errors+=1
                m={
                    "broker_symbol":name,"symbol_id":sid,"structural_signature":spec["structural_signature"],
                    "resolution":"M5","requested_interval":self.plan["interval"],
                    "classification":"DEVELOPMENT_ONLY_NON_ECONOMIC_BREADTH_CAPTURE",
                    "capture_status":"SERIES_CAPTURE_ERROR_RETRYABLE",
                    "current_symbol_state":state,"row_count":0,
                    "error_type":type(exc).__name__,"error":redact_text(str(exc)),
                    "synthetic_fill":False,"forward_fill":False,"schedule_adjusted_coverage_computed":False,
                }
                results.append(m); self.progress(f"[SERIES {i}/40 ERROR-PRESERVED] {name}: {m['error']}")
                continue
            dest=raw_dir/src.name; shutil.copyfile(src,dest); m=dict(meta); m["file"]=dest.relative_to(self.bundle).as_posix(); results.append(m)
            self.progress(f"[SERIES {i}/40 PASS] {name} rows={m['row_count']:,} current_entry_tradable={state['current_entry_tradable']}")
        completed=sum(1 for x in results if x.get("capture_status")=="SERIES_CAPTURE_COMPLETE")
        status=("NON_ECONOMIC_BREADTH_CAPTURE_COMPLETE" if errors==0 and unavailable==0 else "NON_ECONOMIC_BREADTH_CAPTURE_PARTIAL_RETRYABLE")
        manifest={
            "schema":"mxm.greenfield.broker-native-frontier-m5-development-bundle.v1",
            "status":status,
            "captured_utc":datetime.utcnow().isoformat(timespec="seconds")+"Z",
            "tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,
            "source_frontier_sha256":self.plan["source_frontier_sha256"],
            "source_broker_universe_zip_sha256":self.plan["source_broker_universe_zip_sha256"],
            "account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],
            "source_environment":self.plan["source_environment"],"resolution":"M5",
            "requested_interval":self.plan["interval"],"series":results,
            "series_summary":{"planned":40,"completed":completed,"retryable_errors":errors,"current_mapping_unavailable":unavailable,
                              "current_entry_unavailable":sum(1 for x in results if not (x.get("current_symbol_state") or {}).get("current_entry_tradable",False))},
            "schedule_adjusted_coverage_computed":False,
            "economic_outcomes_opened":0,"v2_attempts_consumed":0,
            "orders_placed":False,"account_mutation":False,"protected_evidence_opened":False,
        }
        atomic_write_json(self.bundle/"capture_manifest.json",manifest)
        checks=[]
        for p in sorted(x for x in self.bundle.rglob("*") if x.is_file()):
            checks.append(f"{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}")
        (self.bundle/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8")
        scan_bundle_for_secrets(self.bundle)
        self.progress("[3/3] Deterministic ZIP + secret scan")
        digest=_deterministic_zip(self.bundle,self.zip_path)
        self.progress(f"[COMPLETE] {self.zip_path.name} sha256={digest}")
