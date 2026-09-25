"""Incremental read-only cTrader pre-open supplement and local deterministic finalizer."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .cost_evidence import (
    TIER1_SYMBOLS,
    BoundaryQuoteIndex,
    DecodedTick,
    atomic_write_json,
    canonical_json_bytes,
    cost_resume_contract,
    deterministic_zip_directory,
    prepare_contract_bound_resume,
    sha256_file,
)
from .cost_evidence_openapi import CostEvidenceRunner, _read_chunk_ticks
from .ctrader_capture import CaptureContractError, drop_secret_fields, scan_bundle_for_secrets
from .ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport
from .preopen_supplement import (
    PREOPEN_PLAN_REL,
    PREOPEN_TOOL_VERSION,
    signal_blind_preopen_windows,
)
from .session_replay import NasdaqCashCalendar

BUNDLE_SCHEMA = "mxm.greenfield.v2.tier1-preopen-0930-supplement-bundle.v1"
OLD_V3_WORK_REL = ".m6_cost_evidence_work/tier1_us500_nas100_v3"
NEW_WORK_REL = ".m6_cost_evidence_work/tier1_preopen_0930_v1"


def _fmt_seconds(value: float) -> str:
    value=max(0,int(value))
    h,rem=divmod(value,3600)
    m,s=divmod(rem,60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _price(value):
    if value is None:
        return ""
    return format(float(value), ".10f").rstrip("0").rstrip(".")


class PreopenSupplementRunner(CostEvidenceRunner):
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
        self.plan_path=self.repo_root/PREOPEN_PLAN_REL
        self.calendar_path=self.repo_root/"data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json"
        if not self.plan_path.is_file() or not self.calendar_path.is_file():
            raise CaptureContractError("pre-open plan/calendar authority missing")
        self.resume_contract=cost_resume_contract(self.plan_path,tool_version=PREOPEN_TOOL_VERSION)
        self.work_dir=self.repo_root/NEW_WORK_REL
        self._resume_tool_migrated=False
        self._resume_migrated_chunks=0
        self._resume_previous_tool_version=None
        self.resume_path,self.resume,self._archived_resume_dir=prepare_contract_bound_resume(
            self.work_dir,self.resume_contract
        )
        self.network_endpoint_cache_path=self.work_dir/"network_endpoint_cache.json"
        self._load_network_endpoint_cache()
        self.output_dir=self.repo_root/"preopen_capture_output"/"MXM_M6_TIER1_PREOPEN_0930_SUPPLEMENT_V1"
        self.windows=signal_blind_preopen_windows()
        self.calendar=NasdaqCashCalendar.from_artifact(self.calendar_path)
        self._last_historical_send=None
        self._historical_requests=0
        self._reused_chunks=0
        self._app_authorized=False
        self._authorized_account_id=None
        self._started=time.monotonic()
        self._account_evidence={}
        self._symbol_evidence={}

    def _capture_all(self,account_id:int)->list[dict[str,Any]]:
        tasks=[
            (symbol,side,window)
            for symbol in ("US500","NAS100")
            for side in ("BID","ASK")
            for window in self.windows
        ]
        total=len(tasks)
        records=[]
        started=time.monotonic()
        self._stage(
            f"[2/3] Incremental PREOPEN only | 09:15-09:30 ET | {len(self.windows)} weekdays | "
            f"US500/NAS100 BID+ASK | chunks {total}"
        )
        for idx,(symbol,side,window) in enumerate(tasks,1):
            records.append(self._capture_chunk(account_id,symbol,side,window))
            if idx==1 or idx%25==0 or idx==total:
                elapsed=max(0.001,time.monotonic()-started)
                rate=idx/elapsed
                eta=(total-idx)/rate if rate>0 else 0
                self._stage(
                    f"[PREOPEN {100.0*idx/total:5.1f}%] chunks {idx}/{total} | "
                    f"hist req {self._historical_requests} | reused {self._reused_chunks} | "
                    f"elapsed {_fmt_seconds(elapsed)} | ETA {_fmt_seconds(eta)}"
                )
        return records

    def _preopen_state_rows(self):
        rows=[]
        for symbol in ("US500","NAS100"):
            for window in self.windows:
                bid=_read_chunk_ticks(self._chunk_path(symbol,"BID",window.session_date))
                ask=_read_chunk_ticks(self._chunk_path(symbol,"ASK",window.session_date))
                boundary=window.to_ms+1
                last_bid=bid[-1] if bid else None
                last_ask=ask[-1] if ask else None
                spread=(last_ask.price-last_bid.price) if last_bid and last_ask else None
                availability=(
                    "CAUSAL_TWO_SIDED_AVAILABLE" if last_bid and last_ask
                    else "MISSING_BID" if last_ask
                    else "MISSING_ASK" if last_bid
                    else "MISSING_BOTH_SIDES"
                )
                rows.append({
                    "symbol":symbol,"session_date":window.session_date,
                    "boundary_timestamp_ms":boundary,
                    "bid":None if last_bid is None else last_bid.price,
                    "ask":None if last_ask is None else last_ask.price,
                    "bid_timestamp_ms":None if last_bid is None else last_bid.timestamp_ms,
                    "ask_timestamp_ms":None if last_ask is None else last_ask.timestamp_ms,
                    "bid_age_ms":None if last_bid is None else boundary-last_bid.timestamp_ms,
                    "ask_age_ms":None if last_ask is None else boundary-last_ask.timestamp_ms,
                    "spread":spread,"availability":availability,
                })
        return rows

    def _load_old_resume(self):
        old_root=self.repo_root/OLD_V3_WORK_REL
        resume_path=old_root/"resume.json"
        if not resume_path.is_file():
            raise CaptureContractError(
                "preserved Tier-1 V3 resume/chunks missing; keep .m6_cost_evidence_work/tier1_us500_nas100_v3"
            )
        state=json.loads(resume_path.read_text(encoding="utf-8"))
        completed=state.get("completed")
        if not isinstance(completed,dict):
            raise CaptureContractError("preserved Tier-1 V3 resume has no completed chunk map")
        return old_root,completed

    def _verified_old_ticks(self,old_root:Path,completed:dict,symbol:str,side:str,session_date:str):
        key=f"{symbol}:{side}:{session_date}"
        rec=completed.get(key)
        path=old_root/"chunks"/symbol/side/f"{session_date}.csv"
        if not isinstance(rec,dict) or not path.is_file():
            raise CaptureContractError(f"preserved V3 chunk unavailable: {key}")
        expected=str(rec.get("sha256") or "")
        actual=sha256_file(path)
        if not expected or actual!=expected:
            raise CaptureContractError(f"preserved V3 chunk hash mismatch: {key}")
        return _read_chunk_ticks(path)

    def _write_preopen_csv(self,rows):
        path=self.output_dir/"derived"/"PREOPEN_0930_CAUSAL_STATE.csv"
        path.parent.mkdir(parents=True,exist_ok=True)
        fields=[
            "symbol","session_date","boundary_timestamp_ms","bid","ask",
            "bid_timestamp_ms","ask_timestamp_ms","bid_age_ms","ask_age_ms",
            "spread","availability"
        ]
        with path.open("w",encoding="utf-8",newline="") as fh:
            w=csv.DictWriter(fh,fieldnames=fields,lineterminator="\n")
            w.writeheader()
            for row in rows:
                out=dict(row)
                for k in ("bid","ask","spread"):
                    out[k]="" if out[k] is None else _price(out[k])
                for k in ("bid_timestamp_ms","ask_timestamp_ms","bid_age_ms","ask_age_ms"):
                    out[k]="" if out[k] is None else out[k]
                w.writerow(out)
        return {"path":path.relative_to(self.output_dir).as_posix(),"rows":len(rows),"sha256":sha256_file(path)}

    def _write_c012_generic_cost_support(self,preopen_rows):
        pre_by={(r["symbol"],r["session_date"]):r for r in preopen_rows}
        old_root,completed=self._load_old_resume()
        path=self.output_dir/"derived"/"NAS100_C012_GENERIC_BOUND_COST_SUPPORT.csv"
        path.parent.mkdir(parents=True,exist_ok=True)
        fields=[
            "session_date","boundary_timestamp_ms","causal_bid","causal_ask","causal_spread",
            "causal_bid_age_ms","causal_ask_age_ms","refresh_timestamp_ms",
            "refresh_bid","refresh_ask","refresh_delay_ms","absolute_mid_displacement_points",
            "state"
        ]
        boundary_rows=0
        valid_rows=0
        missing_causal=0
        missing_refresh=0
        max_spread=0.0
        max_move=0.0
        local_raw_files_verified=0
        started=time.monotonic()
        with path.open("w",encoding="utf-8",newline="") as fh:
            w=csv.DictWriter(fh,fieldnames=fields,lineterminator="\n")
            w.writeheader()
            for n,window in enumerate(self.windows,1):
                session=self.calendar.session(datetime.fromisoformat(window.session_date).date())
                if session is None:
                    continue
                bids=self._verified_old_ticks(old_root,completed,"NAS100","BID",window.session_date)
                asks=self._verified_old_ticks(old_root,completed,"NAS100","ASK",window.session_date)
                local_raw_files_verified+=2
                pre=pre_by[("NAS100",window.session_date)]
                if pre["bid_timestamp_ms"] is not None:
                    bids=[DecodedTick(int(pre["bid_timestamp_ms"]),int(round(float(pre["bid"])*100000)))]+bids
                if pre["ask_timestamp_ms"] is not None:
                    asks=[DecodedTick(int(pre["ask_timestamp_ms"]),int(round(float(pre["ask"])*100000)))]+asks
                index=BoundaryQuoteIndex(bids,asks)
                boundary=int(session.open_utc.timestamp()*1000)
                last_entry=int((session.close_utc.timestamp()-3600)*1000)
                close_ms=int(session.close_utc.timestamp()*1000)
                while boundary<=last_entry:
                    boundary_rows+=1
                    causal=index.causal_state_at_boundary(boundary)
                    row={
                        "session_date":window.session_date,"boundary_timestamp_ms":boundary,
                        "causal_bid":"","causal_ask":"","causal_spread":"",
                        "causal_bid_age_ms":"","causal_ask_age_ms":"",
                        "refresh_timestamp_ms":"","refresh_bid":"","refresh_ask":"",
                        "refresh_delay_ms":"","absolute_mid_displacement_points":"",
                        "state":""
                    }
                    if causal.availability!="CAUSAL_TWO_SIDED_AVAILABLE":
                        missing_causal+=1
                        row["state"]="MISSING_CAUSAL_STATE"
                        w.writerow(row)
                        boundary+=15*60*1000
                        continue
                    row.update({
                        "causal_bid":_price(causal.bid),"causal_ask":_price(causal.ask),
                        "causal_spread":_price(causal.spread),
                        "causal_bid_age_ms":causal.bid_age_ms,"causal_ask_age_ms":causal.ask_age_ms,
                    })
                    post_bid=index.first_post_bid(boundary)
                    post_ask=index.first_post_ask(boundary)
                    if post_bid is None or post_ask is None:
                        missing_refresh+=1
                        row["state"]="MISSING_POST_BOUNDARY_SIDE_EVENT"
                        w.writerow(row)
                        boundary+=15*60*1000
                        continue
                    refresh_ts=max(post_bid.timestamp_ms,post_ask.timestamp_ms)
                    if refresh_ts>close_ms:
                        missing_refresh+=1
                        row["state"]="BILATERAL_REFRESH_AFTER_SESSION_CLOSE"
                        w.writerow(row)
                        boundary+=15*60*1000
                        continue
                    refreshed=index.causal_state_at_boundary(refresh_ts)
                    if refreshed.availability!="CAUSAL_TWO_SIDED_AVAILABLE":
                        missing_refresh+=1
                        row["state"]="BILATERAL_REFRESH_STATE_UNAVAILABLE"
                        w.writerow(row)
                        boundary+=15*60*1000
                        continue
                    causal_mid=(float(causal.bid)+float(causal.ask))/2.0
                    refresh_mid=(float(refreshed.bid)+float(refreshed.ask))/2.0
                    move=abs(refresh_mid-causal_mid)
                    max_spread=max(max_spread,float(causal.spread))
                    max_move=max(max_move,move)
                    valid_rows+=1
                    row.update({
                        "refresh_timestamp_ms":refresh_ts,
                        "refresh_bid":_price(refreshed.bid),"refresh_ask":_price(refreshed.ask),
                        "refresh_delay_ms":refresh_ts-boundary,
                        "absolute_mid_displacement_points":_price(move),
                        "state":"VALID_GENERIC_COST_SUPPORT",
                    })
                    w.writerow(row)
                    boundary+=15*60*1000
                if n==1 or n%25==0 or n==len(self.windows):
                    elapsed=max(0.001,time.monotonic()-started)
                    self._stage(
                        f"[LOCAL FINALIZE {100*n/len(self.windows):5.1f}%] NAS100 sessions {n}/{len(self.windows)} | "
                        f"boundaries {boundary_rows} | old raw files hash-verified {local_raw_files_verified} | "
                        f"elapsed {_fmt_seconds(elapsed)}"
                    )
        return {
            "path":path.relative_to(self.output_dir).as_posix(),
            "sha256":sha256_file(path),
            "boundary_rows":boundary_rows,
            "valid_rows":valid_rows,
            "missing_causal_rows":missing_causal,
            "missing_bilateral_refresh_rows":missing_refresh,
            "max_causal_spread_points":max_spread,
            "max_absolute_mid_displacement_to_first_bilateral_refresh_points":max_move,
            "constant_transaction_envelope_points":max_spread+max_move if valid_rows else None,
            "old_v3_raw_files_locally_hash_reverified":local_raw_files_verified,
            "fill_authority":False,
            "candidate_inputs_used":False,
        }

    def _raw_commitment(self,records):
        normalized=[]
        streams={}
        for r in records:
            item={k:r[k] for k in (
                "key","symbol","symbol_id","quote_type","session_date","from_ms","to_ms",
                "row_count","page_count","pagination_boundary_fallback_count","sha256"
            )}
            normalized.append(item)
        normalized=sorted(normalized,key=lambda x:x["key"])
        for symbol in ("US500","NAS100"):
            for side in ("BID","ASK"):
                subset=[x for x in normalized if x["symbol"]==symbol and x["quote_type"]==side]
                streams[f"{symbol}_{side}"]={
                    "chunk_count":len(subset),
                    "row_count":sum(int(x["row_count"]) for x in subset),
                    "manifest_sha256":hashlib.sha256(canonical_json_bytes(subset)).hexdigest(),
                }
        return {
            "schema":"mxm.greenfield.v2.tier1-preopen-local-raw-commitment.v1",
            "chunk_count":len(normalized),
            "total_rows":sum(int(x["row_count"]) for x in normalized),
            "ordered_manifest_sha256":hashlib.sha256(canonical_json_bytes(normalized)).hexdigest(),
            "streams":streams,
            "raw_bytes_transferred":False,
            "raw_bytes_retained_locally":True,
            "local_retention_path":NEW_WORK_REL+"/chunks",
            "deletion_authorized":False,
        }

    def _finalize(self,records):
        self._stage("[3/3] Finalizing compact pre-open supplement")
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)
        evidence=self.output_dir/"evidence"
        evidence.mkdir()
        pre_rows=self._preopen_state_rows()
        pre_meta=self._write_preopen_csv(pre_rows)
        self._stage("[LOCAL] Deriving complete NAS100 C012 generic adverse-cost support from preserved V3 chunks")
        c012_support=self._write_c012_generic_cost_support(pre_rows)
        commitment=self._raw_commitment(records)
        two_sided=sum(1 for r in pre_rows if r["availability"]=="CAUSAL_TWO_SIDED_AVAILABLE")
        atomic_write_json(evidence/"account.json",drop_secret_fields(self._account_evidence))
        atomic_write_json(evidence/"symbol_verification.json",self._symbol_evidence)
        atomic_write_json(evidence/"raw_preopen_chunk_commitment.json",commitment)
        atomic_write_json(evidence/"preopen_summary.json",{
            "schema":"mxm.greenfield.v2.tier1-preopen-0930-summary.v1",
            "window_local":"09:15:00.000-09:29:59.999 America/New_York",
            "boundary":"09:30:00.000 America/New_York",
            "rows":len(pre_rows),
            "causal_two_sided_available":two_sided,
            "causal_state_file":pre_meta,
            "c012_generic_cost_support":c012_support,
            "methodology":"candidate-independent; bilateral refresh is diagnostic cost support, never fill timing",
            "economics":False,
            "protected_evidence":False,
        })
        atomic_write_json(self.output_dir/"provenance_manifest.json",{
            "schema":BUNDLE_SCHEMA,
            "tool_version":PREOPEN_TOOL_VERSION,
            "source_environment":"Pepperstone - Europe LIVE",
            "oauth_scope":"accounts","orders":False,"account_mutation":False,"economics":False,
            "candidate_outcomes_opened":0,"attempts_consumed":0,"protected_evidence_opened":False,
            "targets":self._symbol_evidence,
            "acquisition_domain":"ALL_WEEKDAY_09_15_TO_09_29_59_999_AMERICA_NEW_YORK_SIGNAL_BLIND",
            "plan":PREOPEN_PLAN_REL,
            "resume_contract":self.resume_contract,
            "raw_preopen_commitment":commitment,
            "existing_v3_raw_bulk_transfer":False,
            "existing_v3_raw_local_analysis_only":True,
            "candidate_market_proxy_mutated":False,
        })
        atomic_write_json(self.output_dir/"bundle_manifest.json",{
            "schema":BUNDLE_SCHEMA,
            "transfer_mode":"COMPACT",
            "required_targets":["US500","NAS100"],
            "raw_tick_files_embedded":0,
            "derived_files":[pre_meta["path"],c012_support["path"]],
            "protected_boundary_excluded":True,
            "local_raw_retention_required":True,
            "transfer_instruction":"Return only this compact ZIP. Keep both .m6_cost_evidence_work/tier1_us500_nas100_v3 and .m6_cost_evidence_work/tier1_preopen_0930_v1 until explicitly authorized for deletion.",
        })
        scan_bundle_for_secrets(self.output_dir,[self.client_id,self.client_secret,self.access_token])
        checks=[]
        for path in sorted(p for p in self.output_dir.rglob("*") if p.is_file() and p.name!="CHECKSUMS.sha256"):
            checks.append(f"{sha256_file(path)}  {path.relative_to(self.output_dir).as_posix()}")
        (self.output_dir/"CHECKSUMS.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8")
        target=self.output_dir.parent/"MXM_M6_TIER1_PREOPEN_0930_SUPPLEMENT_V1.zip"
        if target.exists():
            target.unlink()
        deterministic_zip_directory(self.output_dir,target)
        self._stage(f"[DONE] {target}")
        self._stage(f"[SHA256] {sha256_file(target)}")
        return target

    def run(self):
        self.work_dir.mkdir(parents=True,exist_ok=True)
        self._stage("[RATE] historical tick pacing 0.21s; official ceiling 5 historical req/s/connection")
        try:
            account_id=self._authenticate_and_verify_targets()
            records=self._capture_all(account_id)
            return self._finalize(records)
        finally:
            self.transport.close()
            self.access_token=None
