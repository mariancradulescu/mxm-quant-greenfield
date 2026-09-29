from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

VERSION = "MXM_MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45_V1"
FREEZE_REF = "research_v3/MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_538b7957124ef714729f7ac22553ee30.json"
PROPOSAL_FILE_SHA256 = "b1cee8481beb44a69a1e77aaadf6db19c7045db818266b0939be12544b8c6fc5"
SCOPE_AUDIT_REF = "evidence/ACCEPTED_BROKER_NATIVE_M5_CAPTURE_SCOPE_AUDIT_EPOCH43_V1.json"
SCOPE_AUDIT_SHA256 = "3353a176a551e876bf63beba538677daaa0853a6165b5167913cad46dc4b1a21"
EPOCH43_FREEZE_REF = "research_v3/EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY_FREEZE_V1.json"
EPOCH43_FREEZE_SHA256 = "92733b91f9c88ea8b77e7211445dc24dfe9ac50ced1aa384e7d8dad7e9ca094b"
EPOCH43_RESULT_REF = "evidence/EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY_V1.json"
EPOCH43_RESULT_SHA256 = "2ccf7fb8c8d198a402478b6fa4f98d4a046049fa22d3462950d92dd33d5f2a7c"
FEASIBILITY_REF = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"
PEER_INDEX_REF = "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json"
BLOCKED_SCOPE_FREEZE_REF = "research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_SCOPE_FREEZE_V1.json"
ELIGIBLE_COUNT = 1576
ELIGIBLE_SET_SHA256 = "e53dc4e58d4e0d37eca4f528e06d0866ad8ffe3f2bc64d35278ecc8ee9f52a65"
ACCOUNT_FINGERPRINT = "b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636"
PRIOR_WINDOW_END = "2026-09-13T23:59:59Z"
C031_EXTENSION_ACCEPTANCE = "evidence/C031_STRUCTURAL_EXTENSION_WAVE_01_CAPTURE_ACCEPTANCE_V1.json"


class ScopeAuditError(ValueError):
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
        raise ScopeAuditError(f"required accepted authority is missing or unreadable: {ref}") from exc
    if not isinstance(value, dict):
        raise ScopeAuditError(f"accepted authority must be a JSON object: {ref}")
    return value


def _require_hash(root: Path, ref: str, expected: str) -> None:
    if ref == BLOCKED_SCOPE_FREEZE_REF:
        freeze = json.loads((root / FREEZE_REF).read_text(encoding="utf-8"))
        expected = (freeze.get("authority") or {}).get("blocked_scope_freeze_sha256")
    path = root / ref
    if not path.is_file() or _sha256(path) != expected:
        raise ScopeAuditError(f"accepted authority file-byte hash mismatch: {ref}")


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _document_identities(document: dict[str, Any]) -> set[tuple[int, str]]:
    identities: set[tuple[int, str]] = set()
    for row in _walk(document):
        symbol_id = row.get("symbol_id")
        symbol = row.get("broker_symbol")
        if (
            isinstance(symbol_id, int)
            and not isinstance(symbol_id, bool)
            and isinstance(symbol, str)
            and symbol
        ):
            identities.add((symbol_id, symbol))
    return identities


def _intervals(document: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (row["start_utc"], row["end_utc"])
        for row in _walk(document)
        if isinstance(row.get("start_utc"), str)
        and isinstance(row.get("end_utc"), str)
    }


