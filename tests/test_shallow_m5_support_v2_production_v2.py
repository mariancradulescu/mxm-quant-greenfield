from __future__ import annotations

import copy
import hashlib
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from research_core_v4 import shallow_m5_support_v2_production_v2 as p


def campaign():
    return {
        "MASTER_SHA256": p.MASTER_SHA256,
        "ACCOUNT_FINGERPRINT_SHA256": p.ACCOUNT_FINGERPRINT_SHA256,
        "PROTOCOL_FREEZE_SHA256": p.PROTOCOL_FREEZE_SHA256,
        "DIGITS_MAP_SHA256": p.DIGITS_MAP_FILE_SHA256,
        "SOURCE_HEAD": "1" * 40,
        "ARM_COMMIT": "2" * 40,
        "DURABLE_RELEASE_IDENTITY": "mxm-shallow-m5-v2-" + "3" * 64,
    }


def entry(segment=1, shard=0, c=None):
    c = c or campaign()
    return {
        **c,
        "SEGMENT_INDEX": segment,
        "SHARD_INDEX": shard,
        "IDENTITY_RANGE": p.deterministic_identity_range(shard),
        "ENCRYPTED_ASSET_NAME": p.shard_asset_name(segment, shard),
        "ENCRYPTED_ASSET_SHA256": "a" * 64,
        "PLAINTEXT_CANONICAL_SHA256": "b" * 64,
        "ROW_COUNT": 0,
        "FIRST_TIMESTAMP": None,
        "LAST_TIMESTAMP": None,
        "REQUEST_COUNT": 0,
        "RETRY_COUNT": 0,
        "PAGE_CAP_HITS": 0,
        "FAILURE_LEDGER": {},
        "PROTECTED_FORWARD_ROW_COUNT": 0,
    }


def manifest(segment=1, count=1, c=None, complete=False):
    c = c or campaign()
    entries = [entry(segment, i, c) for i in range(count)]
    return {
        **p.manifest_header(c, segment),
        "status": "COMPLETE" if complete else "PARTIAL",
        "entries": entries,
    }


