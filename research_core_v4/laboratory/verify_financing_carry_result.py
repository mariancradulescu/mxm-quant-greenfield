"""Verify original encrypted financing source/results, without keys or model replay."""
import base64,io,json,zipfile,hashlib
from pathlib import Path
from .durable_native_chronology import decode_archive
ROOT=Path(__file__).resolve().parents[2]/'docs/economic-development/20261027/financing-carry-40587457654'
MANIFEST_SHA='2986157382d938688e9770b92479833ff5743cddd8d8ca32a2bdac9e1386f7be'
def need(ok,code):
 if not ok:raise ValueError('ORIGINAL_FINANCING_'+code)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p,limit):
 need(p.is_file() and not p.is_symlink() and p.stat().st_size<=limit,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def verify(root=ROOT):
 root=Path(root);need(not root.is_symlink() and not (root/'source').is_symlink(),'REGULAR_ROOT')
 raw=read(root/'MANIFEST.json',30000);need(sha(raw)==MANIFEST_SHA,'PINNED_MANIFEST');m=json.loads(raw)
 need(m['run_id']==40587457654 and m['source_sha']=='c681974caa97f96cab036a05fd8322304e344a54' and m['attempt']==1 and m['source_rows']==1576,'PROVENANCE')
 need(sha(read(root/'source/MANIFEST.json',30000))==m['source_manifest_sha256'],'SOURCE_MANIFEST')
 sm,source=decode_archive(root/'source',m['artifacts']['source']['sha256'])
 need(sm['artifact_id']==m['artifacts']['source']['id'] and sm['source_run_id']==m['run_id'] and sm['source_head']==m['source_sha'] and sm['archive_bytes']==m['artifacts']['source']['bytes'],'ORIGINAL_SOURCE')
 result=base64.b64decode(read(root/'result-artifact.zip.b64',2000000).strip(),validate=True)
 need(len(result)==m['artifacts']['result']['bytes'] and sha(result)==m['artifacts']['result']['sha256'],'ORIGINAL_RESULT_ZIP')
 with zipfile.ZipFile(io.BytesIO(result)) as z:
  allowed={'receipt.json','cold.json','result.mxmenc','evaluator.dll'}
  need(len(z.namelist())==4 and set(z.namelist())==allowed and sum(x.file_size for x in z.infolist())<2000000,'MEMBERS')
  files={k:z.read(k) for k in allowed}
 for k,b in files.items():need(len(b)==m['result_members'][k]['bytes'] and sha(b)==m['result_members'][k]['sha256'],'RESULT_MEMBER')
 p=json.loads(source['producer.json']);r=json.loads(files['receipt.json']);c=json.loads(files['cold.json'])
 for x in (p,r,c):need(x['run_id']==m['run_id'] and x['source_sha']==m['source_sha'] and x['orders']==0,'PUBLIC_IDENTITY')
 need(read(root/'producer.json',10000)==source['producer.json'] and read(root/'receipt.json',15000)==files['receipt.json'] and read(root/'cold.json',10000)==files['cold.json'],'EXACT_PUBLIC_COPIES')
 need(p['accepted'] is True and p['new_connections']==1 and p['metadata_responses']==m['metadata_responses'] and p['cipher_sha256']==m['source_cipher_sha256']==r['source_cipher_sha256']==sha(source['capture.mxmenc']) and p['private_sha256']==m['source_private_sha256'],'SOURCE_CUSTODY')
 need([p['contact_start_utc'],p['contact_end_utc']]==m['contact_interval_utc']==[r['contact_start_utc'],r['contact_end_utc']],'ACTUAL_CONTACT_WINDOW')
 need(r['source_rows']==1576 and r['spec_sha256']==p['spec_sha256']==m['spec_sha256'] and r['capture_job']==m['jobs']['capture'] and r['model_trials']==r['new_hypotheses']==1 and r['all_universe_financing_rows_independently_reconciled'] is True,'ACTUAL_CSHARP_AND_REFERENCE')
 need(r['disposition']==c['disposition']==m['disposition'] and r['gates']==m['gates'] and r['source_observability']==m['source_observability'],'FIXED_VERDICT')
 need(sha(files['result.mxmenc'])==r['result_cipher_sha256']==c['result_cipher_sha256']==m['result_cipher_sha256'] and r['result_private_sha256']==m['result_private_sha256'] and sha(files['evaluator.dll'])==r['evaluator_sha256']==m['evaluator_sha256'] and files['evaluator.dll'].startswith(b'MZ'),'CIPHER_AND_ACTUAL_DLL')
 need(c['separate_custody_process_readback'] is True and c['algorithm_reexecuted'] is False and r['new_broker_contacts_in_evaluation']==0 and r['next_action']=='STOP_FIXED_IDENTITY_NO_RETUNE_OR_AUTOMATIC_FOLLOWUP','COLD_AND_STOP')
 for k in ('capital_replay','net_edge_proven','hard21_proven','native_robot_operational_reception_proven'):need(r[k] is False and m[k] is False,'NO_PROMOTION')
 need(r['broker_fills_proven'] is False and r['costs_defaulted_to_zero'] is False and m['economic_rerun'] is False and m['source_decrypted_in_work'] is False,'NO_INVENTED_COSTS_OR_REPLAY')
 return {'run_id':m['run_id'],'source_sha':m['source_sha'],'source_rows':1576,'disposition':m['disposition'],'gates':m['gates'],'source_observability':m['source_observability'],'source_decrypted':False,'economic_rerun':False,'orders':0,'net_edge_proven':False}
if __name__=='__main__':print('MXM_ORIGINAL_FINANCING '+json.dumps(verify(),sort_keys=True))