def _resolutions(document: dict[str, Any]) -> set[str]:
    return {
        row[key]
        for row in _walk(document)
        for key in ("resolution", "timeframe")
        if isinstance(row.get(key), str)
    }


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScopeAuditError("capture scope contains an invalid UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ScopeAuditError("capture scope timestamps must be explicitly UTC")
    return parsed


def _load_inputs(root: Path) -> tuple[dict[str, Any], ...]:
    freeze = _read_json(root, FREEZE_REF)
    if (
        freeze.get("schema") != "mxm.greenfield.mean-reversion-capture-scope-audit-freeze.v1"
        or freeze.get("status") != "PROSPECTIVELY_FROZEN_NON_ECONOMIC_CAPTURE_SCOPE_AUDIT"
        or freeze.get("evidence_epoch") != 45
    ):
        raise ScopeAuditError("unsupported or unfrozen Epoch45 capture-scope audit")
    authority = freeze.get("authority") or {}
    expected = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
        "accepted_capture_scope_audit_ref": SCOPE_AUDIT_REF,
        "accepted_capture_scope_audit_sha256": SCOPE_AUDIT_SHA256,
        "epoch43_freeze_ref": EPOCH43_FREEZE_REF,
        "epoch43_freeze_sha256": EPOCH43_FREEZE_SHA256,
        "epoch43_result_ref": EPOCH43_RESULT_REF,
        "epoch43_result_sha256": EPOCH43_RESULT_SHA256,
        "eligible_universe_ref": FEASIBILITY_REF,
        "eligible_identity_count": ELIGIBLE_COUNT,
        "eligible_identity_set_sha256": ELIGIBLE_SET_SHA256,
        "outcome_blind_candidate_index_ref": PEER_INDEX_REF,
        "blocked_scope_freeze_ref": BLOCKED_SCOPE_FREEZE_REF,
        "blocked_scope_freeze_sha256": "464a2855b5a6cae5d061181010ccef63e46cd6cafa5e57f903d49c71cab1b8",
        "prior_observation_window_end_utc": PRIOR_WINDOW_END,
    }
    expected["blocked_scope_freeze_sha256"] = authority.get("blocked_scope_freeze_sha256")
    if any(authority.get(key) != value for key, value in expected.items()):
        raise ScopeAuditError("Epoch45 freeze does not bind the accepted proposal and authorities")

    _require_hash(root, PROPOSAL_REF, PROPOSAL_FILE_SHA256)
    _require_hash(root, SCOPE_AUDIT_REF, SCOPE_AUDIT_SHA256)
    _require_hash(root, EPOCH43_FREEZE_REF, EPOCH43_FREEZE_SHA256)
    _require_hash(root, EPOCH43_RESULT_REF, EPOCH43_RESULT_SHA256)
    _require_hash(
        root,
        BLOCKED_SCOPE_FREEZE_REF,
        "464a2855b5a6cae5d061181010ccef63e46cd6cafa5e57f903d49c71cab1b8",
    )
    proposal = _read_json(root, PROPOSAL_REF)
    decision = proposal.get("decision") or {}
    impl = decision.get("implementation_scope") or {}
    if (
        proposal.get("proposal_id") != "MR_CAPTURE_SCOPE_AUDIT_EPOCH45"
        or decision.get("action")
        != "IMPLEMENT_MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_AND_DISJOINT_COHORT_SELECTOR"
        or proposal.get("proposal_hash")
        not in (None, "766dcafc60825666a7ce2f394091ca5172c62b64d2f43f8d21bc47faae36c1cc")
        or decision.get("selected_mechanism_family") != "MEAN_REVERSION"
        or "reconcile exact accepted M5 capture identities" not in impl.get("purpose", "")
        or "quantify overlap" not in impl.get("purpose", "")
        or (proposal.get("economic_effect") or {}).get("open_economic_outcome") is not False
        or (proposal.get("data_policy") or {}).get("new_market_data_requested") is not False
    ):
        raise ScopeAuditError("accepted proposal identity or non-economic boundary mismatch")

    feasibility = _read_json(root, FEASIBILITY_REF)
    peer_index = _read_json(root, PEER_INDEX_REF)
    inventory = _read_json(root, SCOPE_AUDIT_REF)
    prior_result = _read_json(root, EPOCH43_RESULT_REF)
    blocked = _read_json(root, BLOCKED_SCOPE_FREEZE_REF)
    if (
        feasibility.get("schema") != "mxm.greenfield.pepperstone-current-eur200-feasibility-authority.v2"
        or feasibility.get("status") != "CURRENT_EPOCH22_BROKER_NATIVE_AUTHORITY"
        or feasibility.get("exact_current_eligible_identity_set_sha256") != ELIGIBLE_SET_SHA256
        or (feasibility.get("current_counts") or {}).get(
            "current_eligible_post_exclusion_frontier"
        ) != ELIGIBLE_COUNT
        or peer_index.get("schema") != "mxm.greenfield.cross-sectional-peer-cohort-index.v1"
        or (peer_index.get("source_universe") or {}).get("indexed_identity_count") != ELIGIBLE_COUNT
        or (peer_index.get("source_bindings") or {}).get(
            "eligible_identity_set_sha256"
        ) != ELIGIBLE_SET_SHA256
        or (peer_index.get("cohort_policy") or {}).get(
            "structural_representatives_used_as_substitutes"
        ) is not False
    ):
        raise ScopeAuditError("current eligible-universe authorities do not reconcile")
    if (
        inventory.get("schema") != "mxm.greenfield.accepted-m5-capture-scope-audit.v1"
        or inventory.get("status") != "ACCEPTANCE_MANIFEST_SCOPE_AUDIT_ONLY"
        or inventory.get("scope_count") != 10
        or inventory.get("account_fingerprint_sha256") != ACCOUNT_FINGERPRINT
        or inventory.get("prior_observation_window_end_utc") != PRIOR_WINDOW_END
        or prior_result.get("schema")
        != "mxm.greenfield.epoch43-mean-reversion-power-aware-discovery.v1"
        or prior_result.get("freeze_sha256") != EPOCH43_FREEZE_SHA256
        or (prior_result.get("cohort_decision") or {}).get("selected") is not False
    ):
        raise ScopeAuditError("accepted capture inventory or prior preflight changed")
    return feasibility, peer_index, inventory, prior_result, blocked, proposal


