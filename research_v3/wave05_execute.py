"""Exact-head execution gate for prospectively frozen Performance Research V3 Wave05 C029-C030."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from m7.competition_performance_v3_wave05_c029_c030_evaluator import execute_wave

AUTH_REF="research_v3/WAVE_05_EXECUTION_AUTHORIZATION_V1.json"
CANDIDATE_IDS=("V2-C029","V2-C030")
SPEC_HASHES={"V2-C029":"fec1489eb0ae538497b7b70ef1c0ff6b47233fda24cce46a290922b4e713ce61","V2-C030":"1e6d96b8338867d38ef600acba6c218cee2ed020941e5e3a2695408eeb6c4a27"}
EVALUATOR_REF="m7/competition_performance_v3_wave05_c029_c030_evaluator.py"
EVALUATOR_SHA256="cb465b5950b47edbc6d1b734d7b38b45904f84cb5affae17b3bba9a16d022c04"
EVALUATOR_GIT_BLOB_SHA1="d0917e74f89fbd36880f11a06f864b63558bf5b5"

class V3Wave05ExecutionNotAuthorized(RuntimeError): pass

def git_blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _authorize(root,execution_head,execution_ci_run_id):
    root=Path(root); path=root/AUTH_REF
    if not path.is_file():
        raise V3Wave05ExecutionNotAuthorized("Wave05 authorization not yet persisted")
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
        raise V3Wave05ExecutionNotAuthorized("V3 Wave05 exact-head authorization mismatch")
    return auth

def execute_authorized(root,capture_zip,*,execution_head,execution_ci_run_id):
    _authorize(root,execution_head,execution_ci_run_id)
    return execute_wave(root,capture_zip)
