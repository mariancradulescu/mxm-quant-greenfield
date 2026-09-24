"""Provider-neutral bridge from advanced AI research reasoning to Runtime V2.

The AI layer owns research intelligence. This module deliberately does NOT map a finite
set of next_action strings to hardcoded research procedures. It validates invariant
boundaries, binds an auditable proposal, and compiles any structurally valid proposal
into a NON_ECONOMIC Runtime V2 operation. Economic work remains a separate fail-closed
Runtime V2 path.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.autonomous_runtime_v2 import RuntimeV2
from research_v3.runtime_v2_primitives import (
    GitCheckpointSink,
    atomic_write_json,
    canonical_bytes,
    iso,
    load_json,
    sha256_bytes,
    sha256_file,
)

PROTOCOL_VERSION = "MXM_GENERAL_AI_RESEARCH_DIRECTOR_PROTOCOL_V1"
PROPOSAL_SCHEMA = "mxm.greenfield.general-ai-research-proposal.v1"
ATTESTATION_SCHEMA = "mxm.greenfield.ai-director-artifact-attestation.v1"
PROPOSAL_DIR = Path("research_v3/ai_director/proposals")
REGISTRY_REL = Path("research_v3/ai_director/PROPOSAL_REGISTRY_V1.json")
REQUEST_REL = Path("research_v3/ai_director/AI_REASONING_REQUEST.json")
NEXT_STATE_REL = Path("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
DISCOVERY_LEDGER_REL = Path("discovery/ledger.jsonl")
GENERAL_GATE_REL = Path("evidence/GENERAL_AI_RESEARCH_DIRECTOR_ACCEPTANCE_V1.json")

RESERVED_NEXT_STATE_KEYS = {
    "accounting", "safety", "economic_outcomes_opened", "v2_attempts_used",
    "v2_search_budget_remaining", "protected_forward", "live_orders",
    "competition_start", "competition_start_authorized", "live_orders_authorized",
}


class AIProposalRejected(RuntimeError):
    pass


def _load(root: Path, rel: str | Path) -> dict[str, Any]:
    path = root / Path(rel)
    if not path.is_file():
        raise AIProposalRejected(f"required durable file missing: {path.relative_to(root)}")
    return json.loads(path.read_text(encoding="utf-8"))


def project_snapshot(root: Path) -> dict[str, Any]:
    report = validate_repository_state(root)
    return {
        "v2_attempts_used": int(report["accounting"]["v2_attempts_used"]),
        "v2_search_budget_remaining": int(report["accounting"]["v2_search_budget_remaining"]),
        "economic_outcomes_opened": int(report["accounting"]["economic_outcomes_opened"]),
        "discovery_ledger_sha256": sha256_file(root / DISCOVERY_LEDGER_REL),
    }


def _git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _is_ancestor(root: Path, ancestor: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=root, text=True, capture_output=True,
    )
    return proc.returncode == 0


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AIProposalRejected(f"{label} must be a non-empty string")
    return value.strip()


def validate_artifact_attestation(root: Path, rel: str) -> dict[str, Any]:
    doc = _load(root, rel)
    if doc.get("schema") != ATTESTATION_SCHEMA or doc.get("status") != "VERIFIED":
        raise AIProposalRejected(f"artifact attestation is not VERIFIED: {rel}")
    artifact = doc.get("artifact") or {}
    name = _nonempty(artifact.get("filename"), "artifact.filename")
    digest = _nonempty(artifact.get("sha256"), "artifact.sha256")
    size = artifact.get("size_bytes")
    if len(digest) != 64 or not isinstance(size, int) or size <= 0:
        raise AIProposalRejected(f"artifact identity incomplete: {rel}")
    accepted_ref = _nonempty(doc.get("accepted_metadata_ref"), "accepted_metadata_ref")
    accepted = _load(root, accepted_ref)
    source = accepted.get("source") or accepted.get("accepted_capture") or {}
    expected_name = source.get("external_name") or source.get("filename")
    expected_sha = source.get("zip_sha256") or source.get("sha256")
    expected_size = source.get("zip_size_bytes") or source.get("size_bytes")
    if (name, digest, size) != (expected_name, expected_sha, expected_size):
        raise AIProposalRejected(f"artifact attestation does not match accepted metadata: {rel}")
    verification = doc.get("byte_verification") or {}
    if verification.get("method") != "DIRECT_SHA256_AND_SIZE":
        raise AIProposalRejected("artifact attestation lacks direct-byte verification")
    if verification.get("observed_sha256") != digest or verification.get("observed_size_bytes") != size:
        raise AIProposalRejected("artifact direct-byte verification drift")
    availability = doc.get("availability") or {}
    if availability.get("durable_library") is not True:
        raise AIProposalRejected("artifact is not durably reusable")
    if availability.get("recapture_required") is not False:
        raise AIProposalRejected("accepted existing artifact must not be recaptured")
    return doc


def validate_proposal_shape(proposal: Mapping[str, Any]) -> None:
    if proposal.get("schema") != PROPOSAL_SCHEMA:
        raise AIProposalRejected("unsupported AI proposal schema")
    _nonempty(proposal.get("proposal_id"), "proposal_id")
    provider = proposal.get("provider") or {}
    _nonempty(provider.get("kind"), "provider.kind")
    objective = proposal.get("objective") or {}
    # Intentionally free-form. No objective-class enum and no finite next-action map.
    _nonempty(objective.get("class"), "objective.class")
    _nonempty(objective.get("goal"), "objective.goal")
    _nonempty(objective.get("information_gain_rationale"), "objective.information_gain_rationale")
    if not isinstance(proposal.get("decision"), Mapping):
        raise AIProposalRejected("decision must be an object")
    if not isinstance(proposal.get("next_research_state"), Mapping):
        raise AIProposalRejected("next_research_state must be an object")
    forbidden = RESERVED_NEXT_STATE_KEYS.intersection(proposal["next_research_state"])
    if forbidden:
        raise AIProposalRejected(f"AI next_research_state attempts to overwrite protected keys: {sorted(forbidden)}")

    effect = proposal.get("economic_effect") or {}
    if effect.get("open_economic_outcome") is not False:
        raise AIProposalRejected("AI proposal may not open economics through the reasoning bridge")
    if int(effect.get("consume_v2_attempt", -1)) != 0:
        raise AIProposalRejected("AI reasoning bridge may not consume a V2 attempt")
    if effect.get("create_new_v2_identity") is not False:
        raise AIProposalRejected("AI reasoning bridge may not create a V2 economic identity")

    safety = proposal.get("safety") or {}
    for key in ("protected_forward_opened", "live_orders_authorized", "competition_start_authorized"):
        if safety.get(key) is not False:
            raise AIProposalRejected(f"AI proposal violates fail-closed safety: {key}")

    scope = proposal.get("scope_law") or {}
    if scope.get("rerun_exact_observed_identity") is not False:
        raise AIProposalRejected("exact observed identity rerun forbidden")
    if scope.get("refund_observed_attempts") is not False:
        raise AIProposalRejected("observed attempt refund forbidden")
    family_closures = scope.get("mechanism_family_closure_claims", [])
    if not isinstance(family_closures, list):
        raise AIProposalRejected("mechanism_family_closure_claims must be a list")
    for claim in family_closures:
        if not isinstance(claim, Mapping) or not claim.get("prospective_exhaustion_authority_ref"):
            raise AIProposalRejected("mechanism-family closure requires explicit prospective exhaustion authority")

    data_policy = proposal.get("data_policy") or {}
    if data_policy.get("no_default_multi_year_download") is not True:
        raise AIProposalRejected("no-default-multi-year data law must remain active")
    if data_policy.get("user_selects_symbols_or_horizon") is not False:
        raise AIProposalRejected("user may not become research/data scheduler")
    if data_policy.get("new_market_data_requested") is True:
        req = data_policy.get("minimal_acquisition_request") or {}
        for key in ("source_domain", "symbols", "resolution", "start_utc", "end_utc", "fields", "information_gain_justification"):
            if key not in req:
                raise AIProposalRejected(f"new data request missing prospectively required field: {key}")
        if req["source_domain"] != "PEPPERSTONE_ACCOUNT_VIA_CTRADER_OPEN_API":
            raise AIProposalRejected("empirical market data must be broker-native Pepperstone/cTrader Open API")
        if not isinstance(req["symbols"], list) or not req["symbols"]:
            raise AIProposalRejected("new data request requires explicit AI-selected symbols")
        if not isinstance(req["fields"], list) or not req["fields"]:
            raise AIProposalRejected("new data request requires explicit fields")

    causal = proposal.get("causal_contract") or {}
    required_true = (
        "chronological_incremental_replay",
        "causal_entry_admission",
        "future_information_forbidden",
        "protected_forward_leakage_forbidden",
        "learned_procedure_freeze_before_outer_outcome",
    )
    for key in required_true:
        if causal.get(key) is not True:
            raise AIProposalRejected(f"causal contract not affirmed: {key}")


def _completed_outer_authority(root: Path, state: Mapping[str, Any]) -> dict[str, Any] | None:
    """Verify the persisted capture/result/interpretation chain before releasing its old acquisition contract."""
    capture_ref = state.get("capture_acceptance_ref")
    result_ref = state.get("result_ref")
    interpretation_ref = state.get("interpretation_ref")
    if not all(isinstance(x, str) and x for x in (capture_ref, result_ref, interpretation_ref)):
        return None
    capture = _load(root, capture_ref)
    result = _load(root, result_ref)
    interpretation = _load(root, interpretation_ref)
    if not str(result.get("status") or "").endswith("_COMPLETE"):
        raise AIProposalRejected("claimed completed outer has no completed result")
    if "INTERPRETED" not in str(interpretation.get("status") or ""):
        raise AIProposalRejected("claimed completed outer has no interpretation")
    if interpretation.get("source_result_ref") != result_ref or interpretation.get("source_capture_acceptance_ref") != capture_ref:
        raise AIProposalRejected("completed outer interpretation authority mismatch")
    if result.get("source_capture_sha256") != (capture.get("source_capture") or {}).get("sha256"):
        raise AIProposalRejected("completed outer capture/result hash mismatch")
    if state.get("outer_data_binding_ref") != capture_ref:
        raise AIProposalRejected("completed outer binding does not point to accepted capture")
    return {"capture_ref": capture_ref, "result_ref": result_ref, "interpretation_ref": interpretation_ref}


def _reject_completed_outer_as_unseen(root: Path, proposal: Mapping[str, Any]) -> None:
    """Observed outer evidence may inform research but cannot be declared unseen confirmation again."""
    completed = _completed_outer_authority(root, load_json(root / NEXT_STATE_REL, {}) or {})
    if completed is None:
        return
    observed = set(completed.values())
    for binding in proposal.get("data_bindings") or []:
        if not isinstance(binding, Mapping):
            continue
        role = str(binding.get("role") or binding.get("authority_role") or "").upper()
        ref = binding.get("ref") or binding.get("source_ref") or binding.get("result_ref") or binding.get("artifact_ref")
        if ref in observed and any(x in role for x in ("UNSEEN", "UNOPENED", "INDEPENDENT_CONFIRM")):
            raise AIProposalRejected("completed outer cannot be reused as unseen confirmation")
    decision = proposal.get("decision") or {}
    if decision.get("unseen_confirmation_ref") in observed:
        raise AIProposalRejected("completed outer cannot be reused as unseen confirmation")


def _reject_duplicate_accepted_capture(root: Path, proposal: Mapping[str, Any]) -> None:
    """A new authenticated capture must not repeat an accepted exact broker-native scope."""
    request = (proposal.get("data_policy") or {}).get("minimal_acquisition_request") or {}
    if (proposal.get("data_policy") or {}).get("new_market_data_requested") is not True:
        return
    state = load_json(root / NEXT_STATE_REL, {}) or {}
    plan_ref = state.get("completed_capture_plan_ref")
    capture_ref = state.get("completed_capture_ref")
    report_ref = state.get("completed_structural_report_ref")
    if not all(isinstance(x, str) and x for x in (plan_ref, capture_ref, report_ref)):
        return
    plan = _load(root, plan_ref)
    capture = _load(root, capture_ref)
    report = _load(root, report_ref)
    if (capture.get("source_capture") or {}).get("plan_sha256") != plan.get("plan_sha256"):
        raise AIProposalRejected("accepted capture plan authority mismatch")
    if (report.get("canonical_capture") or {}).get("sha256") != (capture.get("canonical_capture") or {}).get("sha256"):
        raise AIProposalRejected("accepted capture structural report authority mismatch")
    if not str(report.get("status") or "").endswith("_COMPLETE"):
        raise AIProposalRejected("accepted capture lacks completed structural report")
    symbols = [x.get("broker_symbol") if isinstance(x, Mapping) else x for x in plan.get("symbols") or []]
    interval = plan.get("interval") or {}
    if (request.get("symbols") == symbols
            and request.get("resolution") == plan.get("resolution")
            and request.get("start_utc") == interval.get("start_utc")
            and request.get("end_utc") == interval.get("end_utc")):
        raise AIProposalRejected("exact broker-native capture already accepted and screened; reuse existing evidence")


def _validate_broker_native_selection(root: Path, proposal: Mapping[str, Any]) -> None:
    policy = proposal.get("data_policy") or {}
    if policy.get("new_market_data_requested") is not True:
        return
    index = _load(root, "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json")
    acceptance = _load(root, index["source_acceptance_ref"])
    accepted = acceptance.get("accepted_capture") or {}
    if (index.get("source_zip_sha256") != accepted.get("zip_sha256")
            or index.get("source_internal_json_sha256") != accepted.get("internal_json_sha256")
            or index.get("account_fingerprint_sha256") != (acceptance.get("account_identity") or {}).get("account_fingerprint_sha256")):
        raise AIProposalRejected("broker-native feasibility index provenance mismatch")
    request = policy.get("minimal_acquisition_request") or {}
    exceptions = policy.get("future_equity_only_scope") or {}
    for name in request.get("symbols") or []:
        row = (index.get("products") or {}).get(name)
        if row is None:
            raise AIProposalRejected(f"broker-native symbol identity absent from current account: {name}")
        if row[2]:
            raise AIProposalRejected(f"TEST product cannot enter current economic research scope: {name}")
        if row[1] == "NEITHER_FEASIBLE":
            allowed = name in (exceptions.get("symbols") or [])
            justified = bool(exceptions.get("prospective_rationale")) and exceptions.get("initial_eur200_tradable") is False
            if not (allowed and justified):
                raise AIProposalRejected(f"broker-native symbol infeasible at initial EUR200: {name}")


def _active_authoritative_data_contract(root: Path) -> dict[str, Any] | None:
    """Resolve a still-unsatisfied prospective data contract from durable state.

    This is intentionally schema/authority driven rather than a next_action table.
    """
    state = load_json(root / NEXT_STATE_REL, {}) or {}
    binding = state.get("outer_data_binding_ref") or state.get("independent_outer_data_ref")
    if binding:
        if state.get("result_ref") or state.get("interpretation_ref"):
            if _completed_outer_authority(root, state) is None:
                raise AIProposalRejected("completed outer evidence chain incomplete")
        return None

    freeze_rel = (
        state.get("authoritative_freeze_ref")
        or state.get("source_freeze_ref")
        or state.get("freeze_ref")
    )
    freeze = None
    contract = None
    if isinstance(freeze_rel, str) and freeze_rel and (root / freeze_rel).is_file():
        freeze = _load(root, freeze_rel)
        raw = freeze.get("independent_outer_contract")
        if isinstance(raw, Mapping) and raw.get("required") is True:
            contract = dict(raw)

    plan_rel = state.get("outer_capture_plan_ref")
    plan = None
    if isinstance(plan_rel, str) and plan_rel and (root / plan_rel).is_file():
        plan = _load(root, plan_rel)

    if contract is None and plan is None:
        return None

    fixed_symbols = []
    if plan is not None:
        for row in plan.get("symbols") or []:
            if isinstance(row, Mapping) and row.get("broker_symbol"):
                fixed_symbols.append(str(row["broker_symbol"]))
            elif isinstance(row, str):
                fixed_symbols.append(row)
    if not fixed_symbols and contract is not None:
        fixed_symbols = [str(x) for x in contract.get("exact_symbols_fixed_for_first_outer") or []]

    resolution = None
    interval = None
    if plan is not None:
        resolution = plan.get("resolution")
        interval = plan.get("outer_interval")
    if resolution is None and freeze is not None:
        resolution = (freeze.get("data_scope") or {}).get("resolution")

    return {
        "freeze_ref": freeze_rel,
        "freeze": freeze,
        "contract": contract,
        "plan_ref": plan_rel,
        "plan": plan,
        "fixed_symbols": fixed_symbols,
        "resolution": resolution,
        "outer_interval": interval,
    }


def _validate_authoritative_data_contract(root: Path, proposal: Mapping[str, Any]) -> None:
    authority = _active_authoritative_data_contract(root)
    if authority is None:
        return

    scope = proposal.get("scope_law") or {}
    supersession_ref = scope.get("authoritative_contract_supersession_ref")
    if supersession_ref:
        rel = str(supersession_ref)
        path = root / rel
        if not path.is_file():
            raise AIProposalRejected("authoritative data-contract supersession ref missing")
        doc = _load(root, rel)
        status = str(doc.get("status") or "")
        if not status.startswith("FROZEN_"):
            raise AIProposalRejected("authoritative data-contract supersession is not prospectively frozen")
        if doc.get("supersedes_ref") not in {authority.get("freeze_ref"), authority.get("plan_ref")}:
            raise AIProposalRejected("authoritative data-contract supersession does not bind current authority")
        return

    fixed = list(authority.get("fixed_symbols") or [])
    resolution = authority.get("resolution")
    interval = authority.get("outer_interval")
    data_policy = proposal.get("data_policy") or {}
    request = data_policy.get("minimal_acquisition_request") or {}

    candidate_symbol_lists = []
    if request.get("symbols") is not None:
        candidate_symbol_lists.append(("data_policy.minimal_acquisition_request.symbols", request.get("symbols")))
    decision = proposal.get("decision") or {}
    for key in ("panel_symbols", "symbols"):
        if decision.get(key) is not None:
            candidate_symbol_lists.append((f"decision.{key}", decision.get(key)))
    universe = decision.get("universe_selection")
    if isinstance(universe, Mapping) and universe.get("symbol_set") is not None:
        candidate_symbol_lists.append(("decision.universe_selection.symbol_set", universe.get("symbol_set")))

    for label, values in candidate_symbol_lists:
        if not isinstance(values, list):
            raise AIProposalRejected(f"{label} must be a list under authoritative outer contract")
        observed = [str(x) for x in values]
        if fixed and observed != fixed:
            raise AIProposalRejected(
                f"{label} violates frozen outer panel: expected {fixed}, observed {observed}"
            )

    if request:
        if resolution is not None and request.get("resolution") != resolution:
            raise AIProposalRejected("new data request violates frozen outer resolution")
        if interval is not None:
            if request.get("start_utc") != interval.get("start_utc") or request.get("end_utc") != interval.get("end_utc"):
                raise AIProposalRejected("new data request violates prospectively frozen outer interval")

    next_state = proposal.get("next_research_state") or {}
    if resolution is not None and next_state.get("resolution") is not None and next_state.get("resolution") != resolution:
        raise AIProposalRejected("AI next state violates frozen outer resolution")
    if interval is not None:
        if next_state.get("window_start_utc") is not None and next_state.get("window_start_utc") != interval.get("start_utc"):
            raise AIProposalRejected("AI next state violates frozen outer start")
        if next_state.get("window_end_utc") is not None and next_state.get("window_end_utc") != interval.get("end_utc"):
            raise AIProposalRejected("AI next state violates frozen outer end")

    freeze = authority.get("freeze")
    contract = authority.get("contract")
    if freeze is not None and contract is not None:
        source_interval = (freeze.get("data_scope") or {}).get("interval") or {}
        req_start = request.get("start_utc")
        req_end = request.get("end_utc")
        if req_start and req_end and source_interval.get("start_utc") and source_interval.get("end_utc"):
            disjoint = req_end < source_interval["start_utc"] or req_start > source_interval["end_utc"]
            if contract.get("outer_dataset_must_be_disjoint_from_source_capture") is True and not disjoint:
                raise AIProposalRejected("new data request overlaps outer-forbidden source capture")


def validate_proposal(root: Path, proposal: Mapping[str, Any]) -> dict[str, Any]:
    validate_proposal_shape(proposal)
    _validate_authoritative_data_contract(root, proposal)
    _reject_completed_outer_as_unseen(root, proposal)
    _reject_duplicate_accepted_capture(root, proposal)
    _validate_broker_native_selection(root, proposal)
    basis = proposal.get("basis") or {}
    basis_head = _nonempty(basis.get("research_head"), "basis.research_head")
    if not _is_ancestor(root, basis_head):
        raise AIProposalRejected(f"proposal basis head is not an ancestor of live HEAD: {basis_head}")
    expected = basis.get("accounting") or {}
    current = project_snapshot(root)
    for key in ("v2_attempts_used", "v2_search_budget_remaining", "economic_outcomes_opened"):
        if int(expected.get(key, -1)) != current[key]:
            raise AIProposalRejected(f"proposal accounting basis drift: {key}")
    if basis.get("discovery_ledger_sha256") != current["discovery_ledger_sha256"]:
        raise AIProposalRejected("proposal discovery-ledger basis drift")

    refs = proposal.get("authority_refs") or []
    if not isinstance(refs, list) or not refs:
        raise AIProposalRejected("proposal must bind at least one durable authority ref")
    authority_rows = []
    for rel in sorted(set(str(x) for x in refs)):
        path = root / rel
        if not path.is_file():
            raise AIProposalRejected(f"proposal authority missing: {rel}")
        authority_rows.append({"path": rel, "sha256": sha256_file(path)})

    attestation_rows = []
    for rel in proposal.get("artifact_attestation_refs") or []:
        doc = validate_artifact_attestation(root, str(rel))
        attestation_rows.append({
            "path": str(rel),
            "sha256": sha256_file(root / str(rel)),
            "artifact_sha256": doc["artifact"]["sha256"],
            "artifact_size_bytes": doc["artifact"]["size_bytes"],
        })

    return {
        "live_head": _git_head(root),
        "project_snapshot": current,
        "authority_rows": authority_rows,
        "authority_bundle_sha256": sha256_bytes(canonical_bytes(authority_rows)),
        "artifact_attestations": attestation_rows,
    }


def proposal_hash(proposal: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(proposal))


def compile_runtime_plan(
    root: Path,
    proposal: Mapping[str, Any],
    validation: Mapping[str, Any],
    proposal_ref: str,
) -> dict[str, Any]:
    p_hash = proposal_hash(proposal)
    dataset_binding = {
        "discovery_ledger_sha256": validation["project_snapshot"]["discovery_ledger_sha256"],
        "artifact_attestations": validation["artifact_attestations"],
        "declared_data_bindings": proposal.get("data_bindings") or [],
    }
    return {
        "operation_kind": "NON_ECONOMIC_DIRECTOR",
        "candidate_spec_hash": p_hash,
        "dataset_hash": sha256_bytes(canonical_bytes(dataset_binding)),
        "evaluator_hash": sha256_file(root / "research_v3/general_ai_director_bridge.py"),
        "cost_authority_hash": str(validation["authority_bundle_sha256"]),
        "execution_semantics_version": PROTOCOL_VERSION,
        "lifecycle_phase": "AI_RESEARCH_DECISION_NON_ECONOMIC",
        "evaluator": {
            "kind": "python_callable",
            "module": "research_v3.general_ai_director_bridge",
            "function": "evaluate_ai_proposal_operation",
        },
        "ai_proposal": {
            "proposal_ref": proposal_ref,
            "proposal_hash": p_hash,
            "proposal_id": proposal["proposal_id"],
            "objective_class": proposal["objective"]["class"],
            "protocol_version": PROTOCOL_VERSION,
        },
        "pre_outcome_gate": {
            "status": "PASS",
            "classification": "GENERAL_AI_NON_ECONOMIC_RESEARCH_DECISION",
            "new_v2_identity": False,
            "new_project_economic_outcome": False,
        },
        "safety": {
            "live_orders_authorized": False,
            "protected_evidence_opened": False,
            "competition_start_authorized": False,
        },
        "external_data": {"required": False},
    }


def evaluate_ai_proposal_operation(root_value: str | Path, plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(root_value)
    meta = plan.get("ai_proposal") or {}
    proposal_ref = _nonempty(meta.get("proposal_ref"), "ai_proposal.proposal_ref")
    proposal = _load(root, proposal_ref)
    validation = validate_proposal(root, proposal)
    observed_hash = proposal_hash(proposal)
    if observed_hash != meta.get("proposal_hash"):
        raise AIProposalRejected("proposal bytes changed after Runtime V2 materialization")
    return {
        "schema": "mxm.greenfield.general-ai-research-decision-result.v1",
        "status": "PASS",
        "protocol_version": PROTOCOL_VERSION,
        "operation_id": plan["operation_id"],
        "proposal_id": proposal["proposal_id"],
        "proposal_ref": proposal_ref,
        "proposal_hash": observed_hash,
        "objective": proposal["objective"],
        "decision": proposal["decision"],
        "next_research_state": proposal["next_research_state"],
        "authority_bundle_sha256": validation["authority_bundle_sha256"],
        "artifact_attestations": validation["artifact_attestations"],
        "economic_outcome_opened": False,
        "v2_attempt_consumed": 0,
        "new_v2_identity_opened": False,
        "protected_forward_opened": False,
        "live_orders_authorized": False,
        "competition_start_authorized": False,
    }


def _journal_proof(runtime: RuntimeV2, op_id: str) -> dict[str, Any]:
    names = [row.get("event") for row in runtime.journal.events_for(op_id)]
    proof = {
        "non_economic_result_available": names.count("NON_ECONOMIC_RESULT_AVAILABLE"),
        "economic_execution_started": names.count("ECONOMIC_EXECUTION_STARTED"),
        "economic_result_available": names.count("ECONOMIC_RESULT_AVAILABLE"),
        "operation_closed": names.count("OPERATION_CLOSED"),
        "knowledge_scope_updated": names.count("KNOWLEDGE_SCOPE_UPDATED"),
    }
    if proof != {
        "non_economic_result_available": 1,
        "economic_execution_started": 0,
        "economic_result_available": 0,
        "operation_closed": 1,
        "knowledge_scope_updated": 1,
    }:
        raise AIProposalRejected(f"Runtime V2 non-economic proof mismatch for {op_id}: {proof}")
    return proof


def _registry(root: Path) -> dict[str, Any]:
    return load_json(root / REGISTRY_REL, {
        "schema": "mxm.greenfield.general-ai-proposal-registry.v1",
        "protocol_version": PROTOCOL_VERSION,
        "accepted": [],
    })


def _checkpoint(root: Path, boundary: str, op_id: str | None, enabled: bool, push: bool) -> None:
    GitCheckpointSink(root, enabled=enabled, push=push).checkpoint(boundary, op_id)


def _verify_already_materialized_entry(
    root: Path,
    proposal_ref: str,
    proposal: Mapping[str, Any],
    p_hash: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify immutable historical acceptance without revalidating it against today's accounting."""
    if row.get("proposal_hash") != p_hash:
        raise AIProposalRejected("accepted registry proposal hash mismatch")
    if row.get("proposal_ref") != proposal_ref:
        raise AIProposalRejected("accepted registry proposal_ref/hash consistency failure")
    if row.get("proposal_id") != proposal.get("proposal_id"):
        raise AIProposalRejected("accepted registry proposal_id mismatch")
    if row.get("economic_outcome_opened") is not False or int(row.get("v2_attempt_consumed", -1)) != 0:
        raise AIProposalRejected("accepted AI reasoning row has invalid economic accounting")

    op_id = _nonempty(row.get("operation_id"), "accepted.operation_id")
    result_ref = _nonempty(row.get("result_ref"), "accepted.result_ref")
    result_path = root / result_ref
    if not result_path.is_file():
        raise AIProposalRejected(f"accepted proposal result missing: {result_ref}")
    observed_result_hash = sha256_file(result_path)
    if observed_result_hash != row.get("result_sha256"):
        raise AIProposalRejected("accepted proposal persisted result hash drift")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if (
        result.get("proposal_hash") != p_hash
        or result.get("proposal_ref") != proposal_ref
        or result.get("proposal_id") != proposal.get("proposal_id")
        or result.get("operation_id") != op_id
        or result.get("economic_outcome_opened") is not False
        or int(result.get("v2_attempt_consumed", -1)) != 0
    ):
        raise AIProposalRejected("accepted proposal persisted result identity/accounting drift")

    runtime = RuntimeV2(root, lease_seconds=900, owner_token=f"ai-registry-verify-{p_hash[:16]}")
    proof = _journal_proof(runtime, op_id)
    recorded_proof = row.get("journal_proof")
    if recorded_proof != proof:
        raise AIProposalRejected("accepted proposal journal proof drift")

    closure_ref = root / "research_v3/runtime_v2/closures" / f"{op_id}.json"
    if not closure_ref.is_file():
        raise AIProposalRejected("accepted proposal Runtime V2 closure missing")
    closure = json.loads(closure_ref.read_text(encoding="utf-8"))
    if (
        closure.get("operation_id") != op_id
        or closure.get("result_sha256") != observed_result_hash
        or closure.get("economic_outcome_opened") is not False
        or closure.get("status") != "CLOSED_POST_VALIDATION_GREEN"
    ):
        raise AIProposalRejected("accepted proposal Runtime V2 closure integrity drift")

    ledger_rows = runtime._validate_runtime_ledger()
    matches = [
        x for x in ledger_rows
        if x.get("operation_id") == op_id and x.get("entry_type") == "NON_ECONOMIC_RESULT_RECORDED"
    ]
    if len(matches) != 1 or matches[0].get("result_sha256") != observed_result_hash:
        raise AIProposalRejected("accepted proposal Runtime V2 ledger integrity drift")
    if any(
        x.get("operation_id") == op_id and x.get("entry_type") == "RESULT_RECORDED"
        for x in ledger_rows
    ):
        raise AIProposalRejected("accepted non-economic proposal has economic Runtime V2 ledger entry")

    return {"status": "ALREADY_MATERIALIZED", **dict(row)}


