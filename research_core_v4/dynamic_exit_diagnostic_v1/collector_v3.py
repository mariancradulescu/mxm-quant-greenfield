"""Additive tick-envelope capture; same read-only authentication, remaining request budget."""
import os
from research_core_v4.native_executable_qualification_v1.runner_v1 import HistoryReceiptTransport
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m
from .collector_v2 import Collector as Previous
class TickReceiptTransport(HistoryReceiptTransport):
 def receive_envelope(self,*,deadline):
  envelope=super().receive_envelope(deadline=deadline)
  if int(envelope.payloadType)==int(m.ProtoOAGetTickDataRes().payloadType):self.last_history_envelope=envelope
  return envelope
class Collector(Previous):
 def __init__(self):super().__init__();self.caps['BID_ASK']=1199
 def connect(self):
  self.tr=TickReceiptTransport(response_timeout=30);original=self.tr.request
  def counted(req,*args,**kw):
   self.wire_types[type(req).__name__]+=1
   return original(req,*args,**kw)
  self.tr.request=counted;self.tr.connect();self.aid=authenticate_segment(self.tr,*[os.environ[n] for n in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')])
 def quote_ms(self,sid,ms):
  if self.counts['BID_ASK']+2>self.caps['BID_ASK']:return {'symbol_id':sid,'boundary_ms':ms,'sides':{n:{'state':'LOCAL_BID_ASK_CAP'} for n in ('bid','ask')}}
  return super().quote_ms(sid,ms)
