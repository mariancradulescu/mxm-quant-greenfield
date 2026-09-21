import hashlib
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from discovery.canonical import compute_result_hash
from discovery.ledger import derive_active_spec_hashes, read_ledger
from discovery.schema import validate_result

ROOT = Path(__file__).resolve().parents[1]

C006_SPEC = "75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49"
C012_SPEC = "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845"
C006_RESULT_HASH = "223e83c20b7bb64c07e27029510c5b05f9c63a771b6ad0342548949f348d500a"
C012_RESULT_HASH = "70159f6b9b97ffb06d72510df2e1f5014967ac2ac8c94ccf1f69239e5500146c"
ENTRY21_HASH = "c8e743f28c933ab286bc548ab20a2ec0fea9437c541b3b925c22dd27c04cf4a9"
ENTRY22_HASH = "eb0e76934fc41f590a8dc25a506b948f7bb10d4787ab28dac07595d8d67e5614"
LINE20_HASH = "4b63368c36bf048df5456d48f3cd80c6fae61d60cb79e4f1e5774cdf4e4809ad"
PREFIX20_BLOB = "dcc4cf0b4ef39d63eff153d3ca6d151dafe26201"
COST_RULE_BLOB = "64bc7a000e750cd29710b372c4e5587f1610668a"
FAILED_RESULT_COMMIT = "7b53284834dc9097c414ac696319af6c1196c8ca"
FAILED_RUN = 35502923344


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def git_blob_sha_bytes(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + bytes([0]) + data).hexdigest()


def no_duplicate_object_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AssertionError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def expected_iso_weeks():
    cursor = date(2022, 1, 3)
    end = date(2026, 9, 16)
    out, seen = [], set()
    while cursor <= end:
        iso = cursor.isocalendar()
        key = f"{iso.year:04d}-W{iso.week:02d}"
        if key not in seen:
            out.append(key)
            seen.add(key)
        cursor += timedelta(days=1)
    return out


