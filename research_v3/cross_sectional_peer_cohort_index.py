from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

VERSION = "MXM_CROSS_SECTIONAL_PEER_COHORT_INDEX_V1"
PROPOSAL_REF = (
    "research_v3/ai_director/proposals/"
    "AUTO_reason_c54ec9e39feb63a7b60e3645657abf92.json"
)
PROPOSAL_FILE_SHA256 = (
    "2fb81a1d14f4cccda301f44370cceeda6ff1389fcc3ac96e6427009c64ba2657"
)
FEASIBILITY_REF = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"
FEASIBILITY_PAYLOAD_SHA256 = (
    "7b268eae05fad325cb1f0fc962511ca41236b3b58bb83023735fd22b94301452"
)
ELIGIBLE_IDENTITY_SET_SHA256 = (
    "e53dc4e58d4e0d37eca4f528e06d0866ad8ffe3f2bc64d35278ecc8ee9f52a65"
)
COMPACT_AUTHORITY_SHA256 = (
    "2629b471abd6c35351eefae43d2fefbd423e2726cb89363c32f2287e7bedd857"
)
STRUCTURAL_REGISTRY_SHA256 = (
    "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3"
)
FEATURE_STORE_SHA256 = (
    "b92ad33bffad77f00b86933e1f552736485782e17fdea98fd0e84d1ab6dd117c"
)
OPPORTUNITY_MAP_SHA256 = (
    "a6d024f43dd6066a73a1d6dadf35657e30968259d653fd9b4e4b30c5fde42639"
)
ARCHITECTURE_SHA256 = (
    "6b14648bad0aa8e0753f3771896892d0a7d70bd89911800ce9bdbafc0e96a568"
)
EXPECTED_UNIVERSE_SIZE = 1576
ALIGNMENT_STATUS = "NOT_ACQUIRED_MECHANISM_SPECIFIC"

