"""Prospective, outcome-blind Epoch42 mean-reversion cohort/power design."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from research_v3.mean_reversion_cohort_power_design import (
    DesignError,
    audit_prior_scope_distinctness,
    load_prior_freeze_scopes,
    required_effective_sample_size,
)

VERSION = "MXM_EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT_V1"
FREEZE_REF = "research_v3/EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_e32a4b75e24fa8b92aaa3effdce7d093.json"
PROPOSAL_FILE_SHA256 = "c590959baabd63a15a93b9c675cc08c3e727e31a0ab9634dfe06a08e80d56875"
PROPOSAL_HASH = "7792544546520fe7db374a8654036c452f70b009aa50491c1245edd760eaf3ad"
FEASIBILITY_REF = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"
FEATURE_STORE_REF = "research_v3/BROKER_NATIVE_FRONTIER_FEATURE_STORE_EPOCH23_V1.json"
EPOCH39_FREEZE_REF = "research_v3/EPOCH39_MEAN_REVERSION_SCOPE_POWER_PREFLIGHT_FREEZE_V1.json"
EPOCH40_INVENTORY_REF = "evidence/EPOCH40_MEAN_REVERSION_STAGE1_TRIAGE_RESULT_V1.json"
EPOCH41_PREFLIGHT_REF = "evidence/EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT_V1.json"
IDENTITY_COUNT = 1576
IDENTITY_SET_SHA256 = "e53dc4e58d4e0d37eca4f528e06d0866ad8ffe3f2bc64d35278ecc8ee9f52a65"
BROKER_PAYLOAD_SHA256 = "7b268eae05fad325cb1f0fc962511ca41236b3b58bb83023735fd22b94301452"
FEATURE_STORE_SHA256 = "b92ad33bffad77f00b86933e1f552736485782e17fdea98fd0e84d1ab6dd117c"
EPOCH40_SHA256 = "133197a1b592b401a825a6bebce5a358c8a606c5829353b55271bb2fe00dc562"
EPOCH41_SHA256 = "53e89e7cad0c7e70d1b87b3db3481ea57b6db70fa315f968bdba7db286a65435"
LOOKBACKS = (12, 24, 48, 96)
THRESHOLDS = (1.0, 1.5, 2.0)
HORIZONS = (3, 6, 12)
EFFECT_SCENARIOS = (0.2, 0.3, 0.5)
TARGET_POWER = 0.8
FAMILYWISE_ALPHA = 0.05


class PreflightError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightError(f"required authority is missing or unreadable: {relative}") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"required authority must be a JSON object: {relative}")
    return value


def _validate_freeze(root: Path, freeze: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if (
        freeze.get("schema")
        != "mxm.greenfield.epoch42-mean-reversion-cohort-power-preflight-freeze.v1"
        or freeze.get("status")
        != "PROSPECTIVELY_FROZEN_NON_ECONOMIC_HYPOTHESIS_AND_POWER_PREFLIGHT"
        or freeze.get("evidence_epoch") != 42
    ):
        raise PreflightError("unsupported or unprospectively frozen Epoch42 design")

    authority = freeze.get("authority") or {}
    expected_authority = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
        "accepted_proposal_hash": PROPOSAL_HASH,
        "proposal_id": "AUTO_E42_MR_COHORT_POWER",
        "feasibility_authority_ref": FEASIBILITY_REF,
        "feasibility_payload_sha256": BROKER_PAYLOAD_SHA256,
        "eligible_identity_count": IDENTITY_COUNT,
        "eligible_identity_set_sha256": IDENTITY_SET_SHA256,
        "feature_store_ref": FEATURE_STORE_REF,
        "feature_store_sha256": FEATURE_STORE_SHA256,
        "accepted_development_inventory_ref": EPOCH40_INVENTORY_REF,
        "accepted_development_inventory_sha256": EPOCH40_SHA256,
        "accepted_coverage_preflight_ref": EPOCH41_PREFLIGHT_REF,
        "accepted_coverage_preflight_sha256": EPOCH41_SHA256,
    }
    if any(authority.get(key) != value for key, value in expected_authority.items()):
        raise PreflightError("freeze does not bind the accepted proposal and source authorities")

    proposal_path = root / PROPOSAL_REF
    if not proposal_path.is_file() or _sha256(proposal_path) != PROPOSAL_FILE_SHA256:
        raise PreflightError("accepted proposal file-byte hash mismatch")
    proposal = _read_json(root, PROPOSAL_REF)
    proposal_design = ((proposal.get("decision") or {}).get("implementation_scope") or {})
    decision = proposal.get("decision") or {}
    if (
        proposal.get("proposal_id") != "AUTO_E42_MR_COHORT_POWER"
        or proposal.get("proposal_hash") not in (None, PROPOSAL_HASH)
        or decision.get("hypothesis")
        != "Test whether a volatility-normalized one-sided price excursion is followed by signed displacement toward a causal trailing center at predeclared horizons. Treat independent excursion clusters, not M5 bars, as the primary information units."
        or (proposal.get("data_policy") or {}).get("new_market_data_requested") is not False
        or proposal_design.get("next_action")
        != "IMPLEMENT_PROSPECTIVE_MEAN_REVERSION_HYPOTHESIS_AND_POWER_PREFLIGHT"
    ):
        raise PreflightError("accepted proposal scope or non-economic data policy mismatch")

    feasibility = _read_json(root, FEASIBILITY_REF)
    counts = feasibility.get("current_counts") or {}
    if (
        feasibility.get("schema")
        != "mxm.greenfield.pepperstone-current-eur200-feasibility-authority.v2"
        or feasibility.get("status") != "CURRENT_EPOCH22_BROKER_NATIVE_AUTHORITY"
        or feasibility.get("exact_current_eligible_identity_set_sha256") != IDENTITY_SET_SHA256
        or feasibility.get("source_canonical_payload_sha256") != BROKER_PAYLOAD_SHA256
        or counts.get("current_eligible_post_exclusion_frontier") != IDENTITY_COUNT
    ):
        raise PreflightError("current feasibility authority differs from the frozen sampling frame")
    if _sha256(root / FEATURE_STORE_REF) != FEATURE_STORE_SHA256:
        raise PreflightError("accepted frontier feature-store byte hash mismatch")
    if _sha256(root / EPOCH40_INVENTORY_REF) != EPOCH40_SHA256:
        raise PreflightError("accepted Epoch40 inventory byte hash mismatch")
    if _sha256(root / EPOCH41_PREFLIGHT_REF) != EPOCH41_SHA256:
        raise PreflightError("accepted Epoch41 preflight byte hash mismatch")

    epoch39 = _read_json(root, EPOCH39_FREEZE_REF)
    grid = ((epoch39.get("design") or {}).get("coarse_parameter_regions") or {})
    if (
        tuple(grid.get("lookback_bars") or ()) != LOOKBACKS
        or tuple(grid.get("absolute_standardized_deviation_threshold") or ()) != THRESHOLDS
        or tuple(grid.get("holding_horizon_bars") or ()) != HORIZONS
        or grid.get("cell_count") != len(LOOKBACKS) * len(THRESHOLDS) * len(HORIZONS)
    ):
        raise PreflightError("referenced Epoch39 parameter grid does not match the frozen reuse")

    scope = freeze.get("scope") or {}
    design = freeze.get("parameter_design") or {}
    hypothesis = freeze.get("hypothesis") or {}
    event = hypothesis.get("event_definition") or {}
    response = hypothesis.get("response_estimand") or {}
    multiplicity = design.get("multiplicity") or {}
    temporal = freeze.get("temporal_and_missingness") or {}
    data_boundary = freeze.get("data_boundary") or {}
    if (
        scope.get("sampling_frame_size") != IDENTITY_COUNT
        or scope.get("identity_set_sha256") != IDENTITY_SET_SHA256
        or scope.get("selected_cohort") is not None
        or scope.get("structural_41_default_inferential_authority") is not False
        or design.get("lookback_bars") != list(LOOKBACKS)
        or design.get("absolute_z_thresholds") != list(THRESHOLDS)
        or design.get("horizons_bars") != list(HORIZONS)
        or design.get("cell_count") != 36
        or multiplicity.get("primary_family_size") != 36
        or multiplicity.get("one_sided_familywise_alpha") != FAMILYWISE_ALPHA
        or multiplicity.get("per_cell_bonferroni_alpha") != FAMILYWISE_ALPHA / 36
        or multiplicity.get("power_sensitivity_effects") != list(EFFECT_SCENARIOS)
        or multiplicity.get("target_power") != TARGET_POWER
        or multiplicity.get("effect_scenarios_are_economic_thresholds") is not False
        or event.get("resolution") != "M5"
        or event.get("center")
        != "Arithmetic mean of the frozen trailing lookback closes ending at the event close."
        or event.get("scale")
        != "Population standard deviation of those same contiguous trailing closes."
        or event.get("cluster_unit")
        != "For each symbol, begin one excursion cluster on the first threshold crossing from inside the neutral band. Admit no repeat event while z remains in that tail; a return inside the band rearms the next cluster, and a direct crossing into the opposite tail starts a new opposite cluster."
        or response.get("upper_excursion")
        != "ln(close_t / close_t_plus_h) / (sigma_t * sqrt(h))"
        or response.get("lower_excursion")
        != "ln(close_t_plus_h / close_t) / (sigma_t * sqrt(h))"
        or response.get("primary_unit")
        != "Independent excursion cluster, with dependence-aware UTC date/session clustering and pooled cohort inference only when outcome-blind coherence supports pooling."
        or temporal.get("response_sample_must_be_disjoint_from_prior_epoch25_epoch36_observation_window")
        is not True
        or temporal.get("prior_observation_window_end_utc") != "2026-09-13T23:59:59Z"
        or temporal.get("future_response_evaluation_authorized_in_this_phase") is not False
        or data_boundary.get("new_market_data_requested") is not False
        or data_boundary.get("new_market_data_or_collector_authorized") is not False
    ):
        raise PreflightError("frozen cohort, hypothesis, or parameter design is inconsistent")

    for section in (freeze.get("interpretation_boundary") or {}, freeze.get("safety") or {}):
        if any(value is not False for key, value in section.items() if isinstance(value, bool)):
            raise PreflightError("freeze crosses a prohibited economic or safety boundary")
    if freeze.get("accounting_effect") != {
        "economic_outcomes_opened": 0,
        "v2_attempts_consumed": 0,
        "search_budget_change": 0,
    }:
        raise PreflightError("freeze declares a prohibited accounting effect")

    inventory = _read_json(root, EPOCH40_INVENTORY_REF)
    coverage = inventory.get("coverage") or {}
    accepted_coverage = _read_json(root, EPOCH41_PREFLIGHT_REF).get("accepted_data_coverage") or {}
    if (
        inventory.get("schema")
        != "mxm.greenfield.epoch40-mean-reversion-stage1-outcome-blind-triage.v1"
        or coverage.get("eligible_identities") != IDENTITY_COUNT
        or coverage.get("identities_with_verified_m5_bars") != 45
        or coverage.get("other_accepted_capture_scopes")
        != "NOT_MATERIALIZED_OR_HASH_VERIFIED_IN_THIS_RUN; no absence claim"
        or accepted_coverage.get("identities_with_verified_m5_bars") != 45
        or accepted_coverage.get("absence_claim_for_other_capture_scopes") is not False
    ):
        raise PreflightError("bounded accepted-data inventory no longer matches its stated scope")

    try:
        prior_scopes = load_prior_freeze_scopes(root)
        candidate = {
            "event_definition": hypothesis["event_definition"],
            "response_estimand": hypothesis["response_estimand"],
            "causal_timing": hypothesis["causal_timing"],
            "lookback_bars": list(LOOKBACKS),
            "threshold": list(THRESHOLDS),
            "horizon_bars": list(HORIZONS),
            "anchor_stride_bars": "FIRST_CROSSING_PER_EXCURSION_CLUSTER",
        }
        prior_audit = audit_prior_scope_distinctness(candidate, prior_scopes)
    except (DesignError, KeyError) as exc:
        raise PreflightError("prior-scope distinctness audit could not be completed") from exc
    if any(
        item["classification"] != "STRUCTURAL_DIFFERENCE_REQUIRES_PROSPECTIVE_JUDGMENT"
        for item in prior_audit["comparisons"].values()
    ):
        raise PreflightError("candidate scope is not structurally distinct from both prior freezes")
    return prior_scopes, prior_audit, inventory, accepted_coverage


def build_preflight(root: str | Path = ".") -> dict[str, Any]:
    repository = Path(root).resolve()
    freeze = _read_json(repository, FREEZE_REF)
    prior_scopes, prior_audit, inventory, accepted_coverage = _validate_freeze(
        repository, freeze
    )
    del prior_scopes
    cell_count = len(LOOKBACKS) * len(THRESHOLDS) * len(HORIZONS)
    scenarios = [
        {
            "standardized_effect": effect,
            "required_effective_independent_clusters": required_effective_sample_size(
                effect,
                hypothesis_count=cell_count,
                target_power=TARGET_POWER,
                familywise_alpha=FAMILYWISE_ALPHA,
            ),
            "target_power": TARGET_POWER,
            "familywise_alpha": FAMILYWISE_ALPHA,
            "hypothesis_count": cell_count,
            "interpretation": "PLANNING_SENSITIVITY_ONLY_NOT_AN_ECONOMIC_THRESHOLD",
        }
        for effect in EFFECT_SCENARIOS
    ]
    observed = inventory["coverage"]["identities_with_verified_m5_bars"]
    return {
        "schema": "mxm.greenfield.epoch42-mean-reversion-cohort-power-preflight.v1",
        "status": "COMPLETE_NON_ECONOMIC_HYPOTHESIS_AND_POWER_PREFLIGHT",
        "family": "MEAN_REVERSION",
        "evidence_epoch": 42,
        "implementation": {"version": VERSION, "freeze_ref": FREEZE_REF},
        "freeze_sha256": _sha256(repository / FREEZE_REF),
        "source_authority": {
            "accepted_proposal_ref": PROPOSAL_REF,
            "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
            "accepted_proposal_hash": PROPOSAL_HASH,
            "feasibility_authority_ref": FEASIBILITY_REF,
            "eligible_identity_count": IDENTITY_COUNT,
            "eligible_identity_set_sha256": IDENTITY_SET_SHA256,
            "feature_store_ref": FEATURE_STORE_REF,
            "accepted_development_inventory_ref": EPOCH40_INVENTORY_REF,
            "accepted_coverage_preflight_ref": EPOCH41_PREFLIGHT_REF,
            "prior_freeze_refs": [
                "research_v3/EPOCH25_MEAN_REVERSION_FRONTIER_FREEZE_V1.json",
                "research_v3/EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_FRONTIER_FREEZE_V1.json",
            ],
            "prior_result_artifacts_read": False,
        },
        "novelty_audit": {
            **prior_audit,
            "accepted_proposal_authorizes_design_only": True,
            "response_statistic_evaluated": False,
            "same_observation_window_reused": False,
        },
        "hypothesis": freeze["hypothesis"],
        "sampling_frame": {
            "eligible_identity_count": IDENTITY_COUNT,
            "eligible_identity_set_sha256": IDENTITY_SET_SHA256,
            "structural_41_used_as_inferential_universe": False,
            "selected_inferential_cohort": None,
            "cohort_selection_status": "NOT_ESTIMABLE_FROM_BOUNDED_ACCEPTED_INVENTORIES",
            "outcome_blind_selection": True,
            "selection_rule": freeze["scope"]["cohort_rule"],
        },
        "accepted_data_coverage": {
            "bounded_inventory_ref": EPOCH40_INVENTORY_REF,
            "bounded_inventory_verified_m5_identities": observed,
            "eligible_sampling_frame_identities": IDENTITY_COUNT,
            "other_accepted_capture_scopes": "NOT_MATERIALIZED_OR_HASH_VERIFIED_IN_THIS_RUN; no absence claim",
            "unmaterialized_hash_bound_capture_bytes_are_new_acquisition": False,
            "full_frame_history_completeness": "NOT_ESTABLISHED",
            "event_cluster_count": None,
            "effective_independent_cluster_count": None,
            "regime_context_inventory_ref": EPOCH41_PREFLIGHT_REF,
            "regime_inventory_summary": {
                "identities_with_verified_m5_bars": accepted_coverage[
                    "identities_with_verified_m5_bars"
                ],
                "other_accepted_capture_scopes": accepted_coverage[
                    "other_accepted_capture_scopes"
                ],
            },
        },
        "power_preflight": {
            "status": "NOT_ESTIMABLE_WITHOUT_ACCEPTED_DISJOINT_EVENT_INVENTORY",
            "observed_effective_sample_size": None,
            "planning_sensitivity": scenarios,
            "achieved_power_estimated": False,
            "response_statistics_computed": False,
        },
        "temporal_boundary": freeze["temporal_and_missingness"],
        "data_boundary": freeze["data_boundary"],
        "interpretation_boundary": {
            **freeze["interpretation_boundary"],
            "economic_promotion_authorized": False,
        },
        "accounting_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "search_budget_change": 0,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "competition_start_authorized": False,
        },
        "next_gate": "Fresh prospective reasoning must audit exact accepted capture scopes and define any minimal disjoint data increment before evaluating response statistics. Existing hash-bound bytes may be transport-materialized without being called new acquisition.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = build_preflight(args.root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "cohort_selection_status": result["sampling_frame"][
                    "cohort_selection_status"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
