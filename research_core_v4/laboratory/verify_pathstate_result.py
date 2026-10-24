"""Offline original ciphertext/receipt/ZIP reception; no key, decryption or market rerun."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
ROOT=REPO/'docs/economic-development/20261024/pathstate-result-40128480865'
ARCHIVE='d1a874f01b1d854505018ce2d160f2c742f1eb66a7e11a43bea6b844d0aa6a37'
MANIFEST='5781e334b8551f27044d96d7f1cdc18ec9e550d1881fca6c5f9aee6adaeda8da'
CIPHER='3d7d4349fc9ed21a2f76a614090674865edb9841ff0d169e81625ffaaff2fb31'
PRIVATE='0d6c80c5157d7b4d4287862a67d357e84558f17c0a5be8e8383ec54957743206'
SPEC='e9ff40a442915698daf4912baf43eb432dc9ee6313e102748f1c2fcb42f229a8'
def need(ok,why):
    if not ok:raise ValueError('MXM_PATHSTATE_ARCHIVE_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify(root=ROOT):
    root=Path(root);raw_manifest=(root/'MANIFEST.json').read_bytes()
    need(sha(raw_manifest)==MANIFEST,'IMMUTABLE_MANIFEST');m=json.loads(raw_manifest)
    need(len(m['parts'])==16,'PART_COUNT');pieces=[]
    for i,part in enumerate(m['parts']):
        need(part['index']==i and part['path']==f'part-{i:02d}.b64','PART_ORDER')
        path=root/part['path'];need(not path.is_symlink() and path.stat().st_size<45000,'PART_BOUNDS')
        raw=base64.b64decode(path.read_text().strip(),validate=True)
        need(len(raw)==part['bytes']<=32768 and sha(raw)==part['sha256'],'PART_DIGEST');pieces.append(raw)
    archive=b''.join(pieces)
    need(len(archive)==518949==m['archive_bytes'] and sha(archive)==ARCHIVE==m['archive_sha256'],'ORIGINAL_ZIP')
    need(m['run_id']==40128480865 and m['job_id']==120974909464 and m['artifact_id']==12574875087 and m['source_pr']==174 and
         m['source_commit']=='4200df0e55a241a4b4789f0cdd8c387a7c237df5' and
         m['pr_source_head']=='9129a6d4fcd9fe85e25417afcd785c0988b483be' and
         m['pr_test_merge']=='2e33917533104e85e25ba7fa82dc5eabcadcdeb8' and
         m['source_tree']=='357f3f5b21f3e6703373c99d8250c6f7b41d1156' and m['spec_sha256']==SPEC,'NATIVE_PROVENANCE')
    need(sha((REPO/'research_core_v4/laboratory/PATHSTATE_DEVELOPMENT_V1.json').read_bytes())==SPEC,'ORIGINAL_SPEC_UNCHANGED')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        need(len(z.infolist())==2 and set(z.namelist())=={'receipt.json','full-result.mxmenc'} and
             sum(x.file_size for x in z.infolist())<600000,'BOUNDED_MEMBERS')
        receipt=z.read('receipt.json');cipher=z.read('full-result.mxmenc')
    for name,raw in (('receipt.json',receipt),('full-result.mxmenc',cipher)):
        need(len(raw)==m['members'][name]['bytes'] and sha(raw)==m['members'][name]['sha256'],'MEMBER_DIGEST')
    need(sha(cipher)==CIPHER and len(cipher)==517800 and (root/'receipt.json').read_bytes()==receipt,'EXACT_ORIGINAL_COPIES')
    r=json.loads(receipt)
    need(r['schema']=='mxm.pathstate-development-public.v1' and r['run_id']==40128480865 and
         r['source_commit']==m['source_commit'] and r['spec_sha256']==SPEC and
         r['ciphertext_sha256']==CIPHER and r['full_private_sha256']==PRIVATE and
         r['manifest_sha256']=='cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4' and
         r['rows_verified']==3355389 and r['shards_verified']==100 and r['ordinals_verified']==1576 and
         all(r[k]==1576 for k in ('independent_episode_ledgers_reconciled','independent_signal_ledgers_reconciled',
            'independent_forecast_ledgers_reconciled','independent_training_ledgers_reconciled')) and
         r['mechanisms']==r['model_leaves']==1 and r['dependent_reference_friction_leaves']==4 and
         r['evaluation_start']=='2026-08-27T00:00:00Z' and r['warmup_only_source_segment']==1,'COMPLETE_RECONCILIATION')
    need(r['disposition']==m['disposition']=='GROSS_FAIL' and r['partition']=='DEVELOPMENT_ALREADY_FULLY_EXPOSED' and
         r['all_gates_passed'] is False and r['friction_references_hypothetical'] is True and r['C033_preserved'] is True and
         all(r[k] is False for k in ('historical_costs_proven','native_fills_proven','eur200_account_simulated',
            'hard21_proven','independent_confirmation','edge_confirmed','canonical_V2_changed','cloud_activated')) and
         all(m[k] is False for k in ('economic_edge_confirmed','hard21_proven','native_fills_proven','independent_confirmation')) and
         r['orders']==r['new_broker_requests']==m['orders']==0,'NO_PROMOTION')
    return dict(archive_sha256=ARCHIVE,ciphertext_sha256=CIPHER,disposition='GROSS_FAIL',
        training_forecast_signal_episode_ledgers_reconciled=1576,decrypted=False,economic_rerun=False,orders=0)
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
