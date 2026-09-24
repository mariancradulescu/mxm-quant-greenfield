"""Unattended provider-neutral general-AI reasoning wake for MXM Research V3.

The active unattended adapter is GitHub Copilot CLI running programmatically in Actions.
The provider creates NON_ECONOMIC research proposals only. Runtime V2 remains the
deterministic safety, accounting, persistence and exactly-once economic authority.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.general_ai_director_bridge import (
    PROPOSAL_SCHEMA,
    PROTOCOL_VERSION,
    AIProposalRejected,
    project_snapshot,
    validate_proposal,
)
from research_v3.runtime_v2_primitives import (
    GitCheckpointSink,
    atomic_write_json,
    canonical_bytes,
    iso,
    sha256_bytes,
    sha256_file,
)

PROVIDER_VERSION="MXM_GENERAL_AI_REASONING_PROVIDER_V2"
PROVIDER_KIND="GITHUB_COPILOT_CLI"
DEFAULT_MODEL="auto"
NEXT_REL=Path("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
REQUEST_REL=Path("research_v3/ai_director/AI_REASONING_REQUEST.json")
RESPONSE_REL=Path("research_v3/ai_director/AI_REASONING_RESPONSE.json")
GATE_REL=Path("research_v3/ai_director/AI_REASONING_EXTERNAL_GATE.json")
PROPOSAL_DIR=Path("research_v3/ai_director/proposals")

BASE_AUTHORITIES=(
    "research_v3/RESEARCH_CONTRACT_V3.json",
    "data/RESEARCH_SCOPE_GOVERNANCE_V1.json",
    "evidence/MECHANISM_SCOPE_REGISTRY_V1.json",
    "evidence/V2_CONSUMED_IDENTITY_SCOPE_AUDIT_V1.json",
    "data/AUTONOMOUS_UNIVERSE_GOVERNOR_V1.json",
    "data/ADAPTIVE_DATA_ACQUISITION_POLICY_V1.json",
    "data/CAPITAL_FLOW_AWARE_CAUSAL_GOVERNOR_V1.json",
    "research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json",
    "data/BROKER_NATIVE_COMPETITION_STRUCTURAL_MAP_SUMMARY_V2.json",
    "data/BROKER_NATIVE_COMPETITION_UNIVERSE_ACCEPTANCE_V2.json",
    "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json",
    "data/C031_STRUCTURAL_EXTENSION_WAVE_01_M5_CAPTURE_PLAN_V1.json",
    "evidence/C031_STRUCTURAL_EXTENSION_WAVE_01_CAPTURE_ACCEPTANCE_V1.json",
    "evidence/SESSION_GAP_STRUCTURAL_EXTENSION_WAVE_01_REPORT_V1.json",
    "evidence/POST_OUTER_DUPLICATE_CAPTURE_SUPERSESSION_V1.json",
    "evidence/AI_SELECTED_SCOPE_FEASIBILITY_AUDIT_V1.json",
    "evidence/AI_SELECTED_SCOPE_FEASIBILITY_AUDIT_V2.json",
    "evidence/GENERAL_AI_RESEARCH_DIRECTOR_ACCEPTANCE_V1.json",
    "research_v3/ai_director/GENERAL_AI_DIRECTOR_ARCHITECTURE_V1.json",
)

class AIReasoningProviderError(RuntimeError): pass
class AIReasoningExternalGate(RuntimeError): pass

def _load(root:Path,rel:str|Path)->dict[str,Any]:
    p=root/Path(rel)
    if not p.is_file():
        raise AIReasoningProviderError(f"required reasoning authority missing: {p.relative_to(root)}")
    return json.loads(p.read_text(encoding="utf-8"))

def _head(root:Path)->str:
    return subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()

def reasoning_required(next_state:Mapping[str,Any])->bool:
    if next_state.get("user_action_required") is True:
        return False
    if next_state.get("ai_reasoning_required") is True:
        return True
    action=str(next_state.get("next_action") or "").upper()
    status=str(next_state.get("status") or "").upper()
    # Wake detection only. This never maps a state to a research decision.
    return action.startswith("AI_") or "PENDING_AI_INTERPRETATION" in status or "AI_REASONING_REQUIRED" in status

def _authority_context(root:Path,next_state:Mapping[str,Any])->tuple[list[dict[str,Any]],list[str]]:
    refs=list(BASE_AUTHORITIES)
    for key in (
        "result_ref","pre_economic_acceptance_ref","freeze_ref",
        "source_freeze_ref","authoritative_freeze_ref",
        "outer_capture_plan_ref","outer_data_audit_ref","supersession_ref",
        "external_data_gate_ref","capture_acceptance_ref","structural_screen_freeze_ref",
        "outer_data_binding_ref","interpretation_ref","same_wave01_supersession_ref",
        "completed_capture_ref","completed_capture_plan_ref",
        "completed_structural_report_ref","duplicate_capture_supersession_ref",
        "selected_scope_feasibility_audit_ref","superseded_pre_capture_proposal_ref",
    ):
        value=next_state.get(key)
        if isinstance(value,str) and value and value not in refs:
            refs.append(value)
    rows=[]; kept=[]
    for rel in refs:
        p=root/rel
        if not p.is_file():
            continue
        raw=p.read_bytes()
        item={"ref":rel,"sha256":sha256_bytes(raw)}
        try:
            item["content"]=json.loads(raw)
        except Exception:
            item["content_text"]=raw.decode("utf-8",errors="replace")[:16000]
        rows.append(item); kept.append(rel)
    return rows,kept

def build_reasoning_request(root_value:str|Path)->dict[str,Any]:
    root=Path(root_value).resolve()
    next_state=_load(root,NEXT_REL)
    snapshot=project_snapshot(root)
    report=validate_repository_state(root)
    authorities,refs=_authority_context(root,next_state)
    core={
        "provider_version":PROVIDER_VERSION,
        "research_head":_head(root),
        "project_snapshot":snapshot,
        "next_state":next_state,
        "control_plane":{
            "next_action":report.get("next_action"),
            "stage_b_survivors":report.get("stage_b_survivors",[]),
            "stage_b_revalidation_required_candidate_ids":report.get("stage_b_revalidation_required_candidate_ids",[]),
            "material_issues":report.get("material_issues",[]),
            "recoverable_conditions":report.get("recoverable_conditions",[]),
            "safety":report.get("safety",{}),
        },
        "authority_hashes":[{"ref":x["ref"],"sha256":x["sha256"]} for x in authorities],
    }
    request_id="reason_"+sha256_bytes(canonical_bytes(core))[:32]
    return {
        "schema":"mxm.greenfield.general-ai-reasoning-request.v2",
        "status":"AI_REASONING_REQUIRED" if reasoning_required(next_state) else "NO_AI_REASONING_REQUIRED",
        "protocol_version":PROTOCOL_VERSION,
        "provider_version":PROVIDER_VERSION,
        "request_id":request_id,
        "research_head":core["research_head"],
        "project_snapshot":snapshot,
        "next_state":next_state,
        "control_plane":core["control_plane"],
        "authority_refs":refs,
        "authority_hashes":core["authority_hashes"],
        "created_utc":iso(),
    }

def _context_payload(root:Path,request:Mapping[str,Any])->dict[str,Any]:
    authorities,_=_authority_context(root,request["next_state"])
    return {
        "request":{
            "request_id":request["request_id"],
            "research_head":request["research_head"],
            "project_snapshot":request["project_snapshot"],
            "next_state":request["next_state"],
            "control_plane":request["control_plane"],
        },
        "authorities":authorities,
        "non_negotiable_objective":{
            "broker":"Pepperstone",
            "execution_target":"cTrader Algo / one continuous account",
            "starting_capital_eur":200,
            "optimize":"maximum realizable compounded equity growth with practical anti-ruin and recovery capacity",
            "hard21":"floor where applicable; never an arbitrary frequency ceiling",
            "scope":"broader broker-native universe remains open; 10-symbol V6 is not global universe",
        },
    }

def _system_prompt()->str:
    return """You are the autonomous general AI Research Director for MXM Quant Greenfield V2.
