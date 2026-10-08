"""Minimal operational reader successor; every numerical law reused from V1."""
import json
import os
from pathlib import Path
import numpy as np
from research_core_v4.exploratory_dev_v1 import worker as science
from . import gate

ROOT=Path(__file__).resolve().parents[2]

def read_production(permit):
    gate.require(type(permit) is gate.Permit,'SEPARATE_ARM_REQUIRED');permit.check()
    p=permit.payload;checkpoint=Path(p['checkpoint_directory']);marker=checkpoint/'CONSUMED.json'
    gate.require(not marker.exists(),'PASS_ALREADY_CONSUMED_NO_REPLAY')
    manifest=json.loads((ROOT/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json').read_bytes())
    records=sorted(manifest['primary_series'],key=lambda x:x['symbol_id'])
    gate.require(len(records)==145 and len({x['symbol_id'] for x in records})==145,'PRIMARY145_INCOMPLETE')
    evidence=json.loads((ROOT/'research_core_v4/exploratory_dev_v1/RECONCILIATION_AND_CORPUS_V1.json').read_bytes())
    expected={x['sha256']:x['filename'] for x in evidence['archives']}
    gate.require(len(expected)==2 and {x['source_archive_sha256'] for x in records}==set(expected),'ARCHIVE_SCOPE')
    state={'arm_digest':permit.arm_digest,'complete':False,'caches':{},'parsed_series':0,'parsed_rows':0}
    gate.durable_json(marker,state,exclusive=True);archives={};caches=[]
    try:
        for h,name in expected.items():
            permit.check();archives[h]=science.verified_archive(Path(p['archive_directory'])/name,h)
        for record in records:
            permit.check();raw=science.accepted_member(archives[record['source_archive_sha256']],record)
            bars=science.parse_series(raw,record);cache=science.derive(bars)
            final=checkpoint/(str(record['symbol_id'])+'.npz');tmp=final.with_suffix('.tmp')
            with tmp.open('wb') as f:
                np.savez_compressed(f,**cache);f.flush();os.fsync(f.fileno())
            tmp.replace(final)
            state['caches'][str(record['symbol_id'])]=science.digest(final.read_bytes())
            state['parsed_series']+=1;state['parsed_rows']+=len(bars);gate.durable_json(marker,state)
            caches.append(cache);del bars,raw
        state['complete']=True;gate.durable_json(marker,state)
        return caches,[x['symbol_id'] for x in records]
    except BaseException as err:
        state['failure_type']=type(err).__name__;state['failure_reason']=str(err)
        gate.durable_json(marker,state);raise
    finally:
        for z in archives.values():z.close()