REQUIRED_ROW_FIELDS = frozenset(
    {
        "broker_symbol",
        "symbol_id",
        "current_entry_accessible",
        "directional_feasibility",
        "test_product",
        "shortability",
        "asset_class",
        "product_type",
        "session_regions",
        "coverage_bucket",
        "minimum_executable_volume",
        "buy_min_volume_margin_eur",
        "sell_min_volume_margin_eur",
        "schedule_minutes_per_week",
        "accepted_history_state",
        "history_completeness",
        "commission_fee_metadata_available",
        "conservative_friction_proxy_eur",
    }
)


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _finite_number(value: Any, field: str, *, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _cohort_components(row: dict[str, Any]) -> tuple[str, str, str, str] | None:
    asset_class = row["asset_class"]
    product_type = row["product_type"]
    regions = row["session_regions"]
    schedule = row["coverage_bucket"]
    if not all(
        isinstance(value, str) and value.strip()
        for value in (asset_class, product_type, regions, schedule)
    ):
        return None
    normalized_regions = "|".join(
        sorted(set(region.strip() for region in regions.split("|") if region.strip()))
    )
    if not normalized_regions:
        return None
    return asset_class.strip(), product_type.strip(), normalized_regions, schedule.strip()


def _cohort_id(components: tuple[str, str, str, str]) -> str:
    return "peer_" + _sha256_json(list(components))[:16]


def validate_input_bundle(
    bundle: dict[str, Any],
    expected_count: int = EXPECTED_UNIVERSE_SIZE,
) -> list[dict[str, Any]]:
    if not isinstance(bundle, dict):
        raise ValueError("peer-cohort input bundle must be an object")
    if bundle.get("schema") != "mxm.greenfield.cross-sectional-peer-cohort-input.v1":
        raise ValueError("unsupported peer-cohort input schema")
    bindings = bundle.get("source_bindings")
    if not isinstance(bindings, dict):
        raise ValueError("source_bindings must be an object")
    expected_bindings = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
        "current_feasibility_ref": FEASIBILITY_REF,
        "current_broker_payload_sha256": FEASIBILITY_PAYLOAD_SHA256,
        "eligible_identity_set_sha256": ELIGIBLE_IDENTITY_SET_SHA256,
        "compact_authority_sha256": COMPACT_AUTHORITY_SHA256,
        "structural_registry_ref": (
            "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
        ),
        "structural_registry_sha256": STRUCTURAL_REGISTRY_SHA256,
        "feature_store_ref": "research_v3/BROKER_NATIVE_FRONTIER_FEATURE_STORE_EPOCH23_V1.json",
        "feature_store_sha256": FEATURE_STORE_SHA256,
        "opportunity_map_ref": "research_v3/BROKER_NATIVE_FRONTIER_OPPORTUNITY_MAP_EPOCH23_V1.json",
        "opportunity_map_sha256": OPPORTUNITY_MAP_SHA256,
        "architecture_ref": "research_v3/ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE_V1.json",
        "architecture_sha256": ARCHITECTURE_SHA256,
    }
    if any(bindings.get(key) != value for key, value in expected_bindings.items()):
        raise ValueError("peer-cohort input is not bound to the accepted current authority")
    rows = bundle.get("eligible_identities")
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ValueError(f"expected exactly {expected_count} eligible identities")

    symbols: set[str] = set()
    symbol_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each eligible identity must be an object")
        missing = REQUIRED_ROW_FIELDS - row.keys()
        extra = row.keys() - REQUIRED_ROW_FIELDS
        if missing or extra:
            raise ValueError(
                f"invalid identity fields; missing={sorted(missing)}, extra={sorted(extra)}"
            )
        symbol = row["broker_symbol"]
        symbol_id = row["symbol_id"]
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("broker_symbol must be non-empty")
        if isinstance(symbol_id, bool) or not isinstance(symbol_id, int) or symbol_id < 0:
            raise ValueError("symbol_id must be a non-negative integer")
        if symbol in symbols or symbol_id in symbol_ids:
            raise ValueError("duplicate broker identity")
        symbols.add(symbol)
        symbol_ids.add(symbol_id)
        if row["current_entry_accessible"] is not True:
            raise ValueError(f"{symbol} is not currently entry accessible")
        if row["directional_feasibility"] != "BOTH_FEASIBLE":
            raise ValueError(f"{symbol} is not feasible in both directions")
        if row["test_product"] is not False:
            raise ValueError(f"{symbol} is a test or unresolved product")
        if row["shortability"] is not True:
            raise ValueError(f"{symbol} is not confirmed shortable")
        if not isinstance(row["accepted_history_state"], str) or row[
            "accepted_history_state"
        ] not in {
            "ACCEPTED_HISTORY_AVAILABLE",
            "NO_ACCEPTED_HISTORY",
            "UNKNOWN",
        }:
            raise ValueError(f"{symbol} has an unsupported history availability state")
        if not isinstance(row["history_completeness"], str) or not row[
            "history_completeness"
        ].strip():
            raise ValueError(f"{symbol} has invalid history completeness metadata")
        if not isinstance(row["commission_fee_metadata_available"], bool):
            raise ValueError(f"{symbol} has invalid commission metadata availability")
        volume = row["minimum_executable_volume"]
        if not isinstance(volume, (str, int, float)) or isinstance(volume, bool):
            raise ValueError(f"{symbol} has invalid minimum executable volume")
        try:
            volume_decimal = Decimal(str(volume))
        except InvalidOperation as error:
            raise ValueError(f"{symbol} has invalid minimum executable volume") from error
        if not volume_decimal.is_finite() or volume_decimal <= 0:
            raise ValueError(f"{symbol} has invalid minimum executable volume")
        buy_margin = _finite_number(row["buy_min_volume_margin_eur"], "buy margin")
        sell_margin = _finite_number(row["sell_min_volume_margin_eur"], "sell margin")
        schedule_minutes = _finite_number(
            row["schedule_minutes_per_week"], "schedule_minutes_per_week"
        )
        if buy_margin is None or sell_margin is None or min(buy_margin, sell_margin) <= 0:
            raise ValueError(f"{symbol} has invalid margin metadata")
        if max(buy_margin, sell_margin) > 200:
            raise ValueError(f"{symbol} fails current EUR200 two-direction feasibility")
        if schedule_minutes is None or schedule_minutes < 0:
            raise ValueError(f"{symbol} has invalid schedule metadata")
        friction = _finite_number(
            row["conservative_friction_proxy_eur"],
            "conservative_friction_proxy_eur",
            allow_none=True,
        )
        if friction is not None and friction < 0:
            raise ValueError(f"{symbol} has invalid friction metadata")
    if rows != sorted(rows, key=lambda item: (item["broker_symbol"], item["symbol_id"])):
        raise ValueError("eligible identities must be in canonical symbol/id order")
    return rows


