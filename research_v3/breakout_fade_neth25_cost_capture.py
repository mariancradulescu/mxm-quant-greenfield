"""Read-only NETH25 transaction-local cost evidence capture for frozen breakout-fade research."""
from __future__ import annotations

import csv
import copy
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.protobuf.json_format import MessageToDict

from competition.ultra_fast_capture import (
    UltraFastCaptureRunner,
    ImplementationInvalid,
    PROTECTED_UTC,
    _canon,
    _iso,
    _ms,
    _plain,
    _utc,
    _write_checksums,
    _verify_checksums,
)
from m6.cost_evidence import causal_merge_bid_ask
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
from research_v3.breakout_volatility_30m_persistence_screen import _event_direction

PLAN_REL="data/BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_CAPTURE_PLAN_V1.json"
BASE_PROTOCOL_REL="data/COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json"
EXPECTED_PLAN_SHA="2afa8dc853068442cd36e3f02653f034e21183e15e06745e023a561f59e238a9"
OUTPUT_FILENAME="MXM_BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_V1.zip"
PACKAGE_OUTPUT_DIR="breakout_fade_neth25_cost_output"
BUNDLE_DIR="MXM_BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_V1"
TOOL_VERSION="MXM_BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_ANDROID_V1"
EXPECTED_SYMBOL={"broker_symbol":"NETH25","symbol_id":269,"family":"INDEX"}
COST_FIELDS=(
    "event_bar_time_utc","event_direction",
    "entry_boundary_utc","entry_execution_state_utc","entry_quote_delay_ms",
    "entry_spread","entry_one_side_commission_price_equivalent","entry_cost_confidence_state",
    "exit_boundary_utc","exit_execution_state_utc","exit_quote_delay_ms",
    "exit_spread","exit_one_side_commission_price_equivalent","exit_cost_confidence_state",
    "roundtrip_cost_price_equivalent","cost_state",
)

