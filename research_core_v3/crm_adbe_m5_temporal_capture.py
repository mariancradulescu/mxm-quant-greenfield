"""Read-only Pepperstone M5 acquisition for the frozen CRM/ADBE intraday-RV temporal retest."""
from __future__ import annotations
import csv, json, shutil
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from competition.frontier_data_capture import FrontierDataCaptureRunner, _deterministic_zip, _plain, _sha_file, _utc, canonical_plan_sha
from m6.ctrader_capture import CaptureContractError, MappingError, account_fingerprint, atomic_write_json, live_account_candidates, scan_bundle_for_secrets, select_live_pepperstone_account
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAAccountAuthReq, ProtoOAApplicationAuthReq, ProtoOAGetAccountListByAccessTokenReq, ProtoOASymbolByIdReq, ProtoOASymbolsListReq, ProtoOATraderReq
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport
from research_v3.capture_identity import build_capture_manifest
PLAN_REL="data/CRM_ADBE_M5_TEMPORAL_ACQUISITION_PLAN_V1.json"
OUTPUT_FILENAME="MXM_V3_CRM_ADBE_M5_TEMPORAL_EVIDENCE_V1.zip"
BUNDLE_DIR="MXM_V3_CRM_ADBE_M5_TEMPORAL_EVIDENCE_V1"
TOOL_VERSION="MXM_V3_CRM_ADBE_M5_TEMPORAL_ANDROID_STDLIB_V1"
EXPECTED_PLAN_SHA="3eb3155e04541c5d4dab9f7e1483f2d61732063e6213fa07d61ebc80326cf7a3"
EXPECTED={5410:"CRM.US-24",5411:"ADBE.US-24"}
EXPECTED_START="2025-01-02T00:00:00Z"
EXPECTED_END="2025-09-14T23:59:59Z"
def validate_plan(plan):
    if plan.get("schema")!="mxm.research-core-v3.crm-adbe-m5-temporal-acquisition-plan.v1": raise CaptureContractError("wrong CRM/ADBE acquisition plan schema")
    if plan.get("status")!="FROZEN_AUTHORIZED_MINIMAL_READ_ONLY_ACQUISITION": raise CaptureContractError("CRM/ADBE plan is not frozen/authorized")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or canonical_plan_sha(plan)!=EXPECTED_PLAN_SHA: raise CaptureContractError("CRM/ADBE plan hash mismatch")
    if plan.get("resolution")!="M5": raise CaptureContractError("CRM/ADBE collector is exact M5 only")
    if plan.get("account_fingerprint_sha256")!="b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636": raise CaptureContractError("Pepperstone account authority mismatch")
    got={int(x["symbol_id"]):str(x["broker_symbol"]) for x in (plan.get("symbols") or [])}
    if got!=EXPECTED or len(got)!=2: raise CaptureContractError("scope must be exactly CRM.US-24 and ADBE.US-24")
    if plan["interval"]["start_utc"]!=EXPECTED_START or plan["interval"]["end_utc"]!=EXPECTED_END: raise CaptureContractError("frozen acquisition interval changed")
    start=_utc(EXPECTED_START); end=_utc(EXPECTED_END); protected=_utc(plan["protected_forward_start"])
    if not start<end<protected: raise CaptureContractError("interval/protected boundary invalid")
    law=plan.get("capture_law") or {}
    required={"read_only":True,"orders_permitted":False,"account_mutation_permitted":False,"fill_authority":False,"raw_ticks_requested":False,"bid_ask_requested":False,"trendbars_only":True,"extra_symbols_permitted":False,"interval_extension_permitted":False,"external_datasets_permitted":False,"protected_rows_permitted":False,"forward_fill_permitted":False,"synthetic_fill_permitted":False,"exhaust_pagination":True,"preserve_authentic_gaps":True,"strict_timestamp_order":True,"reject_conflicting_duplicates":True,"verify_ohlc_invariants":True}
    for k,v in required.items():
        if law.get(k) is not v: raise CaptureContractError(f"capture law mismatch: {k}")
    out=plan.get("output_contract") or {}
    if out.get("device_computes_strategy_outcomes") is not False or out.get("device_computes_pnl") is not False or out.get("device_estimates_formation_parameters") is not False: raise CaptureContractError("device must return raw M5 only")
    if (plan.get("provenance_gate") or {}).get("status")!="PASS": raise CaptureContractError("pre-acquisition provenance gate not PASS")
    if plan.get("protected_forward_opened") is not False or int(plan.get("candidate_frozen_count") or 0)!=0: raise CaptureContractError("governance boundary mismatch")
    return True
def verify_ohlc_csv(path):
    rows=0; dates=set(); weeks=set(); first=None; last=None
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            try: o=Decimal(row["open"]); h=Decimal(row["high"]); l=Decimal(row["low"]); c=Decimal(row["close"])
            except (InvalidOperation,KeyError) as exc: raise CaptureContractError("invalid OHLC value") from exc
            if l>h or o<l or o>h or c<l or c>h: raise CaptureContractError(f"OHLC invariant failure at {row.get('time_utc')}")
            dt=_utc(row["time_utc"])
            if dt<_utc(EXPECTED_START) or dt>_utc(EXPECTED_END): raise CaptureContractError("row outside frozen requested interval")
            dates.add(dt.date().isoformat()); weeks.add((dt.isocalendar().year,dt.isocalendar().week)); first=first or row["time_utc"]; last=row["time_utc"]; rows+=1
    return {"rows":rows,"utc_dates":len(dates),"iso_weeks":len(weeks),"first":first,"last":last}
