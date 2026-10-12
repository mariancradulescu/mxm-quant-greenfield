"""One capped historical BID/ASK tranche; never H1, M5 or order requests."""
import base64,math
from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector as Existing
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m,enums,decode_ctrader_tick_page
from research_core_v4.native_executable_qualification_v1.runner_v1 import need,sha
class Collector(Existing):
 def __init__(self):super().__init__({'H1':0,'M5':0,'BID_ASK':1200,'NONHISTORY':0})
 def path(self,sid,start,end,existing_quotes):
  out={};raw=[];statuses={};audit={}
  for side,typ in [('bid',enums.BID),('ask',enums.ASK)]:
   frm=int(start*1000)-60000;to=int(end*1000);values={};coverage=[];status='COMPLETE_AUTHENTIC_WINDOW';pages_used=0
   for (own,t),q in existing_quotes.items():
    if own!=sid or t*1000<frm or t*1000-60000>to:continue
    for page in q.get('pages',q.get('raw_pages',[])):
     if page.get('side')!=side:continue
     enc=page.get('encoded',page.get('encoded_tick_rows'))
     if enc is None:continue
     lo=int(page.get('request_from_ms',q['boundary_ms']-60000));hi=int(page.get('request_to_ms',q['boundary_ms']))
     for x in decode_ctrader_tick_page(enc):
      if frm<=x.timestamp_ms<=to:
       value=x.raw_tick/100000
       if x.timestamp_ms in values and values[x.timestamp_ms]!=value:status='SAME_MS_CONFLICT'
       values[x.timestamp_ms]=value
     if page.get('hasMore') is False:coverage.append((max(frm,lo),min(to,hi)))
   gaps=uncovered(frm,to,coverage);audit[side]={'existing_complete_window_ms':to-frm+1-sum(hi-lo+1 for lo,hi in gaps),'uncovered_segments':gaps,'existing_decoded_ticks':len(values)}
   for lo,hi in gaps:
    if status!='COMPLETE_AUTHENTIC_WINDOW':break
    cursor=hi
    while True:
     if pages_used>=40:status='PAGE_CAP_INCOMPLETE';break
     if self.counts['BID_ASK']>=1200:status='LOCAL_BID_ASK_CAP';break
     req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=self.aid,symbolId=sid,type=typ,fromTimestamp=lo,toTimestamp=cursor)
     try:res=self.send(req,True);pages_used+=1
     except Exception as ex:status='TRANSPORT_UNRESOLVED';raw.append({'side':side,'failure_class':type(ex).__name__});break
     if isinstance(res,m.ProtoOAErrorRes):status='PROVIDER_ERROR';raw.append({'side':side,'error_code':res.errorCode});break
     need(isinstance(res,m.ProtoOAGetTickDataRes) and res.ctidTraderAccountId==self.aid,'TICK_RESPONSE_ACCOUNT_BIND')
     enc=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in res.tickData];dec=decode_ctrader_tick_page(enc);need(all(lo<=x.timestamp_ms<=cursor for x in dec),'TICK_PATH_DOMAIN');envelope=self.tr.last_history_envelope;need(envelope is not None,'RAW_TICK_ENVELOPE')
     raw.append({'side':side,'from_ms':lo,'to_ms':cursor,'hasMore':bool(res.hasMore),'encoded':enc,'raw_envelope_b64':base64.b64encode(envelope.SerializeToString()).decode(),'payload_sha256':sha(envelope.payload)})
     for x in dec:
      value=x.raw_tick/100000
      if x.timestamp_ms in values and values[x.timestamp_ms]!=value:status='SAME_MS_CONFLICT';break
      values[x.timestamp_ms]=value
     if status!='COMPLETE_AUTHENTIC_WINDOW' or not res.hasMore:break
     if not dec:status='HASMORE_EMPTY';break
     next_cursor=min(x.timestamp_ms for x in dec)
     if next_cursor>=cursor:status='PAGINATION_NO_PROGRESS';break
     cursor=next_cursor
   out[side]=sorted(values.items());statuses[side]=status
  return out,raw,statuses,audit
 def quote_ms(self,sid,ms):
  sides={};pages=[]
  for side,typ in [('bid',enums.BID),('ask',enums.ASK)]:
   if self.counts['BID_ASK']>=1200:sides[side]={'state':'LOCAL_BID_ASK_CAP'};continue
   try:res=self.send(m.ProtoOAGetTickDataReq(ctidTraderAccountId=self.aid,symbolId=sid,type=typ,fromTimestamp=ms-60000,toTimestamp=ms),True)
   except Exception as ex:sides[side]={'state':'TRANSPORT_UNRESOLVED','failure_class':type(ex).__name__};continue
   if isinstance(res,m.ProtoOAErrorRes):sides[side]={'state':'PROVIDER_ERROR','code':res.errorCode};continue
   need(isinstance(res,m.ProtoOAGetTickDataRes) and res.ctidTraderAccountId==self.aid,'FX_TICK_ACCOUNT_BIND')
   enc=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in res.tickData];dec=decode_ctrader_tick_page(enc);need(all(ms-60000<=x.timestamp_ms<=ms for x in dec),'FX_CAUSAL_DOMAIN');pages.append({'side':side,'from_ms':ms-60000,'to_ms':ms,'encoded':enc,'hasMore':bool(res.hasMore)})
   if dec:
    x=max(dec,key=lambda x:x.timestamp_ms);sides[side]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':x.timestamp_ms,'price':x.raw_tick/100000,'age_ms':ms-x.timestamp_ms,'source_has_more':bool(res.hasMore)}
   else:sides[side]={'state':'EMPTY_AUTHENTIC_WINDOW','source_has_more':bool(res.hasMore)}
  return {'symbol_id':sid,'boundary_ms':ms,'sides':sides,'pages':pages}

def uncovered(frm,to,coverage):
 cursor=frm;gaps=[]
 for lo,hi in sorted((max(frm,lo),min(to,hi)) for lo,hi in coverage if lo<=to and hi>=frm):
  if lo>cursor:gaps.append((cursor,lo-1))
  cursor=max(cursor,hi+1)
  if cursor>to:break
 if cursor<=to:gaps.append((cursor,to))
 return gaps
