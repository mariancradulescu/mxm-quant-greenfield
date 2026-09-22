"""Deterministic, idempotent Discovery post-outcome persistence planning."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_json, compute_result_hash, verify_spec_hash
from .ledger import _entry_hash, derive_active_spec_hashes, read_ledger
from .schema import validate_result


class PersistenceError(ValueError):
    pass


def normalized_result(result: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(result)
    expected = compute_result_hash(out)
    if "result_hash" in out and out["result_hash"] != expected:
        raise PersistenceError("result_hash does not match canonical result bytes")
    out["result_hash"] = expected
    validate_result(out)
    return out


def build_post_outcome_plan(
    root: str | Path,
    *,
    result: Mapping[str, Any],
    result_relpath: str,
    timestamp_utc: str,
) -> dict[str, Any]:
    root = Path(root)
    result = normalized_result(result)
    cid = result["candidate_id"]
    spec_path = root / "discovery" / "candidates" / f"{cid}.json"
    if not spec_path.is_file():
        raise PersistenceError("candidate spec missing")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    verify_spec_hash(spec)

    entries = read_ledger(root / "discovery" / "ledger.jsonl")
    active = derive_active_spec_hashes(entries)
    if active.get(cid) != result["spec_hash"] or spec["spec_hash"] != result["spec_hash"]:
        raise PersistenceError("result is not bound to the active frozen candidate spec")

    same = [
        e for e in entries
        if e.get("entry_type") == "RESULT_RECORDED"
        and e.get("candidate_id") == cid
        and e.get("spec_hash") == result["spec_hash"]
    ]
    for e in same:
        if e.get("payload", {}).get("result_hash") == result["result_hash"]:
            return {"status": "IDEMPOTENT_ALREADY_RECORDED", "result": result}

    if same:
        last = same[-1]
        corrections = [
            e for e in entries
            if e.get("entry_type") == "IMPLEMENTATION_CORRECTION"
            and e.get("candidate_id") == cid
            and e.get("sequence", 0) > last.get("sequence", 0)
            and e.get("payload", {}).get("invalidated_result_hash") == last.get("payload", {}).get("result_hash")
            and e.get("payload", {}).get("same_identity_corrected_rerun_required") is True
            and e.get("payload", {}).get("new_v2_attempt_consumed") is False
        ]
        if not corrections:
            raise PersistenceError("different duplicate result forbidden without a proven implementation correction")

    target = root / result_relpath
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing != result:
            raise PersistenceError("target result path already exists with different content")

    sequence = len(entries) + 1
    previous_hash = entries[-1]["entry_hash"] if entries else None
    payload = {"result_hash": result["result_hash"], "result": result}
    base = {
        "sequence": sequence,
        "timestamp_utc": timestamp_utc,
        "entry_type": "RESULT_RECORDED",
        "candidate_id": cid,
        "spec_hash": result["spec_hash"],
        "previous_entry_hash": previous_hash,
        "payload": payload,
    }
    entry = dict(base)
    entry["entry_hash"] = _entry_hash(base)
    ledger_text = (root / "discovery" / "ledger.jsonl").read_text(encoding="utf-8")
    if ledger_text and not ledger_text.endswith("\n"):
        raise PersistenceError("ledger must end with newline")
    ledger_text += canonical_json(entry) + "\n"
    result_text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    return {
        "status": "READY_TO_PERSIST",
        "result": result,
        "result_relpath": result_relpath,
        "result_text": result_text,
        "ledger_text": ledger_text,
        "ledger_entry": entry,
    }


def apply_post_outcome_plan(root: str | Path, plan: Mapping[str, Any]) -> str:
    if plan.get("status") == "IDEMPOTENT_ALREADY_RECORDED":
        return "IDEMPOTENT_ALREADY_RECORDED"
    if plan.get("status") != "READY_TO_PERSIST":
        raise PersistenceError("plan is not persistable")

    root = Path(root)
    result_path = root / str(plan["result_relpath"])
    ledger_path = root / "discovery" / "ledger.jsonl"
    result_path.parent.mkdir(parents=True, exist_ok=True)

    original_result = result_path.read_bytes() if result_path.exists() else None
    original_ledger = ledger_path.read_bytes()
    with tempfile.TemporaryDirectory(dir=str(root)) as td:
        td = Path(td)
        staged_result = td / "result.json"
        staged_ledger = td / "ledger.jsonl"
        staged_result.write_text(str(plan["result_text"]), encoding="utf-8")
        staged_ledger.write_text(str(plan["ledger_text"]), encoding="utf-8")
        try:
            os.replace(staged_result, result_path)
            os.replace(staged_ledger, ledger_path)
            read_ledger(ledger_path)
        except Exception:
            if original_result is None:
                result_path.unlink(missing_ok=True)
            else:
                result_path.write_bytes(original_result)
            ledger_path.write_bytes(original_ledger)
            raise
    return "PERSISTED"
