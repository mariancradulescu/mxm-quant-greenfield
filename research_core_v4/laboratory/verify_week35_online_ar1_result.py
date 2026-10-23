"""Offline original-result byte preservation; no key or economic retest."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path('docs/economic-development/20261023/week35-online-ar1-reproduction-39973081180')
ARCHIVE='171eb6449230e56f7acfd2d8e1f876f6f82ab99fc8ff17ae8550523c6314807c'
CIPHER='0764f16631fd7eeb95462247b65a98d3fd679d66425ecccd803efc050ce8adf6'
PRIVATE='4c5750bc6c3d451f49a4275cb29addb2a70c9a5bca615e34cb5cc6331005749f'
SPEC='4fb321c8a3f3938440d161e4dd0320880726e9b9aa59651da1318556a4c79cbc'
def need(ok,code):
    if not ok:raise ValueError('MXM_W35_RESULT_ARCHIVE_'+code)
def digest(b):return hashlib.sha256(b).hexdigest()
def verify(root=ROOT):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_bytes())
    need(len(m['parts'])==1,'PART_COUNT')
    chunks=[]
    for i,part in enumerate(m['parts']):
        need(part['index']==i and part['path']==f'part-{i:02d}.b64','PART_ORDER')
        path=root/part['path']
        need(not path.is_symlink() and path.stat().st_size<50000,'BOUNDED_FILE')
        chunk=base64.b64decode(path.read_text().strip(),validate=True)
        need(len(chunk)==part['bytes'] and len(chunk)<=32768 and digest(chunk)==part['sha256'],'PART_DIGEST')
        chunks.append(chunk)
    raw=b''.join(chunks)
    need(len(raw)==6326 and digest(raw)==ARCHIVE==m['archive_sha256'],'PINNED_ORIGINAL_ZIP')
    need(m['run_id']==39973081180 and m['job_id']==120480559096 and m['artifact_id']==12510276625 and
         m['source_commit']=='b25dfdafb036b76fa482b7724163fdc88da13499' and
         m['spec_sha256']==SPEC and m['orders']==0 and not m['confirmation_opened'],'MANIFEST_PROVENANCE')
    need(m['original_failed_run']==39972292334 and not m['original_ciphertext_preserved'] and
         not m['reproduction_is_independent_evidence'],'NO_LOST_ORIGINAL_OR_INDEPENDENCE_CLAIM')
    original=json.loads(Path('docs/economic-development/20261023/week35-online-ar1-first-run-39972292334/public-receipt-from-job-log.json').read_bytes())
    need(original['run_id']==39972292334 and original['native_source_commit']=='409b40d08fd2bb58555bf9fe173f17c7ae488f21' and
         original['spec_sha256']==SPEC and original['disposition']==m['disposition'] and
         original['family_dispositions']==m['family_dispositions'] and
         original['activity_classification']==m['activity_classification'],'FIRST_FAILED_RUN_RETAINED')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(len(z.namelist())==2 and set(z.namelist())=={'receipt.json','full-result.mxmenc'},'MEMBERS')
        need(sum(x.file_size for x in z.infolist())<100000,'MEMBER_BOUNDS')
        receiptbytes=z.read('receipt.json');cipher=z.read('full-result.mxmenc')
    need(digest(cipher)==CIPHER==m['ciphertext_sha256'],'CIPHERTEXT')
    need(digest(receiptbytes)==m['receipt_sha256'] and
         not (root/'receipt.json').is_symlink() and (root/'receipt.json').read_bytes()==receiptbytes,'ORIGINAL_RECEIPT_COPY')
    r=json.loads(receiptbytes)
    need(r['run_id']==39973081180 and r['native_source_commit']==m['source_commit'] and
         r['source_run']==39946364621 and r['spec_sha256']==SPEC and
         r['full_private_sha256']==PRIVATE and r['result_ciphertext_sha256']==CIPHER and
         r['disposition']==m['disposition']=='ONLINE_AR1_FIXED_CONFIGURATION_DOES_NOT_ADVANCE' and
         r['family_dispositions']==m['family_dispositions']=={
          'OnlineAr1':'REJECT_THIS_FIXED_DEVELOPMENT_CONFIGURATION'} and
         r['dependent_model_leaves']==2 and r['mechanisms']==1 and
         r['orders']==r['new_broker_requests']==0 and not r['edge_confirmed'] and
         not r['hard21_proven'] and not r['independent_confirmation'] and
         not r['canonical_V2_ledger_mutated'] and r['C033_reservation_preserved'], 'RESULT_SCOPE_AND_DISPOSITION')
    need(r['activity_classification']==m['activity_classification']=={'OnlineAr1':{
         'base':'BELOW_MODELED_21_ENTRY_THRESHOLD','stress':'BELOW_MODELED_21_ENTRY_THRESHOLD'}} and
         not r['cloud_activated'] and not r['native_ctrader_fills_proven'] and
         not r['historical_costs_proven'],'NO_ACTIVITY_OR_EXECUTION_PROMOTION')
    return {'archive_sha256':ARCHIVE,'ciphertext_sha256':CIPHER,'decrypted':False,
            'economic_retest':False,'original_ciphertext_preserved':False,'independent_evidence':False,'orders':0,'disposition':r['disposition']}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
