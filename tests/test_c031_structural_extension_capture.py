import hashlib, inspect, json, unittest
from pathlib import Path
from research_v3.c031_structural_extension_capture import EXPECTED_PLAN_SHA, EXPECTED_SYMBOLS, OUTPUT_FILENAME, canonical_plan_sha, validate_plan
from research_v3.pydroid_c031_structural_extension_launcher import local_preflight

ROOT=Path(__file__).resolve().parents[1]
class C031StructuralExtensionCaptureTests(unittest.TestCase):
    def test_plan_is_exact_ai_selected_minimal_scope(self):
        p=json.loads((ROOT/"data/C031_STRUCTURAL_EXTENSION_WAVE_01_M5_CAPTURE_PLAN_V1.json").read_text())
        self.assertEqual(p["plan_sha256"],EXPECTED_PLAN_SHA); self.assertEqual(canonical_plan_sha(p),EXPECTED_PLAN_SHA); self.assertTrue(validate_plan(p))
        self.assertEqual({x["broker_symbol"]:int(x["symbol_id"]) for x in p["symbols"]},EXPECTED_SYMBOLS)
        self.assertEqual(p["interval"],{"start_utc":"2026-07-20T00:00:00Z","end_utc":"2026-09-13T23:59:59Z"})
        self.assertEqual(p["resolution"],"M5"); self.assertEqual(len(p["symbols"]),12)
        self.assertEqual((p["economic_outcomes_opened"],p["v2_attempts_consumed"]),(0,0)); self.assertFalse(p["protected_evidence_opened"])
    def test_symbol_bindings_match_accepted_current_broker_universe(self):
        a=json.loads((ROOT/"data/BROKER_NATIVE_COMPETITION_UNIVERSE_ACCEPTANCE_V2.json").read_text())
        self.assertEqual(a["accepted_capture"]["zip_sha256"],"9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77")
        self.assertEqual(a["account_identity"]["account_fingerprint_sha256"],"b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636")
    def test_preflight_is_read_only_and_no_credentials_or_network(self):
        r=local_preflight(); self.assertEqual((r["symbols"],r["resolution"]),(12,"M5")); self.assertFalse(r["network_connection_attempted"]); self.assertFalse(r["credentials_used"])
        self.assertFalse(r["orders_permitted"]); self.assertFalse(r["account_mutation_permitted"]); self.assertFalse(r["economic_outcomes_opened"]); self.assertEqual(r["v2_attempts_consumed"],0)
    def test_capture_source_contains_no_order_requests(self):
        import research_v3.c031_structural_extension_capture as m
        s=inspect.getsource(m)
        for token in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"): self.assertNotIn(token,s)
        self.assertEqual(OUTPUT_FILENAME,"MXM_C031_STRUCTURAL_EXTENSION_WAVE_01_M5_8W_CAPTURE.zip")
    def test_data_sufficiency_authority_requires_only_minimal_capture(self):
        d=json.loads((ROOT/"evidence/C031_STRUCTURAL_EXTENSION_DATA_SUFFICIENCY_V1.json").read_text())
        self.assertEqual(d["status"],"INSUFFICIENT_EXISTING_ACCEPTED_BYTES_EXTERNAL_READ_ONLY_CAPTURE_REQUIRED")
        self.assertEqual(d["conclusion"]["recapture_scope"],"ONLY_AI_SELECTED_12_SYMBOLS_M5_8_WEEKS")
        self.assertTrue(d["conclusion"]["old_16_symbol_multi_year_frontier_recapture_forbidden"])
if __name__=="__main__": unittest.main()
