import json, pathlib, unittest
from research_v3.session_gap_structural_screen_v1 import CANONICAL_ZIP_SHA256, VERSION

class StructuralExtensionWave01FreezeTests(unittest.TestCase):
    def test_capture_acceptance_preserves_scope_and_accounting(self):
        d=json.loads(pathlib.Path("evidence/C031_STRUCTURAL_EXTENSION_WAVE_01_CAPTURE_ACCEPTANCE_V1.json").read_text())
        self.assertEqual(d["status"],"ACCEPTED_AFTER_DETERMINISTIC_EXACT_DUPLICATE_CANONICALIZATION")
        self.assertEqual(d["canonical_capture"]["sha256"],CANONICAL_ZIP_SHA256)
        self.assertEqual(d["canonical_capture"]["symbol_count"],12)
        self.assertTrue(d["scope_law"]["broker_native_universe_remains_open"])
        self.assertFalse(d["scope_law"]["mechanism_family_closed"])
        self.assertEqual(d["duplicate_diagnosis"]["conflicting_duplicate_timestamp_groups"],0)
        self.assertEqual(d["accounting_effect"]["economic_outcomes_opened"],0)
        self.assertEqual(d["accounting_effect"]["v2_attempts_consumed"],0)

    def test_screen_is_frozen_non_economic_before_outcome(self):
        d=json.loads(pathlib.Path("research_v3/SESSION_GAP_STRUCTURAL_EXTENSION_WAVE_01_FREEZE_V1.json").read_text())
        self.assertEqual(d["status"],"FROZEN_PENDING_EXACT_HEAD_GREEN")
        self.assertEqual(d["implementation"]["version"],VERSION)
        self.assertFalse(d["structural_only_semantics"]["cost_hurdle_applied"])
        self.assertFalse(d["structural_only_semantics"]["notional_pnl_computed"])
        self.assertFalse(d["structural_only_semantics"]["economic_candidate_identity_created"])
        self.assertEqual(d["accounting_effect"]["economic_outcomes_opened"],0)
        self.assertEqual(d["accounting_effect"]["v2_attempts_consumed"],0)

if __name__=="__main__": unittest.main()
