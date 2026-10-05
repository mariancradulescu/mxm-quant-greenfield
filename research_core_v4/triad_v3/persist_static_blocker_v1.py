"""Persist the first failed frozen V3 gate. No science repair or simulation."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
P = Path(__file__).parent
START = "342009ecc2f1944b289a7cd482935458323f5567"
CHECKPOINT = "275c762cc7726c4e758384f1fc35557ac53c1f22"
CLASS = "PREOUTCOME_BLOCKED_INHERITED_CURRENT_PROJECTION_ADAPTER_NOT_EQUIVALENT_UNCERTIFIED_UNTESTED_NOT_NULL"

def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

def write(path, obj):
    (ROOT / path).write_text(json.dumps(obj, indent=2, sort_keys=True)+"\n")

raw = json.loads((P / "INHERITED_PROJECTION_STATIC_RAW_V1.json").read_text())
assert not raw["all_pass"] and raw["Monte_Carlo_trials"] == 0
witness = next(row for row in raw["fixtures"] if row["n"] == 23 and row["epsilon"] == 1e-6)
bindings = json.loads((P / "SUCCESSOR_DECLARATION_V1.json").read_text())["bindings"]
for path, expected in bindings.items():
    assert sha(path) == expected, path
for name in ["SUCCESSOR_DECLARATION_V1.json", "INHERITED_SCIENCE_STATIC_GATE_PLAN_V1.json",
             "INHERITED_PROJECTION_STATIC_RAW_V1.json", "projection_adapter_fixture_v1.cpp",
             "inherited_projection_static_audit_v1.py", "freeze_inheritance_gate_v1.py"]:
    path = "research_core_v4/triad_v3/"+name
    bindings[path] = sha(path)

blocker_path = "research_core_v4/state/TRIAD_RELATIONAL_STATE_V3_PREOUTCOME_BLOCKER_V1.json"
counters = {k: 0 for k in ["full_stochastic_null_cases_executed", "full_stochastic_power_cases_executed",
                          "Monte_Carlo_trials", "real_response_openings", "future_real_signed_response_computations",
                          "broker_contacts", "historical_requests", "new_acquisition", "candidate_frozen_count", "orders"]}
counters.update(confirmation="CLOSED", protected_forward="CLOSED", live_trading="NOT_STARTED", Runtime_V2="READ_ONLY")
stopped = ["dual-layer exact-path/daily-score law freeze", "DAILY_AR025 boundary proof", "DAILY_AR050 boundary proof",
           "midnight/gap latent-state proof", "joint tensor/true-null/stability/breadth invariants",
           "V3 certification worker", "complete certification plan", "simultaneous gate-count/trial-count derivation",
           "SHA256 master-seed derivation", "trial-index manifest", "chunk/resume/merge architecture",
           "serial/chunk/concurrency equivalence", "runtime-only benchmark", "ready authority"]
unresolved = [
    "Inherited canonical SVD projection and historical normal-equations C++ adapter disagree on eligible deterministic feature fixtures; actual clockfit throws. No V3 repair authorized after this frozen gate failure.",
    "No complete V3 dual-layer experiment, worker, daily dependence proof, trial manifest or resume architecture frozen; V3 is not ready.",
    "Exact strong FWER, numerical support calibration, localized power curves and MDE remain uncertified. No FWER or power failure is inferred from this static audit.",
    "Semantic identification remains limited to the declared common within-cohort/fixed-clock own-leg linear span; arbitrary identity-specific or nonlinear baselines excluded.",
    "Interpretation restricted to retained complete-clock population. Informative future-path missingness not certified, missing future clocks not generalized.",
    "Historical reception latency not observed; t-10 convention is research observation law only. Later live infrastructure must record actual information availability.",
    "Accepted 75-FX archive is exposed development evidence, never confirmation. Relational family remains open; V6 and protocol unchanged; depth plan only, not authorized.",
    "Authentic costs, spread, slippage, conversion, executable volume, EUR200 margin/sizing, drawdown and economic headroom unresolved; standardized synthetic effects are not economic returns.",
    "current_host_auth_ready=false; machine-owned cTrader execution/authentication not proven; no broker contact permitted here."
]
blocker = {
    "schema": "TRIAD_RELATIONAL_STATE_V3_PREOUTCOME_BLOCKER_V1", "classification": CLASS,
    "mechanism_id": "TRIAD_RELATIONAL_STATE_V3_DAILY_DEPENDENCE_CERTIFICATION_SUCCESSOR",
    "starting_head": START, "checkpoints": {"successor_and_static_inheritance_gate": CHECKPOINT},
    "relationship_to_V2": "Separate prospective certification successor; canonical V2 estimand/nuisance/support retained by hash. Historical C++ adapter reuse failed static inheritance equivalence. No V1/V2 rescue or reinterpretation.",
    "V1_preserved_blocked": True, "V2_preserved_blocked": True,
    "V2_semantic_status": "PASS_DECLARED_PARTIAL_LINEAR_SEMANTIC_IDENTIFICATION_ONLY",
    "inherited_science_file_bindings_pass": True, "inherited_adapter_equivalence_pass": False,
    "failed_gate": {
        "name": "CURRENT_CLOCK_PROJECTION_AND_NUMERICAL_SUPPORT_MATCH_INHERITED_CANONICAL_LAW",
        "type": "DETERMINISTIC_FEATURE_ONLY_IMPLEMENTATION_NON_EQUIVALENCE",
        "raw_ref": "research_core_v4/triad_v3/INHERITED_PROJECTION_STATIC_RAW_V1.json",
        "failed_fixture_indices": raw["failed_fixture_indices"],
        "concrete_witness": {"n": 23, "epsilon": 1e-6, "canonical_rank": 3,
                             "canonical_residual_rms": witness["canonical_residual_rms"],
                             "actual_clockfit": witness["adapter"]["actual_clockfit_status"]},
        "cause": "Analytic inverse of X-transpose-X loses orthogonality on near-collinear rank-three controls accepted by canonical scaled SVD. Gram determinant test passes in the witness, so this is not merely a singular-control fixture.",
        "not_an_empirical_market_FWER_or_power_result": True
    },
    "bindings": bindings, "toolchain": raw["toolchain"],
    "geometry_sha256": bindings["research_core_v4/triad_v2/EXACT_SYNTHETIC_GEOMETRY_V1.txt"],
    "historical_adapter_sha256_not_a_V3_worker": bindings["research_core_v4/triad_v2/exact_geometry_worker_v1.cpp"],
    "V3_worker_sha256": None, "V3_certification_plan_sha256": None, "V3_trial_manifest_sha256": None,
    "later_components": {name: "NOT_REACHED_FIRST_FROZEN_STATIC_GATE_FAILED" for name in stopped},
    "full_stochastic_certification": "NOT_EXECUTED_NOT_CERTIFIED", "all_preexecution_gates_pass": False,
    "READY_FOR_FULL_SYNTHETIC_EXECUTION_NOT_EXECUTED": False, "real_response_authority": False,
    "partial_V2_stochastic_trials": "NON_EVIDENCE_NOT_READ_OR_USED", "broader_relational_family_closed": False,
    "current_host_auth_ready": False, "task_counters": counters,
    "stop_boundary": "STOP_AFTER_V3_STATIC_BLOCKER; NO_REPAIR_NO_V4_NO_RERANK_NO_MONTE_CARLO_NO_REAL_RESPONSE_NO_ACQUISITION_NO_CONFIRMATION_NO_TRADING",
    "unresolved": unresolved
}
write(blocker_path, blocker)

state_path = "research_core_v4/state/V4_STATE.json"
old = json.loads(subprocess.check_output(["git", "show", START+":"+state_path], cwd=ROOT, text=True))
state = dict(old)
state.update(status="TRIAD_V3_PREOUTCOME_BLOCKED_INHERITED_PROJECTION_ADAPTER_NOT_EQUIVALENT",
             next_action="STOP_FOR_INDEPENDENT_GOVERNANCE_NO_V3_REPAIR_NO_V4_NO_RESELECTION",
             stop_boundary=blocker["stop_boundary"])
state["triad_relational_state_v3_wave"] = {
    "mechanism_id": blocker["mechanism_id"], "classification": CLASS,
    "blocker_ref": blocker_path, "blocker_sha256": sha(blocker_path),
    "V1_and_V2_preserved_blocked": True, "real_response_authorized": False,
    "full_Monte_Carlo_authorized": False, "candidate_frozen_count": 0,
    "confirmation_opened": False, "protected_forward_opened": False,
    "static_gate_pass": False
}
write(state_path, state)

report = f"""# TRIAD V3 preoutcome static blocker

