import json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class LiveEquivalentStageBInputEquivalenceRevalidationTests(unittest.TestCase):
    def test_exact_input_equivalence_revalidates_existing_results_without_economics(self):
        a=load("evidence/LIVE_EQUIVALENT_STAGE_B_INPUT_EQUIVALENCE_REVALIDATION_V1.json")
        self.assertEqual(a["status"],"PASS_EXISTING_STAGE_B_RESULTS_REVALIDATED_NO_ECONOMIC_RERUN")
        self.assertFalse(a["economics_rerun_performed"])
        self.assertEqual(a["new_economic_outcomes_opened"],0)
        self.assertEqual(a["additional_v2_attempts_consumed"],0)
        self.assertTrue(a["candidates"]["V2-C006"]["exact_manifest_match"])
        self.assertTrue(a["candidates"]["V2-C012"]["exact_manifest_match"])
        self.assertEqual(
            a["candidates"]["V2-C006"]["current_live_equivalent_stage_b_serialized_intent_manifest_sha256"],
            "6e320849ba49136b5491ecab75bc0ce5c36715a2c2202ade9d97443b41b9a515",
        )
        self.assertEqual(
            a["candidates"]["V2-C012"]["current_live_equivalent_stage_b_serialized_intent_manifest_sha256"],
            "645e1d89a5a61c6f757fc4ac1e7f5a7729d847efab9e207c6a02da72e4d9995a",
        )

    def test_current_state_uses_revalidated_stage_b_authority_without_new_outcome(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(s["v2_attempts_used"],16)
        self.assertEqual(s["v2_search_budget_remaining"],68)
        self.assertEqual(s["economic_outcomes_opened"],23)
        self.assertEqual(s["stage_b_revalidation_required_candidate_ids"],[])
        self.assertEqual(s["current_stage_b_survivor_input_set"],["V2-C006","V2-C012"])
        self.assertEqual(s["current_live_equivalent_stage_b_authoritative_candidate_ids"],["V2-C006","V2-C012"])
        for cid in ("V2-C006","V2-C012"):
            b=s["current_result_authority"][cid]["stage_b_current_config"]
            self.assertEqual(b["state"],"VALID_REVALIDATED_BY_LIVE_EQUIVALENT_INPUT_EQUIVALENCE")
            self.assertTrue(b["current_live_equivalent_authoritative"])
            self.assertFalse(b["economic_rerun_performed"])
            self.assertEqual(b["additional_v2_attempts_consumed"],0)

    def test_stage_b_result_bytes_are_preserved(self):
        c006=load("m6/results/V2-C006_STAGE_B_CURRENT_CONFIG_V1.json")
        c012=load("m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V2.json")
        self.assertEqual(c006["result_sha256"],"72e1c6dd94969add768d5640c245a3cd400fa4e5777fd518b3cf09de872e8d6f")
        self.assertEqual(c006["economic_summary"]["executed_trades"],108)
        self.assertEqual(c012["result_hash"],"91c9306b594110a2ae8cac25acdd10ecb6d7949f2cda7f2331ae9f514059f287")
        self.assertEqual(c012["economic_summary"]["executed_trades"],34)

if __name__=="__main__": unittest.main(verbosity=2)
