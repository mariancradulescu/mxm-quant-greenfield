import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from research_v3.autonomous_runtime_v2 import (
    FailureInjector,
    IdentityBinding,
    InjectedCrash,
    LeaseBusy,
    RuntimeV2,
    make_synthetic_plan,
    zero_human_continuation_demo,
)
from research_v3.runtime_v2_primitives import GitCheckpointSink


class AutonomousRuntimeV2Tests(unittest.TestCase):
    def test_zero_human_continuation_demonstration(self):
        report = zero_human_continuation_demo()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["zero_human_continuation"], "PASS")
        self.assertEqual(report["chaos_failure_points"], "PASS")
        self.assertEqual(len(report["chaos_failure_point_details"]), 12)
        self.assertTrue(report["same_final_canonical_bytes"])
        self.assertEqual(report["duplicate_economic_outcome"], 0)
        self.assertEqual(report["lost_result"], 0)

    def test_identity_is_deterministic_and_binds_all_required_inputs(self):
        plan = make_synthetic_plan("identity")
        a = IdentityBinding(**{k: plan[k] for k in (
            "candidate_spec_hash", "dataset_hash", "evaluator_hash", "cost_authority_hash",
            "execution_semantics_version", "lifecycle_phase",
        )})
        b = IdentityBinding(**a.as_dict())
        self.assertEqual(a.operation_id, b.operation_id)
        self.assertEqual(a.economic_execution_id, b.economic_execution_id)
        changed = dict(a.as_dict()); changed["dataset_hash"] = "f" * 64
        c = IdentityBinding(**changed)
        self.assertNotEqual(a.operation_id, c.operation_id)
        self.assertNotEqual(a.economic_execution_id, c.economic_execution_id)

    def test_result_available_prevents_economic_rerun(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed = RuntimeV2(root, lease_seconds=0)
            op, _ = seed.submit_operation(make_synthetic_plan("no-rerun"))
            crash = RuntimeV2(root, lease_seconds=0,
                              injector=FailureInjector(["result_generation_before_result_persistence"]),
                              owner_token="first")
            with self.assertRaises(InjectedCrash):
                crash.run()
            available_before = len([r for r in crash.journal.events_for(op) if r["event"] == "ECONOMIC_RESULT_AVAILABLE"])
            self.assertEqual(available_before, 1)
            resumed = RuntimeV2(root, lease_seconds=1, owner_token="second")
            self.assertEqual(resumed.run().status, "COMPLETE")
            events = resumed.journal.events_for(op)
            self.assertEqual(len([r for r in events if r["event"] == "ECONOMIC_RESULT_AVAILABLE"]), 1)
            self.assertEqual(len([r for r in events if r["event"] == "RESULT_FILE_PERSISTED"]), 1)

    def test_external_wait_opens_no_outcome_then_resumes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = "input/external.json"
            rt = RuntimeV2(root, lease_seconds=1)
            op, _ = rt.submit_operation(make_synthetic_plan("external-test", external_data={"required": True, "path": path}))
            first = rt.run()
            self.assertEqual(first.status, "EXTERNAL_ACTION_REQUIRED")
            self.assertFalse(rt.journal.has(op, "ECONOMIC_EXECUTION_STARTED"))
            target = root / path; target.parent.mkdir(parents=True); target.write_text('{"ok":true}\n')
            self.assertEqual(RuntimeV2(root, lease_seconds=1).run().status, "COMPLETE")

    def test_valid_lease_blocks_second_executor_and_stale_lease_is_reclaimed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = RuntimeV2(root, lease_seconds=600, owner_token="a")
            a.acquire_lease()
            with self.assertRaises(LeaseBusy):
                RuntimeV2(root, lease_seconds=600, owner_token="b").acquire_lease()
            lease = json.loads(a.lease_path.read_text())
            lease["expires_utc"] = "2000-01-01T00:00:00Z"
            a.lease_path.write_text(json.dumps(lease))
            b = RuntimeV2(root, lease_seconds=600, owner_token="b")
            recovered = b.acquire_lease()
            self.assertEqual(recovered["attempt"], 2)
            self.assertEqual(recovered["retry_metadata"]["reason"], "STALE_LEASE_TAKEOVER")

    def test_checkpoint_push_conflict_rebases_and_retries(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "work"
            remote = Path(td) / "remote.git"
            other = Path(td) / "other"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            root.mkdir()
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "runtime-test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "runtime-test@example.invalid"], cwd=root, check=True)
            (root / "base.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=root, check=True)
            subprocess.run(["git", "push", "-u", "origin", "HEAD:research"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "clone", "--branch", "research", str(remote), str(other)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "other-test"], cwd=other, check=True)
            subprocess.run(["git", "config", "user.email", "other-test@example.invalid"], cwd=other, check=True)
            (other / "remote.txt").write_text("remote advance\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=other, check=True)
            subprocess.run(["git", "commit", "-m", "remote advance"], cwd=other, check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "HEAD:research"], cwd=other, check=True, capture_output=True)
            (root / "checkpoint.txt").write_text("checkpoint\n", encoding="utf-8")
            previous = os.environ.get("MXM_RUNTIME_TARGET_BRANCH")
            os.environ["MXM_RUNTIME_TARGET_BRANCH"] = "research"
            try:
                GitCheckpointSink(root, enabled=True, push=True).checkpoint("conflict-test", None)
            finally:
                if previous is None:
                    os.environ.pop("MXM_RUNTIME_TARGET_BRANCH", None)
                else:
                    os.environ["MXM_RUNTIME_TARGET_BRANCH"] = previous
            local_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            remote_head = subprocess.check_output(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/research"], text=True
            ).strip()
            self.assertEqual(local_head, remote_head)
            self.assertTrue((root / "remote.txt").exists())

    def test_real_operation_is_blocked_until_acceptance_evidence_exists(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = make_synthetic_plan("real-gate")
            plan["lifecycle_phase"] = "STAGE_B"
            rt = RuntimeV2(root, lease_seconds=1)
            op, _ = rt.submit_operation(plan)
            outcome = rt.run()
            self.assertEqual(outcome.status, "HALT_MATERIAL_INTEGRITY")
            self.assertFalse(rt.journal.has(op, "ECONOMIC_EXECUTION_STARTED"))


if __name__ == "__main__":
    unittest.main()
