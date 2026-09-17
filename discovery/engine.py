"""Single generic declarative Discovery engine shell.

M3 freezes candidate semantics, verifies hashes, delegates economic evaluation
to one injected shared evaluator, validates the common result envelope, and can
append lifecycle evidence. It contains no candidate-specific strategy logic.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from .canonical import compute_result_hash, freeze_spec, verify_spec_hash
from .ledger import append_entry
from .schema import validate_result


class DiscoveryEngine:
    def __init__(self, *, ledger_path: Optional[str] = None):
        self.ledger_path = ledger_path

    def freeze_candidate(self, draft: Mapping[str, Any], *, persist: bool = False) -> dict:
        frozen = freeze_spec(draft)
        if persist:
            if not self.ledger_path:
                raise ValueError("ledger_path is required for persistence")
            append_entry(self.ledger_path, entry_type="CANDIDATE_FROZEN",
                         candidate_id=frozen["id"], spec_hash=frozen["spec_hash"],
                         payload={"provenance": frozen["provenance"]})
        return frozen

    def evaluate(self, spec: Mapping[str, Any], data: Any,
                 shared_evaluator: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
                 *, persist: bool = False) -> dict:
        verify_spec_hash(spec)
        result = dict(shared_evaluator(spec, data))
        validate_result(result)
        if result["candidate_id"] != spec["id"]:
            raise ValueError("result candidate_id does not match candidate spec")
        if result["spec_hash"] != spec["spec_hash"]:
            raise ValueError("result spec_hash does not match candidate spec")
        result["result_hash"] = compute_result_hash(result)
        if persist:
            if not self.ledger_path:
                raise ValueError("ledger_path is required for persistence")
            append_entry(self.ledger_path, entry_type="RESULT_RECORDED",
                         candidate_id=spec["id"], spec_hash=spec["spec_hash"],
                         payload={"result_hash": result["result_hash"],
                                  "status": result["status"], "stage": result["stage"]})
        return result