Starting HEAD: `{START}`. Prospective successor/static-gate checkpoint: `{CHECKPOINT}`.
Final HEAD and all remaining checkpoint HEADs are reported with the delivered GitHub commit; no file can contain its own commit hash.

Classification: `{CLASS}`. V3 is not ready for full synthetic execution.

V1 and V2 remain blocked at their separate historical exact scopes. Their blocker files, protocol V2, supersession authority, V6 selection, all V1/V2 code/results and the accepted inventory/support are byte-identical. V2 semantic identification remains PASS only within its declared partial-linear scope. No partial V2 stochastic result was opened or used.

## First frozen gate failed

The prospective inherited-law gate was committed before deterministic execution. It requires the historical C++ projection adapter to represent the canonical inherited current-clock projection/eligibility law. Six of 24 feature-only fixtures fail. At 23 targets and epsilon=1e-6, canonical scaled SVD accepts rank 3, with residual RMS {blocker['failed_gate']['concrete_witness']['canonical_residual_rms']:.17g}. Actual `clockfit` throws `projection orthogonality error`. The Gram determinant is above its cutoff. This demonstrates numerical normal-equation inversion non-equivalence; it does not demonstrate invalid market identification, FWER failure or low power.

The fixture reconstructs the same controls and raw D as synthetic one-bridge relations and calls the actual historical `clockfit`. It has no Y, RNG, bootstrap, price reader or network call. The historical C++ main is renamed and never called. The driver also compares the projection kernel to canonical Python SVD.

