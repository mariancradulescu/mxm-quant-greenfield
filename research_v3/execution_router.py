"""Authoritative execution-class router for MXM Research V3.

A non-empty next_action is never, by itself, authority to call an AI provider.
Routing is based on explicit durable authority and fail-closed gates.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Mapping

from research_v3.general_ai_reasoning_provider import reasoning_required
from research_v3.runtime_v2_primitives import canonical_bytes, load_json, sha256_bytes, sha256_file

DETERMINISTIC_SCHEMA = "mxm.greenfield.deterministic-next-operation.v1"
AUTHORIZED_DETERMINISTIC_STATUS = "AUTHORIZED_DETERMINISTIC_NON_ECONOMIC_OPERATION"

EXECUTION_CLASSES = (
    "MATERIAL_INTEGRITY_OR_EXTERNAL_GATE",
    "SEMANTIC_REASONING",
    "DETERMINISTIC_OPERATION",
    "NOVEL_AI_IMPLEMENTATION",
    "ECONOMIC_EXECUTION",
    "CTRADER_BUILD_OR_CERTIFICATION",
    "AUTHORITY_CI",
    "NO_WORK",
)

class RoutingError(RuntimeError):
    pass

def _root(value: str | Path) -> Path:
    return Path(value).resolve()

def _external_or_integrity_gate(state: Mapping[str, Any]) -> str | None:
    if state.get("status") == "MATERIAL_INTEGRITY_FAILURE":
        return "MATERIAL_INTEGRITY_FAILURE"
    if state.get("user_action_required") is True:
        return "USER_ACTION_REQUIRED"
    if state.get("external_data_required") is True:
        return "EXTERNAL_DATA_REQUIRED"
    if state.get("external_gate") not in (None, "", {}, []):
        return "EXTERNAL_GATE"
    gate = state.get("external_data_gate")
    if gate not in (None, "", {}, []):
        return "EXTERNAL_DATA_GATE"
    return None

def deterministic_operation_ref(state: Mapping[str, Any]) -> str | None:
    ref = state.get("next_deterministic_operation_ref")
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    embedded = state.get("deterministic_next_operation") or {}
    ref = embedded.get("operation_ref") if isinstance(embedded, Mapping) else None
    return str(ref).strip() if isinstance(ref, str) and ref.strip() else None

def _git_blob_sha1(path: Path) -> str:
    data=path.read_bytes()
    header=f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header+data).hexdigest()


def _validate_extended_operation_contract(root: Path, state: Mapping[str, Any], doc: Mapping[str, Any]) -> None:
    contract=doc.get("operation_contract")
    if contract in (None, {}):
        return
    if not isinstance(contract, Mapping):
        raise RoutingError("deterministic operation_contract must be an object")
    kind=str(contract.get("kind") or "")
    if kind!="HASH_BOUND_PYTHON_JSON_TRANSFORM_V1":
        raise RoutingError(f"unsupported deterministic operation contract kind: {kind or '<missing>'}")

    authorization=doc.get("authorization") or {}
    proposal_ref=str(authorization.get("accepted_proposal_ref") or "").strip()
    proposal_id=str(authorization.get("proposal_id") or "").strip()
    proposal_hash=str(authorization.get("proposal_hash") or "").strip()
    proposal_file_sha=str(authorization.get("accepted_proposal_file_sha256") or "").strip()
    registry_ref=str(authorization.get("proposal_registry_ref") or "").strip()
    if not all((proposal_ref,proposal_id,proposal_hash,proposal_file_sha,registry_ref)):
        raise RoutingError("extended deterministic operation missing proposal authorization binding")
    proposal_path=root/proposal_ref
    registry_path=root/registry_ref
    if not proposal_path.is_file() or not registry_path.is_file():
        raise RoutingError("extended deterministic proposal authority missing")
    if sha256_file(proposal_path)!=proposal_file_sha:
        raise RoutingError("extended deterministic proposal file hash mismatch")
    proposal=json.loads(proposal_path.read_text(encoding="utf-8"))
    if proposal.get("proposal_id")!=proposal_id or sha256_bytes(canonical_bytes(proposal))!=proposal_hash:
        raise RoutingError("extended deterministic proposal identity/hash mismatch")
    if state.get("source_ai_proposal_id")!=proposal_id or state.get("source_ai_proposal_hash")!=proposal_hash:
        raise RoutingError("extended deterministic operation does not match canonical proposal binding")
    registry=json.loads(registry_path.read_text(encoding="utf-8"))
    if not any(
        row.get("proposal_id")==proposal_id
        and row.get("proposal_hash")==proposal_hash
        and row.get("proposal_ref")==proposal_ref
        and row.get("economic_outcome_opened") is False
        and int(row.get("v2_attempt_consumed") or 0)==0
        for row in registry.get("accepted",[])
    ):
        raise RoutingError("extended deterministic proposal is not accepted in registry")
    if authorization.get("semantic_judgment_required") is not False or authorization.get("economic_authorization") is not False:
        raise RoutingError("extended deterministic authorization crosses semantic/economic boundary")

    safety=doc.get("safety") or {}
    if any(bool(safety.get(k)) for k in ("protected_forward_opened","live_orders_authorized","competition_start_authorized")):
        raise RoutingError("deterministic operation crosses protected/live safety boundary")

    bindings=doc.get("input_bindings")
    if not isinstance(bindings,list) or not bindings:
        raise RoutingError("extended deterministic operation requires hash-bound input_bindings")
    seen=set()
    for row in bindings:
        if not isinstance(row,Mapping):
            raise RoutingError("invalid deterministic input binding")
        rel=str(row.get("ref") or "").strip(); expected=str(row.get("sha256") or "").strip()
        if not rel or len(expected)!=64 or rel in seen:
            raise RoutingError("invalid or duplicate deterministic input binding")
        seen.add(rel); path=root/rel
        if not path.is_file():
            raise RoutingError(f"deterministic input authority missing: {rel}")
        if sha256_file(path)!=expected:
            raise RoutingError(f"deterministic input authority hash mismatch: {rel}")

    source=doc.get("source_authority") or {}
    feasibility_ref=str(source.get("current_feasibility_ref") or "").strip()
    feasibility_path=root/feasibility_ref
    if not feasibility_ref or not feasibility_path.is_file():
        raise RoutingError("current feasibility authority missing")
    feasibility=json.loads(feasibility_path.read_text(encoding="utf-8"))
    if feasibility.get("source_canonical_payload_sha256")!=source.get("accepted_canonical_payload_sha256"):
        raise RoutingError("accepted canonical broker payload hash mismatch")
    if feasibility.get("exact_current_eligible_identity_set_sha256")!=source.get("eligible_identity_set_sha256"):
        raise RoutingError("eligible identity-set authority hash mismatch")
    if int((feasibility.get("current_counts") or {}).get("current_eligible_post_exclusion_frontier") or 0)!=int(source.get("source_identity_count") or 0):
        raise RoutingError("eligible identity count authority mismatch")

    implementation_ref=str(contract.get("implementation_ref") or "").strip()
    implementation_path=root/implementation_ref
    if not implementation_ref or not implementation_path.is_file():
        raise RoutingError("deterministic transform implementation missing")
    expected_blob=str(contract.get("implementation_git_blob_sha1") or "").strip()
    if len(expected_blob)!=40 or _git_blob_sha1(implementation_path)!=expected_blob:
        raise RoutingError("deterministic transform implementation blob mismatch")
    if not str(contract.get("callable") or "").strip():
        raise RoutingError("deterministic transform callable missing")

    transport=contract.get("input_transport") or {}
    if transport.get("encoding")!="CONCAT_BASE64_GZIP_JSON":
        raise RoutingError("unsupported deterministic input transport encoding")
    refs=transport.get("fragment_refs"); hashes=transport.get("fragment_sha256")
    if not isinstance(refs,list) or not refs or not isinstance(hashes,list) or len(refs)!=len(hashes) or len(set(refs))!=len(refs):
        raise RoutingError("invalid deterministic input fragment contract")
    pieces=[]
    for rel,expected in zip(refs,hashes):
        if not isinstance(rel,str) or not isinstance(expected,str) or len(expected)!=64:
            raise RoutingError("invalid deterministic input fragment binding")
        path=root/rel
        if not path.is_file():
            raise RoutingError(f"deterministic input fragment missing: {rel}")
        if sha256_file(path)!=expected:
            raise RoutingError(f"deterministic input fragment hash mismatch: {rel}")
        pieces.append(path.read_text(encoding="ascii"))
    concat="".join(pieces).encode("ascii")
    if hashlib.sha256(concat).hexdigest()!=transport.get("concatenated_base64_sha256"):
        raise RoutingError("deterministic concatenated input transport hash mismatch")
    decoded_sha=str(transport.get("decoded_json_sha256") or "")
    if len(decoded_sha)!=64:
        raise RoutingError("deterministic decoded JSON hash binding missing")

    output=contract.get("output") or {}
    out_ref=str(output.get("ref") or "")
    if not out_ref.startswith("evidence/") or not output.get("expected_schema") or not output.get("expected_status"):
        raise RoutingError("deterministic output contract is invalid")


def load_authorized_deterministic_operation(root_value: str | Path, state: Mapping[str, Any]) -> dict[str, Any] | None:
    root = _root(root_value)
    ref = deterministic_operation_ref(state)
    if not ref:
        # An implementation may publish a frozen-screen action after its
        # exact-head validation without embedding a path in the canonical
        # state. Resolve only a unique, explicitly authorized operation for
        # that exact action and evidence epoch; ambiguity fails closed.
        if state.get("status") not in {"READY_FOR_FROZEN_SCREEN_EXECUTION", "SCREEN_EXECUTION_AND_RESULT_VERIFICATION_PENDING"} or state.get("implementation_satisfied") is not True:
            return None
        action = str(state.get("next_action") or "").strip()
        epoch = int(state.get("current_research_evidence_epoch") or state.get("evidence_epoch") or 0)
        matches = []
        for candidate in sorted((root / "research_v3").glob("*_DETERMINISTIC_OPERATION_V1.json")):
            doc = json.loads(candidate.read_text(encoding="utf-8"))
            if (doc.get("schema") == DETERMINISTIC_SCHEMA
                    and doc.get("status") == AUTHORIZED_DETERMINISTIC_STATUS
                    and doc.get("operation_name") == action
                    and int(doc.get("evidence_epoch") or 0) == epoch):
                matches.append(candidate)
        if len(matches) > 1:
            raise RoutingError(f"ambiguous deterministic authority for {action}")
        if not matches:
            return None
        ref = str(matches[0].relative_to(root))
    path = root / ref
    if not path.is_file():
        raise RoutingError(f"deterministic operation authority missing: {ref}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != DETERMINISTIC_SCHEMA:
        raise RoutingError("unsupported deterministic operation schema")
    if doc.get("status") != AUTHORIZED_DETERMINISTIC_STATUS:
        raise RoutingError("deterministic operation is not authorized")
    state_epoch = int(state.get("current_research_evidence_epoch") or state.get("evidence_epoch") or 0)
    op_epoch = int(doc.get("evidence_epoch") or 0)
    if state_epoch and op_epoch != state_epoch:
        raise RoutingError(f"deterministic operation evidence epoch mismatch: operation={op_epoch} state={state_epoch}")
    action = str(state.get("next_action") or "").strip()
    op_name = str(doc.get("operation_name") or "").strip()
    if not op_name:
        raise RoutingError("deterministic operation missing operation_name")
    if action and action != op_name:
        raise RoutingError(f"deterministic operation next_action mismatch: {action!r} != {op_name!r}")
    policy = doc.get("execution_policy") or {}
    if policy.get("new_semantic_judgment_required") is True or policy.get("copilot_reasoning_required") is True:
        raise RoutingError("deterministic operation incorrectly requests semantic reasoning")
    effect = doc.get("accounting_effect") or {}
    if (int(effect.get("v2_attempts") or 0) != 0
            or int(effect.get("economic_outcomes") or 0) != 0
            or int(effect.get("copilot_reasoning_calls") or 0) != 0):
        raise RoutingError("deterministic non-economic operation declares economic/provider accounting effect")
    _validate_extended_operation_contract(root,state,doc)
    return doc

def deterministic_operation_required(root_value: str | Path, state: Mapping[str, Any]) -> bool:
    if _external_or_integrity_gate(state):
        return False
    if reasoning_required(state):
        return False
    doc = load_authorized_deterministic_operation(root_value, state)
    if doc is None:
        return False
    policy = doc.get("execution_policy") or {}
    return (
        policy.get("implementation_ai_required") is False
        and policy.get("copilot_reasoning_required") is False
        and policy.get("new_semantic_judgment_required") is False
        and bool(str(state.get("next_action") or "").strip())
    )

def implementation_required(root_value: str | Path, state: Mapping[str, Any]) -> bool:
    if _external_or_integrity_gate(state):
        return False
    if not str(state.get("next_action") or "").strip():
        return False
    if reasoning_required(state):
        return False
    doc = load_authorized_deterministic_operation(root_value, state)
    if doc is not None:
        return (doc.get("execution_policy") or {}).get("implementation_ai_required") is True
    # Explicit routing intent always wins over legacy proposal-binding inference.
    # In particular, an accepted semantic proposal with implementation_ai_required=false
    # is NOT implementation authority.
    if "implementation_ai_required" in state:
        if state.get("implementation_ai_required") is not True:
            return False
        registry=load_json(Path(root_value)/"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json",{}) or {}
        return any(row.get("proposal_id")==state.get("source_ai_proposal_id") and
                   row.get("proposal_hash")==state.get("source_ai_proposal_hash")
                   for row in registry.get("accepted",[]) if state.get("source_ai_proposal_id") and state.get("source_ai_proposal_hash"))
    # Backward compatibility only for historical states that predate explicit routing.
    if state.get("source_ai_proposal_id") and (
        state.get("source_ai_proposal_hash") or state.get("source_runtime_operation_id")
    ):
        return True
    return False

def economic_execution_required(state: Mapping[str, Any]) -> bool:
    return bool(
        state.get("economic_execution_authorized") is True
        or state.get("economic_materialization_authorized") is True
    )

def ctrader_build_required(state: Mapping[str, Any]) -> bool:
    return bool(state.get("ctrader_build_or_certification_required") is True)

def authority_ci_required(state: Mapping[str, Any]) -> bool:
    return bool(state.get("authority_ci_required") is True or state.get("status") == "PENDING_EXACT_HEAD_GREEN")

def classify_execution(root_value: str | Path, state: Mapping[str, Any]) -> dict[str, Any]:
    root = _root(root_value)
    gate = _external_or_integrity_gate(state)
    if gate:
        return {"execution_class": "MATERIAL_INTEGRITY_OR_EXTERNAL_GATE", "reason": gate}
    if reasoning_required(state):
        return {"execution_class": "SEMANTIC_REASONING", "reason": "EXPLICIT_REASONING_REQUIRED"}
    try:
        if deterministic_operation_required(root, state):
            doc = load_authorized_deterministic_operation(root, state)
            return {
                "execution_class": "DETERMINISTIC_OPERATION",
                "reason": "EXPLICIT_AUTHORIZED_DETERMINISTIC_OPERATION",
                "operation_name": doc.get("operation_name"),
                "operation_ref": deterministic_operation_ref(state),
            }
    except RoutingError as exc:
        return {"execution_class": "MATERIAL_INTEGRITY_OR_EXTERNAL_GATE", "reason": "DETERMINISTIC_AUTHORITY_INVALID", "detail": str(exc)}
    if implementation_required(root, state):
        return {"execution_class": "NOVEL_AI_IMPLEMENTATION", "reason": "EXPLICIT_AI_IMPLEMENTATION_AUTHORITY"}
    if economic_execution_required(state):
        return {"execution_class": "ECONOMIC_EXECUTION", "reason": "EXPLICIT_ECONOMIC_AUTHORITY"}
    if ctrader_build_required(state):
        return {"execution_class": "CTRADER_BUILD_OR_CERTIFICATION", "reason": "EXPLICIT_CTRADER_BUILD_AUTHORITY"}
    if authority_ci_required(state):
        return {"execution_class": "AUTHORITY_CI", "reason": "EXACT_HEAD_GREEN_REQUIRED"}
    if str(state.get("next_action") or "").strip():
        return {
            "execution_class": "MATERIAL_INTEGRITY_OR_EXTERNAL_GATE",
            "reason": "UNROUTED_NONEMPTY_ACTION_FAIL_CLOSED",
            "detail": "next_action is non-empty but no explicit deterministic, semantic, AI implementation, economic, CI or cTrader authority exists",
        }
    return {"execution_class": "NO_WORK", "reason": "QUIESCENT"}

def liveness_fingerprint(root_value: str | Path, state: Mapping[str, Any]) -> str:
    root = _root(root_value)
    refs = []
    for key in (
        "next_deterministic_operation_ref",
        "fresh_director_decision_ref",
        "all_frontier_inventory_ref",
        "evidence_epoch_ref",
        "canonical_frontier_ref",
    ):
        rel = state.get(key)
        if isinstance(rel, str) and rel and (root / rel).is_file():
            refs.append({"ref": rel, "sha256": sha256_file(root / rel)})
    payload = {
        "evidence_epoch": state.get("current_research_evidence_epoch") or state.get("evidence_epoch"),
        "next_action": state.get("next_action"),
        "external_gate_state": {
            "user_action_required": state.get("user_action_required"),
            "external_data_required": state.get("external_data_required"),
            "external_gate": state.get("external_gate"),
            "external_data_gate": state.get("external_data_gate"),
        },
        "authority_hashes": refs,
    }
    return sha256_bytes(canonical_bytes(payload))
