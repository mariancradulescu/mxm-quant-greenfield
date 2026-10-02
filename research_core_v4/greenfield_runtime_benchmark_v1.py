from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from research_core_v4 import response_evaluator_v3 as ev
from research_core_v4.runtime_profile_audit_v1 import synthetic_fixture

ROOT = Path(__file__).resolve().parents[1]
BOUNDED_SIZES = (3000, 6000, 12000, 24000)
FULL_SYNTHETIC_SIZE = 118262
BOUNDED_STAGE_LIMIT_SECONDS = 30.0
FULL_REFERENCE_LIMIT_SECONDS = 900.0
AVAILABLE_EXECUTION_LIMIT_SECONDS = 6 * 60 * 60


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile_size(n: int) -> dict:
    events, norm, raw = synthetic_fixture(n)
    t0 = time.perf_counter()
    units = ev.construct_paired_units(events, norm)
    t1 = time.perf_counter()
    diagnostics = ev.build_nonselection_diagnostics(events, norm, raw)
    t2 = time.perf_counter()
    rows = sum(len(v["rows"]) for v in diagnostics.values())
    for value in diagnostics.values():
        assert value["classification"] == "NONSELECTION_ONLY"
        assert value["may_change_lead_verdict"] is False
    return {
        "event_count": n,
        "paired_units": len(units),
        "paired_units_seconds": t1 - t0,
        "nonselection_diagnostics_seconds": t2 - t1,
        "combined_profiled_seconds": t2 - t0,
        "diagnostic_rows": rows,
    }


def main() -> None:
    bounded = [profile_size(n) for n in BOUNDED_SIZES]
    bounded_safe = all(x["combined_profiled_seconds"] < BOUNDED_STAGE_LIMIT_SECONDS for x in bounded)
    if not bounded_safe:
        raise SystemExit("BOUNDED_REFERENCE_PROFILE_UNSAFE_STOP_BEFORE_FULL_SYNTHETIC")
    full = profile_size(FULL_SYNTHETIC_SIZE)
    full_safe = full["combined_profiled_seconds"] < FULL_REFERENCE_LIMIT_SECONDS
    if not full_safe:
        raise SystemExit("FULL_SYNTHETIC_REFERENCE_PROFILE_LACKS_REQUIRED_MARGIN")
    result = {
        "schema": "mxm.research-core-v4.greenfield-reference-runtime-benchmark.v1",
        "status": "PASS_REFERENCE_SOURCE_RUNTIME_WITH_SAFE_MARGIN",
        "synthetic_only": True,
        "real_market_response_values_used": False,
        "reference_implementation_only": True,
        "execution_optimization_adopted": False,
        "bounded_sizes": list(BOUNDED_SIZES),
        "bounded_stage_limit_seconds": BOUNDED_STAGE_LIMIT_SECONDS,
        "bounded_results": bounded,
        "full_synthetic_size": FULL_SYNTHETIC_SIZE,
        "full_reference_limit_seconds": FULL_REFERENCE_LIMIT_SECONDS,
        "full_result": full,
        "available_execution_limit_seconds": AVAILABLE_EXECUTION_LIMIT_SECONDS,
        "measured_margin_multiple_vs_available_limit": AVAILABLE_EXECUTION_LIMIT_SECONDS / full["combined_profiled_seconds"],
        "frozen_reference_hashes": {
            "response_evaluator_v3_sha256": sha256(ROOT / "research_core_v4/response_evaluator_v3.py"),
            "development_execution_runner_v1_sha256": sha256(ROOT / "research_core_v4/development_execution_runner_v1.py"),
            "frozen_v2_semantics_sha256": sha256(ROOT / "research_core_v4/frozen_v2_semantics.py"),
        },
        "support_binding": {
            "rows": 118262,
            "sha256": "e3f8de0012e2bcdd2005d72afef73f738de11fca404675689a8f00422ba0918b",
        },
        "scientific_semantics_changed": False,
        "diagnostics_omitted": False,
        "rng_sequence_changed": False,
        "seed_changed": False,
        "permutations_changed": False,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
