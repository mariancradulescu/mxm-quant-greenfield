from __future__ import annotations
import csv, hashlib, io, json, math, statistics, zipfile
from collections import Counter, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path

VERSION = "MXM_PERFORMANCE_RESEARCH_V3_WAVE06_C031_EVALUATOR_V1"
CAP = "dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d"
COST_SHA = "b7ca6191b5570c1cc22f644feb6b0124c6bec0f00fc5ad5a8c772419bcb481b9"
PREFIX = "MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6/"
CID = "V2-C031"
START = datetime(2026, 6, 15, tzinfo=timezone.utc)
END = datetime(2026, 9, 14, tzinfo=timezone.utc)
LATEST4 = datetime(2026, 8, 17, tzinfo=timezone.utc)
M5 = timedelta(minutes=5)
N = 1000.0
NON_SEMANTIC = {"rationale", "provenance", "spec_hash"}

class Wave06IntegrityError(ValueError):
    pass

def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())

def git_blob_sha1(path):
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def compute_spec_hash(spec):
    return hashlib.sha256(canonical_json({k:v for k,v in spec.items() if k not in NON_SEMANTIC}).encode("utf-8")).hexdigest()

def compute_result_hash(result):
    return hashlib.sha256(canonical_json({k:v for k,v in result.items() if k != "result_hash"}).encode("utf-8")).hexdigest()

def parse_dt(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)

def open_capture(path, acceptance):
    path = Path(path)
    if sha256_file(path) != CAP or acceptance["source"]["zip_sha256"] != CAP:
        raise Wave06IntegrityError("capture SHA mismatch")
    z = zipfile.ZipFile(path)
    bad = z.testzip()
    if bad:
        raise Wave06IntegrityError(f"capture CRC failure: {bad}")
    declared = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in z.read(PREFIX + "CHECKSUMS.sha256").decode().splitlines()
        if line.strip()
    }
    observed = {}
    for name in z.namelist():
        if name.startswith(PREFIX) and not name.endswith("/") and not name.endswith("CHECKSUMS.sha256"):
            observed[name[len(PREFIX):]] = sha256_bytes(z.read(name))
    if declared != observed:
        raise Wave06IntegrityError("capture internal checksum mismatch")
    return z

def load_rows(z, symbol):
    raw = z.read(PREFIX + f"stage_a_m5/{symbol}_M5.csv").decode()
    out = []
    for row in csv.DictReader(io.StringIO(raw)):
        out.append({
            "t": parse_dt(row["time_utc"]),
            "o": float(row["open"]),
            "h": float(row["high"]),
            "l": float(row["low"]),
            "c": float(row["close"]),
        })
    if not out or any(out[i]["t"] >= out[i+1]["t"] for i in range(len(out)-1)):
        raise Wave06IntegrityError(symbol + " chronology")
    if any(min(r["o"],r["h"],r["l"],r["c"]) <= 0 for r in out):
        raise Wave06IntegrityError(symbol + " non-positive OHLC")
    return out

def session_bucket(t):
    h=t.hour
    if h < 8: return "ASIA_00_08"
    if h < 14: return "EUROPE_08_14"
    if h < 21: return "US_14_21"
    return "LATE_21_24"

def weeks():
    out=[]; d=START
    while d < END:
        iso=d.isocalendar(); key=f"{iso.year}-W{iso.week:02d}"
        if key not in out: out.append(key)
        d += timedelta(days=1)
    return out

