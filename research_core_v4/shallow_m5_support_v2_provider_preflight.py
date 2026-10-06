"""Disposable real-GitHub provider preflight for shallow M5 V2 production V2.

Uses only synthetic non-market bytes and GITHUB_TOKEN. It creates a temporary
release/tag and scratch branch, proves release upload/download plus Contents API
manifest roundtrip and recovery semantics, then removes every disposable resource.
No cTrader request code is invoked.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from research_core_v4 import shallow_m5_support_v2_production_v2 as p

ROOT = p.ROOT
REPO = p.REPO
FORBIDDEN_SECRET_ENV = (
    "CTRADER_CLIENT_ID",
    "CTRADER_CLIENT_SECRET",
    "CTRADER_ACCESS_TOKEN",
    "CTRADER_REFRESH_TOKEN",
    "MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM",
)


def gh(args, *, check=True):
    return subprocess.run(
        ["gh", *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _job_id(run_id: int) -> int:
    run = gh(["api", "--method", "GET", f"repos/{REPO}/actions/runs/{run_id}/jobs"], check=False)
    if run.returncode != 0:
        return 0
    try:
        jobs = json.loads(run.stdout).get("jobs", [])
    except Exception:
        return 0
    matches = [x for x in jobs if x.get("name") == "provider-synthetic"]
    if len(matches) != 1:
        return 0
    try:
        return int(matches[0]["id"])
    except Exception:
        return 0


def _resource_absent_release(tag: str) -> bool:
    r = gh(["api", "--method", "GET", f"repos/{REPO}/releases/tags/{tag}"], check=False)
    return r.returncode != 0 and ("404" in r.stderr or "Not Found" in r.stderr)


def _resource_absent_tag(tag: str) -> bool:
    r = gh(["api", "--method", "GET", f"repos/{REPO}/git/ref/tags/{tag}"], check=False)
    return r.returncode != 0 and ("404" in r.stderr or "Not Found" in r.stderr)


def _resource_absent_branch(branch: str) -> bool:
    r = gh(["api", "--method", "GET", f"repos/{REPO}/git/ref/heads/{branch}"], check=False)
    return r.returncode != 0 and ("404" in r.stderr or "Not Found" in r.stderr)


def _delete_release(tag: str) -> bool:
    r = gh(["release", "delete", tag, "--repo", REPO, "--cleanup-tag", "--yes"], check=False)
    return r.returncode == 0 or _resource_absent_release(tag)


def _delete_branch(branch: str) -> bool:
    r = gh(["api", "--method", "DELETE", f"repos/{REPO}/git/refs/heads/{branch}"], check=False)
    return r.returncode == 0 or _resource_absent_branch(branch)


def synthetic_campaign(tested_head: str, tag: str) -> dict:
    return {
        "MASTER_SHA256": p.MASTER_SHA256,
        "ACCOUNT_FINGERPRINT_SHA256": p.ACCOUNT_FINGERPRINT_SHA256,
        "PROTOCOL_FREEZE_SHA256": p.PROTOCOL_FREEZE_SHA256,
        "DIGITS_MAP_SHA256": p.DIGITS_MAP_FILE_SHA256,
        "SOURCE_HEAD": tested_head,
        "ARM_COMMIT": tested_head,
        "DURABLE_RELEASE_IDENTITY": tag,
    }


def synthetic_entry(campaign: dict, encrypted_sha: str, plaintext_sha: str) -> dict:
    return {
        **campaign,
        "SEGMENT_INDEX": 1,
        "SHARD_INDEX": 0,
        "IDENTITY_RANGE": [1, 64],
        "ENCRYPTED_ASSET_NAME": p.shard_asset_name(1, 0),
        "ENCRYPTED_ASSET_SHA256": encrypted_sha,
        "PLAINTEXT_CANONICAL_SHA256": plaintext_sha,
        "ROW_COUNT": 0,
        "FIRST_TIMESTAMP": None,
        "LAST_TIMESTAMP": None,
        "REQUEST_COUNT": 0,
        "RETRY_COUNT": 0,
        "PAGE_CAP_HITS": 0,
        "FAILURE_LEDGER": {},
        "PROTECTED_FORWARD_ROW_COUNT": 0,
    }


def run_preflight(output: Path) -> dict:
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    tested_head = os.environ.get("GITHUB_SHA", "")
    secret_count = sum(1 for name in FORBIDDEN_SECRET_ENV if os.environ.get(name))
    if secret_count:
        raise RuntimeError("forbidden cTrader/private-key secret injection")
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("GITHUB_TOKEN required")
    if len(tested_head) != 40:
        raise RuntimeError("exact tested head required")

    arch_sha = p.campaign_architecture_sha256()
    token = hashlib.sha256(
        f"{tested_head}|{run_id}|{arch_sha}|provider-preflight-v2".encode("ascii")
    ).hexdigest()
    tag = f"mxm-shallow-m5-v2-provider-preflight-{run_id}-{token[:16]}"
    scratch = f"mxm-shallow-m5-v2-provider-preflight-{run_id}-{token[16:32]}"
    manifest_rel = p.segment_manifest_rel(1)
    asset_name = p.shard_asset_name(1, 0)

    result: dict[str, Any] = {
        "schema": "mxm.v4.shallow-m5-v2.github-provider-preflight-result.v1",
        "status": "PREARM_INFRASTRUCTURE_BLOCKED",
        "run_id": run_id,
        "job_id": _job_id(run_id),
        "exact_tested_head": tested_head,
        "temporary_release_identity": tag,
        "temporary_scratch_branch": scratch,
        "architecture_freeze_sha256": arch_sha,
        "encrypted_asset_sha256": None,
        "redownload_sha256": None,
        "manifest_roundtrip_status": "NOT_RUN",
        "recovery_skip_status": "NOT_RUN",
        "conflict_fail_closed_status": "NOT_RUN",
        "branch_drift_guard_status": "NOT_RUN",
        "cleanup_release_status": "NOT_RUN",
        "cleanup_tag_status": "NOT_RUN",
        "cleanup_branch_status": "NOT_RUN",
        "residual_release_count": None,
        "residual_scratch_branch_count": None,
        "ctrader_secret_injection_count": secret_count,
        "broker_contact_count": 0,
        "historical_request_count": 0,
        "market_data_row_count": 0,
    }
    release_created = False
    branch_created = False
    primary_error = None

    try:
        create_branch = gh(
            [
                "api", "--method", "POST", f"repos/{REPO}/git/refs",
                "-f", f"ref=refs/heads/{scratch}",
                "-f", f"sha={tested_head}",
            ],
            check=False,
        )
        if create_branch.returncode != 0:
            raise RuntimeError("scratch branch creation failed")
        branch_created = True

        campaign = synthetic_campaign(tested_head, tag)
        store = p.GitHubReleaseStoreV2(
            tag=tag,
            campaign=campaign,
            branch_name=scratch,
            base_commit=tested_head,
            allowed_paths=frozenset({manifest_rel}),
        )
        self_head = store.verify_branch()
        if self_head != tested_head:
            raise RuntimeError("scratch branch did not start at exact tested head")

        store.ensure_release(create_allowed=True)
        release_created = True

        payload = p.canonical_json_bytes(
            {
                "schema": "mxm.v4.shallow-m5-v2.provider-preflight.synthetic-shard.v1",
                "synthetic": True,
                "contains_real_market_rows": False,
                "contains_real_account_id": False,
                "contains_token_material": False,
                "run_id": run_id,
                "tested_head": tested_head,
            }
        ) + b"\n"

        with tempfile.TemporaryDirectory(prefix="mxm-provider-preflight-") as td:
            td = Path(td)
            package = td / asset_name
            enc = p.encrypt_shard(payload, public_key=ROOT / p.PUBLIC_KEY_REL, output=package)
            result["encrypted_asset_sha256"] = enc["encrypted_asset_sha256"]
            entry = synthetic_entry(campaign, enc["encrypted_asset_sha256"], enc["plaintext_sha256"])
            p.validate_manifest_entry(entry, campaign=campaign, segment=1)
            store.publish_shard(1, 0, package, entry)

            with tempfile.TemporaryDirectory(prefix="mxm-provider-redownload-") as rd:
                downloaded = store._download_asset(asset_name, Path(rd))
                redownload_sha = p.sha256_file(downloaded)
            result["redownload_sha256"] = redownload_sha
            if redownload_sha != enc["encrypted_asset_sha256"]:
                raise RuntimeError("encrypted asset redownload hash mismatch")

        roundtrip = store.load_segment_manifest(1, require_complete=False)
        if roundtrip["entries"] != [entry] or roundtrip["status"] != "PARTIAL":
            raise RuntimeError("manifest roundtrip mismatch")
        result["manifest_roundtrip_status"] = "PASS"

        recovered = store.recoverable_entry(1, 0, [1, 64])
        if recovered != entry:
            raise RuntimeError("recovery skip lookup mismatch")
        result["recovery_skip_status"] = "SKIP_WITHOUT_BROKER_REQUERY"

        bad = copy.deepcopy(entry)
        bad["ENCRYPTED_ASSET_SHA256"] = "0" * 64
        try:
            store.verify_entry_asset(bad)
        except p.SystemicFailure:
            result["conflict_fail_closed_status"] = "PASS_DURABLE_STORAGE_INTEGRITY_FAILURE"
        else:
            raise RuntimeError("hash conflict did not fail closed")

        store.verify_branch()
        result["branch_drift_guard_status"] = "PASS_ALLOWED_SYNTHETIC_MANIFEST_PATH_ONLY"
        result["status"] = "PROVIDER_PATH_PASS_PENDING_CLEANUP"
    except Exception as exc:
        primary_error = f"{type(exc).__name__}: {exc}"
        result["primary_error"] = primary_error
    finally:
        if release_created or not _resource_absent_release(tag):
            result["cleanup_release_status"] = "PASS" if _delete_release(tag) else "FAIL"
        else:
            result["cleanup_release_status"] = "PASS_NOT_PRESENT"
        result["cleanup_tag_status"] = "PASS" if _resource_absent_tag(tag) else "FAIL"

        if branch_created or not _resource_absent_branch(scratch):
            result["cleanup_branch_status"] = "PASS" if _delete_branch(scratch) else "FAIL"
        else:
            result["cleanup_branch_status"] = "PASS_NOT_PRESENT"

        release_absent = _resource_absent_release(tag)
        tag_absent = _resource_absent_tag(tag)
        branch_absent = _resource_absent_branch(scratch)
        result["residual_release_count"] = 0 if release_absent and tag_absent else 1
        result["residual_scratch_branch_count"] = 0 if branch_absent else 1

        cleanup_ok = (
            result["residual_release_count"] == 0
            and result["residual_scratch_branch_count"] == 0
            and result["cleanup_release_status"].startswith("PASS")
            and result["cleanup_tag_status"] == "PASS"
            and result["cleanup_branch_status"].startswith("PASS")
        )
        functional_ok = all(
            (
                result["encrypted_asset_sha256"],
                result["redownload_sha256"],
                result["encrypted_asset_sha256"] == result["redownload_sha256"],
                result["manifest_roundtrip_status"] == "PASS",
                result["recovery_skip_status"] == "SKIP_WITHOUT_BROKER_REQUERY",
                result["conflict_fail_closed_status"] == "PASS_DURABLE_STORAGE_INTEGRITY_FAILURE",
                result["branch_drift_guard_status"] == "PASS_ALLOWED_SYNTHETIC_MANIFEST_PATH_ONLY",
                result["ctrader_secret_injection_count"] == 0,
                result["broker_contact_count"] == 0,
                result["historical_request_count"] == 0,
                result["market_data_row_count"] == 0,
            )
        )
        if functional_ok and cleanup_ok and primary_error is None:
            result["status"] = "PROVEN_MACHINE_SIDE_GITHUB_PROVIDER_PATH_SYNTHETIC_ONLY_NOT_ARMED"
        else:
            result["status"] = "PREARM_INFRASTRUCTURE_BLOCKED"

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(p.canonical_json_bytes(result) + b"\n")

    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = run_preflight(args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PROVEN_MACHINE_SIDE_GITHUB_PROVIDER_PATH_SYNTHETIC_ONLY_NOT_ARMED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
