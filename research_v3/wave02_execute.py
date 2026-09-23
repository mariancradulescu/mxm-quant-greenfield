"""Authorized execution gate for Performance Research V3 Wave02."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from m7.competition_performance_v3_wave02_evaluator import execute_wave
AUTH_REF="research_v3/WAVE_02_EXECUTION_AUTHORIZATION_V1.json"
CIDS=("V2-C024","V2-C025")
class V3Wave02ExecutionNotAuthorized(RuntimeError): pass
def _blob(path):
 data=Path(path).read_bytes();return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()
def _authorize(root,execution_head,execution_ci_run_id):
 root=Path(root);a=json.loads((root/AUTH_REF).read_text(encoding="utf-8"))
 checks=(a.get("status")=="AUTHORIZED_AFTER_EXACT_HEAD_GREEN",a.get("candidate_ids")==list(CIDS),a.get("execution_gate_head")==execution_head,a.get("execution_gate_ci_run_id")==int(execution_ci_run_id),a.get("execution_gate_ci_conclusion")=="SUCCESS",a.get("wrapper_git_blob_sha1")==_blob(Path(__file__)),a.get("protected_evidence_opened") is False,a.get("live_orders") is False,a.get("competition_start") is False)
 if not all(checks): raise V3Wave02ExecutionNotAuthorized("V3 Wave02 exact-head authorization mismatch")
 return a
def execute_authorized(root,capture_zip,*,execution_head,execution_ci_run_id):
 _authorize(root,execution_head,execution_ci_run_id)
 return execute_wave(root,capture_zip)
