"""Reproduce exact preARM fixture-9 failure and capture traceback locals only.
No certification seed, no retry, no changed numerical path.
"""
from pathlib import Path
import json,hashlib,sys,traceback
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P))
import reference_route_v1 as r
import stochastic_worker_v1 as w

def safe(v):
    import numpy as np
    if isinstance(v,np.ndarray):
        return v.tolist()
    if isinstance(v,(str,int,float,bool)) or v is None:
        return v
    if isinstance(v,dict):
        return {str(k):safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):
        return [safe(x) for x in v]
    return repr(v)

out={
  "schema":"TRIAD_V7_EXACT_FAILED_ENGINEERING_FIXTURE_FORENSIC_V1",
  "fixture_id":9,"case_id":9,"case_name":"BASELINE_REGIME_DRIFT",
  "phase":"null","engineering_index":0,
  "engineering_namespace_sha256":w.sha(P/"PREARM_PLAN_V1.json"),
  "certification_seed_usage":False,
  "failure_preserved":False
}
try:
    r.engineering_one((9,"null",0,True))
except Exception as e:
    out["exception_type"]=type(e).__name__
    out["reason"]=str(e)
    out["failure_preserved"]=(type(e).__name__=="NumericalUnavailable" and str(e)=="CANDIDATE_FAIL_CLOSED")
    tb=e.__traceback__
    frames=[]
    while tb:
        f=tb.tb_frame
        rec={"function":f.f_code.co_name,"file":f.f_code.co_filename,"line":tb.tb_lineno}
        if f.f_code.co_name=="trial" and f.f_code.co_filename.endswith("stochastic_worker_v1.py"):
            if "config" in f.f_locals:
                cfg=f.f_locals["config"]
                rec["configuration_id"]=safe(cfg.get("id"))
                rec["configuration_name"]=safe(cfg.get("name")) if "name" in cfg else None
                rec["delta"]=safe(cfg.get("delta"))
            for k in ["mode","case_id","index"]:
                if k in f.f_locals: rec[k]=safe(f.f_locals[k])
            out["trial_context"]={
                "configuration_id":rec.get("configuration_id"),
                "configuration_name":rec.get("configuration_name"),
                "delta":rec.get("delta"),
                "phase":rec.get("mode"),
                "case_id":rec.get("case_id"),
                "engineering_trial_index":rec.get("index")
            }
        if f.f_code.co_name=="clock_fits":
            for k in ["day","k","q","c","target","ids","declared","X","D","keep"]:
                if k in f.f_locals: rec[k]=safe(f.f_locals[k])
            if "target" in f.f_locals and "keep" in f.f_locals:
                rec["full_or_leaveout"]="leaveout"
                rec["excluded_target"]=safe(f.f_locals["target"])
        if f.f_code.co_name=="__call__" and f.f_code.co_filename.endswith("stochastic_worker_v1.py"):
            for k in ["X","D","c","support","out"]:
                if k in f.f_locals: rec[k]=safe(f.f_locals[k])
        frames.append(rec);tb=tb.tb_next
    out["traceback_frames"]=frames
    required=out.get("trial_context",{})
    assert required.get("configuration_id") is not None
    assert required.get("delta") is not None
    assert required.get("phase")=="null"
    assert required.get("case_id")==9
    assert required.get("engineering_trial_index")==0
    if not out["failure_preserved"]: raise
else:
    raise AssertionError("EXPECTED_FAILURE_NOT_REPRODUCED")
Path(sys.argv[1]).write_bytes(w.canonical(out))
print(json.dumps({"failure_preserved":out["failure_preserved"],"reason":out["reason"],"trial_context":out["trial_context"]},sort_keys=True))
