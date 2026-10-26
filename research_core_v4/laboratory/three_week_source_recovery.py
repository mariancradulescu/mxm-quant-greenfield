"""Exact existing EURUSD originals, decoded only inside existing native custody."""
import importlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from .common import need,encoded,bytes_digest
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'
FOLDERS={
 'W35':'docs/economic-development/20261023/native-week35-39946364621',
 'W36':'docs/economic-development/20261026/native-week36-40276181331',
 'W37':'docs/economic-development/20261023/native-week-39917922508'}
RUNS={'W35':39946364621,'W36':40276181331,'W37':39917922508}
ROWS={'W35':683022,'W36':761196,'W37':685474}
SIDE_COUNTS={'W35':(341578,341444),'W36':(381116,380080),'W37':(342248,343226)}
def validate_counts(profile,manifest,native_result):
    bid,ask=SIDE_COUNTS[profile]
    need(manifest['quote_events']==bid+ask==ROWS[profile],'THREE_WEEK_PUBLIC_ROW_COUNT')
    need(manifest.get('bid_events',bid)==bid and manifest.get('ask_events',ask)==ask,'THREE_WEEK_OPTIONAL_MANIFEST_SIDE_COUNT')
    need(native_result['bid_events']==bid and native_result['ask_events']==ask,'THREE_WEEK_AUTHENTIC_SIDE_COUNTS')
    return True
def export(profile,cipher_path,output):
    need(profile in FOLDERS,'THREE_WEEK_REGISTERED_SOURCE')
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and
         subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'THREE_WEEK_NATIVE_CHECKOUT')
    for name in ('three_week_source_recovery.py','week_chronology_reception.py'):
        need((Path('research_core_v4/laboratory')/name).read_bytes()==(Path('../research_core_v4/laboratory')/name).read_bytes(),'THREE_WEEK_EXACT_EXTENSION')
    main=Path('..');m=json.loads((main/FOLDERS[profile]/'MANIFEST.json').read_bytes())
    need(m['source_run_id']==RUNS[profile] and m['quote_events']==ROWS[profile],'THREE_WEEK_MANIFEST_SCOPE')
    cipher=Path(cipher_path).read_bytes()
    need(bytes_digest(cipher)==m['members']['capture.mxmenc']['sha256'],'THREE_WEEK_ORIGINAL_CIPHER')
    os.environ['LAB_CHRONOLOGY_PROFILE']=profile
    from . import week_chronology_reception as native
    importlib.reload(native)
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    with tempfile.TemporaryDirectory() as tmp:
        key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'THREE_WEEK_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)))
        need(len(raw)<=120000000 and bytes_digest(raw)==m['private_sha256'],'THREE_WEEK_PRIVATE_IDENTITY')
        p=strict_json(raw,max_elements=8000000);i=p['identity']
        need(i['run_id']==RUNS[profile] and i['source_sha']==m['code_source'] and
             i['trigger_sha']==m['source_head'] and i['native_decoder_source_sha']==NATIVE and
             i['engine_source_sha']=='dbd0a42bf73f9ae5847a90a4ed159d21e0d7197a' and i['attempt']==1,'THREE_WEEK_ORIGINAL_PROVENANCE')
        r=native.replay(p)
        need(r['provider_window_complete'] and r['chronological_events_processed']==ROWS[profile] and
             validate_counts(profile,m,r),'THREE_WEEK_NATIVE_REDECODE')
        bid,bc,_=native.verify_tree(p['trees']['BID'],p['receipts'],p['account'],1)
        ask,ac,_=native.verify_tree(p['trees']['ASK'],p['receipts'],p['account'],2)
        need(bc and ac,'THREE_WEEK_COMPLETE_TREES');a=b=0;out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('wb') as stream:
            while a<len(bid) or b<len(ask):
                t=min(bid[a][0] if a<len(bid) else 2**63,ask[b][0] if b<len(ask) else 2**63)
                while a<len(bid) and bid[a][0]==t:stream.write(encoded({'t':t,'side':'bid','raw':bid[a][1]})+b'\n');a+=1
                while b<len(ask) and ask[b][0]==t:stream.write(encoded({'t':t,'side':'ask','raw':ask[b][1]})+b'\n');b+=1
        receipt={'profile':profile,'run':RUNS[profile],'source_code':m['code_source'],'source_trigger':m['source_head'],
          'cipher_sha256':bytes_digest(cipher),'private_sha256':bytes_digest(raw),'rows':ROWS[profile],
          'derived_sha256':bytes_digest(out.read_bytes()),'first_ms':native.POLICY['from_ms'],'end_ms':native.POLICY['to_ms'],
          'orders':0,'new_broker_requests':0,'historical_costs_proven':False}
        Path(str(out)+'.receipt.json').write_bytes(encoded(receipt))
if __name__=='__main__':
    need(len(sys.argv)==4,'THREE_WEEK_EXPORT_ARGUMENTS');export(*sys.argv[1:])
