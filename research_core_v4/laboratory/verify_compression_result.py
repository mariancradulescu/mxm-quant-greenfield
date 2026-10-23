"""Offline original ciphertext/ZIP preservation, no decryption or economic rerun."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path('docs/economic-development/20261023/compression-result-39993818621')
ARCHIVE='2bb8fb90cca99b8cf01c2d6c08c235dbb520023c50b79f08e29ba8b1cb98c78c'
CIPHER='7ab6d9e5d0a0a2a2d7aef202e98c3a791390bb81b806ed682f730d14c51aac88'
PRIVATE='a70dd6092eb4e93a3d63a26bd1c548a36f940ca681d7a10350f2b5ce7453fd77'
SPEC='319299c9b20da772776688e92a9d621d03d0981ac588380a655fcb4c9221f363'
def need(ok,reason):
    if not ok:raise ValueError('MXM_COMPRESSION_ARCHIVE_'+reason)
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(root=ROOT):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_bytes());need(len(m['parts'])==10,'PART_COUNT')
    pieces=[]
    for i,p in enumerate(m['parts']):
        need(p['index']==i and p['path']==f'part-{i:02d}.b64','PART_ORDER')
        path=root/p['path'];need(not path.is_symlink() and path.stat().st_size<45000,'PART_BOUNDS')
        b=base64.b64decode(path.read_text().strip(),validate=True)
        need(len(b)==p['bytes'] and len(b)<=32768 and sha(b)==p['sha256'],'PART_DIGEST');pieces.append(b)
    raw=b''.join(pieces)
    need(len(raw)==297007==m['archive_bytes'] and sha(raw)==ARCHIVE==m['archive_sha256'],'ORIGINAL_ZIP')
    need(m['run_id']==39993818621 and m['job_id']==120552627320 and m['artifact_id']==12518768011 and
         m['source_commit']=='f44382d32aeb8783673cd9d06b5ab49a29b7f02a' and
         m['pr_head']=='d1515f32aae7aafd028161764e8546d8aae5e670' and m['required_pr_checks']==5 and
         m['spec_sha256']==SPEC,'NATIVE_PROVENANCE')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(len(z.namelist())==2 and set(z.namelist())=={'receipt.json','full-result.mxmenc'} and
             sum(x.file_size for x in z.infolist())<400000,'BOUNDED_MEMBERS')
        receipt=z.read('receipt.json');cipher=z.read('full-result.mxmenc')
    need(sha(cipher)==CIPHER==m['ciphertext_sha256'] and len(cipher)==296011==m['ciphertext_bytes'],'ORIGINAL_CIPHERTEXT')
    need(sha(receipt)==m['receipt_sha256'] and (root/'receipt.json').read_bytes()==receipt,'ORIGINAL_RECEIPT_COPY')
    v=json.loads(receipt)
    need(v['run_id']==39993818621 and v['source_commit']==m['source_commit'] and v['spec_sha256']==SPEC and
         v['manifest_sha256']=='cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4' and
         v['ciphertext_sha256']==CIPHER and v['full_private_sha256']==PRIVATE==m['full_private_sha256'] and
         v['rows_verified']==3355389 and v['shards_verified']==100 and v['ordinals_verified']==1576 and
         v['independent_episode_ledgers_reconciled']==1576 and v['mechanisms']==v['model_leaves']==1 and
         v['dependent_reference_friction_leaves']==4,'COMPLETE_PRECOMMITTED_RECONCILIATION')
    need(v['disposition']==m['disposition']=='GROSS_FAIL' and not v['all_gates_passed'] and
         v['partition']==m['partition']=='DEVELOPMENT_ALREADY_FULLY_EXPOSED' and
         not v['historical_costs_proven'] and not v['native_fills_proven'] and not v['eur200_account_simulated'] and
         not v['hard21_proven'] and not v['independent_confirmation'] and not v['edge_confirmed'] and
         not v['canonical_V2_changed'] and v['C033_preserved'] and v['new_broker_requests']==v['orders']==m['orders']==0 and
         not v['cloud_activated'] and not m['economic_edge_confirmed'] and not m['confirmation_opened'],'NO_PROMOTION')
    return {'archive_sha256':ARCHIVE,'ciphertext_sha256':CIPHER,'disposition':'GROSS_FAIL',
            'decrypted':False,'economic_rerun':False,'orders':0}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
