"""Canonical live accounting derived from immutable ledger/results/budget authorities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import compute_result_hash, verify_spec_hash
from .ledger import derive_active_spec_hashes, read_ledger
from .schema import validate_result


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _standalone_result_matches(root: Path, candidate_id: str, result: dict[str, Any]) -> bool:
    expected_hash = compute_result_hash(result)
    for path in sorted((root / "discovery" / "results").glob(f"{candidate_id}_STAGE_A_*.json")):
        standalone = _load(path)
        validate_result(standalone)
        if compute_result_hash(standalone) == expected_hash and standalone == result:
            return True
    return False


def derive_current_accounting(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    budget = _load(root / "V2_SEARCH_BUDGET_V1.json")
    entries = read_ledger(root / "discovery" / "ledger.jsonl")
    active = derive_active_spec_hashes(entries)

    result_entries = [e for e in entries if e.get("entry_type") == "RESULT_RECORDED"]
    correction_entries = [e for e in entries if e.get("entry_type") == "IMPLEMENTATION_CORRECTION"]
    evaluated_ids = sorted({e["candidate_id"] for e in result_entries})

    for candidate_id, spec_hash in active.items():
        candidate_path = root / "discovery" / "candidates" / f"{candidate_id}.json"
        if not candidate_path.is_file():
            raise ValueError(f"active candidate missing: {candidate_path}")
        candidate = _load(candidate_path)
        verify_spec_hash(candidate)
        if candidate["spec_hash"] != spec_hash:
            raise ValueError(f"active candidate spec mismatch: {candidate_id}")

    for entry in result_entries:
        result = entry.get("payload", {}).get("result")
        if not isinstance(result, dict):
            raise ValueError(f"ledger result payload missing for sequence {entry['sequence']}")
        validate_result(result)
        expected_hash = compute_result_hash(result)
        if entry["payload"].get("result_hash") != expected_hash:
            raise ValueError(f"ledger result hash mismatch for sequence {entry['sequence']}")
        if not _standalone_result_matches(root, entry["candidate_id"], result):
            raise ValueError(f"standalone result correspondence missing for sequence {entry['sequence']}")

    # Current-configuration Stage-B scenario outcomes are economic observations but do not
    # consume V2 identity budget. Count one current-config outcome per candidate, irrespective
    # of reporting-file version.
    stage_b_current_config_ids = set()
    for path in (root / "m6" / "results").glob("V2-C*_STAGE_B_CURRENT_CONFIG_V*.json"):
        obj = _load(path)
        cid = obj.get("candidate_id")
        if isinstance(cid, str):
            stage_b_current_config_ids.add(cid)

    v2_budget = int(budget["v2_budget"])
    legacy_prior_attempts = int(budget["legacy_prior_attempts"])
    v2_attempts_used = len(evaluated_ids)
    remaining = v2_budget - v2_attempts_used
    if remaining < 0:
        raise ValueError("V2 search budget exhausted below zero")

    latest = result_entries[-1] if result_entries else None
    latest_outcome = None
    if latest is not None:
        r = latest["payload"]["result"]
        latest_outcome = {
            "candidate_id": latest["candidate_id"],
            "stage": r["stage"],
            "status": r["status"],
            "result_hash": latest["payload"]["result_hash"],
        }

    return {
        "v2_search_budget": v2_budget,
        "legacy_prior_attempts": legacy_prior_attempts,
        "v2_attempts_used": v2_attempts_used,
        "v2_evaluated_identities": v2_attempts_used,
        "v2_search_budget_remaining": remaining,
        "global_attempts_seen": legacy_prior_attempts + v2_attempts_used,
        "economic_outcomes_opened": len(result_entries) + len(stage_b_current_config_ids),
        "discovery_ledger_entries": len(entries),
        "discovery_result_recorded_entries": len(result_entries),
        "implementation_correction_entries": len(correction_entries),
        "evaluated_candidate_ids": evaluated_ids,
        "stage_b_current_config_candidate_ids": sorted(stage_b_current_config_ids),
        "latest_economic_outcome": latest_outcome,
    }


def assert_current_state_matches_repository(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    derived = derive_current_accounting(root)
    state = _load(root / "CURRENT_STATE.json")
    for key in (
        "v2_search_budget",
        "legacy_prior_attempts",
        "v2_attempts_used",
        "v2_evaluated_identities",
        "v2_search_budget_remaining",
        "global_attempts_seen",
        "economic_outcomes_opened",
        "discovery_ledger_entries",
        "discovery_result_recorded_entries",
    ):
        if state.get(key) != derived[key]:
            raise ValueError(f"CURRENT_STATE {key}={state.get(key)!r} != derived {derived[key]!r}")
    latest = derived["latest_economic_outcome"]
    if latest:
        live_latest = state.get("latest_economic_outcome") or {}
        for key in ("candidate_id", "stage", "status", "result_hash"):
            if live_latest.get(key) != latest[key]:
                raise ValueError(f"CURRENT_STATE latest_economic_outcome.{key} mismatch")
    return derived
