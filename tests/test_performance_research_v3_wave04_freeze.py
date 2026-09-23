import hashlib, json, unittest
from pathlib import Path
from unittest.mock import patch

from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.ledger import read_ledger
from research_v3.wave04_execute import V3Wave04ExecutionNotAuthorized, execute_authorized

ROOT=Path(__file__).resolve().parents[1]
IDS=("V2-C027","V2-C028")
SPEC_HASHES={"V2-C027":"6c2945d22af7d10156786a823dca7df21afbbb2c96fa92e060e70e58857de8e2","V2-C028":"f0a0b7c78010232bda8035bb2ab4215e1f37624a17e8eb094e2515daeb2f6e5c"}
EVAL_SHA256="3df4629a7bf2aaa6b9008df364f05b134f2c2b1c2fe68f1022932f5dbf786789"
EVAL_BLOB="a298083ed479c767e9b522dce027c02d7ee70ff1"
WRAPPER_BLOB="0275edd571daf65b23c9e634a89206d196792057"
BLOCK_REF="research_v3/WAVE_04_PRE_OUTCOME_CAUSALITY_BLOCK_V1.json"\nCURRENT_BLOCK_REF="research_v3/WAVE_04_PRE_OUTCOME_CAUSALITY_BLOCK_V2.json"
CONTRACT_REF="research_v3/LIVE_EQUIVALENT_HISTORICAL_REPLAY_CONTRACT_V1.json"

def load(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))
def blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

