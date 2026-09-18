import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from m6.ctrader_capture import (
    MappingError,
    READ_ONLY_SCOPE,
    build_asset_catalog,
    discover_symbol_mapping,
    live_account_candidates,
    resolve_or_select_symbol_mapping,
    resolve_symbol_mapping,
)
import m6.pydroid_symbol_mapping as localmap

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "data" / "PRIMARY_WAVE_02_M6_CAPTURE_CLIENT_CHECKPOINT_V9.json"


def sym(symbol_id, name, *, enabled=True, description="", base=None, quote=None, category=None, **extra):
    row = {
        "symbolId": symbol_id,
        "symbolName": name,
        "enabled": enabled,
        "description": description,
    }
    if base is not None:
        row["baseAssetId"] = base
    if quote is not None:
        row["quoteAssetId"] = quote
    if category is not None:
        row["symbolCategoryId"] = category
    row.update(extra)
    return row


class M6LiveSymbolMappingTests(unittest.TestCase):
    def test_01_exact_canonical_name_resolves_uniquely(self):
        rows = [sym(1, "AAPL"), sym(2, "MSFT")]
        selected = resolve_symbol_mapping("AAPL", rows)
        self.assertEqual(selected["symbolId"], 1)

    def test_02_mechanical_suffix_punctuation_variant_resolves_identity_only(self):
        rows = [sym(7, "FOO.US", description="Foo Inc")]
        discovery = discover_symbol_mapping("FOO", rows)
        self.assertEqual(len(discovery["exact_candidates"]), 0)
        self.assertEqual(len(discovery["relaxed_candidates"]), 1)
        self.assertIn(
            "CANONICAL_FIRST_BROKER_TOKEN",
            discovery["relaxed_candidates"][0]["support"],
        )
        selected = resolve_symbol_mapping("FOO", rows)
        self.assertEqual(selected["symbolId"], 7)

    def test_03_asset_identity_can_support_generic_mapping(self):
        assets = build_asset_catalog([
            {"assetId": 10, "name": "AAPL", "displayName": "Apple"},
            {"assetId": 20, "name": "USD", "displayName": "US Dollar"},
        ])
        rows = [
            sym(
                8,
                "BrokerStock.42",
                enabled=True,
                description="Apple Inc",
                base=10,
                quote=20,
            )
        ]
        discovery = discover_symbol_mapping("AAPL", rows, assets_by_id=assets)
        self.assertEqual(len(discovery["relaxed_candidates"]), 1)
        self.assertIn(
            "BASE_ASSET_IDENTITY",
            discovery["relaxed_candidates"][0]["support"],
        )
        self.assertEqual(
            resolve_symbol_mapping("AAPL", rows, assets_by_id=assets)["symbolId"],
            8,
        )

    def test_04_ambiguous_mechanical_matches_do_not_auto_resolve(self):
        rows = [
            sym(1, "AAPL.US", description="Apple Inc"),
            sym(2, "AAPL-US", description="Apple Inc"),
        ]
        discovery = discover_symbol_mapping("AAPL", rows)
        self.assertEqual(len(discovery["credible_candidates"]), 2)
        with self.assertRaises(MappingError):
            resolve_symbol_mapping("AAPL", rows)

    def test_05_zero_auto_match_invokes_local_selection_path(self):
        rows = [
            sym(11, "US-EQ-001", description="AAPL reference instrument"),
        ]
        called = []

        def selector(canonical, discovery):
            called.append((canonical, discovery))
            self.assertEqual(len(discovery["credible_candidates"]), 0)
            self.assertEqual(len(discovery["related_candidates"]), 1)
            return discovery["related_candidates"][0]["symbol_id"]

        selected, source, _ = resolve_or_select_symbol_mapping(
            "AAPL",
            rows,
            selector=selector,
        )
        self.assertEqual(selected["symbolId"], 11)
        self.assertEqual(source, "LOCAL_USER_SELECTION")
        self.assertEqual(len(called), 1)

    def test_06_user_can_choose_block_none(self):
        rows = [sym(11, "US-EQ-001", description="AAPL reference instrument")]
        with self.assertRaisesRegex(MappingError, "BLOCK"):
            resolve_or_select_symbol_mapping(
                "AAPL",
                rows,
                selector=lambda canonical, discovery: 0,
            )

    def test_07_valid_persisted_override_reused_only_while_same_live_symbol_valid(self):
        rows = [sym(21, "AAPL.US", description="Apple Inc", enabled=True)]
        saved = {
            "symbol_id": 21,
            "broker_symbol": "AAPL.US",
            "source_environment": "Pepperstone - Europe LIVE",
        }
        selected, source, _ = resolve_or_select_symbol_mapping(
            "AAPL",
            rows,
            saved_override=saved,
            selector=lambda *_: self.fail("selector must not run for valid override"),
        )
        self.assertEqual(selected["symbolId"], 21)
        self.assertEqual(source, "PERSISTED_LOCAL_OVERRIDE")

    def test_08_stale_disabled_saved_override_is_cleared_and_forces_reselection(self):
        rows = [
            sym(31, "AAPL.US", description="Apple Inc", enabled=False),
            sym(32, "AAPL-US", description="Apple Inc", enabled=True),
        ]
        saved = {
            "symbol_id": 31,
            "broker_symbol": "AAPL.US",
            "source_environment": "Pepperstone - Europe LIVE",
        }
        cleared = []
        selected_calls = []

        def selector(canonical, discovery):
            selected_calls.append(canonical)
            return 32

        selected, source, _ = resolve_or_select_symbol_mapping(
            "AAPL",
            rows,
            saved_override=saved,
            selector=selector,
            clear_saved=lambda canonical: cleared.append(canonical),
        )
        self.assertEqual(cleared, ["AAPL"])
        self.assertEqual(selected_calls, ["AAPL"])
        self.assertEqual(selected["symbolId"], 32)
        self.assertEqual(source, "LOCAL_USER_SELECTION")

    def test_09_economic_or_legacy_fields_cannot_change_mapping(self):
        clean = [sym(41, "AAPL.US", description="Apple Inc")]
        polluted = [
            sym(
                41,
                "AAPL.US",
                description="Apple Inc",
                legacy_strategy_score=-999,
                pnl=123456,
                candidate_rank=1,
                old_result="WINNER",
            )
        ]
        a = resolve_symbol_mapping("AAPL", clean)
        b = resolve_symbol_mapping("AAPL", polluted)
        self.assertEqual(a["symbolId"], b["symbolId"])
        self.assertEqual(a["symbolName"], b["symbolName"])

    def test_10_demo_accounts_are_excluded_from_authoritative_live_candidates(self):
        accounts = [
            {"ctidTraderAccountId": 1, "isLive": False, "brokerTitleShort": "Pepperstone"},
            {"ctidTraderAccountId": 2, "isLive": True, "brokerTitleShort": "Pepperstone"},
        ]
        live = live_account_candidates(accounts)
        self.assertEqual([int(x["ctidTraderAccountId"]) for x in live], [2])

    def test_11_accounts_read_only_contract_and_no_trading_request_added(self):
        self.assertEqual(READ_ONLY_SCOPE, "accounts")
        source = (ROOT / "m6/ctrader_openapi.py").read_text(encoding="utf-8")
        for forbidden in (
            "ProtoOANewOrderReq",
            "ProtoOACancelOrderReq",
            "ProtoOAAmendOrderReq",
            "ProtoOAClosePositionReq",
            'scope="trading"',
            "scope='trading'",
        ):
            self.assertNotIn(forbidden, source)

    def test_12_protobuf_only_android_bootstrap_unchanged(self):
        requirements = (ROOT / "tools/requirements-m6-capture.txt").read_text(
            encoding="utf-8"
        )
        self.assertEqual(requirements.strip(), "protobuf==3.20.1")
        entry = (ROOT / "M6_CAPTURE_RUN.py").read_text(encoding="utf-8")
        self.assertIn("[BOOTSTRAP PASS] Pure-Python protobuf runtime already installed.", entry)
        for forbidden in ("cryptography==", "Twisted==", "pyOpenSSL==", "ctrader-open-api=="):
            self.assertNotIn(forbidden, requirements + "\n" + entry)

    def test_13_local_mapping_file_roundtrip_and_environment_binding(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "symbol_mappings.json"
            with patch.object(localmap, "SYMBOL_MAPPING_PATH", path):
                localmap.save_symbol_override(
                    "AAPL",
                    {
                        "symbol_id": 51,
                        "broker_symbol": "AAPL.US",
                        "account_fingerprint_sha256": "abc",
                    },
                )
                loaded = localmap.load_symbol_overrides()
                localmap.clear_symbol_override("AAPL")
                after = localmap.load_symbol_overrides()
        self.assertEqual(loaded["AAPL"]["symbol_id"], 51)
        self.assertEqual(
            loaded["AAPL"]["source_environment"],
            "Pepperstone - Europe LIVE",
        )
        self.assertNotIn("AAPL", after)

    def test_14_checkpoint_preserves_zero_economic_state(self):
        cp = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        self.assertEqual(
            cp["staging_parent_head"],
            "63e2a239c1e7c0fa7f3893eb5c654eab82f1d006",
        )
        self.assertTrue(cp["symbol_mapping"]["generic_live_metadata_resolver"])
        self.assertTrue(cp["symbol_mapping"]["local_selection_fallback"])
        self.assertFalse(cp["symbol_mapping"]["legacy_used_to_decide_mapping"])
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