class CRMADBEM5Runner(FrontierDataCaptureRunner):
    def __init__(self,*,plan,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan); self.plan=dict(plan); self.client_id=client_id; self.client_secret=client_secret; self.access_token=access_token; self.config=dict(config); self.root=Path(repo_root); self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/"crm_adbe_m5_capture_output"/BUNDLE_DIR; self.work=self.root/".crm_adbe_m5_capture_work"/EXPECTED_PLAN_SHA[:16]; self.zip_path=self.root/OUTPUT_FILENAME
        self._app=False; self._account=None; self._last_hist=None
    def _capture_one(self,aid,spec,full):
        done,meta=super()._capture_one(aid,spec,full); check=verify_ohlc_csv(done)
        if check["rows"]!=int(meta["row_count"]): raise CaptureContractError("row-count mismatch after OHLC verification")
        m=dict(meta); m["ohlc_invariants_verified"]=True; m["integrity_summary"]=check; return done,m
    def _workflow(self):
        self.progress("[1/3] Pepperstone LIVE read-only auth + exact CRM/ADBE identity binding")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret)); self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]; saved=self.config.get("ctid_trader_account_id")
        try: account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector): raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]); self._account=aid
        if account_fingerprint(aid)!=self.plan["account_fingerprint_sha256"]: raise MappingError("LIVE account fingerprint differs from frozen Pepperstone authority")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token)); trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower(): raise MappingError("not verifiably Pepperstone")
        light=[_plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]; by_id={int(x["symbolId"]):x for x in light}
        q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid); q.symbolId.extend(list(EXPECTED)); full={int(x.symbolId):_plain(x) for x in self._send(q).symbol}
        for spec in self.plan["symbols"]:
            sid=int(spec["symbol_id"]); name=str(spec["broker_symbol"]); li=by_id.get(sid); fu=full.get(sid)
            if li is None or fu is None or str(li.get("symbolName"))!=name: raise MappingError(f"identity mismatch {name}/{sid}")
            if li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0: raise MappingError(f"identity no longer new-entry tradable: {name}")
        self.progress("[2/3] Capturing exact two-symbol frozen M5 interval; no strategy outcomes computed")
        raw_dir=self.bundle/"raw"; raw_dir.mkdir(parents=True,exist_ok=True); results=[]
        for i,spec in enumerate(self.plan["symbols"],1):
            done,meta=self._capture_one(aid,spec,full[int(spec["symbol_id"])]); target=raw_dir/done.name; shutil.copyfile(done,target); m=dict(meta); m["file"]=target.relative_to(self.bundle).as_posix(); results.append(m); self.progress(f"[SERIES {i}/2] {spec['broker_symbol']} rows={m['row_count']:,}")
        nonempty=all(int(x.get("row_count") or 0)>0 for x in results); status="CAPTURE_COMPLETE_DATA_SUFFICIENCY_PENDING_DIRECTOR_ACCEPTANCE" if nonempty else "DATA_UNAVAILABLE"
        captured_utc=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        payload={"schema":"mxm.research-core-v3.crm-adbe-m5-temporal-capture-bundle.v1","status":status,"captured_utc":captured_utc,"tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,"account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],"source_environment":self.plan["source_environment"],"resolution":"M5","requested_interval":self.plan["interval"],"symbols":["CRM.US-24","ADBE.US-24"],"series":results,"formation_parameters_estimated_on_device":False,"strategy_outcomes_computed":False,"pnl_computed":False,"orders_placed":False,"account_mutation":False,"fill_authority":False,"bid_ask_captured":False,"ticks_captured":False,"protected_evidence_opened":False,"automatic_extension":False}
        payload_path=self.bundle/"CAPTURE_PAYLOAD.json"; atomic_write_json(payload_path,payload)
        manifest=build_capture_manifest(capture_session_id=f"crm-adbe-m5-{EXPECTED_PLAN_SHA[:16]}",capture_schema=payload["schema"],tool_version=TOOL_VERSION,account_fingerprint=self.plan["account_fingerprint_sha256"],source_environment=self.plan["source_environment"],capture_start_utc=self.plan["interval"]["start_utc"],capture_end_utc=captured_utc,completion_state="COMPLETE" if nonempty else "DATA_UNAVAILABLE",canonical_payloads={"CAPTURE_PAYLOAD.json":payload_path.read_bytes()},original_collector_package_sha256=None,read_only_assertion=True,economic_outcomes_opened=0,orders_placed=False,account_mutation=False,protected_evidence_opened=False)
        atomic_write_json(self.bundle/"CAPTURE_MANIFEST.json",manifest); checks=[]
        for p in sorted(x for x in self.bundle.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256"): checks.append(f"{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}")
        (self.bundle/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8"); scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])
        self.progress("[3/3] Building deterministic transferable evidence ZIP"); digest=_deterministic_zip(self.bundle,self.zip_path); self.progress(f"[DONE] {self.zip_path.name} SHA256={digest}")
        if not nonempty: self.progress("[DATA_UNAVAILABLE] One or both frozen symbols returned zero M5 bars; do not substitute interval/resolution.")
        return self.zip_path
