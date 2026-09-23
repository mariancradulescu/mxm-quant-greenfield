"""MXM Autonomous Research Runtime V2.

Repository-native, restartable research executor with:
- deterministic operation/economic execution identities
- append-only hash-chained write-ahead journal
- lease/heartbeat/stale takeover
- crash-safe atomic persistence
- exactly-once *durable outcome opening* semantics
- multi-transition autonomous execution
- bounded external-data wait states
- optional git checkpoint commits/pushes at sensitive boundaries

The runtime deliberately does not authorize LIVE trading. It is a DEVELOPMENT
research control loop. Real economic adapters must write their result only to the
provided deterministic spool path. A result is considered economically OPENED
only after the spool bytes are atomically durable and ECONOMIC_RESULT_AVAILABLE
is journaled. If a runner dies after ECONOMIC_EXECUTION_STARTED but before that
point, there is no durable opened outcome and retry is legal. Once RESULT_AVAILABLE
(or any later persistence marker) exists, the evaluator is never invoked again.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

RUNTIME_VERSION = "MXM_AUTONOMOUS_RESEARCH_RUNTIME_V2"
SCHEMA_VERSION = "mxm.greenfield.autonomous-research-runtime.v2"
DEFAULT_RUNTIME_DIR = "research_v3/runtime_v2"

STATES = (
    "RECONCILE",
    "VALIDATE_INTEGRITY",
    "DERIVE_NEXT_ACTION",
    "SELECT_RESEARCH_ACTION",
    "ASSESS_DATA_SUFFICIENCY",
    "BUILD_DATA_COLLECTOR_IF_REQUIRED",
    "WAIT_EXTERNAL_DATA_IF_REQUIRED",
    "FREEZE_PROSPECTIVE_SPEC",
    "PRE_OUTCOME_VALIDATE",
    "AUTHORIZE",
    "EXECUTE_NON_ECONOMIC_ACTION",
    "EXECUTE_ECONOMICS_EXACTLY_ONCE",
    "PERSIST_RESULT",
    "VALIDATE_ACCOUNTING_LEDGER_HASHES",
    "POST_PERSISTENCE_VALIDATE",
    "CLOSE_LIFECYCLE",
    "UPDATE_KNOWLEDGE_SCOPE",
    "CONTINUE",
    "HALT_MATERIAL_INTEGRITY",
    "COMPLETE_EXTERNAL_AUTHORIZATION_REQUIRED",
)

SENSITIVE_BOUNDARIES = {
    "prospective_freeze_creation",
    "pre_outcome_validation",
    "authorization",
    "economic_execution_start_marker",
    "result_generation_before_result_persistence",
    "result_file_persistence",
    "ledger_append",
    "accounting_update",
    "current_state_update",
    "checkpoint_update",
    "post_persistence_validation",
    "lifecycle_closure",
}


class RuntimeV2Error(RuntimeError):
    pass


class MaterialIntegrityHalt(RuntimeV2Error):
    pass


class LeaseBusy(RuntimeV2Error):
    pass


class ExternalActionRequired(RuntimeV2Error):
    pass


class InjectedCrash(RuntimeV2Error):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        fsync_dir(path.parent)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_bytes(path, pretty_json_bytes(value))


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _journal_hash(payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    body.pop("entry_hash", None)
    return sha256_bytes(canonical_bytes(body))


@dataclass(frozen=True)
class IdentityBinding:
    candidate_spec_hash: str
    dataset_hash: str
    evaluator_hash: str
    cost_authority_hash: str
    execution_semantics_version: str
    lifecycle_phase: str

    def as_dict(self) -> dict[str, str]:
        return {
            "candidate_spec_hash": self.candidate_spec_hash,
            "dataset_hash": self.dataset_hash,
            "evaluator_hash": self.evaluator_hash,
            "cost_authority_hash": self.cost_authority_hash,
            "execution_semantics_version": self.execution_semantics_version,
            "lifecycle_phase": self.lifecycle_phase,
        }

    @property
    def operation_id(self) -> str:
        return "op_" + sha256_bytes(canonical_bytes({"runtime": RUNTIME_VERSION, **self.as_dict()}))[:32]

    @property
    def economic_execution_id(self) -> str:
        return "econ_" + sha256_bytes(canonical_bytes({"operation_id": self.operation_id, "purpose": "economic_execution"}))[:32]


@dataclass
class RunOutcome:
    status: str
    run_id: str
    completed_operation_ids: list[str]
    waiting_operation_id: str | None = None
    halt_reason: str | None = None
    transitions: int = 0


class FailureInjector:
    def __init__(self, fail_after: Iterable[str] | None = None):
        self.remaining = set(fail_after or [])

    def hit(self, boundary: str) -> None:
        if boundary in self.remaining:
            self.remaining.remove(boundary)
            raise InjectedCrash(f"injected crash after {boundary}")


class Journal:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for idx, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise MaterialIntegrityHalt(f"journal parse failure at line {idx}: {exc}") from exc
        return rows

    def verify(self) -> list[dict[str, Any]]:
        rows = self.rows()
        prev = "GENESIS"
        for idx, row in enumerate(rows, start=1):
            if row.get("sequence") != idx:
                raise MaterialIntegrityHalt(f"journal sequence mismatch at line {idx}")
            if row.get("previous_entry_hash") != prev:
                raise MaterialIntegrityHalt(f"journal previous hash mismatch at line {idx}")
            expected = _journal_hash(row)
            if row.get("entry_hash") != expected:
                raise MaterialIntegrityHalt(f"journal entry hash mismatch at line {idx}")
            prev = expected
        return rows

    def append(self, event: str, *, run_id: str, operation_id: str | None, state: str,
               payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        rows = self.verify()
        prev = rows[-1]["entry_hash"] if rows else "GENESIS"
        row: dict[str, Any] = {
            "sequence": len(rows) + 1,
            "recorded_utc": iso(),
            "runtime_version": RUNTIME_VERSION,
            "run_id": run_id,
            "operation_id": operation_id,
            "state": state,
            "event": event,
            "payload": dict(payload or {}),
            "previous_entry_hash": prev,
        }
        row["entry_hash"] = _journal_hash(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as f:
            f.write(canonical_bytes(row) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        fsync_dir(self.path.parent)
        return row

    def events_for(self, operation_id: str) -> list[dict[str, Any]]:
        return [r for r in self.verify() if r.get("operation_id") == operation_id]

    def has(self, operation_id: str, event: str) -> bool:
        return any(r.get("event") == event for r in self.events_for(operation_id))

    def last_event(self, operation_id: str, event: str) -> dict[str, Any] | None:
        found = [r for r in self.events_for(operation_id) if r.get("event") == event]
        return found[-1] if found else None


class GitCheckpointSink:
    """Optional repository-native checkpoint persistence used by GitHub Actions.

    Commits only when called at material boundaries. Multiple transitions remain in
    one Actions run; this does not create one Actions run per state transition.
    """

    def __init__(self, root: Path, enabled: bool = False, push: bool = False):
        self.root = root
        self.enabled = enabled
        self.push = push

    def checkpoint(self, boundary: str, operation_id: str | None) -> None:
        if not self.enabled:
            return
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=self.root)
        if diff.returncode == 0:
            return
        msg = f"[skip ci] Runtime V2 checkpoint {boundary} {operation_id or 'runtime'}"
        subprocess.run(["git", "commit", "-m", msg], cwd=self.root, check=True)
        if self.push:
            target = os.environ.get("MXM_RUNTIME_TARGET_BRANCH")
            refspec = f"HEAD:refs/heads/{target}" if target else "HEAD"
            first = subprocess.run(
                ["git", "push", "origin", refspec],
                cwd=self.root, text=True, capture_output=True,
            )
            if first.returncode == 0:
                return
            if not target:
                raise RuntimeV2Error(
                    "checkpoint push failed without MXM_RUNTIME_TARGET_BRANCH; "
                    f"stderr={first.stderr.strip()}"
                )
            subprocess.run(["git", "fetch", "origin", target], cwd=self.root, check=True)
            rebase = subprocess.run(
                ["git", "rebase", f"origin/{target}"],
                cwd=self.root, text=True, capture_output=True,
            )
            if rebase.returncode != 0:
                subprocess.run(["git", "rebase", "--abort"], cwd=self.root, check=False)
                raise MaterialIntegrityHalt(
                    "checkpoint push conflict could not be reconciled cleanly; "
                    f"stderr={rebase.stderr.strip()}"
                )
            second = subprocess.run(
                ["git", "push", "origin", refspec],
                cwd=self.root, text=True, capture_output=True,
            )
            if second.returncode != 0:
                raise RuntimeV2Error(
                    "checkpoint push failed after one fetch/rebase retry; "
                    f"stderr={second.stderr.strip()}"
                )

