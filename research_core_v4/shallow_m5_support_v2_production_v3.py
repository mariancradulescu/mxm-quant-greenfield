"""Final V3 prearm authority gate for BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2.

V3 changes only the ARM authorization surface. The accepted V2 execution engine remains
byte-exact and is delegated to after machine validation of the accepted real GitHub
provider preflight result and its independent acceptance authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from research_core_v4 import shallow_m5_support_v2_production_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
REPO = v2.REPO
BRANCH = v2.BRANCH

ARM_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V3.json"
RUNNER_REL = "research_core_v4/shallow_m5_support_v2_production_v3.py"
WORKFLOW_REL = ".github/workflows/breadth-first-shallow-m5-support-v2-production-v3.yml"
ARCH_FREEZE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_MACHINE_SIDE_PRODUCTION_ARCHITECTURE_FREEZE_V3.json"
PROVIDER_RESULT_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_GITHUB_PROVIDER_PREFLIGHT_RESULT_V1.json"
PROVIDER_ACCEPTANCE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PROVIDER_PREFLIGHT_ACCEPTANCE_AUTHORITY_V1.json"

V2_ARCHITECTURE_SHA256 = "ca19f43ebd3e8e5d1de4b87226a4820ccc58616e2e18fe0e46721800c8db0230"
V2_RUNNER_SHA256 = "a1aa8ba8bd104639c2758bf4bc14096565e41c897bceda2d343e0ba68c840de7"
V2_WORKFLOW_SHA256 = "208b26c10b0b3f5750512d126b4fa5a33ffbaa4c085985a64c7ca23a0706e7af"
V2_OUTPUT_TRANSPORT_SHA256 = "90cad3fad2fa92951c2257f74011dd980b4f95b3801614a2ff2f89881b8c0ea2"
PROVIDER_RESULT_SHA256 = "58aba6b981e427e60e7e20550206c1de183a0f5e49ef59809735cb6baddc3153"
PROVIDER_ACCEPTANCE_SHA256 = "c20a86896d839ad54b3c66597d797291d8244fd358555e692f20bbcf6170a00e"

PROVIDER_RUN_ID = 37495439491
PROVIDER_JOB_ID = 112378654896
PROVIDER_TESTED_HEAD = "69b08f0258c17ec414c15c59ee2bf2db9066e7f6"
PROVIDER_STATUS = "PROVEN_MACHINE_SIDE_GITHUB_PROVIDER_PATH_SYNTHETIC_ONLY_NOT_ARMED"
PROVIDER_RESULT_SCHEMA = "mxm.v4.shallow-m5-v2.github-provider-preflight-result.v1"
PROVIDER_ACCEPTANCE_SCHEMA = "mxm.v4.breadth-first-shallow-m5-support-v2.provider-preflight-acceptance-authority.v1"
ARM_SCHEMA = "mxm.v4.breadth-first-shallow-m5-support-v2.production-arm.v3"

HEX64 = frozenset("0123456789abcdef")

CaptureError = v2.CaptureError
SystemicFailure = v2.SystemicFailure
SoftStop = v2.SoftStop


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise PermissionError("PREARM_PROVIDER_AUTHORITY_BINDING_FAILURE")
    return value


def _require(condition: bool) -> None:
    if not condition:
        raise PermissionError("PREARM_PROVIDER_AUTHORITY_BINDING_FAILURE")


def validate_provider_authority(
    result_path: Path | None = None,
    acceptance_path: Path | None = None,
) -> dict:
    result_path = result_path or ROOT / PROVIDER_RESULT_REL
    acceptance_path = acceptance_path or ROOT / PROVIDER_ACCEPTANCE_REL
    _require(result_path.is_file() and acceptance_path.is_file())
    _require(sha256_file(result_path) == PROVIDER_RESULT_SHA256)
    _require(sha256_file(acceptance_path) == PROVIDER_ACCEPTANCE_SHA256)

    result = load_json(result_path)
    _require(result.get("schema") == PROVIDER_RESULT_SCHEMA)
    _require(result.get("status") == PROVIDER_STATUS)
    _require(result.get("run_id") == PROVIDER_RUN_ID)
    _require(result.get("job_id") == PROVIDER_JOB_ID)
    _require(result.get("exact_tested_head") == PROVIDER_TESTED_HEAD)
    encrypted = result.get("encrypted_asset_sha256")
    redownload = result.get("redownload_sha256")
    _require(encrypted == redownload == "857398ed14349c1ff5dc0a0b2fd7d12214d24388f0b8f40ad6c1d4cf9dd66cec")
    _require(result.get("manifest_roundtrip_status") == "PASS")
    _require(result.get("recovery_skip_status") == "SKIP_WITHOUT_BROKER_REQUERY")
    _require(result.get("conflict_fail_closed_status") == "PASS_DURABLE_STORAGE_INTEGRITY_FAILURE")
    _require(result.get("branch_drift_guard_status") == "PASS_ALLOWED_SYNTHETIC_MANIFEST_PATH_ONLY")
    _require(isinstance(result.get("cleanup_release_status"), str) and result["cleanup_release_status"].startswith("PASS"))
    _require(result.get("cleanup_tag_status") == "PASS")
    _require(isinstance(result.get("cleanup_branch_status"), str) and result["cleanup_branch_status"].startswith("PASS"))
    _require(result.get("residual_release_count") == 0)
    _require(result.get("residual_scratch_branch_count") == 0)
    _require(result.get("ctrader_secret_injection_count") == 0)
    _require(result.get("broker_contact_count") == 0)
    _require(result.get("historical_request_count") == 0)
    _require(result.get("market_data_row_count") == 0)

    acceptance = load_json(acceptance_path)
    _require(acceptance.get("schema") == PROVIDER_ACCEPTANCE_SCHEMA)
    _require(acceptance.get("status") == PROVIDER_STATUS)
    proof = acceptance.get("successor_exact_head_validation_and_provider_preflight")
    _require(isinstance(proof, dict))
    _require(proof.get("provider_result_sha256") == PROVIDER_RESULT_SHA256)
    _require(proof.get("run_id") == PROVIDER_RUN_ID)
    _require(proof.get("job_id") == PROVIDER_JOB_ID)
    _require(proof.get("tested_head") == PROVIDER_TESTED_HEAD)
    cleanup = acceptance.get("cleanup_independent_reconciliation")
    _require(isinstance(cleanup, dict) and cleanup.get("cleanup_accepted") is True)

    return {"result": result, "acceptance": acceptance}


def execution_path_equivalence_proof() -> dict:
    _require(sha256_file(ROOT / v2.RUNNER_REL) == V2_RUNNER_SHA256)
    _require(sha256_file(ROOT / v2.WORKFLOW_REL) == V2_WORKFLOW_SHA256)
    _require(sha256_file(ROOT / v2.ARCH_FREEZE_REL) == V2_ARCHITECTURE_SHA256)
    _require(sha256_file(ROOT / v2.OUTPUT_AUTH_REL) == V2_OUTPUT_TRANSPORT_SHA256)
    keys = (
        "SAME_MASTER1576_HASH",
        "SAME_DIGITS_MAP_HASH",
        "SAME_PROTOCOL_DECODER_HASH",
        "SAME_ACCOUNT_FINGERPRINT",
        "SAME_FOUR_SEGMENTS",
        "SAME_M5_REQUEST_BUILDER",
        "SAME_RAW_ENVELOPE_RESPONSE_BINDING",
        "SAME_HASMORE_LAW",
        "SAME_PAGE_CAP_3",
        "SAME_RETRY_CAP_2_AFTER_INITIAL",
        "SAME_4RPS_LIMIT",
        "SAME_HEARTBEAT_LAW",
        "SAME_IDENTITY_CAPTURE_LOOP",
        "SAME_SHARD_PLAINTEXT_SERIALIZATION",
        "SAME_RSA_OPENPGP_ENCRYPTION_PATH",
        "SAME_RELEASE_PROVIDER_PATH",
        "SAME_STRICT_MANIFEST_VALIDATION",
        "SAME_ALL25_PREVIOUS_SEGMENT_ASSET_GATE",
        "SAME_BRANCH_DRIFT_GUARD",
        "SAME_RECOVERY_SEMANTICS",
    )
    return {
        "delegated_execution_runner_ref": v2.RUNNER_REL,
        "delegated_execution_runner_sha256": V2_RUNNER_SHA256,
        "proof": {key: True for key in keys},
    }


def _expected_arm_bindings() -> dict:
    bindings = dict(v2._expected_arm_bindings())
    bindings.update(
        {
            "PROVIDER_PREFLIGHT_RESULT_SHA256": PROVIDER_RESULT_SHA256,
            "PROVIDER_PREFLIGHT_ACCEPTANCE_AUTHORITY_SHA256": PROVIDER_ACCEPTANCE_SHA256,
            "V3_GATE_RUNNER_SHA256": sha256_file(ROOT / RUNNER_REL),
            "V3_GATE_WORKFLOW_SHA256": sha256_file(ROOT / WORKFLOW_REL),
            "V3_GATE_ARCHITECTURE_FREEZE_SHA256": sha256_file(ROOT / ARCH_FREEZE_REL),
        }
    )
    return bindings


def validate_arm(arm_path: Path = ROOT / ARM_REL) -> dict:
    validate_provider_authority()
    execution_path_equivalence_proof()
    if not arm_path.is_file():
        raise PermissionError("PRODUCTION_ARM_V3_ABSENT")
    arm = load_json(arm_path)
    expected_keys = {"schema", "status", "exact_source_head", "durable_release_identity", "bindings"}
    if set(arm) != expected_keys:
        raise PermissionError("ARM_V3_UNKNOWN_OR_MISSING_FIELDS")
    if arm.get("schema") != ARM_SCHEMA:
        raise PermissionError("WRONG_ARM_V3_SCHEMA")
    if arm.get("status") != "ARMED_NOT_EXECUTED":
        raise PermissionError("WRONG_ARM_V3_STATUS")
    source = arm.get("exact_source_head")
    if not isinstance(source, str) or len(source) != 40 or any(c not in HEX64 for c in source):
        raise PermissionError("INVALID_EXACT_SOURCE_HEAD")
    if arm.get("durable_release_identity") != v2.derive_release_identity(source):
        raise PermissionError("NONDETERMINISTIC_OR_WRONG_RELEASE_IDENTITY")
    if arm.get("bindings") != _expected_arm_bindings():
        raise PermissionError("ARM_V3_HASH_OR_PLAN_BINDING_MISMATCH")
    return arm


def validate_arm_git_event(arm: Mapping[str, Any]) -> str:
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if os.environ.get("GITHUB_SHA") and os.environ["GITHUB_SHA"] != head:
        raise PermissionError("GITHUB_SHA_MISMATCH")
    parents = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-list", "--parents", "-n", "1", "HEAD"], text=True
    ).split()
    if len(parents) != 2 or parents[1] != arm.get("exact_source_head"):
        raise PermissionError("ARM_PARENT_MISMATCH")
    changed = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        text=True,
    ).splitlines()
    if changed != [ARM_REL]:
        raise PermissionError("ARM_V3_COMMIT_MUST_CHANGE_ONLY_EXACT_ARM_FILE")
    return head


def production_plan() -> dict:
    plan = dict(v2.production_plan())
    plan.update(
        {
            "architecture_version": 3,
            "authorization_surface_only_successor": True,
            "provider_result_machine_bound": True,
            "provider_acceptance_machine_bound": True,
            "delegated_execution_runner_sha256": V2_RUNNER_SHA256,
            "workflow_dispatch": False,
        }
    )
    return plan


def run_segment(segment: int, *, workdir: Path) -> dict:
    validate_provider_authority()
    execution_path_equivalence_proof()
    original_validate_arm = v2.validate_arm
    original_validate_arm_git_event = v2.validate_arm_git_event
    try:
        v2.validate_arm = validate_arm
        v2.validate_arm_git_event = validate_arm_git_event
        return v2.run_segment(segment, workdir=workdir)
    finally:
        v2.validate_arm = original_validate_arm
        v2.validate_arm_git_event = original_validate_arm_git_event


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    sub.add_parser("validate-arm")
    sub.add_parser("prove-equivalence")
    rs = sub.add_parser("run-segment")
    rs.add_argument("--segment", type=int, choices=[1, 2, 3, 4], required=True)
    rs.add_argument("--workdir", type=Path, required=True)
    args = ap.parse_args()

    if args.command == "plan":
        print(json.dumps(production_plan(), sort_keys=True))
        return 0
    if args.command == "prove-equivalence":
        print(json.dumps(execution_path_equivalence_proof(), sort_keys=True))
        return 0
    if args.command == "validate-arm":
        arm = validate_arm()
        arm_commit = validate_arm_git_event(arm)
        v2.validate_static_bindings()
        campaign = v2.campaign_from_arm(arm, arm_commit)
        store = v2.GitHubReleaseStoreV2(
            tag=campaign["DURABLE_RELEASE_IDENTITY"],
            campaign=campaign,
            branch_name=BRANCH,
            base_commit=arm_commit,
        )
        store.verify_branch()
        print(json.dumps({"status": "PASS_ARM_V3_PROVIDER_AUTHORITY_AND_V2_EXECUTION_BINDINGS"}, sort_keys=True))
        return 0
    try:
        result = run_segment(args.segment, workdir=args.workdir)
        print(json.dumps(result, sort_keys=True))
        return 0
    except SoftStop as exc:
        print(json.dumps({"status": "SOFT_STOP_INCOMPLETE_RECOVER_FROM_DURABLE_SHARDS", "detail": str(exc)}, sort_keys=True))
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
