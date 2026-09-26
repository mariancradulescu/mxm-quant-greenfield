import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from research_v3.general_ai_implementation_executor import DEFAULT_MODEL as IMPLEMENTATION_MODEL, FOUR_PANEL_OUTER_ACQUISITION_FIELDS, FOUR_PANEL_OUTER_SCHEMA, PROTECTED_PREFIXES, ImplementationRejected, _bound_context, _collector_fields_match, _post_green_output, _resolve_current_proposal, _validate_output, authoritative_reasoning_requirement, implementation_required
from research_v3.general_ai_reasoning_provider import DEFAULT_MODEL, reasoning_required

ROOT=Path(__file__).resolve().parents[1]
class GeneralAIImplementationExecutorTests(unittest.TestCase):
    def test_current_state_routes_by_semantics_not_finite_state_names(self):
        s=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        if s.get("user_action_required") is True or s.get("external_gate") or not s.get("next_action") or (s.get("status")=="MATERIAL_INTEGRITY_FAILURE" and s.get("integrity_gate")):
            self.assertFalse(implementation_required(s,ROOT))
        elif reasoning_required(s):
            self.assertFalse(implementation_required(s))
        else:
            self.assertTrue(implementation_required(s,ROOT))
    def test_explicit_integrity_gate_blocks_implementation_even_with_next_action(self):
        self.assertFalse(implementation_required({"status":"MATERIAL_INTEGRITY_FAILURE","integrity_gate":"C032_CAPTURE_REUSE","next_action":"RUN_UNSAFE_SCREEN"}))

    def test_executor_binds_active_proposal_or_preserves_historical_runtime_provenance(self):
        state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        if state.get("source_ai_proposal_id") or state.get("source_ai_proposal_hash"):
            ref,proposal,row=_resolve_current_proposal(ROOT,state)
            self.assertEqual(proposal["proposal_id"],state["source_ai_proposal_id"])
            if state.get("source_ai_proposal_hash"):
                self.assertEqual(row["proposal_hash"],state["source_ai_proposal_hash"])
        elif state.get("source_runtime_operation_id"):
            # An operation-only binding at a fresh semantic boundary is historical
            # provenance, not authority to reuse the predecessor AI proposal.
            self.assertTrue(reasoning_required(state))
            self.assertFalse(implementation_required(state,ROOT))
            registry=json.loads((ROOT/"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json").read_text())
            matches=[
                row for row in registry.get("accepted",[])
                if row.get("operation_id")==state["source_runtime_operation_id"]
            ]
            self.assertEqual(len(matches),1)
            self.assertIsNone(state.get("source_ai_proposal_id"))
            self.assertIsNone(state.get("source_ai_proposal_hash"))
        else:
            self.assertTrue(state.get("supersession_ref") or state.get("outer_capture_plan_ref"))
        source=(ROOT/"research_v3/general_ai_implementation_executor.py").read_text()
        self.assertNotIn("AUTO_reason_a8b81cef686ff74cf678e7e25193f43f.json",source)

    def test_post_green_implementation_returns_to_reasoning(self):
        out={"status":"IMPLEMENTATION_CHANGED_REQUIRES_EXACT_HEAD_GREEN","next_research_state":{"status":"PENDING_EXACT_HEAD_GREEN","next_action":"VALIDATE"}}
        accepted=_post_green_output(out,["research_v3/example.json"])
        ns=accepted["next_research_state"]
        self.assertTrue(ns["ai_reasoning_required"])
        self.assertTrue(ns["research_judgment_required"])
        self.assertFalse(ns["implementation_ai_required"])
        self.assertEqual(ns["green_implementation_artifacts"],["research_v3/example.json"])

    def test_post_green_preserves_result_specific_reasoning_provenance(self):
        out={
            "status":"COMPLETE_NON_ECONOMIC",
            "next_research_state":{
                "status":"PENDING_EXACT_HEAD_GREEN_RELATIVE_VALUE_STRUCTURAL_DIAGNOSTIC_ACCEPTANCE",
                "next_action":"AI_INTERPRET_NEWLY_GREEN_NON_ECONOMIC_RELATIVE_VALUE_STRUCTURAL_RESULT_AND_SELECT_THE_HIGHEST_INFORMATION_LEGAL_NEXT_FRONTIER_ACTION",
                "completed_structural_report_ref":"evidence/EPOCH24_RELATIVE_VALUE_STRUCTURAL_DIAGNOSTIC_ACCEPTANCE_V1.json",
                "completed_family":"RELATIVE_VALUE_COINTEGRATION",
                "family_result":"NO_PAIR_PASSED_FROZEN_NON_ECONOMIC_STRUCTURAL_DIAGNOSTIC",
                "implementation_ai_required":True,
            },
        }
        accepted=_post_green_output(out,[])
        ns=accepted["next_research_state"]
        self.assertEqual(ns["status"],"AI_REASONING_REQUIRED_AFTER_IMPLEMENTATION_GREEN")
        self.assertEqual(
            ns["completed_structural_report_ref"],
            "evidence/EPOCH24_RELATIVE_VALUE_STRUCTURAL_DIAGNOSTIC_ACCEPTANCE_V1.json",
        )
        self.assertEqual(
            ns["family_result"],
            "NO_PAIR_PASSED_FROZEN_NON_ECONOMIC_STRUCTURAL_DIAGNOSTIC",
        )
        self.assertTrue(ns["ai_reasoning_required"])
        self.assertTrue(ns["research_judgment_required"])
        self.assertFalse(ns["implementation_ai_required"])
        self.assertFalse(ns["user_action_required"])
        self.assertEqual(ns["green_implementation_artifacts"],[])

    def test_authoritative_independent_outer_contract_redirects_before_execution(self):
        s={"source_freeze_ref":"research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json","next_action":"ARBITRARY_EXECUTION","user_action_required":False}
        r=authoritative_reasoning_requirement(ROOT,s)
        self.assertIsNotNone(r)
        self.assertTrue(r["ai_reasoning_required"])
        self.assertEqual(r["next_action"],"GENERAL_AI_SELECT_MINIMAL_DISJOINT_OUTER_WINDOW_AND_REQUIRED_COST_AUTHORITY_BEFORE_ANY_OUTER_OUTCOME")

    def test_outer_binding_satisfies_generic_redirect_guard(self):
        s={"source_freeze_ref":"research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json","next_action":"ARBITRARY_EXECUTION","outer_data_binding_ref":"evidence/some_future_binding.json","user_action_required":False}
        self.assertIsNone(authoritative_reasoning_requirement(ROOT,s))

    def test_arbitrary_non_reasoning_action_is_not_finite_mapped(self):
        self.assertFalse(implementation_required({"status":"ANY_FUTURE_STATE","next_action":"SOMETHING_NEVER_SEEN_BEFORE","user_action_required":False},ROOT))
        self.assertFalse(implementation_required({"status":"WAIT","next_action":"EXTERNAL","user_action_required":True},ROOT))
    def test_protected_authorities_include_economics_and_ledgers(self):
        joined="\n".join(PROTECTED_PREFIXES)
        for item in ("CURRENT_STATE.json","discovery/ledger.jsonl","research_v3/runtime_v2/","m6/results/","PROPOSAL_REGISTRY_V1.json",".github/workflows/"):
            self.assertIn(item,joined)
    def test_account_policy_falls_back_transparently_to_auto(self):
        self.assertEqual(DEFAULT_MODEL,"auto")
        self.assertEqual(IMPLEMENTATION_MODEL,"auto")

    def test_large_implementation_authority_is_bounded_and_retrievable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); rel="data/large.json"; (root/"data").mkdir()
            (root/rel).write_text(json.dumps({"schema":"test","status":"ACCEPTED","products":{"X":"x"*9000}}))
            context=_bound_context(root,{},{"authority_refs":[rel]})
            self.assertEqual(context[rel]["content_summary"]["schema"],"test")
            self.assertTrue(context[rel]["content_summary"]["available_via_repository_view"])
            self.assertEqual(len(context[rel]["sha256"]),64)
            self.assertLess(len(json.dumps(context)),1000)

    def test_legacy_four_panel_acquisition_fields_map_to_compact_transfer_contract(self):
        plan={"schema":FOUR_PANEL_OUTER_SCHEMA}
        self.assertTrue(_collector_fields_match(plan,FOUR_PANEL_OUTER_ACQUISITION_FIELDS))
        self.assertFalse(_collector_fields_match(plan,["bid","ask"]))
        explicit={"schema":"future.schema","fields":["time_utc","close"]}
        self.assertTrue(_collector_fields_match(explicit,["time_utc","close"]))
        self.assertFalse(_collector_fields_match(explicit,["timestamp","close"]))

    def test_external_collector_must_match_accepted_ai_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); plan_ref="plan.json"; build_ref="build.py"
            plan={"symbols":[{"broker_symbol":"OLD_SYMBOL"}],"resolution":"M5",
                  "interval":{"start_utc":"2026-07-20T00:00:00Z","end_utc":"2026-09-13T23:59:59Z"},
                  "output_artifact_name":"old.zip","fields":["timestamp_utc"]}
            (root/plan_ref).write_text(json.dumps(plan))
            (root/build_ref).write_text('PLAN_REF="plan.json"')
            proposal={"data_policy":{"new_market_data_requested":True,"minimal_acquisition_request":{
                "symbols":["NEW_SYMBOL"],"resolution":"M5",
                "start_utc":"2026-07-20T00:00:00Z","end_utc":"2026-09-13T23:59:59Z","fields":["timestamp_utc"]}}}
            out={"implementation_id":"test","status":"EXTERNAL_DATA_REQUIRED",
                 "next_research_state":{"status":"WAITING","next_action":"CAPTURE"},
                 "external_data_gate":{"collector_build_ref":build_ref,"collector_plan_ref":plan_ref,
                                       "collector_package_artifact_name":"package.zip",
                                       "expected_return_artifact_name":"old.zip"}}
            with patch("research_v3.general_ai_implementation_executor._resolve_current_proposal",
                       return_value=("proposal.json",proposal,{})):
                with self.assertRaisesRegex(ImplementationRejected,"does not match accepted AI proposal scope"):
                    _validate_output(root,out)
                plan["symbols"]=[{"broker_symbol":"NEW_SYMBOL"}]
                (root/plan_ref).write_text(json.dumps(plan))
                _validate_output(root,out)
                plan["fields"]=["invented_bid"]
                (root/plan_ref).write_text(json.dumps(plan))
                with self.assertRaisesRegex(ImplementationRejected,"fields do not match"):
                    _validate_output(root,out)
if __name__=="__main__": unittest.main()
