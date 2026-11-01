"""ONE precommitted causal quote-reversal test on fresh genuine Pepperstone
BID/ASK. Oct27 earlier DEVELOPMENT and Oct29 later temporal HOLDOUT.
Fixed input-only rule, no tuning, commission-free optimistic BIDASK proxy
NOT EUR200 funded, live executable, economically qualified, or Cloud-safe.
"""
from __future__ import annotations
import bisect
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile

REPO="mariancradulescu/mxm-quant-greenfield"
BRANCH="mxm-remediation-p0-p4-20261015-v1"
RUN=41311440117
SOURCE_HEAD="6273c44e559e7d9a703a86b66ef344300c31814a"
ARTIFACT_NAME="mxm-be-pepperstone-signed-delta-guarded-41311440117"
CIPHER="8271331e4ea33c2ca883e903f9089befa27327114d8ebf9596e20c126808b3be"
PLAINTEXT="66d8f9f12610c13ce135014f90d7b5b68bf04755da76a908d2c9f49d764dd30a"
FP="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"
SYMBOLS=("EURUSD","GBPUSD","USDJPY","XAUUSD")
WINDOWS=(("2026-10-27T10:00:00Z","2026-10-27T10:05:00Z"),
         ("2026-10-29T10:00:00Z","2026-10-29T10:05:00Z"))
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"verification/be-quote-reversal-20261101"
MAX_AGE_MS=2000
LOOKBACK_MS=20000
HOLD_MS=20000
EXECUTION_LATENCY_MS=2000
DECISION_GRID_MS=5000
REVERSAL_THRESHOLD_MULTIPLE_OF_SPREAD=2

def need(ok,reason):
 if not ok:raise ValueError("MXM_BE_QUOTE_REVERSAL_"+reason)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def stamp(s):
 return int(dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)
def validate_ticks(rows,start,end):
 need(type(rows) is list,"TICKS_ARRAY")
 out=[];prev=-1
 for rec in rows:
  need(type(rec) is list and len(rec)==2 and
       type(rec[0]) is int and type(rec[1]) is int,"TICK_FIELDS")
  t,price=rec
  need(start<=t<=end and t>=prev and price>0,"TICK_PRICE_OR_CLOCK")
  out.append((t,price));prev=t
 return out
class Books:
 def __init__(self,bids,asks):
  self.bids=bids;self.asks=asks
  self.bid_t=[z[0] for z in bids];self.ask_t=[z[0] for z in asks]
  self.events=sorted(set(self.bid_t+self.ask_t))
 def at(self,t):
  bi=bisect.bisect_right(self.bid_t,t)-1
  ai=bisect.bisect_right(self.ask_t,t)-1
  if bi<0 or ai<0:return None
  bt,b=self.bids[bi];at,a=self.asks[ai]
  if t-bt>MAX_AGE_MS or t-at>MAX_AGE_MS or a<=b:return None
  return b,a,(a+b)/2
 def first(self,lo,hi,exclude_lower=False):
  i=bisect.bisect_right(self.events,lo) if exclude_lower else bisect.bisect_left(self.events,lo)
  for t in self.events[i:]:
   if t>hi:break
   v=self.at(t)
   if v is not None:return t,v
  return None
def decision(book,t):
 now=book.at(t);old=book.at(t-LOOKBACK_MS)
 if now is None or old is None:return 0
 b,a,mid=now
 movement=10000*(mid/old[2]-1)
 spread=10000*(a-b)/mid
 if abs(movement)<=REVERSAL_THRESHOLD_MULTIPLE_OF_SPREAD*spread:return 0
 return -1 if movement>0 else 1
def examine(bids,asks,start,end):
 book=Books(bids,asks)
 result={"decision_slots":0,"signals":0,"no_later_entry_quote":0,
         "no_later_exit_quote":0,"complete":0,"observations":[]}
 earliest_next=start
 for t in range(start+30000,end-24000,DECISION_GRID_MS):
  if t<earliest_next:continue
  result["decision_slots"]+=1
  d=decision(book,t)
  if not d:continue
  result["signals"]+=1
  entry=book.first(t,t+EXECUTION_LATENCY_MS,True)
  if entry is None:
   result["no_later_entry_quote"]+=1
   earliest_next=t+HOLD_MS+EXECUTION_LATENCY_MS;continue
  entry_t,(eb,ea,em)=entry
  target=entry_t+HOLD_MS
  earliest_next=target+EXECUTION_LATENCY_MS
  exit_info=book.first(target,target+EXECUTION_LATENCY_MS)
  if exit_info is None:
   result["no_later_exit_quote"]+=1;continue
  exit_t,(xb,xa,xm)=exit_info
  gross=10000*d*(xm/em-1)
  after=10000*d*((xb if d==1 else xa)-(ea if d==1 else eb))/em
  result["complete"]+=1
  result["observations"].append({"decision_ms":t,"entry_ms":entry_t,
    "exit_ms":exit_t,"side":d,"gross_mid_bps":gross,
    "after_bidask_zero_fee_bps":after})
 need(result["signals"]==result["no_later_entry_quote"]+
      result["no_later_exit_quote"]+result["complete"],"CENSORING_RECONCILED")
 return result
