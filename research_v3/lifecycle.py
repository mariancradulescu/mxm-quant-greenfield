"""Generic candidate lifecycle interpretation for versioned V2 research results."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

from discovery.canonical import compute_result_hash
from discovery.ledger import read_ledger
from discovery.schema import validate_result

FREEZE_TYPES = {"CANDIDATE_FROZEN", "CANDIDATE_REFROZEN_PRE_OUTCOME"}

class LifecycleError(ValueError):
    pass

@dataclass(frozen=True)
class ResultVersion:
    row: dict[str, Any]
    correction_row: dict[str, Any] | None

    @property
    def result(self) -> dict[str, Any]:
        return self.row["payload"]["result"]

    @property
    def result_hash(self) -> str:
        return self.row["payload"]["result_hash"]

    @property
    def correction_id(self) -> str | None:
        payload = self.row.get("payload") or {}
        if isinstance(payload.get("correction_id"), str):
            return payload["correction_id"]
        if self.correction_row is None:
            return None
        cp = self.correction_row.get("payload") or {}
        value = cp.get("correction_id")
        return value if isinstance(value, str) else None

@dataclass(frozen=True)
class CandidateLifecycle:
    candidate_id: str
    rows: tuple[dict[str, Any], ...]
    freezes: tuple[dict[str, Any], ...]
    corrections: tuple[dict[str, Any], ...]
    results: tuple[ResultVersion, ...]

    @property
    def initial_result(self) -> ResultVersion | None:
        return self.results[0] if self.results else None

    @property
    def current_result(self) -> ResultVersion | None:
        return self.results[-1] if self.results else None

    @property
    def successor_count(self) -> int:
        return max(0, len(self.results) - 1)

    @property
    def incomplete_corrections(self) -> tuple[dict[str, Any], ...]:
        linked = {rv.correction_row["sequence"] for rv in self.results if rv.correction_row is not None}
        return tuple(row for row in self.corrections if row["sequence"] not in linked)

def _verify_result_row(row: Mapping[str, Any], candidate_id: str) -> None:
    payload = row.get("payload")
    if not isinstance(payload, Mapping) or not isinstance(payload.get("result"), Mapping):
        raise LifecycleError(f"{candidate_id}: RESULT_RECORDED missing result payload")
    result = dict(payload["result"])
    validate_result(result)
    if result.get("candidate_id") != candidate_id:
        raise LifecycleError(f"{candidate_id}: result payload identity mismatch")
    expected = compute_result_hash(result)
    if payload.get("result_hash") != expected or result.get("result_hash") != expected:
        raise LifecycleError(f"{candidate_id}: result hash mismatch at sequence {row.get('sequence')}")
    if row.get("spec_hash") != result.get("spec_hash"):
        raise LifecycleError(f"{candidate_id}: result row/spec mismatch")

def candidate_lifecycle(ledger: Iterable[Mapping[str, Any]], candidate_id: str) -> CandidateLifecycle:
    rows = tuple(dict(row) for row in ledger if row.get("candidate_id") == candidate_id)
    freezes = tuple(row for row in rows if row.get("entry_type") in FREEZE_TYPES)
    corrections = tuple(row for row in rows if row.get("entry_type") == "IMPLEMENTATION_CORRECTION")
    result_rows = [row for row in rows if row.get("entry_type") == "RESULT_RECORDED"]
    if result_rows and not freezes:
        raise LifecycleError(f"{candidate_id}: result exists without frozen identity")

    versions: list[ResultVersion] = []
    previous_result_seq = -1
    used_correction_sequences: set[int] = set()
    correction_ids: set[str] = set()
    for index, row in enumerate(result_rows):
        _verify_result_row(row, candidate_id)
        seq = int(row["sequence"])
        eligible = [corr for corr in corrections if previous_result_seq < int(corr["sequence"]) < seq]
        correction = eligible[-1] if eligible else None
        if index > 0 and correction is None:
            raise LifecycleError(
                f"{candidate_id}: successor RESULT_RECORDED at sequence {seq} lacks intervening IMPLEMENTATION_CORRECTION"
            )
        if correction is not None:
            cseq = int(correction["sequence"])
            if cseq in used_correction_sequences:
                raise LifecycleError(f"{candidate_id}: one correction links multiple successors")
            used_correction_sequences.add(cseq)
            cp = correction.get("payload") or {}
            correction_id = cp.get("correction_id") or (row.get("payload") or {}).get("correction_id")
            if isinstance(correction_id, str):
                if correction_id in correction_ids:
                    raise LifecycleError(f"{candidate_id}: duplicate correction_id {correction_id}")
                correction_ids.add(correction_id)
            if cp.get("new_v2_attempt_consumed") is True or cp.get("search_budget_delta") not in (None, 0):
                raise LifecycleError(f"{candidate_id}: same-identity correction consumed search budget")
        versions.append(ResultVersion(row=row, correction_row=correction))
        previous_result_seq = seq

    return CandidateLifecycle(
        candidate_id=candidate_id,
        rows=rows,
        freezes=freezes,
        corrections=corrections,
        results=tuple(versions),
    )

def find_result_version(lifecycle: CandidateLifecycle, result_hash: str) -> ResultVersion:
    matches = [rv for rv in lifecycle.results if rv.result_hash == result_hash]
    if len(matches) != 1:
        raise LifecycleError(
            f"{lifecycle.candidate_id}: expected exactly one result version for {result_hash}, found {len(matches)}"
        )
    return matches[0]

def validate_current_authority(root: str | Path, state: Mapping[str, Any], lifecycle: CandidateLifecycle) -> ResultVersion | None:
    root = Path(root)
    node = (state.get("current_result_authority") or {}).get(lifecycle.candidate_id, {})
    stage_a = node.get("stage_a") if isinstance(node, Mapping) else None
    if not isinstance(stage_a, Mapping):
        return None
    result_hash = stage_a.get("result_hash")
    result_ref = stage_a.get("result_ref")
    if not isinstance(result_hash, str) or not isinstance(result_ref, str):
        return None
    version = find_result_version(lifecycle, result_hash)
    path = root / result_ref
    if not path.is_file():
        raise LifecycleError(f"{lifecycle.candidate_id}: current result_ref missing: {result_ref}")
    standalone = json.loads(path.read_text(encoding="utf-8"))
    validate_result(standalone)
    if standalone != version.result:
        raise LifecycleError(f"{lifecycle.candidate_id}: current standalone result differs from ledger authority")
    return version

def repository_lifecycle_summary(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    ledger = read_ledger(root / "discovery/ledger.jsonl")
    state = json.loads((root / "CURRENT_STATE.json").read_text(encoding="utf-8"))
    candidate_ids = sorted({
        row["candidate_id"] for row in ledger
        if row.get("entry_type") == "RESULT_RECORDED" and str(row.get("candidate_id", "")).startswith("V2-C")
    })
    lifecycles = {cid: candidate_lifecycle(ledger, cid) for cid in candidate_ids}
    incomplete = {
        cid: [row["sequence"] for row in lc.incomplete_corrections]
        for cid, lc in lifecycles.items() if lc.incomplete_corrections
    }
    current_hashes: dict[str, str] = {}
    for cid, lc in lifecycles.items():
        current = validate_current_authority(root, state, lc)
        if current is not None:
            current_hashes[cid] = current.result_hash
    result_rows = sum(len(lc.results) for lc in lifecycles.values())
    successor_rows = sum(lc.successor_count for lc in lifecycles.values())
    return {
        "candidate_ids": candidate_ids,
        "distinct_identity_outcomes_opened": len(candidate_ids),
        "stage_a_result_recorded_entries": result_rows,
        "same_identity_successor_result_entries": successor_rows,
        "implementation_correction_entries": sum(len(lc.corrections) for lc in lifecycles.values()),
        "incomplete_corrections": incomplete,
        "current_result_hashes": current_hashes,
        "ledger_entries": len(ledger),
        "ledger_tail_entry_hash": ledger[-1]["entry_hash"] if ledger else None,
    }
