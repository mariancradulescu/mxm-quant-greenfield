"""Non-economic structural screen for SESSION_GAP_REVERSION Wave 01.

This module measures causal gap-shock density and 60-minute mean-reversion structure.
It deliberately excludes transaction costs, notional PnL, shared-account realization,
candidate identity creation, and any mechanism-family closure decision.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

VERSION="MXM_SESSION_GAP_STRUCTURAL_SCREEN_V1"
CANONICAL_ZIP_SHA256="83df470fb760ec15ae05e5843686e8e4a4dcde84badcd0d4d27740042964afb0"
PREFIX="MXM_C031_STRUCTURAL_EXTENSION_WAVE_01_M5_8W_CAPTURE_CANONICAL_V1/"
M5=timedelta(minutes=5)

class StructuralScreenIntegrityError(ValueError):
    pass

def _sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def _dt(value:str)->datetime:
    return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(timezone.utc)

def open_canonical_capture(path:str|Path)->tuple[zipfile.ZipFile,dict[str,Any]]:
    path=Path(path)
    raw=path.read_bytes()
    if _sha(raw)!=CANONICAL_ZIP_SHA256:
        raise StructuralScreenIntegrityError("canonical capture ZIP hash mismatch")
    z=zipfile.ZipFile(path)
    bad=z.testzip()
    if bad:
        raise StructuralScreenIntegrityError(f"canonical capture CRC failure: {bad}")
    manifest=json.loads(z.read(PREFIX+"canonical_manifest.json"))
    if manifest.get("status")!="VALID_CANONICALIZED_FROM_EXACT_DUPLICATE_WINDOW_OVERLAP":
        raise StructuralScreenIntegrityError("canonical capture status not accepted")
    declared={}
    for line in z.read(PREFIX+"CHECKSUMS.sha256").decode().splitlines():
        if line.strip():
            h,rel=line.split("  ",1); declared[rel]=h
    observed={}
    for name in z.namelist():
        if name.startswith(PREFIX) and not name.endswith("/") and not name.endswith("CHECKSUMS.sha256"):
            observed[name[len(PREFIX):]]=_sha(z.read(name))
    if declared!=observed:
        raise StructuralScreenIntegrityError("canonical internal checksum mismatch")
    return z,manifest

def load_rows(z:zipfile.ZipFile, rel:str)->list[dict[str,Any]]:
    rows=[]
    for row in csv.DictReader(io.StringIO(z.read(PREFIX+rel).decode())):
        rows.append({
            "t":_dt(row["time_utc"]),
            "o":float(row["open"]),"h":float(row["high"]),"l":float(row["low"]),"c":float(row["close"]),
            "v":float(row["tick_volume"]),
        })
    if not rows:
        raise StructuralScreenIntegrityError(f"{rel}: no rows")
    if any(rows[i]["t"]>=rows[i+1]["t"] for i in range(len(rows)-1)):
        raise StructuralScreenIntegrityError(f"{rel}: chronology not strictly increasing")
    if any(min(r["o"],r["h"],r["l"],r["c"])<=0 for r in rows):
        raise StructuralScreenIntegrityError(f"{rel}: non-positive OHLC")
    return rows

def screen_symbol(rows:list[dict[str,Any]],*,minimum_gap_minutes:int=30,scale_window:int=288,
                  minimum_scale_observations:int=144,shock_scale_multiple:float=3.0,
                  scheduled_horizon_minutes:int=60)->dict[str,Any]:
    scale=deque(maxlen=scale_window)
    pending=None
    active=None
    gap_events=scale_ready=shock_events=admitted=filled=settled=0
    samples=[]
    active_weeks=set()
    for i,row in enumerate(rows):
        if active is not None and row["t"]>=active["target"]:
            directional=(1.0 if active["direction"]=="LONG" else -1.0)*(row["o"]/active["entry_price"]-1.0)
            samples.append({
                "signal_time_utc":active["signal_time"].isoformat().replace("+00:00","Z"),
                "entry_time_utc":active["entry_t"].isoformat().replace("+00:00","Z"),
                "exit_time_utc":row["t"].isoformat().replace("+00:00","Z"),
                "direction":active["direction"],
                "gap_return":active["gap_return"],
                "shock_to_scale":active["shock_to_scale"],
                "directional_60m_return":directional,
                "reverted":directional>0,
            })
            iso=active["entry_t"].isocalendar()
            active_weeks.add(f"{iso.year}-W{iso.week:02d}")
            settled+=1
            active=None
        if pending is not None and row["t"]>=pending["decision_time"] and active is None:
            active={
                **pending,
                "entry_t":row["t"],
                "entry_price":row["o"],
                "target":row["t"]+timedelta(minutes=scheduled_horizon_minutes),
            }
            pending=None
            filled+=1
        if i==0:
            continue
        prev=rows[i-1]
        gap_minutes=(row["t"]-prev["t"]).total_seconds()/60.0
        prior=(statistics.median(scale) if len(scale)>=minimum_scale_observations else None)
        if gap_minutes>=minimum_gap_minutes:
            gap_events+=1
            if prior is not None and math.isfinite(prior) and prior>0:
                scale_ready+=1
                gap_ret=row["o"]/prev["c"]-1.0
                if abs(gap_ret)>shock_scale_multiple*prior:
                    shock_events+=1
                    if active is None and pending is None and gap_ret!=0:
                        pending={
                            "decision_time":row["t"]+M5,
                            "direction":"SHORT" if gap_ret>0 else "LONG",
                            "signal_time":row["t"],
                            "gap_return":gap_ret,
                            "shock_to_scale":abs(gap_ret)/prior,
                        }
                        admitted+=1
        if row["t"]-prev["t"]==M5:
            r=abs(row["c"]/prev["c"]-1.0)
            if math.isfinite(r):
                scale.append(r)
    vals=[x["directional_60m_return"] for x in samples]
    gaps=[abs(x["gap_return"]) for x in samples]
    shocks=[x["shock_to_scale"] for x in samples]
    weeks=sorted(active_weeks)
    return {
        "row_count":len(rows),
        "first_timestamp_utc":rows[0]["t"].isoformat().replace("+00:00","Z"),
        "last_timestamp_utc":rows[-1]["t"].isoformat().replace("+00:00","Z"),
        "observed_gap_events":gap_events,
        "gap_events_with_scale_ready":scale_ready,
        "shock_scale_hurdle_passes":shock_events,
        "admitted_structural_signals":admitted,
        "filled_entries_for_structural_measurement":filled,
        "settled_structural_samples":settled,
        "right_censored_pending":1 if pending is not None else 0,
        "right_censored_active":1 if active is not None else 0,
        "active_signal_weeks":len(weeks),
        "active_week_keys":weeks,
        "structural_reversion":{
            "positive_reversion_fraction":(sum(v>0 for v in vals)/len(vals) if vals else None),
            "mean_directional_60m_return":(statistics.mean(vals) if vals else None),
            "median_directional_60m_return":(statistics.median(vals) if vals else None),
            "median_abs_gap_return":(statistics.median(gaps) if gaps else None),
            "median_shock_to_scale":(statistics.median(shocks) if shocks else None),
        },
        "samples":samples,
    }

def execute(path:str|Path)->dict[str,Any]:
    z,manifest=open_canonical_capture(path)
    per_symbol={}
    for s in manifest["series"]:
        per_symbol[s["broker_symbol"]]=screen_symbol(load_rows(z,s["file"]))
    total=sum(x["settled_structural_samples"] for x in per_symbol.values())
    weighted_positive=sum(
        (x["structural_reversion"]["positive_reversion_fraction"] or 0.0)*x["settled_structural_samples"]
        for x in per_symbol.values()
    )
    ranked=sorted(
        per_symbol,
        key=lambda sym:(
            per_symbol[sym]["settled_structural_samples"],
            per_symbol[sym]["active_signal_weeks"],
            per_symbol[sym]["structural_reversion"]["median_directional_60m_return"] if per_symbol[sym]["structural_reversion"]["median_directional_60m_return"] is not None else -1e99,
        ),
        reverse=True,
    )
    result={
        "schema":"mxm.greenfield.session-gap-structural-extension-wave01-screen.v1",
        "status":"NON_ECONOMIC_STRUCTURAL_SCREEN_COMPLETE",
        "version":VERSION,
        "source_ai_proposal_id":"P-20260924-C031-GAP-WAVE-01",
        "source_canonical_capture_sha256":CANONICAL_ZIP_SHA256,
        "scope_law":{
            "this_12_symbol_wave_is_not_the_global_broker_universe":True,
            "mechanism_family_closed":False,
            "exact_C031_rerun":False,
            "economic_candidate_identity_created":False,
        },
        "parameters":{
            "minimum_observed_gap_minutes":30,
            "scale_window_exact_m5_returns":288,
            "minimum_scale_observations":144,
            "shock_scale_multiple":3.0,
            "scheduled_measurement_horizon_minutes":60,
            "cost_hurdle_applied":False,
            "reason_cost_hurdle_not_applied":"This is a pre-economic structural breadth screen; no candidate PnL/cost decision is opened here."
        },
        "aggregate":{
            "symbols":len(per_symbol),
            "settled_structural_samples":total,
            "weighted_positive_reversion_fraction":(weighted_positive/total if total else None),
            "symbols_with_at_least_4_settled_samples":sum(x["settled_structural_samples"]>=4 for x in per_symbol.values()),
            "symbols_with_positive_median_directional_60m_return":sum(
                (x["structural_reversion"]["median_directional_60m_return"] or 0)>0 for x in per_symbol.values()
            ),
        },
        "ranked_by_information_density":ranked,
        "per_symbol":per_symbol,
        "economic_effect":{"economic_outcomes_opened":0,"v2_attempts_consumed":0},
        "safety":{"protected_forward_opened":False,"live_orders_authorized":False,"competition_start_authorized":False},
    }
    raw=json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    result["result_sha256"]=hashlib.sha256(raw).hexdigest()
    return result
