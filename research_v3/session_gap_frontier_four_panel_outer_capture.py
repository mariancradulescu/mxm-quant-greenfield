"""Read-only independent outer M5 + friction capture for the frozen SESSION_GAP four-panel frontier."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from google.protobuf.json_format import MessageToDict

from competition.ultra_fast_capture import (
    UltraFastCaptureRunner,
    ImplementationInvalid,
    _write_checksums,
    _verify_checksums,
)
from m6.ctrader_capture import (
    CaptureContractError,
    MappingError,
    account_fingerprint,
    atomic_write_json,
    live_account_candidates,
    redact_text,
    require_read_only_request,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAAssetListReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport

PLAN_REL="data/SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json"
BASE_PROTOCOL_REL="data/COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json"
EXPECTED_PLAN_SHA="1cddfd3e8a21a992bd3ab756ecf191c0c3e83487a35b266e714388252476ee3f"
OUTPUT_FILENAME="MXM_SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_M5_13W_FRICTION_V1.zip"
BUNDLE_DIR="MXM_SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_M5_13W_FRICTION_V1"
TOOL_VERSION="MXM_SESSION_GAP_FRONTIER_FOUR_PANEL_OUTER_ANDROID_STDLIB_V1"
EXPECTED_SYMBOLS={
    "ZARJPY":98,"US400":7372,"XPDUSD":95,"NETH25":269,
}

def _plain(message):
    return MessageToDict(message,preserving_proto_field_name=False,use_integers_for_enums=True)

def _canon(obj):
    value={k:v for k,v in obj.items() if k!="plan_sha256"}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def _sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def validate_outer_plan(plan):
    if plan.get("schema")!="mxm.greenfield.session-gap-frontier-four-panel-independent-outer-capture-plan.v1":
        raise CaptureContractError("wrong four-panel outer plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_PRE_OUTER_OUTCOME":
        raise CaptureContractError("outer plan is not prospectively frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or _canon(plan)!=EXPECTED_PLAN_SHA:
        raise CaptureContractError("outer plan SHA mismatch")
    observed={str(x["broker_symbol"]):int(x["symbol_id"]) for x in plan.get("symbols") or []}
    if observed!=EXPECTED_SYMBOLS:
        raise CaptureContractError("four-panel identity drift")
    if plan.get("resolution")!="M5":
        raise CaptureContractError("outer collector is M5-only")
    outer=plan["outer_interval"]; source=plan["source_development_interval"]
    if not (outer["end_utc"] < source["start_utc"]):
        raise CaptureContractError("outer interval is not strictly disjoint from DEVELOPMENT")
    if not (outer["end_utc"] < plan["protected_forward_start"]):
        raise CaptureContractError("outer interval reaches protected-forward boundary")
    law=plan.get("capture_law") or {}
    if law.get("read_only") is not True or law.get("orders_permitted") is not False or law.get("account_mutation_permitted") is not False:
        raise CaptureContractError("outer collector is not read-only")
    contract=plan.get("outer_contract") or {}
    if contract.get("source_development_bytes_may_be_outer") is not False or contract.get("outer_unopened_before_freeze") is not True:
        raise CaptureContractError("independent outer contract drift")
    if plan.get("economic_outcomes_opened")!=0 or plan.get("v2_attempts_consumed")!=0:
        raise CaptureContractError("outer capture must be non-economic")
    return True

def build_outer_protocol(plan,base):
    protocol=copy.deepcopy(base)
    dates=list(plan["friction_authority"]["sample_dates"])
    profiles=protocol["friction_screen"]["profiles"]
    profiles["GLOBAL_24X5"]={
        "sample_dates":dates,
        "utc_windows":copy.deepcopy(plan["friction_authority"]["GLOBAL_24X5_windows"]),
    }
    return protocol

class FourPanelIndependentOuterCaptureRunner(UltraFastCaptureRunner):
    def __init__(self,*,plan,base_protocol,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_outer_plan(plan)
        self.outer_plan=copy.deepcopy(plan)
        self.plan={
            "stage_a_interval":copy.deepcopy(plan["outer_interval"]),
            "capture_law":{
                "max_tick_pages_per_side_window":int(plan["capture_law"]["max_tick_pages_per_side_window"]),
                "max_stage_a_pages_per_symbol":int(plan["capture_law"]["max_stage_a_pages_per_symbol"]),
                "trendbar_pagination":{"page_count":int(plan["capture_law"]["trendbar_page_count"])},
            },
        }
        self.protocol=build_outer_protocol(plan,base_protocol)
        self.client_id=client_id; self.client_secret=client_secret; self.access_token=access_token
        self.config=dict(config); self.root=Path(repo_root); self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/"session_gap_frontier_four_panel_outer_output"/BUNDLE_DIR
        self.zip_path=self.root/OUTPUT_FILENAME
        self._app=False; self._account=None; self._last=None; self._requests=0
        self._tick_cache={}; self._conversion_chain_cache={}; self._conversion_rate_cache={}
        self._assets={}; self._asset_ids={}; self._light={}

    def _mapping(self,aid):
        self._assets={str(x.get("assetId")):x.get("name") for x in [_plain(y) for y in self._send(ProtoOAAssetListReq(ctidTraderAccountId=aid)).asset]}
        self._asset_ids={str(name).upper():int(asset_id) for asset_id,name in self._assets.items() if name}
        self._light={int(x["symbolId"]):x for x in [_plain(y) for y in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]}
        q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid); q.symbolId.extend([x["symbol_id"] for x in self.outer_plan["symbols"]])
        full={int(x.symbolId):_plain(x) for x in self._send(q).symbol}
        for candidate in self.outer_plan["symbols"]:
            li=self._light.get(candidate["symbol_id"]); fu=full.get(candidate["symbol_id"])
            if not li or not fu or li.get("symbolName")!=candidate["broker_symbol"] or li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0:
                raise MappingError(f"outer panel mapping/tradability mismatch {candidate['broker_symbol']}")
        return full

    def _validate_bundle(self,friction,series,manifest):
        if len(friction)!=4 or len(series)!=4:
            raise ImplementationInvalid("outer bundle must contain exactly four fixed panel symbols")
        if {x["broker_symbol"] for x in friction}!=set(EXPECTED_SYMBOLS):
            raise ImplementationInvalid("outer friction panel mismatch")
        if {x["broker_symbol"] for x in series}!=set(EXPECTED_SYMBOLS):
            raise ImplementationInvalid("outer M5 panel mismatch")
        for row in series:
            pag=row.get("pagination") or {}
            if pag.get("request_interval_exhausted") is not True:
                raise ImplementationInvalid(f"incomplete outer M5 traversal {row['broker_symbol']}")
            if int(row.get("row_count") or 0)<500:
                raise ImplementationInvalid(f"insufficient outer M5 rows {row['broker_symbol']}")
        if manifest.get("outer_outcome_opened") is not False:
            raise ImplementationInvalid("collector must not open outer outcome")
        if manifest.get("economic_outcomes_opened")!=0 or manifest.get("v2_attempts_consumed")!=0:
            raise ImplementationInvalid("collector mutated economic accounting")
        if manifest.get("raw_ticks_transferred") is not False:
            raise ImplementationInvalid("raw friction ticks may not be transferred")
        return True

    def _workflow(self):
        self.progress("[1/5] Pepperstone LIVE read-only account binding")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret)); self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved=self.config.get("ctid_trader_account_id")
        try:
            account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector): raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]); self._account=aid
        if account_fingerprint(aid)!=self.outer_plan["account_fingerprint_sha256"]:
            raise MappingError("LIVE account fingerprint differs from accepted broker-native universe")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():
            raise MappingError("not verifiably Pepperstone")
        full=self._mapping(aid)

        self.progress("[2/5] Frozen candidate-independent historical friction evidence for the fixed four-panel")
        friction=[]
        for i,candidate in enumerate(self.outer_plan["symbols"],1):
            metrics=self._friction(aid,candidate,full[candidate["symbol_id"]],self._light[candidate["symbol_id"]])
            friction.append(metrics)
            self.progress(f"[FRICTION {i}/4] {candidate['broker_symbol']} state={metrics['friction_state']} cost={metrics['cost_confidence_state']}")

        self.progress("[3/5] Strictly disjoint 13-week M5 outer bytes")
        series=[]
        for i,candidate in enumerate(self.outer_plan["symbols"],1):
            rows,pagination=self._stage_rows(aid,candidate,full[candidate["symbol_id"]])
            series.append(self._write_rows(candidate,rows,pagination))
            self.progress(f"[M5 {i}/4] {candidate['broker_symbol']} rows={len(rows):,} completion={pagination['completion_reason']}")

        self.progress("[4/5] Compact friction/conversion authority + fail-closed bundle validation")
        conversion=self._conversion_summary()
        friction_doc={
            "schema":"mxm.greenfield.session-gap-frontier-four-panel-independent-outer-friction.v1",
            "status":"CAPTURED_PRE_OUTER_INTERPRETATION",
            "plan_sha256":EXPECTED_PLAN_SHA,
            "method":self.outer_plan["friction_authority"]["method"],
            "sample_dates":self.outer_plan["friction_authority"]["sample_dates"],
            "results":friction,
            "raw_ticks_transferred":False,
            "raw_conversion_ticks_transferred":False,
            "candidate_outcomes_used":False,
        }
        manifest={
            "schema":"mxm.greenfield.session-gap-frontier-four-panel-independent-outer-bundle.v1",
            "status":"CAPTURE_COMPLETE_OUTER_UNOPENED",
            "captured_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "tool_version":TOOL_VERSION,
            "plan_sha256":EXPECTED_PLAN_SHA,
            "source_freeze_ref":self.outer_plan["source_freeze_ref"],
            "source_development_capture_sha256":self.outer_plan["source_development_capture_sha256"],
            "outer_interval":self.outer_plan["outer_interval"],
            "resolution":"M5",
            "series":series,
            "friction_symbol_count":len(friction),
            "historical_requests":self._requests,
            "conversion_chain_count":conversion["chain_count"],
            "conversion_window_rate_count":conversion["window_rate_count"],
            "raw_ticks_transferred":False,
            "raw_conversion_ticks_transferred":False,
            "orders_placed":False,
            "account_mutation":False,
            "protected_evidence_opened":False,
            "outer_outcome_opened":False,
            "economic_outcomes_opened":0,
            "v2_attempts_consumed":0,
        }
        atomic_write_json(self.bundle/"friction_summary.json",friction_doc)
        atomic_write_json(self.bundle/"historical_conversion_summary.json",conversion)
        atomic_write_json(self.bundle/"capture_manifest.json",manifest)
        self._validate_bundle(friction,series,manifest)
        _write_checksums(self.bundle); _verify_checksums(self.bundle)
        scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])

        self.progress("[5/5] Deterministic transferable outer ZIP")
        with zipfile.ZipFile(self.zip_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for path in sorted(x for x in self.bundle.rglob("*") if x.is_file()):
                info=zipfile.ZipInfo(path.relative_to(self.bundle).as_posix(),(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o644<<16
                z.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        self.progress(f"[DONE] {self.zip_path.name} bytes={self.zip_path.stat().st_size:,} SHA256={_sha(self.zip_path)}")

    def run(self):
        if self.bundle.exists(): shutil.rmtree(self.bundle)
        self.bundle.mkdir(parents=True); self.zip_path.unlink(missing_ok=True)
        try:
            self.transport.connect(); self._workflow()
        except (TypeError,AssertionError,KeyError,ValueError) as exc:
            raise ImplementationInvalid(f"IMPLEMENTATION_INVALID: {redact_text(str(exc))}") from exc
        finally:
            self.transport.close()
        return self.zip_path
