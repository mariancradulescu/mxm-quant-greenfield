"""No-key contract and mutation tests for the new protected week bridge."""
import copy
import unittest
from unittest.mock import patch
from . import week_chronology_csharp_bridge as bridge

IDENTITY = {
 'run_id': bridge.RUN,
 'source_sha': bridge.SOURCE,
 'trigger_sha': bridge.TRIGGER,
 'native_decoder_source_sha': bridge.NATIVE,
 'engine_source_sha': bridge.ENGINE,
 'attempt': 1,
}
WIRE = {
 'provider_window_complete': True,
 'bid_events': 342248,
 'ask_events': 343226,
 'chronological_events_processed': 685474,
 'same_ms_cross_side_order_unknown': 277457,
 'crossed_causal_snapshots': 0,
 'requested_complete_iso_utc_weeks': 1,
 'orders': 0,
 'economic_outcomes': 0,
 'historical_arrival_times_proven': False,
 'dated_costs_proven': False,
}
def record():
    return {'schema':'mxm.week-native-chronology-private.v1',
            'identity':copy.deepcopy(IDENTITY)}

class WeekBridgeTests(unittest.TestCase):
    def test_identity_and_exact_source_are_pinned(self):
        with patch.object(bridge.native, 'replay', return_value=WIRE):
            self.assertEqual(bridge.validate_private(record()),WIRE)
    def test_mutated_identity_never_reaches_replay(self):
        for field, invalid in [('run_id',0),('source_sha','0'*40),
                               ('trigger_sha','0'*40),('attempt',2),
                               ('native_decoder_source_sha','0'*40),
                               ('engine_source_sha','0'*40)]:
            with self.subTest(field=field):
                r=record();r['identity'][field]=invalid
                with patch.object(bridge.native,'replay',side_effect=AssertionError('SHOULD_NOT_REPLAY')):
                    with self.assertRaisesRegex(ValueError,'WEEK_CSHARP_PRIVATE_IDENTITY'):
                        bridge.validate_private(r)
    def test_no_claim_for_cross_side_precedence_or_execution(self):
        for field,value in [('same_ms_cross_side_order_unknown',0),('orders',1),
                            ('dated_costs_proven',True),('provider_window_complete',False),
                            ('historical_arrival_times_proven',True)]:
            with self.subTest(field=field):
                wrong=dict(WIRE);wrong[field]=value
                with patch.object(bridge.native,'replay',return_value=wrong):
                    with self.assertRaisesRegex(ValueError,'WEEK_CSHARP_UNCERTIFIED_WIRE_RESULT'):
                        bridge.validate_private(record())
    def test_foreign_cipher_refused_before_decryption(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            cipher=Path(t)/'wrong.mxmenc';cipher.write_bytes(b'not the week')
            with patch.object(bridge,'_private_key_from_secret',side_effect=AssertionError('KEY_ACCESSED')):
                with self.assertRaisesRegex(ValueError,'WEEK_CSHARP_EXACT_CIPHER'):
                    bridge.export(cipher,Path(t)/'out')

if __name__=='__main__':
    unittest.main()
