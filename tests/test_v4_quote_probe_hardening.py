"""Adversarial pre-device proofs. Fictional protobufs only, no broker sockets."""
import copy,gzip,json,math,statistics,tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import date,datetime,timezone
from research_core_v4.quote_probe_transport_v1 import decode_ticks,seal,unseal,atomic
from research_core_v4.quote_probe_support_v1 import count_support,_side
from research_core_v4.quote_probe_schedule_preflight_v1 import day_intervals,materialize,preflight
from research_core_v4.pydroid_quote_probe_v1 import logical_capture,reject_quote_export
from research_core_v4.quote_probe_plan_v1 import canonical
from tests import test_v4_quote_support_probe as prior
from tests.test_v4_quote_support_probe import TickBroker,PLAN,ROOT,SmallMetadata,Clock
from m6.ctrader_proto import OpenApiMessages_pb2 as oa
from tests.test_v4_android_current_metadata import FAKE_AID

# Deliberately independent linear stream walk / direct event sums. No production
# feature/mask helper, bisect or optimized revision arrays reused.
def reference(bid,ask,start,end):
    grids={};pointers=[-1,-1];revision=[[],[]]
    for k,rows in enumerate([bid,ask]):
        for i in range(1,len(rows)):
            t,p=rows[i];old=rows[i-1][1]
            if t<end and p!=old:revision[k].append((t,1 if p>old else -1))
    for t in range(start-60000,end,1000):
        vals=[]
        for k,rows in enumerate([bid,ask]):
            while pointers[k]+1<len(rows) and rows[pointers[k]+1][0]<=t:pointers[k]+=1
            i=pointers[k]
            if i<0 or t-rows[i][0]>2000:break
            vals.append(rows[i][1])
        grids[t]=None if len(vals)!=2 or not vals[1]>=vals[0]>0 else ((vals[0]+vals[1])/2,math.log(vals[1]/vals[0])*10000)
    # Reference bins preserve all same-ms changes and sum interval(t-L,t].
    bins={}
    for events in revision:
        for t,d in events:bins.setdefault(t,[0,0])[0 if d>0 else 1]+=1
    signals={(l,i):[] for l in [10,30] for i in [.6,.8]}
    for t in range(start,end,1000):
        cur=grids[t]
        spreads=[grids[q][1] for q in range(t-60000,t,1000) if grids[q] is not None]
        if cur is None or len(spreads)<45:continue
        base=statistics.median(spreads)
        if base<=0 or cur[1]>base:continue
        for l in [10,30]:
            old=grids[t-l*1000]
            if old is None:continue
            counts=[sum(v[k] for q,v in bins.items() if t-l*1000<q<=t) for k in [0,1]]
            n=sum(counts)
            if n<6 or abs(math.log(cur[0]/old[0])*10000)/base>.75:continue
            for i in [.6,.8]:
                if abs(counts[0]-counts[1])/n>=i:signals[l,i].append(t)
    # Independent endpoint timestamp pointer, never accesses future prices.
    stamp=[sorted(set(t for t,p in rows)) for rows in [bid,ask]]
    import bisect
    def available(t):
        for ts in stamp:
            idx=bisect.bisect_right(ts,t)-1
            if idx<0 or t-ts[idx]>2000:return False
        return True
    cells=[]
    for l in [10,30]:
        for i in [.6,.8]:
            for h in [10,30,90]:
                attempts=[];complete=[];next_time=-1
                for t in signals[l,i]:
                    if t<next_time:continue
                    attempts.append(t);next_time=t+(h+1)*1000
                    if available(t+1000) and available(t+(h+1)*1000):complete.append(t)
                for d in ['CONTINUATION','REVERSION']:
                    cells.append(dict(cell_id=f'L{l}_I{i}_H{h}_{d}',trigger_occurrences=len(signals[l,i]),nonoverlap_attempts=len(attempts),timestamp_completable_attempts=len(complete),retention_fraction_timestamp_only=len(complete)/len(attempts) if attempts else None,attempts_three_subwindows=[sum(start+k*1200000<=t<start+(k+1)*1200000 for t in attempts) for k in range(3)],timestamp_completable_three_subwindows=[sum(start+k*1200000<=t<start+(k+1)*1200000 for t in complete) for k in range(3)],attempt_seconds_mask_hex=hex(sum(1<<((t-start)//1000) for t in attempts)),timestamp_completable_mask_hex=hex(sum(1<<((t-start)//1000) for t in complete)),scientific_support_gate_evaluated=False))
    return cells

def stream(scale=1):
    # All events at each1sec tie retain repeated unchanged and up/down revisions.
    bid=[];ask=[]
    for t in range(60000,3826000,1000):
        prices=[100000,100001,100001,100002,100003,100004,100005,100006,100007,100008,100009,100010,100010,100000]
        bid.extend([t,p*scale] for p in prices);ask.extend([t,(p+20)*scale] for p in prices)
    return bid,ask

class HardenedProof(unittest.TestCase):
 def tr(self,broker,slot=None,work=None):return prior.ProbeProof.tr(self,broker,slot,work)
 def test_multiple_ties_and_unchanged_revisions_latest(self):
  ticks=[SimpleNamespace(timestamp=1000,tick=12),SimpleNamespace(timestamp=0,tick=10),SimpleNamespace(timestamp=0,tick=10),SimpleNamespace(timestamp=0,tick=11),SimpleNamespace(timestamp=5,tick=9)]
  rows=decode_ticks(ticks,995,1000);self.assertEqual(rows,[[995,9],[1000,11],[1000,10],[1000,10],[1000,12]])
  ts,up,down,_=_side(rows);self.assertEqual(up,[1000,1000]);self.assertEqual(down,[1000]);self.assertEqual(rows[-1][1],12)
 def test_all24_counts_masks_exact_independent_reference_with_ties(self):
  b,a=stream();actual=count_support(b,a,120000,3720000)
  self.assertEqual(actual['cells'],reference(b,a,120000,3720000));self.assertEqual(actual['ambiguous_causal_seconds'],0)
  self.assertTrue(all(c['timestamp_completable_attempts']>=15 for c in actual['cells']))
 def test_gzip_order_replay_identical(self):
  b,a=stream();b2=json.loads(gzip.decompress(gzip.compress(canonical(b),mtime=0)))
  self.assertEqual(b,b2);self.assertEqual(count_support(b,a,120000,3720000),count_support(b2,a,120000,3720000))
 def test_support_evidence_not_invertible_to_prices(self):
  b,a=stream();x,y=stream(2)
  self.assertNotEqual(b,x);self.assertNotEqual(a,y)
  self.assertEqual(count_support(b,a,120000,3720000),count_support(x,y,120000,3720000))
  # Future horizon price magnitudes can independently vary after signal window.
  y=[[t,p if t<3720000 else p*3] for t,p in y]
  self.assertEqual(count_support(b,a,120000,3720000),count_support(x,y,120000,3720000))
 def test_ties_leaf_reconstruction_and_resume(self):
  slot=copy.deepcopy(PLAN['slots'][0]);slot.update(from_ms=1000,to_ms=1001)
  broker=TickBroker();calls=[]
  def request(msg):
   lo,hi=int(msg.fromTimestamp),int(msg.toTimestamp);calls.append((lo,hi));res=oa.ProtoOAGetTickDataRes(ctidTraderAccountId=FAKE_AID,hasMore=lo<hi)
   for stamp,price in [(hi,3),(0,3),(0,2),(0,1)]:res.tickData.add(timestamp=stamp,tick=price)
   return res
  broker.request=request;tr,slot,c=self.tr(broker,slot)
  expected=[[1000,1],[1000,2],[1000,3],[1000,3],[1001,1],[1001,2],[1001,3],[1001,3]]
  self.assertEqual(tr.capture(slot)[0],expected);n=len(calls);self.assertEqual(tr.capture_cached(slot)[0],expected);self.assertEqual(len(calls),n)
 def test_every_error_fails_closed_including_retryafter(self):
  for code in ['BLOCKED_PAYLOAD_TYPE','REQUEST_FREQUENCY_EXCEEDED','SERVER_UNAVAILABLE','MAINTENANCE','SYMBOL_NOT_FOUND','INCORRECT_BOUNDARIES','ACCOUNT_NOT_AUTHORIZED','UNKNOWN_PROTOCOL']:
   with self.subTest(code=code):
    broker=TickBroker();broker.request=lambda m:oa.ProtoOAErrorRes.FromString(oa.ProtoOAErrorRes(errorCode=code).SerializeToString()+b'\x30\x1e') # official retryAfter field6, older bound proto preserves unknown wire field
    tr,s,c=self.tr(broker)
    with self.assertRaises(PermissionError):tr.capture(s)
    self.assertEqual(len(tr.attempts),1);self.assertEqual(tr.attempts[0]['status'],'BROKER_ERROR_FAIL_CLOSED')
    self.assertFalse(list((tr.workdir/'nodes').rglob('*.gz')))
 def test_empty_success_is_empty_not_unavailable(self):
  tr,s,c=self.tr(TickBroker());record=logical_capture(tr,s,tr.workdir)
  self.assertEqual(record['status'],'EMPTY');self.assertEqual(record['ticks'],0)
 def test_internal_checkpoint_mutation_rejected_before_request(self):
  s=copy.deepcopy(PLAN['slots'][0]);s.update(from_ms=1000,to_ms=1003)
  tr,s,c=self.tr(TickBroker('SPLIT'),s);tr.capture(s);n=len(tr.attempts)
  path=tr.workdir/'nodes'/s['request_id']/'1000_1003.json.gz';payload=json.loads(gzip.decompress(path.read_bytes()));payload['trace']['returned_ticks']=99
  path.write_bytes(gzip.compress(canonical(payload)))
  with self.assertRaises(PermissionError):tr.capture(s)
  self.assertEqual(len(tr.attempts),n)
 def test_missing_completed_leaf_no_redownload(self):
  tr,s,c=self.tr(TickBroker());logical_capture(tr,s,tr.workdir);n=len(tr.attempts)
  next((tr.workdir/'nodes').rglob('*.gz')).unlink()
  with self.assertRaises(PermissionError):logical_capture(tr,s,tr.workdir)
  self.assertEqual(len(tr.attempts),n)
 def test_orphan_raw_mutation_rejected_before_request(self):
  tr,s,c=self.tr(TickBroker());r=logical_capture(tr,s,tr.workdir);n=len(tr.attempts)
  (tr.workdir/'completed'/f"{s['request_id']}.json").unlink();p=tr.workdir/r['raw_path'];body=json.loads(gzip.decompress(p.read_bytes()));body['rows']=[[s['from_ms'],1]];p.write_bytes(gzip.compress(canonical(body)))
  with self.assertRaises(PermissionError):logical_capture(tr,s,tr.workdir)
  self.assertEqual(len(tr.attempts),n)
 def test_journal_corruption_rejected(self):
  tr,s,c=self.tr(TickBroker());tr.capture(s);p=tr.journal;line=json.loads(p.read_bytes());line['depth']=9;p.write_bytes(canonical(line)+b'\n')
  with self.assertRaises(PermissionError):self.tr(TickBroker(),s,tr.workdir)
 def test_raw_price_keys_rejected(self):
  for key in ['rows','price','tick','bid','ask','response_price','future_price']:
   with self.assertRaises(PermissionError):reject_quote_export({'nested':{key:123}})
 def full(self,tz='UTC'):
  return dict(scheduleTimeZone=tz,schedule=[dict(startSecond=86400,endSecond=172800)],holiday=[])
 def test_holiday_own_zone_changes_utc_cut(self):
  full=self.full();day=date(2025,9,15);hd=(day-date(1970,1,1)).days
  full['holiday']=[dict(holidayDate=hd,isRecurring=False,scheduleTimeZone='America/New_York',startSecond=0,endSecond=0)]
  intervals=day_intervals(full,day);self.assertEqual(intervals,[(datetime(2025,9,15,tzinfo=timezone.utc),datetime(2025,9,15,4,tzinfo=timezone.utc))])
 def test_holiday_missing_or_invalid_timezone_rejected(self):
  full=self.full();full['holiday']=[dict(holidayDate=20346,isRecurring=False)]
  with self.assertRaises(ValueError):day_intervals(full,date(2025,9,15))
  full['holiday'][0]['scheduleTimeZone']='Invalid/Timezone'
  with self.assertRaises((ValueError,KeyError)):day_intervals(full,date(2025,9,15))
 def test_dst_nonexistent_and_ambiguous_holiday_boundaries_fail(self):
  for day,seconds in [(date(2025,3,9),2*3600+30*60),(date(2025,11,2),3600+30*60)]:
   full=self.full();full['holiday']=[dict(holidayDate=(day-date(1970,1,1)).days,isRecurring=False,scheduleTimeZone='America/New_York',startSecond=seconds,endSecond=seconds+60)]
   with self.assertRaises(ValueError):day_intervals(full,day)
 def test_recurring_holiday_and_weekday_cycle(self):
  full=self.full();full['holiday']=[dict(holidayDate=(date(2020,9,15)-date(1970,1,1)).days,isRecurring=True,scheduleTimeZone='UTC',startSecond=0,endSecond=0)]
  self.assertEqual(materialize(full,'2025-09-15',0)['status'],'NO_WINDOW')
 def test_preflight_mismatch_only_metadata_and_plan_unchanged(self):
  class Meta:
   def __init__(self):self.calls=[]
   def request(self,req):
    self.calls.append(type(req).__name__);r=oa.ProtoOASymbolByIdRes(ctidTraderAccountId=FAKE_AID)
    r.symbol.add(symbolId=req.symbolId[0],digits=5,pipPosition=4,scheduleTimeZone='UTC');return r
  m=Meta();before=canonical(PLAN);report=preflight(m,FAKE_AID,PLAN)
  self.assertEqual(m.calls,['ProtoOASymbolByIdReq']*56);self.assertEqual(report['status'],'STOP_BEFORE_HISTORICAL_SCHEDULE_MISMATCH');self.assertEqual(report['historical_requests_sent'],0);self.assertEqual(canonical(PLAN),before)
 def test_preflight_exact_calendar_matches_without_history(self):
  from google.protobuf.json_format import ParseDict
  import base64,zlib
  d=json.loads(zlib.decompress(base64.b64decode((ROOT/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64').read_bytes())))
  byid={r['symbol_id']:r['current_full_metadata'] for r in d['rows']}
  class Meta:
   def request(self,req):
    full=copy.deepcopy(byid[req.symbolId[0]])
    for h in full.get('holiday',[]):h['scheduleTimeZone']=full['scheduleTimeZone'] # fictional equality case only
    out=oa.ProtoOASymbolByIdRes(ctidTraderAccountId=FAKE_AID);ParseDict(full,out.symbol.add());return out
  self.assertEqual(preflight(Meta(),FAKE_AID,PLAN)['status'],'EXACT_FROZEN_WINDOWS_MATCH')
 def test_private_registry_same_folder_resume_other_folder_rejected(self):
  from research_core_v4.pydroid_quote_probe_v1 import claim_device_execution
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);claim_device_execution(root/'private',root/'deploy',PLAN);claim_device_execution(root/'private',root/'deploy',PLAN)
   with self.assertRaises(PermissionError):claim_device_execution(root/'private',root/'other',PLAN)
 def test_new_transport_resume_validates_tied_leaf(self):
  s=copy.deepcopy(PLAN['slots'][0]);s.update(from_ms=1000,to_ms=1001)
  broker=TickBroker('SPLIT');tr,s,c=self.tr(broker,s);rows,_=tr.capture(s);n=len(broker.tick_calls)
  newer,s,c=self.tr(broker,s,tr.workdir);self.assertEqual(newer.capture_cached(s)[0],rows);self.assertEqual(len(broker.tick_calls),n)
 def test_common_channel_error_fail_closed(self):
  from m6.ctrader_proto import OpenApiCommonMessages_pb2 as common
  broker=TickBroker();broker.request=lambda m:common.ProtoErrorRes(errorCode='REQUEST_FREQUENCY_EXCEEDED')
  tr,s,c=self.tr(broker)
  with self.assertRaises(PermissionError):tr.capture(s)
 def test_durable_broker_failure_cannot_resume_as_empty(self):
  tr,s,c=self.tr(TickBroker('UNAVAILABLE'))
  with self.assertRaises(PermissionError):tr.capture(s)
  replacement=TickBroker()
  with self.assertRaises(PermissionError):self.tr(replacement,s,tr.workdir)
  self.assertFalse(replacement.tick_calls)
 def test_valid_self_checksum_with_wrong_node_trace_rejected(self):
  tr,s,c=self.tr(TickBroker());tr.capture(s);n=len(tr.attempts)
  path=next((tr.workdir/'nodes').rglob('*.gz'));body=unseal(json.loads(gzip.decompress(path.read_bytes())));body['trace']['returned_ticks']=99;path.write_bytes(gzip.compress(canonical(seal(body))))
  with self.assertRaises(PermissionError):tr.capture(s)
  self.assertEqual(len(tr.attempts),n)
 def test_return_real_price_chunks_stay_local(self):
  from research_core_v4.pydroid_quote_probe_v1 import compact_return
  from research_core_v4.quote_metadata_android_v1 import Secrets
  # Full manifest fictional records; one nonempty per-side quote pair, other
  # slots empty. No protocol calls and no imported scientific evaluator.
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);work=root/'raw-local';work.mkdir();records=[]
   for slot in PLAN['slots']:
    rows=[[slot['from_ms'],81234567+(slot['side']=='ASK')]] if slot['symbol_id']==PLAN['identities'][0]['symbol_id'] and slot['week_index']==0 else []
    payload=dict(request_id=slot['request_id'],plan_sha256=prior.PLAN_SHA,event_order='ordered',rows=rows,traces=[],status='COMPLETE' if rows else 'EMPTY')
    raw=gzip.compress(canonical(payload),mtime=0);path=work/(slot['request_id']+'.json.gz');path.write_bytes(raw)
    records.append(dict(request_id=slot['request_id'],raw_path=path.name,raw_sha256=prior.sha(raw),compressed_bytes=len(raw),uncompressed_bytes=len(gzip.decompress(raw)),ticks=len(rows),status=payload['status'],traces=[]))
   output=compact_return(root,work,PLAN,{'source_head':'SYNTHETIC','file_sha256':{},'device_authority_scope_sha256':'SYNTHETIC'},records,Secrets(),100,[],lambda _:None)
   with zipfile.ZipFile(output) as z:
    self.assertEqual(set(z.namelist()),{'PROBE_EXECUTION_MANIFEST.json','TRANSPORT_METRICS.json','SUPPORT_ONLY_MATRIX.json','LOCAL_RAW_CHUNK_SHA256_MANIFEST.json','SCHEDULE_PREFLIGHT.json','CHECKSUMS.sha256'})
    for n in z.namelist():
     raw=z.read(n);self.assertNotIn(b'81234567',raw);self.assertNotIn(b'81234568',raw)
     if n.endswith('.json'):reject_quote_export(json.loads(raw))
   self.assertEqual(len(list(work.glob('*.gz'))),1120)
 def test_official_timezone_field_retained_in_sanitizer(self):
  from research_core_v4.quote_metadata_android_v1 import sanitize
  from tests.test_v4_android_current_metadata import FRONT
  from research_core_v4.quote_scope_metadata_v1 import FINGERPRINT
  rows=[dict(i,status='METADATA_INSUFFICIENT',current_full_metadata={'holiday':[{'holidayDate':20346,'isRecurring':False,'scheduleTimeZone':'America/New_York'}]}) for i in FRONT]
  result=dict(rows=rows,schema='fixture',started_utc='fixture',completed_utc='fixture',account_fingerprint_sha256=FINGERPRINT,deposit_asset='EUR',source_environment='Pepperstone - Europe LIVE',historical_requests_sent=0,orders_sent=0,features_computed=False,responses_computed=False)
  self.assertEqual(sanitize(result,FRONT)['rows'][0]['current_full_metadata']['holiday'][0]['scheduleTimeZone'],'America/New_York')
 def test_device_run_schedule_stop_has_zero_historical_calls(self):
  from research_core_v4.pydroid_quote_probe_v1 import run_device
  from tests.test_v4_android_current_metadata import FakeOAuth
  from research_core_v4.quote_metadata_android_v1 import MetadataTransport
  from tools.build_v4_quote_probe_package import build as package
  broker=TickBroker();original=broker.request
  def request(msg):
   if type(msg) is oa.ProtoOASymbolsListReq:
    r=oa.ProtoOASymbolsListRes(ctidTraderAccountId=FAKE_AID)
    for i in PLAN['identities']:r.symbol.add(symbolId=i['symbol_id'],symbolName=i['symbol'],enabled=True)
    return r
   return original(msg) # fictional full metadata has mismatching UTC schedule
  broker.request=request;clock=Clock()
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);archive=base/'package.zip';package(ROOT,archive,ROOT.parent/'probe-wheels')
   with zipfile.ZipFile(archive) as z:z.extractall(base)
   deploy=base/'MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1'
   mt=lambda inner,o,secrets,progress:MetadataTransport(inner,o,secrets,progress=progress,clock=clock,sleep=clock.sleep)
   from research_core_v4.quote_scope_metadata_v1 import FINGERPRINT
   with patch('m6.ctrader_capture.account_fingerprint',return_value=FINGERPRINT),patch('research_core_v4.pydroid_quote_probe_v1.MetadataTransport',side_effect=mt):
    output=run_device(deploy,oauth=FakeOAuth(),transport_factory=lambda:broker,progress=lambda _:None,private_registry_root=base/'private')
   self.assertFalse(broker.tick_calls)
   with zipfile.ZipFile(output) as z:
    self.assertEqual(json.loads(z.read('PROBE_EXECUTION_MANIFEST.json'))['historical_requests_sent'],0);self.assertEqual(json.loads(z.read('SCHEDULE_PREFLIGHT.json'))['status'],'STOP_BEFORE_HISTORICAL_SCHEDULE_MISMATCH')
if __name__=='__main__':unittest.main()
