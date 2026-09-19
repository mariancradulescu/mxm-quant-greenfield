import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class Tier1AcceptedEvidenceTests(unittest.TestCase):
    def test_01_capture_acceptance_binds_exact_hashes_and_zero_economics(self):
        a=load("data/TIER1_COST_EVIDENCE_CAPTURE_ACCEPTANCE_V1.json")
        self.assertEqual(a["status"],"ACCEPTED_HASH_VERIFIED_COMPACT_BUNDLE")
        self.assertEqual(a["source_uploaded_bundle"]["sha256"],"f187010d55a6f444827592e23158187c3985c5c3af4631f4e31c53c8a84a1360")
        self.assertEqual(a["canonical_repack"]["sha256"],"43e2e1f01efa6ff06a8fa4af4aab7511d091721771637183db0be505c2174aad")
        self.assertEqual(a["raw_commitment"]["chunk_count"],4912)
        self.assertEqual(a["raw_commitment"]["total_rows"],272842293)
        self.assertTrue(a["raw_commitment"]["recomputed_match"])
        self.assertEqual(a["internal_integrity"]["checksum_failures"],0)
        self.assertFalse(a["internal_integrity"]["orders"])
        self.assertFalse(a["internal_integrity"]["account_mutation"])
        self.assertFalse(a["internal_integrity"]["economics"])
        self.assertEqual(a["research_state"]["economic_outcomes_opened"],0)
        self.assertEqual(a["research_state"]["v2_attempts_used"],0)
        self.assertEqual(a["research_state"]["result_recorded"],0)
        self.assertFalse(a["research_state"]["protected_evidence_opened"])

    def test_02_all_four_stream_commitments_are_complete(self):
        a=load("data/TIER1_COST_EVIDENCE_CAPTURE_ACCEPTANCE_V1.json")
        streams=a["raw_commitment"]["streams"]
        self.assertEqual(set(streams),{"US500_BID","US500_ASK","NAS100_BID","NAS100_ASK"})
        self.assertTrue(all(v["chunk_count"]==1228 for v in streams.values()))
        self.assertEqual(sum(v["row_count"] for v in streams.values()),272842293)

    def test_03_calibration_uses_no_candidate_outcomes_and_does_not_invent_fill_rule(self):
        c=load("evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V1.json")
        self.assertEqual(c["status"],"COMPLETE_PRE_OUTCOME_CONCLUSION_UNRESOLVED")
        self.assertFalse(c["rule_selection_used_candidate_signals"])
        self.assertFalse(c["rule_selection_used_candidate_returns"])
        self.assertFalse(c["rule_selection_used_candidate_pnl"])
        self.assertFalse(c["protected_evidence_used"])
        self.assertEqual(c["calibration_conclusion"]["state"],"UNRESOLVED")
        self.assertFalse(c["calibration_conclusion"]["executable_fill_truth_claimed"])
        self.assertFalse(c["calibration_conclusion"]["conservative_numeric_execution_bound_frozen"])
        self.assertTrue(c["calibration_conclusion"]["no_candidate_economic_outcome_may_open"])

    def test_04_c006_quote_capture_is_complete_but_cost_rule_remains_blocked(self):
        c=load("evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V1.json")
        x=c["candidate_context_review"]["V2-C006"]
        self.assertEqual(x["entry_quote_evidence"]["sessions"],1180)
        self.assertEqual(x["entry_quote_evidence"]["causal_two_sided_available"],1180)
        self.assertEqual(x["exit_quote_evidence"]["causal_two_sided_available"],1180)
        self.assertEqual(x["slippage_delay_gap_effects"]["state"],"UNRESOLVED")
        self.assertEqual(x["m6_stage_a_readiness"],"BLOCKED_DISCOVERY_COST_RULE")

    def test_05_c012_0930_limitation_is_explicit_and_not_promoted_to_fill_truth(self):
        c=load("evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V1.json")
        x=c["candidate_context_review"]["V2-C012"]
        self.assertEqual(x["open_0930_rows"],1180)
        self.assertEqual(x["causal_two_sided_missing"],1172)
        self.assertEqual(x["slippage_delay_gap_effects"]["state"],"UNRESOLVED")
        self.assertEqual(x["m6_stage_a_readiness"],"BLOCKED_DISCOVERY_COST_RULE")

    def test_06_readiness_v4_and_current_state_are_consistent(self):
        r=load("data/PRIMARY_WAVE_02_PRE_M6_READINESS_V4.json")
        s=load("CURRENT_STATE.json")
        self.assertEqual(r["status"],"CANDIDATE_SPECIFIC_POST_TIER1_QUOTE_CAPTURE_COST_CALIBRATION_UNRESOLVED")
        self.assertEqual(r["candidates"]["V2-C006"]["m6_stage_a_readiness"],"BLOCKED_DISCOVERY_COST_RULE")
        self.assertEqual(r["candidates"]["V2-C012"]["m6_stage_a_readiness"],"BLOCKED_DISCOVERY_COST_RULE")
        self.assertEqual(r["ready_candidates"],[])
        self.assertEqual(s["pre_m6_readiness_authority"],"data/PRIMARY_WAVE_02_PRE_M6_READINESS_V4.json")
        self.assertEqual(s["pre_m6_operational_state"],"TIER1_QUOTE_CAPTURE_ACCEPTED_COST_RULE_UNRESOLVED")
        self.assertEqual(s["economic_outcomes_opened"],0)
        self.assertEqual(s["v2_attempts_used"],0)
        self.assertEqual(s["v2_evaluated_identities"],0)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["m6"]["economics_run"])
        self.assertFalse(s["m6"]["auxiliary_evidence"]["m6_stage_a_economics_authorized"])

if __name__=="__main__":
    unittest.main(verbosity=2)