class StageAPostOutcomePersistenceIntegrityTests(unittest.TestCase):
    def test_01_standalone_results_validate_and_hash(self):
        for rel, expected in (
            ("discovery/results/V2-C006_STAGE_A_V1.json", C006_RESULT_HASH),
            ("discovery/results/V2-C012_STAGE_A_V1.json", C012_RESULT_HASH),
        ):
            result = load(rel)
            self.assertTrue(validate_result(result))
            self.assertEqual(result["result_hash"], expected)
            self.assertEqual(compute_result_hash(result), expected)

    def test_02_c012_json_has_no_duplicate_keys_and_complete_week_grid(self):
        raw = (ROOT / "discovery/results/V2-C012_STAGE_A_V1.json").read_text(encoding="utf-8")
        parsed = json.loads(raw, object_pairs_hook=no_duplicate_object_pairs)
        weeks = parsed["metrics"]["weekly_events"]
        self.assertEqual(list(weeks), expected_iso_weeks())
        self.assertIn("2022-W35", weeks)
        self.assertEqual(raw.count('"2022-W05"'), 1)
        self.assertEqual(raw.count('"2022-W35"'), 1)

    def test_03_ledger_prefix_1_20_is_byte_identical_historical_authority(self):
        lines = (ROOT / "discovery/ledger.jsonl").read_bytes().splitlines(keepends=True)
        self.assertEqual(len(lines), 22)
        self.assertEqual(git_blob_sha_bytes(b"".join(lines[:20])), PREFIX20_BLOB)

    def test_04_ledger_validates_all_22_and_exact_result_count(self):
        ledger = read_ledger(ROOT / "discovery/ledger.jsonl")
        self.assertEqual(len(ledger), 22)
        self.assertEqual(sum(e["entry_type"] == "RESULT_RECORDED" for e in ledger), 2)

    def test_05_ledger_result_payloads_exactly_match_standalone_results(self):
        ledger = read_ledger(ROOT / "discovery/ledger.jsonl")
        entries = {e["candidate_id"]: e for e in ledger if e["entry_type"] == "RESULT_RECORDED"}
        for cid in ("V2-C006", "V2-C012"):
            standalone = load(f"discovery/results/{cid}_STAGE_A_V1.json")
            self.assertEqual(entries[cid]["payload"]["result"], standalone)
            self.assertEqual(entries[cid]["payload"]["result_hash"], compute_result_hash(standalone))

    def test_06_hash_chain_20_21_22_is_exact(self):
        ledger = read_ledger(ROOT / "discovery/ledger.jsonl")
        e20, e21, e22 = ledger[19], ledger[20], ledger[21]
        self.assertEqual(e20["entry_hash"], LINE20_HASH)
        self.assertEqual(e21["previous_entry_hash"], LINE20_HASH)
        self.assertEqual(e21["entry_hash"], ENTRY21_HASH)
        self.assertEqual(e22["previous_entry_hash"], ENTRY21_HASH)
        self.assertEqual(e22["entry_hash"], ENTRY22_HASH)

    def test_07_active_candidate_hashes_and_cost_authority_unchanged(self):
        active = derive_active_spec_hashes(read_ledger(ROOT / "discovery/ledger.jsonl"))
        self.assertEqual(active["V2-C006"], C006_SPEC)
        self.assertEqual(active["V2-C012"], C012_SPEC)
        cost_bytes = (ROOT / "evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json").read_bytes()
        self.assertEqual(git_blob_sha_bytes(cost_bytes), COST_RULE_BLOB)

    def test_08_live_accounting_is_four_and_budget_remaining_82(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["economic_outcomes_opened"], 4)
        self.assertEqual(state["v2_attempts_used"], 2)
        self.assertEqual(state["v2_evaluated_identities"], 2)
        self.assertEqual(state["v2_search_budget"], 84)
        self.assertEqual(state["v2_search_budget_remaining"], 82)

    def test_09_survivors_are_stage_a_only_and_protected_remains_closed(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["discovery_survivors"], ["V2-C006", "V2-C012"])
        self.assertEqual(state["certification_survivors"], [])
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])
        for cid in ("V2-C006", "V2-C012"):
            self.assertEqual(load(f"discovery/results/{cid}_STAGE_A_V1.json")["eur200_feasibility"]["state"], "NOT_EVALUATED")

    def test_10_stage_b_does_not_exist_and_is_not_authorized(self):
        state = load("CURRENT_STATE.json")
        stage_b_files = list((ROOT / "discovery/results").glob("*STAGE_B*"))
        self.assertEqual(stage_b_files, [])
        self.assertFalse(state["m6"]["tier1_stage_a"]["stage_b_authorized"])
        self.assertFalse(state["m6"]["tier1_stage_a"]["stage_b_run"])

    def test_11_historical_pre_outcome_and_failed_acceptance_artifacts_remain_historical(self):
        auth = load("data/M6_STAGE_A_EXECUTION_AUTHORIZATION_V1.json")
        prep = load("evidence/M6_STAGE_A_TIER1_PRE_ECONOMIC_MATERIALIZATION_V1.json")
        v1 = load("data/M6_STAGE_A_TIER1_RESULT_ACCEPTANCE_V1.json")
        self.assertEqual(auth["preconditions"]["economic_outcomes_opened"], 0)
        self.assertEqual(auth["preconditions"]["v2_attempts_used"], 0)
        self.assertEqual(prep["research_state"]["economic_outcomes_opened"], 0)
        self.assertEqual(v1["status"], "TWO_STAGE_A_OUTCOMES_RECORDED")

    def test_12_correction_authority_records_failed_ci_and_no_economic_rerun(self):
        corr = load("evidence/M6_STAGE_A_POST_OUTCOME_PERSISTENCE_INTEGRITY_CORRECTION_V1.json")
        self.assertEqual(corr["failed_persistence_state"]["result_commit_sha"], FAILED_RESULT_COMMIT)
        self.assertEqual(corr["failed_persistence_state"]["exact_head_ci_run_id"], FAILED_RUN)
        self.assertEqual(corr["failed_persistence_state"]["tests_run"], 446)
        self.assertEqual(corr["failed_persistence_state"]["failures"], 25)
        self.assertEqual(corr["failed_persistence_state"]["errors"], 15)
        self.assertFalse(corr["recovery_semantics"]["economic_evaluation_reexecuted"])
        self.assertFalse(corr["recovery_semantics"]["pnl_recomputed"])
        self.assertFalse(corr["recovery_semantics"]["new_attempt_consumed"])
        self.assertFalse(corr["stage_b"]["run"])

    def test_13_current_state_is_internally_post_execution_coherent(self):
        state = load("CURRENT_STATE.json")
        self.assertTrue(state["m6"]["economics_run"])
        self.assertEqual(state["m6"]["first_stage_a_runner"]["state"], "EXECUTED_RESULTS_RECORDED")
        self.assertTrue(state["m6"]["first_stage_a_runner"]["authorization_consumed"])
        self.assertTrue(state["m6"]["first_stage_a_runner"]["results_created"])
        self.assertNotIn("PREPARED_NOT_RUN", state["m6"]["first_stage_a_runner"]["preparation_detail"])
        self.assertNotIn("PREPARED_NOT_RUN", state["m6"]["auxiliary_evidence"]["state"])

    def test_14_v2_acceptance_supersedes_failed_v1_without_rewriting_it(self):
        a = load("data/M6_STAGE_A_TIER1_RESULT_ACCEPTANCE_V2.json")
        self.assertEqual(a["supersedes"]["ref"], "data/M6_STAGE_A_TIER1_RESULT_ACCEPTANCE_V1.json")
        self.assertEqual(a["supersedes"]["git_blob_sha1"], "3bbad4baaa79ca0a29f31bfb08a8134fd0c93426")
        self.assertEqual(a["ledger"]["sequence_21_entry_hash"], ENTRY21_HASH)
        self.assertEqual(a["ledger"]["sequence_22_entry_hash"], ENTRY22_HASH)
        self.assertEqual(a["accounting"]["v2_attempts_consumed"], 2)
        self.assertFalse(a["integrity"]["economic_re_evaluation"])
        self.assertFalse(a["integrity"]["stage_b_run"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
