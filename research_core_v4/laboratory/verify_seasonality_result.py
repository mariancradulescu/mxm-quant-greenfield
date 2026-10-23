"""Offline original ciphertext/ZIP preservation, no decryption or economic rerun."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path('docs/economic-development/20261023/utc-seasonality-result-40018030252')
ARCHIVE='fa04235b0e4f9f45c919bd052b5b55c75daf3aec76577b17caef1b20b41f777d'
CIPHER='bbf02de22ec8359f453b5df26a2dfb667c2fecbd0db1b48408190a19d5d626e8'
PRIVATE='83e85724154968205892e6a2bb99e36903ad9cf985442fc7b4b860e4740d6b5d'
SPEC='88be4ce14f6664104a548c3415fdbd2594821df123f8301ac41e54ab5a1b12ed'
def need(ok,reason):
    if not ok:raise ValueError('MXM_SEASONALITY_ARCHIVE_'+reason)
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(root=ROOT):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_bytes());need(len(m['parts'])==12,'PART_COUNT')
    pieces=[]
    for i,p in enumerate(m['parts']):
        need(p['index']==i and p['path']==f'part-{i:02d}.b64','PART_ORDER')
        path=root/p['path'];need(not path.is_symlink() and path.stat().st_size<45000,'PART_BOUNDS')
        b=base64.b64decode(path.read_text().strip(),validate=True)
        need(len(b)==p['bytes'] and len(b)<=32768 and sha(b)==p['sha256'],'PART_DIGEST');pieces.append(b)
    raw=b''.join(pieces)
    need(len(raw)==385476==m['archive_bytes'] and sha(raw)==ARCHIVE==m['archive_sha256'],'ORIGINAL_ZIP')
    need(m['run_id']==40018030252 and m['job_id']==120635049524 and m['artifact_id']==12529970530 and
         m['source_commit']=='4c879c3148ee031041497930f4ef50df5c7e80df' and
         m['pr_head']=='1ff05a9e2c75dcad035ac8a7002cf74189f1b051' and m['required_pr_checks']==2 and
         m['spec_sha256']==SPEC,'NATIVE_PROVENANCE')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(len(z.namelist())==2 and set(z.namelist())=={'receipt.json','full-result.mxmenc'} and
             sum(x.file_size for x in z.infolist())<500000,'BOUNDED_MEMBERS')
        receipt=z.read('receipt.json');cipher=z.read('full-result.mxmenc')
    need(sha(cipher)==CIPHER==m['ciphertext_sha256'] and len(cipher)==384371==m['ciphertext_bytes'],'ORIGINAL_CIPHERTEXT')
    need(sha(receipt)==m['receipt_sha256'] and (root/'receipt.json').read_bytes()==receipt,'ORIGINAL_RECEIPT_COPY')
    v=json.loads(receipt)
    need(v['run_id']==40018030252 and v['source_commit']==m['source_commit'] and v['spec_sha256']==SPEC and
         v['manifest_sha256']=='cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4' and
         v['ciphertext_sha256']==CIPHER and v['full_private_sha256']==PRIVATE==m['full_private_sha256'] and
         v['rows_verified']==3355389 and v['shards_verified']==100 and v['ordinals_verified']==1576 and
         v['independent_episode_ledgers_reconciled']==v['independent_signal_ledgers_reconciled']==1576 and
         v['evaluation_start']=='2026-08-27T00:00:00Z' and v['warmup_only_source_segment']==1 and
         v['friction_references_hypothetical'] and v['mechanisms']==v['model_leaves']==1 and
         v['dependent_reference_friction_leaves']==4,'COMPLETE_PRECOMMITTED_RECONCILIATION')
    need(v['disposition']==m['disposition']=='REFERENCE_FRICTION_FAIL' and not v['all_gates_passed'] and
         v['partition']==m['partition']=='DEVELOPMENT_ALREADY_FULLY_EXPOSED' and
         not v['historical_costs_proven'] and not v['native_fills_proven'] and not v['eur200_account_simulated'] and
         not v['hard21_proven'] and not v['independent_confirmation'] and not v['edge_confirmed'] and
         not v['canonical_V2_changed'] and v['C033_preserved'] and v['new_broker_requests']==v['orders']==m['orders']==0 and
         not v['cloud_activated'] and not m['economic_edge_confirmed'] and not m['confirmation_opened'],'NO_PROMOTION')
    return {'archive_sha256':ARCHIVE,'ciphertext_sha256':CIPHER,'disposition':'REFERENCE_FRICTION_FAIL',
            'decrypted':False,'economic_rerun':False,'orders':0}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
