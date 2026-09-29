from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

VERSION = "MXM_EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY_V1"
FREEZE_REF = "research_v3/EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_22da232dfe8db8062f3951c98cadda8e.json"
PROPOSAL_FILE_SHA256 = "efa2306ee44e558711eac4db63aa09b037c460045c9f81b26b8dddf69e5d6151"
PROPOSAL_HASH = "a089ac3cdc3763ef8311a0eaad7d5e4e09fb63e73bdc2bb46b7fd175321084e2"
FEASIBILITY_SNAPSHOT_REF = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json"
FEASIBILITY_SNAPSHOT_SHA256 = "fbad721388da7f5e48dd54056aaf00fca8554d41daa9fb728e4c546ed50f7851"
FEASIBILITY_REF = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"
PEER_INDEX_REF = "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json"
INVENTORY_REF = "evidence/EPOCH40_MEAN_REVERSION_STAGE1_TRIAGE_RESULT_V1.json"
INVENTORY_SHA256 = "133197a1b592b401a825a6bebce5a358c8a606c5829353b55271bb2fe00dc562"
EPOCH42_RESULT_REF = "evidence/EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT_V1.json"
EPOCH42_RESULT_SHA256 = "ea9dcfa7b1a803d1221a8f5d1ea9e04f2d0577eddbd6bba820911a62768c4332"
CAPTURE_ACCEPTANCE_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
CAPTURE_ZIP_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
ELIGIBLE_IDENTITY_COUNT = 1576
ELIGIBLE_IDENTITY_SET_SHA256 = "e53dc4e58d4e0d37eca4f528e06d0866ad8ffe3f2bc64d35278ecc8ee9f52a65"


