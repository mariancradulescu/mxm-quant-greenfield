import csv,json,tempfile,unittest
from pathlib import Path

from competition.frontier_data_capture import canonicalize_m5_csv, CaptureContractError
from research_v3.evidence_epoch import current_evidence_binding

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class Epoch23ReplacementCaptureAcceptanceTests(unittest.TestCase):
    def test_returned_capture_is_accepted_without_economic_effect(self):
        a=load("evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json")
        self.assertEqual(a["status"],"ACCEPTED_AFTER_DETERMINISTIC_CANONICALIZATION_OF_IDENTICAL_DUPLICATES")
        self.assertEqual(a["capture_provenance"]["returned_transport_zip_sha256"],"d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75")
        self.assertTrue(a["capture_provenance"]["duplicate_bundle_files_byte_identical"])
        self.assertEqual(a["canonicalization_repair"]["conflicting_duplicate_timestamps"],0)
        self.assertFalse(a["canonicalization_repair"]["recapture_required"])
        self.assertEqual(a["accounting_effect"],{"v2_attempts":0,"economic_outcomes":0,"copilot_provider_calls":0})

    def test_three_canonical_series_are_exact_and_clean(self):
        a=load("evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json")
        expected={
            "CXMT.CN-PERP":(7427,16160,6012),
            "ERICB.SE":(5352,6442,18141),
            "XAUUSD-F":(2924,17803,14907),
        }
        self.assertEqual(set(a["series"]),set(expected))
        for symbol,(sid,rows,duplicates_removed) in expected.items():
            row=a["series"][symbol]
            self.assertEqual(row["symbol_id"],sid)
            self.assertEqual(row["canonical_rows"],rows)
            self.assertEqual(row["identical_duplicate_rows_removed"],duplicates_removed)
            self.assertEqual(row["conflicting_duplicate_timestamps"],0)
            self.assertEqual(row["ohlc_failures"],0)
            self.assertEqual(row["out_of_interval_rows"],0)
            self.assertEqual(row["protected_forward_rows"],0)

    def test_current_representative_coverage_is_now_41_of_41(self):
        c=load("evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_STRUCTURAL_COVERAGE_EPOCH23_V1.json")
        self.assertEqual(c["current_representative_history_coverage"]["before"],38)
        self.assertEqual(c["current_representative_history_coverage"]["after"],41)
        self.assertEqual(c["current_representative_history_coverage"]["total_current_representatives"],41)
        self.assertEqual(c["current_41_representative_breakout_aggregate"]["symbols"],41)
        self.assertEqual(c["economic_effect"]["v2_attempts"],0)

    def test_feature_store_and_selector_stop_at_fresh_semantic_boundary(self):
        f=load("research_v3/BROKER_NATIVE_FRONTIER_FEATURE_STORE_EPOCH23_V1.json")
        s=load("research_v3/BROKER_NATIVE_FRONTIER_INFORMATION_GAIN_SELECTION_EPOCH23_V1.json")
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        self.assertEqual(f["summary"]["current_representatives_with_13w_history"],41)
        self.assertEqual(f["summary"]["current_representatives_without_13w_history"],0)
        self.assertEqual(s["selected_next_action"]["action"],"FRESH_GENERAL_AI_MECHANISM_SCOPE_DECISION")
        self.assertTrue(s["fresh_general_ai_call_required"])
        self.assertTrue(n["research_judgment_required"])
        self.assertTrue(n["ai_reasoning_required"])
        self.assertFalse(n["external_data_required"])
        self.assertFalse(n["user_action_required"])

    def test_evidence_epoch_23_and_current_universe_basis_are_not_stale(self):
        e=load("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
        self.assertEqual(e["current_epoch"],23)
        self.assertEqual(e["history"][-1]["event_class"],"AUTHENTICATED_MARKET_DATA_ACCEPTED")
        binding=current_evidence_binding(ROOT)
        u=binding["universe_basis"]
        self.assertEqual(u["accessible_symbols"],1689)
        self.assertEqual(u["both_direction_eur200_feasible"],1607)
        self.assertEqual(u["eligible_post_exclusion_symbols"],1576)
        self.assertEqual(u["structural_representatives"],41)
        self.assertEqual(u["structural_representatives_with_accepted_13w_data"],41)

    def test_global_m5_canonicalization_collapses_identical_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.csv"
            p.write_text(
                "time_utc,open,high,low,close,tick_volume\n"
                "2026-06-15T00:00:00Z,1,2,1,2,3\n"
                "2026-06-15T00:00:00Z,1,2,1,2,3\n"
                "2026-06-15T00:05:00Z,2,3,2,3,4\n",encoding="utf-8"
            )
            canonicalize_m5_csv(p)
            rows=list(csv.DictReader(p.open(encoding="utf-8")))
            self.assertEqual(len(rows),2)
            self.assertEqual([x["time_utc"] for x in rows],["2026-06-15T00:00:00Z","2026-06-15T00:05:00Z"])

    def test_global_m5_canonicalization_rejects_conflicting_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.csv"
            p.write_text(
                "time_utc,open,high,low,close,tick_volume\n"
                "2026-06-15T00:00:00Z,1,2,1,2,3\n"
                "2026-06-15T00:00:00Z,1,3,1,2,3\n",encoding="utf-8"
            )
            with self.assertRaisesRegex(CaptureContractError,"conflicting cross-window"):
                canonicalize_m5_csv(p)

if __name__=="__main__":
    unittest.main()
