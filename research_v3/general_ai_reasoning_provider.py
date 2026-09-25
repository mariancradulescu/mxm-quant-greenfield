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

from research_v3.evidence_eligibility import packet, validate_eligibility, EvidenceIneligible
from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.evidence_epoch import current_evidence_binding
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
    "research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json",
    "data/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json",
    "evidence/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_DATA_AUDIT_V1.json",
    "evidence/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CONFIRMATORY_RESULT_V1.json",
    "evidence/RETROSPECTIVE_HISTORICAL_RESEARCH_VALIDITY_AUDIT_V1.json",
    "evidence/BROKER_NATIVE_PANEL_SCREEN_AUDIT_V1.json",
    "evidence/SESSION_GAP_SCHEDULE_COVERAGE_DEPENDENCY_REVIEW_V1.json",
    "data/BROKER_NATIVE_ADAPTIVE_INFORMATION_FRONTIER_V1.json",
    "data/BROKER_NATIVE_FRONTIER_M5_PROBE_PLAN_V1.json",
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
    for rel in ("research_v3/CURRENT_RESEARCH_FRONTIER_V1.json",
                "research_v3/EPOCH21_OUTCOME_BLIND_CAPACITY_AUDIT_V1.json",
                "research_v3/EPOCH21_ECONOMIC_SEARCH_GOVERNANCE_V1.json",
                "research_v3/ai_director/EVIDENCE_ELIGIBILITY_V1.json",
                "research_v3/EPOCH21_UNSAFE_PROPOSAL_SUPERSESSION_V1.json"):
        if (root/rel).is_file() and rel not in refs: refs.append(rel)
    acceptance_path=root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_ACCEPTANCE_V1.json"
    if acceptance_path.is_file():
        accepted=json.loads(acceptance_path.read_text(encoding="utf-8"))
        rel=accepted.get("requested_ref")
        if accepted.get("status")=="ELIGIBLE_AUTHORITY_ADDED_TO_NEW_PACKET" and isinstance(rel,str) and (root/rel).is_file() and sha256_file(root/rel)==accepted.get("sha256") and rel not in refs:
            refs.append(rel)
    epoch_binding=current_evidence_binding(root)
    for row in epoch_binding["authoritative_evidence_refs_and_hashes"]:
        if row["ref"] not in refs:
            refs.append(row["ref"])
    for row in epoch_binding["provisional_research_artifacts"]:
        if row["ref"] not in refs:
            refs.append(row["ref"])
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
            doc=json.loads(raw)
            if len(raw)>3000:
                item["content_summary"]={
                    "schema":doc.get("schema"),"status":doc.get("status"),
                    "byte_length":len(raw),"available_via_repository_view":True,
                    "top_level_keys":list(doc)[:24],
                }
                if rel.endswith("PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json"):
                    item["content_summary"]["current_accessible_symbols_indexed"]=doc.get("current_accessible_symbols_indexed")
                    item["content_summary"]["source_zip_sha256"]=doc.get("source_zip_sha256")
            else:
                item["content"]=doc
        except Exception:
            item["content_text"]=raw.decode("utf-8",errors="replace")[:3000]
        rows.append(item); kept.append(rel)
    return rows,kept

def build_reasoning_request(root_value:str|Path)->dict[str,Any]:
    root=Path(root_value).resolve()
    next_state=_load(root,NEXT_REL)
    snapshot=project_snapshot(root)
    report=validate_repository_state(root)
    authorities,refs=_authority_context(root,next_state)
    evidence=current_evidence_binding(root)
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
        "evidence_epoch_seen":evidence["evidence_epoch"],
        "evidence_bundle_sha256":evidence["evidence_bundle_sha256"],
        "universe_basis":evidence["universe_basis"],
        "current_open_mechanism_families":evidence["current_open_mechanism_families"],
    }
    # The repository HEAD and full mutable next-state document are transport context,
    # not reasons to buy another semantic judgment on unchanged evidence.
    decision_fingerprint={
        "provider_version":PROVIDER_VERSION,
        "protocol_version":PROTOCOL_VERSION,
        "evidence_epoch":core["evidence_epoch_seen"],
        "evidence_bundle_sha256":core["evidence_bundle_sha256"],
        "authority_hashes":core["authority_hashes"],
        "decision_class":str(next_state.get("next_action") or ""),
        "pending_status":str(next_state.get("status") or ""),
        "accounting":snapshot,
        "universe_basis":core["universe_basis"],
        "open_families":core["current_open_mechanism_families"],
    }
    request_id="reason_"+sha256_bytes(canonical_bytes(decision_fingerprint))[:32]
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
        "evidence_epoch_seen":core["evidence_epoch_seen"],
        "evidence_bundle_sha256":core["evidence_bundle_sha256"],
        "authoritative_evidence_refs_and_hashes":evidence["authoritative_evidence_refs_and_hashes"],
        "provisional_research_artifacts":evidence["provisional_research_artifacts"],
        "universe_basis":core["universe_basis"],
        "current_open_mechanism_families":core["current_open_mechanism_families"],
        "created_utc":iso(),
    }

