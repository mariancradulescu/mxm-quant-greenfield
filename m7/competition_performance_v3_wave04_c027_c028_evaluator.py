from __future__ import annotations
import json, math, statistics
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path

from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.schema import validate_result
from m7.competition_performance_v3_wave02_evaluator import (
    CAP, COST_SHA, M5, contiguous, evaluate, load_rows, open_capture, sha256_file,
)

VERSION = "MXM_PERFORMANCE_RESEARCH_V3_WAVE04_C027_C028_EVALUATOR_V1"
IDS = ("V2-C027", "V2-C028")
PAIRS = (("US500", "US2000"), ("SpotCrude", "SpotBrent"))

class Wave04IntegrityError(ValueError):
    pass

def c027_trades(rows_by_symbol, costs):
    out=[]; diagnostics={}
    for symbol,rows in rows_by_symbol.items():
        active_until=None; decisions=breakouts=expansion_pass=cost_scale_pass=0
        for i in range(144, len(rows)-37):
            decision=rows[i]["t"]+M5
            if decision.minute % 30 != 0: continue
            decisions += 1
            if not contiguous(rows,i-144,i+37): continue
            prior=rows[i-72:i]
            hi=max(x["h"] for x in prior); lo=min(x["l"] for x in prior)
            close=rows[i]["c"]
            direction="LONG" if close>hi else ("SHORT" if close<lo else None)
            if direction is None: continue
            breakouts += 1
            current_abs=abs(close/rows[i-6]["c"]-1.0)
            hist=[]
            for j in range(i-144,i,6):
                if j < 6: continue
                hist.append(abs(rows[j]["c"]/rows[j-6]["c"]-1.0))
            if len(hist)!=24: continue
            scale=statistics.median(hist)
            if not math.isfinite(scale) or scale<=0 or current_abs <= 1.5*scale: continue
            expansion_pass += 1
            if current_abs <= 3.0*costs[symbol]: continue
            cost_scale_pass += 1
            entry_i=i+1; exit_i=i+37
            entry_t=rows[entry_i]["t"]; exit_t=rows[exit_i]["t"]
            if active_until is not None and entry_t < active_until: continue
            out.append({"cid":"V2-C027","s":symbol,"d":direction,"e":entry_t,"x":exit_t,"p":rows[entry_i]["o"],"q":rows[exit_i]["o"],"costf":costs[symbol],"meta":{"channel_high":hi,"channel_low":lo,"signal_close":close,"abs_30m_return":current_abs,"prior_median_abs_30m_return":scale}})
            active_until=exit_t
        diagnostics[symbol]={"decisions":decisions,"channel_breakouts":breakouts,"expansion_passes":expansion_pass,"cost_scale_passes":cost_scale_pass}
    return out,diagnostics

def _pair_shocks(leader, laggard, costs, leader_name, laggard_name):
    lag_idx={r["t"]:i for i,r in enumerate(laggard)}
    history=defaultdict(deque); pending=deque(); out=[]; active_until=None
    decisions=shock_pass=trained=cost_hurdle_pass=0
    for i in range(288,len(leader)-1):
        decision=leader[i]["t"]+M5
        if decision.minute % 15 != 0: continue
        decisions += 1
        while pending and pending[0][0] <= decision:
            avail,entry_t,direction,aligned=pending.popleft(); history[direction].append((entry_t,aligned))
        cutoff=decision-timedelta(days=28)
        for direction in list(history):
            dq=history[direction]
            while dq and dq[0][0] < cutoff: dq.popleft()
            if not dq: del history[direction]
        if not contiguous(leader,i-288,i): continue
        r30=leader[i]["c"]/leader[i-6]["c"]-1.0
        if r30==0: continue
        hist_abs=[abs(leader[j]["c"]/leader[j-6]["c"]-1.0) for j in range(i-288,i,3)]
        if len(hist_abs)!=96: continue
        scale=statistics.median(hist_abs)
        if not math.isfinite(scale) or scale<=0: continue
        score=abs(r30)/scale
        if score <= 2.0: continue
        shock_pass += 1
        direction="LONG" if r30>0 else "SHORT"; sign=1.0 if r30>0 else -1.0
        li=lag_idx.get(decision)
        if li is None or li+12>=len(laggard) or not contiguous(laggard,li,li+12): continue
        exit_t=laggard[li+12]["t"]
        if exit_t != decision+timedelta(minutes=60): continue
        p=laggard[li]["o"]; q=laggard[li+12]["o"]
        if p<=0: continue
        aligned=sign*(q/p-1.0)
        pending.append((exit_t,decision,direction,aligned))
        vals=[x[1] for x in history.get(direction,())]
        if len(vals)<8: continue
        trained += 1
        mean=statistics.mean(vals); se=statistics.stdev(vals)/math.sqrt(len(vals)); lower=mean-se
        if mean<=0 or lower<=costs[laggard_name]: continue
        cost_hurdle_pass += 1
        if active_until is not None and decision < active_until: continue
        out.append({"cid":"V2-C028","s":laggard_name,"d":direction,"e":decision,"x":exit_t,"p":p,"q":q,"costf":costs[laggard_name],"meta":{"leader":leader_name,"shock_score":score,"leader_r30":r30,"train_n":len(vals),"mean_aligned":mean,"se":se,"lower_aligned_edge":lower}})
        active_until=exit_t
    return out,{"decisions":decisions,"shock_passes":shock_pass,"trained_shocks":trained,"cost_hurdle_passes":cost_hurdle_pass}

