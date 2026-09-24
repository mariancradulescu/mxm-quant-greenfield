from __future__ import annotations
import csv, hashlib, io, json, math, statistics, zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.schema import validate_result

VERSION="MXM_BREAKOUT_EPOCH19_C032_EVALUATOR_V1"
CID="V2-C032"
SPEC_HASH="96a752ab7c91401f569527b0a21c7757e4418002cc918e0663589e6ae4044936"
CAPTURE_SHA="801b863d396a117d787b73dd673003cf79a4c9ffa178a38d0c928aba241243f0"
PLAN_SHA="2afa8dc853068442cd36e3f02653f034e21183e15e06745e023a561f59e238a9"
ACCEPTANCE_REF="evidence/BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_CAPTURE_ACCEPTANCE_V1.json"
N=1000.0
M5=timedelta(minutes=5)
HOLD=timedelta(minutes=30)
LOOKBACK=24
EXPANSION=1.5
EXPECTED_FIELDS=("time_utc","open","high","low","close","tick_volume")

class C032IntegrityError(ValueError): pass
class C032PreOutcomeCostUnresolved(C032IntegrityError): pass

def sha256_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha256_file(path)->str: return sha256_bytes(Path(path).read_bytes())
def parse_dt(s): return datetime.fromisoformat(str(s).replace("Z","+00:00")).astimezone(timezone.utc)

def _verify_checksums(z):
    declared={}
    for line in z.read("CHECKSUMS.sha256").decode().splitlines():
        if line.strip():
            digest,rel=line.split("  ",1); declared[rel]=digest
    observed={}
    for rel in ("capture_manifest.json","event_boundary_costs.csv","historical_conversion_summary.json","stage_a_m5/NETH25_M5.csv"):
        observed[rel]=sha256_bytes(z.read(rel))
    if declared!=observed: raise C032IntegrityError("root checksum manifest mismatch")
    prefix="MXM_BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_V1/"
    duplicate_names=[prefix+"CHECKSUMS.sha256",*[prefix+x for x in observed]]
    present=[x for x in duplicate_names if x in z.namelist()]
    if present:
        if len(present)!=len(duplicate_names): raise C032IntegrityError("partial duplicate wrapper")
        if z.read(prefix+"CHECKSUMS.sha256")!=z.read("CHECKSUMS.sha256"): raise C032IntegrityError("duplicate checksum file drift")
        for rel in observed:
            if z.read(prefix+rel)!=z.read(rel): raise C032IntegrityError("duplicate wrapper bytes drift: "+rel)

def open_capture(root,capture_zip):
    root=Path(root); path=Path(capture_zip)
    if sha256_file(path)!=CAPTURE_SHA: raise C032IntegrityError("capture SHA mismatch")
    acceptance=json.loads((root/ACCEPTANCE_REF).read_text())
    if acceptance.get("status")!="ACCEPTED_HASH_VERIFIED_INDEPENDENT_PRE_OUTCOME_COST_AND_M5_CAPTURE": raise C032IntegrityError("capture acceptance not authoritative")
    if acceptance.get("source",{}).get("zip_sha256")!=CAPTURE_SHA: raise C032IntegrityError("acceptance capture SHA mismatch")
    z=zipfile.ZipFile(path)
    bad=z.testzip()
    if bad: raise C032IntegrityError("capture CRC failure: "+bad)
    _verify_checksums(z)
    manifest=json.loads(z.read("capture_manifest.json"))
    checks=(
        manifest.get("status")=="CAPTURE_COMPLETE_COST_EVIDENCE_UNOPENED_ECONOMICS",
        manifest.get("plan_sha256")==PLAN_SHA,
        manifest.get("symbol",{}).get("broker_symbol")=="NETH25",
        manifest.get("symbol",{}).get("symbol_id")==269,
        manifest.get("protected_evidence_opened") is False,
        manifest.get("economic_outcomes_opened")==0,
        manifest.get("v2_attempts_consumed")==0,
        manifest.get("orders_placed") is False,
        manifest.get("account_mutation") is False,
        manifest.get("raw_ticks_transferred") is False,
    )
    if not all(checks): raise C032IntegrityError("capture manifest safety/binding mismatch")
    return z,manifest

