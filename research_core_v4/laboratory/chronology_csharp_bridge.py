"""Read an IMMUTABLE existing native Pepperstone ciphertext using existing MXM custody.
Produces only the bounded authenticated historical BID/ASK stream, never fills.
Invoked only in protected GitHub custody environment; never accepts arbitrary inputs."""
import base64,json,sys,tempfile
from pathlib import Path
from . import chronology_reception as native
from .common import need,encoded,bytes_digest
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
from research_core_v4.successor_c_20261018.readback import FP

SOURCE_RUN=39660692230
CIPHER_SHA256='f1d828d94b304e2af1f310701f92dcb31db935a8db7fc3f8772087adf5499346'
PRIVATE_SHA256='73b854b9d621c965f46c93e22e88c60cb9512c9f07d2ff51fa5df5eae478ba20'
SOURCE_SHA='d2fae5641b759b1c8c24161d83d62d39e104eafd'
TRIGGER_SHA='36ffe2999aae332b2d408c9d12d32bfabfa70802'
def export(cipher_path,output):
    cipher=Path(cipher_path).read_bytes()
    need(bytes_digest(cipher)==CIPHER_SHA256,'CSHARP_AUTHENTIC_CIPHER_CHANGED')
    with tempfile.TemporaryDirectory() as scratch:
        temp=Path(scratch)
        key,fp=_private_key_from_secret(temp)
        need(fp==FP,'CSHARP_COLD_RECIPIENT')
        raw=unpack(owner.bounded_decrypt(cipher,key,temp))
        need(bytes_digest(raw)==PRIVATE_SHA256,'CSHARP_COLD_PRIVATE_CHANGED')
        private=strict_json(raw,max_elements=8_000_000)
        identity=private['identity']
        need(identity['run_id']==SOURCE_RUN and identity['source_sha']==SOURCE_SHA and
             identity['trigger_sha']==TRIGGER_SHA and identity['attempt']==1,
             'CSHARP_AUTHENTIC_SOURCE_RUN_BINDING')
        evidence=native.replay(private) # Same authenticated wire, pagination, source-policy and account-fingerprint checks.
        need(evidence['provider_window_complete'] and evidence['bid_events']==14003 and
             evidence['ask_events']==14209 and evidence['chronological_events_processed']==28212 and
             evidence['same_ms_cross_side_order_unknown']==11414 and
             evidence['crossed_causal_snapshots']==0,'CSHARP_COLD_REPLAY_DRIFT')
        bid,bc,_=native.verify_tree(private['trees']['BID'],private['receipts'],private['account'],1)
        ask,ac,_=native.verify_tree(private['trees']['ASK'],private['receipts'],private['account'],2)
        need(bc and ac and len(bid)+len(ask)==28212,'CSHARP_EVENT_REDECODE')
        # Reuse the ORIGINAL SymbolById response already authenticated by
        # native.replay above. No new broker request and no fee backdating.
        from .captured_symbol_terms import captured_symbol_terms
        request,response=native.decode_record(private['receipts'][1],private['account'])
        need(type(request).__name__=='ProtoOASymbolByIdReq' and list(request.symbolId)==[1] and
             type(response).__name__=='ProtoOASymbolByIdRes' and len(response.symbol)==1,
             'CSHARP_ORIGINAL_SYMBOL_TERMS_BINDING')
        terms=captured_symbol_terms(response.symbol[0])
        terms.update(source_crypto_authenticated_by_original_native_replay=True,
          source_run=SOURCE_RUN,native_source_sha=SOURCE_SHA,source_ciphertext_sha256=CIPHER_SHA256,
          source_private_sha256=PRIVATE_SHA256,
          original_metadata_response_wire_sha256=bytes_digest(base64.b64decode(
              private['receipts'][1]['response_envelope_b64'],validate=True)),
          classification='AUTHENTICATED_CAPTURE_SNAPSHOT_NOT_DATED_HISTORICAL_EXECUTION_TERMS')
        terms_bytes=encoded(terms)
        # Same-ms order across sides is unknowable. Group atomically downstream;
        # this deterministic serializer order is NOT a broker event precedence.
        i=j=0;out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('wb') as f:
            while i<len(bid) or j<len(ask):
                t=min(bid[i][0] if i<len(bid) else 2**63,
                      ask[j][0] if j<len(ask) else 2**63)
                while i<len(bid) and bid[i][0]==t:
                    f.write(encoded({'t':bid[i][0],'side':'bid','raw':bid[i][1]})+b'\n');i+=1
                while j<len(ask) and ask[j][0]==t:
                    f.write(encoded({'t':ask[j][0],'side':'ask','raw':ask[j][1]})+b'\n');j+=1
        Path(str(out)+'.symbol-terms.json').write_bytes(terms_bytes)
        receipt={'schema':'mxm.csharp.authenticated-nonoutcome-bridge.v1',
                'source_run':SOURCE_RUN,'native_source_sha':SOURCE_SHA,
                'ciphertext_sha256':CIPHER_SHA256,'private_sha256':PRIVATE_SHA256,
                'derived_ticks_sha256':bytes_digest(out.read_bytes()),
                'verified_bid_events':len(bid),'verified_ask_events':len(ask),
                'captured_symbol_terms_sha256':bytes_digest(terms_bytes),
                'historical_arrival_proven':False,'historical_costs_proven':False,
                'orders':0,'economic_outcomes':0,'fills':0}
        Path(str(out)+'.receipt.json').write_bytes(encoded(receipt))
        return receipt
if __name__=='__main__':
    need(len(sys.argv)==3,'CSHARP_EXPORT_ARGUMENTS')
    print('MXM_CSHARP_AUTHENTIC_READONLY '+json.dumps(export(sys.argv[1],sys.argv[2]),sort_keys=True),flush=True)