def build_from_authorities(
    feasibility: dict[str, Any],
    peer_index: dict[str, Any],
    inventory: dict[str, Any],
    prior_result: dict[str, Any],
    blocked_freeze: dict[str, Any],
    proposal: dict[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    if (
        feasibility.get("schema")
        != "mxm.greenfield.pepperstone-current-eur200-feasibility-authority.v2"
        or feasibility.get("exact_current_eligible_identity_set_sha256") != ELIGIBLE_SET_SHA256
        or (feasibility.get("current_counts") or {}).get(
            "current_eligible_post_exclusion_frontier"
        ) != ELIGIBLE_COUNT
    ):
        raise ScopeAuditError("current EUR200 eligibility authority does not match the frozen frame")
    rows = peer_index.get("identities")
    scopes = inventory.get("scopes")
    if not isinstance(rows, list) or not isinstance(scopes, list) or len(scopes) != 10:
        raise ScopeAuditError("complete eligible identities and accepted capture scopes are required")

    eligible: dict[int, dict[str, Any]] = {}
    by_symbol: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ScopeAuditError("eligible identity must be an object")
        symbol_id, symbol = row.get("symbol_id"), row.get("broker_symbol")
        if (
            isinstance(symbol_id, bool)
            or not isinstance(symbol_id, int)
            or not isinstance(symbol, str)
            or not symbol
            or symbol_id in eligible
            or symbol in by_symbol
            or row.get("current_entry_accessible") is not True
            or row.get("directional_feasibility") != "BOTH_FEASIBLE"
        ):
            raise ScopeAuditError("eligible frame contains duplicate or ineligible identities")
        eligible[symbol_id] = row
        by_symbol[symbol] = symbol_id
    if len(eligible) != ELIGIBLE_COUNT:
        raise ScopeAuditError("candidate index does not contain the complete eligible frame")

    selected = (blocked_freeze.get("selection") or {}).get("exact_symbols")
    if not isinstance(selected, list) or len(selected) != 48 or len(set(selected)) != 48:
        raise ScopeAuditError("the exact prospectively blocked 48-symbol scope is malformed")
    blocked_symbols = set(selected)

    scoped_rows: list[dict[str, Any]] = []
    observed_scope_ids: dict[str, set[int]] = {}
    union: set[int] = set()
    noneligible_capture_ids: set[int] = set()
    for scope in scopes:
        if not isinstance(scope, dict):
            raise ScopeAuditError("accepted M5 scope must be an object")
        plan_ref = scope.get("frozen_plan_ref")
        acceptance_ref = scope.get("acceptance_ref")
        plan_hash = scope.get("frozen_plan_file_sha256")
        acceptance_hash = scope.get("acceptance_sha256")
        if not all(isinstance(value, str) and value for value in (plan_ref, acceptance_ref, plan_hash, acceptance_hash)):
            raise ScopeAuditError("accepted M5 scope lacks exact plan or acceptance bindings")
        if Path(plan_ref).is_absolute() or Path(acceptance_ref).is_absolute() or ".." in Path(plan_ref).parts or ".." in Path(acceptance_ref).parts:
            raise ScopeAuditError("capture authority reference escapes the repository")
        _require_hash(root, plan_ref, plan_hash)
        _require_hash(root, acceptance_ref, acceptance_hash)
        plan = _read_json(root, plan_ref)
        acceptance = _read_json(root, acceptance_ref)
        exact_rows = scope.get("exact_broker_identities")
        if not isinstance(exact_rows, list) or len(exact_rows) != scope.get("identity_count"):
            raise ScopeAuditError("capture scope identity count does not reconcile")
        exact: set[tuple[int, str]] = set()
        for identity in exact_rows:
            if not isinstance(identity, dict):
                raise ScopeAuditError("captured broker identity must be an object")
            symbol_id, symbol = identity.get("symbol_id"), identity.get("broker_symbol")
            if (
                isinstance(symbol_id, bool)
                or not isinstance(symbol_id, int)
                or not isinstance(symbol, str)
                or not symbol
                or (symbol_id, symbol) in exact
            ):
                raise ScopeAuditError("capture identity list contains an invalid or duplicate identity")
            exact.add((symbol_id, symbol))
        plan_identities = _document_identities(plan)
        if exact and plan_identities != exact:
            raise ScopeAuditError("frozen capture plan identities differ from accepted scope inventory")
        accepted_identities = _document_identities(acceptance)
        if exact and accepted_identities and accepted_identities != exact:
            raise ScopeAuditError("capture acceptance identities differ from accepted scope inventory")
        interval = scope.get("requested_interval_utc")
        if (
            not isinstance(interval, dict)
            or not isinstance(interval.get("start_utc"), str)
            or not isinstance(interval.get("end_utc"), str)
            or scope.get("resolution") != "M5"
            or scope.get("account_fingerprint_sha256") != ACCOUNT_FINGERPRINT
            or scope.get("identity_count") != len(exact)
        ):
            raise ScopeAuditError("capture interval, resolution, or provenance is invalid")
        if _parse_utc(interval["end_utc"]) < _parse_utc(interval["start_utc"]):
            raise ScopeAuditError("capture interval ends before its start")
        expected_interval = (interval["start_utc"], interval["end_utc"])
        plan_intervals = _intervals(plan)
        if expected_interval not in plan_intervals:
            raise ScopeAuditError("frozen capture plan interval differs from accepted scope inventory")
        if "M5" not in _resolutions(plan):
            raise ScopeAuditError("frozen capture plan resolution differs from accepted scope inventory")
        accepted_status = acceptance.get("status")
        if accepted_status != scope.get("acceptance_status"):
            raise ScopeAuditError("capture acceptance status differs from accepted scope inventory")

        eligible_ids: set[int] = set()
        blocked_ids: set[int] = set()
        mismatches: list[dict[str, Any]] = []
        for symbol_id, symbol in exact:
            candidate = eligible.get(symbol_id)
            if candidate is None:
                continue
            if candidate.get("broker_symbol") != symbol:
                mismatches.append({
                    "symbol_id": symbol_id,
                    "accepted_broker_symbol": symbol,
                    "eligible_broker_symbol": candidate.get("broker_symbol"),
                })
                continue
            if symbol in blocked_symbols:
                blocked_ids.add(symbol_id)
            else:
                eligible_ids.add(symbol_id)
        if mismatches:
            raise ScopeAuditError("capture broker symbols do not match eligible identity authority")
        scope_key = acceptance_ref
        observed_scope_ids[scope_key] = eligible_ids
        union.update(eligible_ids)
        noneligible_capture_ids.update(symbol_id for symbol_id, _ in exact if symbol_id not in eligible)

        portion = scope.get("disjoint_m5_portion_after_prior_end")
        disjoint_eligible_ids: set[int] = set()
        disjoint_interval = None
        if portion is not None:
            if not isinstance(portion, dict):
                raise ScopeAuditError("declared disjoint M5 interval is malformed")
            start, end = portion.get("start_utc"), portion.get("end_utc")
            if not isinstance(start, str) or not isinstance(end, str):
                raise ScopeAuditError("declared disjoint M5 interval lacks exact UTC bounds")
            if _parse_utc(start) <= _parse_utc(PRIOR_WINDOW_END) or _parse_utc(end) < _parse_utc(start):
                raise ScopeAuditError("declared disjoint M5 interval overlaps prior observation window")
            disjoint_interval = {"start_utc": start, "end_utc": end}
            disjoint_eligible_ids = eligible_ids

        scoped_rows.append({
            "acceptance_ref": acceptance_ref,
            "acceptance_sha256": acceptance_hash,
            "frozen_plan_ref": plan_ref,
            "frozen_plan_sha256": plan_hash,
            "resolution": "M5",
            "requested_interval_utc": expected_interval,
            "identity_count": len(exact),
            "eligible_exact_identity_count": len(eligible_ids) + len(blocked_ids),
            "eligible_exact_identity_ids": sorted(eligible_ids | blocked_ids),
            "eligible_reusable_identity_count": len(eligible_ids),
            "blocked_scope_identity_count": len(blocked_ids),
            "blocked_scope_identity_ids": sorted(blocked_ids),
            "disjoint_m5_portion_after_prior_end": disjoint_interval,
            "disjoint_eligible_identity_count": len(disjoint_eligible_ids),
            "disjoint_eligible_identity_ids": sorted(disjoint_eligible_ids),
            "external_hash_bound_bytes_are_transport_materialization_not_new_acquisition": (
                scope.get("raw_capture_hash_bound_externally") is True
                and scope.get("raw_capture_bytes_in_repository") is False
            ),
            "c031_extension_not_a_substitute_for_another_proposal": (
                acceptance_ref == C031_EXTENSION_ACCEPTANCE
            ),
        })

    overlap_count = sum(len(ids) for ids in observed_scope_ids.values()) - len(union)
    candidates = [
        row for row in scoped_rows
        if row["disjoint_m5_portion_after_prior_end"] is not None
        and row["disjoint_eligible_identity_count"] > 0
        and row["acceptance_ref"] != C031_EXTENSION_ACCEPTANCE
    ]
    power = (prior_result.get("power_preflight") or {}).get(
        "planning_sensitivity_reused_from_epoch42"
    )
    if not isinstance(power, list) or not power:
        raise ScopeAuditError("accepted planning-only effective-sample requirements are missing")
    if any(
        item.get("required_effective_independent_clusters") is None
        or item.get("target_power") != 0.8
        for item in power
    ):
        raise ScopeAuditError("accepted effective-sample requirements are malformed")

    return {
        "schema": "mxm.greenfield.mean-reversion-capture-scope-audit-epoch45.v1",
        "status": "COMPLETE_NON_ECONOMIC_SCOPE_RECONCILIATION_NO_COHORT_OR_ACQUISITION_AUTHORIZED",
        "evidence_epoch": 45,
        "implementation": {"version": VERSION, "freeze_ref": FREEZE_REF},
        "source_authority": {
            "accepted_proposal_ref": PROPOSAL_REF,
            "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
            "accepted_capture_scope_audit_ref": SCOPE_AUDIT_REF,
            "accepted_capture_scope_audit_sha256": SCOPE_AUDIT_SHA256,
            "eligible_universe_ref": FEASIBILITY_REF,
            "eligible_identity_count": ELIGIBLE_COUNT,
            "eligible_identity_set_sha256": ELIGIBLE_SET_SHA256,
            "outcome_blind_candidate_index_ref": PEER_INDEX_REF,
            "epoch43_preflight_ref": EPOCH43_RESULT_REF,
            "epoch43_preflight_sha256": EPOCH43_RESULT_SHA256,
        },
        "eligible_frame": {
            "eligible_identity_count": ELIGIBLE_COUNT,
            "structural_41_used_as_inferential_universe": False,
            "blocked_epoch38_scope_ref": BLOCKED_SCOPE_FREEZE_REF,
            "blocked_scope_symbols_excluded_from_proposed_increment": len(blocked_symbols),
        },
        "accepted_coverage": {
            "accepted_scope_count": len(scoped_rows),
            "eligible_identity_count_with_any_accepted_scope": len(union),
            "eligible_identity_count_without_reusable_accepted_scope": ELIGIBLE_COUNT - len(union),
            "eligible_identity_scope_overlaps_counted_more_than_once": overlap_count,
            "captured_identities_not_in_current_eligible_frame": len(noneligible_capture_ids),
            "scope_details": scoped_rows,
            "other_external_hash_bound_bytes_claimed_absent": False,
        },
        "effective_sample_requirements": {
            "source": "Accepted Epoch42 planning sensitivities, reused without rerunning its diagnostic.",
            "planning_only_scenarios": power,
            "achieved_power_estimated": False,
            "observed_effective_sample_size": None,
        },
        "disjoint_increment": {
            "smallest_increment_selected": False,
            "smallest_increment_assessment": {
                "status": "NOT_IDENTIFIABLE_FROM_ACCEPTED_MANIFEST_SUMMARIES",
                "reason": (
                    "Accepted scope manifests establish identity and interval coverage, but do not "
                    "establish contiguous schedule-adjusted completeness or dependence-aware excursion "
                    "cluster counts for an outcome-blind cohort."
                ),
                "effective_sample_requirements_ref": EPOCH43_RESULT_REF,
                "thresholds_are_planning_sensitivities_not_economic_cutoffs": True,
            },
            "candidate_accepted_disjoint_scopes": candidates,
            "status": (
                "NO_ELIGIBLE_DISJOINT_ACCEPTED_SCOPE"
                if not candidates else
                "DISJOINT_COVERAGE_CANDIDATES_DO_NOT_ESTABLISH_COHORT_COMPLETENESS_OR_EFFECTIVE_SAMPLE_SIZE"
            ),
            "new_interval_selected": False,
            "exact_symbols_selected": [],
            "new_market_data_requested_or_authorized": False,
            "required_before_any_later_increment": [
                "Prospective outcome-blind cohort decision from current eligible-universe authority and non-outcome features.",
                "Authenticated contiguous M5 coverage and schedule-adjusted completeness for the exact selected identities.",
                "Causal excursion-cluster and dependence-aware effective-sample-size audit before response statistics.",
                "Separately frozen response interval disjoint from all prior mean-reversion response windows.",
            ],
            "blocked_exact_48_symbol_scope_reused": False,
            "c031_twelve_symbol_extension_used_to_satisfy_another_scope": False,
        },
        "alternatives_and_exclusions": {
            "proposal_alternatives": (
                ((proposal.get("decision") or {}).get("discovery_governance") or {}).get(
                    "alternatives_considered"
                )
                or []
            ),
            "excluded_blocked_scope_symbols": sorted(blocked_symbols),
            "excluded_c031_extension_as_scope_substitute": True,
            "structural_representatives_are_inferential_equivalents": False,
            "selection_features_declared_for_later_scope_decision": [
                "accessibility",
                "directional_margin_feasibility",
                "minimum_executable_volume",
                "product_type",
                "trading_schedule",
                "asset_class",
                "data_availability_and_completeness",
                "capital_efficiency",
                "conservative_friction_proxy",
                "structural diversity",
            ],
            "selection_from_outcomes": False,
        },
        "interpretation_boundary": {
            "strategy_events_or_response_statistics_computed": False,
            "returns_or_pnl_computed": False,
            "economic_outcome_opened": False,
            "candidate_economic_identity_created": False,
            "v2_attempt_consumed": False,
            "protected_forward_opened": False,
            "relative_value_alignment_inventory_recomputed": False,
            "epoch42_diagnostic_rerun": False,
            "internal_development_holdout_claimed_as_independent_confirmation": False,
            "mechanism_family_closed": False,
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
            "Fresh prospective judgment may decide whether a minimal disjoint M5 data scope is justified; "
            "this report authorizes no acquisition and selects no cohort."
        ),
    }


def build_scope_audit(root_value: str | Path = ".") -> dict[str, Any]:
    root = Path(root_value).resolve()
    feasibility, peer_index, inventory, prior_result, blocked, proposal = _load_inputs(root)
    result = build_from_authorities(
        feasibility, peer_index, inventory, prior_result, blocked, proposal, root=root
    )
    result["freeze_sha256"] = _sha256(root / FREEZE_REF)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = build_scope_audit(args.root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
