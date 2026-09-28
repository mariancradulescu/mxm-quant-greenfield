from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path
import unittest

from research_v3.cross_sectional_peer_cohort_index import (
    ELIGIBLE_IDENTITY_SET_SHA256,
    FEASIBILITY_PAYLOAD_SHA256,
    PROPOSAL_FILE_SHA256,
    PROPOSAL_REF,
    build_index,
)


def _row(
    symbol: str,
    symbol_id: int,
    *,
    asset_class: str = "US Equities",
    product_type: str = "STANDARD_CASH_SHARE_CFD",
    session_regions: str = "US",
    coverage_bucket: str = "REGIONAL_OR_CASH_SESSION_SCHEDULE",
    schedule_time_zone: str = "America/New_York",
) -> dict:
    return {
        "broker_symbol": symbol,
        "symbol_id": symbol_id,
        "current_entry_accessible": True,
        "directional_feasibility": "BOTH_FEASIBLE",
        "test_product": False,
        "shortability": True,
        "asset_class": asset_class,
        "product_type": product_type,
        "session_regions": session_regions,
        "coverage_bucket": coverage_bucket,
        "schedule_time_zone": schedule_time_zone,
        "minimum_executable_volume": "100",
        "buy_min_volume_margin_eur": 10.0 + symbol_id,
        "sell_min_volume_margin_eur": 11.0 + symbol_id,
        "schedule_minutes_per_week": 1000.0,
        "accepted_history_state": "NO_ACCEPTED_HISTORY",
        "history_completeness": "UNKNOWN",
        "commission_fee_metadata_available": True,
        "conservative_friction_proxy_eur": None,
    }


def _bundle(rows: list[dict]) -> dict:
    rows = sorted(rows, key=lambda row: (row["broker_symbol"], row["symbol_id"]))
    return {
        "schema": "mxm.greenfield.cross-sectional-peer-cohort-input.v1",
        "source_bindings": {
            "accepted_proposal_ref": PROPOSAL_REF,
            "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
            "current_feasibility_ref": (
                "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"
            ),
            "current_broker_payload_sha256": FEASIBILITY_PAYLOAD_SHA256,
            "eligible_identity_set_sha256": ELIGIBLE_IDENTITY_SET_SHA256,
            "compact_authority_sha256": (
                "2629b471abd6c35351eefae43d2fefbd423e2726cb89363c32f2287e7bedd857"
            ),
            "accepted_transport_zip_sha256": (
                "3d1db9a65e93fe5c7ea69411a9c76d8d6381927ce1224e02532640394076e8a9"
            ),
            "accepted_original_collector_zip_sha256": (
                "5ce4b3bc3a47292bb8b9b704d6c8c305a0bc3657d7dd0ace539d93e740a9be15"
            ),
            "structural_registry_ref": (
                "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
            ),
            "structural_registry_sha256": (
                "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3"
            ),
            "feature_store_ref": (
                "research_v3/BROKER_NATIVE_FRONTIER_FEATURE_STORE_EPOCH23_V1.json"
            ),
            "feature_store_sha256": (
                "b92ad33bffad77f00b86933e1f552736485782e17fdea98fd0e84d1ab6dd117c"
            ),
            "opportunity_map_ref": (
                "research_v3/BROKER_NATIVE_FRONTIER_OPPORTUNITY_MAP_EPOCH23_V1.json"
            ),
            "opportunity_map_sha256": (
                "a6d024f43dd6066a73a1d6dadf35657e30968259d653fd9b4e4b30c5fde42639"
            ),
            "architecture_ref": (
                "research_v3/ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE_V1.json"
            ),
            "architecture_sha256": (
                "6b14648bad0aa8e0753f3771896892d0a7d70bd89911800ce9bdbafc0e96a568"
            ),
        },
        "eligible_identities": rows,
    }


ROOT = Path(__file__).resolve().parents[1]
FRAGMENT_HASHES = [
    "5c165c4499050e05e7753e88d9aec496fa21b79ea7a2b31bb6cdbbf89f23ac9b",
    "b072290ca21ae94eddead70a9c82d0c679d7cb54345c3850c5daf0e5503d4fc3",
    "2b5b5c8d4f50c2b340458f284fc4d7f39ab4effb0b0061717c64f035f8d0a63b",
    "ca678a5ceaa5120db2cca21c30d50ba9a644eff3d68a4c733fdcc1a1043bef1b",
    "fbb1aa9edfe1c29677fed8fa3e7755c134c6d6e0f2b9ff84d0ac3c23ae0caff4",
    "a6e78eb21fe0f52bf66f0b080413830b7d2048467ec3b468952b98e2787c7eed",
    "bc5f38f5546d5e9431f3748bfc7bc5f54d33af45acd09e866f925be69ad2938a",
    "a6bc8c778316093060b28890dcbce02fce8de8806e11280a34a65ec2d3300d23",
]
CONCAT_SHA256 = "208d2ed854a240a47300ba89c4e76d0c9861d5aab940e5adee8a11351d6c6e12"
DECODED_SHA256 = "fdee7e48774d6822df0f4dcb274c24ee0ad821ac51580eb418aad7e7e0825b68"

