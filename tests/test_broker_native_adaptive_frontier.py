import inspect, json, unittest
from pathlib import Path
from research_v3.broker_native_information_frontier import select_frontier
from research_v3.broker_native_frontier_probe_capture import EXPECTED_PLAN_SHA, canonical_plan_sha, validate_plan
from research_v3.pydroid_broker_native_frontier_probe_launcher import local_preflight

ROOT=Path(__file__).resolve().parents[1]

class BrokerNativeInformationFrontierTests(unittest.TestCase):
    def test_persisted_frontier_is_dynamic_structural_coverage_not_fixed8(self):
        f=json.loads((ROOT/"data/BROKER_NATIVE_ADAPTIVE_INFORMATION_FRONTIER_V1.json").read_text())
        self.assertFalse(f["selection_law"]["fixed_panel_size"])
        self.assertEqual(f["frontier_count"],len(f["frontier"]))
        self.assertEqual(f["frontier_count"],41)
        sigs={tuple(x["signature"]) for x in f["frontier"]}
        self.assertEqual(len(sigs),len(f["frontier"]))
        excluded=set(f["eligibility"]["previously_observed_symbols_excluded"])
        self.assertIn("NAS100",excluded)
        self.assertTrue(excluded.isdisjoint({x["broker_symbol"] for x in f["frontier"]}))
        self.assertEqual(f["economic_effect"]["v2_attempts_consumed"],0)
        self.assertFalse(f["economic_effect"]["market_data_read"])

    def test_selector_count_emerges_from_signatures(self):
        rows=[
          {"symbol_id":"1","broker_symbol":"A","asset_class":"FX","product_type":"P","coverage_bucket":"C1","session_regions":"R","weekend_capable":"False","directional_summary":"BOTH_FEASIBLE","shortability":"True","surface_minutes_per_margin_eur":"10","min_feasible_margin_eur":"2","data_acquisition_burden":"NEW"},
          {"symbol_id":"2","broker_symbol":"B","asset_class":"FX","product_type":"P","coverage_bucket":"C1","session_regions":"R","weekend_capable":"False","directional_summary":"BOTH_FEASIBLE","shortability":"True","surface_minutes_per_margin_eur":"20","min_feasible_margin_eur":"2","data_acquisition_burden":"NEW"},
          {"symbol_id":"3","broker_symbol":"C","asset_class":"INDEX","product_type":"Q","coverage_bucket":"C2","session_regions":"S","weekend_capable":"False","directional_summary":"BOTH_FEASIBLE","shortability":"True","surface_minutes_per_margin_eur":"5","min_feasible_margin_eur":"1","data_acquisition_burden":"NEW"},
        ]
        out=select_frontier(rows,{"C"})
        self.assertEqual([x["broker_symbol"] for x in out],["B"])
        out2=select_frontier(rows,set())
        self.assertEqual({x["broker_symbol"] for x in out2},{"B","C"})

    def test_probe_plan_is_hash_frozen_non_economic_and_pre_protected(self):
        p=json.loads((ROOT/"data/BROKER_NATIVE_FRONTIER_M5_PROBE_PLAN_V1.json").read_text())
        self.assertEqual(p["plan_sha256"],EXPECTED_PLAN_SHA)
        self.assertEqual(canonical_plan_sha(p),EXPECTED_PLAN_SHA)
        self.assertTrue(validate_plan(p))
        self.assertEqual(len(p["symbols"]),41)
        self.assertEqual(p["interval"],{"start_utc":"2026-08-31T00:00:00Z","end_utc":"2026-09-13T23:59:59Z"})
        self.assertFalse(p["probe_sufficiency"]["schedule_adjusted_coverage_gate"])
        self.assertEqual((p["economic_outcomes_opened"],p["v2_attempts_consumed"]),(0,0))
        self.assertFalse(p["protected_evidence_opened"])

    def test_preflight_is_local_read_only(self):
        r=local_preflight()
        self.assertEqual((r["symbols"],r["resolution"]),(41,"M5"))
        self.assertFalse(r["network_connection_attempted"])
        self.assertFalse(r["credentials_used"])
        self.assertFalse(r["orders_permitted"])
        self.assertFalse(r["account_mutation_permitted"])
        self.assertFalse(r["economic_outcomes_opened"])
        self.assertFalse(r["schedule_adjusted_coverage_gate"])

    def test_collector_contains_no_order_requests(self):
        import research_v3.broker_native_frontier_probe_capture as m
        s=inspect.getsource(m)
        for token in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"):
            self.assertNotIn(token,s)

    def test_schedule_review_does_not_reopen_outer(self):
        d=json.loads((ROOT/"evidence/SESSION_GAP_SCHEDULE_COVERAGE_DEPENDENCY_REVIEW_V1.json").read_text())
        self.assertEqual(d["classification"],"RAW_DATA_VALID_REPROCESS_ONLY")
        self.assertTrue(d["source_zip"]["sha256_verified"])
        self.assertFalse(d["materiality"]["recapture_required"])
        self.assertFalse(d["materiality"]["material_conclusion_changed"])
        self.assertFalse(d["dependency_review"]["outer_evaluator_reads_schedule_adjusted_coverage"])

    def test_historical_validity_audit_preserves_attempts(self):
        d=json.loads((ROOT/"evidence/RETROSPECTIVE_HISTORICAL_RESEARCH_VALIDITY_AUDIT_V1.json").read_text())
        self.assertEqual(d["accounting_after"],{"economic_outcomes_opened":27,"v2_attempts_used":19,"v2_search_budget_remaining":65})
        self.assertEqual(d["preservation"]["attempts_refunded"],0)
        self.assertEqual(d["preservation"]["economic_outcomes_reopened_for_audit"],0)
        self.assertEqual(d["groups"]["DATA_INVALID_OR_UNRECOVERABLE"],[])
        self.assertIn("V2-C031",d["groups"]["VALID_AS_IS"])
        self.assertIn("V2-C029",d["groups"]["DATA_INSUFFICIENT_OR_MISSING_BROKER_NATIVE_FIELD"])
        self.assertIn("V2-C013",d["groups"]["SEMANTICS_CHANGED_NEW_IDENTITY_REQUIRED"])

if __name__=="__main__": unittest.main()