def gap_reversion_trades(rows_by_symbol, costs, *, minimum_gap_minutes=30, scale_window=288,
                         minimum_scale_observations=144, shock_scale_multiple=3.0,
                         cost_multiple=4.0, hold_minutes=60):
    settled=[]
    diagnostics={}
    for symbol, rows in rows_by_symbol.items():
        scale_hist=deque(maxlen=scale_window)
        pending=None
        active=None
        admitted=filled=closed=right_pending=right_active=gap_events=scale_ready=shock_pass=cost_pass=0

        for i,row in enumerate(rows):
            if active is not None and row["t"] >= active["target"]:
                settled.append({
                    "cid":CID, "s":symbol, "d":active["direction"],
                    "e":active["entry_t"], "x":row["t"],
                    "p":active["entry_price"], "q":row["o"],
                    "costf":costs[symbol],
                    "meta":dict(active["meta"], scheduled_target=active["target"].isoformat()),
                })
                closed += 1
                active = None

            if pending is not None and row["t"] >= pending["decision_time"] and active is None:
                active={
                    "entry_t":row["t"],
                    "entry_price":row["o"],
                    "target":row["t"] + timedelta(minutes=hold_minutes),
                    "direction":pending["direction"],
                    "meta":pending["meta"],
                }
                filled += 1
                pending = None

            if i == 0:
                continue

            prev=rows[i-1]
            gap_minutes=(row["t"]-prev["t"]).total_seconds()/60.0
            prior_scale=(statistics.median(scale_hist)
                         if len(scale_hist) >= minimum_scale_observations else None)

            if gap_minutes >= minimum_gap_minutes:
                gap_events += 1
                if prior_scale is not None and math.isfinite(prior_scale) and prior_scale > 0:
                    scale_ready += 1
                    gap_return=row["o"]/prev["c"]-1.0
                    abs_gap=abs(gap_return)
                    if abs_gap > shock_scale_multiple*prior_scale:
                        shock_pass += 1
                        if abs_gap > cost_multiple*costs[symbol]:
                            cost_pass += 1
                            if active is None and pending is None and gap_return != 0:
                                pending={
                                    "decision_time":row["t"]+M5,
                                    "direction":"SHORT" if gap_return > 0 else "LONG",
                                    "meta":{
                                        "signal_bar_open":row["t"].isoformat(),
                                        "observed_gap_minutes":gap_minutes,
                                        "gap_return":gap_return,
                                        "prior_median_abs_exact_m5_return":prior_scale,
                                        "shock_to_scale":abs_gap/prior_scale,
                                        "signal_move_to_roundtrip_cost":abs_gap/costs[symbol],
                                    },
                                }
                                admitted += 1

            if row["t"]-prev["t"] == M5:
                r=abs(row["c"]/prev["c"]-1.0)
                if math.isfinite(r):
                    scale_hist.append(r)

        if pending is not None:
            right_pending += 1
        if active is not None:
            right_active += 1
        diagnostics[symbol]={
            "observed_gap_events":gap_events,
            "gap_events_with_scale_ready":scale_ready,
            "shock_scale_hurdle_passes":shock_pass,
            "cost_hurdle_passes":cost_pass,
            "admitted_signals":admitted,
            "filled_entries":filled,
            "settled_trades":closed,
            "right_censored_pending_entries":right_pending,
            "right_censored_open_trades":right_active,
            "final_scale_observations":len(scale_hist),
        }
    return settled,diagnostics

