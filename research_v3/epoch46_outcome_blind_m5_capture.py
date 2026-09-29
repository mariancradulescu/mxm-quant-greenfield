"""Epoch46 staged outcome-blind Pepperstone M5 acquisition wave."""
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
PLAN_REL="data/EPOCH46_OUTCOME_BLIND_M5_ACQUISITION_WAVE_01_PLAN_V1.json"
OUTPUT_FILENAME="MXM_EPOCH46_OUTCOME_BLIND_M5_WAVE_01.zip"
BUNDLE_DIR="MXM_EPOCH46_OUTCOME_BLIND_M5_WAVE_01"
TOOL_VERSION="MXM_EPOCH46_OUTCOME_BLIND_M5_ANDROID_STDLIB_V1"
EXPECTED_PLAN_SHA="70706ee9c04fb262cf38be8c6cbd0fd7450c91e6d870e5c5f80c9301724ae247"
EXPECTED_SYMBOL_COUNT=34
EXPECTED_PEER_INDEX_BLOB_SHA1="0910fa14264054b4913077f5dffa74dc2569749d"
PRIOR_ACCEPTED_M5_SCOPE_FLOOR_UTC="2026-03-16T00:00:00Z"

def validate_plan(plan):
    if plan.get("schema")!="mxm.greenfield.epoch46-outcome-blind-m5-acquisition-wave.v1": raise CaptureContractError("wrong Epoch46 wave schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_NON_ECONOMIC_OUTCOME_BLIND": raise CaptureContractError("Epoch46 wave is not frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or canonical_plan_sha(plan)!=EXPECTED_PLAN_SHA: raise CaptureContractError("Epoch46 plan hash mismatch")
    if plan.get("resolution")!="M5": raise CaptureContractError("Epoch46 capture is M5-only")
    syms=plan.get("symbols") or []; ids=[int(x["symbol_id"]) for x in syms]; names=[str(x["broker_symbol"]) for x in syms]; cohorts=[str(x["peer_candidate_cohort_id"]) for x in syms]
    if len(syms)!=EXPECTED_SYMBOL_COUNT or len(set(ids))!=EXPECTED_SYMBOL_COUNT or len(set(names))!=EXPECTED_SYMBOL_COUNT or len(set(cohorts))!=EXPECTED_SYMBOL_COUNT: raise CaptureContractError("Epoch46 wave must contain 34 unique identities/cohorts")
    if any(x.get("history_state_at_freeze")!="NO_ACCEPTED_M5_SCOPE_IN_EPOCH45_AUDIT" for x in syms): raise CaptureContractError("Epoch46 wave contains a previously accepted M5 identity")
    sel=plan.get("selection_authority") or {}
    if sel.get("peer_cohort_index_git_blob_sha1")!=EXPECTED_PEER_INDEX_BLOB_SHA1 or int(sel.get("accepted_scope_identity_exclusion_count") or 0)!=45 or sel.get("outcomes_used") is not False: raise CaptureContractError("Epoch46 outcome-blind selection authority mismatch")
    if plan.get("accounting_effect")!={"economic_outcomes_opened":0,"v2_attempts_consumed":0,"v2_search_budget_change":0}: raise CaptureContractError("Epoch46 acquisition changed accounting")
    if plan.get("protected_evidence_opened") is not False: raise CaptureContractError("protected evidence flag invalid")
    start=_utc(plan["interval"]["start_utc"]); end=_utc(plan["interval"]["end_utc"]); floor=_utc(PRIOR_ACCEPTED_M5_SCOPE_FLOOR_UTC); protected=_utc(plan["protected_forward_start"])
    if not start<end<floor<protected: raise CaptureContractError("Epoch46 DEVELOPMENT interval is not earlier/disjoint")
    law=plan.get("capture_law") or {}
    req={"read_only":True,"orders_permitted":False,"account_mutation_permitted":False,"forward_fill_permitted":False,"synthetic_fill_permitted":False,"protected_rows_permitted":False,"exhaust_pagination":True,"preserve_authentic_gaps":True,"strict_timestamp_order":True,"reject_conflicting_duplicates":True,"verify_ohlc_invariants":True}
    for k,v in req.items():
        if law.get(k) is not v: raise CaptureContractError(f"Epoch46 capture law mismatch: {k}")
    return True

def verify_ohlc_csv(path):
    rows=0
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            try: o=Decimal(row["open"]); h=Decimal(row["high"]); l=Decimal(row["low"]); c=Decimal(row["close"])
            except (InvalidOperation,KeyError) as exc: raise CaptureContractError("invalid OHLC value") from exc
            if l>h or o<l or o>h or c<l or c>h: raise CaptureContractError(f"OHLC invariant failure at {row.get('time_utc')}")
            rows+=1
    return rows

def schedule_adjusted_completeness_proxy(spec,row_count,weeks):
    expected=float(spec["schedule_minutes_per_week"])*float(weeks)/5.0
    return {"basis":"CURRENT_ACCEPTED_SCHEDULE_MINUTES_PROXY_NO_SYNTHETIC_HOLIDAY_FILL","expected_m5_bars_proxy":expected,"observed_m5_bars":int(row_count),"coverage_ratio_proxy":(float(row_count)/expected if expected>0 else None),"historical_holiday_schedule_exactness_claimed":False}

class Epoch46OutcomeBlindM5Runner(FrontierDataCaptureRunner):
    def __init__(self,*,plan,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan); self.plan=dict(plan); self.client_id=client_id; self.client_secret=client_secret; self.access_token=access_token; self.config=dict(config); self.root=Path(repo_root); self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60); self.bundle=self.root/"epoch46_outcome_blind_capture_output"/BUNDLE_DIR; self.work=self.root/".epoch46_outcome_blind_capture_work"/EXPECTED_PLAN_SHA[:16]; self.zip_path=self.root/OUTPUT_FILENAME; self._app=False; self._account=None; self._last_hist=None
    def _capture_one(self,aid,spec,full):
        done,meta=super()._capture_one(aid,spec,full); verified=verify_ohlc_csv(done)
        if verified!=int(meta["row_count"]): raise CaptureContractError("row-count mismatch after OHLC verification")
        meta=dict(meta); meta["ohlc_invariants_verified"]=True; meta["schedule_adjusted_completeness"]=schedule_adjusted_completeness_proxy(spec,verified,self.plan["interval"]["weeks"]); return done,meta
    def _workflow(self):
        self.progress("[1/3] Pepperstone LIVE read-only auth + exact Epoch46 identity binding")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret)); self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]; saved=self.config.get("ctid_trader_account_id")
        try: account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector): raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]); self._account=aid
        if account_fingerprint(aid)!=self.plan["account_fingerprint_sha256"]: raise MappingError("LIVE account fingerprint differs from accepted Pepperstone authority")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token)); trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower(): raise MappingError("not verifiably Pepperstone")
        light=[_plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]; L={int(x["symbolId"]):x for x in light}; ids=[int(x["symbol_id"]) for x in self.plan["symbols"]]; full={}
        q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid); q.symbolId.extend(ids)
        for x in self._send(q).symbol: full[int(x.symbolId)]=_plain(x)
        for spec in self.plan["symbols"]:
            sid=int(spec["symbol_id"]); name=spec["broker_symbol"]; li=L.get(sid); fu=full.get(sid)
            if li is None or fu is None or str(li.get("symbolName"))!=name: raise MappingError(f"Epoch46 mapping mismatch {name}/{sid}")
            if li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0: raise MappingError(f"Epoch46 identity no longer new-entry tradable: {name}")
        self.progress("[2/3] Capturing exact 34-identity earlier disjoint M5 DEVELOPMENT wave")
        results=[]; raw_dir=self.bundle/"raw"; raw_dir.mkdir(parents=True,exist_ok=True)
        for i,spec in enumerate(self.plan["symbols"],1):
            done,meta=self._capture_one(aid,spec,full[int(spec["symbol_id"])]); target=raw_dir/done.name; shutil.copyfile(done,target); meta=dict(meta); meta["file"]=target.relative_to(self.bundle).as_posix(); meta["peer_candidate_cohort_id"]=spec["peer_candidate_cohort_id"]; meta["structural_stratum"]=spec["structural_stratum"]; results.append(meta); self.progress(f"[SERIES {i}/{EXPECTED_SYMBOL_COUNT} PASS] {spec['broker_symbol']} rows={meta['row_count']:,}")
        captured_utc=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        payload={"schema":"mxm.greenfield.epoch46-outcome-blind-m5-capture-bundle.v1","status":"M5_OUTCOME_BLIND_WAVE_01_CAPTURE_COMPLETE","captured_utc":captured_utc,"tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,"global_decision_ref":self.plan["selection_authority"]["global_decision_ref"],"peer_cohort_index_ref":self.plan["selection_authority"]["peer_cohort_index_ref"],"account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],"source_environment":self.plan["source_environment"],"resolution":"M5","requested_interval":self.plan["interval"],"series":results,"orders_placed":False,"account_mutation":False,"protected_evidence_opened":False,"economic_outcomes_opened":0,"v2_attempts_consumed":0,"strategy_returns_computed":False,"pnl_computed":False,"winner_selection_performed":False}
        payload_path=self.bundle/"EPOCH46_CAPTURE_PAYLOAD.json"; atomic_write_json(payload_path,payload)
        identity_manifest=build_capture_manifest(capture_session_id=f"epoch46-wave01-{EXPECTED_PLAN_SHA[:16]}",capture_schema=payload["schema"],tool_version=TOOL_VERSION,account_fingerprint=self.plan["account_fingerprint_sha256"],source_environment=self.plan["source_environment"],capture_start_utc=self.plan["interval"]["start_utc"],capture_end_utc=captured_utc,completion_state="COMPLETE",canonical_payloads={"EPOCH46_CAPTURE_PAYLOAD.json":payload_path.read_bytes()},original_collector_package_sha256=None,read_only_assertion=True,economic_outcomes_opened=0,orders_placed=False,account_mutation=False,protected_evidence_opened=False)
        atomic_write_json(self.bundle/"CAPTURE_MANIFEST.json",identity_manifest); checks=[]
        for p in sorted(x for x in self.bundle.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256"): checks.append(f"{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}")
        (self.bundle/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8"); scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token]); self.progress("[3/3] Deterministic transferable ZIP"); digest=_deterministic_zip(self.bundle,self.zip_path); self.progress(f"[DONE] {self.zip_path.name} SHA256={digest}")
