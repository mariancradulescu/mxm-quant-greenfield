from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research_core_v4.crash_recovery_control_v1 import validate_current_control_plane as validate_v1

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "research_core_v4/state/V4_STATE.json"
AUTH2 = ROOT / "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V2.json"

EXPECTED_HISTORY_BLOBS = {
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_OPENING_LOCK_V1.txt": "1e75c3a2e9aeaf6099e57545ad9fb62ca3311445",
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_OPENING_INTERRUPTION_V1.json": "f0d94c13d14a61be297d401b63d62cd4d9f2ac4d",
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V1.json": "174555058661b6cc03d9e1a30e95aaa7a79586da",
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_LOCK_V1.txt": "b6b189b17e8af8f06e2d5cd3ef11dda9069ede89",
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_ATTEMPT_V1.json": "e71021da081f400f20f5d7278526ccd1a06086ca",
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_EXECUTION_OPENING_LOCK_V1.txt": "1e75c3a2e9aeaf6099e57545ad9fb62ca3311445",
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_FAILURE_V1.json": "911811af014c2179cf3289245530569b8e419f0d",
}

EXPECTED_AUDIT_BLOBS = {
    "research_core_v4/state/V4_RECOVERY_V2_INDEPENDENT_GOVERNANCE_AUDIT_V1.json": "b9c62c8be53a7ab0e13c2b6aea8ed91501b8283a",
    "research_core_v4/state/V4_EXECUTION_RUNTIME_PROFILE_AUDIT_V1.json": "8a1a925976e3fb4692e5b35c91bd6ec3a6ac738c",
    "research_core_v4/state/V4_EXECUTION_SURFACE_DECISION_V1.json": "9b6f03d7f13eb2dcb9bea3a46a4323443d13b4d3",
    "research_core_v4/state/V4_PRIVATE_INPUT_TRANSPORT_DECISION_V1.json": "b0571e7da70745d8996374828c888b7add95f053",
    "research_core_v4/state/V4_EXACT_SOURCE_EXECUTION_EQUIVALENCE_CONTRACT_V1.json": "21b08b284041380fbc2c6058c407ecc01a519b9d",
    "research_core_v4/runtime/v4_recovery_v2_private_runtime_template.yml": "c700cba0acd1d963d83a42fdb970342b32009b2d",
}

SCIENCE_SHA256 = {
    "research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json": "3f9a6b1da92b9904da91e86d005f26e8e99d93e5e3497e1b8a72b59b1d4e590e",
    "research_core_v4/response_evaluator_v3.py": "bb846fb3bbbe567c53587a6c22b344ffe39af7129db5e9a4a39c77026f3ade2a",
    "research_core_v4/development_execution_runner_v1.py": "cebcf2ad4f88e40d575cb46ffc14e0862107b47a84260a15b3310f075af4f79d",
    "research_core_v4/frozen_v2_semantics.py": "0a7bda1afe5cbe79373ee833e9d09febc08721d1826d94435f74d900f74f26ed",
}

RESULT_CANDIDATES = (
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json",
    "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json.tmp",
    "V4_FIRST_DEVELOPMENT_RESPONSE_RESULT_V1.json",
    "V4_FIRST_DEVELOPMENT_RESPONSE_RESULT_V1.json.tmp",
)
ARM = ROOT / "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V2_ARM_V1.json"
STAGING = ROOT / "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_RECOVERY_V2_PRIVATE_INPUT_STAGING_CERTIFICATE_V1.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def require(condition: bool, message: str):
    if not condition:
        raise PermissionError("RECOVERY_V2_CONTROL_FAIL " + message)


def validate_recovery_v2_prepared() -> dict:
    v1 = validate_v1()
    require(v1["phase"] == "FIRST_REAL_MARKET_DESIGN_V2_CRASH_RECOVERY_SECOND_INFRASTRUCTURE_FAILURE_STOPPED", "V1 history phase changed")

    state = load(STATE)
    auth = load(AUTH2)
    prep = state.get("recovery_v2_preparation", {})

    for rel, expected in EXPECTED_HISTORY_BLOBS.items():
        require(git_blob_sha1(ROOT / rel) == expected, f"historical bytes changed: {rel}")
    for rel, expected in EXPECTED_AUDIT_BLOBS.items():
        require(git_blob_sha1(ROOT / rel) == expected, f"audit bytes changed: {rel}")
    for rel, expected in SCIENCE_SHA256.items():
        require(sha256(ROOT / rel) == expected, f"frozen science changed: {rel}")

    require(git_blob_sha1(AUTH2) == "e293affbea4c6d3e96b671d8914d0ec8fbe750e8", "Authority V2 bytes changed")
    require(auth["status"] == "PREPARED_NOT_ARMED_PRIVATE_INPUT_STAGING_UNSATISFIED", "Authority V2 status")
    require(auth["scientific_recovery_justified"] is True, "scientific recovery not justified")
    require(auth["real_development_response_execution_authorized"] is False, "real execution prematurely authorized")
    require(auth["arm_authorized"] is False, "arm prematurely authorized")
    require(auth["accepted_canonical_result_limit"] == 1, "accepted result limit changed")
    require(auth["accepted_canonical_result_count_at_prepare"] == 0, "accepted result count not zero")
    require(auth["future_arm"]["process_attempt_limit_after_arm"] == 1, "V2 process attempt limit changed")
    require(auth["future_arm"]["automatic_retry"] is False, "automatic retry enabled")
    require(auth["input_transport"]["private_staging_certificate_present_at_prepare"] is False, "staging certificate claimed present")

    require(prep.get("status") == "PREPARED_NOT_ARMED_PRIVATE_INPUT_STAGING_UNSATISFIED", "state V2 preparation status")
    require(prep.get("real_execution_authorized") is False, "state real execution prematurely authorized")
    require(prep.get("arm_present") is False, "state arm present")
    require(prep.get("private_input_staging_certificate_present") is False, "state staging present")
    require(prep.get("accepted_canonical_result_count") == 0, "state accepted result count")
    require(prep.get("process_attempts_started") == 0, "V2 process already started")
    require(prep.get("private_runtime_repository") == "mariancradulescu/mxm-quant-director", "private runtime repository changed")

    require(not ARM.exists(), "V2 ARM exists during audit stop boundary")
    require(not STAGING.exists(), "private input staging certificate exists unexpectedly")
    present_results = [p for p in RESULT_CANDIDATES if (ROOT / p).exists()]
    require(not present_results, f"canonical or temporary result exists: {present_results}")

    require(state["first_wave"]["development_result_interpreted"] is False, "development result interpreted")
    require(state["first_wave"]["confirmation_execution_authorized"] is False, "confirmation authorized")
    require(state["governance"]["broker_acquisition_authorized"] is False, "broker acquisition authorized")
    require(state["governance"]["protected_forward_opened"] is False, "protected forward opened")
    require(state["governance"]["live_trading_started"] is False, "live trading started")

    return {
        "schema": "mxm.research-core-v4.recovery-v2-control-validation.v1",
        "status": "PASS_PREPARED_NOT_ARMED_NO_REAL_RESPONSE_EXECUTION",
        "v1_history_status": v1["phase"],
        "accepted_canonical_result_count": 0,
        "accepted_canonical_result_limit": 1,
        "private_input_staging_satisfied": False,
        "arm_present": False,
        "real_execution_authorized": False,
        "process_attempts_started": 0,
        "scientific_source_unchanged": True,
        "historical_locks_unchanged": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate_recovery_v2_prepared(), sort_keys=True))
