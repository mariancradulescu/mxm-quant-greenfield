"""Manifest-driven M6 acquisition planning, with no economic evaluation.

This module deliberately does not contain broker credentials, strategy logic, candidate
thresholds, resampling rules, or economic outcomes. It converts the frozen
PRIMARY_WAVE_02 data requirements into exact read-only acquisition requests and
validates the frozen acquisition checkpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .evidence import EvidenceError, canonical_json_sha256, expected_dataset_specs

PLAN_SCHEMA = "mxm.greenfield.v2.primary-wave-02-materialization-acquisition-plan.v1"
CAPTURE_REQUEST_SCHEMA = "mxm.greenfield.v2.read-only-capture-request.v1"
BROKER_SYMBOL_PENDING = "UNRESOLVED_PENDING_ONE_TO_ONE_ENABLED_MAPPING"
SOURCE_ENVIRONMENT = "Pepperstone - Europe LIVE"
AUXILIARY_KEYS = (
    "session_semantics",
    "synchronization",
    "currency_conversion",
    "contract_roll",
    "corporate_actions",
    "short_side_requirements",
    "special_requirement",
)


class AcquisitionPlanError(EvidenceError):
    pass


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise AcquisitionPlanError("timestamp must be a string")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AcquisitionPlanError(f"invalid timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise AcquisitionPlanError(f"timestamp is not explicit UTC: {value}")
    return dt.astimezone(timezone.utc)


def _requirements(requirements: Mapping[str, Any]) -> Mapping[str, Any]:
    reqs = requirements.get("requirements")
    if not isinstance(reqs, Mapping) or not reqs:
        raise AcquisitionPlanError("requirements mapping missing")
    return reqs


def derive_auxiliary_evidence(requirements: Mapping[str, Any], candidate_id: str) -> dict[str, Any]:
    """Copy only requirement-declared semantics and add frozen generic evidence gates."""
    reqs = _requirements(requirements)
    if candidate_id not in reqs:
        raise AcquisitionPlanError(f"unknown candidate: {candidate_id}")
    req = reqs[candidate_id]
    copied = {key: req[key] for key in AUXILIARY_KEYS if key in req}
    copied.update({
        "broker_mapping": {
            "instruments": list(req.get("instruments", [])),
            "requirement": "ONE_TO_ONE_ENABLED_PEPPERSTONE_CTRADER_MAPPING_HASH_BOUND",
        },
        "cost_evidence": {
            "components": ["spread", "commission", "slippage_delay_gaps", "financing_swap", "currency_conversion"],
            "allowed_states": ["VERIFIED", "CONSERVATIVE_BOUND", "UNRESOLVED"],
            "verified_rule": "VERIFIED_REQUIRES_APPLICABLE_HISTORICAL_EVIDENCE_NOT_CURRENT_SNAPSHOT",
            "conservative_bound_rule": "PROSPECTIVELY_FROZEN_ADVERSE_OR_EQUAL_ONLY",
            "positive_financing_rule": "NO_POSITIVE_BENEFIT_UNLESS_HISTORICALLY_VERIFIED_FOR_APPLICABLE_TIMESTAMP",
        },
        "eur200_structural_evidence": {
            "method": "BROKER_NATIVE_READ_ONLY_EXPECTED_MARGIN_AT_APPLICABLE_EXECUTABLE_VOLUME_PLUS_PRICE_CONVERSION_COST_TRUTH",
            "metadata_alone_accepted": False,
            "approximate_margin_estimates_accepted": False,
        },
    })
    return copied


def build_primary_tasks(requirements: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Create the exact primary-market materialization tasks from the frozen manifest."""
    tasks: list[dict[str, Any]] = []
    hashes = requirements.get("candidate_spec_hashes", {})
    for spec in expected_dataset_specs(requirements):
        cid = spec["candidate_id"]
        spec_hash = hashes.get(cid)
        if not isinstance(spec_hash, str) or len(spec_hash) != 64:
            raise AcquisitionPlanError(f"{cid}: active spec hash missing")
        did = spec["dataset_id"]
        tasks.append({
            "task_id": f"ACQ-{cid}-{spec['instrument']}-{spec['resolution']}",
            "dataset_id": did,
            "candidate_id": cid,
            "spec_hash": spec_hash,
            "canonical_instrument": spec["instrument"],
            "resolution": spec["resolution"],
            "broker_symbol_state": BROKER_SYMBOL_PENDING,
            "canonical_output_path": f"data/materialized/{did}.csv",
            "binding_output_path": f"data/materialized/{did}.binding.json",
        })
    return tasks


