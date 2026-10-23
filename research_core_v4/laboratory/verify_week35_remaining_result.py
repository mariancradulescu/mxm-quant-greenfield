"""Offline original-result byte preservation; no key or economic retest."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path('docs/economic-development/20261023/week35-remaining-result-39956825625')
ARCHIVE='2aa2cd6b3471c888e8d4eb2de2370253221f0c316ea44a31e955775bce5a4f63'
CIPHER='273d142f6f8df97c20852c930f2f13edff60b7cb8616d29f8926c2032a503f0b'
PRIVATE='e6b3de20cd4ae5943736fecac798ba6cf8426bcf91ab2d3f5535857d58630105'
SPEC='02feb5c7d78c16543023edc404edbb375f6214a128f4afd96880ee1313dc0dcd'
def need(ok,code):
    if not ok:raise ValueError('MXM_W35_RESULT_ARCHIVE_'+code)
def digest(b):return hashlib.sha256(b).hexdigest()
def verify(root=ROOT):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_bytes())
    need(len(m['parts'])==3,'PART_COUNT')
    chunks=[]
    for i,part in enumerate(m['parts']):
        need(part['index']==i and part['path']==f'part-{i:02d}.b64','PART_ORDER')
        path=root/part['path']
        need(not path.is_symlink() and path.stat().st_size<50000,'BOUNDED_FILE')
        chunk=base64.b64decode(path.read_text().strip(),validate=True)
        need(len(chunk)==part['bytes'] and len(chunk)<=32768 and digest(chunk)==part['sha256'],'PART_DIGEST')
        chunks.append(chunk)
    raw=b''.join(chunks)
    need(len(raw)==85816 and digest(raw)==ARCHIVE==m['archive_sha256'],'PINNED_ORIGINAL_ZIP')
    need(m['run_id']==39956825625 and m['job_id']==120425066646 and m['artifact_id']==12502587482 and
         m['source_commit']=='9255553170762d1c6dd9543a2b2cf820255eb25b' and
         m['spec_sha256']==SPEC and m['orders']==0 and not m['confirmation_opened'],'MANIFEST_PROVENANCE')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(len(z.namelist())==2 and set(z.namelist())=={'receipt.json','full-result.mxmenc'},'MEMBERS')
        need(sum(x.file_size for x in z.infolist())<100000,'MEMBER_BOUNDS')
        receiptbytes=z.read('receipt.json');cipher=z.read('full-result.mxmenc')
    need(digest(cipher)==CIPHER==m['ciphertext_sha256'],'CIPHERTEXT')
    need(digest(receiptbytes)==m['receipt_sha256'] and
         not (root/'receipt.json').is_symlink() and (root/'receipt.json').read_bytes()==receiptbytes,'ORIGINAL_RECEIPT_COPY')
    r=json.loads(receiptbytes)
    need(r['run_id']==39956825625 and r['native_source_commit']==m['source_commit'] and
         r['source_run']==39946364621 and r['spec_sha256']==SPEC and
         r['full_private_sha256']==PRIVATE and r['result_ciphertext_sha256']==CIPHER and
         r['disposition']==m['disposition']=='NEITHER_REMAINING_FIXED_FAMILY_ADVANCES' and
         r['family_dispositions']==m['family_dispositions']=={
          'TrendOnly':'REJECT_THIS_FIXED_DEVELOPMENT_CONFIGURATION',
          'RangeFade':'REJECT_THIS_FIXED_DEVELOPMENT_CONFIGURATION'} and
         r['dependent_model_leaves']==4 and r['mechanisms']==2 and
         r['orders']==r['new_broker_requests']==0 and not r['edge_confirmed'] and
         not r['hard21_proven'] and not r['independent_confirmation'] and
         not r['canonical_V2_ledger_mutated'] and r['C033_reservation_preserved'], 'RESULT_SCOPE_AND_DISPOSITION')
    return {'archive_sha256':ARCHIVE,'ciphertext_sha256':CIPHER,'decrypted':False,
            'economic_retest':False,'orders':0,'disposition':r['disposition']}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