def materialize_proposal(
    root_value: str | Path,
    proposal_ref: str,
    *,
    git_checkpoint: bool = False,
    git_push: bool = False,
) -> dict[str, Any]:
    root = Path(root_value).resolve()
    proposal = _load(root, proposal_ref)
    p_hash = proposal_hash(proposal)

    # Historical accepted proposals are immutable decisions. Verify their durable identity,
    # result, journal, closure and runtime-ledger proof BEFORE consulting today's accounting.
    # This is the idempotent fast path: later legitimate economics must not stale old decisions.
    registry = _registry(root)
    existing = [x for x in registry.get("accepted", []) if x.get("proposal_hash") == p_hash]
    if existing:
        if len(existing) != 1:
            raise AIProposalRejected("duplicate accepted registry rows for immutable proposal hash")
        return _verify_already_materialized_entry(root, proposal_ref, proposal, p_hash, existing[0])

    # Only genuinely new or modified proposal bytes are validated against LIVE accounting,
    # ledger, authorities and safety. A mutation of a historically accepted proposal changes
    # its hash and therefore cannot enter the historical fast path.
    validation = validate_proposal(root, proposal)
    before = project_snapshot(root)
    plan = compile_runtime_plan(root, proposal, validation, proposal_ref)
    runtime = RuntimeV2(
        root,
        lease_seconds=900,
        checkpoint_sink=GitCheckpointSink(root, enabled=git_checkpoint, push=git_push),
        owner_token=f"ai-proposal-{p_hash[:16]}",
    )
    op_id, _ = runtime.submit_operation(plan)
    _checkpoint(root, "general_ai_proposal_materialized", op_id, git_checkpoint, git_push)
    outcome = runtime.run(max_operations=1)
    if outcome.status not in {"COMPLETE", "BOUNDED_CHECKPOINT"}:
        raise AIProposalRejected(f"Runtime V2 failed to close AI proposal: {outcome.status}")
    proof = _journal_proof(runtime, op_id)
    result_ref = f"research_v3/runtime_v2/results/{op_id}.json"
    result = _load(root, result_ref)
    after = project_snapshot(root)
    if after != before:
        raise AIProposalRejected(
            "non-economic AI proposal changed project economics/accounting: "
            + json.dumps({"before": before, "after": after}, sort_keys=True)
        )

    row = {
        "proposal_id": proposal["proposal_id"],
        "proposal_ref": proposal_ref,
        "proposal_hash": p_hash,
        "objective_class": proposal["objective"]["class"],
        "operation_id": op_id,
        "result_ref": result_ref,
        "result_sha256": sha256_file(root / result_ref),
        "journal_proof": proof,
        "accepted_utc": iso(),
        "economic_outcome_opened": False,
        "v2_attempt_consumed": 0,
    }
    registry = _registry(root)
    registry["protocol_version"] = PROTOCOL_VERSION
    registry.setdefault("accepted", []).append(row)
    atomic_write_json(root / REGISTRY_REL, registry)

    publication = proposal.get("publication") or {}
    if publication.get("apply_to_next_state") is True:
        next_doc = dict(load_json(root / NEXT_STATE_REL, {}) or {})
        # Routing metadata belongs to the action that created it. Never inherit it into
        # a newly accepted AI decision unless that decision explicitly re-declares it.
        for key in (
            "ai_reasoning_required",
            "green_implementation_artifacts",
            "external_data_gate_ref",
            "collector_build_ref",
            "collector_package_artifact_name",
            "expected_return_artifact_name",
            "source_implementation_id",
        ):
            next_doc.pop(key, None)
        next_doc.update(dict(proposal["next_research_state"]))
        next_doc["user_action_required"] = bool(proposal["next_research_state"].get("user_action_required", False))
        next_doc.update({
            "schema": "mxm.greenfield.runtime-v2-next-autonomous-state.v3",
            "director_protocol": PROTOCOL_VERSION,
            "source_ai_proposal_id": proposal["proposal_id"],
            "source_ai_proposal_hash": p_hash,
            "source_runtime_operation_id": op_id,
            "accounting": {
                "v2_attempts_used": after["v2_attempts_used"],
                "v2_search_budget_remaining": after["v2_search_budget_remaining"],
                "economic_outcomes_opened": after["economic_outcomes_opened"],
            },
            "safety": {
                "protected_evidence_opened": False,
                "live_orders_authorized": False,
                "competition_start_authorized": False,
            },
        })
        atomic_write_json(root / NEXT_STATE_REL, next_doc)

    _checkpoint(root, "general_ai_proposal_registry", op_id, git_checkpoint, git_push)
    return {"status": "MATERIALIZED", **row, "result": result}


