"""Deterministic first M6 Stage-A runner for V2-C006 and V2-C012.

The runner is fail-closed.  It verifies repository authorities, exact external input hashes,
the frozen pre-economic intent manifest, transaction-local cost applicability and a separate
execution authorization before it may compute a full Stage-A result.  Protected evidence is
outside this runner's scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from discovery.canonical import verify_spec_hash
from discovery.schema import validate_result
from .causal_conversion import CausalConversionSeries, quote_to_eur_rate
from .session_replay import NasdaqCashCalendar
from .stage_a_evaluator import (
    EVALUATOR_VERSION,
    evaluate_prepared_candidate,
)
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
TRANSACTION_LOCAL_COST_RULE_GIT_BLOB = "64bc7a000e750cd29710b372c4e5587f1610668a"
EVALUATOR_POLICY_GIT_BLOB = "6c9999a7641b8f2299f1c4c5aab7ccb9e57c784a"
EVALUATOR_RUNTIME_GIT_BLOB = "05220fcadae6a74a7036e46f64ee1ad1411dc26f"
EVALUATOR_RUNTIME_SHA256 = "16e302dd3a9b58983cbfcb68ca0934c920ea8007fd11e9577685fa95f879874e"
PRE_ECONOMIC_MATERIALIZATION_GIT_BLOB = "f6b2407d0f8a5a42b239a9fd5953c70a83a09b88"

EXPECTED_INTENT_COUNTS = {"V2-C006": 108, "V2-C012": 35}
EXPECTED_INTENT_MANIFEST_SHA256 = {
    "V2-C006": "6e320849ba49136b5491ecab75bc0ce5c36715a2c2202ade9d97443b41b9a515",
    "V2-C012": "f9d0ba61346bbd9a1602fe84e73d4d374d27e9fdec0217906b2ac29f24218c8d",
}
EXPECTED_COMBINED_INTENT_MANIFEST_SHA256 = (
    "a897c7cd5310e6ccaf8ab28d225fd5c16b1ebf0f043a18242efa9c74981656e7"
)
EXPECTED_TRANSACTION_CONTEXT_COUNT = 286
C012_KNOWN_UNSUPPORTED_BOUNDARIES_MS = frozenset({
    1735675200000,
    1767211200000,
})

REPOSITORY_GIT_BLOB_AUTHORITIES = {
    "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json": "7eb74ed9e97e7b2bf2c285737883f9b10d0432cf",
    "data/PRIMARY_WAVE_02_CAPTURE_ACCEPTANCE_V1.json": "1d59b64a8619d8c62de0a5564208cabd5c590bd0",
    "data/TIER1_COST_EVIDENCE_CAPTURE_ACCEPTANCE_V1.json": "e6d3331ae5281b8c005cfe783a057fee8209e0c2",
    "data/TIER1_PREOPEN_0930_SUPPLEMENT_ACCEPTANCE_V1.json": "2af3079ba5da1ec05b8c5c152151396f1424ffbb",
    "discovery/candidates/V2-C006.json": "a5a6e4865206a0f85afcae28a65004e1e24a8277",
    "discovery/candidates/V2-C012.json": "a9a8464d9cf161c3dcae39536280089058e882d9",
    "evidence/C012_DISCOVERY_COST_APPLICABILITY_GATE_V1.json": "6e30763c752ac8aa172ebabb52168169d98c6330",
    "evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json": TRANSACTION_LOCAL_COST_RULE_GIT_BLOB,
    "evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V4.json": "fbcc1dbe911908796d1d2ea8f62853cfe7415736",
    "data/PRIMARY_WAVE_02_PRE_M6_READINESS_V7.json": "5633acefd42814ff6301a291825e0ca5ae514553",
    "data/M6_STAGE_A_TIER1_EVALUATOR_POLICY_V1.json": EVALUATOR_POLICY_GIT_BLOB,
    "evidence/M6_STAGE_A_TIER1_PRE_ECONOMIC_MATERIALIZATION_V1.json": PRE_ECONOMIC_MATERIALIZATION_GIT_BLOB,
    "m6/causal_conversion.py": "ba29e02a2250294d2c48a3cfc7b15d1f298250be",
    "m6/tier1_candidate_replay.py": "028fa4b5bdac1058afa5ffb3e21f40ab299bf1f7",
    "m6/transaction_local_cost.py": "10db6e016139c29262bdce0ceb29db713f632edb",
    "m6/stage_a_evaluator.py": EVALUATOR_RUNTIME_GIT_BLOB,
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


def _git_blob_sha_bytes(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _intent_record(intent: ReplayIntent) -> dict[str, Any]:
    return {
        "candidate_id": intent.candidate_id,
        "spec_hash": intent.spec_hash,
        "direction": intent.direction,
        "decision_utc": _z(intent.decision_utc),
        "entry_utc": _z(intent.entry_utc),
        "entry_price": float(intent.entry_price),
        "exit_utc": _z(intent.exit_utc),
        "exit_price": float(intent.exit_price),
        "evidence": dict(intent.evidence),
    }


def _source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            (root / f"discovery/candidates/{candidate_id}.json").read_text(
                encoding="utf-8"
            )
        )
        if spec.get("spec_hash") != expected_hash or not verify_spec_hash(spec):
            raise StageARunnerIntegrityError(
                f"{candidate_id} frozen spec hash mismatch"
            )

    if (
        C006_HASH != CANDIDATE_HASHES["V2-C006"]
        or C012_HASH != CANDIDATE_HASHES["V2-C012"]
    ):
        raise StageARunnerIntegrityError(
            "candidate replay source hash constants mismatch"
        )

    evaluator_sha = _source_sha256(root / "m6/stage_a_evaluator.py")
    if evaluator_sha != EVALUATOR_RUNTIME_SHA256:
        raise StageARunnerIntegrityError(
            "Stage-A evaluator source SHA256 mismatch"
        )

    readiness = json.loads(
        (root / "data/PRIMARY_WAVE_02_PRE_M6_READINESS_V7.json").read_text(
            encoding="utf-8"
        )
    )
    if readiness.get("first_runner_execution_authorized") is not False:
        raise StageARunnerIntegrityError(
            "historical pre-outcome readiness must remain execution-unauthorized"
        )


def verify_external_inputs(paths: StageAInputPaths) -> None:
    for field, expected in EXTERNAL_INPUT_SHA256.items():
        path = Path(getattr(paths, field))
        if not path.is_file():
            raise StageARunnerIntegrityError(
                f"missing external input: {field} -> {path}"
            )
        actual = sha256_file(path)
        if actual != expected:
            raise StageARunnerIntegrityError(
                f"external input sha256 mismatch {field}: "
                f"expected {expected}, got {actual}"
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

        entry_rate, _ = quote_to_eur_rate(
            "USD", intent.entry_utc, eurusd=eurusd
        )
        exit_rate, _ = quote_to_eur_rate(
            "USD", intent.exit_utc, eurusd=eurusd
        )
        prepared.append(
            PreparedTrade(
                intent=intent,
                entry_cost_evidence=entry_evidence,
                exit_cost_evidence=exit_evidence,
                entry_usd_to_eur_rate=_to_decimal_rate(entry_rate),
                exit_usd_to_eur_rate=_to_decimal_rate(exit_rate),
            )
        )

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
    """Generate frozen replay intents + exact applicable cost rows, but no PnL."""
    verify_repository_authorities(repo_root)
    verify_external_inputs(paths)

    root = Path(repo_root)
    calendar = NasdaqCashCalendar.from_artifact(
        root / "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json"
    )
    us500_rows = _csv_rows(paths.us500_m15)
    nas100_rows = _csv_rows(paths.nas100_m15)
    eurusd = CausalConversionSeries.from_rows(
        "EURUSD", _csv_rows(paths.eurusd_m15)
    )

    c006_intents = c006_replay_intents(us500_rows, calendar)
    c012_intents = c012_replay_intents(
        us500_rows, nas100_rows, calendar
    )

    us500_cost = load_us500_transaction_local_index(
        paths.us500_transaction_local_cost
    )
    nas100_cost = load_c012_transaction_local_index(
        paths.nas100_c012_transaction_local_cost
    )

    return StageAPreEconomicPlan(
        c006=_prepare_candidate(
            "V2-C006",
            c006_intents,
            cost_index=us500_cost,
            eurusd=eurusd,
        ),
        c012=_prepare_candidate(
            "V2-C012",
            c012_intents,
            cost_index=nas100_cost,
            eurusd=eurusd,
        ),
        economics_computed=False,
    )


def verify_pre_economic_materialization(
    plan: StageAPreEconomicPlan,
) -> dict[str, Any]:
    if plan.economics_computed:
        raise StageARunnerIntegrityError(
            "pre-economic materialization may not contain economics"
        )
    candidates = {
        "V2-C006": plan.c006,
        "V2-C012": plan.c012,
    }
    all_records: list[dict[str, Any]] = []
    actual = {}
    transaction_contexts = 0

    for candidate_id in ("V2-C006", "V2-C012"):
        candidate = candidates[candidate_id]
        if candidate.cost_state != "CONSERVATIVE_BOUND":
            raise StageARunnerIntegrityError(
                f"{candidate_id}: transaction cost context unresolved"
            )
        records = [_intent_record(x.intent) for x in candidate.trades]
        count = len(records)
        digest = _sha256_json(records)
        if count != EXPECTED_INTENT_COUNTS[candidate_id]:
            raise StageARunnerIntegrityError(
                f"{candidate_id}: intent count mismatch {count}"
            )
        if digest != EXPECTED_INTENT_MANIFEST_SHA256[candidate_id]:
            raise StageARunnerIntegrityError(
                f"{candidate_id}: frozen intent manifest mismatch"
            )
        for prepared in candidate.trades:
            for evidence, stamp in (
                (prepared.entry_cost_evidence, prepared.intent.entry_utc),
                (prepared.exit_cost_evidence, prepared.intent.exit_utc),
            ):
                expected_ms = int(
                    stamp.astimezone(timezone.utc).timestamp() * 1000
                )
                if evidence.boundary_timestamp_ms != expected_ms:
                    raise StageARunnerIntegrityError(
                        f"{candidate_id}: cost evidence timestamp mismatch"
                    )
                if not evidence.supported:
                    raise StageARunnerIntegrityError(
                        f"{candidate_id}: unsupported cost evidence selected"
                    )
                if (
                    candidate_id == "V2-C012"
                    and evidence.boundary_timestamp_ms
                    in C012_KNOWN_UNSUPPORTED_BOUNDARIES_MS
                ):
                    raise StageARunnerIntegrityError(
                        "C012 selected known fail-closed 15:00 context"
                    )
                transaction_contexts += 1
        all_records.extend(records)
        actual[candidate_id] = {
            "intent_count": count,
            "intent_manifest_sha256": digest,
            "transaction_contexts": count * 2,
        }

    combined = _sha256_json(all_records)
    if combined != EXPECTED_COMBINED_INTENT_MANIFEST_SHA256:
        raise StageARunnerIntegrityError(
            "combined frozen intent manifest mismatch"
        )
    if transaction_contexts != EXPECTED_TRANSACTION_CONTEXT_COUNT:
        raise StageARunnerIntegrityError(
            "transaction context count mismatch"
        )
    return {
        "candidates": actual,
        "combined_intent_manifest_sha256": combined,
        "transaction_context_count": transaction_contexts,
        "unresolved_transaction_context_count": 0,
    }


def _load_execution_authorization(
    path: Path | str | None,
    *,
    runner_source_sha256: str,
) -> Mapping[str, Any]:
    if path is None:
        raise StageAExecutionNotAuthorized(
            "Stage-A economics require a separate explicit execution authorization"
        )
    auth = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        auth.get("schema")
        != "mxm.greenfield.v2.m6-stage-a-execution-authorization.v1"
    ):
        raise StageAExecutionNotAuthorized(
            "invalid Stage-A execution authorization schema"
        )
    if auth.get("status") != "AUTHORIZED":
        raise StageAExecutionNotAuthorized(
            "Stage-A execution authorization is not active"
        )
    if auth.get("candidate_spec_hashes") != CANDIDATE_HASHES:
        raise StageAExecutionNotAuthorized(
            "authorization candidate hashes mismatch"
        )
    if (
        auth.get("transaction_local_cost_rule_git_blob_sha")
        != TRANSACTION_LOCAL_COST_RULE_GIT_BLOB
    ):
        raise StageAExecutionNotAuthorized(
            "authorization transaction-local cost authority mismatch"
        )
    if (
        auth.get("evaluator_policy_git_blob_sha")
        != EVALUATOR_POLICY_GIT_BLOB
        or auth.get("evaluator_runtime_git_blob_sha")
        != EVALUATOR_RUNTIME_GIT_BLOB
        or auth.get("evaluator_runtime_sha256")
        != EVALUATOR_RUNTIME_SHA256
    ):
        raise StageAExecutionNotAuthorized(
            "authorization evaluator binding mismatch"
        )
    if (
        auth.get("pre_economic_materialization_git_blob_sha")
        != PRE_ECONOMIC_MATERIALIZATION_GIT_BLOB
        or auth.get("combined_intent_manifest_sha256")
        != EXPECTED_COMBINED_INTENT_MANIFEST_SHA256
    ):
        raise StageAExecutionNotAuthorized(
            "authorization pre-economic materialization mismatch"
        )
    if auth.get("runner_source_sha256") != runner_source_sha256:
        raise StageAExecutionNotAuthorized(
            "authorization runner source SHA256 mismatch"
        )
    if auth.get("protected_evidence_opened") is not False:
        raise StageAExecutionNotAuthorized(
            "protected evidence must remain unopened"
        )
    if auth.get("stage") != "A":
        raise StageAExecutionNotAuthorized(
            "authorization is not scoped to Stage A"
        )
    return auth


def execute_stage_a_full_in_memory(
    repo_root: Path | str,
    paths: StageAInputPaths,
    *,
    authorization_path: Path | str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Open the two Stage-A economic outcomes only after all frozen gates pass."""
    root = Path(repo_root)
    runner_sha = _source_sha256(Path(__file__))
    _load_execution_authorization(
        authorization_path,
        runner_source_sha256=runner_sha,
    )
    plan = build_pre_economic_plan(root, paths)
    verify_pre_economic_materialization(plan)
    calendar = NasdaqCashCalendar.from_artifact(
        root / "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json"
    )
    c006 = evaluate_prepared_candidate(
        plan.c006,
        calendar=calendar,
        evaluator_sha256=EVALUATOR_RUNTIME_SHA256,
    )
    c012 = evaluate_prepared_candidate(
        plan.c012,
        calendar=calendar,
        evaluator_sha256=EVALUATOR_RUNTIME_SHA256,
    )
    validate_result(c006)
    validate_result(c012)
    return c006, c012


def execute_stage_a_in_memory(
    repo_root: Path | str,
    paths: StageAInputPaths,
    *,
    authorization_path: Path | str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Backward-compatible alias for the now-complete authoritative in-memory path."""
    return execute_stage_a_full_in_memory(
        repo_root,
        paths,
        authorization_path=authorization_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--validate-repository-only",
        action="store_true",
        help=(
            "Validate frozen repository authorities only; no external data, "
            "candidate replay, PnL, attempt or result."
        ),
    )
    args = parser.parse_args(argv)
    if not args.validate_repository_only:
        raise StageAExecutionNotAuthorized(
            "CLI economic execution is intentionally disabled. "
            "Use --validate-repository-only; authoritative Stage-A execution "
            "requires the programmatic path plus an explicit authorization artifact."
        )
    verify_repository_authorities(args.repo_root)
    print(
        "M6_STAGE_A_TIER1_FULL_EVALUATOR_PREPARED_NOT_RUN "
        f"{EVALUATOR_VERSION}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
