import copy
import json
import tempfile
import unittest
from pathlib import Path

import competition.ultra_fast_capture as uf
from competition.ultra_fast_capture import ImplementationInvalid
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbar

ROOT=Path(__file__).resolve().parents[1]
uf.MIN_INTERVAL=0.0


def bar(open_ms, low=100000):
    return ProtoOATrendbar(
        volume=10,low=low,deltaOpen=0,deltaHigh=20,deltaClose=10,
        utcTimestampInMinutes=int(open_ms//60000),
    )


class Response:
    def __init__(self,bars):
        self.trendbar=list(bars)


class SequenceTransport:
    def __init__(self,pages):
        self.pages=[list(x) for x in pages]
        self.calls=[]
        self.connected=True
    def connect(self): self.connected=True
    def close(self): self.connected=False
    def request(self,req,timeout=60):
        if type(req).__name__!="ProtoOAGetTrendbarsReq":
            raise AssertionError(type(req).__name__)
        self.calls.append((int(req.fromTimestamp),int(req.toTimestamp),int(req.count)))
        if not self.pages:
            raise AssertionError("unexpected extra request")
        return Response(self.pages.pop(0))


class StageALowerBoundaryCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json").read_text())
        cls.protocol=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json").read_text())
        cls.start=uf._ms(uf._utc(cls.plan["stage_a_interval"]["start_utc"]))
        cls.end=uf._ms(uf._utc(cls.plan["stage_a_interval"]["end_utc"]))

    def candidate(self):
        return copy.deepcopy(next(x for x in self.plan["shortlist"] if x["broker_symbol"]=="USDJPY"))

    def runner(self,root,transport):
        return uf.UltraFastCaptureRunner(
            plan=copy.deepcopy(self.plan),protocol=copy.deepcopy(self.protocol),
            client_id="x",client_secret="secret",access_token="token",
            config={},repo_root=root,transport=transport,progress=lambda *_:None,
        )

    def test_01_terminal_count_backfill_below_from_is_clipped_and_proves_exhaustion(self):
        in_range=[bar(self.start+i*300000) for i in range(5500)]
        old=[bar(self.start-(i+1)*300000) for i in range(100)]
        transport=SequenceTransport([in_range[-5000:], old+in_range[:500]])
        with tempfile.TemporaryDirectory() as td:
            rows,meta=self.runner(Path(td),transport)._stage_rows(1,self.candidate(),{"digits":5})
        self.assertEqual(len(rows),5500)
        self.assertEqual(meta["completion_reason"],"FROM_BOUNDARY_REACHED")
        self.assertTrue(meta["request_interval_exhausted"])
        self.assertEqual(meta["lower_boundary_overfetch_bars"],100)
        self.assertEqual(meta["page_log"][1]["below_requested_start_bars"],100)
        self.assertEqual(len(transport.calls),2)

    def test_02_new_bar_above_requested_page_upper_boundary_remains_fail_closed(self):
        transport=SequenceTransport([[bar(self.end+60000)]])
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ImplementationInvalid,"above requested page upper boundary"):
                self.runner(Path(td),transport)._stage_rows(1,self.candidate(),{"digits":5})

    def test_03_v6_preserves_v5_checkpoint_schema_and_directory_for_reuse(self):
        self.assertEqual(uf.CHECKPOINT_SCHEMA,"mxm.greenfield.v2.ultra-fast-friction-checkpoint.v5")
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),SequenceTransport([]))
            self.assertTrue(str(runner.checkpoint_dir).endswith("MXM_COMPETITION_ULTRA_FAST_FRICTION_CHECKPOINT_V5"))

    def test_04_v5_failure_is_non_economic_and_v6_does_not_change_accounting(self):
        ev=json.loads((ROOT/"evidence"/"REAL_ANDROID_ULTRA_FAST_V5_STAGE_A_BOUNDARY_FAILURE_V1.json").read_text())
        state=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertFalse(ev["failure"]["economic_outcome"])
        self.assertFalse(ev["failure"]["v2_attempt_consumed"])
        self.assertTrue(ev["progress_before_failure"]["checkpoint_saved"])
        self.assertEqual(ev["progress_before_failure"]["selector_initial_admitted"],"10/12")
        self.assertEqual(state["v2_attempts_used"],8)
        self.assertEqual(state["v2_search_budget_remaining"],76)
        self.assertFalse(state["protected_evidence_opened"])

    def test_05_v6_frontier_keeps_frozen_v4_plan_and_32_shortlist(self):
        f=json.loads((ROOT/"discovery"/"COMPETITION_FRONTIER_WAVE_01_V8.json").read_text())
        self.assertEqual(f["automatic_selection"]["capture_plan"],"data/COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json")
        self.assertEqual(f["structural_shortlist"],self.plan["shortlist"])
        self.assertEqual(f["identity_accounting"]["economic_identities_opened"],0)
        self.assertEqual(f["identity_accounting"]["v2_attempts_consumed"],0)

    def test_06_v6_package_and_output_are_active_runtime_only_successors(self):
        build=(ROOT/"tools"/"build_competition_ultra_fast_capture_package.py").read_text()
        self.assertIn("MXM_COMPETITION_ULTRA_FAST_CAPTURE_PACKAGE_V6.zip",build)
        self.assertIn("COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json",build)
        self.assertEqual(uf.OUTPUT_FILENAME,"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6.zip")


if __name__=="__main__":
    unittest.main()
