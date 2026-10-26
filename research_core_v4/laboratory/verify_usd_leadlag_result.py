"""Bounded offline original ZIP/ciphertext verification; never decrypts or reruns a model."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
ROOT=REPO/'docs/economic-development/20261026/usd-leadlag-result-40271734532'
MANIFEST='f6f952c1c4d68bb9c6d7f4b15bb289d8d4e96461e8ae59449b7698fca2abc9c4'
def need(ok,why):
    if not ok:raise ValueError('USD_LEADLAG_ARCHIVE_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify(root=ROOT):
    root=Path(root);p=root/'MANIFEST.json'
    need(not p.is_symlink() and p.stat().st_size<40000,'MANIFEST_BOUNDS')
    raw=p.read_bytes();need(sha(raw)==MANIFEST,'IMMUTABLE_MANIFEST');m=json.loads(raw)
    need(m['run_id']==40271734532 and m['job_id']==121405815410 and m['source_pr']==182 and
      m['source_sha']=='0c24afe63782d409849dc2d5bbda66bb4d6e30b9' and
      m['pr_head']=='ca2722bb9f0a320d0aafb521f0e99363dac8a08e' and
      m['pr_test_merge']=='fb71480cc86a378d22152170aea4ab80ce6a009c' and
      m['source_tree']=='21159408c6f85cf72dba88a6cb82312f3dbda3e3' and
      m['spec_sha256']=='0f6b3d903990213ebb5840f4ce0123f397ef329708490a09808f8cf785a40ce1','ORIGINAL_PROVENANCE')
    need(0<len(m['parts'])<=128,'PART_COUNT');pieces=[]
    for i,part in enumerate(m['parts']):
        need(part['index']==i and part['path']==f'part-{i:03d}.b64','PART_ORDER')
        p=root/part['path'];need(not p.is_symlink() and p.stat().st_size<=45000,'PART_BOUNDS')
        b=base64.b64decode(p.read_text().strip(),validate=True)
        need(len(b)==part['bytes']<=32768 and sha(b)==part['sha256'],'PART_BYTES');pieces.append(b)
    archive=b''.join(pieces)
    need(len(archive)==m['archive_bytes']<=4194304 and sha(archive)==m['archive_sha256'],'EXACT_NATIVE_ZIP')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        members=z.infolist()
        need(len(members)==2 and set(z.namelist())=={'receipt.json','full-result.mxmenc'} and
          sum(x.file_size for x in members)<=4194304 and all(not x.flag_bits&1 for x in members),'BOUNDED_MEMBERS')
        receipt=z.read('receipt.json');cipher=z.read('full-result.mxmenc')
    for name,raw in [('receipt.json',receipt),('full-result.mxmenc',cipher)]:
        need(len(raw)==m['members'][name]['bytes'] and sha(raw)==m['members'][name]['sha256'],'MEMBER_HASH')
    p=root/'receipt.json';need(not p.is_symlink() and p.stat().st_size<20000 and p.read_bytes()==receipt,'EXACT_RECEIPT_COPY')
    r=json.loads(receipt)
    need(r['schema']=='mxm.usd-leadlag-public.v1' and r['run_id']==m['run_id'] and r['source_sha']==m['source_sha'] and
      r['spec_sha256']==m['spec_sha256'] and r['source_rows']==1960588 and
      r['source_runs']=={'EURUSD':39917922508,'GBPUSD':40179011821} and
      r['independent_all_decisions_and_episodes_reconciled'] is True and r['hypotheses']==r['model_leaves']==r['dependent_fee_slippage_scenarios']==1 and
      r['private_sha256']==m['private_sha256'] and r['ciphertext_sha256']==sha(cipher) and
      r['disposition']==m['disposition'] and r['screen_gates']==m['screen_gates'],'ORIGINAL_RESULT_BINDING')
    need(r['partition']=='DEVELOPMENT_ALREADY_EXPOSED' and r['orders']==r['new_broker_requests']==0 and
      all(r[k] is False for k in ('capital_replay','hard21_proven','edge_confirmed','historical_costs_proven','native_fills_proven','canonical_V2_changed','cloud_activated')),
      'NO_PROMOTION')
    need(sha((REPO/'research_core_v4/laboratory/USD_LEADLAG_DEVELOPMENT_V1.json').read_bytes())==m['spec_sha256'],'SPEC_PRESERVED')
    changed=[p for p,h in m['original_source_files'].items() if not (REPO/p).is_file() or sha((REPO/p).read_bytes())!=h]
    return {'source_run':m['run_id'],'source_sha':m['source_sha'],'artifact_id':m['artifact_id'],
      'original_zip_verified':True,'archive_sha256':m['archive_sha256'],'ciphertext_sha256':sha(cipher),
      'disposition':r['disposition'],'screen_gates':r['screen_gates'],'current_implementation_matches_original':not changed,
      'changed_source_paths':changed,'decrypted':False,'economic_rerun':False,'orders':0,'capital_replay':False,'edge_confirmed':False,'hard21_proven':False}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
