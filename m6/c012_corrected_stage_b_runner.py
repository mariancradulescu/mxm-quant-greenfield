"""Correction-only Stage-B CURRENT-configuration realization for corrected V2-C012.

This module does not create a new V2 identity and does not change any economic rule.
It reuses the corrected same-identity 34-intent C012 stream, the frozen Stage-B EUR200
capital law, the verified CURRENT Pepperstone margin authority, frozen reporting, and
transaction-local costs. Historical Stage-B V1 remains preserved but non-authoritative.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from discovery.canonical import compute_result_hash
from discovery.schema import validate_result

from .c012_corrected_stage_a_runner import (
    C012CorrectionInputPaths,
    EXPECTED_CORRECTED_INTENT_COUNT,
    EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
    build_corrected_c012_pre_economic_candidate,
    verify_corrected_c012_pre_economic_candidate,
)
from .stage_b_current_config_evaluator import (
    realize_current_configuration_capital,
    validate_current_configuration_authority,
)
from .stage_b_current_config_execute import (
    _augment_economic_detail,
    _canonical_bytes,
)
from .stage_b_evaluator import settle_min_volume_trade
from .stage_a_tier1_runner import _csv_rows
from .causal_conversion import CausalConversionSeries
from .stage_b_current_config_reporting import (
    RESULT_LABEL,
    summarize_current_config_realization,
)
from .stage_b_current_config_tier1_runner import (
    COST_RULE_GIT_BLOB,
    COST_RULE_REF,
    CURRENT_AUTHORITY_GIT_BLOB,
    CURRENT_AUTHORITY_REF,
    CURRENT_EVALUATOR_GIT_BLOB,
    CURRENT_EVALUATOR_REF,
    CURRENT_POLICY_GIT_BLOB,
    CURRENT_POLICY_REF,
    HISTORICAL_AUTHORITY_GIT_BLOB,
    HISTORICAL_AUTHORITY_REF,
    CurrentConfigExecutionNotAuthorized,
    CurrentConfigRunnerIntegrityError,
    git_blob_sha1,
)

AUTHORIZATION_SCHEMA = "mxm.greenfield.v2.c012-corrected-stage-b-current-config-authorization.v1"
RESULT_SCHEMA_V2 = "mxm.greenfield.v2.c012-corrected-stage-b-current-config-result.v2"
AUTHORIZATION_REF = "data/C012_CORRECTED_STAGE_B_CURRENT_CONFIG_AUTHORIZATION_V1.json"
RUNNER_REF = "m6/c012_corrected_stage_b_runner.py"
REPORTING_POLICY_REF = "data/M6_STAGE_B_CURRENT_CONFIG_REPORTING_POLICY_V1.json"
REPORTING_POLICY_GIT_BLOB = "e0419b33a7d3dfc5b6ee94b0038093fefcf9c599"
REPORTING_MODULE_REF = "m6/stage_b_current_config_reporting.py"
REPORTING_MODULE_GIT_BLOB = "49851e3ce8d82a3d7661639d76625987b6815638"
CORRECTED_STAGE_A_REF = "discovery/results/V2-C012_STAGE_A_V2.json"
CORRECTED_STAGE_A_RESULT_HASH = "01a0a9b7d44f0ed22d628538d243e3f8118233cdfb3383016490b4aa5240c503"
DOWNSTREAM_INVALIDATION_REF = "evidence/C012_STAGE_B_DOWNSTREAM_INVALIDATION_V1.json"
DOWNSTREAM_INVALIDATION_GIT_BLOB = "640ff59da35e2182c71eb037c5c4e9e30d76940a"
HISTORICAL_STAGE_B_REF = "m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V1.json"
HISTORICAL_STAGE_B_GIT_BLOB = "8c3b1fcdad6b43fcfed2af0919f3ddffd3b541f7"
HISTORICAL_STAGE_B_RESULT_SHA256 = "51edfcc76693425a07c24962f7b3c060fa2e7bb127385233f28f4fc1233edcaa"
CORRECTED_STAGE_B_REF = "m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V2.json"
C012_SPEC_HASH = "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845"
C012_CANDIDATE_REF = "discovery/candidates/V2-C012.json"
C012_CANDIDATE_GIT_BLOB = "a9a8464d9cf161c3dcae39536280089058e882d9"


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _utc(value: Any) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise CurrentConfigRunnerIntegrityError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _direction_sign(direction: str) -> Decimal:
    if direction == "LONG_NAS100":
        return Decimal("1")
    if direction == "SHORT_NAS100":
        return Decimal("-1")
    raise CurrentConfigRunnerIntegrityError(f"unexpected corrected C012 direction: {direction}")


def _close_path_recovery(realization: Any) -> dict[str, Any]:
    closed = [dict(x) for x in realization.path if x.get("event") == "TRADE_CLOSED"]
    peak = Decimal(str(realization.starting_capital_eur))
    peak_time: datetime | None = None
    max_dd = Decimal("0")
    trough_time: datetime | None = None
    recovery_target = peak
    for event in closed:
        t = _utc(event["exit_utc"])
        equity = Decimal(str(event["equity_eur"]))
        if equity > peak:
            peak = equity
            peak_time = t
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            trough_time = t
            recovery_target = peak
    if max_dd == 0 or trough_time is None:
        return {
            "maximum_drawdown_eur": float(max_dd),
            "recovery_status": "NO_DRAWDOWN",
            "time_to_recovery_hours": 0.0,
            "recovery_target_equity_eur": float(recovery_target),
        }
    for event in closed:
        t = _utc(event["exit_utc"])
        if t <= trough_time:
            continue
        equity = Decimal(str(event["equity_eur"]))
        if equity >= recovery_target:
            return {
                "maximum_drawdown_eur": float(max_dd),
                "recovery_status": "RECOVERED",
                "time_to_recovery_hours": (t - trough_time).total_seconds() / 3600.0,
                "recovery_target_equity_eur": float(recovery_target),
            }
    return {
        "maximum_drawdown_eur": float(max_dd),
        "recovery_status": "UNRECOVERED_AT_DEVELOPMENT_END",
        "time_to_recovery_hours": None,
        "recovery_target_equity_eur": float(recovery_target),
    }


def _performance_diagnostics(
    candidate: Any,
    realization: Any,
    frozen_report: Mapping[str, Any],
    paths: C012CorrectionInputPaths,
) -> dict[str, Any]:
    """Reporting-only diagnostics; never influence admission, sizing, PnL or candidate semantics."""
    nas_rows = {_utc(row["time_utc"]): row for row in _csv_rows(paths.nas100_m15)}
    eurusd = CausalConversionSeries.from_rows("EURUSD", _csv_rows(paths.eurusd_m15))
    path_events = list(realization.path)[1:]
    if len(path_events) != len(candidate.trades):
        raise CurrentConfigRunnerIntegrityError("corrected C012 diagnostic path cardinality mismatch")

    realized_before = Decimal(str(realization.starting_capital_eur))
    min_sampled_equity = realized_before
    min_sampled_free_margin: Decimal | None = None
    max_margin_usage_ratio = Decimal("0")
    margin_eur_hours = Decimal("0")
    capital_eur_hours = Decimal("0")
    occupied_hours = Decimal("0")
    executed = 0
    margin_rejected = 0
    sampled_points = 0
    max_hold_minutes = 0

    for prepared, event in zip(candidate.trades, path_events):
        trade = settle_min_volume_trade(prepared)
        if event.get("event") == "MARGIN_BLOCK":
            margin_rejected += 1
            continue
        if event.get("event") != "TRADE_CLOSED":
            raise CurrentConfigRunnerIntegrityError("unexpected corrected C012 diagnostic event")
        executed += 1
        entry = trade["entry_utc"].astimezone(timezone.utc)
        exit_ = trade["exit_utc"].astimezone(timezone.utc)
        required_margin = Decimal(str(event["required_margin_eur"]))
        hold_hours = Decimal(str((exit_ - entry).total_seconds())) / Decimal("3600")
        hold_minutes = int((exit_ - entry).total_seconds() // 60)
        max_hold_minutes = max(max_hold_minutes, hold_minutes)
        occupied_hours += hold_hours
        margin_eur_hours += required_margin * hold_hours
        capital_eur_hours += realized_before * hold_hours

        quantity = Decimal(str(trade["quantity_units"]))
        entry_price = Decimal(str(trade["entry_price"]))
        entry_cost = (
            Decimal(prepared.entry_cost_evidence.transaction_cost_proxy_points)
            * quantity
            * Decimal(prepared.entry_usd_to_eur_rate)
        )
        entry_marked_equity = realized_before - entry_cost
        free = entry_marked_equity - required_margin
        min_sampled_equity = min(min_sampled_equity, entry_marked_equity)
        min_sampled_free_margin = free if min_sampled_free_margin is None else min(min_sampled_free_margin, free)
        if entry_marked_equity > 0:
            max_margin_usage_ratio = max(max_margin_usage_ratio, required_margin / entry_marked_equity)
        sampled_points += 1

        cursor = entry
        while cursor < exit_:
            row = nas_rows.get(cursor)
            if row is None:
                raise CurrentConfigRunnerIntegrityError(f"missing NAS100 M15 row inside corrected C012 hold: {cursor.isoformat()}")
            adverse_price = Decimal(str(row["low"] if trade["direction"] == "LONG_NAS100" else row["high"]))
            completed = cursor + timedelta(minutes=15)
            conversion_obs = eurusd.latest_completed_at_or_before(completed)
            quote_to_eur = Decimal("1") / Decimal(str(conversion_obs.close_price))
            gross_mark = (
                _direction_sign(trade["direction"])
                * (adverse_price - entry_price)
                * quantity
                * quote_to_eur
            )
            marked_equity = realized_before + gross_mark - entry_cost
            free = marked_equity - required_margin
            min_sampled_equity = min(min_sampled_equity, marked_equity)
            min_sampled_free_margin = free if min_sampled_free_margin is None else min(min_sampled_free_margin, free)
            if marked_equity > 0:
                max_margin_usage_ratio = max(max_margin_usage_ratio, required_margin / marked_equity)
            sampled_points += 1
            cursor += timedelta(minutes=15)

        realized_before = Decimal(str(event["equity_eur"]))

    weekly = dict(frozen_report["executed_trade_distribution"]["weekly_executed_entries"])
    total_weeks = len(frozen_report["weekly_final_equity_eur"])
    hard21_weeks = sum(1 for n in weekly.values() if int(n) >= 21)
    max_weekly = max((int(n) for n in weekly.values()), default=0)
    economics_gross = Decimal("0")
    economics_cost = Decimal("0")
    for prepared, event in zip(candidate.trades, path_events):
        if event.get("event") != "TRADE_CLOSED":
            continue
        trade = settle_min_volume_trade(prepared)
        economics_gross += Decimal(trade["gross_pnl_eur"])
        economics_cost += Decimal(trade["transaction_cost_eur"])
    net = Decimal(str(realization.final_equity_eur)) - Decimal(str(realization.starting_capital_eur))
    recovery = _close_path_recovery(realization)
    cost_burden = economics_cost / abs(economics_gross) if economics_gross != 0 else None

    return {
        "starting_equity_eur": float(Decimal(str(realization.starting_capital_eur))),
        "terminal_equity_eur": float(Decimal(str(realization.final_equity_eur))),
        "absolute_pnl_eur": float(net),
        "return_pct": float(net / Decimal(str(realization.starting_capital_eur)) * Decimal("100")),
        "executed_entries": executed,
        "rejected_entries": margin_rejected,
        "margin_rejected_entries": margin_rejected,
        "concurrency_rejected_entries": 0,
        "conflict_rejected_entries": 0,
        "risk_governor_rejected_entries": 0,
        "minimum_sampled_marked_equity_eur": float(min_sampled_equity),
        "minimum_sampled_free_margin_eur": float(min_sampled_free_margin) if min_sampled_free_margin is not None else None,
        "maximum_sampled_margin_usage_ratio": float(max_margin_usage_ratio),
        "maximum_sampled_margin_usage_pct": float(max_margin_usage_ratio * Decimal("100")),
        "close_path_recovery": recovery,
        "weekly_executed_entries": weekly,
        "hard21_actual_execution": {
            "floor_entries_per_certified_utc_iso_week": 21,
            "development_week_count": total_weeks,
            "weeks_meeting_floor": hard21_weeks,
            "maximum_actual_entries_in_any_week": max_weekly,
            "status": "MET" if total_weeks > 0 and hard21_weeks == total_weeks else "NOT_MET",
        },
        "capital_occupancy": dict(frozen_report["capital_occupancy"]),
        "time_in_market_hours": float(occupied_hours),
        "time_in_market_ratio": float(frozen_report["capital_occupancy"]["time_occupancy_ratio"]),
        "margin_eur_hours": float(margin_eur_hours),
        "capital_eur_hours": float(capital_eur_hours),
        "pnl_per_margin_eur_hour": float(net / margin_eur_hours) if margin_eur_hours != 0 else None,
        "pnl_per_capital_eur_hour": float(net / capital_eur_hours) if capital_eur_hours != 0 else None,
        "sampled_unrealized_path": {
            "method": "M15_ADVERSE_HIGH_LOW_MARK_TO_MARKET_REPORTING_ONLY",
            "sampled_points": sampled_points,
            "affects_admission_or_pnl": False,
            "conversion_rule": "LATEST_COMPLETED_EURUSD_M15_AT_OR_BEFORE_SAMPLE_COMPLETION",
            "entry_cost_recognized": True,
            "future_exit_cost_recognized_before_exit": False,
        },
        "cost_burden": {
            "transaction_cost_eur": float(economics_cost),
            "gross_pnl_eur": float(economics_gross),
            "transaction_cost_over_abs_gross": float(cost_burden) if cost_burden is not None else None,
        },
        "swap_burden": {
            "swap_eur": 0.0,
            "status": "NOT_APPLICABLE_TO_FROZEN_INTRADAY_HOLDS" if max_hold_minutes < 24 * 60 else "UNRESOLVED",
            "maximum_hold_minutes": max_hold_minutes,
        },
        "forced_liquidation": {
            "events": None,
            "applied": False,
            "status": "UNRESOLVED_ACCOUNT_SPECIFIC_STOP_OUT_BOUNDARY_NOT_INVENTED",
        },
        "position_overlap": {
            "actual_overlapping_executed_positions": 0,
            "candidate_policy": "NO_OVERLAP_FROZEN_STAGE_B_POLICY",
        },
    }


def validate_corrected_c012_stage_b_result(result: Mapping[str, Any]) -> bool:
    if result.get("schema") != RESULT_SCHEMA_V2:
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 result schema mismatch")
    if result.get("candidate_id") != "V2-C012":
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 candidate mismatch")
    provenance = result.get("execution_provenance")
    metrics = result.get("performance_metrics")
    economics = result.get("economic_summary")
    report = result.get("frozen_reporting")
    if not all(isinstance(x, Mapping) for x in (provenance, metrics, economics, report)):
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 result structure incomplete")
    if provenance.get("corrected_intent_count") != EXPECTED_CORRECTED_INTENT_COUNT:
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 intent count drift")
    if metrics.get("executed_entries", 0) + metrics.get("margin_rejected_entries", 0) != EXPECTED_CORRECTED_INTENT_COUNT:
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 execution/rejection accounting mismatch")
    if economics.get("starting_equity_eur") != 200.0:
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 must start at EUR200")
    if metrics.get("starting_equity_eur") != economics.get("starting_equity_eur"):
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 starting-equity projection mismatch")
    if metrics.get("terminal_equity_eur") != economics.get("final_equity_eur"):
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 terminal-equity projection mismatch")
    observed = result.get("result_hash")
    if not isinstance(observed, str) or observed != compute_result_hash(result):
        raise CurrentConfigRunnerIntegrityError("corrected Stage-B V2 canonical result_hash mismatch")
    return True


def project_current_state_after_successor(
    state: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    validate_corrected_c012_stage_b_result(result)
    out = deepcopy(dict(state))
    correction = out["c012_same_identity_corrected_rerun"]
    node = out["current_result_authority"]["V2-C012"]["stage_b_current_config"]
    correction["corrected_stage_b"] = {
        "status": "CORRECTED_STAGE_B_RECORDED_CURRENT_SUCCESSOR",
        "authorization_ref": AUTHORIZATION_REF,
        "corrected_stage_a_result_ref": CORRECTED_STAGE_A_REF,
        "corrected_stage_a_result_hash": CORRECTED_STAGE_A_RESULT_HASH,
        "corrected_intent_count": EXPECTED_CORRECTED_INTENT_COUNT,
        "corrected_intent_manifest_sha256": EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
        "historical_stage_b_ref": HISTORICAL_STAGE_B_REF,
        "corrected_stage_b_result_ref": CORRECTED_STAGE_B_REF,
        "corrected_stage_b_result_hash": result["result_hash"],
        "new_v2_attempt_consumed": False,
        "search_budget_decrement": 0,
        "protected_evidence_opened": False,
        "economics_run": True,
    }
    node["state"] = "VALID_CORRECTED_SUCCESSOR"
    node["corrected_successor_ref"] = CORRECTED_STAGE_B_REF
    node["corrected_successor_hash"] = result["result_hash"]
    out["active_result_pointers"]["V2-C012_STAGE_B_CURRENT_CONFIG"] = CORRECTED_STAGE_B_REF
    out["phase"] = "C012_CORRECTED_STAGE_B_RECORDED_CURRENT_SUCCESSOR"
    out["next_action"] = "Require exact-head GREEN, then branch Performance Research V3 from that exact GREEN operational tree and continue prospective discovery."
    return out


def verify_corrected_c012_stage_b_pre_economic(repo_root: Path | str) -> dict[str, Any]:
    """Validate all frozen authorities without computing Stage-B PnL/capital."""
    root = Path(repo_root)
    immutable = {
        CURRENT_AUTHORITY_REF: CURRENT_AUTHORITY_GIT_BLOB,
        CURRENT_POLICY_REF: CURRENT_POLICY_GIT_BLOB,
        CURRENT_EVALUATOR_REF: CURRENT_EVALUATOR_GIT_BLOB,
        REPORTING_POLICY_REF: REPORTING_POLICY_GIT_BLOB,
        REPORTING_MODULE_REF: REPORTING_MODULE_GIT_BLOB,
        HISTORICAL_AUTHORITY_REF: HISTORICAL_AUTHORITY_GIT_BLOB,
        COST_RULE_REF: COST_RULE_GIT_BLOB,
        C012_CANDIDATE_REF: C012_CANDIDATE_GIT_BLOB,
        DOWNSTREAM_INVALIDATION_REF: DOWNSTREAM_INVALIDATION_GIT_BLOB,
        HISTORICAL_STAGE_B_REF: HISTORICAL_STAGE_B_GIT_BLOB,
    }
    for rel, expected in immutable.items():
        if git_blob_sha1(root / rel) != expected:
            raise CurrentConfigRunnerIntegrityError(f"corrected C012 Stage-B authority drift: {rel}")

    candidate = _load_json(root / C012_CANDIDATE_REF)
    if candidate.get("spec_hash") != C012_SPEC_HASH:
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-B candidate spec drift")

    stage_a = _load_json(root / CORRECTED_STAGE_A_REF)
    validate_result(stage_a)
    if (
        stage_a.get("candidate_id") != "V2-C012"
        or stage_a.get("spec_hash") != C012_SPEC_HASH
        or stage_a.get("stage") != "A"
        or stage_a.get("status") != "DISCOVERY_SURVIVOR"
        or stage_a.get("metrics", {}).get("event_count") != EXPECTED_CORRECTED_INTENT_COUNT
        or stage_a.get("result_hash") != CORRECTED_STAGE_A_RESULT_HASH
        or compute_result_hash(stage_a) != CORRECTED_STAGE_A_RESULT_HASH
    ):
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-A successor binding drift")

    historical_stage_b = _load_json(root / HISTORICAL_STAGE_B_REF)
    if historical_stage_b.get("result_sha256") != HISTORICAL_STAGE_B_RESULT_SHA256:
        raise CurrentConfigRunnerIntegrityError("historical C012 Stage-B V1 result hash drift")
    invalidation = _load_json(root / DOWNSTREAM_INVALIDATION_REF)
    invalidated = invalidation.get("invalidated_downstream", {})
    if (
        invalidation.get("candidate_id") != "V2-C012"
        or invalidated.get("stage_b_result_ref") != HISTORICAL_STAGE_B_REF
        or invalidated.get("stage_b_result_git_blob_sha1") != HISTORICAL_STAGE_B_GIT_BLOB
        or invalidated.get("stage_b_persisted_result_sha256") != HISTORICAL_STAGE_B_RESULT_SHA256
        or invalidation.get("historical_bytes_overwritten") is not False
        or invalidation.get("new_v2_attempt_consumed") is not False
    ):
        raise CurrentConfigRunnerIntegrityError("historical C012 Stage-B invalidation authority drift")

    authority = _load_json(root / CURRENT_AUTHORITY_REF)
    validate_current_configuration_authority(authority)

    state = _load_json(root / "CURRENT_STATE.json")
    if state.get("v2_attempts_used") != 9 or state.get("v2_search_budget_remaining") != 75:
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-B attempt/budget accounting drift")
    if state.get("protected_evidence_opened") is not False:
        raise CurrentConfigRunnerIntegrityError("protected evidence must remain closed")
    correction = state.get("c012_same_identity_corrected_rerun", {})
    if (
        correction.get("status") != "CORRECTED_STAGE_A_RECORDED_SURVIVOR"
        or correction.get("corrected_stage_a_result_hash") != CORRECTED_STAGE_A_RESULT_HASH
        or correction.get("corrected_stage_a_event_count") != EXPECTED_CORRECTED_INTENT_COUNT
        or correction.get("new_v2_attempt_consumed") is not False
        or correction.get("search_budget_decrement") != 0
    ):
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-A lifecycle state drift")
    node = state.get("current_result_authority", {}).get("V2-C012", {})
    if node.get("stage_a", {}).get("state") != "VALID_CORRECTED_SUCCESSOR":
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-A is not current authority")
    downstream = node.get("stage_b_current_config", {})
    if downstream.get("historical_result_ref") != HISTORICAL_STAGE_B_REF:
        raise CurrentConfigRunnerIntegrityError("historical Stage-B ref drift")
    if downstream.get("corrected_stage_a_successor_ref") != CORRECTED_STAGE_A_REF:
        raise CurrentConfigRunnerIntegrityError("corrected Stage-A successor ref drift")
    if downstream.get("corrected_successor_ref") not in (None, CORRECTED_STAGE_B_REF):
        raise CurrentConfigRunnerIntegrityError("unexpected corrected Stage-B successor ref")

    if (root / CORRECTED_STAGE_B_REF).exists():
        successor = _load_json(root / CORRECTED_STAGE_B_REF)
        if successor.get("candidate_id") != "V2-C012":
            raise CurrentConfigRunnerIntegrityError("corrected Stage-B successor candidate drift")

    return {
        "candidate_id": "V2-C012",
        "spec_hash": C012_SPEC_HASH,
        "corrected_stage_a_result_hash": CORRECTED_STAGE_A_RESULT_HASH,
        "corrected_intent_count": EXPECTED_CORRECTED_INTENT_COUNT,
        "corrected_intent_manifest_sha256": EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
        "historical_stage_b_result_sha256": HISTORICAL_STAGE_B_RESULT_SHA256,
        "economics_computed": False,
        "new_v2_attempt_consumed": False,
        "search_budget_decrement": 0,
    }


def _load_correction_authorization(
    repo_root: Path,
    authorization_path: Path | str | None,
    *,
    execution_head: str,
    execution_ci_run_id: int,
) -> Mapping[str, Any]:
    if authorization_path is None:
        raise CurrentConfigExecutionNotAuthorized("corrected C012 Stage-B requires explicit authorization")
    auth = _load_json(authorization_path)
    checks = (
        auth.get("schema") == AUTHORIZATION_SCHEMA,
        auth.get("status") == "AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
        auth.get("candidate_id") == "V2-C012",
        auth.get("candidate_spec_hash") == C012_SPEC_HASH,
        auth.get("corrected_stage_a_result_ref") == CORRECTED_STAGE_A_REF,
        auth.get("corrected_stage_a_result_hash") == CORRECTED_STAGE_A_RESULT_HASH,
        auth.get("corrected_intent_count") == EXPECTED_CORRECTED_INTENT_COUNT,
        auth.get("corrected_intent_manifest_sha256") == EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
        auth.get("current_authority_git_blob_sha1") == CURRENT_AUTHORITY_GIT_BLOB,
        auth.get("current_evaluator_git_blob_sha1") == CURRENT_EVALUATOR_GIT_BLOB,
        auth.get("reporting_policy_git_blob_sha1") == REPORTING_POLICY_GIT_BLOB,
        auth.get("reporting_module_git_blob_sha1") == REPORTING_MODULE_GIT_BLOB,
        auth.get("historical_stage_b_git_blob_sha1") == HISTORICAL_STAGE_B_GIT_BLOB,
        auth.get("downstream_invalidation_git_blob_sha1") == DOWNSTREAM_INVALIDATION_GIT_BLOB,
        auth.get("runner_git_blob_sha1") == git_blob_sha1(repo_root / RUNNER_REF),
        auth.get("execution_gate_head") == execution_head,
        auth.get("execution_gate_ci_run_id") == int(execution_ci_run_id),
        auth.get("same_identity") is True,
        auth.get("semantic_change") is False,
        auth.get("new_v2_attempt_consumed") is False,
        auth.get("search_budget_decrement") == 0,
        auth.get("protected_evidence_opened") is False,
    )
    if not all(checks):
        raise CurrentConfigExecutionNotAuthorized("corrected C012 Stage-B authorization binding mismatch")
    verify_corrected_c012_stage_b_pre_economic(repo_root)
    return auth


def execute_corrected_c012_stage_b_in_memory(
    repo_root: Path | str,
    paths: C012CorrectionInputPaths,
    *,
    authorization_path: Path | str | None,
    execution_head: str,
    execution_ci_run_id: int,
) -> dict[str, Any]:
    root = Path(repo_root)
    auth = _load_correction_authorization(
        root,
        authorization_path,
        execution_head=execution_head,
        execution_ci_run_id=execution_ci_run_id,
    )
    candidate = build_corrected_c012_pre_economic_candidate(root, paths)
    verify_corrected_c012_pre_economic_candidate(candidate)
    current_margin_authority = _load_json(root / CURRENT_AUTHORITY_REF)
    realization = realize_current_configuration_capital(
        candidate,
        current_margin_authority=current_margin_authority,
    )
    frozen_report = summarize_current_config_realization(realization)
    economics = _augment_economic_detail(candidate, realization)
    if frozen_report.get("label") != RESULT_LABEL:
        raise CurrentConfigRunnerIntegrityError("wrong corrected C012 Stage-B result label")
    if frozen_report["continuous_capital"]["final_equity_eur"] != economics["final_equity_eur"]:
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-B final-equity mismatch")
    if frozen_report["continuous_capital"]["maximum_drawdown_eur"] != economics["maximum_drawdown_eur"]:
        raise CurrentConfigRunnerIntegrityError("corrected C012 Stage-B drawdown mismatch")

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA_V2,
        "label": RESULT_LABEL,
        "candidate_id": "V2-C012",
        "execution_provenance": {
            "authorization_ref": AUTHORIZATION_REF,
            "authorization_revision": auth.get("revision"),
            "execution_head": execution_head,
            "execution_exact_head_ci_run_id": int(execution_ci_run_id),
            "corrected_stage_a_result_ref": CORRECTED_STAGE_A_REF,
            "corrected_stage_a_result_hash": CORRECTED_STAGE_A_RESULT_HASH,
            "corrected_intent_count": EXPECTED_CORRECTED_INTENT_COUNT,
            "corrected_intent_manifest_sha256": EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
            "current_broker_configuration_authority_ref": CURRENT_AUTHORITY_REF,
            "reporting_policy_ref": REPORTING_POLICY_REF,
            "reporting_module_ref": REPORTING_MODULE_REF,
            "historical_stage_b_result_ref": HISTORICAL_STAGE_B_REF,
            "downstream_invalidation_ref": DOWNSTREAM_INVALIDATION_REF,
            "protected_evidence_opened": False,
        },
        "scenario_boundary": {
            "current_configuration_applied_to_development": True,
            "historical_point_in_time_margin_certification": False,
            "historical_margin_state": "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
            "historical_certification_effect": "NONE",
        },
        "economic_summary": economics,
        "frozen_reporting": frozen_report,
        "performance_metrics": _performance_diagnostics(candidate, realization, frozen_report, paths),
    }
    result["result_hash"] = compute_result_hash(result)
    validate_corrected_c012_stage_b_result(result)
    return result


def persist_corrected_c012_stage_b_result(
    result: Mapping[str, Any],
    repo_root: Path | str,
) -> Path:
    root = Path(repo_root)
    if result.get("candidate_id") != "V2-C012":
        raise CurrentConfigRunnerIntegrityError("unexpected corrected Stage-B candidate")
    validate_corrected_c012_stage_b_result(result)
    target = root / CORRECTED_STAGE_B_REF
    if target.exists():
        existing = _load_json(target)
        if existing == dict(result):
            return target
        raise CurrentConfigRunnerIntegrityError("refusing to overwrite different corrected Stage-B successor")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_canonical_bytes(result))
    return target
