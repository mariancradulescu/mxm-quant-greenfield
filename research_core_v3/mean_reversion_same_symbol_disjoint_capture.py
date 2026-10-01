"""Read-only Pepperstone M5 acquisition for the frozen same-symbol mean-reversion temporal generalization test."""
from __future__ import annotations
import csv, shutil
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from competition.frontier_data_capture import FrontierDataCaptureRunner,_deterministic_zip,_plain,_sha_file,_utc,canonical_plan_sha
from m6.ctrader_capture import CaptureContractError,MappingError,account_fingerprint,atomic_write_json,live_account_candidates,scan_bundle_for_secrets,select_live_pepperstone_account
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAAccountAuthReq,ProtoOAApplicationAuthReq,ProtoOAGetAccountListByAccessTokenReq,ProtoOASymbolByIdReq,ProtoOASymbolsListReq,ProtoOATraderReq
from m6.ctrader_transport import LIVE_HOST,LIVE_PORT,StdlibCTraderTransport
from research_v3.capture_identity import build_capture_manifest

PLAN_REL="data/MEAN_REVERSION_SAME_SYMBOL_DISJOINT_M5_ACQUISITION_PLAN_V1.json"
OUTPUT_FILENAME="MXM_V3_MEAN_REVERSION_SAME_SYMBOL_DISJOINT_M5_EVIDENCE_V1.zip"
BUNDLE_DIR="MXM_V3_MEAN_REVERSION_SAME_SYMBOL_DISJOINT_M5_EVIDENCE_V1"
TOOL_VERSION="MXM_V3_MEAN_REVERSION_SAME_SYMBOL_DISJOINT_M5_ANDROID_STDLIB_V1"
EXPECTED_PLAN_SHA="86ac0d74e744dfdc63d1b8291bfe2b367ee28ca4f06fa614b36b69b6da845152"
EXPECTED={49:"USDZAR",61:"GBPSEK",87:"NOKSEK",2764:"AUDNOK",2767:"CADSGD",2785:"EURILS"}
EXPOSURE_FLOOR="2025-09-16T00:00:00Z"

