"""Android-safe cTrader historical BID/ASK capture for PRE-M6 Tier-1 cost evidence."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from google.protobuf.json_format import MessageToDict

from .cost_evidence import (
    HISTORICAL_MIN_INTERVAL_SECONDS,
    QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS,
    QUOTE_TYPES,
    TIER1_SYMBOLS,
    CausalQuoteState,
    DecodedTick,
    atomic_write_bytes,
    canonical_tick_rows,
    causal_merge_bid_ask,
    causal_state_at_boundary,
    cost_resume_contract,
    decode_ctrader_tick_page,
    deterministic_zip_directory,
    first_any_quote_event_at_or_after,
    first_both_sides_refreshed_diagnostic,
    first_tick_at_or_after,
    migrate_compatible_resume_tool_version,
    next_tick_page_to_ms,
    prepare_contract_bound_resume,
    signal_blind_cash_session_windows,
    tick_csv_bytes,
    validate_tick_request_window,
    verified_resume_chunk,
)
from .ctrader_capture import (
    CaptureContractError,
    MappingError,
    account_fingerprint,
    atomic_write_json,
    drop_secret_fields,
    live_account_candidates,
    redact_text,
    require_read_only_request,
    scan_bundle_for_secrets,
    select_live_pepperstone_account,
    sha256_file,
)
from .ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTickDataReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from .ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport
from .session_replay import NasdaqCashCalendar

TOOL_VERSION = "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_PIPELINE3_DNSCACHE1"
BUNDLE_SCHEMA = "mxm.greenfield.v2.m6-tier1-cost-evidence-bundle.v3"
PIPELINE_BATCH_SIZE = 4
NETWORK_RECOVERY_MAX_SECONDS = 1800.0
NETWORK_RECOVERY_MAX_BACKOFF_SECONDS = 30.0


def _plain(message: Any) -> dict[str, Any]:
    return MessageToDict(
        message,
        preserving_proto_field_name=False,
        use_integers_for_enums=True,
    )


def _tick_chunk_key(symbol: str, quote_type: str, session_date: str) -> str:
    return f"{symbol}:{quote_type}:{session_date}"


def _read_chunk_ticks(path: Path) -> list[DecodedTick]:
    out=[]
    with path.open("r",encoding="utf-8",newline="") as fh:
        for row in csv.DictReader(fh):
            out.append(DecodedTick(int(row["timestamp_ms"]),int(row["raw_tick"])))
    return out


class CostEvidenceRunner:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        access_token: str,
        config: Mapping[str, Any],
        repo_root: Path | str,
        progress=print,
        transport: StdlibCTraderTransport | None=None,
    ):
        self.client_id=client_id
        self.client_secret=client_secret
        self.access_token=access_token
        self.config=dict(config)
        self.repo_root=Path(repo_root)
        self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.plan_path=self.repo_root/"data"/"M6_TIER1_COST_EVIDENCE_PLAN_V3.json"
        self.calendar_path=self.repo_root/"data"/"NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json"
        if not self.plan_path.is_file() or not self.calendar_path.is_file():
            raise CaptureContractError("active Tier-1 cost plan/calendar authority missing")
        self.resume_contract=cost_resume_contract(
            self.plan_path, tool_version=TOOL_VERSION
        )
        self.work_dir=self.repo_root/".m6_cost_evidence_work"/"tier1_us500_nas100_v3"
        (
            self._resume_tool_migrated,
            self._resume_migrated_chunks,
            self._resume_previous_tool_version,
        )=migrate_compatible_resume_tool_version(
            self.work_dir,
            self.resume_contract,
            allowed_previous_tool_versions=(
                "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_TICKDELTA1",
                "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_PIPELINE1",
                "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V3_PIPELINE2",
            ),
        )
        self.resume_path,self.resume,self._archived_resume_dir=prepare_contract_bound_resume(
            self.work_dir,self.resume_contract
        )
        self.network_endpoint_cache_path=self.work_dir/"network_endpoint_cache.json"
        self._load_network_endpoint_cache()
        self.output_dir=self.repo_root/"cost_capture_output"/"MXM_M6_TIER1_COST_EVIDENCE_V3"
        self.windows=signal_blind_cash_session_windows()
        self.calendar=NasdaqCashCalendar.from_artifact(self.calendar_path)
        self._last_historical_send=None
        self._historical_requests=0
        self._reused_chunks=0
        self._app_authorized=False
        self._authorized_account_id=None
        self._started=time.monotonic()
        self._account_evidence={}
        self._symbol_evidence={}

    def _stage(self,text:str)->None:
        self.progress(text)

    def _load_network_endpoint_cache(self)->None:
        path=self.network_endpoint_cache_path
        if not path.is_file():
            return
        try:
            value=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError):
            return
        if value.get("host")!=LIVE_HOST or int(value.get("port",0))!=LIVE_PORT:
            return
        endpoints=value.get("endpoints")
        if not isinstance(endpoints,list):
            return
        self.transport.seed_cached_endpoints(endpoints)

    def _persist_network_endpoint_cache(self)->None:
        endpoints=[
            [host,int(port)]
            for host,port in self.transport.cached_endpoints
        ]
        if not endpoints:
            return
        atomic_write_json(self.network_endpoint_cache_path,{
            "schema":"mxm.greenfield.v2.ctrader-live-endpoint-cache.v1",
            "host":LIVE_HOST,
            "port":LIVE_PORT,
            "endpoints":endpoints,
            "role":"OPERATIONAL_RECONNECT_CACHE_NOT_RESEARCH_EVIDENCE",
        })

    def _restore(self):
        self.transport.connect()
        self._persist_network_endpoint_cache()
        if self._app_authorized:
            self._transport_request(ProtoOAApplicationAuthReq(
                clientId=self.client_id,clientSecret=self.client_secret
            ))
        if self._authorized_account_id is not None:
            self._transport_request(ProtoOAAccountAuthReq(
                ctidTraderAccountId=self._authorized_account_id,
                accessToken=self.access_token,
            ))

    def _restore_resilient(self, *, context:str)->None:
        started=time.monotonic()
        attempt=0
        while True:
            attempt+=1
            try:
                self._restore()
                if attempt>1:
                    self._stage(
                        f"[NETWORK RECOVERED] {context} after {attempt} attempts | "
                        f"cached endpoints {len(self.transport.cached_endpoints)}"
                    )
                return
            except Exception as exc:
                elapsed=time.monotonic()-started
                if elapsed>=NETWORK_RECOVERY_MAX_SECONDS:
                    raise CaptureContractError(
                        f"network recovery exceeded {NETWORK_RECOVERY_MAX_SECONDS:.0f}s: "
                        f"{redact_text(str(exc))}"
                    ) from None
                delay=min(
                    NETWORK_RECOVERY_MAX_BACKOFF_SECONDS,
                    float(2**min(attempt-1,5)),
                )
                remaining=max(0.0,NETWORK_RECOVERY_MAX_SECONDS-elapsed)
                self._stage(
                    f"[NETWORK WAIT] {context} | {redact_text(type(exc).__name__+': '+str(exc))} | "
                    f"cached endpoints {len(self.transport.cached_endpoints)} | "
                    f"retry in {delay:.0f}s | recovery budget {remaining:.0f}s"
                )
                time.sleep(delay)

    def _transport_request(self, request):
        require_read_only_request(type(request).__name__)
        response=self.transport.request(request,timeout=60)
        if type(response).__name__=="ProtoOAErrorRes":
            raise CaptureContractError(
                f"cTrader API error: {getattr(response,'errorCode','UNKNOWN')}"
            )
        return response

    def _send(self, request, *, historical=False, retries=3):
        require_read_only_request(type(request).__name__)
        last=None
        for attempt in range(1,retries+1):
            if historical:
                now=time.monotonic()
                if self._last_historical_send is not None:
                    wait=HISTORICAL_MIN_INTERVAL_SECONDS-(now-self._last_historical_send)
                    if wait>0:
                        time.sleep(wait)
                self._last_historical_send=time.monotonic()
            try:
                response=self._transport_request(request)
                if historical:
                    self._historical_requests+=1
                return response
            except Exception as exc:
                last=exc
                if attempt>=retries:
                    break
                delay=min(8.0,float(2**(attempt-1)))
                self._stage(
                    f"[RETRY] {type(request).__name__} {attempt}/{retries}; "
                    f"reconnect in {delay:.0f}s"
                )
                time.sleep(delay)
                try:
                    self.transport.close()
                    self._restore_resilient(context="request reconnect")
                except Exception as reconnect_exc:
                    last=reconnect_exc
        raise CaptureContractError(
            f"{type(request).__name__} failed after {retries} attempts: {redact_text(str(last))}"
        )

    def _send_historical_batch(self, requests, retries=3):
        """Send a small bounded historical batch over one LIVE connection.

        Historical tick responses can be large. A small in-flight set preserves much of
        the latency-hiding benefit without allowing a large response backlog to destabilize
        the TLS connection. Failures are surfaced with a sanitized reason and retried with
        reconnect/backoff; the caller never loses completed hash-verified chunks.
        """
        if not requests:
            return []
        last=None
        for attempt in range(1,retries+1):
            try:
                responses=self.transport.request_batch(
                    list(requests),
                    timeout=120,
                    min_interval_seconds=HISTORICAL_MIN_INTERVAL_SECONDS,
                )
                for response in responses:
                    if type(response).__name__=="ProtoOAErrorRes":
                        code=getattr(response,"errorCode","UNKNOWN")
                        description=getattr(response,"description","")
                        raise CaptureContractError(
                            f"cTrader API error {code}: {description}"
                        )
                self._historical_requests+=len(requests)
                return responses
            except Exception as exc:
                last=exc
                reason=redact_text(f"{type(exc).__name__}: {exc}")
                if attempt>=retries:
                    break
                delay=min(8.0,float(2**(attempt-1)))
                self._stage(
                    f"[PIPELINE RETRY] batch_size={len(requests)} attempt {attempt}/{retries} | "
                    f"{reason} | reconnect in {delay:.0f}s"
                )
                time.sleep(delay)
                try:
                    self.transport.close()
                    self._restore_resilient(context="historical pipeline reconnect")
                except Exception as reconnect_exc:
                    last=reconnect_exc
        if len(requests)>1:
            midpoint=max(1,len(requests)//2)
            self._stage(
                f"[PIPELINE FALLBACK] batch_size={len(requests)} -> "
                f"{midpoint}+{len(requests)-midpoint}; preserving request order"
            )
            left=self._send_historical_batch(requests[:midpoint],retries=2)
            right=self._send_historical_batch(requests[midpoint:],retries=2)
            return left+right
        raise CaptureContractError(
            f"historical single request failed after {retries} attempts: "
            f"{redact_text(str(last))}"
        )

    def _authenticate_and_verify_targets(self)->int:
        self._stage("[1/3] Read-only Pepperstone LIVE authorization")
        self._restore_resilient(context="initial LIVE connection")
        self._send(ProtoOAApplicationAuthReq(
            clientId=self.client_id,clientSecret=self.client_secret
        ))
        self._app_authorized=True
        accounts_res=self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token))
        accounts=[_plain(x) for x in accounts_res.ctidTraderAccount]
        saved=self.config.get("ctid_trader_account_id")
        try:
            account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector):
                raise
            selected=int(selector(live_account_candidates(accounts)))
            account=select_live_pepperstone_account(accounts,account_override=selected)
        account_id=int(account["ctidTraderAccountId"])
        self._authorized_account_id=account_id
        self._send(ProtoOAAccountAuthReq(
            ctidTraderAccountId=account_id,accessToken=self.access_token
        ))
        trader_res=self._send(ProtoOATraderReq(ctidTraderAccountId=account_id))
        trader=_plain(trader_res.trader)
        broker=str(trader.get("brokerName",""))
        if "pepperstone" not in broker.lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():
            raise MappingError("authorized LIVE account is not verifiably Pepperstone")

        symbols_res=self._send(ProtoOASymbolsListReq(
            ctidTraderAccountId=account_id,includeArchivedSymbols=False
        ))
        by_id={int(x.symbolId):_plain(x) for x in symbols_res.symbol}
        req=ProtoOASymbolByIdReq(ctidTraderAccountId=account_id)
        req.symbolId.extend(sorted(v["symbol_id"] for v in TIER1_SYMBOLS.values()))
        full_res=self._send(req)
        full_by_id={int(x.symbolId):_plain(x) for x in full_res.symbol}
        evidence={}
        for canonical,expected in TIER1_SYMBOLS.items():
            sid=int(expected["symbol_id"])
            light=by_id.get(sid)
            full=full_by_id.get(sid)
            if light is None or full is None:
                raise MappingError(f"{canonical}: accepted symbolId {sid} is not current")
            if str(light.get("symbolName"))!=canonical or not bool(light.get("enabled")):
                raise MappingError(f"{canonical}: current symbol identity/enabled state changed")
            trading_mode=full.get("tradingMode",0)
            if trading_mode not in (0,"0",None):
                raise MappingError(f"{canonical}: current trading mode is not ENABLED")
            evidence[canonical]={
                "canonical":canonical,
                "broker_symbol":light.get("symbolName"),
                "symbol_id":sid,
                "accepted_product_family":expected["product_family"],
                "enabled":bool(light.get("enabled")),
                "trading_mode":trading_mode,
                "structural_verification":"EXACT_ACCEPTED_SYMBOL_ID_NAME_CURRENT_ENABLED",
            }
        self._account_evidence={
            "account_fingerprint_sha256":account_fingerprint(account_id),
            "environment":"Pepperstone - Europe LIVE",
            "broker_name":broker,
            "raw_account_id_in_bundle":False,
            "oauth_scope":"accounts",
        }
        self._symbol_evidence=evidence
        self._stage("[PREFLIGHT PASS] US500=127 and NAS100=126 exact current identities verified")
        return account_id

    def _chunk_path(self,symbol,quote_type,session_date)->Path:
        return self.work_dir/"chunks"/symbol/quote_type/f"{session_date}.csv"

    def _capture_chunk(self, account_id:int, symbol:str, quote_type:str, window)->dict[str,Any]:
        key=_tick_chunk_key(symbol,quote_type,window.session_date)
        path=self._chunk_path(symbol,quote_type,window.session_date)
        saved=self.resume["completed"].get(key)
        if isinstance(saved,dict) and verified_resume_chunk(path,str(saved.get("sha256") or "")):
            self._reused_chunks+=1
            return dict(saved)

        validate_tick_request_window(window.from_ms,window.to_ms)
        page_to=window.to_ms
        previous_oldest=None
        ticks=[]
        pages=0
        fallback_count=0
        while page_to>=window.from_ms:
            request=ProtoOAGetTickDataReq(
                ctidTraderAccountId=account_id,
                symbolId=int(TIER1_SYMBOLS[symbol]["symbol_id"]),
                type=int(QUOTE_TYPES[quote_type]),
                fromTimestamp=int(window.from_ms),
                toTimestamp=int(page_to),
            )
            response=self._send(request,historical=True)
            pages+=1
            page=decode_ctrader_tick_page([
                {"timestamp":int(x.timestamp),"tick":int(x.tick)}
                for x in response.tickData
            ])
            ticks.extend(page)
            if not bool(response.hasMore):
                break
            if not page:
                raise CaptureContractError(
                    f"{symbol} {quote_type} {window.session_date}: hasMore with empty page"
                )
            oldest=min(x.timestamp_ms for x in page)
            next_to=next_tick_page_to_ms(
                page,current_from_ms=window.from_ms,previous_oldest_ms=previous_oldest
            )
            if next_to is None:
                break
            if previous_oldest is not None and next_to==oldest-1:
                fallback_count+=1
            if next_to>=page_to:
                next_to=page_to-1
                fallback_count+=1
            previous_oldest=oldest
            page_to=next_to

        rows=canonical_tick_rows(
            ticks,requested_from_ms=window.from_ms,requested_to_ms=window.to_ms
        )
        payload=tick_csv_bytes(rows)
        atomic_write_bytes(path,payload)
        record={
            "key":key,
            "symbol":symbol,
            "symbol_id":int(TIER1_SYMBOLS[symbol]["symbol_id"]),
            "quote_type":quote_type,
            "session_date":window.session_date,
            "from_ms":window.from_ms,
            "to_ms":window.to_ms,
            "row_count":len(rows),
            "page_count":pages,
            "pagination_boundary_fallback_count":fallback_count,
            "sha256":hashlib.sha256(payload).hexdigest(),
        }
        self.resume["completed"][key]=record
        atomic_write_json(self.resume_path,self.resume)
        return record

    def _capture_all(self,account_id:int)->list[dict[str,Any]]:
        self._stage(
            f"[2/3] Capturing historical BID/ASK PIPELINED | {len(self.windows)} weekday cash-session envelopes | "
            f"US500/NAS100 | batch {PIPELINE_BATCH_SIZE} | signal-blind"
        )
        tasks=[]
        for canonical in ("US500","NAS100"):
            for quote_type in ("BID","ASK"):
                for window in self.windows:
                    tasks.append((canonical,quote_type,window))

        total=len(tasks)
        record_by_key={}
        missing=[]
        completed=0

        for canonical,quote_type,window in tasks:
            key=_tick_chunk_key(canonical,quote_type,window.session_date)
            path=self._chunk_path(canonical,quote_type,window.session_date)
            saved=self.resume["completed"].get(key)
            if isinstance(saved,dict) and verified_resume_chunk(path,str(saved.get("sha256") or "")):
                self._reused_chunks+=1
                record_by_key[key]=dict(saved)
                completed+=1
            else:
                missing.append((canonical,quote_type,window))

        if self._resume_tool_migrated:
            self._stage(
                f"[RESUME MIGRATED] {self._resume_migrated_chunks} verified chunks preserved "
                f"from {self._resume_previous_tool_version} -> {TOOL_VERSION}"
            )

        def new_state(task):
            canonical,quote_type,window=task
            validate_tick_request_window(window.from_ms,window.to_ms)
            return {
                "symbol":canonical,
                "quote_type":quote_type,
                "window":window,
                "page_to":int(window.to_ms),
                "previous_oldest":None,
                "ticks":[],
                "pages":0,
                "fallback_count":0,
            }

        def finalize_state(state):
            canonical=state["symbol"]
            quote_type=state["quote_type"]
            window=state["window"]
            key=_tick_chunk_key(canonical,quote_type,window.session_date)
            path=self._chunk_path(canonical,quote_type,window.session_date)
            rows=canonical_tick_rows(
                state["ticks"],
                requested_from_ms=window.from_ms,
                requested_to_ms=window.to_ms,
            )
            payload=tick_csv_bytes(rows)
            atomic_write_bytes(path,payload)
            record={
                "key":key,
                "symbol":canonical,
                "symbol_id":int(TIER1_SYMBOLS[canonical]["symbol_id"]),
                "quote_type":quote_type,
                "session_date":window.session_date,
                "from_ms":window.from_ms,
                "to_ms":window.to_ms,
                "row_count":len(rows),
                "page_count":state["pages"],
                "pagination_boundary_fallback_count":state["fallback_count"],
                "sha256":hashlib.sha256(payload).hexdigest(),
            }
            self.resume["completed"][key]=record
            atomic_write_json(self.resume_path,self.resume)
            return record

        cursor=0
        active=[]
        while cursor<len(missing) or active:
            while cursor<len(missing) and len(active)<PIPELINE_BATCH_SIZE:
                active.append(new_state(missing[cursor]))
                cursor+=1

            requests=[]
            for state in active:
                window=state["window"]
                requests.append(ProtoOAGetTickDataReq(
                    ctidTraderAccountId=account_id,
                    symbolId=int(TIER1_SYMBOLS[state["symbol"]]["symbol_id"]),
                    type=int(QUOTE_TYPES[state["quote_type"]]),
                    fromTimestamp=int(window.from_ms),
                    toTimestamp=int(state["page_to"]),
                ))

            responses=self._send_historical_batch(requests)
            keep=[]
            for state,response in zip(active,responses):
                state["pages"]+=1
                page=decode_ctrader_tick_page([
                    {"timestamp":int(x.timestamp),"tick":int(x.tick)}
                    for x in response.tickData
                ])
                state["ticks"].extend(page)

                done=not bool(response.hasMore)
                if not done:
                    if not page:
                        raise CaptureContractError(
                            f"{state['symbol']} {state['quote_type']} "
                            f"{state['window'].session_date}: hasMore with empty page"
                        )
                    oldest=min(x.timestamp_ms for x in page)
                    next_to=next_tick_page_to_ms(
                        page,
                        current_from_ms=state["window"].from_ms,
                        previous_oldest_ms=state["previous_oldest"],
                    )
                    if next_to is None:
                        done=True
                    else:
                        if (
                            state["previous_oldest"] is not None
                            and next_to==oldest-1
                        ):
                            state["fallback_count"]+=1
                        if next_to>=state["page_to"]:
                            next_to=state["page_to"]-1
                            state["fallback_count"]+=1
                        state["previous_oldest"]=oldest
                        state["page_to"]=next_to
                        if state["page_to"]<state["window"].from_ms:
                            done=True

                if done:
                    record=finalize_state(state)
                    record_by_key[record["key"]]=record
                    completed+=1
                    if completed==1 or completed%10==0 or completed==total:
                        elapsed=max(1e-9,time.monotonic()-self._started)
                        self.progress(
                            f"[COST {100.0*completed/total:5.1f}%] {state['symbol']} "
                            f"{state['quote_type']} {state['window'].session_date} | "
                            f"chunks {completed}/{total} | hist req {self._historical_requests} | "
                            f"{self._historical_requests/elapsed:.2f} req/s | "
                            f"resume {self._reused_chunks} | inflight {len(active)}"
                        )
                else:
                    keep.append(state)
            active=keep

        ordered=[]
        for canonical,quote_type,window in tasks:
            key=_tick_chunk_key(canonical,quote_type,window.session_date)
            ordered.append(record_by_key[key])
        return ordered

    def _write_consolidated_tape(self, symbol:str, quote_type:str)->dict[str,Any]:
        path=self.output_dir/"raw_ticks"/f"{symbol}_{quote_type}.csv"
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(".csv.tmp")
        rows=0
        with tmp.open("w",encoding="utf-8",newline="") as out:
            writer=csv.writer(out,lineterminator="\n")
            writer.writerow(("time_utc","timestamp_ms","raw_tick","price"))
            for window in self.windows:
                chunk=self._chunk_path(symbol,quote_type,window.session_date)
                with chunk.open("r",encoding="utf-8",newline="") as fh:
                    reader=csv.reader(fh)
                    next(reader,None)
                    for row in reader:
                        writer.writerow(row)
                        rows+=1
        tmp.replace(path)
        return {"path":path.relative_to(self.output_dir).as_posix(),"rows":rows,"sha256":sha256_file(path)}

    def _write_boundary_quotes(self,symbol:str)->dict[str,Any]:
        """Persist candidate-independent quote evidence; never assert an executed fill."""
        out_path=self.output_dir/"derived"/f"{symbol}_M15_BOUNDARY_QUOTE_EVIDENCE.csv"
        out_path.parent.mkdir(parents=True,exist_ok=True)
        tmp=out_path.with_suffix(".csv.tmp")
        rows=0
        missing_causal=0
        missing_bid_event=0
        missing_ask_event=0
        missing_any_event=0
        missing_refresh_diagnostic=0
        negative_spread=0

        def price(value):
            if value is None:
                return ""
            return format(value,".10f").rstrip("0").rstrip(".")

        with tmp.open("w",encoding="utf-8",newline="") as out:
            writer=csv.writer(out,lineterminator="\n")
            writer.writerow((
                "session_date","boundary_utc","boundary_timestamp_ms","boundary_role",
                "causal_bid","causal_ask","causal_spread",
                "causal_bid_timestamp_ms","causal_ask_timestamp_ms",
                "causal_bid_age_ms","causal_ask_age_ms","causal_state_availability",
                "first_post_boundary_bid_timestamp_ms","first_post_boundary_bid_price",
                "first_post_boundary_bid_delay_ms",
                "first_post_boundary_ask_timestamp_ms","first_post_boundary_ask_price",
                "first_post_boundary_ask_delay_ms",
                "first_post_boundary_any_timestamp_ms","first_post_boundary_any_side",
                "first_post_boundary_any_bid_price","first_post_boundary_any_ask_price",
                "first_post_boundary_any_delay_ms",
                "both_sides_refreshed_state_timestamp_ms",
                "both_sides_refreshed_bid","both_sides_refreshed_ask",
                "both_sides_refreshed_spread",
                "both_sides_refreshed_bid_timestamp_ms",
                "both_sides_refreshed_ask_timestamp_ms",
                "both_sides_refreshed_delay_ms",
                "both_sides_refreshed_classification"
            ))
            for window in self.windows:
                session=self.calendar.session(
                    datetime.fromisoformat(window.session_date).date()
                )
                if session is None:
                    continue
                bid=_read_chunk_ticks(self._chunk_path(symbol,"BID",window.session_date))
                ask=_read_chunk_ticks(self._chunk_path(symbol,"ASK",window.session_date))
                states=causal_merge_bid_ask(bid,ask)
                boundary=int(session.open_utc.timestamp()*1000)
                close_ms=int(session.close_utc.timestamp()*1000)
                while boundary<=close_ms:
                    causal=causal_state_at_boundary(bid,ask,boundary)
                    if causal.availability!="CAUSAL_TWO_SIDED_AVAILABLE":
                        missing_causal+=1
                    elif causal.spread is not None and causal.spread<0:
                        negative_spread+=1

                    post_bid=first_tick_at_or_after(bid,boundary)
                    if post_bid is None:
                        missing_bid_event+=1
                    post_ask=first_tick_at_or_after(ask,boundary)
                    if post_ask is None:
                        missing_ask_event+=1
                    post_any=first_any_quote_event_at_or_after(bid,ask,boundary)
                    if post_any is None:
                        missing_any_event+=1

                    refresh=None
                    try:
                        refresh=first_both_sides_refreshed_diagnostic(
                            states,
                            boundary,
                            diagnostic_window_ms=QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS,
                        )
                        if refresh.spread<0:
                            negative_spread+=1
                    except CaptureContractError:
                        missing_refresh_diagnostic+=1

                    writer.writerow((
                        window.session_date,
                        datetime.fromtimestamp(boundary/1000,tz=timezone.utc).isoformat(
                            timespec="milliseconds"
                        ).replace("+00:00","Z"),
                        boundary,
                        "SESSION_CLOSE_BOUNDARY" if boundary==close_ms else "GENERIC_M15_BOUNDARY",
                        price(causal.bid),price(causal.ask),price(causal.spread),
                        "" if causal.bid_timestamp_ms is None else causal.bid_timestamp_ms,
                        "" if causal.ask_timestamp_ms is None else causal.ask_timestamp_ms,
                        "" if causal.bid_age_ms is None else causal.bid_age_ms,
                        "" if causal.ask_age_ms is None else causal.ask_age_ms,
                        causal.availability,
                        "" if post_bid is None else post_bid.timestamp_ms,
                        "" if post_bid is None else price(post_bid.price),
                        "" if post_bid is None else post_bid.timestamp_ms-boundary,
                        "" if post_ask is None else post_ask.timestamp_ms,
                        "" if post_ask is None else price(post_ask.price),
                        "" if post_ask is None else post_ask.timestamp_ms-boundary,
                        "" if post_any is None else post_any.timestamp_ms,
                        "" if post_any is None else post_any.side,
                        "" if post_any is None else price(post_any.bid_price),
                        "" if post_any is None else price(post_any.ask_price),
                        "" if post_any is None else post_any.delay_ms,
                        "" if refresh is None else refresh.timestamp_ms,
                        "" if refresh is None else price(refresh.bid),
                        "" if refresh is None else price(refresh.ask),
                        "" if refresh is None else price(refresh.spread),
                        "" if refresh is None else refresh.bid_timestamp_ms,
                        "" if refresh is None else refresh.ask_timestamp_ms,
                        "" if refresh is None else refresh.timestamp_ms-boundary,
                        (
                            "MISSING_WITHIN_DIAGNOSTIC_WINDOW"
                            if refresh is None
                            else "QUOTE_REFRESH_DIAGNOSTIC_ONLY"
                        ),
                    ))
                    rows+=1
                    boundary+=15*60*1000
        tmp.replace(out_path)
        return {
            "path":out_path.relative_to(self.output_dir).as_posix(),
            "rows":rows,
            "missing_causal_two_sided_states":missing_causal,
            "missing_first_post_boundary_bid_events":missing_bid_event,
            "missing_first_post_boundary_ask_events":missing_ask_event,
            "missing_first_post_boundary_any_events":missing_any_event,
            "missing_both_sides_refresh_diagnostics":missing_refresh_diagnostic,
            "negative_spread_states":negative_spread,
            "first_generic_boundary_includes_session_open":True,
            "both_sides_refresh_diagnostic_window_ms":QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS,
            "both_sides_refresh_classification":"QUOTE_REFRESH_DIAGNOSTIC_ONLY",
            "fill_authority":False,
            "sha256":sha256_file(out_path),
        }

    def _finalize(self,records:list[dict[str,Any]])->Path:
        self._stage("[3/3] Finalizing deterministic cost-evidence bundle")
        if self.output_dir.exists():
            import shutil
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)
        tapes={}
        boundaries={}
        for symbol in ("US500","NAS100"):
            for quote_type in ("BID","ASK"):
                tapes[f"{symbol}_{quote_type}"]=self._write_consolidated_tape(symbol,quote_type)
            boundaries[symbol]=self._write_boundary_quotes(symbol)

        evidence=self.output_dir/"evidence"
        evidence.mkdir()
        atomic_write_json(evidence/"account.json",drop_secret_fields(self._account_evidence))
        atomic_write_json(evidence/"symbol_verification.json",self._symbol_evidence)
        atomic_write_json(evidence/"request_manifest.json",{
            "schema":"mxm.greenfield.v2.m6-tier1-cost-request-manifest.v3",
            "official_max_request_window_ms":604800000,
            "historical_limit_per_second":5,
            "implemented_min_interval_seconds":HISTORICAL_MIN_INTERVAL_SECONDS,
            "development_start_date":"2022-01-03",
            "development_end_date":"2026-09-16",
            "protected_boundary_excluded":True,
            "weekday_regular_session_envelopes":len(self.windows),
            "plan_file_sha256":self.resume_contract["plan_file_sha256"],
            "resume_contract_sha256":self.resume_contract["binding_sha256"],
            "records":records,
        })
        atomic_write_json(evidence/"quote_boundary_evidence_policy.json",{
            "schema":"mxm.greenfield.v2.causal-bid-ask-boundary-evidence.v3",
            "classification":"EVIDENCE_ONLY_NO_EXECUTION_FILL_AUTHORITY",
            "event_order":"CHRONOLOGICAL",
            "spread":"ASK_MINUS_BID",
            "future_side_fill":False,
            "generic_boundaries":"OFFICIAL_CASH_SESSION_M15_BOUNDARIES_INCLUDING_09_30",
            "causal_state_at_boundary":{
                "bid":"LATEST_OBSERVED_BID_AT_OR_BEFORE_BOUNDARY",
                "ask":"LATEST_OBSERVED_ASK_AT_OR_BEFORE_BOUNDARY",
                "quote_age_recorded":True,
                "pre_boundary_side_may_remain_current":True,
                "executed_fill_authority":False,
            },
            "first_post_boundary_events":{
                "bid":"FIRST_OBSERVED_BID_AT_OR_AFTER_BOUNDARY",
                "ask":"FIRST_OBSERVED_ASK_AT_OR_AFTER_BOUNDARY",
                "any":"EARLIEST_OBSERVED_BID_AND_OR_ASK_AT_OR_AFTER_BOUNDARY",
                "executed_fill_authority":False,
            },
            "both_sides_refreshed":{
                "classification":"QUOTE_REFRESH_DIAGNOSTIC_ONLY",
                "diagnostic_window_ms":QUOTE_REFRESH_DIAGNOSTIC_WINDOW_MS,
                "candidate_entry_time":False,
                "fill_time":False,
                "stage_a_execution_truth":False,
                "mandatory_delay_assumption":False,
                "economic_fill_authority":False,
            },
            "completed_bar_close":{
                "causal_state_at_or_before_close":True,
                "quote_ages":True,
                "first_bid_event_at_or_after_close_boundary":True,
                "first_ask_event_at_or_after_close_boundary":True,
                "post_close_quote_mixed_into_frozen_close_proxy":False,
            },
            "market_proxy_rule":"CANDIDATE_OHLC_MARKET_PROXY_TIMING_REMAINS_SEPARATE_FROM_QUOTE_COST_EVIDENCE",
            "numeric_quote_age_or_fill_delay_rule":"NOT_FROZEN_PRE_CAPTURE",
            "signal_conditioned_selection":False,
            "candidate_pnl_conditioned_selection":False,
        })
        atomic_write_json(self.output_dir/"provenance_manifest.json",{
            "schema":BUNDLE_SCHEMA,
            "tool_version":TOOL_VERSION,
            "source_environment":"Pepperstone - Europe LIVE",
            "oauth_scope":"accounts",
            "orders":False,
            "account_mutation":False,
            "economics":False,
            "candidate_outcomes_opened":0,
            "attempts_consumed":0,
            "protected_evidence_opened":False,
            "targets":self._symbol_evidence,
            "acquisition_domain":"ALL_WEEKDAY_09_30_TO_16_00_AMERICA_NEW_YORK_ENVELOPES_SIGNAL_BLIND",
            "active_plan":"data/M6_TIER1_COST_EVIDENCE_PLAN_V3.json",
            "calibration_protocol":"data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json",
            "active_calendar":"data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json",
            "resume_contract":self.resume_contract,
            "archived_incompatible_resume_dir":(
                self._archived_resume_dir.name if self._archived_resume_dir else None
            ),
            "raw_tapes":tapes,
            "boundary_quote_evidence":boundaries,
            "execution_fill_rule_frozen":False,
            "candidate_market_proxy_mutated":False,
            "historical_requests_completed":self._historical_requests,
            "resume_chunks_reused":self._reused_chunks,
        })

        scan_bundle_for_secrets(
            self.output_dir,[self.client_id,self.client_secret,self.access_token]
        )

        # Checksums cover every member except the checksum file itself.
        checksum_lines=[]
        for path in sorted(p for p in self.output_dir.rglob("*") if p.is_file()):
            rel=path.relative_to(self.output_dir).as_posix()
            checksum_lines.append(f"{sha256_file(path)}  {rel}")
        (self.output_dir/"CHECKSUMS.sha256").write_text(
            "\n".join(checksum_lines)+"\n",encoding="utf-8"
        )
        atomic_write_json(self.output_dir/"bundle_manifest.json",{
            "schema":BUNDLE_SCHEMA,
            "required_targets":["US500","NAS100"],
            "raw_tape_count":4,
            "derived_boundary_quote_files":2,
            "protected_boundary_excluded":True,
            "transfer_instruction":"Return this ZIP to ChatGPT; do not send local OAuth/work directories.",
        })

        # Refresh checksums after bundle manifest.
        checksum_lines=[]
        for path in sorted(p for p in self.output_dir.rglob("*") if p.is_file() and p.name!="CHECKSUMS.sha256"):
            rel=path.relative_to(self.output_dir).as_posix()
            checksum_lines.append(f"{sha256_file(path)}  {rel}")
        (self.output_dir/"CHECKSUMS.sha256").write_text(
            "\n".join(checksum_lines)+"\n",encoding="utf-8"
        )
        target=self.output_dir.parent/"MXM_M6_TIER1_COST_EVIDENCE_V3.zip"
        deterministic_zip_directory(self.output_dir,target)
        self._stage(f"[DONE] {target}")
        self._stage(f"[SHA256] {sha256_file(target)}")
        return target

    def run(self)->Path:
        self.work_dir.mkdir(parents=True,exist_ok=True)
        if self._archived_resume_dir is not None:
            self._stage(
                f"[RESUME RESET] incompatible prior work archived as "
                f"{self._archived_resume_dir.name}; no stale chunk was reused"
            )
        elif self._resume_tool_migrated:
            self._stage(
                f"[RESUME SAFE MIGRATION] {self._resume_migrated_chunks} chunks hash-verified; "
                f"raw acquisition contract unchanged"
            )
        self._stage(
            "[RATE] historical tick pacing 0.21s; official ceiling 5 historical req/s/connection"
        )
        try:
            account_id=self._authenticate_and_verify_targets()
            records=self._capture_all(account_id)
            return self._finalize(records)
        finally:
            self.transport.close()
            self.access_token=None
