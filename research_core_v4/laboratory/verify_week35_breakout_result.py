"""Offline original-result byte preservation; no key or economic retest."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path('docs/economic-development/20261023/week35-breakout-result-39949806701')
ARCHIVE='eeca3a0c36957b4b49a6f96c0290e56850db05bf9ace2d2bfe2c8db238c5aa7f'
CIPHER='34eebc2a3dcae78ce4aadcac6a45e25b7599cc1fb898563b2dc7055f3fdcb3f1'
PRIVATE='5c96657279beae0cf92a4a5b6061c7f2d3d982d513de219a973247395975f6e6'
SPEC='b42db94d1fdbe5d664f9d5bc6d51ffae8521b6e31a2b59620a6d135496950f36'
def need(ok,code):
    if not ok:raise ValueError('MXM_W35_RESULT_ARCHIVE_'+code)
def digest(b):return hashlib.sha256(b).hexdigest()
def verify(root=ROOT):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_bytes())
    path=root/'artifact.zip.b64'
    need(not path.is_symlink() and path.stat().st_size<100000,'BOUNDED_FILE')
    raw=base64.b64decode(path.read_text().strip(),validate=True)
    need(len(raw)==40864 and digest(raw)==ARCHIVE==m['archive_sha256'],'PINNED_ORIGINAL_ZIP')
    need(m['run_id']==39949806701 and m['job_id']==120401225990 and m['artifact_id']==12498704870 and
         m['source_commit']=='108c2a521233e02717438332b8efc647c93a4297' and
         m['spec_sha256']==SPEC and m['orders']==0 and not m['confirmation_opened'],'MANIFEST_PROVENANCE')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(len(z.namelist())==2 and set(z.namelist())=={'receipt.json','full-result.mxmenc'},'MEMBERS')
        need(sum(x.file_size for x in z.infolist())<100000,'MEMBER_BOUNDS')
        receiptbytes=z.read('receipt.json');cipher=z.read('full-result.mxmenc')
    need(digest(cipher)==CIPHER==m['members']['full-result.mxmenc'],'CIPHERTEXT')
    need(digest(receiptbytes)==m['members']['receipt.json'] and
         not (root/'receipt.json').is_symlink() and (root/'receipt.json').read_bytes()==receiptbytes,'ORIGINAL_RECEIPT_COPY')
    r=json.loads(receiptbytes)
    need(r['run_id']==39949806701 and r['native_source_commit']==m['source_commit'] and
         r['source_run']==39946364621 and r['spec_sha256']==SPEC and
         r['full_private_sha256']==PRIVATE and r['result_ciphertext_sha256']==CIPHER and
         r['disposition']==m['disposition']=='REJECT_THIS_FIXED_DEVELOPMENT_CONFIGURATION' and
         r['dependent_model_leaves']==2 and r['mechanisms']==1 and
         r['orders']==r['new_broker_requests']==0 and not r['edge_confirmed'] and
         not r['hard21_proven'] and not r['independent_confirmation'] and
         not r['canonical_V2_ledger_mutated'] and r['C033_reservation_preserved'], 'RESULT_SCOPE_AND_DISPOSITION')
    return {'archive_sha256':ARCHIVE,'ciphertext_sha256':CIPHER,'decrypted':False,
            'economic_retest':False,'orders':0,'disposition':r['disposition']}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