def _sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def validate_cost_plan(plan):
    if plan.get("schema")!="mxm.greenfield.breakout-fade-neth25-transaction-local-cost-capture-plan.v1":
        raise CaptureContractError("wrong NETH25 cost-capture plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_PRE_ECONOMIC_OUTCOME":
        raise CaptureContractError("NETH25 cost-capture plan is not prospectively frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or _canon(plan)!=EXPECTED_PLAN_SHA:
        raise CaptureContractError("NETH25 cost-capture plan SHA mismatch")
    if plan.get("symbol")!=EXPECTED_SYMBOL:
        raise CaptureContractError("NETH25 cost-capture symbol identity drift")
    if plan.get("resolution")!="M5":
        raise CaptureContractError("NETH25 cost collector is M5-only")
    capture=plan.get("capture_interval") or {}
    analysis=plan.get("event_analysis_interval") or {}
    protected=_utc(plan.get("protected_forward_start"))
    if _utc(capture["end_utc"])>=protected:
        raise CaptureContractError("capture interval reaches protected-forward boundary")
    if _utc(analysis["end_utc"])+timedelta(minutes=36)>=protected:
        raise CaptureContractError("latest event cost window could reach protected-forward boundary")
    if _utc(analysis["start_utc"])<_utc(capture["start_utc"]) or _utc(analysis["end_utc"])>_utc(capture["end_utc"]):
        raise CaptureContractError("event-analysis interval is outside capture interval")
    law=plan.get("capture_law") or {}
    if law.get("read_only") is not True or law.get("orders_permitted") is not False or law.get("account_mutation_permitted") is not False:
        raise CaptureContractError("NETH25 cost collector is not read-only")
    transfer=plan.get("transfer_contract") or {}
    if transfer.get("raw_ticks_transferred") is not False or transfer.get("raw_conversion_ticks_transferred") is not False:
        raise CaptureContractError("raw tick transfer is forbidden")
    if tuple(transfer.get("fields") or ())!=COST_FIELDS:
        raise CaptureContractError("cost transfer fields drift")
    if plan.get("economic_outcomes_opened")!=0 or plan.get("v2_attempts_consumed")!=0 or plan.get("protected_evidence_opened") is not False:
        raise CaptureContractError("NETH25 cost plan is economically contaminated")
    return True

def _boundary_window(boundary,lookback_seconds=300,deadline_seconds=60):
    boundary=boundary.astimezone(timezone.utc)
    start=boundary-timedelta(seconds=int(lookback_seconds))
    end=boundary+timedelta(seconds=int(deadline_seconds))
    return {
        "label":"TRANSACTION_BOUNDARY",
        "from_ms":_ms(start),
        "to_ms":_ms(end),
        "start_utc":_iso(start),
        "end_utc":_iso(end),
        "boundary_ms":_ms(boundary),
        "boundary_utc":_iso(boundary),
    }

def _tuple_rows(rows):
    return [
        (_utc(x["time_utc"]),float(x["open"]),float(x["high"]),float(x["low"]),float(x["close"]))
        for x in rows
    ]

class Neth25TransactionLocalCostCaptureRunner(UltraFastCaptureRunner):
    def __init__(self,*,plan,base_protocol,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_cost_plan(plan)
        self.cost_plan=copy.deepcopy(plan)
        self.plan={
            "stage_a_interval":copy.deepcopy(plan["capture_interval"]),
            "capture_law":{
                "max_tick_pages_per_side_window":int(plan["capture_law"]["max_tick_pages_per_boundary_side"]),
                "max_stage_a_pages_per_symbol":int(plan["capture_law"]["max_stage_a_pages_per_symbol"]),
                "trendbar_pagination":{"page_count":int(plan["capture_law"]["trendbar_page_count"])},
            },
        }
        self.protocol=copy.deepcopy(base_protocol)
        self.client_id=client_id
        self.client_secret=client_secret
        self.access_token=access_token
        self.config=dict(config)
        self.root=Path(repo_root)
        self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/PACKAGE_OUTPUT_DIR/BUNDLE_DIR
        self.zip_path=self.root/OUTPUT_FILENAME
        self._app=False
        self._account=None
        self._last=None
        self._requests=0
        self._tick_cache={}
        self._conversion_chain_cache={}
        self._conversion_rate_cache={}
        self._assets={}
        self._asset_ids={}
        self._light={}

    def _mapping(self,aid):
        self._assets={str(x.get("assetId")):x.get("name") for x in [_plain(y) for y in self._send(ProtoOAAssetListReq(ctidTraderAccountId=aid)).asset]}
        self._asset_ids={str(name).upper():int(asset_id) for asset_id,name in self._assets.items() if name}
        self._light={int(x["symbolId"]):x for x in [_plain(y) for y in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]}
        q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid)
        q.symbolId.extend([EXPECTED_SYMBOL["symbol_id"]])
        full={int(x.symbolId):_plain(x) for x in self._send(q).symbol}
        li=self._light.get(EXPECTED_SYMBOL["symbol_id"])
        fu=full.get(EXPECTED_SYMBOL["symbol_id"])
        if not li or not fu or li.get("symbolName")!=EXPECTED_SYMBOL["broker_symbol"] or li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0:
            raise MappingError("NETH25 mapping/tradability mismatch")
        return fu,li

    def _boundary_cost(self,aid,full,light,boundary):
        spec=self.cost_plan["transaction_boundaries"]
        window=_boundary_window(
            boundary,
            int(spec["quote_context_lookback_seconds"]),
            int(spec["first_bilateral_quote_deadline_seconds"]),
        )
        bid=self._ticks(aid,EXPECTED_SYMBOL["symbol_id"],"BID",window)
        ask=self._ticks(aid,EXPECTED_SYMBOL["symbol_id"],"ASK",window)
        states=causal_merge_bid_ask(bid,ask)
        candidates=[x for x in states if x.timestamp_ms>=window["boundary_ms"] and x.timestamp_ms<=window["to_ms"]]
        if not candidates:
            return {
                "resolved":False,
                "boundary_utc":window["boundary_utc"],
                "execution_state_utc":None,
                "quote_delay_ms":None,
                "spread":None,
                "one_side_commission_price_equivalent":None,
                "cost_confidence_state":"COST_UNRESOLVED_NO_BILATERAL_STATE_BY_DEADLINE",
            }
        chosen=sorted(candidates,key=lambda x:(x.timestamp_ms,x.bid,x.ask))[0]
        selected_dt=datetime.fromtimestamp(chosen.timestamp_ms/1000,tz=timezone.utc)
        commission_window={
            "label":"TRANSACTION_BOUNDARY_COMMISSION",
            "from_ms":window["from_ms"],
            "to_ms":chosen.timestamp_ms,
            "start_utc":window["start_utc"],
            "end_utc":_iso(selected_dt),
        }
        mid=(chosen.bid+chosen.ask)/2.0
        commission=self._commission_for_window(aid,full,light,commission_window,[chosen],mid)
        one_side=commission.get("one_side_effective_commission_price_equivalent")
        confidence=commission.get("cost_confidence_state")
        resolved=one_side is not None and chosen.spread>=0
        return {
            "resolved":bool(resolved),
            "boundary_utc":window["boundary_utc"],
            "execution_state_utc":_iso(selected_dt),
            "quote_delay_ms":int(chosen.timestamp_ms-window["boundary_ms"]),
            "spread":float(chosen.spread),
            "one_side_commission_price_equivalent":float(one_side) if one_side is not None else None,
            "cost_confidence_state":confidence or "COST_UNRESOLVED_COMMISSION",
        }

    def _event_cost_rows(self,aid,full,light,rows):
        tuples=_tuple_rows(rows)
        start=_utc(self.cost_plan["event_analysis_interval"]["start_utc"])
        end=_utc(self.cost_plan["event_analysis_interval"]["end_utc"])
        protected=_utc(self.cost_plan["protected_forward_start"])
        out=[]
        for index in range(24,len(tuples)):
            event_time=tuples[index][0]
            if event_time<start or event_time>end:
                continue
            direction=_event_direction(tuples,index)
            if direction==0:
                continue
            entry=event_time+timedelta(minutes=5)
            exit_=event_time+timedelta(minutes=35)
            if exit_+timedelta(seconds=int(self.cost_plan["transaction_boundaries"]["first_bilateral_quote_deadline_seconds"]))>=protected:
                raise ImplementationInvalid("event boundary would reach protected-forward data")
            entry_cost=self._boundary_cost(aid,full,light,entry)
            exit_cost=self._boundary_cost(aid,full,light,exit_)
            resolved=entry_cost["resolved"] and exit_cost["resolved"]
            total=None
            if resolved:
                total=(
                    0.5*entry_cost["spread"]
                    +0.5*exit_cost["spread"]
                    +entry_cost["one_side_commission_price_equivalent"]
                    +exit_cost["one_side_commission_price_equivalent"]
                )
            out.append({
                "event_bar_time_utc":_iso(event_time),
                "event_direction":"UP" if direction>0 else "DOWN",
                "entry_boundary_utc":entry_cost["boundary_utc"],
                "entry_execution_state_utc":entry_cost["execution_state_utc"],
                "entry_quote_delay_ms":entry_cost["quote_delay_ms"],
                "entry_spread":entry_cost["spread"],
                "entry_one_side_commission_price_equivalent":entry_cost["one_side_commission_price_equivalent"],
                "entry_cost_confidence_state":entry_cost["cost_confidence_state"],
                "exit_boundary_utc":exit_cost["boundary_utc"],
                "exit_execution_state_utc":exit_cost["execution_state_utc"],
                "exit_quote_delay_ms":exit_cost["quote_delay_ms"],
                "exit_spread":exit_cost["spread"],
                "exit_one_side_commission_price_equivalent":exit_cost["one_side_commission_price_equivalent"],
                "exit_cost_confidence_state":exit_cost["cost_confidence_state"],
                "roundtrip_cost_price_equivalent":total,
                "cost_state":"TRANSACTION_LOCAL_COST_RESOLVED" if resolved else "COST_UNRESOLVED",
            })
        return out

    def _write_cost_rows(self,rows):
        path=self.bundle/"event_boundary_costs.csv"
        with path.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=COST_FIELDS,lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        return path

    def _validate_bundle(self,series,cost_rows,manifest):
        if series.get("broker_symbol")!="NETH25" or int(series.get("symbol_id") or 0)!=269:
            raise ImplementationInvalid("NETH25 series identity mismatch")
        if series.get("pagination",{}).get("request_interval_exhausted") is not True:
            raise ImplementationInvalid("NETH25 M5 traversal incomplete")
        if manifest.get("raw_ticks_transferred") is not False or manifest.get("raw_conversion_ticks_transferred") is not False:
            raise ImplementationInvalid("raw ticks may not be transferred")
        if manifest.get("protected_evidence_opened") is not False:
            raise ImplementationInvalid("protected evidence opened unexpectedly")
        if manifest.get("economic_outcomes_opened")!=0 or manifest.get("v2_attempts_consumed")!=0:
            raise ImplementationInvalid("cost capture mutated economic accounting")
        if manifest.get("events_detected")!=len(cost_rows):
            raise ImplementationInvalid("event-cost manifest count mismatch")
        for row in cost_rows:
            if row["cost_state"]=="TRANSACTION_LOCAL_COST_RESOLVED" and row["roundtrip_cost_price_equivalent"] is None:
                raise ImplementationInvalid("resolved cost row lacks total cost")
            if row["entry_execution_state_utc"] and _utc(row["entry_execution_state_utc"])<_utc(row["entry_boundary_utc"]):
                raise ImplementationInvalid("entry quote predates causal boundary")
            if row["exit_execution_state_utc"] and _utc(row["exit_execution_state_utc"])<_utc(row["exit_boundary_utc"]):
                raise ImplementationInvalid("exit quote predates causal boundary")
            for key in ("entry_execution_state_utc","exit_execution_state_utc"):
                if row[key] and _utc(row[key])>=_utc(PROTECTED_UTC):
                    raise ImplementationInvalid("cost row reaches protected-forward boundary")
        return True

    def _workflow(self):
        self.progress("[1/5] Pepperstone LIVE read-only account binding")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
        self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved=self.config.get("ctid_trader_account_id")
        try:
            account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector):
                raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"])
        self._account=aid
        if account_fingerprint(aid)!=self.cost_plan["account_fingerprint_sha256"]:
            raise MappingError("LIVE account fingerprint differs from frozen NETH25 cost plan")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():
            raise MappingError("not verifiably Pepperstone")
        full,light=self._mapping(aid)

        self.progress("[2/5] Strict pre-protected NETH25 M5 traversal")
        rows,pagination=self._stage_rows(aid,EXPECTED_SYMBOL,full)
        series=self._write_rows(EXPECTED_SYMBOL,rows,pagination)

        self.progress("[3/5] Frozen breakout event detection + causal transaction-boundary costs")
        cost_rows=self._event_cost_rows(aid,full,light,rows)
        self._write_cost_rows(cost_rows)

        self.progress("[4/5] Compact conversion authority + fail-closed bundle validation")
        conversion=self._conversion_summary()
        resolved=sum(1 for x in cost_rows if x["cost_state"]=="TRANSACTION_LOCAL_COST_RESOLVED")
        manifest={
            "schema":"mxm.greenfield.breakout-fade-neth25-transaction-local-cost-bundle.v1",
            "status":"CAPTURE_COMPLETE_COST_EVIDENCE_UNOPENED_ECONOMICS",
            "captured_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "tool_version":TOOL_VERSION,
            "plan_sha256":EXPECTED_PLAN_SHA,
            "source_decision_ref":self.cost_plan["source_decision_ref"],
            "symbol":EXPECTED_SYMBOL,
            "capture_interval":self.cost_plan["capture_interval"],
            "event_analysis_interval":self.cost_plan["event_analysis_interval"],
            "protected_forward_start":self.cost_plan["protected_forward_start"],
            "series":series,
            "events_detected":len(cost_rows),
            "transaction_local_cost_resolved":resolved,
            "transaction_local_cost_unresolved":len(cost_rows)-resolved,
            "historical_requests":self._requests,
            "conversion_chain_count":conversion["chain_count"],
            "conversion_window_rate_count":conversion["window_rate_count"],
            "raw_ticks_transferred":False,
            "raw_conversion_ticks_transferred":False,
            "price_levels_transferred_in_cost_rows":False,
            "orders_placed":False,
            "account_mutation":False,
            "protected_evidence_opened":False,
            "economic_outcomes_opened":0,
            "v2_attempts_consumed":0,
            "broader_universe_status":"OPEN_1578_ELIGIBLE_POST_EXCLUSION_FRONTIER_CANDIDATES",
            "family_exhaustion_claimed":False,
        }
        atomic_write_json(self.bundle/"historical_conversion_summary.json",conversion)
        atomic_write_json(self.bundle/"capture_manifest.json",manifest)
        self._validate_bundle(series,cost_rows,manifest)
        _write_checksums(self.bundle)
        _verify_checksums(self.bundle)
        scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])

        self.progress("[5/5] Deterministic transferable NETH25 cost-evidence ZIP")
        with zipfile.ZipFile(self.zip_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for path in sorted(x for x in self.bundle.rglob("*") if x.is_file()):
                info=zipfile.ZipInfo(path.relative_to(self.bundle).as_posix(),(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o644<<16
                z.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        self.progress(f"[DONE] {self.zip_path.name} bytes={self.zip_path.stat().st_size:,} SHA256={_sha(self.zip_path)}")

    def run(self):
        if self.bundle.exists():
            shutil.rmtree(self.bundle)
        self.bundle.mkdir(parents=True)
        self.zip_path.unlink(missing_ok=True)
        try:
            self.transport.connect()
            self._workflow()
        except (TypeError,AssertionError,KeyError,ValueError) as exc:
            raise ImplementationInvalid(f"IMPLEMENTATION_INVALID: {redact_text(str(exc))}") from exc
        finally:
            self.transport.close()
        return self.zip_path
