import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from m6.ctrader_capture import (
    MAPPING_POLICY_GENERIC,
    MAPPING_POLICY_US_EQUITY_CASH,
    MappingError,
    broker_product_profile,
    build_asset_catalog,
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
CHECKPOINT = ROOT / "data/PRIMARY_WAVE_02_M6_CAPTURE_CLIENT_CHECKPOINT_V10.json"


def light(symbol_id, name, description, *, base=10, quote=20, enabled=True):
    return {
        "symbolId": symbol_id,
        "symbolName": name,
        "description": description,
        "baseAssetId": base,
        "quoteAssetId": quote,
        "symbolCategoryId": 7,
        "enabled": enabled,
    }


def cash_schedule():
    intervals = []
    # cTrader schedule uses seconds from Sunday 00:00 in scheduleTimeZone.
    # Monday-Friday 09:30-16:00 => 32.5 hours/week.
    for day in range(1, 6):
        start = day * 86400 + 9 * 3600 + 30 * 60
        intervals.append({"startSecond": start, "endSecond": start + 6 * 3600 + 30 * 60})
    return intervals


def extended_schedule():
    # Five 23.5-hour windows => 117.5 hours/week, unmistakably extended/24x5-like.
    intervals = []
    for day in range(1, 6):
        start = day * 86400
        intervals.append({"startSecond": start, "endSecond": start + 23 * 3600 + 30 * 60})
    return intervals


def full(symbol_id, schedule, *, trading_mode=0):
    return {
        "symbolId": symbol_id,
        "tradingMode": trading_mode,
        "enableShortSelling": True,
        "scheduleTimeZone": "America/New_York",
        "schedule": schedule,
        "minVolume": 100,
        "maxVolume": 100000,
        "stepVolume": 100,
        "holiday": [],
    }


ASSETS = build_asset_catalog(
    [
        {"assetId": 10, "name": "AAPL", "displayName": "Apple"},
        {"assetId": 20, "name": "USD", "displayName": "US Dollar"},
    ]
)


class M6BrokerProductSemanticTests(unittest.TestCase):
    def test_01_frozen_c011_maps_to_cash_session_policy(self):
        for canonical in ("AAPL", "MSFT", "NVDA", "AMZN", "META"):
            self.assertEqual(
                mapping_semantic_policy(PLAN, canonical),
                MAPPING_POLICY_US_EQUITY_CASH,
            )
        self.assertEqual(
            mapping_semantic_policy(PLAN, "XAUUSD"),
            MAPPING_POLICY_GENERIC,
        )

    def test_02_cash_and_24h_are_distinct_broker_products(self):
        standard = broker_product_profile(
            light(804, "AAPL.US", "Apple Inc"),
            full(804, cash_schedule()),
            assets_by_id=ASSETS,
        )
        around_clock = broker_product_profile(
            light(2999, "AAPL.US-24", "Apple Inc (24 Hours)"),
            full(2999, extended_schedule()),
            assets_by_id=ASSETS,
        )
        self.assertEqual(standard["session_class"], "US_CASH_SESSION_LIKE")
        self.assertEqual(standard["weekly_open_hours"], 32.5)
        self.assertEqual(around_clock["session_class"], "EXTENDED_24_5_LIKE")
        self.assertEqual(around_clock["weekly_open_hours"], 117.5)
        self.assertNotEqual(
            standard["product_semantic_fingerprint_sha256"],
            around_clock["product_semantic_fingerprint_sha256"],
        )

    def test_03_c011_selects_cash_product_without_user_prompt(self):
        symbols = [
            light(804, "AAPL.US", "Apple Inc"),
            light(2999, "AAPL.US-24", "Apple Inc (24 Hours)"),
        ]
        discovery = discover_symbol_mapping("AAPL", symbols, assets_by_id=ASSETS)
        selector = Mock(side_effect=AssertionError("user must not choose session variant"))
        selected, profile, source, policy, profiles = resolve_profiled_broker_product(
            "AAPL",
            PLAN,
            discovery,
            symbols,
            {
                804: full(804, cash_schedule()),
                2999: full(2999, extended_schedule()),
            },
            assets_by_id=ASSETS,
            selector=selector,
        )
        selector.assert_not_called()
        self.assertEqual(selected["symbolId"], 804)
        self.assertEqual(profile["session_class"], "US_CASH_SESSION_LIKE")
        self.assertEqual(source, "AUTO_FROZEN_C011_CASH_SESSION")
        self.assertEqual(policy, MAPPING_POLICY_US_EQUITY_CASH)
        self.assertEqual(len(profiles), 2)

    def test_04_reversing_ids_and_names_does_not_change_semantic_choice(self):
        symbols = [
            light(99, "AAPL.US-24", "Apple Inc (24 Hours)"),
            light(5, "AAPL.US", "Apple Inc"),
        ]
        discovery = discover_symbol_mapping("AAPL", symbols, assets_by_id=ASSETS)
        selected, profile, source, _, _ = resolve_profiled_broker_product(
            "AAPL",
            PLAN,
            discovery,
            symbols,
            {
                99: full(99, extended_schedule()),
                5: full(5, cash_schedule()),
            },
            assets_by_id=ASSETS,
        )
        self.assertEqual(selected["symbolName"], "AAPL.US")
        self.assertEqual(profile["session_class"], "US_CASH_SESSION_LIKE")
        self.assertEqual(source, "AUTO_FROZEN_C011_CASH_SESSION")

    def test_05_missing_full_metadata_blocks_instead_of_guessing(self):
        symbols = [
            light(804, "AAPL.US", "Apple Inc"),
            light(2999, "AAPL.US-24", "Apple Inc (24 Hours)"),
        ]
        discovery = discover_symbol_mapping("AAPL", symbols, assets_by_id=ASSETS)
        with self.assertRaisesRegex(MappingError, "full LIVE metadata missing"):
            resolve_profiled_broker_product(
                "AAPL",
                PLAN,
                discovery,
                symbols,
                {804: full(804, cash_schedule())},
                assets_by_id=ASSETS,
            )

    def test_06_two_cash_products_block_if_frozen_semantics_do_not_make_identity_unique(self):
        symbols = [
            light(804, "AAPL.US", "Apple Inc"),
            light(805, "AAPL-US", "Apple Inc"),
        ]
        discovery = discover_symbol_mapping("AAPL", symbols, assets_by_id=ASSETS)
        selector = Mock()
        with self.assertRaisesRegex(MappingError, "requires one current LIVE"):
            resolve_profiled_broker_product(
                "AAPL",
                PLAN,
                discovery,
                symbols,
                {
                    804: full(804, cash_schedule()),
                    805: full(805, cash_schedule()),
                },
                assets_by_id=ASSETS,
                selector=selector,
            )
        selector.assert_not_called()

    def test_07_wrong_saved_24h_override_is_cleared_then_cash_product_selected(self):
        symbols = [
            light(804, "AAPL.US", "Apple Inc"),
            light(2999, "AAPL.US-24", "Apple Inc (24 Hours)"),
        ]
        discovery = discover_symbol_mapping("AAPL", symbols, assets_by_id=ASSETS)
        cleared = []
        selected, profile, source, _, _ = resolve_profiled_broker_product(
            "AAPL",
            PLAN,
            discovery,
            symbols,
            {
                804: full(804, cash_schedule()),
                2999: full(2999, extended_schedule()),
            },
            assets_by_id=ASSETS,
            saved_override={
                "symbol_id": 2999,
                "broker_symbol": "AAPL.US-24",
                "source_environment": "Pepperstone - Europe LIVE",
            },
            clear_saved=lambda canonical: cleared.append(canonical),
        )
        self.assertEqual(cleared, ["AAPL"])
        self.assertEqual(selected["symbolId"], 804)
        self.assertEqual(profile["session_class"], "US_CASH_SESSION_LIKE")
        self.assertEqual(source, "AUTO_FROZEN_C011_CASH_SESSION")

    def test_08_generic_distinct_session_products_do_not_go_to_manual_selector(self):
        generic_plan = {"candidate_dataset_bindings": []}
        symbols = [
            light(1, "FOO.US", "Foo Inc"),
            light(2, "FOO.US-24", "Foo Inc (24 Hours)"),
        ]
        discovery = discover_symbol_mapping("FOO", symbols)
        selector = Mock()
        with self.assertRaisesRegex(MappingError, "different execution/session semantics"):
            resolve_profiled_broker_product(
                "FOO",
                generic_plan,
                discovery,
                symbols,
                {1: full(1, cash_schedule()), 2: full(2, extended_schedule())},
                selector=selector,
            )
        selector.assert_not_called()

    def test_09_manual_fallback_remains_only_for_semantically_equivalent_products(self):
        generic_plan = {"candidate_dataset_bindings": []}
        symbols = [
            light(1, "FOO.US", "Foo Inc"),
            light(2, "FOO-US", "Foo Inc"),
        ]
        discovery = discover_symbol_mapping("FOO", symbols)
        selector = Mock(return_value=2)
        selected, profile, source, policy, _ = resolve_profiled_broker_product(
            "FOO",
            generic_plan,
            discovery,
            symbols,
            {1: full(1, cash_schedule()), 2: full(2, cash_schedule())},
            selector=selector,
        )
        selector.assert_called_once()
        self.assertEqual(selected["symbolId"], 2)
        self.assertEqual(profile["session_class"], "US_CASH_SESSION_LIKE")
        self.assertEqual(source, "LOCAL_EQUIVALENT_PRODUCT_SELECTION")
        self.assertEqual(policy, MAPPING_POLICY_GENERIC)

    def test_10_economic_fields_cannot_change_product_semantic_resolution(self):
        symbols = [
            light(804, "AAPL.US", "Apple Inc"),
            light(2999, "AAPL.US-24", "Apple Inc (24 Hours)"),
        ]
        polluted = [
            dict(symbols[0], pnl=-99999, legacy_rank=999, old_winner=False),
            dict(symbols[1], pnl=99999, legacy_rank=1, old_winner=True),
        ]
        for rows in (symbols, polluted):
            discovery = discover_symbol_mapping("AAPL", rows, assets_by_id=ASSETS)
            selected, _, _, _, _ = resolve_profiled_broker_product(
                "AAPL",
                PLAN,
                discovery,
                rows,
                {
                    804: full(804, cash_schedule()),
                    2999: full(2999, extended_schedule()),
                },
                assets_by_id=ASSETS,
            )
            self.assertEqual(selected["symbolId"], 804)

    def test_11_checkpoint_preserves_zero_economics(self):
        cp = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        self.assertEqual(
            cp["staging_parent_head"],
            "270ef9c5bc0a3f5926021660f64c9e2f8d57c51a",
        )
        self.assertTrue(cp["broker_product_resolution"]["full_metadata_before_selection"])
        self.assertTrue(cp["broker_product_resolution"]["c011_cash_session_semantic_gate"])
        self.assertFalse(cp["broker_product_resolution"]["user_selects_different_session_variant"])
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
