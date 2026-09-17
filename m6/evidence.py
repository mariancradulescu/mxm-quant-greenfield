"""Generic M6 pre-economic materialization/evidence gates.

No strategy-specific collector logic lives here. Frozen requirements drive the
checks. Metadata alone is never promoted to materialized data.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

VERIFIED = "VERIFIED"
CONSERVATIVE_BOUND = "CONSERVATIVE_BOUND"
UNRESOLVED = "UNRESOLVED"
COST_STATES = {VERIFIED, CONSERVATIVE_BOUND, UNRESOLVED}
DATASET_BINDING_SCHEMA = "mxm.greenfield.v2.materialized-dataset-binding.v1"
COST_BINDING_SCHEMA = "mxm.greenfield.v2.discovery-cost-binding.v1"
CAUSAL_BAR_RULE = "COMPLETED_BAR_AVAILABLE_AT_CLOSE"
MISSING_DATA_RULE = "PRESERVE_SOURCE_GAPS_NO_SYNTHESIS_NO_FORWARD_FILL"


class EvidenceError(ValueError):
    pass


def _sha(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise EvidenceError("UTC timestamp must be a string")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceError(f"invalid UTC timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise EvidenceError(f"timestamp is not explicit UTC: {value}")
    return dt.astimezone(timezone.utc)


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_sha256(value: Mapping[str, Any], *, exclude: Sequence[str] = ()) -> str:
    excluded = set(exclude)
    payload = {k: v for k, v in value.items() if k not in excluded}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def expected_dataset_specs(requirements: Mapping[str, Any]) -> list[dict[str, Any]]:
    reqs = requirements.get("requirements")
    if not isinstance(reqs, Mapping):
        raise EvidenceError("requirements manifest has no requirements mapping")
    out = []
    for cid in sorted(reqs):
        req = reqs[cid]
        instruments = req.get("instruments")
        if not isinstance(instruments, list) or not instruments:
            raise EvidenceError(f"{cid}: instruments missing")
        interval = req.get("interval")
        if not isinstance(interval, Mapping):
            raise EvidenceError(f"{cid}: interval missing")
        for instrument in instruments:
            identity = {
                "candidate_id": cid,
                "instrument": instrument,
                "resolution": req.get("resolution"),
                "interval": dict(interval),
            }
            digest = canonical_json_sha256(identity)
            out.append({
                **identity,
                "dataset_id": f"PW02-{cid}-{instrument}-{req.get('resolution')}-{digest[:16]}",
                "required_fields": list(req.get("fields", [])),
            })
    return out


def _text(mapping: Mapping[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"{context}: {key} must be non-empty")
    return value


def _safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute():
        raise EvidenceError("data_file must be repository-relative")
    target = (root / rel).resolve()
    rr = root.resolve()
    if target != rr and rr not in target.parents:
        raise EvidenceError("data_file escapes repository root")
    return target


def _req(requirements: Mapping[str, Any], cid: str, instrument: str) -> Mapping[str, Any]:
    reqs = requirements.get("requirements")
    if not isinstance(reqs, Mapping) or cid not in reqs:
        raise EvidenceError(f"unknown candidate: {cid}")
    req = reqs[cid]
    if instrument not in req.get("instruments", []):
        raise EvidenceError(f"{cid}: unexpected instrument {instrument}")
    return req


def verify_dataset_binding(binding: Mapping[str, Any], requirements: Mapping[str, Any], *,
                           protected_start_utc: str, root: Path | str) -> dict[str, Any]:
    if binding.get("schema") != DATASET_BINDING_SCHEMA:
        raise EvidenceError("unsupported dataset binding schema")
    cid = _text(binding, "candidate_id", "dataset binding")
    instrument = _text(binding, "instrument", cid)
    req = _req(requirements, cid, instrument)

    active_hash = requirements.get("candidate_spec_hashes", {}).get(cid)
    if not _sha(active_hash) or binding.get("spec_hash") != active_hash:
        raise EvidenceError(f"{cid}/{instrument}: active candidate spec hash is not bound")
    expected = next(s for s in expected_dataset_specs(requirements)
                    if s["candidate_id"] == cid and s["instrument"] == instrument)
    if binding.get("dataset_id") != expected["dataset_id"]:
        raise EvidenceError(f"{cid}/{instrument}: canonical dataset identity mismatch")
    if binding.get("resolution") != req.get("resolution"):
        raise EvidenceError(f"{cid}/{instrument}: resolution mismatch")
    if binding.get("interval") != req.get("interval"):
        raise EvidenceError(f"{cid}/{instrument}: interval must exactly match frozen requirement")
    if binding.get("timezone") != "UTC":
        raise EvidenceError(f"{cid}/{instrument}: timezone must be UTC")
    if binding.get("causal_availability") != CAUSAL_BAR_RULE:
        raise EvidenceError(f"{cid}/{instrument}: causal rule mismatch")
    if binding.get("missing_data_rule") != MISSING_DATA_RULE:
        raise EvidenceError(f"{cid}/{instrument}: missing-data rule mismatch")

    source = binding.get("source")
    if not isinstance(source, Mapping):
        raise EvidenceError(f"{cid}/{instrument}: source metadata missing")
    if source.get("broker") != "Pepperstone" or source.get("environment") != "Pepperstone - Europe LIVE":
        raise EvidenceError(f"{cid}/{instrument}: exact Pepperstone LIVE source not bound")
    _text(source, "acquisition_method", f"{cid}/{instrument} source")
    if not _sha(source.get("provenance_sha256")):
        raise EvidenceError(f"{cid}/{instrument}: source provenance hash missing")

    complete = binding.get("completeness")
    if not isinstance(complete, Mapping) or complete.get("state") != "COMPLETE":
        raise EvidenceError(f"{cid}/{instrument}: completeness is not COMPLETE")
    if complete.get("interval") != req.get("interval"):
        raise EvidenceError(f"{cid}/{instrument}: completeness interval mismatch")
    _text(complete, "method", f"{cid}/{instrument} completeness")

    mapping = binding.get("broker_mapping")
    if not isinstance(mapping, Mapping) or mapping.get("canonical_instrument") != instrument:
        raise EvidenceError(f"{cid}/{instrument}: broker mapping missing/mismatched")
    _text(mapping, "broker_symbol", f"{cid}/{instrument} broker mapping")
    if mapping.get("enabled") is not True or not _sha(mapping.get("evidence_sha256")):
        raise EvidenceError(f"{cid}/{instrument}: ENABLED broker mapping is not hash-bound")

    semantic = binding.get("semantic_evidence")
    if not isinstance(semantic, Mapping):
        raise EvidenceError(f"{cid}/{instrument}: semantic evidence missing")
    for key in ("session", "synchronization", "currency_conversion", "contract_roll", "corporate_actions"):
        _text(semantic, key, f"{cid}/{instrument} semantics")
    if req.get("short_side_requirements"):
        _text(semantic, "short_side", f"{cid}/{instrument} semantics")

    declared = binding.get("fields")
    if not isinstance(declared, list) or not declared:
        raise EvidenceError(f"{cid}/{instrument}: fields missing")
    required = set(req.get("fields", []))
    if not required.issubset(set(declared)):
        raise EvidenceError(f"{cid}/{instrument}: required fields missing from binding")

    relative = _text(binding, "data_file", f"{cid}/{instrument}")
    path = _safe_path(Path(root), relative)
    if not path.is_file():
        raise EvidenceError(f"{cid}/{instrument}: actual data bytes are not accessible")
    expected_sha = binding.get("sha256")
    if not _sha(expected_sha) or sha256_file(path) != expected_sha:
        raise EvidenceError(f"{cid}/{instrument}: data sha256 missing/mismatched")

    protected = _utc(protected_start_utc)
    start = _utc(req["interval"]["start_utc"])
    end = _utc(req["interval"]["end_utc"])
    count = 0
    last = None
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        if not required.issubset(set(header)):
            raise EvidenceError(f"{cid}/{instrument}: required CSV columns missing")
        for row in reader:
            ts = _utc(row["time_utc"])
            if ts < start:
                raise EvidenceError(f"{cid}/{instrument}: row before DEVELOPMENT interval")
            if ts > end:
                raise EvidenceError(f"{cid}/{instrument}: row after DEVELOPMENT interval")
            if ts >= protected:
                raise EvidenceError(f"{cid}/{instrument}: protected-forward leakage")
            if last is not None and ts <= last:
                raise EvidenceError(f"{cid}/{instrument}: timestamps not strictly increasing")
            last = ts
            count += 1
    if count <= 0 or binding.get("row_count") != count:
        raise EvidenceError(f"{cid}/{instrument}: empty data or row_count mismatch")

    bh = binding.get("binding_sha256")
    actual_bh = canonical_json_sha256(binding, exclude=("binding_sha256",))
    if not _sha(bh) or bh != actual_bh:
        raise EvidenceError(f"{cid}/{instrument}: immutable dataset binding hash mismatch")
    return {"dataset_id": binding["dataset_id"], "candidate_id": cid, "instrument": instrument,
            "resolution": req["resolution"], "sha256": expected_sha, "row_count": count,
            "broker_symbol": mapping["broker_symbol"], "state": "VERIFIED_MATERIALIZED"}


def materialize_exact_csv(source_path: Path | str, destination_relative: str,
                          binding_metadata: Mapping[str, Any], requirements: Mapping[str, Any], *,
                          protected_start_utc: str, root: Path | str) -> dict[str, Any]:
    """Copy exact bytes only; never resample/fill/transform market data."""
    root = Path(root)
    source = Path(source_path)
    if not source.is_file():
        raise EvidenceError("source data bytes are not accessible")
    dest = _safe_path(root, destination_relative)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise EvidenceError("immutable materialization refuses overwrite")
    shutil.copyfile(source, dest)
    try:
        with dest.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fields = list(reader.fieldnames or [])
            rows = sum(1 for _ in reader)
        binding = dict(binding_metadata)
        binding.update({"schema": DATASET_BINDING_SCHEMA, "data_file": destination_relative,
                        "sha256": sha256_file(dest), "fields": fields, "row_count": rows})
        binding["binding_sha256"] = canonical_json_sha256(binding, exclude=("binding_sha256",))
        verify_dataset_binding(binding, requirements, protected_start_utc=protected_start_utc, root=root)
        return binding
    except Exception:
        dest.unlink(missing_ok=True)
        raise


def verify_cost_binding(binding: Mapping[str, Any], *, candidate_id: str, spec_hash: str) -> dict[str, Any]:
    if binding.get("schema") != COST_BINDING_SCHEMA:
        raise EvidenceError("unsupported cost binding schema")
    if binding.get("candidate_id") != candidate_id or binding.get("spec_hash") != spec_hash:
        raise EvidenceError("cost binding candidate/spec mismatch")
    state = binding.get("state")
    if state not in COST_STATES:
        raise EvidenceError("invalid cost-confidence state")
    if binding.get("prospectively_frozen") is not True:
        raise EvidenceError("cost binding not prospectively frozen")
    components = binding.get("components")
    if not isinstance(components, Mapping) or not components:
        raise EvidenceError("cost components missing")

    states = []
    for name, component in components.items():
        if not isinstance(component, Mapping):
            raise EvidenceError(f"{name}: invalid cost component")
        if component.get("applicable") is False:
            continue
        cstate = component.get("state")
        if cstate not in COST_STATES:
            raise EvidenceError(f"{name}: invalid component state")
        states.append(cstate)
        if cstate == VERIFIED:
            if component.get("historical") is not True or component.get("evidence_kind") == "CURRENT_SNAPSHOT":
                raise EvidenceError(f"{name}: VERIFIED requires historical evidence, not a snapshot")
            if not _sha(component.get("evidence_sha256")):
                raise EvidenceError(f"{name}: historical evidence hash missing")
            _text(component, "effective_interval", f"{name} cost")
        elif cstate == CONSERVATIVE_BOUND:
            if component.get("prospectively_frozen") is not True or component.get("bound_direction") != "ADVERSE_OR_EQUAL":
                raise EvidenceError(f"{name}: conservative bound is not frozen/adverse")
            if not _sha(component.get("basis_sha256")) or ("bound" not in component and "rule" not in component):
                raise EvidenceError(f"{name}: conservative-bound basis/value missing")
    if not states:
        raise EvidenceError("no applicable cost component")
    if state == VERIFIED and any(s != VERIFIED for s in states):
        raise EvidenceError("overall VERIFIED requires every component VERIFIED")
    if state == CONSERVATIVE_BOUND and (UNRESOLVED in states or CONSERVATIVE_BOUND not in states):
        raise EvidenceError("invalid overall CONSERVATIVE_BOUND composition")
    if state != UNRESOLVED and UNRESOLVED in states:
        raise EvidenceError("resolved overall state contains UNRESOLVED component")

    if binding.get("positive_financing_benefit_allowed", False):
        fin = components.get("financing")
        if not isinstance(fin, Mapping) or fin.get("applicable") is False or fin.get("state") != VERIFIED or fin.get("historical") is not True:
            raise EvidenceError("positive financing benefit requires historically VERIFIED financing")

    expected = binding.get("binding_sha256")
    actual = canonical_json_sha256(binding, exclude=("binding_sha256",))
    if not _sha(expected) or expected != actual:
        raise EvidenceError("cost binding hash mismatch")
    return {"candidate_id": candidate_id, "state": state, "binding_sha256": actual}


def gate_candidate_pre_outcome(*, candidate_id: str, spec_hash: str,
                               requirements: Mapping[str, Any], dataset_bindings: Sequence[Mapping[str, Any]],
                               cost_binding: Mapping[str, Any] | None, protected_start_utc: str,
                               root: Path | str) -> dict[str, Any]:
    """Deterministic gate only. This function never evaluates economics or writes the ledger."""
    reqs = requirements.get("requirements", {})
    if candidate_id not in reqs:
        raise EvidenceError(f"unknown candidate: {candidate_id}")
    required = list(reqs[candidate_id]["instruments"])
    by_instrument = {}
    for binding in dataset_bindings:
        if binding.get("candidate_id") != candidate_id:
            continue
        instrument = binding.get("instrument")
        if instrument in by_instrument:
            raise EvidenceError(f"{candidate_id}: duplicate binding for {instrument}")
        by_instrument[instrument] = binding
    missing = [x for x in required if x not in by_instrument]
    if missing:
        return {"candidate_id": candidate_id, "ready": False, "state": "DATA_BLOCKED", "missing_instruments": missing}

    verified = []
    broker_symbols = set()
    for instrument in required:
        item = verify_dataset_binding(by_instrument[instrument], requirements,
                                      protected_start_utc=protected_start_utc, root=root)
        if item["broker_symbol"] in broker_symbols:
            raise EvidenceError(f"{candidate_id}: broker mapping is not one-to-one")
        broker_symbols.add(item["broker_symbol"])
        verified.append(item)
    if cost_binding is None:
        return {"candidate_id": candidate_id, "ready": False, "state": "COST_BLOCKED", "datasets": verified}
    cost = verify_cost_binding(cost_binding, candidate_id=candidate_id, spec_hash=spec_hash)
    if cost["state"] == UNRESOLVED:
        return {"candidate_id": candidate_id, "ready": False, "state": "COST_UNRESOLVED", "datasets": verified, "cost": cost}
    return {"candidate_id": candidate_id, "ready": True, "state": "PRE_OUTCOME_EVIDENCE_READY", "datasets": verified, "cost": cost}
