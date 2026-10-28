"""Restore exact original outputs offline; no key, model replay or recompilation."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261028/quote-innovation-40675714422'
MANIFEST_SHA='27f806d06387ea313ba50efb7600e3f9c43a08e6f2e3eba1253069ba20477813'
def need(ok,why):
 if not ok:raise ValueError('INNOVATION_ORIGINAL_'+why)
def digest(x):return hashlib.sha256(x).hexdigest()
def verify(folder=FOLDER):
 folder=Path(folder);need(not folder.is_symlink() and not (folder/'MANIFEST.json').is_symlink(),'SYMLINK');mraw=(folder/'MANIFEST.json').read_bytes();need(digest(mraw)==MANIFEST_SHA,'MANIFEST');m=json.loads(mraw)
 parts=[]
 for entry in m['parts']:
  path=folder/entry['path'];need(not path.is_symlink(),'SYMLINK');b=base64.b64decode(path.read_text().strip(),validate=True)
  need(len(b)==entry['bytes'] and digest(b)==entry['sha256'],'PART');parts.append(b)
 bundle=b''.join(parts);need(len(bundle)==m['bundle']['bytes'] and digest(bundle)==m['bundle']['sha256'],'BUNDLE')
 with zipfile.ZipFile(io.BytesIO(bundle)) as z:
  need(set(z.namelist())==set(m['bundle']['members']) and len(z.namelist())==len(m['bundle']['members']),'MEMBERS')
  values={}
  for name,e in m['bundle']['members'].items():
   info=z.getinfo(name);need(info.file_size==e['bytes'] and info.file_size<20000000,'MEMBER_BOUND')
   b=z.read(name);need(digest(b)==e['sha256'],'MEMBER_HASH');values[name]=b
 r=json.loads(values['receipt.json']);c=json.loads(values['cold.json']);recovery=json.loads(values['recovery.json'])
 need(recovery['failed_run']==40674118381 and recovery['recovery_run']==r['run_id'] and recovery['original_economics']=='SKIPPED' and recovery['scientific_spec_sha256']==r['spec_sha256'] and recovery['new_scientific_models']==0 and not recovery['scientific_parameters_changed'] and not recovery['attempt_refunded'],'RECOVERY')
 need(r==json.loads((folder/'receipt.json').read_bytes()) and c==json.loads((folder/'cold.json').read_bytes()),'ORIGINAL_RECEIPTS')
 need(r['run_id']==m['run_id'] and r['source_sha']==m['source_sha'] and r['spec_sha256']==m['spec_sha256'],'NATIVE_IDENTITY')
 need(digest(values['full-result.mxmenc'])==r['ciphertext_sha256']==c['ciphertext_sha256'] and digest(values['evaluator.dll'])==r['actual_evaluator_sha256'],'CIPHER_DLL')
 need(c['original_readback'] and c['model_reexecuted'] is False and c['orders']==r['orders']==0,'COLD')
 need(r['source_rows_verified']==2129692 and r['models']==r['cost_scenarios']==r['initial_funding_count']==1 and r['one_initial_capital_eur']==200,'SCOPE')
 need(not any(r[k] for k in ('closed_model_reexecuted','canonical_V2_C033_changed','new_broker_requests','cloud_activated','hard21_proven','economic_edge_proven','historical_costs_proven','native_ctrader_runtime_reception')),'LIMITS')
 need(digest((ROOT/'research_core_v4/laboratory/INNOVATION_ACCOUNT_DEVELOPMENT_V1.json').read_bytes())==m['spec_sha256'],'FROZEN_SPEC')
 return {'run_id':r['run_id'],'disposition':r['disposition'],'original_ciphertext_and_evaluator_verified':True,'algorithm_reexecuted':False,'orders':0}
if __name__=='__main__':print(json.dumps(verify(),sort_keys=True))
