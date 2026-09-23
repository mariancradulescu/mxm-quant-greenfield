from __future__ import annotations
import json, math, statistics
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path

from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.schema import STAGE_A_METRIC_KEYS, validate_result
from m7.competition_performance_v3_wave02_evaluator import (
    CAP, COST_SHA, M5, evaluate, load_rows, open_capture, sha256_file,
)

VERSION = "MXM_PERFORMANCE_RESEARCH_V3_WAVE05_C029_C030_EVALUATOR_V1"
IDS = ("V2-C029", "V2-C030")
PAIRS = (("US500", "US2000"), ("SpotCrude", "SpotBrent"))

class Wave05IntegrityError(ValueError):
    pass

def _contiguous_time(rows, a: int, b: int) -> bool:
    return a >= 0 and b < len(rows) and all(rows[j+1]["t"] - rows[j]["t"] == M5 for j in range(a,b))

def _right_censored(target, last_observed):
    return target > last_observed

def c029_trades(rows_by_symbol, costs):
    settled=[]; diagnostics={}; invalid=[]
    for symbol,rows in rows_by_symbol.items():
        idx={r["t"]:i for i,r in enumerate(rows)}
        active=None
        decisions=breakouts=expansion_pass=cost_scale_pass=admitted=settled_n=right=0
        last_t=rows[-1]["t"] if rows else None
        for i in range(144,len(rows)):
            decision=rows[i]["t"]+M5
            if decision.minute % 30 != 0:
                continue
            if active is not None and active["target"] <= decision:
                ti=idx.get(active["target"])
                if ti is not None and _contiguous_time(rows,active["entry_i"],ti):
                    settled.append({"cid":"V2-C029","s":symbol,"d":active["direction"],"e":active["entry_t"],"x":active["target"],"p":active["entry_price"],"q":rows[ti]["o"],"costf":costs[symbol],"meta":active["meta"]})
                    settled_n += 1
                elif _right_censored(active["target"],last_t):
                    right += 1
                else:
                    invalid.append({"candidate_id":"V2-C029","symbol":symbol,"entry_time":active["entry_t"].isoformat(),"expected_target_time":active["target"].isoformat(),"classification":"POST_ENTRY_SETTLEMENT_DATA_INVALID"})
                active=None

            decisions += 1
            if not _contiguous_time(rows,i-144,i):
                continue
            prior=rows[i-72:i]
            hi=max(x["h"] for x in prior); lo=min(x["l"] for x in prior)
            close=rows[i]["c"]
            direction="LONG" if close>hi else ("SHORT" if close<lo else None)
            if direction is None:
                continue
            breakouts += 1
            current_abs=abs(close/rows[i-6]["c"]-1.0)
            hist=[abs(rows[j]["c"]/rows[j-6]["c"]-1.0) for j in range(i-144,i,6)]
            if len(hist)!=24:
                continue
            scale=statistics.median(hist)
            if not math.isfinite(scale) or scale<=0 or current_abs <= 1.5*scale:
                continue
            expansion_pass += 1
            if current_abs <= 3.0*costs[symbol]:
                continue
            cost_scale_pass += 1
            if active is not None:
                continue
            entry_i=i+1
            if entry_i>=len(rows) or rows[entry_i]["t"] != decision:
                continue
            entry=rows[entry_i]
            admitted += 1
            active={
                "entry_i":entry_i,"entry_t":decision,"entry_price":entry["o"],
                "target":decision+timedelta(minutes=180),"direction":direction,
                "meta":{"channel_high":hi,"channel_low":lo,"signal_close":close,"abs_30m_return":current_abs,"prior_median_abs_30m_return":scale},
            }
        if active is not None:
            ti=idx.get(active["target"])
            if ti is not None and _contiguous_time(rows,active["entry_i"],ti):
                settled.append({"cid":"V2-C029","s":symbol,"d":active["direction"],"e":active["entry_t"],"x":active["target"],"p":active["entry_price"],"q":rows[ti]["o"],"costf":costs[symbol],"meta":active["meta"]})
                settled_n += 1
            elif _right_censored(active["target"],last_t):
                right += 1
            else:
                invalid.append({"candidate_id":"V2-C029","symbol":symbol,"entry_time":active["entry_t"].isoformat(),"expected_target_time":active["target"].isoformat(),"classification":"POST_ENTRY_SETTLEMENT_DATA_INVALID"})
        diagnostics[symbol]={"decisions":decisions,"channel_breakouts":breakouts,"expansion_passes":expansion_pass,"cost_scale_passes":cost_scale_pass,"admitted_entries":admitted,"settled_entries":settled_n,"right_censored_entries":right}
    return settled,diagnostics,invalid

def _settle_lag_example(laggard,lag_idx,item,last_t):
    ti=lag_idx.get(item["target"])
    if ti is None:
        return ("RIGHT_CENSORED",None) if _right_censored(item["target"],last_t) else ("INVALID",None)
    if not _contiguous_time(laggard,item["entry_i"],ti):
        return "INVALID",None
    q=laggard[ti]["o"]
    if item["entry_price"]<=0:
        return "INVALID",None
    aligned=item["sign"]*(q/item["entry_price"]-1.0)
    return "SETTLED",aligned

