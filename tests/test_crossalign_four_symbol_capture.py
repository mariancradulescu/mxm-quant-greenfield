import inspect
import json
import unittest
from pathlib import Path

from research_v3.crossalign_four_symbol_capture import (
    EXPECTED_SYMBOLS,
    OUTPUT_FILENAME,
    PLAN_REL,
    validate_plan,
)
from research_v3.pydroid_crossalign_four_symbol_launcher import local_preflight

ROOT = Path(__file__).resolve().parents[1]


class CrossAlignCaptureTests(unittest.TestCase):
    def test_exact_scope_is_frozen_and_trendbar_only(self):
        plan = json.loads((ROOT / PLAN_REL).read_text())
        self.assertTrue(validate_plan(plan))
        self.assertEqual(
            {x["broker_symbol"]: x["symbol_id"] for x in plan["symbols"]},
            EXPECTED_SYMBOLS,
        )
        self.assertEqual(plan["fields"], [
            "timestamp_utc", "open", "high", "low", "close", "tick_volume"
        ])
        self.assertEqual(plan["output_artifact_name"], OUTPUT_FILENAME)
        self.assertFalse(plan["research_contract"]["bid_ask_or_spread_requested"])

    def test_preflight_is_local_and_non_economic(self):
        result = local_preflight()
        self.assertEqual(result["symbols"], 4)
        self.assertEqual(result["resolution"], "M5")
        self.assertFalse(result["network_connection_attempted"])
        self.assertFalse(result["orders_permitted"])
        self.assertFalse(result["account_mutation_permitted"])
        self.assertFalse(result["economic_outcomes_opened"])

    def test_collector_has_no_order_or_bid_ask_contract(self):
        from research_v3 import crossalign_four_symbol_capture as module
        source = inspect.getsource(module)
        for token in (
            "ProtoOANewOrderReq", "ProtoOACancelOrderReq",
            "ProtoOAClosePositionReq", "ProtoOAAmendOrderReq",
        ):
            self.assertNotIn(token, source)
        self.assertNotIn('"bid"', source)
        self.assertNotIn('"ask"', source)

    def test_package_binds_exact_plan(self):
        source = (ROOT / "tools/build_crossalign_four_symbol_capture_package.py").read_text()
        self.assertIn("data/CROSSALIGN_FOUR_SYMBOL_M5_CAPTURE_PLAN_V1.json", source)
        self.assertIn("research_v3/crossalign_four_symbol_capture.py", source)
        self.assertIn("CROSSALIGN_FOUR_SYMBOL_M5_CAPTURE_RUN.py", source)

    def test_root_runner_resolves_pydroid_exec_location(self):
        runner = ROOT / "CROSSALIGN_FOUR_SYMBOL_M5_CAPTURE_RUN.py"
        scope = {
            "__name__": "pydroid_stub",
            "__file__": "/data/user/0/ru.iiec.pydroid3/files/accomp_files/iec_run/iec_run.py",
            "mainpyfile": str(runner),
        }
        exec(compile(runner.read_text(), "<string>", "exec"), scope)
        self.assertEqual(scope["ROOT"], ROOT)
        self.assertEqual(scope["package_root"](), ROOT)


if __name__ == "__main__":
    unittest.main()
