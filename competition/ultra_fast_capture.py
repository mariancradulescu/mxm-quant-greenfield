"""Compact read-only friction qualification + 13-week M5 Stage-A capture V2.

Runtime-integrity law:
- one shared canonical M5 normalizer from competition.frontier_data_capture;
- software/contract failures abort the capture;
- only valid sparse Stage-A data may trigger deterministic market replacement;
- FRICTION_FAIL means valid friction evidence failed frozen economic thresholds.
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
    ProtoOASymbolsListReq,
    ProtoOATraderReq,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport

PLAN_REL="data/COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V2.json"
PROTOCOL_REL="data/COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V2.json"
EXPECTED_PLAN_SHA="5a636910618d87466f3b02f2edcd43898f18040e3fcfe80c013a7b67b921f9fd"
OUTPUT_FILENAME="MXM_COMPETITION_ULTRA_FAST_STAGE_A_V2.zip"
TOOL_VERSION="MXM_COMPETITION_ULTRA_FAST_ANDROID_STDLIB_V2_RUNTIME_FRICTION_INTEGRITY"
QUOTE_TYPES={"BID":1,"ASK":2}
RAW_HEADER=("time_utc","open","high","low","close","tick_volume")
MIN_INTERVAL=1/4.7
PROTECTED_UTC="2026-09-17T12:02:58Z"
ELIGIBLE_COST_STATES={FULL_FRICTION_RESOLVED,SPREAD_RESOLVED_COMMISSION_BOUNDED}
VALID_FRICTION_STATES={"FRICTION_PASS","FRICTION_WATCH","FRICTION_FAIL",FRICTION_UNRESOLVED}


class ImplementationInvalid(CaptureContractError):
    """Deterministic implementation/schema/contract failure. Never market evidence."""


class StageADataInsufficient(Exception):
    """Valid broker response but too little bounded Stage-A data for this market."""


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


def margin_pct_eur200(value):
    return float(Decimal(str(value))/Decimal("2"))


def validate_plan(plan,protocol):
    if plan.get("schema")!="mxm.greenfield.v2.ultra-fast-competition-capture-plan.v2":
        raise ImplementationInvalid("invalid ultra-fast V2 plan schema")
    if plan.get("status")!="FROZEN_PRE_CAPTURE_PRE_OUTCOME_RUNTIME_INTEGRITY_CORRECTED":
        raise ImplementationInvalid("ultra-fast V2 plan not frozen")
    if plan.get("plan_sha256")!=EXPECTED_PLAN_SHA or _canon(plan)!=EXPECTED_PLAN_SHA:
        raise ImplementationInvalid("ultra-fast V2 plan hash mismatch")
    if protocol.get("schema")!="mxm.greenfield.v2.ultra-fast-data-minimal-discovery-protocol.v2":
        raise ImplementationInvalid("invalid ultra-fast V2 protocol schema")
    if protocol.get("status")!="FROZEN_PRE_FRICTION_PRE_STAGE_A_OUTCOME_RUNTIME_INTEGRITY_CORRECTED":
        raise ImplementationInvalid("ultra-fast V2 protocol not frozen")
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
    a=int(math.floor(p)); b=int(math.ceil(p))
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
            d=date.fromisoformat(ds); monday=d-timedelta(days=d.weekday())
            for w in profiles[profile]["weekend_windows_per_week"]:
                x=monday+timedelta(days=5 if w["weekday"]=="SATURDAY" else 6)
                out.append(_window(x.isoformat(),w["start"],w["end"],w["label"]))
        return sorted(out,key=lambda x:(x["from_ms"],x["label"]))
    raise ImplementationInvalid("unknown friction profile")


def qualify_friction(metrics,rules):
    confidence=metrics.get("cost_confidence_state")
    if confidence not in ELIGIBLE_COST_STATES:
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
            and (metrics.get("p75_spread_over_median_range") or math.inf)<=rule["max_p75_spread_over_median_m5_range"]
            and (metrics.get("p95_spread_over_median_range") or math.inf)<=rule["max_p95_spread_over_median_m5_range"]
            and (metrics.get("p75_effective_friction_over_median_range") or math.inf)<=rule["max_p75_effective_friction_over_median_range"]
            and (metrics.get("p95_effective_friction_over_median_range") or math.inf)<=rule["max_p95_effective_friction_over_median_range"]
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
    move=x.get("movement_to_effective_p75_friction") or 0
    return (
        tier,
        confidence,
        -float(move),
        float(x["accepted_min_margin_pct_eur200"]),
        -float(x["schedule_minutes_per_week"]),
        float(x.get("p95_effective_friction_over_median_range") or math.inf),
        x["broker_symbol"],
    )


def _eligible_for_selection(x):
    if x.get("cost_confidence_state") not in ELIGIBLE_COST_STATES:
        return False
    if x.get("friction_state")=="FRICTION_PASS":
        return True
    return x.get("friction_state")=="FRICTION_WATCH" and float(x.get("movement_to_effective_p75_friction") or 0)>=2.0


def select_stage_a(results,law):
    by=defaultdict(list)
    for x in results:
        if _eligible_for_selection(x):
            by[x["family"]].append(x)
    for xs in by.values():
        xs.sort(key=_rank)

    chosen=[]; variants=set(); counts=defaultdict(int)
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
    start=_utc(plan["stage_a_interval"]["start_utc"])
    end=_utc(plan["stage_a_interval"]["end_utc"])
    protected=_utc(PROTECTED_UTC)
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
    lines=[f"{_sha(p)}  {p.relative_to(bundle).as_posix()}" for p in files]
    path=Path(bundle)/"CHECKSUMS.sha256"
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return path


def _verify_checksums(bundle):
    bundle=Path(bundle); path=bundle/"CHECKSUMS.sha256"
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


def validate_capture_postconditions(*,plan,friction_results,selection,series,bundle,manifest,verify_checksums=False):
    expected=[x["broker_symbol"] for x in plan["shortlist"]]
    observed=[x.get("broker_symbol") for x in friction_results]
    if len(friction_results)!=32 or len(set(observed))!=32 or set(observed)!=set(expected):
        raise ImplementationInvalid("friction evidence does not account for exact 32-symbol shortlist")
    for x in friction_results:
        if x.get("friction_state") not in VALID_FRICTION_STATES:
            raise ImplementationInvalid("invalid friction evidence state")
        if x.get("cost_confidence_state") not in {
            FULL_FRICTION_RESOLVED,SPREAD_RESOLVED_COMMISSION_BOUNDED,
            COMMISSION_CONVERSION_UNRESOLVED,FRICTION_UNRESOLVED
        }:
            raise ImplementationInvalid("invalid cost-confidence state")
    if not any(x["friction_state"] in {"FRICTION_PASS","FRICTION_WATCH","FRICTION_FAIL"} for x in friction_results):
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
    if manifest.get("raw_ticks_transferred") is not False:
        raise ImplementationInvalid("raw tick transfer forbidden")
    if manifest.get("orders_placed") is not False or manifest.get("account_mutation") is not False:
        raise ImplementationInvalid("capture safety postcondition violated")
    if manifest.get("economic_outcomes_opened")!=0 or manifest.get("v2_attempts_consumed")!=0:
        raise ImplementationInvalid("capture unexpectedly consumed economics")

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
        self.plan=dict(plan);self.protocol=dict(protocol)
        self.client_id=client_id;self.client_secret=client_secret;self.access_token=access_token
        self.config=dict(config);self.root=Path(repo_root);self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.bundle=self.root/"competition_ultra_fast_output"/"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V2"
        self.zip_path=self.root/OUTPUT_FILENAME
        self._app=False;self._account=None;self._last=None;self._requests=0

    def _request(self,request,historical=False):
        require_read_only_request(type(request).__name__)
        if historical:
            now=time.monotonic(); wait=0 if self._last is None else MIN_INTERVAL-(now-self._last)
            if wait>0:
                time.sleep(wait)
            self._last=time.monotonic()
        response=self.transport.request(request,timeout=60)
        if type(response).__name__=="ProtoOAErrorRes":
            raise CaptureContractError(f"cTrader API error: {getattr(response,'errorCode','UNKNOWN')}")
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
        for n in range(retries):
            try:
                return self._request(request,historical)
            except (TypeError,AssertionError,KeyError,ValueError) as exc:
                raise ImplementationInvalid(f"{type(request).__name__} implementation/contract failure: {redact_text(str(exc))}") from exc
            except Exception as exc:
                last=exc
                if n+1==retries:
                    break
                time.sleep(min(8,2**n))
                try:
                    self.transport.close();self._restore()
                except Exception as reconnect:
                    last=reconnect
        raise CaptureContractError(f"{type(request).__name__} failed after valid retries: {redact_text(str(last))}")

    def _ticks(self,account_id,symbol_id,side,window):
        to=window["to_ms"];prev=None;out=[];pages=0
        limit=int(self.plan["capture_law"]["max_tick_pages_per_side_window"])
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
        return out

    def _sample_bars(self,account_id,symbol_id,digits,window):
        response=self._send(ProtoOAGetTrendbarsReq(
            ctidTraderAccountId=account_id,symbolId=symbol_id,
            period=ProtoOATrendbarPeriod.Value("M5"),
            fromTimestamp=window["from_ms"],toTimestamp=window["to_ms"],count=100,
        ),historical=True)
        return normalize_m5(
            [_plain(x) for x in response.trendbar],
            digits=digits,
            start_utc=window["start_utc"],
            end_utc=window["end_utc"],
            protected_utc=PROTECTED_UTC,
        )

    def _friction(self,account_id,candidate,full_symbol,light_symbol,assets):
        stats=[];qcount=0
        for window in friction_windows(self.protocol,candidate["friction_profile"]):
            bid=self._ticks(account_id,candidate["symbol_id"],"BID",window)
            ask=self._ticks(account_id,candidate["symbol_id"],"ASK",window)
            states=causal_merge_bid_ask(bid,ask)
            bars=self._sample_bars(account_id,candidate["symbol_id"],int(full_symbol.get("digits",5)),window)
            spreads=[x.spread for x in states if x.spread>=0]
            mids=[(x.bid+x.ask)/2 for x in states if x.bid+x.ask>0]
            ranges=[float(x["high"])-float(x["low"]) for x in bars if float(x["high"])>=float(x["low"])]
            qcount+=len(states)
            stats.append({
                "label":window["label"],
                "start_utc":window["start_utc"],
                "end_utc":window["end_utc"],
                "quote_states":len(states),
                "m5_bars":len(bars),
                "median_spread":_med(spreads),
                "median_mid":_med(mids),
                "median_m5_range":_med(ranges),
            })

        observed=[x for x in stats if x.get("median_spread") is not None]
        spreads=[x["median_spread"] for x in observed]
        mids=[x["median_mid"] for x in observed if x.get("median_mid")]
        ranges=[x["median_m5_range"] for x in stats if (x.get("median_m5_range") or 0)>0]
        med=_med(spreads);p75=_q(spreads,.75);p90=_q(spreads,.90);p95=_q(spreads,.95)
        mid=_med(mids);rng=_med(ranges)
        commission=type_aware_roundtrip_commission(
            full_symbol,light_symbol,assets,mid=mid,min_volume_cents=int(full_symbol.get("minVolume") or 0)
        )
        confidence=commission["cost_confidence_state"]
        rt=commission.get("roundtrip_commission_price_equivalent")
        effective_p75=(p75+rt) if p75 is not None and rt is not None else None
        effective_p95=(p95+rt) if p95 is not None and rt is not None else None

        metrics={
            **candidate,
            "planned_windows":len(stats),
            "observed_two_sided_windows":len(observed),
            "two_sided_window_coverage":len(observed)/len(stats) if stats else 0,
            "quote_state_count":qcount,
            "window_summaries":stats,
            "median_spread":med,"p75_spread":p75,"p90_spread":p90,"p95_spread":p95,
            "median_mid":mid,"median_m5_range":rng,
            "median_spread_over_mid":med/mid if med is not None and mid else None,
            "p95_spread_over_mid":p95/mid if p95 is not None and mid else None,
            "p75_spread_over_median_range":p75/rng if p75 is not None and rng else None,
            "p95_spread_over_median_range":p95/rng if p95 is not None and rng else None,
            "effective_p75_friction":effective_p75,
            "effective_p95_friction":effective_p95,
            "p75_effective_friction_over_median_range":effective_p75/rng if effective_p75 is not None and rng else None,
            "p95_effective_friction_over_median_range":effective_p95/rng if effective_p95 is not None and rng else None,
            "movement_to_p75_spread":rng/p75 if rng and p75 else None,
            "movement_to_p95_spread":rng/p95 if rng and p95 else None,
            "movement_to_effective_p75_friction":rng/effective_p75 if rng and effective_p75 else None,
            "cost_confidence_state":confidence,
            "commission":commission,
        }
        metrics["friction_state"]=qualify_friction(metrics,self.protocol["friction_screen"]["qualification"])
        return metrics

    def _stage_rows(self,account_id,candidate,full_symbol):
        interval=self.plan["stage_a_interval"]
        frm=_ms(_utc(interval["start_utc"]));to=_ms(_utc(interval["end_utc"]))
        page_to=to;rows={};pages=0
        while page_to>=frm:
            if pages>=int(self.plan["capture_law"]["max_stage_a_pages_per_symbol"]):
                raise ImplementationInvalid("Stage-A page limit exceeded")
            response=self._send(ProtoOAGetTrendbarsReq(
                ctidTraderAccountId=account_id,symbolId=candidate["symbol_id"],
                period=ProtoOATrendbarPeriod.Value("M5"),fromTimestamp=frm,toTimestamp=page_to,count=5000,
            ),historical=True)
            pages+=1
            bars=[_plain(x) for x in response.trendbar]
            for row in normalize_m5(
                bars,
                digits=int(full_symbol.get("digits",5)),
                start_utc=interval["start_utc"],
                end_utc=interval["end_utc"],
                protected_utc=PROTECTED_UTC,
            ):
                key=row["time_utc"]
                if key in rows and rows[key]!=row:
                    raise ImplementationInvalid("conflicting Stage-A duplicate")
                rows[key]=row
            if not response.hasMore:
                break
            if not bars:
                raise ImplementationInvalid("Stage-A hasMore with empty page")
            try:
                nxt=min(int(x["utcTimestampInMinutes"])*60000 for x in bars)-1
            except (TypeError,ValueError,KeyError) as exc:
                raise ImplementationInvalid("malformed Stage-A pagination timestamp") from exc
            if nxt>=page_to:
                raise ImplementationInvalid("Stage-A pagination did not advance")
            page_to=nxt
        return [rows[k] for k in sorted(rows)]

    def _write_rows(self,candidate,rows):
        d=self.bundle/"stage_a_m5";d.mkdir(parents=True,exist_ok=True)
        path=d/(candidate["broker_symbol"].replace("/","_")+"_M5.csv")
        with path.open("w",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=RAW_HEADER,lineterminator="\n")
            writer.writeheader()
            writer.writerows([{k:x[k] for k in RAW_HEADER} for x in rows])
        inspected=_inspect_stage_csv(path,self.plan)
        return {
            "broker_symbol":candidate["broker_symbol"],"symbol_id":candidate["symbol_id"],"family":candidate["family"],
            **inspected,"file":path.relative_to(self.bundle).as_posix(),
        }

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

        assets={str(x.get("assetId")):x.get("name") for x in [_plain(y) for y in self._send(ProtoOAAssetListReq(ctidTraderAccountId=aid)).asset]}
        light={int(x["symbolId"]):x for x in [_plain(y) for y in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol]}
        q=ProtoOASymbolByIdReq(ctidTraderAccountId=aid);q.symbolId.extend([x["symbol_id"] for x in self.plan["shortlist"]])
        full={int(x.symbolId):_plain(x) for x in self._send(q).symbol}
        for candidate in self.plan["shortlist"]:
            li=light.get(candidate["symbol_id"]);fu=full.get(candidate["symbol_id"])
            if not li or not fu or li.get("symbolName")!=candidate["broker_symbol"] or li.get("enabled") is False or int(fu.get("tradingMode",-1))!=0:
                raise MappingError(f"shortlist mapping/tradability mismatch {candidate['broker_symbol']}")

        self.progress("[2/5] 4-week stratified friction; raw ticks discarded locally")
        friction=[]
        for i,candidate in enumerate(self.plan["shortlist"],1):
            metrics=self._friction(aid,candidate,full[candidate["symbol_id"]],light[candidate["symbol_id"]],assets)
            friction.append(metrics)
            self.progress(
                f"[FRICTION {i}/32] {candidate['broker_symbol']} {metrics['friction_state']} "
                f"cost={metrics['cost_confidence_state']} coverage={metrics['two_sided_window_coverage']:.0%}"
            )

        initial,alternates=select_stage_a(friction,self.protocol["selection_law"])
        self.progress(f"[3/5] selector admitted {len(initial)}/12 initial markets")
        ranked=sorted([x for x in friction if _eligible_for_selection(x)],key=_rank)
        chosen=[];series=[];replacements=[];used=set();counts=defaultdict(int)
        minrows=int(self.plan["capture_law"]["min_stage_a_m5_rows"])
        target_counts=defaultdict(int)
        for x in initial:
            target_counts[x["family"]]+=1

        def try_capture(candidate):
            if candidate["broker_symbol"] in used:
                return False
            if not _eligible_for_selection(candidate):
                return False
            rows=self._stage_rows(aid,candidate,full[candidate["symbol_id"]])
            if len(rows)<minrows:
                used.add(candidate["broker_symbol"])
                replacements.append({
                    "broker_symbol":candidate["broker_symbol"],"family":candidate["family"],
                    "state":"STAGE_A_DATA_INSUFFICIENT","row_count":len(rows),
                    "minimum_required":minrows,"alpha_consulted":False,
                })
                return False
            series.append(self._write_rows(candidate,rows));chosen.append(candidate);used.add(candidate["broker_symbol"])
            counts[candidate["family"]]+=1
            self.progress(f"[STAGE-A {len(chosen)}/12] {candidate['broker_symbol']} rows={len(rows):,}")
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

        self.progress("[4/5] compact evidence + fail-closed postconditions")
        friction_doc={
            "schema":"mxm.greenfield.v2.ultra-fast-friction-summary.v2",
            "raw_ticks_transferred":False,"source_weeks":"2026-W34..2026-W37",
            "implementation_failure_is_market_failure":False,
            "results":friction,
        }
        selection_doc={
            "schema":"mxm.greenfield.v2.ultra-fast-stage-a-selection.v2",
            "initial_selected":[x["broker_symbol"] for x in initial],
            "final_selected":[x["broker_symbol"] for x in chosen],
            "alternates":alternates,"data_availability_replacements":replacements,
            "alpha_outcomes_used":False,"user_manual_replacements":False,
            "family_quotas_role":"FIRST_WAVE_INFORMATION_DIVERSITY_ONLY",
        }
        status="COMPACT_FRICTION_AND_STAGE_A_DEVELOPMENT_CAPTURE_COMPLETE" if chosen else "FRICTION_QUALIFICATION_COMPLETE_NO_STAGE_A_MARKETS"
        manifest={
            "schema":"mxm.greenfield.v2.ultra-fast-stage-a-capture-bundle.v2",
            "status":status,
            "captured_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "tool_version":TOOL_VERSION,"plan_sha256":EXPECTED_PLAN_SHA,
            "source_broker_universe_zip_sha256":self.plan["source_broker_universe_zip_sha256"],
            "account_fingerprint_sha256":self.plan["account_fingerprint_sha256"],
            "source_environment":self.plan["source_environment"],
            "friction_shortlist_count":len(friction),"stage_a_selected_count":len(chosen),
            "stage_a_interval":self.plan["stage_a_interval"],"latest_4_week_diagnostic":self.plan["latest_4_week_diagnostic"],
            "series":series,"historical_requests":self._requests,
            "raw_ticks_transferred":False,"orders_placed":False,"account_mutation":False,
            "protected_evidence_opened":False,"economic_outcomes_opened":0,"v2_attempts_consumed":0,
            "implementation_invalid_conditions":0,
        }
        atomic_write_json(self.bundle/"friction_summary.json",friction_doc)
        atomic_write_json(self.bundle/"selection.json",selection_doc)
        atomic_write_json(self.bundle/"capture_manifest.json",manifest)
        validate_capture_postconditions(
            plan=self.plan,friction_results=friction,selection=selection_doc,series=series,
            bundle=self.bundle,manifest=manifest,verify_checksums=False,
        )
        _write_checksums(self.bundle)
        validate_capture_postconditions(
            plan=self.plan,friction_results=friction,selection=selection_doc,series=series,
            bundle=self.bundle,manifest=manifest,verify_checksums=True,
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
        self.bundle.mkdir(parents=True)
        self.zip_path.unlink(missing_ok=True)
        try:
            self.transport.connect();self._workflow()
        except (TypeError,AssertionError,KeyError,ValueError) as exc:
            raise ImplementationInvalid(f"IMPLEMENTATION_INVALID: {redact_text(str(exc))}") from exc
        finally:
            self.transport.close()
        return self.zip_path
