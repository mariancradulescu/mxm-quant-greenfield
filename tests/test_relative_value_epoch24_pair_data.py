import csv
import hashlib
import io
import unittest

from research_v3.relative_value_epoch24_prerequisite import (
    PairDataError,
    _timestamp_set_sha256,
    product_quote_comparability,
    read_price_series_bytes,
    synchronize_pair,
)


def _raw(rows):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(("time_utc", "open", "high", "low", "close", "tick_volume"))
    for row in rows:
        writer.writerow(row)
    return stream.getvalue().encode()


def _rep(symbol, symbol_id, asset="DE Equities", product="STANDARD_CASH_SHARE_CFD"):
    return {
        "broker_symbol": symbol,
        "symbol_id": symbol_id,
        "signature": [asset, product, "REGIONAL_OR_CASH_SESSION_SCHEDULE", "EUROPE", False],
        "min_margin_eur": 1.0,
    }


class RelativeValueEpoch24PairDataTests(unittest.TestCase):
    def test_synchronizes_common_utc_bars_and_preserves_explicit_missingness(self):
        left_raw = _raw(
            [
                ("2026-01-01T00:00:00Z", 1, 1, 1, 1, 0),
                ("2026-01-01T00:05:00Z", 2, 2, 2, 2, 0),
                ("2026-01-01T00:10:00Z", 3, 3, 3, 3, 0),
            ]
        )
        right_raw = _raw(
            [
                ("2026-01-01T00:05:00Z", 4, 4, 4, 4, 0),
                ("2026-01-01T00:10:00Z", 5, 5, 5, 5, 0),
                ("2026-01-01T00:15:00Z", 6, 6, 6, 6, 0),
            ]
        )
        left = read_price_series_bytes(
            left_raw,
            hashlib.sha256(left_raw).hexdigest(),
            broker_symbol="AAA",
            symbol_id=1,
            canonicalize=False,
        )
        right = read_price_series_bytes(
            right_raw,
            hashlib.sha256(right_raw).hexdigest(),
            broker_symbol="BBB",
            symbol_id=2,
            canonicalize=False,
        )
        out = synchronize_pair(
            left,
            right,
            _rep("AAA", 1),
            _rep("BBB", 2),
            quote_unit_authority={"AAA": "EUR", "BBB": "EUR"},
            expected_common_m5_timestamps=2,
        )
        self.assertEqual(out["alignment"]["common_m5_timestamps"], 2)
        self.assertEqual(out["alignment"]["left_only_rows"], 1)
        self.assertEqual(out["alignment"]["right_only_rows"], 1)
        self.assertEqual(out["alignment"]["forward_filled_rows"], 0)
        self.assertEqual(out["alignment"]["imputed_rows"], 0)
        self.assertTrue(out["comparability"]["comparable"])
        self.assertFalse(out["economic_effect"]["returns_or_pnl_computed"])
        self.assertFalse(out["economic_effect"]["winning_pair_selected"])

    def test_conflicting_duplicate_is_rejected_even_when_canonicalization_allowed(self):
        raw = _raw(
            [
                ("2026-01-01T00:00:00Z", 1, 1, 1, 1, 0),
                ("2026-01-01T00:00:00Z", 1, 1, 1, 2, 0),
            ]
        )
        with self.assertRaisesRegex(PairDataError, "conflicting duplicate"):
            read_price_series_bytes(
                raw,
                hashlib.sha256(raw).hexdigest(),
                broker_symbol="AAA",
                symbol_id=1,
                canonicalize=True,
            )

    def test_broker_symbol_and_symbol_id_identity_fail_closed(self):
        raw = _raw([("2026-01-01T00:00:00Z", 1, 1, 1, 1, 0)])
        series = read_price_series_bytes(
            raw,
            hashlib.sha256(raw).hexdigest(),
            broker_symbol="AAA",
            symbol_id=1,
            canonicalize=False,
        )
        with self.assertRaisesRegex(PairDataError, "symbol-id identity mismatch"):
            synchronize_pair(
                series,
                series,
                _rep("AAA", 999),
                _rep("AAA", 1),
            )

    def test_quote_unit_is_explicit_and_never_inferred_from_symbol_name(self):
        no_metadata = product_quote_comparability(_rep("AAA", 1), _rep("BBB", 2))
        self.assertFalse(no_metadata["comparable"])
        self.assertIn("QUOTE_UNIT_UNKNOWN_FAIL_CLOSED", no_metadata["reasons"])
        self.assertFalse(no_metadata["quote_unit_inference_from_symbol_name"])

        mismatch = product_quote_comparability(
            _rep("AAA", 1),
            _rep("BBB", 2),
            quote_unit_authority={"AAA": "EUR", "BBB": "USD"},
        )
        self.assertFalse(mismatch["comparable"])
        self.assertIn("QUOTE_UNIT_MISMATCH", mismatch["reasons"])

    def test_ambiguous_product_type_fails_closed(self):
        out = product_quote_comparability(
            _rep("AAA", 1, product="OTHER_OR_TEST_CFD"),
            _rep("BBB", 2, product="OTHER_OR_TEST_CFD"),
            quote_unit_authority={"AAA": "EUR", "BBB": "EUR"},
        )
        self.assertFalse(out["comparable"])
        self.assertIn("AMBIGUOUS_PRODUCT_TYPE_FAIL_CLOSED", out["reasons"])

    def test_exact_broker_product_metadata_resolves_coarse_registry_label(self):
        authority = {
            "AAA": {
                "symbol_id": 1,
                "product_type": "OTHER_OR_TEST_CFD",
                "unit_family": "EQUITY_CFD",
                "lot_size": "100",
                "quote_asset": "EUR",
                "broker_metadata_complete": True,
                "source_ref": "accepted-current-broker-capture",
            },
            "BBB": {
                "symbol_id": 2,
                "product_type": "OTHER_OR_TEST_CFD",
                "unit_family": "EQUITY_CFD",
                "lot_size": "100",
                "quote_asset": "EUR",
                "broker_metadata_complete": True,
                "source_ref": "accepted-current-broker-capture",
            },
        }
        out = product_quote_comparability(
            _rep("AAA", 1, asset="AT Equities", product="OTHER_OR_TEST_CFD"),
            _rep("BBB", 2, asset="BE Equities", product="OTHER_OR_TEST_CFD"),
            quote_unit_authority=authority,
        )
        self.assertTrue(out["comparable"])
        self.assertTrue(out["rich_broker_product_metadata_used"])
        self.assertTrue(out["same_contract_unit"])
        self.assertFalse(out["quote_unit_inference_from_symbol_name"])

    def test_missingness_hash_is_order_invariant(self):
        a = _timestamp_set_sha256(
            {"2026-01-01T00:10:00Z", "2026-01-01T00:00:00Z"}
        )
        b = _timestamp_set_sha256(
            {"2026-01-01T00:00:00Z", "2026-01-01T00:10:00Z"}
        )
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
