"""Broad current catalog and outcome-blind staged native H1/tick collection."""
import os,json,time,math,base64
from collections import Counter,defaultdict
from datetime import datetime,timezone
from google.protobuf.json_format import MessageToDict
from research_core_v4.native_executable_qualification_v1.runner_v1 import HistoryReceiptTransport,schedule_state,sha,need
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,RateLimiter
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m,enums,decode_ctrader_tick_page
from research_core_v4 import shallow_m5_support_v2 as v2
from research_core_v4.wide_greenfield_v1 import kernel_v1 as k
ALLOW={'ProtoOATraderReq','ProtoOAAssetListReq','ProtoOAAssetClassListReq','ProtoOASymbolCategoryListReq','ProtoOASymbolsListReq','ProtoOASymbolByIdReq','ProtoOAExpectedMarginReq','ProtoOAGetTrendbarsReq','ProtoOAGetTickDataReq'}
def plain(x):return MessageToDict(x,preserving_proto_field_name=True,use_integers_for_enums=True)
class Collector:
 def __init__(self):self.tr=None;self.counts=Counter();self.raw=[];self.hrate=RateLimiter(min_interval=.25);self.nrate=RateLimiter(min_interval=.04)
 def connect(self):
  self.tr=HistoryReceiptTransport(response_timeout=30);self.tr.connect();self.aid=authenticate_segment(self.tr,*[os.environ[n] for n in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')])
 def close(self):
  if self.tr:self.tr.close()
 def send(self,req,historical=False):
  name=type(req).__name__;need(name in ALLOW,'READ_ONLY_ALLOWLIST');need(self.counts['history']<900 and self.counts['tick']<10000 and self.counts['nonhistory']<4000,'COLLECTION_CAP');(self.hrate if historical else self.nrate).before_send();self.counts['tick' if name=='ProtoOAGetTickDataReq' else 'history' if historical else 'nonhistory']+=1
  res=self.tr.request(req,timeout=30);return res
 def catalog(self):
  out={};raw=[]
  for name,key,field in [('ProtoOATraderReq','trader','trader'),('ProtoOAAssetListReq','assets','asset'),('ProtoOAAssetClassListReq','classes','assetClass'),('ProtoOASymbolCategoryListReq','categories','symbolCategory'),('ProtoOASymbolsListReq','light','symbol')]:
   req=getattr(m,name)(ctidTraderAccountId=self.aid)
   if name=='ProtoOASymbolsListReq':req.includeArchivedSymbols=True
   res=self.send(req);need(not isinstance(res,m.ProtoOAErrorRes),'CATALOG_PROVIDER_ERROR');raw.append({'request_type':name,'response_b64':base64.b64encode(res.SerializeToString()).decode()});v=getattr(res,field);out[key]=plain(v) if key=='trader' else [plain(x) for x in v]
   if key=='light':out['archived']=[plain(x) for x in res.archivedSymbol]
  assets={int(x['assetId']):x['name'] for x in out['assets']};need(assets[int(out['trader']['depositAssetId'])]=='EUR' and 'Pepperstone' in out['trader'].get('brokerName',''),'EXISTING_EUR_BROKER_IDENTITY')
  ids=sorted(int(x['symbolId']) for x in out['light']);out['full']={};out['margin']={}
  for j in range(0,len(ids),64):
   req=m.ProtoOASymbolByIdReq(ctidTraderAccountId=self.aid);req.symbolId.extend(ids[j:j+64]);res=self.send(req)
   if isinstance(res,m.ProtoOAErrorRes):continue
   need(res.ctidTraderAccountId==self.aid,'CATALOG_ACCOUNT_BIND');out['full'].update({str(x.symbolId):plain(x) for x in res.symbol});raw.append({'request_type':'ProtoOASymbolByIdReq','sids':ids[j:j+64],'response_b64':base64.b64encode(res.SerializeToString()).decode()})
  for pos,sid in enumerate(ids):
   f=out['full'].get(str(sid));light=next(x for x in out['light'] if int(x['symbolId'])==sid)
   if not f or not light.get('enabled',False) or int(f.get('tradingMode',-1))!=0:continue
   mv=int(f.get('minVolume',0))
   if not mv>0:continue
   try:
    req=m.ProtoOAExpectedMarginReq(ctidTraderAccountId=self.aid,symbolId=sid);req.volume.append(mv);res=self.send(req)
    if isinstance(res,m.ProtoOAErrorRes):out['margin'][str(sid)]={'state':'PROVIDER_ERROR','code':res.errorCode};continue
    need(res.ctidTraderAccountId==self.aid,'MARGIN_ACCOUNT_BIND');md=int(res.moneyDigits) if res.HasField('moneyDigits') else int(out['trader'].get('moneyDigits',2));rr=[plain(x) for x in res.margin];z=rr[0] if rr else {};out['margin'][str(sid)]={'state':'CURRENT_EUR_EXPECTED_MARGIN','money_digits':md,'volume_cents':mv,'buy_eur':int(z['buyMargin'])/10**md if 'buyMargin' in z else None,'sell_eur':int(z['sellMargin'])/10**md if 'sellMargin' in z else None,'raw':rr}
   except Exception as ex:out['margin'][str(sid)]={'state':'REQUEST_UNRESOLVED','failure_class':type(ex).__name__}
   if pos%200==0:print(json.dumps({'phase':'BROAD_CURRENT_CATALOG','ordinal':pos,'numeric_outcomes_public':False}),flush=True)
  out['raw_catalog_receipts']=raw;out['retrieved_utc']=datetime.now(timezone.utc).isoformat();return out
 def h1(self,sid,digits,frm,to):
  rows={};receipts=[];cursor=to*1000-1;status='COMPLETE_EXACT_WINDOW'
  for page in range(3):
   req=m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=self.aid,symbolId=sid,period=enums.H1,count=5000,fromTimestamp=frm*1000,toTimestamp=cursor)
   try:res=self.send(req,True)
   except Exception as ex:receipts.append({'failure_class':type(ex).__name__});status='TRANSPORT_UNRESOLVED';break
   if isinstance(res,m.ProtoOAErrorRes):receipts.append({'provider_error':res.errorCode});status='PROVIDER_ERROR';break
   envelope=self.tr.last_history_envelope;need(envelope is not None and int(envelope.payloadType)==v2.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE,'H1_RAW_ENVELOPE');res=v2.ProtoOAGetTrendbarsResV2.FromString(envelope.payload);need(res.IsInitialized() and res.ctidTraderAccountId==self.aid and res.period==enums.H1 and (not res.HasField('symbolId') or res.symbolId==sid),'H1_NATIVE_RESPONSE_BINDING');decoded=[v2.decode_trendbar(v2.ProtoOATrendbarV2.FromString(b.SerializeToString()),digits=digits,segment_from_ms=0,segment_to_ms=cursor) for b in res.trendbar];tt=[int(datetime.fromisoformat(x['time_utc'].replace('Z','+00:00')).timestamp()) for x in decoded];need(len(tt)==len(set(tt)) and all(t%60==0 and t*1000<=cursor for t in tt),'H1_GRID_RESPONSE')
   present=res.HasField('hasMore');more=bool(res.hasMore) if present else None;lower=sum(t<frm for t in tt)
   rec={'sid':sid,'period':'H1','from_ms':frm*1000,'to_ms':cursor,'page':page+1,'has_more_present':present,'has_more':more,'raw_response_envelope_b64':base64.b64encode(envelope.SerializeToString()).decode(),'lower_discarded':lower,'rows_in_scope':sum(frm<=t<to for t in tt),'raw_payload_sha256':sha(envelope.payload)};receipts.append(rec)
   for t,r in zip(tt,decoded):
    if frm<=t<to:
     z=[float(r[n]) for n in ('open','high','low','close','tick_volume')];need(t not in rows or rows[t]==z,'H1_CONFLICT');rows[t]=z
   if lower or (present and not more):break
   if not tt or not present:status='HASMORE_UNRESOLVED';break
   cursor=min(tt)*1000-1
   if cursor<frm*1000:break
  else:status='PAGE_CAP_INCOMPLETE'
  return rows,receipts,status
 def quote(self,sid,t):
  sides={};pages=[]
  for name,typ in [('bid',enums.BID),('ask',enums.ASK)]:
   try:res=self.send(m.ProtoOAGetTickDataReq(ctidTraderAccountId=self.aid,symbolId=sid,type=typ,fromTimestamp=t*1000-60000,toTimestamp=t*1000),True)
   except Exception as ex:sides[name]={'state':'TRANSPORT_UNRESOLVED','failure_class':type(ex).__name__};continue
   if isinstance(res,m.ProtoOAErrorRes):sides[name]={'state':'PROVIDER_ERROR','code':res.errorCode};continue
   need(res.ctidTraderAccountId==self.aid,'QUOTE_ACCOUNT_BIND');enc=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in res.tickData];dec=decode_ctrader_tick_page(enc);need(all(t*1000-60000<=x.timestamp_ms<=t*1000 for x in dec),'QUOTE_CAUSAL_WINDOW');pages.append({'side':name,'encoded':enc,'hasMore':bool(res.hasMore)})
   if dec:
    x=max(dec,key=lambda x:x.timestamp_ms);sides[name]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':x.timestamp_ms,'price':x.raw_tick/100000,'age_ms':t*1000-x.timestamp_ms,'source_has_more':bool(res.hasMore)}
   else:sides[name]={'state':'EMPTY_AUTHENTIC_WINDOW','source_has_more':bool(res.hasMore)}
  return {'symbol_id':sid,'boundary_ms':t*1000,'sides':sides,'pages':pages}

