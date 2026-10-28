"""Original encrypted unit ledger only: no decryption, unit calculation or model replay."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
from .verify_financing_carry_result import verify as verify_source,ROOT as SOURCE_ROOT,MANIFEST_SHA as SOURCE_MANIFEST_SHA
ROOT=Path(__file__).resolve().parents[2]/'docs/economic-development/20261028/displayed-financing-40636503311'
MANIFEST_SHA='6c5a2235fc82c63b3ae3d7e3dbe5857ac766d33d4d9164a78ee92cee80939efe'
def need(ok,why):
 if not ok:raise ValueError('ORIGINAL_FINANCING_UNITS_'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p,limit):
 need(p.is_file() and not p.is_symlink() and p.stat().st_size<=limit,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def verify(root=ROOT):
 root=Path(root);need(not root.is_symlink() and not (root/'artifact').is_symlink(),'REGULAR_ROOT')
 raw=read(root/'MANIFEST.json',30000);need(sha(raw)==MANIFEST_SHA,'PINNED_MANIFEST');m=json.loads(raw)
 need(m['schema']=='mxm.original-displayed-financing-components.v1' and m['run_id']==40636503311 and m['job_id']==122644581129 and m['attempt']==1 and m['source_sha']=='3cf69ecf33b682c9fe77393a02f22710ec28eb13' and m['artifact_id']==12794195409,'NATIVE_IDENTITY')
 need(0<m['artifact_bytes']<2000000 and 0<len(m['parts'])<=128,'ARCHIVE_BOUNDS');chunks=[]
 for i,p in enumerate(m['parts']):
  need(p['index']==i and p['path']==f'artifact/part-{i:02d}.b64' and 0<p['bytes']<=16384,'PART_IDENTITY')
  b=base64.b64decode(read(root/p['path'],21850).strip(),validate=True);need(len(b)==p['bytes'] and sha(b)==p['sha256'],'PART_BYTES');chunks.append(b)
 archive=b''.join(chunks);need(len(archive)==m['artifact_bytes'] and sha(archive)==m['artifact_sha256'],'ORIGINAL_ZIP')
 with zipfile.ZipFile(io.BytesIO(archive)) as z:
  expected={'receipt.json','cold.json','ledger.mxmenc','evaluator.dll'}
  need(len(z.namelist())==4 and set(z.namelist())==expected and sum(x.file_size for x in z.infolist())<2000000,'MEMBERS')
  files={k:z.read(k) for k in expected}
 for k,b in files.items():need(len(b)==m['members'][k]['bytes'] and sha(b)==m['members'][k]['sha256'],'MEMBER_DIGEST')
 r=json.loads(files['receipt.json']);c=json.loads(files['cold.json'])
 for k in ('receipt.json','cold.json'):need(read(root/k,15000)==files[k],'ORIGINAL_PUBLIC_COPY')
 for x in (r,c):need(x['run_id']==m['run_id'] and x['source_sha']==m['source_sha'] and x['orders']==0,'RECEIPT_IDENTITY')
 verify_source();source=json.loads((SOURCE_ROOT/'MANIFEST.json').read_bytes())
 need(SOURCE_MANIFEST_SHA==m['original_manifest_sha256'] and r['original_source_run']==m['original_source_run']==40587457654 and r['original_source_sha']==source['source_sha'] and r['original_private_sha256']==source['source_private_sha256'] and r['original_cipher_sha256']==source['source_cipher_sha256'],'AUTHENTIC_ORIGINAL_INPUT_LINK')
 need(r['rows']==m['rows']==1576 and r['policy_sha256']==m['policy_sha256'] and r['disposition']==m['disposition']=='AUTHENTIC_CURRENT_UNIT_COMPONENTS_ONLY' and r['all_components_independently_reconciled'] is True and r['any_component_estimated'] is True,'EXACT_COMPONENT_RECEPTION')
 need(sha(files['ledger.mxmenc'])==r['ledger_cipher_sha256']==c['ledger_cipher_sha256']==m['ledger_cipher_sha256'] and r['ledger_private_sha256']==m['ledger_private_sha256'] and sha(files['evaluator.dll'])==r['actual_evaluator_sha256']==m['actual_evaluator_sha256'] and files['evaluator.dll'].startswith(b'MZ'),'CIPHER_AND_ACTUAL_DLL')
 need(c['separate_custody_process_readback'] is True and c['algorithm_reexecuted'] is False,'SEPARATE_COLD_READBACK')
 for k in ('actual_broker_charges_proven','market_account_replay','net_edge_proven','native_robot_operational_reception_proven','hard21_proven'):need(r[k] is False and m[k] is False,'NO_PROMOTION')
 need(r['calendar_inferred'] is False and r['historical_applicability_proven'] is False and r['closed_screen_reexecuted'] is False and m['source_decrypted_in_work'] is False and m['unit_calculation_rerun_during_preservation'] is False,'NO_REINTERPRETATION')
 for k in ('new_broker_requests','new_strategy_trials','orders'):need(r[k]==m[k]==0,'NO_ADDITIONAL_ACTIVITY')
 return {'run_id':m['run_id'],'source_sha':m['source_sha'],'rows':1576,'disposition':m['disposition'],'all_components_independently_reconciled':True,'any_component_estimated':True,'original_zip_sha256':m['artifact_sha256'],'source_decrypted':False,'unit_calculation_rerun':False,'new_broker_requests':0,'new_strategy_trials':0,'orders':0,'actual_broker_charges_proven':False,'market_account_replay':False,'net_edge_proven':False,'native_robot_operational_reception_proven':False}
if __name__=='__main__':print('MXM_ORIGINAL_DISPLAYED_FINANCING '+json.dumps(verify(),sort_keys=True))
