"""Fail-closed pre-promotion validation for authoritative repository state."""
from __future__ import annotations

import compileall
import json
import os
from pathlib import Path

from discovery.accounting import assert_current_state_matches_repository
from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.ledger import read_ledger
from discovery.schema import validate_result

ROOT = Path(__file__).resolve().parents[1]
PATH_PREFIXES = ("data/", "discovery/", "evidence/", "m6/", "m7/", "competition/", "tests/", "tools/")


def _json_files():
    for path in ROOT.rglob("*.json"):
        if ".git" not in path.parts:
            yield path


def _walk_refs(value):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_refs(nested)
    elif isinstance(value, str):
        yield value



def _validate_repository_local_ref(ref: str, *, source: Path) -> None:
    if not ref.startswith(PATH_PREFIXES):
        return
    if any(token in ref for token in ("*", "{", "}")):
        return
    if not ref.endswith((".json", ".py", ".txt")):
        return
    if not (ROOT / ref).exists():
        raise ValueError(
            f"repository-local reference missing from {source.relative_to(ROOT)}: {ref}"
        )


def _validate_active_authority_references(state):
    sources = [(ROOT / "CURRENT_STATE.json", state)]
    for path in _json_files():
        if path == ROOT / "CURRENT_STATE.json":
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and value.get("authority_scope") == "ACTIVE_CURRENT":
            sources.append((path, value))
    for source, value in sources:
        for ref in _walk_refs(value):
            _validate_repository_local_ref(ref, source=source)


def _validate_current_dependency_semantics(state):
    branch = state.get("authoritative_branch")
    operational = state.get("operational_branch_authority")
    if not isinstance(operational, dict):
        raise ValueError("missing operational_branch_authority")
    if branch != operational.get("branch"):
        raise ValueError("authoritative_branch contradicts operational branch authority")
    if operational.get("work_branch") == branch:
        raise ValueError("work branch must remain distinct from operational branch")

    invalid = set(state.get("implementation_invalid_consumed_identities", []))
    survivors = set(state.get("discovery_survivors", []))
    stage_b_inputs = set(state.get("current_stage_b_survivor_input_set", []))
    current = state.get("current_result_authority")
    if not isinstance(current, dict):
        raise ValueError("missing current_result_authority")

    for cid in invalid:
        node = current.get(cid)
        if not isinstance(node, dict):
            raise ValueError(f"implementation-invalid identity lacks current authority node: {cid}")
        stage_a = node.get("stage_a")
        if not isinstance(stage_a, dict):
            raise ValueError(f"implementation-invalid identity lacks Stage-A authority: {cid}")
        replay_invalid = stage_a.get("live_equivalent_replay_state") == "IMPLEMENTATION_INVALID_SAME_SEMANTICS_CORRECTABLE"
        corrected = stage_a.get("state") == "VALID_CORRECTED_SUCCESSOR" and not replay_invalid
        if not corrected and cid in survivors:
            raise ValueError(f"current survivor list contains invalidated identity without corrected successor: {cid}")
        if not corrected and cid in stage_b_inputs:
            raise ValueError(f"current Stage-B input set contains invalidated identity without corrected successor: {cid}")

        # Only identities that actually reached Stage B require downstream
        # invalidation. Stage-A-only identities must not fabricate a Stage-B node.
        downstream = node.get("stage_b_current_config")
        if downstream is not None:
            if not isinstance(downstream, dict):
                raise ValueError(f"invalid downstream authority node: {cid}")
            if not corrected and downstream.get("state") != "INVALIDATED_DOWNSTREAM_OF_IMPLEMENTATION_INVALID_STAGE_A":
                raise ValueError(f"current downstream result not invalidated for implementation-invalid upstream: {cid}")
            if not corrected:
                ref = downstream.get("invalidation_ref")
                if not isinstance(ref, str) or not (ROOT / ref).exists():
                    raise ValueError(f"missing explicit downstream invalidation authority: {cid}")

    correction = state.get("c012_same_identity_corrected_rerun")
    if not isinstance(correction, dict):
        raise ValueError("missing C012 corrected rerun state")
    pending = correction.get("status") not in {
        "CORRECTED_STAGE_A_RECORDED_SURVIVOR",
        "CORRECTED_STAGE_A_RECORDED_NON_SURVIVOR",
    }
    if pending:
        if "V2-C012" in survivors or "V2-C012" in stage_b_inputs:
            raise ValueError("C012 cannot be current survivor/Stage-B input before corrected Stage-A successor")
        if "C012" not in str(state.get("phase", "")) or "C012" not in str(state.get("next_action", "")):
            raise ValueError("branch/action pointers contradict pending C012 correction state")


def main() -> int:
    if not compileall.compile_dir(str(ROOT), quiet=1, force=True):
        raise SystemExit("Python compilation failed")

    for path in _json_files():
        json.loads(path.read_text(encoding="utf-8"))

    for path in sorted((ROOT / "discovery" / "candidates").glob("V2-C*.json")):
        verify_spec_hash(json.loads(path.read_text(encoding="utf-8")))

    for path in sorted((ROOT / "discovery" / "results").glob("V2-C*_STAGE_A_*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        validate_result(result)
        if result.get("result_hash") != compute_result_hash(result):
            raise ValueError(f"result_hash mismatch: {path.relative_to(ROOT)}")

    read_ledger(ROOT / "discovery" / "ledger.jsonl")
    accounting = assert_current_state_matches_repository(ROOT)

    state = json.loads((ROOT / "CURRENT_STATE.json").read_text(encoding="utf-8"))
    _validate_active_authority_references(state)
    _validate_current_dependency_semantics(state)

    print("AUTHORITATIVE_PROMOTION_VALIDATION_PASS", accounting)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
