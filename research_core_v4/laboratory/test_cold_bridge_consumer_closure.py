from pathlib import Path
import unittest
from .cold_bridge_consumer_closure import contract


class ColdBridgeClosureTest(unittest.TestCase):
    def setUp(self):
        self.original={'common','chronology_reception'}
        self.text=Path('.github/workflows/mxm-csharp-exit-lifecycle-cold.yml').read_text()

    def test_current_both_consumers_have_complete_contract(self):
        for name in ('mxm-csharp-exit-lifecycle-cold.yml','mxm-csharp-authentic-cold.yml'):
            result=contract(Path('.github/workflows',name).read_text(),Path.cwd(),self.original)
            self.assertEqual(len(result),2)

    def test_actual_missing_dependency_failure_is_detected_before_keys(self):
        line='          cp research_core_v4/laboratory/captured_symbol_terms.py .sealed-chronology-source/research_core_v4/laboratory/captured_symbol_terms.py\n'
        with self.assertRaisesRegex(ValueError,'MISSING_BRIDGE_DEPENDENCY_captured_symbol_terms'):
            contract(self.text.replace(line,''),Path.cwd(),self.original)

    def test_missing_dependency_trigger_cannot_leave_broken_consumer_dormant(self):
        with self.assertRaisesRegex(ValueError,'MISSING_BRIDGE_PUSH_TRIGGER_captured_symbol_terms'):
            contract(self.text.replace('      - research_core_v4/laboratory/captured_symbol_terms.py\n',''),
                     Path.cwd(),self.original)

    def test_no_expiring_source_fallback(self):
        with self.assertRaisesRegex(ValueError,'MISSING_DURABLE_SOURCE_RESTORE'):
            contract(self.text.replace('durable_native_chronology --out','missing_restore --out'),
                     Path.cwd(),self.original)


if __name__=='__main__':unittest.main()
