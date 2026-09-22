"""C012 same-identity implementation-correction Stage-A runner.

Correction-only path for the already-frozen V2-C012 identity. It reuses the original
immutable DEVELOPMENT data, calendar, transaction-local cost method, conversion semantics,
Stage-A economic unit, and evaluator. It never economically evaluates V2-C006.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from discovery.schema import validate_result
from .causal_conversion import CausalConversionSeries
from .session_replay import NasdaqCashCalendar
from .stage_a_evaluator import EVALUATOR_RUNTIME_SHA256, evaluate_prepared_candidate
from .stage_a_tier1_runner import (
    C012_KNOWN_UNSUPPORTED_BOUNDARIES_MS,
    PreparedCandidate,
    StageAExecutionNotAuthorized,
    StageARunnerIntegrityError,
    _csv_rows,
    _git_blob_sha_bytes,
    _intent_record,
    _prepare_candidate,
    _sha256_json,
    verify_repository_authorities,
)
from .tier1_candidate_replay import C012_HASH, c012_replay_intents
from .transaction_local_cost import load_c012_transaction_local_index, sha256_file

PRE_ECONOMIC_AUTHORITY_REF = "evidence/C012_SAME_IDENTITY_CORRECTED_STAGE_A_PRE_ECONOMIC_MATERIALIZATION_V1.json"
DOWNSTREAM_INVALIDATION_REF = "evidence/C012_STAGE_B_DOWNSTREAM_INVALIDATION_V1.json"
EXPECTED_CORRECTED_INTENT_COUNT = 34
EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256 = "645e1d89a5a61c6f757fc4ac1e7f5a7729d847efab9e207c6a02da72e4d9995a"
EXPECTED_CORRECTED_TRANSACTION_CONTEXTS = 68
EXPECTED_REPLAY_GIT_BLOB_SHA1 = "b4cc3f2b56bb586edefe5c8821225225e79f27ca"
CORRECTED_EXTERNAL_INPUT_SHA256 = {
    "us500_m15": "e62aff5634ee2c3b9f3cbea3766a68d7a4a68b64ec9727aaa8cc757e2834fe87",
    "nas100_m15": "f92330927b0f41c3f6502951dbe512aa11449184916634c80e8f67f3c217eb7c",
    "eurusd_m15": "bce32af6ef251115d0628d746af16849a7ac23d7185a716670b0b22a4f09adde",
    "nas100_c012_transaction_local_cost": "dd4f6be917773fc580d4725d7c30ef4aabd5ec4ce19a30fdced8c5a85f4bd999",
}

@dataclass(frozen=True)
class C012CorrectionInputPaths:
    us500_m15: Path
    nas100_m15: Path
    eurusd_m15: Path
    nas100_c012_transaction_local_cost: Path

def verify_c012_correction_external_inputs(paths: C012CorrectionInputPaths) -> None:
    for field, expected in CORRECTED_EXTERNAL_INPUT_SHA256.items():
        path = Path(getattr(paths, field))
        if not path.is_file():
            raise StageARunnerIntegrityError(f"missing corrected C012 input: {field} -> {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise StageARunnerIntegrityError(f"corrected C012 input sha256 mismatch {field}: expected {expected}, got {actual}")

def build_corrected_c012_pre_economic_candidate(repo_root: Path | str, paths: C012CorrectionInputPaths) -> PreparedCandidate:
    root = Path(repo_root)
    verify_repository_authorities(root)
    verify_c012_correction_external_inputs(paths)
    correction = json.loads((root / "evidence/C012_SAME_IDENTITY_IMPLEMENTATION_CORRECTION_V1.json").read_text(encoding="utf-8"))
    if (
        correction.get("candidate_id") != "V2-C012"
        or correction.get("candidate_spec_hash") != C012_HASH
        or correction.get("corrected_replay_git_blob_sha1") != EXPECTED_REPLAY_GIT_BLOB_SHA1
        or correction.get("same_identity") is not True
        or correction.get("semantic_change") is not False
        or correction.get("new_v2_attempt_consumed") is not False
    ):
        raise StageARunnerIntegrityError("invalid C012 same-identity correction authority")
    calendar = NasdaqCashCalendar.from_artifact(root / "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json")
    us500_rows = _csv_rows(paths.us500_m15)
    nas100_rows = _csv_rows(paths.nas100_m15)
    eurusd = CausalConversionSeries.from_rows("EURUSD", _csv_rows(paths.eurusd_m15))
    intents = c012_replay_intents(us500_rows, nas100_rows, calendar)
    cost_index = load_c012_transaction_local_index(paths.nas100_c012_transaction_local_cost)
    return _prepare_candidate("V2-C012", intents, cost_index=cost_index, eurusd=eurusd)

def verify_corrected_c012_pre_economic_candidate(candidate: PreparedCandidate) -> dict[str, Any]:
    if candidate.candidate_id != "V2-C012" or candidate.spec_hash != C012_HASH:
        raise StageARunnerIntegrityError("corrected C012 candidate identity/spec mismatch")
    if candidate.cost_state != "CONSERVATIVE_BOUND":
        raise StageARunnerIntegrityError("corrected C012 transaction cost context unresolved")
    records = [_intent_record(x.intent) for x in candidate.trades]
    count = len(records)
    digest = _sha256_json(records)
    if count != EXPECTED_CORRECTED_INTENT_COUNT:
        raise StageARunnerIntegrityError(f"corrected C012 intent count mismatch {count}")
    if digest != EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256:
        raise StageARunnerIntegrityError("corrected C012 intent manifest mismatch")
    contexts = 0
    for prepared in candidate.trades:
        for evidence, stamp in ((prepared.entry_cost_evidence, prepared.intent.entry_utc),(prepared.exit_cost_evidence, prepared.intent.exit_utc)):
            expected_ms = int(stamp.timestamp() * 1000)
            if evidence.boundary_timestamp_ms != expected_ms or not evidence.supported:
                raise StageARunnerIntegrityError("corrected C012 cost evidence mismatch")
            if evidence.boundary_timestamp_ms in C012_KNOWN_UNSUPPORTED_BOUNDARIES_MS:
                raise StageARunnerIntegrityError("corrected C012 selected known fail-closed boundary")
            contexts += 1
    if contexts != EXPECTED_CORRECTED_TRANSACTION_CONTEXTS:
        raise StageARunnerIntegrityError("corrected C012 transaction context count mismatch")
    return {"candidate_id":"V2-C012","intent_count":count,"intent_manifest_sha256":digest,"transaction_context_count":contexts,"unresolved_transaction_context_count":0,"economics_computed":False}

def _load_correction_authorization(repo_root: Path, authorization_path: Path | str | None, *, execution_head: str, execution_ci_run_id: int) -> Mapping[str, Any]:
    if authorization_path is None:
        raise StageAExecutionNotAuthorized("corrected C012 economics require explicit correction authorization")
    auth = json.loads(Path(authorization_path).read_text(encoding="utf-8"))
    checks = (
        auth.get("schema") == "mxm.greenfield.v2.c012-same-identity-stage-a-rerun-authorization.v1",
        auth.get("status") == "AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
        auth.get("candidate_id") == "V2-C012",
        auth.get("candidate_spec_hash") == C012_HASH,
        auth.get("corrected_intent_count") == EXPECTED_CORRECTED_INTENT_COUNT,
        auth.get("corrected_intent_manifest_sha256") == EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
        auth.get("corrected_replay_git_blob_sha1") == EXPECTED_REPLAY_GIT_BLOB_SHA1,
        auth.get("pre_economic_materialization_ref") == PRE_ECONOMIC_AUTHORITY_REF,
        auth.get("downstream_invalidation_ref") == DOWNSTREAM_INVALIDATION_REF,
        auth.get("evaluator_runtime_sha256") == EVALUATOR_RUNTIME_SHA256,
        auth.get("runner_git_blob_sha1") == _git_blob_sha_bytes(Path(__file__).read_bytes()),
        auth.get("execution_gate_head") == execution_head,
        auth.get("execution_gate_ci_run_id") == int(execution_ci_run_id),
        auth.get("same_identity") is True,
        auth.get("semantic_change") is False,
        auth.get("new_v2_attempt_consumed") is False,
        auth.get("search_budget_decrement") == 0,
        auth.get("protected_evidence_opened") is False,
    )
    if not all(checks):
        raise StageAExecutionNotAuthorized("corrected C012 authorization binding mismatch")
    material = json.loads((repo_root / PRE_ECONOMIC_AUTHORITY_REF).read_text(encoding="utf-8"))
    if material.get("status") != "PASS_CORRECTED_SAME_IDENTITY_PRE_ECONOMIC_NO_PNL":
        raise StageAExecutionNotAuthorized("corrected C012 pre-economic materialization not active")
    return auth

def execute_corrected_c012_stage_a_in_memory(repo_root: Path | str, paths: C012CorrectionInputPaths, *, authorization_path: Path | str | None, execution_head: str, execution_ci_run_id: int) -> dict[str, Any]:
    root = Path(repo_root)
    _load_correction_authorization(root, authorization_path, execution_head=execution_head, execution_ci_run_id=execution_ci_run_id)
    candidate = build_corrected_c012_pre_economic_candidate(root, paths)
    verify_corrected_c012_pre_economic_candidate(candidate)
    calendar = NasdaqCashCalendar.from_artifact(root / "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json")
    result = evaluate_prepared_candidate(candidate, calendar=calendar, evaluator_sha256=EVALUATOR_RUNTIME_SHA256)
    validate_result(result)
    return result