def _context_payload(root:Path,request:Mapping[str,Any])->dict[str,Any]:
    frontier=json.loads((root/"research_v3/CURRENT_RESEARCH_FRONTIER_V1.json").read_text())
    audit=json.loads((root/"research_v3/EPOCH21_OUTCOME_BLIND_CAPACITY_AUDIT_V1.json").read_text())
    epoch_doc=json.loads((root/"research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json").read_text())
    delta=list((epoch_doc.get("trigger_event") or {}).get("refs") or [])
    scope=[{"id":row["candidate_id"],"family":row["mechanism_family"],
            "symbols":row["exact_universe_size"],"design_class":row["classification"],
            "replacement":row["replacement_eligible"],"result_ref":row["latest_result_ref"]}
           for row in audit["per_identity"]]
    p=packet(root,evidence_epoch=request["evidence_epoch_seen"],
             decision_class="FRESH_FRONTIER_LEVEL_RESEARCH",
             refs=request["authority_refs"],accounting=frontier["accounting"],
             universe=frontier["open_frontier"],
             semantic_question="From the entire legal broker-native frontier, choose the highest-information prospective research wave for extremely fast and high realizable compounded EUR200 Pepperstone/cTrader equity growth with free-margin survival and recovery capacity. Select mechanism and breadth from reusable evidence, not the last candidate.",
             delta_refs=delta)
    p["allowed_authority_refs"]=[x["ref"] for x in
        p["admissible_inputs"]+p["historical_context"]+p["forbidden_inputs"]]
    return {"request_id":request["request_id"],"eligibility_packet":p,
            "historical_consumed_identity_summaries":scope,
            "valid_survivors":["V2-C006","V2-C012","V2-C031"],
            "unresolved_prerequisites":["C006 historical cash-session calendar",
                "C029 development settlement coverage","C030 zero settled trade"],
            "project_objective":{"broker":"Pepperstone","platform":"cTrader",
                "starting_capital_eur":200,"account":"ONE_CONTINUOUS_ACCOUNT",
                "goal":"EXTREMELY_HIGH_AND_FAST_REALIZABLE_COMPOUNDED_EQUITY_GROWTH",
                "must_preserve":["free_margin","recovery_capacity","anti_ruin"]},
            "capacity":{"base_remaining":64,"methodology_replacement_total":15,
                "lifetime_economic_exposure":20,"outcomes_opened":28},
            "causal_prohibitions":["NO_C032_RERUN","NO_C032_OUTCOME_CAPTURE_REUSE",
                "NO_PROTECTED_FORWARD_LEAKAGE","NO_RETROACTIVE_TUNING",
                "NO_OUTCOME_DRIVEN_SCOPE_SELECTION"],
            "authority_protocol":"If a necessary ref is absent, return status ADDITIONAL_AUTHORITY_REQUIRED with requested_authority_or_class and rationale. Do not invent an allowed ref."}


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
- Large authoritative files are supplied by hash and repository path rather than fully inlined. Use the repository view/search tools to read their relevant rows before deciding; never infer a selected symbol's feasibility from a short context summary.
- The newer feasibility audit V2 superseded the later twelve-symbol proposal before capture: GER30 is absent from the current account, and XAGUSD, BTCUSD and US30 cannot enter at minimum volume with initial EUR200. Do not reactivate either superseded proposal from the immutable registry. You must verify every proposed symbol against the index before submission; the deterministic bridge enforces this.
- Evaluate the broader feasible broker-native universe without treating a narrow six-symbol result as a family-level closure, and do not predetermine mechanism family, panel size or screening procedure.
- Do not ask the human to choose routine candidates, symbols, horizon, architecture or risk internals.
- Current accepted structural representatives establish structural/data-surface coverage only, not economic equivalence for all members sharing a signature.
- Explicitly decide whether the accepted 40 representative series are sufficient for the NEXT research decision. Do not assume either sufficiency or insufficiency.
- Explicitly assess whether additional prospective exploration inside the broader eligible broker-native universe has positive expected information gain before narrowing to a mechanism-specific outer.
- A provisional four-panel SESSION_GAP outer may be reauthorized or superseded; do not treat its existence as authorization.
- Never let an older proposal silently inherit authority across a newer research evidence epoch.
- A certified collector PACKAGE is not accepted market-data evidence. If a provisional outer has a collector package but no accepted returned capture, do not claim the outer bytes already exist.
- If you reauthorize a preserved provisional outer, bind the exact frozen plan symbols/resolution/interval, set new_market_data_requested=true, and request the authenticated read-only capture. Reuse the already-built exact-scope collector rather than inventing a new scope or pretending capture bytes are available.
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
    unknown=[x for x in refs if x not in allowed]
    if unknown:
        sanitized=[x for x in unknown if re.fullmatch(r"[A-Za-z0-9_./-]{1,220}",x)]
        raise AIProposalRejected("provider candidate referenced authority outside supplied context: "+json.dumps(sanitized[:8]))
    raw_policy=candidate.get("data_policy") or {}
    new_data=bool(raw_policy.get("new_market_data_requested"))
    data_policy={"no_default_multi_year_download":True,"user_selects_symbols_or_horizon":False,"new_market_data_requested":new_data}
    if new_data:
        data_policy["minimal_acquisition_request"]=raw_policy.get("minimal_acquisition_request") or {}
    closure=candidate.get("mechanism_family_closure_claims") or []
    if not isinstance(closure,list):
        raise AIProposalRejected("mechanism_family_closure_claims must be list")
    pid=str(candidate.get("proposal_id") or f"AUTO-{request['request_id']}").strip()
    response_id="reason_response_"+sha256_bytes(canonical_bytes({"request_id":request["request_id"],"candidate":candidate}))[:32]
    proposed_next=dict(next_state)
    proposed_next.setdefault("research_judgment_required",False)
    proposed_next["authorizing_evidence_epoch"]=int(request["evidence_epoch_seen"])
    proposal={
        "schema":PROPOSAL_SCHEMA,
        "proposal_id":pid,
        "provider":{"kind":"GITHUB_COPILOT_CLI_GENERAL_REASONING","vendor":"GitHub Copilot","model":provider_meta.get("model"),"provider_version":PROVIDER_VERSION,"reasoning_request_id":request["request_id"]},
        "basis":{"research_head":request["research_head"],"accounting":{"v2_attempts_used":request["project_snapshot"]["v2_attempts_used"],"v2_search_budget_remaining":request["project_snapshot"]["v2_search_budget_remaining"],"economic_outcomes_opened":request["project_snapshot"]["economic_outcomes_opened"]},"discovery_ledger_sha256":request["project_snapshot"]["discovery_ledger_sha256"]},
        "objective":dict(objective),
        "decision":dict(decision),
        "next_research_state":proposed_next,
        "authority_refs":refs,
        "data_bindings":candidate.get("data_bindings") or [],
        "artifact_attestation_refs":candidate.get("artifact_attestation_refs") or [],
        "economic_effect":{"open_economic_outcome":False,"consume_v2_attempt":0,"create_new_v2_identity":False},
        "safety":{"protected_forward_opened":False,"live_orders_authorized":False,"competition_start_authorized":False},
        "scope_law":{"rerun_exact_observed_identity":False,"refund_observed_attempts":False,"mechanism_family_closure_claims":closure},
        "data_policy":data_policy,
        "causal_contract":{"chronological_incremental_replay":True,"causal_entry_admission":True,"future_information_forbidden":True,"protected_forward_leakage_forbidden":True,"learned_procedure_freeze_before_outer_outcome":True},
        "publication":{"apply_to_next_state":True},
        "evidence_binding":{
            "reasoning_request_id":request["request_id"],
            "reasoning_response_id":response_id,
            "evidence_epoch_seen":int(request["evidence_epoch_seen"]),
            "evidence_bundle_sha256":request["evidence_bundle_sha256"],
            "authoritative_evidence_refs_and_hashes":list(request["authoritative_evidence_refs_and_hashes"]),
            "accounting_basis":dict(request["project_snapshot"]),
            "universe_basis":dict(request["universe_basis"]),
            "current_open_mechanism_families":list(request["current_open_mechanism_families"]),
        },
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
    for attempt in range(1):
        try:
            candidate,meta=transport(token,model,_user_prompt(context,correction),root=root)
            if candidate.get("status")=="ADDITIONAL_AUTHORITY_REQUIRED":
                requested=str(candidate.get("requested_authority_or_class") or "")[:220]
                rationale=str(candidate.get("rationale") or "")[:700]
                if not requested or not rationale:
                    raise AIProposalRejected("additional authority request lacks explicit ref/class or rationale")
                requirement={"schema":"mxm.greenfield.additional-authority-request.v1",
                             "status":"ADDITIONAL_AUTHORITY_REQUIRED",
                             "requested_authority_or_class":requested,"rationale":rationale,
                             "request_id":request["request_id"],"evidence_epoch":request["evidence_epoch_seen"],
                             "no_economic_outcome":True,"created_utc":iso()}
                atomic_write_json(root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",requirement)
                sink.checkpoint("general_ai_additional_authority_request",None)
                return requirement
            proposal=_wrap(root,request,candidate,meta); chosen_meta=meta
            break
        except AIProposalRejected as exc:
            rejection={"schema":"mxm.greenfield.ai-proposal-eligibility-rejection.v1",
                       "status":"REJECTED_BEFORE_REGISTRY_AND_IMPLEMENTATION",
                       "reason":str(exc),"request_id":request["request_id"],
                       "evidence_epoch":request["evidence_epoch_seen"],
                       "economic_outcomes_opened_delta":0,"v2_attempts_consumed_delta":0,
                       "implementation_provider_calls":0,"created_utc":iso()}
            atomic_write_json(root/"research_v3/ai_director/PROPOSAL_ELIGIBILITY_REJECTION_V1.json",rejection)
            sink.checkpoint("general_ai_semantic_rejection",None)
            return rejection
        except AIReasoningExternalGate as exc:
            gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1","status":"EXTERNAL_AUTHORIZATION_REQUIRED","provider":"github-copilot-cli","request_id":request["request_id"],"detail":str(exc),"created_utc":iso()}
            atomic_write_json(root/GATE_REL,gate); sink.checkpoint("general_ai_reasoning_external_gate",None)
            return gate
        except Exception as exc:
            correction=f"{type(exc).__name__}: {exc}"
            errors.append({"model":model,"attempt":attempt+1,"error":correction})
            if "monthly quota" in correction.lower() or "exceeded your quota" in correction.lower():
                raise AIReasoningProviderError("monthly quota exhausted; no duplicate provider retries") from exc
    if proposal is None:
        gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1","status":"PROVIDER_RETRY_REQUIRED","provider":"github-copilot-cli","request_id":request["request_id"],"errors":errors[-8:],"created_utc":iso()}
        atomic_write_json(root/GATE_REL,gate); sink.checkpoint("general_ai_reasoning_provider_retry",None)
        raise AIReasoningProviderError("all configured general reasoning attempts failed")

    try:
        validate_eligibility(proposal)
    except EvidenceIneligible as exc:
        rejection={"schema":"mxm.greenfield.ai-proposal-eligibility-rejection.v1",
                   "status":"REJECTED_BEFORE_REGISTRY_AND_IMPLEMENTATION",
                   "reason":str(exc),"request_id":request["request_id"],
                   "proposal_id":proposal.get("proposal_id"),
                   "evidence_epoch":request["evidence_epoch_seen"],
                   "economic_outcomes_opened_delta":0,"v2_attempts_consumed_delta":0,
                   "implementation_provider_calls":0,"created_utc":iso()}
        atomic_write_json(root/"research_v3/ai_director/PROPOSAL_ELIGIBILITY_REJECTION_V1.json",rejection)
        sink.checkpoint("general_ai_eligibility_rejection",None)
        return rejection
    path.parent.mkdir(parents=True,exist_ok=True)
    atomic_write_json(path,proposal)
    binding=proposal["evidence_binding"]; created=iso()
    response={"schema":"mxm.greenfield.general-ai-reasoning-response.v1","status":"PROPOSAL_GENERATED_PENDING_RUNTIME_V2_MATERIALIZATION",
              "request_id":request["request_id"],"response_id":binding["reasoning_response_id"],
              "proposal_ref":str(rel),"proposal_sha256":sha256_file(path),
              "provider":{"kind":"github-copilot-cli",**dict(chosen_meta or {})},
              "evidence_epoch_seen":binding["evidence_epoch_seen"],"evidence_bundle_sha256":binding["evidence_bundle_sha256"],
              "authoritative_evidence_refs_and_hashes":binding["authoritative_evidence_refs_and_hashes"],
              "accounting_basis":binding["accounting_basis"],"universe_basis":binding["universe_basis"],
              "current_open_mechanism_families":binding["current_open_mechanism_families"],
              "economic_outcome_opened":False,"v2_attempt_consumed":0,"created_utc":created}
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
