"""Verify original PR173 proof/product artifacts offline; never execute vendor code."""
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path
from .confirmed_entry_ledger_checks import check,need
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/'docs/economic-development/20261024/confirmed-entry-ledger-40125946805'
PINS={'ledger':(12573621254,1004,'3fd39e8e5c1ba263b8de19b67c67169b25788dcf19137bf601825e4fd750d560'),
 'product-cli':(12573536406,77292,'cad33135ae4dbb474337ef74fef2cad6d0a30cfccf33c8bcd2c3e9de70044a24')}
SOURCE='f677c9aa75b59c3e4cd3ae5938f0643fc31e5af6'
MANIFEST_SHA='2079917e5503f5b5db64962808a1891c6121033a70116288ba5be222b397fc9d'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify(root=ARCHIVE):
    root=Path(root);raw_manifest=(root/'MANIFEST.json').read_bytes()
    need(sha(raw_manifest)==MANIFEST_SHA,'IMMUTABLE_ORIGINAL_MANIFEST');m=json.loads(raw_manifest)
    need(m['schema']=='mxm.confirmed-entry-ledger.original-ci-archives.v1' and m['run_id']==40125946805 and
         m['job_id']==120967247199 and m['source_pr']==173 and m['pr_source_head']=='ef24beb02446a68bf6eb5be028741f5d6baa1154' and
         m['pr_test_merge']==SOURCE,'ORIGINAL_NATIVE_PROVENANCE')
    need(m['broker_orders']==0 and all(m[k] is False for k in
        ('economic_edge_proven','hard21_proven','native_storage_recovery_proven')),'NO_PROMOTION')
    need(set(m['archives'])==set(PINS),'TWO_ORIGINAL_ARTIFACTS')
    all_members={}
    for name,(aid,length,digest) in PINS.items():
        a=m['archives'][name];need((a['artifact_id'],a['bytes'],a['sha256'])==(aid,length,digest),'ORIGINAL_ARCHIVE_PIN')
        chunks=[]
        need(len(a['parts'])==(length+32767)//32768,'BOUNDED_PART_COUNT')
        for i,part in enumerate(a['parts']):
            need(part['path']==f'{name}-{i:02d}.b64','PART_PATH')
            path=root/part['path'];need(not path.is_symlink() and path.stat().st_size<=43700,'PART_SIZE')
            raw=base64.b64decode(path.read_text().strip(),validate=True)
            need(len(raw)==part['bytes']<=32768 and sha(raw)==part['sha256'],'PART_HASH');chunks.append(raw)
        archive=b''.join(chunks);need(len(archive)==length and sha(archive)==digest,'EXACT_ORIGINAL_ZIP')
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            need(len(z.infolist())==len(a['members']) and set(z.namelist())==set(a['members']) and
                 sum(x.file_size for x in z.infolist())<300000,'BOUNDED_ORIGINAL_MEMBERS')
            members={p:z.read(p) for p in z.namelist()}
        for p,raw in members.items():
            need(len(raw)==a['members'][p]['bytes'] and sha(raw)==a['members'][p]['sha256'],'MEMBER_HASH')
        all_members[name]=members
    raw=all_members['ledger']['proof.json'];need((root/'proof.json').read_bytes()==raw,'EXACT_ORIGINAL_PROOF_COPY')
    proof=json.loads(raw);need(proof['source_sha']==SOURCE and proof['checks']==m['checks']==80 and
       proof['hard_kills']==m['hard_kills']==3 and proof['new_os_processes']==m['new_os_processes']==6,'PROOF_SOURCE')
    result=check(proof)
    c=all_members['product-cli'];prefix='verification/ctrader-cli-metadata/'
    r=c[prefix+'receipt.json'];need((root/'cli-receipt.json').read_bytes()==r,'EXACT_CLI_RECEIPT_COPY');v=json.loads(r)
    need(v['source_sha']==SOURCE and v['native_metadata_returncode']==0 and v['native_malformed_returncode']==1 and
         v['product_target_framework']=='net6.0' and v['native_vendor_metadata_read'],'ORIGINAL_METADATA_RECEPTION')
    binary='research_core_v4/native_tick_replay_v1/csharp/bin/Release/net6.0/'
    need(sha(c[binary+'native_tick_replay_v1.algo'])==v['artifact_sha256'] and
         len(c[binary+'native_tick_replay_v1.algo'])==v['artifact_bytes'] and
         sha(c[binary+'MxmReferenceBot.dll'])==v['product_assembly_sha256'] and
         sha(c[prefix+'metadata.stdout.txt'])==v['metadata_stdout_sha256'],'ORIGINAL_PRODUCT')
    for k in ('economic_edge_proven','hard21_proven','native_storage_recovery_proven','native_trading_callbacks_proven',
              'run_command_invoked','backtest_command_invoked','broker_credentials_supplied','broker_network_available','cloud_activated'):
        need(v[k] is False,'CLI_NO_PROMOTION_'+k)
    need(v['broker_orders']==v['new_research_trials']==0,'CLI_NO_ORDER_OR_STUDY')
    # Original evidence remains valid history after later product development;
    # report applicability separately instead of recertifying changed source.
    identical=all((ROOT/path).is_file() and sha((ROOT/path).read_bytes())==digest
                  for path,digest in m['implementation_sha256'].items())
    return dict(result,original_archives_verified=2,cli_executed=False,native_storage_reception=False,
                current_implementation_matches_original=identical)
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
