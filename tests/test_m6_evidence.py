import copy
import json
import tempfile
import unittest
from pathlib import Path

from m6.evidence import (
    CAUSAL_BAR_RULE, CONSERVATIVE_BOUND, COST_BINDING_SCHEMA, DATASET_BINDING_SCHEMA,
    EvidenceError, MISSING_DATA_RULE, UNRESOLVED, VERIFIED, canonical_json_sha256,
    expected_dataset_specs, gate_candidate_pre_outcome, materialize_exact_csv,
    sha256_file, verify_cost_binding, verify_dataset_binding,
)

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = "2026-09-17T12:02:58Z"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def fixture_requirements(instruments=None):
    instruments = instruments or ["TEST"]
    return {
        "candidate_spec_hashes": {"V2-C900": "a" * 64},
        "requirements": {
            "V2-C900": {
                "instruments": instruments,
                "resolution": "H1",
                "interval": {
                    "classification": "DEVELOPMENT_ONLY",
                    "start_utc": "2026-01-01T00:00:00Z",
                    "end_utc": "2026-01-02T23:59:59Z",
                    "protected_boundary_excluded": True,
                },
                "fields": ["time_utc", "open", "high", "low", "close", "tick_volume"],
                "session_semantics": "fixture",
                "synchronization": "fixture",
                "currency_conversion": ["USD_to_EUR causal evidence"],
                "contract_roll": "NOT_APPLICABLE",
                "corporate_actions": "NOT_APPLICABLE",
            }
        },
    }


def write_csv(root, rel="data/materialized/test.csv", timestamps=None):
    timestamps = timestamps or ["2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z"]
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["time_utc,open,high,low,close,tick_volume"]
    for i, ts in enumerate(timestamps, 1):
        rows.append(f"{ts},{i},{i+1},{i-1},{i},10")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def valid_binding(root, requirements=None, instrument="TEST", rel="data/materialized/test.csv"):
    requirements = requirements or fixture_requirements()
    path = Path(root) / rel
    spec = next(x for x in expected_dataset_specs(requirements)
                if x["candidate_id"] == "V2-C900" and x["instrument"] == instrument)
    req = requirements["requirements"]["V2-C900"]
    b = {
        "schema": DATASET_BINDING_SCHEMA,
        "dataset_id": spec["dataset_id"],
        "candidate_id": "V2-C900",
        "spec_hash": "a" * 64,
        "instrument": instrument,
        "resolution": "H1",
        "interval": copy.deepcopy(req["interval"]),
        "timezone": "UTC",
        "causal_availability": CAUSAL_BAR_RULE,
        "missing_data_rule": MISSING_DATA_RULE,
        "source": {
            "broker": "Pepperstone",
            "environment": "Pepperstone - Europe LIVE",
            "acquisition_method": "read-only fixture export",
            "provenance_sha256": "1" * 64,
        },
        "completeness": {
            "state": "COMPLETE",
            "interval": copy.deepcopy(req["interval"]),
            "method": "broker export completeness fixture",
        },
        "broker_mapping": {
            "canonical_instrument": instrument,
            "broker_symbol": f"{instrument}.broker",
            "enabled": True,
            "evidence_sha256": "2" * 64,
        },
        "semantic_evidence": {
            "session": "broker session fixture",
            "synchronization": "single symbol fixture",
            "currency_conversion": "hash-bound conversion fixture",
            "contract_roll": "not applicable fixture",
            "corporate_actions": "not applicable fixture",
        },
        "fields": ["time_utc", "open", "high", "low", "close", "tick_volume"],
        "data_file": rel,
        "sha256": sha256_file(path),
        "row_count": 2,
    }
    b["binding_sha256"] = canonical_json_sha256(b, exclude=("binding_sha256",))
    return b


def conservative_cost(state=CONSERVATIVE_BOUND):
    components = {
        "spread": {
            "applicable": True, "state": CONSERVATIVE_BOUND, "prospectively_frozen": True,
            "bound_direction": "ADVERSE_OR_EQUAL", "basis_sha256": "3" * 64, "bound": 1.0,
        },
        "commission": {
            "applicable": True, "state": VERIFIED, "historical": True,
            "evidence_kind": "HISTORICAL_SERIES", "evidence_sha256": "4" * 64,
            "effective_interval": "fixture",
        },
        "slippage": {
            "applicable": True, "state": CONSERVATIVE_BOUND, "prospectively_frozen": True,
            "bound_direction": "ADVERSE_OR_EQUAL", "basis_sha256": "5" * 64, "rule": "adverse fixture",
        },
        "financing": {"applicable": False},
        "currency_conversion": {
            "applicable": True, "state": CONSERVATIVE_BOUND, "prospectively_frozen": True,
            "bound_direction": "ADVERSE_OR_EQUAL", "basis_sha256": "6" * 64, "bound": 0.1,
        },
    }
    if state == UNRESOLVED:
        components["slippage"] = {"applicable": True, "state": UNRESOLVED}
    b = {
        "schema": COST_BINDING_SCHEMA, "candidate_id": "V2-C900", "spec_hash": "a" * 64,
        "state": state, "prospectively_frozen": True, "positive_financing_benefit_allowed": False,
        "components": components,
    }
    b["binding_sha256"] = canonical_json_sha256(b, exclude=("binding_sha256",))
    return b