def selftest():
 need(LOOKBACK_MS==20000 and HOLD_MS==20000 and MAX_AGE_MS==2000 and
      EXECUTION_LATENCY_MS==2000 and
      REVERSAL_THRESHOLD_MULTIPLE_OF_SPREAD==2 and
      SYMBOLS==("EURUSD","GBPUSD","USDJPY","XAUUSD"),
      "FROZEN_SOURCE_BLIND_PREDECLARATION")
 start=stamp(WINDOWS[0][0])
 bids=[(start+1000*i,100000+10*i) for i in range(300)]
 asks=[(t,p+10) for t,p in bids]
 book=Books(bids,asks)
 need(decision(book,start+30000)==-1,"CONTRARIAN_CAUSAL_SIGNAL")
 fixed=decision(book,start+30000)
 future_poison=bids[:40]+[(t,p+10000000) for t,p in bids[40:]]
 need(decision(Books(future_poison,asks),start+30000)==fixed,
      "FORWARD_POISON_NOT_CAUSAL")
 r=examine(bids,asks,start,start+300000)
 need(r["complete"]>0 and all(x["entry_ms"]>x["decision_ms"] and
      x["exit_ms"]>=x["entry_ms"]+HOLD_MS and
      x["after_bidask_zero_fee_bps"]<x["gross_mid_bps"]
      for x in r["observations"]),"LATER_PRICE_SPREAD_PAY")
 need(examine(bids,[],start,start+300000)["complete"]==0,
      "NO_SYNTHETIC_EMPTY_QUOTE")
 need(Books([(start,100000)],[(start+3000,100010)]).at(start+3000) is None,
      "STRICT_PRIOR_SIDE_AGE")
 print("MXM_BE_QUOTE_REVERSAL_FIXED_SOURCE_BLIND_SUCCESS")
def summarize(data):
 obs=data["observations"]
 m=[r["gross_mid_bps"] for r in obs]
 n=[r["after_bidask_zero_fee_bps"] for r in obs]
 return {k:data[k] for k in ("decision_slots","signals",
  "no_later_entry_quote","no_later_exit_quote","complete")}|{
  "mean_gross_mid_bps":round(statistics.mean(m),6) if m else None,
  "mean_after_bidask_zero_commission_bps":round(statistics.mean(n),6) if n else None,
  "positive_after_bidask":sum(v>0 for v in n),
  "spread_friction_bps_sum":round(sum(m)-sum(n),6),
  "sum_after_bidask_bps_nonportfolio":round(sum(n),6)}
