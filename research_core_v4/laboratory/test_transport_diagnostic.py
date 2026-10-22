import os,unittest
from unittest.mock import patch
from .common import LabError
from . import transport_diagnostic as diagnostic,custody,recovery_v3

class TransportDiagnosticTests(unittest.TestCase):
    def test_only_fixed_new_diagnostic_paths(self):
        self.assertEqual(diagnostic.probe_path(1,'A'),'typed-successor/transport-diagnostics/1/A.json')
        for run,writer in ((0,'A'),(True,'A'),(1,'../program-state'),(1,'A/../../program-state')):
            with self.assertRaises(LabError):diagnostic.probe_path(run,writer)
    def test_replies_redact_raw_and_encoded_authority(self):
        self.assertEqual(diagnostic.redact_reply(b'raw-token auth native-token',('raw-token','auth','native-token')),
            '[REDACTED] [REDACTED] [REDACTED]')
    def test_no_scope_or_schedule_can_reach_transport(self):
        with patch.object(custody,'_NATIVE_WRITER_SCOPE',None),patch.dict(os.environ,{},clear=True):
            with self.assertRaises(LabError):diagnostic.observe_transport(object())
        wf=recovery_v3.build_workflow('a'*40)
        self.assertIs(wf['on']['workflow_dispatch']['inputs']['cas_transport_probe']['default'],False)
        self.assertIn("github.event_name == 'workflow_dispatch'",wf['jobs']['ordinary-recovery']['steps'][-1]['env']['LAB_CAS_TRANSPORT_DIAGNOSTIC'])

if __name__=='__main__':unittest.main()
