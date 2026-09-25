import json,tempfile,unittest
from pathlib import Path

from competition.capture_runtime import (
    CONTRACT_VERSION,CaptureCheckpoint,CaptureProgress,CaptureResumeError,
    RUNTIME_SCHEMA,new_checkpoint,validate_resume,
)
from competition.broker_universe_capture_v3 import (
    COLLECTOR_SCHEMA_VERSION,TOOL_VERSION,merge_partial_rows,remaining_ids,
)

class FakeClock:
    def __init__(self):self.t=100.0
    def __call__(self):return self.t
    def advance(self,n):self.t+=n

class CaptureRuntimeV1Tests(unittest.TestCase):
    def _checkpoint(self):
        return {
            "schema":RUNTIME_SCHEMA,"capture_session_id":"s1",
            "collector_schema_version":COLLECTOR_SCHEMA_VERSION,"tool_version":TOOL_VERSION,
            "capture_contract_version":CONTRACT_VERSION,"account_fingerprint":"fp",
            "capture_start_utc":"2026-09-25T00:00:00Z","last_checkpoint_epoch":1000.0,
            "observed_or_frozen_symbol_universe_hash":"u1","active_phase":"EXPECTED_MARGIN",
            "completed_symbol_metadata_batches":[0],"completed_symbol_ids":[1,2],
            "completed_expected_margin_symbol_ids":[1],"completed_leverage_ids":[],
            "retry_count":1,"reconnect_count":1,"partial_payload_hashes":{},"completion_state":"PARTIAL",
        }

    def test_interrupted_metadata_and_margin_skip_completed_work(self):
        self.assertEqual(remaining_ids([1,2,3,4],[1,2]),[3,4])
        self.assertEqual(remaining_ids([1,2,3],[1]),[2,3])

    def test_resumed_and_uninterrupted_row_merge_are_equivalent(self):
        fresh={"1":{"x":1},"2":{"x":2},"3":{"x":3}}
        resumed=merge_partial_rows({"1":{"x":1}},{"2":{"x":2},"3":{"x":3}})
        self.assertEqual(resumed,fresh)
        with self.assertRaises(CaptureResumeError):
            merge_partial_rows({"1":{"x":1}},{"1":{"x":99}})

    def test_account_tool_contract_and_universe_mismatch_fail_closed(self):
        cp=self._checkpoint()
        for kwargs in (
            {"account_fingerprint":"other"},
            {"tool_version":"other"},
            {"capture_contract_version":"other"},
            {"observed_symbol_universe_hash":"other"},
        ):
            base=dict(account_fingerprint="fp",collector_schema_version=COLLECTOR_SCHEMA_VERSION,
                      tool_version=TOOL_VERSION,capture_contract_version=CONTRACT_VERSION,
                      observed_symbol_universe_hash="u1",coherence_tolerance_seconds=3600,now_epoch=1200.0)
            base.update(kwargs)
            with self.assertRaises(CaptureResumeError):validate_resume(cp,**base)

    def test_long_interruption_reuses_static_metadata_but_refreshes_margin(self):
        cp=self._checkpoint()
        out=validate_resume(cp,account_fingerprint="fp",collector_schema_version=COLLECTOR_SCHEMA_VERSION,
            tool_version=TOOL_VERSION,capture_contract_version=CONTRACT_VERSION,
            observed_symbol_universe_hash="u1",coherence_tolerance_seconds=100,now_epoch=1200.0)
        self.assertTrue(out["reuse_static_symbol_metadata"])
        self.assertTrue(out["refresh_time_sensitive_expected_margin"])

    def test_corrupt_checkpoint_fails_closed_and_credentials_cannot_persist(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"cp.json";p.write_text("{bad",encoding="utf-8")
            with self.assertRaises(CaptureResumeError):CaptureCheckpoint(p).load()
            p.unlink()
            with self.assertRaises(CaptureResumeError):
                CaptureCheckpoint(p).save({"capture_session_id":"s","access_token":"secret"})

    def test_heartbeat_is_time_based_and_progress_reaches_100_only_after_finalization(self):
        messages=[];clock=FakeClock();p=CaptureProgress(messages.append,heartbeat_seconds=10,clock=clock)
        p.configure("expected_margin_identities",10)
        self.assertTrue(messages)
        messages.clear();clock.advance(11);p.update(4,current_identifier=123)
        self.assertTrue(messages);self.assertIn("[ACTIVE]",messages[-1]);self.assertIn("current=123",messages[-1])
        p.update(10,force=True)
        self.assertLess(p.snapshot()["overall_percent"],100.0)
        p.mark_finalized()
        self.assertEqual(p.snapshot()["overall_percent"],100.0)

    def test_retry_and_reconnect_are_visible_in_heartbeat(self):
        messages=[];clock=FakeClock();p=CaptureProgress(messages.append,heartbeat_seconds=10,clock=clock)
        p.configure("metadata",5);messages.clear();p.retry();p.reconnect()
        self.assertGreaterEqual(len(messages),2)
        snap=p.snapshot();self.assertEqual(snap["retry_count"],1);self.assertEqual(snap["reconnect_count"],1)

if __name__=="__main__":unittest.main()