class DiscoveryError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(root: Path, ref: str) -> dict[str, Any]:
    try:
        value = json.loads((root / ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"required accepted authority is missing or unreadable: {ref}") from exc
    if not isinstance(value, dict):
        raise DiscoveryError(f"accepted authority must be a JSON object: {ref}")
    return value


def _require_file_hash(root: Path, ref: str, expected: str) -> None:
    path = root / ref
    if not path.is_file() or _sha256(path) != expected:
        raise DiscoveryError(f"accepted authority file-byte hash mismatch: {ref}")


def _load_authorities(root: Path) -> tuple[dict[str, Any], ...]:
    freeze = _read_json(root, FREEZE_REF)
    if (
        freeze.get("schema")
        != "mxm.greenfield.epoch43-mean-reversion-power-aware-discovery-freeze.v1"
        or freeze.get("status")
        != "PROSPECTIVELY_FROZEN_NON_ECONOMIC_COHORT_COVERAGE_AND_POWER_SCREEN"
        or freeze.get("evidence_epoch") != 43
    ):
        raise DiscoveryError("unsupported or unprospectively frozen Epoch43 screen")

    authority = freeze.get("authority") or {}
    expected_authority = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
        "accepted_proposal_hash": PROPOSAL_HASH,
        "proposal_id": "MR_POWER_AWARE_DISCOVERY_PIPELINE_EPOCH43",
        "current_feasibility_snapshot_ref": FEASIBILITY_SNAPSHOT_REF,
        "current_feasibility_snapshot_sha256": FEASIBILITY_SNAPSHOT_SHA256,
        "eligible_universe_ref": FEASIBILITY_REF,
        "eligible_identity_count": ELIGIBLE_IDENTITY_COUNT,
        "eligible_identity_set_sha256": ELIGIBLE_IDENTITY_SET_SHA256,
        "outcome_blind_candidate_index_ref": PEER_INDEX_REF,
        "accepted_development_inventory_ref": INVENTORY_REF,
        "accepted_development_inventory_sha256": INVENTORY_SHA256,
        "accepted_prior_power_design_ref": EPOCH42_RESULT_REF,
        "accepted_prior_power_design_sha256": EPOCH42_RESULT_SHA256,
        "accepted_capture_acceptance_ref": CAPTURE_ACCEPTANCE_REF,
        "accepted_capture_zip_sha256": CAPTURE_ZIP_SHA256,
    }
    if any(authority.get(key) != value for key, value in expected_authority.items()):
        raise DiscoveryError("freeze does not bind the accepted Epoch43 proposal and authorities")

    _require_file_hash(root, PROPOSAL_REF, PROPOSAL_FILE_SHA256)
    _require_file_hash(root, FEASIBILITY_SNAPSHOT_REF, FEASIBILITY_SNAPSHOT_SHA256)
    _require_file_hash(root, INVENTORY_REF, INVENTORY_SHA256)
    _require_file_hash(root, EPOCH42_RESULT_REF, EPOCH42_RESULT_SHA256)
    proposal = _read_json(root, PROPOSAL_REF)
    decision = proposal.get("decision") or {}
    if (
        proposal.get("proposal_id") != "MR_POWER_AWARE_DISCOVERY_PIPELINE_EPOCH43"
        or proposal.get("proposal_hash") not in (None, PROPOSAL_HASH)
        or decision.get("mechanism_family") != "MEAN_REVERSION"
        or decision.get("status") != "IMPLEMENTATION_REQUIRED"
        or (proposal.get("economic_effect") or {}).get("open_economic_outcome") is not False
        or (proposal.get("data_policy") or {}).get("new_market_data_requested") is not False
    ):
        raise DiscoveryError("accepted proposal identity or non-economic boundary mismatch")

    feasibility = _read_json(root, FEASIBILITY_REF)
    if (
        feasibility.get("schema")
        != "mxm.greenfield.pepperstone-current-eur200-feasibility-authority.v2"
        or feasibility.get("status") != "CURRENT_EPOCH22_BROKER_NATIVE_AUTHORITY"
        or feasibility.get("exact_current_eligible_identity_set_sha256")
        != ELIGIBLE_IDENTITY_SET_SHA256
        or (feasibility.get("current_counts") or {}).get(
            "current_eligible_post_exclusion_frontier"
        )
        != ELIGIBLE_IDENTITY_COUNT
    ):
        raise DiscoveryError("current full-universe feasibility authority mismatch")

    peer_index = _read_json(root, PEER_INDEX_REF)
    if (
        peer_index.get("schema") != "mxm.greenfield.cross-sectional-peer-cohort-index.v1"
        or peer_index.get("status") != "COMPLETE_NON_ECONOMIC_CANDIDATE_UNIVERSE_INDEX"
        or (peer_index.get("source_universe") or {}).get("indexed_identity_count")
        != ELIGIBLE_IDENTITY_COUNT
        or (peer_index.get("source_universe") or {}).get(
            "eligible_identity_set_authority_sha256"
        )
        != ELIGIBLE_IDENTITY_SET_SHA256
        or (peer_index.get("source_bindings") or {}).get(
            "eligible_identity_set_sha256"
        )
        != ELIGIBLE_IDENTITY_SET_SHA256
        or (peer_index.get("cohort_policy") or {}).get(
            "structural_representatives_used_as_substitutes"
        )
        is not False
    ):
        raise DiscoveryError("persisted outcome-blind index does not bind the full eligible frame")

    inventory = _read_json(root, INVENTORY_REF)
    coverage = inventory.get("coverage") or {}
    if (
        inventory.get("schema")
        != "mxm.greenfield.epoch40-mean-reversion-stage1-outcome-blind-triage.v1"
        or inventory.get("status")
        != "COMPLETE_BOUNDED_OUTCOME_BLIND_ACCEPTED_CAPTURE_TRIAGE"
        or coverage.get("eligible_identities") != ELIGIBLE_IDENTITY_COUNT
        or coverage.get("identities_with_verified_m5_bars") != 45
        or coverage.get("other_accepted_capture_scopes")
        != "NOT_MATERIALIZED_OR_HASH_VERIFIED_IN_THIS_RUN; no absence claim"
    ):
        raise DiscoveryError("accepted development inventory exceeds or conflicts with its scope")

    epoch42 = _read_json(root, EPOCH42_RESULT_REF)
    accepted_coverage = epoch42.get("accepted_data_coverage") or {}
    if (
        epoch42.get("schema")
        != "mxm.greenfield.epoch42-mean-reversion-cohort-power-preflight.v1"
        or epoch42.get("status") != "COMPLETE_NON_ECONOMIC_HYPOTHESIS_AND_POWER_PREFLIGHT"
        or accepted_coverage.get("eligible_sampling_frame_identities")
        != ELIGIBLE_IDENTITY_COUNT
        or accepted_coverage.get("bounded_inventory_verified_m5_identities") != 45
        or accepted_coverage.get("unmaterialized_hash_bound_capture_bytes_are_new_acquisition")
        is not False
        or (epoch42.get("sampling_frame") or {}).get("selected_inferential_cohort") is not None
        or (epoch42.get("power_preflight") or {}).get("response_statistics_computed") is not False
    ):
        raise DiscoveryError("accepted Epoch42 evidence does not support this non-economic reuse")

    capture = _read_json(root, CAPTURE_ACCEPTANCE_REF)
    source = capture.get("source") or {}
    interval = capture.get("interval") or {}
    if (
        capture.get("schema")
        != "mxm.greenfield.broker-native-frontier-m5-13w-development-acceptance.v1"
        or capture.get("status") != "ACCEPTED_COMPLETE_NON_ECONOMIC_DEVELOPMENT_CAPTURE"
        or source.get("zip_sha256") != CAPTURE_ZIP_SHA256
        or interval.get("resolution") != "M5"
        or interval.get("start_utc") != "2026-06-15T00:00:00Z"
        or interval.get("end_utc") != "2026-09-13T23:59:59Z"
        or capture.get("validation", {}).get("series_complete") != 40
    ):
        raise DiscoveryError("accepted M5 capture scope differs from the frozen authority")

    return feasibility, peer_index, inventory, epoch42, capture