class CrossSectionalPeerCohortIndexTests(unittest.TestCase):
    def test_current_hash_bound_transport_builds_all_1576_once_without_outcomes(self):
        pieces=[]
        for index,expected in enumerate(FRAGMENT_HASHES):
            path=ROOT/f"research_v3/runtime_v2_inputs/CROSS_SECTIONAL_PEER_COHORT_INPUT_V1.part{index:02d}.b64"
            raw=path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),expected)
            pieces.append(raw)
        encoded=b"".join(pieces)
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),CONCAT_SHA256)
        decoded=gzip.decompress(base64.b64decode(encoded,validate=True))
        self.assertEqual(hashlib.sha256(decoded).hexdigest(),DECODED_SHA256)
        bundle=json.loads(decoded)
        self.assertEqual(len(bundle["eligible_identities"]),1576)
        self.assertEqual(
            sum(row["accepted_history_state"]=="ACCEPTED_HISTORY_AVAILABLE" for row in bundle["eligible_identities"]),
            42,
        )
        result=build_index(bundle)
        self.assertEqual(result["source_universe"]["indexed_identity_count"],1576)
        self.assertEqual(result["coverage"]["cohort_breadth_total"],1576)
        self.assertEqual(result["coverage"]["unassigned_missing_metadata_count"],0)
        self.assertFalse(result["cohort_policy"]["structural_representatives_used_as_substitutes"])
        self.assertFalse(result["interpretation_boundary"]["strategy_or_price_outcome_evaluated"])
        self.assertFalse(result["interpretation_boundary"]["returns_or_pnl_computed"])
        self.assertEqual(result["interpretation_boundary"]["economic_outcomes_opened"],0)
        self.assertEqual(result["interpretation_boundary"]["v2_attempts_consumed"],0)

    def test_preserves_all_rows_and_groups_only_exact_peer_metadata(self):
        rows = [
            _row("A.US", 1),
            _row("B.US", 2),
            _row("C.US", 3, product_type="ETF_CFD"),
            _row("D.US", 4, session_regions="EUROPE", schedule_time_zone="Europe/London"),
        ]
        result = build_index(_bundle(rows), expected_count=4)
        self.assertEqual(result["source_universe"]["indexed_identity_count"], 4)
        self.assertEqual(result["coverage"]["assigned_identity_count"], 4)
        self.assertEqual(result["coverage"]["cohort_count"], 3)
        self.assertEqual(
            result["coverage"]["cohort_breadth_total"],
            result["source_universe"]["indexed_identity_count"],
        )
        self.assertFalse(
            result["interpretation_boundary"]["strategy_or_price_outcome_evaluated"]
        )
        self.assertTrue(
            all(
                row["aligned_multi_symbol_history_state"] == "NOT_ACQUIRED_MECHANISM_SPECIFIC"
                for row in result["identities"]
            )
        )

    def test_missing_cohort_metadata_is_retained_and_flagged(self):
        result = build_index(
            _bundle([_row("MISSING", 8, session_regions="", schedule_time_zone="Unknown/Zone")]),
            expected_count=1,
        )
        self.assertEqual(result["source_universe"]["indexed_identity_count"], 1)
        self.assertEqual(result["coverage"]["unassigned_missing_metadata_count"], 1)
        self.assertIsNone(result["identities"][0]["peer_candidate_cohort_id"])
        self.assertEqual(
            result["identities"][0]["cohort_assignment_status"],
            "UNASSIGNED_MISSING_COHORT_METADATA",
        )

    def test_session_region_must_match_current_schedule_metadata(self):
        row = _row("A.US", 1)
        row["session_regions"] = "EUROPE"
        with self.assertRaisesRegex(ValueError, "session-region metadata"):
            build_index(_bundle([row]), expected_count=1)

    def test_invalid_binding_or_eligibility_fails_closed(self):
        bundle = _bundle([_row("A.US", 1)])
        changed_binding = copy.deepcopy(bundle)
        changed_binding["source_bindings"]["accepted_proposal_file_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "not bound"):
            build_index(changed_binding, expected_count=1)

        ineligible = copy.deepcopy(bundle)
        ineligible["eligible_identities"][0]["directional_feasibility"] = "BUY_ONLY"
        with self.assertRaisesRegex(ValueError, "not feasible"):
            build_index(ineligible, expected_count=1)

    def test_outcome_fields_and_duplicates_are_rejected(self):
        row = _row("A.US", 1)
        row["observed_return"] = 0.2
        with self.assertRaisesRegex(ValueError, "invalid identity fields"):
            build_index(_bundle([row]), expected_count=1)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_index(
                _bundle([_row("A.US", 1), _row("A.US", 1)]),
                expected_count=2,
            )

    def test_capital_proxy_history_gap_and_non_economic_boundary(self):
        result = build_index(_bundle([_row("A.US", 1)]), expected_count=1)
        identity = result["identities"][0]
        self.assertAlmostEqual(
            identity["capital_efficiency_proxy_schedule_minutes_per_minimum_margin_eur"],
            1000 / 11,
        )
        self.assertIsNone(identity["conservative_friction_proxy_eur"])
        self.assertFalse(result["interpretation_boundary"]["economic_equivalence_claimed"])
        self.assertEqual(
            result["coverage"]["cohorts"][0]["aligned_history_readiness"]["aligned_identities"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
