"""Noncircular exact DEVELOPMENT authority. No authorization is minted here.

An independent acceptance is a separate, later Git artifact. Its introduction
commit may change only that approval, never the bound implementation or ARM.
This enforces artifact separation; independence of the human audit remains a
governance assertion, not an invented cryptographic identity certificate.
"""
import hashlib
import json
import pathlib
import re
import subprocess
from datetime import datetime, timezone
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n

ROOT=old.ROOT
PREFIX="research_core_v4/numeric_development_v2/"
ARM=PREFIX+"EXACT_REAL_DEVELOPMENT_ARM_CANDIDATE_V2.json"
APPROVAL=PREFIX+"INDEPENDENT_ACCEPTANCE_V2.json"
RECOVERY=PREFIX+"INDEPENDENT_RECOVERY_ACCEPTANCE_V2.json"
BINDINGS=PREFIX+"VERSIONED_SOURCE_SHA256_MANIFEST_V2.json"
EXPERIMENT="MASTER1576_HOURLY_PRICE_ACTIVITY_COUPLING_DIRECTIONAL_RESPONSE_V1"
SCOPE={"experiment":EXPERIMENT,"purpose":"DESCRIPTIVE_GROSS_DEVELOPMENT_ONLY",
       "identities":1576,"assets":100,"historical_rows":3355389,
       "start_UTC":"2026-08-20T00:00:00Z","end_exclusive_UTC":"2026-09-17T00:00:00Z",
       "lags_seconds":[0,300,900],"response_horizon_seconds":3600,
       "attempts":1,"automatic_retries":0,"broker_requests":0,
       "protected_forward":False,"new_alpha":False,"live_orders":False}
BUDGET={"wall_seconds":3600,"cpu_seconds":7200,"ram_kib":8388608,"workers":1}
REAL_WORKFLOW=".github/workflows/mxm-master1576-real-numeric-v2.yml"

def need(ok,code):old.need(ok,code)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def enc(x):return n.enc(x)
def read(path):return json.loads((ROOT/path).read_bytes())
def digest(path):return sha((ROOT/path).read_bytes())
def git(*args):
    try:return subprocess.check_output(["git",*args],cwd=ROOT,stderr=subprocess.DEVNULL)
    except Exception:raise n.NumericalStop("GIT_ANCESTRY_OR_SOURCE") from None
def ancestor(a,b):
    need(re.fullmatch("[0-9a-f]{40}",a or "") and re.fullmatch("[0-9a-f]{40}",b or ""),"HEAD_FORMAT")
    git("merge-base","--is-ancestor",a,b)
def exact_document(x,keys,code):need(type(x) is dict and set(x)==set(keys),code)
def verify_bindings(source,head,bindings):
    ancestor(source,head)
    need(bindings==read(BINDINGS)["bindings"],"BINDING_MANIFEST_DRIFT")
    need(len(bindings)>=15 and old.WORKER_PATH in bindings and old.GUARD_PATH in bindings,
         "SOURCE_BINDING_INCOMPLETE")
    for path,expected in bindings.items():
        need(re.fullmatch("[0-9a-f]{64}",expected or "") is not None,"SHA_FORMAT")
        need(digest(path)==expected and sha(git("show",source+":"+path))==expected,
             "BOUND_SOURCE_DRIFT")
    need(sha(git("show",source+":"+BINDINGS))==digest(BINDINGS),"MANIFEST_PARENT_DRIFT")
def candidate(source,bindings):
    return {"schema":"mxm.numeric.arm.v2","status":"CANDIDATE_NOT_AUTHORIZED",
      "mode":"real","source_head":source,"scope":SCOPE,"budget":BUDGET,
      "bindings":bindings,"manifest_sha256":n.MANIFEST_SHA,"design_sha256":n.DESIGN_SHA,
      "kernel_sha256":n.KERNEL_SHA,"key_spki_sha256":old.FP,
      "invocation_id":sha(enc({"experiment":EXPERIMENT,"design":n.DESIGN_SHA,"data":n.MANIFEST_SHA})),
      "expires_UTC":"2026-10-16T23:59:59Z"}