def load_rows(z):
    raw=z.read("stage_a_m5/NETH25_M5.csv").decode()
    reader=csv.DictReader(io.StringIO(raw))
    if tuple(reader.fieldnames or ())!=EXPECTED_FIELDS: raise C032IntegrityError("unexpected M5 fields")
    out=[]
    for r in reader:
        out.append({"t":parse_dt(r["time_utc"]),"o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),"c":float(r["close"]),"v":int(r["tick_volume"])})
    if not out or any(out[i]["t"]>=out[i+1]["t"] for i in range(len(out)-1)): raise C032IntegrityError("M5 chronology invalid")
    return out

def load_costs(z):
    rows=list(csv.DictReader(io.StringIO(z.read("event_boundary_costs.csv").decode())))
    if len({x["event_bar_time_utc"] for x in rows})!=len(rows): raise C032IntegrityError("duplicate event cost row")
    out={}
    for r in rows:
        for k in ("entry_spread","entry_one_side_commission_price_equivalent","exit_spread","exit_one_side_commission_price_equivalent","roundtrip_cost_price_equivalent"):
            r[k]=None if r[k] in (None,"") else float(r[k])
        out[parse_dt(r["event_bar_time_utc"])]=r
    return out

def contiguous(rows,a,b):
    return a>=0 and b<len(rows) and all(rows[i+1]["t"]-rows[i]["t"]==M5 for i in range(a,b))

def event_direction(rows,i):
    if i<LOOKBACK or not contiguous(rows,i-LOOKBACK,i): return 0
    prior=rows[i-LOOKBACK:i]; cur=rows[i]
    med=statistics.median(x["h"]-x["l"] for x in prior); rng=cur["h"]-cur["l"]
    expansion=(rng>=EXPANSION*med) if med>0 else rng>0
    if not expansion: return 0
    hi=max(x["h"] for x in prior); lo=min(x["l"] for x in prior)
    if cur["c"]>hi: return 1
    if cur["c"]<lo: return -1
    return 0

def _first_later_index(rows,start_i,target):
    for j in range(start_i+1,len(rows)):
        if rows[j]["t"]>=target: return j
    return None

def build_admitted_trades(rows,costs):
    events=[]
    for i in range(LOOKBACK,len(rows)):
        d=event_direction(rows,i)
        if d: events.append((i,d))
    if {rows[i]["t"] for i,_ in events}!=set(costs): raise C032IntegrityError("frozen event law does not reproduce exact cost-row event set")
    active_until=None; trades=[]; suppressed=[]; right_censored=[]
    for i,d in events:
        event_t=rows[i]["t"]; decision=event_t+M5
        if active_until is not None and decision<=active_until:
            suppressed.append(event_t); continue
        ei=_first_later_index(rows,i,decision)
        if ei is None:
            right_censored.append(event_t); continue
        entry=rows[ei]
        target=entry["t"]+HOLD
        xi=_first_later_index(rows,ei,target)
        if xi is None:
            right_censored.append(event_t); active_until=datetime.max.replace(tzinfo=timezone.utc); continue
        exit_=rows[xi]
        cost=costs[event_t]
        expected_entry=event_t+M5; expected_exit=expected_entry+HOLD
        if entry["t"]!=expected_entry or exit_["t"]!=expected_exit:
            raise C032PreOutcomeCostUnresolved("admitted trade requires cost at a delayed executable boundary not captured by frozen transaction-local cost plan")
        if cost.get("cost_state")!="TRANSACTION_LOCAL_COST_RESOLVED" or cost.get("roundtrip_cost_price_equivalent") is None:
            raise C032PreOutcomeCostUnresolved("admitted trade has unresolved transaction-local cost")
        if parse_dt(cost["entry_boundary_utc"])!=entry["t"] or parse_dt(cost["exit_boundary_utc"])!=exit_["t"]:
            raise C032IntegrityError("cost boundary does not match admitted execution boundary")
        rt=float(cost["roundtrip_cost_price_equivalent"])
        recomputed=0.5*float(cost["entry_spread"])+0.5*float(cost["exit_spread"])+float(cost["entry_one_side_commission_price_equivalent"])+float(cost["exit_one_side_commission_price_equivalent"])
        if abs(rt-recomputed)>1e-9: raise C032IntegrityError("transaction-local cost arithmetic mismatch")
        trades.append({"event":event_t,"d":"SHORT" if d>0 else "LONG","e":entry["t"],"x":exit_["t"],"p":entry["o"],"q":exit_["o"],"cost_price":rt})
        active_until=exit_["t"]
    return trades,{"events_detected":len(events),"suppressed_by_prior_active_state":len(suppressed),"right_censored":len(right_censored),"admitted":len(trades)}

def _add(bucket,key,g,c,n):
    x=bucket.setdefault(key,{"event_count":0,"gross_pnl_eur":0.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":0.0})
    x["event_count"]+=1; x["gross_pnl_eur"]+=g; x["transaction_cost_eur"]+=c; x["coarse_net_pnl_eur"]+=n

def evaluate(root,capture_zip):
    root=Path(root); z,manifest=open_capture(root,capture_zip)
    spec=json.loads((root/"discovery/candidates/V2-C032.json").read_text()); verify_spec_hash(spec)
    if spec.get("spec_hash")!=SPEC_HASH: raise C032IntegrityError("C032 active spec hash mismatch")
    rows=load_rows(z); costs=load_costs(z)
    trades,diag=build_admitted_trades(rows,costs)
    if not trades: raise C032IntegrityError("C032 has no admitted trades")
    trades=sorted(trades,key=lambda x:(x["x"],x["e"],x["event"]))
    gross=cost=net=cum=peak=dd=0.0; dates=[]; holds=[]; weekly=Counter(); weekday=Counter(); session=Counter(); sy={}; di={}; sub={}
    start=parse_dt(manifest["event_analysis_interval"]["start_utc"]); end=parse_dt(manifest["event_analysis_interval"]["end_utc"])
    for t in trades:
        sg=1 if t["d"]=="LONG" else -1
        g=((t["q"]-t["p"])/t["p"])*sg*N
        c=(t["cost_price"]/t["p"])*N
        n=g-c
        gross+=g; cost+=c; net+=n; cum+=n; peak=max(peak,cum); dd=max(dd,peak-cum)
        iso=t["e"].isocalendar(); weekly[f"{iso.year}-W{iso.week:02d}"]+=1
        names=("MON","TUE","WED","THU","FRI","SAT","SUN"); weekday[names[t["e"].weekday()]]+=1
        h=(t["e"].hour//3)*3; session[f"UTC_{h:02d}_{(h+3)%24:02d}"]+=1
        holds.append((t["x"]-t["e"]).total_seconds()/60); dates.append(t["e"].date())
        _add(sy,"NETH25",g,c,n); _add(di,t["d"],g,c,n)
        _add(sub,"SEP14_15" if t["e"].date()<=datetime(2026,9,15,tzinfo=timezone.utc).date() else "SEP16_17",g,c,n)
    unique=sorted(set(dates)); gaps=[0] if not unique else [max(0,(b-a).days-1) for a,b in zip(unique,unique[1:])] or [0]
    metrics={
        "event_count":len(trades),"gross_pnl":gross,"coarse_net_pnl":net,
        "gross_return":gross/(len(trades)*N),"coarse_net_return":net/(len(trades)*N),
        "gross_per_event":gross/len(trades),"net_per_event":net/len(trades),"cost_burden":cost/(len(trades)*N),
        "turnover":2*N*len(trades),"weekly_events":dict(sorted(weekly.items())),"active_weeks":len(weekly),
        "longest_inactive_gap":max(gaps),"weekday_distribution":dict(sorted(weekday.items())),"session_distribution":dict(sorted(session.items())),
        "hold_duration":{"min_minutes":min(holds),"median_minutes":statistics.median(holds),"mean_minutes":statistics.mean(holds),"max_minutes":max(holds)},
        "exposure":sum(holds)/max(1.0,(end-start).total_seconds()/60),"drawdown":dd,
        "symbol_contribution":sy,"direction_contribution":di,"subperiod_contribution":sub,
        "regime_contribution":{"state":"NOT_APPLICABLE","reason":"No post-outcome regime binning; this is one prospectively frozen fixed-rule independent outer."},
    }
    status="GROSS_EDGE_FAIL" if gross<=0 else ("COARSE_NET_FAIL" if net<=0 else "DISCOVERY_SURVIVOR")
    result={
        "candidate_id":CID,"spec_hash":SPEC_HASH,"stage":"A","status":status,
        "implementation_validity":{"state":"VALID","reason":"Exact-head authorized fixed event/state-machine evaluator with no future-dependent admission and exact hash-bound capture checks."},
        "metrics":metrics,
        "eur200_feasibility":{"state":"FEASIBLE","reason":"Accepted broker-native EUR200 feasibility index marks NETH25 BOTH_FEASIBLE; Stage A remains analytic EUR1000 normalization."},
        "cost_confidence":{"state":"VERIFIED","reason":"Every admitted trade binds a TRANSACTION_LOCAL_COST_RESOLVED entry+exit row from the accepted independent capture; unresolved rows are not used for admission and would halt if admitted."},
        "data_completeness":{"state":"SUFFICIENT","reason":"Hash-verified independent NETH25 M5/cost capture is strictly post-development and pre-protected-forward; all admitted executions have exact required M5 opens and resolved costs."},
        "provenance":{
            "data_evidence":{"identity":"MXM_BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_V1","binding":{"type":"DATASET_SHA256","sha256":CAPTURE_SHA}},
            "cost_evidence":{"identity":"MXM_BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_V1","state":"VERIFIED","sha256":CAPTURE_SHA},
            "evaluator":{"version":VERSION,"sha256":sha256_file(__file__)},
        },
    }
    validate_result(result); result["result_hash"]=compute_result_hash(result); validate_result(result)
    summary={"candidate_id":CID,"diagnostics":diag,"result_hash":result["result_hash"],"status":status,"protected_evidence_opened":False}
    return result,summary
