"""Restartable, idempotent post-outcome persistence for V3 economic waves.

This module never executes economics. It accepts already-opened result artifacts,
verifies identity and hashes, reconciles partial persistence, appends no more than
one RESULT_RECORDED per wave candidate, and projects accounting deterministically.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from discovery.canonical import canonical_json, compute_result_hash
from discovery.ledger import derive_active_spec_hashes, read_ledger, validate_lifecycle_append
from discovery.schema import validate_result


class WavePersistenceError(ValueError):
    pass


def _pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _entry_hash(base: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(base).encode("utf-8")).hexdigest()


def _read_json_bytes(data: bytes, label: str) -> dict:
    try:
        value = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise WavePersistenceError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise WavePersistenceError(f"{label} must contain a JSON object")
    return value


def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        raise WavePersistenceError(f"missing {label}: {path}")
    return _read_json_bytes(path.read_bytes(), label)


def _read_git_blob(root: Path, sha: str) -> bytes:
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise WavePersistenceError("git_blob_sha1 must be a lowercase 40-character SHA-1")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob", sha],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except Exception as exc:
        raise WavePersistenceError(f"cannot recover git blob {sha}") from exc
    if _git_blob_sha1(proc.stdout) != sha:
        raise WavePersistenceError(f"git blob verification failed for {sha}")
    return proc.stdout


def _source_bytes(root: Path, source: Any, cid: str) -> bytes:
    if isinstance(source, (str, os.PathLike, Path)):
        path = Path(source)
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            raise WavePersistenceError(f"{cid} result source does not exist: {path}")
        return path.read_bytes()
    if isinstance(source, Mapping):
        if "candidate_id" in source:
            return _pretty_json_bytes(dict(source))
        sha = source.get("git_blob_sha1")
        if isinstance(sha, str):
            return _read_git_blob(root, sha)
        path = source.get("path")
        if isinstance(path, str):
            return _source_bytes(root, path, cid)
    raise WavePersistenceError(f"unsupported result source for {cid}")


def _verify_result(result: dict, cid: str, spec_hash: str) -> None:
    validate_result(result)
    if result.get("candidate_id") != cid:
        raise WavePersistenceError(f"{cid} result candidate_id mismatch")
    if result.get("spec_hash") != spec_hash:
        raise WavePersistenceError(f"{cid} result spec_hash mismatch")
    expected = compute_result_hash(result)
    if result.get("result_hash") != expected:
        raise WavePersistenceError(f"{cid} result_hash mismatch: expected {expected}, got {result.get('result_hash')}")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with tmp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


@contextmanager
def _wave_lock(root: Path, wave_key: str):
    lock_dir = root / ".mxm_persistence"
    lock_dir.mkdir(parents=True, exist_ok=True)
    handle = (lock_dir / f"{wave_key}.lock").open("a+b")
    try:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass
        yield
    finally:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except ImportError:
            pass
        handle.close()


def persist_wave_results(
    root: str | os.PathLike[str],
    *,
    wave_key: str,
    results: Mapping[str, Any] | None,
    recorded_utc: str,
    result_refs: Mapping[str, str] | None = None,
    execution_result_ref: str | None = None,
    live_equivalent_candidate_ids: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict:
    """Persist already-opened results and safely resume any partial persistence."""
    root = Path(root)
    if not recorded_utc or not recorded_utc.endswith("Z"):
        raise WavePersistenceError("recorded_utc must be an explicit UTC Z timestamp")

    with _wave_lock(root, wave_key):
        state_path = root / "CURRENT_STATE.json"
        ledger_path = root / "discovery/ledger.jsonl"
        state = _load_json(state_path, "CURRENT_STATE")
        ledger = read_ledger(ledger_path)
        active = derive_active_spec_hashes(ledger)

        perf = state.get("performance_research_v3")
        if not isinstance(perf, dict) or not isinstance(perf.get(wave_key), dict):
            raise WavePersistenceError(f"CURRENT_STATE missing performance_research_v3.{wave_key}")
        wave = perf[wave_key]
        candidate_ids = list(wave.get("candidate_ids") or [])
        spec_hashes = dict(wave.get("candidate_spec_hashes") or {})
        if not candidate_ids or set(candidate_ids) != set(spec_hashes):
            raise WavePersistenceError("wave candidate/spec bindings are incomplete")

        freeze_ref = wave.get("freeze_ref")
        if not isinstance(freeze_ref, str):
            raise WavePersistenceError("wave freeze_ref missing")
        freeze = _load_json(root / freeze_ref, "wave freeze authority")
        before = freeze.get("accounting_before")
        if not isinstance(before, dict):
            raise WavePersistenceError("wave freeze authority missing accounting_before")

        supplied = dict(results or {})
        unknown = set(supplied) - set(candidate_ids)
        if unknown:
            raise WavePersistenceError(f"result sources contain non-wave candidates: {sorted(unknown)}")

        refs = dict(result_refs or wave.get("result_refs") or {})
        for cid in candidate_ids:
            refs.setdefault(cid, f"discovery/results/{cid}_STAGE_A_V1.json")
        execution_ref = execution_result_ref or wave.get("execution_result_ref") or f"research_v3/{wave_key.upper()}_EXECUTION_RESULT_V1.json"

        existing_rows = {
            cid: [e for e in ledger if e.get("candidate_id") == cid and e.get("entry_type") == "RESULT_RECORDED"]
            for cid in candidate_ids
        }
        for cid, rows in existing_rows.items():
            if len(rows) > 1:
                raise WavePersistenceError(f"{cid} has duplicate RESULT_RECORDED rows")

        docs: dict[str, dict] = {}
        bytes_by_id: dict[str, bytes] = {}
        for cid in candidate_ids:
            spec_hash = spec_hashes[cid]
            if active.get(cid) != spec_hash:
                raise WavePersistenceError(f"{cid} active frozen spec hash mismatch")
            candidates: list[tuple[str, bytes]] = []
            final_path = root / refs[cid]
            if cid in supplied:
                candidates.append(("supplied", _source_bytes(root, supplied[cid], cid)))
            if final_path.exists():
                candidates.append(("standalone", final_path.read_bytes()))
            if existing_rows[cid]:
                embedded = existing_rows[cid][0].get("payload", {}).get("result")
                if not isinstance(embedded, dict):
                    raise WavePersistenceError(f"{cid} ledger row lacks authoritative result payload")
                candidates.append(("ledger", _pretty_json_bytes(embedded)))
            if not candidates:
                continue

            parsed = []
            for kind, data in candidates:
                doc = _read_json_bytes(data, f"{cid} {kind} result")
                _verify_result(doc, cid, spec_hash)
                parsed.append((kind, data, doc))
            authoritative = parsed[0][2]
            if any(doc != authoritative for _, _, doc in parsed[1:]):
                raise WavePersistenceError(f"{cid} partial persistence contains conflicting result payloads")
            preferred = next((x for x in parsed if x[0] == "supplied"), None)
            preferred = preferred or next((x for x in parsed if x[0] == "standalone"), None) or parsed[0]
            docs[cid] = authoritative
            bytes_by_id[cid] = preferred[1]

        if not docs:
            raise WavePersistenceError("no opened result artifacts were supplied or recoverable")

        desired_ledger = list(ledger)
        sequences: dict[str, int] = {}
        entry_hashes: dict[str, str] = {}
        newly_appended: list[str] = []
        for cid in candidate_ids:
            if cid not in docs:
                continue
            result = docs[cid]
            rows = existing_rows[cid]
            if rows:
                row = rows[0]
                if row.get("spec_hash") != spec_hashes[cid] or row.get("payload", {}).get("result_hash") != result["result_hash"] or row.get("payload", {}).get("result") != result:
                    raise WavePersistenceError(f"{cid} existing ledger result conflicts with authoritative payload")
                sequences[cid] = int(row["sequence"])
                entry_hashes[cid] = row["entry_hash"]
                continue
            payload = {"result_hash": result["result_hash"], "result": result}
            validate_lifecycle_append(desired_ledger, entry_type="RESULT_RECORDED", candidate_id=cid, spec_hash=spec_hashes[cid], payload=payload)
            base = {
                "sequence": len(desired_ledger) + 1,
                "timestamp_utc": recorded_utc,
                "entry_type": "RESULT_RECORDED",
                "candidate_id": cid,
                "spec_hash": spec_hashes[cid],
                "previous_entry_hash": desired_ledger[-1]["entry_hash"] if desired_ledger else None,
                "payload": payload,
            }
            row = dict(base)
            row["entry_hash"] = _entry_hash(base)
            desired_ledger.append(row)
            sequences[cid] = row["sequence"]
            entry_hashes[cid] = row["entry_hash"]
            newly_appended.append(cid)

        opened_ids = [cid for cid in candidate_ids if cid in docs]
        before_attempts = int(before["v2_attempts_used"])
        before_outcomes = int(before["economic_outcomes_opened"])

        # Current accounting is derived from immutable repository exposure, not from
        # the historical forensic-authority subset or a one-result-per-identity rule.
        final_result_count = sum(e.get("entry_type") == "RESULT_RECORDED" for e in desired_ledger)
        exposed_v2_ids = sorted({
            e["candidate_id"] for e in desired_ledger
            if e.get("entry_type") == "RESULT_RECORDED"
            and str(e.get("candidate_id", "")).startswith("V2-C")
        })
        after_attempts = len(exposed_v2_ids)
        after_budget = int(state.get("v2_search_budget", 84)) - after_attempts
        stage_b_observations = int(state.get("stage_b_current_config_economic_observations", 0))
        after_outcomes = final_result_count + stage_b_observations

        current_attempts = int(state.get("v2_attempts_used", before_attempts))
        current_outcomes = int(state.get("economic_outcomes_opened", before_outcomes))
        if not before_attempts <= current_attempts <= after_attempts:
            raise WavePersistenceError("CURRENT_STATE attempts are outside recoverable wave bounds")
        if not before_outcomes <= current_outcomes <= after_outcomes:
            raise WavePersistenceError("CURRENT_STATE economic outcomes are outside recoverable wave bounds")
        if int(state.get("discovery_result_recorded_entries", 0)) > final_result_count:
            raise WavePersistenceError("CURRENT_STATE result count is ahead of recoverable ledger")

        live_equivalent = set(live_equivalent_candidate_ids or ())
        if not live_equivalent <= set(opened_ids):
            raise WavePersistenceError("live-equivalent authority may only be assigned to opened wave identities")

        state["v2_attempts_used"] = after_attempts
        state["v2_evaluated_identities"] = after_attempts
        state["v2_search_budget_remaining"] = after_budget
        state["economic_outcomes_opened"] = after_outcomes
        state["global_attempts_seen"] = int(state.get("legacy_prior_attempts", 0)) + after_attempts
        state["discovery_ledger_entries"] = len(desired_ledger)
        state["discovery_result_recorded_entries"] = final_result_count
        state["stage_a_result_recorded_entries"] = final_result_count
        state["distinct_identity_outcomes_opened"] = after_attempts
        state["stage_b_current_config_economic_observations"] = stage_b_observations
        state["v2_budget_charged_candidate_ids"] = exposed_v2_ids
        state["v2_historical_evaluated_candidate_ids"] = exposed_v2_ids
        state["structural_only_since_previous_economic_outcome"] = False
        state.setdefault("current_result_authority", {})
        state.setdefault("active_result_pointers", {})

        current_live = set(state.get("current_live_equivalent_authoritative_candidate_ids", []))
        current_invalid = set(state.get("current_invalid_result_authority_candidate_ids", []))
        for cid in opened_ids:
            result = docs[cid]
            stage_a_authority = {
                "state": "VALID_AS_FROZEN_AND_IMPLEMENTED",
                "result_ref": refs[cid],
                "result_hash": result["result_hash"],
                "status": result["status"],
            }
            if cid in live_equivalent:
                stage_a_authority.update({
                    "live_equivalent_replay_state": "VALID_AS_FROZEN_AND_IMPLEMENTED",
                    "current_live_equivalent_authoritative": True,
                    "same_identity_correction_allowed": False,
                    "new_identity_required": False,
                })
                current_live.add(cid)
                current_invalid.discard(cid)
            state["current_result_authority"][cid] = {"stage_a": stage_a_authority}
            state["active_result_pointers"][f"{cid}_STAGE_A"] = refs[cid]
        state["current_live_equivalent_authoritative_candidate_ids"] = sorted(current_live)
        state["current_invalid_result_authority_candidate_ids"] = sorted(current_invalid)

        last_cid = opened_ids[-1]
        last = docs[last_cid]
        state["latest_economic_outcome"] = {
            "candidate_id": last_cid, "stage": last["stage"], "status": last["status"],
            "result_hash": last["result_hash"], "result_ref": refs[last_cid], "recorded_utc": recorded_utc,
        }

        complete = len(opened_ids) == len(candidate_ids)
        status = "RESULTS_RECORDED_PENDING_EXACT_HEAD_GREEN" if complete else "PARTIAL_RESULTS_RECORDED_PENDING_RESUME"
        wave["status"] = status
        wave["candidate_own_outcomes_opened"] = bool(opened_ids)
        wave["result_statuses"] = {cid: docs[cid]["status"] for cid in opened_ids}
        wave["result_hashes"] = {cid: docs[cid]["result_hash"] for cid in opened_ids}
        wave["result_refs"] = {cid: refs[cid] for cid in opened_ids}
        wave[f"v2_attempts_used_after_{wave_key}"] = after_attempts
        wave[f"v2_search_budget_remaining_after_{wave_key}"] = after_budget
        wave[f"economic_outcomes_opened_after_{wave_key}"] = after_outcomes
        wave["economic_attempt_delta"] = len(opened_ids)
        wave["persistence_additional_attempts_consumed"] = 0
        wave["execution_result_ref"] = execution_ref
        wave["stage_b_extension_candidates"] = [cid for cid in opened_ids if docs[cid]["status"] == "DISCOVERY_SURVIVOR"]
        wave["ledger_result_sequences"] = dict(sequences)
        wave["ledger_tail_entry_hash"] = desired_ledger[-1]["entry_hash"] if desired_ledger else None

        label = wave_key.upper()
        perf["status"] = f"{label}_{status}"
        state["phase"] = f"PERFORMANCE_RESEARCH_V3_{label}_{status}"
        state["next_action"] = (
            f"Require exact-head full CI GREEN for canonically persisted {label} outcomes; then continue prospective research without rerunning already-opened economics."
            if complete else
            f"Resume {label} only for still-unopened identities; never rerun already-opened outcomes."
        )

        execution = {
            "schema": "mxm.greenfield.performance-research-v3.wave-execution-result.v1",
            "wave_key": wave_key,
            "status": "PERSISTED_PENDING_EXACT_HEAD_GREEN" if complete else "PARTIAL_PERSISTENCE_RECOVERABLE",
            "recorded_utc": recorded_utc,
            "classification": "AUTHORIZED_ECONOMIC_OUTCOME_POST_OUTCOME_PERSISTENCE",
            "authorization": {
                "ref": wave.get("authorization_ref"),
                "execution_gate_head": wave.get("execution_gate_head"),
                "execution_gate_ci_run_id": wave.get("execution_gate_ci_run_id"),
                "execution_gate_ci_conclusion": wave.get("execution_gate_ci_conclusion"),
            },
            "batch": {
                "candidate_ids": candidate_ids,
                "opened_candidate_ids": opened_ids,
                "opened_count": len(opened_ids),
                "persistence_additional_attempts": 0,
                "same_frozen_semantics": True,
                "rescue_tuning": False,
                "protected_evidence_used": False,
                "live_equivalent_candidate_ids": sorted(live_equivalent),
            },
            "results": {
                cid: {
                    "status": docs[cid]["status"], "result_hash": docs[cid]["result_hash"],
                    "result_ref": refs[cid], "result_git_blob_sha1": _git_blob_sha1(bytes_by_id[cid]),
                } for cid in opened_ids
            },
            "accounting": {
                "before": {
                    "v2_attempts_used": before_attempts,
                    "v2_search_budget_remaining": int(before["v2_search_budget_remaining"]),
                    "v2_evaluated_identities": int(before["v2_evaluated_identities"]),
                    "economic_outcomes_opened": before_outcomes,
                },
                "after": {
                    "v2_attempts_used": after_attempts,
                    "v2_search_budget_remaining": after_budget,
                    "v2_evaluated_identities": after_attempts,
                    "economic_outcomes_opened": after_outcomes,
                },
                "persistence_additional_attempts_consumed": 0,
            },
            "ledger": {
                "result_sequences": sequences,
                "result_entry_hashes": entry_hashes,
                "new_result_ids_this_invocation": newly_appended,
                "new_tail_entry_hash": desired_ledger[-1]["entry_hash"] if desired_ledger else None,
            },
            "safety": {
                "protected_evidence_opened": bool(state.get("protected_evidence_opened", False)),
                "live_orders_authorized": bool(state.get("live_orders_authorized", False)),
                "competition_start_authorized": bool(state.get("competition_start_authorized", False)),
            },
        }

        ledger_bytes = b"".join((canonical_json(e) + "\n").encode("utf-8") for e in desired_ledger)
        state_bytes = _pretty_json_bytes(state)
        execution_bytes = _pretty_json_bytes(execution)

        tx_dir = root / ".mxm_persistence" / wave_key
        tx_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = tx_dir / "manifest.json"
        manifest = {
            "schema": "mxm.greenfield.wave-persistence-manifest.v1",
            "wave_key": wave_key,
            "status": "PREPARED",
            "recorded_utc": recorded_utc,
            "opened_candidate_ids": opened_ids,
            "result_hashes": {cid: docs[cid]["result_hash"] for cid in opened_ids},
            "desired": {
                "ledger_sha256": _sha256(ledger_bytes),
                "state_sha256": _sha256(state_bytes),
                "execution_result_sha256": _sha256(execution_bytes),
            },
        }
        _atomic_write(manifest_path, _pretty_json_bytes(manifest))

        for cid in opened_ids:
            path = root / refs[cid]
            if path.exists():
                existing = _read_json_bytes(path.read_bytes(), f"{cid} existing standalone result")
                if existing != docs[cid]:
                    raise WavePersistenceError(f"{cid} standalone result conflicts with authoritative payload")
            else:
                _atomic_write(path, bytes_by_id[cid])

        _atomic_write(root / execution_ref, execution_bytes)
        _atomic_write(ledger_path, ledger_bytes)

        verified = read_ledger(ledger_path)
        if len(verified) != len(desired_ledger):
            raise WavePersistenceError("ledger roundtrip length mismatch after write")
        for cid in opened_ids:
            rows = [e for e in verified if e.get("candidate_id") == cid and e.get("entry_type") == "RESULT_RECORDED"]
            if len(rows) != 1 or rows[0]["payload"]["result_hash"] != docs[cid]["result_hash"]:
                raise WavePersistenceError(f"{cid} ledger roundtrip verification failed")

        _atomic_write(state_path, state_bytes)

        manifest["status"] = "COMPLETE"
        manifest["final"] = {
            "ledger_sha256": _sha256(ledger_path.read_bytes()),
            "state_sha256": _sha256(state_path.read_bytes()),
            "execution_result_sha256": _sha256((root / execution_ref).read_bytes()),
            "ledger_entries": len(verified),
            "result_recorded_entries": final_result_count,
            "v2_attempts_used": after_attempts,
            "v2_search_budget_remaining": after_budget,
            "economic_outcomes_opened": after_outcomes,
        }
        _atomic_write(manifest_path, _pretty_json_bytes(manifest))

        return {
            "wave_key": wave_key,
            "status": "COMPLETE",
            "opened_candidate_ids": opened_ids,
            "new_result_ids_this_invocation": newly_appended,
            "result_hashes": manifest["result_hashes"],
            "ledger_result_sequences": sequences,
            "v2_attempts_used": after_attempts,
            "v2_search_budget_remaining": after_budget,
            "economic_outcomes_opened": after_outcomes,
            "persistence_additional_attempts_consumed": 0,
            "manifest_path": str(manifest_path.relative_to(root)),
        }
