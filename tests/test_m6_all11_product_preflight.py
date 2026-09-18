import json
import unittest
from pathlib import Path

from m6.ctrader_capture import (
    CaptureContractError,
    TRANSFERABLE_REQUIRED_FILES,
    _validate_transfer_names,
)

from m6.broker_product_identity import (
    CANONICAL_ORDER,
    PRODUCT_FAMILIES,
    build_catalog,
    build_current_catalog_artifact,
    classify_product_family,
    format_preflight_matrix,
    product_profile,
    relevant_symbol_ids,
    resolve_all_11,
)

ROOT = Path(__file__).resolve().parents[1]


ASSETS = [
    {"assetId": 1, "name": "USD"},
    {"assetId": 2, "name": "AUD"},
    {"assetId": 3, "name": "JPY"},
    {"assetId": 4, "name": "XAU", "displayName": "Gold"},
    {"assetId": 5, "name": "BTC", "displayName": "Bitcoin"},
    {"assetId": 6, "name": "US500"},
    {"assetId": 7, "name": "NAS100"},
    {"assetId": 8, "name": "WTI", "displayName": "WTI Crude Oil"},
    {"assetId": 9, "name": "BRENT"},
    {"assetId": 10, "name": "NATGAS"},
    {"assetId": 11, "name": "GASOLINE"},
    {"assetId": 20, "name": "AAPL"},
    {"assetId": 21, "name": "MSFT"},
    {"assetId": 22, "name": "NVDA"},
    {"assetId": 23, "name": "AMZN"},
    {"assetId": 24, "name": "META"},
]
ASSET_CLASSES = [
    {"id": 1000, "name": "Indices"},
    {"id": 1001, "name": "Perpetual Index"},
    {"id": 2000, "name": "Commodities"},
    {"id": 2001, "name": "Perpetual Commodity"},
    {"id": 3000, "name": "Cryptocurrencies"},
    {"id": 4000, "name": "Forex"},
    {"id": 5000, "name": "US Shares"},
    {"id": 5001, "name": "Perpetual Shares"},
]
CATEGORIES = [
    {"id": 100, "name": "Index CFDs", "assetClassId": 1000},
    {"id": 101, "name": "Perpetual Index CFDs", "assetClassId": 1001},
    {"id": 200, "name": "Commodity CFDs", "assetClassId": 2000},
    {"id": 201, "name": "Perpetual Commodity CFDs", "assetClassId": 2001},
    {"id": 300, "name": "Crypto CFDs", "assetClassId": 3000},
    {"id": 400, "name": "Forex", "assetClassId": 4000},
    {"id": 500, "name": "US Shares", "assetClassId": 5000},
    {"id": 501, "name": "Perpetual Shares", "assetClassId": 5001},
]
A = build_catalog(ASSETS, ("assetId",))
C = build_catalog(CATEGORIES, ("id",))
AC = build_catalog(ASSET_CLASSES, ("id",))


def light(sid, name, category, base, quote=1, description="", enabled=True, **extra):
    row = {
        "symbolId": sid,
        "symbolName": name,
        "symbolCategoryId": category,
        "baseAssetId": base,
        "quoteAssetId": quote,
        "description": description,
        "enabled": enabled,
    }
    row.update(extra)
    return row


def full(sid, *, trading_mode=0, hours=23):
    return {
        "symbolId": sid,
        "tradingMode": trading_mode,
        "scheduleTimeZone": "UTC",
        "schedule": [{"startSecond": 86400, "endSecond": 86400 + hours * 3600}],
        "minVolume": 100,
        "maxVolume": 1000000,
        "stepVolume": 100,
        "lotSize": 100,
        "measurementUnits": "units",
        "enableShortSelling": True,
        "holiday": [],
    }