class PerformanceResearchV3Wave04FreezeTests(unittest.TestCase):
    def test_01_specs_are_distinct_frozen_and_hash_valid(self):
        families=[]
        for cid in IDS:
            spec=load(f"discovery/candidates/{cid}.json")
            self.assertTrue(verify_spec_hash(spec))
            self.assertEqual(spec["spec_hash"],SPEC_HASHES[cid])
            self.assertTrue(spec["provenance"]["frozen_before_own_economic_outcome"])
            self.assertFalse(spec["provenance"]["protected_evidence_used"])
            families.append(spec["mechanism"]["family"])
        self.assertEqual(families,["VOLATILITY_EXPANSION_BREAKOUT","CROSS_MARKET_LEAD_LAG"])

    def test_02_historical_freeze_and_code_bindings_are_immutable(self):
        wave=load("research_v3/WAVE_04_PRE_OUTCOME_FREEZE_V1.json")
        self.assertEqual(wave["status"],"FROZEN_PENDING_EXACT_HEAD_GREEN")
        self.assertEqual(tuple(wave["candidate_ids"]),IDS)
        self.assertEqual(wave["candidate_spec_hashes"],SPEC_HASHES)
        self.assertEqual(wave["evaluator"]["sha256"],EVAL_SHA256)
        self.assertEqual(wave["evaluator"]["git_blob_sha1"],EVAL_BLOB)
        self.assertEqual(hashlib.sha256((ROOT/wave["evaluator"]["ref"]).read_bytes()).hexdigest(),EVAL_SHA256)
        self.assertEqual(blob_sha1(ROOT/wave["evaluator"]["ref"]),EVAL_BLOB)
        self.assertEqual(blob_sha1(ROOT/"research_v3/wave04_execute.py"),WRAPPER_BLOB)
        self.assertEqual(wave["accounting_before"],{
            "v2_attempts_used":16,"v2_search_budget_remaining":68,
            "v2_evaluated_identities":16,"economic_outcomes_opened":19,
            "discovery_ledger_entries":52,"discovery_result_recorded_entries":17})
        self.assertEqual(wave["new_attempts_consumed_by_freeze"],0)
        self.assertFalse(wave["candidate_own_outcomes_opened"])

    def test_03_current_lifecycle_is_monotonic_duplicate_free_and_revoked_pre_outcome(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        state=load("CURRENT_STATE.json")
        w=state["performance_research_v3"]["wave04"]
        for cid,seq in (("V2-C027",53),("V2-C028",54)):
            rows=[x for x in ledger if x.get("candidate_id")==cid]
            freezes=[x for x in rows if x["entry_type"]=="CANDIDATE_FROZEN"]
            results=[x for x in rows if x["entry_type"]=="RESULT_RECORDED"]
            self.assertEqual(len(freezes),1)
            self.assertEqual(len(results),0)
            self.assertEqual(freezes[0]["sequence"],seq)
            self.assertEqual(freezes[0]["spec_hash"],SPEC_HASHES[cid])
        self.assertEqual(w["status"],"BLOCKED_PRE_OUTCOME_LIVE_EQUIVALENCE_VIOLATION")
        self.assertTrue(w["authorization_revoked"])
        self.assertFalse(w["candidate_own_outcomes_opened"])
        self.assertEqual(w["economic_attempt_delta"],0)
        self.assertEqual(state["v2_attempts_used"],4)
        self.assertEqual(state["v2_evaluated_identities"],16)
        self.assertEqual(state["v2_search_budget_remaining"],80)
        self.assertEqual(state["economic_outcomes_opened"],19)
        self.assertEqual(state["discovery_ledger_entries"],len(ledger))
        self.assertEqual(state["discovery_result_recorded_entries"],sum(x["entry_type"]=="RESULT_RECORDED" for x in ledger))
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])

    def test_04_revoked_authorization_fails_before_economics(self):
        auth=load("research_v3/WAVE_04_EXECUTION_AUTHORIZATION_V1.json")
        self.assertEqual(auth["status"],"REVOKED_PRE_OUTCOME_CAUSALITY_INVALID")
        self.assertEqual(tuple(auth["candidate_ids"]),IDS)
        self.assertEqual(auth["candidate_spec_hashes"],SPEC_HASHES)
        self.assertEqual(auth["revocation_ref"],BLOCK_REF)
        self.assertFalse(auth["candidate_own_outcomes_opened"])
        with patch("research_v3.wave04_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
            with self.assertRaises(V3Wave04ExecutionNotAuthorized):
                execute_authorized(ROOT,"missing.zip",execution_head=auth["execution_gate_head"],execution_ci_run_id=auth["execution_gate_ci_run_id"])
            economic.assert_not_called()

    def test_05_block_authority_records_exact_pre_outcome_defect_and_zero_consumption(self):
        block=load(BLOCK_REF)
        self.assertEqual(block["status"],"BLOCKED_PRE_OUTCOME_LIVE_EQUIVALENCE_VIOLATION")
        self.assertEqual(block["candidate_spec_hashes"],SPEC_HASHES)
        self.assertEqual(block["evaluator"]["sha256"],EVAL_SHA256)
        self.assertFalse(block["forensic_recovery"]["economic_outcomes_opened"])
        self.assertEqual(block["forensic_recovery"]["determination"],"NEITHER_C027_NOR_C028_OUTCOME_WAS_OPENED")
        self.assertEqual(block["consumed_identity_law"]["attempts_consumed"],0)
        self.assertEqual(block["consumed_identity_law"]["v2_attempts_used_remains"],16)
        self.assertTrue(block["disposition"]["authorization_revoked"])
        self.assertFalse(block["disposition"]["execute_frozen_wave04"])\n        current=load(CURRENT_BLOCK_REF)\n        self.assertEqual(current["status"],"BLOCKED_PRE_OUTCOME_FROZEN_SPEC_CAUSALLY_INVALID")\n        self.assertTrue(all(v=="FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY" for v in current["classifications"].values()))\n        self.assertEqual(current["attempts_consumed"],0)

    def test_06_live_equivalent_contract_forbids_future_exit_admission(self):
        contract=load(CONTRACT_REF)
        self.assertEqual(contract["status"],"ACTIVE")
        self.assertEqual(contract["core_rule"],"AT_HISTORICAL_TIME_T_THE_SYSTEM_MAY_USE_ONLY_INFORMATION_AVAILABLE_BY_T")
        self.assertIn("FUTURE_BARS_IN_DECISION_OR_ADMISSION",contract["prohibitions"])
        self.assertIn("future exit-bar existence or price must never be queried to decide admission at T.",contract["decision_boundary_rules"]["future_exit"])
        self.assertFalse(contract["safety"]["protected_evidence_opened"])
        self.assertFalse(contract["safety"]["live_orders_authorized"])
        self.assertFalse(contract["safety"]["competition_start_authorized"])

if __name__=="__main__": unittest.main(verbosity=2)
