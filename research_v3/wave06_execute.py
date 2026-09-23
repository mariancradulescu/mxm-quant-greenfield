"""Exact-head execution gate for prospectively frozen Performance Research V3 Wave06 C031."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from m7.competition_performance_v3_wave06_c031_evaluator import execute_wave

AUTH_REF="research_v3/WAVE_06_EXECUTION_AUTHORIZATION_V1.json"
CANDIDATE_IDS=("V2-C031",)
SPEC_HASHES={"V2-C031":"4a57910026bc8df63446fa8024ac86a18ce8a732039a9388f704a50bbccfc4e1"}
EVALUATOR_REF="m7/competition_performance_v3_wave06_c031_evaluator.py"
EVALUATOR_SHA256="90bfa75c44ba6d281b2e84e5aa81b0fddeadcf3b7b5f4ec19bcd70c311ca0344"
EVALUATOR_GIT_BLOB_SHA1="ed1a8f67b65f52018f0d067ed9afc9e7d10f4081"

class V3Wave06ExecutionNotAuthorized(RuntimeError):
    pass

def git_blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _authorize(root,execution_head,execution_ci_run_id):
    root=Path(root); path=root/AUTH_REF
    if not path.is_file():
        raise V3Wave06ExecutionNotAuthorized("Wave06 authorization not yet persisted")
    auth=json.loads(path.read_text(encoding="utf-8"))
    checks=(
        auth.get("status")=="AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
        tuple(auth.get("candidate_ids",[]))==CANDIDATE_IDS,
        auth.get("candidate_spec_hashes")==SPEC_HASHES,
        auth.get("execution_gate_head")==execution_head,
        auth.get("execution_gate_ci_run_id")==int(execution_ci_run_id),
        auth.get("execution_gate_ci_conclusion")=="SUCCESS",
        auth.get("evaluator_ref")==EVALUATOR_REF,
        auth.get("evaluator_sha256")==EVALUATOR_SHA256,
        auth.get("evaluator_git_blob_sha1")==EVALUATOR_GIT_BLOB_SHA1,
        sha256_file(root/EVALUATOR_REF)==EVALUATOR_SHA256,
        git_blob_sha1(root/EVALUATOR_REF)==EVALUATOR_GIT_BLOB_SHA1,
        auth.get("wrapper_git_blob_sha1")==git_blob_sha1(Path(__file__)),
        auth.get("candidate_own_outcomes_opened") is False,
        auth.get("protected_evidence_opened") is False,
        auth.get("live_orders") is False,
        auth.get("competition_start") is False,
    )
    if not all(checks):
        raise V3Wave06ExecutionNotAuthorized("V3 Wave06 exact-head authorization mismatch")
    return auth

def execute_authorized(root,capture_zip,*,execution_head,execution_ci_run_id):
    _authorize(root,execution_head,execution_ci_run_id)
    return execute_wave(root,capture_zip)