def drain(root_value: str | Path, *, git_checkpoint: bool = False, git_push: bool = False) -> dict[str, Any]:
    root = Path(root_value).resolve()
    results = []
    proposal_dir = root / PROPOSAL_DIR
    for path in sorted(proposal_dir.glob("*.json")):
        proposal = json.loads(path.read_text(encoding="utf-8"))
        if proposal.get("schema") != PROPOSAL_SCHEMA:
            continue
        rel = str(path.relative_to(root))
        results.append(materialize_proposal(
            root, rel, git_checkpoint=git_checkpoint, git_push=git_push,
        ))
    return {"status": "PASS", "processed": results, "count": len(results)}


def write_reasoning_request(root_value: str | Path) -> dict[str, Any]:
    root = Path(root_value).resolve()
    snapshot = project_snapshot(root)
    request = {
        "schema": "mxm.greenfield.general-ai-reasoning-request.v1",
        "status": "AI_REASONING_REQUIRED",
        "protocol_version": PROTOCOL_VERSION,
        "research_head": _git_head(root),
        "project_snapshot": snapshot,
        "instruction": (
            "Choose the highest-information legal research action. Reason freely about hypotheses, "
            "mechanisms, universes, data sufficiency, methodology and implementation. Return an "
            "auditable general-ai-research-proposal.v1. Do not ask the user to choose routine "
            "research parameters. Do not open economics through the reasoning channel."
        ),
        "required_authorities": [
            "research_v3/RESEARCH_CONTRACT_V3.json",
            "data/RESEARCH_SCOPE_GOVERNANCE_V1.json",
            "evidence/MECHANISM_SCOPE_REGISTRY_V1.json",
            "evidence/V2_CONSUMED_IDENTITY_SCOPE_AUDIT_V1.json",
            "data/AUTONOMOUS_UNIVERSE_GOVERNOR_V1.json",
            "data/ADAPTIVE_DATA_ACQUISITION_POLICY_V1.json",
            "data/CAPITAL_FLOW_AWARE_CAUSAL_GOVERNOR_V1.json",
            "research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json",
        ],
        "created_utc": iso(),
    }
    atomic_write_json(root / REQUEST_REL, request)
    return request


def _emit(payload: Mapping[str, Any]) -> None:
    print(json.dumps(dict(payload), sort_keys=True, indent=2))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as handle:
            if payload.get("status") is not None:
                handle.write(f"status={payload['status']}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=PROTOCOL_VERSION)
    parser.add_argument("command", choices=("validate", "materialize", "drain", "request"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--proposal")
    parser.add_argument("--git-checkpoint", action="store_true")
    parser.add_argument("--git-push", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.command == "validate":
        if not args.proposal:
            raise SystemExit("--proposal required")
        proposal = _load(root, args.proposal)
        payload = {"status": "PASS", "validation": validate_proposal(root, proposal)}
    elif args.command == "materialize":
        if not args.proposal:
            raise SystemExit("--proposal required")
        payload = materialize_proposal(
            root, args.proposal, git_checkpoint=args.git_checkpoint, git_push=args.git_push,
        )
    elif args.command == "drain":
        payload = drain(root, git_checkpoint=args.git_checkpoint, git_push=args.git_push)
    else:
        payload = write_reasoning_request(root)
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
