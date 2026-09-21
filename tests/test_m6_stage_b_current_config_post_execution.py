import hashlib
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from m6.stage_a_tier1_runner import StageAInputPaths
from m6.stage_b_current_config_execute import (
    CurrentConfigScenarioAlreadyExecuted,
    execute_authorized_current_config,
)

ROOT = Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

def canonical_result_hash(result):
    payload = dict(result)
    observed = payload.pop("result_sha256")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return observed, hashlib.sha256(canonical).hexdigest()

def git_blob_sha1(rel):
    data = (ROOT / rel).read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()

class StageBCurrentConfigPostExecutionTests(unittest.TestCase):
    def test_01_execution_record_is_exactly_once_and_exact_head_green(self):
        run=load("m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json")
        self.assertEqual(run["status"],"EXECUTED_EXACTLY_ONCE")
        self.assertEqual(run["source_gate_git_blob_sha1"],"f08832e1f7b5eb399ec806ac9690a63f2fa1f3b4")
        self.assertEqual(run["execution_head"],"1a395746a5f1351fd239a612131faec975f6f060")
        self.assertEqual(run["execution_exact_head_ci"]["run_id"],35595820997)
        self.assertEqual(run["execution_exact_head_ci"]["conclusion"],"SUCCESS")
        self.assertEqual(run["execution_exact_head_ci"]["tests_passed"],544)
        self.assertEqual(run["execution_exact_head_ci"]["tests_failed"],0)
        self.assertEqual(run["execution_count"],1)
        self.assertEqual(run["current_config_stage_b_outcomes_opened"],2)
        self.assertFalse(run["protected_evidence_opened"])

    def test_02_accounting_stays_on_existing_two_v2_identities(self):
        a=load("m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json")["accounting_after_execution"]
        self.assertEqual(a["economic_outcomes_opened"],4)
        self.assertEqual(a["v2_attempts_used"],2)
        self.assertEqual(a["v2_evaluated_identities"],2)
        self.assertEqual(a["v2_search_budget_total"],84)
        self.assertEqual(a["v2_search_budget_remaining"],82)
        self.assertEqual(a["discovery_ledger_entries"],22)
        self.assertEqual(a["discovery_result_recorded_entries"],2)
        ledger=[json.loads(x) for x in (ROOT/"discovery/ledger.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(len(ledger),26)
        self.assertEqual(sum(x["entry_type"]=="RESULT_RECORDED" for x in ledger),2)

    def test_03_accepted_results_are_hash_valid_and_unchanged(self):
        expected={
            "V2-C006":("m6/results/V2-C006_STAGE_B_CURRENT_CONFIG_V1.json","72e1c6dd94969add768d5640c245a3cd400fa4e5777fd518b3cf09de872e8d6f","0234d84f09a168ff70da4c07b9ccde49159010fc",258.6947216647057,108),
            "V2-C012":("m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V1.json","51edfcc76693425a07c24962f7b3c060fa2e7bb127385233f28f4fc1233edcaa","8c3b1fcdad6b43fcfed2af0919f3ddffd3b541f7",257.84259369263856,35),
        }
        for cid,(ref,result_sha,blob_sha,final_equity,trades) in expected.items():
            r=load(ref); observed,calculated=canonical_result_hash(r)
            self.assertEqual(observed,calculated); self.assertEqual(observed,result_sha)
            self.assertEqual(git_blob_sha1(ref),blob_sha)
            self.assertEqual(r["candidate_id"],cid)
            self.assertEqual(r["economic_summary"]["final_equity_eur"],final_equity)
            self.assertEqual(r["economic_summary"]["executed_trades"],trades)
            self.assertEqual(r["economic_summary"]["margin_blocked_trades"],0)
            self.assertFalse(r["scenario_boundary"]["historical_point_in_time_margin_certification"])

    def test_04_run_record_blob_is_unchanged(self):
        self.assertEqual(git_blob_sha1("m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json"),"04df816b7c460045808bba61ba2c7662566fef38")

    def test_05_append_only_consumption_authority_closes_v4_exactly_once(self):
        c=load("evidence/M6_STAGE_B_CURRENT_CONFIG_POST_EXECUTION_CONSUMPTION_V1.json")
        self.assertEqual(c["status"],"CONSUMED_EXECUTED_EXACTLY_ONCE")
        self.assertEqual(c["authorization"]["git_blob_sha1"],"f08832e1f7b5eb399ec806ac9690a63f2fa1f3b4")
        self.assertFalse(c["authorization"]["historical_consumed_field"])
        self.assertEqual(c["execution"]["execution_count"],1)
        self.assertEqual(c["execution"]["exact_head_ci"]["run_id"],35595820997)
        a=c["accounting_after_execution"]
        self.assertEqual(a["economic_outcomes_opened_total"],4)
        self.assertEqual(a["current_config_stage_b_outcomes_opened"],2)
        self.assertEqual(a["v2_attempts_used"],2); self.assertEqual(a["v2_evaluated_identities"],2)
        self.assertEqual(a["v2_search_budget_total"],84); self.assertEqual(a["v2_search_budget_remaining"],82)
        self.assertEqual(a["discovery_ledger_entries"],22); self.assertEqual(a["discovery_result_recorded_entries"],2)
        self.assertFalse(c["protected_evidence_opened"]); self.assertFalse(c["live_orders"]); self.assertFalse(c["competition_start"])

    def test_06_provenance_is_corrected_append_only_without_rewriting_results(self):
        p=load("evidence/M6_STAGE_B_CURRENT_CONFIG_POST_EXECUTION_PROVENANCE_CORRECTION_V1.json")
        self.assertEqual(p["classification"],"METADATA_REFERENCE_CORRECTION_NO_ECONOMIC_EFFECT")
        self.assertTrue(p["accepted_results_immutable"])
        c=p["corrected_reference"]
        self.assertEqual(c["persisted_incorrect_value"],"data/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json")
        self.assertEqual(c["authoritative_correct_value"],"evidence/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json")
        self.assertEqual(c["authoritative_git_blob_sha1"],"47c1f081bdce0dec92dd40543d6627ae224f6f8d")
        self.assertEqual(c["economic_effect"],"NONE")
        lineage=p["extra_metadata_lineage"]
        self.assertEqual(lineage["classification"],"POST_EXECUTION_METADATA_PROVENANCE_UNVERIFIED")
        self.assertFalse(lineage["accepted_economic_metrics_invalidated"])
        self.assertFalse(lineage["accepted_result_hashes_invalidated"])

    def test_07_active_state_is_post_execution_and_history_remains_unresolved(self):
        s=load("CURRENT_STATE.json"); t=s["m6"]["stage_b_current_configuration"]
        self.assertEqual(t["state"],"EXECUTED_RESULTS_PERSISTED")
        self.assertFalse(t["execution_authorized"]); self.assertTrue(t["authorization_consumed"])
        self.assertTrue(t["economics_run"]); self.assertTrue(t["results_created"])
        self.assertEqual(t["stage_b_current_config_outcomes_opened"],2)
        self.assertEqual(s["economic_outcomes_opened"],4); self.assertEqual(s["current_config_stage_b_outcomes_opened"],2)
        self.assertEqual(s["v2_attempts_used"],2); self.assertEqual(s["v2_evaluated_identities"],2)
        self.assertEqual(s["v2_search_budget"],84); self.assertEqual(s["v2_search_budget_remaining"],82)
        self.assertEqual(s["discovery_ledger_entries"],26); self.assertEqual(s["discovery_result_recorded_entries"],2)
        self.assertEqual(s["historical_point_in_time_margin_state"],"UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND")
        self.assertFalse(s["historical_margin_blocks_current_operational_work"])
        self.assertFalse(s["protected_evidence_opened"]); self.assertFalse(s["live_orders_authorized"]); self.assertFalse(s["competition_start_authorized"])

    def test_08_v4_remains_immutable_historical_pre_execution_provenance(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json")
        self.assertEqual(a["status"],"AUTHORIZED"); self.assertTrue(a["single_use"])
        self.assertFalse(a["consumed"]); self.assertTrue(a["execution_authorized"]); self.assertTrue(a["independent_audit_pass"])

    def test_09_second_invocation_is_blocked_before_any_economic_or_materialization_code(self):
        missing=ROOT/"__must_not_be_read__"
        paths=StageAInputPaths(us500_m15=missing,nas100_m15=missing,eurusd_m15=missing,us500_transaction_local_cost=missing,nas100_c012_transaction_local_cost=missing)
        names=("verify_repository_current_config_authorities","build_pre_economic_plan","verify_pre_economic_materialization","execute_current_config_scenario_in_memory","_augment_economic_detail")
        ps=[patch(f"m6.stage_b_current_config_execute.{name}",side_effect=AssertionError(f"{name} must not be reached")) for name in names]
        mocks=[p.start() for p in ps]
        try:
            with self.assertRaises(CurrentConfigScenarioAlreadyExecuted):
                execute_authorized_current_config(ROOT,paths,execution_head="must-not-matter",execution_ci_run_id=0)
            for m in mocks: m.assert_not_called()
        finally:
            for p in reversed(ps): p.stop()

    def test_09b_consumption_authority_alone_blocks_before_economics(self):
        with tempfile.TemporaryDirectory() as td:
            isolated_root=Path(td)
            authority_path=isolated_root/"evidence"/"M6_STAGE_B_CURRENT_CONFIG_POST_EXECUTION_CONSUMPTION_V1.json"
            authority_path.parent.mkdir(parents=True)
            authority_path.write_text(
                (ROOT/"evidence"/"M6_STAGE_B_CURRENT_CONFIG_POST_EXECUTION_CONSUMPTION_V1.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.assertFalse((isolated_root/"m6"/"results"/"STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json").exists())
            self.assertFalse((isolated_root/"m6"/"results"/"V2-C006_STAGE_B_CURRENT_CONFIG_V1.json").exists())
            self.assertFalse((isolated_root/"m6"/"results"/"V2-C012_STAGE_B_CURRENT_CONFIG_V1.json").exists())

            missing=isolated_root/"__must_not_be_read__"
            paths=StageAInputPaths(
                us500_m15=missing,
                nas100_m15=missing,
                eurusd_m15=missing,
                us500_transaction_local_cost=missing,
                nas100_c012_transaction_local_cost=missing,
            )
            names=(
                "verify_repository_current_config_authorities",
                "build_pre_economic_plan",
                "verify_pre_economic_materialization",
                "execute_current_config_scenario_in_memory",
                "_augment_economic_detail",
            )
            ps=[
                patch(
                    f"m6.stage_b_current_config_execute.{name}",
                    side_effect=AssertionError(f"{name} must not be reached"),
                )
                for name in names
            ]
            mocks=[p.start() for p in ps]
            try:
                with self.assertRaises(CurrentConfigScenarioAlreadyExecuted):
                    execute_authorized_current_config(
                        isolated_root,
                        paths,
                        execution_head="must-not-matter",
                        execution_ci_run_id=0,
                    )
                for m in mocks:
                    m.assert_not_called()
            finally:
                for p in reversed(ps):
                    p.stop()

    def test_10_immutable_candidate_cost_margin_and_ledger_blobs_are_unchanged(self):
        expected={
            "discovery/candidates/V2-C006.json":"a5a6e4865206a0f85afcae28a65004e1e24a8277",
            "discovery/candidates/V2-C012.json":"a9a8464d9cf161c3dcae39536280089058e882d9",
            "evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json":"64bc7a000e750cd29710b372c4e5587f1610668a",
            "evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json":"63a959ef9c767956d92772102f3aae3ab3b58237",
            "evidence/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json":"47c1f081bdce0dec92dd40543d6627ae224f6f8d",
        }
        for ref,sha in expected.items(): self.assertEqual(git_blob_sha1(ref),sha,ref)
        lines=(ROOT/"discovery/ledger.jsonl").read_bytes().splitlines()
        prefix22=b"\n".join(lines[:22])
        historical_blob=hashlib.sha1(f"blob {len(prefix22)}\\0".encode("ascii")+prefix22).hexdigest()
        self.assertEqual(historical_blob,"c2ca9eb4d6d3d523b3d5443d5b7fe6993abaaa80")

    def test_11_historical_certification_and_protected_boundary_remain_closed(self):
        run=load("m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json")
        c=load("evidence/M6_STAGE_B_CURRENT_CONFIG_POST_EXECUTION_CONSUMPTION_V1.json")
        self.assertEqual(run["historical_margin_certification_effect"],"NONE")
        self.assertEqual(c["historical_margin"]["state"],"UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND")
        self.assertEqual(c["historical_margin"]["certification_effect"],"NONE")
        self.assertFalse(c["historical_margin"]["blocks_current_operational_work"])
        self.assertFalse(c["protected_evidence_opened"])

if __name__=="__main__":
    unittest.main(verbosity=2)
