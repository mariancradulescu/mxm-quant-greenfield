import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import competition.ultra_fast_capture as uf
from competition.ultra_fast_capture import PayloadRateLimited
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAGetTickDataReq

ROOT=Path(__file__).resolve().parents[1]


class ProtoOAErrorRes:
    def __init__(self,code="BLOCKED_PAYLOAD_TYPE",retry_after=None,description=""):
        self.errorCode=code
        self.description=description
        if retry_after is not None:
            self.retryAfter=retry_after


class SequenceTransport:
    def __init__(self,responses):
        self.responses=list(responses)
        self.calls=0
        self.connected=True
    def connect(self): self.connected=True
    def close(self): self.connected=False
    def request(self,req,timeout=60):
        self.calls+=1
        if not self.responses:
            raise AssertionError("unexpected request")
        item=self.responses.pop(0)
        if isinstance(item,Exception):
            raise item
        return item


class UltraFastRateLimitRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json").read_text())
        cls.protocol=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json").read_text())

    def runner(self,root,transport,progress=lambda *_:None):
        return uf.UltraFastCaptureRunner(
            plan=copy.deepcopy(self.plan),protocol=copy.deepcopy(self.protocol),
            client_id="x",client_secret="secret",access_token="token",
            config={},repo_root=root,transport=transport,progress=progress,
        )

    def request(self):
        return ProtoOAGetTickDataReq(
            ctidTraderAccountId=1,symbolId=1,type=1,
            fromTimestamp=1_700_000_000_000,toTimestamp=1_700_000_000_100,
        )

    def test_01_effective_historical_pacing_has_material_headroom_below_official_five_rps(self):
        self.assertGreater(uf.HISTORICAL_MIN_INTERVAL_SECONDS,0.25)
        self.assertGreater(1.0/uf.HISTORICAL_MIN_INTERVAL_SECONDS,3.8)
        self.assertLess(1.0/uf.HISTORICAL_MIN_INTERVAL_SECONDS,4.0)

    def test_02_blocked_payload_type_is_not_capture_contract_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),SequenceTransport([ProtoOAErrorRes(retry_after=3)]))
            with self.assertRaises(PayloadRateLimited) as ctx:
                runner._request(self.request(),historical=True)
        self.assertEqual(ctx.exception.retry_after,3.0)

    def test_03_send_honors_retry_after_without_reconnect_or_transport_retry_consumption(self):
        success=object()
        transport=SequenceTransport([ProtoOAErrorRes(retry_after=2),success])
        progress=[]
        with tempfile.TemporaryDirectory() as td, patch.object(uf.time,"sleep") as sleeper:
            runner=self.runner(Path(td),transport,progress.append)
            out=runner._send(self.request(),historical=True,retries=1)
        self.assertIs(out,success)
        self.assertEqual(transport.calls,2)
        self.assertEqual(sleeper.call_count,1)
        self.assertGreaterEqual(float(sleeper.call_args.args[0]),2.25)
        self.assertTrue(any("[RATE LIMIT BACKOFF]" in x for x in progress))

    def test_04_missing_retry_after_uses_bounded_fallback(self):
        success=object()
        transport=SequenceTransport([ProtoOAErrorRes(),success])
        with tempfile.TemporaryDirectory() as td, patch.object(uf.time,"sleep") as sleeper:
            runner=self.runner(Path(td),transport)
            self.assertIs(runner._send(self.request(),historical=True,retries=1),success)
        self.assertEqual(float(sleeper.call_args.args[0]),uf.RATE_LIMIT_FALLBACK_SECONDS)

    def test_05_non_rate_api_error_remains_fail_closed(self):
        transport=SequenceTransport([ProtoOAErrorRes(code="INVALID_REQUEST")])
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            with self.assertRaises(uf.ImplementationInvalid):
                runner._send(self.request(),historical=True,retries=1)

    def test_06_real_v4_failure_is_non_economic_and_does_not_change_accounting(self):
        ev=json.loads((ROOT/"evidence"/"REAL_ANDROID_ULTRA_FAST_V4_RATE_LIMIT_FAILURE_V1.json").read_text())
        state=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertEqual(ev["failure"]["classification"],"IMPLEMENTATION_RATE_LIMIT_HANDLING_FAILURE")
        self.assertFalse(ev["failure"]["economic_outcome"])
        self.assertFalse(ev["failure"]["v2_attempt_consumed"])
        self.assertEqual(state["v2_search_budget"],84)
        self.assertEqual(state["v2_attempts_used"],6)
        self.assertEqual(state["v2_search_budget_remaining"],78)

    def test_07_v5_correction_preserves_v4_plan_and_frozen_discovery_law(self):
        corr=json.loads((ROOT/"data"/"COMPETITION_ANDROID_HISTORICAL_RATE_LIMIT_CORRECTION_V1.json").read_text())
        frontier=json.loads((ROOT/"discovery"/"COMPETITION_FRONTIER_WAVE_01_V7.json").read_text())
        self.assertEqual(corr["preserved"]["plan_sha256"],self.plan["plan_sha256"])
        self.assertTrue(corr["preserved"]["friction_thresholds_unchanged"])
        self.assertTrue(corr["preserved"]["shortlist_unchanged"])
        self.assertEqual(frontier["automatic_selection"]["capture_plan"],"data/COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json")
        self.assertEqual(frontier["structural_shortlist"],self.plan["shortlist"])
        self.assertFalse(frontier["runtime_integrity"]["rate_limit_error_is_market_failure"])

    def test_08_v5_package_and_output_supersede_v4_runtime_only(self):
        build=(ROOT/"tools"/"build_competition_ultra_fast_capture_package.py").read_text()
        self.assertIn("MXM_COMPETITION_ULTRA_FAST_CAPTURE_PACKAGE_V6.zip",build)
        self.assertIn("COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json",build)
        self.assertEqual(uf.OUTPUT_FILENAME,"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6.zip")
        self.assertEqual(uf.CHECKPOINT_SCHEMA,"mxm.greenfield.v2.ultra-fast-friction-checkpoint.v5")


if __name__=="__main__":
    unittest.main()
