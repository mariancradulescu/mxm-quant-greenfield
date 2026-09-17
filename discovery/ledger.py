"""Append-only JSONL ledger with a deterministic hash chain.

The ledger records candidate lifecycle evidence. M3 does not write an economic
candidate entry to the authoritative ledger; tests exercise this module only on
temporary files.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from .canonical import canonical_json

ALLOWED_ENTRY_TYPES = {"CANDIDATE_FROZEN", "RESULT_RECORDED", "IMPLEMENTATION_CORRECTION"}


def _entry_hash(entry_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(entry_without_hash).encode("utf-8")).hexdigest()


def read_ledger(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    previous_hash: Optional[str] = None
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                raise ValueError(f"blank ledger line at {line_number}")
            entry = json.loads(raw)
            expected_sequence = len(entries) + 1
            if entry.get("sequence") != expected_sequence:
                raise ValueError(f"non-contiguous ledger sequence at line {line_number}")
            if entry.get("previous_entry_hash") != previous_hash:
                raise ValueError(f"broken previous_entry_hash at line {line_number}")
            actual_hash = entry.get("entry_hash")
            base = {k: v for k, v in entry.items() if k != "entry_hash"}
            if actual_hash != _entry_hash(base):
                raise ValueError(f"entry_hash mismatch at line {line_number}")
            entries.append(entry)
            previous_hash = actual_hash
    return entries


def append_entry(path, *, entry_type: str, candidate_id: str, spec_hash: str,
                 payload: Mapping[str, Any], timestamp_utc: Optional[str] = None) -> dict:
    if entry_type not in ALLOWED_ENTRY_TYPES:
        raise ValueError(f"unsupported ledger entry_type: {entry_type}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = read_ledger(path)
    sequence = len(entries) + 1
    previous_hash = entries[-1]["entry_hash"] if entries else None
    timestamp = timestamp_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    base = {
        "sequence": sequence, "timestamp_utc": timestamp, "entry_type": entry_type,
        "candidate_id": candidate_id, "spec_hash": spec_hash,
        "previous_entry_hash": previous_hash, "payload": dict(payload),
    }
    entry = dict(base)
    entry["entry_hash"] = _entry_hash(base)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(entry) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return entry
