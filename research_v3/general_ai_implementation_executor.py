"""Generic general-AI implementation continuation for non-economic research states.

The AI chooses implementation. This module supplies bounded file tooling and deterministic
postconditions; it intentionally contains no next_action -> script mapping.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess
from pathlib import Path
from typing import Any, Mapping
from research_v3.evidence_eligibility import validate_eligibility, EvidenceIneligible
from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.evidence_epoch import stale_reasoning_redirect
from research_v3.general_ai_director_bridge import NEXT_STATE_REL, project_snapshot, proposal_hash
from research_v3.general_ai_reasoning_provider import reasoning_required
from research_v3.runtime_v2_primitives import GitCheckpointSink, atomic_write_json, canonical_bytes, iso, load_json, sha256_bytes, sha256_file

VERSION="MXM_GENERAL_AI_IMPLEMENTATION_EXECUTOR_V2"
REQUEST_REL=Path("research_v3/ai_director/IMPLEMENTATION_REQUEST.json")
RESPONSE_REL=Path("research_v3/ai_director/IMPLEMENTATION_RESPONSE.json")
GATE_REL=Path("research_v3/ai_director/IMPLEMENTATION_EXTERNAL_GATE.json")
DEFAULT_MODEL="auto"
FOUR_PANEL_OUTER_SCHEMA="mxm.greenfield.session-gap-frontier-four-panel-independent-outer-capture-plan.v1"
FOUR_PANEL_OUTER_FIELDS=["time_utc","open","high","low","close","tick_volume","historical_bid_ask_friction_summary","historical_conversion_summary"]
FOUR_PANEL_OUTER_ACQUISITION_FIELDS=["timestamp","open","high","low","close","volume","bid","ask","broker_native_commission_or_cost_metadata"]
FOUR_PANEL_OUTER_OUTPUT="MXM_SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_M5_13W_FRICTION_V1.zip"
PROTECTED_PREFIXES=(
    "CURRENT_STATE.json","V2_SEARCH_BUDGET_V1.json","V2_PROTECTED_FORWARD_START.json",
    "discovery/ledger.jsonl","m6/results/","research_v3/runtime_v2/",
    "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json",
    "research_v3/ai_director/PROPOSAL_REGISTRY_V1.json","research_v3/ai_director/proposals/",
    ".github/workflows/",
)

class ImplementationRejected(RuntimeError): pass

def _head(root:Path)->str:
    return subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()

def _next(root:Path)->dict[str,Any]:
    return dict(load_json(root/NEXT_STATE_REL,{}) or {})

def implementation_required(next_state:Mapping[str,Any],root_value:str|Path=".")->bool:
    """Compatibility wrapper around the explicit authority router.

    next_action alone is never authority to spend an AI implementation call.
    """
    return routed_implementation_required(Path(root_value).resolve(),next_state)

def authoritative_reasoning_requirement(root:Path,next_state:Mapping[str,Any])->dict[str,Any]|None:
    """Return a generic reasoning redirect when an authoritative freeze forbids execution before a prerequisite."""
    rel=next_state.get("source_freeze_ref") or next_state.get("freeze_ref")
    if not isinstance(rel,str) or not rel:
        return None
    path=root/rel
    if not path.is_file():
        return None
    try:
        freeze=json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    contract=freeze.get("independent_outer_contract")
    if not isinstance(contract,Mapping) or contract.get("required") is not True:
        return None
    binding=next_state.get("outer_data_binding_ref") or next_state.get("independent_outer_data_ref")
    if binding:
        return None
    step=str(contract.get("next_step") or "").strip()
    if not step:
        raise ImplementationRejected("authoritative independent-outer contract has no next_step")
    return {
        "status":"AI_REASONING_REQUIRED_BY_AUTHORITATIVE_DATA_CONTRACT",
        "next_action":step,
        "ai_reasoning_required":True,
        "authoritative_freeze_ref":rel,
        "reason":"Authoritative freeze requires an unopened disjoint outer-data decision/binding before any executable outer screen.",
        "user_action_required":False,
    }

def exact_head_green(root:Path)->dict[str,Any]:
    observed=_head(root)
    expected=os.environ.get("MXM_PREDECESSOR_CI_HEAD","").strip()
    conclusion=os.environ.get("MXM_PREDECESSOR_CI_CONCLUSION","").strip().lower()
    run_id=os.environ.get("MXM_PREDECESSOR_CI_RUN_ID","").strip()
    return {"green":bool(expected and conclusion=="success" and expected==observed),"head":observed,
            "predecessor_head":expected or None,"predecessor_conclusion":conclusion or None,
            "predecessor_run_id":int(run_id) if run_id.isdigit() else None}

def _tree_digest(root:Path,rel:str)->str:
    p=root/rel
    if not p.exists(): return "MISSING"
    if p.is_file(): return sha256_file(p)
    rows=[]
    for f in sorted(x for x in p.rglob("*") if x.is_file()):
        rows.append({"path":str(f.relative_to(root)),"sha256":sha256_file(f)})
    return sha256_bytes(canonical_bytes(rows))

def protected_snapshot(root:Path)->dict[str,str]:
    return {rel:_tree_digest(root,rel) for rel in PROTECTED_PREFIXES}

def _changed_paths(root:Path)->list[str]:
    raw=subprocess.check_output(["git","status","--porcelain=v1","-z"],cwd=root)
    parts=[x for x in raw.decode("utf-8",errors="replace").split("\0") if x]
    out=[]
    for item in parts:
        path=item[3:] if len(item)>=4 else item
        if " -> " in path: path=path.split(" -> ",1)[1]
        out.append(path.replace("\\","/"))
    return sorted(set(out))

def _is_protected(path:str)->bool:
    p=path.replace("\\","/")
    return any(p==x.rstrip("/") or p.startswith(x) for x in PROTECTED_PREFIXES)

def _restore(root:Path)->None:
    subprocess.run(["git","reset","--hard","HEAD"],cwd=root,check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(["git","clean","-fd"],cwd=root,check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def _extract_json(text:str)->dict[str,Any]:
    s=text.strip(); fence=chr(96)*3
    if s.startswith(fence):
        s=s.split("\n",1)[1] if "\n" in s else s
        if s.endswith(fence): s=s[:-3]
    try: obj=json.loads(s)
    except Exception:
        a=s.find("{"); b=s.rfind("}")
        if a<0 or b<=a: raise ImplementationRejected("implementation agent returned no JSON object")
        obj=json.loads(s[a:b+1])
    if not isinstance(obj,dict): raise ImplementationRejected("implementation response must be object")
    return obj

def _resolve_current_proposal(root:Path,next_state:Mapping[str,Any])->tuple[str,dict[str,Any],dict[str,Any]]:
    proposal_id=str(next_state.get("source_ai_proposal_id") or "").strip()
    proposal_hash_hint=str(next_state.get("source_ai_proposal_hash") or "").strip()
    operation_id=str(next_state.get("source_runtime_operation_id") or "").strip()
    if not proposal_id and not proposal_hash_hint and not operation_id:
        raise ImplementationRejected("implementation state is not bound to an accepted AI proposal")
    registry=load_json(root/"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json",{}) or {}
    matches=[]
    for raw in list(registry.get("accepted") or []):
        row=dict(raw)
        if proposal_id and row.get("proposal_id")!=proposal_id:
            continue
        if proposal_hash_hint and row.get("proposal_hash")!=proposal_hash_hint:
            continue
        if operation_id and row.get("operation_id")!=operation_id:
            continue
        matches.append(row)
    if len(matches)!=1:
        raise ImplementationRejected(f"durable state must resolve exactly one accepted AI proposal; got {len(matches)}")
    row=matches[0]
    if row.get("economic_outcome_opened") is not False or int(row.get("v2_attempt_consumed",-1))!=0:
        raise ImplementationRejected("implementation source proposal must be non-economic")
    proposal_ref=str(row.get("proposal_ref") or "").strip()
    if not proposal_ref or not (root/proposal_ref).is_file():
        raise ImplementationRejected("accepted proposal_ref missing")
    proposal=dict(load_json(root/proposal_ref,{}) or {})
    observed=proposal_hash(proposal)
    if observed!=row.get("proposal_hash"):
        raise ImplementationRejected("accepted implementation proposal hash drift")
    if proposal_id and proposal.get("proposal_id")!=proposal_id:
        raise ImplementationRejected("accepted implementation proposal_id drift")
    if proposal_hash_hint and observed!=proposal_hash_hint:
        raise ImplementationRejected("durable state proposal hash drift")
    return proposal_ref,proposal,row

def _bound_context(root:Path,next_state:Mapping[str,Any],proposal:Mapping[str,Any])->dict[str,Any]:
    refs=[]
    for rel in list(proposal.get("authority_refs") or []):
        if isinstance(rel,str):
            refs.append(rel)
    for key in ("result_ref","capture_acceptance_ref","structural_screen_freeze_ref","freeze_ref",
                "completed_capture_plan_ref","completed_capture_ref","completed_structural_report_ref",
                "duplicate_capture_supersession_ref"):
        rel=next_state.get(key)
        if isinstance(rel,str):
            refs.append(rel)
    docs={}
    for rel in sorted(set(refs)):
        p=root/rel
        if not p.is_file() or p.stat().st_size>500_000:
            continue
        try:
            raw=p.read_bytes()
            doc=json.loads(raw)
            if len(raw)>3000:
                docs[rel]={
                    "sha256":sha256_bytes(raw),
                    "content_summary":{
                        "schema":doc.get("schema"),"status":doc.get("status"),
                        "byte_length":len(raw),"available_via_repository_view":True,
                        "top_level_keys":list(doc)[:24],
                    },
                }
            else:
                docs[rel]=doc
        except Exception:
            pass
    return docs

def _post_green_output(out:Mapping[str,Any],changed_paths:list[str])->dict[str,Any]:
    payload=json.loads(json.dumps(out))
    ns=dict(payload.get("next_research_state") or {})
    if str(ns.get("status") or "").startswith("PENDING_EXACT_HEAD_GREEN"):
        payload["next_research_state"]={
            "status":"AI_REASONING_REQUIRED_AFTER_IMPLEMENTATION_GREEN",
            "next_action":"AI_INTERPRET_NEWLY_GREEN_NON_ECONOMIC_IMPLEMENTATION_AND_CHOOSE_HIGHEST_INFORMATION_LEGAL_NEXT_ACTION",
            "ai_reasoning_required":True,
            "green_implementation_artifacts":list(changed_paths),
        }
    return payload

def _prompt(root:Path,next_state:Mapping[str,Any])->str:
    proposal_ref,proposal,registry_row=_resolve_current_proposal(root,next_state)
    bound_context=_bound_context(root,next_state,proposal)
    return """You are the GENERAL AI IMPLEMENTATION DIRECTOR for MXM Quant Greenfield V2.
