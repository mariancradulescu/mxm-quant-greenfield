"""Bounded authentic native M5 and BID/ASK collector; independent request counters."""
import time,base64,os,math
from collections import Counter
from datetime import datetime,timezone
from research_core_v4.wide_greenfield_v1.collect_v2 import Collector as Original
from research_core_v4.native_executable_qualification_v1.runner_v1 import need,sha
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m,enums
from research_core_v4 import shallow_m5_support_v2 as v2
from research_core_v4.native_executable_qualification_v1.runner_v1 import HistoryReceiptTransport
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment
class Collector(Original):
 def __init__(self,caps):super().__init__();self.caps=caps;self.receipts=[];self.wire_types=Counter()
 def connect(self):
  self.tr=HistoryReceiptTransport(response_timeout=30);original=self.tr.request
  def counted(req,*args,**kw):
   self.wire_types[type(req).__name__]+=1
   return original(req,*args,**kw)
  self.tr.request=counted;self.tr.connect()
  self.aid=authenticate_segment(self.tr,*[os.environ[n] for n in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')])
 def send(self,req,historical=False):
  name=type(req).__name__
  if name=='ProtoOAGetTickDataReq':kind='BID_ASK'
  elif name=='ProtoOAGetTrendbarsReq':kind='M5' if req.period==enums.M5 else 'H1'
  else:kind='NONHISTORY'
  need(kind in self.caps and self.counts[kind]<self.caps[kind],'LOCAL_'+kind+'_CAP')
  need(name in ('ProtoOAGetTickDataReq','ProtoOAGetTrendbarsReq'),'ONLY_FROZEN_HISTORICAL_REQUESTS')
  self.hrate.before_send();self.counts[kind]+=1
  return self.tr.request(req,timeout=30)
 def m5(self,sid,digits,frm,to):
  rows={};receipts=[];cursor=to*1000-1;status='COMPLETE_EXACT_WINDOW'
  for page in range(3):
   req=m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=self.aid,symbolId=sid,period=enums.M5,count=5000,fromTimestamp=frm*1000,toTimestamp=cursor)
   try:res=self.send(req,True)
   except Exception as ex:receipts.append({'failure_class':type(ex).__name__});status='TRANSPORT_UNRESOLVED';break
   if isinstance(res,m.ProtoOAErrorRes):receipts.append({'provider_error':res.errorCode});status='PROVIDER_ERROR';break
   envelope=self.tr.last_history_envelope;need(envelope is not None and int(envelope.payloadType)==v2.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE,'M5_RAW_ENVELOPE');res=v2.ProtoOAGetTrendbarsResV2.FromString(envelope.payload);need(res.IsInitialized() and res.ctidTraderAccountId==self.aid and res.period==enums.M5 and (not res.HasField('symbolId') or res.symbolId==sid),'M5_NATIVE_RESPONSE_BINDING');decoded=[v2.decode_trendbar(v2.ProtoOATrendbarV2.FromString(b.SerializeToString()),digits=digits,segment_from_ms=0,segment_to_ms=cursor) for b in res.trendbar];tt=[int(datetime.fromisoformat(x['time_utc'].replace('Z','+00:00')).timestamp()) for x in decoded];need(len(tt)==len(set(tt)) and all(t%300==0 and t*1000<=cursor for t in tt),'M5_GRID_RESPONSE')
   present=res.HasField('hasMore');more=bool(res.hasMore) if present else None;lower=sum(t<frm for t in tt)
   rec={'sid':sid,'period':'M5','from_ms':frm*1000,'to_ms':cursor,'page':page+1,'has_more_present':present,'has_more':more,'raw_response_envelope_b64':base64.b64encode(envelope.SerializeToString()).decode(),'lower_discarded':lower,'rows_in_scope':sum(frm<=t<to for t in tt),'raw_payload_sha256':sha(envelope.payload)};receipts.append(rec)
   for t,r in zip(tt,decoded):
    if frm<=t<to:
     z=[float(r[n]) for n in ('open','high','low','close','tick_volume')];need(t not in rows or rows[t]==z,'M5_CONFLICT');rows[t]=z
   if lower or (present and not more):break
   if not tt or not present:status='HASMORE_UNRESOLVED';break
   cursor=min(tt)*1000-1
   if cursor<frm*1000:break
  else:status='PAGE_CAP_INCOMPLETE'
  return rows,receipts,status
