import json, unittest
from pathlib import Path
from discovery.ledger import read_ledger
from research_v3.lifecycle import (
    candidate_lifecycle, find_result_version, repository_lifecycle_summary,
    validate_current_authority,
)

ROOT=Path(__file__).resolve().parents[1]

class ResearchV3LifecycleTests(unittest.TestCase):
    def test_repository_summary_separates_identity_exposure_from_result_versions(self):
        summary=repository_lifecycle_summary(ROOT)
        self.assertEqual(summary["distinct_identity_outcomes_opened"],16)
        self.assertEqual(summary["stage_a_result_recorded_entries"],21)
        self.assertEqual(summary["same_identity_successor_result_entries"],5)
        self.assertEqual(summary["implementation_correction_entries"],5)
        self.assertEqual(summary["incomplete_corrections"],{})
        self.assertEqual(summary["ledger_entries"],62)
        self.assertEqual(summary["ledger_tail_entry_hash"],"69d99c52e7486e1a2c6271437ae5b159e942f10b013ccae3e6a5e477affea250")

    def test_c012_has_two_versioned_successors_and_current_authority_is_latest(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        state=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        lc=candidate_lifecycle(ledger,"V2-C012")
        self.assertEqual(len(lc.results),3)
        self.assertEqual(lc.successor_count,2)
        self.assertEqual(len(lc.corrections),2)
        self.assertEqual(find_result_version(lc,"01a0a9b7d44f0ed22d628538d243e3f8118233cdfb3383016490b4aa5240c503").row["sequence"],42)
        current=validate_current_authority(ROOT,state,lc)
        self.assertIsNotNone(current)
        self.assertEqual(current.result_hash,"897eb0d6787b38470c72040cf6109397b398d77ecf9a7a65eb9c287bab1fac8e")
        self.assertEqual(current.row["sequence"],58)

    def test_c023_historical_result_and_corrected_successor_both_remain_canonical(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        state=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        lc=candidate_lifecycle(ledger,"V2-C023")
        self.assertEqual(len(lc.results),2)
        self.assertEqual(lc.initial_result.result_hash,"e11ea2b1d8b66a1dcae565e3067d5bbba2a49ab9fb401ebf476a6d14ec476d98")
        self.assertEqual(lc.initial_result.row["sequence"],40)
        self.assertEqual(lc.current_result.result_hash,"7a2ddce8a2bad2ec8baeca3d21494e30ea235cbaea64ebce367e9658f639be25")
        self.assertEqual(validate_current_authority(ROOT,state,lc).result_hash,lc.current_result.result_hash)

    def test_wave02_may_mix_immutable_historical_result_and_later_corrected_successor(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        c24=candidate_lifecycle(ledger,"V2-C024")
        c25=candidate_lifecycle(ledger,"V2-C025")
        self.assertEqual(len(c24.results),1)
        self.assertEqual(c24.successor_count,0)
        self.assertEqual(len(c25.results),2)
        self.assertEqual(c25.initial_result.result_hash,"f4c4e63952cf5c7a66b11a127d2a6dda057436f8091b0b59ba6897347c1fa077")
        self.assertEqual(c25.current_result.result_hash,"73f5c13fd72c118cf533430063351cef18060c3ac4e739c8b5e3b285a4bc9336")
        self.assertEqual(c25.current_result.result["status"],"DATA_INSUFFICIENT")

if __name__=="__main__":
    unittest.main(verbosity=2)
