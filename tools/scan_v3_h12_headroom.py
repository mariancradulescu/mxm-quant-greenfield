"""Diagnostic H12 (~60 minute) headroom scan over the existing corrected V3 surface.

No new market data, no protected-forward access, no candidate promotion.
The corrected surface already contains H12 DEVELOPMENT outcomes. This script reuses
the same outcome-informed gross-screen heuristics and parameter connectivity as the
H6 assessment, but it does NOT claim H12 familywise multiplicity inference because
week-cluster vectors were retained only for the frozen H6 primary horizon.
"""
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from research_core_v3.corrected_semantics import VARIANTS, adjacent
from tools.run_v3_broad_surface import canonical, sha

HORIZON = "12"
POLICY = {
    "material_mean_response_bps": 0.1,
    "minimum_event_retention": 0.5,
    "minimum_date_support": 60,
    "minimum_week_support": 20,
    "maximum_top10_absolute_concentration": 0.5,
    "chronological_thirds": "ALL_THREE_POSITIVE",
    "minimum_numeric_connected_plateau_cells": 3,
}


def horizon_gross_checks(cell: dict) -> dict[str, bool]:
    strict = cell["variants"][VARIANTS[3]]["horizons"][HORIZON]
    timing = cell["variants"][VARIANTS[1]]["horizons"][HORIZON]
    effects = cell["effects"][HORIZON]
    threshold = POLICY["material_mean_response_bps"] / 1e4
    return {
        "timing_continuity_sign_stability": effects["sign_stability"] is True,
        "material_corrected_next_open": (strict["mean_response"] or 0) > threshold
        and (timing["mean_response"] or 0) > threshold,
        "positive_robust_effect": (strict["robust_effect_estimate"] or 0) > 0,
        "retention": (cell["event_retention_fraction"] or 0)
        >= POLICY["minimum_event_retention"],
        "dates": strict["independent_date_clusters"]
        >= POLICY["minimum_date_support"],
        "weeks": strict["independent_week_clusters"]
        >= POLICY["minimum_week_support"],
        "chronology": len(strict["chronological_thirds"]) == 3
        and all((x or 0) > 0 for x in strict["chronological_thirds"]),
        "concentration": strict["response_concentration_top10_abs_share"]
        is not None
        and strict["response_concentration_top10_abs_share"]
        <= POLICY["maximum_top10_absolute_concentration"],
    }


def load_cells(root: Path) -> tuple[dict, list[dict]]:
    state = root / "research_core_v3" / "state"
    manifest = json.loads(
        (state / "CORRECTED_145_DEVELOPMENT_MANIFEST_V2.json").read_text()
    )
    digest = manifest.pop("sha256")
    assert sha(canonical(manifest)) == digest
    cells: list[dict] = []
    for shard in manifest["shards"]:
        blob = (state / shard["path"]).read_bytes()
        assert sha(blob) == shard["sha256"]
        doc = json.loads(gzip.decompress(blob))
        for symbol in doc["symbols"]:
            cells.extend(symbol["cells"])
    assert len(cells) == 7975
    return {"sha256": digest, **manifest}, cells