Implement the current valid NON_ECONOMIC research decision generically. There is NO finite next_action mapping.
Inspect the repository with file view/search tools and decide whether implementation is already sufficient,
whether code/tests/manifests need edits, or whether a genuine external data dependency remains.

You MAY edit/create non-economic code, tests, prospective manifests and new evidence. You MUST NOT modify:
CURRENT_STATE/accounting, discovery ledger, Runtime V2 ledgers/journals/closures/results, m6/results, accepted AI
proposals/registry, protected-forward authority, search budget, GitHub workflows, or any economic result.
Do not create a candidate economic identity, open economics, authorize live orders, open protected evidence,
or rerun C031 Stage-B. Do not use network or shell tools. Do not ask the human to choose research parameters.

Authoritative prospective freezes override an older proposal when they impose a stricter causal/data prerequisite.
Never execute on source/development bytes if a bound freeze requires unopened disjoint outer data.
If repository files already implement the selected action or exact collector, do not rewrite them. Validate by inspection.
An existing collector for a different frozen symbol/window scope does NOT implement this proposal.
Before creating a new capture gate, verify existing accepted cTrader-derived repository and
hash-bound Library artifacts against each requested symbol/window; acquire only a justified missing
increment, and do not describe an already accepted capture as unavailable merely because its bytes
are external to the Git repository.
For any external data gate, build and test a collector for the accepted proposal's exact broker-native
symbols, resolution, interval, and fields; bind collector_plan_ref and output filename to that new plan.
Historical cTrader trendbars expose a single OHLC and tick volume, not separate bid and ask OHLC.
If the proposal requests bid/ask bars or spread, use exact historical bid and ask tick data with
complete pagination and explicit alignment, or fail closed and return to AI reasoning for a
prospective data-scope correction. Never label single-price bars as bid/ask or invent spreads.
The previously accepted C031 twelve-symbol extension has already been captured and structurally
screened; its collector must never be used to satisfy a different twelve-symbol proposal.
If external authenticated market bytes are genuinely required, return EXTERNAL_DATA_REQUIRED and bind the existing
exact-scope collector build reference/artifact. The human's only permitted role is to run the read-only collector and upload
its returned ZIP to the GPT/Director chat; never tell the human to modify GitHub.

