"""Compact read-only friction qualification + 13-week M5 Stage-A capture V6.

Evidence-integrity law:
- one canonical M5 normalizer;
- official broker-native conversion chains for material cross-currency commission;
- same-window historical conversion only;
- true intra-window spread tails;
- equal-window qualification aggregation;
- software/contract failures abort capture and never become economic market failures.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import statistics
import time
import zipfile
from collections import defaultdict
from datetime import date, datetime, time as dtime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from google.protobuf.json_format import MessageToDict

from competition.friction_costs import (
    COMMISSION_CONVERSION_UNRESOLVED,
    FRICTION_UNRESOLVED,
    FULL_FRICTION_RESOLVED,
    SPREAD_RESOLVED_COMMISSION_BOUNDED,
    required_conversion_currencies,
    type_aware_roundtrip_commission,
)
from competition.frontier_data_capture import normalize_m5
from m6.cost_evidence import causal_merge_bid_ask, decode_ctrader_tick_page, next_tick_page_to_ms
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
    ProtoOAGetTickDataReq,
    ProtoOAGetTrendbarsReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsForConversionReq,
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport

PLAN_REL="data/COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json"
PROTOCOL_REL="data/COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json"
EXPECTED_PLAN_SHA="bb80361bbfdd732529a50d62a290d57d5ec256308e508c686a6a26c376079520"
OUTPUT_FILENAME="MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6.zip"
TOOL_VERSION="MXM_COMPETITION_ULTRA_FAST_ANDROID_STDLIB_V6_STAGE_A_LOWER_BOUNDARY_CLIP"
QUOTE_TYPES={"BID":1,"ASK":2}
RAW_HEADER=("time_utc","open","high","low","close","tick_volume")
# Official cTrader historical-data limit is 5 requests/second/connection.
# Keep deterministic headroom for scheduler/network jitter and additionally honor server retryAfter.
HISTORICAL_MIN_INTERVAL_SECONDS=0.26
MIN_INTERVAL=HISTORICAL_MIN_INTERVAL_SECONDS
RATE_LIMIT_FALLBACK_SECONDS=2.0
RATE_LIMIT_GUARD_SECONDS=0.25
RATE_LIMIT_RETRY_BUDGET=8
PROTECTED_UTC="2026-09-17T12:02:58Z"
ELIGIBLE_COST_STATES={FULL_FRICTION_RESOLVED,SPREAD_RESOLVED_COMMISSION_BOUNDED}
VALID_FRICTION_STATES={"FRICTION_PASS","FRICTION_WATCH","FRICTION_FAIL",FRICTION_UNRESOLVED}
STAGE_COMPLETION_REASONS={"HAS_MORE_FALSE","SHORT_PAGE_INTERVAL_EXHAUSTED","FROM_BOUNDARY_REACHED","EMPTY_FINAL_PAGE_AFTER_FULL_PAGE","EMPTY_INTERVAL"}
CHECKPOINT_SCHEMA="mxm.greenfield.v2.ultra-fast-friction-checkpoint.v5"


class ImplementationInvalid(CaptureContractError):
    """Deterministic implementation/schema/contract failure. Never market evidence."""


class ConversionUnavailable(Exception):
    """Broker-native conversion chain/rate is legitimately unavailable for a sampled window."""


class CheckpointInvalid(CaptureContractError):
    """Local checkpoint cannot be reused; recapture friction without trusting it."""


class PayloadRateLimited(Exception):
    """Server-side payload block/rate limit. Retry only after the broker-provided cooldown."""

    def __init__(self,retry_after=0.0,description=""):
        try:
            value=float(retry_after or 0.0)
        except (TypeError,ValueError):
            value=0.0
        self.retry_after=max(0.0,value)
        self.description=str(description or "")
        super().__init__(f"BLOCKED_PAYLOAD_TYPE retry_after={self.retry_after:g}s")


def _plain(message):
    return MessageToDict(message,preserving_proto_field_name=False,use_integers_for_enums=True)


def _utc(value):
    x=datetime.fromisoformat(value[:-1]+"+00:00" if value.endswith("Z") else value)
    if x.tzinfo is None or x.utcoffset()!=timedelta(0):
        raise ImplementationInvalid("explicit UTC required")
    return x.astimezone(timezone.utc)


def _iso(x):
    return x.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")


def _ms(x):
    return int(x.timestamp()*1000)


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def _canon(obj):
    value={k:v for k,v in obj.items() if k!="plan_sha256"}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def _json_sha(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def _trendbar_has_more(response):
    descriptor=getattr(response,"DESCRIPTOR",None)
    fields=getattr(descriptor,"fields_by_name",{}) if descriptor is not None else {}
    if "hasMore" in fields:
        return True,bool(getattr(response,"hasMore"))
    if hasattr(response,"hasMore"):
        return True,bool(getattr(response,"hasMore"))
    return False,None


def margin_pct_eur200(value):
    return float(Decimal(str(value))/Decimal("2"))


def validate_plan(plan,protocol):
    if plan.get("schema")!="mxm.greenfield.v2.ultra-fast-competition-capture-plan.v4":
        raise ImplementationInvalid("invalid ultra-fast V4 plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_PRE_OUTCOME_TRENDBAR_PAGINATION_CHECKPOINT_CORRECTED":
        raise ImplementationInvalid("ultra-fast V4 plan not frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or _canon(plan)!=EXPECTED_PLAN_SHA:
        raise ImplementationInvalid("ultra-fast V4 plan hash mismatch")
    if protocol.get("schema")!="mxm.greenfield.v2.ultra-fast-data-minimal-discovery-protocol.v3":
        raise ImplementationInvalid("invalid ultra-fast V3 protocol schema")
    if protocol.get("status")!="FROZEN_PRE_FRICTION_PRE_STAGE_A_OUTCOME_CONVERSION_TAIL_INTEGRITY_CORRECTED":
        raise ImplementationInvalid("ultra-fast V3 protocol not frozen")
    if len(plan.get("shortlist") or [])!=32 or plan.get("max_stage_a_markets")!=12:
        raise ImplementationInvalid("unexpected shortlist/Stage-A cap")
    if any(abs(margin_pct_eur200(x["accepted_min_margin_eur"])-float(x["accepted_min_margin_pct_eur200"]))>1e-9 for x in plan["shortlist"]):
        raise ImplementationInvalid("factor-100 margin regression")
    if plan.get("economic_outcomes_opened")!=0 or plan.get("v2_attempts_consumed")!=0 or plan.get("protected_evidence_opened") is not False:
        raise ImplementationInvalid("capture plan economically contaminated")
    return True


def _q(values,q):
    xs=sorted(float(x) for x in values)
    if not xs:
        return None
    p=(len(xs)-1)*q
    a=int(math.floor(p));b=int(math.ceil(p))
    return xs[a] if a==b else xs[a]+(xs[b]-xs[a])*(p-a)


def _med(values):
    return statistics.median(values) if values else None


def _window(ds,start,end,label):
    d=date.fromisoformat(ds)
    a=datetime.combine(d,dtime.fromisoformat(start),timezone.utc)
    b=datetime.combine(d,dtime.fromisoformat(end),timezone.utc)
    return {"label":label,"from_ms":_ms(a),"to_ms":_ms(b),"start_utc":_iso(a),"end_utc":_iso(b)}


def friction_windows(protocol,profile):
    profiles=protocol["friction_screen"]["profiles"]
    if profile in {"GLOBAL_24X5","US_REGIONAL"}:
        z=profiles[profile]
        return [_window(d,w["start"],w["end"],w["label"]) for d in z["sample_dates"] for w in z["utc_windows"]]
    if profile=="CRYPTO_24X7":
        out=friction_windows(protocol,"GLOBAL_24X5")
        for ds in profiles["GLOBAL_24X5"]["sample_dates"]:
            d=date.fromisoformat(ds);monday=d-timedelta(days=d.weekday())
            for w in profiles[profile]["weekend_windows_per_week"]:
                x=monday+timedelta(days=5 if w["weekday"]=="SATURDAY" else 6)
                out.append(_window(x.isoformat(),w["start"],w["end"],w["label"]))
        return sorted(out,key=lambda x:(x["from_ms"],x["label"]))
    raise ImplementationInvalid("unknown friction profile")


def qualify_friction(metrics,rules):
    if metrics.get("cost_confidence_state") not in ELIGIBLE_COST_STATES:
        return FRICTION_UNRESOLVED
    floor=rules["evidence_floor"]
    if (
        metrics.get("two_sided_window_coverage",0)<floor["min_two_sided_window_coverage"]
        or metrics.get("quote_state_count",0)<floor["min_quote_states"]
        or (metrics.get("median_m5_range") or 0)<=0
    ):
        return FRICTION_UNRESOLVED

    def ok(rule):
        return (
            metrics["two_sided_window_coverage"]>=rule["min_two_sided_window_coverage"]
            and metrics["quote_state_count"]>=rule["min_quote_states"]
            and (metrics.get("median_m5_range") or 0)>0
            and (metrics.get("median_window_p75_spread_over_range") or math.inf)<=rule["max_median_window_p75_spread_over_range"]
            and (metrics.get("p75_window_p95_spread_over_range") or math.inf)<=rule["max_p75_window_p95_spread_over_range"]
            and (metrics.get("median_window_p75_effective_friction_over_range") or math.inf)<=rule["max_median_window_p75_effective_friction_over_range"]
            and (metrics.get("p75_window_p95_effective_friction_over_range") or math.inf)<=rule["max_p75_window_p95_effective_friction_over_range"]
            and (metrics.get("median_spread_over_mid") or math.inf)<=rule["max_median_spread_over_mid"]
        )
    if ok(rules["FRICTION_PASS"]):
        return "FRICTION_PASS"
    if ok(rules["FRICTION_WATCH"]):
        return "FRICTION_WATCH"
    return "FRICTION_FAIL"


def _rank(x):
    tier={"FRICTION_PASS":0,"FRICTION_WATCH":1}.get(x.get("friction_state"),9)
    confidence={FULL_FRICTION_RESOLVED:0,SPREAD_RESOLVED_COMMISSION_BOUNDED:1}.get(x.get("cost_confidence_state"),9)
    move=x.get("movement_to_window_balanced_p75_effective_friction") or 0
    return (
        tier,confidence,-float(move),
        float(x["accepted_min_margin_pct_eur200"]),
        -float(x["schedule_minutes_per_week"]),
        float(x.get("p75_window_p95_effective_friction_over_range") or math.inf),
        x["broker_symbol"],
    )


def _eligible_for_selection(x):
    if x.get("cost_confidence_state") not in ELIGIBLE_COST_STATES:
        return False
    if x.get("friction_state")=="FRICTION_PASS":
        return True
    return x.get("friction_state")=="FRICTION_WATCH" and float(x.get("movement_to_window_balanced_p75_effective_friction") or 0)>=2.0


def select_stage_a(results,law):
    by=defaultdict(list)
    for x in results:
        if _eligible_for_selection(x):
            by[x["family"]].append(x)
    for xs in by.values():
        xs.sort(key=_rank)

    chosen=[];variants=set();counts=defaultdict(int)
    def add(x):
        if x["variant_family"] in variants:
            return False
        chosen.append(x);variants.add(x["variant_family"]);counts[x["family"]]+=1
        return True

    for family,quota in law["family_target_quotas"].items():
        for x in by.get(family,[]):
            if counts[family]>=quota:
                break
            add(x)

    pool=sorted([x for xs in by.values() for x in xs if x["friction_state"]=="FRICTION_PASS"],key=_rank)
    for x in pool:
        if len(chosen)>=law["max_stage_a_markets"]:
            break
        if x in chosen or counts[x["family"]]>=4:
            continue
        add(x)
    return chosen[:law["max_stage_a_markets"]],{f:[x["broker_symbol"] for x in xs if x not in chosen] for f,xs in by.items()}


def _inspect_stage_csv(path,plan):
    rows=0;first=last=None;prev=None
    start=_utc(plan["stage_a_interval"]["start_utc"]);end=_utc(plan["stage_a_interval"]["end_utc"]);protected=_utc(PROTECTED_UTC)
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        reader=csv.DictReader(f)
        if tuple(reader.fieldnames or ())!=RAW_HEADER:
            raise ImplementationInvalid(f"unexpected Stage-A CSV header: {path}")
        for row in reader:
            t=_utc(row["time_utc"])
            if prev is not None and t<=prev:
                raise ImplementationInvalid(f"non-increasing Stage-A timestamps: {path}")
            if t<start or t+timedelta(minutes=5)>end or t+timedelta(minutes=5)>=protected:
                raise ImplementationInvalid(f"Stage-A row outside completed-bar DEVELOPMENT boundary: {path}")
            for k in ("open","high","low","close"):
                float(row[k])
            int(row["tick_volume"])
            rows+=1;first=first or row["time_utc"];last=row["time_utc"];prev=t
    return {"row_count":rows,"first_timestamp_utc":first,"last_timestamp_utc":last,"sha256":_sha(path)}


def _write_checksums(bundle):
    files=sorted(x for x in Path(bundle).rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256")
    path=Path(bundle)/"CHECKSUMS.sha256"
    path.write_text("\n".join(f"{_sha(p)}  {p.relative_to(bundle).as_posix()}" for p in files)+"\n",encoding="utf-8")
    return path


def _verify_checksums(bundle):
    bundle=Path(bundle);path=bundle/"CHECKSUMS.sha256"
    if not path.is_file():
        raise ImplementationInvalid("CHECKSUMS.sha256 missing")
    declared={}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest,rel=line.split("  ",1)
        if rel in declared:
            raise ImplementationInvalid("duplicate checksum path")
        declared[rel]=digest
    actual={p.relative_to(bundle).as_posix():_sha(p) for p in sorted(x for x in bundle.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256")}
    if declared!=actual:
        raise ImplementationInvalid("bundle checksum manifest mismatch")
    return True


def validate_capture_postconditions(*,plan,friction_results,selection,series,bundle,manifest,conversion_summary,verify_checksums=False):
    expected=[x["broker_symbol"] for x in plan["shortlist"]]
    observed=[x.get("broker_symbol") for x in friction_results]
    if len(friction_results)!=32 or len(set(observed))!=32 or set(observed)!=set(expected):
        raise ImplementationInvalid("friction evidence does not account for exact 32-symbol shortlist")
    valid_evidence=0
    for x in friction_results:
        if x.get("friction_state") not in VALID_FRICTION_STATES:
            raise ImplementationInvalid("invalid friction evidence state")
        if x.get("cost_confidence_state") not in {FULL_FRICTION_RESOLVED,SPREAD_RESOLVED_COMMISSION_BOUNDED,COMMISSION_CONVERSION_UNRESOLVED,FRICTION_UNRESOLVED}:
            raise ImplementationInvalid("invalid cost-confidence state")
        windows=x.get("window_summaries") or []
        if len(windows)!=x.get("planned_windows"):
            raise ImplementationInvalid("window summary cardinality mismatch")
        for w in windows:
            if w.get("quote_states",0)>0:
                for label in ("spread_median","spread_p75","spread_p90","spread_p95"):
                    if w.get(label) is None:
                        raise ImplementationInvalid(f"missing true spread tail {label}")
                if not (w["spread_median"]<=w["spread_p75"]<=w["spread_p90"]<=w["spread_p95"]):
                    raise ImplementationInvalid("spread quantile ordering invalid")
            commission=w.get("commission") or {}
            confidence=commission.get("cost_confidence_state")
            if confidence not in {FULL_FRICTION_RESOLVED,SPREAD_RESOLVED_COMMISSION_BOUNDED,COMMISSION_CONVERSION_UNRESOLVED}:
                raise ImplementationInvalid("window commission confidence missing")
            evidence=commission.get("conversion_evidence") or {}
            for _,ev in evidence.items():
                if ev.get("window_start_utc")!=w.get("start_utc") or ev.get("window_end_utc")!=w.get("end_utc"):
                    raise ImplementationInvalid("historical conversion window does not match friction window")
                if ev.get("used_current_or_future_rate"):
                    raise ImplementationInvalid("current/future conversion substitution forbidden")
        if x["friction_state"] in {"FRICTION_PASS","FRICTION_WATCH","FRICTION_FAIL"}:
            valid_evidence+=1
    if valid_evidence==0:
        raise ImplementationInvalid("no valid friction evidence across the shortlist")

    final=list(selection.get("final_selected") or [])
    if len(final)!=len(set(final)) or len(final)>plan["max_stage_a_markets"]:
        raise ImplementationInvalid("invalid final Stage-A selection cardinality")
    index={x["broker_symbol"]:x for x in friction_results}
    for symbol in final:
        x=index.get(symbol)
        if not x or not _eligible_for_selection(x):
            raise ImplementationInvalid(f"selected market lacks valid resolved PASS/WATCH evidence: {symbol}")

    if len(series)!=len(final) or manifest.get("stage_a_selected_count")!=len(final):
        raise ImplementationInvalid("selection/manifest/series counts disagree")
    if manifest.get("friction_shortlist_count")!=32:
        raise ImplementationInvalid("manifest friction shortlist count mismatch")
    if manifest.get("raw_ticks_transferred") is not False or manifest.get("raw_conversion_ticks_transferred") is not False:
        raise ImplementationInvalid("raw tick transfer forbidden")
    if manifest.get("orders_placed") is not False or manifest.get("account_mutation") is not False:
        raise ImplementationInvalid("capture safety postcondition violated")
    if manifest.get("economic_outcomes_opened")!=0 or manifest.get("v2_attempts_consumed")!=0:
        raise ImplementationInvalid("capture unexpectedly consumed economics")

    if conversion_summary.get("raw_conversion_ticks_transferred") is not False:
        raise ImplementationInvalid("conversion summary permits raw tick transfer")
    for chain in conversion_summary.get("chains",[]):
        if not chain.get("first_asset_id") or not chain.get("last_asset_id") or not chain.get("symbols"):
            raise ImplementationInvalid("unbound conversion-chain authority")
    for ev in conversion_summary.get("window_rates",[]):
        if ev.get("used_current_or_future_rate"):
            raise ImplementationInvalid("conversion cache contains current/future substitution")

    series_by={x["broker_symbol"]:x for x in series}
    if set(series_by)!=set(final):
        raise ImplementationInvalid("Stage-A series symbols differ from final selection")
    minrows=int(plan["capture_law"]["min_stage_a_m5_rows"])
    for symbol,record in series_by.items():
        path=Path(bundle)/record["file"]
        if not path.is_file():
            raise ImplementationInvalid(f"missing Stage-A CSV {symbol}")
        inspected=_inspect_stage_csv(path,plan)
        if inspected["row_count"]<minrows:
            raise ImplementationInvalid(f"selected Stage-A market below minimum rows {symbol}")
        if record["row_count"]!=inspected["row_count"] or record["sha256"]!=inspected["sha256"]:
            raise ImplementationInvalid(f"Stage-A manifest/hash mismatch {symbol}")
        pagination=record.get("pagination") or {}
        if pagination.get("request_interval_exhausted") is not True:
            raise ImplementationInvalid(f"Stage-A interval completeness missing {symbol}")
        if pagination.get("completion_reason") not in STAGE_COMPLETION_REASONS:
            raise ImplementationInvalid(f"Stage-A pagination completion reason invalid {symbol}")
        if pagination.get("normalized_unique_completed_bars")!=record["row_count"]:
            raise ImplementationInvalid(f"Stage-A pagination unique-bar count mismatch {symbol}")
        if pagination.get("conflicts")!=0:
            raise ImplementationInvalid(f"Stage-A pagination conflicts nonzero {symbol}")
        if pagination.get("first_timestamp_utc")!=record["first_timestamp_utc"] or pagination.get("last_timestamp_utc")!=record["last_timestamp_utc"]:
            raise ImplementationInvalid(f"Stage-A pagination boundary metadata mismatch {symbol}")

    if final and manifest.get("status")!="COMPACT_FRICTION_AND_STAGE_A_DEVELOPMENT_CAPTURE_COMPLETE":
        raise ImplementationInvalid("non-empty Stage-A bundle has wrong completion status")
    if not final and manifest.get("status")!="FRICTION_QUALIFICATION_COMPLETE_NO_STAGE_A_MARKETS":
        raise ImplementationInvalid("zero-market bundle must not claim Stage-A completion")
    if verify_checksums:
        _verify_checksums(bundle)
    return True


class UltraFastCaptureRunner:
    def __init__(self,*,plan,protocol,client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        validate_plan(plan,protocol)
        self.plan=dict(plan);self.protocol=dict(protocol);self.client_id=client_id;self.client_secret=client_secret
        self.access_token=access_token;self.config=dict(config);self.root=Path(repo_root);self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/"competition_ultra_fast_output"/"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V4"
        self.checkpoint_dir=self.root/"competition_ultra_fast_checkpoint"/"MXM_COMPETITION_ULTRA_FAST_FRICTION_CHECKPOINT_V5"
        self.zip_path=self.root/OUTPUT_FILENAME
        self._app=False;self._account=None;self._last=None;self._requests=0
        self._tick_cache={}
        self._conversion_chain_cache={}
        self._conversion_rate_cache={}
        self._assets={}
        self._asset_ids={}
        self._light={}

    def _request(self,request,historical=False):
        require_read_only_request(type(request).__name__)
        if historical:
            now=time.monotonic();wait=0 if self._last is None else MIN_INTERVAL-(now-self._last)
            if wait>0:
                time.sleep(wait)
            self._last=time.monotonic()
        response=self.transport.request(request,timeout=60)
        if type(response).__name__=="ProtoOAErrorRes":
            code=str(getattr(response,"errorCode","UNKNOWN"))
            if code=="BLOCKED_PAYLOAD_TYPE":
                retry_after=getattr(response,"retryAfter",0)
                description=getattr(response,"description","")
                raise PayloadRateLimited(retry_after=retry_after,description=description)
            raise CaptureContractError(f"cTrader API error: {code}")
        if historical:
            self._requests+=1
        return response

    def _restore(self):
        self.transport.connect()
        if self._app:
            self._request(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
        if self._account is not None:
            self._request(ProtoOAAccountAuthReq(ctidTraderAccountId=self._account,accessToken=self.access_token))

    def _send(self,request,historical=False,retries=4):
        last=None
        transport_attempt=0
        rate_limit_hits=0
        while transport_attempt<retries:
            try:
                return self._request(request,historical)
            except PayloadRateLimited as exc:
                rate_limit_hits+=1
                if rate_limit_hits>RATE_LIMIT_RETRY_BUDGET:
                    raise CaptureContractError(
                        f"{type(request).__name__} rate-limit retry budget exhausted after {RATE_LIMIT_RETRY_BUDGET} broker blocks"
                    ) from exc
                delay=max(RATE_LIMIT_FALLBACK_SECONDS,exc.retry_after+RATE_LIMIT_GUARD_SECONDS)
                self.progress(
                    f"[RATE LIMIT BACKOFF] {type(request).__name__} block {rate_limit_hits}/{RATE_LIMIT_RETRY_BUDGET}; "
                    f"retry_after={exc.retry_after:g}s wait={delay:g}s"
                )
                time.sleep(delay)
                self._last=None
                continue
            except (TypeError,AssertionError,KeyError,ValueError) as exc:
                raise ImplementationInvalid(f"{type(request).__name__} implementation/contract failure: {redact_text(str(exc))}") from exc
            except Exception as exc:
                last=exc
                transport_attempt+=1
                if transport_attempt>=retries:
                    break
                time.sleep(min(8,2**(transport_attempt-1)))
                try:
                    self.transport.close();self._restore()
                except Exception as reconnect:
                    last=reconnect
        raise CaptureContractError(f"{type(request).__name__} failed after valid retries: {redact_text(str(last))}")

    def _ticks(self,account_id,symbol_id,side,window):
        key=(int(symbol_id),str(side),int(window["from_ms"]),int(window["to_ms"]))
        if key in self._tick_cache:
            return list(self._tick_cache[key])
        to=window["to_ms"];prev=None;out=[];pages=0;limit=int(self.plan["capture_law"]["max_tick_pages_per_side_window"])
        while to>=window["from_ms"]:
            if pages>=limit:
                raise ImplementationInvalid("friction tick page limit exceeded")
            response=self._send(ProtoOAGetTickDataReq(
                ctidTraderAccountId=account_id,symbolId=symbol_id,type=QUOTE_TYPES[side],
                fromTimestamp=window["from_ms"],toTimestamp=to,
            ),historical=True)
            pages+=1
            page=decode_ctrader_tick_page([{"timestamp":int(x.timestamp),"tick":int(x.tick)} for x in response.tickData])
            out.extend(page)
            if not response.hasMore:
                break
            if not page:
                raise ImplementationInvalid("historical tick response hasMore with empty page")
            nxt=next_tick_page_to_ms(page,current_from_ms=window["from_ms"],previous_oldest_ms=prev)
            if nxt is None:
                break
            oldest=min(x.timestamp_ms for x in page)
            if nxt>=to:
                raise ImplementationInvalid("historical tick pagination did not advance")
            prev=oldest;to=nxt
        canonical=tuple(sorted({(x.timestamp_ms,x.raw_tick):x for x in out}.values(),key=lambda x:(x.timestamp_ms,x.raw_tick)))
        self._tick_cache[key]=canonical
        return list(canonical)

    def _sample_bars(self,account_id,symbol_id,digits,window):
        response=self._send(ProtoOAGetTrendbarsReq(
            ctidTraderAccountId=account_id,symbolId=symbol_id,period=ProtoOATrendbarPeriod.Value("M5"),
            fromTimestamp=window["from_ms"],toTimestamp=window["to_ms"],count=100,
        ),historical=True)
        return normalize_m5(
            [_plain(x) for x in response.trendbar],digits=digits,
            start_utc=window["start_utc"],end_utc=window["end_utc"],protected_utc=PROTECTED_UTC,
        )

    def _conversion_chain(self,account_id,first_asset_id,last_asset_id):
        first_asset_id=int(first_asset_id);last_asset_id=int(last_asset_id)
        if first_asset_id==last_asset_id:
            return []
        key=(first_asset_id,last_asset_id)
        if key in self._conversion_chain_cache:
            return self._conversion_chain_cache[key]
        response=self._send(ProtoOASymbolsForConversionReq(
            ctidTraderAccountId=account_id,firstAssetId=first_asset_id,lastAssetId=last_asset_id
        ))
        chain=[_plain(x) for x in response.symbol]
        if not chain:
            raise ConversionUnavailable(f"broker returned no conversion chain {first_asset_id}->{last_asset_id}")
        current=first_asset_id
        normalized=[]
        for leg in chain:
            try:
                sid=int(leg["symbolId"]);base=int(leg["baseAssetId"]);quote=int(leg["quoteAssetId"])
            except (TypeError,ValueError,KeyError) as exc:
                raise ImplementationInvalid("malformed conversion-chain light symbol") from exc
            if current==base:
                nxt=quote;direction="BASE_TO_QUOTE"
            elif current==quote:
                nxt=base;direction="QUOTE_TO_BASE"
            else:
                raise ImplementationInvalid("broker conversion chain is not contiguous in returned order")
            normalized.append({
                "symbol_id":sid,"symbol_name":leg.get("symbolName"),
                "base_asset_id":base,"quote_asset_id":quote,
                "base_asset":self._assets.get(str(base)),"quote_asset":self._assets.get(str(quote)),
                "direction":direction,
            })
            current=nxt
        if current!=last_asset_id:
            raise ImplementationInvalid("broker conversion chain does not terminate at requested asset")
        self._conversion_chain_cache[key]=normalized
        return normalized

    def _conversion_window_rate(self,account_id,first_asset_id,last_asset_id,window):
        first_asset_id=int(first_asset_id);last_asset_id=int(last_asset_id)
        key=(first_asset_id,last_asset_id,int(window["from_ms"]),int(window["to_ms"]))
        if key in self._conversion_rate_cache:
            return self._conversion_rate_cache[key]
        if first_asset_id==last_asset_id:
            result={
                "first_asset_id":first_asset_id,"last_asset_id":last_asset_id,
                "first_asset":self._assets.get(str(first_asset_id)),"last_asset":self._assets.get(str(last_asset_id)),
                "window_start_utc":window["start_utc"],"window_end_utc":window["end_utc"],
                "rate":1.0,"symbols":[],"used_current_or_future_rate":False,
            }
            self._conversion_rate_cache[key]=result
            return result
        chain=self._conversion_chain(account_id,first_asset_id,last_asset_id)
        current=first_asset_id;rate=1.0;legs=[]
        for leg in chain:
            bid=self._ticks(account_id,leg["symbol_id"],"BID",window)
            ask=self._ticks(account_id,leg["symbol_id"],"ASK",window)
            states=causal_merge_bid_ask(bid,ask)
            if not states:
                raise ConversionUnavailable(f"no same-window two-sided conversion quotes for symbol {leg['symbol_id']}")
            if current==leg["base_asset_id"]:
                values=[x.bid for x in states if x.bid>0]
                direction="BASE_TO_QUOTE_AT_BID";nxt=leg["quote_asset_id"]
            elif current==leg["quote_asset_id"]:
                values=[1.0/x.ask for x in states if x.ask>0]
                direction="QUOTE_TO_BASE_AT_INVERSE_ASK";nxt=leg["base_asset_id"]
            else:
                raise ImplementationInvalid("conversion chain traversal lost asset continuity")
            leg_rate=_med(values)
            if leg_rate is None or leg_rate<=0:
                raise ConversionUnavailable(f"no valid executable conversion rate for symbol {leg['symbol_id']}")
            rate*=leg_rate
            legs.append({
                **leg,"execution_direction":direction,"quote_state_count":len(states),
                "median_bid":_med([x.bid for x in states if x.bid>0]),
                "median_ask":_med([x.ask for x in states if x.ask>0]),
                "median_executable_rate":leg_rate,
            })
            current=nxt
        result={
            "first_asset_id":first_asset_id,"last_asset_id":last_asset_id,
            "first_asset":self._assets.get(str(first_asset_id)),"last_asset":self._assets.get(str(last_asset_id)),
            "window_start_utc":window["start_utc"],"window_end_utc":window["end_utc"],
            "rate":rate,"symbols":legs,"used_current_or_future_rate":False,
        }
        self._conversion_rate_cache[key]=result
        return result

    def _currency_rate_to_quote(self,account_id,currency,quote_asset_id,window,candidate_light,candidate_states):
        currency=str(currency).upper()
        quote_name=str(self._assets.get(str(quote_asset_id)) or "").upper()
        base_id=int(candidate_light["baseAssetId"]);quote_id=int(candidate_light["quoteAssetId"])
        base_name=str(self._assets.get(str(base_id)) or "").upper()
        if currency==quote_name:
            return 1.0,{"method":"IDENTITY","window_start_utc":window["start_utc"],"window_end_utc":window["end_utc"],"rate":1.0,"used_current_or_future_rate":False}
        if currency==base_name and quote_asset_id==quote_id:
            bids=[x.bid for x in candidate_states if x.bid>0]
            rate=_med(bids)
            if rate is None:
                raise ConversionUnavailable(f"no candidate BID to convert {currency}->{quote_name}")
            return rate,{"method":"TRADED_SYMBOL_BASE_TO_QUOTE_AT_BID","symbol_id":int(candidate_light["symbolId"]),"window_start_utc":window["start_utc"],"window_end_utc":window["end_utc"],"rate":rate,"used_current_or_future_rate":False}
        first_id=self._asset_ids.get(currency)
        if first_id is None:
            raise ConversionUnavailable(f"asset ID unavailable for commission currency {currency}")
        evidence=self._conversion_window_rate(account_id,first_id,quote_asset_id,window)
        return float(evidence["rate"]),{"method":"BROKER_NATIVE_CONVERSION_CHAIN",**evidence}

    def _base_to_usd_rate(self,account_id,window,candidate_light,candidate_states):
        base_id=int(candidate_light["baseAssetId"]);quote_id=int(candidate_light["quoteAssetId"])
        base_name=str(self._assets.get(str(base_id)) or "").upper();quote_name=str(self._assets.get(str(quote_id)) or "").upper()
        if base_name=="USD":
            return 1.0,{"method":"IDENTITY","window_start_utc":window["start_utc"],"window_end_utc":window["end_utc"],"rate":1.0,"used_current_or_future_rate":False}
        if quote_name=="USD":
            rate=_med([x.bid for x in candidate_states if x.bid>0])
            if rate is None:
                raise ConversionUnavailable("no candidate BID for base->USD")
            return rate,{"method":"TRADED_SYMBOL_BASE_TO_USD_AT_BID","symbol_id":int(candidate_light["symbolId"]),"window_start_utc":window["start_utc"],"window_end_utc":window["end_utc"],"rate":rate,"used_current_or_future_rate":False}
        usd_id=self._asset_ids.get("USD")
        if usd_id is None:
            raise ConversionUnavailable("USD asset ID unavailable")
        evidence=self._conversion_window_rate(account_id,base_id,usd_id,window)
        return float(evidence["rate"]),{"method":"BROKER_NATIVE_CONVERSION_CHAIN",**evidence}

    def _commission_for_window(self,account_id,full_symbol,light_symbol,window,states,mid):
        required=required_conversion_currencies(full_symbol,light_symbol,self._assets)
        quote_id=int(light_symbol["quoteAssetId"])
        rates={};evidence={};base_to_usd=None
        for item in sorted(required):
            if item=="__UNSUPPORTED_COMMISSION_TYPE__" or item=="__UNSUPPORTED_MIN_COMMISSION_TYPE__":
                continue
            try:
                if item=="__BASE_TO_USD__":
                    base_to_usd,ev=self._base_to_usd_rate(account_id,window,light_symbol,states)
                    evidence["BASE_TO_USD"]=ev
                else:
                    rate,ev=self._currency_rate_to_quote(account_id,item,quote_id,window,light_symbol,states)
                    rates[item]=rate;evidence[f"{item}_TO_QUOTE"]=ev
            except ConversionUnavailable as exc:
                evidence[item]={"state":COMMISSION_CONVERSION_UNRESOLVED,"reason":str(exc),"window_start_utc":window["start_utc"],"window_end_utc":window["end_utc"],"used_current_or_future_rate":False}
        return type_aware_roundtrip_commission(
            full_symbol,light_symbol,self._assets,mid=mid,min_volume_cents=int(full_symbol.get("minVolume") or 0),
            currency_to_quote_rates=rates,base_to_usd_rate=base_to_usd,conversion_evidence=evidence,
        )

    def _friction(self,account_id,candidate,full_symbol,light_symbol):
        summaries=[];pooled_spreads=[];pooled_mids=[];qcount=0
        for window in friction_windows(self.protocol,candidate["friction_profile"]):
            bid=self._ticks(account_id,candidate["symbol_id"],"BID",window)
            ask=self._ticks(account_id,candidate["symbol_id"],"ASK",window)
            states=causal_merge_bid_ask(bid,ask)
            bars=self._sample_bars(account_id,candidate["symbol_id"],int(full_symbol.get("digits",5)),window)
            spreads=[x.spread for x in states if x.spread>=0]
            mids=[(x.bid+x.ask)/2 for x in states if x.bid+x.ask>0]
            ranges=[float(x["high"])-float(x["low"]) for x in bars if float(x["high"])>=float(x["low"])]
            qcount+=len(states);pooled_spreads.extend(spreads);pooled_mids.extend(mids)
            spread_median=_med(spreads);spread_p75=_q(spreads,.75);spread_p90=_q(spreads,.90);spread_p95=_q(spreads,.95)
            mid=_med(mids);rng=_med(ranges)
            commission=self._commission_for_window(account_id,full_symbol,light_symbol,window,states,mid)
            rt=commission.get("roundtrip_commission_price_equivalent")
            ep75=(spread_p75+rt) if spread_p75 is not None and rt is not None else None
            ep90=(spread_p90+rt) if spread_p90 is not None and rt is not None else None
            ep95=(spread_p95+rt) if spread_p95 is not None and rt is not None else None
            summaries.append({
                "label":window["label"],"start_utc":window["start_utc"],"end_utc":window["end_utc"],
                "quote_states":len(states),"m5_bars":len(bars),
                "spread_median":spread_median,"spread_p75":spread_p75,"spread_p90":spread_p90,"spread_p95":spread_p95,
                "median_mid":mid,"median_m5_range":rng,
                "p75_spread_over_range":spread_p75/rng if spread_p75 is not None and rng else None,
                "p95_spread_over_range":spread_p95/rng if spread_p95 is not None and rng else None,
                "effective_friction_p75":ep75,"effective_friction_p90":ep90,"effective_friction_p95":ep95,
                "p75_effective_friction_over_range":ep75/rng if ep75 is not None and rng else None,
                "p95_effective_friction_over_range":ep95/rng if ep95 is not None and rng else None,
                "commission":commission,
            })

        observed=[x for x in summaries if x.get("spread_median") is not None]
        range_windows=[x for x in summaries if (x.get("median_m5_range") or 0)>0 and x.get("spread_p75") is not None]
        cost_states=[x["commission"]["cost_confidence_state"] for x in range_windows]
        if any(x==COMMISSION_CONVERSION_UNRESOLVED for x in cost_states):
            confidence=COMMISSION_CONVERSION_UNRESOLVED
        elif any(x==SPREAD_RESOLVED_COMMISSION_BOUNDED for x in cost_states):
            confidence=SPREAD_RESOLVED_COMMISSION_BOUNDED
        elif range_windows and all(x==FULL_FRICTION_RESOLVED for x in cost_states):
            confidence=FULL_FRICTION_RESOLVED
        else:
            confidence=FRICTION_UNRESOLVED

        spread75_ratios=[x["p75_spread_over_range"] for x in range_windows if x.get("p75_spread_over_range") is not None]
        spread95_ratios=[x["p95_spread_over_range"] for x in range_windows if x.get("p95_spread_over_range") is not None]
        eff75_ratios=[x["p75_effective_friction_over_range"] for x in range_windows if x.get("p75_effective_friction_over_range") is not None]
        eff95_ratios=[x["p95_effective_friction_over_range"] for x in range_windows if x.get("p95_effective_friction_over_range") is not None]
        central_eff=_med(eff75_ratios)
        metrics={
            **candidate,
            "planned_windows":len(summaries),"observed_two_sided_windows":len(observed),
            "two_sided_window_coverage":len(observed)/len(summaries) if summaries else 0,
            "quote_state_count":qcount,"window_summaries":summaries,
            "pooled_state_spread_median":_med(pooled_spreads),
            "pooled_state_p75_spread":_q(pooled_spreads,.75),
            "pooled_state_p90_spread":_q(pooled_spreads,.90),
            "pooled_state_p95_spread":_q(pooled_spreads,.95),
            "median_mid":_med(pooled_mids),
            "median_m5_range":_med([x["median_m5_range"] for x in range_windows]),
            "median_spread_over_mid":(_med(pooled_spreads)/_med(pooled_mids)) if pooled_spreads and pooled_mids and _med(pooled_mids) else None,
            "median_window_p75_spread_over_range":_med(spread75_ratios),
            "p75_window_p95_spread_over_range":_q(spread95_ratios,.75),
            "max_window_p95_spread_over_range":max(spread95_ratios) if spread95_ratios else None,
            "median_window_p75_effective_friction_over_range":central_eff,
            "p75_window_p95_effective_friction_over_range":_q(eff95_ratios,.75),
            "max_window_p95_effective_friction_over_range":max(eff95_ratios) if eff95_ratios else None,
            "movement_to_window_balanced_p75_effective_friction":1.0/central_eff if central_eff and central_eff>0 else None,
            "cost_confidence_state":confidence,
            "tail_aggregation":"TRUE_INTRA_WINDOW_QUANTILES_PLUS_EQUAL_WINDOW_BALANCED_RATIOS",
        }
        metrics["friction_state"]=qualify_friction(metrics,self.protocol["friction_screen"]["qualification"])
        return metrics

    def _stage_rows(self,account_id,candidate,full_symbol):
        interval=self.plan["stage_a_interval"];frm=_ms(_utc(interval["start_utc"]));to=_ms(_utc(interval["end_utc"]))
        page_size=int(self.plan["capture_law"]["trendbar_pagination"]["page_count"])
        page_limit=int(self.plan["capture_law"]["max_stage_a_pages_per_symbol"])
        page_to=to;rows={};pages=0;raw_total=0;full_pages=0;short_pages=0;empty_pages=0;duplicates=0
        lower_boundary_overfetch=0
        completion=None;schema_exposes=None;previous_was_full=False;page_log=[]
        while page_to>=frm:
            if pages>=page_limit:
                raise ImplementationInvalid("Stage-A page limit exceeded before interval exhaustion")
            request_to=page_to
            response=self._send(ProtoOAGetTrendbarsReq(
                ctidTraderAccountId=account_id,symbolId=candidate["symbol_id"],period=ProtoOATrendbarPeriod.Value("M5"),
                fromTimestamp=frm,toTimestamp=request_to,count=page_size,
            ),historical=True)
            pages+=1
            raw=list(response.trendbar)
            bars=[_plain(x) for x in raw]
            count=len(bars);raw_total+=count
            supports,has_more=_trendbar_has_more(response)
            if schema_exposes is None:
                schema_exposes=supports
            elif schema_exposes!=supports:
                raise ImplementationInvalid("ProtoOAGetTrendbarsRes hasMore schema exposure changed mid-capture")
            if count>page_size:
                raise ImplementationInvalid("Stage-A response exceeded requested page count")

            if not bars:
                empty_pages+=1
                if supports and has_more:
                    raise ImplementationInvalid("Stage-A empty page cannot advertise hasMore=true")
                if pages==1:
                    completion="EMPTY_INTERVAL"
                elif previous_was_full:
                    completion="EMPTY_FINAL_PAGE_AFTER_FULL_PAGE"
                else:
                    raise ImplementationInvalid("unexpected empty Stage-A page before defensible exhaustion")
                page_log.append({"page":pages,"request_to_ms":request_to,"raw_bars":0,"has_more_exposed":supports,"has_more":has_more})
                break

            try:
                raw_times=[int(x["utcTimestampInMinutes"])*60000 for x in bars]
            except (TypeError,ValueError,KeyError) as exc:
                raise ImplementationInvalid("malformed Stage-A trendbar timestamp") from exc
            if any(t>request_to for t in raw_times):
                raise ImplementationInvalid("Stage-A response bar above requested page upper boundary")
            page_lower_overfetch=sum(1 for t in raw_times if t<frm)
            lower_boundary_overfetch+=page_lower_overfetch
            page_seen={}
            for item,t in zip(bars,raw_times):
                if t in page_seen:
                    if page_seen[t]!=item:
                        raise ImplementationInvalid("conflicting Stage-A duplicate inside response page")
                    duplicates+=1
                else:
                    page_seen[t]=item
            oldest=min(raw_times);newest=max(raw_times)
            normalized=normalize_m5(
                bars,digits=int(full_symbol.get("digits",5)),start_utc=interval["start_utc"],
                end_utc=interval["end_utc"],protected_utc=PROTECTED_UTC,
            )
            for row in normalized:
                key=row["time_utc"]
                if key in rows:
                    if rows[key]!=row:
                        raise ImplementationInvalid("conflicting Stage-A duplicate")
                    duplicates+=1
                else:
                    rows[key]=row

            is_full=count==page_size
            full_pages+=int(is_full);short_pages+=int(not is_full)
            page_log.append({
                "page":pages,"request_to_ms":request_to,"raw_bars":count,
                "oldest_bar_open_ms":oldest,"newest_bar_open_ms":newest,
                "below_requested_start_bars":page_lower_overfetch,
                "has_more_exposed":supports,"has_more":has_more,
            })

            if oldest<=frm:
                completion="FROM_BOUNDARY_REACHED"
                break
            if supports:
                if has_more is False:
                    completion="HAS_MORE_FALSE"
                    break
                if has_more is True and not is_full:
                    raise ImplementationInvalid("Stage-A hasMore=true on a short page")
            elif not is_full:
                completion="SHORT_PAGE_INTERVAL_EXHAUSTED"
                break

            nxt=oldest-1
            if nxt>=request_to or nxt<frm-1:
                raise ImplementationInvalid("Stage-A pagination did not make strict backward progress")
            page_to=nxt
            previous_was_full=is_full

        if completion not in STAGE_COMPLETION_REASONS:
            raise ImplementationInvalid("Stage-A interval did not reach an explicit completion state")
        ordered=[rows[k] for k in sorted(rows)]
        meta={
            "requested_start_utc":interval["start_utc"],"requested_end_utc":interval["end_utc"],
            "page_size":page_size,"page_limit":page_limit,"pages":pages,
            "raw_bars_returned":raw_total,"normalized_unique_completed_bars":len(ordered),
            "first_timestamp_utc":ordered[0]["time_utc"] if ordered else None,
            "last_timestamp_utc":ordered[-1]["time_utc"] if ordered else None,
            "completion_reason":completion,"request_interval_exhausted":True,
            "response_schema_exposed_has_more":bool(schema_exposes),
            "full_pages":full_pages,"short_pages":short_pages,"empty_pages":empty_pages,
            "lower_boundary_overfetch_bars":lower_boundary_overfetch,
            "lower_boundary_overfetch_policy":"CLIP_BEFORE_FROZEN_START_AND_COUNT_AS_BOUNDARY_EXHAUSTION_EVIDENCE",
            "identical_duplicate_count":duplicates,"conflicts":0,
            "page_log":page_log,
        }
        return ordered,meta

    def _write_rows(self,candidate,rows,pagination):
        d=self.bundle/"stage_a_m5";d.mkdir(parents=True,exist_ok=True);path=d/(candidate["broker_symbol"].replace("/","_")+"_M5.csv")
        with path.open("w",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=RAW_HEADER,lineterminator="\n");writer.writeheader()
            writer.writerows([{k:x[k] for k in RAW_HEADER} for x in rows])
        inspected=_inspect_stage_csv(path,self.plan)
        if pagination.get("request_interval_exhausted") is not True or pagination.get("completion_reason") not in STAGE_COMPLETION_REASONS:
            raise ImplementationInvalid("Stage-A CSV cannot be written from incomplete pagination")
        if inspected["row_count"]!=pagination.get("normalized_unique_completed_bars"):
            raise ImplementationInvalid("Stage-A CSV row count disagrees with pagination evidence")
        return {"broker_symbol":candidate["broker_symbol"],"symbol_id":candidate["symbol_id"],"family":candidate["family"],**inspected,"pagination":pagination,"file":path.relative_to(self.bundle).as_posix()}

    def _conversion_summary(self):
        chains=[]
        for (first,last),symbols in sorted(self._conversion_chain_cache.items()):
            chains.append({
                "first_asset_id":first,"last_asset_id":last,
                "first_asset":self._assets.get(str(first)),"last_asset":self._assets.get(str(last)),
                "symbols":symbols,
            })
        window_rates=[self._conversion_rate_cache[k] for k in sorted(self._conversion_rate_cache)]
        return {
            "schema":"mxm.greenfield.v2.ultra-fast-historical-conversion-summary.v1",
            "authority":"CTRADER_PROTO_OA_SYMBOLS_FOR_CONVERSION",
            "chain_count":len(chains),"window_rate_count":len(window_rates),
            "chains":chains,"window_rates":window_rates,
            "raw_conversion_ticks_transferred":False,
            "current_or_future_rate_substitution":False,
        }

    def _checkpoint_binding(self):
        friction_spec={
            "latest_4_week_diagnostic":self.plan["latest_4_week_diagnostic"],
            "friction_screen":self.protocol["friction_screen"],
            "selection_law":self.protocol["selection_law"],
        }
        return {
            "plan_sha256":EXPECTED_PLAN_SHA,
            "protocol_authority":PROTOCOL_REL,
            "protocol_sha256":_json_sha(self.protocol),
            "account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],
            "source_environment":self.plan["source_environment"],
            "shortlist_sha256":_json_sha(self.plan["shortlist"]),
            "friction_spec_sha256":_json_sha(friction_spec),
            "conversion_authority":"CTRADER_PROTO_OA_SYMBOLS_FOR_CONVERSION_SAME_WINDOW_HISTORICAL",
        }

    def _persist_friction_checkpoint(self,friction,conversion_summary,initial,alternates):
        if self.checkpoint_dir.exists():
            shutil.rmtree(self.checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True)
        friction_doc={
            "schema":"mxm.greenfield.v2.ultra-fast-friction-summary.v3",
            "raw_ticks_transferred":False,"raw_conversion_ticks_transferred":False,
            "source_weeks":"2026-W34..2026-W37",
            "implementation_failure_is_market_failure":False,
            "tail_semantics":"TRUE_INTRA_WINDOW_QUANTILES_WINDOW_BALANCED_QUALIFICATION",
            "results":friction,
        }
        selection_doc={
            "schema":"mxm.greenfield.v2.ultra-fast-stage-a-initial-selection.v4",
            "initial_selected":[x["broker_symbol"] for x in initial],
            "alternates":alternates,
            "alpha_outcomes_used":False,"user_manual_replacements":False,
            "family_quotas_role":"FIRST_WAVE_INFORMATION_DIVERSITY_ONLY",
        }
        manifest={
            "schema":CHECKPOINT_SCHEMA,
            "status":"FRICTION_CONVERSION_SELECTION_CHECKPOINT_COMPLETE",
            "binding":self._checkpoint_binding(),
            "friction_shortlist_count":len(friction),
            "initial_selected_count":len(initial),
            "raw_ticks_transferred":False,"raw_conversion_ticks_transferred":False,
            "credentials_persisted":False,"orders_placed":False,"account_mutation":False,
            "economic_outcomes_opened":0,"v2_attempts_consumed":0,
        }
        atomic_write_json(self.checkpoint_dir/"friction_summary.json",friction_doc)
        atomic_write_json(self.checkpoint_dir/"historical_conversion_summary.json",conversion_summary)
        atomic_write_json(self.checkpoint_dir/"selection_initial.json",selection_doc)
        atomic_write_json(self.checkpoint_dir/"checkpoint_manifest.json",manifest)
        _write_checksums(self.checkpoint_dir)
        _verify_checksums(self.checkpoint_dir)
        scan_bundle_for_secrets(self.checkpoint_dir,[self.client_secret,self.access_token])
        self.progress(f"[CHECKPOINT SAVED] {self.checkpoint_dir}")

    def _load_friction_checkpoint(self):
        if not self.checkpoint_dir.exists():
            return None
        try:
            _verify_checksums(self.checkpoint_dir)
            manifest=json.loads((self.checkpoint_dir/"checkpoint_manifest.json").read_text(encoding="utf-8"))
            friction_doc=json.loads((self.checkpoint_dir/"friction_summary.json").read_text(encoding="utf-8"))
            conversion=json.loads((self.checkpoint_dir/"historical_conversion_summary.json").read_text(encoding="utf-8"))
            selection=json.loads((self.checkpoint_dir/"selection_initial.json").read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError,ValueError,KeyError) as exc:
            raise CheckpointInvalid(f"checkpoint parse/checksum failure: {redact_text(str(exc))}") from exc
        if manifest.get("schema")!=CHECKPOINT_SCHEMA or manifest.get("status")!="FRICTION_CONVERSION_SELECTION_CHECKPOINT_COMPLETE":
            raise CheckpointInvalid("checkpoint schema/status mismatch")
        if manifest.get("binding")!=self._checkpoint_binding():
            raise CheckpointInvalid("checkpoint authority binding mismatch")
        if manifest.get("raw_ticks_transferred") is not False or manifest.get("raw_conversion_ticks_transferred") is not False or manifest.get("credentials_persisted") is not False:
            raise CheckpointInvalid("checkpoint safety binding invalid")
        if manifest.get("economic_outcomes_opened")!=0 or manifest.get("v2_attempts_consumed")!=0:
            raise CheckpointInvalid("checkpoint is economically contaminated")
        friction=list(friction_doc.get("results") or [])
        if len(friction)!=32 or len({x.get("broker_symbol") for x in friction})!=32:
            raise CheckpointInvalid("checkpoint friction shortlist incomplete")
        expected={x["broker_symbol"] for x in self.plan["shortlist"]}
        if {x.get("broker_symbol") for x in friction}!=expected:
            raise CheckpointInvalid("checkpoint friction identities mismatch")
        names=list(selection.get("initial_selected") or [])
        if len(names)>self.plan["max_stage_a_markets"] or len(names)!=len(set(names)):
            raise CheckpointInvalid("checkpoint initial selection invalid")
        index={x["broker_symbol"]:x for x in friction}
        try:
            initial=[index[x] for x in names]
        except KeyError as exc:
            raise CheckpointInvalid("checkpoint selected symbol absent from friction evidence") from exc
        if any(not _eligible_for_selection(x) for x in initial):
            raise CheckpointInvalid("checkpoint selected market no longer eligible under frozen law")
        if conversion.get("raw_conversion_ticks_transferred") is not False or conversion.get("current_or_future_rate_substitution") is not False:
            raise CheckpointInvalid("checkpoint conversion authority invalid")
        scan_bundle_for_secrets(self.checkpoint_dir,[self.client_secret,self.access_token])
        self.progress(f"[CHECKPOINT REUSED] {self.checkpoint_dir}")
        return friction,conversion,initial,selection.get("alternates") or {}

    def _workflow(self):
        self.progress("[1/5] Pepperstone LIVE read-only account binding")
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret));self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved=self.config.get("ctid_trader_account_id")
        try:
            account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get("account_selector")
            if saved is not None or not callable(selector):
                raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account["ctidTraderAccountId"]);self._account=aid
        if account_fingerprint(aid)!=self.plan["account_fingerprint_sha256"]:
            raise MappingError("account fingerprint mismatch")
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if "pepperstone" not in str(trader.get("brokerName","")).lower() and "pepperstone" not in str(account.get("brokerTitleShort","")).lower():
            raise MappingError("not Pepperstone")

        self._assets={str(x.get("assetId")):x.get("name") for x in [_plain(y) for y in self._send(ProtoOAAssetListReq(ctidTraderAccountId=aid)).asset]}
        self._asset_ids={str(name).upper():int(asset_id) for asset_id,name in self._assets.items() if name}
        self._light={int(x["symbolId"]):x for x in [_plain(y) for y in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]}
        q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.extend([x["symbol_id"] for x in self.plan["shortlist"]])
        full={int(x.symbolId):_plain(x) for x in self._send(q).symbol}
        for candidate in self.plan["shortlist"]:
            li=self._light.get(candidate["symbol_id"]);fu=full.get(candidate["symbol_id"])
            if not li or not fu or li.get("symbolName")!=candidate["broker_symbol"] or li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0:
                raise MappingError(f"shortlist mapping/tradability mismatch {candidate['broker_symbol']}")

        checkpoint=None
        try:
            checkpoint=self._load_friction_checkpoint()
        except CheckpointInvalid as exc:
            self.progress(f"[CHECKPOINT INVALID -> RECAPTURE FRICTION] {redact_text(str(exc))}")
            shutil.rmtree(self.checkpoint_dir,ignore_errors=True)

        if checkpoint is None:
            self.progress("[2/5] 4-week true-tail friction + same-window broker conversion chains")
            friction=[]
            for i,candidate in enumerate(self.plan["shortlist"],1):
                metrics=self._friction(aid,candidate,full[candidate["symbol_id"]],self._light[candidate["symbol_id"]])
                friction.append(metrics)
                self.progress(f"[FRICTION {i}/32] {candidate['broker_symbol']} {metrics['friction_state']} cost={metrics['cost_confidence_state']} coverage={metrics['two_sided_window_coverage']:.0%}")
            initial,alternates=select_stage_a(friction,self.protocol["selection_law"])
            conversion_summary=self._conversion_summary()
            self._persist_friction_checkpoint(friction,conversion_summary,initial,alternates)
        else:
            friction,conversion_summary,initial,alternates=checkpoint
            self.progress("[2/5] friction/conversion reused from authority-bound local checkpoint")

        self.progress(f"[3/5] selector admitted {len(initial)}/12 initial markets")
        ranked=sorted([x for x in friction if _eligible_for_selection(x)],key=_rank)
        chosen=[];series=[];replacements=[];used=set();counts=defaultdict(int);minrows=int(self.plan["capture_law"]["min_stage_a_m5_rows"])
        target_counts=defaultdict(int)
        for x in initial:
            target_counts[x["family"]]+=1

        def try_capture(candidate):
            if candidate["broker_symbol"] in used or not _eligible_for_selection(candidate):
                return False
            rows,pagination=self._stage_rows(aid,candidate,full[candidate["symbol_id"]])
            if pagination.get("request_interval_exhausted") is not True:
                raise ImplementationInvalid("Stage-A minimum-row gate reached before interval completeness")
            if len(rows)<minrows:
                used.add(candidate["broker_symbol"])
                replacements.append({
                    "broker_symbol":candidate["broker_symbol"],"family":candidate["family"],
                    "state":"STAGE_A_DATA_INSUFFICIENT","row_count":len(rows),"minimum_required":minrows,
                    "pagination":pagination,"alpha_consulted":False
                })
                return False
            series.append(self._write_rows(candidate,rows,pagination));chosen.append(candidate);used.add(candidate["broker_symbol"]);counts[candidate["family"]]+=1
            self.progress(f"[STAGE-A {len(chosen)}/12] {candidate['broker_symbol']} rows={len(rows):,} pages={pagination['pages']} completion={pagination['completion_reason']}")
            return True

        for candidate in initial:
            try_capture(candidate)
        for candidate in ranked:
            if len(chosen)>=12:
                break
            if counts[candidate["family"]]>=target_counts[candidate["family"]]:
                continue
            try_capture(candidate)
        if len(chosen)<12:
            for candidate in ranked:
                if len(chosen)>=12:
                    break
                if candidate["friction_state"]!="FRICTION_PASS" or counts[candidate["family"]]>=4:
                    continue
                try_capture(candidate)

        self.progress("[4/5] compact evidence + conversion/tail postconditions")
        conversion_summary=self._conversion_summary()
        friction_doc={
            "schema":"mxm.greenfield.v2.ultra-fast-friction-summary.v3","raw_ticks_transferred":False,
            "raw_conversion_ticks_transferred":False,"source_weeks":"2026-W34..2026-W37",
            "implementation_failure_is_market_failure":False,
            "tail_semantics":"TRUE_INTRA_WINDOW_QUANTILES_WINDOW_BALANCED_QUALIFICATION",
            "results":friction,
        }
        selection_doc={
            "schema":"mxm.greenfield.v2.ultra-fast-stage-a-selection.v4",
            "initial_selected":[x["broker_symbol"] for x in initial],"final_selected":[x["broker_symbol"] for x in chosen],
            "alternates":alternates,"data_availability_replacements":replacements,
            "alpha_outcomes_used":False,"user_manual_replacements":False,
            "family_quotas_role":"FIRST_WAVE_INFORMATION_DIVERSITY_ONLY",
        }
        status="COMPACT_FRICTION_AND_STAGE_A_DEVELOPMENT_CAPTURE_COMPLETE" if chosen else "FRICTION_QUALIFICATION_COMPLETE_NO_STAGE_A_MARKETS"
        manifest={
            "schema":"mxm.greenfield.v2.ultra-fast-stage-a-capture-bundle.v4","status":status,
            "captured_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,
            "source_broker_universe_zip_sha256":self.plan["source_broker_universe_zip_sha256"],
            "account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],"source_environment":self.plan["source_environment"],
            "friction_shortlist_count":len(friction),"stage_a_selected_count":len(chosen),
            "stage_a_interval":self.plan["stage_a_interval"],"latest_4_week_diagnostic":self.plan["latest_4_week_diagnostic"],
            "series":series,"historical_requests":self._requests,
            "conversion_chain_count":conversion_summary["chain_count"],"conversion_window_rate_count":conversion_summary["window_rate_count"],
            "friction_checkpoint_reused":checkpoint is not None,"friction_checkpoint_authority":str(self.checkpoint_dir),
            "raw_ticks_transferred":False,"raw_conversion_ticks_transferred":False,
            "orders_placed":False,"account_mutation":False,"protected_evidence_opened":False,
            "economic_outcomes_opened":0,"v2_attempts_consumed":0,"implementation_invalid_conditions":0,
        }
        atomic_write_json(self.bundle/"friction_summary.json",friction_doc)
        atomic_write_json(self.bundle/"historical_conversion_summary.json",conversion_summary)
        atomic_write_json(self.bundle/"selection.json",selection_doc)
        atomic_write_json(self.bundle/"capture_manifest.json",manifest)
        validate_capture_postconditions(
            plan=self.plan,friction_results=friction,selection=selection_doc,series=series,bundle=self.bundle,
            manifest=manifest,conversion_summary=conversion_summary,verify_checksums=False,
        )
        _write_checksums(self.bundle)
        validate_capture_postconditions(
            plan=self.plan,friction_results=friction,selection=selection_doc,series=series,bundle=self.bundle,
            manifest=manifest,conversion_summary=conversion_summary,verify_checksums=True,
        )
        scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])

        self.progress("[5/5] deterministic phone-friendly ZIP")
        with zipfile.ZipFile(self.zip_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for path in sorted(x for x in self.bundle.rglob("*") if x.is_file()):
                info=zipfile.ZipInfo(path.relative_to(self.bundle).as_posix(),(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
                z.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        self.progress(f"[DONE] {self.zip_path.name} bytes={self.zip_path.stat().st_size:,} SHA256={_sha(self.zip_path)}")

    def run(self):
        if self.bundle.exists():
            shutil.rmtree(self.bundle)
        self.bundle.mkdir(parents=True);self.zip_path.unlink(missing_ok=True)
        try:
            self.transport.connect();self._workflow()
        except (TypeError,AssertionError,KeyError,ValueError) as exc:
            raise ImplementationInvalid(f"IMPLEMENTATION_INVALID: {redact_text(str(exc))}") from exc
        finally:
            self.transport.close()
        return self.zip_path
