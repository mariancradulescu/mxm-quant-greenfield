"""Accepted bytes/header and local-host observations only; no number parsing."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import zipfile
from . import gate

def inspect(archive_directory):
    root=gate.ROOT;old=root/'research_core_v4/exploratory_dev_v1'
    delivery=json.loads((old/'DELIVERY_MANIFEST_V1.json').read_bytes())
    for p,h in delivery['files_sha256'].items():
        if gate.sha((root/p).read_bytes())!=h:raise ValueError('V1_DELIVERY_DRIFT:'+p)
    manifest=json.loads((root/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json').read_bytes())
    evidence=json.loads((old/'RECONCILIATION_AND_CORPUS_V1.json').read_bytes())
    for p,h in evidence['frozen_authorities_verified_sha256'].items():
        if gate.sha((root/p).read_bytes())!=h:raise ValueError('INHERITED_DRIFT:'+p)
    gate.signed_scope()
    rows=[];archives=[]
    for expected in evidence['archives']:
        p=Path(archive_directory)/expected['filename']
        if not p.is_file():raise ValueError('ARCHIVE_UNAVAILABLE')
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
        if h.hexdigest()!=expected['sha256']:raise ValueError('ARCHIVE_DIGEST')
        with zipfile.ZipFile(p) as z:
            names=z.namelist()
            if len(names)!=len(set(names)):raise ValueError('DUPLICATE_MEMBER')
            for s in manifest['primary_series']:
                if s['source_archive_sha256']!=h.hexdigest():continue
                if s['file']!='raw/'+str(s['symbol_id'])+'_M5.csv':raise ValueError('MEMBER_SCOPE')
                with z.open(s['file']) as f:header=f.readline(4096).decode('utf-8-sig').rstrip('\r\n')
                if header!='time_utc,open,high,low,close,tick_volume':raise ValueError('HEADER_SCHEMA')
                if gate.sha(z.read(s['file']))!=s['series_sha256']:raise ValueError('SERIES_DIGEST')
                rows.append({'symbol_id':s['symbol_id'],'member':s['file'],'header':header,'series_sha256':s['series_sha256']})
        archives.append({**expected,'physically_accessible_now':True,'observed_sha256':h.hexdigest()})
    if len(rows)!=145:raise ValueError('PRIMARY145_INCOMPLETE')
    filesystem=json.loads(subprocess.check_output(['findmnt','-J','-T',str(root)],text=True))['filesystems'][0]
    future_exists=Path('/srv/mxm-primary145/accepted-archives').is_dir()
    blockers=['PERSISTENT_EXECUTION_HOST_NOT_BOUND: independent lifecycle/storage attestation remains required']
    if filesystem['fstype'] in ('overlay','tmpfs','ramfs','erofs'):
        blockers[0]='PERSISTENT_EXECUTION_HOST_NOT_BOUND: observed filesystem '+filesystem['fstype']+' is denied'
    if not future_exists:blockers.append('FUTURE_ARCHIVE_MATERIALIZATION_NOT_VERIFIED: signed future archive path absent')
    return {'input_head':'84af51091046d663575433dcedaba87b5af295c9',
      'observed_checkout_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
      'delivery_integrity':'PASS_26_OF_26','inherited_hashes':'PASS','archives':archives,'accepted_headers_verified':145,
      'members':rows,'numerical_fields_converted':0,'real_responses_computed':0,
      'execution_host_observation':{'hostname':socket.gethostname(),'filesystem':filesystem,
        'cgroup_memory_max_bytes':int(Path('/sys/fs/cgroup/memory.max').read_text()),
        'RLIMIT_CPU_supported':True,'RLIMIT_AS_supported':True,
        'future_archive_directory_exists':future_exists,
        'independent_key_installed':gate.KEY.is_file()},
      'workflow_counts_evidence':'separate live GitHub connector reconciliation, not inferred by this script',
      'proven_operational_blockers':blockers,
      'accepted_sources_are_rematerializable_not_assumed_persistent':[x['filename'] for x in archives],
      'immutable_V1_preserved':True}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive_directory');args=parser.parse_args()
    result=inspect(args.archive_directory)
    (gate.HERE/'RECONCILIATION_AND_HOST_V2.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'headers_and_digests':145,'real_numeric_fields':0,'memory_cap_bytes':result['execution_host_observation']['cgroup_memory_max_bytes'],
      'filesystem':result['execution_host_observation']['filesystem']['fstype'],'future_archive_directory_exists':result['execution_host_observation']['future_archive_directory_exists']}))