class M6EvidenceTests(unittest.TestCase):
    def test_01_live_primary_wave_expands_to_exact_12_dataset_identities(self):
        req = load("data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V2.json")
        specs = expected_dataset_specs(req)
        self.assertEqual(len(specs), 12)
        by_cid = {}
        for s in specs:
            by_cid.setdefault(s["candidate_id"], []).append(s["instrument"])
        self.assertEqual(sorted(by_cid["V2-C011"]), ["AAPL", "AMZN", "META", "MSFT", "NVDA"])
        self.assertEqual(sorted(by_cid["V2-C012"]), ["NAS100", "US500"])

    def test_02_checkpoint_preserves_zero_economics_and_non_authoritative_role(self):
        s = load("data/PRIMARY_WAVE_02_M6_PREPARATION_STATUS_V1.json")
        self.assertEqual(s["status_role"], "NON_AUTHORITATIVE_DERIVED_CHECKPOINT")
        self.assertEqual(s["pre_economic_integrity"]["result_recorded_count"], 0)
        self.assertEqual(s["pre_economic_integrity"]["v2_attempts_used"], 0)
        self.assertFalse(s["pre_economic_integrity"]["protected_evidence_opened"])
        self.assertFalse(s["inventory_findings"]["legacy_pack_bytes_present_at_frozen_ref"])

    def test_03_metadata_only_or_absent_bytes_never_verify(self):
        with tempfile.TemporaryDirectory() as td:
            req = fixture_requirements()
            path = write_csv(td)
            b = valid_binding(td, req)
            path.unlink()
            with self.assertRaises(EvidenceError):
                verify_dataset_binding(b, req, protected_start_utc=PROTECTED, root=td)

    def test_04_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req = fixture_requirements()
            write_csv(td)
            b = valid_binding(td, req)
            b["sha256"] = "f" * 64
            b["binding_sha256"] = canonical_json_sha256(b, exclude=("binding_sha256",))
            with self.assertRaises(EvidenceError):
                verify_dataset_binding(b, req, protected_start_utc=PROTECTED, root=td)

    def test_05_active_spec_hash_and_canonical_identity_are_mandatory(self):
        with tempfile.TemporaryDirectory() as td:
            req = fixture_requirements()
            write_csv(td)
            b = valid_binding(td, req)
            b["spec_hash"] = "b" * 64
            b["binding_sha256"] = canonical_json_sha256(b, exclude=("binding_sha256",))
            with self.assertRaises(EvidenceError):
                verify_dataset_binding(b, req, protected_start_utc=PROTECTED, root=td)

    def test_06_required_csv_fields_are_derived_from_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            req = fixture_requirements()
            p = Path(td) / "data/materialized/test.csv"
            p.parent.mkdir(parents=True)
            p.write_text("time_utc,open,high,low,close\n2026-01-01T01:00:00Z,1,2,0,1\n", encoding="utf-8")
            b = valid_binding(td, req)
            b["fields"] = ["time_utc", "open", "high", "low", "close"]
            b["sha256"] = sha256_file(p)
            b["row_count"] = 1
            b["binding_sha256"] = canonical_json_sha256(b, exclude=("binding_sha256",))
            with self.assertRaises(EvidenceError):
                verify_dataset_binding(b, req, protected_start_utc=PROTECTED, root=td)

    def test_07_current_snapshot_cannot_be_verified_historical_cost(self):
        b = conservative_cost()
        b["state"] = VERIFIED
        b["components"]["spread"] = {
            "applicable": True, "state": VERIFIED, "historical": True,
            "evidence_kind": "CURRENT_SNAPSHOT", "evidence_sha256": "3" * 64,
            "effective_interval": "fixture",
        }
        for key in ("slippage", "currency_conversion"):
            b["components"][key] = {
                "applicable": True, "state": VERIFIED, "historical": True,
                "evidence_kind": "HISTORICAL_SERIES", "evidence_sha256": "7" * 64,
                "effective_interval": "fixture",
            }
        b["binding_sha256"] = canonical_json_sha256(b, exclude=("binding_sha256",))
        with self.assertRaises(EvidenceError):
            verify_cost_binding(b, candidate_id="V2-C900", spec_hash="a" * 64)

    def test_08_prospectively_frozen_adverse_conservative_bound_verifies(self):
        b = conservative_cost()
        self.assertEqual(verify_cost_binding(b, candidate_id="V2-C900", spec_hash="a" * 64)["state"], CONSERVATIVE_BOUND)

    def test_09_positive_financing_credit_requires_historically_verified_financing(self):
        b = conservative_cost()
        b["positive_financing_benefit_allowed"] = True
        b["components"]["financing"] = {
            "applicable": True, "state": CONSERVATIVE_BOUND, "prospectively_frozen": True,
            "bound_direction": "ADVERSE_OR_EQUAL", "basis_sha256": "8" * 64, "bound": 0.0,
        }
        b["binding_sha256"] = canonical_json_sha256(b, exclude=("binding_sha256",))
        with self.assertRaises(EvidenceError):
            verify_cost_binding(b, candidate_id="V2-C900", spec_hash="a" * 64)

    def test_10_generic_materializer_copies_exact_bytes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.csv"
            source.write_text(
                "time_utc,open,high,low,close,tick_volume\n"
                "2026-01-01T01:00:00Z,1,2,0,1,10\n"
                "2026-01-01T02:00:00Z,2,3,1,2,10\n", encoding="utf-8")
            req = fixture_requirements()
            spec = expected_dataset_specs(req)[0]
            meta = {
                "dataset_id": spec["dataset_id"], "candidate_id": "V2-C900", "spec_hash": "a" * 64,
                "instrument": "TEST", "resolution": "H1", "interval": copy.deepcopy(req["requirements"]["V2-C900"]["interval"]),
                "timezone": "UTC", "causal_availability": CAUSAL_BAR_RULE, "missing_data_rule": MISSING_DATA_RULE,
                "source": {"broker": "Pepperstone", "environment": "Pepperstone - Europe LIVE",
                           "acquisition_method": "fixture export", "provenance_sha256": "1" * 64},
                "completeness": {"state": "COMPLETE", "interval": copy.deepcopy(req["requirements"]["V2-C900"]["interval"]),
                                 "method": "fixture complete"},
                "broker_mapping": {"canonical_instrument": "TEST", "broker_symbol": "TEST.broker",
                                   "enabled": True, "evidence_sha256": "2" * 64},
                "semantic_evidence": {"session": "fixture", "synchronization": "fixture", "currency_conversion": "fixture",
                                      "contract_roll": "fixture", "corporate_actions": "fixture"},
            }
            b = materialize_exact_csv(source, "data/materialized/test.csv", meta, req,
                                      protected_start_utc=PROTECTED, root=td)
            self.assertEqual(b["sha256"], sha256_file(source))
            with self.assertRaises(EvidenceError):
                materialize_exact_csv(source, "data/materialized/test.csv", meta, req,
                                      protected_start_utc=PROTECTED, root=td)

    def test_11_multi_instrument_gate_blocks_without_every_required_dataset(self):
        with tempfile.TemporaryDirectory() as td:
            req = fixture_requirements(["A", "B"])
            write_csv(td, "data/materialized/a.csv")
            a = valid_binding(td, req, "A", "data/materialized/a.csv")
            g = gate_candidate_pre_outcome(candidate_id="V2-C900", spec_hash="a" * 64, requirements=req,
                                           dataset_bindings=[a], cost_binding=None, protected_start_utc=PROTECTED, root=td)
            self.assertFalse(g["ready"])
            self.assertEqual(g["state"], "DATA_BLOCKED")
            self.assertEqual(g["missing_instruments"], ["B"])

    def test_12_unresolved_cost_blocks_without_creating_economic_result(self):
        with tempfile.TemporaryDirectory() as td:
            req = fixture_requirements()
            write_csv(td)
            b = valid_binding(td, req)
            c = conservative_cost(UNRESOLVED)
            g = gate_candidate_pre_outcome(candidate_id="V2-C900", spec_hash="a" * 64, requirements=req,
                                           dataset_bindings=[b], cost_binding=c, protected_start_utc=PROTECTED, root=td)
            self.assertFalse(g["ready"])
            self.assertEqual(g["state"], "COST_UNRESOLVED")

    def test_13_complete_data_plus_resolved_cost_can_reach_pre_outcome_ready_only(self):
        with tempfile.TemporaryDirectory() as td:
            req = fixture_requirements()
            write_csv(td)
            b = valid_binding(td, req)
            g = gate_candidate_pre_outcome(candidate_id="V2-C900", spec_hash="a" * 64, requirements=req,
                                           dataset_bindings=[b], cost_binding=conservative_cost(),
                                           protected_start_utc=PROTECTED, root=td)
            self.assertTrue(g["ready"])
            self.assertEqual(g["state"], "PRE_OUTCOME_EVIDENCE_READY")
            self.assertNotIn("result", g)

    def test_14_live_authorities_remain_zero_attempts_results_and_protected_closed(self):
        state = load("CURRENT_STATE.json")
        completion = load("discovery/PRIMARY_WAVE_02_PRE_OUTCOME_COMPLETION_V1.json")
        req = load("data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V2.json")
        self.assertEqual(state["v2_attempts_used"], 0)
        self.assertEqual(state["v2_evaluated_identities"], 0)
        self.assertEqual(state["economic_outcomes_opened"], 0)
        self.assertFalse(state["protected_evidence_opened"])
        self.assertEqual(completion["result_recorded_count"], 0)
        self.assertEqual(req["candidate_spec_hashes"], completion["active_candidate_hashes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
