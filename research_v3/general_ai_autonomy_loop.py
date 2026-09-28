"""Bounded zero-human continuation loop across AI reasoning and AI implementation."""
from __future__ import annotations
import argparse, json, hashlib, os, subprocess
from pathlib import Path
from research_v3.evidence_epoch import stale_reasoning_redirect, refresh_derived_views, current_evidence_epoch, current_evidence_binding
from research_v3.general_ai_director_bridge import drain, project_snapshot
from research_v3.general_ai_implementation_executor import execute as implement, implementation_required, ImplementationRejected, ImplementationProviderAttemptError
from research_v3.execution_router import deterministic_operation_required
from research_v3.deterministic_operation_executor import execute_chain as execute_deterministic_chain
from research_v3.general_ai_reasoning_provider import wake as reason, reasoning_required, AIReasoningProviderError
from research_v3.general_ai_reasoning_provider import build_reasoning_request
from research_v3.runtime_v2_primitives import GitCheckpointSink, load_json, atomic_write_json, iso, sha256_file
from research_v3.general_ai_director_bridge import NEXT_STATE_REL

VERSION="MXM_GENERAL_AI_AUTONOMY_LOOP_V2"
PROVIDER_RECOVERY_REL=Path("research_v3/ai_director/PROVIDER_RECOVERY_STATE.json")
PROVIDER_USAGE_REL=Path("research_v3/ai_director/PROVIDER_USAGE_V1.json")
BLOCKED_SCOPES_REL=Path("research_v3/ai_director/BLOCKED_FRONTIER_SCOPES_V1.json")
MAX_ELIGIBILITY_RETRIES=2

def _recover_eligibility_rejection(root:Path,state:dict,rejection:dict,*,git_checkpoint:bool,git_push:bool)->dict:
    """Retire rejected implementation intent and bind a finite new semantic request to feedback."""
    epoch=current_evidence_epoch(root)
    previous=dict(state.get("eligibility_retry") or {})
    count=(int(previous.get("count") or 0) if previous.get("evidence_epoch")==epoch else 0)+1
    retired={"request_id":rejection.get("request_id"),"proposal_id":rejection.get("proposal_id"),
             "reason":rejection.get("reason"),"evidence_epoch":epoch,"count":count}
    next_state=dict(state)
    for key in ("source_ai_proposal_id","source_ai_proposal_hash","source_runtime_operation_id",
                "implementation_scope","implementation_ai_scope","implementation_task_scope",
                "fresh_director_decision_ref"):
        next_state.pop(key,None)
    next_state.update({"status":"FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_ELIGIBILITY_REJECTION" if count<=MAX_ELIGIBILITY_RETRIES else "ELIGIBILITY_RETRY_BUDGET_EXHAUSTED",
                       "next_action":"AI_REASSESS_HIGHEST_INFORMATION_LEGAL_NEXT_ACTION_FROM_CURRENT_EVIDENCE_EPOCH" if count<=MAX_ELIGIBILITY_RETRIES else "WAIT_FOR_NEW_MATERIAL_EVIDENCE_OR_AUTHORITY",
                       "ai_reasoning_required":count<=MAX_ELIGIBILITY_RETRIES,
                       "research_judgment_required":count<=MAX_ELIGIBILITY_RETRIES,
                       "implementation_ai_required":False,"implementation_satisfied":False,
                       "eligibility_retry":retired,"current_research_evidence_epoch":epoch})
    atomic_write_json(root/NEXT_STATE_REL,next_state)
    refresh_derived_views(root)
    GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("general_ai_eligibility_recovery",None)
    return next_state
try:
    MAX_RECOVERABLE_PROVIDER_FAILURES=max(2,min(5,int(os.environ.get("MXM_PROVIDER_MAX_RECOVERABLE_FAILURES","2"))))
except ValueError:
    MAX_RECOVERABLE_PROVIDER_FAILURES=2

