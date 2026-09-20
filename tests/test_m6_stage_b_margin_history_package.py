import inspect
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from m6.ctrader_capture import CaptureContractError, require_read_only_request
from m6.stage_b_margin_evidence import (
    DEVELOPMENT_END_MS,
    DEVELOPMENT_START_MS,
    MARGIN_HISTORY_PACKAGE_FILES,
    PROTECTED_FORWARD_START_MS,
    TARGET_SYMBOLS,
    HistoryWindow,
    assert_transferable_privacy,
    bisect_window,
    build_margin_history_pydroid_package,
    exhaust_window,
    initial_windows,
    sanitize_deal,
    summarize_observations,
    validate_development_window,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class StageBMarginHistoryPackageTests(unittest.TestCase):
    def test_01_frozen_plan_validates(self):
        plan = load("data/M6_STAGE_B_MARGIN_HISTORY_SUPPLEMENT_PLAN_V1.json")
        self.assertTrue(validate_plan(plan))
        self.assertEqual(
            plan["status"],
            "FROZEN_READ_ONLY_MINIMAL_GENERIC_EXTENSION_PRE_STAGE_B_OUTCOME",
        )
        self.assertFalse(plan["orders"])
        self.assertFalse(plan["account_mutation"])

    def test_02_target_symbols_are_exact(self):
        self.assertEqual(TARGET_SYMBOLS, {"US500": 127, "NAS100": 126})
        plan = load("data/M6_STAGE_B_MARGIN_HISTORY_SUPPLEMENT_PLAN_V1.json")
        self.assertEqual(plan["target_products"]["US500"]["symbol_id"], 127)
        self.assertEqual(plan["target_products"]["NAS100"]["symbol_id"], 126)

    def test_03_protected_forward_boundary_cannot_be_crossed(self):
        self.assertLess(DEVELOPMENT_END_MS, PROTECTED_FORWARD_START_MS)
        validate_development_window(
            HistoryWindow(DEVELOPMENT_START_MS, DEVELOPMENT_END_MS)
        )
        with self.assertRaises(CaptureContractError):
            validate_development_window(
                HistoryWindow(DEVELOPMENT_START_MS, PROTECTED_FORWARD_START_MS)
            )

    def test_04_read_only_allowlist_is_enforced(self):
        allowed = {
            "ProtoOAApplicationAuthReq",
            "ProtoOAGetAccountListByAccessTokenReq",
            "ProtoOAAccountAuthReq",
            "ProtoOATraderReq",
            "ProtoOASymbolsListReq",
            "ProtoOASymbolByIdReq",
            "ProtoOADealListReq",
            "ProtoOAGetDynamicLeverageByIDReq",
            "ProtoOAMarginCallListReq",
        }
        plan = load("data/M6_STAGE_B_MARGIN_HISTORY_SUPPLEMENT_PLAN_V1.json")
        self.assertEqual(set(plan["read_only_requests"]), allowed)
        for name in allowed:
            self.assertEqual(require_read_only_request(name), name)

    def test_05_order_and_account_mutation_requests_are_forbidden(self):
        for name in (
            "ProtoOANewOrderReq",
            "ProtoOACancelOrderReq",
            "ProtoOAAmendOrderReq",
            "ProtoOAClosePositionReq",
            "ProtoOAAmendPositionSLTPReq",
            "ProtoOAAccountLogoutReq",
        ):
            with self.assertRaises(CaptureContractError):
                require_read_only_request(name)

    def test_06_initial_31_day_windows_are_non_overlapping(self):
        windows = initial_windows()
        self.assertGreater(len(windows), 1)
        self.assertEqual(windows[0].from_ms, DEVELOPMENT_START_MS)
        self.assertEqual(windows[-1].to_ms, DEVELOPMENT_END_MS)
        for a, b in zip(windows, windows[1:]):
            self.assertEqual(a.to_ms + 1, b.from_ms)
            self.assertLess(a.to_ms, b.from_ms)
        max_width = 31 * 24 * 60 * 60 * 1000
        self.assertTrue(all((w.to_ms - w.from_ms + 1) <= max_width for w in windows))

    def test_07_recursive_bisection_is_non_overlapping(self):
        w = HistoryWindow(DEVELOPMENT_START_MS, DEVELOPMENT_START_MS + 9)
        left, right = bisect_window(w)
        self.assertEqual(left.from_ms, w.from_ms)
        self.assertEqual(right.to_ms, w.to_ms)
        self.assertEqual(left.to_ms + 1, right.from_ms)
        seen = []
        def fetch(window):
            seen.append((window.from_ms, window.to_ms))
            if window == w:
                return [{"discarded": True}], True
            return [{"from": window.from_ms, "to": window.to_ms}], False
        rows, stats = exhaust_window(w, fetch)
        self.assertEqual(stats.request_count, 3)
        self.assertEqual(stats.split_count, 1)
        self.assertEqual(stats.complete_leaf_windows, 2)
        self.assertEqual(stats.has_more_responses, 1)
        self.assertNotIn({"discarded": True}, rows)
        self.assertEqual(rows[0]["to"] + 1, rows[1]["from"])

    def test_08_one_millisecond_has_more_fails_closed(self):
        w = HistoryWindow(DEVELOPMENT_START_MS, DEVELOPMENT_START_MS)
        with self.assertRaisesRegex(CaptureContractError, "one-millisecond"):
            exhaust_window(w, lambda _: ([], True))

    def test_09_deal_sanitization_is_target_and_development_only(self):
        good = {
            "dealId": 111,
            "orderId": 222,
            "positionId": 333,
            "label": "PRIVATE",
            "comment": "PRIVATE",
            "symbolId": 127,
            "executionTimestamp": DEVELOPMENT_START_MS + 1000,
            "volume": 10,
            "filledVolume": 10,
            "executionPrice": 5000.0,
            "tradeSide": 1,
            "dealStatus": 2,
            "marginRate": 0.05,
            "baseToUsdConversionRate": 1.0,
            "moneyDigits": 2,
        }
        row = sanitize_deal(good)
        self.assertIsNotNone(row)
        self.assertEqual(row["symbol"], "US500")
        for forbidden in (
            "dealId", "orderId", "positionId", "label", "comment"
        ):
            self.assertNotIn(forbidden, row)
        other = dict(good, symbolId=999)
        self.assertIsNone(sanitize_deal(other))
        protected = dict(good, executionTimestamp=PROTECTED_FORWARD_START_MS)
        self.assertIsNone(sanitize_deal(protected))

    def test_10_margin_rate_classifications_are_frozen(self):
        base = {
            "execution_utc": "2024-01-01T00:00:00.000Z",
            "execution_timestamp_ms": DEVELOPMENT_START_MS,
            "deal_status": 2,
        }
        none = summarize_observations([])
        self.assertEqual(
            none["US500"]["state"],
            "UNRESOLVED_NO_ACCOUNT_NATIVE_HISTORICAL_MARGIN_OBSERVATIONS",
        )
        missing = summarize_observations([
            dict(base, symbol="US500", margin_rate=None)
        ])
        self.assertEqual(
            missing["US500"]["state"],
            "UNRESOLVED_MARGIN_RATE_NOT_RECORDED",
        )
        present = summarize_observations([
            dict(base, symbol="US500", margin_rate=0.05)
        ])
        self.assertEqual(
            present["US500"]["state"],
            "OBSERVATIONS_CAPTURED_REQUIRES_SEPARATE_FAIL_CLOSED_AUTHORITY_ASSESSMENT",
        )

    def test_11_current_dynamic_leverage_is_not_historical_authority(self):
        plan = load("data/M6_STAGE_B_MARGIN_HISTORY_SUPPLEMENT_PLAN_V1.json")
        self.assertEqual(
            plan["current_structural_diagnostics"]["dynamic_leverage"]["classification"],
            "CURRENT_ONLY_NOT_HISTORICAL_AUTHORITY",
        )
        self.assertTrue(
            plan["interpretation"]["current_dynamic_leverage_may_not_be_backfilled_into_history"]
        )

    def test_12_current_expected_margin_is_diagnostic_only(self):
        policy = load("data/M6_STAGE_B_TIER1_EVALUATOR_POLICY_V1.json")
        margin = policy["margin_law"]
        self.assertTrue(margin["current_broker_native_expected_margin_diagnostic_only"])
        self.assertTrue(margin["approximate_leverage_arithmetic_forbidden"])
        self.assertEqual(margin["current_snapshot"]["V2-C006"]["buy_margin_eur"], 33.38)
        self.assertEqual(margin["current_snapshot"]["V2-C012"]["buy_margin_eur"], 129.04)

    def test_13_forbidden_identity_and_credential_fields_fail_privacy(self):
        for key in (
            "ctidTraderAccountId",
            "traderLogin",
            "dealId",
            "orderId",
            "positionId",
            "label",
            "comment",
            "accessToken",
            "refreshToken",
            "clientSecret",
            "password",
        ):
            with self.assertRaises(CaptureContractError):
                assert_transferable_privacy({key: "x"})
        assert_transferable_privacy(
            {"account_fingerprint_sha256": "a" * 64, "margin_rate": 0.05}
        )

    def test_14_deterministic_package_member_list_is_exact(self):
        expected = (
            "M6_STAGE_B_MARGIN_HISTORY_RUN.py",
            "m6/__init__.py",
            "m6/_ctrader_capture_base.py",
            "m6/ctrader_capture.py",
            "m6/ctrader_transport.py",
            "m6/stage_b_margin_evidence.py",
            "m6/stage_b_margin_openapi.py",
            "m6/pydroid_stage_b_margin_launcher.py",
            "m6/pydroid_oauth.py",
            "m6/ctrader_proto/__init__.py",
            "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py",
            "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
            "m6/ctrader_proto/OpenApiModelMessages_pb2.py",
            "m6/ctrader_proto/OpenApiMessages_pb2.py",
            "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
            "tools/requirements-m6-capture.txt",
            "data/M6_STAGE_B_MARGIN_HISTORY_SUPPLEMENT_PLAN_V1.json",
            "evidence/M6_STAGE_B_MARGIN_EVIDENCE_RESOLUTION_V1.json",
            "README_STAGE_B_MARGIN_HISTORY.txt",
        )
        self.assertEqual(MARGIN_HISTORY_PACKAGE_FILES, expected)

    def test_15_all_required_package_files_exist(self):
        missing = [
            rel for rel in MARGIN_HISTORY_PACKAGE_FILES
            if not (ROOT / rel).is_file()
        ]
        self.assertEqual(missing, [])

    def test_16_deterministic_package_build_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.zip"
            b = Path(td) / "b.zip"
            da = build_margin_history_pydroid_package(ROOT, a)
            db = build_margin_history_pydroid_package(ROOT, b)
            self.assertEqual(da, db)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with zipfile.ZipFile(a) as zf:
                self.assertEqual(tuple(zf.namelist()), MARGIN_HISTORY_PACKAGE_FILES)

    def test_17_package_contains_no_private_secret_files_or_values(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "package.zip"
            build_margin_history_pydroid_package(ROOT, p)
            with zipfile.ZipFile(p) as zf:
                names = tuple(zf.namelist())
                self.assertFalse(any(".mxm_quant" in x for x in names))
                self.assertFalse(any("account_selection" in x.lower() for x in names))
                self.assertFalse(any("token.json" in x.lower() for x in names))
                payload = b"\n".join(zf.read(x) for x in names)
                self.assertNotIn(b"MXM_TEST_REAL_SECRET_VALUE", payload)

    def test_18_stage_a_results_and_attempt_accounting_unchanged(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["economic_outcomes_opened"], 2)
        self.assertEqual(state["v2_attempts_used"], 2)
        self.assertEqual(state["v2_evaluated_identities"], 2)
        self.assertEqual(state["v2_search_budget"], 84)
        self.assertEqual(state["v2_search_budget_remaining"], 82)
        self.assertEqual(
            state["m6"]["first_stage_a_runner"]["result_hashes"]["V2-C006"],
            "223e83c20b7bb64c07e27029510c5b05f9c63a771b6ad0342548949f348d500a",
        )
        self.assertEqual(
            state["m6"]["first_stage_a_runner"]["result_hashes"]["V2-C012"],
            "70159f6b9b97ffb06d72510df2e1f5014967ac2ac8c94ccf1f69239e5500146c",
        )

    def test_19_stage_b_outcomes_remain_zero(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["m6"]["stage_b"]["stage_b_outcomes_opened"], 0)
        self.assertFalse(state["m6"]["stage_b"]["economics_run"])
        self.assertFalse(state["m6"]["stage_b"]["results_created"])
        self.assertFalse(any((ROOT / "discovery/results").glob("*STAGE_B*")))

    def test_20_stage_b_execution_remains_unauthorized(self):
        state = load("CURRENT_STATE.json")
        self.assertFalse(state["m6"]["stage_b"]["execution_authorized"])
        self.assertFalse(state["m6"]["tier1_stage_a"]["stage_b_authorized"])

    def test_21_protected_evidence_remains_unopened(self):
        state = load("CURRENT_STATE.json")
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["m6"]["stage_b"]["protected_evidence_opened"])

    def test_22_user_action_is_gated_by_green_package_acceptance(self):
        state = load("CURRENT_STATE.json")
        acceptance = load("data/M6_STAGE_B_MARGIN_HISTORY_PACKAGE_ACCEPTANCE_V1.json")
        self.assertEqual(
            acceptance["status"],
            "PASS_PACKAGE_COMPLETE_EXACT_HEAD_GREEN_USER_CAPTURE_REQUIRED",
        )
        self.assertEqual(acceptance["source_ci"]["conclusion"], "SUCCESS")
        self.assertEqual(acceptance["source_ci"]["tests_failed"], 0)
        self.assertEqual(
            acceptance["package"]["package_sha256"],
            "404af12c0d43e72f4e8bfde9eac113c3624e52411ac951c1e17dd83cc9fb09e9",
        )
        self.assertTrue(state["user_action_required"])
        self.assertTrue(
            state["m6"]["stage_b"]["margin_history_package"]["user_action_required"]
        )
        self.assertFalse(state["m6"]["stage_b"]["execution_authorized"])
        self.assertFalse(state["m6"]["stage_b"]["economics_run"])
        self.assertEqual(state["m6"]["stage_b"]["stage_b_outcomes_opened"], 0)

    def test_23_runtime_source_has_no_trading_request_classes(self):
        import m6.stage_b_margin_openapi as runtime
        source = inspect.getsource(runtime)
        for token in (
            "ProtoOANewOrderReq",
            "ProtoOACancelOrderReq",
            "ProtoOAAmendOrderReq",
            "ProtoOAClosePositionReq",
            "ProtoOAAmendPositionSLTPReq",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
