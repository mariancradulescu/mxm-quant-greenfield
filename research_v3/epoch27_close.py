"""Exactly-once closure of a frozen non-economic research spec."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from research_v3.evidence_epoch import advance_evidence_epoch
from research_v3.research_spec_kernel import execute
from research_v3.runtime_v2_primitives import atomic_write_json

SPEC = Path("research_v3/EPOCH27_PROSPECTIVE_BREAKOUT_RESEARCH_SPEC_V1.json")
INPUT = Path("research_v3/EPOCH27_BREAKOUT_EVENT_TABLE_V1.b64")
RESULT = Path("evidence/EPOCH27_BREAKOUT_STABILITY_BREADTH_RESULT_V1.json")
EPOCH = Path("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
STATE = Path("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
FRONTIER = Path("research_v3/CURRENT_RESEARCH_FRONTIER_V1.json")
PROJECTION = Path("research_v3/ACTIVE_RESEARCH_PROJECTION_V1.json")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(root: Path) -> dict:
    root = root.resolve()
    epoch = load(root/EPOCH)
    state = load(root/STATE)
    if epoch["current_epoch"] != 27:
        if epoch["current_epoch"] == 28 and (root/RESULT).is_file():
            return {"status": "ALREADY_CLOSED", "epoch": 28}
        raise ValueError("unexpected evidence epoch: refusing duplicate or stale execution")
    if (root/RESULT).exists():
        raise ValueError("unadvanced result already exists: manual integrity review required")
    if state["status"] != "ADDITIONAL_AUTHORITY_REQUIRED" or state["current_research_evidence_epoch"] != 27:
        raise ValueError("semantic selection is no longer the authoritative current state")
    spec = load(root/SPEC)
    if spec["semantic_authority"]["family"] != "BREAKOUT_VOLATILITY_EXPANSION":
        raise ValueError("current semantic authority mismatch")
    accounting = dict(state["accounting"])
    result = execute(root/SPEC, root/INPUT, root/RESULT)
    if result["economic_effect"] != {"economic_outcomes_opened": 0,
                                     "v2_attempts_consumed": 0,
                                     "search_budget_change": 0}:
        raise ValueError("economic boundary violation")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    advance_evidence_epoch(root, event_class="MATERIAL_DEVELOPMENT_STRUCTURAL_EVIDENCE_ACCEPTED",
                           refs=[str(SPEC), str(RESULT)],
                           reason="Epoch27 frozen breakout chronological breadth diagnostic completed; descriptive development only",
                           advanced_utc=now)
    state.update({
        "status": "FRESH_GENERAL_AI_REASONING_REQUIRED",
        "next_action": "AI_REASSESS_HIGHEST_INFORMATION_LEGAL_NEXT_ACTION_FROM_CURRENT_EVIDENCE_EPOCH",
        "ai_reasoning_required": True, "research_judgment_required": True,
        "implementation_ai_required": False, "implementation_satisfied": False,
        "current_research_evidence_epoch": 28, "evidence_epoch": 28,
        "authorizing_evidence_epoch": 27,
        "latest_material_structural_result_ref": str(RESULT),
        "completed_structural_report_ref": str(RESULT),
        "completed_family": "BREAKOUT_VOLATILITY_EXPANSION",
        "family_result": result["structural_gate_status"],
        "next_deterministic_operation_ref": None,
        "deterministic_next_operation": None,
        "source_implementation_id": None,
        "external_data_gate": None, "external_data_required": False,
        "economic_authorization": "NOT_REQUESTED",
        "user_action_required": False,
        "accounting": accounting,
    })
    atomic_write_json(root/STATE, state)
    frontier = load(root/FRONTIER)
    frontier.update({
        "status": "EPOCH28_BREAKOUT_STRUCTURAL_RESULT_ACCEPTED_FRESH_SEMANTIC_BOUNDARY",
        "evidence_epoch": 28,
        "active_mechanism_family": None,
        "latest_material_structural_result_ref": str(RESULT),
        "latest_prospective_freeze_ref": str(SPEC),
        "source_refs": list(dict.fromkeys(frontier.get("source_refs", [])+[str(SPEC), str(RESULT)])),
    })
    atomic_write_json(root/FRONTIER, frontier)
    projection = {
        "schema": "mxm.greenfield.active-research-projection.v1",
        "evidence_epoch": 28,
        "latest_accepted_material_result_ref": str(RESULT),
        "accepted_semantic_decision_ref": spec["semantic_authority"]["proposal_ref"],
        "execution_requirement": "FRESH_GENERAL_AI_RESEARCH_JUDGMENT",
        "authority": "NEW_EVIDENCE_EPOCH_REQUIRES_FRESH_REASONING",
        "accounting": accounting,
        "safety": {"protected_forward_opened": False, "live_orders_authorized": False},
        "historical_frontier_ref": str(FRONTIER),
    }
    atomic_write_json(root/PROJECTION, projection)
    if load(root/STATE)["accounting"] != accounting:
        raise ValueError("accounting changed during non-economic closure")
    return {"status": "MATERIAL_RESULT_ACCEPTED", "starting_epoch": 27,
            "final_epoch": 28, "structural_gate_status": result["structural_gate_status"],
            "eligible_symbols": result["eligible_symbols"],
            "stable_symbols": result["stable_symbols"],
            "accounting": accounting}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(run(args.root), sort_keys=True))
