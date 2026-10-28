"""Verify exact original archive and delivered observer; no key, broker or model run."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DIR=ROOT/'docs/economic-development/20261028/commodity-anchor-40709936368'
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(base=DIR):
 m=json.loads((base/'manifest.json').read_bytes());raw=(base/'runtime-original.zip').read_bytes()
 if len(raw)!=m['bytes'] or sha(raw)!=m['sha256']:raise ValueError('ORIGINAL_ARCHIVE')
 with zipfile.ZipFile(base/'runtime-original.zip') as z:
  if sorted(z.namelist())!=sorted(m['members']):raise ValueError('ORIGINAL_MEMBERS')
  if sum(x.file_size for x in z.infolist())>20000000:raise ValueError('ORIGINAL_BOUND')
  b={p:z.read(p) for p in m['members']}
 for p,v in m['members'].items():
  if len(b[p])!=v['bytes'] or sha(b[p])!=v['sha256']:raise ValueError('ORIGINAL_MEMBER_'+p)
 r=json.loads(b['receipt.json']);p=json.loads(b['producer.json']);c=json.loads(b['cache.json']);cold=json.loads(b['cold.json'])
 if r!=json.loads((base/'logged-receipt.json').read_bytes()):raise ValueError('LOGGED_RESULT')
 if r['run_id']!=40709936368 or r['source_sha']!='88c2907a125581cb6c6b84654565688cb91a2db5' or r['spec_sha256']!='f135ebf57cee3302f70e399695ec7dff40123fed3d2c3996933b5727a016f7e1':raise ValueError('RESULT_IDENTITY')
 if r['disposition']!='SOURCE_NOT_ADMITTED' or r['models_executed']!=0 or r['initial_funding_count']!=0 or r['native_h1_requests']!=0 or r['metadata_requests']!=3 or r['orders']!=0 or r['gates']!={}:raise ValueError('NO_MODEL_OUTCOME')
 for name,key in [('source.mxmenc','source_sha256'),('result.mxmenc','cipher_sha256'),('evaluator.dll','evaluator_sha256'),('cache-input.mxmenc','cache_input_sha256')]:
  if sha(b[name])!=r[key]:raise ValueError('RESULT_MEMBER_BINDING')
 if p['failure_code']!='LAB_ANCHOR_EXACT_USD_IDENTITIES' or p['complete'] or p['request_counts']!={'panel':3} or p['rows']!={} or p['cipher_sha256']!=r['source_sha256']:raise ValueError('PRODUCER_STOP')
 if c['existing_source_overlap_rows']!={'1':545,'250':521} or c['predecessor_run']!=40707021640 or c['cache_input_sha256']!=r['cache_input_sha256']:raise ValueError('CACHE_BINDING')
 if cold['original_readback'] is not True or cold['model_reexecuted'] or cold['cipher_sha256']!=r['cipher_sha256']:raise ValueError('COLD_ORIGINAL')
 package=ROOT/'docs/cloud-recovery/20261028/native-observation-package'
 receipt=json.loads((package/'logged-receipt.json').read_bytes())
 if len((package/'MxmNativeObservation.algo').read_bytes())!=83337 or sha((package/'MxmNativeObservation.algo').read_bytes())!=receipt['package_sha256'] or receipt['package_sha256']!='897e4f55aae5d2a646e6bf9e0984528761dc7c9c34b56222eb5e64dbde7d116c':raise ValueError('COMPILED_PACKAGE')
 if sha((package/'reception-request.json').read_bytes())!=receipt['request_sha256'] or receipt['native_callbacks_received'] or receipt['cloud_activated'] or receipt['orders']!=0:raise ValueError('OBSERVATION_UNRECEIVED')
 return {'originals_verified':True,'run':r['run_id'],'models':0,'orders':0,'cloud':False}
if __name__=='__main__':
 import sys
 if sys.argv[1:]==['--self-test']:
  import shutil,tempfile
  verify()
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp)/'original';shutil.copytree(DIR,d);f=d/'runtime-original.zip';b=bytearray(f.read_bytes());b[len(b)//2]^=1;f.write_bytes(b)
   try:verify(d)
   except ValueError:pass
   else:raise AssertionError('CORRUPT_ARCHIVE_ACCEPTED')
  print(json.dumps({'originals':verify(),'corrupt_archive_rejected':True,'model_reexecuted':False}))
 elif not sys.argv[1:]:print(json.dumps(verify()))
 else:raise ValueError('OFFLINE_VERIFIER_ARGUMENT')
