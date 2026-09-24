import json, unittest
from pathlib import Path
from research_v3.general_ai_implementation_executor import DEFAULT_MODEL as IMPLEMENTATION_MODEL, PROTECTED_PREFIXES, implementation_required
from research_v3.general_ai_reasoning_provider import DEFAULT_MODEL, reasoning_required

ROOT=Path(__file__).resolve().parents[1]
class GeneralAIImplementationExecutorTests(unittest.TestCase):
    def test_current_state_routes_by_semantics_not_finite_state_names(self):
        s=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        if s.get("user_action_required") is True:
            self.assertFalse(implementation_required(s))
        elif reasoning_required(s):
            self.assertFalse(implementation_required(s))
        else:
            self.assertTrue(implementation_required(s))
    def test_arbitrary_non_reasoning_action_is_not_finite_mapped(self):
        self.assertTrue(implementation_required({"status":"ANY_FUTURE_STATE","next_action":"SOMETHING_NEVER_SEEN_BEFORE","user_action_required":False}))
        self.assertFalse(implementation_required({"status":"WAIT","next_action":"EXTERNAL","user_action_required":True}))
    def test_protected_authorities_include_economics_and_ledgers(self):
        joined="\n".join(PROTECTED_PREFIXES)
        for item in ("CURRENT_STATE.json","discovery/ledger.jsonl","research_v3/runtime_v2/","m6/results/","PROPOSAL_REGISTRY_V1.json",".github/workflows/"):
            self.assertIn(item,joined)
    def test_account_policy_falls_back_transparently_to_auto(self):
        self.assertEqual(DEFAULT_MODEL,"auto")
        self.assertEqual(IMPLEMENTATION_MODEL,"auto")
if __name__=="__main__": unittest.main()
