"""Canonical serialization and semantic hashing for V2 candidate specifications."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .schema import validate_candidate_spec

_NON_SEMANTIC_FIELDS = {"rationale", "provenance", "spec_hash"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def semantic_payload(spec: Mapping[str, Any]) -> dict:
    return {key: value for key, value in spec.items() if key not in _NON_SEMANTIC_FIELDS}


def compute_spec_hash(spec: Mapping[str, Any]) -> str:
    payload = semantic_payload(spec)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def freeze_spec(spec: Mapping[str, Any]) -> dict:
    frozen = dict(spec)
    frozen["spec_hash"] = compute_spec_hash(frozen)
    validate_candidate_spec(frozen)
    return frozen


def verify_spec_hash(spec: Mapping[str, Any]) -> bool:
    validate_candidate_spec(spec)
    expected = compute_spec_hash(spec)
    if spec["spec_hash"] != expected:
        raise ValueError(f"spec_hash mismatch: expected {expected}, got {spec['spec_hash']}")
    return True


def compute_result_hash(result: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in result.items() if key != "result_hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
