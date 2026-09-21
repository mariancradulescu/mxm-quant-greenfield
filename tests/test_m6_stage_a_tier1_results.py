import json
import unittest
from pathlib import Path

from discovery.canonical import compute_result_hash
from discovery.ledger import derive_active_spec_hashes, read_ledger
from discovery.schema import validate_result

ROOT=Path(__file__).resolve().parents[1]

C006_HASH="75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49"
C012_HASH="3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845"
C006_RESULT_HASH="223e83c20b7bb64c07e27029510c5b05f9c63a771b6ad0342548949f348d500a"
C012_RESULT_HASH="70159f6b9b97ffb06d72510df2e1f5014967ac2ac8c94ccf1f69239e5500146c"
EVALUATOR_SHA="16e302dd3a9b58983cbfcb68ca0934c920ea8007fd11e9577685fa95f879874e"
COST_RULE_BLOB="64bc7a000e750cd29710b372c4e5587f1610668a"


def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))


class M6StageATier1ResultsTests(unittest.TestCase):
    def test_01_results_validate_and_hash_exactly(self):
        for rel, expected in (
            ("discovery/results/V2-C006_STAGE_A_V1.json", C006_RESULT_HASH),
            ("discovery/results/V2-C012_STAGE_A_V1.json", C012_RESULT_HASH),
        ):
            r=load(rel)
            self.assertTrue(validate_result(r))
            self.assertEqual(r["result_hash"], expected)
            self.assertEqual(compute_result_hash(r), expected)
            self.assertEqual(r["stage"], "A")
            self.assertEqual(r["status"], "DISCOVERY_SURVIVOR")
            self.assertEqual(r["eur200_feasibility"]["state"], "NOT_EVALUATED")
            self.assertEqual(r["provenance"]["evaluator"]["sha256"], EVALUATOR_SHA)

    def test_02_c006_exact_stage_a_metrics(self):
        r=load("discovery/results/V2-C006_STAGE_A_V1.json")
        m=r["metrics"]
        self.assertEqual(m["event_count"],108)
        self.assertEqual(m["gross_pnl"],154.16920204753237)
        self.assertEqual(m["coarse_net_pnl"],124.72483885922844)
        self.assertEqual(m["gross_return"],0.0014274926115512255)
        self.assertEqual(m["coarse_net_return"],0.00115485961906693)
        self.assertEqual(m["cost_burden"],0.0002726329924842955)
        self.assertEqual(m["drawdown"],53.07545164351332)
        self.assertEqual(
            r["provenance"]["cost_evidence"]["sha256"],
            "601eedcb147021fff54f4d3bd2a43d831c455a821ddafa01a0036afe5c5485d6",
        )

    def test_03_c012_exact_stage_a_metrics(self):
        r=load("discovery/results/V2-C012_STAGE_A_V1.json")
        m=r["metrics"]
        self.assertEqual(m["event_count"],35)
        self.assertEqual(m["gross_pnl"],47.10259401875881)
        self.assertEqual(m["coarse_net_pnl"],40.881179572198114)
        self.assertEqual(m["gross_return"],0.0013457884005359658)
        self.assertEqual(m["coarse_net_return"],0.0011680337020628033)
        self.assertEqual(m["cost_burden"],0.00017775469847316266)
        self.assertEqual(m["drawdown"],37.97260992760511)
        self.assertEqual(
            r["provenance"]["cost_evidence"]["sha256"],
            "dd4f6be917773fc580d4725d7c30ef4aabd5ec4ce19a30fdced8c5a85f4bd999",
        )

    def test_04_ledger_records_exactly_two_results_and_chain(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        self.assertEqual(len(ledger),22)
        results=[x for x in ledger if x["entry_type"]=="RESULT_RECORDED"]
        self.assertEqual(len(results),2)
        e21,e22=results
        self.assertEqual(e21["sequence"],21)
        self.assertEqual(e21["candidate_id"],"V2-C006")
        self.assertEqual(e21["spec_hash"],C006_HASH)
        self.assertEqual(e21["payload"]["result_hash"],C006_RESULT_HASH)
        self.assertEqual(e21["entry_hash"],"c8e743f28c933ab286bc548ab20a2ec0fea9437c541b3b925c22dd27c04cf4a9")
        self.assertEqual(e22["sequence"],22)
        self.assertEqual(e22["candidate_id"],"V2-C012")
        self.assertEqual(e22["spec_hash"],C012_HASH)
        self.assertEqual(e22["payload"]["result_hash"],C012_RESULT_HASH)
        self.assertEqual(e22["previous_entry_hash"],e21["entry_hash"])
        self.assertEqual(e22["entry_hash"],"eb0e76934fc41f590a8dc25a506b948f7bb10d4787ab28dac07595d8d67e5614")

    def test_05_active_candidate_hashes_are_unchanged_after_results(self):
        active=derive_active_spec_hashes(read_ledger(ROOT/"discovery/ledger.jsonl"))
        self.assertEqual(active["V2-C006"],C006_HASH)
        self.assertEqual(active["V2-C012"],C012_HASH)
        self.assertEqual(load("discovery/candidates/V2-C006.json")["spec_hash"],C006_HASH)
        self.assertEqual(load("discovery/candidates/V2-C012.json")["spec_hash"],C012_HASH)

    def test_06_result_acceptance_history_and_live_accounting_are_exact(self):
        a=load("data/M6_STAGE_A_TIER1_RESULT_ACCEPTANCE_V1.json")
        s=load("CURRENT_STATE.json")
        self.assertEqual(a["status"],"TWO_STAGE_A_OUTCOMES_RECORDED")
        self.assertEqual(a["discovery_survivors"],["V2-C006","V2-C012"])
        self.assertEqual(a["certification_survivors"],[])
        self.assertEqual(a["accounting"]["v2_attempts_consumed"],2)
        self.assertEqual(a["accounting"]["economic_outcomes_opened"],2)
        self.assertEqual(a["accounting"]["result_recorded"],2)
        self.assertEqual(a["ledger"]["final_entries"],22)

        self.assertEqual(s["economic_outcomes_opened"],4)
        self.assertEqual(s["v2_attempts_used"],2)
        self.assertEqual(s["v2_evaluated_identities"],2)
        self.assertEqual(s["discovery_survivors"],["V2-C006","V2-C012"])
        self.assertEqual(s["certification_survivors"],[])
        self.assertEqual(s["latest_economic_outcome"]["candidate_id"],"V2-C012")
        self.assertEqual(s["latest_economic_outcome"]["result_hash"],C012_RESULT_HASH)
        self.assertTrue(s["m6"]["economics_run"])
        self.assertEqual(s["m6"]["first_stage_a_runner"]["state"],"EXECUTED_RESULTS_RECORDED")
        self.assertTrue(s["m6"]["first_stage_a_runner"]["authorization_consumed"])
        self.assertTrue(s["m6"]["first_stage_a_runner"]["results_created"])
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])

    def test_07_transaction_local_cost_methodology_and_protected_boundary_unchanged(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(
            s["tier1_discovery_transaction_local_cost_rule_authority"],
            "evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json",
        )
        self.assertFalse(s["protected_evidence_opened"])
        self.assertEqual(
            load("evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json")
            ["primary_discovery_cost"]["name"],
            "TRANSACTION_LOCAL_SAME_ROW_ADVERSE_PROXY",
        )

    def test_08_stage_a_survivors_are_not_certification_survivors(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(s["discovery_survivors"],["V2-C006","V2-C012"])
        self.assertEqual(s["certification_survivors"],[])
        for cid in ("V2-C006","V2-C012"):
            self.assertEqual(
                load(f"discovery/results/{cid}_STAGE_A_V1.json")
                ["eur200_feasibility"]["state"],
                "NOT_EVALUATED",
            )


if __name__=="__main__":
    unittest.main(verbosity=2)