class V2DurabilityTests(unittest.TestCase):
    def test_strict_segment_manifest_all_header_bindings(self):
        m = manifest()
        got = p.validate_segment_manifest(m, campaign=campaign(), segment=1, require_complete=False)
        self.assertEqual(got, m)
        bad = dict(m)
        bad["unknown_semantic_field"] = True
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(bad, campaign=campaign(), segment=1, require_complete=False)

    def test_wrong_arm_commit_fails(self):
        m = manifest()
        m["ARM_COMMIT"] = "f" * 40
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=campaign(), segment=1, require_complete=False)

    def test_wrong_master_hash_fails(self):
        m = manifest()
        m["MASTER_SHA256"] = "0" * 64
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=campaign(), segment=1, require_complete=False)

    def test_wrong_account_fingerprint_fails(self):
        m = manifest()
        m["ACCOUNT_FINGERPRINT_SHA256"] = "0" * 64
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=campaign(), segment=1, require_complete=False)

    def test_wrong_protocol_hash_fails(self):
        m = manifest()
        m["PROTOCOL_FREEZE_SHA256"] = "0" * 64
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=campaign(), segment=1, require_complete=False)

    def test_wrong_digits_hash_fails(self):
        m = manifest()
        m["DIGITS_MAP_SHA256"] = "0" * 64
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=campaign(), segment=1, require_complete=False)

    def test_wrong_release_identity_fails(self):
        m = manifest()
        m["DURABLE_RELEASE_IDENTITY"] = "wrong"
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=campaign(), segment=1, require_complete=False)

    def test_duplicate_shard_index_fails(self):
        c = campaign()
        m = manifest(c=c)
        m["entries"].append(copy.deepcopy(m["entries"][0]))
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=c, segment=1, require_complete=False)

    def test_wrong_identity_range_fails(self):
        c = campaign()
        m = manifest(c=c)
        m["entries"][0]["IDENTITY_RANGE"] = [2, 65]
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=c, segment=1, require_complete=False)

    def test_wrong_asset_name_fails(self):
        c = campaign()
        m = manifest(c=c)
        m["entries"][0]["ENCRYPTED_ASSET_NAME"] = "wrong.mxmenc"
        with self.assertRaises(p.SystemicFailure):
            p.validate_segment_manifest(m, campaign=c, segment=1, require_complete=False)

    def test_complete_requires_exact_25_indices(self):
        c = campaign()
        m = manifest(count=25, c=c, complete=True)
        got = p.validate_segment_manifest(m, campaign=c, segment=1, require_complete=True)
        self.assertEqual([x["SHARD_INDEX"] for x in got["entries"]], list(range(25)))

    def test_previous_segment_all25_asset_hash_verification(self):
        c = campaign()
        store = object.__new__(p.GitHubReleaseStoreV2)
        store.tag = c["DURABLE_RELEASE_IDENTITY"]
        store.campaign = c
        store.branch_name = p.BRANCH
        store.base_commit = c["ARM_COMMIT"]
        store.allowed_paths = p.ALLOWED_POST_ARM_CAMPAIGN_PATHS
        full = manifest(count=25, c=c, complete=True)
        store.load_segment_manifest = mock.Mock(return_value=full)
        store._asset_names = mock.Mock(return_value={p.shard_asset_name(1, i) for i in range(25)})
        store.verify_entry_asset = mock.Mock(return_value="a" * 64)
        out = store.validate_complete_segment_assets(1)
        self.assertEqual(len(out["entries"]), 25)
        self.assertEqual(store.verify_entry_asset.call_count, 25)

    def test_missing_previous_asset_fails_before_auth(self):
        c = campaign()
        store = object.__new__(p.GitHubReleaseStoreV2)
        store.tag = c["DURABLE_RELEASE_IDENTITY"]
        store.campaign = c
        store.branch_name = p.BRANCH
        store.base_commit = c["ARM_COMMIT"]
        store.allowed_paths = p.ALLOWED_POST_ARM_CAMPAIGN_PATHS
        store.load_segment_manifest = mock.Mock(return_value=manifest(count=25, c=c, complete=True))
        names = {p.shard_asset_name(1, i) for i in range(25)}
        names.remove(p.shard_asset_name(1, 9))
        store._asset_names = mock.Mock(return_value=names)
        with self.assertRaises(p.SystemicFailure):
            store.validate_complete_segment_assets(1)
        src = inspect.getsource(p.run_segment)
        self.assertLess(src.index("store.validate_complete_segment_assets(segment - 1)"), src.index("v1._connect_and_auth(credentials)"))

    def test_corrupted_previous_asset_fails_before_auth(self):
        c = campaign()
        store = object.__new__(p.GitHubReleaseStoreV2)
        store.tag = c["DURABLE_RELEASE_IDENTITY"]
        store.campaign = c
        store.branch_name = p.BRANCH
        store.base_commit = c["ARM_COMMIT"]
        store.allowed_paths = p.ALLOWED_POST_ARM_CAMPAIGN_PATHS
        e = entry(c=c)
        store._asset_names = mock.Mock(return_value={e["ENCRYPTED_ASSET_NAME"]})
        with tempfile.TemporaryDirectory() as td:
            wrong = Path(td) / e["ENCRYPTED_ASSET_NAME"]
            wrong.write_bytes(b"corrupt")
            store._download_asset = mock.Mock(return_value=wrong)
            with self.assertRaises(p.SystemicFailure):
                store.verify_entry_asset(e)

    def test_unrelated_post_arm_branch_commit_fails_closed(self):
        allowed = next(iter(p.ALLOWED_POST_ARM_CAMPAIGN_PATHS))
        def fake(cmd, check=True):
            s = " ".join(cmd)
            if " fetch " in f" {s} ":
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "rev-parse refs/remotes/origin/" in s:
                return mock.Mock(returncode=0, stdout="9"*40+"\n", stderr="")
            if "merge-base --is-ancestor" in s:
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "rev-list --reverse" in s:
                return mock.Mock(returncode=0, stdout="8"*40+"\n", stderr="")
            if "diff-tree" in s:
                return mock.Mock(returncode=0, stdout="README.md\n", stderr="")
            raise AssertionError(s)
        with mock.patch.object(p, "_run", side_effect=fake):
            with self.assertRaises(p.SystemicFailure):
                p.verify_branch_chain(base_commit="2"*40, branch_name="x", allowed_paths=frozenset({allowed}))

    def test_allowed_manifest_only_campaign_chain_passes(self):
        allowed = next(iter(p.ALLOWED_POST_ARM_CAMPAIGN_PATHS))
        def fake(cmd, check=True):
            s = " ".join(cmd)
            if " fetch " in f" {s} ":
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "rev-parse refs/remotes/origin/" in s:
                return mock.Mock(returncode=0, stdout="9"*40+"\n", stderr="")
            if "merge-base --is-ancestor" in s:
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "rev-list --reverse" in s:
                return mock.Mock(returncode=0, stdout="8"*40+"\n", stderr="")
            if "diff-tree" in s:
                return mock.Mock(returncode=0, stdout=allowed+"\n", stderr="")
            raise AssertionError(s)
        with mock.patch.object(p, "_run", side_effect=fake):
            self.assertEqual(
                p.verify_branch_chain(base_commit="2"*40, branch_name="x", allowed_paths=frozenset({allowed})),
                "9"*40,
            )

    def test_durable_shard_recovery_skip(self):
        c = campaign()
        store = object.__new__(p.GitHubReleaseStoreV2)
        store.tag = c["DURABLE_RELEASE_IDENTITY"]
        store.campaign = c
        store.branch_name = p.BRANCH
        store.base_commit = c["ARM_COMMIT"]
        store.allowed_paths = p.ALLOWED_POST_ARM_CAMPAIGN_PATHS
        e = entry(c=c)
        store.load_segment_manifest = mock.Mock(return_value=manifest(c=c))
        store._asset_names = mock.Mock(return_value={e["ENCRYPTED_ASSET_NAME"]})
        store.verify_entry_asset = mock.Mock(return_value=e["ENCRYPTED_ASSET_SHA256"])
        self.assertEqual(store.recoverable_entry(1, 0, [1, 64]), e)

    def test_incomplete_shard_recovery_recapture(self):
        c = campaign()
        store = object.__new__(p.GitHubReleaseStoreV2)
        store.tag = c["DURABLE_RELEASE_IDENTITY"]
        store.campaign = c
        store.branch_name = p.BRANCH
        store.base_commit = c["ARM_COMMIT"]
        store.allowed_paths = p.ALLOWED_POST_ARM_CAMPAIGN_PATHS
        empty = p.new_segment_manifest(c, 1)
        store.load_segment_manifest = mock.Mock(return_value=empty)
        store._asset_names = mock.Mock(return_value=set())
        self.assertIsNone(store.recoverable_entry(1, 0, [1, 64]))

    def test_systemic_failure_no_automatic_rerun(self):
        law = p.recovery_governance()
        self.assertFalse(law["automatic_rerun"])
        self.assertEqual(law["systemic_failure"], "STOP_FOR_INDEPENDENT_GOVERNANCE")

    def test_same_arm_machine_side_rerun_semantics(self):
        src = inspect.getsource(p.validate_arm_git_event)
        self.assertIn('os.environ.get("GITHUB_SHA")', src)
        self.assertNotIn("GITHUB_RUN_ATTEMPT", src)
        law = p.recovery_governance()
        self.assertTrue(law["exact_same_arm_github_sha_required"])
        self.assertFalse(law["new_arm_for_infrastructure_recovery"])

    def test_zero_workflow_dispatch(self):
        workflow = (p.ROOT / p.WORKFLOW_REL).read_text(encoding="utf-8")
        self.assertNotIn("workflow_dispatch", workflow)

    def test_deterministic_release_identity_law(self):
        with mock.patch.object(p, "campaign_architecture_sha256", return_value="a"*64):
            a = p.derive_release_identity("1"*40)
            b = p.derive_release_identity("1"*40)
            c = p.derive_release_identity("2"*40)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("mxm-shallow-m5-v2-"))

    def test_previous_gate_is_before_ctrader_secret_read_and_auth(self):
        src = inspect.getsource(p.run_segment)
        gate = src.index("store.validate_complete_segment_assets(segment - 1)")
        secret_read = src.index('required = ("CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET", "CTRADER_ACCESS_TOKEN")')
        auth = src.index("v1._connect_and_auth(credentials)")
        self.assertLess(gate, secret_read)
        self.assertLess(gate, auth)

    def test_v1_files_are_not_v2_write_targets(self):
        self.assertNotEqual(p.RUNNER_REL, p.v1.RUNNER_REL)
        self.assertNotEqual(p.WORKFLOW_REL, p.v1.WORKFLOW_REL)
        self.assertNotEqual(p.ARCH_FREEZE_REL, p.v1.ARCH_FREEZE_REL)
        self.assertNotEqual(p.OUTPUT_AUTH_REL, p.v1.OUTPUT_AUTH_REL)


if __name__ == "__main__":
    unittest.main()
