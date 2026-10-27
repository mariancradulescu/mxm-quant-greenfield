"""Offline verification of ORIGINAL encrypted source/result; no model, key or broker."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
from .durable_native_chronology import decode_archive
ROOT=Path(__file__).resolve().parents[2]/'docs/economic-development/20261027/depth-pressure-40536275775'
MANIFEST_SHA='aab6e568e732a23f86ee6c5461d0171b44cce82e48f7de1b51ebe499772056a4'
def need(ok,why):
 if not ok:raise ValueError('ORIGINAL_DEPTH_PRESSURE_'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p,limit):
 need(p.is_file() and not p.is_symlink() and p.stat().st_size<=limit,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def verify(root=ROOT):
 root=Path(root);need(not root.is_symlink() and not (root/'source').is_symlink(),'REGULAR_ROOT')
 raw=read(root/'MANIFEST.json',30000);need(sha(raw)==MANIFEST_SHA,'PINNED_MANIFEST');m=json.loads(raw)
 need(m['run_id']==40536275775 and m['attempt']==1 and m['source_sha']=='05465f133567dfcc81e1bc2fe6b0020f5cbf0485' and
  m['spec_sha256']=='d980a10359f43217d7a579279182035810acc3627ccbcd4708b28a4b586ec0d7','NATIVE_PROVENANCE')
 need(sha(read(root/'source/MANIFEST.json',30000))==m['source_manifest_sha256'],'SOURCE_MANIFEST')
 sm,source=decode_archive(root/'source',m['artifacts']['source']['sha256'])
 need(sm['artifact_id']==m['artifacts']['source']['id']==12748323446 and sm['source_run_id']==m['run_id'] and sm['source_head']==m['source_sha'] and
  sm['archive_bytes']==m['artifacts']['source']['bytes'] and sha(source['capture.mxmenc'])==m['source_cipher_sha256'],'SOURCE_ORIGINAL')
 result=base64.b64decode(read(root/'result-artifact.zip.b64',2000000).strip(),validate=True)
 need(len(result)==m['artifacts']['result']['bytes'] and sha(result)==m['artifacts']['result']['sha256'] and m['artifacts']['result']['id']==12748019284,'RESULT_ORIGINAL_ZIP')
 with zipfile.ZipFile(io.BytesIO(result)) as z:
  allowed={'receipt.json','cold.json','result.mxmenc','evaluator.dll'}
  need(len(z.namelist())==4 and set(z.namelist())==allowed and sum(i.file_size for i in z.infolist())<2000000,'EXACT_MEMBERS')
  files={k:z.read(k) for k in allowed}
 for k,b in files.items():need(len(b)==m['result_members'][k]['bytes'] and sha(b)==m['result_members'][k]['sha256'],'RESULT_MEMBER_'+k)
 producer=json.loads(source['producer.json']);r=json.loads(files['receipt.json']);c=json.loads(files['cold.json'])
 for p in (producer,r,c):need(p['run_id']==m['run_id'] and p['source_sha']==m['source_sha'] and p['orders']==0,'PUBLIC_NATIVE_IDENTITY')
 need(read(root/'producer.json',10000)==source['producer.json'] and read(root/'receipt.json',10000)==files['receipt.json'] and read(root/'cold.json',10000)==files['cold.json'],'EXACT_PUBLIC_COPIES')
 need(producer['accepted'] is True and producer['new_connections']==1 and producer['events']==r['source_rows']==4066 and
  producer['cipher_sha256']==m['source_cipher_sha256'] and producer['private_sha256']==m['source_private_sha256'] and
  [producer['contact_start_utc'],producer['contact_end_utc']]==m['contact_interval_utc'],'AUTHENTIC_SOURCE_SCOPE')
 need(r['capture_job']==m['jobs']['capture']==122302262185 and m['jobs']['evaluate']==122309956020 and
  r['model_trials']==r['new_hypotheses']==m['model_trials']==1 and r['all_decisions_episodes_censors_independently_reconciled'] is True and
  r['new_broker_contacts_in_evaluation']==0 and r['spec_sha256']==m['spec_sha256'],'ACTUAL_MODEL_AND_REFERENCE')
 need(r['disposition']==c['disposition']==m['disposition']=='DATA_LIMITED' and
  r['gates']==m['gates']=={'at_least_100_complete':False,'censor_fraction_at_most_5pct':False,'quoted_gross_positive':False},'FIXED_VERDICT_NO_REINTERPRETATION')
 need(sha(files['result.mxmenc'])==r['result_cipher_sha256']==c['result_cipher_sha256']==m['result_cipher_sha256'] and
  r['result_private_sha256']==m['result_private_sha256'] and sha(files['evaluator.dll'])==r['evaluator_sha256']==m['evaluator_sha256'] and files['evaluator.dll'].startswith(b'MZ'),'ORIGINAL_CIPHER_AND_ACTUAL_DLL')
 need(c['separate_custody_process_readback'] is True and c['algorithm_reexecuted'] is False and
  r['next_action']=='STOP_FIXED_IDENTITY_NO_RETUNE_OR_AUTOMATIC_FOLLOWUP','COLD_AND_TERMINALITY')
 for k in ('capital_replay','net_edge_proven','hard21_proven','native_robot_operational_reception_proven'):need(r[k] is False and m[k] is False,'NO_PROMOTION_'+k)
 need(r['broker_fills_proven'] is False and r['costs_defaulted_to_zero'] is False and m['economic_rerun'] is False and m['source_decrypted_in_work'] is False,'NO_COST_FILL_OR_RERUN_CLAIM')
 return {'schema':'mxm.original-depth-pressure-verification.v1','run_id':m['run_id'],'source_sha':m['source_sha'],'source_events':4066,
  'model_trials':1,'disposition':m['disposition'],'all_decisions_episodes_censors_reconciled':True,'source_decrypted':False,'economic_rerun':False,
  'source_archive_sha256':m['artifacts']['source']['sha256'],'result_archive_sha256':m['artifacts']['result']['sha256'],'orders':0,'net_edge_proven':False,'hard21_proven':False,'native_robot_operational_reception_proven':False}
if __name__=='__main__':print('MXM_ORIGINAL_DEPTH_PRESSURE '+json.dumps(verify(),sort_keys=True))
