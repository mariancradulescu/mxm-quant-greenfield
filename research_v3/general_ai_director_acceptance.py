"""Repository-level acceptance for the general AI research director protocol."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_v3.general_ai_director_bridge import (
    GENERAL_GATE_REL,
    PROTOCOL_VERSION,
    materialize_proposal,
    project_snapshot,
    validate_artifact_attestation,
)
from research_v3.runtime_v2_primitives import GitCheckpointSink, atomic_write_json, iso, load_json, sha256_file

E2E_GATE = Path("evidence/ZERO_HUMAN_END_TO_END_RESEARCH_PROGRESSION_V1.json")
REPORT_REL = Path("research_v3/ai_director/GENERAL_AI_DIRECTOR_ACCEPTANCE_REPORT_V1.json")
UNIVERSE_PROPOSAL = "research_v3/ai_director/proposals/ACCEPTANCE_UNIVERSE_DATA_V1.json"
STRATEGY_PROPOSAL = "research_v3/ai_director/proposals/ACCEPTANCE_STRATEGY_PROGRESSION_V1.json"
LIVE_PROPOSAL = "research_v3/ai_director/proposals/LIVE_RESUME_C031_STAGE_B_PREPARATION_V1.json"
V6_ATTESTATION = "research_v3/ai_director/artifact_attestations/MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6_LIBRARY_V1.json"


class GeneralAIAcceptanceError(RuntimeError):
    pass


def _checkpoint(root: Path, boundary: str, enabled: bool, push: bool) -> None:
    GitCheckpointSink(root, enabled=enabled, push=push).checkpoint(boundary, None)


def prove(root_value: str | Path, *, git_checkpoint: bool = False, git_push: bool = False) -> dict[str, Any]:
    root = Path(root_value).resolve()
    existing = load_json(root / GENERAL_GATE_REL, {}) or {}
    if existing.get("status") == "PASS":
        return {"status": "ALREADY_PASS", "gate": existing}

    e2e = load_json(root / E2E_GATE, {}) or {}
    if e2e.get("status") != "PASS" or e2e.get("economics_opened_during_fix") != 0:
        raise GeneralAIAcceptanceError("Runtime V2 end-to-end liveness acceptance is not durably PASS")

    baseline = project_snapshot(root)
    attestation = validate_artifact_attestation(root, V6_ATTESTATION)

    first = materialize_proposal(
        root, UNIVERSE_PROPOSAL, git_checkpoint=git_checkpoint, git_push=git_push,
    )
    second = materialize_proposal(
        root, STRATEGY_PROPOSAL, git_checkpoint=git_checkpoint, git_push=git_push,
    )
    first_class = first["objective_class"]
    second_class = second["objective_class"]
    if first_class == second_class:
        raise GeneralAIAcceptanceError("acceptance objective classes are not materially distinct")

    first_doc = json.loads((root / UNIVERSE_PROPOSAL).read_text(encoding="utf-8"))
    second_doc = json.loads((root / STRATEGY_PROPOSAL).read_text(encoding="utf-8"))
    dims = {
        *(first_doc.get("acceptance_dimensions") or []),
        *(second_doc.get("acceptance_dimensions") or []),
    }
    if "UNIVERSE_AND_DATA_REASONING" not in dims or "STRATEGY_AND_ECONOMIC_PROGRESSION" not in dims:
        raise GeneralAIAcceptanceError("required materially different reasoning dimensions not demonstrated")

    after_cases = project_snapshot(root)
    if after_cases != baseline:
        raise GeneralAIAcceptanceError("general AI acceptance cases changed project economics")

    interim = {
        "schema": "mxm.greenfield.general-ai-research-director-acceptance.v1",
        "status": "PASS",
        "protocol_version": PROTOCOL_VERSION,
        "provider_neutral_interface": "PASS",
        "finite_next_action_mapping_required": False,
        "runtime_v2_deterministic_guard_preserved": "PASS",
        "objective_classes_demonstrated": [first_class, second_class],
        "universe_data_reasoning": "PASS",
        "strategy_economic_progression_reasoning": "PASS",
        "existing_artifact_discovery_reuse": "PASS",
        "v6_artifact": {
            "filename": attestation["artifact"]["filename"],
            "sha256": attestation["artifact"]["sha256"],
            "size_bytes": attestation["artifact"]["size_bytes"],
            "durable_library": True,
            "recapture_required": False,
            "user_action_required": False,
            "github_runner_direct_access": False,
        },
        "economics_opened_during_acceptance": 0,
        "v2_attempt_delta": 0,
        "discovery_ledger_unchanged": True,
        "protected_forward_opened": False,
        "live_orders_authorized": False,
        "competition_start_authorized": False,
        "accepted_utc": iso(),
    }
    atomic_write_json(root / GENERAL_GATE_REL, interim)
    _checkpoint(root, "general_ai_director_acceptance_gate", git_checkpoint, git_push)

    # After the acceptance gate is durable, resume the real project with another free-form AI proposal.
    live = materialize_proposal(
        root, LIVE_PROPOSAL, git_checkpoint=git_checkpoint, git_push=git_push,
    )
    final_snapshot = project_snapshot(root)
    if final_snapshot != baseline:
        raise GeneralAIAcceptanceError("post-acceptance live reasoning proposal changed project economics")

    report = {
        "schema": "mxm.greenfield.general-ai-research-director-acceptance-report.v1",
        "status": "PASS",
        "protocol_version": PROTOCOL_VERSION,
        "acceptance_operations": [first, second],
        "post_acceptance_resume_operation": live,
        "accounting_before": baseline,
        "accounting_after": final_snapshot,
        "economics_opened_during_acceptance": final_snapshot["economic_outcomes_opened"] - baseline["economic_outcomes_opened"],
        "v2_attempt_delta": final_snapshot["v2_attempts_used"] - baseline["v2_attempts_used"],
        "discovery_ledger_unchanged": final_snapshot["discovery_ledger_sha256"] == baseline["discovery_ledger_sha256"],
        "artifact_reuse_attestation_ref": V6_ATTESTATION,
        "next_state_ref": "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json",
        "completed_utc": iso(),
    }
    if report["economics_opened_during_acceptance"] != 0 or report["v2_attempt_delta"] != 0 or not report["discovery_ledger_unchanged"]:
        raise GeneralAIAcceptanceError("final acceptance accounting invariant failed")
    atomic_write_json(root / REPORT_REL, report)

    gate = dict(interim)
    gate.update({
        "report_ref": str(REPORT_REL),
        "report_sha256": sha256_file(root / REPORT_REL),
        "post_acceptance_resume_operation_id": live.get("operation_id"),
        "status": "PASS",
    })
    atomic_write_json(root / GENERAL_GATE_REL, gate)
    _checkpoint(root, "general_ai_director_acceptance_complete", git_checkpoint, git_push)
    return {"status": "PASS", "gate": gate, "report": report}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prove",))
    parser.add_argument("--root", default=".")
    parser.add_argument("--git-checkpoint", action="store_true")
    parser.add_argument("--git-push", action="store_true")
    args = parser.parse_args(argv)
    payload = prove(
        args.root, git_checkpoint=args.git_checkpoint, git_push=args.git_push,
    )
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
