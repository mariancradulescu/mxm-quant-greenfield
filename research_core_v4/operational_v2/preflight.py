"""Outcome-blind machine preflight; broker connect is never called here."""
import argparse,gzip,hashlib,json,pathlib,os,sys,urllib.request,io
import numpy as np
from bank import R,P,C,core,sha,canonical,software_checks
from power import structural_support
from provider import ensure,put,REPO,BRANCH
S='research_core_v4/state/';F=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_INFERENCE_V2_DEPTH_IMPLEMENTATION_FREEZE_V1.json'
OLD='b80f8dba610153c91b051ffd5073ee3433e300c4'
def getold(path):
 assert path=='support_only_v1/checkpoint.json' or (path.startswith('support_only_v1/shards/') and path.endswith('.bin')) or path=='support_only_v1/results/event_masks.npz'
 return urllib.request.urlopen('https://raw.githubusercontent.com/'+REPO+'/'+OLD+'/'+path,timeout=60).read()
def frozen():
 f=json.loads((R/F).read_bytes())
 for p,h in f['files_sha256'].items():assert sha(R/p)==h,p
 return f

def software():
 from readonly import ReadOnlyTransport,ALLOWED
 from m6.ctrader_transport import encode_envelope
 from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage,ProtoHeartbeatEvent
 from research_core_v4 import shallow_m5_support_v2 as d,current_wave_support_worker_v1 as w
 from research_core_v4.shallow_m5_support_v2_boundary_v4 import RawTemporalGeometry,pagination_decision_v4
 checks={};v=software_checks();checks['v2_score_and_power_software']=v
 class Dummy:
  def __init__(self):self.sent=[]
  def sendall(self,b):self.sent.append(b)
 dummy=Dummy();tr=ReadOnlyTransport();tr._sock=dummy
 for pt in range(0,2300):
  if pt in ALLOWED:continue
  try:tr._send_bytes(encode_envelope(ProtoMessage(payloadType=pt,payload=b'')))
  except PermissionError:pass
  else:raise AssertionError('FORBIDDEN_PAYLOAD_SENT')
 assert not dummy.sent;checks['all_nonwhitelisted_payload_types_blocked_before_socket']=True
 tr._send_bytes(encode_envelope(ProtoHeartbeatEvent()));assert len(dummy.sent)==1;checks['heartbeat_only_mock_send']=True
 a=np.ones((84,261),bool);assert structural_support(a).all();a[:7]=False;assert not structural_support(a).any();checks['unchanged12block4perthird_support_gate']=True
 from masks import derive
 roster=[{'SYMBOL_ID':j+1,'BROKER_NATIVE_CONTEXT':'TEST','MASTER_ORDINAL':j+1} for j in range(3)]
 # Availability arithmetic uses immutable support window primitives directly.
 old=(w.G,w.START,w.END);w.G=8064;w.START=1787184000;w.END=w.START+8064*300
 bits=np.full(8064,31,np.uint8);m=w.own_masks(bits);assert not m['B'][0] and m['B'][12];checks['completed_baseline_window_no_forwardfill']=True
 row={'time_utc':'2026-08-20T00:00:00Z','open':'1.00','high':'2.00','low':'0.50','close':'1.50','tick_volume':'4'}
 # Actual accepted START is Aug20; use the worker's exact timestamp authority.
 w.START=w.timestamp(row['time_utc']);w.END=w.START+8064*300;k,flags=w.project(row,1,2);assert k==0 and flags==31;checks['accepted_boolean_projector_schema_grid_positivity']=True
 row['time_utc']='2026-08-20T00:01:00Z'
 try:w.project(row,1,2)
 except w.SupportError:pass
 else:raise AssertionError('OUT_OF_GRID_ACCEPTED')
 checks['off_grid_hard_fail']=True;w.G,w.START,w.END=old
 ctx=d.RequestContext('SYNTHETIC',1,3,1000000,2000000)
 g=RawTemporalGeometry(1,900000,900000,True,1,0,0,0,0,0);dec=pagination_decision_v4(ctx=ctx,geometry=g,has_more_present=True,has_more_value=True,page_index=1);assert dec.complete;checks['accepted_lower_overfetch_pagination_before_numeric_decode']=True
 cert=json.loads((R/(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_INFERENCE_V2_CERTIFICATION_RESULT_V1.json')).read_bytes());assert cert['all30_completed'] and len(cert['cells'])==30 and all(c['selected_wilson_upper']<=.05 and c['pass'] for c in cert['cells']);checks['all30_certification_cells_pass']=True
 cf=json.loads((R/C).read_bytes());assert cf['selected_k']==cert['selected_k']==15 and not cf['retuning_allowed'];checks['cutoff_frozen_and_unchanged']=True
 return checks

def execute(output):
 f=frozen();checks=software();needed=['CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN'];assert all(os.environ.get(x) for x in needed),'CTRADER_CREDENTIAL_UNAVAILABLE'
 assert os.environ.get('EXACT_TARGET'),'EXACT_TARGET_REQUIRED'
 # Only authenticated Github provider is exercised. No broker credentials are used.
 head=ensure(os.environ['EXACT_TARGET']);cpb=getold('support_only_v1/checkpoint.json');assert hashlib.sha256(cpb).hexdigest()==f['accepted_checkpoint_sha256'];cp=json.loads(cpb);assert cp['complete'] and len(cp['assets'])==100
 segments=[]
 for seg in range(4):
  rows=[]
  for sh in range(25):
   j=seg*25+sh;b=getold('support_only_v1/shards/'+f'{j:03d}'+'.bin');assert hashlib.sha256(b).hexdigest()==cp['assets'][j]['mask_sha256'];v=np.frombuffer(b,np.uint8).reshape(-1,2016);assert v.shape[0]==(64 if sh<24 else 40) and (v<=31).all();rows.append(v)
  segments.append(np.vstack(rows))
 raw=np.concatenate(segments,axis=1);roster=json.loads((R/(S+'MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json')).read_bytes())['entries'];ix=[e['MASTER_ORDINAL']-1 for e in roster];assert len(ix)==1575 and len(set(ix))==1575;valid=raw[ix].copy();raw=None
 # Recompute geometric joints from already accepted Boolean bytes and compare
 # directly with the original accepted event masks. No raw M5 is accessed.
 oldb=getold('support_only_v1/results/event_masks.npz');assert hashlib.sha256(oldb).hexdigest()=='26acadf914fbcd904badd2200186424bf54f485af09cf69e797bf837f0f3aba7'
 from masks import derive
 from datetime import datetime,timezone
 tmp=R/'preflight_mask_output';daily,geom=derive(valid,roster,int(datetime(2026,8,20,tzinfo=timezone.utc).timestamp()),tmp)
 with np.load(io.BytesIO(oldb)) as accepted,np.load(tmp/'event_masks.npz') as observed:
  for key in observed.files:
   oldkey=key.replace('frozen_peer_response_','peer_response_')
   if oldkey in accepted.files:assert np.array_equal(observed[key],accepted[oldkey]),key
 assert daily.shape==(0,261);checks['all1575_accounted_and_exact_old_joint_peer_masks_reproduced']=True;checks['raw_M5_or_encrypted_asset_bodies_read']=False
 summary={'schema':'mxm.operational-v2.machine-preflight-result.v1','status':'PASS','checks':checks,'unique_software_checks_passed':32,'mask_reconciliation_checks_passed':1,'tests_failed':0,'credential_presence_only':True,'broker_requests':0,'history_requests':0,'new_market_rows':0,'real_inputs':0,'orders':0,'original_available_at':'UNKNOWN_UNCHANGED','exact_target':os.environ['EXACT_TARGET'],'run_id':int(os.environ['GITHUB_RUN_ID']),'job':'readonly-machine-preflight','durable_branch':BRANCH,'initial_validity_shape':list(valid.shape),'initial_validity_sha256':hashlib.sha256(valid.tobytes()).hexdigest()}
 z=gzip.compress(valid.tobytes(),mtime=0);payload={'support_depth_v2/initial/validity.bin.gz':z,'support_depth_v2/preflight.json':canonical(summary)};head=put(head,payload,'Machine preflight only; durable accepted Boolean masks; broker untouched')
 assert head;summary['durable_head']=head;pathlib.Path(output).write_bytes(canonical(summary));print('PREFLIGHT_RESULT='+json.dumps(summary,sort_keys=True),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--software',action='store_true');a.add_argument('--output',default='preflight.json');args=a.parse_args()
 if args.software:print('SOFTWARE='+json.dumps(software(),sort_keys=True))
 else:execute(args.output)
