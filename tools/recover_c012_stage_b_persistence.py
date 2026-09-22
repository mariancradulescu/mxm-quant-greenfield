"""Recover the already-opened corrected C012 Stage-B result from versioned Base64 bytes.

Persistence-only recovery. This module MUST NOT execute economic simulation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

from discovery.accounting import assert_current_state_matches_repository
from discovery.canonical import canonical_json, compute_result_hash
from m6.c012_corrected_stage_b_runner import (
    AUTHORIZATION_REF,
    CORRECTED_STAGE_B_REF,
    RUNNER_REF,
    project_current_state_after_successor,
    validate_corrected_c012_stage_b_result,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FRAGMENT_COUNT = 20
EXPECTED_BASE64_CHARS = 38236
EXPECTED_BYTES = 28676
EXPECTED_ARTIFACT_SHA256 = "c7aac56699eee738da022926b2992be653d08d190983cd128a5e14087ebc98d1"
EXPECTED_RESULT_HASH = "91c9306b594110a2ae8cac25acdd10ecb6d7949f2cda7f2331ae9f514059f287"
EXPECTED_OPERATIONAL_HEAD = "67228568317621ffe536b7744537beb7398f2c74"


def _load_staged_bytes() -> bytes:
    fragments = []
    for i in range(1, EXPECTED_FRAGMENT_COUNT + 1):
        path = ROOT / ".persist_tmp" / f"c012.b64.{i:02d}"
        if not path.is_file():
            raise RuntimeError(f"missing persistence fragment: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="ascii")
        if any(ch.isspace() for ch in text):
            raise RuntimeError(f"unexpected whitespace in persistence fragment {i:02d}")
        expected_len = 236 if i == EXPECTED_FRAGMENT_COUNT else 2000
        if len(text) != expected_len:
            raise RuntimeError(f"fragment {i:02d} length {len(text)} != {expected_len}")
        fragments.append(text)
    joined = "".join(fragments)
    if len(joined) != EXPECTED_BASE64_CHARS:
        raise RuntimeError("staged Base64 length mismatch")
    raw = base64.b64decode(joined, validate=True)
    if len(raw) != EXPECTED_BYTES:
        raise RuntimeError("decoded corrected C012 Stage-B byte length mismatch")
    if hashlib.sha256(raw).hexdigest() != EXPECTED_ARTIFACT_SHA256:
        raise RuntimeError("corrected C012 Stage-B artifact SHA256 mismatch")
    return raw


def _verify_result(raw: bytes) -> dict:
    obj = json.loads(raw)
    if canonical_json(obj).encode("utf-8") != raw:
        raise RuntimeError("corrected C012 Stage-B bytes are not canonical JSON")
    if obj.get("result_hash") != EXPECTED_RESULT_HASH:
        raise RuntimeError("corrected C012 Stage-B stored result_hash drift")
    if compute_result_hash(obj) != EXPECTED_RESULT_HASH:
        raise RuntimeError("corrected C012 Stage-B canonical result_hash mismatch")
    validate_corrected_c012_stage_b_result(obj)

    economics = obj.get("economic_summary", {})
    metrics = obj.get("performance_metrics", {})
    exact = {
        "candidate_id": obj.get("candidate_id") == "V2-C012",
        "starting_equity": economics.get("starting_equity_eur") == 200.0,
        "terminal_equity": economics.get("final_equity_eur") == 275.0412454262676,
        "absolute_pnl": economics.get("absolute_net_return_eur") == 75.0412454262676,
        "return_pct": economics.get("net_return_pct") == 37.5206227131338,
        "executions": economics.get("executed_trades") == 34,
        "margin_rejects": economics.get("margin_blocked_trades") == 0,
        "max_drawdown": economics.get("maximum_drawdown_eur") == 65.540820612669,
        "min_free_margin": metrics.get("minimum_sampled_free_margin_eur") == 65.2732923716486,
        "hard21": metrics.get("hard21_actual_execution", {}).get("status") == "NOT_MET",
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise RuntimeError(f"corrected C012 Stage-B economic-field drift: {failed}")
    return obj


def main() -> int:
    raw = _load_staged_bytes()
    result = _verify_result(raw)
    target = ROOT / CORRECTED_STAGE_B_REF
    state_path = ROOT / "CURRENT_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    if state.get("v2_attempts_used") != 9 or state.get("v2_search_budget_remaining") != 75:
        raise RuntimeError("V2 same-identity accounting drift before persistence recovery")
    if state.get("protected_evidence_opened") is not False:
        raise RuntimeError("protected evidence must remain closed")
    if state.get("live_orders_authorized") is not False or state.get("competition_start_authorized") is not False:
        raise RuntimeError("live/competition authorization drift")

    if target.exists():
        if target.read_bytes() != raw:
            raise RuntimeError("existing corrected Stage-B successor differs from recovered canonical bytes")
        validate_corrected_c012_stage_b_result(json.loads(target.read_text(encoding="utf-8")))
        downstream = state["current_result_authority"]["V2-C012"]["stage_b_current_config"]
        if (
            downstream.get("corrected_successor_ref") != CORRECTED_STAGE_B_REF
            or downstream.get("corrected_successor_hash") != EXPECTED_RESULT_HASH
        ):
            raise RuntimeError("existing successor is not projected into CURRENT_STATE")
        print("C012_STAGE_B_PERSISTENCE_RECOVERY_NOOP_VERIFIED")
        return 0

    ledger_path = ROOT / "discovery" / "ledger.jsonl"
    ledger_sha_before = hashlib.sha256(ledger_path.read_bytes()).hexdigest()

    projected = project_current_state_after_successor(state, result)
    projected["phase"] = "C012_CORRECTED_STAGE_B_RECORDED_PENDING_EXACT_HEAD_GREEN"
    projected["next_action"] = (
        "Run exact-head full suite; after GREEN preserve C012 as valid EUR200-realizable primitive, "
        "remove temporary persistence scaffolding, promote the exact GREEN operational tree, and "
        "bootstrap Performance Research V3 without consuming another V2 attempt."
    )
    corrected = projected["c012_same_identity_corrected_rerun"]["corrected_stage_b"]
    corrected.update({
        "status": "CORRECTED_STAGE_B_RECORDED_CURRENT_SUCCESSOR_PENDING_EXACT_HEAD_GREEN",
        "corrected_stage_b_artifact_sha256": EXPECTED_ARTIFACT_SHA256,
        "corrected_stage_b_byte_length": EXPECTED_BYTES,
        "persistence_recovery": {
            "status": "RECOVERED_FROM_VERSIONED_BASE64_FRAGMENTS_NO_ECONOMIC_RERUN",
            "source_head": os.environ.get("GITHUB_SHA"),
            "fragment_count": EXPECTED_FRAGMENT_COUNT,
            "base64_char_count": EXPECTED_BASE64_CHARS,
            "canonical_result_hash_verified": True,
            "artifact_sha256_verified": True,
            "economic_rerun_performed": False,
            "additional_v2_attempts_consumed": 0,
            "ledger_mutation_required": False,
            "ledger_sha256_unchanged": ledger_sha_before,
        },
        "economic_rerun_performed": False,
        "new_v2_attempt_consumed": False,
        "search_budget_decrement": 0,
        "protected_evidence_opened": False,
    })

    operational = projected.get("operational_branch_authority", {})
    operational["branch"] = "competition-performance-v1-20260921"
    operational["work_branch"] = "c012-stage-b-persist-staging-20260922"
    operational["reconciled_parent_head"] = EXPECTED_OPERATIONAL_HEAD
    projected["authoritative_branch"] = "competition-performance-v1-20260921"

    refs = list(projected.get("current_authority_refs", []))
    for ref in (AUTHORIZATION_REF, RUNNER_REF, CORRECTED_STAGE_B_REF):
        if ref not in refs:
            refs.append(ref)
    projected["current_authority_refs"] = refs

    if projected.get("v2_attempts_used") != 9 or projected.get("v2_search_budget_remaining") != 75:
        raise RuntimeError("V2 accounting changed during corrected Stage-B projection")
    if projected.get("protected_evidence_opened") is not False:
        raise RuntimeError("protected evidence opened during corrected Stage-B projection")
    if projected.get("live_orders_authorized") is not False or projected.get("competition_start_authorized") is not False:
        raise RuntimeError("authorization changed during corrected Stage-B projection")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    state_path.write_text(json.dumps(projected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if hashlib.sha256(ledger_path.read_bytes()).hexdigest() != ledger_sha_before:
        raise RuntimeError("Discovery ledger changed during Stage-B persistence recovery")
    derived = assert_current_state_matches_repository(ROOT)
    if derived["v2_attempts_used"] != 9 or derived["v2_search_budget_remaining"] != 75:
        raise RuntimeError("derived accounting changed during Stage-B persistence recovery")

    print("C012_STAGE_B_PERSISTENCE_RECOVERY_PASS", {
        "result_ref": CORRECTED_STAGE_B_REF,
        "result_hash": EXPECTED_RESULT_HASH,
        "artifact_sha256": EXPECTED_ARTIFACT_SHA256,
        "bytes": EXPECTED_BYTES,
        "v2_attempts_used": derived["v2_attempts_used"],
        "v2_search_budget_remaining": derived["v2_search_budget_remaining"],
        "economic_rerun_performed": False,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
