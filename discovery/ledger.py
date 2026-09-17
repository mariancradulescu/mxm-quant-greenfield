"""Append-only Discovery lifecycle ledger with deterministic active-hash enforcement."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from .canonical import canonical_json, compute_result_hash
from .schema import validate_result

ALLOWED_ENTRY_TYPES = {
    "CANDIDATE_FROZEN", "CANDIDATE_REFROZEN_PRE_OUTCOME", "RESULT_RECORDED",
    "IMPLEMENTATION_CORRECTION",
}

def _entry_hash(entry_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(entry_without_hash).encode("utf-8")).hexdigest()

def read_ledger(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    entries=[]; previous_hash: Optional[str]=None
    with path.open("r",encoding="utf-8") as handle:
        for line_number,raw in enumerate(handle,start=1):
            if not raw.strip(): raise ValueError(f"blank ledger line at {line_number}")
            entry=json.loads(raw)
            if entry.get("sequence") != len(entries)+1: raise ValueError(f"non-contiguous ledger sequence at line {line_number}")
            if entry.get("previous_entry_hash") != previous_hash: raise ValueError(f"broken previous_entry_hash at line {line_number}")
            actual=entry.get("entry_hash"); base={k:v for k,v in entry.items() if k!="entry_hash"}
            if actual != _entry_hash(base): raise ValueError(f"entry_hash mismatch at line {line_number}")
            entries.append(entry); previous_hash=actual
    return entries

def result_count(entries: list[dict]) -> int:
    return sum(e.get("entry_type")=="RESULT_RECORDED" for e in entries)

def derive_active_spec_hashes(entries: list[dict]) -> dict[str,str]:
    active: dict[str,str] = {}
    any_result=False
    for e in entries:
        et=e.get("entry_type"); cid=e.get("candidate_id"); sh=e.get("spec_hash"); payload=e.get("payload") or {}
        if et=="CANDIDATE_FROZEN":
            if cid in active: raise ValueError(f"candidate already frozen: {cid}")
            active[cid]=sh
        elif et=="CANDIDATE_REFROZEN_PRE_OUTCOME":
            if any_result: raise ValueError("CANDIDATE_REFROZEN_PRE_OUTCOME exists after a V2 economic result")
            if cid not in active: raise ValueError(f"refreeze for unfrozen candidate: {cid}")
            if payload.get("old_spec_hash") != active[cid]: raise ValueError(f"refreeze old_spec_hash mismatch for {cid}")
            if payload.get("new_spec_hash") != sh: raise ValueError(f"refreeze new_spec_hash mismatch for {cid}")
            if payload.get("outcome_seen") is not False or payload.get("attempt_consumed") is not False:
                raise ValueError("pre-outcome refreeze must explicitly preserve zero outcome/attempt")
            active[cid]=sh
        elif et=="RESULT_RECORDED":
            if cid not in active: raise ValueError(f"result for unfrozen candidate: {cid}")
            if sh != active[cid]: raise ValueError(f"result spec_hash is stale/non-active for {cid}")
            any_result=True
        elif et=="IMPLEMENTATION_CORRECTION":
            if cid not in active: raise ValueError(f"implementation correction for unfrozen candidate: {cid}")
            if sh != active[cid]: raise ValueError("implementation correction may not silently change economic identity")
    return active

def validate_lifecycle_append(entries: list[dict], *, entry_type: str, candidate_id: str, spec_hash: str, payload: Mapping[str,Any]) -> None:
    if entry_type not in ALLOWED_ENTRY_TYPES: raise ValueError(f"unsupported ledger entry_type: {entry_type}")
    active=derive_active_spec_hashes(entries)
    if entry_type=="CANDIDATE_FROZEN":
        if candidate_id in active: raise ValueError(f"candidate already frozen: {candidate_id}")
    elif entry_type=="CANDIDATE_REFROZEN_PRE_OUTCOME":
        if result_count(entries): raise ValueError("pre-outcome refreeze forbidden after any V2 economic result exists")
        if candidate_id not in active: raise ValueError("cannot refreeze an unfrozen candidate")
        if payload.get("old_spec_hash") != active[candidate_id]: raise ValueError("old_spec_hash is not current active hash")
        if payload.get("new_spec_hash") != spec_hash: raise ValueError("new_spec_hash must equal ledger spec_hash")
        if payload.get("outcome_seen") is not False or payload.get("attempt_consumed") is not False:
            raise ValueError("pre-outcome refreeze requires outcome_seen=false and attempt_consumed=false")
    elif entry_type=="RESULT_RECORDED":
        if candidate_id not in active: raise ValueError("RESULT_RECORDED requires authoritative frozen candidate")
        if active[candidate_id] != spec_hash: raise ValueError("RESULT_RECORDED spec_hash must equal current active frozen hash")
        result=payload.get("result")
        if not isinstance(result,Mapping): raise ValueError("RESULT_RECORDED requires payload.result full authoritative result")
        validate_result(result)
        if result["candidate_id"] != candidate_id or result["spec_hash"] != spec_hash:
            raise ValueError("RESULT_RECORDED result identity does not match ledger identity")
        if payload.get("result_hash") != compute_result_hash(result):
            raise ValueError("RESULT_RECORDED result_hash mismatch")
    elif entry_type=="IMPLEMENTATION_CORRECTION":
        if candidate_id not in active or active[candidate_id] != spec_hash:
            raise ValueError("implementation correction must bind current active economic identity")

def append_entry(path, *, entry_type: str, candidate_id: str, spec_hash: str,
                 payload: Mapping[str,Any], timestamp_utc: Optional[str]=None) -> dict:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); entries=read_ledger(path)
    validate_lifecycle_append(entries,entry_type=entry_type,candidate_id=candidate_id,spec_hash=spec_hash,payload=payload)
    sequence=len(entries)+1; previous_hash=entries[-1]["entry_hash"] if entries else None
    timestamp=timestamp_utc or datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    base={"sequence":sequence,"timestamp_utc":timestamp,"entry_type":entry_type,
          "candidate_id":candidate_id,"spec_hash":spec_hash,"previous_entry_hash":previous_hash,"payload":dict(payload)}
    entry=dict(base); entry["entry_hash"]=_entry_hash(base)
    with path.open("a",encoding="utf-8") as handle:
        handle.write(canonical_json(entry)+"\n"); handle.flush(); os.fsync(handle.fileno())
    return entry
