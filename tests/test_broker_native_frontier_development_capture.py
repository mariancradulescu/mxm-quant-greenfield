import inspect, json, unittest
from pathlib import Path
from research_v3.broker_native_frontier_development_capture import EXPECTED_PLAN_SHA, canonical_plan_sha, validate_plan
from research_v3.pydroid_broker_native_frontier_development_launcher import local_preflight

ROOT=Path(__file__).resolve().parents[1]

class BrokerNativeFrontierDevelopmentCaptureTests(unittest.TestCase):
    def test_accepted_probe_is_complete_non_economic(self):
        a=json.loads((ROOT/"data/BROKER_NATIVE_FRONTIER_M5_PROBE_ACCEPTANCE_V1.json").read_text())
        self.assertEqual(a["status"],"ACCEPTED_COMPLETE_NON_ECONOMIC_STRUCTURAL_PROBE")
        self.assertEqual(a["validation"]["series_complete"],41)
        self.assertEqual(a["validation"]["total_m5_rows"],64343)
        self.assertEqual(a["validation"]["protected_forward_rows"],0)
        self.assertEqual(a["safety"]["economic_outcomes_opened"],0)
        self.assertEqual(a["runtime_repair_validation"]["current_trading_mode"],"CLOSE_ONLY_MODE")
        self.assertEqual(a["runtime_repair_validation"]["historical_capture_status"],"SERIES_CAPTURE_COMPLETE")

    def test_topology_selection_is_not_fixed_n_or_outcome_selected(self):
        d=json.loads((ROOT/"evidence/BROKER_NATIVE_FRONTIER_M5_TOPOLOGY_REPORT_V1.json").read_text())
        law=d["selection_law_for_next_data_extension"]
        self.assertFalse(law["fixed_n"])
        self.assertFalse(law["economic_outcomes_used"])
        self.assertFalse(law["price_direction_used"])
        self.assertFalse(law["returns_used"])
        self.assertEqual(law["resulting_symbol_count"],40)
        self.assertEqual(law["excluded_only"][0]["broker_symbol"],"SHEIN.HK-PERP")

    def test_13w_plan_is_hash_frozen_non_economic(self):
        p=json.loads((ROOT/"data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_PLAN_V1.json").read_text())
        self.assertEqual(p["plan_sha256"],EXPECTED_PLAN_SHA)
        self.assertEqual(canonical_plan_sha(p),EXPECTED_PLAN_SHA)
        self.assertTrue(validate_plan(p))
        self.assertEqual(len(p["symbols"]),40)
        self.assertNotIn("SHEIN.HK-PERP",{x["broker_symbol"] for x in p["symbols"]})
        self.assertEqual(p["interval"],{"start_utc":"2026-06-15T00:00:00Z","end_utc":"2026-09-13T23:59:59Z"})
        self.assertEqual((p["economic_outcomes_opened"],p["v2_attempts_consumed"]),(0,0))
        self.assertFalse(p["protected_evidence_opened"])

    def test_preflight_is_local_read_only(self):
        r=local_preflight()
        self.assertEqual((r["symbols"],r["resolution"]),(40,"M5"))
        self.assertEqual(r["interval"],{"start_utc":"2026-06-15T00:00:00Z","end_utc":"2026-09-13T23:59:59Z"})
        self.assertFalse(r["network_connection_attempted"])
        self.assertFalse(r["credentials_used"])
        self.assertFalse(r["orders_permitted"])
        self.assertFalse(r["account_mutation_permitted"])
        self.assertFalse(r["economic_outcomes_opened"])
        self.assertFalse(r["schedule_adjusted_coverage_gate"])

    def test_collector_contains_no_order_requests(self):
        import research_v3.broker_native_frontier_development_capture as m
        s=inspect.getsource(m)
        for token in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"):
            self.assertNotIn(token,s)

if __name__=="__main__":
    unittest.main()
