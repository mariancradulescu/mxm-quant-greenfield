"""Fail-closed pre-promotion validation for authoritative repository state."""
from __future__ import annotations

import compileall
import json
from pathlib import Path

from discovery.accounting import assert_current_state_matches_repository
from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.ledger import read_ledger
from discovery.schema import validate_result

ROOT = Path(__file__).resolve().parents[1]
PATH_PREFIXES = ("data/", "discovery/", "evidence/", "m6/", "m7/", "competition/", "tests/", "tools/")


def _json_files():
    for path in ROOT.rglob("*.json"):
        if ".git" not in path.parts:
            yield path


def _walk_refs(value):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_refs(nested)
    elif isinstance(value, str):
        yield value


def main() -> int:
    if not compileall.compile_dir(str(ROOT), quiet=1, force=True):
        raise SystemExit("Python compilation failed")

    for path in _json_files():
        json.loads(path.read_text(encoding="utf-8"))

    for path in sorted((ROOT / "discovery" / "candidates").glob("V2-C*.json")):
        verify_spec_hash(json.loads(path.read_text(encoding="utf-8")))

    for path in sorted((ROOT / "discovery" / "results").glob("V2-C*_STAGE_A_*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        validate_result(result)
        if result.get("result_hash") != compute_result_hash(result):
            raise ValueError(f"result_hash mismatch: {path.relative_to(ROOT)}")

    read_ledger(ROOT / "discovery" / "ledger.jsonl")
    accounting = assert_current_state_matches_repository(ROOT)

    state = json.loads((ROOT / "CURRENT_STATE.json").read_text(encoding="utf-8"))
    for ref in _walk_refs(state):
        if not ref.startswith(PATH_PREFIXES):
            continue
        if any(token in ref for token in ("*", "{", "}")):
            continue
        if not ref.endswith((".json", ".py", ".txt")):
            continue
        if not (ROOT / ref).exists():
            raise ValueError(f"repository-local reference missing: {ref}")

    print("AUTHORITATIVE_PROMOTION_VALIDATION_PASS", accounting)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
