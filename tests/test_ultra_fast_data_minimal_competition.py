import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import competition.ultra_fast_capture as uf
from competition.friction_costs import (
    COMMISSION_CONVERSION_UNRESOLVED,
    FULL_FRICTION_RESOLVED,
    type_aware_roundtrip_commission,
)
from competition.pydroid_ultra_fast_launcher import local_preflight
from competition.ultra_fast_capture import (
    EXPECTED_PLAN_SHA,
    ImplementationInvalid,
    _write_checksums,
    friction_windows,
    margin_pct_eur200,
    qualify_friction,
    select_stage_a,
    validate_capture_postconditions,
    validate_plan,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbar

ROOT=Path(__file__).resolve().parents[1]
uf.MIN_INTERVAL=0.0


def bar_at(ms, *, low=100000, high_delta=100, close_delta=50, volume=20):
    return ProtoOATrendbar(
        volume=volume,
        low=low,
        deltaOpen=0,
        deltaClose=close_delta,
        deltaHigh=high_delta,
        utcTimestampInMinutes=int(ms//60000),
    )


class FakeMarketTransport:
    def __init__(self, plan, *, spread_raw=10, stage_paginated=True):
        self.plan=plan
        self.spread_raw=spread_raw
        self.stage_paginated=stage_paginated
        self.connected=False
        self.calls=[]

    def connect(self):
        self.connected=True

    def close(self):
        self.connected=False

    def request(self, req, timeout=60):
        self.calls.append(type(req).__name__)
        name=type(req).__name__
        if name=="ProtoOAGetTickDataReq":
            raw=100000 if int(req.type)==1 else 100000+self.spread_raw
            newest=int(req.toTimestamp)-1000
            ticks=[SimpleNamespace(timestamp=newest,tick=raw)]
            ticks.extend(SimpleNamespace(timestamp=-1000,tick=0) for _ in range(29))
            return SimpleNamespace(tickData=ticks,hasMore=False)
        if name=="ProtoOAGetTrendbarsReq":
            if int(req.count)==100:
                start=int(req.fromTimestamp)
                return SimpleNamespace(
                    trendbar=[bar_at(start),bar_at(start+5*60*1000)],
                    hasMore=False,
                )
            start_ms=int(uf._ms(uf._utc(self.plan["stage_a_interval"]["start_utc"])))
            rows=[bar_at(start_ms+i*5*60*1000) for i in range(600)]
            if not self.stage_paginated:
                return SimpleNamespace(trendbar=rows,hasMore=False)
            cutoff=start_ms+300*5*60*1000
            if int(req.toTimestamp)>=cutoff:
                return SimpleNamespace(trendbar=rows[300:],hasMore=True)
            return SimpleNamespace(trendbar=rows[:300],hasMore=False)
        raise AssertionError(f"unexpected fake request {name}")


class UltraFastRuntimeIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V2.json").read_text())
        cls.protocol=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V2.json").read_text())

    def make_runner(self, tmp, *, spread_raw=10, one_window=True):
        plan=copy.deepcopy(self.plan)
        protocol=copy.deepcopy(self.protocol)
        if one_window:
            protocol["friction_screen"]["profiles"]["GLOBAL_24X5"]={
                "sample_dates":["2026-09-03"],
                "utc_windows":[{"label":"EUROPE","start":"08:00","end":"08:10"}],
            }
        transport=FakeMarketTransport(plan,spread_raw=spread_raw)
        runner=uf.UltraFastCaptureRunner(
            plan=plan,protocol=protocol,client_id="x",client_secret="secret",
            access_token="token",config={},repo_root=tmp,transport=transport,progress=lambda *_:None,
        )
        return runner,plan,protocol,transport

    def eurusd_context(self, *, commission_type=1, commission_rate_raw=5_000_000_000, min_raw=0, min_type=1):
        candidate=copy.deepcopy(next(x for x in self.plan["shortlist"] if x["broker_symbol"]=="EURUSD"))
        full={
            "digits":5,"minVolume":100000,"lotSize":10000000,
            "commissionType":commission_type,
            "preciseTradingCommissionRate":commission_rate_raw,
            "preciseMinCommission":min_raw,
            "minCommissionType":min_type,
            "minCommissionAsset":"USD",
            "pnlConversionFeeRate":0,
        }
        light={"symbolId":1,"symbolName":"EURUSD","baseAssetId":10,"quoteAssetId":20,"enabled":True}
        assets={"10":"EUR","20":"USD"}
        return candidate,full,light,assets

    def test_01_plan_and_factor100_regressions(self):
        self.assertTrue(validate_plan(self.plan,self.protocol))
        self.assertEqual(self.plan["plan_sha256"],EXPECTED_PLAN_SHA)
        self.assertEqual(margin_pct_eur200(33.33),16.665)
        self.assertEqual(margin_pct_eur200(29.05),14.525)
        self.assertEqual(margin_pct_eur200(2.53),1.265)
        self.assertEqual(margin_pct_eur200(0.14),0.07)

    def test_02_real_friction_path_executes_canonical_normalize_m5_signature(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,transport=self.make_runner(Path(td))
            candidate,full,light,assets=self.eurusd_context()
            result=runner._friction(1,candidate,full,light,assets)
            self.assertGreater(result["quote_state_count"],20)
            self.assertIsNotNone(result["median_spread"])
            self.assertIsNotNone(result["median_m5_range"])
            self.assertEqual(result["cost_confidence_state"],FULL_FRICTION_RESOLVED)
            self.assertEqual(result["friction_state"],"FRICTION_PASS")
            self.assertIn("ProtoOAGetTrendbarsReq",transport.calls)

    def test_03_commission_type_1_usd_per_million_scaling(self):
        _,full,light,assets=self.eurusd_context(commission_type=1,commission_rate_raw=5_000_000_000)
        c=type_aware_roundtrip_commission(full,light,assets,mid=1.0,min_volume_cents=100000)
        self.assertEqual(c["commission_type"],"USD_PER_MILLION_USD")
        self.assertEqual(c["trading_commission_scale"],100_000_000)
        self.assertAlmostEqual(c["roundtrip_commission_price_equivalent"],0.0001,places=12)

    def test_04_commission_types_2_3_4_have_distinct_dimensions_and_scales(self):
        assets={"1":"USD","2":"JPY","3":"ABC","4":"EUR"}
        light_usd={"baseAssetId":1,"quoteAssetId":2}
        c2=type_aware_roundtrip_commission(
            {"lotSize":10000,"commissionType":2,"preciseTradingCommissionRate":1_500_000_000,"preciseMinCommission":0},
            light_usd,assets,mid=150.0,min_volume_cents=10000,
        )
        self.assertEqual(c2["commission_type"],"USD_PER_LOT")
        self.assertEqual(c2["trading_commission_scale"],100_000_000)
        self.assertAlmostEqual(c2["roundtrip_commission_price_equivalent"],45.0,places=9)

        light_pct={"baseAssetId":3,"quoteAssetId":4}
        c3=type_aware_roundtrip_commission(
            {"lotSize":10000,"commissionType":3,"preciseTradingCommissionRate":500,"preciseMinCommission":0},
            light_pct,assets,mid=10.0,min_volume_cents=10000,
        )
        self.assertEqual(c3["commission_type"],"PERCENTAGE_OF_VALUE")
        self.assertEqual(c3["trading_commission_scale"],100_000)
        self.assertAlmostEqual(c3["roundtrip_commission_price_equivalent"],0.001,places=12)

        c4=type_aware_roundtrip_commission(
            {"lotSize":10000,"commissionType":4,"preciseTradingCommissionRate":1_500_000_000,"preciseMinCommission":0},
            light_pct,assets,mid=10.0,min_volume_cents=10000,
        )
        self.assertEqual(c4["commission_type"],"QUOTE_CCY_PER_LOT")
        self.assertEqual(c4["trading_commission_scale"],100_000_000)
        self.assertAlmostEqual(c4["roundtrip_commission_price_equivalent"],0.3,places=12)

    def test_05_minimum_commission_type_is_honored(self):
        _,full,light,assets=self.eurusd_context(
            commission_type=4,commission_rate_raw=0,min_raw=200_000_000,min_type=2
        )
        c=type_aware_roundtrip_commission(full,light,assets,mid=1.0,min_volume_cents=100000)
        self.assertEqual(c["min_commission_type"],"QUOTE_CURRENCY")
        self.assertAlmostEqual(c["roundtrip_commission_price_equivalent"],0.004,places=12)

        full2=dict(full,minCommissionType=1,minCommissionAsset="USD")
        c2=type_aware_roundtrip_commission(full2,light,assets,mid=1.0,min_volume_cents=100000)
        self.assertEqual(c2["min_commission_type"],"CURRENCY")
        self.assertAlmostEqual(c2["roundtrip_commission_price_equivalent"],0.004,places=12)

    def test_06_unsupported_or_unconvertible_material_commission_is_explicitly_unresolved(self):
        _,full,light,assets=self.eurusd_context(commission_type=99,commission_rate_raw=100_000_000)
        c=type_aware_roundtrip_commission(full,light,assets,mid=1.0,min_volume_cents=100000)
        self.assertEqual(c["cost_confidence_state"],COMMISSION_CONVERSION_UNRESOLVED)
        metrics={
            "cost_confidence_state":c["cost_confidence_state"],
            "two_sided_window_coverage":1.0,"quote_state_count":100,"median_m5_range":1.0,
            "p75_spread_over_median_range":0.01,"p95_spread_over_median_range":0.02,
            "p75_effective_friction_over_median_range":None,"p95_effective_friction_over_median_range":None,
            "median_spread_over_mid":0.001,
        }
        self.assertEqual(qualify_friction(metrics,self.protocol["friction_screen"]["qualification"]),"FRICTION_UNRESOLVED")

    def test_07_high_commission_can_make_valid_market_friction_fail(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,_=self.make_runner(Path(td))
            candidate,full,light,assets=self.eurusd_context(
                commission_type=4,commission_rate_raw=5_000_000_000
            )
            result=runner._friction(1,candidate,full,light,assets)
            self.assertGreater(result["quote_state_count"],20)
            self.assertEqual(result["cost_confidence_state"],FULL_FRICTION_RESOLVED)
            self.assertEqual(result["friction_state"],"FRICTION_FAIL")

    def test_08_programming_contract_error_cannot_become_friction_fail(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,_=self.make_runner(Path(td))
            candidate,full,light,assets=self.eurusd_context()
            def broken(*args,**kwargs):
                raise TypeError("normalize contract defect")
            runner._sample_bars=broken
            with self.assertRaises(TypeError):
                runner._friction(1,candidate,full,light,assets)

    def test_09_stage_rows_uses_real_canonical_normalizer_and_paginates(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,transport=self.make_runner(Path(td),one_window=False)
            candidate,full,_,_=self.eurusd_context()
            rows=runner._stage_rows(1,candidate,full)
            self.assertEqual(len(rows),600)
            self.assertLess(rows[0]["time_utc"],rows[-1]["time_utc"])
            self.assertGreaterEqual(transport.calls.count("ProtoOAGetTrendbarsReq"),2)

    def test_10_selected_market_writes_real_integrity_checked_stage_a_csv(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);runner,_,_,_=self.make_runner(root,one_window=False)
            runner.bundle.mkdir(parents=True,exist_ok=True)
            candidate,full,_,_=self.eurusd_context()
            rows=runner._stage_rows(1,candidate,full)
            record=runner._write_rows(candidate,rows)
            path=runner.bundle/record["file"]
            self.assertTrue(path.is_file())
            self.assertEqual(record["row_count"],600)
            self.assertEqual(record["sha256"],uf._sha(path))

    def test_11_selector_never_admits_unresolved_commission(self):
        base=[]
        for i,c in enumerate(self.plan["shortlist"][:12]):
            x=copy.deepcopy(c)
            x.update({
                "friction_state":"FRICTION_PASS","cost_confidence_state":FULL_FRICTION_RESOLVED,
                "movement_to_effective_p75_friction":10-i/10,
                "p95_effective_friction_over_median_range":0.2,
            })
            base.append(x)
        bad=copy.deepcopy(self.plan["shortlist"][12])
        bad.update({
            "friction_state":"FRICTION_PASS","cost_confidence_state":COMMISSION_CONVERSION_UNRESOLVED,
            "movement_to_effective_p75_friction":999,
            "p95_effective_friction_over_median_range":0.01,
        })
        chosen,_=select_stage_a(base+[bad],self.protocol["selection_law"])
        self.assertNotIn(bad["broker_symbol"],[x["broker_symbol"] for x in chosen])

    def _synthetic_postcondition_fixture(self,root):
        runner,plan,protocol,_=self.make_runner(root,one_window=False)
        runner.bundle.mkdir(parents=True,exist_ok=True)
        candidate,full,_,_=self.eurusd_context()
        rows=runner._stage_rows(1,candidate,full)
        record=runner._write_rows(candidate,rows)
        friction=[]
        for x in plan["shortlist"]:
            y=copy.deepcopy(x)
            y.update({
                "cost_confidence_state":FULL_FRICTION_RESOLVED,
                "friction_state":"FRICTION_FAIL",
                "movement_to_effective_p75_friction":1.0,
                "p95_effective_friction_over_median_range":0.8,
            })
            friction.append(y)
        friction[0]["friction_state"]="FRICTION_PASS"
        friction[0]["movement_to_effective_p75_friction"]=5.0
        selection={"final_selected":[candidate["broker_symbol"]]}
        manifest={
            "status":"COMPACT_FRICTION_AND_STAGE_A_DEVELOPMENT_CAPTURE_COMPLETE",
            "stage_a_selected_count":1,"friction_shortlist_count":32,
            "raw_ticks_transferred":False,"orders_placed":False,"account_mutation":False,
            "economic_outcomes_opened":0,"v2_attempts_consumed":0,
        }
        return runner,plan,friction,selection,[record],manifest

    def test_12_manifest_selection_series_and_checksums_reconcile(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            runner,plan,friction,selection,series,manifest=self._synthetic_postcondition_fixture(root)
            (runner.bundle/"friction_summary.json").write_text(json.dumps({"results":friction}),encoding="utf-8")
            (runner.bundle/"selection.json").write_text(json.dumps(selection),encoding="utf-8")
            (runner.bundle/"capture_manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
            self.assertTrue(validate_capture_postconditions(
                plan=plan,friction_results=friction,selection=selection,series=series,
                bundle=runner.bundle,manifest=manifest,verify_checksums=False,
            ))
            _write_checksums(runner.bundle)
            self.assertTrue(validate_capture_postconditions(
                plan=plan,friction_results=friction,selection=selection,series=series,
                bundle=runner.bundle,manifest=manifest,verify_checksums=True,
            ))

    def test_13_systemic_unresolved_capture_cannot_be_marked_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);runner,plan,_,_=self.make_runner(root)
            friction=[]
            for x in plan["shortlist"]:
                y=copy.deepcopy(x)
                y.update({"cost_confidence_state":"FRICTION_UNRESOLVED","friction_state":"FRICTION_UNRESOLVED"})
                friction.append(y)
            manifest={
                "status":"FRICTION_QUALIFICATION_COMPLETE_NO_STAGE_A_MARKETS",
                "stage_a_selected_count":0,"friction_shortlist_count":32,
                "raw_ticks_transferred":False,"orders_placed":False,"account_mutation":False,
                "economic_outcomes_opened":0,"v2_attempts_consumed":0,
            }
            with self.assertRaises(ImplementationInvalid):
                validate_capture_postconditions(
                    plan=plan,friction_results=friction,selection={"final_selected":[]},series=[],
                    bundle=runner.bundle,manifest=manifest,verify_checksums=False,
                )

    def test_14_sparse_valid_evidence_is_unresolved_not_friction_fail(self):
        rules=self.protocol["friction_screen"]["qualification"]
        metrics={
            "cost_confidence_state":FULL_FRICTION_RESOLVED,
            "two_sided_window_coverage":0.1,"quote_state_count":2,"median_m5_range":1.0,
            "p75_spread_over_median_range":0.1,"p95_spread_over_median_range":0.2,
            "p75_effective_friction_over_median_range":0.1,"p95_effective_friction_over_median_range":0.2,
            "median_spread_over_mid":0.001,
        }
        self.assertEqual(qualify_friction(metrics,rules),"FRICTION_UNRESOLVED")

    def test_15_pydroid_preflight_executes_v2_authorities_without_network(self):
        p=local_preflight()
        self.assertEqual(p["plan_sha256"],EXPECTED_PLAN_SHA)
        self.assertEqual(p["shortlist"],32)
        self.assertEqual(p["max_stage_a_markets"],12)
        self.assertEqual(p["global_windows"],20)
        self.assertEqual(p["crypto_windows"],28)
        self.assertEqual(p["regional_windows"],8)
        self.assertFalse(p["raw_ticks_transferred"])
        self.assertFalse(p["network_connection_attempted"])
        self.assertFalse(p["credentials_used"])
        self.assertFalse(p["orders_permitted"])
        self.assertFalse(p["account_mutation_permitted"])
        self.assertFalse(p["economic_outcomes_opened"])

    def test_16_accounting_and_protection_remain_unchanged(self):
        s=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertEqual(s["v2_search_budget"],84)
        self.assertEqual(s["v2_evaluated_identities"],2)
        self.assertEqual(s["v2_attempts_used"],2)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])


if __name__=="__main__":
    unittest.main()
