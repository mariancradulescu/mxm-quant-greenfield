"""Restartable persistence for same-identity live-equivalent corrected successors.

This module performs persistence only.  It never executes candidate economics.  Every
corrected successor must keep an already-exposed V2 candidate id and the exact active
frozen spec hash.  It appends an IMPLEMENTATION_CORRECTION + RESULT_RECORDED pair once,
keeps historical result bytes, and derives search-budget usage from distinct exposed
identities rather than result-row count.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from discovery.canonical import canonical_json, compute_result_hash
from discovery.ledger import derive_active_spec_hashes, read_ledger, validate_lifecycle_append
from discovery.schema import validate_result

CORRECTION_ID = "SAME_IDENTITY_LIVE_EQUIVALENT_CORRECTION_V1"
CORRECTION_IDS = ("V2-C006", "V2-C012", "V2-C023", "V2-C025")
RESULT_REFS = {
    "V2-C006": "discovery/results/V2-C006_STAGE_A_V2.json",
    "V2-C012": "discovery/results/V2-C012_STAGE_A_V3.json",
    "V2-C023": "discovery/results/V2-C023_STAGE_A_V2.json",
    "V2-C025": "discovery/results/V2-C025_STAGE_A_V2.json",
}


class SameIdentityPersistenceError(ValueError):
    pass


def _pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry_hash(base: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(base).encode("utf-8")).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with tmp.open("wb") as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, path)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise SameIdentityPersistenceError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SameIdentityPersistenceError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise SameIdentityPersistenceError(f"{label} must be a JSON object")
    return value


def _verify_result(result: Mapping[str, Any], cid: str, spec_hash: str) -> dict[str, Any]:
    doc = json.loads(json.dumps(result))
    validate_result(doc)
    if doc.get("candidate_id") != cid or doc.get("spec_hash") != spec_hash:
        raise SameIdentityPersistenceError(f"{cid} corrected result identity/spec mismatch")
    expected = compute_result_hash(doc)
    if doc.get("result_hash") != expected:
        raise SameIdentityPersistenceError(f"{cid} corrected result_hash mismatch")
    return doc


def _append_row(entries: list[dict[str, Any]], *, entry_type: str, cid: str,
                spec_hash: str, payload: Mapping[str, Any], recorded_utc: str) -> dict[str, Any]:
    validate_lifecycle_append(entries, entry_type=entry_type, candidate_id=cid,
                              spec_hash=spec_hash, payload=payload)
    base = {
        "sequence": len(entries) + 1,
        "timestamp_utc": recorded_utc,
        "entry_type": entry_type,
        "candidate_id": cid,
        "spec_hash": spec_hash,
        "previous_entry_hash": entries[-1]["entry_hash"] if entries else None,
        "payload": dict(payload),
    }
    row = dict(base); row["entry_hash"] = _entry_hash(base); entries.append(row); return row


def persist_same_identity_corrections(
    root: str | os.PathLike[str], *, results: Mapping[str, Mapping[str, Any]],
    recorded_utc: str, authority_ref: str,
) -> dict[str, Any]:
    """Persist already-opened same-identity corrected successors exactly once.

    This function never computes economics and never creates a new V2 identity.  A rerun
    with the same successor bytes is a no-op for the ledger and attempt accounting.
    """
    root = Path(root)
    if not recorded_utc.endswith("Z"):
        raise SameIdentityPersistenceError("recorded_utc must be explicit UTC Z")
    if not results:
        raise SameIdentityPersistenceError("at least one corrected result is required")
    unknown = set(results) - set(CORRECTION_IDS)
    if unknown:
        raise SameIdentityPersistenceError(f"outside correction scope: {sorted(unknown)}")

    state_path = root / "CURRENT_STATE.json"
    ledger_path = root / "discovery/ledger.jsonl"
    audit_path = root / "evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V3.json"
    state = _load_json(state_path, "CURRENT_STATE")
    audit = _load_json(audit_path, "forensic audit")
    entries = read_ledger(ledger_path)
    active = derive_active_spec_hashes(entries)

    historical = set(state.get("v2_historical_evaluated_candidate_ids") or
                     audit.get("attempt_accounting", {}).get("historical_evaluated_candidate_ids") or [])
    if not historical:
        raise SameIdentityPersistenceError("missing historical exposed identity set")
    before_distinct = {e["candidate_id"] for e in entries if e.get("entry_type") == "RESULT_RECORDED" and str(e.get("candidate_id", "")).startswith("V2-C")}
    if before_distinct != historical:
        raise SameIdentityPersistenceError("ledger distinct exposure set disagrees with historical authority")

    docs: dict[str, dict[str, Any]] = {}
    for cid, supplied in results.items():
        if cid not in historical:
            raise SameIdentityPersistenceError(f"{cid} was not already exposed; same-identity path forbidden")
        if cid not in active:
            raise SameIdentityPersistenceError(f"{cid} lacks active frozen spec")
        docs[cid] = _verify_result(supplied, cid, active[cid])

    desired = list(entries)
    appended: dict[str, dict[str, int]] = {}
    for cid in CORRECTION_IDS:
        if cid not in docs:
            continue
        result = docs[cid]
        correction_rows = [e for e in desired if e.get("entry_type") == "IMPLEMENTATION_CORRECTION" and e.get("candidate_id") == cid and (e.get("payload") or {}).get("correction_id") == CORRECTION_ID]
        result_rows = [e for e in desired if e.get("entry_type") == "RESULT_RECORDED" and e.get("candidate_id") == cid and (e.get("payload") or {}).get("correction_id") == CORRECTION_ID]
        if correction_rows or result_rows:
            if len(correction_rows) != 1 or len(result_rows) != 1:
                raise SameIdentityPersistenceError(f"{cid} partial/duplicate corrected persistence")
            if (result_rows[0].get("payload") or {}).get("result_hash") != result["result_hash"] or (result_rows[0].get("payload") or {}).get("result") != result:
                raise SameIdentityPersistenceError(f"{cid} corrected persistence conflicts with supplied bytes")
            continue

        prior = state.get("current_result_authority", {}).get(cid, {}).get("stage_a", {})
        correction_payload = {
            "correction_id": CORRECTION_ID,
            "authority_ref": authority_ref,
            "same_identity": True,
            "semantic_change": False,
            "new_v2_attempt_consumed": False,
            "search_budget_delta": 0,
            "post_outcome_artifact_reconstruction": True,
            "historical_result_ref": prior.get("result_ref"),
            "historical_result_hash": prior.get("result_hash"),
            "corrected_result_ref": RESULT_REFS[cid],
            "corrected_result_hash": result["result_hash"],
        }
        crow = _append_row(desired, entry_type="IMPLEMENTATION_CORRECTION", cid=cid,
                           spec_hash=active[cid], payload=correction_payload, recorded_utc=recorded_utc)
        rpayload = {
            "result_hash": result["result_hash"], "result": result,
            "correction_id": CORRECTION_ID, "same_identity_correction": True,
            "new_v2_attempt_consumed": False, "search_budget_delta": 0,
            "authority_ref": authority_ref,
        }
        rrow = _append_row(desired, entry_type="RESULT_RECORDED", cid=cid,
                           spec_hash=active[cid], payload=rpayload, recorded_utc=recorded_utc)
        appended[cid] = {"correction_sequence": crow["sequence"], "result_sequence": rrow["sequence"]}

    final_distinct = {e["candidate_id"] for e in desired if e.get("entry_type") == "RESULT_RECORDED" and str(e.get("candidate_id", "")).startswith("V2-C")}
    if final_distinct != historical:
        raise SameIdentityPersistenceError("same-identity correction changed distinct V2 exposure set")

    # Write/version corrected standalone result bytes before changing authority pointers.
    for cid, result in docs.items():
        out = root / RESULT_REFS[cid]
        data = _pretty(result)
        if out.exists() and out.read_bytes() != data:
            raise SameIdentityPersistenceError(f"{cid} corrected successor file conflicts with supplied bytes")
        if not out.exists():
            _atomic_write(out, data)

    # Project state from immutable exposure history; row count may grow, identity count may not.
    result_rows = [e for e in desired if e.get("entry_type") == "RESULT_RECORDED"]
    v2_ids = sorted(final_distinct)
    v2_budget = int(state.get("v2_search_budget", 84))
    stage_b_observations = int(state.get("stage_b_current_config_economic_observations", 0))
    state["v2_attempts_used"] = len(v2_ids)
    state["v2_evaluated_identities"] = len(v2_ids)
    state["v2_search_budget_remaining"] = v2_budget - len(v2_ids)
    state["global_attempts_seen"] = int(state.get("legacy_prior_attempts", 0)) + len(v2_ids)
    state["discovery_result_recorded_entries"] = len(result_rows)
    state["stage_a_result_recorded_entries"] = len(result_rows)
    state["distinct_identity_outcomes_opened"] = len(v2_ids)
    state["economic_outcomes_opened"] = len(result_rows) + stage_b_observations
    state["discovery_ledger_entries"] = len(desired)

    state.setdefault("current_result_authority", {})
    state.setdefault("active_result_pointers", {})
    state.setdefault("superseded_or_invalid_historical_result_pointers", {})
    corrected_now = set(state.get("current_live_equivalent_authoritative_candidate_ids", []))
    pending = set(state.get("pending_same_identity_correction_candidate_ids", CORRECTION_IDS))
    for cid, result in docs.items():
        old = dict(state["current_result_authority"].get(cid, {}).get("stage_a", {}))
        if old.get("correction_id") == CORRECTION_ID:
            old_ref = old.get("historical_result_ref")
            old_hash = old.get("historical_result_hash")
        elif old.get("result_ref") and old.get("result_hash"):
            old_ref = old.get("result_ref")
            old_hash = old.get("result_hash")
        elif old.get("corrected_successor_ref") and old.get("corrected_successor_hash"):
            old_ref = old.get("corrected_successor_ref")
            old_hash = old.get("corrected_successor_hash")
        else:
            old_ref = old.get("historical_result_ref")
            old_hash = old.get("historical_result_hash")
        if old_ref:
            key = f"{cid}_STAGE_A_PRE_LIVE_EQUIVALENT_CORRECTION"
            state["superseded_or_invalid_historical_result_pointers"].setdefault(key, old_ref)
        stage_a = dict(old)
        stage_a.update({
            "state": "VALID_CORRECTED_SUCCESSOR",
            "result_ref": RESULT_REFS[cid],
            "result_hash": result["result_hash"],
            "status": result["status"],
            "live_equivalent_replay_state": "CORRECTED_SAME_IDENTITY_CURRENT_AUTHORITY",
            "correction_id": CORRECTION_ID,
            "correction_authority_ref": authority_ref,
            "same_identity_correction_allowed": False,
            "new_identity_required": False,
            "current_live_equivalent_authoritative": True,
            "historical_result_ref": old_ref,
            "historical_result_hash": old_hash,
        })
        state["current_result_authority"].setdefault(cid, {})["stage_a"] = stage_a
        state["active_result_pointers"][f"{cid}_STAGE_A"] = RESULT_REFS[cid]
        corrected_now.add(cid); pending.discard(cid)

    state["current_live_equivalent_authoritative_candidate_ids"] = sorted(corrected_now)
    state["pending_same_identity_correction_candidate_ids"] = sorted(pending)
    survivor_ids = sorted(
        cid for cid in corrected_now
        if state.get("current_result_authority", {}).get(cid, {}).get("stage_a", {}).get("status") == "DISCOVERY_SURVIVOR"
    )
    state["live_equivalent_discovery_survivors"] = survivor_ids
    state["discovery_survivors"] = survivor_ids
    # Stage-B bytes remain invalid until their own downstream revalidation completes.
    state["current_stage_b_survivor_input_set"] = []
    state["stage_b_revalidation_required_candidate_ids"] = survivor_ids
    state["same_identity_live_equivalent_correction"] = {
        "correction_id": CORRECTION_ID,
        "authority_ref": authority_ref,
        "corrected_candidate_ids": sorted(corrected_now),
        "pending_candidate_ids": sorted(pending),
        "additional_v2_attempts_consumed": 0,
        "post_outcome_artifact_reconstruction": True,
        "result_refs": {cid: RESULT_REFS[cid] for cid in corrected_now if cid in RESULT_REFS},
    }
    state["structural_only_since_previous_economic_outcome"] = False
    state["latest_economic_outcome"] = {
        "candidate_id": list(docs)[-1], "stage": "A",
        "status": docs[list(docs)[-1]]["status"],
        "result_hash": docs[list(docs)[-1]]["result_hash"],
        "result_ref": RESULT_REFS[list(docs)[-1]], "recorded_utc": recorded_utc,
        "classification": "SAME_IDENTITY_CORRECTED_SUCCESSOR_RECONSTRUCTED_AFTER_ARTIFACT_LOSS",
    }
    if not pending:
        state["performance_research_v3"]["status"] = "SAME_IDENTITY_LIVE_EQUIVALENT_CORRECTIONS_RECORDED_PENDING_STAGE_B_REVALIDATION"
        state["phase"] = "PERFORMANCE_RESEARCH_V3_SAME_IDENTITY_CORRECTIONS_RECORDED"
        state["next_action"] = "Revalidate downstream Stage-B only for corrected live-equivalent Stage-A survivors; consume zero additional V2 identity attempts."

    # Forensic classification remains historical; only the current pending lifecycle changes.
    aa = audit.setdefault("attempt_accounting", {})
    aa["pending_same_identity_correction_candidate_ids"] = sorted(pending)
    aa["corrected_same_identity_candidate_ids"] = sorted(corrected_now & set(CORRECTION_IDS))
    aa["v2_attempts_used"] = len(v2_ids)
    aa["v2_search_budget_remaining"] = v2_budget - len(v2_ids)
    aa["distinct_identity_outcomes_opened"] = len(v2_ids)
    aa["stage_a_result_recorded_entries"] = len(result_rows)
    aa["stage_b_current_config_economic_observations"] = stage_b_observations
    aa["economic_outcomes_opened_historical"] = len(result_rows) + stage_b_observations
    audit["status"] = "COMPLETE_PER_IDENTITY_CLASSIFICATION_EXPOSURE_ACCOUNTING_AND_CORRECTION_LIFECYCLE"

    tx = root / ".mxm_persistence/same_identity_live_equivalent_v1/manifest.json"
    ledger_bytes = b"".join((canonical_json(e) + "\n").encode("utf-8") for e in desired)
    manifest = {
        "schema": "mxm.greenfield.same-identity-correction-persistence.v1",
        "status": "PREPARED", "correction_id": CORRECTION_ID,
        "recorded_utc": recorded_utc, "candidate_ids": sorted(docs),
        "result_hashes": {cid: docs[cid]["result_hash"] for cid in docs},
        "desired": {"ledger_sha256": _sha256(ledger_bytes), "state_sha256": _sha256(_pretty(state)), "audit_sha256": _sha256(_pretty(audit))},
    }
    _atomic_write(tx, _pretty(manifest))
    _atomic_write(audit_path, _pretty(audit))
    _atomic_write(ledger_path, ledger_bytes)
    verified = read_ledger(ledger_path)
    if verified != desired:
        raise SameIdentityPersistenceError("ledger roundtrip mismatch")
    _atomic_write(state_path, _pretty(state))
    manifest["status"] = "COMPLETE"
    manifest["final"] = {
        "ledger_entries": len(desired), "result_recorded_entries": len(result_rows),
        "distinct_v2_identities": len(v2_ids), "v2_attempts_used": state["v2_attempts_used"],
        "v2_search_budget_remaining": state["v2_search_budget_remaining"],
        "economic_outcomes_opened": state["economic_outcomes_opened"],
        "appended": appended,
    }
    _atomic_write(tx, _pretty(manifest))
    return manifest
