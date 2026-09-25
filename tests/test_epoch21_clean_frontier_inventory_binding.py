import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

class Epoch21CleanFrontierInventoryBindingTests(unittest.TestCase):
    def test_clean_decision_is_bound_without_economic_or_ai_delta(self):
        decision=load("research_v3/EPOCH21_CLEAN_FRONTIER_GENERAL_AI_DECISION_V1.json")
        binding=load("research_v3/EPOCH21_CLEAN_FRONTIER_RUNTIME_BINDING_V1.json")
        state=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        epoch=load("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
        self.assertEqual(decision["status"], "ACCEPTED_NON_ECONOMIC_FRONTIER_LEVEL_DECISION")
        self.assertEqual(decision["decision"]["action"], "BUILD_NON_ECONOMIC_ALL_FRONTIER_PREREQUISITE_AND_COVERAGE_INVENTORY")
        self.assertEqual(binding["status"], "BOUND_AND_DETERMINISTICALLY_VALIDATED")
        self.assertFalse(binding["evidence_epoch_advanced"])
        self.assertEqual(binding["provider_effect"]["copilot_provider_calls_delta"], 0)
        self.assertEqual(binding["accounting_effect"]["v2_attempts_delta"], 0)
        self.assertEqual(binding["accounting_effect"]["economic_outcomes_delta"], 0)
        self.assertEqual(epoch["current_epoch"], 21)
        self.assertIn(state["status"], {"DETERMINISTIC_FRONTIER_INVENTORY_COMPLETE","DETERMINISTIC_CAPTURE_CONTRACT_COMPLETE","INFORMATION_GAIN_ACQUISITION_PLAN_READY"})
        self.assertFalse(state["research_judgment_required"])
        self.assertFalse(state["ai_reasoning_required"])
        self.assertEqual(state["fresh_director_decision_ref"], "research_v3/EPOCH21_CLEAN_FRONTIER_GENERAL_AI_DECISION_V1.json")

    def test_exact_eligible_identity_and_signature_reconciliation(self):
        feasibility=load("data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json")
        frontier=load("data/BROKER_NATIVE_ADAPTIVE_INFORMATION_FRONTIER_V1.json")
        inventory=load("evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json")
        excluded=set(frontier["eligibility"]["previously_observed_symbols_excluded"])
        eligible=sorted(symbol for symbol,row in feasibility["products"].items() if row[1]=="BOTH_FEASIBLE" and row[2] is False and symbol not in excluded)
        persisted=[row["broker_symbol"] for row in inventory["identity_coverage"]["eligible_identities"]]
        self.assertEqual(len(eligible), 1578)
        self.assertEqual(persisted, eligible)
        reps=frontier["frontier"]
        sigs={tuple(row["signature"]) for row in reps}
        self.assertEqual(len(reps), 41)
        self.assertEqual(len(sigs), 41)
        self.assertTrue(all(row["broker_symbol"] in set(eligible) for row in reps))
        self.assertEqual(inventory["structural_signature_coverage"]["distinct_signatures"], 41)
        self.assertEqual(inventory["eur200_margin_coverage"]["eligible_current_index_pass"], 1578)

    def test_inventory_keeps_economic_gates_fail_closed(self):
        inv=load("evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json")
        op=load("research_v3/EPOCH21_NEXT_DETERMINISTIC_OPERATION_V1.json")
        state=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        self.assertEqual(inv["accounting_effect"]["v2_attempts_consumed"], 0)
        self.assertEqual(inv["accounting_effect"]["economic_outcomes_opened"], 0)
        self.assertEqual(inv["accounting_effect"]["copilot_reasoning_calls"], 0)
        self.assertEqual(inv["pre_economic_gate_inventory"]["COST_AUTHORITY_PASS"], "FAIL_CLOSED_UNTIL_FRESH_ENVELOPE_BOUND_TRANSACTION_LOCAL_COST_AUTHORITY")
        self.assertEqual(op["operation_name"], "BUILD_READ_ONLY_ALL_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT")
        self.assertFalse(op["execution_policy"]["implementation_ai_required"])
        self.assertFalse(op["execution_policy"]["copilot_reasoning_required"])
        self.assertIsNone(op["scope"]["mechanism_family"])
        if state["next_action"] != op["operation_name"]:
            self.assertEqual(state.get("capture_contract_ref"), "research_v3/BROKER_NATIVE_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT_V1.json")
        self.assertFalse(state["safety"]["live_orders_authorized"])
        self.assertFalse(state["safety"]["protected_evidence_opened"])

    def test_accounting_capacity_unchanged(self):
        frontier=load("research_v3/CURRENT_RESEARCH_FRONTIER_V1.json")
        a=frontier["accounting"]
        self.assertEqual(a["lifetime_consumed_v2_identities"], 20)
        self.assertEqual(a["original_base_budget_total"], 84)
        self.assertEqual(a["original_base_used_historically"], 20)
        self.assertEqual(a["base_budget_remaining"], 64)
        self.assertEqual(a["economic_outcomes_opened"], 28)
        self.assertEqual(a["refunds"], 0)
        self.assertEqual(a["methodology_replacement_capacity_total"], 15)
        self.assertEqual(a["methodology_replacement_capacity_used"], 0)
        self.assertEqual(a["prospectively_frozen_extension_capacity"], 0)
        self.assertEqual(a["future_available_capacity"], 79)

if __name__ == "__main__":
    unittest.main()