You own advanced research reasoning: interpretation, hypothesis/mechanism generation, universe reasoning,
data sufficiency, research prioritization, methodology design and the highest-information legal next action.
Do NOT behave like a finite state machine and do NOT merely echo next_action. Infer the best research action
from the authoritative context.

Return ONE JSON object only, with these keys:
proposal_id: concise unique string
objective: object with class, goal, information_gain_rationale
decision: arbitrary JSON object expressing your actual research decision and enough implementation semantics
next_research_state: arbitrary JSON object with at least status and next_action; do not include protected accounting/safety keys
authority_refs: non-empty list chosen only from refs provided in context
data_bindings: optional list
artifact_attestation_refs: MUST be [] unless the supplied context explicitly identifies a document whose schema is mxm.greenfield.ai-director-artifact-attestation.v1 and status is VERIFIED
data_policy: object with new_market_data_requested boolean, and if true minimal_acquisition_request with source_domain exactly PEPPERSTONE_ACCOUNT_VIA_CTRADER_OPEN_API, symbols,resolution,start_utc,end_utc,fields,information_gain_justification
mechanism_family_closure_claims: list; normally empty unless prospective exhaustion authority exists

The next_research_state object MUST NOT contain any of these deterministic/protected keys:
accounting, safety, economic_outcomes_opened, v2_attempts_used, v2_search_budget_remaining,
protected_forward, live_orders, competition_start, competition_start_authorized, live_orders_authorized.
Those values are injected and guarded outside the AI layer.

