"""Authorized V3 Wave01 economic entry point. Authorization is checked before input reads/economics."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from m7.competition_expansion_index_m15 import execute_wave

AUTH_REF="research_v3/WAVE_01_EXECUTION_AUTHORIZATION_V1.json"
CIDS=("V2-C013","V2-C014","V2-C015","V2-C016")

class V3ExecutionNotAuthorized(RuntimeError):
    pass

def _blob(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def _authorize(root, execution_head, execution_ci_run_id):
    root=Path(root)
    auth=json.loads((root/AUTH_REF).read_text(encoding="utf-8"))
    if auth.get("status")!="AUTHORIZED_AFTER_EXACT_HEAD_GREEN": raise V3ExecutionNotAuthorized("V3 Wave01 exact-head authorization missing")
    if auth.get("candidate_ids")!=list(CIDS): raise V3ExecutionNotAuthorized("V3 Wave01 candidate set drift")
    if auth.get("execution_gate_head")!=execution_head or auth.get("execution_gate_ci_run_id")!=int(execution_ci_run_id): raise V3ExecutionNotAuthorized("V3 Wave01 exact-head gate mismatch")
    if auth.get("execution_gate_ci_conclusion")!="SUCCESS": raise V3ExecutionNotAuthorized("V3 Wave01 gate is not GREEN")
    expected=auth.get("wrapper_git_blob_sha1")
    if not expected or _blob(Path(__file__))!=expected: raise V3ExecutionNotAuthorized("V3 Wave01 wrapper binding mismatch")
    if auth.get("protected_evidence_opened") is not False: raise V3ExecutionNotAuthorized("protected evidence invariant drift")
    return auth

def execute_authorized(root, *, us500_m15, nas100_m15, eurusd_m15, us500_cost, nas100_cost, execution_head, execution_ci_run_id):
    _authorize(root,execution_head,execution_ci_run_id)
    return execute_wave(root,us500_m15=us500_m15,nas100_m15=nas100_m15,eurusd_m15=eurusd_m15,us500_cost=us500_cost,nas100_cost=nas100_cost)