def universe():
    rows = [
        light(1001, "US500", 100, 6, description="S&P 500 cash index CFD"),
        light(1002, "US500-F", 100, 6, description="US500 Forward CFD"),
        light(1003, "US500-PERP", 101, 6, description="SP500 Perpetual CFD"),
        light(1101, "NAS100", 100, 7, description="NASDAQ 100 cash index CFD"),
        light(1102, "NAS100-F", 100, 7, description="NAS100 Forward CFD"),
        light(1103, "NAS100-PERP", 101, 7, description="NAS100 Perpetual CFD"),
        light(1201, "XAUUSD", 200, 4, description="Spot Gold"),
        light(1202, "XAUUSD-F", 200, 4, description="Gold Forward CFD"),
        light(1301, "SpotCrude", 200, 8, description="WTI Crude Oil Spot"),
        light(1302, "Crude-F", 200, 8, description="WTI Crude Forward CFD"),
        light(1303, "SpotBrent", 200, 9, description="Brent crude oil spot"),
        light(1304, "NatGas", 200, 10, description="Natural Gas spot"),
        light(1305, "Gasoline", 200, 11, description="Gasoline spot"),
        light(1306, "WTI-PERP", 201, 8, description="WTI Perpetual CFD"),
        light(1401, "BTCUSD", 300, 5, description="Bitcoin / US Dollar"),
        light(1402, "BTCUSD-PERP", 201, 5, description="Bitcoin Perpetual CFD"),
        light(1501, "AUDJPY", 400, 2, quote=3, description="Australian Dollar / Japanese Yen"),
    ]
    base_by_ticker = {"AAPL": 20, "MSFT": 21, "NVDA": 22, "AMZN": 23, "META": 24}
    sid = 2000
    for ticker, base in base_by_ticker.items():
        rows.extend([
            light(sid + 1, f"{ticker}.US", 500, base, description=f"{ticker} standard share CFD"),
            light(sid + 2, f"{ticker}.US-24", 500, base, description=f"{ticker} (24 Hours)"),
            light(sid + 3, f"{ticker}.US-PERP", 501, base, description=f"{ticker} Perpetual CFD"),
        ])
        sid += 10
    return rows


def full_map(rows):
    return {int(row["symbolId"]): full(int(row["symbolId"])) for row in rows}


