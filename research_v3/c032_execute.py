"""Exact-head execution gate for prospectively frozen V2-C032 independent NETH25 breakout-fade outer."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from m7.competition_performance_v3_c032_evaluator import evaluate

AUTH_REF="research_v3/C032_EXECUTION_AUTHORIZATION_V1.json"
CID="V2-C032"
SPEC_HASH="96a752ab7c91401f569527b0a21c7757e4418002cc918e0663589e6ae4044936"
EVALUATOR_REF="m7/competition_performance_v3_c032_evaluator.py"
EVALUATOR_SHA256="88034ea95dc05d6bbcd7aca95cc94b8d94ffaaf9871a0885d8299a8ac6a08cc7"
EVALUATOR_GIT_BLOB_SHA1="16c72a92c71707ddbf5efae367278705c68cfa51"

class C032ExecutionNotAuthorized(RuntimeError): pass

def git_blob_sha1(path):
    data=Path(path).read_bytes(); return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()
def sha256_file(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _authorize(root,execution_head,execution_ci_run_id):
    root=Path(root); p=root/AUTH_REF
    if not p.is_file(): raise C032ExecutionNotAuthorized("C032 authorization not yet persisted")
    a=json.loads(p.read_text())
    checks=(
        a.get("status")=="AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
        a.get("candidate_id")==CID,
        a.get("candidate_spec_hash")==SPEC_HASH,
        a.get("execution_gate_head")==execution_head,
        a.get("execution_gate_ci_run_id")==int(execution_ci_run_id),
        a.get("execution_gate_ci_conclusion")=="SUCCESS",
        a.get("evaluator_ref")==EVALUATOR_REF,
        a.get("evaluator_sha256")==EVALUATOR_SHA256,
        a.get("evaluator_git_blob_sha1")==EVALUATOR_GIT_BLOB_SHA1,
        sha256_file(root/EVALUATOR_REF)==EVALUATOR_SHA256,
        git_blob_sha1(root/EVALUATOR_REF)==EVALUATOR_GIT_BLOB_SHA1,
        a.get("wrapper_git_blob_sha1")==git_blob_sha1(Path(__file__)),
        a.get("candidate_own_outcome_opened") is False,
        a.get("protected_evidence_opened") is False,
        a.get("live_orders") is False,
        a.get("competition_start") is False,
    )
    if not all(checks): raise C032ExecutionNotAuthorized("C032 exact-head authorization mismatch")
    return a

def execute_authorized(root,capture_zip,*,execution_head,execution_ci_run_id):
    _authorize(root,execution_head,execution_ci_run_id)
    return evaluate(root,capture_zip)
