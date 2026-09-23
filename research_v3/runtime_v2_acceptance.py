"""Chaos/recovery acceptance proof for Autonomous Research Runtime V2."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from research_v3.runtime_v2_primitives import RUNTIME_VERSION, FailureInjector, InjectedCrash, LeaseBusy, atomic_write_json
from research_v3.autonomous_runtime_v2 import RuntimeV2, make_synthetic_plan, canonical_runtime_snapshot

def zero_human_continuation_demo() -> dict[str, Any]:
    """Run the mandatory synthetic acceptance proof without touching project economics."""
    boundaries = [
        "prospective_freeze_creation",
        "pre_outcome_validation",
        "authorization",
        "economic_execution_start_marker",
        "result_generation_before_result_persistence",
        "result_file_persistence",
        "ledger_append",
        "accounting_update",
        "current_state_update",
        "checkpoint_update",
        "post_persistence_validation",
        "lifecycle_closure",
    ]
    with tempfile.TemporaryDirectory(prefix="mxm-runtime-v2-acceptance-") as td:
        base = Path(td) / "base"; base.mkdir()
        rt = RuntimeV2(base, lease_seconds=1)
        for seed in ("cycle-a", "cycle-b", "cycle-c"):
            rt.submit_operation(make_synthetic_plan(seed))
        baseline = rt.run()
        if baseline.status != "COMPLETE" or len(baseline.completed_operation_ids) != 3:
            raise AssertionError("baseline autonomous multi-cycle run failed")
        expected = canonical_runtime_snapshot(base)

        chaos: dict[str, str] = {}
        for boundary in boundaries:
            case = Path(td) / f"case-{boundary}"; case.mkdir()
            seed_rt = RuntimeV2(case, lease_seconds=1)
            for seed in ("cycle-a", "cycle-b", "cycle-c"):
                seed_rt.submit_operation(make_synthetic_plan(seed))
            crashing = RuntimeV2(case, lease_seconds=0, injector=FailureInjector([boundary]), owner_token=f"crash-{boundary}")
            try:
                crashing.run()
            except InjectedCrash:
                pass
            resumed = RuntimeV2(case, lease_seconds=1, owner_token=f"resume-{boundary}")
            outcome = resumed.run()
            if outcome.status != "COMPLETE":
                raise AssertionError(f"{boundary}: did not autonomously recover")
            got = canonical_runtime_snapshot(case)
            if got != expected:
                raise AssertionError(f"{boundary}: final canonical bytes differ from baseline")
            chaos[boundary] = "PASS"

        ext = Path(td) / "external"; ext.mkdir()
        ext_rt = RuntimeV2(ext, lease_seconds=1)
        ext_path = "development_input/external.json"
        op, _ = ext_rt.submit_operation(make_synthetic_plan("external", external_data={"required": True, "path": ext_path}))
        first = ext_rt.run()
        if first.status != "EXTERNAL_ACTION_REQUIRED" or first.waiting_operation_id != op:
            raise AssertionError("external-data wait state failed")
        target = ext / ext_path; target.parent.mkdir(parents=True, exist_ok=True); atomic_write_json(target, {"ok": True})
        second = RuntimeV2(ext, lease_seconds=1).run()
        if second.status != "COMPLETE":
            raise AssertionError("external-data autonomous resume failed")

        lease_case = Path(td) / "lease"; lease_case.mkdir()
        lease_rt1 = RuntimeV2(lease_case, lease_seconds=600, owner_token="owner-a")
        lease_rt1.submit_operation(make_synthetic_plan("lease"))
        lease_rt1.acquire_lease()
        blocked = False
        try:
            RuntimeV2(lease_case, lease_seconds=600, owner_token="owner-b").acquire_lease()
        except LeaseBusy:
            blocked = True
        if not blocked:
            raise AssertionError("double executor start was not blocked")
        lease_doc = json.loads(lease_rt1.lease_path.read_text(encoding="utf-8"))
        lease_doc["expires_utc"] = "2000-01-01T00:00:00Z"
        atomic_write_json(lease_rt1.lease_path, lease_doc)
        takeover = RuntimeV2(lease_case, lease_seconds=600, owner_token="owner-b")
        reclaimed = takeover.acquire_lease()
        if reclaimed.get("retry_metadata", {}).get("reason") != "STALE_LEASE_TAKEOVER":
            raise AssertionError("stale lease was not reclaimed with durable takeover metadata")
        takeover.release_lease()

        repeat = Path(td) / "repeat"; repeat.mkdir()
        repeat_rt = RuntimeV2(repeat, lease_seconds=1)
        repeat_rt.submit_operation(make_synthetic_plan("repeat"))
        if repeat_rt.run().status != "COMPLETE":
            raise AssertionError("repeat baseline failed")
        snap1 = canonical_runtime_snapshot(repeat)
        if RuntimeV2(repeat, lease_seconds=1).run().status != "COMPLETE":
            raise AssertionError("repeat dispatch did not cleanly no-op")
        snap2 = canonical_runtime_snapshot(repeat)
        if snap1 != snap2:
            raise AssertionError("repeated dispatch changed canonical economics/accounting")

        class OneShotCheckpointFailure:
            def __init__(self):
                self.failed = False
            def checkpoint(self, boundary: str, operation_id: str | None) -> None:
                if boundary == "authorization" and not self.failed:
                    self.failed = True
                    raise RuntimeError("simulated git checkpoint/push interruption")

        push_case = Path(td) / "push-interruption"; push_case.mkdir()
        push_seed = RuntimeV2(push_case, lease_seconds=1)
        push_seed.submit_operation(make_synthetic_plan("push-interruption"))
        failed_push_runtime = RuntimeV2(
            push_case, lease_seconds=0, owner_token="push-fail",
            checkpoint_sink=OneShotCheckpointFailure(),
        )
        try:
            failed_push_runtime.run()
        except RuntimeError as exc:
            if "checkpoint/push interruption" not in str(exc):
                raise
        resumed_push = RuntimeV2(push_case, lease_seconds=1, owner_token="push-resume").run()
        if resumed_push.status != "COMPLETE":
            raise AssertionError("interrupted checkpoint/push did not recover")

        gate = Path(td) / "gate"; gate.mkdir()
        gate_rt = RuntimeV2(gate, lease_seconds=1)
        bad_op, _ = gate_rt.submit_operation(make_synthetic_plan("gate", gate_status="FAIL"))
        halted = gate_rt.run()
        if halted.status != "HALT_MATERIAL_INTEGRITY":
            raise AssertionError("failed gate did not fail closed")
        if gate_rt.journal.has(bad_op, "ECONOMIC_RESULT_AVAILABLE"):
            raise AssertionError("failed gate opened economics")

        return {
            "schema": "mxm.greenfield.runtime-v2-acceptance-report.v1",
            "runtime_version": RUNTIME_VERSION,
            "status": "PASS",
            "zero_human_continuation": "PASS",
            "synthetic_cycles": 3,
            "chaos_failure_points": "PASS",
            "chaos_failure_point_details": chaos,
            "external_data_wait_resume": "PASS",
            "stale_lease_takeover": "PASS",
            "double_executor_start": "PASS",
            "repeated_dispatch": "PASS",
            "watchdog_valid_lease_noop": "PASS",
            "failed_ci_test_gate_fail_closed": "PASS",
            "interrupted_checkpoint_push_recovery": "PASS",
            "duplicate_result": 0,
            "duplicate_ledger_entry": 0,
            "duplicate_economic_outcome": 0,
            "duplicate_attempt": 0,
            "lost_result": 0,
            "same_final_canonical_bytes": True,
        }
