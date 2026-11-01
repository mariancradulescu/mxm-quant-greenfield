"""Bounded genuine Pepperstone Open API read-only October M5 source extension.
Four source cohort symbols, four fixed seven-day windows, no models or fills.
Not a permanent universe restriction, confirmation release, DEMO/LIVE order or Cloud.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import time
from decimal import Decimal
from pathlib import Path
from m6.ctrader_capture import require_read_only_request
from m6.ctrader_proto import OpenApiMessages_pb2 as m
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import StdlibCTraderTransport
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,encrypt_shard,public_spki_sha256

REPO="mariancradulescu/mxm-quant-greenfield"
BRANCH="mxm-remediation-p0-p4-20261015-v1"
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"verification/be-new-october-m5-20261101"
SYMBOLS=("EURUSD","GBPUSD","USDJPY","XAUUSD")
WINDOW_START="2026-10-01T00:00:00Z"
WINDOW_END="2026-10-29T00:00:00Z"
SLICES=4
M5=300000
PUB=ROOT/"research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
FP="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"
AUTH=("ProtoOAApplicationAuthReq","ProtoOAGetAccountListByAccessTokenReq","ProtoOAAccountAuthReq")
ALLOWED=AUTH+("ProtoOASymbolsListReq","ProtoOASymbolByIdReq","ProtoOAGetTrendbarsReq")
SECRETS=("R3_CTRADER_CLIENT_ID","R3_CTRADER_CLIENT_SECRET","R3_CTRADER_ACCESS_TOKEN")
MAX_REQUESTS=3+1+1+SLICES*len(SYMBOLS)
def need(x,why):
 if not x:raise ValueError("MXM_BE_NEW_OCT_M5_"+why)
def ms(s):return int(dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)
def digest(x):return hashlib.sha256(x).hexdigest()
def decode_bars(raw,digits,start,end):
 need(1<=digits<=8 and start<end and (end-start)%M5==0,"BAR_CONTRACT")
 rows={};factor=Decimal(10)**digits
 for x in raw:
  t=int(x.utcTimestampInMinutes)*60000
  if t<start or t>=end:continue
  lo=int(x.low);o=lo+int(x.deltaOpen);hi=lo+int(x.deltaHigh)
  cl=lo+int(x.deltaClose);v=int(x.volume)
  need(t%M5==0 and 0<lo<=min(o,cl)<=max(o,cl)<=hi and v>=0,
       "NATIVE_M5_OHLCV_GEOMETRY")
  row={"open_utc_ms":t,"open":str(Decimal(o)/factor),
       "high":str(Decimal(hi)/factor),"low":str(Decimal(lo)/factor),
       "close":str(Decimal(cl)/factor),"tick_volume":v,
       "available_no_earlier_than_utc_ms":t+M5}
  need(t not in rows or rows[t]==row,"CONFLICTING_DUPLICATE_BAR")
  rows[t]=row
 return [rows[k] for k in sorted(rows)]
def selftest():
 need(SYMBOLS==("EURUSD","GBPUSD","USDJPY","XAUUSD") and SLICES==4 and
      ms(WINDOW_END)-ms(WINDOW_START)==28*86400000 and
      len(ALLOWED)==6 and MAX_REQUESTS==21,"FROZEN_SCOPE")
 for n in ALLOWED:require_read_only_request(n)
 need(ProtoOATrendbarPeriod.Value("M5")>=0,"M5_PROTO_ENUM_AVAILABLE")
 need("ProtoOANewOrderReq" not in ALLOWED and
      "ProtoOASubscribeSpotsReq" not in ALLOWED,"NO_TRADING_OR_SUBSCRIPTIONS")
 start=ms(WINDOW_START)
 class Bar:
  utcTimestampInMinutes=start//60000;low=100000;deltaOpen=15
  deltaHigh=30;deltaClose=20;volume=12
 row=decode_bars([Bar()],5,start,start+M5)
 need(len(row)==1 and row[0]["open"]=="1.00015" and
      row[0]["close"]=="1.0002" and
      row[0]["available_no_earlier_than_utc_ms"]==start+M5,
      "OPEN_TIME_FENCE_AND_PRICE_DELTAS")
 class Bad(Bar):deltaClose=31
 try:decode_bars([Bad()],5,start,start+M5)
 except ValueError:pass
 else:need(False,"BAD_CLOSE_MUST_FAIL")
 need(decode_bars([Bar()],5,start+M5,start+2*M5)==[],
      "OUTSIDE_WINDOW_EXCLUDED")
 print("MXM_BE_NEW_OCTOBER_M5_SOURCE_BLIND_SUCCESS")
class ViewOnly:
 def __init__(self,tr):self.tr=tr;self.wire=[]
 def request(self,req,**kwargs):
  n=type(req).__name__
  need(n in ALLOWED and len(self.wire)<MAX_REQUESTS,"BOUNDED_READ_ONLY_API")
  require_read_only_request(n)
  self.wire.append(n)
  response=self.tr.request(req,**kwargs)
  need(not isinstance(response,m.ProtoOAErrorRes),"API_REJECTED")
  return response
def original():
 selftest()
 need(os.environ.get("GITHUB_REPOSITORY")==REPO and
      os.environ.get("GITHUB_REF")=="refs/heads/"+BRANCH and
      os.environ.get("GITHUB_EVENT_NAME")=="push" and
      os.environ.get("GITHUB_RUN_ATTEMPT")=="1" and
      os.environ.get("GITHUB_JOB")=="one-pepperstone-view-m5-source",
      "FIRST_OFFICIAL_GITHUB_ONLY")
 need(all(os.environ.get(k) for k in SECRETS) and
      not os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM"),
      "ISOLATED_VIEW_CREDENTIALS")
 need(public_spki_sha256(PUB)==FP,"EXISTING_PUBLIC_RECIPIENT")
 vals=tuple(os.environ.pop(k) for k in SECRETS)
 tr=StdlibCTraderTransport(connect_timeout=15,response_timeout=30)
 wire=ViewOnly(tr)
 try:
  tr.connect();account=authenticate_segment(wire,*vals);vals=None
  need(wire.wire==list(AUTH),"AUTHORIZED_LIVE_VIEW_ACCOUNT_ONLY")
  res=wire.request(m.ProtoOASymbolsListReq(
    ctidTraderAccountId=account,includeArchivedSymbols=False),timeout=25)
  need(isinstance(res,m.ProtoOASymbolsListRes),"SYMBOLS_RESPONSE")
  matches={}
  for s in res.symbol:
   name=str(s.symbolName).upper()
   if name in SYMBOLS:
    need(name not in matches and int(s.symbolId)>0,"UNIQUE_SYMBOL_ID")
    matches[name]=int(s.symbolId)
  need(set(matches)==set(SYMBOLS),"FOUR_SAME_BROKER_SYMBOLS")
  req=m.ProtoOASymbolByIdReq(ctidTraderAccountId=account)
  req.symbolId.extend([matches[n] for n in SYMBOLS])
  detail=wire.request(req,timeout=25)
  need(isinstance(detail,m.ProtoOASymbolByIdRes),"SYMBOL_DETAIL_RESPONSE")
  precision={int(s.symbolId):int(s.digits) for s in detail.symbol}
  need(all(1<=precision.get(i,0)<=8 for i in matches.values()),
       "BROKER_DIGITS")
  start=ms(WINDOW_START);end=ms(WINDOW_END)
  slice_ms=(end-start)//SLICES
  allrows=[];support=[]
  for name in SYMBOLS:
   observed=set();found=[]
   for i in range(SLICES):
    a=start+i*slice_ms;z=a+slice_ms
    req=m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
     symbolId=matches[name],period=ProtoOATrendbarPeriod.Value("M5"),
     fromTimestamp=a,toTimestamp=z,count=5000)
    ans=wire.request(req,timeout=30)
    need(isinstance(ans,m.ProtoOAGetTrendbarsRes) and not bool(ans.hasMore),
         "NO_TRUNCATED_M5_SOURCE")
    rows=decode_bars(ans.trendbar,precision[matches[name]],a,z)
    for row in rows:
     ts=row["open_utc_ms"]
     need(ts not in observed,"BROKER_M5_DUPLICATE_CROSS_WINDOW")
     observed.add(ts)
    found.extend(rows)
    support.append({"symbol":name,"slice":i,"start_utc_ms":a,
      "end_utc_ms":z,"bars":len(rows),"no_forward_bars":True})
    time.sleep(.23)
   allrows.append({"symbol":name,"broker_symbol_id":matches[name],
       "digits":precision[matches[name]],"bars":found})
  need(len(support)==16 and len(allrows)==4 and
       len(wire.wire)==MAX_REQUESTS,"ALL_REQUESTS_ACCOUNTED_FOR")
  raw=json.dumps(allrows,separators=(",",":"),sort_keys=True).encode()
  OUT.mkdir(parents=True,exist_ok=False)
  encrypt_shard(raw,public_key=PUB,output=OUT/"october-m5-original.mxmenc")
  public={"schema":"mxm.be.new-pepperstone-october-M5-development.v1",
   "original_source":"PEPPERSTONE_EUROPE_LIVE_VIEW_OPENAPI",
   "symbol_population_not_permanent_filter":SYMBOLS,
   "from_utc":WINDOW_START,"to_utc_exclusive":WINDOW_END,
   "research_development_until_utc":"2026-10-22T00:00:00Z",
   "later_week_held_for_independent_future_test":True,
   "per_symbol_slice_counts":support,
   "broker_current_symbol_list_count":len(res.symbol),
   "bars_total":sum(len(x["bars"]) for x in allrows),
   "encrypted_original_sha256":digest((OUT/"october-m5-original.mxmenc").read_bytes()),
   "original_plain_sha256":digest(raw),
   "orders":0,"demo_orders":0,"cloud_activations":0,
   "broker_requests":len(wire.wire),"trading_requests":0,
   "executability_proven":False,"broker_net_eur_or_hard21_proven":False,
   "historical_bidask_covered":False,"source_gaps_filled":False}
  (OUT/"public.json").write_text(json.dumps(public,sort_keys=True,separators=(",",":"))+"\n")
  print("MXM_BE_NEW_OCTOBER_M5_ORIGINAL "+
        json.dumps(public,sort_keys=True),flush=True)
 finally:
  vals=None
  for k in SECRETS:os.environ.pop(k,None)
  tr.close()
if __name__=="__main__":
 import sys
 need(sys.argv[1:] in (["selftest"],["original"]),"CLI")
 selftest() if sys.argv[1:]==["selftest"] else original()
