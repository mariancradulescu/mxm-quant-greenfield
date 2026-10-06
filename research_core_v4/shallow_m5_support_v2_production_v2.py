"""Production architecture V2 for BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2.

V2 preserves the accepted V1 capture science and protocol decoder while hardening:
- strict durable segment manifest bindings,
- deterministic release identity,
- exact previous-segment asset verification before broker authentication,
- campaign branch drift protection,
- same-ARM governed GitHub Actions rerun recovery.

This module creates no ARM and performs no broker contact unless a separately-created
hash-bound V2 ARM is the exact triggering commit.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from research_core_v4 import shallow_m5_support_v2 as decoder
from research_core_v4 import shallow_m5_support_v2_production as v1

ROOT = Path(__file__).resolve().parents[1]
REPO = v1.REPO
BRANCH = v1.BRANCH

ARM_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V2.json"
RUNNER_REL = "research_core_v4/shallow_m5_support_v2_production_v2.py"
WORKFLOW_REL = ".github/workflows/breadth-first-shallow-m5-support-v2-production-v2.yml"
ARCH_FREEZE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_MACHINE_SIDE_PRODUCTION_ARCHITECTURE_FREEZE_V2.json"
ACCEPTANCE_REL = v1.ACCEPTANCE_REL
OUTPUT_AUTH_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_OUTPUT_TRANSPORT_AUTHORITY_V2.json"
PROTOCOL_FREEZE_REL = v1.PROTOCOL_FREEZE_REL
DIGITS_MAP_REL = v1.DIGITS_MAP_REL
PUBLIC_KEY_REL = v1.PUBLIC_KEY_REL

PROTOCOL_FREEZE_SHA256 = v1.PROTOCOL_FREEZE_SHA256
V2_IMPLEMENTATION_SHA256 = v1.V2_IMPLEMENTATION_SHA256
DIGITS_MAP_FILE_SHA256 = v1.DIGITS_MAP_FILE_SHA256
CANONICAL_DIGITS_MAP_SHA256 = v1.CANONICAL_DIGITS_MAP_SHA256
MASTER_SHA256 = v1.MASTER_SHA256
ACCOUNT_FINGERPRINT_SHA256 = v1.ACCOUNT_FINGERPRINT_SHA256
PUBLIC_SPKI_SHA256 = v1.PUBLIC_SPKI_SHA256

SEGMENTS = v1.SEGMENTS
MASTER_COUNT = v1.MASTER_COUNT
IDENTITIES_PER_SHARD = v1.IDENTITIES_PER_SHARD
SHARD_COUNT_PER_SEGMENT = v1.SHARD_COUNT_PER_SEGMENT
MAX_PAGES = v1.MAX_PAGES
RETRY_CAP_AFTER_INITIAL = v1.RETRY_CAP_AFTER_INITIAL
MAX_WIRE_ATTEMPTS_PER_PAGE = v1.MAX_WIRE_ATTEMPTS_PER_PAGE
RATE_LIMIT_RPS = v1.RATE_LIMIT_RPS
MIN_INTER_REQUEST_SECONDS = v1.MIN_INTER_REQUEST_SECONDS
HEARTBEAT_MAX_IDLE_SECONDS = v1.HEARTBEAT_MAX_IDLE_SECONDS
SOFT_STOP_MINUTES = v1.SOFT_STOP_MINUTES
GITHUB_JOB_TIMEOUT_MINUTES = v1.GITHUB_JOB_TIMEOUT_MINUTES
SHUTDOWN_UPLOAD_MARGIN_MINUTES = v1.SHUTDOWN_UPLOAD_MARGIN_MINUTES

ALLOWED_OUTBOUND_MESSAGE_NAMES = v1.ALLOWED_OUTBOUND_MESSAGE_NAMES
FORBIDDEN_OUTBOUND_MESSAGE_NAMES = v1.FORBIDDEN_OUTBOUND_MESSAGE_NAMES
SYSTEMIC_CODES = v1.SYSTEMIC_CODES

CaptureError = v1.CaptureError
SystemicFailure = v1.SystemicFailure
TransientPageFailure = v1.TransientPageFailure
SoftStop = v1.SoftStop
RateLimiter = v1.RateLimiter
encrypt_shard = v1.encrypt_shard
decrypt_synthetic_package = v1.decrypt_synthetic_package
sha256_file = v1.sha256_file
sha256_bytes = v1.sha256_bytes
canonical_json_bytes = v1.canonical_json_bytes
load_json = v1.load_json
atomic_json = v1.atomic_json

SEGMENT_MANIFEST_PATHS = tuple(
    f"research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_SEGMENT_{i}_DURABLE_MANIFEST.json"
    for i in range(1, 5)
)
FINAL_MANIFEST_REL = v1.FINAL_MANIFEST_REL
ALLOWED_POST_ARM_CAMPAIGN_PATHS = frozenset((*SEGMENT_MANIFEST_PATHS, FINAL_MANIFEST_REL))

SEGMENT_MANIFEST_SCHEMA = "mxm.v4.shallow-m5-v2.segment-durable-manifest.v1"
SEGMENT_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "MASTER_SHA256",
        "ACCOUNT_FINGERPRINT_SHA256",
        "PROTOCOL_FREEZE_SHA256",
        "DIGITS_MAP_SHA256",
        "SEGMENT_INDEX",
        "SEGMENT_FROM_UTC",
        "SEGMENT_TO_UTC_INCLUSIVE",
        "SOURCE_HEAD",
        "ARM_COMMIT",
        "DURABLE_RELEASE_IDENTITY",
        "status",
        "entries",
    }
)
ENTRY_KEYS = frozenset(
    {
        "MASTER_SHA256",
        "ACCOUNT_FINGERPRINT_SHA256",
        "PROTOCOL_FREEZE_SHA256",
        "DIGITS_MAP_SHA256",
        "SOURCE_HEAD",
        "ARM_COMMIT",
        "DURABLE_RELEASE_IDENTITY",
        "SEGMENT_INDEX",
        "SHARD_INDEX",
        "IDENTITY_RANGE",
        "ENCRYPTED_ASSET_NAME",
        "ENCRYPTED_ASSET_SHA256",
        "PLAINTEXT_CANONICAL_SHA256",
        "ROW_COUNT",
        "FIRST_TIMESTAMP",
        "LAST_TIMESTAMP",
        "REQUEST_COUNT",
        "RETRY_COUNT",
        "PAGE_CAP_HITS",
        "FAILURE_LEDGER",
        "PROTECTED_FORWARD_ROW_COUNT",
    }
)
FINAL_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "MASTER_SHA256",
        "ACCOUNT_FINGERPRINT_SHA256",
        "PROTOCOL_FREEZE_SHA256",
        "DIGITS_MAP_SHA256",
        "SOURCE_HEAD",
        "ARM_COMMIT",
        "DURABLE_RELEASE_IDENTITY",
        "segment_count",
        "encrypted_shard_count",
        "PROTECTED_FORWARD_ROW_COUNT",
        "entries",
        "status",
    }
)
HEX64 = frozenset("0123456789abcdef")


def _hex64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX64


def segment_manifest_rel(segment: int) -> str:
    if segment not in (1, 2, 3, 4):
        raise CaptureError("segment must be 1..4")
    return SEGMENT_MANIFEST_PATHS[segment - 1]


def shard_asset_name(segment: int, shard_index: int) -> str:
    return v1.shard_asset_name(segment, shard_index)


def deterministic_identity_range(shard_index: int) -> list[int]:
    if shard_index < 0 or shard_index >= SHARD_COUNT_PER_SEGMENT:
        raise CaptureError("invalid shard index")
    start = shard_index * IDENTITIES_PER_SHARD + 1
    end = min(MASTER_COUNT, start + IDENTITIES_PER_SHARD - 1)
    return [start, end]


def campaign_architecture_sha256() -> str:
    path = ROOT / ARCH_FREEZE_REL
    if not path.is_file():
        raise SystemicFailure("HASH_BOUND_IMPLEMENTATION_MISMATCH")
    return sha256_file(path)


def derive_release_identity(source_head: str) -> str:
    if not isinstance(source_head, str) or len(source_head) != 40 or any(c not in HEX64 for c in source_head):
        raise CaptureError("invalid source head")
    payload = {
        "domain": "mxm.v4.shallow-m5-v2.production-v2.release-identity.v1",
        "source_head": source_head,
        "architecture_freeze_sha256": campaign_architecture_sha256(),
    }
    digest = sha256_bytes(canonical_json_bytes(payload))
    return f"mxm-shallow-m5-v2-{digest}"


def expected_release_body(campaign: Mapping[str, Any]) -> str:
    return canonical_json_bytes(
        {
            "schema": "mxm.v4.shallow-m5-v2.production-v2.release-binding.v1",
            "SOURCE_HEAD": campaign["SOURCE_HEAD"],
            "ARM_COMMIT": campaign["ARM_COMMIT"],
            "DURABLE_RELEASE_IDENTITY": campaign["DURABLE_RELEASE_IDENTITY"],
            "ARCHITECTURE_FREEZE_SHA256": campaign_architecture_sha256(),
        }
    ).decode("utf-8")


def _expected_arm_bindings() -> dict:
    return {
        "V2_PROTOCOL_DECODER_FREEZE_SHA256": PROTOCOL_FREEZE_SHA256,
        "V2_IMPLEMENTATION_SHA256": V2_IMPLEMENTATION_SHA256,
        "V2_DIGITS_MAP_SHA256": DIGITS_MAP_FILE_SHA256,
        "MASTER1576_SHA256": MASTER_SHA256,
        "AUTH_V3_ACCOUNT_FINGERPRINT_SHA256": ACCOUNT_FINGERPRINT_SHA256,
        "FOUR_SEGMENT_GEOMETRY": [list(x) for x in SEGMENTS],
        "PAGE_CAP_3": MAX_PAGES,
        "RETRY_CAP_2_AFTER_INITIAL": RETRY_CAP_AFTER_INITIAL,
        "RATE_LIMIT_4RPS": RATE_LIMIT_RPS,
        "OUTPUT_ENCRYPTION_AUTHORITY_SHA256": sha256_file(ROOT / OUTPUT_AUTH_REL),
        "PRODUCTION_RUNNER_SHA256": sha256_file(ROOT / RUNNER_REL),
        "PRODUCTION_WORKFLOW_SHA256": sha256_file(ROOT / WORKFLOW_REL),
        "ARCHITECTURE_FREEZE_SHA256": sha256_file(ROOT / ARCH_FREEZE_REL),
        "ACCEPTANCE_AUTHORITY_SHA256": sha256_file(ROOT / ACCEPTANCE_REL),
    }


def validate_arm(arm_path: Path = ROOT / ARM_REL) -> dict:
    if not arm_path.is_file():
        raise PermissionError("PRODUCTION_ARM_V2_ABSENT")
    arm = load_json(arm_path)
    if set(arm) != {"schema", "status", "exact_source_head", "durable_release_identity", "bindings"}:
        raise PermissionError("ARM_V2_UNKNOWN_OR_MISSING_FIELDS")
    if arm.get("schema") != "mxm.v4.breadth-first-shallow-m5-support-v2.production-arm.v2":
        raise PermissionError("WRONG_ARM_V2_SCHEMA")
    if arm.get("status") != "ARMED_NOT_EXECUTED":
        raise PermissionError("WRONG_ARM_V2_STATUS")
    source = arm.get("exact_source_head")
    if not isinstance(source, str) or len(source) != 40 or any(c not in HEX64 for c in source):
        raise PermissionError("INVALID_EXACT_SOURCE_HEAD")
    if arm.get("durable_release_identity") != derive_release_identity(source):
        raise PermissionError("NONDETERMINISTIC_OR_WRONG_RELEASE_IDENTITY")
    if arm.get("bindings") != _expected_arm_bindings():
        raise PermissionError("ARM_V2_HASH_OR_PLAN_BINDING_MISMATCH")
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
        raise PermissionError("ARM_V2_COMMIT_MUST_CHANGE_ONLY_EXACT_ARM_FILE")
    return head


def campaign_from_arm(arm: Mapping[str, Any], arm_commit: str) -> dict:
    expected_release = derive_release_identity(str(arm["exact_source_head"]))
    if arm["durable_release_identity"] != expected_release:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    return {
        "MASTER_SHA256": MASTER_SHA256,
        "ACCOUNT_FINGERPRINT_SHA256": ACCOUNT_FINGERPRINT_SHA256,
        "PROTOCOL_FREEZE_SHA256": PROTOCOL_FREEZE_SHA256,
        "DIGITS_MAP_SHA256": DIGITS_MAP_FILE_SHA256,
        "SOURCE_HEAD": str(arm["exact_source_head"]),
        "ARM_COMMIT": arm_commit,
        "DURABLE_RELEASE_IDENTITY": expected_release,
    }


def validate_static_bindings() -> dict:
    return v1.validate_static_bindings()


def _run(cmd: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def verify_branch_chain(
    *,
    base_commit: str,
    branch_name: str,
    allowed_paths: frozenset[str],
) -> str:
    if not base_commit or not branch_name or not allowed_paths:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    remote_ref = f"refs/remotes/origin/{branch_name}"
    fetch = _run(
        [
            "git", "-C", str(ROOT), "fetch", "--no-tags", "origin",
            f"+refs/heads/{branch_name}:{remote_ref}",
        ],
        check=False,
    )
    if fetch.returncode != 0:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    head = _run(["git", "-C", str(ROOT), "rev-parse", remote_ref]).stdout.strip()
    ancestor = _run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", base_commit, head],
        check=False,
    )
    if ancestor.returncode != 0:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    commits = _run(
        ["git", "-C", str(ROOT), "rev-list", "--reverse", f"{base_commit}..{head}"]
    ).stdout.splitlines()
    for commit in commits:
        changed = _run(
            ["git", "-C", str(ROOT), "diff-tree", "--no-commit-id", "--name-only", "-r", commit]
        ).stdout.splitlines()
        if not changed or any(path not in allowed_paths for path in changed):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    return head


def manifest_header(campaign: Mapping[str, Any], segment: int) -> dict:
    return {
        "schema": SEGMENT_MANIFEST_SCHEMA,
        "MASTER_SHA256": campaign["MASTER_SHA256"],
        "ACCOUNT_FINGERPRINT_SHA256": campaign["ACCOUNT_FINGERPRINT_SHA256"],
        "PROTOCOL_FREEZE_SHA256": campaign["PROTOCOL_FREEZE_SHA256"],
        "DIGITS_MAP_SHA256": campaign["DIGITS_MAP_SHA256"],
        "SEGMENT_INDEX": segment,
        "SEGMENT_FROM_UTC": SEGMENTS[segment - 1][0],
        "SEGMENT_TO_UTC_INCLUSIVE": SEGMENTS[segment - 1][1],
        "SOURCE_HEAD": campaign["SOURCE_HEAD"],
        "ARM_COMMIT": campaign["ARM_COMMIT"],
        "DURABLE_RELEASE_IDENTITY": campaign["DURABLE_RELEASE_IDENTITY"],
    }


def new_segment_manifest(campaign: Mapping[str, Any], segment: int) -> dict:
    return {
        **manifest_header(campaign, segment),
        "status": "PARTIAL",
        "entries": [],
    }


def validate_manifest_entry(
    entry: Mapping[str, Any],
    *,
    campaign: Mapping[str, Any],
    segment: int,
) -> dict:
    if set(entry) != ENTRY_KEYS:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    for key in (
        "MASTER_SHA256",
        "ACCOUNT_FINGERPRINT_SHA256",
        "PROTOCOL_FREEZE_SHA256",
        "DIGITS_MAP_SHA256",
        "SOURCE_HEAD",
        "ARM_COMMIT",
        "DURABLE_RELEASE_IDENTITY",
    ):
        if entry.get(key) != campaign[key]:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    if entry.get("SEGMENT_INDEX") != segment:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    shard = entry.get("SHARD_INDEX")
    if type(shard) is not int or shard not in range(SHARD_COUNT_PER_SEGMENT):
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    if entry.get("IDENTITY_RANGE") != deterministic_identity_range(shard):
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    if entry.get("ENCRYPTED_ASSET_NAME") != shard_asset_name(segment, shard):
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    if not _hex64(entry.get("ENCRYPTED_ASSET_SHA256")) or not _hex64(entry.get("PLAINTEXT_CANONICAL_SHA256")):
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    for key in ("ROW_COUNT", "REQUEST_COUNT", "RETRY_COUNT", "PAGE_CAP_HITS", "PROTECTED_FORWARD_ROW_COUNT"):
        value = entry.get(key)
        if type(value) is not int or value < 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    if entry["PROTECTED_FORWARD_ROW_COUNT"] != 0:
        raise SystemicFailure("PROTECTED_FORWARD_LEAK")
    if not isinstance(entry.get("FAILURE_LEDGER"), dict):
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    for key in ("FIRST_TIMESTAMP", "LAST_TIMESTAMP"):
        if entry.get(key) is not None and not isinstance(entry.get(key), str):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    return dict(entry)


def validate_segment_manifest(
    manifest: Mapping[str, Any],
    *,
    campaign: Mapping[str, Any],
    segment: int,
    require_complete: bool,
) -> dict:
    if set(manifest) != SEGMENT_MANIFEST_KEYS:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    expected_header = manifest_header(campaign, segment)
    for key, value in expected_header.items():
        if manifest.get(key) != value:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    status = manifest.get("status")
    if status not in {"PARTIAL", "COMPLETE"}:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) > SHARD_COUNT_PER_SEGMENT:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    validated = [
        validate_manifest_entry(x, campaign=campaign, segment=segment)
        for x in entries
    ]
    indices = [x["SHARD_INDEX"] for x in validated]
    names = [x["ENCRYPTED_ASSET_NAME"] for x in validated]
    if len(indices) != len(set(indices)) or len(names) != len(set(names)):
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    if indices != sorted(indices):
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    if require_complete or status == "COMPLETE":
        if status != "COMPLETE":
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        if len(validated) != SHARD_COUNT_PER_SEGMENT or set(indices) != set(range(SHARD_COUNT_PER_SEGMENT)):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    elif status == "PARTIAL" and len(validated) == SHARD_COUNT_PER_SEGMENT:
        raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
    out = dict(manifest)
    out["entries"] = validated
    return out


def _release_allowed_asset_name(name: str) -> bool:
    expected = {
        shard_asset_name(segment, shard)
        for segment in range(1, 5)
        for shard in range(SHARD_COUNT_PER_SEGMENT)
    }
    return name in expected


class GitHubReleaseStoreV2:
    def __init__(
        self,
        *,
        tag: str,
        campaign: Mapping[str, Any],
        branch_name: str = BRANCH,
        base_commit: str | None = None,
        allowed_paths: frozenset[str] = ALLOWED_POST_ARM_CAMPAIGN_PATHS,
    ):
        self.tag = tag
        self.campaign = dict(campaign)
        self.branch_name = branch_name
        self.base_commit = base_commit or str(campaign["ARM_COMMIT"])
        self.allowed_paths = frozenset(allowed_paths)
        if tag != self.campaign.get("DURABLE_RELEASE_IDENTITY"):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        if not os.environ.get("GH_TOKEN"):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")

    def _gh(self, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
        return _run(["gh", *args], check=check)

    def verify_branch(self) -> str:
        return verify_branch_chain(
            base_commit=self.base_commit,
            branch_name=self.branch_name,
            allowed_paths=self.allowed_paths,
        )

    def release_json(self) -> dict | None:
        run = self._gh(
            ["api", "--method", "GET", f"repos/{REPO}/releases/tags/{self.tag}"],
            check=False,
        )
        if run.returncode != 0:
            if "404" in run.stderr or "Not Found" in run.stderr:
                return None
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        try:
            value = json.loads(run.stdout)
        except Exception as exc:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE") from exc
        return value

    def validate_existing_release(self, release: Mapping[str, Any]) -> int:
        if (
            release.get("tag_name") != self.tag
            or release.get("target_commitish") != self.campaign["ARM_COMMIT"]
            or release.get("body") != expected_release_body(self.campaign)
            or release.get("draft") is not False
        ):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        rid = release.get("id")
        if type(rid) is not int or rid <= 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return rid

    def ensure_release(self, *, create_allowed: bool) -> int:
        self.verify_branch()
        existing = self.release_json()
        if existing is not None:
            return self.validate_existing_release(existing)
        if not create_allowed:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        run = self._gh(
            [
                "api", "--method", "POST", f"repos/{REPO}/releases",
                "-f", f"tag_name={self.tag}",
                "-f", f"target_commitish={self.campaign['ARM_COMMIT']}",
                "-f", f"name={self.tag}",
                "-f", f"body={expected_release_body(self.campaign)}",
                "-F", "draft=false",
                "-F", "prerelease=false",
            ],
            check=False,
        )
        if run.returncode != 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        release = self.release_json()
        if release is None:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return self.validate_existing_release(release)

    def _asset_names(self) -> set[str]:
        release = self.release_json()
        if release is None:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        self.validate_existing_release(release)
        assets = release.get("assets")
        if not isinstance(assets, list):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        names = [str(x.get("name", "")) for x in assets]
        if len(names) != len(set(names)):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return set(names)

    def _download_asset(self, name: str, dest: Path) -> Path:
        dest.mkdir(parents=True, exist_ok=True)
        run = self._gh(
            ["release", "download", self.tag, "--repo", REPO, "--pattern", name, "--dir", str(dest)],
            check=False,
        )
        path = dest / name
        if run.returncode != 0 or not path.is_file():
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return path

    def _delete_asset(self, name: str) -> None:
        run = self._gh(
            ["release", "delete-asset", self.tag, name, "--repo", REPO, "--yes"],
            check=False,
        )
        if run.returncode != 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")

    def load_segment_manifest(self, segment: int, *, require_complete: bool = False) -> dict:
        rel = segment_manifest_rel(segment)
        run = self._gh(
            ["api", "--method", "GET", f"repos/{REPO}/contents/{rel}", "-f", f"ref={self.branch_name}"],
            check=False,
        )
        if run.returncode != 0:
            if ("404" in run.stderr or "Not Found" in run.stderr) and not require_complete:
                return new_segment_manifest(self.campaign, segment)
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        try:
            payload = json.loads(run.stdout)
            raw = base64.b64decode(str(payload["content"]).replace("\n", ""))
            manifest = json.loads(raw)
        except Exception as exc:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE") from exc
        return validate_segment_manifest(
            manifest,
            campaign=self.campaign,
            segment=segment,
            require_complete=require_complete,
        )

    def _put_repo_json(self, rel: str, value: Mapping[str, Any], message: str) -> str:
        if rel not in self.allowed_paths:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        before = self.verify_branch()
        existing = self._gh(
            ["api", "--method", "GET", f"repos/{REPO}/contents/{rel}", "-f", f"ref={self.branch_name}"],
            check=False,
        )
        args = [
            "api", "--method", "PUT", f"repos/{REPO}/contents/{rel}",
            "-f", f"message={message}",
            "-f", "content=" + base64.b64encode(canonical_json_bytes(value) + b"\n").decode("ascii"),
            "-f", f"branch={self.branch_name}",
        ]
        if existing.returncode == 0:
            try:
                args += ["-f", "sha=" + str(json.loads(existing.stdout)["sha"])]
            except Exception as exc:
                raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE") from exc
        elif "404" not in existing.stderr and "Not Found" not in existing.stderr:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        write = self._gh(args, check=False)
        if write.returncode != 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        after = self.verify_branch()
        if after == before:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        ancestry = _run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", before, after],
            check=False,
        )
        if ancestry.returncode != 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return after

    def verify_entry_asset(self, entry: Mapping[str, Any]) -> str:
        name = str(entry.get("ENCRYPTED_ASSET_NAME", ""))
        expected = str(entry.get("ENCRYPTED_ASSET_SHA256", ""))
        if not _release_allowed_asset_name(name) and self.branch_name == BRANCH:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        if name not in self._asset_names():
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        with tempfile.TemporaryDirectory(prefix="mxm-m5v2-v2-asset-") as td:
            path = self._download_asset(name, Path(td))
            observed = sha256_file(path)
        if observed != expected:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        return observed

    def validate_complete_segment_assets(self, segment: int) -> dict:
        manifest = self.load_segment_manifest(segment, require_complete=True)
        expected_names = {shard_asset_name(segment, i) for i in range(SHARD_COUNT_PER_SEGMENT)}
        release_names = self._asset_names()
        if not expected_names <= release_names:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        if any(not _release_allowed_asset_name(x) for x in release_names) and self.branch_name == BRANCH:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        for entry in manifest["entries"]:
            self.verify_entry_asset(entry)
        if sum(int(x["PROTECTED_FORWARD_ROW_COUNT"]) for x in manifest["entries"]) != 0:
            raise SystemicFailure("PROTECTED_FORWARD_LEAK")
        return manifest

    def recoverable_entry(self, segment: int, shard_index: int, identity_range: list[int]) -> dict | None:
        manifest = self.load_segment_manifest(segment, require_complete=False)
        matches = [x for x in manifest["entries"] if x["SHARD_INDEX"] == shard_index]
        if len(matches) > 1:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        name = shard_asset_name(segment, shard_index)
        names = self._asset_names()
        if not matches:
            if name in names:
                self._delete_asset(name)
            return None
        entry = matches[0]
        if entry["IDENTITY_RANGE"] != identity_range or entry["ENCRYPTED_ASSET_NAME"] != name:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        self.verify_entry_asset(entry)
        return entry

    def publish_shard(self, segment: int, shard_index: int, package: Path, entry: Mapping[str, Any]) -> None:
        self.verify_branch()
        validated = validate_manifest_entry(entry, campaign=self.campaign, segment=segment)
        name = validated["ENCRYPTED_ASSET_NAME"]
        if package.name != name or name in self._asset_names():
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        upload = self._gh(["release", "upload", self.tag, str(package), "--repo", REPO], check=False)
        if upload.returncode != 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        self.verify_entry_asset(validated)
        manifest = self.load_segment_manifest(segment, require_complete=False)
        if any(x["SHARD_INDEX"] == shard_index for x in manifest["entries"]):
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        entries = list(manifest["entries"]) + [validated]
        entries.sort(key=lambda x: x["SHARD_INDEX"])
        manifest["entries"] = entries
        manifest["status"] = "COMPLETE" if len(entries) == SHARD_COUNT_PER_SEGMENT else "PARTIAL"
        manifest = validate_segment_manifest(
            manifest,
            campaign=self.campaign,
            segment=segment,
            require_complete=(manifest["status"] == "COMPLETE"),
        )
        self._put_repo_json(
            segment_manifest_rel(segment),
            manifest,
            f"Publish shallow M5 V2 V2 segment {segment} shard {shard_index:02d} durable manifest",
        )
        roundtrip = self.load_segment_manifest(segment, require_complete=(manifest["status"] == "COMPLETE"))
        if roundtrip != manifest:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")

    def publish_final_manifest(self) -> dict:
        manifests = [self.validate_complete_segment_assets(i) for i in range(1, 5)]
        entries = [entry for m in manifests for entry in m["entries"]]
        final = {
            "schema": "mxm.v4.shallow-m5-v2.final-durable-manifest.v2",
            **self.campaign,
            "segment_count": 4,
            "encrypted_shard_count": len(entries),
            "PROTECTED_FORWARD_ROW_COUNT": sum(int(x["PROTECTED_FORWARD_ROW_COUNT"]) for x in entries),
            "entries": entries,
            "status": "COMPLETE",
        }
        if set(final) != FINAL_MANIFEST_KEYS or final["encrypted_shard_count"] != 100 or final["PROTECTED_FORWARD_ROW_COUNT"] != 0:
            raise SystemicFailure("DURABLE_STORAGE_INTEGRITY_FAILURE")
        self._put_repo_json(FINAL_MANIFEST_REL, final, "Publish shallow M5 V2 V2 final compact durable manifest")
        return final


def _manifest_entry_v2(
    *,
    campaign: Mapping[str, Any],
    segment: int,
    shard_index: int,
    items: Sequence[Mapping[str, Any]],
    plaintext_sha: str,
    encrypted_sha: str,
) -> dict:
    rows = [r for item in items for r in item.get("rows", [])]
    failures = Counter(
        str(item.get("failure", {}).get("code"))
        for item in items
        if item.get("failure")
    )
    protected = sum(
        1 for row in rows
        if decoder.to_ms(row["time_utc"]) >= decoder.to_ms(decoder.PROTECTED_FORWARD_BOUNDARY_UTC)
    )
    if protected:
        raise SystemicFailure("PROTECTED_FORWARD_LEAK")
    return {
        **campaign,
        "SEGMENT_INDEX": segment,
        "SHARD_INDEX": shard_index,
        "IDENTITY_RANGE": deterministic_identity_range(shard_index),
        "ENCRYPTED_ASSET_NAME": shard_asset_name(segment, shard_index),
        "ENCRYPTED_ASSET_SHA256": encrypted_sha,
        "PLAINTEXT_CANONICAL_SHA256": plaintext_sha,
        "ROW_COUNT": len(rows),
        "FIRST_TIMESTAMP": min((x["time_utc"] for x in rows), default=None),
        "LAST_TIMESTAMP": max((x["time_utc"] for x in rows), default=None),
        "REQUEST_COUNT": sum(int(x.get("request_count", 0)) for x in items),
        "RETRY_COUNT": sum(int(x.get("retry_count", 0)) for x in items),
        "PAGE_CAP_HITS": sum(int(x.get("page_cap_hits", 0)) for x in items),
        "FAILURE_LEDGER": dict(sorted(failures.items())),
        "PROTECTED_FORWARD_ROW_COUNT": 0,
    }


def production_plan() -> dict:
    plan = copy.deepcopy(v1.production_plan())
    plan.update(
        {
            "architecture_version": 2,
            "strict_segment_manifest_validation": True,
            "deterministic_release_identity": True,
            "previous_segment_all_25_assets_redownload_hash_verified_before_auth": True,
            "campaign_branch_drift_guard": True,
            "same_arm_github_actions_rerun_recovery": True,
            "workflow_dispatch": False,
        }
    )
    return plan


def run_segment(segment: int, *, workdir: Path) -> dict:
    if segment not in (1, 2, 3, 4):
        raise CaptureError("segment must be 1..4")
    arm = validate_arm()
    arm_commit = validate_arm_git_event(arm)
    static = validate_static_bindings()
    campaign = campaign_from_arm(arm, arm_commit)

    store = GitHubReleaseStoreV2(
        tag=campaign["DURABLE_RELEASE_IDENTITY"],
        campaign=campaign,
        branch_name=BRANCH,
        base_commit=arm_commit,
        allowed_paths=ALLOWED_POST_ARM_CAMPAIGN_PATHS,
    )
    store.verify_branch()
    store.ensure_release(create_allowed=(segment == 1))
    if segment > 1:
        store.validate_complete_segment_assets(segment - 1)
    store.verify_branch()

    required = ("CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET", "CTRADER_ACCESS_TOKEN")
    if any(not os.environ.get(x) for x in required):
        raise SystemicFailure("TOKEN_INVALID_OR_EXPIRED")
    if os.environ.get("CTRADER_REFRESH_TOKEN"):
        raise PermissionError("REFRESH_TOKEN_MUST_NOT_BE_IN_PRODUCTION_SEGMENT_ENVIRONMENT")
    credentials = tuple(os.environ[x] for x in required)

    master = static["master"]
    digits = static["digits"]
    workdir.mkdir(parents=True, exist_ok=True)
    checkpoint = workdir / "local-checkpoint.json"
    soft_deadline = time.monotonic() + SOFT_STOP_MINUTES * 60
    limiter = RateLimiter()
    transport, account_id = v1._connect_and_auth(credentials)

    captured_shards = 0
    skipped_shards = 0
    try:
        for shard_index in range(SHARD_COUNT_PER_SEGMENT):
            identity_range = deterministic_identity_range(shard_index)
            existing = store.recoverable_entry(segment, shard_index, identity_range)
            if existing is not None:
                skipped_shards += 1
                continue
            if time.monotonic() >= soft_deadline:
                raise SoftStop("soft runtime boundary reached before new shard")
            items = []
            for ordinal in range(identity_range[0], identity_range[1] + 1):
                row = master[ordinal - 1]
                try:
                    symbol_id = int(row["symbol_id"])
                    symbol_digits = int(digits[symbol_id])
                except Exception as exc:
                    items.append(
                        {
                            "ordinal": ordinal,
                            "symbol_id": row.get("symbol_id"),
                            "classification": "IDENTITY_OR_MAPPING_FAILURE",
                            "request_count": 0,
                            "retry_count": 0,
                            "page_cap_hits": 0,
                            "failure": {"code": "IDENTITY_OR_MAPPING_FAILURE", "detail": type(exc).__name__},
                            "rows": [],
                        }
                    )
                    continue
                transport, item = v1._identity_result(
                    segment=segment,
                    ordinal=ordinal,
                    symbol_id=symbol_id,
                    digits=symbol_digits,
                    account_id=account_id,
                    transport=transport,
                    limiter=limiter,
                    credentials=credentials,
                    checkpoint_path=checkpoint,
                    soft_deadline=soft_deadline,
                )
                items.append(item)

            plaintext = v1._shard_plaintext(segment, shard_index, items)
            package = workdir / shard_asset_name(segment, shard_index)
            enc = encrypt_shard(plaintext, public_key=ROOT / PUBLIC_KEY_REL, output=package)
            entry = _manifest_entry_v2(
                campaign=campaign,
                segment=segment,
                shard_index=shard_index,
                items=items,
                plaintext_sha=enc["plaintext_sha256"],
                encrypted_sha=enc["encrypted_asset_sha256"],
            )
            store.publish_shard(segment, shard_index, package, entry)
            package.unlink(missing_ok=True)
            checkpoint.unlink(missing_ok=True)
            captured_shards += 1
    finally:
        transport.close()
        for p in workdir.glob("*.mxmenc"):
            p.unlink(missing_ok=True)
        checkpoint.unlink(missing_ok=True)

    manifest = store.load_segment_manifest(segment, require_complete=True)
    if len(manifest["entries"]) != SHARD_COUNT_PER_SEGMENT:
        raise SoftStop("segment incomplete after graceful boundary")
    final = None
    if segment == 4:
        final = store.publish_final_manifest()
    return {
        "segment": segment,
        "status": "COMPLETE",
        "captured_shards": captured_shards,
        "skipped_durable_shards": skipped_shards,
        "segment_manifest_ref": segment_manifest_rel(segment),
        "final_manifest_ref": FINAL_MANIFEST_REL if final else None,
        "durable_release_identity": campaign["DURABLE_RELEASE_IDENTITY"],
        "arm_commit": campaign["ARM_COMMIT"],
    }


def recovery_governance() -> dict:
    return {
        "automatic_unbounded_retry": False,
        "workflow_dispatch": False,
        "new_arm_for_infrastructure_recovery": False,
        "permitted_recovery": "RERUN_FAILED_OR_CANCELLED_EXACT_JOB_OF_SAME_ORIGINAL_ARM_WORKFLOW_RUN",
        "exact_same_arm_github_sha_required": True,
        "exact_same_release_identity_required": True,
        "durable_verified_shards": "SKIP_WITHOUT_BROKER_REQUERY",
        "incomplete_unpublished_shard": "MAY_BE_RECAPTURED_AS_INFRASTRUCTURE_RECOVERY",
        "systemic_failure": "STOP_FOR_INDEPENDENT_GOVERNANCE",
        "automatic_rerun": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    sub.add_parser("validate-arm")
    rs = sub.add_parser("run-segment")
    rs.add_argument("--segment", type=int, choices=[1, 2, 3, 4], required=True)
    rs.add_argument("--workdir", type=Path, required=True)
    args = ap.parse_args()

    if args.command == "plan":
        print(json.dumps(production_plan(), sort_keys=True))
        return 0
    if args.command == "validate-arm":
        arm = validate_arm()
        arm_commit = validate_arm_git_event(arm)
        validate_static_bindings()
        campaign = campaign_from_arm(arm, arm_commit)
        store = GitHubReleaseStoreV2(
            tag=campaign["DURABLE_RELEASE_IDENTITY"],
            campaign=campaign,
            branch_name=BRANCH,
            base_commit=arm_commit,
        )
        store.verify_branch()
        print(json.dumps({"status": "PASS_ARM_V2_STATIC_AND_BRANCH_BINDINGS"}, sort_keys=True))
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
