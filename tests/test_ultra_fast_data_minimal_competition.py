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
    ConversionUnavailable,
    ImplementationInvalid,
    _write_checksums,
    friction_windows,
    margin_pct_eur200,
    qualify_friction,
    select_stage_a,
    validate_capture_postconditions,
    validate_plan,
)
from m6.cost_evidence import CausalQuoteState, DecodedTick
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOALightSymbol, ProtoOATrendbar

ROOT=Path(__file__).resolve().parents[1]
uf.MIN_INTERVAL=0.0


def bar_at(ms, *, low=100000, high_delta=100, close_delta=50, volume=20):
    return ProtoOATrendbar(
        volume=volume,low=low,deltaOpen=0,deltaClose=close_delta,deltaHigh=high_delta,
        utcTimestampInMinutes=int(ms//60000),
    )


def compressed_tick_rows(start_ms, raw_prices, *, step_ms=1000):
    chronological=[(start_ms+i*step_ms,int(raw)) for i,raw in enumerate(raw_prices)]
    newest=list(reversed(chronological))
    out=[]
    prev_ts=prev_raw=None
    for i,(ts,raw) in enumerate(newest):
        if i==0:
            out.append(SimpleNamespace(timestamp=ts,tick=raw))
        else:
            out.append(SimpleNamespace(timestamp=ts-prev_ts,tick=raw-prev_raw))
        prev_ts,prev_raw=ts,raw
    return out


def quote_states(bid, ask, *, n=30, start_ms=1_000_000):
    return [
        CausalQuoteState(
            timestamp_ms=start_ms+i*1000,bid=bid,ask=ask,
            bid_timestamp_ms=start_ms+i*1000,ask_timestamp_ms=start_ms+i*1000,
            spread=ask-bid,
        )
        for i in range(n)
    ]


class FakeMarketTransport:
    def __init__(self, plan):
        self.plan=plan;self.connected=False;self.calls=[]
        self.tick_specs={}
        self.conversion_chains={}
        self.fail_conversion_with=None

    def connect(self): self.connected=True
    def close(self): self.connected=False

    def set_ticks(self,symbol_id,bids,asks,window_start_ms):
        self.tick_specs[(symbol_id,1)]=(list(bids),window_start_ms)
        self.tick_specs[(symbol_id,2)]=(list(asks),window_start_ms)

    def request(self,req,timeout=60):
        name=type(req).__name__;self.calls.append((name,getattr(req,"symbolId",None),getattr(req,"type",None)))
        if name=="ProtoOASymbolsForConversionReq":
            if self.fail_conversion_with is not None:
                raise self.fail_conversion_with("conversion tool failure")
            chain=self.conversion_chains.get((int(req.firstAssetId),int(req.lastAssetId)),[])
            return SimpleNamespace(symbol=chain)
        if name=="ProtoOAGetTickDataReq":
            key=(int(req.symbolId),int(req.type))
            if key in self.tick_specs:
                prices,start=self.tick_specs[key]
                return SimpleNamespace(tickData=compressed_tick_rows(start,prices),hasMore=False)
            base=100000 if int(req.type)==1 else 100010
            return SimpleNamespace(tickData=compressed_tick_rows(int(req.fromTimestamp)+1000,[base]*30),hasMore=False)
        if name=="ProtoOAGetTrendbarsReq":
            if int(req.count)==100:
                start=int(req.fromTimestamp)
                return SimpleNamespace(trendbar=[bar_at(start),bar_at(start+5*60*1000)],hasMore=False)
            start_ms=int(uf._ms(uf._utc(self.plan["stage_a_interval"]["start_utc"])))
            rows=[bar_at(start_ms+i*5*60*1000) for i in range(600)]
            return SimpleNamespace(trendbar=rows,hasMore=False)
        raise AssertionError(f"unexpected fake request {name}")


class UltraFastConversionTailIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V4.json").read_text())
        cls.protocol=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json").read_text())

    def make_runner(self,tmp,*,one_window=True):
        plan=copy.deepcopy(self.plan);protocol=copy.deepcopy(self.protocol)
        if one_window:
            protocol["friction_screen"]["profiles"]["GLOBAL_24X5"]={
                "sample_dates":["2026-09-03"],
                "utc_windows":[{"label":"EUROPE","start":"08:00","end":"08:10"}],
            }
        transport=FakeMarketTransport(plan)
        runner=uf.UltraFastCaptureRunner(
            plan=plan,protocol=protocol,client_id="x",client_secret="secret",
            access_token="token",config={},repo_root=tmp,transport=transport,progress=lambda *_:None,
        )
        runner._assets={"10":"EUR","20":"USD","30":"JPY","40":"AUD","50":"MXN","60":"NOK","70":"SEK"}
        runner._asset_ids={v:k for k,v in ((10,"EUR"),(20,"USD"),(30,"JPY"),(40,"AUD"),(50,"MXN"),(60,"NOK"),(70,"SEK"))}
        runner._asset_ids={k:int(v) for k,v in runner._asset_ids.items()}
        return runner,plan,protocol,transport

    def candidate(self,name):
        return copy.deepcopy(next(x for x in self.plan["shortlist"] if x["broker_symbol"]==name))

    def full_fx(self,*,digits=5,rate=300_000_000,ctype=2,min_raw=0,min_type=1,min_asset="USD"):
        return {
            "digits":digits,"minVolume":100000,"lotSize":10000000,
            "commissionType":ctype,"preciseTradingCommissionRate":rate,
            "preciseMinCommission":min_raw,"minCommissionType":min_type,
            "minCommissionAsset":min_asset,"pnlConversionFeeRate":0,
        }

    def light(self,sid,name,base,quote):
        return {"symbolId":sid,"symbolName":name,"baseAssetId":base,"quoteAssetId":quote,"enabled":True}

    def window(self):
        return friction_windows(self.protocol,"GLOBAL_24X5")[0]

    def test_01_plan_and_factor100_regressions(self):
        self.assertTrue(validate_plan(self.plan,self.protocol))
        self.assertEqual(self.plan["plan_sha256"],EXPECTED_PLAN_SHA)
        for v,e in [(33.33,16.665),(29.05,14.525),(2.53,1.265),(0.14,0.07)]:
            self.assertEqual(margin_pct_eur200(v),e)

    def test_02_eurusd_usd_quote_commission_resolves_directly(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,_=self.make_runner(Path(td))
            light=self.light(1,"EURUSD",10,20)
            states=quote_states(1.1,1.1001)
            c=runner._commission_for_window(1,self.full_fx(),light,self.window(),states,1.10005)
            self.assertEqual(c["cost_confidence_state"],FULL_FRICTION_RESOLVED)
            self.assertAlmostEqual(c["roundtrip_commission_price_equivalent"],0.00006,places=12)
            self.assertEqual(c["conversion_evidence"],{})

    def test_03_usdjpy_usd_base_commission_resolves_from_same_window_bid(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,_=self.make_runner(Path(td))
            light=self.light(4,"USDJPY",20,30)
            states=quote_states(150.0,150.02)
            c=runner._commission_for_window(1,self.full_fx(digits=3),light,self.window(),states,150.01)
            self.assertEqual(c["cost_confidence_state"],FULL_FRICTION_RESOLVED)
            self.assertAlmostEqual(c["currency_to_quote_rates"]["USD"],150.0,places=9)
            self.assertEqual(c["conversion_evidence"]["USD_TO_QUOTE"]["method"],"TRADED_SYMBOL_BASE_TO_QUOTE_AT_BID")

    def _install_usdjpy_chain(self,transport,window):
        transport.conversion_chains[(20,30)]=[
            ProtoOALightSymbol(symbolId=4,symbolName="USDJPY",baseAssetId=20,quoteAssetId=30,enabled=True)
        ]
        start=window["from_ms"]+1000
        transport.set_ticks(4,[15000000]*30,[15001000]*30,start)

    def test_04_audjpy_cross_uses_official_same_window_conversion_chain(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,transport=self.make_runner(Path(td));w=self.window();self._install_usdjpy_chain(transport,w)
            light=self.light(11,"AUDJPY",40,30)
            states=quote_states(95.0,95.02)
            c=runner._commission_for_window(1,self.full_fx(digits=3),light,w,states,95.01)
            self.assertEqual(c["cost_confidence_state"],FULL_FRICTION_RESOLVED)
            ev=c["conversion_evidence"]["USD_TO_QUOTE"]
            self.assertEqual(ev["method"],"BROKER_NATIVE_CONVERSION_CHAIN")
            self.assertEqual(ev["first_asset"],"USD");self.assertEqual(ev["last_asset"],"JPY")
            self.assertEqual(ev["window_start_utc"],w["start_utc"]);self.assertFalse(ev["used_current_or_future_rate"])
            self.assertGreater(c["roundtrip_commission_price_equivalent"],0)

    def test_05_mxnjpy_cross_reuses_chain_and_historical_tick_cache(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,transport=self.make_runner(Path(td));w=self.window();self._install_usdjpy_chain(transport,w)
            states1=quote_states(95.0,95.02);states2=quote_states(8.0,8.02)
            c1=runner._commission_for_window(1,self.full_fx(digits=3),self.light(11,"AUDJPY",40,30),w,states1,95.01)
            c2=runner._commission_for_window(1,self.full_fx(digits=3),self.light(2778,"MXNJPY",50,30),w,states2,8.01)
            self.assertEqual(c1["cost_confidence_state"],FULL_FRICTION_RESOLVED)
            self.assertEqual(c2["cost_confidence_state"],FULL_FRICTION_RESOLVED)
            chain_calls=[x for x in transport.calls if x[0]=="ProtoOASymbolsForConversionReq"]
            usdjpy_tick_calls=[x for x in transport.calls if x[0]=="ProtoOAGetTickDataReq" and x[1]==4]
            self.assertEqual(len(chain_calls),1)
            self.assertEqual(len(usdjpy_tick_calls),2)  # one BID + one ASK total, reused across both crosses

    def test_06_genuine_missing_chain_is_unresolved_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,_=self.make_runner(Path(td));w=self.window()
            c=runner._commission_for_window(
                1,self.full_fx(digits=3),self.light(11,"AUDJPY",40,30),w,quote_states(95.0,95.02),95.01
            )
            self.assertEqual(c["cost_confidence_state"],COMMISSION_CONVERSION_UNRESOLVED)
            self.assertIsNone(c["roundtrip_commission_price_equivalent"])
            self.assertIn("USD",c["conversion_evidence"])

    def test_07_conversion_tool_failure_aborts_as_implementation_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,transport=self.make_runner(Path(td));transport.fail_conversion_with=TypeError
            with self.assertRaises(ImplementationInvalid):
                runner._commission_for_window(
                    1,self.full_fx(digits=3),self.light(11,"AUDJPY",40,30),
                    self.window(),quote_states(95.0,95.02),95.01
                )

    def test_08_commission_types_keep_type_specific_scaling(self):
        assets={"1":"USD","2":"JPY","3":"ABC","4":"EUR"}
        c2=type_aware_roundtrip_commission(
            {"lotSize":10000,"commissionType":2,"preciseTradingCommissionRate":1_500_000_000,"preciseMinCommission":0},
            {"baseAssetId":1,"quoteAssetId":2},assets,mid=150.0,min_volume_cents=10000,
            currency_to_quote_rates={"USD":150.0},
        )
        self.assertEqual(c2["trading_commission_scale"],100_000_000)
        self.assertAlmostEqual(c2["roundtrip_commission_price_equivalent"],45.0,places=9)
        c3=type_aware_roundtrip_commission(
            {"lotSize":10000,"commissionType":3,"preciseTradingCommissionRate":500,"preciseMinCommission":0},
            {"baseAssetId":3,"quoteAssetId":4},assets,mid=10.0,min_volume_cents=10000,
        )
        self.assertEqual(c3["trading_commission_scale"],100_000)
        self.assertAlmostEqual(c3["roundtrip_commission_price_equivalent"],0.001,places=12)

    def test_09_true_tail_quantiles_detect_90pct_tight_10pct_wide(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,protocol,_=self.make_runner(Path(td))
            candidate=self.candidate("EURUSD");full=self.full_fx(rate=0);light=self.light(1,"EURUSD",10,20)
            window=friction_windows(protocol,"GLOBAL_24X5")[0]
            start=window["from_ms"]+1000
            bid=[DecodedTick(start,100000)]
            asks=[]
            for i in range(100):
                raw=100010 if i<90 else 100200
                asks.append(DecodedTick(start+i*1000,raw))
            def fake_ticks(aid,sid,side,w):
                return bid if side=="BID" else asks
            runner._ticks=fake_ticks
            runner._sample_bars=lambda *a,**k:[
                {"time_utc":window["start_utc"],"open":"1","high":"1.001","low":"1","close":"1.0005","tick_volume":"10"}
            ]
            result=runner._friction(1,candidate,full,light)
            ws=result["window_summaries"][0]
            self.assertLess(ws["spread_median"],0.0002)
            self.assertGreater(ws["spread_p95"],0.001)
            self.assertEqual(result["friction_state"],"FRICTION_FAIL")

    def test_10_session_balanced_tail_not_hidden_by_high_tick_window(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,protocol,_=self.make_runner(Path(td),one_window=False)
            protocol["friction_screen"]["profiles"]["GLOBAL_24X5"]={
                "sample_dates":["2026-09-03","2026-09-04","2026-09-08","2026-09-09"],
                "utc_windows":[{"label":"EUROPE","start":"08:00","end":"08:10"}],
            }
            candidate=self.candidate("EURUSD");full=self.full_fx(rate=0);light=self.light(1,"EURUSD",10,20)
            windows=friction_windows(protocol,"GLOBAL_24X5")
            def fake_ticks(aid,sid,side,w):
                idx=next(i for i,x in enumerate(windows) if x["start_utc"]==w["start_utc"])
                n=1000 if idx<3 else 10
                if side=="BID":
                    return [DecodedTick(w["from_ms"]+1000,100000)]
                raw=100010 if idx<3 else 100200
                return [DecodedTick(w["from_ms"]+1000+i*1000,raw) for i in range(n)]
            runner._ticks=fake_ticks
            runner._sample_bars=lambda aid,sid,dig,w:[
                {"time_utc":w["start_utc"],"open":"1","high":"1.001","low":"1","close":"1.0005","tick_volume":"10"}
            ]
            result=runner._friction(1,candidate,full,light)
            self.assertLess(result["pooled_state_p95_spread"],0.0002)  # high-tick tight sessions dominate pooled diagnostic
            self.assertGreater(result["p75_window_p95_spread_over_range"],0.2)  # equal-window tail retains bad session
            self.assertEqual(result["tail_aggregation"],"TRUE_INTRA_WINDOW_QUANTILES_PLUS_EQUAL_WINDOW_BALANCED_RATIOS")

    def test_11_real_friction_path_executes_canonical_m5_and_true_tails(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,transport=self.make_runner(Path(td))
            candidate=self.candidate("EURUSD");full=self.full_fx(rate=0);light=self.light(1,"EURUSD",10,20)
            result=runner._friction(1,candidate,full,light)
            self.assertGreater(result["quote_state_count"],20)
            ws=result["window_summaries"][0]
            self.assertIsNotNone(ws["spread_p75"]);self.assertIsNotNone(ws["spread_p90"]);self.assertIsNotNone(ws["spread_p95"])
            self.assertIn("ProtoOAGetTrendbarsReq",[x[0] for x in transport.calls])

    def test_12_programming_contract_error_cannot_become_friction_fail(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,_=self.make_runner(Path(td))
            runner._sample_bars=lambda *a,**k: (_ for _ in ()).throw(TypeError("normalize defect"))
            with self.assertRaises(TypeError):
                runner._friction(1,self.candidate("EURUSD"),self.full_fx(rate=0),self.light(1,"EURUSD",10,20))

    def test_13_stage_rows_uses_canonical_normalizer_and_paginates(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,transport=self.make_runner(Path(td),one_window=False)
            rows=runner._stage_rows(1,self.candidate("EURUSD"),self.full_fx(rate=0))
            self.assertEqual(len(rows),600);self.assertLess(rows[0]["time_utc"],rows[-1]["time_utc"])
            self.assertGreaterEqual(len([x for x in transport.calls if x[0]=="ProtoOAGetTrendbarsReq"]),1)

    def test_14_selected_market_writes_integrity_checked_stage_a_csv(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);runner,_,_,_=self.make_runner(root,one_window=False);runner.bundle.mkdir(parents=True,exist_ok=True)
            candidate=self.candidate("EURUSD");rows=runner._stage_rows(1,candidate,self.full_fx(rate=0))
            record=runner._write_rows(candidate,rows);path=runner.bundle/record["file"]
            self.assertTrue(path.is_file());self.assertEqual(record["row_count"],600);self.assertEqual(record["sha256"],uf._sha(path))

    def test_15_selector_never_admits_unresolved_commission(self):
        base=[]
        for i,c in enumerate(self.plan["shortlist"][:12]):
            x=copy.deepcopy(c);x.update({
                "friction_state":"FRICTION_PASS","cost_confidence_state":FULL_FRICTION_RESOLVED,
                "movement_to_window_balanced_p75_effective_friction":10-i/10,
                "p75_window_p95_effective_friction_over_range":0.2,
            });base.append(x)
        bad=copy.deepcopy(self.plan["shortlist"][12]);bad.update({
            "friction_state":"FRICTION_PASS","cost_confidence_state":COMMISSION_CONVERSION_UNRESOLVED,
            "movement_to_window_balanced_p75_effective_friction":999,
            "p75_window_p95_effective_friction_over_range":0.01,
        })
        chosen,_=select_stage_a(base+[bad],self.protocol["selection_law"])
        self.assertNotIn(bad["broker_symbol"],[x["broker_symbol"] for x in chosen])

    def test_16_sparse_valid_evidence_is_unresolved_not_friction_fail(self):
        metrics={
            "cost_confidence_state":FULL_FRICTION_RESOLVED,"two_sided_window_coverage":0.1,
            "quote_state_count":2,"median_m5_range":1.0,
            "median_window_p75_spread_over_range":0.1,"p75_window_p95_spread_over_range":0.2,
            "median_window_p75_effective_friction_over_range":0.1,"p75_window_p95_effective_friction_over_range":0.2,
            "median_spread_over_mid":0.001,
        }
        self.assertEqual(qualify_friction(metrics,self.protocol["friction_screen"]["qualification"]),"FRICTION_UNRESOLVED")

    def _synthetic_postcondition_fixture(self,root):
        runner,plan,_,_=self.make_runner(root,one_window=False);runner.bundle.mkdir(parents=True,exist_ok=True)
        candidate=self.candidate("EURUSD");rows,pagination=runner._stage_rows(1,candidate,self.full_fx(rate=0));record=runner._write_rows(candidate,rows,pagination)
        friction=[]
        for x in plan["shortlist"]:
            y=copy.deepcopy(x);y.update({
                "cost_confidence_state":FULL_FRICTION_RESOLVED,"friction_state":"FRICTION_FAIL",
                "movement_to_window_balanced_p75_effective_friction":1.0,
                "p75_window_p95_effective_friction_over_range":0.8,
                "planned_windows":1,
                "window_summaries":[{
                    "start_utc":"2026-09-03T08:00:00Z","end_utc":"2026-09-03T08:10:00Z",
                    "quote_states":30,"spread_median":0.0001,"spread_p75":0.0001,"spread_p90":0.0001,"spread_p95":0.0001,
                    "commission":{"cost_confidence_state":FULL_FRICTION_RESOLVED,"conversion_evidence":{}},
                }],
            });friction.append(y)
        friction[0]["friction_state"]="FRICTION_PASS";friction[0]["movement_to_window_balanced_p75_effective_friction"]=5.0
        selection={"final_selected":[candidate["broker_symbol"]]}
        manifest={
            "status":"COMPACT_FRICTION_AND_STAGE_A_DEVELOPMENT_CAPTURE_COMPLETE",
            "stage_a_selected_count":1,"friction_shortlist_count":32,
            "raw_ticks_transferred":False,"raw_conversion_ticks_transferred":False,
            "orders_placed":False,"account_mutation":False,"economic_outcomes_opened":0,"v2_attempts_consumed":0,
        }
        conversion={"chains":[],"window_rates":[],"raw_conversion_ticks_transferred":False}
        return runner,plan,friction,selection,[record],manifest,conversion

    def test_17_manifest_selection_series_conversion_and_checksums_reconcile(self):
        with tempfile.TemporaryDirectory() as td:
            runner,plan,friction,selection,series,manifest,conversion=self._synthetic_postcondition_fixture(Path(td))
            (runner.bundle/"friction_summary.json").write_text(json.dumps({"results":friction}),encoding="utf-8")
            (runner.bundle/"historical_conversion_summary.json").write_text(json.dumps(conversion),encoding="utf-8")
            (runner.bundle/"selection.json").write_text(json.dumps(selection),encoding="utf-8")
            (runner.bundle/"capture_manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
            self.assertTrue(validate_capture_postconditions(plan=plan,friction_results=friction,selection=selection,series=series,bundle=runner.bundle,manifest=manifest,conversion_summary=conversion,verify_checksums=False))
            _write_checksums(runner.bundle)
            self.assertTrue(validate_capture_postconditions(plan=plan,friction_results=friction,selection=selection,series=series,bundle=runner.bundle,manifest=manifest,conversion_summary=conversion,verify_checksums=True))

    def test_18_systemic_unresolved_capture_cannot_be_marked_complete(self):
        with tempfile.TemporaryDirectory() as td:
            runner,plan,_,_=self.make_runner(Path(td));friction=[]
            for x in plan["shortlist"]:
                y=copy.deepcopy(x);y.update({
                    "cost_confidence_state":"FRICTION_UNRESOLVED","friction_state":"FRICTION_UNRESOLVED",
                    "planned_windows":1,"window_summaries":[{
                        "start_utc":"2026-09-03T08:00:00Z","end_utc":"2026-09-03T08:10:00Z","quote_states":0,
                        "commission":{"cost_confidence_state":COMMISSION_CONVERSION_UNRESOLVED,"conversion_evidence":{}},
                    }],
                });friction.append(y)
            manifest={"status":"FRICTION_QUALIFICATION_COMPLETE_NO_STAGE_A_MARKETS","stage_a_selected_count":0,"friction_shortlist_count":32,"raw_ticks_transferred":False,"raw_conversion_ticks_transferred":False,"orders_placed":False,"account_mutation":False,"economic_outcomes_opened":0,"v2_attempts_consumed":0}
            with self.assertRaises(ImplementationInvalid):
                validate_capture_postconditions(plan=plan,friction_results=friction,selection={"final_selected":[]},series=[],bundle=runner.bundle,manifest=manifest,conversion_summary={"chains":[],"window_rates":[],"raw_conversion_ticks_transferred":False},verify_checksums=False)

    def test_19_conversion_summary_contains_no_raw_ticks_and_historical_windows(self):
        with tempfile.TemporaryDirectory() as td:
            runner,_,_,transport=self.make_runner(Path(td));w=self.window();self._install_usdjpy_chain(transport,w)
            runner._conversion_window_rate(1,20,30,w)
            summary=runner._conversion_summary()
            self.assertFalse(summary["raw_conversion_ticks_transferred"]);self.assertFalse(summary["current_or_future_rate_substitution"])
            self.assertEqual(summary["chain_count"],1);self.assertEqual(summary["window_rate_count"],1)
            self.assertEqual(summary["window_rates"][0]["window_start_utc"],w["start_utc"])

    def test_20_pydroid_preflight_has_conversion_request_and_no_network(self):
        p=local_preflight()
        self.assertEqual(p["plan_sha256"],EXPECTED_PLAN_SHA);self.assertEqual(p["shortlist"],32);self.assertEqual(p["max_stage_a_markets"],12)
        self.assertEqual(p["global_windows"],20);self.assertEqual(p["crypto_windows"],28);self.assertEqual(p["regional_windows"],8)
        self.assertFalse(p["raw_ticks_transferred"]);self.assertFalse(p["network_connection_attempted"]);self.assertFalse(p["credentials_used"])
        self.assertFalse(p["orders_permitted"]);self.assertFalse(p["account_mutation_permitted"]);self.assertFalse(p["economic_outcomes_opened"])

    def test_21_accounting_and_protection_remain_unchanged(self):
        s=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertEqual(s["v2_search_budget"],84);self.assertEqual(s["v2_evaluated_identities"],2);self.assertEqual(s["v2_attempts_used"],2)
        self.assertFalse(s["protected_evidence_opened"]);self.assertFalse(s["live_orders_authorized"]);self.assertFalse(s["competition_start_authorized"])


if __name__=="__main__":
    unittest.main()
