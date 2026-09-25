import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from m6._ctrader_capture_base import (
    FORBIDDEN_MUTATION_PROTO_REQUESTS,
    READ_ONLY_PROTO_REQUESTS,
)
from m6.ctrader_capture import (
    MAPPING_POLICY_INDEX_CASH_CFD,
    MAPPING_POLICY_NON_FUTURES_CFD,
    MappingError,
    TRANSFERABLE_REQUIRED_FILES,
    broker_product_profile,
    build_asset_class_catalog,
    build_symbol_category_catalog,
    discover_symbol_mapping,
    mapping_semantic_policy,
    resolve_profiled_broker_product,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "data/PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json").read_text(
        encoding="utf-8"
    )
)
CHECKPOINT = ROOT / "data/PRIMARY_WAVE_02_M6_CAPTURE_CLIENT_CHECKPOINT_V11.json"


def light(symbol_id, name, description, category_id, *, enabled=True):
    return {
        "symbolId": symbol_id,
        "symbolName": name,
        "description": description,
        "symbolCategoryId": category_id,
        "enabled": enabled,
    }


def extended_schedule():
    rows = []
    for day in range(1, 6):
        start = day * 86400 + 3600
        rows.append(
            {"startSecond": start, "endSecond": start + 22 * 3600 + 59 * 60}
        )
    return rows


def full(symbol_id):
    return {
        "symbolId": symbol_id,
        "tradingMode": 0,
        "enableShortSelling": True,
        "scheduleTimeZone": "Etc/UTC",
        "schedule": extended_schedule(),
        "minVolume": 100,
        "maxVolume": 100000,
        "stepVolume": 100,
        "holiday": [],
    }


CATEGORIES = build_symbol_category_catalog(
    [
        {"id": 10, "assetClassId": 1, "name": "Indices"},
        {"id": 20, "assetClassId": 2, "name": "Futures"},
        {"id": 30, "assetClassId": 3, "name": "Metals"},
        {"id": 40, "assetClassId": 4, "name": "Energy"},
        {"id": 50, "assetClassId": 5, "name": "Crypto"},
        {"id": 60, "assetClassId": 6, "name": "Forex"},
    ]
)
ASSET_CLASSES = build_asset_class_catalog(
    [
        {"id": 1, "name": "Indices"},
        {"id": 2, "name": "Futures"},
        {"id": 3, "name": "Metals"},
        {"id": 4, "name": "Commodities"},
        {"id": 5, "name": "Cryptocurrencies"},
        {"id": 6, "name": "Forex"},
    ]
)