def _record_invocation(root: Path, state: dict, phase: str, outcome: str, retryable: bool, advanced: bool, *, git_checkpoint: bool=False, git_push: bool=False) -> None:
    """Track runtime provider invocations without guessing CLI credits or selected model."""
    doc=dict(load_json(root/PROVIDER_USAGE_REL,{}) or {})
    rows=list(doc.get("invocations") or [])
    rows.append({
        "timestamp":iso(), "provider":"github-copilot-cli",
        "model_requested":os.environ.get("MXM_COPILOT_MODEL" if phase=="GENERAL_AI_REASONING" else "MXM_COPILOT_IMPLEMENTATION_MODEL","auto"),
        "actual_model_identity":None, "actual_credit_usage":None,
        "request_fingerprint":_request_fingerprint(root,state,phase),
        "purpose":phase, "evidence_epoch":state.get("current_research_evidence_epoch"),
        "outcome":outcome, "retryable":retryable, "material_state_advancement":advanced,
    })
    atomic_write_json(root/PROVIDER_USAGE_REL,{
        "schema":"mxm.greenfield.provider-usage.v1",
        "measurement_scope":"runtime provider attempts; all handled success, timeout, transport-failure and rejected attempts are counted; internal CLI credits and auto-selected model identity remain unknown",
        "provider_invocations":len(rows),
        "provider_attempts":len(rows),
        "successful_reasoning_invocations":sum(x["purpose"]=="GENERAL_AI_REASONING" and x["outcome"]=="SUCCESS" for x in rows),
        "successful_implementation_invocations":sum(x["purpose"]=="GENERAL_AI_IMPLEMENTATION" and x["outcome"]=="SUCCESS" for x in rows),
        "failed_or_timeout_invocations":sum(x.get("outcome")!="SUCCESS" for x in rows),
        "timeout_invocations":sum("TIMEOUT" in str(x.get("outcome") or "").upper() for x in rows),
        "material_state_advancing_invocations":sum(bool(x.get("material_state_advancement")) for x in rows),
        "quota_failures":sum(x["outcome"]=="PROVIDER_UNAVAILABLE" for x in rows),
        "invocations":rows,
    })
    GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("general_ai_provider_usage",None)


def _recoverable_provider_failure(exc: Exception) -> bool:
    if isinstance(exc,subprocess.TimeoutExpired):
        return True
    detail=f"{type(exc).__name__}: {exc}".lower()
    markers=(
        "monthly quota",
        "quota",
        "rate limit",
        "rate-limit",
        "too many requests",
        "http 429",
        "status 429",
        "temporarily unavailable",
        "service unavailable",
        "copilot implementation failed",
        "copilot cli failed",
        "all configured general reasoning attempts failed",
        "timed out",
        "timeout",
    )
    if isinstance(exc, AIReasoningProviderError):
        return True
    if isinstance(exc, ImplementationRejected):
        return any(marker in detail for marker in markers)
    return False

def _provider_attempt_was_started(exc:Exception)->bool:
    return isinstance(exc,(subprocess.TimeoutExpired,ImplementationProviderAttemptError,AIReasoningProviderError))