def build_from_authorities(
    feasibility: dict[str, Any],
    peer_index: dict[str, Any],
    inventory: dict[str, Any],
    epoch42: dict[str, Any],
    capture: dict[str, Any],
) -> dict[str, Any]:
    if (
        (feasibility.get("current_counts") or {}).get(
            "current_eligible_post_exclusion_frontier"
        )
        != ELIGIBLE_IDENTITY_COUNT
        or feasibility.get("exact_current_eligible_identity_set_sha256")
        != ELIGIBLE_IDENTITY_SET_SHA256
        or peer_index.get("schema") != "mxm.greenfield.cross-sectional-peer-cohort-index.v1"
        or (peer_index.get("source_universe") or {}).get("indexed_identity_count")
        != ELIGIBLE_IDENTITY_COUNT
        or (peer_index.get("source_universe") or {}).get(
            "eligible_identity_set_authority_sha256"
        )
        != ELIGIBLE_IDENTITY_SET_SHA256
    ):
        raise DiscoveryError("full feasible-universe authorities do not reconcile")
    if (
        inventory.get("schema")
        != "mxm.greenfield.epoch40-mean-reversion-stage1-outcome-blind-triage.v1"
        or (inventory.get("coverage") or {}).get("eligible_identities")
        != ELIGIBLE_IDENTITY_COUNT
        or epoch42.get("schema")
        != "mxm.greenfield.epoch42-mean-reversion-cohort-power-preflight.v1"
        or (epoch42.get("sampling_frame") or {}).get("selected_inferential_cohort") is not None
    ):
        raise DiscoveryError("accepted inventories do not support the frozen design")
    capture_interval = capture.get("interval") or {}
    if (
        (capture.get("source") or {}).get("zip_sha256") != CAPTURE_ZIP_SHA256
        or capture_interval.get("resolution") != "M5"
        or capture_interval.get("start_utc") != "2026-06-15T00:00:00Z"
        or capture_interval.get("end_utc") != "2026-09-13T23:59:59Z"
        or (capture.get("validation") or {}).get("series_complete") != 40
    ):
        raise DiscoveryError("accepted capture scope does not match the frozen history")

    indexed = peer_index.get("identities")
    observed = inventory.get("identities")
    if not isinstance(indexed, list) or not isinstance(observed, list):
        raise DiscoveryError("full-frame candidate and accepted-data inventories are required")

    by_id: dict[int, dict[str, Any]] = {}
    for row in indexed:
        if not isinstance(row, dict):
            raise DiscoveryError("candidate index identity must be an object")
        symbol_id = row.get("symbol_id")
        if (
            isinstance(symbol_id, bool)
            or not isinstance(symbol_id, int)
            or symbol_id in by_id
            or row.get("current_entry_accessible") is not True
            or row.get("directional_feasibility") != "BOTH_FEASIBLE"
        ):
            raise DiscoveryError("candidate index contains an invalid or ineligible identity")
        cohort_id = row.get("peer_candidate_cohort_id")
        if cohort_id is not None and (not isinstance(cohort_id, str) or not cohort_id):
            raise DiscoveryError("candidate stratum identifier is malformed")
        by_id[symbol_id] = row

    data_by_id: dict[int, dict[str, Any]] = {}
    for row in observed:
        if not isinstance(row, dict):
            raise DiscoveryError("accepted-data identity must be an object")
        symbol_id = row.get("symbol_id")
        if (
            isinstance(symbol_id, bool)
            or not isinstance(symbol_id, int)
            or symbol_id in data_by_id
        ):
            raise DiscoveryError("accepted-data inventory contains an invalid or duplicate identity")
        data_by_id[symbol_id] = row
    if (
        len(by_id) != ELIGIBLE_IDENTITY_COUNT
        or by_id.keys() != data_by_id.keys()
        or len(data_by_id) != ELIGIBLE_IDENTITY_COUNT
    ):
        raise DiscoveryError("candidate index and data inventory do not reconcile to the full frame")

    actual_bars = 0
    accepted_history_count = 0
    completeness_auditable_count = 0
    event_cluster_support_count = 0
    feature_counts = {
        "both_direction_eur200_feasibility": 0,
        "minimum_executable_volume": 0,
        "trading_schedule_and_session_metadata": 0,
        "capital_efficiency_proxy": 0,
        "conservative_friction_proxy": 0,
        "realized_volatility_opportunity_proxy": 0,
        "schedule_adjusted_history_completeness": 0,
        "reversal_event_cluster_density": 0,
        "dependence_adjusted_effective_sample_size": 0,
    }
    strata: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "candidate_identities": 0,
            "accepted_history_identities": 0,
            "verified_m5_inventory_identities": 0,
            "schedule_completeness_auditable_identities": 0,
            "event_cluster_support_identities": 0,
            "conservative_friction_proxy_available_identities": 0,
        }
    )
    for symbol_id, row in by_id.items():
        item = data_by_id[symbol_id]
        bars = item.get("observed_m5_bars", 0)
        if isinstance(bars, bool) or not isinstance(bars, int) or bars < 0:
            raise DiscoveryError("accepted inventory has an invalid M5 row count")
        actual_bars += bars
        history_available = row.get("accepted_history_state") == "ACCEPTED_HISTORY_AVAILABLE"
        if history_available:
            accepted_history_count += 1
        feature_counts["both_direction_eur200_feasibility"] += int(
            row.get("directional_feasibility") == "BOTH_FEASIBLE"
        )
        feature_counts["minimum_executable_volume"] += int(
            row.get("minimum_executable_volume") is not None
        )
        peer_metadata = row.get("peer_coherence_metadata") or {}
        if not isinstance(peer_metadata, dict):
            raise DiscoveryError("candidate schedule and session metadata must be an object")
        feature_counts["trading_schedule_and_session_metadata"] += int(
            all(
                isinstance(peer_metadata.get(field), str) and peer_metadata[field]
                for field in ("session_regions", "coverage_bucket")
            )
        )
        feature_counts["capital_efficiency_proxy"] += int(
            row.get("capital_efficiency_proxy_schedule_minutes_per_minimum_margin_eur")
            is not None
        )
        feature_counts["conservative_friction_proxy"] += int(
            row.get("conservative_friction_proxy_eur") is not None
        )
        volatility_proxy = item.get("median_abs_adjacent_log_price_change")
        if (
            isinstance(volatility_proxy, (int, float))
            and not isinstance(volatility_proxy, bool)
            and math.isfinite(volatility_proxy)
        ):
            feature_counts["realized_volatility_opportunity_proxy"] += 1
        complete = (
            history_available
            and item.get("usable_for_descriptive_stage1") is True
            and item.get("missingness_class") == "SCHEDULE_ADJUSTED_COMPLETENESS_VERIFIED"
        )
        if complete:
            completeness_auditable_count += 1
            feature_counts["schedule_adjusted_history_completeness"] += 1
        has_event_support = (
            complete
            and isinstance(item.get("reversal_event_cluster_count"), int)
            and not isinstance(item.get("reversal_event_cluster_count"), bool)
            and item["reversal_event_cluster_count"] > 0
            and isinstance(item.get("effective_independent_sample_size"), (int, float))
            and not isinstance(item.get("effective_independent_sample_size"), bool)
            and item["effective_independent_sample_size"] > 0
        )
        if has_event_support:
            event_cluster_support_count += 1
            feature_counts["reversal_event_cluster_density"] += 1
            feature_counts["dependence_adjusted_effective_sample_size"] += 1

        cohort_id = row.get("peer_candidate_cohort_id") or "UNASSIGNED_MISSING_COHORT_METADATA"
        group = strata[cohort_id]
        group["candidate_identities"] += 1
        group["accepted_history_identities"] += int(history_available)
        group["verified_m5_inventory_identities"] += int(bars > 0)
        group["schedule_completeness_auditable_identities"] += int(complete)
        group["event_cluster_support_identities"] += int(has_event_support)
        group["conservative_friction_proxy_available_identities"] += int(
            row.get("conservative_friction_proxy_eur") is not None
        )

    inventory_coverage = inventory["coverage"]
    if (
        actual_bars != inventory_coverage.get("reported_total_m5_bars", actual_bars)
        or sum(item["verified_m5_inventory_identities"] for item in strata.values())
        != inventory_coverage.get("identities_with_verified_m5_bars")
    ):
        raise DiscoveryError("accepted-data inventory aggregates do not reconcile")

    planning = (epoch42.get("power_preflight") or {}).get("planning_sensitivity")
    if (
        not isinstance(planning, list)
        or [item.get("standardized_effect") for item in planning] != [0.2, 0.3, 0.5]
        or any(item.get("hypothesis_count") != 36 for item in planning)
    ):
        raise DiscoveryError("accepted Epoch42 planning-only power scenarios are malformed")

    capture_source = capture["source"]
    capture_interval = capture["interval"]
    frame_count = (feasibility.get("current_counts") or {}).get(
        "current_eligible_post_exclusion_frontier"
    )
    if frame_count != ELIGIBLE_IDENTITY_COUNT:
        raise DiscoveryError("feasibility frame count changed")

    return {
        "schema": "mxm.greenfield.epoch43-mean-reversion-power-aware-discovery.v1",
        "status": "COMPLETE_NON_ECONOMIC_POWER_AWARE_DISCOVERY_PREFLIGHT",
        "family": "MEAN_REVERSION",
        "evidence_epoch": 43,
        "implementation": {"version": VERSION, "freeze_ref": FREEZE_REF},
        "source_authority": {
            "accepted_proposal_ref": PROPOSAL_REF,
            "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
            "accepted_proposal_hash": PROPOSAL_HASH,
            "current_feasibility_snapshot_ref": FEASIBILITY_SNAPSHOT_REF,
            "eligible_universe_ref": FEASIBILITY_REF,
            "eligible_identity_count": ELIGIBLE_IDENTITY_COUNT,
            "eligible_identity_set_sha256": ELIGIBLE_IDENTITY_SET_SHA256,
            "outcome_blind_candidate_index_ref": PEER_INDEX_REF,
            "accepted_development_inventory_ref": INVENTORY_REF,
            "accepted_prior_power_design_ref": EPOCH42_RESULT_REF,
            "accepted_capture_acceptance_ref": CAPTURE_ACCEPTANCE_REF,
            "accepted_capture_zip_sha256": CAPTURE_ZIP_SHA256,
            "prior_power_scenarios_reused_without_recomputation": True,
        },
        "freeze_sha256": None,
        "sampling_frame": {
            "eligible_identity_count": frame_count,
            "candidate_strata_count": len(strata),
            "candidate_strata_are_metadata_only": True,
            "selected_inferential_cohort": None,
            "selected_identity_count": None,
            "fixed_panel_size_imposed": False,
            "selection_outcome_blind": True,
            "structural_41_used_as_inferential_universe": False,
            "strata": [
                {"candidate_stratum_id": key, **value}
                for key, value in sorted(strata.items())
            ],
        },
        "accepted_data_coverage": {
            "inventory_ref": INVENTORY_REF,
            "inventory_file_sha256": INVENTORY_SHA256,
            "identities_with_verified_m5_bars_in_bounded_inventory": inventory_coverage[
                "identities_with_verified_m5_bars"
            ],
            "accepted_history_identities_in_persisted_candidate_index": accepted_history_count,
            "total_verified_m5_rows": actual_bars,
            "schedule_adjusted_completeness_auditable_identities": completeness_auditable_count,
            "identities_with_event_cluster_and_effective_sample_support": event_cluster_support_count,
            "full_frame_history_completeness": "NOT_ESTABLISHED",
            "other_accepted_capture_scopes": inventory_coverage[
                "other_accepted_capture_scopes"
            ],
            "absence_claim_for_other_capture_scopes": False,
            "outcome_blind_feature_coverage": {
                "denominator": ELIGIBLE_IDENTITY_COUNT,
                "identities_with_feature": feature_counts,
                "realized_volatility_proxy_definition": (
                    "Existing Epoch40 median absolute adjacent log-price change; coverage proxy only, "
                    "not reversal-event density, completeness, or outcome evidence."
                ),
            },
            "accepted_external_capture": {
                "zip_sha256": capture_source["zip_sha256"],
                "resolution": capture_interval["resolution"],
                "start_utc": capture_interval["start_utc"],
                "end_utc": capture_interval["end_utc"],
                "series_complete": capture["validation"]["series_complete"],
                "bytes_external_to_git_are_transport_materialization_not_new_acquisition": True,
                "this_interval_disjoint_from_epoch25_epoch36_response_window": False,
            },
        },
        "cohort_decision": {
            "status": "NO_INFERENTIAL_COHORT_SELECTED_INSUFFICIENT_AUTHENTICATED_EVENT_DEPENDENCE_SUPPORT",
            "selected": False,
            "selection_blockers": [
                "Schedule-adjusted contiguous-history completeness is not established for a prospectively selected cohort.",
                "The accepted inventories do not contain frozen mean-reversion excursion-cluster counts or dependence-adjusted effective sample sizes for the full feasible frame.",
                "The hash-bound 13-week M5 capture is recognized as existing accepted external data, but its interval is not disjoint from the prior Epoch25/Epoch36 response window and its identity scope cannot be promoted to a full-frame inferential cohort.",
            ],
            "minimal_later_data_dependency": {
                "symbols": "Exact identities only after later prospective outcome-blind cohort selection; none are selected by this report.",
                "resolution": "M5",
                "fields": ["time_utc", "open", "high", "low", "close", "tick_volume"],
                "interval": "Reconcile exact accepted scopes first; any interval used for response evaluation must be separately frozen and disjoint from the prior Epoch25/Epoch36 observation window.",
                "requirements": [
                    "Hash-authenticated exact broker-symbol identity and complete pagination/coverage attestation.",
                    "Schedule-adjusted completeness and contiguous-segment audit with no filling or interpolation.",
                    "Causal event-cluster counts and dependence-aware effective sample size before response statistics.",
                ],
                "new_market_data_requested_or_authorized": False,
            },
        },
        "power_preflight": {
            "status": "EFFECTIVE_SAMPLE_SIZE_NOT_ESTIMABLE_FROM_ACCEPTED_INVENTORIES",
            "planning_sensitivity_reused_from_epoch42": planning,
            "observed_effective_sample_size": None,
            "achieved_power_estimated": False,
            "response_statistics_computed": False,
            "epoch42_diagnostic_rerun": False,
        },
        "interpretation_boundary": {
            "outcome_blind_non_economic_inventory_only": True,
            "strategy_events_or_response_statistics_computed": False,
            "strategy_returns_read": False,
            "pnl_computed": False,
            "economic_outcome_opened": False,
            "candidate_economic_identity_created": False,
            "v2_attempt_consumed": False,
            "protected_forward_opened": False,
            "independent_confirmation_claimed": False,
            "internal_development_holdout_is_independent_confirmation": False,
            "structural_41_used_as_inferential_universe": False,
            "epoch42_diagnostic_rerun": False,
            "relative_value_alignment_inventory_recomputed": False,
            "mechanism_family_closed": False,
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
        "next_gate": (
            "Fresh prospective reasoning must audit exact accepted capture scopes and define any "
            "minimal disjoint development-data increment before outcome response evaluation. "
            "Already hash-bound external bytes remain transport materialization, not new acquisition."
        ),
    }


def build_preflight(root: str | Path = ".") -> dict[str, Any]:
    repository = Path(root).resolve()
    feasibility, peer_index, inventory, epoch42, capture = _load_authorities(repository)
    result = build_from_authorities(feasibility, peer_index, inventory, epoch42, capture)
    result["freeze_sha256"] = _sha256(repository / FREEZE_REF)
    return result


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
                "cohort_status": result["cohort_decision"]["status"],
                "selected_identity_count": result["sampling_frame"]["selected_identity_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
