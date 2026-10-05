"""Prospective successor/inheritance freeze. No simulation or market reader."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
P = Path(__file__).parent
START = "342009ecc2f1944b289a7cd482935458323f5567"
MECHANISM = "TRIAD_RELATIONAL_STATE_V3_DAILY_DEPENDENCE_CERTIFICATION_SUCCESSOR"

def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

def write(name, obj):
    (P / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")

v1 = "research_core_v4/state/TRIAD_RELATIONAL_STATE_V1_PREOUTCOME_BLOCKER_V1.json"
v2 = "research_core_v4/state/TRIAD_RELATIONAL_STATE_V2_PREOUTCOME_BLOCKER_V1.json"
assert sha(v1) == "4095666954df6f34aaf8b4d1057a7e66a5b7126f093a18cef02abf108a8b9f9c"
assert sha(v2) == "085d8e010b4e02611e3e87797678cf093037b152ae06694cb70e6893b518647e"
base = json.loads((ROOT / "research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json").read_text())
# Read authoritative bindings, not partial stochastic progress or rejection counts.
bindings = dict(base["bindings"])
for name in ["TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json", "EXACT_SUPPORT_CERTIFICATION_PLAN_V1.json",
             "EXACT_SUPPORT_RAW_RESULT_V1.json", "EXACT_SUPPORT_INTERPRETATION_V1.json",
             "SEMANTIC_IDENTIFICATION_PLAN_V1.json", "SEMANTIC_RAW_RESULT_V1.json",
             "SEMANTIC_INTERPRETATION_V1.json", "EXACT_SYNTHETIC_GEOMETRY_BINDINGS_V1.json",
             "EXACT_SYNTHETIC_GEOMETRY_V1.txt", "exact_geometry_worker_v1.cpp"]:
    path = "research_core_v4/triad_v2/" + name
    bindings[path] = sha(path)
bindings[v1] = sha(v1)
bindings[v2] = sha(v2)
for path, expected in bindings.items():
    assert sha(path) == expected, path

write("SUCCESSOR_DECLARATION_V1.json", {
    "schema": "TRIAD_V3_PROSPECTIVE_SUCCESSOR_DECLARATION_V1", "starting_head": START,
    "mechanism_id": MECHANISM, "status": "DECLARED_INHERITANCE_GATES_PENDING_NOT_READY",
    "V1_classification": "PREOUTCOME_BLOCKED_INCREMENTAL_ESTIMAND_NOT_IDENTIFIED_UNTESTED_NOT_NULL",
    "V2_classification": "PREOUTCOME_BLOCKED_EXACT_DEPENDENCE_ENVELOPE_INCOMPLETE_CALIBRATION_UNCERTIFIED_UNTESTED_NOT_NULL",
    "historical_rescue": "FORBIDDEN", "V2_semantic_identification": "PASS_DECLARED_PARTIAL_LINEAR_SEMANTIC_IDENTIFICATION_ONLY",
    "relationship": "Separate prospective exact successor; V2 estimand/nuisance/support unchanged by hash. Only dual-layer exact-path plus daily-score dependence envelope and its implementation may change.",
    "bindings": bindings,
    "stop_on_first_frozen_static_gate_failure": True,
    "no_scientific_claim_from_static_proof": True,
    "partial_V2_stochastic_counts": "NON_EVIDENCE_NOT_READ_OR_USED",
    "authorized_next_steps": ["inheritance equivalence", "dual-layer law", "worker", "deterministic invariants", "trial manifest freeze", "ready authority"],
    "prohibited": ["V1 or V2 modification", "Monte Carlo", "real signed response", "broker", "acquisition", "reranking", "depth selection", "confirmation", "protected forward", "trading"],
    "scope_limits": {
        "population": "retained complete-clock population; informative future-path censoring not certified",
        "latency": "t-10 research availability convention; historical reception latency unobserved; not live latency proof",
        "candidate_frozen_count": 0, "current_host_auth_ready": False,
        "Runtime_V2": "READ_ONLY", "confirmation": "CLOSED", "protected_forward": "CLOSED"
    }
})
write("INHERITED_SCIENCE_STATIC_GATE_PLAN_V1.json", {
    "schema": "TRIAD_V3_INHERITED_SCIENCE_STATIC_GATE_PLAN_V1", "mechanism_id": MECHANISM,
    "starting_head": START, "status": "FROZEN_BEFORE_DETERMINISTIC_EXECUTION",
    "bindings": bindings,
    "gate": "CURRENT_CLOCK_PROJECTION_AND_NUMERICAL_SUPPORT_MATCH_INHERITED_CANONICAL_LAW",
    "canonical_implementation": "research_core_v4/triad_v2/orthogonal_score_v2.py:current_projection",
    "candidate_adapter": "research_core_v4/triad_v2/exact_geometry_worker_v1.cpp:clockfit/inv3",
    "reason": "Hash identity of the source files alone cannot prove the numerical adapter represents the inherited current-clock law. Eligibility must match, not merely agree on well-conditioned examples.",
    "fixtures": {
        "target_counts": [5, 10, 11, 23],
        "near_collinearity_epsilon": [1.0, 0.01, 0.0001, 0.000001, 0.0000001, 0.00000001],
        "construction": "i=1..n; X=[1,sin(i*sqrt(2)),sin(i*sqrt(2))+epsilon*cos(i*sqrt(3))]; D=sin(i*sqrt(5)); positive fixed target scales=1. Deterministic feature/control fixtures, no Y.",
        "use": "Projection/support invariants only; not synthetic FWER, power, market data or parameter selection"
    },
    "pass_rule": "Every fixture accepted by canonical current_projection must be accepted by adapter; accepted normalized residuals agree within 1e-7 absolute. Any failure blocks V3 without repair in this task.",
    "failure_classification": "PREOUTCOME_BLOCKED_INHERITED_CURRENT_PROJECTION_ADAPTER_NOT_EQUIVALENT_UNCERTIFIED_UNTESTED_NOT_NULL",
    "after_failure": "Persist exact raw discrepancy and V3 blocker; no envelope/worker/manifest readiness claim, no successor V4, no reranking, no Monte Carlo.",
    "Monte_Carlo_trials": 0
})