def _pair_shocks(leader,laggard,costs,leader_name,laggard_name):
    lag_idx={r["t"]:i for i,r in enumerate(laggard)}
    history=defaultdict(deque); pending=deque(); settled=[]; invalid=[]
    active=None
    decisions=shock_pass=trained=cost_hurdle=admitted=right=training_invalid=0
    last_lag=laggard[-1]["t"] if laggard else None

    def process_due(now):
        nonlocal active,right,training_invalid
        while pending and pending[0]["target"] <= now:
            item=pending.popleft(); status,aligned=_settle_lag_example(laggard,lag_idx,item,last_lag)
            if status=="SETTLED":
                history[item["direction"]].append((item["entry_t"],aligned))
            elif status=="RIGHT_CENSORED":
                right += 1
            else:
                training_invalid += 1
                invalid.append({"candidate_id":"V2-C030","pair":f"{leader_name}_TO_{laggard_name}","entry_time":item["entry_t"].isoformat(),"expected_target_time":item["target"].isoformat(),"classification":"POST_ENTRY_TRAINING_SETTLEMENT_DATA_INVALID"})
        if active is not None and active["target"] <= now:
            status,aligned=_settle_lag_example(laggard,lag_idx,active,last_lag)
            if status=="SETTLED":
                ti=lag_idx[active["target"]]
                settled.append({"cid":"V2-C030","s":laggard_name,"d":active["direction"],"e":active["entry_t"],"x":active["target"],"p":active["entry_price"],"q":laggard[ti]["o"],"costf":costs[laggard_name],"meta":active["meta"]})
            elif status=="RIGHT_CENSORED":
                right += 1
            else:
                invalid.append({"candidate_id":"V2-C030","pair":f"{leader_name}_TO_{laggard_name}","entry_time":active["entry_t"].isoformat(),"expected_target_time":active["target"].isoformat(),"classification":"POST_ENTRY_TRADE_SETTLEMENT_DATA_INVALID"})
            active=None

    for i in range(288,len(leader)):
        decision=leader[i]["t"]+M5
        if decision.minute % 15 != 0:
            continue
        process_due(decision)
        cutoff=decision-timedelta(days=28)
        for direction in list(history):
            dq=history[direction]
            while dq and dq[0][0] < cutoff:
                dq.popleft()
            if not dq:
                del history[direction]
        decisions += 1
        if not _contiguous_time(leader,i-288,i):
            continue
        r30=leader[i]["c"]/leader[i-6]["c"]-1.0
        if r30==0:
            continue
        hist_abs=[abs(leader[j]["c"]/leader[j-6]["c"]-1.0) for j in range(i-288,i,3)]
        if len(hist_abs)!=96:
            continue
        scale=statistics.median(hist_abs)
        if not math.isfinite(scale) or scale<=0:
            continue
        score=abs(r30)/scale
        if score<=2.0:
            continue
        shock_pass += 1
        direction="LONG" if r30>0 else "SHORT"; sg=1.0 if r30>0 else -1.0
        li=lag_idx.get(decision)
        if li is None:
            continue
        entry_price=laggard[li]["o"]
        if entry_price<=0:
            continue
        item={"entry_i":li,"entry_t":decision,"entry_price":entry_price,"target":decision+timedelta(minutes=60),"direction":direction,"sign":sg}
        pending.append(dict(item))
        vals=[x[1] for x in history.get(direction,())]
        if len(vals)<8:
            continue
        trained += 1
        mean=statistics.mean(vals); se=statistics.stdev(vals)/math.sqrt(len(vals)); lower=mean-se
        if mean<=0 or lower<=costs[laggard_name]:
            continue
        cost_hurdle += 1
        if active is not None:
            continue
        admitted += 1
        item["meta"]={"leader":leader_name,"shock_score":score,"leader_r30":r30,"train_n":len(vals),"mean_aligned":mean,"se":se,"lower_aligned_edge":lower}
        active=item

    process_due(last_lag+M5 if last_lag is not None else leader[-1]["t"]+M5)
    right += len(pending); pending.clear()
    if active is not None:
        right += 1; active=None
    diag={"decisions":decisions,"shock_passes":shock_pass,"trained_shocks":trained,"cost_hurdle_passes":cost_hurdle,"admitted_trade_entries":admitted,"settled_trade_entries":len(settled),"right_censored_pending_items":right,"training_settlement_invalid":training_invalid}
    return settled,diag,invalid

def c030_trades(rows_by_symbol,costs):
    out=[]; diagnostics={}; invalid=[]
    for leader,laggard in PAIRS:
        trades,diag,bad=_pair_shocks(rows_by_symbol[leader],rows_by_symbol[laggard],costs,leader,laggard)
        out.extend(trades); invalid.extend(bad); diagnostics[f"{leader}_TO_{laggard}"]=diag
    return out,diagnostics,invalid

