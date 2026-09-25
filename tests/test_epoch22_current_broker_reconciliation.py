import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(rel):return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class Epoch22CurrentBrokerReconciliationTests(unittest.TestCase):
    def test_repacked_capture_is_accepted_by_canonical_payload_identity(self):
        a=load("evidence/BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_EPOCH22_ACCEPTANCE_V1.json")
        p=a["capture_provenance"]
        self.assertEqual(a["status"],"ACCEPTED_COMPLETE_CURRENT_BROKER_NATIVE_READ_ONLY_CAPTURE")
        self.assertEqual(p["uploaded_transport_zip_sha256"],"3d1db9a65e93fe5c7ea69411a9c76d8d6381927ce1224e02532640394076e8a9")
        self.assertEqual(p["original_pydroid_collector_zip_sha256"],"5ce4b3bc3a47292bb8b9b704d6c8c305a0bc3657d7dd0ace539d93e740a9be15")
        self.assertEqual(p["accepted_canonical_payload_sha256"],"7b268eae05fad325cb1f0fc962511ca41236b3b58bb83023735fd22b94301452")
        self.assertEqual(p["logical_payload_copies"],2);self.assertTrue(p["duplicate_payloads_byte_identical"])
        self.assertFalse(p["outer_zip_hash_is_evidence_identity"])
        self.assertEqual(a["accounting_effect"],{"v2_attempts":0,"economic_outcomes":0,"copilot_provider_calls":0})

    def test_current_counts_and_drift_replace_stale_current_metadata_only(self):
        a=load("evidence/BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_EPOCH22_ACCEPTANCE_V1.json")
        self.assertEqual(a["capture_contract_validation"]["current_symbol_count"],5324)
        self.assertEqual(a["capture_contract_validation"]["current_new_entry_accessible_count"],1689)
        self.assertEqual(a["current_counts"]["both_feasible"],1607)
        d={x["broker_symbol"]:x for x in a["current_broker_drift"]["material_transitions"]}
        self.assertEqual(d["SHEIN.HK-PERP"]["trading_mode"],3)
        self.assertEqual(d["Crude-F"]["directional_feasibility_summary"],"NEITHER_FEASIBLE")
        self.assertEqual(d["Brent-F"]["directional_feasibility_summary"],"NEITHER_FEASIBLE")
        self.assertEqual(d["RHMd.DE"]["directional_feasibility_summary"],"BOTH_FEASIBLE")

    def test_current_structural_registry_is_1576_with_41_signatures_and_three_replacements(self):
        r=load("research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json")
        self.assertEqual(r["counts"],{"eligible_identities":1576,"distinct_signatures":41,"representative_count":41})
        self.assertEqual(set(r["representative_changes"]["removed_representatives"]),{"Crude-F","HEXAB.SE","SHEIN.HK-PERP"})
        self.assertEqual(set(r["representative_changes"]["added_representatives"]),{"XAUUSD-F","CXMT.CN-PERP","ERICB.SE"})
        self.assertEqual(len(r["representatives"]),41)
        self.assertEqual(sum(1 for x in r["representatives"] if x["has_13w_history"]),38)
        self.assertFalse(r["structural_representative_is_economic_equivalence"])

    def test_feature_store_preserves_margin_headroom_and_explicit_missingness(self):
        f=load("research_v3/BROKER_NATIVE_FRONTIER_FEATURE_STORE_EPOCH22_V1.json")
        self.assertEqual(f["universe_identity_count"],1576)
        self.assertEqual(f["summary"]["structural_signature_known"],1576)
        self.assertEqual(f["summary"]["current_margin_known"],1576)
        self.assertEqual(f["summary"]["current_representatives_without_13w_history"],3)
        self.assertEqual(f["missingness"]["identity_level_transaction_local_cost_missing"],1576)
        self.assertAlmostEqual(f["margin_quality_law"]["RHMd.DE"]["worst_direction_margin_headroom_eur"],2.32)

    def test_selector_chooses_only_three_missing_current_representatives(self):
        s=load("research_v3/BROKER_NATIVE_FRONTIER_INFORMATION_GAIN_SELECTION_EPOCH22_V1.json")
        pick=s["selected_next_acquisition"]
        self.assertEqual(set(pick["symbols"]),{"XAUUSD-F","CXMT.CN-PERP","ERICB.SE"})
        self.assertEqual(pick["marginal_coverage_gain"],{"current_representatives_with_13w_history_before":38,"after_if_complete":41,"added":3})
        self.assertEqual(s["effect"]["v2_attempts"],0);self.assertEqual(s["effect"]["provider_calls"],0)
        self.assertTrue(s["no_random_ticker_sampling"]);self.assertTrue(s["no_arbitrary_top_n"])

    def test_epoch_advanced_for_new_current_evidence_not_for_outcome(self):
        e=load("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
        self.assertEqual(e["current_epoch"],22)
        self.assertEqual(e["history"][-1]["event_class"],"CURRENT_BROKER_NATIVE_EXECUTION_FEASIBILITY_EVIDENCE_ACCEPTED")

if __name__=="__main__":unittest.main()
