"""Repository-level zero-human liveness proof for Autonomous Research Runtime V2.

This module does not execute project economics. It persists a non-economic
checkpoint on one GitHub Actions run and requires a distinct chained supervisor
run (or the scheduled watchdog) to recover it and finish acceptance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from research_v3.runtime_v2_acceptance import zero_human_continuation_demo
from research_v3.runtime_v2_primitives import (
    RUNTIME_VERSION,
    atomic_write_json,
    canonical_bytes,
    iso,
    load_json,
    sha256_bytes,
    sha256_file,
)

STATE_REL = "research_v3/runtime_v2_acceptance/REPOSITORY_LIVENESS_STATE.json"
REPORT_REL = "research_v3/runtime_v2_acceptance/LATEST_ACCEPTANCE_REPORT.json"
GATE_REL = "evidence/AUTONOMOUS_RESEARCH_RUNTIME_V2_ACCEPTANCE_V1.json"
CHECKPOINT_REL = "research_v3/AUTONOMOUS_CHECKPOINT_V1.json"
DISCOVERY_LEDGER_REL = "discovery/ledger.jsonl"
SCHEMA = "mxm.greenfield.runtime-v2-repository-liveness.v1"


def _accounting_snapshot(root: Path) -> dict[str, Any]:
    checkpoint = load_json(root / CHECKPOINT_REL, {})
    accounting = dict(checkpoint.get("accounting") or {})
    return {
        "v2_attempts_used": accounting.get("v2_attempts_used"),
        "v2_search_budget_remaining": accounting.get("v2_search_budget_remaining"),
        "economic_outcomes_opened": accounting.get("economic_outcomes_opened"),
        "discovery_ledger_sha256": sha256_file(root / DISCOVERY_LEDGER_REL),
    }


def _assert_unchanged(root: Path, baseline: dict[str, Any]) -> dict[str, Any]:
    current = _accounting_snapshot(root)
    if current != baseline:
        raise RuntimeError(
            "project economics changed during Runtime V2 liveness acceptance: "
            + json.dumps({"baseline": baseline, "current": current}, sort_keys=True)
        )
    return current


def _operation_id() -> str:
    payload = {
        "schema": SCHEMA,
        "kind": "NON_ECONOMIC_SYNTHETIC_REPOSITORY_RESTART",
        "target_branch": "performance-research-v3-20260922",
        "runtime_version": RUNTIME_VERSION,
    }
    return "liveness_" + sha256_bytes(canonical_bytes(payload))[:24]


def _ctx() -> dict[str, str]:
    return {
        "run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "actor": os.environ.get("GITHUB_ACTOR", "local"),
        "predecessor_run_id": os.environ.get("MXM_PREDECESSOR_RUN_ID", ""),
        "continuation_origin": os.environ.get("MXM_CONTINUATION_ORIGIN", ""),
    }


def _assert_local(report: dict[str, Any]) -> None:
    for key in (
        "zero_human_continuation",
        "chaos_failure_points",
        "stale_lease_takeover",
        "double_executor_start",
        "repeated_dispatch",
        "interrupted_checkpoint_push_recovery",
        "external_data_wait_resume",
    ):
        if report.get(key) != "PASS":
            raise RuntimeError(f"acceptance requirement failed: {key}={report.get(key)!r}")
    for key in (
        "duplicate_result",
        "duplicate_ledger_entry",
        "duplicate_economic_outcome",
        "duplicate_attempt",
        "lost_result",
    ):
        if report.get(key) != 0:
            raise RuntimeError(f"duplicate/loss invariant failed: {key}={report.get(key)!r}")
    if report.get("same_final_canonical_bytes") is not True:
        raise RuntimeError("canonical-byte equivalence failed")


def advance(root: Path) -> dict[str, Any]:
    root = root.resolve()
    state_path = root / STATE_REL
    report_path = root / REPORT_REL
    ctx = _ctx()
    state = load_json(state_path, None)

    if report_path.is_file():
        report = load_json(report_path, {})
        if report.get("status") == "PASS" and report.get("repository_level_liveness") == "PASS":
            return {"action": "ALREADY_ACCEPTED", "report_sha256": sha256_file(report_path)}

    if state is None:
        baseline = _accounting_snapshot(root)
        state = {
            "schema": SCHEMA,
            "status": "CHECKPOINTED_AWAITING_RESTART",
            "operation_id": _operation_id(),
            "runtime_version": RUNTIME_VERSION,
            "phase": 1,
            "first_run_id": ctx["run_id"],
            "first_run_attempt": ctx["run_attempt"],
            "first_event_name": ctx["event_name"],
            "first_actor": ctx["actor"],
            "created_utc": iso(),
            "baseline_accounting": baseline,
            "economic_operation": False,
            "economic_outcome_opened": False,
        }
        atomic_write_json(state_path, state)
        return {"action": "DISPATCH_CONTINUE", "first_run_id": ctx["run_id"]}

    if state.get("status") != "CHECKPOINTED_AWAITING_RESTART":
        raise RuntimeError(f"unexpected liveness state: {state.get('status')!r}")
    if ctx["run_id"] == str(state.get("first_run_id")):
        raise RuntimeError("continuation must occur in a distinct GitHub Actions run")

    chained = (
        ctx["predecessor_run_id"] == str(state.get("first_run_id"))
        and ctx["continuation_origin"] == "predecessor_workflow_dispatch"
    )
    watchdog = ctx["continuation_origin"] == "scheduled_watchdog"
    if not (chained or watchdog):
        raise RuntimeError("continuation lacks zero-human predecessor/watchdog proof")

    baseline = dict(state.get("baseline_accounting") or {})
    before = _assert_unchanged(root, baseline)
    local = zero_human_continuation_demo()
    _assert_local(local)
    after = _assert_unchanged(root, baseline)

    report = dict(local)
    report.update({
        "schema": "mxm.greenfield.runtime-v2-acceptance-report.v2",
        "status": "PASS",
        "runtime_version": RUNTIME_VERSION,
        "zero_human_continuation": "PASS",
        "repository_level_liveness": "PASS",
        "repository_operation_id": state["operation_id"],
        "repository_restart": {
            "first_run_id": str(state.get("first_run_id")),
            "resume_run_id": ctx["run_id"],
            "distinct_runs": True,
            "continuation_origin": ctx["continuation_origin"],
            "predecessor_run_id": ctx["predecessor_run_id"],
            "first_event_name": state.get("first_event_name"),
            "resume_event_name": ctx["event_name"],
            "first_actor": state.get("first_actor"),
            "resume_actor": ctx["actor"],
            "manual_workflow_rerun_required": False,
            "chat_message_required_between_runs": False,
        },
        "accounting_before": before,
        "accounting_after": after,
        "economics_opened_during_fix": 0,
        "project_discovery_ledger_unchanged": True,
        "completed_utc": iso(),
    })
    atomic_write_json(report_path, report)
    state.update({
        "status": "COMPLETED_PENDING_VERIFY",
        "phase": 2,
        "resume_run_id": ctx["run_id"],
        "report_ref": REPORT_REL,
        "report_sha256": sha256_file(report_path),
        "accounting_after": after,
        "economic_outcome_opened": False,
        "completed_utc": iso(),
    })
    atomic_write_json(state_path, state)
    return {"action": "DISPATCH_VERIFY", "report_sha256": state["report_sha256"]}


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    state = load_json(root / STATE_REL, {})
    report = load_json(root / REPORT_REL, {})
    if state.get("status") != "COMPLETED_PENDING_VERIFY":
        raise RuntimeError("liveness state is not ready for verification")
    _assert_local(report)
    if report.get("repository_level_liveness") != "PASS":
        raise RuntimeError("repository-level liveness proof is not PASS")
    if report.get("economics_opened_during_fix") != 0:
        raise RuntimeError("acceptance indicates project economics changed")
    current = _assert_unchanged(root, dict(state.get("baseline_accounting") or {}))
    report_hash = sha256_file(root / REPORT_REL)
    if state.get("report_sha256") != report_hash:
        raise RuntimeError("persisted acceptance report hash mismatch")
    verification_run_id = _ctx()["run_id"]
    gate = {
        "schema": "mxm.greenfield.autonomous-research-runtime-v2-acceptance-gate.v1",
        "runtime_version": RUNTIME_VERSION,
        "status": "PASS",
        "economic_resume_gate_open": True,
        "report_ref": REPORT_REL,
        "report_sha256": report_hash,
        "repository_level_liveness": "PASS",
        "zero_human_continuation": "PASS",
        "economics_opened_during_fix": 0,
        "verification_run_id": verification_run_id,
        "verified_utc": iso(),
    }
    atomic_write_json(root / GATE_REL, gate)
    state["status"] = "VERIFIED_GREEN_PENDING_SUPERVISOR_COMPLETION"
    state["phase"] = 3
    state["verification_run_id"] = verification_run_id
    state["verified_utc"] = iso()
    atomic_write_json(root / STATE_REL, state)
    return {
        "action": "VERIFIED",
        "status": "PASS",
        "report_sha256": report_hash,
        "accounting": current,
        "first_run_id": state.get("first_run_id"),
        "resume_run_id": state.get("resume_run_id"),
        "verification_run_id": verification_run_id,
    }


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            for key in ("action", "report_sha256", "first_run_id", "resume_run_id", "verification_run_id"):
                if key in payload and payload[key] is not None:
                    f.write(f"{key}={payload[key]}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("advance", "verify"))
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    payload = advance(Path(args.root)) if args.command == "advance" else verify(Path(args.root))
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