def validate_plan(plan):
    if plan.get("schema")!="mxm.research-core-v3.mean-reversion-same-symbol-disjoint-m5-acquisition-plan.v1": raise CaptureContractError("wrong same-symbol plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_OUTCOME_BLIND_SAME_SYMBOL_TEMPORAL_TEST": raise CaptureContractError("same-symbol plan is not frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or canonical_plan_sha(plan)!=EXPECTED_PLAN_SHA: raise CaptureContractError("same-symbol plan hash mismatch")
    if plan.get("resolution")!="M5": raise CaptureContractError("same-symbol collector is M5-only")
    if plan.get("account_fingerprint_sha256")!="b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636": raise CaptureContractError("account authority mismatch")
    syms=plan.get("symbols") or []; got={int(x["symbol_id"]):str(x["broker_symbol"]) for x in syms}
    if got!=EXPECTED or len(syms)!=6: raise CaptureContractError("same-symbol scope must be the exact six frozen identities")
    a=plan.get("frozen_architecture") or {}
    if a.get("id")!="HALF_REVERSION_PROGRESS_VOL_TRAIL_V1" or a.get("design_commit")!="5b412dd57d66e14e361b33b0bbf90ba9b681c14a" or a.get("parameters_must_remain_unchanged") is not True: raise CaptureContractError("frozen exit architecture binding mismatch")
    start=_utc(plan["interval"]["start_utc"]); end=_utc(plan["interval"]["end_utc"]); floor=_utc(EXPOSURE_FLOOR); protected=_utc(plan["protected_forward_start"])
    if plan["interval"].get("weeks")!=13 or not start<end<floor<protected: raise CaptureContractError("disjoint interval boundary invalid")
    if plan["interval"]["start_utc"]!="2025-06-16T00:00:00Z" or plan["interval"]["end_utc"]!="2025-09-14T23:59:59Z": raise CaptureContractError("interval changed after freeze")
    law=plan.get("capture_law") or {}
    required={"read_only":True,"orders_permitted":False,"account_mutation_permitted":False,"forward_fill_permitted":False,"synthetic_fill_permitted":False,"protected_rows_permitted":False,"exhaust_pagination":True,"preserve_authentic_gaps":True,"strict_timestamp_order":True,"reject_conflicting_duplicates":True,"verify_ohlc_invariants":True,"raw_ticks_requested":False,"trendbars_only":True}
    for k,v in required.items():
        if law.get(k) is not v: raise CaptureContractError(f"capture law mismatch: {k}")
    if (plan.get("scientific_boundary") or {}).get("no_automatic_additional_acquisition") is not True: raise CaptureContractError("automatic acquisition must remain disabled")
    if plan.get("protected_forward_opened") is not False: raise CaptureContractError("protected-forward flag invalid")
    return True

def verify_ohlc_csv(path):
    rows=0; weeks=set()
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            try: o=Decimal(row["open"]); h=Decimal(row["high"]); l=Decimal(row["low"]); c=Decimal(row["close"])
            except (InvalidOperation,KeyError) as exc: raise CaptureContractError("invalid OHLC value") from exc
            if l>h or o<l or o>h or c<l or c>h: raise CaptureContractError(f"OHLC invariant failure at {row.get('time_utc')}")
            dt=_utc(row["time_utc"]); weeks.add((dt.isocalendar().year,dt.isocalendar().week)); rows+=1
    return rows,len(weeks)

def completeness(spec,row_count):
    expected=float(spec["schedule_minutes_per_week"])*13.0/5.0
    return {"basis":"CURRENT_ACCEPTED_FX_SCHEDULE_MINUTES_PROXY_NO_SYNTHETIC_HOLIDAY_FILL","expected_m5_bars_proxy":expected,"observed_m5_bars":int(row_count),"coverage_ratio_proxy":float(row_count)/expected if expected>0 else None,"historical_holiday_schedule_exactness_claimed":False}

class SameSymbolDisjointM5Runner(FrontierDataCaptureRunner):
    def __init__(self,*,plan,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan); self.plan=dict(plan); self.client_id=client_id; self.client_secret=client_secret; self.access_token=access_token; self.config=dict(config); self.root=Path(repo_root); self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60); self.bundle=self.root/"same_symbol_disjoint_capture_output"/BUNDLE_DIR; self.work=self.root/".same_symbol_disjoint_capture_work"/EXPECTED_PLAN_SHA[:16]; self.zip_path=self.root/OUTPUT_FILENAME; self._app=False; self._account=None; self._last_hist=None
    def _capture_one(self,aid,spec,full):
        done,meta=super()._capture_one(aid,spec,full); rows,weeks=verify_ohlc_csv(done)
        if rows!=int(meta["row_count"]): raise CaptureContractError("row-count mismatch after OHLC verification")
        m=dict(meta); m["ohlc_invariants_verified"]=True; m["active_iso_weeks"]=weeks; m["schedule_adjusted_completeness"]=completeness(spec,rows); return done,m
    def _workflow(self):
        self.progress("[1/3] Pepperstone LIVE read-only auth + exact six-symbol identity binding")
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
        light=[_plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]; L={int(x["symbolId"]):x for x in light}; ids=list(EXPECTED); full={}
        q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid); q.symbolId.extend(ids)
        for x in self._send(q).symbol: full[int(x.symbolId)]=_plain(x)
        for spec in self.plan["symbols"]:
            sid=int(spec["symbol_id"]); name=spec["broker_symbol"]; li=L.get(sid); fu=full.get(sid)
            if li is None or fu is None or str(li.get("symbolName"))!=name: raise MappingError(f"same-symbol mapping mismatch {name}/{sid}")
            if li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0: raise MappingError(f"same-symbol identity no longer new-entry tradable: {name}")
        self.progress("[2/3] Capturing exact six-symbol 13-week pre-exposure M5 interval")
        results=[]; raw_dir=self.bundle/"raw"; raw_dir.mkdir(parents=True,exist_ok=True)
        for i,spec in enumerate(self.plan["symbols"],1):
            done,meta=self._capture_one(aid,spec,full[int(spec["symbol_id"])]); target=raw_dir/done.name; shutil.copyfile(done,target); meta=dict(meta); meta["file"]=target.relative_to(self.bundle).as_posix(); meta["planning_friction_bps"]=spec["planning_friction_bps"]; results.append(meta); self.progress(f"[SERIES {i}/6] {spec['broker_symbol']} rows={meta['row_count']:,} active_weeks={meta['active_iso_weeks']}")
        captured_utc=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        acceptance=self.plan["post_capture_acceptance"]; sufficient=[]
        for m in results:
            cov=(m.get("schedule_adjusted_completeness") or {}).get("coverage_ratio_proxy")
            sufficient.append(int(m.get("active_iso_weeks") or 0)>=int(acceptance["minimum_active_iso_weeks_per_symbol"]) and cov is not None and float(cov)>=float(acceptance["schedule_adjusted_coverage_proxy_floor"]))
        payload={"schema":"mxm.research-core-v3.mean-reversion-same-symbol-disjoint-m5-capture-bundle.v1","status":"CAPTURE_COMPLETE_DATA_SUFFICIENCY_PENDING_DIRECTOR_ACCEPTANCE","captured_utc":captured_utc,"tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,"architecture_id":"HALF_REVERSION_PROGRESS_VOL_TRAIL_V1","account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],"source_environment":self.plan["source_environment"],"resolution":"M5","requested_interval":self.plan["interval"],"mean_reversion_exposure_floor_utc":EXPOSURE_FLOOR,"series":results,"all_six_meet_frozen_capture_sufficiency_proxy":all(sufficient),"orders_placed":False,"account_mutation":False,"protected_evidence_opened":False,"economic_outcomes_opened":0,"strategy_returns_computed":False,"pnl_computed":False,"winner_selection_performed":False,"automatic_additional_acquisition":False}
        payload_path=self.bundle/"CAPTURE_PAYLOAD.json"; atomic_write_json(payload_path,payload)
        identity=build_capture_manifest(capture_session_id=f"mr-same-symbol-{EXPECTED_PLAN_SHA[:16]}",capture_schema=payload["schema"],tool_version=TOOL_VERSION,account_fingerprint=self.plan["account_fingerprint_sha256"],source_environment=self.plan["source_environment"],capture_start_utc=self.plan["interval"]["start_utc"],capture_end_utc=captured_utc,completion_state="COMPLETE",canonical_payloads={"CAPTURE_PAYLOAD.json":payload_path.read_bytes()},original_collector_package_sha256=None,read_only_assertion=True,economic_outcomes_opened=0,orders_placed=False,account_mutation=False,protected_evidence_opened=False)
        atomic_write_json(self.bundle/"CAPTURE_MANIFEST.json",identity); checks=[]
        for p in sorted(x for x in self.bundle.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256"): checks.append(f"{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}")
        (self.bundle/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8"); scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token]); self.progress("[3/3] Deterministic transferable ZIP"); digest=_deterministic_zip(self.bundle,self.zip_path); self.progress(f"[DONE] {self.zip_path.name} SHA256={digest}")
