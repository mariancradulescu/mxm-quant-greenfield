"""Offline restoration of exact new WEEK ciphertext/receipts; no decrypt or broker."""
import base64
import io
import json
import zipfile
from pathlib import Path
from .durable_native_chronology import decode_archive, digest, need

ROOT=Path('docs/economic-development/20261023/native-week35-39946364621')
ARCHIVE_SHA='c09a5bdd4c60b325d23383189a349463a0054fd89576b74724be909d03a51a9c'
CIPHER_SHA='0d1badd1a944eeac7a67f1f7c87e05d26c1ea14ea016a0ea25fbb40ce7cb92ee'
PRIVATE_SHA='2b37063a948d7b761a7f854e59649793ba1d5ff5e30a7e5255b03f4042cadb13'
COLD_ZIP_SHA='8400149e020c2cfc6e421147b7068fc4ec00a6c2fd5969675e92c7e68db49cbe'
COLD_SHA='bc8f7b586648d089cae1a601e25af96f6f0a6908df22372701d580bf98d09a57'
CODE='b54ee59548846ad8013b25965dbe4bcb19d4a978'
TRIGGER='0dae3ca9dab65f51433969ccee4259ecb0f31d90'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'


def restore_week35(root=ROOT,destination=Path('verification/week35-chronology')):
    root=Path(root)
    m,files=decode_archive(root,ARCHIVE_SHA,max_archive_bytes=8*1024*1024,max_parts=256,part_size=32768)
    need(m['source_run_id']==39946364621 and m['artifact_id']==12498866094 and
         m['artifact_name']=='week-chronology-39946364621' and
         m['source_head']==TRIGGER and m['code_source']==CODE and m['decoder_source']==NATIVE and
         m['partition']=='DEVELOPMENT' and m['iso_week']=='2026-W35' and
         m['quote_events']==683022 and m['cold_artifact_id']==12497888286 and
         m['native_producer_job_id']==120390356655 and m['native_cold_job_id']==120390881213 and
         m['private_sha256']==PRIVATE_SHA and m['new_broker_requests_on_restore']==m['orders']==m['strategy_trials']==0 and
         m['independent_confirmation'] is False,'WEEK_SOURCE_IDENTITY')
    need(digest(files['capture.mxmenc'])==CIPHER_SHA,'WEEK_PINNED_CIPHER')
    coldpath=root/'cold-artifact.zip.b64'
    need(not coldpath.is_symlink() and coldpath.stat().st_size<=8192,'WEEK_COLD_FILE')
    coldzip=base64.b64decode(coldpath.read_text().strip(),validate=True)
    need(digest(coldzip)==COLD_ZIP_SHA==m['cold_archive_sha256'],'WEEK_COLD_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(coldzip)) as z:
        need(z.namelist()==['cold.json'] and z.infolist()[0].file_size<=16384,'WEEK_COLD_MEMBERS')
        coldbytes=z.read('cold.json')
    need(digest(coldbytes)==COLD_SHA==m['cold_receipt_sha256'],'WEEK_COLD_RECEIPT')
    need(not (root/'cold.json').is_symlink() and (root/'cold.json').read_bytes()==coldbytes,'WEEK_COLD_COPY')
    producer=json.loads(files['producer.json']);cold=json.loads(coldbytes)
    for name,receipt in [('chronology-collect',producer),('chronology-cold',cold)]:
        p=receipt['policy']
        need(receipt['phase']==name and receipt['accepted'] is True and receipt['attempt']==1 and
             receipt['run_id']==39946364621 and receipt['source_sha']==CODE and
             receipt['trigger_sha']==TRIGGER and receipt['native_decoder_source_sha']==NATIVE and
             receipt['ciphertext_sha256']==CIPHER_SHA and receipt['provider_window_complete'] is True and
             receipt['bid_events']==341578 and receipt['ask_events']==341444 and
             receipt['chronological_events_processed']==683022 and receipt['history_requests']==196 and
             receipt['window_ms']==604800000 and receipt['orders']==receipt['economic_outcomes']==0 and
             receipt['hard21_proven'] is False and receipt['dated_costs_proven'] is False and
             receipt['historical_arrival_times_proven'] is False and
             p['from_ms']==1787529600000 and p['to_ms']==1788134400000 and p['iso_week']=='2026-W35' and
             p['symbol_id']==1 and p['symbol_name']=='EURUSD' and p['strategy_trials']==0 and
             p['confirmation_opened'] is False,'WEEK_ORIGINAL_RECEIPT')
    need(cold['independently_redecoded'] is True and cold['native_producer_conclusion']=='success' and
         cold['native_producer_job_id']==120390356655 and cold['private_sha256']==PRIVATE_SHA,
         'WEEK_NATIVE_COLD_BINDING')
    files['cold.json']=coldbytes
    destination=Path(destination)
    need(not destination.is_symlink(),'WEEK_DESTINATION_SYMLINK')
    for name,data in files.items():
        path=destination/name
        need(not path.is_symlink() and (not path.exists() or path.read_bytes()==data),'WEEK_OUTPUT_CONFLICT')
    destination.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():
        path=destination/name
        if not path.exists():
            with path.open('xb') as output:output.write(data)
    return {'schema':'mxm.durable-week35-ciphertext-restore.v1','source_run_id':39946364621,
      'archive_sha256':ARCHIVE_SHA,'ciphertext_sha256':CIPHER_SHA,'private_sha256':PRIVATE_SHA,
      'quote_events':683022,'requested_iso_week':'2026-W35','partition':'DEVELOPMENT',
      'decrypted':False,'new_broker_requests':0,'orders':0,'strategy_trials':0,
      'independent_confirmation':False,'hard21_proven':False,'historical_costs_proven':False}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path('verification/week35-chronology'))
    args=parser.parse_args();print(json.dumps(restore_week35(destination=args.out),sort_keys=True))
