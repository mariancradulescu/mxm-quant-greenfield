import base64
import gzip
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.deterministic_operation_executor import _validate_epoch47_compact_result
from research_v3.mean_reversion_epoch47_wave01_coarse_parameter_region_scan import (
    ScanError,
    _date_effective_n,
    _power_scenarios,
    scan_symbol,
    validate_freeze,
)


ROOT = Path(__file__).resolve().parents[1]

def bars(closes, *, start=None, gap_after=None):
    start = start or datetime(2026, 1, 5, tzinfo=timezone.utc)
    rows = []
    for index, close in enumerate(closes):
        offset = index + (1 if gap_after is not None and index >= gap_after else 0)
        rows.append({
            "timestamp": start + timedelta(minutes=5 * offset),
            "close": float(close),
        })
    return rows


class MeanReversionEpoch47Wave01ScanTests(unittest.TestCase):
    def test_scan_records_every_frozen_cell_without_response_fields(self):
        result = scan_symbol(
            bars([1, 1, 2, 2, 2, 1, 1, 2, 1]),
            symbol="TEST",
            symbol_id=1,
            structural_stratum={"asset_class": "TEST"},
        )
        self.assertEqual(len(result), 12)
        self.assertEqual(
            {(row["lookback_bars"], row["absolute_standardized_deviation_threshold"]) for row in result},
            {(lookback, threshold) for lookback in (12, 24, 48, 96) for threshold in (1.0, 1.5, 2.0)},
        )
        prohibited = {"return", "pnl", "response", "winner", "post_event"}
        for row in result:
            self.assertFalse(prohibited.intersection(row))
            self.assertIn("per_utc_date_event_counts", row)
            self.assertIn("closed_form_power_estimates", row)

    def test_event_clusters_rearm_inside_band_and_direct_opposite_crossing_rearms(self):
        result = scan_symbol(
            bars([1, 1, 2, 2, 2, 1]),
            symbol="TEST",
            symbol_id=1,
            structural_stratum={},
            lookbacks=(3,),
            thresholds=(0.5,),
        )[0]
        self.assertEqual(result["eligible_contiguous_windows"], 3)
        self.assertEqual(result["reversal_event_count"], 2)
        self.assertEqual(result["per_utc_date_event_counts"][0]["event_count"], 2)

    def test_timestamp_gaps_are_not_bridged(self):
        result = scan_symbol(
            bars([1, 2, 3, 4, 5, 6], gap_after=4),
            symbol="TEST",
            symbol_id=1,
            structural_stratum={},
            lookbacks=(3,),
            thresholds=(1.0,),
        )[0]
        self.assertEqual(result["eligible_contiguous_windows"], 2)

    def test_effective_sample_and_power_are_bounded_and_monotonic(self):
        dates = {datetime(2026, 1, day).date(): 0 for day in range(1, 11)}
        self.assertEqual(_date_effective_n(dates)["effective_n"], 10.0)
        powers = [item["estimated_power"] for item in _power_scenarios(30)]
        self.assertGreater(powers[0], powers[1])
        self.assertGreater(powers[1], powers[2])

    def test_repaired_operation_transport_is_hash_bound_pre_response_and_epoch_correct(self):
        freeze=json.loads((ROOT/"research_v3/EPOCH47_MEAN_REVERSION_WAVE01_COARSE_PARAMETER_REGION_FREEZE_V1.json").read_text())
        self.assertEqual(freeze["evidence_epoch"],45)
        self.assertEqual(freeze["research_sequence_label"],"EPOCH47")
        validate_freeze(freeze,ROOT)
        suff=json.loads((ROOT/"evidence/EPOCH46_OUTCOME_BLIND_M5_WAVE_01_DATA_SUFFICIENCY_V1.json").read_text())
        density=suff["outcome_blind_event_availability"]["mean_reversion_preregistered_grid_event_density"]
        self.assertEqual(density["lookback_bars"],[12,24,48,96])
        self.assertEqual(density["absolute_standardized_deviation_thresholds"],[1.0,1.5,2.0])

        op=json.loads((ROOT/"research_v3/EPOCH47_MEAN_REVERSION_WAVE01_COARSE_PARAMETER_REGION_SCAN_DETERMINISTIC_OPERATION_V1.json").read_text())
        self.assertEqual(op["evidence_epoch"],45)
        self.assertEqual(op["result_validation"]["evidence_epoch"],46)
        self.assertEqual(op["materializer"],"MATERIALIZE_BASE64_GZIP_NON_ECONOMIC_STRUCTURAL_RESULT")
        self.assertEqual(len(op["payload_refs"]),16)
        encoded="".join((ROOT/ref).read_text(encoding="ascii").strip() for ref in op["payload_refs"])
        self.assertEqual(len(encoded),25876)
        self.assertEqual(hashlib.sha256(encoded.encode("ascii")).hexdigest(),op["payload_sha256"])
        decoded=gzip.decompress(base64.b64decode(encoded,validate=True))
        self.assertEqual(hashlib.sha256(decoded).hexdigest(),op["decoded_result_sha256"])
        result=json.loads(decoded)
        _validate_epoch47_compact_result(result)
        self.assertEqual(result["evidence_epoch"],46)
        self.assertEqual(result["grid"]["symbol_cell_records"],396)
        self.assertEqual(result["scope"]["identities_scanned"],33)
        self.assertEqual(result["scope"]["total_m5_rows"],305938)
        self.assertFalse(result["interpretation_boundary"]["post_event_directional_or_return_response_computed"])
        self.assertFalse(result["interpretation_boundary"]["pnl_computed"])
        self.assertFalse(result["grid"]["winner_selection_performed"])

    def test_unsupported_or_unfrozen_authority_fails_closed(self):
        with self.assertRaises(ScanError):
            validate_freeze({}, Path("."))


if __name__ == "__main__":
    unittest.main()