def build_plan(requirements: Mapping[str, Any], *, protected_start_utc: str,
               requirements_git_blob_sha: str) -> dict[str, Any]:
    """Build a deterministic pre-acquisition plan. This function has no side effects."""
    protected = _utc(protected_start_utc)
    reqs = _requirements(requirements)
    for cid, req in reqs.items():
        interval = req.get("interval")
        if not isinstance(interval, Mapping):
            raise AcquisitionPlanError(f"{cid}: interval missing")
        if _utc(interval["end_utc"]) >= protected:
            raise AcquisitionPlanError(f"{cid}: DEVELOPMENT interval reaches protected evidence")
    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "status": "FROZEN_PRE_ACQUISITION_CHECKPOINT",
        "authority": {
            "requirements": "data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V2.json",
            "requirements_git_blob_sha": requirements_git_blob_sha,
            "wave": "discovery/PRIMARY_WAVE_02_PRE_OUTCOME_COMPLETION_V1.json",
            "central_data_manifest": "data/DATA_MANIFEST.json",
        },
        "protected_forward_start": protected_start_utc,
        "protected_evidence_opened": False,
        "acquisition_contract": {
            "manifest_driven_only": True,
            "source_environment": SOURCE_ENVIRONMENT,
            "read_only_broker_access_only": True,
            "orders_forbidden": True,
            "account_mutation_forbidden": True,
            "candidate_identity_changes_forbidden": True,
            "strategy_threshold_or_economic_logic_in_collector_forbidden": True,
            "exact_manifest_resolution_and_interval_required": True,
            "closed_completed_bars_only": True,
            "preserve_real_missing_bars_maintenance_gaps": True,
            "no_resample_no_synthetic_fill_no_forward_fill": True,
            "raw_component_hashes_and_provenance_required": True,
            "metadata_or_expected_hash_is_not_availability": True,
            "no_protected_forward_rows": True,
            "no_unrelated_universe_download": True,
        },
        "primary_dataset_tasks": build_primary_tasks(requirements),
        "requirement_driven_auxiliary_evidence": {
            "derive_verbatim_per_candidate_from_requirements_keys": list(AUXILIARY_KEYS),
            "broker_mapping": "ONE_TO_ONE_ENABLED_PEPPERSTONE_CTRADER_MAPPING_HASH_BOUND_PER_CANONICAL_INSTRUMENT",
            "cost_components": ["spread", "commission", "slippage_delay_gaps", "financing_swap", "currency_conversion"],
            "cost_rule": "VERIFIED requires applicable historical evidence; otherwise only a prospectively frozen ADVERSE_OR_EQUAL CONSERVATIVE_BOUND may resolve a component; current snapshots are not VERIFIED history.",
            "positive_financing_rule": "No positive financing benefit unless historically VERIFIED for the applicable timestamp/period.",
            "eur200_rule": "Only broker-native read-only expected-margin evidence at applicable executable volume plus current price/conversion/cost truth may establish feasibility; metadata or approximate formulas are insufficient.",
        },
        "materialization_sequence": [
            "verify active candidate hash and canonical dataset identity",
            "resolve and hash-bind exact ENABLED broker symbol mapping",
            "acquire exact DEVELOPMENT broker bytes and only manifest-required auxiliary evidence",
            "emit canonical row-level CSV containing every required field with causal provenance",
            "hash raw components, provenance, canonical CSV and immutable dataset binding",
            "verify through m6.evidence.verify_dataset_binding with protected boundary enforced",
            "only then append actual provenance to data/DATA_MANIFEST.json",
            "bind cost evidence separately and run pre-outcome evidence gate",
        ],
        "current_execution_block": {
            "state": "BLOCKED_EXTERNAL_BROKER_READ_ONLY_CAPTURE_REQUIRED",
            "reason": "Current ChatGPT tools can write/test GitHub but provide no authenticated Pepperstone/cTrader historical-data or expected-margin channel; plugin discovery returned no cTrader/Pepperstone connector.",
            "user_action_required": True,
            "required_external_capability": "Authorized read-only Pepperstone cTrader capture returning exact historical bytes, broker mapping/session semantics, and broker-native expected-margin evidence without orders.",
            "forbidden_substitutions": [
                "public-price proxies",
                "approximate margin estimates",
                "current spread/swap snapshots as VERIFIED historical evidence",
                "legacy strategy/economic outputs",
            ],
        },
        "state_invariants": {
            "result_recorded_count": 0,
            "v2_attempts_used": 0,
            "v2_evaluated_identities": 0,
            "economic_outcomes_opened": 0,
            "protected_evidence_opened": False,
            "m6_status": "PENDING",
        },
    }
    plan["plan_sha256"] = canonical_json_sha256(plan, exclude=("plan_sha256",))
    return plan


