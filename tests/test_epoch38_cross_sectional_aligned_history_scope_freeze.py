from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from research_v3.epoch38_cross_sectional_aligned_history_scope_freeze import (
    EXPECTED_PROPOSAL_BLOB_SHA,
    FREEZE_REF,
    PEER_INDEX_REF,
    PROPOSAL_REF,
    validate_documents,
)

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class Epoch38AlignedHistoryScopeFreezeTests(unittest.TestCase):
    def setUp(self):
        self.proposal=load(PROPOSAL_REF)
        self.index=load(PEER_INDEX_REF)
        self.freeze=load(FREEZE_REF)

    def test_freeze_matches_accepted_exact_scope_and_peer_index(self):
        out=validate_documents(self.proposal,self.index,self.freeze)
        self.assertEqual(out["accepted_peer_breadth"],113)
        self.assertEqual(out["frozen_sample_size"],48)
        self.assertEqual(out["exact_symbols"],self.proposal["decision"]["scope"]["exact_symbols"])

    def test_post_green_validation_operation_is_authorized_without_acquisition(self):
        op=load(Path("research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_ACQUISITION_READINESS_OPERATION_V1.json"))
        self.assertEqual(op["operation_name"],"VALIDATE_EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_SCOPE_FREEZE")
        self.assertIn("FETCH_MARKET_DATA",op["forbidden_actions"])
        self.assertIn("OPEN_ECONOMICS",op["forbidden_actions"])

    def test_proposal_file_binding_is_exact_and_not_semantic_hash_substitution(self):
        bad=copy.deepcopy(self.freeze)
        bad["source_ai_proposal"]["proposal_git_blob_sha"]="d0f9945e61b6c400d34816b1b899894377541f3"
        with self.assertRaisesRegex(ValueError,"exact accepted proposal file"):
            validate_documents(self.proposal,self.index,bad)
        with self.assertRaisesRegex(ValueError,"proposal file binding"):
            validate_documents(self.proposal,self.index,self.freeze,proposal_git_blob_sha="0"*40)

    def test_scope_drift_fails_closed(self):
        bad=copy.deepcopy(self.freeze)
        bad["development_data"]["resolution"]="H1"
        with self.assertRaisesRegex(ValueError,"resolution drift"):
            validate_documents(self.proposal,self.index,bad)

    def test_wrong_cohort_membership_fails_closed_without_mutating_breadth(self):
        bad=copy.deepcopy(self.freeze)
        self.assertEqual(len([x for x in self.index["identities"] if x.get("peer_candidate_cohort_id")=="peer_f00b1cfa2c5c4549"]),113)
        bad["selection"]["exact_symbols"][0]="EURUSD"
        self.assertEqual(len(bad["selection"]["exact_symbols"]),48)
        with self.assertRaisesRegex(ValueError,"outside the accepted peer cohort"):
            validate_documents(self.proposal,self.index,bad)
        self.assertEqual(len([x for x in self.index["identities"] if x.get("peer_candidate_cohort_id")=="peer_f00b1cfa2c5c4549"]),113)

if __name__=="__main__":
    unittest.main()
