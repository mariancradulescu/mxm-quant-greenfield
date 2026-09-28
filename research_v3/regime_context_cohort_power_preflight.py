from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

VERSION = "MXM_EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT_V1"
FREEZE_REF = "research_v3/EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_f90b3ceb92870099d22c1d028eefc952.json"
PROPOSAL_SHA256 = "bc458f977dec26ce0840efc29f02c57d2fbe497f34a5b9d50ff3ce5304c0e7f9"
FEASIBILITY_REF = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"
PEER_INDEX_REF = "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json"
REGIME_AUDIT_REF = "evidence/REGIME_CONTEXT_DATA_SUFFICIENCY_AUDIT_V1.json"
DEVELOPMENT_INVENTORY_REF = "evidence/EPOCH40_MEAN_REVERSION_STAGE1_TRIAGE_RESULT_V1.json"
ARCHITECTURE_REF = "research_v3/ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE_V1.json"
REGIME_AUDIT_SHA256 = "10cb085585bc236a9a738696a9b2d58db4d79971872cf3b8554d0899b5099fdd"
DEVELOPMENT_INVENTORY_SHA256 = "133197a1b592b401a825a6bebce5a358c8a606c5829353b55271bb2fe00dc562"
IDENTITY_COUNT = 1576
IDENTITY_SET_SHA256 = "e53dc4e58d4e0d37eca4f528e06d0866ad8ffe3f2bc64d35278ecc8ee9f52a65"
BROKER_PAYLOAD_SHA256 = "7b268eae05fad325cb1f0fc962511ca41236b3b58bb83023735fd22b94301452"


