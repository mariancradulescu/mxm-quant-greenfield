"""Verify original peer-screen bytes without keys, policy execution or market replay."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[2]
ROOT=BASE/'docs/economic-development/20261028/peer-residual-40641460227'
MANIFEST_SHA='5a3d2669e4b6d6d7cd5a1fd960e9ebca4588257057f127af81967b9e7e9221a0'
def need(ok,why):
 if not ok:raise ValueError('ORIGINAL_PEER_RESIDUAL_'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p,limit):
 need(p.is_file() and not p.is_symlink() and p.stat().st_size<=limit,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def verify(root=ROOT):
 root=Path(root);need(not root.is_symlink() and not (root/'artifact').is_symlink(),'REGULAR_ROOT')
 raw=read(root/'MANIFEST.json',30000);need(sha(raw)==MANIFEST_SHA,'PINNED_MANIFEST');m=json.loads(raw)
 need(m['run_id']==40641460227 and m['job_id']==122660331816 and m['attempt']==1 and m['source_sha']=='50f539beccc61e2fbc0dcf9ab45c931bb04a642c' and m['artifact_id']==12795887578,'NATIVE_IDENTITY')
 need(0<m['artifact_bytes']<2000000 and 0<len(m['parts'])<=128,'ARCHIVE_BOUNDS');chunks=[]
 for i,p in enumerate(m['parts']):
  need(p['index']==i and p['path']==f'artifact/part-{i:02d}.b64' and 0<p['bytes']<=16384,'PART_IDENTITY')
  b=base64.b64decode(read(root/p['path'],21850).strip(),validate=True);need(len(b)==p['bytes'] and sha(b)==p['sha256'],'PART_DIGEST');chunks.append(b)
 archive=b''.join(chunks);need(len(archive)==m['artifact_bytes'] and sha(archive)==m['artifact_sha256'],'ORIGINAL_ARCHIVE')
 with zipfile.ZipFile(io.BytesIO(archive)) as z:
  expected={'receipt.json','cold.json','result.mxmenc','evaluator.dll'}
  need(len(z.namelist())==4 and set(z.namelist())==expected and sum(x.file_size for x in z.infolist())<2000000,'EXACT_MEMBERS');files={k:z.read(k) for k in expected}
 for k,b in files.items():need(len(b)==m['members'][k]['bytes'] and sha(b)==m['members'][k]['sha256'],'MEMBER_DIGEST')
 r=json.loads(files['receipt.json']);c=json.loads(files['cold.json'])
 for k in ('receipt.json','cold.json'):need(read(root/k,15000)==files[k],'ORIGINAL_PUBLIC_COPIES')
 for x in (r,c):need(x['run_id']==m['run_id'] and x['source_sha']==m['source_sha'] and x['orders']==0,'RECEIPT_IDENTITY')
 source=read(BASE/'research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_DURABLE_MANIFEST_V1.json',2000000)
 need(sha(source)==r['source_manifest_sha256']==m['source_manifest_sha256']=='cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4','ORIGINAL_MARKET_MANIFEST')
 need(sha(read(BASE/'research_programs/admissions/PEER_RESIDUAL_20261028.json',30000))==r['spec_sha256']==m['spec_sha256'] and r['input_sha256']==m['input_sha256'],'FROZEN_POLICY_INPUT')
 need(r['source_rows']==m['source_rows']==3355389 and r['source_shards']==m['source_shards']==100 and r['source_identities']==m['source_identities']==1576 and r['model_trials']==m['model_trials']==1 and r['new_dependent_hypotheses']==m['new_dependent_hypotheses']==1 and r['all_causal_feature_selection_and_episode_records_reconciled'] is True,'COMPLETE_SCOPE_PARITY')
 gates={'all_three_source_blocks_above_5bps':False,'at_least_100_complete':True,'censor_fraction_at_most_5pct':False,'gross_positive':True,'mean_above_reference_5bps':True,'top5_absolute_symbol_contribution_at_most_50pct':True}
 need(r['disposition']==c['disposition']==m['disposition']=='DATA_LIMITED' and r['gates']==m['gates']==gates,'FIXED_VERDICT_NO_FAVORABLE_REINTERPRETATION')
 need(sha(files['result.mxmenc'])==r['cipher_sha256']==c['cipher_sha256']==m['cipher_sha256'] and r['private_sha256']==m['private_sha256'] and sha(files['evaluator.dll'])==r['actual_evaluator_sha256']==m['actual_evaluator_sha256'] and files['evaluator.dll'].startswith(b'MZ'),'ORIGINAL_CIPHER_AND_ACTUAL_DLL')
 need(c['separate_custody_process_readback'] is True and c['algorithm_reexecuted'] is False and r['next_action']=='STOP_FIXED_IDENTITY_NO_RETUNE_NO_AUTOMATIC_FOLLOWUP' and m['fixed_identity_closed_no_retune'] is True,'COLD_AND_CLOSURE')
 for k in ('capital_replay','net_edge_proven','historical_costs_proven','actual_fills_proven','hard21_proven','native_robot_operational_reception_proven'):need(r[k] is False and m[k] is False,'NO_PROMOTION')
 need(r['reference_friction_is_hypothetical'] is True and r['independent_confirmation'] is False and r['protected_opened'] is False and r['formal_V2_C033_changed'] is False and m['source_decrypted_in_work'] is False and m['economic_rerun_during_preservation'] is False,'NO_COST_CONFIRMATION_OR_RERUN_INFERENCE')
 for k in ('new_broker_requests','orders'):need(r[k]==m[k]==0,'NO_ADDITIONAL_ACTIVITY')
 return {'run_id':m['run_id'],'source_sha':m['source_sha'],'source_rows':3355389,'source_shards':100,'source_identities':1576,'model_trials':1,'disposition':'DATA_LIMITED','gates':gates,'source_decrypted':False,'economic_rerun':False,'net_edge_proven':False,'orders':0,'original_zip_sha256':m['artifact_sha256']}
if __name__=='__main__':print('MXM_ORIGINAL_PEER_RESIDUAL '+json.dumps(verify(),sort_keys=True))
