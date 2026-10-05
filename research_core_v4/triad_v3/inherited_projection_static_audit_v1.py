"""Execute the frozen feature-only inheritance gate. No Monte Carlo, no Y."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import numpy as np

P = Path(__file__).parent
ROOT = P.resolve().parents[1]
plan_path = P / "INHERITED_SCIENCE_STATIC_GATE_PLAN_V1.json"
plan = json.loads(plan_path.read_text())
for path, expected in plan["bindings"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
spec = importlib.util.spec_from_file_location("canonical_v2", ROOT / "research_core_v4/triad_v2/orthogonal_score_v2.py")
canonical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canonical)
fixtures = []
stdin = []
for n in plan["fixtures"]["target_counts"]:
    for epsilon in plan["fixtures"]["near_collinearity_epsilon"]:
        i = np.arange(1, n+1, dtype=float)
        a = np.sin(i*np.sqrt(2))
        X = np.column_stack([np.ones(n), a, a+epsilon*np.cos(i*np.sqrt(3))])
        D = np.sin(i*np.sqrt(5))
        Z = X / np.sqrt(np.mean(X*X, axis=0))
        singular = np.linalg.svd(Z, compute_uv=False)
        row = {"n": n, "epsilon": epsilon, "scaled_singular_values": singular.tolist(),
               "canonical_rank_tol_1e12": int(np.linalg.matrix_rank(Z, tol=1e-12))}
        try:
            result = canonical.current_projection(X, D)
            row.update(canonical_accepted=True, canonical_residual_rms=result["rms"],
                       canonical_orthogonality_error=result["orthogonality_error"],
                       canonical_normalized=result["normalized"].tolist())
        except AssertionError:
            row["canonical_accepted"] = False
        fixtures.append(row)
        stdin.append(str(n))
        stdin.extend(" ".join(format(float(v), ".17g") for v in [*X[j], D[j]]) for j in range(n))
with tempfile.TemporaryDirectory(prefix="triad_v3_static_") as tmp:
    binary = Path(tmp) / "projection_fixture"
    command = ["g++", "-O3", "-std=c++17", "-Wall", "-Wextra", str(P / "projection_adapter_fixture_v1.cpp"), "-o", str(binary)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    completed = subprocess.run([str(binary)], input="\n".join(stdin)+"\n", capture_output=True, text=True, check=True)
    cpp = [json.loads(line) for line in completed.stdout.splitlines()]
assert len(cpp) == len(fixtures)
failures = []
for index, (row, candidate) in enumerate(zip(fixtures, cpp)):
    row["adapter"] = candidate
    row["pass"] = True
    if row["canonical_accepted"]:
        if candidate["actual_clockfit_status"] != "ACCEPTED":
            row["pass"] = False
            row["failure"] = "CANONICAL_ELIGIBLE_ACTUAL_CLOCKFIT_REJECTS_OR_THROWS"
        elif not candidate["accepted"]:
            row["pass"] = False
            row["failure"] = "CANONICAL_ELIGIBLE_ADAPTER_REJECTS"
        else:
            error = float(np.max(np.abs(np.array(row["canonical_normalized"])-candidate["normalized"])))
            row["maximum_normalized_residual_error"] = error
            row["pass"] = error <= 1e-7
            if not row["pass"]:
                row["failure"] = "PROJECTION_OUTPUT_NOT_EQUIVALENT"
    if not row["pass"]:
        failures.append(index)
raw = {
    "schema": "TRIAD_V3_INHERITED_PROJECTION_STATIC_RAW_V1",
    "gate_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "fixture_source_sha256": hashlib.sha256((P / "projection_adapter_fixture_v1.cpp").read_bytes()).hexdigest(),
    "toolchain": {"compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0],
                  "flags": ["-O3", "-std=c++17", "-Wall", "-Wextra"], "fast_math": False,
                  "binary_sha256": binary_sha, "numpy": np.__version__},
    "fixtures": fixtures, "failed_fixture_indices": failures,
    "all_pass": not failures, "Monte_Carlo_trials": 0, "Y_values_read_or_generated": 0,
    "real_response_reads": 0, "benchmark": "NOT_PERFORMED"
}
(P / "INHERITED_PROJECTION_STATIC_RAW_V1.json").write_text(json.dumps(raw, indent=2, sort_keys=True)+"\n")
print(json.dumps({"all_pass": raw["all_pass"], "failures": [{"n": fixtures[i]["n"], "epsilon": fixtures[i]["epsilon"], "failure": fixtures[i]["failure"]} for i in failures], "Monte_Carlo_trials": 0}))