def original():
 selftest()
 need(os.getenv("GITHUB_REPOSITORY")==REPO and
      os.getenv("GITHUB_EVENT_NAME")=="push" and
      os.getenv("GITHUB_REF")=="refs/heads/"+BRANCH and
      os.getenv("GITHUB_RUN_ATTEMPT")=="1",
      "OFFICIAL_CUSTODY_FIRST_ONLY")
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.shallow_m5_support_v2_production import (
  decrypt_synthetic_package,encrypt_shard,public_spki_sha256)
 from research_core_v4.laboratory.mxm_be_new_pepperstone_bidask_20261101 import (
  spreads,median_p90)
 pub=ROOT/"research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
 need(public_spki_sha256(pub)==FP,"EXISTING_CUSTODY_RECIPIENT")
 with tempfile.TemporaryDirectory(prefix="mxm-be-source-quote-") as directory:
  tmp=Path(directory)
  key,fp=_private_key_from_secret(tmp)
  need(fp==FP,"CUSTODY_KEY_FINGERPRINT")
  source=tmp/"source";source.mkdir()
  subprocess.run(["gh","run","download",str(RUN),"-R",REPO,
    "-n",ARTIFACT_NAME,"-D",str(source)],check=True,capture_output=True,text=True,timeout=120)
  encrypted=(source/"original-bidask.mxmenc").read_bytes()
  need(digest(encrypted)==CIPHER,"AUTHENTIC_CIPHERTEXT_SHA")
  public=json.loads((source/"public.json").read_bytes())
  need(public["schema"]=="mxm.be.pepperstone-new-read-only-bidask.v1" and
       public["authentication"]=="AUTHORIZED_LIVE_VIEW_ACCOUNT_FINGERPRINT_VERIFIED" and
       public["original_cipher_sha256"]==CIPHER and
       public["private_plain_sha256"]==PLAINTEXT and
       public["requested_instrument_names"]==list(SYMBOLS) and
       public["source_time_windows"]==[list(x) for x in WINDOWS] and
       public["complete_two_sided_windows"]==8 and
       public["broker_orders"]==0 and public["cloud_activations"]==0,
       "AUTHENTIC_SOURCE_PUBLIC_RECEIPT")
  raw=decrypt_synthetic_package(encrypted,private_key=key)
  need(digest(raw)==PLAINTEXT,"AUTHENTIC_PLAIN_SHA")
  private=json.loads(raw)
  need(type(private) is list and len(private)==8,"PRIVATE_EIGHT_WINDOWS")
  per=[];details=[]
  for symbol in SYMBOLS:
   for window in range(2):
    matches=[x for x in private if x["symbol"]==symbol and x["window"]==window]
    need(len(matches)==1,"EXACT_SYMBOL_WINDOW_JOIN")
    x=matches[0];start,end=map(stamp,WINDOWS[window])
    bid=x["bid"];ask=x["ask"]
    need(not bid["has_more"] and not ask["has_more"],
         "INCOMPLETE_BROKER_SIDE")
    bb=validate_ticks(bid["ticks"],start,end)
    aa=validate_ticks(ask["ticks"],start,end)
    item=x["derived_pairing"];computed=median_p90(spreads(bb,aa))
    need(all(computed[k]==item[k] for k in computed) and
         item["bid_events"]==len(bb) and item["ask_events"]==len(aa),
         "RECONCILE_FROZEN_SOURCE_SPREAD_AND_COUNTS")
    result=examine(bb,aa,start,end)
    per.append({"symbol":symbol,"window":window,
      "date_utc":WINDOWS[window][0][:10],
      "original_quote_pairs":item["paired_observations"],**summarize(result)})
    details.extend([{"symbol":symbol,"window":window,**e}
       for e in result["observations"]])
  need(len(per)==8,"ENTIRE_PREDECLARED_POPULATION")
  cohorts={}
  for window,label in ((0,"earlier_development_oct27"),(1,"later_temporal_holdout_oct29")):
   group=[x for x in per if x["window"]==window]
   observations=[x for x in details if x["window"]==window]
   cohorts[label]={
    "signals":sum(x["signals"] for x in group),
    "complete":len(observations),
    "right_censored":sum(x["no_later_entry_quote"]+x["no_later_exit_quote"] for x in group),
    "mean_after_bidask_zero_commission_bps":round(statistics.mean(
      x["after_bidask_zero_fee_bps"] for x in observations),6) if observations else None,
    "mean_gross_mid_bps":round(statistics.mean(
      x["gross_mid_bps"] for x in observations),6) if observations else None}
  output={"schema":"mxm.be.quote-reversal-one-original-bidask-development.v1",
   "hypothesis":"STRICT_PRIOR_20S_MID_REVERSAL_OVER_2X_SPREAD_HOLD_20S",
   "source_run_id":RUN,"source_head":SOURCE_HEAD,
   "source_cipher_sha256":CIPHER,"frozen_instruments":SYMBOLS,
   "frozen_windows":WINDOWS,"symbol_window_results":per,
   "chronological_cohorts":cohorts,
   "qualification":"NOT_QUALIFIED_UNLESS_INDEPENDENT_BROKER_NET_EUR_PROVEN",
   "revenue_claim":"NONE_ZERO_COMMISSION_OPTIMISTIC_BIDASK_PROXY",
   "real_margin_200_eur_funding_verified":False,
   "native_instrument_fees_or_swaps_charged":False,
   "fills_or_live_quote_execution_verified":False,
   "independent_broker_hard21":False,
   "source_cost_aggregates_observed_before_hypothesis":True,
   "individual_price_outcomes_unopened_at_precommit":True,
   "independent_strategy_confirmation":False,
   "broker_requests":0,"orders":0,
   "cloud_activations":0,"earlier_window_tuned":False,
   "later_window_retuned":False,"sealed_negative_config_protected":True,
   "alpha_promotion":False}
  OUT.mkdir(parents=True,exist_ok=False)
  encrypted_output=OUT/"individual-economic.mxmenc"
  encrypt_shard(json.dumps(details,sort_keys=True,separators=(",",":")).encode(),
   public_key=pub,output=encrypted_output)
  output["encrypted_trades_sha256"]=digest(encrypted_output.read_bytes())
  (OUT/"public.json").write_text(json.dumps(output,sort_keys=True,separators=(",",":"))+"\n")
  print("MXM_BE_FRESH_BIDASK_PREDICTIVE_FIRST_ORIGINAL "+
    json.dumps(output,sort_keys=True),flush=True)
if __name__=="__main__":
 import sys
 need(sys.argv[1:] in (["selftest"],["original"]),"CLI_SCOPE")
 selftest() if sys.argv[1:]==["selftest"] else original()
