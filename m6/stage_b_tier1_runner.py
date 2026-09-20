"""Fail-closed Stage-B structural runner preparation.

This runner may materialize the already-frozen Stage-A survivor intents/cost contexts and
validate current broker structural diagnostics, but it may not open Stage-B economics unless:
1) a separately frozen Stage-B execution authorization is supplied; and
2) a separately frozen applicable conservative historical margin authority is supplied.

CLI economic execution is intentionally disabled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .stage_a_tier1_runner import (
    CANDIDATE_HASHES,
    StageAInputPaths,
    build_pre_economic_plan,
    verify_pre_economic_materialization,
)
from .stage_b_evaluator import FIXED_VOLUME_CENTS, validate_margin_authority

EXPECTED_MARGIN_SHA256 = "08a5643687d4be0fb4f97422e13104c5b9eb08357932bad2463388c368140c9d"
SYMBOL_METADATA_SHA256 = "6427658afc8e3c7e710e843f4b1b2421dca4da9984f427dd966888f15314a583"
EXPECTED_CURRENT_MARGIN_DIAGNOSTIC = {
    "V2-C006": {"symbol": "US500", "volume_cents": 10, "buy_margin_minor": 3338, "sell_margin_minor": 3338, "money_digits": 2},
    "V2-C012": {"symbol": "NAS100", "volume_cents": 10, "buy_margin_minor": 12904, "sell_margin_minor": 12903, "money_digits": 2},
}


class StageBRunnerIntegrityError(ValueError):
    pass


class StageBExecutionNotAuthorized(PermissionError):
    pass


def sha256_file(path: Path | str) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_current_margin_diagnostic(expected_margin_path: Path | str, symbol_metadata_path: Path | str) -> dict[str, Any]:
    if sha256_file(expected_margin_path) != EXPECTED_MARGIN_SHA256:
        raise StageBRunnerIntegrityError("expected-margin evidence SHA256 mismatch")
    if sha256_file(symbol_metadata_path) != SYMBOL_METADATA_SHA256:
        raise StageBRunnerIntegrityError("symbol metadata SHA256 mismatch")
    margin=json.loads(Path(expected_margin_path).read_text(encoding="utf-8"))
    meta=json.loads(Path(symbol_metadata_path).read_text(encoding="utf-8"))
    out={}
    for cid, expected in EXPECTED_CURRENT_MARGIN_DIAGNOSTIC.items():
        symbol=expected["symbol"]
        node=margin[symbol]
        if node.get("approximate_formula_used") is not False:
            raise StageBRunnerIntegrityError("approximate margin arithmetic is forbidden")
        if node.get("order_placed") is not False:
            raise StageBRunnerIntegrityError("read-only structural capture must not place orders")
        if node.get("volume_cents") != expected["volume_cents"]:
            raise StageBRunnerIntegrityError("current margin volume mismatch")
        row=node["margin"][0]
        if int(row["volume"]) != expected["volume_cents"]:
            raise StageBRunnerIntegrityError("expected margin response volume mismatch")
        if int(row["buyMargin"]) != expected["buy_margin_minor"] or int(row["sellMargin"]) != expected["sell_margin_minor"]:
            raise StageBRunnerIntegrityError("current expected-margin amount drift")
        if int(node["money_digits"]) != expected["money_digits"]:
            raise StageBRunnerIntegrityError("moneyDigits drift")
        sm=meta[symbol]
        if int(sm["symbolId"]) not in (126,127):
            raise StageBRunnerIntegrityError("symbol identity drift")
        if int(sm["minVolume"]) != FIXED_VOLUME_CENTS[cid] or int(sm["stepVolume"]) != FIXED_VOLUME_CENTS[cid]:
            raise StageBRunnerIntegrityError("minimum/step volume drift")
        out[cid]={
            "symbol":symbol,
            "volume_cents":expected["volume_cents"],
            "buy_margin_eur":int(row["buyMargin"])/(10**expected["money_digits"]),
            "sell_margin_eur":int(row["sellMargin"])/(10**expected["money_digits"]),
            "historical_causal_margin_state":"UNRESOLVED_CURRENT_STRUCTURAL_DIAGNOSTIC_ONLY",
        }
    return out


def build_stage_b_pre_economic_plan(
    repo_root: Path | str,
    paths: StageAInputPaths,
    *,
    expected_margin_path: Path | str,
    symbol_metadata_path: Path | str,
) -> dict[str, Any]:
    stage_a_plan=build_pre_economic_plan(repo_root, paths)
    manifest=verify_pre_economic_materialization(stage_a_plan)
    margin=verify_current_margin_diagnostic(expected_margin_path, symbol_metadata_path)
    return {
        "stage_a_pre_economic_plan":stage_a_plan,
        "intent_manifest":manifest,
        "current_margin_diagnostic":margin,
        "stage_b_economics_computed":False,
        "historical_margin_authority_present":False,
    }


def execute_stage_b_full_in_memory(*args, authorization: Mapping[str, Any] | None=None, margin_authority: Mapping[str, Any] | None=None, **kwargs):
    if authorization is None:
        raise StageBExecutionNotAuthorized("Stage-B economic execution requires a separate frozen authorization")
    if authorization.get("status") != "AUTHORIZED":
        raise StageBExecutionNotAuthorized("Stage-B authorization is not active")
    if authorization.get("candidate_spec_hashes") != CANDIDATE_HASHES:
        raise StageBExecutionNotAuthorized("Stage-B authorization candidate binding mismatch")
    if authorization.get("protected_evidence_opened") is not False:
        raise StageBExecutionNotAuthorized("protected evidence must remain unopened")
    if margin_authority is None:
        raise StageBExecutionNotAuthorized("Stage-B requires separately frozen historical margin authority")
    validate_margin_authority(margin_authority)
    raise StageBExecutionNotAuthorized("economic execution path remains intentionally unopened in PREPARED_NOT_RUN state")


def main(argv: Sequence[str] | None=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--validate-repository-only", action="store_true")
    args=parser.parse_args(argv)
    if not args.validate_repository_only:
        raise StageBExecutionNotAuthorized("CLI Stage-B economics are intentionally disabled")
    root=Path(args.repo_root)
    state=json.loads((root/"CURRENT_STATE.json").read_text(encoding="utf-8"))
    if state.get("protected_evidence_opened") is not False:
        raise StageBRunnerIntegrityError("protected evidence must remain unopened")
    if state.get("v2_attempts_used") != 2 or state.get("economic_outcomes_opened") != 2:
        raise StageBRunnerIntegrityError("Stage-B preparation requires exactly the two already-opened Stage-A outcomes")
    if state.get("discovery_survivors") != ["V2-C006","V2-C012"]:
        raise StageBRunnerIntegrityError("Stage-B preparation survivor set drift")
    print("M6_STAGE_B_TIER1_EUR200_PREPARED_NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
