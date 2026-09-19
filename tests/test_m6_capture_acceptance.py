import json
import unittest
from pathlib import Path

from discovery.ledger import read_ledger

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class M6CaptureAcceptanceTests(unittest.TestCase):
    def test_01_capture_acceptance_binds_exact_hash_verified_components(self):
        a = load("data/PRIMARY_WAVE_02_CAPTURE_ACCEPTANCE_V1.json")
        self.assertEqual(
            a["status"],
            "RAW_COMPONENTS_HASH_VERIFIED_CURRENT_MAPPING_11_OF_11_PASS_AUXILIARY_REQUIREMENTS_PARTIAL",
        )
        self.assertEqual(a["broker_product_preflight"]["pass_count"], 11)
        self.assertEqual(a["broker_product_preflight"]["required_count"], 11)
        self.assertTrue(a["broker_product_preflight"]["all_current_mappings_pass"])
        self.assertEqual(len(a["raw_components"]), 11)
        self.assertEqual(len(a["auxiliary_conversion_components"]), 2)
        self.assertEqual(
            a["source_capture_bundle"]["original_sha256"],
            "540513555ea66fd67f1c641679618b03d6e6d50b836b06f6f5d0d5ed551ea2a9",
        )
        self.assertEqual(
            a["source_capture_bundle"]["reconciled_sha256"],
            "88c68f1724eba71ef58fe02a929c935dc1cbf4be432897db599be7b37fd4ae72",
        )
        self.assertEqual(
            a["source_capture_bundle"]["stale_blocked_marker"]["classification"],
            "STALE_OUTPUT_FROM_PRIOR_FAILED_ATTEMPT_NOT_CURRENT_CAPTURE_STATE",
        )
        self.assertFalse(any(x["protected_forward_rows_included"] for x in a["raw_components"]))

    def test_02_data_manifest_registers_all_actual_primary_and_conversion_hashes(self):
        a = load("data/PRIMARY_WAVE_02_CAPTURE_ACCEPTANCE_V1.json")
        d = load("data/DATA_MANIFEST.json")
        by_id = {x["dataset_id"]: x for x in d["datasets"]}
        self.assertIn("A116_CADJPY_V2_H1_SOURCE_PACK_V1_STRICT", by_id)
        for raw in a["raw_components"]:
            item = by_id[raw["raw_capture_id"]]
            self.assertEqual(item["state"], "MATERIALIZED_HASH_VERIFIED_RAW_COMPONENT")
            self.assertEqual(item["rows"], raw["row_count"])
            self.assertEqual(item["csv_sha256"], raw["csv_sha256"])
            self.assertFalse(item["protected_forward_rows_included"])
            self.assertFalse(item["resampling_performed"])
            self.assertFalse(item["synthetic_fill_performed"])
            self.assertFalse(item["forward_fill_performed"])
        for aux in a["auxiliary_conversion_components"]:
            item = by_id[aux["aux_raw_id"]]
            self.assertEqual(
                item["state"], "MATERIALIZED_HASH_VERIFIED_AUXILIARY_RAW_COMPONENT"
            )
            self.assertEqual(item["rows"], aux["row_count"])
            self.assertEqual(item["csv_sha256"], aux["csv_sha256"])
            self.assertEqual(
                item["historical_chain_point_in_time_validity"],
                "UNRESOLVED_CURRENT_CHAIN_NOT_PROVEN_HISTORICALLY_EFFECTIVE",
            )
        m = d["primary_wave_02_materialization"]
        self.assertEqual(m["raw_primary_series_materialized"], 11)
        self.assertEqual(m["auxiliary_conversion_series_materialized"], 2)
        self.assertFalse(m["candidate_ready_for_economic_outcome"])

    def test_03_current_state_advances_materialization_only_not_economics(self):
        s = load("CURRENT_STATE.json")
        self.assertEqual(s["m6"]["status"], "PENDING")
        self.assertEqual(
            s["m6"]["raw_materialization"]["state"],
            "PASS_HASH_VERIFIED_PRIMARY_WAVE_02_RAW_COMPONENTS",
        )
        self.assertEqual(
            s["m6"]["auxiliary_evidence"]["state"],
            "TIER1_PREOUTCOME_COST_METHOD_RESOLVED_C006_C012_READY",
        )
        self.assertEqual(
            s["m6"]["auxiliary_evidence"]["active_readiness_ref"],
            "data/PRIMARY_WAVE_02_PRE_M6_READINESS_V6.json",
        )
        self.assertFalse(s["m6"]["auxiliary_evidence"]["m6_stage_a_economics_authorized"])
        self.assertFalse(s["m6"]["economics_run"])
        self.assertEqual(s["economic_outcomes_opened"], 0)
        self.assertEqual(s["v2_attempts_used"], 0)
        self.assertEqual(s["v2_evaluated_identities"], 0)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])

    def test_04_no_result_or_protected_boundary_change_from_capture_acceptance(self):
        ledger = read_ledger(ROOT / "discovery/ledger.jsonl")
        protected = load("V2_PROTECTED_FORWARD_START.json")
        self.assertFalse(any(x["entry_type"] == "RESULT_RECORDED" for x in ledger))
        self.assertEqual(len(ledger), 20)
        self.assertEqual(
            protected["V2_PROTECTED_FORWARD_START"], "2026-09-17T12:02:58Z"
        )
        self.assertFalse(protected["protected_evidence_opened"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
