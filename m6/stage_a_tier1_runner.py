"""Prepared first M6 Stage-A runner for V2-C006 and V2-C012.

The runner is intentionally PREPARED / NOT AUTHORIZED TO EXECUTE by this repository state.
Repository authorities and external evidence bytes are hash-gated.  The pre-economic plan
uses frozen candidate replay, the corrected Nasdaq calendar, causal USD->EUR conversion and
transaction-local Tier-1 cost evidence.  No result file is written by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from discovery.canonical import verify_spec_hash
from .causal_conversion import CausalConversionSeries, quote_to_eur_rate
from .session_replay import NasdaqCashCalendar
from .tier1_candidate_replay import (
    C006_HASH,
    C012_HASH,
    ReplayIntent,
    c006_replay_intents,
    c012_replay_intents,
)
from .transaction_local_cost import (
    CostEvidenceUnavailable,
    TransactionCostEvidence,
    load_c012_transaction_local_index,
    load_us500_transaction_local_index,
    sha256_file,
)

CANDIDATE_HASHES = {
    "V2-C006": "75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49",
    "V2-C012": "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845",
}

REPOSITORY_GIT_BLOB_AUTHORITIES = {
    "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json": "7eb74ed9e97e7b2bf2c285737883f9b10d0432cf",
    "data/PRIMARY_WAVE_02_CAPTURE_ACCEPTANCE_V1.json": "1d59b64a8619d8c62de0a5564208cabd5c590bd0",
    "data/TIER1_COST_EVIDENCE_CAPTURE_ACCEPTANCE_V1.json": "e6d3331ae5281b8c005cfe783a057fee8209e0c2",
    "data/TIER1_PREOPEN_0930_SUPPLEMENT_ACCEPTANCE_V1.json": "2af3079ba5da1ec05b8c5c152151396f1424ffbb",
    "discovery/candidates/V2-C006.json": "a5a6e4865206a0f85afcae28a65004e1e24a8277",
    "discovery/candidates/V2-C012.json": "a9a8464d9cf161c3dcae39536280089058e882d9",
    "evidence/C012_DISCOVERY_COST_APPLICABILITY_GATE_V1.json": "6e30763c752ac8aa172ebabb52168169d98c6330",
    "evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json": "64bc7a000e750cd29710b372c4e5587f1610668a",
    "evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V4.json": "fbcc1dbe911908796d1d2ea8f62853cfe7415736",
    "data/PRIMARY_WAVE_02_PRE_M6_READINESS_V7.json": "5633acefd42814ff6301a291825e0ca5ae514553",
    "m6/causal_conversion.py": "ba29e02a2250294d2c48a3cfc7b15d1f298250be",
    "m6/tier1_candidate_replay.py": "028fa4b5bdac1058afa5ffb3e21f40ab299bf1f7",
    "m6/transaction_local_cost.py": "10db6e016139c29262bdce0ceb29db713f632edb",
}

EXTERNAL_INPUT_SHA256 = {
    "us500_m15": "e62aff5634ee2c3b9f3cbea3766a68d7a4a68b64ec9727aaa8cc757e2834fe87",
    "nas100_m15": "f92330927b0f41c3f6502951dbe512aa11449184916634c80e8f67f3c217eb7c",
    "eurusd_m15": "bce32af6ef251115d0628d746af16849a7ac23d7185a716670b0b22a4f09adde",
    "us500_transaction_local_cost": "601eedcb147021fff54f4d3bd2a43d831c455a821ddafa01a0036afe5c5485d6",
    "nas100_c012_transaction_local_cost": "dd4f6be917773fc580d4725d7c30ef4aabd5ec4ce19a30fdced8c5a85f4bd999",
}


class StageARunnerIntegrityError(ValueError):
    pass


class StageAExecutionNotAuthorized(PermissionError):
    pass


@dataclass(frozen=True)
class StageAInputPaths:
    us500_m15: Path
    nas100_m15: Path
    eurusd_m15: Path
    us500_transaction_local_cost: Path
    nas100_c012_transaction_local_cost: Path


@dataclass(frozen=True)
class PreparedTrade:
    intent: ReplayIntent
    entry_cost_evidence: TransactionCostEvidence
    exit_cost_evidence: TransactionCostEvidence
    entry_usd_to_eur_rate: Decimal
    exit_usd_to_eur_rate: Decimal


@dataclass(frozen=True)
class PreparedCandidate:
    candidate_id: str
    spec_hash: str
    cost_state: str
    trades: tuple[PreparedTrade, ...]
    unresolved_reason: str | None


@dataclass(frozen=True)
class StageAPreEconomicPlan:
    c006: PreparedCandidate
    c012: PreparedCandidate
    economics_computed: bool = False


@dataclass(frozen=True)
class CandidateEconomicSummary:
    candidate_id: str
    spec_hash: str
    event_count: int
    gross_pnl_eur: Decimal
    transaction_cost_eur: Decimal
    coarse_net_pnl_eur: Decimal


def _git_blob_sha_bytes(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def verify_repository_authorities(repo_root: Path | str) -> None:
    root = Path(repo_root)
    for rel, expected in REPOSITORY_GIT_BLOB_AUTHORITIES.items():
        path = root / rel
        if not path.is_file():
            raise StageARunnerIntegrityError(f"missing authority: {rel}")
        actual = _git_blob_sha_bytes(path.read_bytes())
        if actual != expected:
            raise StageARunnerIntegrityError(
                f"authority blob mismatch {rel}: expected {expected}, got {actual}"
            )

    for candidate_id, expected_hash in CANDIDATE_HASHES.items():
        spec = json.loads(
            (root / f"discovery/candidates/{candidate_id}.json").read_text(encoding="utf-8")
        )
        if spec.get("spec_hash") != expected_hash or not verify_spec_hash(spec):
            raise StageARunnerIntegrityError(f"{candidate_id} frozen spec hash mismatch")

    if C006_HASH != CANDIDATE_HASHES["V2-C006"] or C012_HASH != CANDIDATE_HASHES["V2-C012"]:
        raise StageARunnerIntegrityError("candidate replay source hash constants mismatch")

    readiness = json.loads(
        (root / "data/PRIMARY_WAVE_02_PRE_M6_READINESS_V7.json").read_text(encoding="utf-8")
    )
    if readiness.get("first_runner_execution_authorized") is not False:
        raise StageARunnerIntegrityError(
            "pre-outcome readiness must keep first runner execution unauthorized"
        )


def verify_external_inputs(paths: StageAInputPaths) -> None:
    for field, expected in EXTERNAL_INPUT_SHA256.items():
        path = getattr(paths, field)
        if not Path(path).is_file():
            raise StageARunnerIntegrityError(f"missing external input: {field} -> {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise StageARunnerIntegrityError(
                f"external input sha256 mismatch {field}: expected {expected}, got {actual}"
            )


def _csv_rows(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _to_decimal_rate(rate: float) -> Decimal:
    return Decimal(str(rate))


def _prepare_candidate(
    candidate_id: str,
    intents: Sequence[ReplayIntent],
    *,
    cost_index: Any,
    eurusd: CausalConversionSeries,
) -> PreparedCandidate:
    prepared: list[PreparedTrade] = []
    for intent in intents:
        try:
            entry_evidence = cost_index.evidence_for(intent.entry_utc)
            exit_evidence = cost_index.evidence_for(intent.exit_utc)
        except CostEvidenceUnavailable as exc:
            return PreparedCandidate(
                candidate_id=candidate_id,
                spec_hash=CANDIDATE_HASHES[candidate_id],
                cost_state="UNRESOLVED",
                trades=(),
                unresolved_reason=str(exc),
            )

        entry_rate, _ = quote_to_eur_rate("USD", intent.entry_utc, eurusd=eurusd)
        exit_rate, _ = quote_to_eur_rate("USD", intent.exit_utc, eurusd=eurusd)
        prepared.append(PreparedTrade(
            intent=intent,
            entry_cost_evidence=entry_evidence,
            exit_cost_evidence=exit_evidence,
            entry_usd_to_eur_rate=_to_decimal_rate(entry_rate),
            exit_usd_to_eur_rate=_to_decimal_rate(exit_rate),
        ))

    return PreparedCandidate(
        candidate_id=candidate_id,
        spec_hash=CANDIDATE_HASHES[candidate_id],
        cost_state="CONSERVATIVE_BOUND",
        trades=tuple(prepared),
        unresolved_reason=None,
    )


def build_pre_economic_plan(
    repo_root: Path | str,
    paths: StageAInputPaths,
) -> StageAPreEconomicPlan:
    """Generate deterministic intents + applicable precomputed cost rows, but no PnL."""
    verify_repository_authorities(repo_root)
    verify_external_inputs(paths)

    root = Path(repo_root)
    calendar = NasdaqCashCalendar.from_artifact(
        root / "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json"
    )
    us500_rows = _csv_rows(paths.us500_m15)
    nas100_rows = _csv_rows(paths.nas100_m15)
    eurusd = CausalConversionSeries.from_rows("EURUSD", _csv_rows(paths.eurusd_m15))

    c006_intents = c006_replay_intents(us500_rows, calendar)
    c012_intents = c012_replay_intents(us500_rows, nas100_rows, calendar)

    us500_cost = load_us500_transaction_local_index(paths.us500_transaction_local_cost)
    nas100_cost = load_c012_transaction_local_index(
        paths.nas100_c012_transaction_local_cost
    )

    return StageAPreEconomicPlan(
        c006=_prepare_candidate(
            "V2-C006", c006_intents, cost_index=us500_cost, eurusd=eurusd
        ),
        c012=_prepare_candidate(
            "V2-C012", c012_intents, cost_index=nas100_cost, eurusd=eurusd
        ),
        economics_computed=False,
    )


def _load_execution_authorization(path: Path | str | None) -> Mapping[str, Any]:
    if path is None:
        raise StageAExecutionNotAuthorized(
            "Stage-A economics require a separate explicit execution authorization artifact"
        )
    auth = json.loads(Path(path).read_text(encoding="utf-8"))
    if auth.get("schema") != "mxm.greenfield.v2.m6-stage-a-execution-authorization.v1":
        raise StageAExecutionNotAuthorized("invalid Stage-A execution authorization schema")
    if auth.get("status") != "AUTHORIZED":
        raise StageAExecutionNotAuthorized("Stage-A execution authorization is not active")
    if auth.get("candidate_spec_hashes") != CANDIDATE_HASHES:
        raise StageAExecutionNotAuthorized("authorization candidate hashes mismatch")
    if auth.get("transaction_local_cost_rule_git_blob_sha") != "64bc7a000e750cd29710b372c4e5587f1610668a":
        raise StageAExecutionNotAuthorized("authorization cost authority mismatch")
    if auth.get("protected_evidence_opened") is not False:
        raise StageAExecutionNotAuthorized("protected evidence must remain unopened")
    return auth


def _direction_sign(direction: str) -> Decimal:
    if direction in {"LONG", "LONG_NAS100"}:
        return Decimal("1")
    if direction in {"SHORT", "SHORT_NAS100"}:
        return Decimal("-1")
    raise StageARunnerIntegrityError(f"unsupported direction {direction}")


def _summarize_candidate(candidate: PreparedCandidate) -> CandidateEconomicSummary:
    if candidate.cost_state != "CONSERVATIVE_BOUND":
        raise StageARunnerIntegrityError(
            f"{candidate.candidate_id}: cannot compute economics with unresolved cost"
        )
    gross = Decimal("0")
    cost = Decimal("0")
    for trade in candidate.trades:
        intent = trade.intent
        sign = _direction_sign(intent.direction)
        entry_price = Decimal(str(intent.entry_price))
        exit_price = Decimal(str(intent.exit_price))
        quantity = Decimal("1000") / (entry_price * trade.entry_usd_to_eur_rate)
        gross_quote = sign * (exit_price - entry_price) * quantity
        gross += gross_quote * trade.exit_usd_to_eur_rate

        entry_points = trade.entry_cost_evidence.transaction_cost_proxy_points
        exit_points = trade.exit_cost_evidence.transaction_cost_proxy_points
        if entry_points is None or exit_points is None:
            raise StageARunnerIntegrityError("supported evidence missing transaction proxy")
        cost += (
            entry_points * quantity * trade.entry_usd_to_eur_rate
            + exit_points * quantity * trade.exit_usd_to_eur_rate
        )
    return CandidateEconomicSummary(
        candidate_id=candidate.candidate_id,
        spec_hash=candidate.spec_hash,
        event_count=len(candidate.trades),
        gross_pnl_eur=gross,
        transaction_cost_eur=cost,
        coarse_net_pnl_eur=gross - cost,
    )


def execute_stage_a_in_memory(
    repo_root: Path | str,
    paths: StageAInputPaths,
    *,
    authorization_path: Path | str | None,
) -> tuple[CandidateEconomicSummary, CandidateEconomicSummary]:
    """Future execution entrypoint. It writes no result files and is currently unauthorized."""
    _load_execution_authorization(authorization_path)
    plan = build_pre_economic_plan(repo_root, paths)
    return _summarize_candidate(plan.c006), _summarize_candidate(plan.c012)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--validate-repository-only",
        action="store_true",
        help="Validate frozen repository authorities only; no candidate replay or economics.",
    )
    args = parser.parse_args(argv)
    if not args.validate_repository_only:
        raise StageAExecutionNotAuthorized(
            "This prepared runner defaults fail-closed. Use --validate-repository-only; "
            "economic execution requires a future explicit authorization artifact."
        )
    verify_repository_authorities(args.repo_root)
    print("M6_STAGE_A_TIER1_RUNNER_PREPARED_NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
