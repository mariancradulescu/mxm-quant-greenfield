"""Offline restoration of exact new WEEK ciphertext/receipts; no decrypt or broker."""
import base64
import io
import json
import zipfile
from pathlib import Path
from .durable_native_chronology import decode_archive, digest, need

ROOT=Path('docs/economic-development/20261026/native-week36-40276181331')
ARCHIVE_SHA='332495b9f0760dae4d3c341ec703513f7b5df4affc84c49f3f4b68ac2712cc23'
CIPHER_SHA='45e3f2d620ea9dcc5a3960d0d887c365821eab7da84b485212072dc9e96e1060'
PRIVATE_SHA='c8e348ef4ebd2c9418594d2b1033191c9e64b684e85fe1bee42033f81dce7800'
COLD_ZIP_SHA='2e055151f970fda67d1b2ae200f1073e1ffbd64140a6589a0ec9d632a33ff029'
COLD_SHA='9cb6cb4d8c83c164f4130a108af8f1dc0a505f964fab204f0bee781eee2a247c'
CODE='a0b7b39d435c898edf3b4222f4fc8f8e849e2602'
TRIGGER='3d171dbd328c28cd5089771d8a7d259d54637913'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'


def restore_week36(root=ROOT,destination=Path('verification/week36-chronology')):
    root=Path(root)
    m,files=decode_archive(root,ARCHIVE_SHA,max_archive_bytes=8*1024*1024,max_parts=256,part_size=32768)
    need(m['source_run_id']==40276181331 and m['artifact_id']==12630526391 and
         m['artifact_name']=='week-chronology-40276181331' and
         m['source_head']==TRIGGER and m['code_source']==CODE and m['decoder_source']==NATIVE and
         m['partition']=='DEVELOPMENT' and m['iso_week']=='2026-W36' and
         m['quote_events']==761196 and m['cold_artifact_id']==12630551433 and
         m['native_producer_job_id']==121419619417 and m['native_cold_job_id']==121420063615 and
         m['private_sha256']==PRIVATE_SHA and m['new_broker_requests_on_restore']==m['orders']==m['strategy_trials']==0 and
         m['independent_confirmation'] is False,'WEEK_SOURCE_IDENTITY')
    need(digest(files['capture.mxmenc'])==CIPHER_SHA,'WEEK_PINNED_CIPHER')
    need(not (root/'producer.json').is_symlink() and
         (root/'producer.json').read_bytes()==files['producer.json'],'WEEK_PRODUCER_COPY')
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
             receipt['run_id']==40276181331 and receipt['source_sha']==CODE and
             receipt['trigger_sha']==TRIGGER and receipt['native_decoder_source_sha']==NATIVE and
             receipt['ciphertext_sha256']==CIPHER_SHA and receipt['provider_window_complete'] is True and
             receipt['bid_events']==381116 and receipt['ask_events']==380080 and
             receipt['chronological_events_processed']==761196 and receipt['history_requests']==214 and
             receipt['window_ms']==604800000 and receipt['orders']==receipt['economic_outcomes']==0 and
             receipt['hard21_proven'] is False and receipt['dated_costs_proven'] is False and
             receipt['historical_arrival_times_proven'] is False and
             p['from_ms']==1788134400000 and p['to_ms']==1788739200000 and p['iso_week']=='2026-W36' and
             p['symbol_id']==1 and p['symbol_name']=='EURUSD' and p['strategy_trials']==0 and
             p['confirmation_opened'] is False,'WEEK_ORIGINAL_RECEIPT')
    need(cold['independently_redecoded'] is True and cold['native_producer_conclusion']=='success' and
         cold['native_producer_job_id']==121419619417 and cold['private_sha256']==PRIVATE_SHA,
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
    return {'schema':'mxm.durable-week36-ciphertext-restore.v1','source_run_id':40276181331,
      'archive_sha256':ARCHIVE_SHA,'ciphertext_sha256':CIPHER_SHA,'private_sha256':PRIVATE_SHA,
      'quote_events':761196,'requested_iso_week':'2026-W36','partition':'DEVELOPMENT',
      'decrypted':False,'new_broker_requests':0,'orders':0,'strategy_trials':0,
      'independent_confirmation':False,'hard21_proven':False,'historical_costs_proven':False}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path('verification/week36-chronology'))
    args=parser.parse_args();print(json.dumps(restore_week36(destination=args.out),sort_keys=True))
