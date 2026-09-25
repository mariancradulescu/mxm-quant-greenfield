"""Generic bridge from an accepted AI decision to a Runtime V2 economic operation.

It contains no research next-action table. The durable NEXT state supplies an explicit
runtime_operation_envelope_ref. The materializer validates that the referenced AI proposal
was already accepted as a NON_ECONOMIC decision, then hands the frozen operation plan to
Runtime V2. Runtime V2 remains the sole economic executor.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Mapping

from research_v3.economic_envelope_governor import validate as validate_research_envelope, EnvelopeIneligible
from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.autonomous_runtime_v2 import RuntimeV2
from research_v3.runtime_v2_primitives import GitCheckpointSink, sha256_file

SCHEMA = "mxm.greenfield.ai-authorized-runtime-operation-envelope.v1"

class EconomicEnvelopeError(RuntimeError): pass

def _load(root: Path, rel: str) -> dict[str, Any]:
    p=root/rel
    if not p.is_file(): raise EconomicEnvelopeError(f"missing durable ref: {rel}")
    return json.loads(p.read_text(encoding="utf-8"))

def _accepted_registry(root: Path) -> list[dict[str, Any]]:
    return list((_load(root,"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json").get("accepted") or []))

def validate_envelope(root: Path, envelope: Mapping[str, Any]) -> dict[str, Any]:
    if envelope.get("schema") != SCHEMA or envelope.get("status") != "AUTHORIZED_EXACT_HEAD_GREEN":
        raise EconomicEnvelopeError("economic operation envelope is not exact-head authorized")
    ai=envelope.get("ai_authorization") or {}
    matches=[x for x in _accepted_registry(root)
             if x.get("proposal_id")==ai.get("proposal_id")
             and x.get("operation_id")==ai.get("runtime_decision_operation_id")
             and x.get("proposal_hash")==ai.get("proposal_hash")]
    if len(matches)!=1 or matches[0].get("economic_outcome_opened") is not False:
        raise EconomicEnvelopeError("AI authorization is not uniquely accepted/non-economic")
    proposal=_load(root,str(ai.get("proposal_ref")))
    decision=proposal.get("decision") or {}
    if int((proposal.get("evidence_binding") or {}).get("evidence_epoch_seen",0) or 0)>=21:
        try:
            validate_research_envelope(root,envelope.get("experiment_governance") or {})
        except EnvelopeIneligible as exc:
            raise EconomicEnvelopeError("epoch-21 economic envelope prerequisite/breadth gate: "+str(exc)) from exc
    if decision.get("execute_exactly_once") is not True or decision.get("economic_execution_must_use_runtime_v2") is not True:
        raise EconomicEnvelopeError("AI proposal did not authorize exactly-once Runtime V2 execution")
    report=validate_repository_state(root)
    basis=envelope.get("basis_accounting") or {}
    for key in ("v2_attempts_used","v2_search_budget_remaining","economic_outcomes_opened"):
        if int(basis.get(key,-1)) != int(report["accounting"][key]):
            raise EconomicEnvelopeError(f"economic envelope accounting basis drift: {key}")
    plan=dict(envelope.get("runtime_plan") or {})
    safety=plan.get("safety") or {}
    if safety.get("protected_evidence_opened") is not False or safety.get("live_orders_authorized") is not False:
        raise EconomicEnvelopeError("economic envelope safety drift")
    if (plan.get("pre_outcome_gate") or {}).get("status")!="PASS":
        raise EconomicEnvelopeError("economic pre-outcome gate not PASS")
    if (plan.get("external_data") or {}).get("required") is True:
        raise EconomicEnvelopeError("generic materializer refuses unsatisfied external dependency")
    return {"control_plane":report,"plan":plan}

def materialize(root_value: str|Path, *, git_checkpoint: bool=False, git_push: bool=False) -> dict[str,Any]:
    root=Path(root_value).resolve()
    next_doc=_load(root,"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
    ref=next_doc.get("runtime_operation_envelope_ref")
    if not isinstance(ref,str) or not ref:
        return {"status":"NO_AUTHORIZED_ECONOMIC_ENVELOPE"}
    envelope=_load(root,ref)
    validated=validate_envelope(root,envelope)
    runtime=RuntimeV2(root,lease_seconds=900,checkpoint_sink=GitCheckpointSink(root,enabled=git_checkpoint,push=git_push),
                      owner_token="ai-economic-envelope-"+str(envelope.get("envelope_id",""))[:24])
    op_id,_=runtime.submit_operation(validated["plan"])
    expected=envelope.get("expected_operation_id")
    if expected and expected!=op_id:
        raise EconomicEnvelopeError(f"Runtime V2 operation identity drift: {op_id} != {expected}")
    outcome=runtime.run(max_operations=1)
    result_path=(validated["plan"].get("result_path") or f"research_v3/runtime_v2/results/{op_id}.json")
    payload={"status":outcome.status,"operation_id":op_id,"result_path":result_path}
    p=root/result_path
    if p.is_file(): payload["result_bytes_sha256"]=sha256_file(p)
    return payload

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("command",choices=("materialize",)); p.add_argument("--root",default=".")
    p.add_argument("--git-checkpoint",action="store_true"); p.add_argument("--git-push",action="store_true"); a=p.parse_args(argv)
    print(json.dumps(materialize(a.root,git_checkpoint=a.git_checkpoint,git_push=a.git_push),sort_keys=True,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
