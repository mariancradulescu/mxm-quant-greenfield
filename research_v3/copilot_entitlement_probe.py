"""Exactly-once availability probe for the Actions Copilot credential."""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from research_v3.runtime_v2_primitives import atomic_write_json, load_json, iso

PROBE_REL=Path("research_v3/ai_director/PRO_ENTITLEMENT_PROBE_V1.json")
RECOVERY_REL=Path("research_v3/ai_director/PROVIDER_RECOVERY_STATE.json")
USAGE_REL=Path("research_v3/ai_director/PROVIDER_USAGE_V1.json")
PROBE_ID="2026-09-25-COPILOT-PRO-ENTITLEMENT-01"
REPLY="MXM_COPILOT_PROBE_OK"

def prepare(root:Path, run_id:str)->dict:
    path=root/PROBE_REL
    if path.exists():
        return {"action":"SKIP_ALREADY_PREPARED","record":load_json(path,{})}
    prior=load_json(root/RECOVERY_REL,{}) or {}
    doc={"schema":"mxm.greenfield.copilot-entitlement-probe.v1",
         "probe_id":PROBE_ID,"status":"PREPARED_UNCONSUMED",
         "actions_run_id":run_id,"provider":"github-copilot-cli",
         "requested_model":"auto","credential_source":"GitHub Actions github.token",
         "previous_quota_status":prior.get("status"),
         "previous_quota_failures":prior.get("consecutive_recoverable_failures"),
         "created_utc":iso(),"economic_outcomes_opened_delta":0,
         "v2_attempts_consumed_delta":0}
    atomic_write_json(path,doc)
    return {"action":"PREPARED_MUST_PERSIST_BEFORE_EXECUTE","record":doc}

def _record_usage(root:Path,outcome:str)->None:
    doc=dict(load_json(root/USAGE_REL,{}) or {})
    rows=list(doc.get("invocations") or [])
    rows.append({"timestamp":iso(),"provider":"github-copilot-cli",
                 "model_requested":"auto","actual_model_identity":None,
                 "actual_credit_usage":None,"request_fingerprint":PROBE_ID,
                 "purpose":"PRO_ENTITLEMENT_AVAILABILITY_PROBE",
                 "evidence_epoch":20,"outcome":outcome,
                 "retryable":False,"material_state_advancement":False})
    doc.update({"schema":"mxm.greenfield.provider-usage.v1",
                "provider_invocations":len(rows),
                "quota_failures":sum(x.get("outcome")=="PROVIDER_UNAVAILABLE" for x in rows),
                "invocations":rows})
    atomic_write_json(root/USAGE_REL,doc)

def execute(root:Path, run_id:str, token:str, transport=None)->dict:
    path=root/PROBE_REL
    doc=dict(load_json(path,{}) or {})
    if doc.get("probe_id")!=PROBE_ID or doc.get("actions_run_id")!=run_id:
        raise RuntimeError("Probe identity/run mismatch; refuse provider call")
    if doc.get("status")!="CLAIMED_CALL_CONSUMED":
        return {"action":"SKIP_PROBE_NOT_CLAIMED_OR_ALREADY_FINISHED","record":doc}
    if transport is None and os.environ.get("MXM_PROBE_CLAIM_PERSISTED")!="1":
        raise RuntimeError("Durable provider-call claim not confirmed")
    if not token or (not shutil.which("copilot") and transport is None):
        raise RuntimeError("Actions credential or Copilot CLI unavailable before probe")
    cmd=["copilot","-p","Reply with exactly "+REPLY+" and nothing else.",
         "-s","--model=auto","--no-ask-user","--no-auto-update",
         "--no-color","--no-custom-instructions",
         "--deny-tool=shell","--deny-tool=write","--deny-tool=url"]
    env=dict(os.environ)
    env["GITHUB_TOKEN"]=token
    env["COPILOT_GITHUB_TOKEN"]=token
    if transport is None:
        try:
            result=subprocess.run(cmd,cwd=root,env=env,text=True,capture_output=True,timeout=120)
            code,stdout,stderr=result.returncode,result.stdout,result.stderr
        except subprocess.TimeoutExpired:
            code,stdout,stderr=124,"","timeout"
    else:
        code,stdout,stderr=transport()
    detail=(stderr+"\n"+stdout).lower()
    if code==0 and stdout.strip()==REPLY:
        status="AVAILABLE"
    elif "monthly quota" in detail or "exceeded your quota" in detail:
        status="PROVIDER_UNAVAILABLE"
    elif any(x in detail for x in ("unauthorized","forbidden","not entitled","authentication","permission","403","401")):
        status="AUTH_OR_ENTITLEMENT_FAILURE"
    else:
        status="PROBE_INCONCLUSIVE"
    doc.update({"status":status,"completed_utc":iso(),"process_exit_code":code,
                "provider_call_count":1,"response_marker_seen":stdout.strip()==REPLY,
                "raw_provider_output_persisted":False})
    atomic_write_json(path,doc)
    _record_usage(root,status)
    recovery=dict(load_json(root/RECOVERY_REL,{}) or {})
    recovery["probe_ref"]=str(PROBE_REL)
    recovery["entitlement_change"]="FREE_TO_PRO_USER_REPORTED"
    recovery["updated_utc"]=iso()
    if status=="AVAILABLE":
        recovery["status"]="PROVIDER_AVAILABLE_AFTER_ENTITLEMENT_PROBE"
        recovery["failure_class"]=None
        recovery["consecutive_recoverable_failures"]=0
        recovery["retry_policy"]="MATERIAL_DECISION_GATE_ONLY"
    else:
        recovery["status"]="PROVIDER_UNAVAILABLE" if status=="PROVIDER_UNAVAILABLE" else "AUTH_OR_ENTITLEMENT_FAILURE"
        recovery["failure_class"]=status
        recovery["retry_policy"]="NO_AUTOMATIC_RETRY"
    atomic_write_json(root/RECOVERY_REL,recovery)
    return {"action":"ONE_PROVIDER_CALL_COMPLETED","status":status,"record":doc}

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=("prepare","claim","execute"))
    p.add_argument("--root",default=".")
    p.add_argument("--run-id",required=True)
    args=p.parse_args()
    root=Path(args.root).resolve()
    if args.command=="prepare":
        out=prepare(root,args.run_id)
    elif args.command=="claim":
        path=root/PROBE_REL
        doc=dict(load_json(path,{}) or {})
        if doc.get("actions_run_id")!=args.run_id or doc.get("status")!="PREPARED_UNCONSUMED":
            raise RuntimeError("Probe cannot be claimed again")
        doc["status"]="CLAIMED_CALL_CONSUMED"
        doc["claimed_utc"]=iso()
        atomic_write_json(path,doc)
        out={"action":"CLAIMED_MUST_PERSIST_BEFORE_PROVIDER_CALL"}
    else:
        out=execute(root,args.run_id,os.environ.get("GITHUB_TOKEN",""))
    print(json.dumps(out,sort_keys=True))

if __name__=="__main__":
    main()
