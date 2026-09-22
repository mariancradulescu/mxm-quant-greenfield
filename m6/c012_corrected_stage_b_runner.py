"""Correction-only Stage-B CURRENT-configuration realization for corrected V2-C012.

This module does not create a new V2 identity and does not change any economic rule.
It reuses the corrected same-identity 34-intent C012 stream, the frozen Stage-B EUR200
capital law, the verified CURRENT Pepperstone margin authority, frozen reporting, and
transaction-local costs. Historical Stage-B V1 remains preserved but non-authoritative.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from discovery.canonical import compute_result_hash
from discovery.schema import validate_result

from .c012_corrected_stage_a_runner import (
    C012CorrectionInputPaths,
    EXPECTED_CORRECTED_INTENT_COUNT,
    EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
    build_corrected_c012_pre_economic_candidate,
    verify_corrected_c012_pre_economic_candidate,
)
from .stage_b_current_config_evaluator import (
    realize_current_configuration_capital,
    validate_current_configuration_authority,
)
from .stage_b_current_config_execute import (
    RESULT_SCHEMA,
    _augment_economic_detail,
    _canonical_bytes,
    _sha256_without_result_hash,
)
from .stage_b_current_config_reporting import (
    RESULT_LABEL,
    summarize_current_config_realization,
)
from .stage_b_current_config_tier1_runner import (
    COST_RULE_GIT_BLOB,
    COST_RULE_REF,
    CURRENT_AUTHORITY_GIT_BLOB,
    CURRENT_AUTHORITY_REF,
    CURRENT_EVALUATOR_GIT_BLOB,
    CURRENT_EVALUATOR_REF,
    CURRENT_POLICY_GIT_BLOB,
    CURRENT_POLICY_REF,
    HISTORICAL_AUTHORITY_GIT_BLOB,
    HISTORICAL_AUTHORITY_REF,
    CurrentConfigExecutionNotAuthorized,
    CurrentConfigRunnerIntegrityError,
    git_blob_sha1,
)

AUTHORIZATION_SCHEMA = "mxm.greenfield.v2.c012-corrected-stage-b-current-config-authorization.v1"
AUTHORIZATION_REF = "data/C012_CORRECTED_STAGE_B_CURRENT_CONFIG_AUTHORIZATION_V1.json"
RUNNER_REF = "m6/c012_corrected_stage_b_runner.py"
REPORTING_POLICY_REF = "data/M6_STAGE_B_CURRENT_CONFIG_REPORTING_POLICY_V1.json"
REPORTING_POLICY_GIT_BLOB = "e0419b33a7d3dfc5b6ee94b0038093fefcf9c599"
REPORTING_MODULE_REF = "m6/stage_b_current_config_reporting.py"
REPORTING_MODULE_GIT_BLOB = "49851e3ce8d82a3d7661639d76625987b6815638"
CORRECTED_STAGE_A_REF = "discovery/results/V2-C012_STAGE_A_V2.json"
CORRECTED_STAGE_A_RESULT_HASH = "01a0a9b7d44f0ed22d628538d243e3f8118233cdfb3383016490b4aa5240c503"
DOWNSTREAM_INVALIDATION_REF = "evidence/C012_STAGE_B_DOWNSTREAM_INVALIDATION_V1.json"
DOWNSTREAM_INVALIDATION_GIT_BLOB = "640ff59da35e2182c71eb037c5c4e9e30d76940a"
HISTORICAL_STAGE_B_REF = "m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V1.json"
HISTORICAL_STAGE_B_GIT_BLOB = "8c3b1fcdad6b43fcfed2af0919f3ddffd3b541f7"
HISTORICAL_STAGE_B_RESULT_SHA256 = "51edfcc76693425a07c24962f7b3c060fa2e7bb127385233f28f4fc1233edcaa"
CORRECTED_STAGE_B_REF = "m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V2.json"
C012_SPEC_HASH = "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845"
C012_CANDIDATE_REF = "discovery/candidates/V2-C012.json"
C012_CANDIDATE_GIT_BLOB = "a9a8464d9cf161c3dcae39536280089058e882d9"


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_corrected_c012_stage_b_pre_economic(repo_root: Path | str) -> dict[str, Any]:
    """Validate all frozen authorities without computing Stage-B PnL/capital."""
    root = Path(repo_root)
    immutable = {
        CURRENT_AUTHORITY_REF: CURRENT_AUTHORITY_GIT_BLOB,
        CURRENT_POLICY_REF: CURRENT_POLICY_GIT_BLOB,
        CURRENT_EVALUATOR_REF: CURRENT_EVALUATOR_GIT_BLOB,
        REPORTING_POLICY_REF: REPORTING_POLICY_GIT_BLOB,
        REPORTING_MODULE_REF: REPORTING_MODULE_GIT_BLOB,
        HISTORICAL_AUTHORITY_REF: HISTORICAL_AUTHORITY_GIT_BLOB,
        COST_RULE_REF: COST_RULE_GIT_BLOB,
        C012_CANDIDATE_REF: C012_CANDIDATE_GIT_BLOB,
        DOWNSTREAM_INVALIDATION_REF: DOWNSTREAM_INVALIDATION_GIT_BLOB,
        HISTORICAL_STAGE_B_REF: HISTORICAL_STAGE_B_GIT_BLOB,
    }
    for rel, expected in immutable.items():
        if git_blob_sha1(root / rel) != expected:
            raise CurrentConfigRunnerIntegrityError(f"corrected C012 Stage-B authority drift: {rel}")

    candidate = _load_json(root / C012_CANDIDATE_REF)
    if candidate.get("spec_hash") != C012_SPEC_HASH:
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-B candidate spec drift")

    stage_a = _load_json(root / CORRECTED_STAGE_A_REF)
    validate_result(stage_a)
    if (
        stage_a.get("candidate_id") != "V2-C012"
        or stage_a.get("spec_hash") != C012_SPEC_HASH
        or stage_a.get("stage") != "A"
        or stage_a.get("status") != "DISCOVERY_SURVIVOR"
        or stage_a.get("metrics", {}).get("event_count") != EXPECTED_CORRECTED_INTENT_COUNT
        or stage_a.get("result_hash") != CORRECTED_STAGE_A_RESULT_HASH
        or compute_result_hash(stage_a) != CORRECTED_STAGE_A_RESULT_HASH
    ):
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-A successor binding drift")

    historical_stage_b = _load_json(root / HISTORICAL_STAGE_B_REF)
    if historical_stage_b.get("result_sha256") != HISTORICAL_STAGE_B_RESULT_SHA256:
        raise CurrentConfigRunnerIntegrityError("historical C012 Stage-B V1 result hash drift")
    invalidation = _load_json(root / DOWNSTREAM_INVALIDATION_REF)
    invalidated = invalidation.get("invalidated_downstream", {})
    if (
        invalidation.get("candidate_id") != "V2-C012"
        or invalidated.get("stage_b_result_ref") != HISTORICAL_STAGE_B_REF
        or invalidated.get("stage_b_result_git_blob_sha1") != HISTORICAL_STAGE_B_GIT_BLOB
        or invalidated.get("stage_b_persisted_result_sha256") != HISTORICAL_STAGE_B_RESULT_SHA256
        or invalidation.get("historical_bytes_overwritten") is not False
        or invalidation.get("new_v2_attempt_consumed") is not False
    ):
        raise CurrentConfigRunnerIntegrityError("historical C012 Stage-B invalidation authority drift")

    authority = _load_json(root / CURRENT_AUTHORITY_REF)
    validate_current_configuration_authority(authority)

    state = _load_json(root / "CURRENT_STATE.json")
    if state.get("v2_attempts_used") != 9 or state.get("v2_search_budget_remaining") != 75:
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-B attempt/budget accounting drift")
    if state.get("protected_evidence_opened") is not False:
        raise CurrentConfigRunnerIntegrityError("protected evidence must remain closed")
    correction = state.get("c012_same_identity_corrected_rerun", {})
    if (
        correction.get("status") != "CORRECTED_STAGE_A_RECORDED_SURVIVOR"
        or correction.get("corrected_stage_a_result_hash") != CORRECTED_STAGE_A_RESULT_HASH
        or correction.get("corrected_stage_a_event_count") != EXPECTED_CORRECTED_INTENT_COUNT
        or correction.get("new_v2_attempt_consumed") is not False
        or correction.get("search_budget_decrement") != 0
    ):
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-A lifecycle state drift")
    node = state.get("current_result_authority", {}).get("V2-C012", {})
    if node.get("stage_a", {}).get("state") != "VALID_CORRECTED_SUCCESSOR":
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-A is not current authority")
    downstream = node.get("stage_b_current_config", {})
    if downstream.get("historical_result_ref") != HISTORICAL_STAGE_B_REF:
        raise CurrentConfigRunnerIntegrityError("historical Stage-B ref drift")
    if downstream.get("corrected_stage_a_successor_ref") != CORRECTED_STAGE_A_REF:
        raise CurrentConfigRunnerIntegrityError("corrected Stage-A successor ref drift")
    if downstream.get("corrected_successor_ref") not in (None, CORRECTED_STAGE_B_REF):
        raise CurrentConfigRunnerIntegrityError("unexpected corrected Stage-B successor ref")

    if (root / CORRECTED_STAGE_B_REF).exists():
        successor = _load_json(root / CORRECTED_STAGE_B_REF)
        if successor.get("candidate_id") != "V2-C012":
            raise CurrentConfigRunnerIntegrityError("corrected Stage-B successor candidate drift")

    return {
        "candidate_id": "V2-C012",
        "spec_hash": C012_SPEC_HASH,
        "corrected_stage_a_result_hash": CORRECTED_STAGE_A_RESULT_HASH,
        "corrected_intent_count": EXPECTED_CORRECTED_INTENT_COUNT,
        "corrected_intent_manifest_sha256": EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
        "historical_stage_b_result_sha256": HISTORICAL_STAGE_B_RESULT_SHA256,
        "economics_computed": False,
        "new_v2_attempt_consumed": False,
        "search_budget_decrement": 0,
    }


def _load_correction_authorization(
    repo_root: Path,
    authorization_path: Path | str | None,
    *,
    execution_head: str,
    execution_ci_run_id: int,
) -> Mapping[str, Any]:
    if authorization_path is None:
        raise CurrentConfigExecutionNotAuthorized("corrected C012 Stage-B requires explicit authorization")
    auth = _load_json(authorization_path)
    checks = (
        auth.get("schema") == AUTHORIZATION_SCHEMA,
        auth.get("status") == "AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
        auth.get("candidate_id") == "V2-C012",
        auth.get("candidate_spec_hash") == C012_SPEC_HASH,
        auth.get("corrected_stage_a_result_ref") == CORRECTED_STAGE_A_REF,
        auth.get("corrected_stage_a_result_hash") == CORRECTED_STAGE_A_RESULT_HASH,
        auth.get("corrected_intent_count") == EXPECTED_CORRECTED_INTENT_COUNT,
        auth.get("corrected_intent_manifest_sha256") == EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
        auth.get("current_authority_git_blob_sha1") == CURRENT_AUTHORITY_GIT_BLOB,
        auth.get("current_evaluator_git_blob_sha1") == CURRENT_EVALUATOR_GIT_BLOB,
        auth.get("reporting_policy_git_blob_sha1") == REPORTING_POLICY_GIT_BLOB,
        auth.get("reporting_module_git_blob_sha1") == REPORTING_MODULE_GIT_BLOB,
        auth.get("historical_stage_b_git_blob_sha1") == HISTORICAL_STAGE_B_GIT_BLOB,
        auth.get("downstream_invalidation_git_blob_sha1") == DOWNSTREAM_INVALIDATION_GIT_BLOB,
        auth.get("runner_git_blob_sha1") == git_blob_sha1(repo_root / RUNNER_REF),
        auth.get("execution_gate_head") == execution_head,
        auth.get("execution_gate_ci_run_id") == int(execution_ci_run_id),
        auth.get("same_identity") is True,
        auth.get("semantic_change") is False,
        auth.get("new_v2_attempt_consumed") is False,
        auth.get("search_budget_decrement") == 0,
        auth.get("protected_evidence_opened") is False,
    )
    if not all(checks):
        raise CurrentConfigExecutionNotAuthorized("corrected C012 Stage-B authorization binding mismatch")
    verify_corrected_c012_stage_b_pre_economic(repo_root)
    return auth


def execute_corrected_c012_stage_b_in_memory(
    repo_root: Path | str,
    paths: C012CorrectionInputPaths,
    *,
    authorization_path: Path | str | None,
    execution_head: str,
    execution_ci_run_id: int,
) -> dict[str, Any]:
    root = Path(repo_root)
    auth = _load_correction_authorization(
        root,
        authorization_path,
        execution_head=execution_head,
        execution_ci_run_id=execution_ci_run_id,
    )
    candidate = build_corrected_c012_pre_economic_candidate(root, paths)
    verify_corrected_c012_pre_economic_candidate(candidate)
    current_margin_authority = _load_json(root / CURRENT_AUTHORITY_REF)
    realization = realize_current_configuration_capital(
        candidate,
        current_margin_authority=current_margin_authority,
    )
    frozen_report = summarize_current_config_realization(realization)
    economics = _augment_economic_detail(candidate, realization)
    if frozen_report.get("label") != RESULT_LABEL:
        raise CurrentConfigRunnerIntegrityError("wrong corrected C012 Stage-B result label")
    if frozen_report["continuous_capital"]["final_equity_eur"] != economics["final_equity_eur"]:
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-B final-equity mismatch")
    if frozen_report["continuous_capital"]["maximum_drawdown_eur"] != economics["maximum_drawdown_eur"]:
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-B drawdown mismatch")

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "label": RESULT_LABEL,
        "candidate_id": "V2-C012",
        "execution_provenance": {
            "authorization_ref": AUTHORIZATION_REF,
            "authorization_revision": auth.get("revision"),
            "execution_head": execution_head,
            "execution_exact_head_ci_run_id": int(execution_ci_run_id),
            "corrected_stage_a_result_ref": CORRECTED_STAGE_A_REF,
            "corrected_stage_a_result_hash": CORRECTED_STAGE_A_RESULT_HASH,
            "corrected_intent_count": EXPECTED_CORRECTED_INTENT_COUNT,
            "corrected_intent_manifest_sha256": EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
            "current_broker_configuration_authority_ref": CURRENT_AUTHORITY_REF,
            "reporting_policy_ref": REPORTING_POLICY_REF,
            "reporting_module_ref": REPORTING_MODULE_REF,
            "historical_stage_b_result_ref": HISTORICAL_STAGE_B_REF,
            "downstream_invalidation_ref": DOWNSTREAM_INVALIDATION_REF,
            "protected_evidence_opened": False,
        },
        "scenario_boundary": {
            "current_configuration_applied_to_development": True,
            "historical_point_in_time_margin_certification": False,
            "historical_margin_state": "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
            "historical_certification_effect": "NONE",
        },
        "economic_summary": economics,
        "frozen_reporting": frozen_report,
    }
    result["result_sha256"] = _sha256_without_result_hash(result)
    return result


def persist_corrected_c012_stage_b_result(
    result: Mapping[str, Any],
    repo_root: Path | str,
) -> Path:
    root = Path(repo_root)
    if result.get("candidate_id") != "V2-C012":
        raise CurrentConfigRunnerIntegrityError("unexpected corrected Stage-B candidate")
    if result.get("result_sha256") != _sha256_without_result_hash(result):
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B result hash mismatch")
    target = root / CORRECTED_STAGE_B_REF
    if target.exists():
        existing = _load_json(target)
        if existing == dict(result):
            return target
        raise CurrentConfigRunnerIntegrityError("refusing to overwrite different corrected Stage-B successor")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_canonical_bytes(result))
    return target
