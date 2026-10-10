"""Frozen extrema TIME-order sign: no training, optimization or private outputs."""
import math
from datetime import datetime,timezone
from research_core_v4.owner_frontier_v1.transition_kernel_v1 import label_at,n,LAG

def empty():
    return {"calendar":0,"eligible_pair":0,"supported":0,
      "new_gross_sum_bps":0.0,"baseline_gross_sum_bps":0.0,
      "new_positive":0,"baseline_positive":0,"reason_counts":{}}

def bump(m,reason):
    m["reason_counts"][reason]=m["reason_counts"].get(reason,0)+1

def evaluate(bars):
    weeks=[empty() for _ in range(4)]
    iso={}
    trials=[]
    for j in range(0,672,4):
        t=n.START+j*3600
        action=t+LAG
        week=j//168
        dt=datetime.fromtimestamp(action,timezone.utc).isocalendar()
        tag=f"{dt.year}-W{dt.week:02d}"
        m=weeks[week]
        z=iso.setdefault(tag,empty())
        for mm in (m,z):mm["calendar"]+=1
        stamps=range(t-3600,t,300)
        rows=[bars.get(s) for s in stamps]
        if any(r is None for r in rows):
            reason="FEATURE_GAP"
        elif any(not n.frozen.valid_bar(s,r,action) for s,r in zip(stamps,rows)):
            reason="FEATURE_RECEIPT_CONDITIONAL"
        else:
            # deterministic earliest-index tie law: no outcome-dependent threshold
            imax=max(range(12),key=lambda i:rows[i]["high"])
            imin=min(range(12),key=lambda i:rows[i]["low"])
            new=(imax>imin)-(imax<imin)
            body=math.log(rows[-1]["close"]/rows[0]["open"])
            old=(body>0)-(body<0)
            if new==0:reason="SAME_BAR_EXTREMA_ABSTAIN"
            elif old==0:reason="ZERO_BASELINE_ABSTAIN"
            else:
                for mm in (m,z):mm["eligible_pair"]+=1
                y,reason=label_at(bars,t)
                if y is not None:
                    a=new*y;b=old*y
                    for mm in (m,z):
                        mm["supported"]+=1
                        mm["new_gross_sum_bps"]+=a
                        mm["baseline_gross_sum_bps"]+=b
                        mm["new_positive"]+=int(a>0)
                        mm["baseline_positive"]+=int(b>0)
                    trials.append({"hour_index":j,"fixed_week":week,
                      "iso_week":tag,"new_direction":new,"baseline_direction":old,
                      "argmax_high_index":imax,"argmin_low_index":imin,
                      "response_reference_bps":y,"new_gross_reference_bps":a,
                      "baseline_gross_reference_bps":b})
        for mm in (m,z):bump(mm,reason)
    assert all(m["calendar"]==42 and sum(m["reason_counts"].values())==42 for m in weeks)
    return {"four_weeks":weeks,"iso_utc":iso,"trials":trials}

def merge(values):
    out=empty()
    for m in values:
        for k in ("calendar","eligible_pair","supported","new_gross_sum_bps",
                  "baseline_gross_sum_bps","new_positive","baseline_positive"):
            out[k]+=m[k]
        for k,v in m["reason_counts"].items():
            out["reason_counts"][k]=out["reason_counts"].get(k,0)+v
    s=out["supported"]
    out["new_mean_reference_bps"]=out["new_gross_sum_bps"]/s if s else None
    out["baseline_mean_reference_bps"]=out["baseline_gross_sum_bps"]/s if s else None
    out["paired_increment_reference_bps"]=(out["new_gross_sum_bps"]-out["baseline_gross_sum_bps"])/s if s else None
    out["new_mean_minus_flat_bps_sensitivity"]={str(c):(out["new_gross_sum_bps"]/s-c if s else None) for c in (2,5,10)}
    out["cost_sensitivity_not_actual_net"]=True
    return out
