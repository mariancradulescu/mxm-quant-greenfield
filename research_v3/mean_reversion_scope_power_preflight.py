from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any

VERSION = "MXM_EPOCH39_MEAN_REVERSION_SCOPE_POWER_PREFLIGHT_V1"
FREEZE_REF = "research_v3/EPOCH39_MEAN_REVERSION_SCOPE_POWER_PREFLIGHT_FREEZE_V1.json"
FREEZE_SCHEMA = "mxm.greenfield.epoch39-mean-reversion-scope-power-preflight-freeze.v1"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_44ec982538d0519ed46c879423c096b6.json"
PROPOSAL_FILE_SHA256 = "9feec0b687b66e18685535bf023833343fcb3812bb88cc3921f57cc65d065f39"
PROPOSAL_ID = "AI_E39_MEAN_REVERSION_SCOPE_PREFLIGHT"
PROPOSAL_HASH = "0990efaed7c085f0926117349545570bfd7f0e141f1f5aada4ebd598a9226671"
FEASIBILITY_REF = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"
FEASIBILITY_ACCEPTANCE_REF = "evidence/BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_EPOCH22_ACCEPTANCE_V1.json"
ARCHITECTURE_REF = "research_v3/ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE_V1.json"
PARAMETER_GOVERNOR_REF = "research_v3/PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1.json"
EXPECTED_IDENTITY_COUNT = 1576
EXPECTED_IDENTITY_SET_SHA256 = "e53dc4e58d4e0d37eca4f528e06d0866ad8ffe3f2bc64d35278ecc8ee9f52a65"
EXPECTED_CANONICAL_PAYLOAD_SHA256 = "7b268eae05fad325cb1f0fc962511ca41236b3b58bb83023735fd22b94301452"
LOOKBACKS = (12, 24, 48, 96)
THRESHOLDS = (1.0, 1.5, 2.0)
HORIZONS = (3, 6, 12)
EFFECT_SCENARIOS = (0.2, 0.3, 0.5)
TARGET_POWER = 0.8
FDR_Q = 0.05