Important boundaries:
- The reasoning proposal itself is NON_ECONOMIC; do not claim it opened an outcome or consumed an attempt.
- Do not rerun C031 Stage-B or any already observed exact identity.
- Do not infer mechanism-family exhaustion from narrow exact-scope failures.
- Preserve one continuous account, realistic free margin/margin, capital-flow accounting and anti-ruin.
- Prefer structural screening and minimal justified incremental data before expensive broad economics.
- Use only authorized Pepperstone-account cTrader/Open API or previously hash-bound captures from that same broker account for empirical market, costs, margin, and execution evidence. Public official documentation may clarify semantics; no external market dataset is empirical authority.
- The completed independent outer is observed evidence, not an unopened confirmation set; never re-open or rerun its exact outcome. If new authenticated broker-native data are unavoidable, define the smallest read-only capture and stop at that external gate.
- The accepted C031 twelve-symbol M5 extension for 2026-07-20 through 2026-09-13 and its structural report already exist. The previous AI proposal asking for those same bytes was superseded. Reuse its accepted, hash-bound evidence without another collector or screen; do not ask the user to upload it again.
- An independent account-native minimum-volume audit found BTCUSD, US30, and XAGUSD infeasible in both directions at initial EUR200 in the later pre-capture proposal. That exact proposal was superseded before capture. Do not treat these as initially tradable EUR200 opportunities. You may consider later higher-equity feasibility only with explicit prospective rationale; independently choose the revised direction from the full evidence and verify any claimed broker feasibility.
- Before proposing any new capture symbols, use the accepted account-native feasibility index to verify exact symbol names, product identity, TEST exclusion and EUR200 directional feasibility. A symbol infeasible at initial EUR200 requires an explicitly declared future_equity_only_scope with symbols, prospective_rationale and initial_eur200_tradable false; do not imply it is currently executable. Do not invent a broker symbol spelling.
- The newer feasibility audit V2 superseded the later twelve-symbol proposal before capture: GER30 is absent from the current account, and XAGUSD, BTCUSD and US30 cannot enter at minimum volume with initial EUR200. Do not reactivate either superseded proposal from the immutable registry. You must verify every proposed symbol against the index before submission; the deterministic bridge enforces this.
- Evaluate the broader feasible broker-native universe without treating a narrow six-symbol result as a family-level closure, and do not predetermine mechanism family, panel size or screening procedure.
- Do not ask the human to choose routine candidates, symbols, horizon, architecture or risk internals.
- If a genuine external dependency is unavoidable, identify the minimum external gate explicitly.
- Treat every supplied prospective freeze/data plan as authoritative. If it fixes panel membership, resolution, or an unopened outer-data scope, do not substitute symbols or dates unless a separate durable prospective supersession authority is explicitly supplied in context.
- Source/development bytes that were used to select a panel may not be reused as independent outer evidence when an authoritative freeze requires disjoint unopened data.
- Never output chain-of-thought. Put only concise decision rationale in information_gain_rationale/decision.
"""

def _user_prompt(context:Mapping[str,Any], correction:str|None=None)->str:
    base=_system_prompt()+"\n\nAUTHORITATIVE REPOSITORY CONTEXT:\n"+json.dumps(context,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    if correction:
        base+="\n\nYOUR PREVIOUS JSON WAS REJECTED BY DETERMINISTIC VALIDATION. CORRECT IT WITHOUT CHANGING THE RESEARCH GOAL:\n"+correction
    return base

def _extract_json(text:str)->dict[str,Any]:
    s=text.strip()
    fence=chr(96)*3
    if s.startswith(fence):
        s=re.sub("^"+re.escape(fence)+r"(?:json)?\s*","",s,flags=re.I)
        s=re.sub(r"\s*"+re.escape(fence)+r"$","",s)
    try:
        obj=json.loads(s)
    except Exception:
        a=s.find("{"); b=s.rfind("}")
        if a<0 or b<=a:
            raise AIReasoningProviderError("provider response contains no JSON object")
        obj=json.loads(s[a:b+1])
    if not isinstance(obj,dict):
        raise AIReasoningProviderError("provider response is not a JSON object")
    return obj

def _looks_external_gate(text:str)->bool:
    s=text.lower()
    markers=(
        "copilot requests permission",
        "copilot-requests",
        "not entitled",
        "no copilot",
        "copilot subscription",
        "copilot plan",
        "authentication failed",
        "unauthorized",
        "forbidden",
        "billing",
        "policy",
    )
    return any(x in s for x in markers)

def copilot_cli_transport(token:str,model:str,prompt:str,*,root:Path)->tuple[dict[str,Any],dict[str,Any]]:
    if not shutil.which("copilot"):
        raise AIReasoningProviderError("GitHub Copilot CLI executable is not installed")
    cmd=[
        "copilot",
        "-p",prompt,
        "-s",
        "--model="+model,
        "--no-ask-user",
        "--no-auto-update",
        "--no-color",
        "--no-custom-instructions",
        "--deny-tool=shell",
        "--deny-tool=write",
        "--deny-tool=url",
    ]
    env=dict(os.environ)
    env["GITHUB_TOKEN"]=token
    env["COPILOT_GITHUB_TOKEN"]=token
    proc=subprocess.run(cmd,cwd=root,env=env,text=True,capture_output=True,timeout=240)
    if proc.returncode!=0:
        detail=(proc.stderr+"\n"+proc.stdout).strip()
        if _looks_external_gate(detail):
            raise AIReasoningExternalGate(detail[:1600])
        raise AIReasoningProviderError("Copilot CLI failed: "+detail[:2000])
    output=proc.stdout.strip()
    if not output:
        raise AIReasoningProviderError("Copilot CLI returned empty output")
    return _extract_json(output),{
        "provider":"github-copilot-cli",
        "model":model,
        "model_selection":"AUTO_ACCOUNT_AVAILABLE" if model=="auto" else "EXPLICIT",
        "actual_model_identity":None if model=="auto" else model,
        "actual_model_identity_known":model!="auto",
        "model_identity_limitation":"Copilot CLI silent programmatic mode does not expose the model selected behind Auto." if model=="auto" else None,
        "cli":"@github/copilot",
    }

def _wrap(root:Path,request:Mapping[str,Any],candidate:Mapping[str,Any],provider_meta:Mapping[str,Any])->dict[str,Any]:
    objective=candidate.get("objective"); decision=candidate.get("decision"); next_state=candidate.get("next_research_state")
    if not isinstance(objective,Mapping) or not isinstance(decision,Mapping) or not isinstance(next_state,Mapping):
        raise AIProposalRejected("provider candidate missing objective/decision/next_research_state objects")
    allowed=set(request["authority_refs"])
    refs=candidate.get("authority_refs") or []
    if not isinstance(refs,list) or not refs:
        raise AIProposalRejected("provider candidate authority_refs must be non-empty")
    refs=[str(x) for x in refs]
    if any(x not in allowed for x in refs):
        raise AIProposalRejected("provider candidate referenced authority outside supplied context")
    raw_policy=candidate.get("data_policy") or {}
    new_data=bool(raw_policy.get("new_market_data_requested"))
    data_policy={"no_default_multi_year_download":True,"user_selects_symbols_or_horizon":False,"new_market_data_requested":new_data}
    if new_data:
        data_policy["minimal_acquisition_request"]=raw_policy.get("minimal_acquisition_request") or {}
    closure=candidate.get("mechanism_family_closure_claims") or []
    if not isinstance(closure,list):
        raise AIProposalRejected("mechanism_family_closure_claims must be list")
    pid=str(candidate.get("proposal_id") or f"AUTO-{request['request_id']}").strip()
    proposal={
        "schema":PROPOSAL_SCHEMA,
        "proposal_id":pid,
        "provider":{"kind":"GITHUB_COPILOT_CLI_GENERAL_REASONING","vendor":"GitHub Copilot","model":provider_meta.get("model"),"provider_version":PROVIDER_VERSION,"reasoning_request_id":request["request_id"]},
        "basis":{"research_head":request["research_head"],"accounting":{"v2_attempts_used":request["project_snapshot"]["v2_attempts_used"],"v2_search_budget_remaining":request["project_snapshot"]["v2_search_budget_remaining"],"economic_outcomes_opened":request["project_snapshot"]["economic_outcomes_opened"]},"discovery_ledger_sha256":request["project_snapshot"]["discovery_ledger_sha256"]},
        "objective":dict(objective),
        "decision":dict(decision),
        "next_research_state":dict(next_state),
        "authority_refs":refs,
        "data_bindings":candidate.get("data_bindings") or [],
        "artifact_attestation_refs":candidate.get("artifact_attestation_refs") or [],
        "economic_effect":{"open_economic_outcome":False,"consume_v2_attempt":0,"create_new_v2_identity":False},
        "safety":{"protected_forward_opened":False,"live_orders_authorized":False,"competition_start_authorized":False},
        "scope_law":{"rerun_exact_observed_identity":False,"refund_observed_attempts":False,"mechanism_family_closure_claims":closure},
        "data_policy":data_policy,
        "causal_contract":{"chronological_incremental_replay":True,"causal_entry_admission":True,"future_information_forbidden":True,"protected_forward_leakage_forbidden":True,"learned_procedure_freeze_before_outer_outcome":True},
        "publication":{"apply_to_next_state":True},
    }
    validate_proposal(root,proposal)
    return proposal

def _proposal_ref(request_id:str)->Path:
    return PROPOSAL_DIR/f"AUTO_{request_id}.json"

def wake(root_value:str|Path=".",*,token:str|None=None,transport:Callable[...,tuple[dict[str,Any],dict[str,Any]]]=copilot_cli_transport,git_checkpoint:bool=False,git_push:bool=False)->dict[str,Any]:
    root=Path(root_value).resolve()
    request=build_reasoning_request(root)
    atomic_write_json(root/REQUEST_REL,request)
    sink=GitCheckpointSink(root,enabled=git_checkpoint,push=git_push)
    if request["status"]!="AI_REASONING_REQUIRED":
        sink.checkpoint("general_ai_reasoning_request_noop",None)
        return {"status":"NO_AI_REASONING_REQUIRED","request_id":request["request_id"]}

    rel=_proposal_ref(request["request_id"]); path=root/rel
    if path.is_file():
        proposal=json.loads(path.read_text(encoding="utf-8"))
        validate_proposal(root,proposal)
        sink.checkpoint("general_ai_reasoning_reused",None)
        return {"status":"PROPOSAL_ALREADY_DURABLE","request_id":request["request_id"],"proposal_ref":str(rel),"proposal_hash":sha256_file(path)}

    token=token or os.environ.get("GITHUB_TOKEN") or os.environ.get("COPILOT_GITHUB_TOKEN")
    if not token:
        gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1","status":"EXTERNAL_AUTHORIZATION_REQUIRED","provider":"github-copilot-cli","required":"GITHUB_TOKEN with copilot-requests: write and repository-owner Copilot access","request_id":request["request_id"],"created_utc":iso()}
        atomic_write_json(root/GATE_REL,gate); sink.checkpoint("general_ai_reasoning_external_gate",None)
        return gate

    context=_context_payload(root,request)
    correction=None; errors=[]; chosen_meta=None; proposal=None
    model=os.environ.get("MXM_COPILOT_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL
    for attempt in range(5):
        try:
            candidate,meta=transport(token,model,_user_prompt(context,correction),root=root)
            proposal=_wrap(root,request,candidate,meta); chosen_meta=meta
            break
        except AIReasoningExternalGate as exc:
            gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1","status":"EXTERNAL_AUTHORIZATION_REQUIRED","provider":"github-copilot-cli","request_id":request["request_id"],"detail":str(exc),"created_utc":iso()}
            atomic_write_json(root/GATE_REL,gate); sink.checkpoint("general_ai_reasoning_external_gate",None)
            return gate
        except Exception as exc:
            correction=f"{type(exc).__name__}: {exc}"
            errors.append({"model":model,"attempt":attempt+1,"error":correction})
    if proposal is None:
        gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1","status":"PROVIDER_RETRY_REQUIRED","provider":"github-copilot-cli","request_id":request["request_id"],"errors":errors[-8:],"created_utc":iso()}
        atomic_write_json(root/GATE_REL,gate); sink.checkpoint("general_ai_reasoning_provider_retry",None)
        raise AIReasoningProviderError("all configured general reasoning attempts failed")

    path.parent.mkdir(parents=True,exist_ok=True)
    atomic_write_json(path,proposal)
    response={"schema":"mxm.greenfield.general-ai-reasoning-response.v1","status":"PROPOSAL_GENERATED_PENDING_RUNTIME_V2_MATERIALIZATION","request_id":request["request_id"],"proposal_ref":str(rel),"proposal_sha256":sha256_file(path),"provider":{"kind":"github-copilot-cli",**dict(chosen_meta or {})},"economic_outcome_opened":False,"v2_attempt_consumed":0,"created_utc":iso()}
    atomic_write_json(root/RESPONSE_REL,response)
    if (root/GATE_REL).exists():
        (root/GATE_REL).unlink()
    sink.checkpoint("general_ai_reasoning_response",None)
    return response

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=PROVIDER_VERSION)
    p.add_argument("command",choices=("request","wake"))
    p.add_argument("--root",default=".")
    p.add_argument("--git-checkpoint",action="store_true")
    p.add_argument("--git-push",action="store_true")
    a=p.parse_args(argv)
    if a.command=="request":
        payload=build_reasoning_request(a.root)
        atomic_write_json(Path(a.root)/REQUEST_REL,payload)
    else:
        payload=wake(a.root,git_checkpoint=a.git_checkpoint,git_push=a.git_push)
    print(json.dumps(payload,sort_keys=True,indent=2))
    return 0
if __name__=="__main__": raise SystemExit(main())
