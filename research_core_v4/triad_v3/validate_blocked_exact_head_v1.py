"""Read-only deterministic verification of preserved history and V3 blocker."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
START = "342009ecc2f1944b289a7cd482935458323f5567"
state_path = "research_core_v4/state/V4_STATE.json"
def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)
def sha(data):
    return hashlib.sha256(data).hexdigest()

history_paths = git("ls-tree", "-r", "--name-only", START).decode().splitlines()
changes = []
for path in history_paths:
    if sha(git("show", START+":"+path)) != sha((ROOT / path).read_bytes()):
        changes.append(path)
assert changes == [state_path], changes
before = json.loads(git("show", START+":"+state_path))
after = json.loads((ROOT / state_path).read_text())
changed_state_keys = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
assert changed_state_keys == ["next_action", "status", "stop_boundary", "triad_relational_state_v3_wave"], changed_state_keys
blocker_path = "research_core_v4/state/TRIAD_RELATIONAL_STATE_V3_PREOUTCOME_BLOCKER_V1.json"
blocker_bytes = (ROOT / blocker_path).read_bytes()
blocker = json.loads(blocker_bytes)
assert after["triad_relational_state_v3_wave"]["blocker_sha256"] == sha(blocker_bytes)
for path, expected in blocker["bindings"].items():
    assert sha((ROOT / path).read_bytes()) == expected, path
raw = json.loads((ROOT / blocker["failed_gate"]["raw_ref"]).read_text())
assert not raw["all_pass"] and len(raw["failed_fixture_indices"]) == 6
assert blocker["real_response_authority"] is False
assert not blocker["READY_FOR_FULL_SYNTHETIC_EXECUTION_NOT_EXECUTED"]
assert all(blocker["task_counters"][key] == 0 for key in ["full_stochastic_null_cases_executed", "full_stochastic_power_cases_executed", "Monte_Carlo_trials", "real_response_openings", "future_real_signed_response_computations", "broker_contacts", "historical_requests", "new_acquisition", "candidate_frozen_count", "orders"])
witness = next(r for r in raw["fixtures"] if r["n"] == 23 and r["epsilon"] == 1e-6)
assert witness["canonical_accepted"] and witness["canonical_rank_tol_1e12"] == 3
assert witness["adapter"]["scaled_gram_determinant"] > 1e-12
assert witness["adapter"]["actual_clockfit_status"] == "THROWS_projection orthogonality error"
assert blocker["failed_gate"]["concrete_witness"]["canonical_residual_rms"] == witness["canonical_residual_rms"]
for row in raw["fixtures"]:
    if row["canonical_accepted"] and row["adapter"]["actual_clockfit_status"] != "ACCEPTED":
        assert not row["pass"]
new_paths = [p for p in git("ls-files", "--others", "--exclude-standard").decode().splitlines()]
assert all(p.startswith("research_core_v4/triad_v3/") or p == blocker_path for p in new_paths), new_paths
print(json.dumps({"status": "PASS_BLOCKED_STATE_INTEGRITY_NOT_STATISTICAL_CERTIFICATION", "starting_head": START,
                  "validated_head": git("rev-parse", "HEAD").decode().strip(),
                  "historical_files_checked": len(history_paths), "changed_historical_files": changes,
                  "changed_state_keys": changed_state_keys, "blocker_sha256": sha(blocker_bytes),
                  "deterministic_projection_failures": 6, "Monte_Carlo_trials": 0}, sort_keys=True))
