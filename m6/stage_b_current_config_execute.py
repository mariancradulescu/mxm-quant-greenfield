"""Thin fail-closed execution wiring for the authorized Stage-B CURRENT configuration scenario.

This module does not change any economic rule. It binds the already-frozen Stage-A materialized
inputs to the already-authorized V4 current-configuration runner, then summarizes/persists the
two deterministic scenario reports outside the Discovery ledger.

The economic core remains:
- m6.stage_b_current_config_evaluator
- m6.stage_b_current_config_tier1_runner
- m6.stage_b_current_config_reporting

Historical point-in-time margin remains unresolved and is not asserted by this execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .stage_a_tier1_runner import (
    StageAInputPaths,
    build_pre_economic_plan,
    verify_pre_economic_materialization,
)
from .stage_b_evaluator import settle_min_volume_trade
from .stage_b_current_config_reporting import (
    RESULT_LABEL,
    summarize_current_config_realization,
)
from .stage_b_current_config_tier1_runner import (
    CURRENT_AUTHORITY_REF,
    CurrentConfigRunnerIntegrityError,
    execute_current_config_scenario_in_memory,
    git_blob_sha1,
    validate_execution_authorization,
    verify_repository_current_config_authorities,
)

AUTHORIZATION_REF = "data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json"
REPORTING_POLICY_REF = "data/M6_STAGE_B_CURRENT_CONFIG_REPORTING_POLICY_V1.json"
REPORTING_MODULE_REF = "m6/stage_b_current_config_reporting.py"
RESULT_SCHEMA = "mxm.greenfield.v2.m6-stage-b-current-config-result.v1"
RESULT_FILENAMES = {
    "V2-C006": "V2-C006_STAGE_B_CURRENT_CONFIG_V1.json",
    "V2-C012": "V2-C012_STAGE_B_CURRENT_CONFIG_V1.json",
}
RUN_RECORD_REF = "m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json"
POST_EXECUTION_CONSUMPTION_REF = (
    "evidence/M6_STAGE_B_CURRENT_CONFIG_POST_EXECUTION_CONSUMPTION_V1.json"
)
CANONICAL_RESULT_REFS = {
    cid: f"m6/results/{filename}" for cid, filename in RESULT_FILENAMES.items()
}


class CurrentConfigScenarioAlreadyExecuted(CurrentConfigRunnerIntegrityError):
    """Raised before any economic work when authoritative evidence proves Stage-B already ran."""


def assert_current_config_scenario_not_already_executed(repo_root: Path | str) -> None:
    """Fail closed on every authoritative post-execution marker before touching economics."""
    root = Path(repo_root)

    run_path = root / RUN_RECORD_REF
    if run_path.exists():
        run = _load_json(run_path)
        if run.get("status") == "EXECUTED_EXACTLY_ONCE":
            raise CurrentConfigScenarioAlreadyExecuted(
                "Stage-B CURRENT configuration scenario already executed: run record is authoritative"
            )

    consumption_path = root / POST_EXECUTION_CONSUMPTION_REF
    if consumption_path.exists():
        consumption = _load_json(consumption_path)
        if (
            consumption.get("status") == "CONSUMED_EXECUTED_EXACTLY_ONCE"
            and consumption.get("execution_count") == 1
        ):
            raise CurrentConfigScenarioAlreadyExecuted(
                "Stage-B CURRENT configuration scenario already executed: consumption authority is authoritative"
            )

    existing = [ref for ref in CANONICAL_RESULT_REFS.values() if (root / ref).exists()]
    if existing:
        raise CurrentConfigScenarioAlreadyExecuted(
            "Stage-B CURRENT configuration scenario already executed: canonical result exists: "
            + ", ".join(existing)
        )


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _z(value: Any) -> str:
    text = str(value)
    if text.endswith("Z"):
        return text
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise CurrentConfigRunnerIntegrityError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_without_result_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("result_sha256", None)
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _money(value: Decimal) -> float:
    if not value.is_finite():
        raise CurrentConfigRunnerIntegrityError("non-finite monetary value")
    return float(value)


def _augment_economic_detail(candidate: Any, realization: Any) -> dict[str, Any]:
    events = list(realization.path)[1:]
    if len(events) != len(candidate.trades):
        raise CurrentConfigRunnerIntegrityError("capital path/intent cardinality mismatch")

    gross = Decimal("0")
    costs = Decimal("0")
    net = Decimal("0")
    direction: dict[str, dict[str, Any]] = {}
    executed_events: list[dict[str, Any]] = []

    peak = Decimal(str(realization.starting_capital_eur))
    max_dd = Decimal("0")
    max_dd_pct_peak = Decimal("0")

    for prepared, event in zip(candidate.trades, events):
        expected_entry = prepared.intent.entry_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if event.get("entry_utc") != expected_entry:
            raise CurrentConfigRunnerIntegrityError("capital path/intended entry mismatch")
        if event.get("direction") != prepared.intent.direction:
            raise CurrentConfigRunnerIntegrityError("capital path/direction mismatch")

        if event.get("event") == "TRADE_CLOSED":
            trade = settle_min_volume_trade(prepared)
            g = Decimal(trade["gross_pnl_eur"])
            c = Decimal(trade["transaction_cost_eur"])
            n = Decimal(trade["coarse_net_pnl_eur"])
            if n != g - c:
                raise CurrentConfigRunnerIntegrityError("gross/cost/net identity failure")
            if Decimal(str(event["net_pnl_eur"])) != n:
                raise CurrentConfigRunnerIntegrityError("capital path/net PnL mismatch")

            gross += g
            costs += c
            net += n
            key = str(trade["direction"])
            node = direction.setdefault(
                key,
                {
                    "executed_trades": 0,
                    "gross_pnl_eur": Decimal("0"),
                    "transaction_cost_eur": Decimal("0"),
                    "net_pnl_eur": Decimal("0"),
                },
            )
            node["executed_trades"] += 1
            node["gross_pnl_eur"] += g
            node["transaction_cost_eur"] += c
            node["net_pnl_eur"] += n
            executed_events.append(dict(event))

            equity = Decimal(str(event["equity_eur"]))
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
            dd_pct = dd / peak if peak > 0 else Decimal("0")
            if dd_pct > max_dd_pct_peak:
                max_dd_pct_peak = dd_pct
        elif event.get("event") != "MARGIN_BLOCK":
            raise CurrentConfigRunnerIntegrityError("unexpected capital path event")

    final_equity = Decimal(str(realization.final_equity_eur))
    starting = Decimal(str(realization.starting_capital_eur))
    absolute_return = final_equity - starting
    if absolute_return != net:
        raise CurrentConfigRunnerIntegrityError("final equity/net PnL identity failure")

    direction_out = {
        key: {
            "executed_trades": int(node["executed_trades"]),
            "gross_pnl_eur": _money(node["gross_pnl_eur"]),
            "transaction_cost_eur": _money(node["transaction_cost_eur"]),
            "net_pnl_eur": _money(node["net_pnl_eur"]),
        }
        for key, node in sorted(direction.items())
    }
    first_event = dict(executed_events[0]) if executed_events else None
    last_event = dict(executed_events[-1]) if executed_events else None

    return {
        "starting_equity_eur": _money(starting),
        "final_equity_eur": _money(final_equity),
        "absolute_net_return_eur": _money(absolute_return),
        "net_return_pct": float((absolute_return / starting) * Decimal("100")),
        "gross_pnl_eur": _money(gross),
        "transaction_costs_eur": _money(costs),
        "net_pnl_eur": _money(net),
        "executed_trades": int(realization.executed_trades),
        "margin_blocked_trades": int(realization.margin_blocked_trades),
        "direction_contribution": direction_out,
        "maximum_drawdown_eur": _money(max_dd),
        "maximum_drawdown_pct_of_peak": float(max_dd_pct_peak * Decimal("100")),
        "maximum_drawdown_pct_of_starting_capital": float((max_dd / starting) * Decimal("100")),
        "first_executed_event": first_event,
        "last_executed_event": last_event,
    }


def execute_authorized_current_config(
    repo_root: Path | str,
    input_paths: StageAInputPaths,
    *,
    execution_head: str,
    execution_ci_run_id: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(repo_root)

    # First repository-state gate: before preflight, materialization, realization, PnL or capital path.
    assert_current_config_scenario_not_already_executed(root)

    preflight = verify_repository_current_config_authorities(root)
    authorization = _load_json(root / AUTHORIZATION_REF)
    validate_execution_authorization(authorization)

    if authorization.get("consumed") is not False:
        raise CurrentConfigRunnerIntegrityError("V4 authorization is already consumed")
    if authorization.get("execution_authorized") is not True:
        raise CurrentConfigRunnerIntegrityError("V4 execution is not authorized")
    gate = authorization.get("execution_gate", {})
    if gate.get("execute_exactly_once_after_success") is not True:
        raise CurrentConfigRunnerIntegrityError("V4 exact-once gate drift")

    if git_blob_sha1(root / REPORTING_POLICY_REF) != authorization.get("reporting_policy_git_blob_sha1"):
        raise CurrentConfigRunnerIntegrityError("V4 reporting-policy binding mismatch")
    if git_blob_sha1(root / REPORTING_MODULE_REF) != authorization.get("reporting_module_git_blob_sha1"):
        raise CurrentConfigRunnerIntegrityError("V4 reporting-module binding mismatch")

    plan = build_pre_economic_plan(root, input_paths)
    manifest = verify_pre_economic_materialization(plan)
    expected_manifest = _load_json(root / "evidence/M6_STAGE_B_CURRENT_CONFIG_PRE_ECONOMIC_MATERIALIZATION_V1.json")
    expected_bindings = expected_manifest["stage_a_survivor_bindings"]
    if manifest["combined_intent_manifest_sha256"] != expected_bindings["combined_intent_manifest_sha256"]:
        raise CurrentConfigRunnerIntegrityError("frozen combined intent manifest mismatch")
    if manifest["candidates"]["V2-C006"]["intent_count"] != expected_bindings["V2-C006"]["intent_count"]:
        raise CurrentConfigRunnerIntegrityError("C006 intent count drift")
    if manifest["candidates"]["V2-C012"]["intent_count"] != expected_bindings["V2-C012"]["intent_count"]:
        raise CurrentConfigRunnerIntegrityError("C012 intent count drift")

    current_margin_authority = _load_json(root / CURRENT_AUTHORITY_REF)
    realizations = execute_current_config_scenario_in_memory(
        (plan.c006, plan.c012),
        authorization=authorization,
        current_margin_authority=current_margin_authority,
    )
    if len(realizations) != 2:
        raise CurrentConfigRunnerIntegrityError("exactly two scenario realizations required")

    out: list[dict[str, Any]] = []
    for candidate, realization in zip((plan.c006, plan.c012), realizations):
        frozen_report = summarize_current_config_realization(realization)
        if frozen_report.get("label") != RESULT_LABEL:
            raise CurrentConfigRunnerIntegrityError("wrong result label")
        economics = _augment_economic_detail(candidate, realization)
        if frozen_report["continuous_capital"]["final_equity_eur"] != economics["final_equity_eur"]:
            raise CurrentConfigRunnerIntegrityError("report/economic final-equity mismatch")
        if frozen_report["continuous_capital"]["maximum_drawdown_eur"] != economics["maximum_drawdown_eur"]:
            raise CurrentConfigRunnerIntegrityError("report/economic drawdown mismatch")

        result: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "label": RESULT_LABEL,
            "candidate_id": realization.candidate_id,
            "execution_provenance": {
                "authorization_ref": AUTHORIZATION_REF,
                "authorization_revision": authorization.get("revision"),
                "execution_head": execution_head,
                "execution_exact_head_ci_run_id": int(execution_ci_run_id),
                "current_broker_configuration_authority_ref": CURRENT_AUTHORITY_REF,
                "current_broker_configuration_status": preflight["authority_status"],
                "reporting_policy_ref": REPORTING_POLICY_REF,
                "reporting_module_ref": REPORTING_MODULE_REF,
                "combined_intent_manifest_sha256": manifest["combined_intent_manifest_sha256"],
                "protected_evidence_opened": False,
            },
            "scenario_boundary": {
                "current_configuration_applied_to_development": True,
                "historical_point_in_time_margin_certification": False,
                "historical_margin_state": preflight["historical_margin_state"],
                "historical_certification_effect": "NONE",
            },
            "economic_summary": economics,
            "frozen_reporting": frozen_report,
        }
        result["result_sha256"] = _sha256_without_result_hash(result)
        out.append(result)

    return out[0], out[1]


def persist_results(
    results: Sequence[Mapping[str, Any]],
    output_dir: Path | str,
) -> tuple[Path, ...]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for result in results:
        cid = str(result.get("candidate_id"))
        if cid not in RESULT_FILENAMES:
            raise CurrentConfigRunnerIntegrityError("unexpected result candidate")
        expected_hash = _sha256_without_result_hash(result)
        if result.get("result_sha256") != expected_hash:
            raise CurrentConfigRunnerIntegrityError("result hash mismatch before persistence")
        path = out / RESULT_FILENAMES[cid]
        if path.exists():
            raise CurrentConfigRunnerIntegrityError(f"refusing to overwrite existing result: {path}")
        path.write_bytes(_canonical_bytes(result))
        written.append(path)
    if len(written) != 2:
        raise CurrentConfigRunnerIntegrityError("exactly two result files required")
    return tuple(written)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--us500-m15", required=True)
    parser.add_argument("--nas100-m15", required=True)
    parser.add_argument("--eurusd-m15", required=True)
    parser.add_argument("--us500-transaction-local-cost", required=True)
    parser.add_argument("--nas100-c012-transaction-local-cost", required=True)
    parser.add_argument("--execution-head", required=True)
    parser.add_argument("--execution-ci-run-id", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    paths = StageAInputPaths(
        us500_m15=Path(args.us500_m15),
        nas100_m15=Path(args.nas100_m15),
        eurusd_m15=Path(args.eurusd_m15),
        us500_transaction_local_cost=Path(args.us500_transaction_local_cost),
        nas100_c012_transaction_local_cost=Path(args.nas100_c012_transaction_local_cost),
    )
    results = execute_authorized_current_config(
        args.repo_root,
        paths,
        execution_head=args.execution_head,
        execution_ci_run_id=args.execution_ci_run_id,
    )
    written = persist_results(results, args.output_dir)
    print("M6_STAGE_B_CURRENT_CONFIG_EXECUTED_EXACTLY_ONCE")
    for path, result in zip(written, results):
        print(json.dumps({
            "candidate_id": result["candidate_id"],
            "result_sha256": result["result_sha256"],
            "path": str(path),
            "feasibility_status": result["frozen_reporting"]["feasibility_status"],
            "final_equity_eur": result["economic_summary"]["final_equity_eur"],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
