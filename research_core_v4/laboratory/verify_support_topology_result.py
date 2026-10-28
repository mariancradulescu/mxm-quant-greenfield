"""Verify original time-only support output without custody, source access or recomputation."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[2]
ROOT=BASE/'docs/economic-development/20261028/support-topology-40650642477'
MANIFEST_SHA='6563fa41cfeb2dfe43c8ebbb046fb6ee22d874bf9bed010c9b4eeaee0d05c17d'
def need(ok,why):
 if not ok:raise ValueError('ORIGINAL_SUPPORT_TOPOLOGY_'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p,limit):
 need(p.is_file() and not p.is_symlink() and p.stat().st_size<=limit,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def verify(root=ROOT):
 root=Path(root);need(not root.is_symlink() and not (root/'bundle').is_symlink(),'REGULAR_ROOT')
 raw=read(root/'MANIFEST.json',30000);need(sha(raw)==MANIFEST_SHA,'PINNED_MANIFEST');m=json.loads(raw)
 need(m['run_id']==40650642477 and m['job_id']==122689643153 and m['attempt']==1 and m['source_sha']=='02df7a28893d6394e70ce861819e5aeef2390e7d','NATIVE_IDENTITY')
 need(m['bundle_kind']=='RUNTIME_ORIGINAL_OUTPUT_BUNDLE_NOT_ACTIONS_TRANSPORT_ZIP' and 0<m['bundle_bytes']<1500000 and 0<len(m['parts'])<=100,'ORIGINAL_BUNDLE_BOUNDS');chunks=[]
 for i,p in enumerate(m['parts']):
  need(p['index']==i and p['path']==f'bundle/part-{i:02d}.b64' and 0<p['bytes']<=16384,'PART_IDENTITY')
  b=base64.b64decode(read(root/p['path'],21850).strip(),validate=True);need(len(b)==p['bytes'] and sha(b)==p['sha256'],'PART_DIGEST');chunks.append(b)
 archive=b''.join(chunks);need(len(archive)==m['bundle_bytes'] and sha(archive)==m['bundle_sha256'],'ORIGINAL_RUNTIME_BUNDLE')
 with zipfile.ZipFile(io.BytesIO(archive)) as z:
  expected={'receipt.json','cold.json','result.mxmenc','evaluator.dll'}
  need(len(z.namelist())==4 and set(z.namelist())==expected and sum(x.file_size for x in z.infolist())<2000000,'EXACT_MEMBERS');files={k:z.read(k) for k in expected}
 for k,b in files.items():need(len(b)==m['members'][k]['bytes'] and sha(b)==m['members'][k]['sha256'],'MEMBER_DIGEST')
 r=json.loads(files['receipt.json']);c=json.loads(files['cold.json'])
 for k in ('receipt.json','cold.json'):need(read(root/k,20000)==files[k],'ORIGINAL_PUBLIC_COPY')
 for x in (r,c):need(x['run_id']==m['run_id'] and x['source_sha']==m['source_sha'] and x['orders']==0,'RECEIPT_IDENTITY')
 need(r['source_rows']==3355389 and r['source_shards']==100 and r['source_identities']==1576 and r['cells_reconciled']==18912 and r['all_time_only_cells_reconciled'] is True,'COMPLETE_SCOPE_PARITY')
 need(r['disposition']==c['disposition']==m['disposition']=='OBSERVATION_SUPPORT_ONLY_NO_STRATEGY_QUALIFICATION','NO_ECONOMIC_QUALIFICATION')
 need(r['each_profile_all_four_blocks_at_most_5pct_missing_unselected_grid']==m['unselected_grid_flags']=={'1': False, '12': False, '288': False},'ORIGINAL_OBSERVATION_FLAGS')
 need(sha(read(BASE/'research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_DURABLE_MANIFEST_V1.json',2000000))==r['source_manifest_sha256']==m['source_manifest_sha256']=='cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4','ORIGINAL_MARKET_MANIFEST')
 need(sha(read(BASE/'research_programs/reconciliation/SUPPORT_TOPOLOGY_20261028.json',30000))==r['spec_sha256']==m['spec_sha256'] and r['input_sha256']==m['input_sha256'],'FROZEN_TIME_ONLY_SPEC_INPUT')
 need(sha(files['result.mxmenc'])==r['cipher_sha256']==c['cipher_sha256']==m['cipher_sha256'] and r['private_sha256']==m['private_sha256'] and sha(files['evaluator.dll'])==r['actual_evaluator_sha256']==m['actual_evaluator_sha256'] and files['evaluator.dll'].startswith(b'MZ'),'ORIGINAL_CIPHER_AND_ACTUAL_DLL')
 need(c['separate_custody_process_readback'] is True and c['algorithm_reexecuted'] is False,'SEPARATE_COLD_WITHOUT_RECOMPUTATION')
 for k in ('prices_exported','return_stability_measured','signal_conditioned_censoring_identified','closed_identities_reexecuted','capital_replay','net_edge_proven','historical_costs_proven','actual_fills_proven','hard21_proven','native_robot_operational_reception_proven','protected_opened','independent_confirmation','formal_V2_C033_changed'):need(r[k] is False,'NO_PROMOTION_OR_CLOSED_REPLAY')
 for k in ('new_strategy_identities','model_trials','new_broker_requests','orders'):need(r[k]==0,'NO_ADDITIONAL_ECONOMIC_OR_BROKER_ACTIVITY')
 need(m['source_decrypted_in_work'] is False and m['support_recomputed_during_preservation'] is False and r['next_action']=='DIRECTOR_SOURCE_SELECTION_REQUIRES_DISTINCT_PROSPECTIVE_MECHANISM_NO_AUTOMATIC_TRIAL','NO_RETUNE_RERUN_OR_AUTOMATIC_MODEL')
 return dict(run_id=m['run_id'],source_sha=m['source_sha'],source_rows=3355389,cells_reconciled=18912,unselected_grid_flags=m['unselected_grid_flags'],disposition=r['disposition'],source_decrypted=False,support_recomputed=False,new_strategy_identities=0,net_edge_proven=False,orders=0,bundle_sha256=m['bundle_sha256'])
if __name__=='__main__':print('MXM_ORIGINAL_SUPPORT_TOPOLOGY '+json.dumps(verify(),sort_keys=True))