class PreflightError(ValueError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightError(f"{label} is missing or unreadable") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"{label} must be a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_authorities(root: Path) -> tuple[dict[str, Any], ...]:
    freeze = _read_json(root / FREEZE_REF, "prospective freeze")
    if (
        freeze.get("schema")
        != "mxm.greenfield.epoch41-regime-context-cohort-power-preflight-freeze.v1"
        or freeze.get("status")
        != "PROSPECTIVELY_FROZEN_NON_ECONOMIC_COHORT_AND_POWER_PREFLIGHT"
    ):
        raise PreflightError("unsupported or unprospectively frozen preflight")
    authority = freeze.get("authority") or {}
    expected_refs = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "feasibility_authority_ref": FEASIBILITY_REF,
        "peer_cohort_index_ref": PEER_INDEX_REF,
        "regime_context_data_audit_ref": REGIME_AUDIT_REF,
        "accepted_development_inventory_ref": DEVELOPMENT_INVENTORY_REF,
        "adaptive_discovery_architecture_ref": ARCHITECTURE_REF,
    }
    if any(authority.get(key) != value for key, value in expected_refs.items()):
        raise PreflightError("freeze does not bind the accepted decision authorities")
    if authority.get("accepted_proposal_file_sha256") != PROPOSAL_SHA256:
        raise PreflightError("freeze does not bind the accepted proposal file-byte hash")
    if (
        authority.get("regime_context_data_audit_sha256") != REGIME_AUDIT_SHA256
        or authority.get("accepted_development_inventory_sha256")
        != DEVELOPMENT_INVENTORY_SHA256
    ):
        raise PreflightError("freeze does not bind the accepted data-audit bytes")

    proposal_path = root / PROPOSAL_REF
    if not proposal_path.is_file() or _sha256(proposal_path) != PROPOSAL_SHA256:
        raise PreflightError("accepted proposal file-byte hash mismatch")
    proposal = _read_json(proposal_path, "accepted proposal")
    if proposal.get("proposal_id") != "AUTO_reason_f90b3ceb92870099d22c1d028eefc952_REGIME_PREFLIGHT":
        raise PreflightError("accepted proposal identity mismatch")

    feasibility = _read_json(root / FEASIBILITY_REF, "current feasibility authority")
    peer_index = _read_json(root / PEER_INDEX_REF, "persisted outcome-blind cohort index")
    regime_audit = _read_json(root / REGIME_AUDIT_REF, "accepted regime context audit")
    inventory = _read_json(root / DEVELOPMENT_INVENTORY_REF, "accepted development inventory")
    architecture = _read_json(root / ARCHITECTURE_REF, "adaptive discovery architecture")
    if (
        _sha256(root / REGIME_AUDIT_REF) != REGIME_AUDIT_SHA256
        or _sha256(root / DEVELOPMENT_INVENTORY_REF) != DEVELOPMENT_INVENTORY_SHA256
    ):
        raise PreflightError("accepted data-audit file-byte hash mismatch")

    if (
        feasibility.get("schema")
        != "mxm.greenfield.pepperstone-current-eur200-feasibility-authority.v2"
        or feasibility.get("status") != "CURRENT_EPOCH22_BROKER_NATIVE_AUTHORITY"
        or feasibility.get("exact_current_eligible_identity_set_sha256") != IDENTITY_SET_SHA256
        or feasibility.get("source_canonical_payload_sha256") != BROKER_PAYLOAD_SHA256
        or (feasibility.get("current_counts") or {}).get("current_eligible_post_exclusion_frontier")
        != IDENTITY_COUNT
    ):
        raise PreflightError("feasible-universe authority differs from the frozen identity frame")
    if (
        peer_index.get("schema") != "mxm.greenfield.cross-sectional-peer-cohort-index.v1"
        or peer_index.get("status") != "COMPLETE_NON_ECONOMIC_CANDIDATE_UNIVERSE_INDEX"
        or (peer_index.get("source_universe") or {}).get("indexed_identity_count") != IDENTITY_COUNT
        or (peer_index.get("source_bindings") or {}).get("eligible_identity_set_sha256")
        != IDENTITY_SET_SHA256
        or (peer_index.get("coverage") or {}).get("cohort_breadth_total") != IDENTITY_COUNT
    ):
        raise PreflightError("persisted outcome-blind index does not cover the full feasible universe")
    if (
        regime_audit.get("schema") != "mxm.greenfield.regime-context-data-sufficiency-audit.v1"
        or regime_audit.get("status") != "COMPLETE_NON_ECONOMIC_DATA_SUFFICIENCY_AUDIT"
        or (regime_audit.get("scope") or {}).get("representative_count") != 41
        or (regime_audit.get("input_attestation") or {}).get(
            "all_41_representatives_processed_exactly_once"
        )
        is not True
    ):
        raise PreflightError("accepted regime audit is not the expected structural-only audit")
    if (
        inventory.get("schema")
        != "mxm.greenfield.epoch40-mean-reversion-stage1-outcome-blind-triage.v1"
        or inventory.get("status") != "COMPLETE_BOUNDED_OUTCOME_BLIND_ACCEPTED_CAPTURE_TRIAGE"
        or (inventory.get("coverage") or {}).get("eligible_identities") != IDENTITY_COUNT
    ):
        raise PreflightError("accepted development inventory does not cover the frozen frame")
    adaptive = architecture.get("adaptive_discovery_universe") or {}
    if (
        architecture.get("status") != "ACTIVE_PROSPECTIVE_DISCOVERY_POLICY"
        or adaptive.get("current_persisted_size") != IDENTITY_COUNT
        or adaptive.get("selection_timing") != "PROSPECTIVE_BEFORE_NEW_STRATEGY_OUTCOME"
        or (architecture.get("structural_panel") or {}).get("prohibited_default_role")
        != "INFERENTIAL_ECONOMIC_DISCOVERY_UNIVERSE"
    ):
        raise PreflightError("adaptive universe policy does not support the frozen boundaries")

    boundary = freeze.get("interpretation_boundary") or {}
    if any(
        boundary.get(key) is not False
        for key in (
            "strategy_events_or_returns_computed",
            "pnl_computed",
            "economic_outcome_opened",
            "candidate_economic_identity_created",
            "v2_attempt_consumed",
            "protected_forward_opened",
            "independent_confirmation_claimed",
            "mechanism_family_closed",
            "live_orders_authorized",
            "competition_start_authorized",
        )
    ):
        raise PreflightError("freeze crosses a prohibited economic or safety boundary")
    if freeze.get("accounting_effect") != {
        "economic_outcomes_opened": 0,
        "v2_attempts_consumed": 0,
        "search_budget_change": 0,
    }:
        raise PreflightError("freeze accounting boundary is not zero-effect")
    return feasibility, peer_index, regime_audit, inventory, architecture


