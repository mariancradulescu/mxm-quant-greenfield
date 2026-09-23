"""Fail-closed pre-promotion validation for authoritative repository state."""
from __future__ import annotations

import compileall
import json
import os
from pathlib import Path

from discovery.accounting import assert_current_state_matches_repository, derive_current_accounting
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

    implementation_class = set(state.get("implementation_invalid_consumed_identities", []))
    frozen_spec_invalid = set(state.get("frozen_spec_invalid_consumed_identities", []))
    pending_same_identity = set(state.get("pending_same_identity_correction_candidate_ids", implementation_class))
    if not pending_same_identity <= implementation_class:
        raise ValueError("pending same-identity set is outside historical implementation-correction class")
    corrected_same_identity = implementation_class - pending_same_identity
    currently_invalid = pending_same_identity | frozen_spec_invalid
    historical_forensic = implementation_class | frozen_spec_invalid
    survivors = set(state.get("discovery_survivors", []))
    stage_b_inputs = set(state.get("current_stage_b_survivor_input_set", []))
    current_live = set(state.get("current_live_equivalent_authoritative_candidate_ids", []))
    current = state.get("current_result_authority")
    if not isinstance(current, dict):
        raise ValueError("missing current_result_authority")

    for cid in historical_forensic:
        node = current.get(cid)
        if not isinstance(node, dict):
            raise ValueError(f"forensic identity lacks current authority node: {cid}")
        stage_a = node.get("stage_a")
        if not isinstance(stage_a, dict):
            raise ValueError(f"forensic identity lacks Stage-A authority: {cid}")
        replay_state = stage_a.get("live_equivalent_replay_state")
        if cid in frozen_spec_invalid:
            if replay_state != "FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY":
                raise ValueError(f"frozen-spec-invalid identity has wrong forensic state: {cid}")
            corrected = False
        elif cid in pending_same_identity:
            if replay_state != "IMPLEMENTATION_ONLY_SAME_SEMANTICS_CORRECTABLE":
                raise ValueError(f"pending implementation-only identity has wrong forensic state: {cid}")
            if stage_a.get("current_live_equivalent_authoritative") is not False:
                raise ValueError(f"pending same-identity correction already claims live-equivalent authority: {cid}")
            corrected = False
        else:
            corrected = (
                stage_a.get("state") == "VALID_CORRECTED_SUCCESSOR"
                and replay_state == "CORRECTED_SAME_IDENTITY_CURRENT_AUTHORITY"
                and stage_a.get("current_live_equivalent_authoritative") is True
            )
            if not corrected:
                raise ValueError(f"completed same-identity correction lacks corrected successor authority: {cid}")
            if cid not in current_live:
                raise ValueError(f"corrected same-identity result missing current live-equivalent authority membership: {cid}")

        if not corrected and cid in survivors:
            raise ValueError(f"current survivor list contains invalidated identity without corrected successor: {cid}")
        if not corrected and cid in stage_b_inputs:
            raise ValueError(f"current Stage-B input set contains invalidated identity without corrected successor: {cid}")

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

    audit_ref = state.get("forensic_consumed_identity_audit_authority")
    if audit_ref != "evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V3.json":
        raise ValueError("current forensic authority is not V3")
    audit = json.loads((ROOT / audit_ref).read_text(encoding="utf-8"))
    historical = set(audit["attempt_accounting"]["historical_evaluated_candidate_ids"])
    charged = set(audit["attempt_accounting"]["budget_charged_candidate_ids"])
    if charged != historical:
        raise ValueError("every historically opened V2 identity must remain budget-charged")
    if historical != historical_forensic:
        raise ValueError("forensic classes do not cover historical V2 exposure set")
    if set(audit["attempt_accounting"]["pending_same_identity_correction_candidate_ids"]) != pending_same_identity:
        raise ValueError("pending same-identity correction set mismatch")
    if set(audit["attempt_accounting"]["invalid_frozen_spec_candidate_ids"]) != frozen_spec_invalid:
        raise ValueError("frozen-spec-invalid set mismatch")
    if audit["attempt_accounting"].get("refunded_candidate_ids"):
        raise ValueError("observed V2 identities must not be retroactively refunded")
    current_accounting = derive_current_accounting(ROOT)
    current_exposed = set(current_accounting["evaluated_candidate_ids"])
    if not historical <= current_exposed:
        raise ValueError("historical forensic exposure disappeared from current ledger")
    state_charged = set(state.get("v2_budget_charged_candidate_ids", current_exposed))
    if state_charged != current_exposed:
        raise ValueError("current budget-charged identity set does not match repository exposure")
    if state.get("v2_attempts_used") != len(current_exposed):
        raise ValueError("current V2 budget charge does not match distinct opened identity exposure")
    if state.get("v2_evaluated_identities") != len(current_exposed):
        raise ValueError("current evaluated identity count mismatch")
    if state.get("global_attempts_seen") != state.get("legacy_prior_attempts",0) + state.get("v2_evaluated_identities",0):
        raise ValueError("global information-exposure attempt count mismatch")
    if current_live & currently_invalid:
        raise ValueError("currently invalid forensic identities cannot be live-equivalent authorities")
    if not corrected_same_identity <= current_live:
        raise ValueError("completed same-identity corrections are missing live-equivalent authority")

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
