"""Restore exact original second-symbol encrypted source, offline, without keys or research."""
import base64
import io
import json
import zipfile
from pathlib import Path
from .durable_native_chronology import decode_archive, digest, need
ROOT=Path('docs/economic-development/20261025/native-gbpusd-week37-40179011821')
MANIFEST_SHA='4e963de3e7ce02391a1ee5b6e28f46fa9a29d09d57e85fc94f2b268cbd9e6422'
ARCHIVE_SHA='c997ed65e2538d2c4508bbecb1dbd5589da5f77b6e57ad76b1ed06815cc8d4d4'
COLD_ZIP_SHA='597de3e5623185fea3b744034870e1fe90ae8c5aebab87565db881f973aea19b'
CIPHER_SHA='3c643d7f4d72503deb39873e5bf10a8f6cb210d83d310d11150acd549dc7c08a'
PRIVATE_SHA='d1dd4ff123f9542f99db15a2e982022e2074e1e63a3a703807d2c2ad2defd513'
CODE='e750288c76eb2d917cbadcea0c9a3449ea4941d5'
TRIGGER='ca3cd598a14be12785e1e1ed2ef7866a70e35ed1'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'

def restore_gbpusd_week37(root=ROOT,destination=Path('verification/gbpusd-week37-chronology')):
    root=Path(root);manifest=root/'MANIFEST.json'
    need(not root.is_symlink() and not manifest.is_symlink() and manifest.stat().st_size<100000,'GBP_MANIFEST_FILE')
    need(digest(manifest.read_bytes())==MANIFEST_SHA,'GBP_IMMUTABLE_MANIFEST')
    m,files=decode_archive(root,ARCHIVE_SHA,max_archive_bytes=8*1024*1024,max_parts=512,part_size=32768)
    need(m['source_run_id']==40179011821 and m['artifact_id']==12593805217 and
         m['code_source']==CODE and m['source_head']==TRIGGER and m['decoder_source']==NATIVE and
         m['native_producer_job_id']==121126047508 and m['native_cold_job_id']==121126477583 and
         m['cold_artifact_id']==12593214990 and m['private_sha256']==PRIVATE_SHA,'GBP_NATIVE_SOURCE_IDENTITY')
    need(digest(files['capture.mxmenc'])==CIPHER_SHA,'GBP_PINNED_CIPHER')
    path=root/'cold-artifact.zip.b64'
    need(not path.is_symlink() and path.stat().st_size<8192,'GBP_COLD_FILE')
    raw=base64.b64decode(path.read_text().strip(),validate=True)
    need(digest(raw)==COLD_ZIP_SHA==m['cold_archive_sha256'],'GBP_COLD_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(z.namelist()==['cold.json'] and z.infolist()[0].file_size<16384,'GBP_COLD_MEMBERS')
        coldbytes=z.read('cold.json')
    need(digest(coldbytes)==m['cold_receipt_sha256'],'GBP_COLD_RECEIPT')
    for name,value in [('cold.json',coldbytes),('producer.json',files['producer.json'])]:
        path=root/name
        need(not path.is_symlink() and path.read_bytes()==value,'GBP_EXACT_RECEIPT_COPY')
    producer=json.loads(files['producer.json']);cold=json.loads(coldbytes)
    for phase,r in [('chronology-collect',producer),('chronology-cold',cold)]:
        p=r['policy']
        need(r['schema']=='mxm.week-native-chronology-public.v1' and r['phase']==phase and
             r['accepted'] is True and r['run_id']==40179011821 and r['attempt']==1 and
             r['source_sha']==CODE and r['trigger_sha']==TRIGGER and r['native_decoder_source_sha']==NATIVE and
             r['ciphertext_sha256']==CIPHER_SHA and r['provider_window_complete'] is True and
             r['bid_events']==639246 and r['ask_events']==635868 and
             r['chronological_events_processed']==1275114 and r['history_requests']==370 and
             r['metadata_requests']==2 and r['same_ms_cross_side_order_unknown']==462759 and
             r['crossed_causal_snapshots']==2 and r['window_ms']==604800000,'GBP_ORIGINAL_NATIVE_RECEIPT')
        need(p==m['policy'] and p['symbol_id']==2 and p['symbol_name']=='GBPUSD' and
             p['from_ms']==1788739200000 and p['to_ms']==1789344000000 and p['iso_week']=='2026-W37' and
             p['strategy_trials']==p['orders']==p['economic_outcomes']==0 and
             p['automatic_retry'] is False and p['confirmation_opened'] is False,'GBP_FIXED_DEVELOPMENT_POLICY')
        need(r['orders']==r['economic_outcomes']==0 and all(r[k] is False for k in
             ('hard21_proven','dated_costs_proven','historical_arrival_times_proven','continuous_market_coverage_proven',
              'economic_fidelity_accepted','research_capability_accepted')),'GBP_NO_ECONOMIC_OR_EXECUTION_PROMOTION')
    need(cold['native_producer_job_id']==121126047508 and cold['native_producer_conclusion']=='success' and
         cold['independently_redecoded'] is True and cold['private_sha256']==PRIVATE_SHA,'GBP_COLD_PRODUCER_BINDING')
    need(m['orders']==m['strategy_trials']==m['new_broker_requests_on_restore']==0 and
         all(m[k] is False for k in ('independent_confirmation','historical_costs_proven','economic_edge_proven',
                                    'hard21_proven','merged_economic_replay_executed')),'GBP_NO_PROMOTION')
    files['cold.json']=coldbytes;destination=Path(destination)
    need(not destination.is_symlink(),'GBP_DESTINATION_SYMLINK')
    for name,value in files.items():
        path=destination/name
        need(not path.is_symlink() and (not path.exists() or path.read_bytes()==value),'GBP_OUTPUT_CONFLICT')
    destination.mkdir(parents=True,exist_ok=True)
    for name,value in files.items():
        path=destination/name
        if not path.exists():
            with path.open('xb') as output:output.write(value)
    return {'schema':'mxm.durable-gbpusd-week37-ciphertext-restore.v1','source_run_id':40179011821,
            'archive_sha256':ARCHIVE_SHA,'ciphertext_sha256':CIPHER_SHA,'private_sha256':PRIVATE_SHA,
            'symbol_name':'GBPUSD','quote_events':1275114,'requested_iso_week':'2026-W37',
            'partition':'DEVELOPMENT_ALREADY_EXPOSED','existing_eurusd_same_week_run':39917922508,
            'crossed_causal_snapshots':2,'same_ms_cross_side_order_unknown':462759,
            'decrypted':False,'new_broker_requests':0,'orders':0,'strategy_trials':0,
            'independent_confirmation':False,'historical_costs_proven':False,'economic_edge_proven':False,
            'hard21_proven':False,'merged_economic_replay_executed':False}
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path('verification/gbpusd-week37-chronology'))
    args=parser.parse_args();print(json.dumps(restore_gbpusd_week37(destination=args.out),sort_keys=True))