def _add(bucket,key,g,c,n):
    node=bucket.setdefault(key,{"event_count":0,"gross_pnl_eur":0.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":0.0})
    node["event_count"] += 1
    node["gross_pnl_eur"] += g
    node["transaction_cost_eur"] += c
    node["coarse_net_pnl_eur"] += n

def _zero_contribution():
    return {"NO_EVENTS":{"event_count":0,"gross_pnl_eur":0.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":0.0}}

def evaluate(spec,trades):
    trades=sorted(trades,key=lambda x:(x["x"],x["s"],x["d"],x["e"]))
    W={k:0 for k in weeks()}
    wd={k:0 for k in ("MON","TUE","WED","THU","FRI","SAT","SUN")}
    ss=Counter(); sy={}; di={}; sub={}; dates=[]; holds=[]
    gross=cost=net=cum=peak=dd=0.0

    for t in trades:
        sg=1 if t["d"].startswith("LONG") else -1
        g=((t["q"]-t["p"])/t["p"])*sg*N
        c=t["costf"]*N
        n=g-c
        gross+=g; cost+=c; net+=n
        cum+=n; peak=max(peak,cum); dd=max(dd,peak-cum)
        iso=t["e"].isocalendar(); key=f"{iso.year}-W{iso.week:02d}"
        if key in W: W[key]+=1
        wd[("MON","TUE","WED","THU","FRI","SAT","SUN")[t["e"].weekday()]]+=1
        ss[session_bucket(t["e"])] += 1
        dates.append(t["e"].date())
        holds.append((t["x"]-t["e"]).total_seconds()/60.0)
        _add(sy,t["s"],g,c,n); _add(di,t["d"],g,c,n)
        _add(sub,"LATEST_4W" if t["e"]>=LATEST4 else "EARLY_9W",g,c,n)

    if trades:
        unique_dates=sorted(set(dates))
        gaps=[(unique_dates[0]-START.date()).days]
        gaps += [(b-a).days-1 for a,b in zip(unique_dates,unique_dates[1:])]
        gaps += [(END.date()-unique_dates[-1]).days]
        event_count=len(trades)
        metrics={
            "event_count":event_count,
            "gross_pnl":gross,
            "coarse_net_pnl":net,
            "gross_return":gross/(event_count*N),
            "coarse_net_return":net/(event_count*N),
            "gross_per_event":gross/event_count,
            "net_per_event":net/event_count,
            "cost_burden":cost/(event_count*N),
            "turnover":2*N*event_count,
            "weekly_events":W,
            "active_weeks":sum(v>0 for v in W.values()),
            "longest_inactive_gap":max(gaps),
            "weekday_distribution":wd,
            "session_distribution":dict(sorted(ss.items())),
            "hold_duration":{"min_minutes":min(holds),"median_minutes":statistics.median(holds),"mean_minutes":statistics.mean(holds),"max_minutes":max(holds)},
            "exposure":sum(holds)/(((END-START).total_seconds()/60.0)*max(1,len(sy))),
            "drawdown":dd,
            "symbol_contribution":sy,
            "direction_contribution":di,
            "subperiod_contribution":sub,
            "regime_contribution":{"state":"NOT_APPLICABLE","reason":"Observed market-gap state is part of the prospectively frozen signal, not a post-outcome regime bin."},
        }
        status="GROSS_EDGE_FAIL" if gross<=0 else ("COARSE_NET_FAIL" if net<=0 else "DISCOVERY_SURVIVOR")
    else:
        metrics={
            "event_count":0,
            "gross_pnl":0.0,
            "coarse_net_pnl":0.0,
            "gross_return":0.0,
            "coarse_net_return":0.0,
            "gross_per_event":0.0,
            "net_per_event":0.0,
            "cost_burden":0.0,
            "turnover":0.0,
            "weekly_events":W,
            "active_weeks":0,
            "longest_inactive_gap":(END-START).days,
            "weekday_distribution":wd,
            "session_distribution":{"NO_EVENTS":0},
            "hold_duration":{"min_minutes":0.0,"median_minutes":0.0,"mean_minutes":0.0,"max_minutes":0.0},
            "exposure":0.0,
            "drawdown":0.0,
            "symbol_contribution":_zero_contribution(),
            "direction_contribution":_zero_contribution(),
            "subperiod_contribution":{
                "EARLY_9W":{"event_count":0,"gross_pnl_eur":0.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":0.0},
                "LATEST_4W":{"event_count":0,"gross_pnl_eur":0.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":0.0},
            },
            "regime_contribution":{"state":"NOT_APPLICABLE","reason":"No post-outcome regime binning; zero settled events under the frozen identity."},
        }
        status="GROSS_EDGE_FAIL"

    result={
        "candidate_id":CID,
        "spec_hash":spec["spec_hash"],
        "stage":"A",
        "status":status,
        "implementation_validity":{"state":"VALID","reason":"Wave06 per-symbol chronological state machine admits signals before any future fill/exit observation and processes entry/exit only when observed market opens arrive."},
        "metrics":metrics,
        "eur200_feasibility":{"state":"NOT_EVALUATED","reason":"Stage A uses fixed EUR1000 analytic normalization; exact shared EUR200 realization is Stage B only for a Stage-A survivor."},
        "cost_confidence":{"state":"CONSERVATIVE_BOUND","reason":"Uses the unchanged pre-outcome V6 per-symbol conservative roundtrip cost authority."},
        "data_completeness":{"state":"SUFFICIENT","reason":"Accepted checksum-bound V6 DEVELOPMENT capture is sufficient for the frozen first-observed-open settlement rule; capture-end pending states are prospectively right-censored."},
        "provenance":{
            "data_evidence":{"identity":"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6","binding":{"type":"DATASET_SHA256","sha256":CAP}},
            "cost_evidence":{"identity":"COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1","state":"CONSERVATIVE_BOUND","sha256":COST_SHA},
            "evaluator":{"version":VERSION,"sha256":sha256_file(__file__)},
        },
    }
    result["result_hash"]=compute_result_hash(result)
    return result

def execute_wave(root,capture_zip):
    root=Path(root)
    acceptance=json.loads((root/"data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json").read_text(encoding="utf-8"))
    costs_path=root/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json"
    if sha256_file(costs_path) != COST_SHA:
        raise Wave06IntegrityError("cost authority SHA mismatch")
    costs_doc=json.loads(costs_path.read_text(encoding="utf-8"))
    wave=json.loads((root/"research_v3/WAVE_06_PRE_OUTCOME_FREEZE_V1.json").read_text(encoding="utf-8"))
    if wave.get("status") not in {"FROZEN_PENDING_EXACT_HEAD_GREEN","AUTHORIZED_AFTER_EXACT_HEAD_GREEN"}:
        raise Wave06IntegrityError("Wave06 not frozen/authorized")
    spec=json.loads((root/"discovery/candidates/V2-C031.json").read_text(encoding="utf-8"))
    if spec.get("spec_hash") != compute_spec_hash(spec):
        raise Wave06IntegrityError("C031 spec hash mismatch")
    if wave.get("candidate_spec_hashes",{}).get(CID) != spec["spec_hash"]:
        raise Wave06IntegrityError("C031 freeze/spec mismatch")
    z=open_capture(capture_zip,acceptance)
    rows_by={s:load_rows(z,s) for s in acceptance["selected_markets"]}
    costs={s:float(v["roundtrip_cost_fraction"]) for s,v in costs_doc["symbols"].items()}
    if set(rows_by) != set(spec["universe"]) or set(costs) < set(spec["universe"]):
        raise Wave06IntegrityError("V6 universe/cost coverage mismatch")
    trades,diag=gap_reversion_trades(
        rows_by,costs,
        minimum_gap_minutes=int(spec["parameters"]["minimum_observed_gap_minutes"]),
        scale_window=int(spec["parameters"]["scale_window_exact_m5_returns"]),
        minimum_scale_observations=int(spec["parameters"]["minimum_scale_observations"]),
        shock_scale_multiple=float(spec["parameters"]["shock_scale_multiple"]),
        cost_multiple=float(spec["parameters"]["minimum_signal_move_cost_multiple"]),
        hold_minutes=int(spec["parameters"]["scheduled_hold_minutes"]),
    )
    result=evaluate(spec,trades)
    summary={
        "schema":"mxm.greenfield.performance-research-v3.wave06-stage-a-summary.v1",
        "capture_sha256":CAP,
        "cost_authority_sha256":COST_SHA,
        "result":{
            "candidate_id":CID,
            "status":result["status"],
            "event_count":result["metrics"]["event_count"],
            "gross_pnl":result["metrics"]["gross_pnl"],
            "coarse_net_pnl":result["metrics"]["coarse_net_pnl"],
            "result_hash":result["result_hash"],
        },
        "diagnostics":diag,
        "stage_b_extension_candidates":[CID] if result["status"]=="DISCOVERY_SURVIVOR" else [],
        "protected_evidence_opened":False,
    }
    return {CID:result},summary
