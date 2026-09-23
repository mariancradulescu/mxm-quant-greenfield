"""Exact-head execution gate for prospectively frozen Performance Research V3 Wave03 C026."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from m7.competition_performance_v3_wave03_c026_evaluator import execute_wave

AUTH_REF = "research_v3/WAVE_03_EXECUTION_AUTHORIZATION_V1.json"
CANDIDATE_ID = "V2-C026"
SPEC_HASH = "41880f453efd363da860024e8f9b7b299bd14b9f2367156779f3f193f9abc9e9"
EVALUATOR_REF = "m7/competition_performance_v3_wave03_c026_evaluator.py"
EVALUATOR_SHA256 = "29b250904fa4b3de8e4ce0292ab38332670e624cff9a01ab649ee831fffe057f"
EVALUATOR_GIT_BLOB_SHA1 = "7c07c1d39053baa1e31ed4eb3d552520d809ccd7"


class V3Wave03ExecutionNotAuthorized(RuntimeError):
    pass


def git_blob_sha1(path):
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _authorize(root, execution_head, execution_ci_run_id):
    root = Path(root)
    auth = json.loads((root / AUTH_REF).read_text(encoding="utf-8"))
    checks = (
        auth.get("status") == "AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
        auth.get("candidate_ids") == [CANDIDATE_ID],
        auth.get("candidate_spec_hashes", {}).get(CANDIDATE_ID) == SPEC_HASH,
        auth.get("execution_gate_head") == execution_head,
        auth.get("execution_gate_ci_run_id") == int(execution_ci_run_id),
        auth.get("execution_gate_ci_conclusion") == "SUCCESS",
        auth.get("evaluator_ref") == EVALUATOR_REF,
        auth.get("evaluator_sha256") == EVALUATOR_SHA256,
        auth.get("evaluator_git_blob_sha1") == EVALUATOR_GIT_BLOB_SHA1,
        sha256_file(root / EVALUATOR_REF) == EVALUATOR_SHA256,
        git_blob_sha1(root / EVALUATOR_REF) == EVALUATOR_GIT_BLOB_SHA1,
        auth.get("wrapper_git_blob_sha1") == git_blob_sha1(Path(__file__)),
        auth.get("candidate_own_outcomes_opened") is False,
        auth.get("protected_evidence_opened") is False,
        auth.get("live_orders") is False,
        auth.get("competition_start") is False,
    )
    if not all(checks):
        raise V3Wave03ExecutionNotAuthorized("V3 Wave03 exact-head authorization mismatch")
    return auth


def execute_authorized(root, capture_zip, *, execution_head, execution_ci_run_id):
    _authorize(root, execution_head, execution_ci_run_id)
    return execute_wave(root, capture_zip)
