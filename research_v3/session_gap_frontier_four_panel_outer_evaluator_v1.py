"""Exact prospective non-economic outer evaluator for the frozen four-panel SESSION_GAP_REVERSION test."""
from __future__ import annotations
import csv, hashlib, io, json, math, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from research_v3.session_gap_structural_screen_v1 import screen_symbol

VERSION="MXM_SESSION_GAP_FRONTIER_FOUR_PANEL_OUTER_EVALUATOR_V1"
CAPTURE_SHA256="73cc5b5a2bf2d756ef4ca75ef0b4fbd5e13a3da04d7dab2809b57616fbc41404"
PLAN_SHA256="1cddfd3e8a21a992bd3ab756ecf191c0c3e83487a35b266e714388252476ee3f"
SYMBOLS=("ZARJPY","US400","XPDUSD","NETH25")
ALPHA=0.05

class OuterIntegrityError(ValueError): pass
def _sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def _dt(s:str)->datetime: return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)

def _load(path:str|Path):
    path=Path(path); raw=path.read_bytes()
    if _sha(raw)!=CAPTURE_SHA256: raise OuterIntegrityError("capture ZIP hash mismatch")
    z=zipfile.ZipFile(path)
    bad=z.testzip()
    if bad: raise OuterIntegrityError(f"ZIP CRC failure: {bad}")
    manifest=json.loads(z.read("capture_manifest.json"))
    if manifest.get("status")!="CAPTURE_COMPLETE_OUTER_UNOPENED": raise OuterIntegrityError("manifest status mismatch")
    if manifest.get("plan_sha256")!=PLAN_SHA256: raise OuterIntegrityError("plan hash mismatch")
    if manifest.get("outer_outcome_opened") is not False: raise OuterIntegrityError("outer already opened by capture")
    declared={}
    for line in z.read("CHECKSUMS.sha256").decode().splitlines():
        if line.strip():
            h,rel=line.split(None,1); declared[rel.strip()]=h
    for rel,h in declared.items():
        if _sha(z.read(rel))!=h: raise OuterIntegrityError(f"checksum mismatch: {rel}")
    return z,manifest

def _rows(z:zipfile.ZipFile,sym:str):
    rel=f"stage_a_m5/{sym}_M5.csv"; out=[]
    for row in csv.DictReader(io.StringIO(z.read(rel).decode())):
        out.append({"t":_dt(row["time_utc"]),"o":float(row["open"]),"h":float(row["high"]),
                    "l":float(row["low"]),"c":float(row["close"]),"v":float(row["tick_volume"])})
    if any(out[i]["t"]>=out[i+1]["t"] for i in range(len(out)-1)): raise OuterIntegrityError(f"{sym}: chronology")
    return out

def _binom_upper(x:int,n:int)->float:
    if n<=0: return 1.0
    return sum(math.comb(n,k) for k in range(x,n+1))/(2**n)

def execute(path:str|Path)->dict[str,Any]:
    z,manifest=_load(path); per={}; raw_p={}
    for sym in SYMBOLS:
        s=screen_symbol(_rows(z,sym),minimum_gap_minutes=30,scale_window=288,
                        minimum_scale_observations=144,shock_scale_multiple=3.0,
                        scheduled_horizon_minutes=60)
        vals=[x["directional_60m_return"] for x in s["samples"]]
        pos=sum(v>0 for v in vals); neg=sum(v<0 for v in vals); zero=sum(v==0 for v in vals)
        n=pos+neg; p=_binom_upper(pos,n); raw_p[sym]=p
        per[sym]={"settled_structural_samples":s["settled_structural_samples"],"active_signal_weeks":s["active_signal_weeks"],
                  "positive":pos,"negative":neg,"exact_zero_excluded":zero,"confirmatory_nonzero_n":n,
                  "positive_fraction_nonzero":(pos/n if n else None),"one_sided_exact_binomial_p":p,
                  "median_directional_60m_return":s["structural_reversion"]["median_directional_60m_return"],
                  "mean_directional_60m_return":s["structural_reversion"]["mean_directional_60m_return"],
                  "observed_gap_events":s["observed_gap_events"],"shock_scale_hurdle_passes":s["shock_scale_hurdle_passes"],
                  "admitted_structural_signals":s["admitted_structural_signals"]}
    ordered=sorted(SYMBOLS,key=lambda s:(raw_p[s],s)); alive=True
    for i,sym in enumerate(ordered):
        threshold=ALPHA/(len(SYMBOLS)-i); reject=bool(alive and raw_p[sym]<=threshold)
        if alive and not reject: alive=False
        per[sym]["holm_rank"]=i+1; per[sym]["holm_threshold"]=threshold; per[sym]["holm_reject_null"]=reject
    total=sum(per[s]["settled_structural_samples"] for s in SYMBOLS)
    positives=sum(per[s]["positive"] for s in SYMBOLS); nonzero=sum(per[s]["confirmatory_nonzero_n"] for s in SYMBOLS)
    result={"schema":"mxm.greenfield.session-gap-frontier-four-panel-independent-outer-confirmatory-result.v1",
      "status":"NON_ECONOMIC_CONFIRMATORY_OUTER_COMPLETE","version":VERSION,
      "source_capture_sha256":CAPTURE_SHA256,"source_plan_sha256":PLAN_SHA256,
      "source_capture_manifest_status":manifest["status"],"fixed_symbols":list(SYMBOLS),
      "frozen_test":{"primary_endpoint":"sign of causal directional_60m_return","null_hypothesis":"P(directional_60m_return > 0) <= 0.5",
        "per_symbol_test":"ONE_SIDED_EXACT_BINOMIAL_SIGN_TEST","exact_zeros_excluded":True,
        "familywise_correction":"HOLM_BONFERRONI","familywise_alpha":ALPHA,"family_size":4},
      "parameters":{"minimum_observed_gap_minutes":30,"scale_window_exact_m5_returns":288,"minimum_scale_observations":144,
        "shock_scale_multiple":3.0,"scheduled_measurement_horizon_minutes":60},
      "per_symbol":per,
      "aggregate_descriptive_only":{"settled_structural_samples":total,"confirmatory_nonzero_samples":nonzero,
        "sample_weighted_positive_fraction_nonzero":(positives/nonzero if nonzero else None),
        "holm_rejections":sum(per[s]["holm_reject_null"] for s in SYMBOLS)},
      "interpretation_boundary":{"panel_aggregate_is_descriptive_only":True,"mechanism_family_closed":False,
        "economic_candidate_identity_created":False,"cost_aware_economic_conclusion_opened":False,"exact_c031_rerun":False},
      "economic_effect":{"economic_outcomes_opened":0,"v2_attempts_consumed":0},
      "safety":{"protected_forward_opened":False,"live_orders_authorized":False,"competition_start_authorized":False}}
    b=json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    result["result_sha256"]=hashlib.sha256(b).hexdigest(); return result
