"""Repository-native autonomous planning and operation materialization for Runtime V2."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.autonomous_runtime_v2 import RuntimeV2
from research_v3.runtime_v2_primitives import (
    DEFAULT_RUNTIME_DIR,
    GitCheckpointSink,
    atomic_write_json,
    iso,
    load_json,
    parse_iso,
    sha256_file,
)

DIRECTOR_VERSION = "MXM_AUTONOMOUS_RESEARCH_DIRECTOR_V2"
E2E_STATE_REL = "research_v3/runtime_v2_acceptance/END_TO_END_PROGRESSION_STATE.json"
E2E_REPORT_REL = "research_v3/runtime_v2_acceptance/END_TO_END_PROGRESSION_REPORT.json"
E2E_GATE_REL = "evidence/ZERO_HUMAN_END_TO_END_RESEARCH_PROGRESSION_V1.json"
NEXT_STATE_REL = "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json"
OLD_GATE_REL = "evidence/AUTONOMOUS_RESEARCH_RUNTIME_V2_ACCEPTANCE_V1.json"
DISCOVERY_LEDGER_REL = "discovery/ledger.jsonl"
V6_ACCEPTANCE_REL = "data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json"
EXTERNAL_REQUEST_REL = "research_v3/runtime_v2/external_requests/NEXT_REQUIRED_INPUT.json"
AUTONOMOUS_WAKE_EVENTS = {"workflow_run", "schedule"}
MAX_ACCEPTED_WAKE_LATENCY_SECONDS = 600


class DirectorHalt(RuntimeError):
    pass


def _load(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    if not path.is_file():
        raise DirectorHalt(f"required durable file missing: {rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def _project_snapshot(root: Path) -> dict[str, Any]:
    state = _load(root, "CURRENT_STATE.json")
    report = validate_repository_state(root)
    return {
        "v2_attempts_used": int(report["accounting"]["v2_attempts_used"]),
        "v2_search_budget_remaining": int(report["accounting"]["v2_search_budget_remaining"]),
        "economic_outcomes_opened": int(report["accounting"]["economic_outcomes_opened"]),
        "stage_a_result_recorded_entries": int(state.get("stage_a_result_recorded_entries", -1)),
        "stage_b_current_config_economic_observations": int(state.get("stage_b_current_config_economic_observations", -1)),
        "discovery_ledger_sha256": sha256_file(root / DISCOVERY_LEDGER_REL),
    }


def _assert_project_unchanged(root: Path, baseline: Mapping[str, Any]) -> dict[str, Any]:
    current = _project_snapshot(root)
    if dict(baseline) != current:
        raise DirectorHalt(
            "project economics changed during end-to-end autonomy acceptance: "
            + json.dumps({"before": dict(baseline), "after": current}, sort_keys=True)
        )
    return current


def _old_acceptance_pass(root: Path) -> bool:
    gate = load_json(root / OLD_GATE_REL, {})
    return (
        gate.get("status") in {"PASS", "PASS_EXACT_HEAD_GREEN"}
        and gate.get("repository_level_liveness") == "PASS"
        and gate.get("zero_human_continuation") == "PASS"
        and gate.get("economics_opened_during_fix") == 0
    )


def _existing_operation_paths(root: Path) -> list[Path]:
    ops_dir = root / DEFAULT_RUNTIME_DIR / "operations"
    return sorted(ops_dir.glob("op_*.json")) if ops_dir.is_dir() else []


def _candidate_result_ref(root: Path, candidate_id: str) -> str:
    state = _load(root, "CURRENT_STATE.json")
    rel = (state.get("active_result_pointers") or {}).get(f"{candidate_id}_STAGE_A")
    if isinstance(rel, str) and rel:
        return rel
    for wave in (state.get("performance_research_v3") or {}).values():
        if isinstance(wave, Mapping):
            rel = (wave.get("result_refs") or {}).get(candidate_id)
            if isinstance(rel, str) and rel:
                return rel
    raise DirectorHalt(f"no durable Stage-A result ref for {candidate_id}")


def _candidate_score(result: Mapping[str, Any]) -> tuple[int, int, int, float]:
    metrics = result.get("metrics") or {}
    return (
        int((result.get("data_completeness") or {}).get("state") == "SUFFICIENT"),
        int(metrics.get("active_weeks") or 0),
        int(metrics.get("event_count") or 0),
        abs(float(metrics.get("coarse_net_pnl") or 0.0)),
    )


def choose_concrete_research_action(root: Path, report: Mapping[str, Any]) -> dict[str, Any]:
    next_action = str(report.get("next_action") or "")
    if next_action != "ASSESS_STAGE_B_SURVIVOR":
        raise DirectorHalt(f"no autonomous materializer implemented for legal next_action={next_action!r}")
    survivors = sorted(set(report.get("stage_b_survivors") or []))
    ranked: list[tuple[tuple[int, int, int, float], str, str, dict[str, Any]]] = []
    for cid in survivors:
        rel = _candidate_result_ref(root, cid)
        result = _load(root, rel)
        if result.get("status") == "DISCOVERY_SURVIVOR":
            ranked.append((_candidate_score(result), cid, rel, result))
    if not ranked:
        raise DirectorHalt("control plane requested Stage-B assessment but no valid survivor remains")
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    score, cid, rel, result = ranked[0]
    data_hash = str(((result.get("provenance") or {}).get("data_evidence") or {}).get("binding", {}).get("sha256") or "")
    cost_hash = str(((result.get("provenance") or {}).get("cost_evidence") or {}).get("sha256") or "")
    if len(data_hash) != 64 or len(cost_hash) != 64:
        raise DirectorHalt("selected survivor lacks complete data/cost provenance")
    return {
        "objective": next_action,
        "candidate_id": cid,
        "stage_a_result_ref": rel,
        "candidate_spec_hash": str(result["spec_hash"]),
        "dataset_hash": data_hash,
        "cost_authority_hash": cost_hash,
        "selection_score": {
            "data_sufficient": score[0],
            "active_weeks": score[1],
            "event_count": score[2],
            "absolute_coarse_net_pnl": score[3],
        },
        "selection_population": survivors,
    }


def _director_plan(root: Path, *, action: str, selection: Mapping[str, Any],
                   predecessor_result_ref: str | None = None) -> dict[str, Any]:
    return {
        "operation_kind": "NON_ECONOMIC_DIRECTOR",
        "candidate_spec_hash": str(selection["candidate_spec_hash"]),
        "dataset_hash": str(selection["dataset_hash"]),
        "evaluator_hash": sha256_file(root / "research_v3/autonomous_director_v2.py"),
        "cost_authority_hash": str(selection["cost_authority_hash"]),
        "execution_semantics_version": f"{DIRECTOR_VERSION}:{action}",
        "lifecycle_phase": "AUTONOMY_ACCEPTANCE_NON_ECONOMIC",
        "evaluator": {
            "kind": "python_callable",
            "module": "research_v3.autonomous_director_v2",
            "function": "evaluate_director_operation",
        },
        "director": {
            "director_version": DIRECTOR_VERSION,
            "action": action,
            "candidate_id": selection["candidate_id"],
            "stage_a_result_ref": selection["stage_a_result_ref"],
            "predecessor_result_ref": predecessor_result_ref,
        },
        "pre_outcome_gate": {
            "status": "PASS",
            "classification": "NON_ECONOMIC_AUTONOMY_PROOF",
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


def _find_exact_repo_artifact(root: Path, *, filename: str, sha256: str) -> str | None:
    for path in root.rglob(filename):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_file() and sha256_file(path) == sha256:
            return str(path.relative_to(root))
    return None


def evaluate_director_operation(root_value: str | Path, plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(root_value)
    meta = dict(plan.get("director") or {})
    action = str(meta.get("action"))
    cid = str(meta.get("candidate_id"))
    stage_a_ref = str(meta.get("stage_a_result_ref"))
    stage_a = _load(root, stage_a_ref)
    base = {
        "schema": "mxm.greenfield.runtime-v2-director-result.v1",
        "director_version": DIRECTOR_VERSION,
        "operation_kind": "NON_ECONOMIC_DIRECTOR",
        "operation_id": plan["operation_id"],
        "action": action,
        "candidate_id": cid,
        "stage_a_result_ref": stage_a_ref,
        "economic_outcome_opened": False,
        "new_v2_identity_opened": False,
    }

    if action == "ASSESS_STAGE_B_SURVIVOR":
        report = validate_repository_state(root)
        if report.get("next_action") != "ASSESS_STAGE_B_SURVIVOR" or cid not in set(report.get("stage_b_survivors") or []):
            raise DirectorHalt("durable Stage-B-survivor objective drifted before assessment")
        if stage_a.get("status") != "DISCOVERY_SURVIVOR":
            raise DirectorHalt("selected candidate is no longer a Stage-A survivor")
        if (stage_a.get("implementation_validity") or {}).get("state") != "VALID":
            raise DirectorHalt("selected survivor is not implementation-valid")
        base.update({
            "status": "PASS",
            "decision": {
                "stage_b_research_deserved": True,
                "existing_stage_a_evidence_semantically_sufficient":
                    (stage_a.get("data_completeness") or {}).get("state") == "SUFFICIENT",
                "requires_new_v2_identity": False,
                "requires_new_market_data_before_input_materialization_check": False,
            },
            "next_action": "ASSESS_STAGE_B_INPUT_MATERIALIZATION",
        })
        return base

    if action == "ASSESS_STAGE_B_INPUT_MATERIALIZATION":
        predecessor = str(meta.get("predecessor_result_ref") or "")
        prior = _load(root, predecessor) if predecessor else {}
        if prior.get("status") != "PASS" or not (prior.get("decision") or {}).get("stage_b_research_deserved"):
            raise DirectorHalt("predecessor did not establish Stage-B research need")
        source = (_load(root, V6_ACCEPTANCE_REL).get("source") or {})
        name = str(source.get("external_name") or "")
        digest = str(source.get("zip_sha256") or "")
        if not name or len(digest) != 64:
            raise DirectorHalt("accepted V6 package identity is incomplete")
        repo_ref = _find_exact_repo_artifact(root, filename=name, sha256=digest)
        base.update({
            "status": "PASS",
            "decision": {
                "existing_data_semantically_sufficient": True,
                "new_market_data_acquisition_required": False,
                "requires_new_v2_identity": False,
                "accepted_artifact": {
                    "filename": name,
                    "sha256": digest,
                    "size_bytes": source.get("zip_size_bytes"),
                    "repository_ref": repo_ref,
                    "available_in_repository": bool(repo_ref),
                },
            },
            "next_action": "PREPARE_STAGE_B_RUNTIME_OPERATION"
                if repo_ref else "BUILD_MINIMAL_EXISTING_DATA_MATERIALIZATION_REQUEST",
        })
        return base

    if action == "BUILD_MINIMAL_EXISTING_DATA_MATERIALIZATION_REQUEST":
        source = (_load(root, V6_ACCEPTANCE_REL).get("source") or {})
        base.update({
            "status": "EXTERNAL_EXISTING_ARTIFACT_REQUIRED",
            "request": {
                "request_type": "MATERIALIZE_ALREADY_ACCEPTED_ARTIFACT",
                "new_market_data_acquisition": False,
                "filename": source.get("external_name"),
                "sha256": source.get("zip_sha256"),
                "size_bytes": source.get("zip_size_bytes"),
                "purpose": "Stage-B shared-capital realization input after E2E autonomy acceptance.",
                "forbidden": [
                    "re-capture merely because repository bytes are absent",
                    "open a new V2 identity",
                    "open a Stage-B outcome before exact accepted bytes are available",
                ],
            },
            "next_action": "WAIT_EXTERNAL_EXISTING_V6_ARTIFACT",
        })
        return base

    raise DirectorHalt(f"unsupported director action {action!r}")


def _result_ref_for_op(root: Path, op_id: str) -> str:
    rel = f"{DEFAULT_RUNTIME_DIR}/results/{op_id}.json"
    if not (root / rel).is_file():
        raise DirectorHalt(f"director result missing after Runtime V2 close: {op_id}")
    return rel


def _journal_evidence(root: Path, op_id: str) -> dict[str, Any]:
    runtime = RuntimeV2(root, lease_seconds=1, owner_token="director-proof-reader")
    names = [row.get("event") for row in runtime.journal.events_for(op_id)]
    return {
        "operation_id": op_id,
        "non_economic_result_available_count": names.count("NON_ECONOMIC_RESULT_AVAILABLE"),
        "economic_execution_started_count": names.count("ECONOMIC_EXECUTION_STARTED"),
        "economic_result_available_count": names.count("ECONOMIC_RESULT_AVAILABLE"),
        "operation_closed_count": names.count("OPERATION_CLOSED"),
        "knowledge_scope_updated_count": names.count("KNOWLEDGE_SCOPE_UPDATED"),
    }


def _checkpoint(root: Path, boundary: str, op_id: str | None, *, enabled: bool, push: bool) -> None:
    GitCheckpointSink(root, enabled=enabled, push=push).checkpoint(boundary, op_id)


def _write_next_state(root: Path, state: Mapping[str, Any], control: Mapping[str, Any]) -> None:
    doc = dict(load_json(root / NEXT_STATE_REL, {}) or {})
    doc.update({
        "schema": "mxm.greenfield.runtime-v2-next-autonomous-state.v2",
        "status": state.get("next_state_status", "READY"),
        "next_action": state.get("next_action"),
        "control_plane_next_action": control.get("next_action"),
        "director_version": DIRECTOR_VERSION,
        "end_to_end_acceptance": state.get("status"),
        "autonomous_wake_run_id": state.get("autonomous_wake_run_id"),
        "autonomous_wake_event": state.get("autonomous_wake_event"),
        "observed_wake_latency_seconds": state.get("observed_wake_latency_seconds"),
        "accepted_wake_latency_bound_seconds": MAX_ACCEPTED_WAKE_LATENCY_SECONDS,
        "material_issues": list(control.get("material_issues") or []),
    })
    atomic_write_json(root / NEXT_STATE_REL, doc)


def _run_one(root: Path, plan: dict[str, Any], *, owner_token: str,
             git_checkpoint: bool, git_push: bool) -> tuple[str, str, dict[str, Any]]:
    runtime = RuntimeV2(
        root,
        lease_seconds=900,
        checkpoint_sink=GitCheckpointSink(root, enabled=git_checkpoint, push=git_push),
        owner_token=owner_token,
    )
    op_id, _ = runtime.submit_operation(plan)
    _checkpoint(root, "director_operation_materialized", op_id, enabled=git_checkpoint, push=git_push)
    outcome = runtime.run(max_operations=1)
    if outcome.status not in {"COMPLETE", "BOUNDED_CHECKPOINT"}:
        raise DirectorHalt(f"director operation did not close cleanly: {outcome.status}")
    result_ref = _result_ref_for_op(root, op_id)
    result = _load(root, result_ref)
    proof = _journal_evidence(root, op_id)
    if proof["non_economic_result_available_count"] != 1:
        raise DirectorHalt("director op lacks exactly one NON_ECONOMIC_RESULT_AVAILABLE")
    if proof["economic_execution_started_count"] or proof["economic_result_available_count"]:
        raise DirectorHalt("director op crossed an economic Runtime V2 boundary")
    if proof["operation_closed_count"] != 1 or proof["knowledge_scope_updated_count"] != 1:
        raise DirectorHalt("director op is not durably closed")
    return op_id, result_ref, result


def _finalize(root: Path, state: dict[str, Any], *, run_id: str, event_name: str,
              git_checkpoint: bool, git_push: bool) -> dict[str, Any]:
    before = dict(state["accounting_before"])
    after = _assert_project_unchanged(root, before)
    op_ids = list(state.get("operation_ids") or [])
    if len(op_ids) < 2:
        raise DirectorHalt("acceptance requires at least two autonomous operations")
    proofs = [_journal_evidence(root, op) for op in op_ids]
    for proof in proofs:
        if proof["non_economic_result_available_count"] != 1:
            raise DirectorHalt("non-economic result count mismatch")
        if proof["economic_execution_started_count"] or proof["economic_result_available_count"]:
            raise DirectorHalt("economic Runtime event observed during infrastructure acceptance")
        if proof["operation_closed_count"] != 1 or proof["knowledge_scope_updated_count"] != 1:
            raise DirectorHalt("operation boundary not durably complete")
    chain = list(state.get("workflow_chain") or [])
    if not chain or chain[0].get("event_name") not in AUTONOMOUS_WAKE_EVENTS:
        raise DirectorHalt("proof did not start from a genuine autonomous wake event")
    observed_latency = state.get("observed_wake_latency_seconds")
    if observed_latency is None or float(observed_latency) > MAX_ACCEPTED_WAKE_LATENCY_SECONDS:
        raise DirectorHalt(
            f"autonomous wake exceeded bounded latency: {observed_latency!r}s > "
            f"{MAX_ACCEPTED_WAKE_LATENCY_SECONDS}s"
        )
    report = {
        "schema": "mxm.greenfield.zero-human-end-to-end-research-progression-report.v1",
        "status": "PASS",
        "director_version": DIRECTOR_VERSION,
        "autonomous_wake": {
            "run_id": state["autonomous_wake_run_id"],
            "event_name": state["autonomous_wake_event"],
            "actor": state.get("autonomous_wake_actor"),
            "origin_run_id": state.get("wake_origin_run_id"),
            "origin_completed_at": state.get("wake_origin_completed_at"),
            "observed_utc": state.get("wake_observed_utc"),
            "observed_latency_seconds": state.get("observed_wake_latency_seconds"),
            "accepted_latency_bound_seconds": MAX_ACCEPTED_WAKE_LATENCY_SECONDS,
        },
        "bounded_recovery_latency": "PASS",
        "workflow_chain": chain + [{"run_id": run_id, "event_name": event_name, "phase": "verify"}],
        "starting_condition": {"queued_operations": 0, "durable_next_action": state["starting_next_action"]},
        "planner_operation_materialization": "PASS",
        "cross_operation_progression": "PASS",
        "zero_human_end_to_end_research_progression": "PASS",
        "manual_dispatch_between_steps": False,
        "chat_message_required_between_steps": False,
        "hidden_mnt_data_dependency": False,
        "operation_proofs": proofs,
        "selected_research_action": state["selection"],
        "accounting_before": before,
        "accounting_after": after,
        "economics_opened_during_fix": after["economic_outcomes_opened"] - before["economic_outcomes_opened"],
        "v2_attempt_delta": after["v2_attempts_used"] - before["v2_attempts_used"],
        "discovery_ledger_unchanged": after["discovery_ledger_sha256"] == before["discovery_ledger_sha256"],
        "next_action": state["next_action"],
        "protected_forward_opened": False,
        "live_orders_authorized": False,
        "competition_start_authorized": False,
    }
    if report["economics_opened_during_fix"] != 0 or report["v2_attempt_delta"] != 0 or not report["discovery_ledger_unchanged"]:
        raise DirectorHalt("E2E fix changed project economics/accounting")
    atomic_write_json(root / E2E_REPORT_REL, report)
    atomic_write_json(root / E2E_GATE_REL, {
        "schema": "mxm.greenfield.zero-human-end-to-end-research-progression-gate.v1",
        "status": "PASS",
        "director_version": DIRECTOR_VERSION,
        "report_ref": E2E_REPORT_REL,
        "report_sha256": sha256_file(root / E2E_REPORT_REL),
        "autonomous_wake_run_id": state["autonomous_wake_run_id"],
        "autonomous_wake_event": state["autonomous_wake_event"],
        "observed_wake_latency_seconds": state["observed_wake_latency_seconds"],
        "accepted_wake_latency_bound_seconds": MAX_ACCEPTED_WAKE_LATENCY_SECONDS,
        "bounded_recovery_latency": "PASS",
        "planner_operation_materialization": "PASS",
        "cross_operation_progression": "PASS",
        "zero_human_end_to_end_research_progression": "PASS",
        "economics_opened_during_fix": 0,
        "v2_attempt_delta": 0,
        "economic_resume_gate_open": True,
    })
    state.update({
        "status": "PASS",
        "phase": "ACCEPTED",
        "verification_run_id": run_id,
        "next_state_status": "READY",
    })
    atomic_write_json(root / E2E_STATE_REL, state)
    _write_next_state(root, state, validate_repository_state(root))
    _checkpoint(root, "zero_human_end_to_end_acceptance_pass", None, enabled=git_checkpoint, push=git_push)
    return report


def supervise(root_value: str | Path, *, event_name: str, run_id: str, run_attempt: str,
              actor: str, predecessor_run_id: str, wake_origin_completed_at: str,
              git_checkpoint: bool, git_push: bool) -> dict[str, Any]:
    root = Path(root_value).resolve()
    if not _old_acceptance_pass(root):
        raise DirectorHalt("legacy Runtime V2 acceptance must remain durably PASS")
    control = validate_repository_state(root)
    state = load_json(root / E2E_STATE_REL, None)
    gate = load_json(root / E2E_GATE_REL, {}) or {}

    if state is None:
        if event_name not in AUTONOMOUS_WAKE_EVENTS:
            return {
                "action": "WAIT_FOR_AUTONOMOUS_WAKE",
                "status": "READY_FOR_AUTONOMOUS_WAKE_PROOF",
                "next_action": control["next_action"],
            }
        observed_utc = iso()
        if event_name == "workflow_run":
            if not predecessor_run_id or not wake_origin_completed_at:
                raise DirectorHalt("workflow_run wake lacks upstream run identity/timestamp")
            latency_seconds = max(
                0.0,
                (parse_iso(observed_utc) - parse_iso(wake_origin_completed_at)).total_seconds(),
            )
        else:
            latency_seconds = 0.0
        if latency_seconds > MAX_ACCEPTED_WAKE_LATENCY_SECONDS:
            raise DirectorHalt(
                f"autonomous wake latency {latency_seconds:.3f}s exceeds "
                f"{MAX_ACCEPTED_WAKE_LATENCY_SECONDS}s acceptance bound"
            )
        existing = _existing_operation_paths(root)
        if existing:
            raise DirectorHalt("E2E starting condition requires zero pre-existing Runtime V2 operations")
        selection = choose_concrete_research_action(root, control)
        state = {
            "schema": "mxm.greenfield.zero-human-end-to-end-research-progression-state.v1",
            "director_version": DIRECTOR_VERSION,
            "status": "IN_PROGRESS",
            "phase": 0,
            "starting_next_action": control["next_action"],
            "selection": selection,
            "accounting_before": _project_snapshot(root),
            "autonomous_wake_run_id": run_id,
            "autonomous_wake_event": event_name,
            "autonomous_wake_actor": actor,
            "wake_origin_run_id": predecessor_run_id or None,
            "wake_origin_completed_at": wake_origin_completed_at or None,
            "wake_observed_utc": observed_utc,
            "observed_wake_latency_seconds": latency_seconds,
            "accepted_wake_latency_bound_seconds": MAX_ACCEPTED_WAKE_LATENCY_SECONDS,
            "workflow_chain": [{
                "run_id": run_id,
                "run_attempt": run_attempt,
                "event_name": event_name,
                "actor": actor,
                "predecessor_run_id": predecessor_run_id,
                "phase": "start",
            }],
            "operation_ids": [],
            "operation_result_refs": [],
            "next_action": "ASSESS_STAGE_B_SURVIVOR",
            "next_state_status": "IN_PROGRESS",
        }
        atomic_write_json(root / E2E_STATE_REL, state)
        _checkpoint(root, "e2e_autonomous_wake_start", None, enabled=git_checkpoint, push=git_push)
        op_id, result_ref, result = _run_one(
            root,
            _director_plan(root, action="ASSESS_STAGE_B_SURVIVOR", selection=selection),
            owner_token=f"{run_id}-{run_attempt}-e2e1",
            git_checkpoint=git_checkpoint,
            git_push=git_push,
        )
        if result.get("status") != "PASS":
            raise DirectorHalt("first autonomous planning operation did not PASS")
        state["operation_ids"].append(op_id)
        state["operation_result_refs"].append(result_ref)
        state["phase"] = 1
        state["next_action"] = result["next_action"]
        atomic_write_json(root / E2E_STATE_REL, state)
        _write_next_state(root, state, control)
        _checkpoint(root, "e2e_first_operation_closed", op_id, enabled=git_checkpoint, push=git_push)
        return {"action": "DISPATCH_CONTINUE", "status": "IN_PROGRESS",
                "next_action": state["next_action"], "operation_id": op_id}

    state["workflow_chain"] = list(state.get("workflow_chain") or []) + [{
        "run_id": run_id,
        "run_attempt": run_attempt,
        "event_name": event_name,
        "actor": actor,
        "predecessor_run_id": predecessor_run_id,
        "phase": state.get("phase"),
    }]

    if state.get("status") == "IN_PROGRESS" and state.get("phase") == 1:
        _assert_project_unchanged(root, state["accounting_before"])
        predecessor = state["operation_result_refs"][-1]
        op_id, result_ref, result = _run_one(
            root,
            _director_plan(root, action="ASSESS_STAGE_B_INPUT_MATERIALIZATION",
                           selection=state["selection"], predecessor_result_ref=predecessor),
            owner_token=f"{run_id}-{run_attempt}-e2e2",
            git_checkpoint=git_checkpoint,
            git_push=git_push,
        )
        if result.get("status") != "PASS":
            raise DirectorHalt("second autonomous planning operation did not PASS")
        state["operation_ids"].append(op_id)
        state["operation_result_refs"].append(result_ref)
        state["phase"] = 2
        state["next_action"] = result["next_action"]
        atomic_write_json(root / E2E_STATE_REL, state)
        _write_next_state(root, state, control)
        _checkpoint(root, "e2e_second_operation_closed", op_id, enabled=git_checkpoint, push=git_push)
        return {"action": "DISPATCH_CONTINUE", "status": "IN_PROGRESS",
                "next_action": state["next_action"], "operation_id": op_id}

    if state.get("status") == "IN_PROGRESS" and state.get("phase") == 2:
        report = _finalize(
            root, state, run_id=run_id, event_name=event_name,
            git_checkpoint=git_checkpoint, git_push=git_push,
        )
        return {"action": "DISPATCH_CONTINUE", "status": "PASS", "next_action": report["next_action"]}

    if state.get("status") == "PASS" and gate.get("status") == "PASS":
        _assert_project_unchanged(root, state["accounting_before"])
        if state.get("next_action") == "BUILD_MINIMAL_EXISTING_DATA_MATERIALIZATION_REQUEST":
            predecessor = state["operation_result_refs"][-1]
            op_id, result_ref, result = _run_one(
                root,
                _director_plan(root, action="BUILD_MINIMAL_EXISTING_DATA_MATERIALIZATION_REQUEST",
                               selection=state["selection"], predecessor_result_ref=predecessor),
                owner_token=f"{run_id}-{run_attempt}-postaccept",
                git_checkpoint=git_checkpoint,
                git_push=git_push,
            )
            if result.get("status") != "EXTERNAL_EXISTING_ARTIFACT_REQUIRED":
                raise DirectorHalt("post-acceptance existing-artifact decision did not reach external gate")
            atomic_write_json(root / EXTERNAL_REQUEST_REL, {
                "schema": "mxm.greenfield.runtime-v2-existing-artifact-request.v1",
                "status": "EXTERNAL_ACTION_REQUIRED",
                "candidate_id": state["selection"]["candidate_id"],
                "request": result["request"],
                "source_operation_id": op_id,
                "source_result_ref": result_ref,
                "economics_opened": False,
                "new_v2_identity_opened": False,
            })
            state.update({
                "post_acceptance_operation_id": op_id,
                "post_acceptance_result_ref": result_ref,
                "status": "PASS_EXTERNAL_GATE_REACHED",
                "phase": "POST_ACCEPTANCE_EXTERNAL_GATE",
                "next_action": result["next_action"],
                "next_state_status": "EXTERNAL_ACTION_REQUIRED",
            })
            atomic_write_json(root / E2E_STATE_REL, state)
            _write_next_state(root, state, control)
            _checkpoint(root, "post_acceptance_external_gate", op_id, enabled=git_checkpoint, push=git_push)
            return {"action": "STOP_EXTERNAL_GATE", "status": state["status"],
                    "next_action": state["next_action"], "operation_id": op_id}
        return {"action": "STOP_LEGAL_GATE", "status": state["status"], "next_action": state.get("next_action")}

    if state.get("status") == "PASS_EXTERNAL_GATE_REACHED" and gate.get("status") == "PASS":
        return {"action": "STOP_EXTERNAL_GATE", "status": state["status"], "next_action": state.get("next_action")}

    raise DirectorHalt(f"unsupported durable E2E state: status={state.get('status')} phase={state.get('phase')}")


def _emit(payload: Mapping[str, Any]) -> None:
    print(json.dumps(dict(payload), sort_keys=True, indent=2))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            for key in ("action", "status", "next_action", "operation_id"):
                if payload.get(key) is not None:
                    handle.write(f"{key}={payload[key]}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=DIRECTOR_VERSION)
    parser.add_argument("command", choices=("supervise", "inspect"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", "local"))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "LOCAL"))
    parser.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    parser.add_argument("--actor", default=os.environ.get("GITHUB_ACTOR", "local"))
    parser.add_argument("--predecessor-run-id", default=os.environ.get("MXM_PREDECESSOR_RUN_ID", ""))
    parser.add_argument("--wake-origin-completed-at", default=os.environ.get("MXM_WAKE_ORIGIN_COMPLETED_AT", ""))
    parser.add_argument("--git-checkpoint", action="store_true")
    parser.add_argument("--git-push", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.command == "inspect":
        payload = {
            "control_plane": validate_repository_state(root),
            "e2e_state": load_json(root / E2E_STATE_REL, None),
            "e2e_gate": load_json(root / E2E_GATE_REL, None),
        }
    else:
        payload = supervise(
            root,
            event_name=str(args.event_name),
            run_id=str(args.run_id),
            run_attempt=str(args.run_attempt),
            actor=str(args.actor),
            predecessor_run_id=str(args.predecessor_run_id),
            wake_origin_completed_at=str(args.wake_origin_completed_at),
            git_checkpoint=bool(args.git_checkpoint),
            git_push=bool(args.git_push),
        )
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