Return ONE JSON object only:
{
 "implementation_id":"...",
 "status":"COMPLETE_NON_ECONOMIC|EXTERNAL_DATA_REQUIRED|IMPLEMENTATION_CHANGED_REQUIRES_EXACT_HEAD_GREEN",
 "summary":"...",
 "decision":{},
 "next_research_state":{"status":"...","next_action":"..."},
  "external_data_gate": null OR {
    "reason":"...",
    "collector_build_ref":"...",
    "collector_plan_ref":"...",
   "collector_package_artifact_name":"...",
   "expected_return_artifact_name":"..."
 },
 "tests_requested":["..."]
}
No chain-of-thought.

CURRENT_NEXT_STATE:
"""+json.dumps(next_state,sort_keys=True,indent=2)+"\n\nBOUND_ACCEPTED_PROPOSAL_REF:\n"+proposal_ref+"\n\nBOUND_ACCEPTED_AI_DECISION:\n"+json.dumps(proposal,sort_keys=True,indent=2)+"\n\nBOUND_ACCEPTED_REGISTRY_ROW:\n"+json.dumps(registry_row,sort_keys=True,indent=2)+"\n\nBOUND_REPOSITORY_CONTEXT:\n"+json.dumps(bound_context,sort_keys=True,indent=2)

def _transport(root:Path,prompt:str,token:str,model:str)->tuple[dict[str,Any],dict[str,Any]]:
    if not shutil.which("copilot"): raise ImplementationRejected("GitHub Copilot CLI executable missing")
    cmd=["copilot","-p",prompt,"-s","--model="+model,"--no-ask-user","--no-auto-update","--no-color","--no-custom-instructions",
         "--available-tools=view,grep,glob,edit,create,apply_patch","--allow-tool=read","--allow-tool=write"]
    for rel in PROTECTED_PREFIXES:
        cmd.append("--deny-tool=write("+rel.rstrip("/")+")")
    env=dict(os.environ); env["GITHUB_TOKEN"]=token; env["COPILOT_GITHUB_TOKEN"]=token
    p=subprocess.run(cmd,cwd=root,env=env,text=True,capture_output=True,timeout=300)
    if p.returncode!=0: raise ImplementationRejected("Copilot implementation failed: "+(p.stderr+"\n"+p.stdout)[-2400:])
    return _extract_json(p.stdout),{
        "provider":"github-copilot-cli","model":model,
        "model_selection":"AUTO_ACCOUNT_AVAILABLE" if model=="auto" else "EXPLICIT",
        "actual_model_identity":None if model=="auto" else model,
        "actual_model_identity_known":model!="auto",
        "model_identity_limitation":"Explicit gpt-5.3-codex and gpt-5.4 were rejected as unavailable by this Copilot connection; Auto is the proven available route, and silent mode does not expose the selected identity." if model=="auto" else None,
        "cli":"@github/copilot",
    }

def _collector_fields_match(plan:Mapping[str,Any],request_fields:Any)->bool:
    plan_fields=plan.get("fields")
    if plan.get("schema")==FOUR_PANEL_OUTER_SCHEMA and plan_fields is None:
        # The legacy frozen outer plan predates an explicit transferable fields key.
        # Its collector contract acquires single-price M5 trendbars plus exact historical
        # BID/ASK ticks and broker-native commission/conversion evidence, then transfers
        # OHLCV + compact friction/conversion summaries (never raw tick streams).
        return request_fields==FOUR_PANEL_OUTER_ACQUISITION_FIELDS
    return plan_fields==request_fields

def _validate_output(root:Path,out:Mapping[str,Any])->None:
    status=str(out.get("status") or "")
    if status not in {"COMPLETE_NON_ECONOMIC","EXTERNAL_DATA_REQUIRED","IMPLEMENTATION_CHANGED_REQUIRES_EXACT_HEAD_GREEN"}:
        raise ImplementationRejected("unsupported implementation status")
    ns=out.get("next_research_state")
    if not isinstance(ns,Mapping) or not str(ns.get("status") or "") or not str(ns.get("next_action") or ""):
        raise ImplementationRejected("implementation must supply next_research_state")
    forbidden={"accounting","safety","economic_outcomes_opened","v2_attempts_used","v2_search_budget_remaining",
               "protected_forward","live_orders","competition_start","competition_start_authorized","live_orders_authorized"}
    if forbidden.intersection(ns): raise ImplementationRejected("implementation next state attempts protected mutation")
    gate=out.get("external_data_gate")
    if status=="EXTERNAL_DATA_REQUIRED":
        if not isinstance(gate,Mapping): raise ImplementationRejected("external gate object required")
        build=str(gate.get("collector_build_ref") or "")
        if not build or not (root/build).is_file(): raise ImplementationRejected("external gate collector build ref missing")
        plan_ref=str(gate.get("collector_plan_ref") or "")
        if not plan_ref or not (root/plan_ref).is_file(): raise ImplementationRejected("external gate requires frozen collector_plan_ref")
        plan=load_json(root/plan_ref,{}) or {}
        _,proposal,_=_resolve_current_proposal(root,_next(root))
        request=(proposal.get("data_policy") or {}).get("minimal_acquisition_request") or {}
        if (proposal.get("data_policy") or {}).get("new_market_data_requested") is not True:
            raise ImplementationRejected("external gate lacks authorized broker-native data request")
        symbols=[x.get("broker_symbol") if isinstance(x,Mapping) else x for x in plan.get("symbols") or []]
        interval=plan.get("interval") or plan.get("outer_interval") or {}
        if (symbols!=request.get("symbols") or plan.get("resolution")!=request.get("resolution")
                or interval.get("start_utc")!=request.get("start_utc")
                or interval.get("end_utc")!=request.get("end_utc")):
            raise ImplementationRejected("collector plan does not match accepted AI proposal scope")
        if not _collector_fields_match(plan,request.get("fields")):
            raise ImplementationRejected("collector plan fields do not match accepted AI proposal scope")
        expected_output=plan.get("output_artifact_name")
        if expected_output is None and plan.get("schema")==FOUR_PANEL_OUTER_SCHEMA:
            expected_output=FOUR_PANEL_OUTER_OUTPUT
        if expected_output!=gate.get("expected_return_artifact_name"):
            raise ImplementationRejected("collector output artifact does not match frozen plan")
        if plan_ref not in (root/build).read_text(encoding="utf-8"):
            raise ImplementationRejected("collector build does not package the frozen AI plan")
        package=str(gate.get("collector_package_artifact_name") or "")
        returned=str(gate.get("expected_return_artifact_name") or "")
        if not package.endswith(".zip") or not returned.endswith(".zip"): raise ImplementationRejected("external gate ZIP names required")

def _publish_next(root:Path,out:Mapping[str,Any],before:Mapping[str,Any])->dict[str,Any]:
    doc=_next(root); doc.update(dict(out["next_research_state"]))
    doc.update({"schema":"mxm.greenfield.runtime-v2-next-autonomous-state.v3",
                "implementation_executor":VERSION,
                "source_implementation_id":out["implementation_id"],
                "accounting":{"v2_attempts_used":before["v2_attempts_used"],"v2_search_budget_remaining":before["v2_search_budget_remaining"],"economic_outcomes_opened":before["economic_outcomes_opened"]},
                "safety":{"protected_evidence_opened":False,"live_orders_authorized":False,"competition_start_authorized":False}})
    atomic_write_json(root/NEXT_STATE_REL,doc); return doc

def _publish_external_gate(root:Path,out:Mapping[str,Any],before:Mapping[str,Any])->dict[str,Any]:
    gate=dict(out["external_data_gate"])
    gate.update({"schema":"mxm.greenfield.general-ai-implementation-external-data-gate.v1",
                 "status":"EXTERNAL_DATA_REQUIRED","implementation_id":out["implementation_id"],
                 "created_utc":iso(),"economic_outcomes_opened":0,"v2_attempts_consumed":0,
                 "user_instruction":"Run the read-only collector package and upload the returned ZIP back into this GPT/Director chat. Do not modify GitHub."})
    atomic_write_json(root/GATE_REL,gate)
    next_out=dict(out)
    next_out["next_research_state"]={
        "status":"WAITING_EXTERNAL_AUTHENTICATED_DATA",
        "next_action":"AWAIT_READ_ONLY_CAPTURE_ZIP_RETURN_TO_AI_DIRECTOR",
        "external_data_gate_ref":str(GATE_REL),
        "collector_build_ref":gate["collector_build_ref"],
        "collector_package_artifact_name":gate["collector_package_artifact_name"],
        "expected_return_artifact_name":gate["expected_return_artifact_name"],
        "user_action_required":True,
    }
    return _publish_next(root,next_out,before)

def _normal_commit_push(root:Path,message:str)->str:
    subprocess.run(["git","add","-A"],cwd=root,check=True)
    subprocess.run(["git","commit","-m",message],cwd=root,check=True)
    sha=_head(root); target=os.environ.get("MXM_RUNTIME_TARGET_BRANCH","").strip()
    refspec=f"HEAD:refs/heads/{target}" if target else "HEAD"
    p=subprocess.run(["git","push","origin",refspec],cwd=root,text=True,capture_output=True)
    if p.returncode!=0: raise ImplementationRejected("implementation push failed: "+p.stderr[-1600:])
    return sha

def execute(root_value:str|Path=".",*,git_checkpoint:bool=False,git_push:bool=False)->dict[str,Any]:
    root=Path(root_value).resolve(); next_state=_next(root)
    stale=stale_reasoning_redirect(root,next_state)
    if stale is not None:
        before=project_snapshot(root)
        doc=dict(next_state); doc.update(stale)
        atomic_write_json(root/NEXT_STATE_REL,doc)
        if project_snapshot(root)!=before:
            raise ImplementationRejected("stale-reasoning redirect changed economic/accounting snapshot")
        GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("stale_reasoning_fail_closed",None)
        return {"status":"AI_REASONING_REQUIRED","next_state":doc,"stale_reasoning_guard":stale["stale_reasoning_guard"]}
    if not implementation_required(next_state,root): return {"status":"NO_IMPLEMENTATION_REQUIRED"}
    if next_state.get("source_ai_proposal_id"):
        superseded=load_json(root/"research_v3/EPOCH21_UNSAFE_PROPOSAL_SUPERSESSION_V1.json",{}) or {}
        if superseded.get("proposal_id")==next_state["source_ai_proposal_id"]:
            raise ImplementationRejected("superseded proposal cannot invoke implementation provider")
        _,bound_proposal,_=_resolve_current_proposal(root,next_state)
        try:
            validate_eligibility(bound_proposal)
        except EvidenceIneligible as exc:
            raise ImplementationRejected("pre-implementation evidence eligibility: "+str(exc)) from exc
    redirect=authoritative_reasoning_requirement(root,next_state)
    if redirect is not None:
        before=project_snapshot(root)
        out={
            "implementation_id":"authoritative-data-contract-redirect",
            "status":"COMPLETE_NON_ECONOMIC",
            "summary":"Execution was superseded by an authoritative prerequisite requiring additional AI reasoning/data binding.",
            "decision":{"classification":"ADDITIONAL_AI_REASONING_REQUIRED","authoritative_contract":redirect["authoritative_freeze_ref"]},
            "next_research_state":redirect,
            "external_data_gate":None,
            "tests_requested":[],
        }
        published=_publish_next(root,out,before)
        GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("general_ai_implementation_reasoning_redirect",None)
        return {"status":"AI_REASONING_REQUIRED","output":out,"next_state":published}
    before=project_snapshot(root); protected=protected_snapshot(root); state_hash=sha256_bytes(canonical_bytes(next_state))
    green=exact_head_green(root)
    pending=load_json(root/RESPONSE_REL,{}) or {}
    if pending.get("status")=="PENDING_EXACT_HEAD_GREEN" and pending.get("basis_next_state_sha256")==state_hash:
        if not green["green"]: return {"status":"PENDING_EXACT_HEAD_GREEN","exact_head":green}
        out=pending["implementation_output"]; _validate_output(root,out)
        accepted_out=_post_green_output(out,list(pending.get("changed_paths") or []))
        if accepted_out["status"]=="EXTERNAL_DATA_REQUIRED": published=_publish_external_gate(root,accepted_out,before)
        else: published=_publish_next(root,accepted_out,before)
        pending["status"]="ACCEPTED_AFTER_EXACT_HEAD_GREEN"; pending["accepted_exact_head"]=green
        pending["accepted_output"]=accepted_out
        atomic_write_json(root/RESPONSE_REL,pending)
        GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("general_ai_implementation_acceptance",None)
        return {"status":"IMPLEMENTATION_ACCEPTED","output":out,"next_state":published,"exact_head":green}

    if not green["green"]:
        return {"status":"PENDING_EXACT_HEAD_GREEN","exact_head":green}

    request={"schema":"mxm.greenfield.general-ai-implementation-request.v1","executor_version":VERSION,
             "research_head":_head(root),"basis_next_state_sha256":state_hash,"next_state":next_state,
             "project_snapshot":before,"exact_head":green,"created_utc":iso()}
    atomic_write_json(root/REQUEST_REL,request)
    # Do not let the request file count as an AI implementation edit.
    GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("general_ai_implementation_request",None)
    protected=protected_snapshot(root)
    token=os.environ.get("GITHUB_TOKEN") or os.environ.get("COPILOT_GITHUB_TOKEN")
    if not token: raise ImplementationRejected("GITHUB_TOKEN/COPILOT_GITHUB_TOKEN required")
    model=os.environ.get("MXM_COPILOT_IMPLEMENTATION_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        out,provider=_transport(root,_prompt(root,next_state),token,model)
        _validate_output(root,out)
        changed=_changed_paths(root)
        if not changed and out["status"]=="COMPLETE_NON_ECONOMIC":
            ns=dict(out.get("next_research_state") or {})
            if ns.get("next_action")==next_state.get("next_action") and implementation_required(ns,root):
                raise ImplementationRejected("implementation made no durable progress and repeated the same executable next_action")
        bad=[p for p in changed if _is_protected(p)]
        if bad: raise ImplementationRejected("AI implementation touched protected paths: "+repr(bad))
        if project_snapshot(root)!=before: raise ImplementationRejected("AI implementation changed economic/accounting snapshot")
        if protected_snapshot(root)!=protected: raise ImplementationRejected("AI implementation changed protected bytes")
        if changed:
            subprocess.run(["python","-m","unittest","discover","-s","tests","-p","test_*.py","-v"],cwd=root,check=True)
            response={"schema":"mxm.greenfield.general-ai-implementation-response.v1","status":"PENDING_EXACT_HEAD_GREEN",
                      "executor_version":VERSION,"basis_next_state_sha256":state_hash,"implementation_output":out,
                      "provider":provider,"changed_paths":changed,"project_snapshot":before,"created_utc":iso()}
            atomic_write_json(root/RESPONSE_REL,response)
            sha=_normal_commit_push(root,"AI implement non-economic research continuation")
            return {"status":"PENDING_EXACT_HEAD_GREEN","implementation_commit":sha,"changed_paths":changed,"provider":provider}
        response={"schema":"mxm.greenfield.general-ai-implementation-response.v1","status":"IMPLEMENTATION_VALIDATED_NO_CODE_CHANGE",
                  "executor_version":VERSION,"basis_next_state_sha256":state_hash,"implementation_output":out,
                  "provider":provider,"changed_paths":[],"project_snapshot":before,"exact_head":green,"created_utc":iso()}
        atomic_write_json(root/RESPONSE_REL,response)
        if out["status"]=="EXTERNAL_DATA_REQUIRED": published=_publish_external_gate(root,out,before)
        else: published=_publish_next(root,out,before)
        if project_snapshot(root)!=before: raise ImplementationRejected("publication changed economic/accounting snapshot")
        GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("general_ai_implementation_result",None)
        return {"status":"EXTERNAL_DATA_REQUIRED" if out["status"]=="EXTERNAL_DATA_REQUIRED" else "IMPLEMENTATION_COMPLETE",
                "output":out,"next_state":published,"provider":provider,"exact_head":green}
    except Exception:
        _restore(root)
        raise

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=VERSION); p.add_argument("command",choices=("inspect","execute")); p.add_argument("--root",default=".")
    p.add_argument("--git-checkpoint",action="store_true"); p.add_argument("--git-push",action="store_true"); a=p.parse_args(argv)
    root=Path(a.root)
    payload={"status":"IMPLEMENTATION_REQUIRED" if implementation_required(_next(root),root) else "NO_IMPLEMENTATION_REQUIRED",
             "next_state":_next(root),"exact_head":exact_head_green(root)} if a.command=="inspect" else execute(root,git_checkpoint=a.git_checkpoint,git_push=a.git_push)
    print(json.dumps(payload,sort_keys=True,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
