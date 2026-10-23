"""Offline restoration of exact new WEEK ciphertext/receipts; no decrypt or broker."""
import base64
import io
import json
import zipfile
from pathlib import Path
from .durable_native_chronology import decode_archive, digest, need

ROOT=Path('docs/economic-development/20261023/native-week-39917922508')
ARCHIVE_SHA='dbbda51f6419b8f5d576044a034b4f28200476f9ebf9be633463ceab0a004906'
CIPHER_SHA='2403c74dfd81ab410f9b9c3bdabf4f3d5a5a4df0133cd0adc03933a364d539b6'
PRIVATE_SHA='8dde8355c79f3f379bf14f1fd47a8ed5815646cafbcfc287762fb68c2c2e7b51'
COLD_ZIP_SHA='2c5971cf7fa61cf8372c9d32e0be1d14237b71113b57c7ba18c1e17ff94f1b1e'
COLD_SHA='fff8965b686d62695ba1dfb410f3cdf4985e22ca5455f3ce76af8a394d48a1cc'
CODE='120db3391ed1f4105120274b73a9259690eeeb64'
TRIGGER='e65fea6321d84acce19c0a965f7814ca6d842183'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'


def restore_week(root=ROOT,destination=Path('verification/week-chronology')):
    root=Path(root)
    m,files=decode_archive(root,ARCHIVE_SHA,max_archive_bytes=8*1024*1024,max_parts=256,part_size=32768)
    need(m['source_run_id']==39917922508 and m['artifact_id']==12486315900 and
         m['artifact_name']=='week-chronology-39917922508' and
         m['source_head']==TRIGGER and m['code_source']==CODE and m['decoder_source']==NATIVE and
         m['partition']=='DEVELOPMENT' and m['iso_week']=='2026-W37' and
         m['quote_events']==685474 and m['cold_artifact_id']==12486460595 and
         m['native_producer_job_id']==120295856025 and m['native_cold_job_id']==120296341940 and
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
             receipt['run_id']==39917922508 and receipt['source_sha']==CODE and
             receipt['trigger_sha']==TRIGGER and receipt['native_decoder_source_sha']==NATIVE and
             receipt['ciphertext_sha256']==CIPHER_SHA and receipt['provider_window_complete'] is True and
             receipt['bid_events']==342248 and receipt['ask_events']==343226 and
             receipt['chronological_events_processed']==685474 and receipt['history_requests']==210 and
             receipt['window_ms']==604800000 and receipt['orders']==receipt['economic_outcomes']==0 and
             receipt['hard21_proven'] is False and receipt['dated_costs_proven'] is False and
             receipt['historical_arrival_times_proven'] is False and
             p['from_ms']==1788739200000 and p['to_ms']==1789344000000 and p['iso_week']=='2026-W37' and
             p['symbol_id']==1 and p['symbol_name']=='EURUSD' and p['strategy_trials']==0 and
             p['confirmation_opened'] is False,'WEEK_ORIGINAL_RECEIPT')
    need(cold['independently_redecoded'] is True and cold['native_producer_conclusion']=='success' and
         cold['native_producer_job_id']==120295856025 and cold['private_sha256']==PRIVATE_SHA,
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
    return {'schema':'mxm.durable-week-ciphertext-restore.v1','source_run_id':39917922508,
      'archive_sha256':ARCHIVE_SHA,'ciphertext_sha256':CIPHER_SHA,'private_sha256':PRIVATE_SHA,
      'quote_events':685474,'requested_iso_week':'2026-W37','partition':'DEVELOPMENT',
      'decrypted':False,'new_broker_requests':0,'orders':0,'strategy_trials':0,
      'independent_confirmation':False,'hard21_proven':False,'historical_costs_proven':False}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path('verification/week-chronology'))
    args=parser.parse_args();print(json.dumps(restore_week(destination=args.out),sort_keys=True))
