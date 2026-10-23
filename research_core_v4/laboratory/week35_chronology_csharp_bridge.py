"""Bridge the EXACT stored Pepperstone ISO 2026-W35 wire to the existing C# portfolio.

Only the existing protected custody job may decrypt. Quote-side order within a
millisecond is unknown; this bridge preserves timestamp/side observations, not
historical fills. No broker requests, strategy selection, or authority writes.
"""
import base64
import json
import sys
import tempfile
from pathlib import Path

from . import week_chronology_reception as native
from .common import bytes_digest, encoded, need
from .captured_symbol_terms import captured_symbol_terms
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json, unpack
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
from research_core_v4.successor_c_20261018.readback import FP

RUN = 39946364621
SOURCE = 'b54ee59548846ad8013b25965dbe4bcb19d4a978'
TRIGGER = '0dae3ca9dab65f51433969ccee4259ecb0f31d90'
NATIVE = 'd2fae5641b759b1c8c24161d83d62d39e104eafd'
ENGINE = 'dbd0a42bf73f9ae5847a90a4ed159d21e0d7197a'
CIPHER = '0d1badd1a944eeac7a67f1f7c87e05d26c1ea14ea016a0ea25fbb40ce7cb92ee'
PRIVATE = '2b37063a948d7b761a7f854e59649793ba1d5ff5e30a7e5255b03f4042cadb13'
START = 1787529600000
END = 1788134400000

def validate_private(private):
    need(native.PROFILE=='W35','W35_CSHARP_EXPLICIT_PROFILE')
    i = private['identity']
    need(private['schema'] == 'mxm.week-native-chronology-private.v1' and
         i['run_id'] == RUN and i['source_sha'] == SOURCE and
         i['trigger_sha'] == TRIGGER and i['native_decoder_source_sha'] == NATIVE and
         i['engine_source_sha'] == ENGINE and i['attempt'] == 1,
         'WEEK_CSHARP_PRIVATE_IDENTITY')
    result = native.replay(private)
    need(result['provider_window_complete'] is True and
         result['bid_events'] == 341578 and result['ask_events'] == 341444 and
         result['chronological_events_processed'] == 683022 and
         result['same_ms_cross_side_order_unknown'] == 303438 and
         result['crossed_causal_snapshots'] == 0 and
         result['requested_complete_iso_utc_weeks'] == 1 and
         result['orders'] == result['economic_outcomes'] == 0 and
         result['historical_arrival_times_proven'] is False and
         result['dated_costs_proven'] is False,
         'WEEK_CSHARP_UNCERTIFIED_WIRE_RESULT')
    return result

def export(cipher_path, output):
    ciphertext = Path(cipher_path).read_bytes()
    need(bytes_digest(ciphertext) == CIPHER, 'WEEK_CSHARP_EXACT_CIPHER')
    with tempfile.TemporaryDirectory() as scratch:
        key, fp = _private_key_from_secret(Path(scratch))
        need(fp == FP, 'WEEK_CSHARP_EXISTING_CUSTODY_RECIPIENT')
        raw = unpack(owner.bounded_decrypt(ciphertext, key, Path(scratch)))
        need(len(raw) <= 120_000_000 and bytes_digest(raw) == PRIVATE,
             'WEEK_CSHARP_EXACT_PRIVATE')
        private = strict_json(raw, max_elements=8_000_000)
        validate_private(private)
        bid, bc, _ = native.verify_tree(
            private['trees']['BID'], private['receipts'], private['account'], 1)
        ask, ac, _ = native.verify_tree(
            private['trees']['ASK'], private['receipts'], private['account'], 2)
        need(bc and ac and len(bid) == 341578 and len(ask) == 341444 and
             all(START <= t < END for t, _ in bid) and
             all(START <= t < END for t, _ in ask),
             'WEEK_CSHARP_EXACT_INTERVAL')
        request, response = native.decode_record(private['receipts'][1], private['account'])
        need(type(request).__name__ == 'ProtoOASymbolByIdReq' and
             list(request.symbolId) == [1] and
             type(response).__name__ == 'ProtoOASymbolByIdRes' and
             len(response.symbol) == 1,
             'WEEK_CSHARP_NATIVE_METADATA')
        terms = captured_symbol_terms(response.symbol[0])
        terms.update(
            classification='AUTHENTICATED_WEEK_CAPTURE_SNAPSHOT_NOT_DATED_HISTORICAL_EXECUTION_TERMS',
            source_crypto_authenticated_by_week_native_replay=True,
            source_run=RUN, source_code_sha=SOURCE,
            source_ciphertext_sha256=CIPHER, source_private_sha256=PRIVATE,
            historical_commission_proven=False, dated_historical_volume_rules_proven=False,
            original_metadata_response_wire_sha256=bytes_digest(base64.b64decode(
                private['receipts'][1]['response_envelope_b64'], validate=True))
        )
        terms_bytes = encoded(terms)
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        # A fixed serialization order within a millisecond is NOT proof that
        # the market arrived in that order. C# consumes atomic timestamp groups.
        with out.open('wb') as stream:
            i = j = 0
            while i < len(bid) or j < len(ask):
                stamp = min(bid[i][0] if i < len(bid) else 2**63,
                            ask[j][0] if j < len(ask) else 2**63)
                while i < len(bid) and bid[i][0] == stamp:
                    stream.write(encoded({'t': bid[i][0], 'side': 'bid', 'raw': bid[i][1]}) + b'\n')
                    i += 1
                while j < len(ask) and ask[j][0] == stamp:
                    stream.write(encoded({'t': ask[j][0], 'side': 'ask', 'raw': ask[j][1]}) + b'\n')
                    j += 1
        Path(str(out) + '.symbol-terms.json').write_bytes(terms_bytes)
        receipt = {
            'schema': 'mxm.csharp.authenticated-week-development-bridge.v1',
            'source_run': RUN, 'source_code_sha': SOURCE,
            'ciphertext_sha256': CIPHER, 'private_sha256': PRIVATE,
            'derived_ticks_sha256': bytes_digest(out.read_bytes()),
            'captured_symbol_terms_sha256': bytes_digest(terms_bytes),
            'iso_week': '2026-W35', 'first_inclusive_ms': START,
            'last_exclusive_ms': END,
            'verified_bid_events': len(bid), 'verified_ask_events': len(ask),
            'same_ms_cross_side_precedence_unknown': 303438,
            'complete_provider_pages': True, 'continuous_liquidity_proven': False,
            'historical_arrival_times_proven': False,
            'historical_costs_proven': False,
            'broker_fills_proven': False, 'hard21_proven': False,
            'partition': 'DEVELOPMENT', 'new_broker_requests': 0,
            'orders': 0, 'fills': 0, 'economic_outcomes': 0
        }
        Path(str(out) + '.receipt.json').write_bytes(encoded(receipt))
        return receipt

if __name__ == '__main__':
    need(len(sys.argv) == 3, 'WEEK_CSHARP_EXPORT_ARGUMENTS')
    print('MXM_CSHARP_WEEK_DEVELOPMENT_READONLY ' +
          json.dumps(export(sys.argv[1], sys.argv[2]), sort_keys=True), flush=True)