class PreflightError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise PreflightError(f"required authority missing: {relative}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightError(f"required authority is unreadable: {relative}") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"required authority is not an object: {relative}")
    return value


def validate_freeze(freeze: dict[str, Any], root: str | Path = ".") -> None:
    repository = Path(root)
    if freeze.get("schema") != FREEZE_SCHEMA or freeze.get("status") != (
        "PROSPECTIVELY_FROZEN_BEFORE_MEAN_REVERSION_SCOPE_POWER_PREFLIGHT"
    ):
        raise PreflightError("unsupported or unprospectively frozen preflight")
    authority = freeze.get("authority") or {}
    if (
        authority.get("accepted_proposal_ref") != PROPOSAL_REF
        or authority.get("accepted_proposal_file_sha256") != PROPOSAL_FILE_SHA256
        or authority.get("accepted_proposal_hash") != PROPOSAL_HASH
        or authority.get("source_eligible_identity_count") != EXPECTED_IDENTITY_COUNT
        or authority.get("source_eligible_identity_set_sha256") != EXPECTED_IDENTITY_SET_SHA256
        or authority.get("source_canonical_broker_payload_sha256") != EXPECTED_CANONICAL_PAYLOAD_SHA256
    ):
        raise PreflightError("freeze does not bind the accepted proposal and feasible-universe authority")

    proposal_path = repository / PROPOSAL_REF
    if not proposal_path.is_file() or _sha256(proposal_path) != PROPOSAL_FILE_SHA256:
        raise PreflightError("accepted proposal byte hash mismatch")
    proposal = _load(repository, PROPOSAL_REF)
    if proposal.get("proposal_id") != PROPOSAL_ID or proposal.get("proposal_hash") not in (
        None,
        PROPOSAL_HASH,
    ):
        raise PreflightError("accepted proposal identity mismatch")

    feasibility = _load(repository, FEASIBILITY_REF)
    counts = feasibility.get("current_counts") or {}
    if (
        feasibility.get("schema") != "mxm.greenfield.pepperstone-current-eur200-feasibility-authority.v2"
        or feasibility.get("status") != "CURRENT_EPOCH22_BROKER_NATIVE_AUTHORITY"
        or feasibility.get("source_canonical_payload_sha256") != EXPECTED_CANONICAL_PAYLOAD_SHA256
        or feasibility.get("exact_current_eligible_identity_set_sha256") != EXPECTED_IDENTITY_SET_SHA256
        or counts.get("current_eligible_post_exclusion_frontier") != EXPECTED_IDENTITY_COUNT
        or counts.get("both_direction_eur200_feasible") != 1607
        or counts.get("excluded_identity_count_currently_both_feasible") not in (None, 23)
    ):
        raise PreflightError("current feasibility authority does not match frozen identity-set authority")

    acceptance = _load(repository, FEASIBILITY_ACCEPTANCE_REF)
    validation = acceptance.get("capture_contract_validation") or {}
    if (
        acceptance.get("status") != "ACCEPTED_COMPLETE_CURRENT_BROKER_NATIVE_READ_ONLY_CAPTURE"
        or validation.get("accepted_canonical_payload_sha256") not in (
            None,
            EXPECTED_CANONICAL_PAYLOAD_SHA256,
        )
        or validation.get("current_symbol_count") != 5324
        or validation.get("current_new_entry_accessible_count") != 1689
        or acceptance.get("accounting_effect", {}).get("economic_outcomes") != 0
    ):
        raise PreflightError("accepted broker capture does not support the current feasibility authority")

    architecture = _load(repository, ARCHITECTURE_REF)
    adaptive = architecture.get("adaptive_discovery_universe") or {}
    if (
        architecture.get("status") != "ACTIVE_PROSPECTIVE_DISCOVERY_POLICY"
        or adaptive.get("current_persisted_size") != EXPECTED_IDENTITY_COUNT
        or adaptive.get("selection_timing") != "PROSPECTIVE_BEFORE_NEW_STRATEGY_OUTCOME"
        or architecture.get("structural_panel", {}).get("prohibited_default_role")
        != "INFERENTIAL_ECONOMIC_DISCOVERY_UNIVERSE"
    ):
        raise PreflightError("adaptive discovery architecture does not permit the frozen scope")

    governor = _load(repository, PARAMETER_GOVERNOR_REF)
    requirements = governor.get("prospective_search_space_requirements") or {}
    if (
        governor.get("status") != "ACTIVE_PROSPECTIVE_POLICY"
        or requirements.get("ranges_frozen_before_development_surface") is not True
        or requirements.get("effective_material_trials_recorded") is not True
        or requirements.get("winner_only_logging") is not False
    ):
        raise PreflightError("parameter governor requirements are not satisfied")

    scope = freeze.get("scope") or {}
    design = freeze.get("design") or {}
    grid = design.get("coarse_parameter_regions") or {}
    expected_cells = len(LOOKBACKS) * len(THRESHOLDS) * len(HORIZONS)
    if (
        scope.get("mechanism_family") != "MEAN_REVERSION"
        or scope.get("candidate_sampling_frame") != "ALL_1576_CURRENT_EUR200_FEASIBLE_POST_EXCLUSION_IDENTITIES"
        or scope.get("structural_41_default_inferential_authority") is not False
        or tuple(grid.get("lookback_bars") or ()) != LOOKBACKS
        or tuple(grid.get("absolute_standardized_deviation_threshold") or ()) != THRESHOLDS
        or tuple(grid.get("holding_horizon_bars") or ()) != HORIZONS
        or grid.get("cell_count") != expected_cells
        or grid.get("all_regions_frozen_before_development_surface") is not True
        or design.get("power_design", {}).get("target_power") != TARGET_POWER
        or design.get("power_design", {}).get("standardized_effect_sensitivity_scenarios") != list(EFFECT_SCENARIOS)
        or design.get("exploratory_multiplicity") != (
            f"Benjamini-Hochberg FDR q={FDR_Q} across all {expected_cells} frozen cells; "
            "record every cell and all failed/insufficient cells. This exploratory adjustment is not confirmatory authority."
        )
    ):
        raise PreflightError("scope or power design differs from the frozen preflight")

    boundary = freeze.get("interpretation_boundary") or {}
    if any(
        boundary.get(key) is not False
        for key in (
            "strategy_returns_computed",
            "pnl_computed",
            "economic_outcome_opened",
            "v2_attempt_consumed",
            "candidate_economic_identity_created",
            "mechanism_family_closed",
            "protected_forward_opened",
            "live_orders_authorized",
            "competition_start_authorized",
        )
    ):
        raise PreflightError("freeze crosses an economic, identity, or safety boundary")


def required_effective_dates(
    standardized_effect: float,
    *,
    cell_count: int = len(LOOKBACKS) * len(THRESHOLDS) * len(HORIZONS),
    target_power: float = TARGET_POWER,
    familywise_alpha: float = FDR_Q,
) -> int:
    if not math.isfinite(standardized_effect) or standardized_effect <= 0:
        raise ValueError("standardized effect must be finite and positive")
    if cell_count < 1 or not 0 < target_power < 1 or not 0 < familywise_alpha < 1:
        raise ValueError("invalid power-design parameters")
    normal = NormalDist()
    alpha = familywise_alpha / cell_count
    z_alpha = normal.inv_cdf(1.0 - alpha)
    z_power = normal.inv_cdf(target_power)
    return math.ceil(((z_alpha + z_power) / standardized_effect) ** 2)


def build_preflight(root: str | Path = ".") -> dict[str, Any]:
    repository = Path(root).resolve()
    freeze = _load(repository, FREEZE_REF)
    validate_freeze(freeze, repository)
    cell_count = len(LOOKBACKS) * len(THRESHOLDS) * len(HORIZONS)
    power_scenarios = [
        {
            "standardized_effect": effect,
            "required_effective_independent_utc_dates": required_effective_dates(effect),
            "target_power": TARGET_POWER,
            "one_sided_bonferroni_alpha": FDR_Q / cell_count,
            "interpretation": "DESIGN_SENSITIVITY_ONLY_NOT_AN_ECONOMIC_THRESHOLD",
        }
        for effect in EFFECT_SCENARIOS
    ]
    return {
        "schema": "mxm.greenfield.epoch39-mean-reversion-scope-power-preflight.v1",
        "status": "COMPLETE_NON_ECONOMIC_SCOPE_AND_POWER_DESIGN_PREFLIGHT",
        "evidence_epoch": 39,
        "implementation": {"version": VERSION, "freeze_ref": FREEZE_REF},
        "source_authority": {
            "accepted_proposal_ref": PROPOSAL_REF,
            "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
            "accepted_proposal_hash": PROPOSAL_HASH,
            "feasibility_authority_ref": FEASIBILITY_REF,
            "eligible_identity_count": EXPECTED_IDENTITY_COUNT,
            "eligible_identity_set_sha256": EXPECTED_IDENTITY_SET_SHA256,
            "canonical_broker_payload_sha256": EXPECTED_CANONICAL_PAYLOAD_SHA256,
        },
        "scope": {
            "mechanism_family": "MEAN_REVERSION",
            "sampling_frame": "ALL_1576_CURRENT_EUR200_FEASIBLE_POST_EXCLUSION_IDENTITIES",
            "sampling_frame_size": EXPECTED_IDENTITY_COUNT,
            "identity_set_sha256": EXPECTED_IDENTITY_SET_SHA256,
            "symbol_subselection_performed": False,
            "structural_41_used_as_inferential_panel": False,
            "pre_outcome_feature_gaps": list(freeze["scope"]["missing_pre_outcome_features"]),
            "current_decision": "Preserve the full eligible universe as the outcome-blind sampling frame; do not invent a fixed subset while full-frame data completeness and event independence are unknown.",
        },
        "design": {
            "estimand": freeze["design"]["estimand"],
            "causal_event_rule": freeze["design"]["causal_event_rule"],
            "coarse_parameter_regions": freeze["design"]["coarse_parameter_regions"],
            "effective_independence": freeze["design"]["dependence_unit"],
            "missingness": freeze["design"]["missing_data"],
            "exploratory_multiplicity": {
                "method": "BENJAMINI_HOCHBERG_FDR",
                "q": FDR_Q,
                "family_size": cell_count,
                "all_cells_and_insufficient_cells_recorded": True,
            },
            "power_sensitivity": {
                "scenarios": power_scenarios,
                "observed_event_density_available": False,
                "achieved_power_estimated": False,
                "reason": "No broad historical M5 panel exists for the 1576-identity sampling frame; do not substitute the 41 structural representatives or count raw bars as independent events.",
            },
        },
        "data_boundary": {
            "new_market_data_acquisition_in_this_phase": False,
            "current_broker_capture_transport_materialization_is_new_acquisition": False,
            "later_minimal_m5_ohlc_history_needed_to_measure_event_density": True,
            "later_data_scope_must_follow_a_pre_outcome_completeness_and_redundancy_audit": True,
            "no_default_multi_year_download": True,
        },
        "interpretation_boundary": freeze["interpretation_boundary"],
        "accounting_effect": {
            "v2_attempts_consumed": 0,
            "economic_outcomes_opened": 0,
            "search_budget_change": 0,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "competition_start_authorized": False,
        },
        "next_gate": "Materialize only the already accepted hash-bound current broker capture if an exact member listing is needed, then determine the smallest pre-outcome M5 history extension from completeness, event independence, structural heterogeneity, and acquisition cost. No new market-data request is authorized by this preflight.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = build_preflight(args.root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "scope_size": result["scope"]["sampling_frame_size"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