def build_index(
    bundle: dict[str, Any],
    expected_count: int = EXPECTED_UNIVERSE_SIZE,
) -> dict[str, Any]:
    rows = validate_input_bundle(bundle, expected_count)
    cohorts: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    identities = []
    unassigned_count = 0

    for row in rows:
        components = _cohort_components(row)
        cohort_id = _cohort_id(components) if components else None
        if components:
            cohorts[components].append(row)
        else:
            unassigned_count += 1
        buy_margin = float(row["buy_min_volume_margin_eur"])
        sell_margin = float(row["sell_min_volume_margin_eur"])
        minimum_margin = min(buy_margin, sell_margin)
        identities.append(
            {
                "broker_symbol": row["broker_symbol"],
                "symbol_id": row["symbol_id"],
                "peer_candidate_cohort_id": cohort_id,
                "cohort_assignment_status": (
                    "ASSIGNED_CANDIDATE_PEER_COHORT"
                    if cohort_id
                    else "UNASSIGNED_MISSING_COHORT_METADATA"
                ),
                "current_entry_accessible": True,
                "directional_feasibility": "BOTH_FEASIBLE",
                "minimum_executable_volume": row["minimum_executable_volume"],
                "buy_min_volume_margin_eur": buy_margin,
                "sell_min_volume_margin_eur": sell_margin,
                "minimum_directional_margin_eur": minimum_margin,
                "schedule_minutes_per_week": float(row["schedule_minutes_per_week"]),
                "capital_efficiency_proxy_schedule_minutes_per_minimum_margin_eur": (
                    float(row["schedule_minutes_per_week"]) / minimum_margin
                ),
                "commission_fee_metadata_available": row[
                    "commission_fee_metadata_available"
                ],
                "conservative_friction_proxy_eur": row[
                    "conservative_friction_proxy_eur"
                ],
                "accepted_history_state": row["accepted_history_state"],
                "history_completeness": row["history_completeness"],
                "aligned_multi_symbol_history_state": ALIGNMENT_STATUS,
                "peer_coherence_metadata": {
                    "asset_class": row["asset_class"],
                    "product_type": row["product_type"],
                    "session_regions": row["session_regions"],
                    "coverage_bucket": row["coverage_bucket"],
                },
            }
        )

    cohort_reports = []
    for components, members in sorted(cohorts.items()):
        friction = [
            float(row["conservative_friction_proxy_eur"])
            for row in members
            if row["conservative_friction_proxy_eur"] is not None
        ]
        efficiency = [
            float(row["schedule_minutes_per_week"])
            / min(
                float(row["buy_min_volume_margin_eur"]),
                float(row["sell_min_volume_margin_eur"]),
            )
            for row in members
        ]
        cohort_reports.append(
            {
                "peer_candidate_cohort_id": _cohort_id(components),
                "candidate_basis": {
                    "asset_class": components[0],
                    "product_type": components[1],
                    "session_regions": components[2],
                    "coverage_bucket": components[3],
                },
                "breadth": len(members),
                "identity_coverage_count": len(members),
                "commission_fee_metadata_available_count": sum(
                    row["commission_fee_metadata_available"] for row in members
                ),
                "accepted_history_available_count": sum(
                    row["accepted_history_state"] == "ACCEPTED_HISTORY_AVAILABLE"
                    for row in members
                ),
                "no_accepted_history_count": sum(
                    row["accepted_history_state"] == "NO_ACCEPTED_HISTORY"
                    for row in members
                ),
                "history_availability_unknown_count": sum(
                    row["accepted_history_state"] == "UNKNOWN" for row in members
                ),
                "history_completeness_counts": dict(
                    sorted(Counter(row["history_completeness"] for row in members).items())
                ),
                "conservative_friction_proxy_available_count": len(friction),
                "conservative_friction_proxy_eur": {
                    "minimum": min(friction) if friction else None,
                    "median": _median(friction) if friction else None,
                    "maximum": max(friction) if friction else None,
                    "interpretation": (
                        "available metadata only; no spread or slippage is fabricated"
                    ),
                },
                "capital_efficiency_proxy": {
                    "definition": (
                        "schedule_minutes_per_week / "
                        "min(buy_min_volume_margin_eur, sell_min_volume_margin_eur)"
                    ),
                    "minimum": min(efficiency),
                    "median": _median(efficiency),
                    "maximum": max(efficiency),
                    "interpretation": (
                        "broker-feasibility proxy only; not economic quality or a universal ranking"
                    ),
                },
                "aligned_history_readiness": {
                    "state": ALIGNMENT_STATUS,
                    "aligned_identities": 0,
                    "identities_requiring_aligned_history": len(members),
                    "barrier": "aligned history is required before cross-symbol inference",
                },
            }
        )

    return {
        "schema": "mxm.greenfield.cross-sectional-peer-cohort-index.v1",
        "status": "COMPLETE_NON_ECONOMIC_CANDIDATE_UNIVERSE_INDEX",
        "implementation": VERSION,
        "source_bindings": bundle["source_bindings"],
        "source_universe": {
            "expected_eligible_identity_count": expected_count,
            "indexed_identity_count": len(identities),
            "identity_rows_sha256": _sha256_json(
                [[row["broker_symbol"], row["symbol_id"]] for row in identities]
            ),
            "eligible_identity_set_authority_sha256": ELIGIBLE_IDENTITY_SET_SHA256,
        },
        "cohort_policy": {
            "key": [
                "asset_class",
                "product_type",
                "exact normalized session_regions set",
                "coverage_bucket",
            ],
            "selection_is_outcome_blind": True,
            "missing_metadata_policy": "retain identity and flag unassigned; never infer missing values",
            "cohort_membership_is_candidate_peer_coherence_prior_only": True,
            "behavioral_or_economic_equivalence_claimed": False,
            "structural_representatives_used_as_substitutes": False,
        },
        "coverage": {
            "assigned_identity_count": len(identities) - unassigned_count,
            "unassigned_missing_metadata_count": unassigned_count,
            "cohort_count": len(cohort_reports),
            "cohort_breadth_total": sum(row["breadth"] for row in cohort_reports),
            "cohorts": cohort_reports,
        },
        "identities": identities,
        "power_design_prerequisites": [
            "Acquire aligned same-resolution history for a prospectively frozen cohort scope.",
            "Define the later cross-sectional estimand and dependence/cluster unit before outcomes.",
            "Estimate effective independent sample size and power for a prospectively meaningful effect.",
            "Predeclare missingness, schedule overlap, multiplicity, and temporal validation rules.",
            "Do not treat an internal development holdout as independent confirmation.",
        ],
        "interpretation_boundary": {
            "strategy_or_price_outcome_evaluated": False,
            "returns_or_pnl_computed": False,
            "economic_equivalence_claimed": False,
            "aligned_history_sufficient_for_inference": False,
            "protected_forward_opened": False,
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "research_judgment_remaining": (
                "A later estimand, cohort eligibility threshold, acquisition scope, and power "
                "design must be explicitly prospectively frozen."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the outcome-blind peer-cohort index.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = json.loads(args.input.read_text(encoding="utf-8"))
    result = build_index(bundle)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
