import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import competition.ultra_fast_capture as uf
from competition.ultra_fast_capture import (
    CheckpointInvalid,
    ImplementationInvalid,
    STAGE_COMPLETION_REASONS,
    _trendbar_has_more,
    _write_checksums,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAGetTrendbarsRes
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbar

ROOT=Path(__file__).resolve().parents[1]
uf.MIN_INTERVAL=0.0


def make_bar(open_ms, *, low=100000, close_delta=10):
    return ProtoOATrendbar(
        volume=10,
        low=low,
        deltaOpen=0,
        deltaHigh=20,
        deltaClose=close_delta,
        utcTimestampInMinutes=int(open_ms//60000),
    )


class NoHasMoreResponse:
    def __init__(self, bars):
        self.trendbar=list(bars)


class HasMoreResponse:
    def __init__(self, bars, has_more):
        self.trendbar=list(bars)
        self.hasMore=bool(has_more)


class DatasetTransport:
    def __init__(self, bars, *, expose_has_more=False):
        self.bars=list(bars)
        self.expose_has_more=expose_has_more
        self.calls=[]
        self.connected=False

    def connect(self): self.connected=True
    def close(self): self.connected=False

    def request(self, req, timeout=60):
        if type(req).__name__!="ProtoOAGetTrendbarsReq":
            raise AssertionError(type(req).__name__)
        self.calls.append((int(req.fromTimestamp),int(req.toTimestamp),int(req.count)))
        eligible=[
            b for b in self.bars
            if int(req.fromTimestamp)<=int(b.utcTimestampInMinutes)*60000<=int(req.toTimestamp)
        ]
        eligible.sort(key=lambda b:int(b.utcTimestampInMinutes))
        count=int(req.count)
        page=eligible[-count:]
        if self.expose_has_more:
            return HasMoreResponse(page,len(eligible)>count)
        return NoHasMoreResponse(page)


class StuckTransport(DatasetTransport):
    def request(self, req, timeout=60):
        self.calls.append((int(req.fromTimestamp),int(req.toTimestamp),int(req.count)))
        count=int(req.count)
        page=sorted(self.bars,key=lambda b:int(b.utcTimestampInMinutes))[-count:]
        return NoHasMoreResponse(page)


class TrendbarPaginationCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json").read_text())
        cls.protocol=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json").read_text())
        cls.start_ms=uf._ms(uf._utc(cls.plan["stage_a_interval"]["start_utc"]))

    def candidate(self):
        return copy.deepcopy(next(x for x in self.plan["shortlist"] if x["broker_symbol"]=="EURUSD"))

    def full_symbol(self):
        return {"digits":5}

    def dataset(self,n,*,offset_minutes=0):
        base=self.start_ms+offset_minutes*60_000
        return [make_bar(base+i*5*60_000) for i in range(n)]

    def runner(self,root,transport):
        return uf.UltraFastCaptureRunner(
            plan=copy.deepcopy(self.plan),
            protocol=copy.deepcopy(self.protocol),
            client_id="x",client_secret="secret",access_token="token",
            config={},repo_root=root,transport=transport,progress=lambda *_:None,
        )

    def test_01_packaged_proto_descriptor_compatibility_is_introspected(self):
        exposed="hasMore" in ProtoOAGetTrendbarsRes.DESCRIPTOR.fields_by_name
        response=ProtoOAGetTrendbarsRes()
        runtime_exposed,value=_trendbar_has_more(response)
        self.assertEqual(runtime_exposed,exposed)
        self.assertIn(exposed,(True,False))
        if not exposed:
            self.assertIsNone(value)

    def test_02_no_has_more_over_5000_bars_requires_multiple_pages_and_completes(self):
        bars=self.dataset(6000)
        transport=DatasetTransport(bars,expose_has_more=False)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            rows,meta=runner._stage_rows(1,self.candidate(),self.full_symbol())
        self.assertEqual(len(rows),6000)
        self.assertEqual(meta["pages"],2)
        self.assertFalse(meta["response_schema_exposed_has_more"])
        self.assertTrue(meta["request_interval_exhausted"])
        self.assertIn(meta["completion_reason"],STAGE_COMPLETION_REASONS)
        self.assertNotEqual(meta["normalized_unique_completed_bars"],5000)

    def test_03_no_has_more_over_10000_bars_uses_at_least_three_requests(self):
        bars=self.dataset(11050)
        transport=DatasetTransport(bars,expose_has_more=False)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            rows,meta=runner._stage_rows(1,self.candidate(),self.full_symbol())
        self.assertEqual(len(rows),11050)
        self.assertGreaterEqual(meta["pages"],3)
        self.assertEqual(meta["full_pages"],2)
        self.assertTrue(meta["request_interval_exhausted"])

    def test_04_final_short_page_proves_interval_exhaustion_without_has_more(self):
        bars=self.dataset(6000,offset_minutes=24*60)
        transport=DatasetTransport(bars,expose_has_more=False)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            rows,meta=runner._stage_rows(1,self.candidate(),self.full_symbol())
        self.assertEqual(len(rows),6000)
        self.assertEqual(meta["completion_reason"],"SHORT_PAGE_INTERVAL_EXHAUSTED")
        self.assertEqual(meta["full_pages"],1)
        self.assertEqual(meta["short_pages"],1)

    def test_05_exactly_full_terminal_page_gets_one_more_empty_proof(self):
        bars=self.dataset(10000,offset_minutes=24*60)
        transport=DatasetTransport(bars,expose_has_more=False)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            rows,meta=runner._stage_rows(1,self.candidate(),self.full_symbol())
        self.assertEqual(len(rows),10000)
        self.assertEqual(meta["pages"],3)
        self.assertEqual(meta["full_pages"],2)
        self.assertEqual(meta["empty_pages"],1)
        self.assertEqual(meta["completion_reason"],"EMPTY_FINAL_PAGE_AFTER_FULL_PAGE")

    def test_06_non_advancing_or_out_of_boundary_page_is_implementation_invalid(self):
        bars=self.dataset(5000,offset_minutes=24*60)
        transport=StuckTransport(bars)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            with self.assertRaises(ImplementationInvalid):
                runner._stage_rows(1,self.candidate(),self.full_symbol())

    def test_07_identical_duplicate_is_deduplicated_and_counted(self):
        bars=self.dataset(100)
        bars.insert(50,copy.deepcopy(bars[50]))
        transport=DatasetTransport(bars,expose_has_more=False)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            rows,meta=runner._stage_rows(1,self.candidate(),self.full_symbol())
        self.assertEqual(len(rows),100)
        self.assertEqual(meta["identical_duplicate_count"],1)
        self.assertEqual(meta["conflicts"],0)

    def test_08_conflicting_duplicate_is_implementation_invalid(self):
        bars=self.dataset(100)
        conflict=make_bar(int(bars[50].utcTimestampInMinutes)*60_000,low=100500,close_delta=5)
        bars.insert(50,conflict)
        transport=DatasetTransport(bars,expose_has_more=False)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            with self.assertRaises(ImplementationInvalid):
                runner._stage_rows(1,self.candidate(),self.full_symbol())

    def test_09_current_official_style_has_more_still_works(self):
        bars=self.dataset(6000,offset_minutes=24*60)
        transport=DatasetTransport(bars,expose_has_more=True)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            rows,meta=runner._stage_rows(1,self.candidate(),self.full_symbol())
        self.assertEqual(len(rows),6000)
        self.assertTrue(meta["response_schema_exposed_has_more"])
        self.assertEqual(meta["pages"],2)
        self.assertEqual(meta["completion_reason"],"HAS_MORE_FALSE")

    def test_10_one_5000_page_is_never_complete_merely_because_minimum_floor_is_500(self):
        bars=self.dataset(6000)
        transport=DatasetTransport(bars,expose_has_more=False)
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),transport)
            rows,meta=runner._stage_rows(1,self.candidate(),self.full_symbol())
        self.assertGreater(len(rows),5000)
        self.assertGreater(meta["pages"],1)
        self.assertTrue(meta["request_interval_exhausted"])
        self.assertEqual(self.plan["capture_law"]["min_stage_a_m5_rows"],500)

    def _checkpoint_payload(self,runner):
        friction=[]
        for i,candidate in enumerate(self.plan["shortlist"]):
            x=copy.deepcopy(candidate)
            x.update({
                "friction_state":"FRICTION_PASS" if i==0 else "FRICTION_FAIL",
                "cost_confidence_state":"FULL_FRICTION_RESOLVED",
                "movement_to_window_balanced_p75_effective_friction":5.0 if i==0 else 0.5,
                "p75_window_p95_effective_friction_over_range":0.2,
                "planned_windows":1,
                "window_summaries":[],
            })
            friction.append(x)
        initial=[friction[0]]
        conversion={
            "schema":"mxm.greenfield.v2.ultra-fast-historical-conversion-summary.v1",
            "authority":"CTRADER_PROTO_OA_SYMBOLS_FOR_CONVERSION",
            "chain_count":0,"window_rate_count":0,"chains":[],"window_rates":[],
            "raw_conversion_ticks_transferred":False,
            "current_or_future_rate_substitution":False,
        }
        return friction,conversion,initial,{"FX":[]}

    def test_11_friction_checkpoint_persists_before_stage_and_reuses_with_exact_bindings(self):
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),DatasetTransport([]))
            friction,conversion,initial,alternates=self._checkpoint_payload(runner)
            runner._persist_friction_checkpoint(friction,conversion,initial,alternates)
            self.assertTrue((runner.checkpoint_dir/"CHECKSUMS.sha256").is_file())
            loaded=runner._load_friction_checkpoint()
            self.assertIsNotNone(loaded)
            lf,lc,li,la=loaded
            self.assertEqual(len(lf),32)
            self.assertEqual(li[0]["broker_symbol"],initial[0]["broker_symbol"])
            self.assertFalse(lc["raw_conversion_ticks_transferred"])

    def test_12_checkpoint_binding_mismatch_is_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),DatasetTransport([]))
            friction,conversion,initial,alternates=self._checkpoint_payload(runner)
            runner._persist_friction_checkpoint(friction,conversion,initial,alternates)
            path=runner.checkpoint_dir/"checkpoint_manifest.json"
            manifest=json.loads(path.read_text())
            manifest["binding"]["account_fingerprint_sha256"]="wrong"
            path.write_text(json.dumps(manifest,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
            _write_checksums(runner.checkpoint_dir)
            with self.assertRaises(CheckpointInvalid):
                runner._load_friction_checkpoint()

    def test_13_checkpoint_checksum_corruption_is_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),DatasetTransport([]))
            friction,conversion,initial,alternates=self._checkpoint_payload(runner)
            runner._persist_friction_checkpoint(friction,conversion,initial,alternates)
            path=runner.checkpoint_dir/"friction_summary.json"
            path.write_text(path.read_text()+" ",encoding="utf-8")
            with self.assertRaises(CheckpointInvalid):
                runner._load_friction_checkpoint()

    def test_14_checkpoint_does_not_consume_attempt_or_open_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            runner=self.runner(Path(td),DatasetTransport([]))
            friction,conversion,initial,alternates=self._checkpoint_payload(runner)
            runner._persist_friction_checkpoint(friction,conversion,initial,alternates)
            manifest=json.loads((runner.checkpoint_dir/"checkpoint_manifest.json").read_text())
            self.assertEqual(manifest["economic_outcomes_opened"],0)
            self.assertEqual(manifest["v2_attempts_consumed"],0)

    def test_15_failed_v3_evidence_is_non_economic(self):
        ev=json.loads((ROOT/"evidence"/"REAL_ANDROID_ULTRA_FAST_V3_TRENDBAR_PAGINATION_FAILURE_V1.json").read_text())
        self.assertEqual(ev["failure"]["classification"],"IMPLEMENTATION_PROTOCOL_COMPATIBILITY_FAILURE")
        self.assertFalse(ev["failure"]["economic_outcome"])
        self.assertFalse(ev["failure"]["v2_attempt_consumed"])
        self.assertFalse(ev["console_only_friction_observation"]["threshold_retuning_permitted"])

    def test_16_capture_non_economic_history_and_current_accounting_reconcile(self):
        state=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertEqual(state["v2_search_budget"],84)
        self.assertEqual(state["v2_evaluated_identities"],8)
        self.assertEqual(state["v2_attempts_used"],8)
        self.assertEqual(state["v2_search_budget"]-state["v2_attempts_used"],76)
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])


if __name__=="__main__":
    unittest.main()
