import unittest
from unittest.mock import patch
from .common import LabError
from .protocol import economic_gate

class ResearchReceptionHoldTests(unittest.TestCase):
    def test_operational_acceptance_alone_cannot_release_research(self):
        with patch('research_core_v4.laboratory.operational_acceptance.verify_operational_acceptance',return_value=True) as verify:
            with self.assertRaisesRegex(LabError,'RESEARCH_CAPABILITY_NATIVE_RECEPTION_NOT_IMPLEMENTED'):
                economic_gate({'fixture':'operational-only'},'a'*40,{},route=object())
            verify.assert_called_once()
