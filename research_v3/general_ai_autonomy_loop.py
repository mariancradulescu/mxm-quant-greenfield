"""Bounded zero-human continuation loop across AI reasoning and AI implementation."""
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path
from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.evidence_epoch import stale_reasoning_redirect
from research_v3.general_ai_director_bridge import drain
from research_v3.general_ai_implementation_executor import execute as implement, implementation_required, ImplementationRejected
from research_v3.general_ai_reasoning_provider import wake as reason, reasoning_required, AIReasoningProviderError
from research_v3.runtime_v2_primitives import GitCheckpointSink, load_json, atomic_write_json, iso
from research_v3.general_ai_director_bridge import NEXT_STATE_REL

VERSION="MXM_GENERAL_AI_AUTONOMY_LOOP_V2"
PROVIDER_RECOVERY_REL=Path("research_v3/ai_director/PROVIDER_RECOVERY_STATE.json")

def _recoverable_provider_failure(exc: Exception) -> bool:
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
    )
    if isinstance(exc, AIReasoningProviderError):
        return True
    if isinstance(exc, ImplementationRejected):
        return any(marker in detail for marker in markers)
    return False

def _request_fingerprint(root: Path, state: dict, phase: str) -> str:
    """Stable across timer wakes and CI updates; changes with research authority."""
    epoch=load_json(root/Path("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json"),{}) or {}
    authority={
        "phase":phase,
        "epoch":epoch.get("current_epoch"),
        "evidence_refs":epoch.get("authoritative_evidence_refs"),
        "trigger":epoch.get("trigger_event"),
        "decision":state.get("next_action"),
        "status":state.get("status"),
        "contract":load_json(root/Path("research_v3/RESEARCH_CONTRACT_V3.json"),{}),
        "universe":load_json(root/Path("data/AUTONOMOUS_UNIVERSE_GOVERNOR_V1.json"),{}),
    }
    return hashlib.sha256(json.dumps(authority,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

def _provider_unavailable(root: Path, state: dict, phase: str) -> dict | None:
    prior=dict(load_json(root/PROVIDER_RECOVERY_REL,{}) or {})
    legacy_quota=(prior.get("status") == "PROVIDER_RETRY_REQUIRED"
                  and "monthly quota" in str(prior.get("detail","")).lower()
                  and prior.get("request_fingerprint") is None)
    if legacy_quota:
        if prior.get("phase") == phase and prior.get("current_evidence_epoch") == state.get("current_research_evidence_epoch"):
            return prior
        return None
    if prior.get("status") != "PROVIDER_UNAVAILABLE" or prior.get("failure_class") != "MONTHLY_QUOTA_EXHAUSTED":
        return None
    if prior.get("request_fingerprint") != _request_fingerprint(root,state,phase):
        return None
    return prior

def _persist_provider_recovery(root: Path, exc: Exception, *, phase: str, git_checkpoint: bool, git_push: bool) -> dict:
    state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
    prior=dict(load_json(root/PROVIDER_RECOVERY_REL,{}) or {})
    attempts=int(prior.get("consecutive_recoverable_failures") or 0)+1
    quota="quota" in str(exc).lower()
    payload={
        "schema":"mxm.greenfield.provider-recovery-state.v1",
        "status":"PROVIDER_UNAVAILABLE" if quota else "PROVIDER_RETRY_REQUIRED",
        "request_fingerprint":_request_fingerprint(root,state,phase),
        "first_failure_utc":prior.get("first_failure_utc") or iso(),
        "failure_class":"MONTHLY_QUOTA_EXHAUSTED" if quota else type(exc).__name__,
        "retry_eligibility":"ONLY_AFTER_CONFIRMED_PROVIDER_RESET_OR_EXPLICIT_OPERATOR_OVERRIDE" if quota else "NEXT_LIVENESS_WAKE",
        "provider":"github-copilot-cli",
        "phase":phase,
        "detail":str(exc)[-1600:],
        "consecutive_recoverable_failures":attempts,
        "current_evidence_epoch":state.get("current_research_evidence_epoch"),
        "pending_status":state.get("status"),
        "pending_next_action":state.get("next_action"),
        "user_action_required":False,
        "economic_outcomes_opened_delta":0,
        "v2_attempts_consumed_delta":0,
        "search_budget_change":0,
        "retry_policy":"NO_AUTOMATIC_RETRY_WHILE_QUOTA_EXHAUSTED" if quota else "RETRY_ON_NEXT_LIVENESS_WAKE",
        "updated_utc":iso(),
    }
    atomic_write_json(root/PROVIDER_RECOVERY_REL,payload)
    GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("general_ai_provider_recovery",None)
    return payload

def run(root_value=".",*,git_checkpoint=False,git_push=False,max_cycles=8):
    root=Path(root_value).resolve(); trace=[]
    for cycle in range(1,max_cycles+1):
        validate_repository_state(root)
        state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
        stale=stale_reasoning_redirect(root,state)
        if stale is not None:
            state.update(stale); atomic_write_json(root/NEXT_STATE_REL,state)
            trace.append({"cycle":cycle,"kind":"STALE_REASONING_GUARD","status":"FRESH_GENERAL_AI_REASONING_REQUIRED",
                          "current_evidence_epoch":state.get("current_research_evidence_epoch")})
        if state.get("user_action_required") is True:
            return {"status":"EXTERNAL_USER_ACTION_REQUIRED","cycles":cycle-1,"trace":trace,"next_state":state}
        if reasoning_required(state):
            blocked=_provider_unavailable(root,state,"GENERAL_AI_REASONING")
            if blocked is not None:
                return {"status":"PROVIDER_UNAVAILABLE","cycles":cycle-1,"trace":trace,"recovery":blocked,"next_state":state}
            try:
                r=reason(root,git_checkpoint=git_checkpoint,git_push=git_push)
            except Exception as exc:
                if not _recoverable_provider_failure(exc):
                    raise
                recovery=_persist_provider_recovery(root,exc,phase="GENERAL_AI_REASONING",git_checkpoint=git_checkpoint,git_push=git_push)
                trace.append({"cycle":cycle,"kind":"RECOVERABLE_PROVIDER_FAILURE","phase":"GENERAL_AI_REASONING","recovery":recovery})
                return {"status":recovery["status"],"cycles":cycle,"trace":trace,"recovery":recovery,"next_state":state}
            d=drain(root,git_checkpoint=git_checkpoint,git_push=git_push)
            trace.append({"cycle":cycle,"kind":"GENERAL_AI_REASONING","reasoning":r,"drain_status":d.get("status")})
            continue
        if implementation_required(state):
            blocked=_provider_unavailable(root,state,"GENERAL_AI_IMPLEMENTATION")
            if blocked is not None:
                return {"status":"PROVIDER_UNAVAILABLE","cycles":cycle-1,"trace":trace,"recovery":blocked,"next_state":state}
            try:
                out=implement(root,git_checkpoint=git_checkpoint,git_push=git_push)
            except Exception as exc:
                if not _recoverable_provider_failure(exc):
                    raise
                recovery=_persist_provider_recovery(root,exc,phase="GENERAL_AI_IMPLEMENTATION",git_checkpoint=git_checkpoint,git_push=git_push)
                trace.append({"cycle":cycle,"kind":"RECOVERABLE_PROVIDER_FAILURE","phase":"GENERAL_AI_IMPLEMENTATION","recovery":recovery})
                return {"status":recovery["status"],"cycles":cycle,"trace":trace,"recovery":recovery,"next_state":state}
            trace.append({"cycle":cycle,"kind":"GENERAL_AI_IMPLEMENTATION","result_status":out.get("status")})
            if out.get("status") in {"EXTERNAL_DATA_REQUIRED","PENDING_EXACT_HEAD_GREEN"}:
                return {"status":out["status"],"cycles":cycle,"trace":trace,"result":out}
            continue
        return {"status":"QUIESCENT_NO_ACTION","cycles":cycle-1,"trace":trace,"next_state":state}
    return {"status":"BOUNDED_CONTINUATION_CHECKPOINT","cycles":max_cycles,"trace":trace,
            "next_state":dict(load_json(root/NEXT_STATE_REL,{}) or {})}

def main(argv=None):
    p=argparse.ArgumentParser(description=VERSION); p.add_argument("command",choices=("continue",)); p.add_argument("--root",default=".")
    p.add_argument("--git-checkpoint",action="store_true"); p.add_argument("--git-push",action="store_true"); p.add_argument("--max-cycles",type=int,default=8); a=p.parse_args(argv)
    out=run(a.root,git_checkpoint=a.git_checkpoint,git_push=a.git_push,max_cycles=a.max_cycles)
    print(json.dumps(out,sort_keys=True,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