def _request_fingerprint(root: Path, state: dict, phase: str) -> str:
    """Bind provider spend to material authority, never CI/head/checkpoint churn."""
    binding=current_evidence_binding(root)
    semantic_authority={
        "authorizing_evidence_epoch":state.get("authorizing_evidence_epoch"),
        "source_ai_proposal_id":state.get("source_ai_proposal_id"),
        "source_ai_proposal_hash":state.get("source_ai_proposal_hash"),
        "fresh_director_decision_ref":state.get("fresh_director_decision_ref"),
        "status":state.get("status"),
        "next_action":state.get("next_action"),
    }
    required_capability=(
        state.get("next_deterministic_operation_ref")
        or state.get("implementation_task_scope")
        or state.get("implementation_ai_scope")
        or state.get("implementation_scope")
        or state.get("next_action")
    )
    authority={
        "phase":phase,
        "evidence_epoch":binding["evidence_epoch"],
        "evidence_bundle_sha256":binding["evidence_bundle_sha256"],
        "material_input_hashes":binding["authoritative_evidence_refs_and_hashes"],
        "semantic_authority":semantic_authority,
        "blocked_scope_set":_blocked_scopes(root),
        "required_capability":required_capability,
        "contract":load_json(root/Path("research_v3/RESEARCH_CONTRACT_V3.json"),{}),
        "universe":load_json(root/Path("data/AUTONOMOUS_UNIVERSE_GOVERNOR_V1.json"),{}),
    }
    return hashlib.sha256(json.dumps(authority,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

def _blocked_scopes(root: Path) -> list[str]:
    doc=load_json(root/BLOCKED_SCOPES_REL,{}) or {}
    if doc.get("schema")=="mxm.greenfield.blocked-frontier-scopes.v1":
        return sorted({row["scope_id"] for row in doc.get("items",[]) if row.get("status")=="PARKED_LOCAL_FRONTIER"})
    request=load_json(root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",{}) or {}
    return sorted(set(request.get("blocked_scope_ids") or [])) if request.get("scope_status")=="PARKED_LOCAL_FRONTIER" else []

def _park_authority(root: Path, state: dict, request: dict, *, git_checkpoint: bool, git_push: bool) -> bool:
    """Scope a legacy request only when canonical state supplies one unambiguous blocked family."""
    if request.get("scope_status")=="PARKED_LOCAL_FRONTIER":
        return True
    blocked=list(request.get("blocked_scope_ids") or [])
    open_families=set(current_evidence_binding(root).get("current_open_mechanism_families") or [])
    if (request.get("evidence_epoch")!=state.get("current_research_evidence_epoch")
            or len(blocked)!=1 or blocked[0] not in open_families
            or not state.get("broader_universe_remains_open")):
        return False
    # Scope comes from canonical machine state, not free-text provider output.
    parked=dict(request,scope_status="PARKED_LOCAL_FRONTIER",blocked_scope_ids=blocked,
                scope_provenance={"source_request_id":request.get("request_id"),
                                  "binding_class":"EXPLICIT_MACHINE_OWNED_FRONTIER_SCOPE"})
    atomic_write_json(root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",parked)
    document=dict(load_json(root/BLOCKED_SCOPES_REL,{}) or {})
    items=list(document.get("items") or [])
    if not any(row.get("source_request_id")==request.get("request_id") for row in items):
        items.append({"scope_id":blocked[0],"status":"PARKED_LOCAL_FRONTIER",
                      "source_request_id":request.get("request_id"),
                      "source_evidence_epoch":request.get("evidence_epoch"),
                      "requested_authority_or_class":request.get("requested_authority_or_class")})
    atomic_write_json(root/BLOCKED_SCOPES_REL,{"schema":"mxm.greenfield.blocked-frontier-scopes.v1",
                                             "status":"LOCAL_BLOCKERS_ONLY","items":items})
    GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("scoped_authority_blocker",None)
    return True

def _current_authority_request(root:Path,state:dict)->dict|None:
    """Recover the exact local authority request from the currently accepted AI proposal.

    The accepted proposal, not stale inherited state fields, owns the blocked scope.
    """
    proposal_id=str(state.get("source_ai_proposal_id") or "").strip()
    proposal_hash=str(state.get("source_ai_proposal_hash") or "").strip()
    if not proposal_id and not proposal_hash:
        return None
    registry=load_json(root/"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json",{}) or {}
    matches=[
        row for row in list(registry.get("accepted") or [])
        if (not proposal_id or row.get("proposal_id")==proposal_id)
        and (not proposal_hash or row.get("proposal_hash")==proposal_hash)
    ]
    if len(matches)!=1:
        return None
    proposal_ref=str(matches[0].get("proposal_ref") or "").strip()
    proposal=load_json(root/proposal_ref,{}) if proposal_ref else {}
    decision=dict((proposal or {}).get("decision") or {})
    explicit_authority=str(decision.get("status") or "").upper()=="ADDITIONAL_AUTHORITY_REQUIRED"
    prospective_authority=(str(decision.get("action") or "").upper()=="REQUEST_PROSPECTIVE_AUTHORITY"
                           or str(decision.get("decision_type") or "").upper()=="HOLD_FOR_DISTINCT_PROSPECTIVE_AUTHORITY")
    prospective_authority=(prospective_authority
                           and state.get("status")=="ADDITIONAL_AUTHORITY_REQUIRED")
    if not (explicit_authority or prospective_authority):
        return None
    scope=str(decision.get("blocked_scope_id") or
              ((decision.get("selected_mechanism_family") or decision.get("selected_scope")) if prospective_authority else "") or "").strip()
    if scope in _blocked_scopes(root):
        return None
    requested=str(decision.get("requested_authority_or_class") or state.get("requested_authority_or_class") or "").strip()
    if not scope or not requested:
        return None
    binding=dict((proposal or {}).get("evidence_binding") or {})
    request_id=str(binding.get("reasoning_request_id") or ((proposal or {}).get("provider") or {}).get("reasoning_request_id") or "").strip()
    if not request_id:
        request_id="authority_"+hashlib.sha256(json.dumps({
            "proposal_hash":matches[0].get("proposal_hash"),"scope":scope,
            "epoch":state.get("current_research_evidence_epoch")
        },sort_keys=True,separators=(",",":")).encode()).hexdigest()[:32]
    return {
        "schema":"mxm.greenfield.additional-authority-request.v1",
        "status":"ADDITIONAL_AUTHORITY_REQUIRED",
        "requested_authority_or_class":requested,
        "rationale":str(decision.get("rationale") or state.get("rationale") or "")[:700],
        "request_id":request_id,
        "evidence_epoch":state.get("current_research_evidence_epoch"),
        "blocked_scope_ids":[scope],
        "no_economic_outcome":True,
        "source_ai_proposal_id":proposal_id or None,
        "source_ai_proposal_hash":proposal_hash or None,
    }

def _park_current_local_authority(root:Path,state:dict,*,git_checkpoint:bool,git_push:bool)->dict|None:
    request=_current_authority_request(root,state)
    if request is None:
        return None
    if not _park_authority(root,state,request,git_checkpoint=False,git_push=False):
        return None
    parked=dict(load_json(root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",{}) or {})
    next_state=_resume_after_local_park(root,state,git_checkpoint=git_checkpoint,git_push=git_push)
    return {"request":parked,"next_state":next_state}

def _resume_after_local_park(root:Path,state:dict,*,git_checkpoint:bool,git_push:bool)->dict:
    next_state=dict(state)
    for key in ("blocked_scope_id","requested_authority_or_class","implementation_scope","implementation_ai_scope",
                "implementation_task_scope","source_ai_proposal_id","source_ai_proposal_hash"):
        next_state.pop(key,None)
    next_state.update({
        "status":"FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_LOCAL_AUTHORITY_PARK",
        "next_action":"AI_SELECT_HIGHEST_INFORMATION_LEGAL_NEXT_ACTION_OUTSIDE_PARKED_LOCAL_FRONTIERS",
        "ai_reasoning_required":True,
        "research_judgment_required":True,
        "implementation_ai_required":False,
        "implementation_satisfied":False,
        "implementation_scope_complete":False,
        "user_action_required":False,
        "external_data_required":False,
        "external_data_gate":None,
        "external_gate":None,
        "additional_authority_request_ref":"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",
    })
    atomic_write_json(root/NEXT_STATE_REL,next_state)
    refresh_derived_views(root)
    GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("local_authority_park_and_continue",None)
    return next_state

def _material_state_signature(state: dict) -> str:
    """Hash only routing/research state that can represent material progress.

    Provider usage, checkpoint timestamps and Git HEAD churn are deliberately excluded.
    """
    keys=(
        "status","next_action","current_research_evidence_epoch","evidence_epoch",
        "authorizing_evidence_epoch","ai_reasoning_required","research_judgment_required",
        "implementation_ai_required","next_deterministic_operation_ref",
        "user_action_required","external_data_required","external_gate","external_data_gate",
        "source_ai_proposal_id","source_ai_proposal_hash","source_runtime_operation_id",
        "source_implementation_id","completed_family","completed_structural_report_ref",
        "latest_material_structural_result_ref","family_result","accounting","safety",
    )
    payload={k:state.get(k) for k in keys if k in state}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


def _provider_unavailable(root: Path, state: dict, phase: str) -> dict | None:
    prior=dict(load_json(root/PROVIDER_RECOVERY_REL,{}) or {})
    if os.environ.get("MXM_COPILOT_QUOTA_RESET_CONFIRMED") == "1":
        return None
    legacy_quota=(prior.get("status") == "PROVIDER_RETRY_REQUIRED"
                  and "monthly quota" in str(prior.get("detail","")).lower())
    provider_blocked=prior.get("status") in {"PROVIDER_UNAVAILABLE","AUTH_OR_ENTITLEMENT_FAILURE","PROBE_INCONCLUSIVE"}
    exhausted=(prior.get("status")=="PROVIDER_RETRY_BUDGET_EXHAUSTED"
               and prior.get("phase")==phase
               and prior.get("request_fingerprint")==_request_fingerprint(root,state,phase))
    # Account entitlement is global across phases; bounded retry exhaustion is local to one semantic request.
    return prior if legacy_quota or provider_blocked or exhausted else None

def _persist_provider_recovery(root: Path, exc: Exception, *, phase: str, git_checkpoint: bool, git_push: bool) -> dict:
    state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
    prior=dict(load_json(root/PROVIDER_RECOVERY_REL,{}) or {})
    fingerprint=_request_fingerprint(root,state,phase)
    same_request=prior.get("request_fingerprint")==fingerprint and prior.get("phase")==phase
    previous_attempts=int(prior.get("consecutive_recoverable_failures") or 0) if same_request else 0
    attempts=previous_attempts+1
    quota="quota" in str(exc).lower()
    status=("PROVIDER_UNAVAILABLE" if quota else
            "PROVIDER_RETRY_BUDGET_EXHAUSTED" if attempts>=MAX_RECOVERABLE_PROVIDER_FAILURES else
            "PROVIDER_RETRY_REQUIRED")
    payload={
        "schema":"mxm.greenfield.provider-recovery-state.v1",
        "status":status,
        "request_fingerprint":fingerprint,
        "first_failure_utc":(prior.get("first_failure_utc") or iso()) if same_request else iso(),
        "failure_class":"MONTHLY_QUOTA_EXHAUSTED" if quota else type(exc).__name__,
        "retry_eligibility":("ONLY_AFTER_CONFIRMED_PROVIDER_RESET_OR_EXPLICIT_OPERATOR_OVERRIDE" if quota else
                             "ONLY_AFTER_NEW_SEMANTIC_REQUEST_OR_PROVIDER_RECOVERY_SIGNAL" if status=="PROVIDER_RETRY_BUDGET_EXHAUSTED" else
                             "NEXT_LIVENESS_WAKE"),
        "provider":"github-copilot-cli",
        "phase":phase,
        "detail":str(exc)[-1600:],
        "consecutive_recoverable_failures":attempts,
        "max_recoverable_failures":MAX_RECOVERABLE_PROVIDER_FAILURES,
        "current_evidence_epoch":state.get("current_research_evidence_epoch"),
        "pending_status":state.get("status"),
        "pending_next_action":state.get("next_action"),
        "user_action_required":False,
        "economic_outcomes_opened_delta":0,
        "v2_attempts_consumed_delta":0,
        "search_budget_change":0,
        "retry_policy":("NO_AUTOMATIC_RETRY_WHILE_QUOTA_EXHAUSTED" if quota else
                        "FINITE_RETRY_BUDGET_EXHAUSTED" if status=="PROVIDER_RETRY_BUDGET_EXHAUSTED" else
                        "RETRY_ON_NEXT_LIVENESS_WAKE"),
        "updated_utc":iso(),
    }
    atomic_write_json(root/PROVIDER_RECOVERY_REL,payload)
    GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("general_ai_provider_recovery",None)
    return payload

def run(root_value=".",*,git_checkpoint=False,git_push=False,max_cycles=8):
    root=Path(root_value).resolve(); trace=[]
    initial_epoch=current_evidence_epoch(root)
    for cycle in range(1,max_cycles+1):
        refresh_derived_views(root)
        state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
        if "accounting" in state:
            snapshot=project_snapshot(root)
            expected_accounting={
                "v2_attempts_used":snapshot["v2_attempts_used"],
                "v2_search_budget_remaining":snapshot["v2_search_budget_remaining"],
                "economic_outcomes_opened":snapshot["economic_outcomes_opened"],
            }
            if dict(state.get("accounting") or {})!=expected_accounting:
                raise RuntimeError("canonical active-state accounting diverged from durable economic ledger")
        safety=dict(state.get("safety") or {})
        if bool(safety.get("live_orders_authorized") or safety.get("protected_evidence_opened") or safety.get("protected_forward_opened")):
            raise RuntimeError("canonical active state crosses protected/live safety boundary")
        stale=stale_reasoning_redirect(root,state)
        if stale is not None:
            state.update(stale); atomic_write_json(root/NEXT_STATE_REL,state)
            trace.append({"cycle":cycle,"kind":"STALE_REASONING_GUARD","status":"FRESH_GENERAL_AI_REASONING_REQUIRED",
                          "current_evidence_epoch":state.get("current_research_evidence_epoch")})
        rejection=load_json(root/"research_v3/ai_director/PROPOSAL_ELIGIBILITY_REJECTION_V1.json",{}) or {}
        registry=load_json(root/"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json",{}) or {}
        accepted=any(row.get("proposal_id")==state.get("source_ai_proposal_id") and
                     row.get("proposal_hash")==state.get("source_ai_proposal_hash")
                     for row in registry.get("accepted",[]) if state.get("source_ai_proposal_id"))
        if (rejection.get("status")=="REJECTED_BEFORE_REGISTRY_AND_IMPLEMENTATION"
                and state.get("status")!="MATERIAL_INTEGRITY_FAILURE"
                and rejection.get("evidence_epoch")==current_evidence_epoch(root)
                and not state.get("eligibility_retry")
                and (not accepted or str(state.get("next_action") or "").startswith("AI_"))
                ):
            state=_recover_eligibility_rejection(root,state,rejection,git_checkpoint=git_checkpoint,git_push=git_push)
            trace.append({"cycle":cycle,"kind":"REJECTED_PROPOSAL_AUTHORITY_RETIRED"})
            continue
        if state.get("status")=="MATERIAL_INTEGRITY_FAILURE" and state.get("integrity_gate"):
            return {"status":"MATERIAL_INTEGRITY_FAILURE","progress_class":"MATERIAL_FAILURE","cycles":cycle-1,"trace":trace,"next_state":state}
        if state.get("user_action_required") is True or state.get("external_data_required") is True or state.get("external_gate") not in (None,"",{},[]) or state.get("external_data_gate") not in (None,"",{},[]):
            return {"status":"EXTERNAL_USER_ACTION_REQUIRED" if state.get("user_action_required") is True else "EXTERNAL_DATA_REQUIRED","progress_class":"LEGITIMATE_EXTERNAL_GATE","cycles":cycle-1,"trace":trace,"next_state":state}
        if state.get("status")=="ADDITIONAL_AUTHORITY_REQUIRED" and state.get("requested_authority_or_class"):
            parked=_park_current_local_authority(root,state,git_checkpoint=git_checkpoint,git_push=git_push)
            if parked is None:
                if accepted and state.get("implementation_ai_required") is True:
                    feedback={"request_id":state.get("source_ai_proposal_id"),
                              "proposal_id":state.get("source_ai_proposal_id"),
                              "evidence_epoch":current_evidence_epoch(root),
                              "reason":"Accepted authority request lacks an explicit machine-checkable blocked_scope_id or selected_scope; implementation is not authority to invent one."}
                    atomic_write_json(root/"research_v3/ai_director/UNSCOPED_AUTHORITY_REJECTION_V1.json",feedback)
                    state=_recover_eligibility_rejection(root,state,feedback,git_checkpoint=git_checkpoint,git_push=git_push)
                    trace.append({"cycle":cycle,"kind":"UNSCOPED_ACCEPTED_AUTHORITY_RETIRED","feedback":feedback})
                    if reasoning_required(state):
                        continue
                return {"status":"ADDITIONAL_AUTHORITY_REQUIRED","progress_class":"MISSING_RESEARCH_AUTHORITY",
                        "cycles":cycle-1,"trace":trace,"next_state":state}
            trace.append({"cycle":cycle,"kind":"LOCAL_AUTHORITY_PARKED",
                          "blocked_scope_ids":parked["request"].get("blocked_scope_ids"),
                          "provider_calls_delta":0})
            state=dict(parked["next_state"])
            continue
        if deterministic_operation_required(root,state):
            out=execute_deterministic_chain(root,max_operations=max_cycles-cycle+1,git_checkpoint=git_checkpoint,git_push=git_push)
            if out.get("status")=="PENDING_EXACT_HEAD_GREEN":
                trace.append({"cycle":cycle,"kind":"PENDING_EXACT_HEAD_GREEN","operation_name":out.get("operation_name"),"exact_head":out.get("exact_head"),"provider_calls_delta":0})
                return {"status":"PENDING_EXACT_HEAD_GREEN","progress_class":"SAFE_NO_PROGRESS","cycles":cycle,
                        "trace":trace,"result":out,"next_state":out.get("next_state") or state}
            trace.append({"cycle":cycle,"kind":"DETERMINISTIC_OPERATION","completed_operations":out.get("completed_operations"),"provider_calls_delta":out.get("provider_calls_delta",0)})
            state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
            if state.get("user_action_required") is True or state.get("external_data_required") is True:
                return {"status":"EXTERNAL_USER_ACTION_REQUIRED" if state.get("user_action_required") is True else "EXTERNAL_DATA_REQUIRED","progress_class":"LEGITIMATE_EXTERNAL_GATE","cycles":cycle,"trace":trace,"next_state":state,"result":out}
            continue
        if reasoning_required(state):
            prior_authority=load_json(root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",{}) or {}
            accepted_authority=load_json(root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_ACCEPTANCE_V1.json",{}) or {}
            if (prior_authority.get("status")=="ADDITIONAL_AUTHORITY_REQUIRED"
                    and prior_authority.get("evidence_epoch")==state.get("current_research_evidence_epoch")
                    and accepted_authority.get("source_request_id")!=prior_authority.get("request_id")):
                if not _park_authority(root,state,prior_authority,git_checkpoint=git_checkpoint,git_push=git_push):
                    return {"status":"ADDITIONAL_AUTHORITY_REQUIRED","progress_class":"MISSING_EXTERNAL_AUTHORITY",
                            "cycles":cycle-1,"trace":trace,"request":prior_authority,"next_state":state}
                prior_authority=load_json(root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",{})
                if build_reasoning_request(root)["request_id"]==prior_authority.get("request_id"):
                    return {"status":"ADDITIONAL_AUTHORITY_REQUIRED","progress_class":"MISSING_EXTERNAL_AUTHORITY",
                            "cycles":cycle-1,"trace":trace,"request":prior_authority,"next_state":state}
            blocked=_provider_unavailable(root,state,"GENERAL_AI_REASONING")
            if blocked is not None:
                return {"status":"PROVIDER_UNAVAILABLE","progress_class":"PROVIDER_UNAVAILABLE","cycles":cycle-1,"trace":trace,"recovery":blocked,"next_state":state}
            try:
                r=reason(root,git_checkpoint=git_checkpoint,git_push=git_push)
            except Exception as exc:
                if not _recoverable_provider_failure(exc):
                    if _provider_attempt_was_started(exc):
                        _record_invocation(root,state,"GENERAL_AI_REASONING","REJECTED_OR_FATAL",False,False,git_checkpoint=git_checkpoint,git_push=git_push)
                    raise
                recovery=_persist_provider_recovery(root,exc,phase="GENERAL_AI_REASONING",git_checkpoint=git_checkpoint,git_push=git_push)
                outcome="TIMEOUT" if isinstance(exc,subprocess.TimeoutExpired) else recovery["status"]
                _record_invocation(root,state,"GENERAL_AI_REASONING",outcome,recovery["status"]=="PROVIDER_RETRY_REQUIRED",False,git_checkpoint=git_checkpoint,git_push=git_push)
                trace.append({"cycle":cycle,"kind":"RECOVERABLE_PROVIDER_FAILURE","phase":"GENERAL_AI_REASONING","recovery":recovery})
                blocked=recovery["status"] in {"PROVIDER_UNAVAILABLE","PROVIDER_RETRY_BUDGET_EXHAUSTED"}
                return {"status":recovery["status"],"progress_class":"PROVIDER_UNAVAILABLE" if blocked else "SAFE_NO_PROGRESS","cycles":cycle,"trace":trace,"recovery":recovery,"next_state":state}
            if r.get("status")=="REJECTED_BEFORE_REGISTRY_AND_IMPLEMENTATION":
                _record_invocation(root,state,"GENERAL_AI_REASONING","REJECTED_BY_ELIGIBILITY",False,False,git_checkpoint=git_checkpoint,git_push=git_push)
                state=_recover_eligibility_rejection(root,state,r,git_checkpoint=git_checkpoint,git_push=git_push)
                trace.append({"cycle":cycle,"kind":"PROPOSAL_REJECTED_PRE_REGISTRY","rejection":r})
                if not reasoning_required(state):
                    return {"status":"ELIGIBILITY_RETRY_BUDGET_EXHAUSTED","progress_class":"MISSING_RESEARCH_AUTHORITY",
                            "cycles":cycle,"trace":trace,"next_state":state}
                continue
            d=drain(root,git_checkpoint=git_checkpoint,git_push=git_push)
            if r.get("status")!="EXTERNAL_PROPOSAL_REUSED":
                _record_invocation(root,state,"GENERAL_AI_REASONING","SUCCESS",False,d.get("status") not in {"NO_PENDING_PROPOSAL","PROPOSAL_ALREADY_DURABLE"},git_checkpoint=git_checkpoint,git_push=git_push)
            trace.append({"cycle":cycle,"kind":"GENERAL_AI_REASONING","reasoning":r,"drain_status":d.get("status")})
            if r.get("status")=="ADDITIONAL_AUTHORITY_REQUIRED":
                if _park_authority(root,state,r,git_checkpoint=git_checkpoint,git_push=git_push):
                    state=_resume_after_local_park(root,state,git_checkpoint=git_checkpoint,git_push=git_push)
                    trace.append({"cycle":cycle,"kind":"LOCAL_AUTHORITY_PARKED",
                                  "blocked_scope_ids":r.get("blocked_scope_ids"),"provider_calls_delta":0})
                    continue
                return {"status":"ADDITIONAL_AUTHORITY_REQUIRED","progress_class":"MISSING_EXECUTION_AUTHORITY","cycles":cycle,"trace":trace,"next_state":state,"request":r}
            continue
        if implementation_required(state,root):
            blocked=_provider_unavailable(root,state,"GENERAL_AI_IMPLEMENTATION")
            if blocked is not None:
                return {"status":"PROVIDER_UNAVAILABLE","progress_class":"PROVIDER_UNAVAILABLE","cycles":cycle-1,"trace":trace,"recovery":blocked,"next_state":state}
            before_material=_material_state_signature(state)
            try:
                out=implement(root,git_checkpoint=git_checkpoint,git_push=git_push)
            except Exception as exc:
                if not _recoverable_provider_failure(exc):
                    if _provider_attempt_was_started(exc):
                        _record_invocation(root,state,"GENERAL_AI_IMPLEMENTATION","REJECTED_OR_FATAL",False,False,git_checkpoint=git_checkpoint,git_push=git_push)
                    raise
                recovery=_persist_provider_recovery(root,exc,phase="GENERAL_AI_IMPLEMENTATION",git_checkpoint=git_checkpoint,git_push=git_push)
                outcome="TIMEOUT" if isinstance(exc,subprocess.TimeoutExpired) else recovery["status"]
                _record_invocation(root,state,"GENERAL_AI_IMPLEMENTATION",outcome,recovery["status"]=="PROVIDER_RETRY_REQUIRED",False,git_checkpoint=git_checkpoint,git_push=git_push)
                trace.append({"cycle":cycle,"kind":"RECOVERABLE_PROVIDER_FAILURE","phase":"GENERAL_AI_IMPLEMENTATION","recovery":recovery})
                blocked=recovery["status"] in {"PROVIDER_UNAVAILABLE","PROVIDER_RETRY_BUDGET_EXHAUSTED"}
                return {"status":recovery["status"],"progress_class":"PROVIDER_UNAVAILABLE" if blocked else "SAFE_NO_PROGRESS","cycles":cycle,"trace":trace,"recovery":recovery,"next_state":state}
            after_state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
            advanced=_material_state_signature(after_state)!=before_material or bool(out.get("changed_paths"))
            provider_called=out.get("provider_called") is not False and out.get("provider") is not None
            if provider_called:
                _record_invocation(root,state,"GENERAL_AI_IMPLEMENTATION","SUCCESS",False,advanced,git_checkpoint=git_checkpoint,git_push=git_push)
            trace.append({"cycle":cycle,"kind":"GENERAL_AI_IMPLEMENTATION","result_status":out.get("status"),"provider_called":provider_called,"material_state_advancement":advanced})
            if out.get("status") in {"EXTERNAL_DATA_REQUIRED","PENDING_EXACT_HEAD_GREEN"}:
                return {"status":out["status"],"progress_class":"LEGITIMATE_EXTERNAL_GATE" if out["status"]=="EXTERNAL_DATA_REQUIRED" else "SAFE_NO_PROGRESS","cycles":cycle,"trace":trace,"result":out}
            continue
        return {"status":"QUIESCENT_NO_ACTION","progress_class":"MATERIAL_PROGRESS" if current_evidence_epoch(root)!=initial_epoch else "SAFE_NO_PROGRESS","cycles":cycle-1,"trace":trace,"next_state":state}
    return {"status":"BOUNDED_CONTINUATION_CHECKPOINT","progress_class":"MATERIAL_PROGRESS" if current_evidence_epoch(root)!=initial_epoch else "SAFE_NO_PROGRESS","cycles":max_cycles,"trace":trace,
            "next_state":dict(load_json(root/NEXT_STATE_REL,{}) or {})}

def main(argv=None):
    p=argparse.ArgumentParser(description=VERSION); p.add_argument("command",choices=("continue",)); p.add_argument("--root",default=".")
    p.add_argument("--git-checkpoint",action="store_true"); p.add_argument("--git-push",action="store_true"); p.add_argument("--max-cycles",type=int,default=8); a=p.parse_args(argv)
    out=run(a.root,git_checkpoint=a.git_checkpoint,git_push=a.git_push,max_cycles=a.max_cycles)
    print(json.dumps(out,sort_keys=True,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