No repair was made after the first frozen gate failed. V1/V2 were not modified or reclassified. V3 stops at the authorized blocker boundary, before dual-layer specification and before Monte Carlo.

## Hashes and toolchain

Canonical estimand/nuisance design: `{bindings['research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json']}`.
Inherited geometry: `{blocker['geometry_sha256']}`.
Historical adapter (not a V3 worker): `{blocker['historical_adapter_sha256_not_a_V3_worker']}`.
V3 static gate plan: `{bindings['research_core_v4/triad_v3/INHERITED_SCIENCE_STATIC_GATE_PLAN_V1.json']}`.
Static raw evidence: `{bindings['research_core_v4/triad_v3/INHERITED_PROJECTION_STATIC_RAW_V1.json']}`.
Fixture harness: `{bindings['research_core_v4/triad_v3/projection_adapter_fixture_v1.cpp']}`.
V3 blocker: `{sha(blocker_path)}`.
Compiler: {raw['toolchain']['compiler']}; flags `-O3 -std=c++17 -Wall -Wextra`; no fast-math. Python {subprocess.check_output(['python','--version'],text=True).strip()}, NumPy {raw['toolchain']['numpy']}.
Fixture binary: `{raw['toolchain']['binary_sha256']}`.

## Required later components: not reached

The intended successor architecture is separate exact-path and complete joint daily-score dependence layers, both required. DAILY_AR025/DAILY_AR050 daily boundary, midnight/gap persistence, joint tensor, partial-null labels, common stability/breadth geometry, trial manifest and resumable execution have **not** been implemented or proven. No complete certification plan, V3 certification worker, trial-count derivation, master seeds, chunk law or manifest has been frozen. Their SHA256 values are absent, not passes. Serial/chunk equivalence and runtime benchmark were not performed. Readiness authority was not issued.

## Counters and boundaries

Full stochastic null cases=0; full stochastic power cases=0; Monte Carlo trials=0; real response openings=0; future real signed response computations=0; broker contacts=0; historical requests=0; new acquisition=0; candidate frozen count=0; orders=0. Confirmation CLOSED; protected forward CLOSED; live trading NOT_STARTED; Runtime V2 READ_ONLY; current_host_auth_ready=false. No reranking, depth selection or family closure.

## Remaining limitations

""" + "\n".join("- "+x for x in unresolved)+"\n"
(P / "FINAL_STATIC_BLOCKER_REPORT_V1.md").write_text(report)
print(json.dumps({"classification": CLASS, "blocker_sha256": sha(blocker_path), "static_failures": len(raw['failed_fixture_indices'])}))