def connected_regions(cells: list[dict], spec: dict) -> list[dict]:
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, cell in enumerate(cells):
        key = (
            cell["symbol_id"],
            cell["mechanism"],
            json.dumps(cell["context"], sort_keys=True),
        )
        groups[key].append(i)

    regions: list[dict] = []
    for key, ids in groups.items():
        mechanism = key[1]
        grid = next(
            m["parameter_grid"]
            for m in spec["mechanisms"]
            if m["name"] == mechanism
        )
        passing = {
            i for i in ids if all(horizon_gross_checks(cells[i]).values())
        }
        while passing:
            initial = min(passing)
            component = {initial}
            stack = [initial]
            passing.remove(initial)
            while stack:
                i = stack.pop()
                neighbors = [
                    j
                    for j in sorted(passing)
                    if adjacent(cells[i]["params"], cells[j]["params"], grid)
                ]
                for j in neighbors:
                    passing.remove(j)
                    component.add(j)
                    stack.append(j)
            if len(component) < POLICY[
                "minimum_numeric_connected_plateau_cells"
            ]:
                continue
            members = [cells[i] for i in sorted(component)]
            strict = [
                c["variants"][VARIANTS[3]]["horizons"][HORIZON]
                for c in members
            ]
            regions.append(
                {
                    "symbol": members[0]["symbol"],
                    "symbol_id": int(members[0]["symbol_id"]),
                    "mechanism": mechanism,
                    "context": members[0]["context"],
                    "plateau_cell_count": len(members),
                    "parameters": [c["params"] for c in members],
                    "constituent_cell_indices": sorted(component),
                    "minimum_mean_response_bps": min(
                        float(x["mean_response"]) * 1e4 for x in strict
                    ),
                    "median_member_mean_response_bps": float(
                        np.median(
                            [float(x["mean_response"]) * 1e4 for x in strict]
                        )
                    ),
                    "minimum_robust_effect_bps": min(
                        float(x["robust_effect_estimate"]) * 1e4
                        for x in strict
                    ),
                    "minimum_event_count": min(int(x["n"]) for x in strict),
                    "minimum_independent_week_clusters": min(
                        int(x["independent_week_clusters"]) for x in strict
                    ),
                    "horizon_bars": 12,
                    "approx_holding_minutes": 60,
                    "multiplicity_status": "NOT_RECOMPUTED_AT_H12",
                    "candidate_frozen": False,
                }
            )
    return regions


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    state = root / "research_core_v3" / "state"
    manifest, cells = load_cells(root)
    spec = json.loads((state / "FROZEN_EXPERIMENT_SPEC_V1.json").read_text())
    assert 12 in spec["response_horizons_bars"]
    assert spec["primary_horizon_bars"] == 6

    checks = [horizon_gross_checks(c) for c in cells]
    gross_cells = sum(all(x.values()) for x in checks)
    regions = connected_regions(cells, spec)
    regions.sort(
        key=lambda r: (
            -r["minimum_mean_response_bps"],
            r["symbol"],
            r["mechanism"],
        )
    )
    measured_symbols = set()
    for name in (
        "MAXT14_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V2.json",
        "WAVE2_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V1.json",
        "WINNER_FIRST_FRICTION_ACQUISITION_PLAN_V1.json",
    ):
        doc = json.loads((state / name).read_text())
        measured_symbols.update(str(x["symbol"]) for x in doc["targets"])
    for region in regions:
        region["has_existing_authentic_friction_sample"] = (
            region["symbol"] in measured_symbols
        )

    by_mech = {}
    for mech in [m["name"] for m in spec["mechanisms"]]:
        rs = [r for r in regions if r["mechanism"] == mech]
        by_mech[mech] = {
            "diagnostic_regions": len(rs),
            "symbols": len({r["symbol_id"] for r in rs}),
            "max_minimum_mean_response_bps": max(
                (r["minimum_mean_response_bps"] for r in rs), default=None
            ),
        }

    report = {
        "schema": "mxm.research-core-v3.h12-headroom-diagnostic.v1",
        "status": "DEVELOPMENT_DIAGNOSTIC_ONLY",
        "source_corrected_surface_sha256": manifest["sha256"],
        "existing_surface_cells": 7975,
        "source_primary_horizon_bars": 6,
        "diagnostic_horizon_bars": 12,
        "approx_holding_minutes": 60,
        "new_market_data_used": False,
        "protected_forward_opened": False,
        "outcome_informed_diagnostic": True,
        "candidate_freeze_allowed": False,
        "net_certification_allowed": False,
        "h12_familywise_multiplicity_recomputed": False,
        "reason_no_h12_familywise_claim": (
            "H12 week-cluster vectors were not retained in assembled corrected shards; "
            "existing H6 max-T p-values cannot be reused for H12."
        ),
        "screening_policy": POLICY,
        "h12_gross_screen_cells": gross_cells,
        "h12_connected_diagnostic_regions": len(regions),
        "h12_connected_symbols": len({r["symbol_id"] for r in regions}),
        "mechanisms": by_mech,
        "regions": regions,
        "top20": regions[:20],
    }
    report["sha256"] = sha(canonical(report))
    out = state / "H12_HEADROOM_DIAGNOSTIC_V1.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "sha256": report["sha256"],
                "gross_cells": gross_cells,
                "regions": len(regions),
                "symbols": report["h12_connected_symbols"],
                "mechanisms": by_mech,
                "top20": regions[:20],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