class BrokerProductIdentityTests(unittest.TestCase):
    def classify(self, row):
        fam, evidence, conflicts = classify_product_family(
            row,
            full(row["symbolId"]),
            assets_by_id=A,
            categories_by_id=C,
            asset_classes_by_id=AC,
        )
        return fam, evidence, conflicts

    def test_01_taxonomy_is_complete(self):
        required = {
            "FX_SPOT_OR_MARGIN_CFD", "SPOT_METAL_CFD", "SPOT_ENERGY_CFD",
            "SPOT_CRYPTO_CFD", "CASH_INDEX_CFD", "INDEX_FORWARD_OR_FUTURES_CFD",
            "COMMODITY_FORWARD_OR_FUTURES_CFD", "STANDARD_CASH_SHARE_CFD",
            "EXTENDED_HOURS_SHARE_CFD", "PERPETUAL_INDEX_CFD",
            "PERPETUAL_SHARE_CFD", "PERPETUAL_COMMODITY_CFD",
            "OTHER_PERPETUAL_CFD", "OTHER_CFD", "UNKNOWN",
        }
        self.assertEqual(PRODUCT_FAMILIES, required)

    def test_02_us500_cash_forward_perpetual_are_distinct(self):
        rows = universe()
        by_name = {x["symbolName"]: x for x in rows}
        self.assertEqual(self.classify(by_name["US500"])[0], "CASH_INDEX_CFD")
        self.assertEqual(self.classify(by_name["US500-F"])[0], "INDEX_FORWARD_OR_FUTURES_CFD")
        self.assertEqual(self.classify(by_name["US500-PERP"])[0], "PERPETUAL_INDEX_CFD")

    def test_03_nas100_cash_forward_perpetual_are_distinct(self):
        rows = universe()
        by_name = {x["symbolName"]: x for x in rows}
        self.assertEqual(self.classify(by_name["NAS100"])[0], "CASH_INDEX_CFD")
        self.assertEqual(self.classify(by_name["NAS100-F"])[0], "INDEX_FORWARD_OR_FUTURES_CFD")
        self.assertEqual(self.classify(by_name["NAS100-PERP"])[0], "PERPETUAL_INDEX_CFD")

    def test_04_xau_spot_vs_forward(self):
        rows = universe()
        by_name = {x["symbolName"]: x for x in rows}
        self.assertEqual(self.classify(by_name["XAUUSD"])[0], "SPOT_METAL_CFD")
        self.assertEqual(self.classify(by_name["XAUUSD-F"])[0], "COMMODITY_FORWARD_OR_FUTURES_CFD")

    def test_05_wti_family_separates_spot_forward_other_energy_and_perpetual(self):
        rows = universe()
        by_name = {x["symbolName"]: x for x in rows}
        self.assertEqual(self.classify(by_name["SpotCrude"])[0], "SPOT_ENERGY_CFD")
        self.assertEqual(self.classify(by_name["Crude-F"])[0], "COMMODITY_FORWARD_OR_FUTURES_CFD")
        self.assertEqual(self.classify(by_name["SpotBrent"])[0], "SPOT_ENERGY_CFD")
        self.assertEqual(self.classify(by_name["NatGas"])[0], "SPOT_ENERGY_CFD")
        self.assertEqual(self.classify(by_name["Gasoline"])[0], "SPOT_ENERGY_CFD")
        self.assertEqual(self.classify(by_name["WTI-PERP"])[0], "PERPETUAL_COMMODITY_CFD")

    def test_06_btc_and_audjpy_standard_products(self):
        rows = universe()
        by_name = {x["symbolName"]: x for x in rows}
        self.assertEqual(self.classify(by_name["BTCUSD"])[0], "SPOT_CRYPTO_CFD")
        self.assertEqual(self.classify(by_name["BTCUSD-PERP"])[0], "OTHER_PERPETUAL_CFD")
        self.assertEqual(self.classify(by_name["AUDJPY"])[0], "FX_SPOT_OR_MARGIN_CFD")

    def test_07_all_five_share_underlyings_cash_24h_perpetual_are_generic(self):
        rows = universe()
        by_name = {x["symbolName"]: x for x in rows}
        for ticker in ("AAPL", "MSFT", "NVDA", "AMZN", "META"):
            self.assertEqual(self.classify(by_name[f"{ticker}.US"])[0], "STANDARD_CASH_SHARE_CFD")
            self.assertEqual(self.classify(by_name[f"{ticker}.US-24"])[0], "EXTENDED_HOURS_SHARE_CFD")
            self.assertEqual(self.classify(by_name[f"{ticker}.US-PERP"])[0], "PERPETUAL_SHARE_CFD")

    def test_08_perpetual_precedence_and_contradiction_fail_closed(self):
        p = light(9001, "US500-PERP", 101, 6, description="Perpetual Index")
        self.assertEqual(self.classify(p)[0], "PERPETUAL_INDEX_CFD")
        bad = light(9002, "US500-F", 101, 6, description="Perpetual Index Forward")
        fam, _, conflicts = self.classify(bad)
        self.assertEqual(fam, "UNKNOWN")
        self.assertIn("CONTRADICTORY_PERPETUAL_AND_FORWARD_MARKERS", conflicts)

    def test_09_schedule_duration_does_not_define_index_product_family(self):
        row = light(9003, "US500", 100, 6, description="S&P 500 cash index CFD")
        fam, _, _ = classify_product_family(
            row, full(9003, hours=23),
            assets_by_id=A, categories_by_id=C, asset_classes_by_id=AC,
        )
        self.assertEqual(fam, "CASH_INDEX_CFD")

    def test_10_all_11_resolve_before_capture(self):
        rows = universe()
        result = resolve_all_11(
            rows, full_map(rows),
            assets_by_id=A, categories_by_id=C, asset_classes_by_id=AC,
        )
        self.assertEqual(result["pass_count"], 11)
        self.assertEqual(result["required_count"], 11)
        self.assertTrue(result["all_current_mappings_pass"])
        self.assertTrue(result["historical_capture_authorized_by_preflight"])
        self.assertEqual([x["canonical"] for x in result["matrix"]], list(CANONICAL_ORDER))
        expected = {
            "US500": "US500", "NAS100": "NAS100", "XAUUSD": "XAUUSD",
            "WTIUSD": "SpotCrude", "BTCUSD": "BTCUSD", "AUDJPY": "AUDJPY",
            "AAPL": "AAPL.US", "MSFT": "MSFT.US", "NVDA": "NVDA.US",
            "AMZN": "AMZN.US", "META": "META.US",
        }
        self.assertEqual(
            {k: v["selected_current_product"]["symbol_name"] for k, v in result["bridge"].items()},
            expected,
        )

    def test_11_one_failure_keeps_complete_all11_diagnostics_and_blocks_history(self):
        rows = [x for x in universe() if x["symbolName"] != "SpotCrude"]
        result = resolve_all_11(
            rows, full_map(rows),
            assets_by_id=A, categories_by_id=C, asset_classes_by_id=AC,
        )
        self.assertEqual(result["pass_count"], 10)
        self.assertFalse(result["all_current_mappings_pass"])
        self.assertFalse(result["historical_capture_authorized_by_preflight"])
        self.assertEqual(len(result["matrix"]), 11)
        self.assertEqual(result["bridge"]["WTIUSD"]["status"], "BLOCKED")
        excluded = result["bridge"]["WTIUSD"]["excluded_materially_different_products"]
        names = {x["broker_symbol"] for x in excluded}
        self.assertTrue({"Crude-F", "SpotBrent", "NatGas", "Gasoline", "WTI-PERP"} <= names)
        lines = format_preflight_matrix(result)
        self.assertIn("CAPTURE NOT STARTED", lines[0])
        self.assertEqual(len(lines), 13)

    def test_12_archived_product_never_replaces_current_enabled_product(self):
        rows = [x for x in universe() if x["symbolName"] != "AAPL.US"]
        archived = [{
            "symbolId": 99991, "symbolName": "AAPL.US",
            "description": "old Apple share CFD", "utcLastUpdateTimestamp": 1,
        }]
        result = resolve_all_11(
            rows, full_map(rows), archived_symbols=archived,
            assets_by_id=A, categories_by_id=C, asset_classes_by_id=AC,
        )
        self.assertEqual(result["bridge"]["AAPL"]["status"], "BLOCKED")
        self.assertEqual(
            result["bridge"]["AAPL"]["archived_lineage_evidence"][0]["role"],
            "ARCHIVED_LINEAGE_EVIDENCE_ONLY_NOT_CURRENT_MAPPING",
        )

    def test_13_economic_and_legacy_fields_cannot_change_mapping(self):
        clean = universe()
        dirty = [
            dict(x, pnl=999999 if x["symbolName"].endswith("-24") else -999999,
                 legacy_rank=1, candidate_rank=1, old_result="WINNER")
            for x in clean
        ]
        a = resolve_all_11(
            clean, full_map(clean), assets_by_id=A, categories_by_id=C, asset_classes_by_id=AC
        )
        b = resolve_all_11(
            dirty, full_map(dirty), assets_by_id=A, categories_by_id=C, asset_classes_by_id=AC
        )
        self.assertEqual(
            {k: v["selected_current_product"]["symbol_id"] for k, v in a["bridge"].items()},
            {k: v["selected_current_product"]["symbol_id"] for k, v in b["bridge"].items()},
        )
        self.assertFalse(a["economic_information_used"])
        self.assertFalse(a["legacy_information_used"])

    def test_14_current_mapping_does_not_promote_historical_metadata(self):
        rows = universe()
        preflight = resolve_all_11(
            rows, full_map(rows), assets_by_id=A, categories_by_id=C, asset_classes_by_id=AC
        )
        catalog = build_current_catalog_artifact(
            account_environment="Pepperstone - Europe LIVE",
            broker="Pepperstone",
            account_fingerprint_sha256="abc",
            assets=ASSETS, asset_classes=ASSET_CLASSES, symbol_categories=CATEGORIES,
            light_symbols=rows, archived_symbols=[], full_by_id=full_map(rows), preflight=preflight,
        )
        self.assertTrue(catalog["current_schedule_not_historical_schedule"])
        self.assertTrue(catalog["current_structural_metadata_not_historical_metadata"])
        for item in preflight["bridge"].values():
            self.assertTrue(item["current_mapping_is_not_historical_metadata"])

    def test_15_runtime_inventory_archives_and_all11_gate_precede_aux_and_history(self):
        source = (ROOT / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        self.assertIn("includeArchivedSymbols=True", source)
        self.assertIn("resolve_all_11(", source)
        gate = source.index("if passed_after_binding != len(preflight")
        aux = source.index("self._capture_expected_margin(account_id)")
        history = source.index("self._capture_raw_series(account_id, raw)")
        self.assertLess(gate, aux)
        self.assertLess(gate, history)
        self.assertIn("BROKER PRODUCT PREFLIGHT: 11/11 PASS", source)

    def test_16_conversion_expected_margin_and_accounts_scope_remain_read_only(self):
        source = (ROOT / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        self.assertIn("ProtoOASymbolsForConversionReq", source)
        self.assertIn("ProtoOAExpectedMarginReq", source)
        self.assertIn('"order_placed": False', source)
        oauth = (ROOT / "m6/pydroid_oauth.py").read_text(encoding="utf-8")
        from m6 import ctrader_capture as capture_module
        self.assertEqual(capture_module.READ_ONLY_SCOPE, "accounts")
        self.assertIn("READ_ONLY_SCOPE,", oauth)
        self.assertIn('"eur200_feasibility": "UNRESOLVED_MINIMUM_EXECUTABLE_VOLUME_MARGIN_ONLY"', source)
        self.assertIn('"approximate_formula_used": False', source)
        for forbidden in (
            "ProtoOANewOrderReq", "ProtoOACancelOrderReq", "ProtoOAAmendOrderReq",
            "ProtoOAClosePositionReq",
        ):
            self.assertNotIn(forbidden, source)

    def test_17_tick_history_is_reviewed_but_not_broadly_downloaded(self):
        source = (ROOT / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        self.assertNotIn("ProtoOAGetTickDataReq", source)
        provenance = json.loads(
            (ROOT / "evidence/BROKER_PRODUCT_IDENTITY_SOURCES_V1.json").read_text(encoding="utf-8")
        )
        facts = json.dumps(provenance)
        self.assertIn("ProtoOAGetTickDataReq", facts)

    def test_18_public_source_provenance_is_current_only(self):
        provenance = json.loads(
            (ROOT / "evidence/BROKER_PRODUCT_IDENTITY_SOURCES_V1.json").read_text(encoding="utf-8")
        )
        self.assertIn("NOT_HISTORICAL_2022_2026_TRUTH", provenance["classification"])
        source_ids = {x["source_id"] for x in provenance["sources"]}
        self.assertIn("CTRADER_MESSAGES_PROTO_CURRENT", source_ids)
        self.assertIn("PEPPERSTONE_COMMODITIES_CURRENT", source_ids)
        self.assertIn("PEPPERSTONE_SHARE_24H_CURRENT", source_ids)
        self.assertIn("PEPPERSTONE_PERPETUAL_CURRENT", source_ids)
        self.assertFalse(provenance["protobuf_packaged_schema_note"]["generated_message_files_replaced"])

    def test_19_zero_economics_protected_boundary_and_m6_pending(self):
        state = json.loads((ROOT / "CURRENT_STATE.json").read_text(encoding="utf-8"))
        protected = json.loads((ROOT / "V2_PROTECTED_FORWARD_START.json").read_text(encoding="utf-8"))
        ledger = [
            json.loads(x) for x in (ROOT / "discovery/ledger.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        self.assertEqual(state["economic_outcomes_opened"], 0)
        self.assertEqual(state["v2_attempts_used"], 0)
        self.assertEqual(state["v2_evaluated_identities"], 0)
        self.assertEqual(state["m6"]["status"], "PENDING")
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])
        self.assertFalse(protected["protected_evidence_opened"])
        self.assertFalse(any(x["entry_type"] == "RESULT_RECORDED" for x in ledger))

    def test_20_relevant_full_metadata_scope_covers_material_variants_without_whole_market_history(self):
        rows = universe()
        ids = relevant_symbol_ids(
            rows, assets_by_id=A, categories_by_id=C, asset_classes_by_id=AC
        )
        self.assertEqual(ids, {int(x["symbolId"]) for x in rows})
        source = (ROOT / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        self.assertIn("Structural relevance is evaluated over the complete CURRENT light-symbol", source)
        self.assertNotIn("whole universe backtest", source.lower())


    def test_21_success_bundle_rejects_stale_blocked_marker(self):
        names = set(TRANSFERABLE_REQUIRED_FILES)
        names.update({f"raw/series_{i:02d}.csv" for i in range(11)})
        with self.assertRaisesRegex(
            CaptureContractError,
            "must not contain BLOCKED.json",
        ):
            _validate_transfer_names(names | {"BLOCKED.json"})

    def test_22_runtime_cleans_deterministic_bundle_dir_before_rerun(self):
        source = (ROOT / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        run_start = source.index("def run(self) -> Path:")
        workflow = source.index("def _workflow(self) -> None:")
        run_block = source[run_start:workflow]
        self.assertIn("shutil.rmtree(self.bundle_dir)", run_block)
        self.assertIn('(self.bundle_dir / "BLOCKED.json").unlink(missing_ok=True)', source)



if __name__ == "__main__":
    unittest.main(verbosity=2)