def _unavailable(reason):
    return {k:{"state":"UNAVAILABLE","reason":reason} for k in STAGE_A_METRIC_KEYS}

def _data_insufficient(cid,spec,reason):
    result={"candidate_id":cid,"spec_hash":spec["spec_hash"],"stage":"A","status":"DATA_INSUFFICIENT","implementation_validity":{"state":"VALID","reason":"Live-equivalent Wave05 admission and post-entry settlement state machine passed control-path validation."},"metrics":_unavailable(reason),"eur200_feasibility":{"state":"NOT_EVALUATED","reason":"Stage A cannot promote while DEVELOPMENT settlement evidence is insufficient."},"cost_confidence":{"state":"CONSERVATIVE_BOUND","reason":"Uses unchanged pre-outcome V6 per-symbol roundtrip cost authority."},"data_completeness":{"state":"INSUFFICIENT","reason":reason},"provenance":{"data_evidence":{"identity":"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6","binding":{"type":"DATASET_SHA256","sha256":CAP}},"cost_evidence":{"identity":"COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1","state":"CONSERVATIVE_BOUND","sha256":COST_SHA},"evaluator":{"version":VERSION,"sha256":sha256_file(__file__)}}}
    validate_result(result); result["result_hash"]=compute_result_hash(result); validate_result(result); return result

def _finalize(cid,spec,trades,invalid):
    if invalid:
        return _data_insufficient(cid,spec,f"{len(invalid)} causally admitted or training post-entry settlement(s) lack the frozen exact/contiguous target evidence inside the DEVELOPMENT capture; no entry is retroactively erased and no partial PnL is used.")
    if not trades:
        return _data_insufficient(cid,spec,"No fully settled economic trade is available after causal admission/right-censoring under the frozen Wave05 mechanism.")
    result=evaluate(cid,spec,trades,COST_SHA)
    result["implementation_validity"]={"state":"VALID","reason":"Wave05 live-equivalent event state machine passed: future target availability is not queried before admission."}
    result["metrics"]["regime_contribution"]={"state":"NOT_APPLICABLE","reason":"Wave05 signal/training states are prospectively frozen mechanism inputs, not post-outcome regime bins."}
    result["provenance"]["evaluator"]={"version":VERSION,"sha256":sha256_file(__file__)}
    result["result_hash"]=compute_result_hash(result); validate_result(result); return result

def execute_wave(root,capture_zip):
    root=Path(root)
    acceptance=json.loads((root/"data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json").read_text())
    costs_doc=json.loads((root/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json").read_text())
    if sha256_file(root/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json") != COST_SHA:
        raise Wave05IntegrityError("cost authority SHA mismatch")
    wave=json.loads((root/"research_v3/WAVE_05_PRE_OUTCOME_FREEZE_V1.json").read_text())
    if wave.get("status") not in {"FROZEN_PENDING_EXACT_HEAD_GREEN","AUTHORIZED_AFTER_EXACT_HEAD_GREEN"}:
        raise Wave05IntegrityError("Wave05 not frozen/authorized")
    z=open_capture(capture_zip,acceptance)
    rows_by={s:load_rows(z,s) for s in acceptance["selected_markets"]}
    costs={s:v["roundtrip_cost_fraction"] for s,v in costs_doc["symbols"].items()}
    specs={}
    for cid in IDS:
        spec=json.loads((root/"discovery/candidates"/f"{cid}.json").read_text()); verify_spec_hash(spec)
        if wave["candidate_spec_hashes"].get(cid)!=spec["spec_hash"]:
            raise Wave05IntegrityError(cid+" wave spec mismatch")
        specs[cid]=spec
    t29,d29,b29=c029_trades(rows_by,costs)
    t30,d30,b30=c030_trades(rows_by,costs)
    results={"V2-C029":_finalize("V2-C029",specs["V2-C029"],t29,b29),"V2-C030":_finalize("V2-C030",specs["V2-C030"],t30,b30)}
    summary={"schema":"mxm.greenfield.performance-research-v3.wave05-stage-a-summary.v1","capture_sha256":CAP,"cost_authority_sha256":COST_SHA,"results":{cid:{"status":r["status"],"event_count":r["metrics"]["event_count"] if not isinstance(r["metrics"]["event_count"],dict) else None,"gross_pnl":r["metrics"]["gross_pnl"] if not isinstance(r["metrics"]["gross_pnl"],dict) else None,"coarse_net_pnl":r["metrics"]["coarse_net_pnl"] if not isinstance(r["metrics"]["coarse_net_pnl"],dict) else None,"result_hash":r["result_hash"]} for cid,r in results.items()},"learning_diagnostics":{"V2-C029":d29,"V2-C030":d30},"settlement_invalid_counts":{"V2-C029":len(b29),"V2-C030":len(b30)},"stage_b_extension_candidates":[cid for cid,r in results.items() if r["status"]=="DISCOVERY_SURVIVOR"],"protected_evidence_opened":False}
    return results,summary
