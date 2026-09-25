import inspect,json,unittest
from pathlib import Path

from m6.ctrader_capture import CaptureContractError
from research_v3.current_frontier_replacement_development_capture import (
    EXPECTED_IDENTITIES,EXPECTED_PLAN_SHA,validate_plan,
)
import competition.broker_universe_capture_v3 as broker_v3

ROOT=Path(__file__).resolve().parents[1]

class CurrentFrontierReplacementCaptureTests(unittest.TestCase):
    def test_plan_is_exact_three_current_representatives_and_non_economic(self):
        p=json.loads((ROOT/"data/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_PLAN_EPOCH22_V1.json").read_text())
        self.assertTrue(validate_plan(p))
        self.assertEqual(p["plan_sha256"],EXPECTED_PLAN_SHA)
        got={(x["broker_symbol"],int(x["symbol_id"])) for x in p["symbols"]}
        self.assertEqual(got,set(EXPECTED_IDENTITIES))
        self.assertEqual(p["v2_attempts_consumed"],0);self.assertEqual(p["economic_outcomes_opened"],0)
        self.assertFalse(p["protected_evidence_opened"])

    def test_plan_mutation_fails_closed(self):
        p=json.loads((ROOT/"data/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_PLAN_EPOCH22_V1.json").read_text())
        p["symbols"][0]["broker_symbol"]="NETH25"
        with self.assertRaises(CaptureContractError):validate_plan(p)

    def test_broker_universe_v3_has_manifest_heartbeat_and_resume_without_trade_requests(self):
        src=inspect.getsource(broker_v3)
        for token in ("CAPTURE_MANIFEST.json","CaptureProgress","CaptureCheckpoint","validate_resume","completed_expected_margin_symbol_ids"):
            self.assertIn(token,src)
        for forbidden in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"):
            self.assertNotIn(forbidden,src)
        self.assertEqual(broker_v3.PAYLOAD_SCHEMA,"mxm.greenfield.v2.broker-native-competition-universe-capture.v2")

    def test_broker_universe_package_builder_includes_resume_and_identity_modules(self):
        src=(ROOT/"tools/build_competition_broker_universe_capture_package.py").read_text()
        self.assertIn("competition/broker_universe_capture_v3.py",src)
        self.assertIn("competition/capture_runtime.py",src)
        self.assertIn("research_v3/capture_identity.py",src)

if __name__=="__main__":unittest.main()