def validate(arm,approval,head,mode,arm_raw,*,artifacts=True):
    exact_document(arm,candidate("",{}).keys(),"ARM_FIELDS")
    need(arm["schema"]=="mxm.numeric.arm.v2" and arm["status"]=="CANDIDATE_NOT_AUTHORIZED"
         and arm["mode"]==mode,"ARM_STATUS_OR_MODE")
    need(enc(arm["scope"])==enc(SCOPE) and enc(arm["budget"])==enc(BUDGET),"ARM_SCOPE")
    need(arm["manifest_sha256"]==n.MANIFEST_SHA and arm["design_sha256"]==n.DESIGN_SHA
         and arm["kernel_sha256"]==n.KERNEL_SHA and arm["key_spki_sha256"]==old.FP,"ARM_SCIENCE")
    need(arm["invocation_id"]==candidate("",{})["invocation_id"],"EXPERIMENT_ID_DRIFT")
    try:expires=datetime.strptime(arm["expires_UTC"],"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:raise n.NumericalStop("EXPIRY_FORMAT") from None
    need(datetime.now(timezone.utc)<=expires,"STALE_ARM")
    exact_document(approval,{"schema","status","mode","role","arm_sha256","source_head",
                            "arm_commit","audit_receipt_sha256","explicit_acceptance"},"APPROVAL_FIELDS")
    need(approval["schema"]=="mxm.numeric.independent.acceptance.v2" and
         approval["status"]=="INDEPENDENT_ACCEPTANCE_PASS" and approval["mode"]==mode and
         approval["role"]==("INDEPENDENT_AUDITOR" if mode=="real" else "FABRICATED_TEST_AUTHORITY") and
         approval["explicit_acceptance"] is True,"INDEPENDENT_APPROVAL_REQUIRED")
    need(approval["arm_sha256"]==sha(arm_raw) and approval["source_head"]==arm["source_head"]
         and re.fullmatch("[0-9a-f]{64}",approval["audit_receipt_sha256"] or ""),"APPROVAL_BINDING")
    verify_bindings(arm["source_head"],head,arm["bindings"])
    if artifacts:
        ac=approval["arm_commit"];ancestor(arm["source_head"],ac);ancestor(ac,head)
        need(sha(git("show",ac+":"+ARM))==sha(arm_raw),"ARM_COMMIT_BINDING")
        pc=git("log","-1","--format=%H",head,"--",APPROVAL).decode().strip()
        need(pc not in (arm["source_head"],ac),"APPROVAL_SEPARATION")
        ancestor(ac,pc)
        changed=git("diff-tree","--no-commit-id","--name-only","-r",pc).decode().splitlines()
        need(changed==[APPROVAL] and git("rev-list","--parents","-n","1",pc).decode().count(" ")==1,
             "APPROVAL_COMMIT_MUST_BE_SEPARATE")
    return arm
def real_gate(head):
    need((ROOT/ARM).is_file() and (ROOT/APPROVAL).is_file(),"MISSING_INDEPENDENT_APPROVAL")
    arm=read(ARM);approval=read(APPROVAL)
    need((ROOT/ARM).read_bytes()==enc(arm),"ARM_CANONICAL_BYTES")
    return validate(arm,approval,head,"real",(ROOT/ARM).read_bytes())
def recovery_gate(auth,arm,approval_sha,previous_run,checkpoint):
    exact_document(auth,{"schema","status","mode","role","arm_sha256","approval_sha256",
      "invocation_id","previous_run_id","checkpoint_receipt_sha256","next_shard","attempts",
      "automatic_retries","explicit_acceptance","previous_resource_ceiling"},"RECOVERY_FIELDS")
    need(auth["schema"]=="mxm.numeric.recovery.acceptance.v2" and auth["status"]=="AUTHORIZED_ONE_RECOVERY"
      and auth["role"]==("INDEPENDENT_AUDITOR" if arm["mode"]=="real" else "FABRICATED_TEST_AUTHORITY")
      and auth["mode"]==arm["mode"] and auth["explicit_acceptance"] is True,"RECOVERY_APPROVAL")
    need(auth["arm_sha256"]==sha(enc(arm)) and auth["approval_sha256"]==approval_sha
      and auth["invocation_id"]==arm["invocation_id"] and auth["previous_run_id"]==previous_run
      and auth["checkpoint_receipt_sha256"]==checkpoint["encrypted_artifact_sha256"]
      and type(auth["next_shard"]) is int and auth["next_shard"] in (25,50,75,100)
      and type(auth["attempts"]) is int and auth["attempts"]==1
      and type(auth["automatic_retries"]) is int and auth["automatic_retries"]==0,"RECOVERY_BINDING")
    ceiling=auth["previous_resource_ceiling"]
    need(type(ceiling) is dict and set(ceiling)=={"wall_seconds","cpu_seconds"},"RECOVERY_BUDGET_FIELDS")
    need(all(type(ceiling[k]) in (int,float) and 0<=ceiling[k]<BUDGET[k] for k in ceiling),"RECOVERY_BUDGET")

def preflight_inventory(manifest,entries):
    """All release metadata checks precede the one-use claim and data opening."""
    acceptance=read("research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_CAMPAIGN_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json")
    expected=acceptance["exact_release_inventory"]
    release=old.api("releases/tags/"+manifest["DURABLE_RELEASE_IDENTITY"])
    need(release["id"]==expected["release_id"] and json.loads(release["body"])==expected["body"],"INPUT_RELEASE_DRIFT")
    assets=old.api("releases/"+str(release["id"])+"/assets?per_page=100&page=1")
    need(len(assets)==100 and old.api("releases/"+str(release["id"])+"/assets?per_page=100&page=2")==[],"INPUT_ASSET_COUNT")
    names={a["name"]:a for a in assets};need(len(names)==100 and len(expected["assets"])==100,"INPUT_ASSET_UNIQUENESS")
    for x in expected["assets"]:
        need(x["name"] in names and all(names[x["name"]].get(k)==v for k,v in x.items()),"INPUT_ASSET_METADATA_DRIFT")
    need(set(names)=={e["ENCRYPTED_ASSET_NAME"] for e in entries},"MANIFEST_ASSET_NAMES")
    for e in entries:
        a=names[e["ENCRYPTED_ASSET_NAME"]]
        need(a["digest"]=="sha256:"+e["ENCRYPTED_ASSET_SHA256"] and 0<a["size"]<128*1024*1024,
             "INPUT_CIPHER_SHA_OR_SIZE")
    return names

def real_event_gate():
    """Real authority is usable only through the exact bound machine workflow."""
    import os
    need(os.environ.get("GITHUB_EVENT_NAME") in ("push","workflow_dispatch") and
         os.environ.get("GITHUB_WORKFLOW_REF")==old.REPO+"/"+REAL_WORKFLOW+"@refs/heads/"+old.BRANCH,
         "REAL_WORKFLOW_EVENT_BINDING")

def stopped_original_preflight(arm,previous):
    """A real recovery must never race a still-running original Actions job."""
    need(type(previous) is int and previous>0,"PREVIOUS_RUN_FORMAT")
    name="mxm-numeric-v2-claim-real-"+arm["invocation_id"]
    refs=old.api("git/matching-refs/tags/"+name)
    matches=[r for r in refs if r["ref"]=="refs/tags/"+name]
    need(len(matches)==1,"ORIGINAL_INVOCATION_NOT_CLAIMED")
    run=old.api("actions/runs/"+str(previous))
    need(run["id"]==previous and run["head_sha"]==matches[0]["object"]["sha"] and
         run["run_attempt"]==1 and run["path"]==REAL_WORKFLOW and
         run["status"]=="completed" and run["conclusion"] in ("failure","cancelled","timed_out"),
         "ORIGINAL_RUN_MUST_BE_STOPPED_AND_FAILED")