class M6FrozenBrokerProductFamilyTests(unittest.TestCase):
    def _resolve(self, canonical, symbols):
        discovery = discover_symbol_mapping(canonical, symbols)
        full_by_id = {int(row["symbolId"]): full(int(row["symbolId"])) for row in symbols}
        selector = Mock(side_effect=AssertionError("manual selector must not run"))
        result = resolve_profiled_broker_product(
            canonical,
            PLAN,
            discovery,
            symbols,
            full_by_id,
            categories_by_id=CATEGORIES,
            asset_classes_by_id=ASSET_CLASSES,
            selector=selector,
        )
        selector.assert_not_called()
        return result

    def test_01_index_bindings_use_cash_index_cfd_policy(self):
        self.assertEqual(
            mapping_semantic_policy(PLAN, "NAS100"),
            MAPPING_POLICY_INDEX_CASH_CFD,
        )
        self.assertEqual(
            mapping_semantic_policy(PLAN, "US500"),
            MAPPING_POLICY_INDEX_CASH_CFD,
        )

    def test_02_other_frozen_spot_continuous_products_use_non_futures_policy(self):
        for canonical in ("XAUUSD", "WTIUSD", "BTCUSD", "AUDJPY"):
            self.assertEqual(
                mapping_semantic_policy(PLAN, canonical),
                MAPPING_POLICY_NON_FUTURES_CFD,
            )

    def test_03_same_long_hours_do_not_make_cash_index_and_future_equivalent(self):
        cash = broker_product_profile(
            light(101, "NAS100", "NASDAQ 100 Index", 10),
            full(101),
            categories_by_id=CATEGORIES,
            asset_classes_by_id=ASSET_CLASSES,
        )
        future = broker_product_profile(
            light(102, "NAS100-F", "NASDAQ 100 Futures CFD", 20),
            full(102),
            categories_by_id=CATEGORIES,
            asset_classes_by_id=ASSET_CLASSES,
        )
        self.assertEqual(cash["session_class"], "EXTENDED_24_5_LIKE")
        self.assertEqual(future["session_class"], "EXTENDED_24_5_LIKE")
        self.assertEqual(cash["contract_family"], "CASH_SPOT_INDEX_CFD_LIKE")
        self.assertEqual(future["contract_family"], "FUTURES_FORWARD_LIKE")

    def test_04_nas100_cash_index_is_selected_and_future_excluded(self):
        symbols = [
            light(101, "NAS100", "NASDAQ 100 Index", 10),
            light(102, "NAS100-F", "NASDAQ 100 Futures CFD", 20),
        ]
        selected, profile, source, policy, profiles = self._resolve("NAS100", symbols)
        self.assertEqual(selected["symbolId"], 101)
        self.assertEqual(profile["contract_family"], "CASH_SPOT_INDEX_CFD_LIKE")
        self.assertEqual(source, "AUTO_FROZEN_INDEX_CASH_CFD")
        self.assertEqual(policy, MAPPING_POLICY_INDEX_CASH_CFD)
        self.assertEqual(len(profiles), 2)

    def test_05_us500_cash_index_is_selected_and_future_excluded(self):
        symbols = [
            light(201, "US500", "US 500 Index", 10),
            light(202, "US500-F", "US 500 Futures CFD", 20),
        ]
        selected, profile, source, _, _ = self._resolve("US500", symbols)
        self.assertEqual(selected["symbolId"], 201)
        self.assertEqual(profile["contract_family"], "CASH_SPOT_INDEX_CFD_LIKE")
        self.assertEqual(source, "AUTO_FROZEN_INDEX_CASH_CFD")

    def test_06_suffix_evidence_still_excludes_future_when_category_catalog_is_weak(self):
        symbols = [
            light(301, "NAS100", "NASDAQ 100", 99),
            light(302, "NAS100-F", "NASDAQ 100", 99),
        ]
        discovery = discover_symbol_mapping("NAS100", symbols)
        selected, profile, source, _, _ = resolve_profiled_broker_product(
            "NAS100",
            PLAN,
            discovery,
            symbols,
            {301: full(301), 302: full(302)},
            categories_by_id={},
            asset_classes_by_id={},
        )
        self.assertEqual(selected["symbolId"], 301)
        self.assertEqual(profile["contract_family"], "UNKNOWN")
        self.assertEqual(source, "AUTO_FROZEN_INDEX_CASH_CFD")

    def test_07_future_only_index_blocks_fail_closed(self):
        symbols = [light(401, "NAS100-F", "NASDAQ 100 Futures CFD", 20)]
        discovery = discover_symbol_mapping("NAS100", symbols)
        with self.assertRaisesRegex(MappingError, "non-futures broker product"):
            resolve_profiled_broker_product(
                "NAS100",
                PLAN,
                discovery,
                symbols,
                {401: full(401)},
                categories_by_id=CATEGORIES,
                asset_classes_by_id=ASSET_CLASSES,
            )

    def test_08_xauusd_spot_is_selected_over_forward(self):
        symbols = [
            light(501, "XAUUSD", "Spot Gold", 30),
            light(502, "XAUUSD-F", "Gold Futures Forward CFD", 20),
        ]
        selected, profile, source, policy, _ = self._resolve("XAUUSD", symbols)
        self.assertEqual(selected["symbolId"], 501)
        self.assertNotEqual(profile["contract_family"], "FUTURES_FORWARD_LIKE")
        self.assertEqual(source, "AUTO_FROZEN_NON_FUTURES_PRODUCT")
        self.assertEqual(policy, MAPPING_POLICY_NON_FUTURES_CFD)

    def test_09_wtiusd_non_futures_is_selected_over_forward(self):
        symbols = [
            light(601, "WTIUSD", "WTI Crude Oil CFD", 40),
            light(602, "WTIUSD-F", "WTI Crude Futures Forward", 20),
        ]
        selected, _, source, policy, _ = self._resolve("WTIUSD", symbols)
        self.assertEqual(selected["symbolId"], 601)
        self.assertEqual(source, "AUTO_FROZEN_NON_FUTURES_PRODUCT")
        self.assertEqual(policy, MAPPING_POLICY_NON_FUTURES_CFD)

    def test_10_economic_and_legacy_fields_cannot_change_contract_family_choice(self):
        symbols = [
            dict(
                light(701, "NAS100", "NASDAQ 100 Index", 10),
                pnl=-999999,
                legacy_rank=99,
                old_result="LOSER",
            ),
            dict(
                light(702, "NAS100-F", "NASDAQ 100 Futures CFD", 20),
                pnl=999999,
                legacy_rank=1,
                old_result="WINNER",
            ),
        ]
        selected, _, _, _, _ = self._resolve("NAS100", symbols)
        self.assertEqual(selected["symbolId"], 701)

    def test_11_category_and_asset_class_requests_are_read_only_only(self):
        self.assertIn("ProtoOASymbolCategoryListReq", READ_ONLY_PROTO_REQUESTS)
        self.assertIn("ProtoOAAssetClassListReq", READ_ONLY_PROTO_REQUESTS)
        for forbidden in (
            "ProtoOANewOrderReq",
            "ProtoOACancelOrderReq",
            "ProtoOAAmendOrderReq",
            "ProtoOAClosePositionReq",
        ):
            self.assertIn(forbidden, FORBIDDEN_MUTATION_PROTO_REQUESTS)
            self.assertNotIn(forbidden, READ_ONLY_PROTO_REQUESTS)

    def test_12_structural_catalogs_are_transferable_mapping_evidence(self):
        self.assertIn("evidence/symbol_categories.json", TRANSFERABLE_REQUIRED_FILES)
        self.assertIn("evidence/asset_classes.json", TRANSFERABLE_REQUIRED_FILES)

    def test_13_current_schedule_remains_mapping_snapshot_not_historical_truth(self):
        source = (ROOT / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        self.assertIn('"historical_session_calendar_versions"', source)
        self.assertIn('"UNRESOLVED"', source)
        self.assertIn("Current schedule/holiday metadata is not relabelled as historical", source)

    def test_14_checkpoint_preserves_zero_economics(self):
        cp = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        self.assertEqual(
            cp["staging_parent_head"],
            "86819f42e2267a99120c345f915e35787a04ecaa",
        )
        self.assertTrue(cp["broker_product_resolution"]["symbol_category_evidence"])
        self.assertTrue(cp["broker_product_resolution"]["asset_class_evidence"])
        self.assertTrue(cp["broker_product_resolution"]["index_cash_vs_future_separated"])
        self.assertFalse(cp["broker_product_resolution"]["user_selects_cash_vs_future"])
        self.assertFalse(cp["broker_product_resolution"]["legacy_or_economics_used"])
        actual = cp["actual_execution"]
        self.assertFalse(actual["broker_capture_run"])
        self.assertFalse(actual["m6_economics_run"])
        self.assertEqual(actual["economic_outcomes_opened"], 0)
        self.assertEqual(actual["v2_attempts_used"], 0)
        self.assertEqual(actual["result_recorded"], 0)
        self.assertFalse(actual["protected_evidence_opened"])
        self.assertFalse(actual["live_orders"])
        self.assertFalse(actual["competition_start"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
