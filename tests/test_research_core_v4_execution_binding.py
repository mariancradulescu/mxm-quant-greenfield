from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_core_v4 import development_execution_runner_v1 as runner
from research_core_v4 import exact_geometry_calibration_v2 as cal
from research_core_v4 import response_evaluator_v3 as ev
from research_core_v4 import response_evaluator_v2 as legacy_ev
from research_core_v4.frozen_v2_semantics import paired_arm_hierarchical_mean, select_leaf_index


def base_authority():
    return {
        "schema":"mxm.research-core-v4.first-development-response-execution-authority.v3",
        "status":"AUTHORIZED_READY_NOT_EXECUTED",
        "scientific_design":"research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json",
        "real_development_response_execution_authorized":True,
        "confirmation_response_execution_authorized":False,
        "broker_acquisition_authorized":False,
        "quote_revision_v2_execution_authorized":False,
        "protected_forward_opened":False,
        "live_trading_authorized":False,
        "candidate_promotion_authorized":False,
        "development_scope":{
            "contexts":["FX_SPOT","SPOT_CRYPTO","US_EQUITY_EXTENDED_HOURS"],
            "volatility_states":["LOW","HIGH"],
            "response_horizons_m5":[3,6,12,48],
            "permutations":1023,
            "seed":20261002,
        },
    }


