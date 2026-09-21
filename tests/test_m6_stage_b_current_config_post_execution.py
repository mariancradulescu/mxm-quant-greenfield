import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def canonical_result_hash(result):
    payload = dict(result)
    observed = payload.pop("result_sha256")
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return observed, hashlib.sha256(canonical).hexdigest()


class StageBCurrentConfigPostExecutionTests(unittest.TestCase):
    def test_01_execution_record_is_exactly_once_and_exact_head_green(self):
        run = load("m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json")
        self.assertEqual(run["status"], "EXECUTED_EXACTLY_ONCE")
        self.assertEqual(run["source_gate_ref"], "data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json")
        self.assertEqual(run["source_gate_git_blob_sha1"], "f08832e1f7b5eb399ec806ac9690a63f2fa1f3b4")
        self.assertEqual(run["execution_head"], "1a395746a5f1351fd239a612131faec975f6f060")
        self.assertEqual(run["execution_exact_head_ci"]["run_id"], 35595820997)
        self.assertEqual(run["execution_exact_head_ci"]["conclusion"], "SUCCESS")
        self.assertEqual(run["execution_exact_head_ci"]["tests_passed"], 544)
        self.assertEqual(run["execution_exact_head_ci"]["tests_failed"], 0)
        self.assertEqual(run["execution_count"], 1)
        self.assertEqual(run["current_config_stage_b_outcomes_opened"], 2)
        self.assertFalse(run["protected_evidence_opened"])

    def test_02_accounting_stays_on_existing_two_v2_identities(self):
        run = load("m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json")
        a = run["accounting_after_execution"]
        self.assertEqual(a["economic_outcomes_opened"], 4)
        self.assertEqual(a["v2_attempts_used"], 2)
        self.assertEqual(a["v2_evaluated_identities"], 2)
        self.assertEqual(a["v2_search_budget_total"], 84)
        self.assertEqual(a["v2_search_budget_remaining"], 82)
        self.assertEqual(a["discovery_ledger_entries"], 22)
        self.assertEqual(a["discovery_result_recorded_entries"], 2)
        ledger = [
            json.loads(line)
            for line in (ROOT / "discovery/ledger.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(ledger), 22)
        self.assertEqual(sum(x["entry_type"] == "RESULT_RECORDED" for x in ledger), 2)

    def test_03_c006_result_is_complete_and_hash_valid(self):
        r = load("m6/results/V2-C006_STAGE_B_CURRENT_CONFIG_V1.json")
        observed, calculated = canonical_result_hash(r)
        self.assertEqual(observed, calculated)
        self.assertEqual(observed, "72e1c6dd94969add768d5640c245a3cd400fa4e5777fd518b3cf09de872e8d6f")
        self.assertEqual(r["execution_result_sha256"], "ad11540b23ad7c40ab1c3c461c2107646e4cad60ba15e6ddaa505883543beec0")
        self.assertEqual(r["candidate_id"], "V2-C006")
        self.assertEqual(r["label"], "STAGE_B_CURRENT_CONFIGURATION_SCENARIO")
        e = r["economic_summary"]
        self.assertEqual(e["starting_equity_eur"], 200.0)
        self.assertEqual(e["final_equity_eur"], 258.6947216647057)
        self.assertEqual(e["executed_trades"], 108)
        self.assertEqual(e["margin_blocked_trades"], 0)
        self.assertEqual(r["frozen_reporting"]["weekly_final_equity_distribution"]["period_count"], 246)
        self.assertEqual(r["frozen_reporting"]["monthly_final_equity_distribution"]["period_count"], 57)
        self.assertFalse(r["scenario_boundary"]["historical_point_in_time_margin_certification"])

    def test_04_c012_result_is_complete_and_hash_valid(self):
        r = load("m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V1.json")
        observed, calculated = canonical_result_hash(r)
        self.assertEqual(observed, calculated)
        self.assertEqual(observed, "51edfcc76693425a07c24962f7b3c060fa2e7bb127385233f28f4fc1233edcaa")
        self.assertEqual(r["execution_result_sha256"], "8cc248def5564c58bf31d374e2100081751f272c714ac099d6b7e8eb6c971923")
        self.assertEqual(r["candidate_id"], "V2-C012")
        self.assertEqual(r["label"], "STAGE_B_CURRENT_CONFIGURATION_SCENARIO")
        e = r["economic_summary"]
        self.assertEqual(e["starting_equity_eur"], 200.0)
        self.assertEqual(e["final_equity_eur"], 257.84259369263856)
        self.assertEqual(e["executed_trades"], 35)
        self.assertEqual(e["margin_blocked_trades"], 0)
        self.assertEqual(r["frozen_reporting"]["weekly_final_equity_distribution"]["period_count"], 246)
        self.assertEqual(r["frozen_reporting"]["monthly_final_equity_distribution"]["period_count"], 57)
        self.assertFalse(r["scenario_boundary"]["historical_point_in_time_margin_certification"])

    def test_05_run_record_binds_both_results_and_keeps_history_unresolved(self):
        run = load("m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json")
        self.assertEqual(
            run["persisted_result_sha256"],
            {
                "V2-C006": "72e1c6dd94969add768d5640c245a3cd400fa4e5777fd518b3cf09de872e8d6f",
                "V2-C012": "51edfcc76693425a07c24962f7b3c060fa2e7bb127385233f28f4fc1233edcaa",
            },
        )
        self.assertEqual(
            run["historical_margin_state"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertEqual(run["historical_margin_certification_effect"], "NONE")
        self.assertFalse(run["live_orders"])
        self.assertFalse(run["competition_start"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
