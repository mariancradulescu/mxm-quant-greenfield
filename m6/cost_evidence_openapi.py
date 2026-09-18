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
    QUOTE_TYPES,
    TIER1_SYMBOLS,
    CausalQuoteState,
    DecodedTick,
    atomic_write_bytes,
    canonical_tick_rows,
    causal_merge_bid_ask,
    decode_ctrader_tick_page,
    deterministic_zip_directory,
    next_tick_page_to_ms,
    quote_state_at_or_before,
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

TOOL_VERSION = "MXM_M6_TIER1_COST_EVIDENCE_ANDROID_STDLIB_V1"
BUNDLE_SCHEMA = "mxm.greenfield.v2.m6-tier1-cost-evidence-bundle.v1"


def _plain(message: Any) -> dict[str, Any]:
    return MessageToDict(
        message,
        preserving_proto_field_name=False,
        use_integers_for_enums=True,
    )


def _tick_chunk_key(symbol: str, quote_type: str, session_date: str) -> str:
    return f"{symbol}:{quote_type}:{session_date}"


def _load_resume(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema":"mxm.greenfield.v2.m6-cost-resume.v1","completed":{}}
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:
        raise CaptureContractError("cost-evidence resume state is malformed") from exc
    if not isinstance(value,dict) or not isinstance(value.get("completed"),dict):
        raise CaptureContractError("cost-evidence resume state has invalid schema")
    return value


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
        self.work_dir=self.repo_root/".m6_cost_evidence_work"/"tier1_us500_nas100_v1"
        self.output_dir=self.repo_root/"cost_capture_output"/"MXM_M6_TIER1_COST_EVIDENCE_V1"
        self.resume_path=self.work_dir/"resume.json"
        self.windows=signal_blind_cash_session_windows()
        self.resume=_load_resume(self.resume_path)
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

    def _transport_request(self, request):
        require_read_only_request(type(request).__name__)
        response=self.transport.request(request,timeout=60)
        if type(response).__name__=="ProtoOAErrorRes":
            raise CaptureContractError(
                f"cTrader API error: {getattr(response,'errorCode','UNKNOWN')}"
            )
        return response

    def _restore(self):
        self.transport.connect()
        if self._app_authorized:
            self._transport_request(ProtoOAApplicationAuthReq(
                clientId=self.client_id,clientSecret=self.client_secret
            ))
        if self._authorized_account_id is not None:
            self._transport_request(ProtoOAAccountAuthReq(
                ctidTraderAccountId=self._authorized_account_id,
                accessToken=self.access_token,
            ))

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
                    self._restore()
                except Exception as reconnect_exc:
                    last=reconnect_exc
        raise CaptureContractError(
            f"{type(request).__name__} failed after {retries} attempts: {redact_text(str(last))}"
        )

    def _authenticate_and_verify_targets(self)->int:
        self._stage("[1/3] Read-only Pepperstone LIVE authorization")
        self.transport.connect()
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
            f"[2/3] Capturing historical BID/ASK | {len(self.windows)} weekday cash-session envelopes | "
            "US500/NAS100 | signal-blind"
        )
        total=len(self.windows)*len(TIER1_SYMBOLS)*len(QUOTE_TYPES)
        completed=0
        records=[]
        for canonical in ("US500","NAS100"):
            for quote_type in ("BID","ASK"):
                for window in self.windows:
                    record=self._capture_chunk(account_id,canonical,quote_type,window)
                    records.append(record)
                    completed+=1
                    if completed==1 or completed%10==0 or completed==total:
                        elapsed=max(1e-9,time.monotonic()-self._started)
                        self.progress(
                            f"[COST {100.0*completed/total:5.1f}%] {canonical} {quote_type} "
                            f"{window.session_date} | chunks {completed}/{total} | "
                            f"hist req {self._historical_requests} | "
                            f"{self._historical_requests/elapsed:.2f} req/s | resume {self._reused_chunks}"
                        )
        return records

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
        out_path=self.output_dir/"derived"/f"{symbol}_M15_BOUNDARY_QUOTES.csv"
        out_path.parent.mkdir(parents=True,exist_ok=True)
        tmp=out_path.with_suffix(".csv.tmp")
        rows=0
        missing=0
        negative_spread=0
        with tmp.open("w",encoding="utf-8",newline="") as out:
            writer=csv.writer(out,lineterminator="\n")
            writer.writerow((
                "session_date","boundary_utc","boundary_timestamp_ms",
                "bid","ask","spread","bid_timestamp_ms","ask_timestamp_ms","state"
            ))
            for window in self.windows:
                bid=_read_chunk_ticks(self._chunk_path(symbol,"BID",window.session_date))
                ask=_read_chunk_ticks(self._chunk_path(symbol,"ASK",window.session_date))
                states=causal_merge_bid_ask(bid,ask)
                boundary=window.from_ms+15*60*1000
                while boundary<=window.to_ms:
                    try:
                        state=quote_state_at_or_before(states,boundary)
                        if state.spread<0:
                            negative_spread+=1
                        writer.writerow((
                            window.session_date,
                            datetime.fromtimestamp(boundary/1000,tz=timezone.utc).isoformat(
                                timespec="milliseconds"
                            ).replace("+00:00","Z"),
                            boundary,
                            format(state.bid,".10f").rstrip("0").rstrip("."),
                            format(state.ask,".10f").rstrip("0").rstrip("."),
                            format(state.spread,".10f").rstrip("0").rstrip("."),
                            state.bid_timestamp_ms,
                            state.ask_timestamp_ms,
                            "CAUSAL_TWO_SIDED",
                        ))
                    except CaptureContractError:
                        missing+=1
                        writer.writerow((
                            window.session_date,
                            datetime.fromtimestamp(boundary/1000,tz=timezone.utc).isoformat(
                                timespec="milliseconds"
                            ).replace("+00:00","Z"),
                            boundary,"","","","","","MISSING_CAUSAL_TWO_SIDED_QUOTE",
                        ))
                    rows+=1
                    boundary+=15*60*1000
        tmp.replace(out_path)
        return {
            "path":out_path.relative_to(self.output_dir).as_posix(),
            "rows":rows,
            "missing_causal_boundaries":missing,
            "negative_spread_states":negative_spread,
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
            "schema":"mxm.greenfield.v2.m6-tier1-cost-request-manifest.v1",
            "official_max_request_window_ms":604800000,
            "historical_limit_per_second":5,
            "implemented_min_interval_seconds":HISTORICAL_MIN_INTERVAL_SECONDS,
            "development_start_date":"2022-01-03",
            "development_end_date":"2026-09-16",
            "protected_boundary_excluded":True,
            "weekday_regular_session_envelopes":len(self.windows),
            "records":records,
        })
        atomic_write_json(evidence/"spread_reconstruction_policy.json",{
            "schema":"mxm.greenfield.v2.causal-bid-ask-merge.v1",
            "event_order":"CHRONOLOGICAL",
            "bid_state":"LATEST_BID_OBSERVED_AT_OR_BEFORE_T",
            "ask_state":"LATEST_ASK_OBSERVED_AT_OR_BEFORE_T",
            "future_fill":False,
            "emit_only_after_both_sides_seen":True,
            "spread":"ASK_MINUS_BID",
            "boundary_snapshot":"LATEST_CAUSAL_TWO_SIDED_STATE_AT_OR_BEFORE_EACH_GENERIC_M15_BOUNDARY",
            "signal_conditioned_selection":False,
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
            "raw_tapes":tapes,
            "boundary_quotes":boundaries,
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
        target=self.output_dir.parent/"MXM_M6_TIER1_COST_EVIDENCE_V1.zip"
        deterministic_zip_directory(self.output_dir,target)
        self._stage(f"[DONE] {target}")
        self._stage(f"[SHA256] {sha256_file(target)}")
        return target

    def run(self)->Path:
        self.work_dir.mkdir(parents=True,exist_ok=True)
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
