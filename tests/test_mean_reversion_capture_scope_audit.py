from __future__ import annotations

import copy
import unittest
from pathlib import Path

from research_v3.mean_reversion_capture_scope_audit import (
    FREEZE_REF,
    ScopeAuditError,
    _load_inputs,
    build_from_authorities,
    build_scope_audit,
)
import json

ROOT = Path(__file__).resolve().parents[1]


class MeanReversionCaptureScopeAuditTests(unittest.TestCase):
    def test_reconciles_full_eligible_frame_without_selecting_a_cohort_or_increment(self):
        result = build_scope_audit(ROOT)
        coverage = result["accepted_coverage"]
        increment = result["disjoint_increment"]
        boundary = result["interpretation_boundary"]

        self.assertEqual(result["eligible_frame"]["eligible_identity_count"], 1576)
        self.assertEqual(coverage["accepted_scope_count"], 10)
        self.assertEqual(
            coverage["eligible_identity_count_with_any_accepted_scope"]
            + coverage["eligible_identity_count_without_reusable_accepted_scope"],
            1576,
        )
        self.assertGreaterEqual(coverage["eligible_identity_scope_overlaps_counted_more_than_once"], 0)
        self.assertFalse(result["eligible_frame"]["structural_41_used_as_inferential_universe"])
        self.assertFalse(increment["smallest_increment_selected"])
        self.assertEqual(
            increment["smallest_increment_assessment"]["status"],
            "NOT_IDENTIFIABLE_FROM_ACCEPTED_MANIFEST_SUMMARIES",
        )
        self.assertEqual(increment["exact_symbols_selected"], [])
        self.assertFalse(increment["new_market_data_requested_or_authorized"])
        self.assertFalse(increment["blocked_exact_48_symbol_scope_reused"])
        self.assertFalse(increment["c031_twelve_symbol_extension_used_to_satisfy_another_scope"])
        self.assertFalse(boundary["strategy_events_or_response_statistics_computed"])
        self.assertFalse(boundary["returns_or_pnl_computed"])
        self.assertFalse(boundary["economic_outcome_opened"])
        self.assertFalse(boundary["relative_value_alignment_inventory_recomputed"])
        self.assertEqual(result["accounting_effect"]["v2_attempts_consumed"], 0)
        self.assertEqual(len(result["alternatives_and_exclusions"]["proposal_alternatives"]), 3)

    def test_capture_identity_mismatch_fails_closed(self):
        feasibility, peers, inventory, prior, blocked, proposal = _load_inputs(ROOT)
        changed = copy.deepcopy(inventory)
        changed["scopes"][0]["exact_broker_identities"][0]["broker_symbol"] += ".WRONG"
        with self.assertRaises(ScopeAuditError):
            build_from_authorities(
                feasibility, peers, changed, prior, blocked, proposal, root=ROOT
            )

    def test_capture_interval_mismatch_fails_closed(self):
        feasibility, peers, inventory, prior, blocked, proposal = _load_inputs(ROOT)
        changed = copy.deepcopy(inventory)
        changed["scopes"][0]["requested_interval_utc"]["start_utc"] = (
            changed["scopes"][0]["requested_interval_utc"]["end_utc"]
        )
        changed["scopes"][0]["requested_interval_utc"]["end_utc"] = "2020-01-01T00:00:00Z"
        with self.assertRaises(ScopeAuditError):
            build_from_authorities(
                feasibility, peers, changed, prior, blocked, proposal, root=ROOT
            )

    def test_prospective_freeze_and_operation_are_exact_head_gated(self):
        freeze = json.loads((ROOT / FREEZE_REF).read_text(encoding="utf-8"))
        operation = json.loads(
            (
                ROOT
                / "research_v3/MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45_DETERMINISTIC_OPERATION_V1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(freeze["evidence_epoch"], 45)
        self.assertEqual(operation["evidence_epoch"], 44)
        self.assertEqual(operation["result_validation"]["evidence_epoch"], 45)
        self.assertTrue(operation["execution_policy"]["exact_head_green_required_before_execution"])
        self.assertFalse(operation["execution_policy"]["new_semantic_judgment_required"])
        self.assertEqual(operation["accounting_effect"]["v2_attempts"], 0)
        self.assertEqual(operation["accounting_effect"]["economic_outcomes"], 0)
        self.assertEqual(
            operation["result_ref"],
            "evidence/MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45_V1.json",
        )


if __name__ == "__main__":
    unittest.main()