class ExecutionBindingTests(unittest.TestCase):
    def setUp(self):
        runner.RESPONSE_OPENING_STARTED=False

    def test_tampered_input_file_rejected_before_response_read(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"9_M5.csv"
            p.write_text("time_utc,close\n2025-09-16T00:00:00Z,1.0\n",encoding="utf-8")
            item={
                "symbol":"EURGBP","symbol_id":9,"row_count":1,
                "series_sha256":"0"*64,
                "first_timestamp_utc":"2025-09-16T00:00:00Z",
                "last_timestamp_utc":"2025-09-16T00:00:00Z",
            }
            with self.assertRaises(PermissionError):
                runner.verify_series_file(p,item)
            self.assertFalse(runner.RESPONSE_OPENING_STARTED)

    def test_wrong_bound_file_hash_rejected_before_response_read(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"design.json";p.write_text("{}\n",encoding="utf-8")
            with self.assertRaises(PermissionError):
                runner.verify_bound_file("design_sha256",p,"f"*64)
            self.assertFalse(runner.RESPONSE_OPENING_STARTED)

    def test_wrong_skeleton_hash_rejected_before_response_read(self):
        e=ev.SignalEvent(
            "FX_SPOT","X",1,ev.parse_utc("2026-01-01T00:00:00Z"),1,"LOW","FULL",
            100.0,.01,"2026-W01",(True,False,False,False),0,"Thursday","ASIA_UTC",None
        )
        with self.assertRaises(PermissionError):
            runner.verify_rebuilt_skeleton([e],"0"*64,1)
        self.assertFalse(runner.RESPONSE_OPENING_STARTED)

    def test_public_real_response_paths_cannot_bypass_runner(self):
        a=base_authority()
        with self.assertRaises(PermissionError):
            ev.evaluate_real_development(authority=a,events=(),bars_by_symbol={})
        with self.assertRaises(PermissionError):
            ev.evaluate_prevalidated_development(authority=a,design={},events=(),bars_by_symbol={},source_hashes={})
        with self.assertRaises(PermissionError):
            ev._evaluate_prevalidated_development_core(authority=a,design={},events=(),bars_by_symbol={},source_hashes={})
        with self.assertRaises(PermissionError):
            ev._runner_execution_capability()

    def test_internal_capability_object_cannot_bypass_runner_caller_check(self):
        a=base_authority()
        with self.assertRaises(PermissionError):
            ev._evaluate_prevalidated_development_core(
                authority=a,design={},events=(),bars_by_symbol={},source_hashes={},
                _execution_capability=ev._EXECUTION_CAPABILITY,
            )

    def test_legacy_v2_complete_real_response_paths_are_disabled(self):
        a=base_authority()
        with self.assertRaises(PermissionError):
            legacy_ev.require_real_response_authority(a)
        with self.assertRaises(PermissionError):
            legacy_ev.evaluate_real_development(authority=a,events=(),bars_by_symbol={})
        with self.assertRaises(PermissionError):
            legacy_ev.evaluate_development_from_directory(authority=a,design={},raw_root='.')

    def test_wrong_seed_rejected(self):
        a=base_authority();a["development_scope"]["seed"]=1
        with self.assertRaises(PermissionError):ev.require_real_response_authority(a)

    def test_wrong_permutation_count_rejected(self):
        a=base_authority();a["development_scope"]["permutations"]=127
        with self.assertRaises(PermissionError):ev.require_real_response_authority(a)

    def test_wrong_context_scope_rejected(self):
        a=base_authority();a["development_scope"]["contexts"]=["FX_SPOT"]
        with self.assertRaises(PermissionError):ev.require_real_response_authority(a)

    def test_wrong_horizon_scope_rejected(self):
        a=base_authority();a["development_scope"]["response_horizons_m5"]=[3,6,12]
        with self.assertRaises(PermissionError):ev.require_real_response_authority(a)

    def test_protected_forward_true_rejected(self):
        a=base_authority();a["protected_forward_opened"]=True
        with self.assertRaises(PermissionError):ev.require_real_response_authority(a)

    def test_confirmation_authorized_true_rejected(self):
        a=base_authority();a["confirmation_response_execution_authorized"]=True
        with self.assertRaises(PermissionError):ev.require_real_response_authority(a)

    def test_broker_acquisition_true_rejected(self):
        a=base_authority();a["broker_acquisition_authorized"]=True
        with self.assertRaises(PermissionError):ev.require_real_response_authority(a)

    def test_exact_selected_leaf_tiebreak(self):
        idx=select_leaf_index(
            [.01,.01,.01,.01],
            [2.0,2.0,2.0,1.5],
            [("LOW",48),("HIGH",3),("LOW",3),("LOW",6)],
        )
        self.assertEqual(idx,2)

    def test_production_calibration_tiebreak_parity(self):
        self.assertIs(ev.select_leaf_index,cal.select_leaf_index)

    def test_production_calibration_full_arm_gate_parity(self):
        self.assertIs(ev.paired_arm_hierarchical_mean,cal.paired_arm_hierarchical_mean)
        units=[
            ev.PairedUnit("C","A","2026-W01",1,"LOW",3,2.0,0.0),
            ev.PairedUnit("C","A","2026-W01",-1,"LOW",3,4.0,0.0),
            ev.PairedUnit("C","B","2026-W01",1,"LOW",3,6.0,0.0),
            ev.PairedUnit("C","B","2026-W01",-1,"LOW",3,8.0,0.0),
        ]
        self.assertAlmostEqual(paired_arm_hierarchical_mean(units,"FULL",2),5.0)


    def test_live_authority_v3_bindings_match_production_support_v2_preoutcome(self):
        # Recovery must not relax the original READY gate. Validate Authority V3
        # against the immutable pre-interruption state snapshot using the unchanged runner.
        authority=runner.load_json(runner.ROOT/runner.AUTHORITY_REL)
        historical=runner.load_json(runner.ROOT/"research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_PREINTERRUPTION_STATE_V1.json")
        design=runner.load_json(runner.ROOT/runner.DESIGN_REL)
        manifest=runner.load_json(runner.ROOT/runner.MANIFEST_REL)
        support=runner.load_json(runner.ROOT/runner.SUPPORT_REL)
        runner.verify_static_bindings(authority,historical,design,manifest,support)
        self.assertEqual(authority["status"],"AUTHORIZED_READY_NOT_EXECUTED")
        self.assertTrue(authority["real_development_response_execution_authorized"])
        self.assertTrue(historical["first_wave"]["evaluator_execution_authorized"])
        self.assertEqual(authority["bindings"]["support_skeleton_row_count"],118262)
        self.assertEqual(authority["bindings"]["support_skeleton_sha256"],"e3f8de0012e2bcdd2005d72afef73f738de11fca404675689a8f00422ba0918b")
        self.assertFalse(runner.RESPONSE_OPENING_STARTED)
        self.assertFalse(historical["first_wave"]["development_outcomes_opened"])
        self.assertFalse(historical["first_wave"]["confirmation_outcomes_opened"])

        # Separately validate the current interrupted/recovery state without making
        # the frozen runner accept it as a fresh READY state.
        from research_core_v4.crash_recovery_control_v1 import validate_current_control_plane
        report=validate_current_control_plane()
        self.assertEqual(report["status"],"PASS")
        self.assertEqual(report["allowed_attempts"],1)
        self.assertFalse(report["scientific_design_changed"])
        self.assertFalse(report["evaluator_changed"])
        self.assertFalse(report["runner_changed"])


    def test_exactly_one_current_development_authority_is_v3(self):
        state=runner.load_json(runner.ROOT/runner.STATE_REL)
        self.assertEqual(state["first_wave"]["development_response_execution_authority"],runner.AUTHORITY_REL)
        self.assertTrue(runner.AUTHORITY_REL.endswith("FIRST_V4_DEVELOPMENT_RESPONSE_EXECUTION_AUTHORITY_V3.json"))
        self.assertEqual(state["first_wave"]["execution_authority_v1_status"],"SUPERSEDED_BEFORE_ANY_REAL_V4_RESPONSE")
        self.assertEqual(state["first_wave"]["execution_authority_v2_status"],"SUPERSEDED_BEFORE_ANY_REAL_V4_RESPONSE")
        self.assertNotEqual(state["first_wave"]["execution_authority_v1"],runner.AUTHORITY_REL)
        self.assertNotEqual(state["first_wave"]["execution_authority_v2"],runner.AUTHORITY_REL)

    def test_result_provenance_hashes_present_and_atomic_write(self):
        prov={
            "authority_sha256":"a"*64,
            "canonical_state_binding_sha256":"b"*64,
            "canonical_design_sha256":"c"*64,
            "evaluator_sha256":"d"*64,
            "shared_semantics_sha256":"e"*64,
            "primary_manifest_sha256":"f"*64,
            "support_audit_sha256":"1"*64,
            "rebuilt_support_skeleton_sha256":"2"*64,
            "rebuilt_support_skeleton_row_count":95506,
            "source_series_sha256":{"X":"3"*64},
            "context_support_counts":{},
            "seed":20261002,
            "permutations":1023,
        }
        b=runner.PrevalidatedBundle(
            base_authority(),{"status":"SYNTHETIC_AUTHORIZED_NOT_EXECUTED"}, {}, {}, {}, tuple(), {}, {"X":"3"*64}, prov
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            ev,"_evaluate_prevalidated_development_core",
            return_value={"schema":"synthetic-known-answer","contexts":[]}
        ):
            p=Path(td)/"result.json"
            digest=runner.execute_once(b,p)
            out=json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(out["execution_provenance"],prov)
            self.assertIn("raw_result_sha256_without_self_field",out)
            self.assertEqual(len(digest),64)
            self.assertTrue(runner.RESPONSE_OPENING_STARTED)
            self.assertTrue(p.with_suffix(p.suffix+".opening.lock").exists())


if __name__=="__main__":
    unittest.main()
