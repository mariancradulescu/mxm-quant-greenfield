"""2026-11-01 source-first, bounded new Pepperstone Europe LIVE VIEW-only tick observation.

Fresh two-window BID/ASK reception informs native CSharp friction realism,
NOT alpha confirmation, old-R3 protected labels, broker fills, or executable
concurrent book proofs. Uses existing m6 transport/read-only request whitelist
and existing R3 isolated Pepperstone secrets. No subscriptions or mutations.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
from m6.ctrader_capture import require_read_only_request
from m6.ctrader_proto import OpenApiMessages_pb2 as msg
from m6.ctrader_transport import StdlibCTraderTransport
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment
from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256

REPO="mariancradulescu/mxm-quant-greenfield"
BRANCH="mxm-remediation-p0-p4-20261015-v1"
OUT=Path("verification/be-pepperstone-new-bidask-20261101")
SYMBOLS=("EURUSD","GBPUSD","USDJPY","XAUUSD")
WINDOWS=(("2026-10-27T10:00:00Z","2026-10-27T10:05:00Z"),
         ("2026-10-29T10:00:00Z","2026-10-29T10:05:00Z"))
PUB=Path("research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem")
FINGERPRINT="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"
ALLOWED=("ProtoOAApplicationAuthReq","ProtoOAGetAccountListByAccessTokenReq",
         "ProtoOAAccountAuthReq","ProtoOASymbolsListReq",
         "ProtoOASymbolByIdReq","ProtoOAGetTickDataReq")
SECRETS=("R3_CTRADER_CLIENT_ID","R3_CTRADER_CLIENT_SECRET","R3_CTRADER_ACCESS_TOKEN")
MAX_REQUESTS=3+1+1+2*len(SYMBOLS)*len(WINDOWS)
def need(ok,reason):
 if not ok:raise ValueError("MXM_BE_READ_ONLY_BIDASK_"+reason)
def digest(blob):return hashlib.sha256(blob).hexdigest()
def utc_ms(s):
 t=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
 need(t.utcoffset()==dt.timedelta(0),"UTC");return int(t.timestamp()*1000)
def decode_side(ticks,start,end):
 """OpenAPI response: newest tick has epoch; next carries delta BACKWARD."""
 out=[];stamp=None
 for i,tick in enumerate(ticks):
  rawtime=int(tick.timestamp)
  stamp=rawtime if i==0 else stamp-rawtime
  price=int(tick.tick)
  # Multiple genuine ticks may share the same millisecond (zero delta).
  need(rawtime>=0 and price>0
       and start<=stamp<=end and (not out or stamp<=out[-1][0]),
       "TICK_DELTA_CHRONOLOGY_OR_PRICE")
  out.append((stamp,price))
 return list(reversed(out))
def spreads(bids,asks):
 """Strict-prior, <=5s receipt-time pairing; NOT a synchronized wire book."""
 import bisect
 btimes=[x[0] for x in bids];atimes=[x[0] for x in asks]
 events=sorted(set(btimes+atimes))
 widths=[]
 for stamp in events:
  bi=bisect.bisect_right(btimes,stamp)-1
  ai=bisect.bisect_right(atimes,stamp)-1
  if bi<0 or ai<0:continue
  tb,b= bids[bi];ta,a=asks[ai]
  if stamp-tb>5000 or stamp-ta>5000:continue
  if a<=b:continue
  widths.append(20000.0*(a-b)/(a+b))
 return widths
def median_p90(vals):
 s=sorted(vals);return {"paired_observations":len(vals),
  "median_spread_bps":round(statistics.median(s),5) if s else None,
  "p90_spread_bps":round(s[(9*(len(s)-1))//10],5) if s else None}
def selftest():
 need(SYMBOLS==("EURUSD","GBPUSD","USDJPY","XAUUSD") and len(WINDOWS)==2,
      "FROZEN_SYMBOLS_WINDOWS")
 for x in ALLOWED:require_read_only_request(x)
 need("ProtoOANewOrderReq" not in ALLOWED and
      "ProtoOASubscribeSpotsReq" not in ALLOWED and
      "ProtoOAGetTrendbarsReq" not in ALLOWED,"READ_ONLY_WIRE_SCOPE")
 start=utc_ms("2026-10-27T10:00:00Z")
 class Tick:
  def __init__(self,t,p):self.timestamp=t;self.tick=p
 result=decode_side([Tick(start+1400,100010),Tick(200,100005),
    Tick(400,100002)],start,start+3000)
 need(result==[(start+800,100002),(start+1200,100005),(start+1400,100010)],
      "TICK_RELATIVE_DECODING")
 ask=[(start+900,100020),(start+1300,100022)]
 vals=spreads(result,ask)
 need(len(vals)>=2 and all(x>0 for x in vals),"STRICT_PRIOR_SPREAD")
 need(spreads(result,[(start+7000,100022)])==[],"NO_FUTURE_QUOTES")
 need(median_p90(vals)["p90_spread_bps"]>0,"QUANTILE")
 print("MXM_BE_NEW_PEPPERSTONE_BIDASK_SOURCE_BLIND_SUCCESS")
class BoundReadOnly:
 def __init__(self,tr):self.tr=tr;self.requests=[]
 def request(self,req,**kw):
  label=type(req).__name__
  need(label in ALLOWED and len(self.requests)<MAX_REQUESTS,"REQUEST_ALLOWLIST")
  require_read_only_request(label)
  self.requests.append(label)
  result=self.tr.request(req,**kw)
  need(not isinstance(result,msg.ProtoOAErrorRes),"PEPPERSTONE_API_RESPONSE_ERROR")
  return result

def run():
 selftest()
 need(os.getenv("GITHUB_REPOSITORY")==REPO and
      os.getenv("GITHUB_REF")=="refs/heads/"+BRANCH and
      os.getenv("GITHUB_EVENT_NAME")=="push" and
      os.getenv("GITHUB_RUN_ATTEMPT")=="1" and
      os.getenv("GITHUB_JOB")=="isolated-pepperstone-view-source",
      "OFFICIAL_FIRST_PUSH_ONLY")
 need(all(os.getenv(x) for x in SECRETS) and
      not os.getenv("R3_CUSTODY_PRIVATE_KEY_PEM") and
      not os.getenv("CTRADER_REFRESH_TOKEN"),"SECRETS_ISOLATED")
 need(public_spki_sha256(PUB)==FINGERPRINT,"IMMUTABLE_PUBLIC_RECIPIENT")
 values=tuple(os.environ.pop(x) for x in SECRETS)
 record={"schema":"mxm.be.pepperstone-new-read-only-bidask.v1",
         "read_only_broker":"PEPPERSTONE_EUROPE_LIVE",
         "observation_purpose":"SOURCE_FIRST_COST_REALISM_DEVELOPMENT_NOT_ALPHA",
         "source_time_windows":WINDOWS,"requested_instrument_names":SYMBOLS,
         "historical_prices_requested":True,"broker_orders":0,"demo_orders":0,
         "cloud_activations":0,"frozen_R3_confirmation_opened":False,
         "independent_alpha_confirmation":False,"realtime_executability_proven":False,
         "quote_pairing":"STRICT_PRIOR_5SEC_NOT_EXCHANGE_ATOMIC",
         "no_permanent_universe_exclusion":True,"instrument_observations":[],
         "authentication":"NOT_COMPLETED"}
 private=[]
 transport=StdlibCTraderTransport(connect_timeout=15,response_timeout=30)
 bound=BoundReadOnly(transport)
 try:
  transport.connect()
  account=authenticate_segment(bound,*values)
  values=None
  need(bound.requests==list(ALLOWED[:3]),"AUTH_SCOPE")
  response=bound.request(msg.ProtoOASymbolsListReq(
   ctidTraderAccountId=account,includeArchivedSymbols=False),timeout=25)
  need(isinstance(response,msg.ProtoOASymbolsListRes),"SYMBOL_LIST_RESPONSE")
  symbols=list(response.symbol)
  name_to_id={}
  for x in symbols:
   name=str(x.symbolName).upper();ident=int(x.symbolId)
   if name in SYMBOLS:
    need(name not in name_to_id and ident>0,"AMBIGUOUS_SYMBOL")
    name_to_id[name]=ident
  missing=[n for n in SYMBOLS if n not in name_to_id]
  record["broker_current_enabled_universe_count"]=len(symbols)
  record["missing_frozen_source_symbols"]=missing
  ids=list(name_to_id.values())
  need(len(ids)>=2,"INSUFFICIENT_CURRENT_BROKER_SYMBOLS")
  byid=msg.ProtoOASymbolByIdReq(ctidTraderAccountId=account)
  byid.symbolId.extend(ids)
  detail=bound.request(byid,timeout=25)
  need(isinstance(detail,msg.ProtoOASymbolByIdRes),"SYMBOL_BYID_RESPONSE")
  digits={int(x.symbolId):int(x.digits) for x in detail.symbol}
  need(all(1<=digits.get(i,0)<=8 for i in ids),"PRICE_PRECISION")
  for name in SYMBOLS:
   if name in missing:continue
   ident=name_to_id[name]
   for label,(s,e) in enumerate(WINDOWS):
    start,end=utc_ms(s),utc_ms(e)
    need(0<end-start<=300000,"WINDOW_LIMIT")
    side={}
    for typ,kind in ((1,"BID"),(2,"ASK")):
     # Native OpenAPI read-only historical BID and ASK, no subscriptions.
     req=msg.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
      symbolId=ident,type=typ,fromTimestamp=start,toTimestamp=end)
     res=bound.request(req,timeout=30)
     need(isinstance(res,msg.ProtoOAGetTickDataRes) and
          int(res.ctidTraderAccountId)==account,"TICK_ACCOUNT_BINDING")
     side[kind]={"has_more":bool(res.hasMore),
       "ticks":decode_side(res.tickData,start,end)}
     time.sleep(.23)
    # A truncated side is NEVER treated as a full matched spread sample.
    complete=not side["BID"]["has_more"] and not side["ASK"]["has_more"]
    width=spreads(side["BID"]["ticks"],side["ASK"]["ticks"]) if complete else []
    entry={"symbol":name,"window":label,
      "complete_both_sides":complete,
      "bid_events":len(side["BID"]["ticks"]),"ask_events":len(side["ASK"]["ticks"]),
      "open_api_price_digits":digits[ident],**median_p90(width),
      "source_side_pairing_not_order_execution":True}
    record["instrument_observations"].append(entry)
    private.append({"symbol":name,"window":label,"symbol_id":ident,
       "bid":side["BID"],"ask":side["ASK"],"derived_pairing":entry})
  record["authentication"]="AUTHORIZED_LIVE_VIEW_ACCOUNT_FINGERPRINT_VERIFIED"
  record["outbound_type_counts"]={q:bound.requests.count(q) for q in ALLOWED}
  need(len(bound.requests)<=MAX_REQUESTS,"REQUEST_COUNT")
  record["complete_two_sided_windows"]=sum(x["complete_both_sides"] for x in record["instrument_observations"])
  raw=json.dumps(private,sort_keys=True,separators=(",",":")).encode()
  record["private_plain_sha256"]=digest(raw)
  OUT.mkdir(parents=True,exist_ok=False)
  encrypt_shard(raw,public_key=PUB,output=OUT/"original-bidask.mxmenc")
  record["original_cipher_sha256"]=digest((OUT/"original-bidask.mxmenc").read_bytes())
  (OUT/"public.json").write_text(json.dumps(record,sort_keys=True,separators=(",",":"))+"\n")
  print("MXM_BE_NEW_PEPPERSTONE_VIEW_FIRST_SOURCE "+json.dumps(record,sort_keys=True),flush=True)
 finally:
  values=None
  for key in SECRETS:os.environ.pop(key,None)
  transport.close()

if __name__=="__main__":
 import sys
 need(sys.argv[1:] in (["selftest"],["protected"]),"CLI")
 selftest() if sys.argv[1:]==["selftest"] else run()
