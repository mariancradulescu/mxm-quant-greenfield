"""Fail-closed runner for the Stage-B CURRENT broker-configuration scenario.

Repository validation is enabled now. Economic execution is implemented in memory but remains
blocked until a separate single-use authorization is activated after independent audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .stage_b_evaluator import CANDIDATE_SPEC_HASHES
from .stage_b_current_config_evaluator import (
    CURRENT_CONFIG_AUTHORITY_STATUS,
    realize_current_configuration_capital,
    validate_current_configuration_authority,
)

CURRENT_AUTHORITY_REF = "evidence/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json"
CURRENT_AUTHORITY_GIT_BLOB = "47c1f081bdce0dec92dd40543d6627ae224f6f8d"
CURRENT_POLICY_REF = "data/M6_STAGE_B_CURRENT_CONFIG_TIER1_EVALUATOR_POLICY_V1.json"
CURRENT_POLICY_GIT_BLOB = "bf157e44a3f93e111fc02006bd035595ba4c6084"
CURRENT_EVALUATOR_REF = "m6/stage_b_current_config_evaluator.py"
CURRENT_EVALUATOR_GIT_BLOB = "4a469e5722dd82f40b6351dccea6ed90811c2cf6"
HISTORICAL_AUTHORITY_REF = "evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json"
HISTORICAL_AUTHORITY_GIT_BLOB = "63a959ef9c767956d92772102f3aae3ab3b58237"
HISTORICAL_POLICY_REF = "data/M6_STAGE_B_TIER1_EVALUATOR_POLICY_V1.json"
HISTORICAL_POLICY_GIT_BLOB = "c0538732cd8a51c309d663baccbd919462aff4a2"
HISTORICAL_EVALUATOR_REF = "m6/stage_b_evaluator.py"
HISTORICAL_EVALUATOR_GIT_BLOB = "8996a683a28ef84d5e7c91db870f0e8a1aca8fe1"
HISTORICAL_RUNNER_REF = "m6/stage_b_tier1_runner.py"
HISTORICAL_RUNNER_GIT_BLOB = "89b6f59e41c000afca81036b20ecde9fd9ee2a18"
COST_RULE_REF = "evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json"
COST_RULE_GIT_BLOB = "64bc7a000e750cd29710b372c4e5587f1610668a"
CANDIDATE_BLOBS = {
    "V2-C006": ("discovery/candidates/V2-C006.json", "a5a6e4865206a0f85afcae28a65004e1e24a8277"),
    "V2-C012": ("discovery/candidates/V2-C012.json", "a9a8464d9cf161c3dcae39536280089058e882d9"),
}
AUTHORIZATION_SCHEMA = "mxm.greenfield.v2.m6-stage-b-current-config-execution-authorization.v1"


class CurrentConfigRunnerIntegrityError(ValueError):
    pass


class CurrentConfigExecutionNotAuthorized(PermissionError):
    pass


def git_blob_sha1(path: Path | str) -> str:
    data = Path(path).read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_repository_current_config_authorities(repo_root: Path | str) -> dict[str, Any]:
    root = Path(repo_root)
    immutable = {
        CURRENT_AUTHORITY_REF: CURRENT_AUTHORITY_GIT_BLOB,
        CURRENT_POLICY_REF: CURRENT_POLICY_GIT_BLOB,
        CURRENT_EVALUATOR_REF: CURRENT_EVALUATOR_GIT_BLOB,
        HISTORICAL_AUTHORITY_REF: HISTORICAL_AUTHORITY_GIT_BLOB,
        HISTORICAL_POLICY_REF: HISTORICAL_POLICY_GIT_BLOB,
        HISTORICAL_EVALUATOR_REF: HISTORICAL_EVALUATOR_GIT_BLOB,
        HISTORICAL_RUNNER_REF: HISTORICAL_RUNNER_GIT_BLOB,
        COST_RULE_REF: COST_RULE_GIT_BLOB,
    }
    for rel, expected in immutable.items():
        actual = git_blob_sha1(root / rel)
        if actual != expected:
            raise CurrentConfigRunnerIntegrityError(f"authority/runtime drift: {rel}")
    for cid, (rel, expected) in CANDIDATE_BLOBS.items():
        if git_blob_sha1(root / rel) != expected:
            raise CurrentConfigRunnerIntegrityError(f"candidate blob drift: {cid}")
        candidate = _load_json(root / rel)
        if candidate.get("spec_hash") != CANDIDATE_SPEC_HASHES[cid]:
            raise CurrentConfigRunnerIntegrityError(f"candidate spec hash drift: {cid}")

    authority = _load_json(root / CURRENT_AUTHORITY_REF)
    validate_current_configuration_authority(authority)

    policy = _load_json(root / CURRENT_POLICY_REF)
    if policy.get("status") != "FROZEN_POST_STAGE_A_PRE_CURRENT_CONFIG_STAGE_B_OUTCOME":
        raise CurrentConfigRunnerIntegrityError("current-config policy status drift")
    if policy.get("current_configuration_authority", {}).get("git_blob_sha1") != CURRENT_AUTHORITY_GIT_BLOB:
        raise CurrentConfigRunnerIntegrityError("policy authority binding drift")
    if policy.get("evaluator", {}).get("git_blob_sha1") != CURRENT_EVALUATOR_GIT_BLOB:
        raise CurrentConfigRunnerIntegrityError("policy evaluator binding drift")
    if policy.get("margin_law", {}).get("state") != CURRENT_CONFIG_AUTHORITY_STATUS:
        raise CurrentConfigRunnerIntegrityError("policy current margin law drift")
    if policy.get("margin_law", {}).get("historical_invariance_claimed") is not False:
        raise CurrentConfigRunnerIntegrityError("historical invariance must not be claimed")

    historical = _load_json(root / HISTORICAL_AUTHORITY_REF)
    if historical.get("status") != "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND":
        raise CurrentConfigRunnerIntegrityError("historical unresolved authority changed")

    state = _load_json(root / "CURRENT_STATE.json")
    track = state.get("m6", {}).get("stage_b_current_configuration", {})
    allowed_pre_execution_states = {
        "PREPARED_NOT_RUN_AWAITING_INDEPENDENT_AUDIT": False,
        "AUDITED_PENDING_SINGLE_USE_AUTHORIZATION": False,
        "AUTHORIZED_NOT_RUN": True,
    }
    state_name = track.get("state")
    if state_name not in allowed_pre_execution_states:
        raise CurrentConfigRunnerIntegrityError("current-config track state drift")
    if track.get("execution_authorized") is not allowed_pre_execution_states[state_name]:
        raise CurrentConfigRunnerIntegrityError("current-config authorization/state mismatch")
    if track.get("economics_run") is not False:
        raise CurrentConfigRunnerIntegrityError("current-config economics must remain unopened")
    if track.get("stage_b_current_config_outcomes_opened") != 0:
        raise CurrentConfigRunnerIntegrityError("unexpected current-config outcome")
    if state.get("economic_outcomes_opened") != 2 or state.get("v2_attempts_used") != 2:
        raise CurrentConfigRunnerIntegrityError("attempt/outcome accounting drift")
    if state.get("v2_evaluated_identities") != 2 or state.get("v2_search_budget_remaining") != 82:
        raise CurrentConfigRunnerIntegrityError("search accounting drift")
    if state.get("protected_evidence_opened") is not False:
        raise CurrentConfigRunnerIntegrityError("protected evidence must remain unopened")

    return {
        "authority_status": authority["status"],
        "policy_status": policy["status"],
        "historical_margin_state": historical["status"],
        "current_config_outcomes_opened": 0,
    }


def validate_execution_authorization(authorization: Mapping[str, Any]) -> None:
    if authorization.get("schema") != AUTHORIZATION_SCHEMA:
        raise CurrentConfigExecutionNotAuthorized("invalid current-config authorization schema")
    if authorization.get("status") != "AUTHORIZED":
        raise CurrentConfigExecutionNotAuthorized("authorization is not active")
    if authorization.get("execution_authorized") is not True:
        raise CurrentConfigExecutionNotAuthorized("execution_authorized must be true")
    if authorization.get("single_use") is not True or authorization.get("consumed") is not False:
        raise CurrentConfigExecutionNotAuthorized("single-use authorization unavailable")
    if authorization.get("independent_audit_pass") is not True:
        raise CurrentConfigExecutionNotAuthorized("independent audit must pass before activation")
    if authorization.get("candidate_spec_hashes") != CANDIDATE_SPEC_HASHES:
        raise CurrentConfigExecutionNotAuthorized("authorization candidate binding mismatch")
    if authorization.get("current_authority_git_blob_sha1") != CURRENT_AUTHORITY_GIT_BLOB:
        raise CurrentConfigExecutionNotAuthorized("authorization authority binding mismatch")
    if authorization.get("current_policy_git_blob_sha1") != CURRENT_POLICY_GIT_BLOB:
        raise CurrentConfigExecutionNotAuthorized("authorization policy binding mismatch")
    if authorization.get("protected_evidence_opened") is not False:
        raise CurrentConfigExecutionNotAuthorized("protected evidence must remain unopened")
    if authorization.get("current_config_stage_b_outcomes_before_authorization") != 0:
        raise CurrentConfigExecutionNotAuthorized("authorization must precede scenario outcomes")


def execute_current_config_scenario_in_memory(
    candidates: Sequence[Any],
    *,
    authorization: Mapping[str, Any],
    current_margin_authority: Mapping[str, Any],
):
    validate_execution_authorization(authorization)
    validate_current_configuration_authority(current_margin_authority)
    return tuple(
        realize_current_configuration_capital(
            candidate,
            current_margin_authority=current_margin_authority,
        )
        for candidate in candidates
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--validate-repository-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.validate_repository_only:
        raise CurrentConfigExecutionNotAuthorized(
            "economic execution is blocked pending independent audit and separate authorization activation"
        )
    result = verify_repository_current_config_authorities(args.repo_root)
    print("M6_STAGE_B_CURRENT_CONFIG_PREPARED_NOT_RUN")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
