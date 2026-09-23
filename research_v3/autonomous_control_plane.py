"""Autonomous restartable research control plane for Performance Research V3."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from discovery.accounting import assert_current_state_matches_repository
from discovery.ledger import read_ledger
from research_v3.lifecycle import repository_lifecycle_summary

CHECKPOINT_REF = "research_v3/AUTONOMOUS_CHECKPOINT_V1.json"
CONTROL_PLANE_VERSION = "MXM_AUTONOMOUS_CONTROL_PLANE_V1"

class ControlPlaneHalt(RuntimeError):
    pass

def _load(root: Path, rel: str) -> dict[str, Any]:
    return json.loads((root / rel).read_text(encoding="utf-8"))

def inspect_repository_state(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    state = _load(root, "CURRENT_STATE.json")
    accounting = assert_current_state_matches_repository(root)
    lifecycle = repository_lifecycle_summary(root)
    ledger = read_ledger(root / "discovery/ledger.jsonl")
    issues: list[dict[str, Any]] = []
    recoverable: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    if lifecycle["distinct_identity_outcomes_opened"] != accounting["v2_attempts_used"]:
        issues.append({"class":"ACCOUNTING_INTEGRITY","detail":"distinct opened identities != v2_attempts_used"})
    if lifecycle["stage_a_result_recorded_entries"] != accounting["stage_a_result_recorded_entries"]:
        issues.append({"class":"ACCOUNTING_INTEGRITY","detail":"Stage-A result-row count mismatch"})
    if lifecycle["incomplete_corrections"]:
        recoverable.append({"class":"PARTIAL_SAME_IDENTITY_PERSISTENCE","detail":lifecycle["incomplete_corrections"]})

    pending = sorted(state.get("pending_same_identity_correction_candidate_ids", []))
    if pending:
        recoverable.append({"class":"PENDING_SAME_IDENTITY_CORRECTION","candidate_ids":pending})

    correction = state.get("same_identity_live_equivalent_correction") or {}
    correction_refs = correction.get("result_refs") or {}
    ledger_hashes = {
        (row.get("payload") or {}).get("result_hash")
        for row in ledger if row.get("entry_type") == "RESULT_RECORDED"
    }
    orphaned_successors: list[str] = []
    for cid, rel in correction_refs.items():
        path = root / rel
        if not path.is_file():
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        if result.get("result_hash") not in ledger_hashes:
            orphaned_successors.append(cid)
    if orphaned_successors:
        recoverable.append({"class":"RESULT_FILE_AHEAD_OF_LEDGER","candidate_ids":sorted(orphaned_successors)})

    perf = state.get("performance_research_v3") or {}
    for key, wave in sorted(perf.items()):
        if not key.startswith("wave") or not isinstance(wave, Mapping):
            continue
        candidate_ids = list(wave.get("candidate_ids") or [])
        if not candidate_ids:
            continue
        result_counts = {
            cid: len([row for row in ledger if row.get("candidate_id") == cid and row.get("entry_type") == "RESULT_RECORDED"])
            for cid in candidate_ids
        }
        opened = bool(wave.get("candidate_own_outcomes_opened"))
        status = str(wave.get("status", ""))
        revoked = bool(wave.get("authorization_revoked")) or "BLOCKED" in status or "REVOKED" in status
        if not opened and any(result_counts.values()):
            recoverable.append({"class":"WAVE_LEDGER_AHEAD_OF_STATE","wave_key":key,"result_counts":result_counts})
        elif not opened and not revoked and wave.get("authorization_bound") is True:
            recoverable.append({"class":"AUTHORIZED_WAVE_UNOPENED","wave_key":key,"candidate_ids":candidate_ids})
        elif not opened and not revoked and "FROZEN_PENDING_EXACT_HEAD_GREEN" in status:
            recoverable.append({"class":"FROZEN_WAVE_PENDING_AUTHORIZATION","wave_key":key,"candidate_ids":candidate_ids})
        elif not opened and revoked:
            blocked.append({"class":"INVALID_OR_REVOKED_WAVE","wave_key":key,"candidate_ids":candidate_ids})

    stage_b = sorted(state.get("stage_b_revalidation_required_candidate_ids", []))
    current_live = sorted(state.get("current_live_equivalent_authoritative_candidate_ids", []))
    invalid_specs = sorted(state.get("invalid_frozen_spec_candidate_ids", []))
    safety = {
        "protected_evidence_opened": bool(state.get("protected_evidence_opened")),
        "live_orders_authorized": bool(state.get("live_orders_authorized")),
        "competition_start_authorized": bool(state.get("competition_start_authorized")),
    }
    if any(safety.values()):
        issues.append({"class":"EXTERNAL_SAFETY_GATE_DRIFT","detail":safety})

    if issues:
        next_action = "HALT_FAIL_CLOSED_MATERIAL_INTEGRITY"
    elif any(x["class"] in {"PARTIAL_SAME_IDENTITY_PERSISTENCE","RESULT_FILE_AHEAD_OF_LEDGER","WAVE_LEDGER_AHEAD_OF_STATE"} for x in recoverable):
        next_action = "RESUME_IDEMPOTENT_PERSISTENCE"
    elif pending:
        next_action = "RESUME_SAME_IDENTITY_CORRECTION"
    elif any(x["class"]=="AUTHORIZED_WAVE_UNOPENED" for x in recoverable):
        next_action = "EXECUTE_AUTHORIZED_WAVE"
    elif any(x["class"]=="FROZEN_WAVE_PENDING_AUTHORIZATION" for x in recoverable):
        next_action = "REQUIRE_EXACT_HEAD_GREEN_AND_BIND_AUTHORIZATION"
    elif stage_b:
        next_action = "REVALIDATE_STAGE_B"
    else:
        next_action = "FREEZE_NEXT_HIGH_INFORMATION_WAVE"

    return {
        "schema":"mxm.greenfield.autonomous-control-plane-report.v1",
        "control_plane_version":CONTROL_PLANE_VERSION,
        "phase":state.get("phase"),
        "next_action":next_action,
        "accounting":accounting,
        "lifecycle":lifecycle,
        "current_live_equivalent_authoritative_candidate_ids":current_live,
        "pending_same_identity_correction_candidate_ids":pending,
        "stage_b_revalidation_required_candidate_ids":stage_b,
        "invalid_frozen_spec_candidate_ids":invalid_specs,
        "recoverable_conditions":recoverable,
        "blocked_historical_waves":blocked,
        "material_issues":issues,
        "safety":safety,
    }

def validate_repository_state(root: str | Path = ".") -> dict[str, Any]:
    report = inspect_repository_state(root)
    if report["material_issues"]:
        raise ControlPlaneHalt(json.dumps(report["material_issues"], sort_keys=True))
    if report["accounting"]["v2_attempts_used"] != report["lifecycle"]["distinct_identity_outcomes_opened"]:
        raise ControlPlaneHalt("search-budget identity count does not match lifecycle exposure")
    if report["accounting"]["economic_outcomes_opened"] != (
        report["lifecycle"]["stage_a_result_recorded_entries"]
        + report["accounting"]["stage_b_current_config_economic_observations"]
    ):
        raise ControlPlaneHalt("economic outcome decomposition mismatch")
    return report

def targeted_test_modules(report: Mapping[str, Any]) -> list[str]:
    modules = [
        "tests.test_current_accounting_integrity",
        "tests.test_same_identity_persistence_v1",
        "tests.test_same_identity_live_equivalent_correction_v1",
        "tests.test_research_v3_lifecycle",
        "tests.test_autonomous_control_plane_v1",
    ]
    if report.get("stage_b_revalidation_required_candidate_ids"):
        modules += [
            "tests.test_c012_same_identity_recovery_authority",
            "tests.test_c012_corrected_stage_b_recovery",
        ]
    return modules

def run_targeted_tests(root: str | Path = ".", modules: list[str] | None = None) -> None:
    root = Path(root)
    report = validate_repository_state(root)
    modules = modules or targeted_test_modules(report)
    subprocess.run([sys.executable, "-m", "unittest", "-v", *modules], cwd=root, check=True)

def resume_idempotent_persistence(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    report = inspect_repository_state(root)
    relevant = [
        x for x in report["recoverable_conditions"]
        if x["class"] in {"PARTIAL_SAME_IDENTITY_PERSISTENCE","RESULT_FILE_AHEAD_OF_LEDGER"}
    ]
    if not relevant:
        return report
    state = _load(root, "CURRENT_STATE.json")
    correction = state.get("same_identity_live_equivalent_correction") or {}
    refs = correction.get("result_refs") or {}
    docs = {}
    for cid, rel in refs.items():
        path = root / rel
        if path.is_file():
            docs[cid] = json.loads(path.read_text(encoding="utf-8"))
    if not docs:
        raise ControlPlaneHalt("partial same-identity persistence detected but no durable corrected result files exist")
    from research_v3.same_identity_persistence_v1 import persist_same_identity_corrections
    authority_ref = correction.get("authority_ref")
    if not isinstance(authority_ref, str):
        raise ControlPlaneHalt("same-identity recovery lacks durable authority_ref")
    persist_same_identity_corrections(
        root, results=docs, recorded_utc="2026-09-23T09:36:00Z", authority_ref=authority_ref,
    )
    return validate_repository_state(root)

def write_checkpoint(root: str | Path, report: Mapping[str, Any], *, status: str) -> Path:
    root = Path(root)
    path = root / CHECKPOINT_REF
    checkpoint = {
        "schema":"mxm.greenfield.autonomous-research-checkpoint.v1",
        "control_plane_version":CONTROL_PLANE_VERSION,
        "status":status,
        "phase":report.get("phase"),
        "next_action":report.get("next_action"),
        "ledger_tail_entry_hash":report.get("lifecycle",{}).get("ledger_tail_entry_hash"),
        "accounting":{
            key:report.get("accounting",{}).get(key) for key in (
                "v2_attempts_used","v2_evaluated_identities","v2_search_budget_remaining",
                "economic_outcomes_opened","distinct_identity_outcomes_opened",
                "stage_a_result_recorded_entries","stage_b_current_config_economic_observations",
            )
        },
        "current_live_equivalent_authoritative_candidate_ids":report.get("current_live_equivalent_authoritative_candidate_ids",[]),
        "pending_same_identity_correction_candidate_ids":report.get("pending_same_identity_correction_candidate_ids",[]),
        "stage_b_revalidation_required_candidate_ids":report.get("stage_b_revalidation_required_candidate_ids",[]),
        "recoverable_conditions":report.get("recoverable_conditions",[]),
        "material_issues":report.get("material_issues",[]),
        "safety":report.get("safety",{}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return path

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=("inspect","validate","targeted-tests","resume"))
    parser.add_argument("--root",default=".")
    parser.add_argument("--checkpoint",action="store_true")
    args=parser.parse_args(argv)
    if args.command=="inspect":
        report=inspect_repository_state(args.root)
    elif args.command=="validate":
        report=validate_repository_state(args.root)
    elif args.command=="targeted-tests":
        run_targeted_tests(args.root); report=validate_repository_state(args.root)
    else:
        report=resume_idempotent_persistence(args.root)
    if args.checkpoint:
        write_checkpoint(args.root,report,status="VALIDATED" if not report["material_issues"] else "HALTED")
    print(json.dumps(report,sort_keys=True,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
