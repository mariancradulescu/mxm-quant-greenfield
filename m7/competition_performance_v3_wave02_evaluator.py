from __future__ import annotations
import csv, hashlib, io, json, math, statistics, zipfile
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.schema import validate_result

VERSION = "MXM_PERFORMANCE_RESEARCH_V3_WAVE02_EVALUATOR_V1"
CAP = "dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d"
COST_SHA = "b7ca6191b5570c1cc22f644feb6b0124c6bec0f00fc5ad5a8c772419bcb481b9"
PREFIX = "MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6/"
IDS = ("V2-C024", "V2-C025")
START = datetime(2026, 6, 15, tzinfo=timezone.utc)
END = datetime(2026, 9, 14, tzinfo=timezone.utc)
LATEST4 = datetime(2026, 8, 17, tzinfo=timezone.utc)
M5 = timedelta(minutes=5)
N = 1000.0

class Wave02IntegrityError(ValueError):
    pass

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())

def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)

def open_capture(path: Path | str, acceptance: dict):
    path = Path(path)
    if sha256_file(path) != CAP or acceptance["source"]["zip_sha256"] != CAP:
        raise Wave02IntegrityError("capture SHA mismatch")
    z = zipfile.ZipFile(path)
    bad = z.testzip()
    if bad:
        raise Wave02IntegrityError(f"capture CRC failure: {bad}")
    declared = {
        x.split("  ", 1)[1]: x.split("  ", 1)[0]
        for x in z.read(PREFIX + "CHECKSUMS.sha256").decode().splitlines()
        if x.strip()
    }
    observed = {}
    for name in z.namelist():
        if name.startswith(PREFIX) and not name.endswith("/") and not name.endswith("CHECKSUMS.sha256"):
            observed[name[len(PREFIX):]] = sha256_bytes(z.read(name))
    if declared != observed:
        raise Wave02IntegrityError("capture internal checksum mismatch")
    return z