def c028_trades(rows_by_symbol,costs):
    out=[]; diagnostics={}
    for leader,laggard in PAIRS:
        trades,diag=_pair_shocks(rows_by_symbol[leader],rows_by_symbol[laggard],costs,leader,laggard)
        out.extend(trades); diagnostics[f"{leader}_TO_{laggard}"]=diag
    return out,diagnostics

def _finalize(cid,spec,trades):
    result=evaluate(cid,spec,trades,COST_SHA)
    result["implementation_validity"]={"state":"VALID","reason":"Frozen Wave04 causal evaluator and accepted V6/cost integrity gates passed."}
    result["metrics"]["regime_contribution"]={"state":"NOT_APPLICABLE","reason":"Wave04 signal states are prospectively frozen mechanism inputs, not post-outcome regime bins."}
    result["provenance"]["evaluator"]={"version":VERSION,"sha256":sha256_file(__file__)}
    result["result_hash"]=compute_result_hash(result)
    validate_result(result)
    return result

def execute_wave(root,capture_zip):
    root=Path(root)
    acceptance=json.loads((root/"data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json").read_text())
    costs_doc=json.loads((root/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json").read_text())
    if sha256_file(root/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json") != COST_SHA: raise Wave04IntegrityError("cost authority SHA mismatch")
    wave=json.loads((root/"research_v3/WAVE_04_PRE_OUTCOME_FREEZE_V1.json").read_text())
    if wave.get("status") not in {"FROZEN_PENDING_EXACT_HEAD_GREEN","AUTHORIZED_AFTER_EXACT_HEAD_GREEN"}: raise Wave04IntegrityError("Wave04 not frozen/authorized")
    z=open_capture(capture_zip,acceptance)
    rows_by={s:load_rows(z,s) for s in acceptance["selected_markets"]}
    costs={s:v["roundtrip_cost_fraction"] for s,v in costs_doc["symbols"].items()}
    specs={}
    for cid in IDS:
        spec=json.loads((root/"discovery/candidates"/f"{cid}.json").read_text()); verify_spec_hash(spec)
        if wave["candidate_spec_hashes"].get(cid)!=spec["spec_hash"]: raise Wave04IntegrityError(cid+" wave spec mismatch")
        specs[cid]=spec
    t27,d27=c027_trades(rows_by,costs)
    t28,d28=c028_trades(rows_by,costs)
    if not t27: raise Wave04IntegrityError("V2-C027 no events")
    if not t28: raise Wave04IntegrityError("V2-C028 no events")
    results={"V2-C027":_finalize("V2-C027",specs["V2-C027"],t27),"V2-C028":_finalize("V2-C028",specs["V2-C028"],t28)}
    summary={"schema":"mxm.greenfield.performance-research-v3.wave04-stage-a-summary.v1","capture_sha256":CAP,"cost_authority_sha256":COST_SHA,"results":{cid:{"status":r["status"],"event_count":r["metrics"]["event_count"],"gross_pnl":r["metrics"]["gross_pnl"],"coarse_net_pnl":r["metrics"]["coarse_net_pnl"],"result_hash":r["result_hash"],"weekly_events":r["metrics"]["weekly_events"]} for cid,r in results.items()},"learning_diagnostics":{"V2-C027":d27,"V2-C028":d28},"stage_b_extension_candidates":[cid for cid,r in results.items() if r["status"]=="DISCOVERY_SURVIVOR"],"protected_evidence_opened":False}
    return results,summary
