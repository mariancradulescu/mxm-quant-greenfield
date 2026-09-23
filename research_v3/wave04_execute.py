"""Exact-head execution gate for prospectively frozen Performance Research V3 Wave04 C027-C028."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from m7.competition_performance_v3_wave04_c027_c028_evaluator import execute_wave

AUTH_REF = "research_v3/WAVE_04_EXECUTION_AUTHORIZATION_V1.json"
CANDIDATE_IDS = ("V2-C027", "V2-C028")
SPEC_HASHES = {"V2-C027":"6c2945d22af7d10156786a823dca7df21afbbb2c96fa92e060e70e58857de8e2","V2-C028":"f0a0b7c78010232bda8035bb2ab4215e1f37624a17e8eb094e2515daeb2f6e5c"}
EVALUATOR_REF = "m7/competition_performance_v3_wave04_c027_c028_evaluator.py"
EVALUATOR_SHA256 = "3df4629a7bf2aaa6b9008df364f05b134f2c2b1c2fe68f1022932f5dbf786789"
EVALUATOR_GIT_BLOB_SHA1 = "a298083ed479c767e9b522dce027c02d7ee70ff1"

class V3Wave04ExecutionNotAuthorized(RuntimeError):
    pass

def git_blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def sha256_file(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _authorize(root,execution_head,execution_ci_run_id):
    root=Path(root); auth=json.loads((root/AUTH_REF).read_text(encoding="utf-8"))
    checks=(
      auth.get("status")=="AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
      tuple(auth.get("candidate_ids",[]))==CANDIDATE_IDS,
      auth.get("candidate_spec_hashes")==SPEC_HASHES,
      auth.get("execution_gate_head")==execution_head,
      auth.get("execution_gate_ci_run_id")==int(execution_ci_run_id),
      auth.get("execution_gate_ci_conclusion")=="SUCCESS",
      auth.get("evaluator_ref")==EVALUATOR_REF, auth.get("evaluator_sha256")==EVALUATOR_SHA256,
      auth.get("evaluator_git_blob_sha1")==EVALUATOR_GIT_BLOB_SHA1,
      sha256_file(root/EVALUATOR_REF)==EVALUATOR_SHA256, git_blob_sha1(root/EVALUATOR_REF)==EVALUATOR_GIT_BLOB_SHA1,
      auth.get("wrapper_git_blob_sha1")==git_blob_sha1(Path(__file__)),
      auth.get("candidate_own_outcomes_opened") is False, auth.get("protected_evidence_opened") is False,
      auth.get("live_orders") is False, auth.get("competition_start") is False,
    )
    if not all(checks): raise V3Wave04ExecutionNotAuthorized("V3 Wave04 exact-head authorization mismatch")
    return auth

def execute_authorized(root,capture_zip,*,execution_head,execution_ci_run_id):
    _authorize(root,execution_head,execution_ci_run_id)
    return execute_wave(root,capture_zip)