def identities(cat):
 assets={int(x['assetId']):x['name'] for x in cat['assets']};classes={int(x['id']):x['name'] for x in cat['classes']};cats={int(x['id']):classes.get(int(x['assetClassId']),'UNKNOWN') for x in cat['categories']};out=[]
 for li in cat['light']:
  sid=int(li['symbolId']);f=cat['full'].get(str(sid));margin=cat['margin'].get(str(sid),{});reason=[]
  if not li.get('enabled',False) or not f or int(f.get('tradingMode',-1))!=0:reason.append('CURRENT_NOT_ENTRY_ENABLED')
  if not f or any(n not in f for n in ('minVolume','stepVolume','maxVolume','lotSize','digits','preciseTradingCommissionRate','preciseMinCommission','commissionType','minCommissionType','pnlConversionFeeRate','scheduleTimeZone')):reason.append('CONTRACT_UNRESOLVED')
  mm=[margin.get(n) for n in ('buy_eur','sell_eur')];mx=max(mm) if all(x is not None for x in mm) else None
  if mx is None:reason.append('MARGIN_UNRESOLVED')
  elif mx>80:reason.append('CURRENT_MARGIN_EXCEEDS_40PCT_RESERVE_POLICY')
  if f and (int(f.get('minVolume',0))<=0 or int(f.get('stepVolume',0))<=0 or int(f.get('lotSize',0))<=0):reason.append('VOLUME_LATTICE_UNRESOLVED')
  out.append({'sid':sid,'symbol':li.get('symbolName'),'class':cats.get(int(li.get('symbolCategoryId',-1)),'UNKNOWN'),'base':assets.get(int(li.get('baseAssetId',-1))),'quote':assets.get(int(li.get('quoteAssetId',-1))),'margin_eur':mx,'min_units':int(f['minVolume'])/100 if f and 'minVolume' in f else None,'reasons':reason,'research_contract_eligible':not reason})
 return out

def stratified(rows,cap,per_stratum,primary_ids):
 groups=defaultdict(list)
 for r in rows:
  if r['research_contract_eligible']:groups[(r['class'],r['quote'])].append(r)
 for gg in groups.values():gg.sort(key=lambda r:(r['sid'] in primary_ids,r['margin_eur'],r['sid']))
 out=[]
 for j in range(per_stratum):
  for g in sorted(groups,key=str):
   if j<len(groups[g]) and len(out)<cap:out.append(groups[g][j])
 return out

def aggregate_m5(bars):
 out={}
 for t in sorted(bars):
  if t%3600:continue
  rr=[bars.get(t+i*300) for i in range(12)]
  if all(r is not None for r in rr):out[t]=[rr[0][0],max(r[1] for r in rr),min(r[2] for r in rr),rr[-1][3],sum(r[4] for r in rr)]
 return out