def validate_plan(plan: Mapping[str, Any], requirements: Mapping[str, Any], *,
                  protected_start_utc: str) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise AcquisitionPlanError("unsupported acquisition plan schema")
    if plan.get("protected_forward_start") != protected_start_utc or plan.get("protected_evidence_opened") is not False:
        raise AcquisitionPlanError("protected-forward state mismatch")
    expected_hash = canonical_json_sha256(plan, exclude=("plan_sha256",))
    if plan.get("plan_sha256") != expected_hash:
        raise AcquisitionPlanError("acquisition plan hash mismatch")
    contract = plan.get("acquisition_contract")
    if not isinstance(contract, Mapping):
        raise AcquisitionPlanError("acquisition contract missing")
    for key in (
        "manifest_driven_only", "read_only_broker_access_only", "orders_forbidden",
        "account_mutation_forbidden", "candidate_identity_changes_forbidden",
        "strategy_threshold_or_economic_logic_in_collector_forbidden",
        "exact_manifest_resolution_and_interval_required", "closed_completed_bars_only",
        "preserve_real_missing_bars_maintenance_gaps", "no_resample_no_synthetic_fill_no_forward_fill",
        "raw_component_hashes_and_provenance_required", "metadata_or_expected_hash_is_not_availability",
        "no_protected_forward_rows", "no_unrelated_universe_download",
    ):
        if contract.get(key) is not True:
            raise AcquisitionPlanError(f"acquisition contract flag not frozen true: {key}")
    if contract.get("source_environment") != SOURCE_ENVIRONMENT:
        raise AcquisitionPlanError("source environment mismatch")

    actual_tasks = plan.get("primary_dataset_tasks")
    expected_tasks = build_primary_tasks(requirements)
    if actual_tasks != expected_tasks:
        raise AcquisitionPlanError("primary acquisition tasks do not exactly match frozen requirements")
    if len(actual_tasks) != 12:
        raise AcquisitionPlanError("PRIMARY_WAVE_02 must expand to exactly 12 primary dataset tasks")

    for cid in sorted(_requirements(requirements)):
        derive_auxiliary_evidence(requirements, cid)
    inv = plan.get("state_invariants")
    if not isinstance(inv, Mapping):
        raise AcquisitionPlanError("state invariants missing")
    if any(inv.get(k) != 0 for k in ("result_recorded_count", "v2_attempts_used", "v2_evaluated_identities", "economic_outcomes_opened")):
        raise AcquisitionPlanError("economic state changed in acquisition plan")
    if inv.get("protected_evidence_opened") is not False or inv.get("m6_status") != "PENDING":
        raise AcquisitionPlanError("protected/M6 state changed in acquisition plan")
    return {"state": "VALID_PRE_ACQUISITION_PLAN", "plan_sha256": expected_hash, "primary_task_count": len(actual_tasks)}


def build_external_capture_request(plan: Mapping[str, Any], requirements: Mapping[str, Any], *,
                                   candidate_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Emit a credential-free request for an external authorized read-only broker adapter."""
    protected = plan.get("protected_forward_start")
    validate_plan(plan, requirements, protected_start_utc=protected)
    selected = set(candidate_ids or sorted(_requirements(requirements)))
    unknown = selected.difference(_requirements(requirements))
    if unknown:
        raise AcquisitionPlanError(f"unknown candidate selection: {sorted(unknown)}")
    tasks = [t for t in plan["primary_dataset_tasks"] if t["candidate_id"] in selected]
    auxiliary = {cid: derive_auxiliary_evidence(requirements, cid) for cid in sorted(selected)}
    request = {
        "schema": CAPTURE_REQUEST_SCHEMA,
        "plan_sha256": plan["plan_sha256"],
        "source_environment": SOURCE_ENVIRONMENT,
        "permission": "READ_ONLY_NO_ORDERS_NO_ACCOUNT_MUTATION",
        "protected_forward_start": protected,
        "primary_dataset_tasks": tasks,
        "auxiliary_evidence": auxiliary,
        "credentials_persisted": False,
        "economic_evaluation_requested": False,
    }
    request["request_sha256"] = canonical_json_sha256(request, exclude=("request_sha256",))
    return request