def load_rows(z, symbol: str):
    out = []
    raw = z.read(PREFIX + f"stage_a_m5/{symbol}_M5.csv").decode()
    for r in csv.DictReader(io.StringIO(raw)):
        out.append({"t": parse_dt(r["time_utc"]), "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]), "c": float(r["close"])})
    if not out or any(out[i]["t"] >= out[i+1]["t"] for i in range(len(out)-1)):
        raise Wave02IntegrityError(symbol + " chronology")
    return out

def contiguous(rows, a: int, b: int) -> bool:
    return a >= 0 and b < len(rows) and all(rows[i+1]["t"] - rows[i]["t"] == M5 for i in range(a, b))

def decision_boundary(bar_open: datetime) -> bool:
    completed = bar_open + M5
    return completed.minute % 15 == 0

def sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)

def session_bucket(t: datetime) -> str:
    h = t.hour
    if h < 8: return "ASIA_00_08"
    if h < 14: return "EUROPE_08_14"
    if h < 21: return "US_14_21"
    return "LATE_21_24"

def weeks():
    out=[]; d=START
    while d < END:
        iso=d.isocalendar(); k=f"{iso.year}-W{iso.week:02d}"
        if k not in out: out.append(k)
        d += timedelta(days=1)
    return out

def _r3(rows, i):
    return rows[i]["c"] / rows[i-3]["c"] - 1.0

def _c024_snapshot(rows_by_symbol, index_by_symbol, t):
    vals={}
    for symbol, rows in rows_by_symbol.items():
        i=index_by_symbol[symbol].get(t)
        if i is None or i < 39 or not contiguous(rows, i-39, i):
            continue
        prior=[]
        ok=True
        for j in range(i-36, i):
            if j < 3:
                ok=False; break
            prior.append(abs(_r3(rows,j)))
        if not ok or len(prior)!=36:
            continue
        scale=statistics.median(prior)
        if not math.isfinite(scale) or scale <= 0:
            continue
        r=_r3(rows,i)
        vals[symbol]={"norm":r/scale,"r3":r,"scale":scale,"i":i}
    if len(vals) < 4:
        return None
    med=statistics.median(v["norm"] for v in vals.values())
    for v in vals.values(): v["resid"]=v["norm"]-med
    return vals

def c024_trades(rows_by_symbol, costs):
    idx={s:{r["t"]:i for i,r in enumerate(q)} for s,q in rows_by_symbol.items()}
    decision_times=sorted({r["t"] for q in rows_by_symbol.values() for r in q if decision_boundary(r["t"])})
    out=[]; active_until=None
    for t in decision_times:
        decision=t+M5
        if active_until is not None and decision <= active_until:
            continue
        snap=_c024_snapshot(rows_by_symbol,idx,t)
        if not snap: continue
        eligible=[]
        for s,v in snap.items():
            i=v["i"]; q=rows_by_symbol[s]
            if i+12 >= len(q) or not contiguous(q,i,i+12):
                continue
            resid=v["resid"]
            if resid == 0: continue
            eligible.append((abs(resid)/costs[s], s, resid, i))
        if not eligible: continue
        eligible.sort(key=lambda x:(-x[0],x[1]))
        _,symbol,entry_resid,i=eligible[0]
        q=rows_by_symbol[symbol]
        ei=i+1
        entry=q[ei]
        direction="SHORT" if entry_resid>0 else "LONG"
        exit_price=None; exit_time=None; exit_reason=None
        # Dynamic exit is decided only from completed bars; execution is at the next observed M5 open.
        for k in range(ei, ei+11):
            decision2=q[k]["t"]+M5
            snap2=_c024_snapshot(rows_by_symbol,idx,q[k]["t"])
            if not snap2 or symbol not in snap2: continue
            resid2=snap2[symbol]["resid"]
            if resid2 == 0 or sign(resid2) != sign(entry_resid):
                if k+1 < len(q) and q[k+1]["t"] == decision2:
                    exit_price=q[k+1]["o"]; exit_time=q[k+1]["t"]; exit_reason="RESIDUAL_ZERO_OR_CROSS_NEXT_OPEN"
                    break
        if exit_price is None:
            xi=ei+11
            exit_price=q[xi]["c"]; exit_time=q[xi]["t"]+M5; exit_reason="MAX_HOLD_CLOSE"
        out.append({"cid":"V2-C024","s":symbol,"d":direction,"e":entry["t"],"x":exit_time,"p":entry["o"],"q":exit_price,"costf":costs[symbol],"meta":{"entry_residual":entry_resid,"exit_reason":exit_reason}})
        active_until=exit_time
    return out

def _c025_state(rows,i):
    if i < 147 or not contiguous(rows,i-147,i): return None
    r1=rows[i]["c"]/rows[i-1]["c"]-1.0
    r3=_r3(rows,i)
    r12=rows[i]["c"]/rows[i-12]["c"]-1.0
    prior=[abs(_r3(rows,j)) for j in range(i-144,i)]
    med=statistics.median(prior)
    if med <= 0 or not math.isfinite(med): return None
    return (sign(r1),sign(r3),sign(r12),"HIGH" if abs(r3)>med else "LOW",session_bucket(rows[i]["t"]+M5))

def c025_trades(rows_by_symbol,costs):
    out=[]; diagnostics={}
    for symbol,rows in rows_by_symbol.items():
        pending=deque()  # (availability_time, decision_time, state, realized_forward_return)
        hist=defaultdict(deque) # state -> deque[(decision_time, return)]
        active_until=None; decisions=eligible_states=cost_hurdle_pass=0
        for i in range(147,len(rows)-4):
            if not decision_boundary(rows[i]["t"]): continue
            dtime=rows[i]["t"]+M5
            while pending and pending[0][0] <= dtime:
                avail,dec,st,ret=pending.popleft(); hist[st].append((dec,ret))
            cutoff=dtime-timedelta(days=28)
            for st in list(hist):
                dq=hist[st]
                while dq and dq[0][0] < cutoff: dq.popleft()
                if not dq: del hist[st]
            st=_c025_state(rows,i)
            if st is None: continue
            decisions+=1
            # Build today's training example prospectively; it cannot be used until target exit completes.
            ei=i+1; xi=ei+2
            if contiguous(rows,i,xi):
                entry=rows[ei]["o"]; ex=rows[xi]["c"]
                if entry>0:
                    pending.append((rows[xi]["t"]+M5,dtime,st,ex/entry-1.0))
            vals=[x[1] for x in hist.get(st,())]
            if len(vals)<2: continue
            eligible_states+=1
            mean=statistics.mean(vals); sd=statistics.stdev(vals); se=sd/math.sqrt(len(vals))
            if abs(mean)-se <= costs[symbol] or mean==0: continue
            cost_hurdle_pass+=1
            if active_until is not None and dtime <= active_until: continue
            if not contiguous(rows,i,xi): continue
            out.append({"cid":"V2-C025","s":symbol,"d":"LONG" if mean>0 else "SHORT","e":rows[ei]["t"],"x":rows[xi]["t"]+M5,"p":rows[ei]["o"],"q":rows[xi]["c"],"costf":costs[symbol],"meta":{"state":list(st),"train_n":len(vals),"mean":mean,"se":se,"lower_abs_edge":abs(mean)-se}})
            active_until=rows[xi]["t"]+M5
        diagnostics[symbol]={"decisions":decisions,"states_with_at_least_2_prior_examples":eligible_states,"cost_hurdle_passes":cost_hurdle_pass}
    return out,diagnostics

def add(bucket,key,g,c,n):
    x=bucket.setdefault(key,{"event_count":0,"gross_pnl_eur":0.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":0.0})
    x["event_count"]+=1; x["gross_pnl_eur"]+=g; x["transaction_cost_eur"]+=c; x["coarse_net_pnl_eur"]+=n

def evaluate(cid,spec,trades,cost_sha):
    if not trades: raise Wave02IntegrityError(cid+" no events")
    trades=sorted(trades,key=lambda x:(x["x"],x["s"],x["d"],x["e"]))
    W={k:0 for k in weeks()}; wd={k:0 for k in ("MON","TUE","WED","THU","FRI","SAT","SUN")}; ss=Counter(); sy={}; di={}; sub={}; dates=set(); holds=[]
    gross=cost=net=cum=peak=dd=0.0
    for t in trades:
        sg=1 if t["d"].startswith("LONG") else -1
        g=((t["q"]-t["p"])/t["p"])*sg*N; c=t["costf"]*N; n=g-c
        gross+=g; cost+=c; net+=n; cum+=n; peak=max(peak,cum); dd=max(dd,peak-cum)
        iso=t["e"].isocalendar(); W[f"{iso.year}-W{iso.week:02d}"]+=1
        wd[("MON","TUE","WED","THU","FRI","SAT","SUN")[t["e"].weekday()]]+=1
        h=(t["e"].hour//3)*3; ss[f"UTC_{h:02d}_{(h+3)%24:02d}"]+=1; dates.add(t["e"].date()); holds.append((t["x"]-t["e"]).total_seconds()/60)
        add(sy,t["s"],g,c,n); add(di,t["d"],g,c,n); add(sub,"LATEST_4W" if t["e"]>=LATEST4 else "EARLY_9W",g,c,n)
    D=sorted(dates); gaps=[(D[0]-START.date()).days]+[(b-a).days-1 for a,b in zip(D,D[1:])]+[(END.date()-D[-1]).days]
    m={"event_count":len(trades),"gross_pnl":gross,"coarse_net_pnl":net,"gross_return":gross/(len(trades)*N),"coarse_net_return":net/(len(trades)*N),"gross_per_event":gross/len(trades),"net_per_event":net/len(trades),"cost_burden":cost/(len(trades)*N),"turnover":2*N*len(trades),"weekly_events":W,"active_weeks":sum(v>0 for v in W.values()),"longest_inactive_gap":max(gaps),"weekday_distribution":wd,"session_distribution":dict(sorted(ss.items())),"hold_duration":{"min_minutes":min(holds),"median_minutes":statistics.median(holds),"mean_minutes":statistics.mean(holds),"max_minutes":max(holds)},"exposure":sum(holds)/(((END-START).total_seconds()/60)*max(1,len(sy))),"drawdown":dd,"symbol_contribution":sy,"direction_contribution":di,"subperiod_contribution":sub,"regime_contribution":{"state":"NOT_APPLICABLE","reason":"No post-outcome regime binning is introduced; C025 regime/state variables are part of the prospectively frozen signal itself."}}
    status="GROSS_EDGE_FAIL" if gross<=0 else ("COARSE_NET_FAIL" if net<=0 else "DISCOVERY_SURVIVOR")
    result={"candidate_id":cid,"spec_hash":spec["spec_hash"],"stage":"A","status":status,"implementation_validity":{"state":"VALID","reason":"Frozen V3 Wave02 causal evaluator and accepted V6/cost integrity gates passed."},"metrics":m,"eur200_feasibility":{"state":"NOT_EVALUATED","reason":"Stage A uses fixed EUR1000 analytic normalization; exact shared EUR200 realization is Stage B only for a Stage-A survivor."},"cost_confidence":{"state":"CONSERVATIVE_BOUND","reason":"Uses the unchanged pre-outcome V6 per-symbol coarse roundtrip cost authority."},"data_completeness":{"state":"SUFFICIENT","reason":"Accepted V6 13-week M5 capture with checksum-bound complete series for the selected broker-native frontier."},"provenance":{"data_evidence":{"identity":"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6","binding":{"type":"DATASET_SHA256","sha256":CAP}},"cost_evidence":{"identity":"COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1","state":"CONSERVATIVE_BOUND","sha256":cost_sha},"evaluator":{"version":VERSION,"sha256":sha256_file(__file__)}}}
    validate_result(result); result["result_hash"]=compute_result_hash(result); validate_result(result); return result

def execute_wave(root,capture_zip):
    root=Path(root)
    acceptance=json.loads((root/"data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json").read_text())
    costs_doc=json.loads((root/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json").read_text())
    if sha256_file(root/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json") != COST_SHA:
        raise Wave02IntegrityError("cost authority SHA mismatch")
    wave=json.loads((root/"research_v3/WAVE_02_PRE_OUTCOME_FREEZE_V1.json").read_text())
    if wave.get("status") not in {"FROZEN_PENDING_EXACT_HEAD_GREEN","AUTHORIZED_AFTER_EXACT_HEAD_GREEN"}:
        raise Wave02IntegrityError("Wave02 not frozen/authorized")
    z=open_capture(capture_zip,acceptance)
    rows_by={s:load_rows(z,s) for s in acceptance["selected_markets"]}
    costs={s:v["roundtrip_cost_fraction"] for s,v in costs_doc["symbols"].items()}
    specs={}
    for cid in IDS:
        spec=json.loads((root/"discovery/candidates"/f"{cid}.json").read_text()); verify_spec_hash(spec)
        if wave["candidate_spec_hashes"].get(cid)!=spec["spec_hash"]: raise Wave02IntegrityError(cid+" wave spec mismatch")
        specs[cid]=spec
    t24=c024_trades(rows_by,costs)
    t25,diag25=c025_trades(rows_by,costs)
    results={"V2-C024":evaluate("V2-C024",specs["V2-C024"],t24,COST_SHA),"V2-C025":evaluate("V2-C025",specs["V2-C025"],t25,COST_SHA)}
    summary={"schema":"mxm.greenfield.performance-research-v3.wave02-stage-a-summary.v1","capture_sha256":CAP,"cost_authority_sha256":COST_SHA,"results":{cid:{"status":r["status"],"event_count":r["metrics"]["event_count"],"gross_pnl":r["metrics"]["gross_pnl"],"coarse_net_pnl":r["metrics"]["coarse_net_pnl"],"result_hash":r["result_hash"],"weekly_events":r["metrics"]["weekly_events"]} for cid,r in results.items()},"c025_learning_diagnostics":diag25,"stage_b_extension_candidates":[cid for cid,r in results.items() if r["status"]=="DISCOVERY_SURVIVOR"],"protected_evidence_opened":False}
    return results,summary
