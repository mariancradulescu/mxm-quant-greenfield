"""Full1120/1155 fictional persisted evidence; no probe or broker is run."""
import copy,gzip,json,shutil,tempfile,unittest,zipfile,socket
from pathlib import Path
from unittest.mock import patch
import V4_QUOTE_SUPPORT_PRIVATE_PROOF_VERIFY as verifier
from research_core_v4.quote_probe_transport_v1 import seal,EVENT_ORDER
from research_core_v4.quote_probe_support_v1 import count_support
from tools.build_v4_private_proof_package import build
ROOT=Path(__file__).resolve().parents[1]
C=verifier.canonical
H=verifier.sha
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(C(seal(v)))
def update_authority(root,a):
 p=root/'PRIVATE_PROOF_AUTHORITY_V1.json';p.write_bytes(C(a)+b'\n');m=root/'PRIVATE_PROOF_PACKAGE_MANIFEST.json';body=json.loads(m.read_bytes());body['file_sha256'][p.name]=H(p.read_bytes());m.write_bytes(C(body)+b'\n')
def create_fixture(base):
 root=base/'MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1';private=base/'private';private.mkdir();archive=base/'overlay.zip'
 with zipfile.ZipFile(ROOT.parent/'MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1_RECOVERY_FINAL.zip') as z:z.extractall(base)
 build(ROOT,archive)
 with zipfile.ZipFile(archive) as z:z.extractall(base)
 plan=json.loads((root/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json').read_bytes());w=root/'DEVICE_LOCAL_PROBE_RAW'/verifier.PLAN_SHA;w.mkdir(parents=True)
 (private/('v4_probe_'+verifier.PLAN_SHA+'.lock')).write_bytes(b'')
 registry={'plan_sha256':verifier.PLAN_SHA,'folder_sha256':H(str(root.resolve()).encode()),'logical_execution_count':1};put(private/('v4_probe_'+verifier.PLAN_SHA+'.json'),registry)
 wires=[];attempts=[];outcomes=[]
 def wire(s,lo,hi,depth,rows,more=False):
  q={'attempt_index':len(wires),'request_id':s['request_id'],'from_ms':lo,'to_ms':hi,'depth':depth,'retry_index':0,'status':'SENT_OR_ACK_UNKNOWN'}
  o=dict(q,status='RECEIVED',returned_ticks=len(rows),has_more=more,latency_seconds=0.1);attempts.append(C(seal(q))+b'\n');outcomes.append(C(seal(o))+b'\n');wires.append(o);return o
 first=plan['slots'][0];wire(first,first['from_ms'],first['to_ms'],0,[[first['from_ms']+i,100000+i%3] for i in range(66)])
 records=[];payloads={}
 def node(s,lo,hi,depth,rows,split=False):
  t=wire(s,lo,hi,depth,rows,split);r={'request_id':s['request_id'],'from_ms':lo,'to_ms':hi,'depth':depth,'trace':t,'event_order':EVENT_ORDER,'status':'SPLIT' if split else 'LEAF'}
  if not split:r['rows']=rows
  p=w/'nodes'/s['request_id']/f'{lo}_{hi}.json.gz';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(C(seal(r)),mtime=0));return t
 for i,s in enumerate(plan['slots']):
  rid=s['request_id'];lo,hi=s['from_ms'],s['to_ms'];rows=[[lo+j,100000+j%3] for j in range(66)] if i==0 else [[lo+10,100000+i]] if i in [30,31] else []
  if 1<=i<=17:
   mid=(lo+hi)//2;traces=[node(s,lo,hi,0,[],True),node(s,lo,mid,1,[]),node(s,mid+1,hi,1,[])]
  else:traces=[node(s,lo,hi,0,rows)]
  payload={'request_id':rid,'plan_sha256':verifier.PLAN_SHA,'status':'COMPLETE' if rows else 'EMPTY','event_order':EVENT_ORDER,'rows':rows,'traces':traces};plain=C(seal(payload));blob=gzip.compress(plain,mtime=0);p=w/'raw'/(rid+'.json.gz');p.parent.mkdir(exist_ok=True);p.write_bytes(blob)
  record={'request_id':rid,'plan_sha256':verifier.PLAN_SHA,'raw_path':'raw/'+rid+'.json.gz','raw_sha256':H(blob),'compressed_bytes':len(blob),'uncompressed_bytes':len(plain),'ticks':len(rows),'status':payload['status'],'traces':traces,'has_more_count':sum(t['has_more'] for t in traces),'split_depth_max':max(t['depth'] for t in traces),'latency_seconds_received_pages':sum(t['latency_seconds'] for t in traces)};put(w/'completed'/(rid+'.json'),record);records.append(record);payloads[rid]=rows
 (w/'wire_attempts.jsonl').write_bytes(b''.join(attempts));(w/'wire_outcomes.jsonl').write_bytes(b''.join(outcomes))
 schedule={'status':'EXACT_FROZEN_WINDOWS_MATCH','mismatches':[],'identities_checked':56,'identity_week_windows_checked':560,'base_slot_count':1120};put(w/'current_schedule_preflight.json',schedule)
 put(w/'terminal_transport_stop.json',{'status':'TRANSPORT_ARCHITECTURE_NOT_FEASIBLE_AS_CURRENTLY_CONFIGURED','request_id':verifier.FIRST,'automatic_retry_authorized':False});put(w/'active_seconds.json',{'active_seconds':719.123456789})
 originals={n:(w/n).read_bytes() for n in verifier.CONTROL};originals['wire_attempts.jsonl']=attempts[0];originals['wire_outcomes.jsonl']=outcomes[0];originals['active_seconds.json']=C(seal({'active_seconds':5.563847219}))
 for n,b in originals.items():p=w/'ORIGINAL_DECODER_STOP_EVIDENCE'/n;p.parent.mkdir(exist_ok=True);p.write_bytes(b)
 recovery=(root/'research_core_v4/state/DECODER_RECOVERY_AUTHORITY_V1.json').read_bytes();first_node=w/'nodes'/verifier.FIRST/f"{first['from_ms']}_{first['to_ms']}.json.gz"
 put(w/'decoder_recovery_binding.json',{'schema':'mxm.v4.exact-device-decoder-recovery-binding.v2','authority_sha256':H(recovery),'folder_binding':registry,'private_registry_sha256':H((private/('v4_probe_'+verifier.PLAN_SHA+'.json')).read_bytes()),'replacement_consumed':True,'payload_equality_proven':False,'replacement_request_sha256':'a'*64,'original_attempts_charged':1,'original_active_seconds_charged':5.563847219,'original_file_sha256':{n:H(b) for n,b in originals.items()},'authorized_current_schedule_sha256':H((w/'current_schedule_preflight.json').read_bytes()),'replacement_node_sha256':H(first_node.read_bytes())})
 groups={}
 for s in plan['slots']:groups.setdefault((s['symbol_id'],s['week_index']),{})[s['side']]=s
 matrix=[]
 for (sid,wi),sides in sorted(groups.items()):
  bid,ask=sides['BID'],sides['ASK'];row={'symbol_id':sid,'asset_class':bid['asset_class'],'week_index':wi,'singleton_transport_only':bid['transport_only_singleton']}
  if bid['transport_only_singleton']:
   row['status']='SINGLETON_TRANSPORT_ONLY_NO_FEATURE_COUNTS';row['support']={'cells':[{'cell_id':f'L{l}_I{i}_H{h}_{d}','nonoverlap_attempts':None,'timestamp_completable_attempts':None,'status':'UNOBSERVED_'+row['status']} for l in [10,30] for i in [0.6,0.8] for h in [10,30,90] for d in ['CONTINUATION','REVERSION']],'response_values_read':False}
  else:row['status']='SUPPORT_COUNTS_ONLY';row['support']=count_support(payloads[bid['request_id']],payloads[ask['request_id']],bid['signal_from_ms'],bid['signal_to_ms'])
  matrix.append(row)
 raw=[{k:r[k] for k in ['request_id','raw_path','raw_sha256','compressed_bytes','uncompressed_bytes','ticks','status']} for r in records]
 files={'SUPPORT_ONLY_MATRIX.json':C(matrix)+b'\n','TRANSPORT_METRICS.json':C({'logical_requests':records,'wire_attempts':wires})+b'\n','LOCAL_RAW_CHUNK_SHA256_MANIFEST.json':C(raw)+b'\n','SCHEDULE_PREFLIGHT.json':C(schedule)+b'\n','PROBE_EXECUTION_MANIFEST.json':C({'status':'fictional'})+b'\n'}
 a=json.loads((root/'PRIVATE_PROOF_AUTHORITY_V1.json').read_bytes());a['compact_file_sha256']={n:H(b) for n,b in files.items()};update_authority(root,a)
 return root,private,plan
class PrivateProofTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.base=tempfile.TemporaryDirectory();cls.root0,cls.private0,cls.plan=create_fixture(Path(cls.base.name))
 @classmethod
 def tearDownClass(cls):cls.base.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);b=Path(self.tmp.name);self.root=b/self.root0.name;self.private=b/'private';shutil.copytree(self.root0,self.root);shutil.copytree(self.private0,self.private)
  registry=self.private/('v4_probe_'+verifier.PLAN_SHA+'.json');body=verifier.sealed(registry.read_bytes());body['folder_sha256']=H(str(self.root.resolve()).encode());put(registry,body)
  self.w=self.root/'DEVICE_LOCAL_PROBE_RAW'/verifier.PLAN_SHA;p=self.w/'decoder_recovery_binding.json';v=verifier.sealed(p.read_bytes());v['folder_binding']=body;v['private_registry_sha256']=H(registry.read_bytes());put(p,v)
 def state(self):return {str(p.relative_to(self.w)):H(p.read_bytes()) for p in self.w.rglob('*') if p.is_file()}
 def runproof(self):return verifier.run(self.root,self.private,progress=lambda _:None)
 def fails(self):
  before=self.state()
  with self.assertRaises(Exception):self.runproof()
  self.assertEqual(self.state(),before);self.assertFalse((self.root/'RETURN_PRIVATE_PROOF'/verifier.OUTPUT).exists())
 def test_complete1120_pass_no_prices_and_immutable(self):
  before=self.state()
  with patch('research_core_v4.quote_metadata_android_v1.MetadataTransport',side_effect=AssertionError('transport forbidden')) as t, patch('m6.ctrader_transport.StdlibCTraderTransport',side_effect=AssertionError('broker forbidden')) as b, patch('m6.pydroid_oauth.ensure_v2_authorization',side_effect=AssertionError('OAuth forbidden')) as oauth:
   output=self.runproof();self.assertEqual(t.call_count,0);self.assertEqual(b.call_count,0);self.assertEqual(oauth.call_count,0)
  self.assertEqual(self.state(),before)
  with zipfile.ZipFile(output) as z:
   self.assertEqual(len(z.namelist()),7);m=json.loads(z.read('PRIVATE_PROOF_MANIFEST.json'));self.assertTrue(m['lossless_reconstruction']);self.assertTrue(m['support_matrix_hash_match']);self.assertEqual(m['network_calls'],0)
   for name in z.namelist():
    if name.endswith('.json'):
     from research_core_v4.pydroid_quote_probe_v1 import reject_quote_export
     from research_core_v4.quote_metadata_android_v1 import reject_sensitive_keys
     value=json.loads(z.read(name));reject_quote_export(value);reject_sensitive_keys(value)
 def test_corrupt_raw(self):(next((self.w/'raw').iterdir())).write_bytes(b'corrupt');self.fails()
 def test_corrupt_completed(self):(next((self.w/'completed').iterdir())).write_bytes(b'corrupt');self.fails()
 def test_corrupt_node(self):next((self.w/'nodes').rglob('*.gz')).write_bytes(b'corrupt');self.fails()
 def test_missing_node(self):next((self.w/'nodes').rglob('*.gz')).unlink();self.fails()
 def test_altered_attempt(self):
  p=self.w/'wire_attempts.jsonl';lines=p.read_bytes().splitlines();v=verifier.sealed(lines[2]);v['retry_index']=1;lines[2]=C(seal(v));p.write_bytes(b'\n'.join(lines)+b'\n');self.fails()
 def test_altered_outcome(self):
  p=self.w/'wire_outcomes.jsonl';lines=p.read_bytes().splitlines();v=verifier.sealed(lines[2]);v['latency_seconds']=1.0;lines[2]=C(seal(v));p.write_bytes(b'\n'.join(lines)+b'\n');self.fails()
 def test_extra_completed(self):(self.w/'completed'/('0'*64+'.json')).write_bytes(b'{}');self.fails()
 def test_missing_completed(self):next((self.w/'completed').iterdir()).unlink();self.fails()
 def test_wrong_raw_sha(self):
  p=next((self.w/'completed').iterdir());v=verifier.sealed(p.read_bytes());v['raw_sha256']='0'*64;put(p,v);self.fails()
 def test_node_raw_price_mismatch_same_tick_count(self):
  s=self.plan['slots'][30];p=self.w/'nodes'/s['request_id']/f"{s['from_ms']}_{s['to_ms']}.json.gz";v=verifier.sealed(gzip.decompress(p.read_bytes()));v['rows'][0][1]+=1;p.write_bytes(gzip.compress(C(seal(v)),mtime=0));self.fails()
 def test_matrix_recomputation_hash_mismatch(self):
  a=json.loads((self.root/'PRIVATE_PROOF_AUTHORITY_V1.json').read_bytes());a['compact_file_sha256']['SUPPORT_ONLY_MATRIX.json']='0'*64;update_authority(self.root,a);self.fails()
 def test_network_path_fails_even_if_caught(self):
  original=count_support
  def attempted(*args):
   try:socket.socket()
   except Exception:pass
   return original(*args)
  with patch('research_core_v4.quote_probe_support_v1.count_support',side_effect=attempted):self.fails()
 def test_existing_evidence_write_fails_even_if_caught(self):
  original=count_support
  def attempted(*args):
   try:(self.w/'active_seconds.json').write_bytes(b'changed')
   except Exception:pass
   return original(*args)
  with patch('research_core_v4.quote_probe_support_v1.count_support',side_effect=attempted):self.fails()
 def test_oauth_private_cache_read_denied(self):
  original=count_support;p=self.private/'app_credentials.json';p.write_bytes(b'fictional private credential')
  def attempted(*args):p.read_bytes();return original(*args)
  with patch('research_core_v4.quote_probe_support_v1.count_support',side_effect=attempted):self.fails()
 def test_price_field_export_rejected(self):
  with self.assertRaises(verifier.ProofError):verifier.proof_sanitized({'price':100000})
  with self.assertRaises(verifier.ProofError):verifier.proof_sanitized({'client_secret':'fictional'})
 def test_output_symlink_to_evidence_rejected(self):
  (self.root/'RETURN_PRIVATE_PROOF').symlink_to(self.w,target_is_directory=True);self.fails()
 def test_changed_original_stop(self):
  put(self.w/'terminal_transport_stop.json',{'status':'OTHER'});self.fails()
 def test_changed_original_archive(self):
  put(self.w/'ORIGINAL_DECODER_STOP_EVIDENCE'/'active_seconds.json',{'active_seconds':5.56});self.fails()
 def test_later_terminal_stop(self):put(self.w/'terminal_recovery_stop.json',{'status':'STOP'});self.fails()
if __name__=='__main__':unittest.main()