def _population_rows(
    peer_index: dict[str, Any], inventory: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    indexed = peer_index.get("identities")
    observed = inventory.get("identities")
    if not isinstance(indexed, list) or not isinstance(observed, list):
        raise PreflightError("full-frame identity inventories are missing")
    indexed_by_id: dict[int, dict[str, Any]] = {}
    for row in indexed:
        symbol_id = row.get("symbol_id")
        if isinstance(symbol_id, bool) or not isinstance(symbol_id, int) or symbol_id in indexed_by_id:
            raise PreflightError("cohort index contains an invalid or duplicate symbol id")
        indexed_by_id[symbol_id] = row
        if (
            row.get("current_entry_accessible") is not True
            or row.get("directional_feasibility") != "BOTH_FEASIBLE"
        ):
            raise PreflightError("cohort index contains an identity outside current eligibility")
    inventory_by_id: dict[int, dict[str, Any]] = {}
    for row in observed:
        symbol_id = row.get("symbol_id")
        if isinstance(symbol_id, bool) or not isinstance(symbol_id, int) or symbol_id in inventory_by_id:
            raise PreflightError("development inventory contains an invalid or duplicate symbol id")
        inventory_by_id[symbol_id] = row
    if len(indexed_by_id) != IDENTITY_COUNT or indexed_by_id.keys() != inventory_by_id.keys():
        raise PreflightError("cohort and accepted inventory do not enumerate the same full frame")
    return indexed, inventory_by_id


def build_from_authorities(
    feasibility: dict[str, Any],
    peer_index: dict[str, Any],
    regime_audit: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    if (
        (regime_audit.get("scope") or {}).get("representative_count") != 41
        or (regime_audit.get("input_attestation") or {}).get(
            "all_41_representatives_processed_exactly_once"
        ) is not True
        or not isinstance(regime_audit.get("symbols"), dict)
        or len(regime_audit["symbols"]) != 41
    ):
        raise PreflightError("structural regime audit cannot become a full-frame inferential sample")
    indexed, inventory_by_id = _population_rows(peer_index, inventory)
    coverage = inventory["coverage"]
    with_bars = sum(
        int(row.get("observed_m5_bars") or 0) > 0 for row in inventory_by_id.values()
    )
    if with_bars != coverage.get("identities_with_verified_m5_bars"):
        raise PreflightError("accepted-data inventory counts do not reconcile")

    strata: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "candidate_members": 0,
            "members_with_accepted_m5_bars": 0,
            "accepted_m5_bar_count": 0,
            "regime_context_coverage": "NOT_AUDITED",
            "effective_independent_sample_size": None,
        }
    )
    for identity in indexed:
        cohort_id = identity.get("peer_candidate_cohort_id")
        if not isinstance(cohort_id, str) or not cohort_id:
            # The persisted inventory's unassigned identities remain in the frame;
            # missing metadata is never guessed or imputed.
            cohort_id = "UNASSIGNED_MISSING_COHORT_METADATA"
        summary = strata[cohort_id]
        summary["candidate_members"] += 1
        sample = inventory_by_id[int(identity["symbol_id"])]
        bars = int(sample.get("observed_m5_bars") or 0)
        if bars > 0:
            summary["members_with_accepted_m5_bars"] += 1
            summary["accepted_m5_bar_count"] += bars

    structural_symbols = regime_audit.get("symbols")
    if not isinstance(structural_symbols, dict) or len(structural_symbols) != 41:
        raise PreflightError("structural regime audit symbol inventory is incomplete")

    eligible_count = (feasibility.get("current_counts") or {}).get(
        "current_eligible_post_exclusion_frontier"
    )
    return {
        "schema": "mxm.greenfield.epoch41-regime-context-cohort-power-preflight.v1",
        "status": "COMPLETE_NON_ECONOMIC_COHORT_POWER_PREFLIGHT",
        "evidence_epoch": 41,
        "family": "REGIME_CONTEXT_CONDITIONED",
        "implementation": {"version": VERSION, "freeze_ref": FREEZE_REF},
        "source_authority": {
            "feasibility_authority_ref": FEASIBILITY_REF,
            "eligible_identity_count": eligible_count,
            "eligible_identity_set_sha256": IDENTITY_SET_SHA256,
            "peer_cohort_index_ref": PEER_INDEX_REF,
            "regime_context_data_audit_ref": REGIME_AUDIT_REF,
            "accepted_development_inventory_ref": DEVELOPMENT_INVENTORY_REF,
        },
        "selection_provenance": {
            "persisted_peer_index_source_bindings": peer_index.get("source_bindings"),
            "persisted_peer_index_universe": peer_index.get("source_universe"),
            "accepted_development_capture_attestation": (
                inventory.get("source_authority") or {}
            ).get("captures"),
            "structural_regime_audit_input_attestation": regime_audit.get("input_attestation"),
            "persisted_peer_index_recomputed": False,
        },
        "sampling_frame": {
            "eligible_identity_count": IDENTITY_COUNT,
            "candidate_cohort_strata": len(strata),
            "cohort_strata_basis": (
                "Persisted outcome-blind broker metadata grouping only; not a claim of "
                "behavioral or economic peers and not a regime-context member selection."
            ),
            "selection_is_outcome_blind": True,
            "fixed_panel_size_imposed": False,
            "selected_inferential_identity_count": None,
            "selected_inferential_identity_set": None,
            "structural_41_used_as_inferential_universe": False,
            "cohort_strata": [
                {"cohort_id": cohort_id, **summary}
                for cohort_id, summary in sorted(strata.items())
            ],
        },
        "accepted_data_coverage": {
            "inventory_scope": "PERSISTED_ACCEPTED_NON_ECONOMIC_M5_INVENTORY_ONLY",
            "identities_with_verified_m5_bars": with_bars,
            "identities_not_verified_in_bounded_inventory_run": IDENTITY_COUNT - with_bars,
            "other_accepted_capture_scopes": coverage.get("other_accepted_capture_scopes"),
            "absence_claim_for_other_capture_scopes": False,
            "reported_accepted_m5_bar_count": sum(
                int(row.get("observed_m5_bars") or 0) for row in inventory_by_id.values()
            ),
            "regime_context_coverage_for_full_frame": "NOT_AUDITED",
            "context_effective_sample_size_for_full_frame": "NOT_ESTIMABLE",
            "structural_audit_context_effective_sample_size_is_inferential_authority": False,
            "unmaterialized_accepted_capture_bytes_are_new_acquisition": False,
        },
        "power_preflight": {
            "status": "NOT_ESTIMABLE_FROM_ACCEPTED_FULL_FRAME_DATA",
            "per_cohort_effective_independent_sample_size": None,
            "achieved_power": None,
            "planning_sensitivity": None,
            "reason": (
                "The accepted regime-context audit covers only the 41 topology representatives, "
                "which are not an inferential discovery universe. The full-frame accepted inventory "
                "does not contain regime-context classifications or dependence-adjusted effective "
                "sample sizes for the 1576 eligible identities."
            ),
        },
        "decision": {
            "cohort_selected": False,
            "status": "DATA_INSUFFICIENT_FOR_PROSPECTIVE_INFERENTIAL_COHORT_SELECTION",
            "data_gap": (
                "No accepted full-frame or selected-stratum regime-context feature history and "
                "dependence-adjusted effective sample size are available. Existing 41-symbol "
                "structural audit is descriptive only and cannot be substituted."
            ),
            "next_phase": (
                "Fresh semantic reasoning must define the minimal outcome-blind regime-context "
                "data scope using the reported coverage gaps. Any later acquisition requires its "
                "own prospective authority; no new market data is authorized here."
            ),
        },
        "interpretation_boundary": {
            "strategy_outcomes_or_returns_read": False,
            "pnl_computed": False,
            "candidate_economic_identity_created": False,
            "structural_41_inferential_substitution": False,
            "independent_confirmation_claimed": False,
            "relative_value_alignment_inventory_recomputed": False,
            "economic_promotion_authorized": False,
            "mechanism_family_closed": False,
            "protected_forward_opened": False,
            "live_orders_authorized": False,
        },
        "accounting_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "search_budget_change": 0,
        },
        "safety": {
            "competition_start_authorized": False,
            "live_orders_authorized": False,
            "protected_forward_opened": False,
        },
    }


def build_preflight(root: str | Path = ".") -> dict[str, Any]:
    repository = Path(root).resolve()
    feasibility, peer_index, regime_audit, inventory, _ = _load_authorities(repository)
    result = build_from_authorities(feasibility, peer_index, regime_audit, inventory)
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
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "cohort_selected": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
