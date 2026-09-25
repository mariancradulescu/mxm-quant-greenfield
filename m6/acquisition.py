"""Generic, outcome-blind M6 acquisition planning.

Raw broker market capture is candidate-independent and cached once. Candidate-specific
bindings reference shared raw captures while preserving the frozen causal/session/
synchronization requirements. No economics, protected-forward reads, orders, or account
mutation occur here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .evidence import EvidenceError, canonical_json_sha256, expected_dataset_specs

PLAN_SCHEMA = "mxm.greenfield.v2.primary-wave-02-materialization-acquisition-plan.v2"
CAPTURE_REQUEST_SCHEMA = "mxm.greenfield.v2.read-only-capture-request.v2"
BROKER_SYMBOL_PENDING = "UNRESOLVED_PENDING_ONE_TO_ONE_ENABLED_MAPPING"
SOURCE_ENVIRONMENT = "Pepperstone - Europe LIVE"
RAW_SEMANTICS_PROFILE = "BROKER_NATIVE_COMPLETED_BARS_PRESERVE_SOURCE_GAPS_NO_RESAMPLE_V1"
AUXILIARY_KEYS = (
    "session_semantics",
    "synchronization",
    "currency_conversion",
    "contract_roll",
    "corporate_actions",
    "short_side_requirements",
    "special_requirement",
)
LEGACY_ALLOWED_INPUT_CLASSES = frozenset({
    "INDEPENDENTLY_VERIFIED_BROKER_TRUTH",
    "COMPETITION_TRUTH",
    "VERIFIED_EXECUTION_SEMANTICS",
    "CONTAMINATION_PRIOR_ATTEMPT_ACCOUNTING",
    "RAW_DEVELOPMENT_MARKET_BYTES",
})
LEGACY_FORBIDDEN_INPUT_CLASSES = frozenset({
    "V2_CANDIDATE_SELECTION",
    "MECHANISM_SELECTION",
    "SIGNAL_DEFINITION",
    "ENTRY_EXIT_LOGIC",
    "THRESHOLD",
    "LOOKBACK",
    "PARAMETER",
    "RANKING",
    "CANDIDATE_RESCUE",
    "ECONOMIC_CONCLUSION",
    "SURVIVOR_DECISION",
    "PORTFOLIO_SELECTION",
    "LEGACY_STRATEGY_CODE",
    "LEGACY_CANDIDATE_LOGIC",
    "LEGACY_ECONOMIC_RESULT",
    "LEGACY_PERFORMANCE_CONCLUSION",
    "LEGACY_ALLOCATOR",
})
BROKER_UNIVERSE_ALLOWED_PURPOSES = frozenset({
    "CANONICAL_SYMBOL_MAPPING",
    "ENABLED_STATUS",
    "EXECUTABLE_SYMBOL_IDENTITY",
    "VOLUME_MARGIN_EXECUTION_METADATA",
    "BROKER_STRUCTURAL_FEASIBILITY",
})
BROKER_UNIVERSE_FORBIDDEN_PURPOSES = frozenset({
    "ECONOMIC_SEARCH_UNIVERSE",
    "WHOLE_UNIVERSE_BACKTEST",
    "PRIMARY_WAVE_02_RESELECTION",
    "CANDIDATE_RANKING",
})


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


def _sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def _requirements(requirements: Mapping[str, Any]) -> Mapping[str, Any]:
    reqs = requirements.get("requirements")
    if not isinstance(reqs, Mapping) or not reqs:
        raise AcquisitionPlanError("requirements mapping missing")
    return reqs


def classify_historical_bytes(*, data_end_utc: str, protected_start_utc: str,
                              acquisition_utc: str | None = None) -> str:
    """Classification follows historical timestamp, never download freshness."""
    del acquisition_utc
    if _utc(data_end_utc) < _utc(protected_start_utc):
        return "DEVELOPMENT"
    raise AcquisitionPlanError("data reaching protected-forward cannot enter DEVELOPMENT acquisition")


def validate_legacy_v1_input(input_class: str, *, provenance_sha256: str | None = None,
                             historical_classification: str | None = None) -> dict[str, str]:
    """Enforce the hard clean-room boundary on any legacy/V1 input."""
    if input_class in LEGACY_FORBIDDEN_INPUT_CLASSES or input_class not in LEGACY_ALLOWED_INPUT_CLASSES:
        raise AcquisitionPlanError(f"legacy/V1 input forbidden: {input_class}")
    if input_class == "RAW_DEVELOPMENT_MARKET_BYTES":
        if historical_classification != "DEVELOPMENT" or not _sha256(provenance_sha256):
            raise AcquisitionPlanError(
                "legacy raw bytes require DEVELOPMENT classification and immutable provenance hash"
            )
    return {"state": "ALLOWED_BOUNDARY_INPUT", "input_class": input_class}


def validate_broker_universe_use(purpose: str) -> dict[str, str]:
    if purpose in BROKER_UNIVERSE_FORBIDDEN_PURPOSES or purpose not in BROKER_UNIVERSE_ALLOWED_PURPOSES:
        raise AcquisitionPlanError(f"broker universe use forbidden in this phase: {purpose}")
    return {"state": "ALLOWED_STRUCTURAL_METADATA_USE", "purpose": purpose}


def derive_auxiliary_evidence(requirements: Mapping[str, Any], candidate_id: str) -> dict[str, Any]:
    """Copy only frozen requirement-declared auxiliary semantics; never invent strategy logic."""
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
            "allowed_states": ["VERIFIED", "CONSERVATIVE_BOUND", "UNRESOLVED"],
            "verified_rule": "VERIFIED_REQUIRES_APPLICABLE_HISTORICAL_EVIDENCE_NOT_CURRENT_SNAPSHOT",
            "conservative_bound_rule": "PROSPECTIVELY_FROZEN_ADVERSE_OR_EQUAL_ONLY",
            "positive_financing_rule":
                "NO_POSITIVE_BENEFIT_UNLESS_HISTORICALLY_VERIFIED_FOR_APPLICABLE_TIMESTAMP",
        },
        "eur200_structural_evidence": {
            "method":
                "BROKER_NATIVE_READ_ONLY_EXPECTED_MARGIN_AT_APPLICABLE_EXECUTABLE_VOLUME_PLUS_PRICE_CONVERSION_COST_TRUTH",
            "metadata_alone_accepted": False,
            "approximate_margin_estimates_accepted": False,
        },
    })
    return copied


def _raw_defaults(requirements: Mapping[str, Any]) -> dict[str, Any]:
    reqs = _requirements(requirements)
    intervals = {canonical_json_sha256(req["interval"]): req["interval"] for req in reqs.values()}
    if len(intervals) != 1:
        raise AcquisitionPlanError("PRIMARY_WAVE_02 raw capture interval is not common")
    interval = dict(next(iter(intervals.values())))
    return {
        "source_environment": SOURCE_ENVIRONMENT,
        "interval": interval,
        "timezone": "UTC",
        "raw_broker_semantics_profile": RAW_SEMANTICS_PROFILE,
    }


def _raw_identity(defaults: Mapping[str, Any], instrument: str, resolution: str) -> dict[str, Any]:
    return {
        "source_environment": defaults["source_environment"],
        "canonical_instrument": instrument,
        "resolution": resolution,
        "interval": dict(defaults["interval"]),
        "timezone": defaults["timezone"],
        "raw_broker_semantics_profile": defaults["raw_broker_semantics_profile"],
    }


def build_unique_raw_capture_tasks(requirements: Mapping[str, Any]) -> list[dict[str, Any]]:
    defaults = _raw_defaults(requirements)
    unique: dict[str, dict[str, Any]] = {}
    for spec in expected_dataset_specs(requirements):
        identity = _raw_identity(defaults, spec["instrument"], spec["resolution"])
        digest = canonical_json_sha256(identity)
        raw_id = f"PW02-RAW-{spec['instrument']}-{spec['resolution']}-{digest[:16]}"
        task = {
            "raw_capture_id": raw_id,
            "raw_identity_sha256": digest,
            "canonical_instrument": spec["instrument"],
            "resolution": spec["resolution"],
            "broker_symbol_state": BROKER_SYMBOL_PENDING,
            "actual_bytes_sha256": None,
        }
        if raw_id in unique and unique[raw_id] != task:
            raise AcquisitionPlanError(f"raw capture identity collision: {raw_id}")
        unique[raw_id] = task
    return sorted(
        unique.values(),
        key=lambda item: (item["canonical_instrument"], item["resolution"], item["raw_capture_id"]),
    )


def _candidate_semantics(req: Mapping[str, Any]) -> dict[str, Any]:
    return {key: req[key] for key in AUXILIARY_KEYS if key in req}


def build_candidate_dataset_bindings(requirements: Mapping[str, Any]) -> list[dict[str, Any]]:
    reqs = _requirements(requirements)
    hashes = requirements.get("candidate_spec_hashes", {})
    raw_lookup = {
        (task["canonical_instrument"], task["resolution"]): task
        for task in build_unique_raw_capture_tasks(requirements)
    }
    bindings: list[dict[str, Any]] = []
    for spec in expected_dataset_specs(requirements):
        cid = spec["candidate_id"]
        spec_hash = hashes.get(cid)
        if not _sha256(spec_hash):
            raise AcquisitionPlanError(f"{cid}: active spec hash missing")
        raw = raw_lookup[(spec["instrument"], spec["resolution"])]
        bindings.append({
            "binding_id": f"PW02-BIND-{cid}-{spec['instrument']}-{spec['resolution']}",
            "candidate_id": cid,
            "spec_hash": spec_hash,
            "dataset_id": spec["dataset_id"],
            "canonical_instrument": spec["instrument"],
            "resolution": spec["resolution"],
            "raw_capture_id": raw["raw_capture_id"],
            "raw_identity_sha256": raw["raw_identity_sha256"],
            "semantic_requirements_sha256": canonical_json_sha256(_candidate_semantics(reqs[cid])),
        })
    return bindings


def build_plan(requirements: Mapping[str, Any], *, protected_start_utc: str,
               requirements_git_blob_sha: str) -> dict[str, Any]:
    protected = _utc(protected_start_utc)
    reqs = _requirements(requirements)
    for cid, req in reqs.items():
        interval = req.get("interval")
        if not isinstance(interval, Mapping):
            raise AcquisitionPlanError(f"{cid}: interval missing")
        if _utc(interval["end_utc"]) >= protected:
            raise AcquisitionPlanError(f"{cid}: DEVELOPMENT interval reaches protected evidence")
        if classify_historical_bytes(
            data_end_utc=interval["end_utc"],
            protected_start_utc=protected_start_utc,
            acquisition_utc="IGNORED",
        ) != "DEVELOPMENT":
            raise AcquisitionPlanError(f"{cid}: pre-protected history not DEVELOPMENT")

    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "status": "FROZEN_PRE_ACQUISITION_CHECKPOINT",
        "supersedes": {
            "path": "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V1.json",
            "plan_sha256": "69e59ffd14d2402f838a86519b22c2362e96c76470bb847a4754cf41b2517971",
            "preserved_unchanged": True,
            "reason": "STRUCTURAL_RAW_CAPTURE_DEDUPLICATION_ONLY_NO_CANDIDATE_OR_ECONOMIC_CHANGE",
        },
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
            "capture_each_unique_raw_series_once": True,
            "candidate_bindings_reference_shared_raw_capture": True,
            "auxiliary_evidence_is_separate_from_raw_ohlc_identity": True,
            "download_freshness_is_not_evidence_freshness": True,
        },
        "raw_capture_identity_contract": {
            "candidate_id_in_raw_identity": False,
            "identity_components": [
                "raw_capture_defaults.source_environment",
                "canonical_instrument",
                "resolution",
                "raw_capture_defaults.interval",
                "raw_capture_defaults.timezone",
                "raw_capture_defaults.raw_broker_semantics_profile",
            ],
            "must_remain_distinct_when_any_identity_component_differs": True,
            "actual_raw_bytes_hashed_once_after_capture": True,
            "candidate_bindings_must_reference_same_raw_hash_for_shared_capture": True,
        },
        "unique_raw_capture_tasks": build_unique_raw_capture_tasks(requirements),
        "candidate_dataset_bindings": build_candidate_dataset_bindings(requirements),
        "legacy_contamination_boundary": {
            "allowed_input_classes": sorted(LEGACY_ALLOWED_INPUT_CLASSES),
            "forbidden_input_classes": sorted(LEGACY_FORBIDDEN_INPUT_CLASSES),
            "raw_development_bytes_rule":
                "ALLOWED_ONLY_WITH_VALID_IMMUTABLE_PROVENANCE_HASH_AND_DEVELOPMENT_CLASSIFICATION",
            "legacy_may_never_influence_v2_research_choices_or_economic_conclusions": True,
            "forbidden_named_reconstruction_or_import": [
                "A-series strategy logic", "PF01", "PF02", "BNY", "legacy allocators",
                "old experts", "old signals", "old thresholds", "old candidate rankings",
                "old economic outcomes",
            ],
        },
        "data_classification_rule": {
            "basis": "HISTORICAL_TIMESTAMP_NOT_DOWNLOAD_DATE",
            "pre_protected_history_classification": "DEVELOPMENT",
            "fresh_reacquisition_does_not_create_untouched_or_oos_evidence": True,
            "protected_forward_start_immutable": protected_start_utc,
        },
        "broker_universe_rule": {
            "allowed_purposes": sorted(BROKER_UNIVERSE_ALLOWED_PURPOSES),
            "forbidden_purposes": sorted(BROKER_UNIVERSE_FORBIDDEN_PURPOSES),
            "broker_universe_may_not_change_primary_wave_02_selection": True,
            "whole_universe_backtest_forbidden": True,
        },
        "historical_live_parity": {
            "discovery":
                "CAUSAL_DEVELOPMENT_EVALUATION_VECTORIZED_ONLY_WHEN_MATHEMATICALLY_EQUIVALENT_AND_CAUSAL",
            "certification": "STRICT_INCREMENTAL_CHRONOLOGICAL_REPLAY_AS_IF_TIME_WERE_FLOWING_LIVE",
            "information_at_t_only": True,
            "future_bars_forbidden": True,
            "future_normalization_forbidden": True,
            "hindsight_forbidden": True,
            "retrospective_fills_forbidden": True,
            "future_broker_state_forbidden": True,
            "future_regime_knowledge_forbidden": True,
            "final_architecture": [
                "SHARED_DETERMINISTIC_ECONOMIC_CORE",
                "HISTORICAL_REPLAY_ADAPTER",
                "CTRADER_LIVE_ADAPTER",
            ],
        },
        "requirement_driven_auxiliary_evidence": {
            "derive_verbatim_per_candidate_from_requirements_keys": list(AUXILIARY_KEYS),
            "separate_from_raw_market_capture": True,
        },
        "current_execution_block": {
            "state": "BLOCKED_EXTERNAL_BROKER_READ_ONLY_CAPTURE_REQUIRED",
            "user_action_required": True,
            "required_external_capability":
                "Authorized read-only Pepperstone cTrader capture returning exact historical bytes plus immutable provenance/hash evidence; no orders or account mutation.",
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
        "raw_capture_defaults": _raw_defaults(requirements),
    }
    plan["plan_sha256"] = canonical_json_sha256(plan, exclude=("plan_sha256",))
    return plan


def validate_plan(plan: Mapping[str, Any], requirements: Mapping[str, Any], *,
                  protected_start_utc: str) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise AcquisitionPlanError("unsupported acquisition plan schema")
    if plan.get("protected_forward_start") != protected_start_utc:
        raise AcquisitionPlanError("protected-forward timestamp mismatch")
    if plan.get("protected_evidence_opened") is not False:
        raise AcquisitionPlanError("protected evidence state changed")
    if plan.get("plan_sha256") != canonical_json_sha256(plan, exclude=("plan_sha256",)):
        raise AcquisitionPlanError("acquisition plan hash mismatch")

    if plan.get("unique_raw_capture_tasks") != build_unique_raw_capture_tasks(requirements):
        raise AcquisitionPlanError("unique raw capture tasks differ from frozen requirements")
    if plan.get("candidate_dataset_bindings") != build_candidate_dataset_bindings(requirements):
        raise AcquisitionPlanError("candidate bindings differ from frozen requirements")
    if plan.get("raw_capture_defaults") != _raw_defaults(requirements):
        raise AcquisitionPlanError("raw capture defaults differ from frozen requirements")

    raw_tasks = plan["unique_raw_capture_tasks"]
    bindings = plan["candidate_dataset_bindings"]
    if len(raw_tasks) != 11 or len({t["raw_capture_id"] for t in raw_tasks}) != 11:
        raise AcquisitionPlanError("PRIMARY_WAVE_02 must contain exactly 11 unique raw captures")
    if len(bindings) != 12:
        raise AcquisitionPlanError("PRIMARY_WAVE_02 must retain exactly 12 candidate bindings")

    c006 = next(
        b for b in bindings
        if b["candidate_id"] == "V2-C006" and b["canonical_instrument"] == "US500"
    )
    c012 = next(
        b for b in bindings
        if b["candidate_id"] == "V2-C012" and b["canonical_instrument"] == "US500"
    )
    if (c006["raw_capture_id"], c006["raw_identity_sha256"]) != (
        c012["raw_capture_id"], c012["raw_identity_sha256"]
    ):
        raise AcquisitionPlanError("C006/C012 US500 M15 do not share one raw identity")
    if c006["semantic_requirements_sha256"] == c012["semantic_requirements_sha256"]:
        raise AcquisitionPlanError("C006/C012 semantic bindings were collapsed")

    boundary = plan.get("legacy_contamination_boundary", {})
    if boundary.get("legacy_may_never_influence_v2_research_choices_or_economic_conclusions") is not True:
        raise AcquisitionPlanError("legacy contamination boundary weakened")
    universe = plan.get("broker_universe_rule", {})
    if universe.get("broker_universe_may_not_change_primary_wave_02_selection") is not True:
        raise AcquisitionPlanError("broker universe selection boundary weakened")
    classification = plan.get("data_classification_rule", {})
    if classification.get("pre_protected_history_classification") != "DEVELOPMENT":
        raise AcquisitionPlanError("pre-protected history classification changed")

    inv = plan.get("state_invariants", {})
    for key in ("result_recorded_count", "v2_attempts_used", "v2_evaluated_identities",
                "economic_outcomes_opened"):
        if inv.get(key) != 0:
            raise AcquisitionPlanError("economic state changed in acquisition plan")
    if inv.get("protected_evidence_opened") is not False or inv.get("m6_status") != "PENDING":
        raise AcquisitionPlanError("protected/M6 state changed in acquisition plan")
    return {
        "state": "VALID_PRE_ACQUISITION_PLAN",
        "plan_sha256": plan["plan_sha256"],
        "unique_raw_capture_count": len(raw_tasks),
        "candidate_binding_count": len(bindings),
    }


def build_external_capture_request(plan: Mapping[str, Any], requirements: Mapping[str, Any], *,
                                   candidate_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Produce candidate-scoped read-only capture request with shared raw captures deduplicated."""
    protected = plan.get("protected_forward_start")
    validate_plan(plan, requirements, protected_start_utc=protected)
    selected = set(candidate_ids or sorted(_requirements(requirements)))
    unknown = selected.difference(_requirements(requirements))
    if unknown:
        raise AcquisitionPlanError(f"unknown candidate selection: {sorted(unknown)}")
    bindings = [b for b in plan["candidate_dataset_bindings"] if b["candidate_id"] in selected]
    needed = {b["raw_capture_id"] for b in bindings}
    raw_tasks = [t for t in plan["unique_raw_capture_tasks"] if t["raw_capture_id"] in needed]
    request = {
        "schema": CAPTURE_REQUEST_SCHEMA,
        "plan_sha256": plan["plan_sha256"],
        "source_environment": SOURCE_ENVIRONMENT,
        "permission": "READ_ONLY_NO_ORDERS_NO_ACCOUNT_MUTATION",
        "protected_forward_start": protected,
        "raw_capture_defaults": plan["raw_capture_defaults"],
        "unique_raw_capture_tasks": raw_tasks,
        "candidate_dataset_bindings": bindings,
        "auxiliary_evidence": {
            cid: derive_auxiliary_evidence(requirements, cid) for cid in sorted(selected)
        },
        "credentials_persisted": False,
        "economic_evaluation_requested": False,
    }
    request["request_sha256"] = canonical_json_sha256(request, exclude=("request_sha256",))
    return request
