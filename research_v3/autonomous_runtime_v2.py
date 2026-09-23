"""Autonomous Research Runtime V2 executor."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from research_v3.runtime_v2_primitives import (
    RUNTIME_VERSION, SCHEMA_VERSION, DEFAULT_RUNTIME_DIR, STATES, SENSITIVE_BOUNDARIES,
    RuntimeV2Error, MaterialIntegrityHalt, LeaseBusy, ExternalActionRequired, InjectedCrash,
    utc_now, iso, parse_iso, canonical_bytes, pretty_json_bytes, sha256_bytes, sha256_file,
    fsync_dir, atomic_write_bytes, atomic_write_json, load_json, IdentityBinding, RunOutcome,
    FailureInjector, Journal, GitCheckpointSink,
)

class RuntimeV2:
    def __init__(self, root: str | Path, *, runtime_dir: str = DEFAULT_RUNTIME_DIR,
                 lease_seconds: int = 900, injector: FailureInjector | None = None,
                 checkpoint_sink: GitCheckpointSink | None = None,
                 owner_token: str | None = None):
        self.root = Path(root).resolve()
        self.runtime = self.root / runtime_dir
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.operations_dir = self.runtime / "operations"
        self.freeze_dir = self.runtime / "freeze"
        self.auth_dir = self.runtime / "authorizations"
        self.spool_dir = self.runtime / "spool"
        self.results_dir = self.runtime / "results"
        self.closure_dir = self.runtime / "closures"
        self.external_dir = self.runtime / "external_requests"
        for p in (self.operations_dir, self.freeze_dir, self.auth_dir, self.spool_dir,
                  self.results_dir, self.closure_dir, self.external_dir):
            p.mkdir(parents=True, exist_ok=True)
        self.journal = Journal(self.runtime / "operation_journal.jsonl")
        self.lease_path = self.runtime / "lease.json"
        self.checkpoint_path = self.runtime / "checkpoint.json"
        self.accounting_path = self.runtime / "accounting.json"
        self.state_path = self.runtime / "CURRENT_RUNTIME_STATE.json"
        self.ledger_path = self.runtime / "runtime_ledger.jsonl"
        self.knowledge_path = self.runtime / "knowledge_scope.json"
        self.lease_seconds = lease_seconds
        self.injector = injector or FailureInjector()
        self.checkpoint_sink = checkpoint_sink or GitCheckpointSink(self.root, enabled=False)
        self.owner_token = owner_token or os.environ.get("GITHUB_RUN_ID") or uuid.uuid4().hex
        self.run_id = "run_" + sha256_bytes(canonical_bytes({
            "owner_token": self.owner_token,
            "started_utc": iso(),
            "nonce": uuid.uuid4().hex,
            "runtime": RUNTIME_VERSION,
        }))[:24]
        self.current_operation_id: str | None = None
        self.current_state = "RECONCILE"
        self.transitions = 0

    # ---------------- lease / liveness ----------------
    def _lease(self) -> dict[str, Any] | None:
        return load_json(self.lease_path)

    def acquire_lease(self) -> dict[str, Any]:
        now = utc_now()
        existing = self._lease()
        attempt = 1
        retry_metadata: dict[str, Any] = {}
        if existing and existing.get("status") == "ACTIVE":
            expires = parse_iso(existing["expires_utc"])
            if expires > now and existing.get("owner_token") != self.owner_token:
                raise LeaseBusy(f"lease owned by {existing.get('run_id')} until {existing.get('expires_utc')}")
            if expires <= now and existing.get("owner_token") != self.owner_token:
                attempt = int(existing.get("attempt", 1)) + 1
                retry_metadata = {
                    "reason": "STALE_LEASE_TAKEOVER",
                    "previous_run_id": existing.get("run_id"),
                    "previous_owner_token": existing.get("owner_token"),
                    "expired_utc": existing.get("expires_utc"),
                }
                self.journal.append(
                    "STALE_LEASE_RECLAIMED", run_id=self.run_id, operation_id=existing.get("current_operation_id"),
                    state="RECONCILE", payload=retry_metadata,
                )
        lease = {
            "schema": "mxm.greenfield.runtime-v2-lease.v1",
            "status": "ACTIVE",
            "runtime_version": RUNTIME_VERSION,
            "run_id": self.run_id,
            "owner_token": self.owner_token,
            "acquired_utc": iso(now),
            "heartbeat_utc": iso(now),
            "last_progress_utc": iso(now),
            "expires_utc": iso(now + timedelta(seconds=self.lease_seconds)),
            "current_operation_id": None,
            "current_state": "RECONCILE",
            "attempt": attempt,
            "retry_metadata": retry_metadata,
        }
        atomic_write_json(self.lease_path, lease)
        return lease

    def heartbeat(self, *, progress: bool = True) -> None:
        lease = self._lease()
        if not lease or lease.get("owner_token") != self.owner_token or lease.get("status") != "ACTIVE":
            raise LeaseBusy("runtime no longer owns active lease")
        now = utc_now()
        lease["heartbeat_utc"] = iso(now)
        lease["expires_utc"] = iso(now + timedelta(seconds=self.lease_seconds))
        lease["current_operation_id"] = self.current_operation_id
        lease["current_state"] = self.current_state
        if progress:
            lease["last_progress_utc"] = iso(now)
        atomic_write_json(self.lease_path, lease)

    def release_lease(self, status: str = "RELEASED") -> None:
        lease = self._lease()
        if not lease or lease.get("owner_token") != self.owner_token:
            return
        lease["status"] = status
        lease["released_utc"] = iso()
        lease["current_operation_id"] = self.current_operation_id
        lease["current_state"] = self.current_state
        atomic_write_json(self.lease_path, lease)

    # ---------------- plan / identities ----------------
    def submit_operation(self, plan: Mapping[str, Any]) -> tuple[str, Path]:
        identity = self.identity_from_plan(plan)
        op_id = identity.operation_id
        normalized = dict(plan)
        normalized.update({
            "schema": "mxm.greenfield.runtime-v2-operation.v1",
            "runtime_version": RUNTIME_VERSION,
            "operation_id": op_id,
            "economic_execution_id": identity.economic_execution_id,
            "identity_binding": identity.as_dict(),
        })
        path = self.operations_dir / f"{op_id}.json"
        data = pretty_json_bytes(normalized)
        if path.exists() and path.read_bytes() != data:
            raise MaterialIntegrityHalt(f"operation identity collision with different bytes: {op_id}")
        if not path.exists():
            atomic_write_bytes(path, data)
        return op_id, path

    @staticmethod
    def identity_from_plan(plan: Mapping[str, Any]) -> IdentityBinding:
        src = plan.get("identity_binding") or plan
        required = (
            "candidate_spec_hash", "dataset_hash", "evaluator_hash", "cost_authority_hash",
            "execution_semantics_version", "lifecycle_phase",
        )
        missing = [k for k in required if not isinstance(src.get(k), str) or not src.get(k)]
        if missing:
            raise MaterialIntegrityHalt(f"operation missing identity binding fields: {missing}")
        return IdentityBinding(**{k: str(src[k]) for k in required})

    def plans(self) -> list[dict[str, Any]]:
        out = []
        for path in sorted(self.operations_dir.glob("op_*.json")):
            plan = json.loads(path.read_text(encoding="utf-8"))
            ident = self.identity_from_plan(plan)
            if plan.get("operation_id") != ident.operation_id:
                raise MaterialIntegrityHalt(f"operation_id mismatch in {path}")
            if plan.get("economic_execution_id") != ident.economic_execution_id:
                raise MaterialIntegrityHalt(f"economic_execution_id mismatch in {path}")
            out.append(plan)
        return out

    # ---------------- durable transition helpers ----------------
    def _set_state(self, state: str, *, next_action: str | None = None, extra: Mapping[str, Any] | None = None) -> None:
        if state not in STATES:
            raise MaterialIntegrityHalt(f"unknown runtime state {state}")
        self.current_state = state
        doc = {
            "schema": SCHEMA_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "run_id": self.run_id,
            "current_operation_id": self.current_operation_id,
            "current_state": state,
            "next_action": next_action,
            "updated_utc": iso(),
            "transitions": self.transitions,
            "extra": dict(extra or {}),
        }
        atomic_write_json(self.state_path, doc)
        self.heartbeat(progress=True)
        self.transitions += 1

    def _checkpoint(self, boundary: str) -> None:
        journal_rows = self.journal.verify()
        cp = {
            "schema": "mxm.greenfield.runtime-v2-checkpoint.v1",
            "runtime_version": RUNTIME_VERSION,
            "run_id": self.run_id,
            "current_operation_id": self.current_operation_id,
            "current_state": self.current_state,
            "journal_entries": len(journal_rows),
            "journal_tail_hash": journal_rows[-1]["entry_hash"] if journal_rows else "GENESIS",
            "updated_utc": iso(),
            "boundary": boundary,
        }
        atomic_write_json(self.checkpoint_path, cp)
        self.checkpoint_sink.checkpoint(boundary, self.current_operation_id)

    def _boundary(self, boundary: str, *, checkpoint: bool = True) -> None:
        if checkpoint:
            self._checkpoint(boundary)
        self.injector.hit(boundary)

    # ---------------- reconciliation / validation ----------------
    def reconcile(self) -> None:
        self._set_state("RECONCILE", next_action="VALIDATE_INTEGRITY")
        self.journal.verify()
        # Validate every result marker against durable bytes.
        for plan in self.plans():
            op = plan["operation_id"]
            available_event = "NON_ECONOMIC_RESULT_AVAILABLE" if self._is_non_economic(plan) else "ECONOMIC_RESULT_AVAILABLE"
            avail = self.journal.last_event(op, available_event)
            result_persisted = self.journal.last_event(op, "RESULT_FILE_PERSISTED")
            spool = self._spool_path(plan)
            result = self._result_path(plan)
            if avail:
                expected = avail["payload"].get("result_sha256")
                if not spool.exists():
                    raise MaterialIntegrityHalt(f"{op}: RESULT_AVAILABLE journaled but spool missing")
                if sha256_file(spool) != expected:
                    raise MaterialIntegrityHalt(f"{op}: spool hash mismatch")
            if result_persisted:
                expected = result_persisted["payload"].get("result_sha256")
                if not result.exists() or sha256_file(result) != expected:
                    raise MaterialIntegrityHalt(f"{op}: persisted result missing/hash mismatch")
        self._set_state("VALIDATE_INTEGRITY", next_action="DERIVE_NEXT_ACTION")
        self._validate_runtime_ledger()

    def _validate_runtime_ledger(self) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        prev = "GENESIS"
        rows = []
        for idx, line in enumerate(self.ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("sequence") != idx or row.get("previous_entry_hash") != prev:
                raise MaterialIntegrityHalt(f"runtime ledger chain invalid at {idx}")
            body = dict(row); body.pop("entry_hash", None)
            expected = sha256_bytes(canonical_bytes(body))
            if row.get("entry_hash") != expected:
                raise MaterialIntegrityHalt(f"runtime ledger hash invalid at {idx}")
            prev = expected
            rows.append(row)
        return rows

    # ---------------- operation execution ----------------
    @staticmethod
    def _is_non_economic(plan: Mapping[str, Any]) -> bool:
        return str(plan.get("operation_kind", "")).upper() == "NON_ECONOMIC_DIRECTOR"

    def _spool_path(self, plan: Mapping[str, Any]) -> Path:
        if self._is_non_economic(plan):
            return self.spool_dir / f"{plan['operation_id']}.non_economic.json"
        return self.spool_dir / f"{plan['economic_execution_id']}.json"

    def _result_path(self, plan: Mapping[str, Any]) -> Path:
        rel = plan.get("result_path")
        if rel:
            path = (self.root / str(rel)).resolve()
            if self.root not in path.parents and path != self.root:
                raise MaterialIntegrityHalt("result_path escapes repository root")
            return path
        return self.results_dir / f"{plan['operation_id']}.json"

    def _external_ready(self, plan: Mapping[str, Any]) -> bool:
        req = plan.get("external_data") or {}
        if not req.get("required"):
            return True
        rel = req.get("path")
        if not isinstance(rel, str) or not rel:
            return False
        path = (self.root / rel).resolve()
        if not path.exists():
            return False
        expected = req.get("sha256")
        return not expected or sha256_file(path) == expected

    def _build_external_request(self, plan: Mapping[str, Any]) -> None:
        op = plan["operation_id"]
        req = {
            "schema": "mxm.greenfield.runtime-v2-external-data-request.v1",
            "operation_id": op,
            "status": "WAIT_EXTERNAL_DATA_IF_REQUIRED",
            "external_data": plan.get("external_data") or {},
            "created_utc": iso(),
        }
        atomic_write_json(self.external_dir / f"{op}.json", req)

    def _freeze(self, plan: Mapping[str, Any]) -> None:
        op = plan["operation_id"]
        freeze = {
            "schema": "mxm.greenfield.runtime-v2-prospective-freeze.v1",
            "runtime_version": RUNTIME_VERSION,
            "operation_id": op,
            "economic_execution_id": plan["economic_execution_id"],
            "identity_binding": plan["identity_binding"],
            "plan_sha256": sha256_bytes(canonical_bytes(plan)),
            "economic_outcome_opened": False,
        }
        path = self.freeze_dir / f"{op}.json"
        if path.exists():
            existing = load_json(path)
            for key in ("operation_id", "economic_execution_id", "identity_binding", "plan_sha256"):
                if existing.get(key) != freeze.get(key):
                    raise MaterialIntegrityHalt(f"{op}: prospective freeze drift in {key}")
        else:
            atomic_write_json(path, freeze)
        if not self.journal.has(op, "INTENT_PREPARED"):
            self.journal.append("INTENT_PREPARED", run_id=self.run_id, operation_id=op,
                                state="FREEZE_PROSPECTIVE_SPEC", payload={"freeze_sha256": sha256_file(path)})
        self._boundary("prospective_freeze_creation")

    def _pre_outcome_validate(self, plan: Mapping[str, Any]) -> None:
        op = plan["operation_id"]
        gate = plan.get("pre_outcome_gate") or {}
        if gate.get("status", "PASS") != "PASS":
            raise MaterialIntegrityHalt(f"{op}: pre-outcome gate is not PASS")
        safety = plan.get("safety") or {}
        if safety.get("live_orders_authorized") is True:
            raise MaterialIntegrityHalt("Runtime V2 DEVELOPMENT executor refuses LIVE orders")
        if safety.get("protected_evidence_opened") is True:
            raise MaterialIntegrityHalt("Runtime V2 refuses protected evidence opening")
        if not self.journal.has(op, "PRECONDITIONS_VALIDATED"):
            self.journal.append("PRECONDITIONS_VALIDATED", run_id=self.run_id, operation_id=op,
                                state="PRE_OUTCOME_VALIDATE", payload={"gate": gate, "safety": safety})
        self._boundary("pre_outcome_validation")

    def _authorize(self, plan: Mapping[str, Any]) -> None:
        op = plan["operation_id"]
        auth_path = self.auth_dir / f"{op}.json"
        auth = {
            "schema": "mxm.greenfield.runtime-v2-authorization.v1",
            "operation_id": op,
            "economic_execution_id": plan["economic_execution_id"],
            "identity_binding": plan["identity_binding"],
            "status": "AUTHORIZED_AFTER_PRECONDITIONS_VALIDATED",
            "live_orders_authorized": False,
            "protected_evidence_opened": False,
        }
        if auth_path.exists():
            existing = load_json(auth_path)
            if existing.get("economic_execution_id") != plan["economic_execution_id"]:
                raise MaterialIntegrityHalt(f"{op}: authorization execution id drift")
        else:
            atomic_write_json(auth_path, auth)
        if not self.journal.has(op, "AUTHORIZED"):
            self.journal.append("AUTHORIZED", run_id=self.run_id, operation_id=op, state="AUTHORIZE",
                                payload={"authorization_sha256": sha256_file(auth_path),
                                         "economic_execution_id": plan["economic_execution_id"]})
        self._boundary("authorization")

    def _invoke_evaluator(self, plan: Mapping[str, Any], destination: Path) -> None:
        evaluator = plan.get("evaluator") or {}
        kind = evaluator.get("kind", "synthetic")
        if kind == "synthetic":
            payload = {
                "schema": "mxm.greenfield.runtime-v2-synthetic-result.v1",
                "operation_id": plan["operation_id"],
                "economic_execution_id": plan["economic_execution_id"],
                "identity_binding": plan["identity_binding"],
                "synthetic": True,
                "result": evaluator.get("payload", {"score": 1.0}),
            }
            atomic_write_json(destination, payload)
            return
        if kind == "command":
            argv = evaluator.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                raise MaterialIntegrityHalt("command evaluator requires argv string list")
            # Adapter contract: output placeholder is replaced by a path under runtime spool.
            tmp_output = destination.with_suffix(".engine.tmp")
            command = [x.replace("{OUTPUT}", str(tmp_output)) for x in argv]
            env = dict(os.environ)
            env["MXM_ECONOMIC_EXECUTION_ID"] = plan["economic_execution_id"]
            env["MXM_OPERATION_ID"] = plan["operation_id"]
            subprocess.run(command, cwd=self.root, env=env, check=True)
            if not tmp_output.exists():
                raise MaterialIntegrityHalt("command evaluator did not produce required {OUTPUT} file")
            # The runtime becomes sole owner of durable outcome opening.
            data = tmp_output.read_bytes()
            tmp_output.unlink(missing_ok=True)
            atomic_write_bytes(destination, data)
            return
        if kind == "python_callable":
            module_name = evaluator.get("module")
            function_name = evaluator.get("function")
            if not isinstance(module_name, str) or not isinstance(function_name, str):
                raise MaterialIntegrityHalt("python_callable evaluator requires module/function")
            fn = getattr(importlib.import_module(module_name), function_name)
            value = fn(self.root, dict(plan))
            data = value if isinstance(value, bytes) else pretty_json_bytes(value)
            atomic_write_bytes(destination, data)
            return
        raise MaterialIntegrityHalt(f"unsupported evaluator kind {kind}")

    def _execute_economics_exactly_once(self, plan: Mapping[str, Any]) -> tuple[Path, str]:
        op = plan["operation_id"]
        econ = plan["economic_execution_id"]
        spool = self.spool_dir / f"{econ}.json"
        result_available = self.journal.last_event(op, "ECONOMIC_RESULT_AVAILABLE")
        persisted = self.journal.has(op, "RESULT_FILE_PERSISTED") or self.journal.has(op, "OPERATION_CLOSED")
        if result_available or persisted:
            # Absolute no-rerun zone.
            if not spool.exists():
                # A canonical result may survive after spool cleanup in future versions.
                result = self._result_path(plan)
                if result.exists() and persisted:
                    expected = self.journal.last_event(op, "RESULT_FILE_PERSISTED")["payload"]["result_sha256"]
                    if sha256_file(result) != expected:
                        raise MaterialIntegrityHalt(f"{op}: canonical result hash drift")
                    return result, expected
                raise MaterialIntegrityHalt(f"{op}: durable opened outcome marker exists but no result bytes survive")
            digest = sha256_file(spool)
            expected = result_available["payload"].get("result_sha256") if result_available else digest
            if expected != digest:
                raise MaterialIntegrityHalt(f"{op}: opened result spool hash drift")
            return spool, digest

        # STARTED is intentionally PRE_OPEN. A crash here may retry only if no atomic spool exists.
        if not self.journal.has(op, "ECONOMIC_EXECUTION_STARTED"):
            self.journal.append(
                "ECONOMIC_EXECUTION_STARTED", run_id=self.run_id, operation_id=op,
                state="EXECUTE_ECONOMICS_EXACTLY_ONCE",
                payload={"economic_execution_id": econ, "outcome_state": "PRE_OPEN"},
            )
            self._boundary("economic_execution_start_marker")

        if not spool.exists():
            self._invoke_evaluator(plan, spool)
        digest = sha256_file(spool)
        if not self.journal.has(op, "ECONOMIC_RESULT_AVAILABLE"):
            self.journal.append(
                "ECONOMIC_RESULT_AVAILABLE", run_id=self.run_id, operation_id=op,
                state="EXECUTE_ECONOMICS_EXACTLY_ONCE",
                payload={"economic_execution_id": econ, "result_sha256": digest, "outcome_state": "OPENED"},
            )
        self._boundary("result_generation_before_result_persistence")
        return spool, digest

    def _execute_non_economic_exactly_once(self, plan: Mapping[str, Any]) -> tuple[Path, str]:
        op = plan["operation_id"]
        spool = self._spool_path(plan)
        result_available = self.journal.last_event(op, "NON_ECONOMIC_RESULT_AVAILABLE")
        persisted = self.journal.has(op, "RESULT_FILE_PERSISTED") or self.journal.has(op, "OPERATION_CLOSED")
        if result_available or persisted:
            if not spool.exists():
                result = self._result_path(plan)
                if result.exists() and persisted:
                    expected = self.journal.last_event(op, "RESULT_FILE_PERSISTED")["payload"]["result_sha256"]
                    if sha256_file(result) != expected:
                        raise MaterialIntegrityHalt(f"{op}: canonical non-economic result hash drift")
                    return result, expected
                raise MaterialIntegrityHalt(f"{op}: durable non-economic result marker exists but no result bytes survive")
            digest = sha256_file(spool)
            expected = result_available["payload"].get("result_sha256") if result_available else digest
            if expected != digest:
                raise MaterialIntegrityHalt(f"{op}: non-economic result spool hash drift")
            return spool, digest

        if not self.journal.has(op, "NON_ECONOMIC_EXECUTION_STARTED"):
            self.journal.append(
                "NON_ECONOMIC_EXECUTION_STARTED", run_id=self.run_id, operation_id=op,
                state="EXECUTE_NON_ECONOMIC_ACTION",
                payload={"execution_id": plan["economic_execution_id"], "economic_outcome_opened": False},
            )
            self._checkpoint("non_economic_execution_start_marker")

        if not spool.exists():
            self._invoke_evaluator(plan, spool)
        digest = sha256_file(spool)
        if not self.journal.has(op, "NON_ECONOMIC_RESULT_AVAILABLE"):
            self.journal.append(
                "NON_ECONOMIC_RESULT_AVAILABLE", run_id=self.run_id, operation_id=op,
                state="EXECUTE_NON_ECONOMIC_ACTION",
                payload={"execution_id": plan["economic_execution_id"], "result_sha256": digest,
                         "economic_outcome_opened": False},
            )
        return spool, digest

    def _persist_result(self, plan: Mapping[str, Any], spool: Path, digest: str) -> Path:
        op = plan["operation_id"]
        result = self._result_path(plan)
        if result.exists():
            if sha256_file(result) != digest:
                raise MaterialIntegrityHalt(f"{op}: result path exists with different bytes")
        else:
            atomic_write_bytes(result, spool.read_bytes())
        if sha256_file(result) != digest:
            raise MaterialIntegrityHalt(f"{op}: result hash verification failed")
        if not self.journal.has(op, "RESULT_FILE_PERSISTED"):
            self.journal.append("RESULT_FILE_PERSISTED", run_id=self.run_id, operation_id=op,
                                state="PERSIST_RESULT", payload={"result_path": str(result.relative_to(self.root)),
                                                                  "result_sha256": digest})
        self._boundary("result_file_persistence")
        return result

    def _append_runtime_ledger(self, plan: Mapping[str, Any], result: Path, digest: str) -> None:
        op = plan["operation_id"]
        rows = self._validate_runtime_ledger()
        entry_type = "NON_ECONOMIC_RESULT_RECORDED" if self._is_non_economic(plan) else "RESULT_RECORDED"
        existing = [r for r in rows if r.get("operation_id") == op and r.get("entry_type") == entry_type]
        if existing:
            if len(existing) != 1 or existing[0].get("result_sha256") != digest:
                raise MaterialIntegrityHalt(f"{op}: duplicate/drifting runtime ledger result")
            return
        prev = rows[-1]["entry_hash"] if rows else "GENESIS"
        row: dict[str, Any] = {
            "sequence": len(rows) + 1,
            "entry_type": entry_type,
            "operation_id": op,
            "economic_execution_id": plan["economic_execution_id"],
            "result_path": str(result.relative_to(self.root)),
            "result_sha256": digest,
            "identity_binding": plan["identity_binding"],
            "previous_entry_hash": prev,
        }
        row["entry_hash"] = sha256_bytes(canonical_bytes(row))
        with self.ledger_path.open("ab") as f:
            f.write(canonical_bytes(row) + b"\n")
            f.flush(); os.fsync(f.fileno())
        fsync_dir(self.ledger_path.parent)
        self._validate_runtime_ledger()
        if not self.journal.has(op, "LEDGER_PERSISTED"):
            self.journal.append("LEDGER_PERSISTED", run_id=self.run_id, operation_id=op,
                                state="PERSIST_RESULT", payload={"ledger_sequence": row["sequence"],
                                                                  "ledger_entry_hash": row["entry_hash"]})
        self._boundary("ledger_append")

    def _project_accounting(self, plan: Mapping[str, Any]) -> None:
        op = plan["operation_id"]
        acc = load_json(self.accounting_path, {
            "schema": "mxm.greenfield.runtime-v2-accounting.v1",
            "completed_operation_ids": [],
            "non_economic_operation_ids": [],
            "economic_execution_ids": [],
            "economic_outcomes_opened": 0,
        })
        completed = set(acc.get("completed_operation_ids", []))
        completed.add(op)
        acc["completed_operation_ids"] = sorted(completed)
        if self._is_non_economic(plan):
            non_economic = set(acc.get("non_economic_operation_ids", []))
            non_economic.add(op)
            acc["non_economic_operation_ids"] = sorted(non_economic)
        else:
            econ_ids = set(acc.get("economic_execution_ids", []))
            econ_ids.add(plan["economic_execution_id"])
            acc["economic_execution_ids"] = sorted(econ_ids)
        acc.setdefault("economic_execution_ids", [])
        acc.setdefault("non_economic_operation_ids", [])
        acc["economic_outcomes_opened"] = len(set(acc["economic_execution_ids"]))
        atomic_write_json(self.accounting_path, acc)
        if not self.journal.has(op, "ACCOUNTING_PROJECTED"):
            self.journal.append(
                "ACCOUNTING_PROJECTED", run_id=self.run_id, operation_id=op, state="PERSIST_RESULT",
                payload={
                    "economic_outcomes_opened": acc["economic_outcomes_opened"],
                    "non_economic_operation": self._is_non_economic(plan),
                },
            )
        self._boundary("accounting_update")

    def _project_current_state(self, plan: Mapping[str, Any], digest: str) -> None:
        op = plan["operation_id"]
        state = load_json(self.state_path, {})
        state.update({
            "schema": SCHEMA_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "current_operation_id": op,
            "current_state": "VALIDATE_ACCOUNTING_LEDGER_HASHES",
            "last_result_sha256": digest,
            "last_economic_execution_id": plan["economic_execution_id"],
            "updated_utc": iso(),
        })
        atomic_write_json(self.state_path, state)
        if not self.journal.has(op, "STATE_PROJECTED"):
            self.journal.append("STATE_PROJECTED", run_id=self.run_id, operation_id=op,
                                state="PERSIST_RESULT", payload={"result_sha256": digest})
        self._boundary("current_state_update")

    def _project_checkpoint(self, plan: Mapping[str, Any]) -> None:
        self._checkpoint("checkpoint_update")
        self.injector.hit("checkpoint_update")

    def _validate_post_persistence(self, plan: Mapping[str, Any], digest: str) -> None:
        op = plan["operation_id"]
        result = self._result_path(plan)
        if not result.exists() or sha256_file(result) != digest:
            raise MaterialIntegrityHalt(f"{op}: canonical result invalid post-persistence")
        rows = self._validate_runtime_ledger()
        matches = [r for r in rows if r.get("operation_id") == op]
        if len(matches) != 1 or matches[0].get("result_sha256") != digest:
            raise MaterialIntegrityHalt(f"{op}: runtime ledger/result mismatch")
        acc = load_json(self.accounting_path, {})
        if acc.get("economic_outcomes_opened") != len(set(acc.get("economic_execution_ids", []))):
            raise MaterialIntegrityHalt("runtime accounting is not exact")
        if not self.journal.has(op, "POST_VALIDATION_GREEN"):
            self.journal.append("POST_VALIDATION_GREEN", run_id=self.run_id, operation_id=op,
                                state="POST_PERSISTENCE_VALIDATE", payload={"result_sha256": digest})
        self._boundary("post_persistence_validation")

    def _close(self, plan: Mapping[str, Any], digest: str) -> None:
        op = plan["operation_id"]
        closure = {
            "schema": "mxm.greenfield.runtime-v2-lifecycle-closure.v1",
            "operation_id": op,
            "execution_id": plan["economic_execution_id"],
            "result_sha256": digest,
            "economic_outcome_opened": not self._is_non_economic(plan),
            "status": "CLOSED_POST_VALIDATION_GREEN",
        }
        closure_path = self.closure_dir / f"{op}.json"
        if not closure_path.exists():
            atomic_write_json(closure_path, closure)
        if not self.journal.has(op, "OPERATION_CLOSED"):
            self.journal.append(
                "OPERATION_CLOSED", run_id=self.run_id, operation_id=op, state="CLOSE_LIFECYCLE",
                payload={"closure_sha256": sha256_file(closure_path),
                         "economic_outcome_opened": not self._is_non_economic(plan)},
            )
        self._boundary("lifecycle_closure")

    def _update_knowledge_scope(self, plan: Mapping[str, Any]) -> None:
        op = plan["operation_id"]
        knowledge = load_json(self.knowledge_path, {
            "schema": "mxm.greenfield.runtime-v2-knowledge-scope.v1",
            "completed_operation_ids": [],
            "mechanism_family_closed_count": 0,
        })
        ids = set(knowledge.get("completed_operation_ids", [])); ids.add(op)
        knowledge["completed_operation_ids"] = sorted(ids)
        # Runtime infrastructure never closes a mechanism family from one candidate failure.
        knowledge.setdefault("mechanism_family_closed_count", 0)
        atomic_write_json(self.knowledge_path, knowledge)
        if not self.journal.has(op, "KNOWLEDGE_SCOPE_UPDATED"):
            self.journal.append("KNOWLEDGE_SCOPE_UPDATED", run_id=self.run_id, operation_id=op,
                                state="UPDATE_KNOWLEDGE_SCOPE", payload={"completed_count": len(ids)})

    def _operation_complete(self, plan: Mapping[str, Any]) -> bool:
        # Closure is not the final canonical transition; knowledge-scope projection must also survive.
        op = plan["operation_id"]
        return self.journal.has(op, "OPERATION_CLOSED") and self.journal.has(op, "KNOWLEDGE_SCOPE_UPDATED")

    def _assert_runtime_acceptance_gate(self, plan: Mapping[str, Any]) -> None:
        if self._is_non_economic(plan):
            return
        if (plan.get("identity_binding") or {}).get("lifecycle_phase") == "SYNTHETIC_ACCEPTANCE":
            return
        gate_path = self.root / "evidence/AUTONOMOUS_RESEARCH_RUNTIME_V2_ACCEPTANCE_V1.json"
        gate = load_json(gate_path, {})
        if gate.get("runtime_version") != RUNTIME_VERSION or gate.get("status") not in {"PASS_EXACT_HEAD_GREEN", "PASS"}:
            raise MaterialIntegrityHalt(
                "AUTONOMOUS_RESEARCH_RUNTIME_V2 acceptance gate is not durably PASS; real economics remain forbidden"
            )
        if gate.get("economic_resume_gate_open") is not True:
            raise MaterialIntegrityHalt("Runtime V2 partial acceptance evidence does not open its legacy resume gate")
        e2e_path = self.root / "evidence/ZERO_HUMAN_END_TO_END_RESEARCH_PROGRESSION_V1.json"
        e2e = load_json(e2e_path, {})
        if e2e.get("status") != "PASS" or e2e.get("economics_opened_during_fix") != 0:
            raise MaterialIntegrityHalt(
                "ZERO_HUMAN_END_TO_END_RESEARCH_PROGRESSION is not durably PASS; real economics remain forbidden"
            )
        ai_gate_path = self.root / "evidence/GENERAL_AI_RESEARCH_DIRECTOR_ACCEPTANCE_V1.json"
        ai_gate = load_json(ai_gate_path, {})
        if ai_gate.get("status") != "PASS" or ai_gate.get("economics_opened_during_acceptance") != 0:
            raise MaterialIntegrityHalt(
                "GENERAL_AI_RESEARCH_DIRECTOR acceptance is not durably PASS; real economics remain forbidden"
            )

    def execute_operation(self, plan: Mapping[str, Any]) -> str:
        op = str(plan["operation_id"])
        self.current_operation_id = op
        self._set_state("DERIVE_NEXT_ACTION", next_action="SELECT_RESEARCH_ACTION")
        if self._operation_complete(plan):
            return "ALREADY_CLOSED"
        self._set_state("SELECT_RESEARCH_ACTION", next_action="ASSESS_DATA_SUFFICIENCY")
        self._assert_runtime_acceptance_gate(plan)
        self._set_state("ASSESS_DATA_SUFFICIENCY")
        if not self._external_ready(plan):
            self._set_state("BUILD_DATA_COLLECTOR_IF_REQUIRED", next_action="WAIT_EXTERNAL_DATA_IF_REQUIRED")
            self._build_external_request(plan)
            self.journal.append("EXTERNAL_DATA_REQUIRED", run_id=self.run_id, operation_id=op,
                                state="WAIT_EXTERNAL_DATA_IF_REQUIRED", payload=plan.get("external_data") or {})
            self._checkpoint("external_data_wait")
            self._set_state("WAIT_EXTERNAL_DATA_IF_REQUIRED", next_action="COMPLETE_EXTERNAL_AUTHORIZATION_REQUIRED")
            return "WAIT_EXTERNAL_DATA"

        self._set_state("FREEZE_PROSPECTIVE_SPEC", next_action="PRE_OUTCOME_VALIDATE")
        self._freeze(plan)
        self._set_state("PRE_OUTCOME_VALIDATE", next_action="AUTHORIZE")
        self._pre_outcome_validate(plan)
        next_exec = "EXECUTE_NON_ECONOMIC_ACTION" if self._is_non_economic(plan) else "EXECUTE_ECONOMICS_EXACTLY_ONCE"
        self._set_state("AUTHORIZE", next_action=next_exec)
        self._authorize(plan)
        if self._is_non_economic(plan):
            self._set_state("EXECUTE_NON_ECONOMIC_ACTION", next_action="PERSIST_RESULT")
            spool, digest = self._execute_non_economic_exactly_once(plan)
        else:
            self._set_state("EXECUTE_ECONOMICS_EXACTLY_ONCE", next_action="PERSIST_RESULT")
            spool, digest = self._execute_economics_exactly_once(plan)
        self._set_state("PERSIST_RESULT", next_action="VALIDATE_ACCOUNTING_LEDGER_HASHES")
        result = self._persist_result(plan, spool, digest)
        self._append_runtime_ledger(plan, result, digest)
        self._project_accounting(plan)
        self._project_current_state(plan, digest)
        self._project_checkpoint(plan)
        self._set_state("VALIDATE_ACCOUNTING_LEDGER_HASHES", next_action="POST_PERSISTENCE_VALIDATE")
        self._validate_runtime_ledger()
        self._set_state("POST_PERSISTENCE_VALIDATE", next_action="CLOSE_LIFECYCLE")
        self._validate_post_persistence(plan, digest)
        self._set_state("CLOSE_LIFECYCLE", next_action="UPDATE_KNOWLEDGE_SCOPE")
        self._close(plan, digest)
        self._set_state("UPDATE_KNOWLEDGE_SCOPE", next_action="CONTINUE")
        self._update_knowledge_scope(plan)
        self._checkpoint("knowledge_scope_update")
        self._set_state("CONTINUE", next_action="DERIVE_NEXT_ACTION")
        return "CLOSED"

    def run(self, *, max_operations: int = 50) -> RunOutcome:
        completed: list[str] = []
        try:
            self.acquire_lease()
            self.reconcile()
            processed = 0
            while processed < max_operations:
                pending = [p for p in self.plans() if not self._operation_complete(p)]
                if not pending:
                    self._set_state("CONTINUE", next_action="NO_PENDING_RESEARCH_ACTION")
                    self.release_lease("RELEASED_CLEAN")
                    self._checkpoint("clean_release")
                    return RunOutcome("COMPLETE", self.run_id, completed, transitions=self.transitions)
                plan = pending[0]
                status = self.execute_operation(plan)
                if status == "WAIT_EXTERNAL_DATA":
                    self._set_state("COMPLETE_EXTERNAL_AUTHORIZATION_REQUIRED", next_action="WAIT_EXTERNAL_DATA_IF_REQUIRED")
                    self.release_lease("RELEASED_EXTERNAL_WAIT")
                    self._checkpoint("external_wait_release")
                    return RunOutcome("EXTERNAL_ACTION_REQUIRED", self.run_id, completed,
                                      waiting_operation_id=plan["operation_id"], transitions=self.transitions)
                if status in {"CLOSED", "ALREADY_CLOSED"}:
                    if plan["operation_id"] not in completed:
                        completed.append(plan["operation_id"])
                processed += 1
            self.release_lease("RELEASED_BOUNDED")
            self._checkpoint("bounded_release")
            return RunOutcome("BOUNDED_CHECKPOINT", self.run_id, completed, transitions=self.transitions)
        except LeaseBusy:
            raise
        except InjectedCrash:
            # Deliberately keep lease ACTIVE to exercise stale-run takeover semantics.
            raise
        except MaterialIntegrityHalt as exc:
            self.current_state = "HALT_MATERIAL_INTEGRITY"
            try:
                self._set_state("HALT_MATERIAL_INTEGRITY", next_action=None, extra={"reason": str(exc)})
                self.journal.append("MATERIAL_INTEGRITY_HALT", run_id=self.run_id,
                                    operation_id=self.current_operation_id,
                                    state="HALT_MATERIAL_INTEGRITY", payload={"reason": str(exc)})
                self._checkpoint("material_integrity_halt")
            finally:
                self.release_lease("RELEASED_MATERIAL_HALT")
                try:
                    self._checkpoint("material_halt_release")
                except Exception:
                    pass
            return RunOutcome("HALT_MATERIAL_INTEGRITY", self.run_id, completed,
                              halt_reason=str(exc), transitions=self.transitions)
        except Exception:
            # Unexpected implementation failures retain lease until stale timeout, preventing
            # a second executor from racing a possibly active first process.
            raise


def make_synthetic_plan(seed: str, *, external_data: Mapping[str, Any] | None = None,
                        gate_status: str = "PASS") -> dict[str, Any]:
    def h(label: str) -> str:
        return sha256_bytes(f"{seed}:{label}".encode("utf-8"))
    return {
        "candidate_spec_hash": h("spec"),
        "dataset_hash": h("dataset"),
        "evaluator_hash": h("evaluator"),
        "cost_authority_hash": h("cost"),
        "execution_semantics_version": "SYNTHETIC_V1",
        "lifecycle_phase": "SYNTHETIC_ACCEPTANCE",
        "evaluator": {"kind": "synthetic", "payload": {"seed": seed, "net_pnl_eur": 1.0}},
        "pre_outcome_gate": {"status": gate_status},
        "safety": {"live_orders_authorized": False, "protected_evidence_opened": False},
        "external_data": dict(external_data or {"required": False}),
    }


def canonical_runtime_snapshot(root: Path) -> dict[str, Any]:
    runtime = root / DEFAULT_RUNTIME_DIR
    # Exclude liveness timestamps/run IDs from byte-equivalence proof. Canonical economic
    # and accounting artifacts must match exactly.
    files = [
        runtime / "runtime_ledger.jsonl",
        runtime / "accounting.json",
        runtime / "knowledge_scope.json",
    ]
    results = sorted((runtime / "results").glob("*.json")) if (runtime / "results").exists() else []
    closures = sorted((runtime / "closures").glob("*.json")) if (runtime / "closures").exists() else []
    return {
        "files": {str(p.relative_to(root)): sha256_file(p) for p in files + results + closures if p.exists()},
        "ledger": (runtime / "runtime_ledger.jsonl").read_text(encoding="utf-8") if (runtime / "runtime_ledger.jsonl").exists() else "",
        "accounting": load_json(runtime / "accounting.json", {}),
        "results": {p.name: p.read_text(encoding="utf-8") for p in results},
    }


def _copy_operation_plans(src_root: Path, dst_root: Path) -> None:
    src = src_root / DEFAULT_RUNTIME_DIR / "operations"
    dst = dst_root / DEFAULT_RUNTIME_DIR / "operations"
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.glob("*.json"):
        shutil.copy2(p, dst / p.name)



def zero_human_continuation_demo() -> dict[str, Any]:
    from research_v3.runtime_v2_acceptance import zero_human_continuation_demo as _demo
    return _demo()

def _cmd_acceptance(args: argparse.Namespace) -> int:
    report = zero_human_continuation_demo()
    text = json.dumps(report, sort_keys=True, indent=2)
    print(text)
    if args.report:
        atomic_write_bytes(Path(args.report), (text + "\n").encode("utf-8"))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    sink = GitCheckpointSink(root.resolve(), enabled=args.git_checkpoint, push=args.git_push)
    runtime = RuntimeV2(root, runtime_dir=args.runtime_dir, lease_seconds=args.lease_seconds,
                        checkpoint_sink=sink, owner_token=args.owner_token)
    outcome = runtime.run(max_operations=args.max_operations)
    print(json.dumps(outcome.__dict__, sort_keys=True, indent=2))
    return 0 if outcome.status in {"COMPLETE", "BOUNDED_CHECKPOINT", "EXTERNAL_ACTION_REQUIRED"} else 2


def _cmd_submit_synthetic(args: argparse.Namespace) -> int:
    rt = RuntimeV2(args.root, runtime_dir=args.runtime_dir)
    plan = make_synthetic_plan(args.seed)
    op, path = rt.submit_operation(plan)
    print(json.dumps({"operation_id": op, "path": str(path)}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=RUNTIME_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    acc = sub.add_parser("acceptance")
    acc.add_argument("--report")
    acc.set_defaults(func=_cmd_acceptance)

    run = sub.add_parser("run")
    run.add_argument("--root", default=".")
    run.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    run.add_argument("--lease-seconds", type=int, default=900)
    run.add_argument("--max-operations", type=int, default=50)
    run.add_argument("--owner-token")
    run.add_argument("--git-checkpoint", action="store_true")
    run.add_argument("--git-push", action="store_true")
    run.set_defaults(func=_cmd_run)

    syn = sub.add_parser("submit-synthetic")
    syn.add_argument("seed")
    syn.add_argument("--root", default=".")
    syn.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    syn.set_defaults(func=_cmd_submit_synthetic)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
