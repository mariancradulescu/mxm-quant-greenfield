"""SOURCE-FIRST finite comparative DEVELOPMENT economics using existing Pepperstone H1 custody.
Source observability comes before economic identity admission. No trading or new collection.
"""
import collections
import datetime as dt
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from research_core_v4.laboratory.common import need

ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/"research_core_v4/laboratory/SOURCE_FIRST_DIVERSE_H1_20261028_V1.json"
AUTH=ROOT/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json"
OUT=ROOT/"verification/source-first-diverse-h1"
H=3600
START=int(dt.datetime(2026,8,3,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,8,31,tzinfo=dt.timezone.utc).timestamp())
SOURCES={
 1:(631098100,"c33f401a97d06e2efe31e49f37a1f977238b41b66eb1d939b1d6700fb2530915"),
 5:(631095492,"75602c6520cadce8e878e7dce607aa896dd025b3388b16b1f722699ebc455850"),
 111:(631086728,"2538248862212f2c7258a0e5183fc8e5b283f7c6fc84fd44de1fd4bf7948a16e"),
 250:(631098274,"809e20a51550ad50bc6ac4a8df524deba47d640f5a0d35454b496ffd2a9d3c2f")
}
TARGETS={5:"AUDUSD",111:"Copper",250:"SpotCrude"}
COSTS={5:0.00012605282979588124,111:0.0005268316490290482,250:0.0004207461369287441}
MODELS=("MOMENTUM_IMPULSE","VOLATILITY_COMPRESSION","CROSS_ASSET_RESIDUAL")
IDENTITIES=("V4-SUP-20261028-IMPULSE","V4-SUP-20261028-COMPRESSION","V4-SUP-20261028-RESIDUAL")
NOTIONAL=1000.
def digest(blob):return hashlib.sha256(blob).hexdigest()
def encode(value):return (json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def week(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime("%G-W%V")
def session(t):
 d=dt.datetime.fromtimestamp(t,dt.timezone.utc)
 return d.weekday()<5 and 7<=d.hour<=15
def validate():
 s=json.loads(SPEC.read_bytes())
 need(s["schema"]=="mxm.source-first-comparative-development.v1" and s["fixed_source_ids"]==sorted(SOURCES) and s["target_ids"]==sorted(TARGETS),"SPEC_SOURCE")
 need(s["mechanisms"]==list(MODELS) and s["conditional_identity_names"]==list(IDENTITIES),"SPEC_IDENTITIES")
 need(s["preflight_before_economic_identity"] is True and s["max_new_identity_reservations"]==3 and s["new_broker_requests"]==0 and s["orders"]==0 and s["protected_opened"] is False,"SCOPE")
 need(s["evaluation_interval"]==["2026-08-03T00:00:00Z","2026-08-31T00:00:00Z"] and s["decision_session_utc"]==[7,15] and s["hold_hours"]==2,"CALENDAR")
 need(s["min_causal_decisions_per_target"]==80 and s["min_observable_response_fraction"]==0.90 and s["min_eligible_weeks"]==3,"SUPPORT")
 cost=json.loads(AUTH.read_bytes())
 need(cost["status"]=="FROZEN_PRE_C017_C022_ECONOMIC_OUTCOMES" and cost["cost_state"]=="CONSERVATIVE_BOUND","COST_AUTH")
 for sid,name in TARGETS.items():
  r=cost["symbols"][name]
  need(r["roundtrip_cost_fraction"]==COSTS[sid] and r["source_friction_state"]=="FRICTION_PASS","COST_BIND")
 need(cost["rule"]["fixed_stage_a_abs_entry_notional_eur"]==1000,"NOTIONAL")
 return s,cost
def bars(original,sid):
 need(original["schema"]=="mxm.wide.private.h1.v1" and original["same_native_account"] is True and original["identity"]["sid"]==sid,"ORIGINAL_SOURCE")
 result={}
 for raw,bar in original["bars"].items():
  t=int(raw)
  if START-3*H<=t<END+5*H:
   need(t%H==0 and len(bar)>=4,"H1_GRID")
   p=tuple(float(z) for z in bar[:4])
   need(all(math.isfinite(z) and z>0 for z in p) and p[2]<=min(p[0],p[3]) and max(p[0],p[3])<=p[1],"H1_QUALITY")
   need(t not in result,"NO_DUPLICATES")
   result[t]=p
 return result
def causal_times(m):
 return [t for t in range(START,END,H) if session(t) and all(t-j*H in m for j in (0,1,2))]
def fulfilled(m,t):
 return all(t+j*H in m for j in (2,3,4))
def support(corpus):
 """No return, OHLC price or direction access in source admission."""
 profiles={}
 for sid in TARGETS:
  m=corpus[sid];c=causal_times(m)
  response=sum(fulfilled(m,t) for t in c)
  w=collections.Counter(week(t) for t in c)
  profiles[str(sid)]={"source_rows":len(m),"past_eligible_decisions":len(c),"response_complete":response,
   "response_missing":len(c)-response,"response_complete_fraction":response/len(c) if c else 0,
   "calendar_weeks":dict(sorted(w.items())),"eligible_weeks":sum(z>0 for z in w.values()),
   "passed":len(c)>=80 and len(w)>=3 and response>=0.90*len(c)}
 paired=0
 for t in causal_times(corpus[250]):
  if all(t-j*H in corpus[111] for j in (0,1,2)) and
     all(fulfilled(corpus[sid],t) for sid in (111,250)):paired+=1
 # Source evidence must justify each family, not merely the aggregate row count.
 passed=all(x["passed"] for x in profiles.values()) and paired>=60
 return {"profiles":profiles,"paired_copper_oil_support":paired,
  "source_admission": "PASS_BEFORE_IDENTITIES" if passed else "STOP_NO_IDENTITY_ADMITTED",
  "session_filter_frozen_before_outcomes":True,
  "market_closed_vs_collection_gap_disambiguated":False,
  "missing_future_not_imputed":True,
  "selection_observes_timestamps_only":True}
def signal(model,sid,t,corpus):
 m=corpus[sid];prevprev=m[t-2*H];prev=m[t-H];cur=m[t]
 r0=(cur[3]/prev[3]-1);r1=(prev[3]/prevprev[3]-1)
 range0=(cur[1]-cur[2])/cur[0];range1=(prev[1]-prev[2])/prev[0]
 if model==MODELS[0]:
  if range0<=1.15*range1 or abs(r0)<=0.45*range0:return 0,"NO_IMPULSE"
  return (1 if r0>0 else -1),"SIGNAL"
 if model==MODELS[1]:
  # Post-impulse volatility collapse: mean-reversion pressure after a move followed
  # by an hour whose observed range contracts.
  if range0>=0.80*range1 or abs(r1)<=0.55*range1:return 0,"NO_COMPRESSION"
  return (-1 if r1>0 else 1),"SIGNAL"
 if model==MODELS[2]:
  refsid=111 if sid in (5,250) else 250
  ref=corpus[refsid]
  if not all(t-j*H in ref for j in (0,1,2)):return None,"REFERENCE_FEATURE_MISSING"
  x=(ref[t][3]/ref[t-H][3]-1)
  residual=r0-x
  if abs(residual)<0.00035:return 0,"NO_RESIDUAL_DISLOCATION"
  # A true relative-change spread, not legacy EURUSD -> oil sign transmission.
  return (-1 if residual>0 else 1),"SIGNAL"
 raise ValueError("UNKNOWN_MODEL")
def evaluate(corpus,sup):
 need(sup["source_admission"]=="PASS_BEFORE_IDENTITIES","SUPPORT_BEFORE_ECONOMIC_IDENTITIES")
 identity_out=[]
 for model,ident in zip(MODELS,IDENTITIES):
  markets=[];total=collections.Counter()
  for sid,name in TARGETS.items():
   m=corpus[sid];decisions=causal_times(m)
   reasons=collections.Counter();weekly=collections.defaultdict(lambda:{"eligible":0,"signals":0,"settled":0,"gross_eur":0.,"coarse_cost_eur":0.,"coarse_net_eur":0.})
   signals=0;settled=0;gross=cost=0.;last_entry=-10**30
   for t in decisions:
    w=week(t);weekly[w]["eligible"]+=1
    side,why=signal(model,sid,t,corpus)
    if side is None:reasons[why]+=1;continue
    if side==0:reasons[why]+=1;continue
    if t+2*H < last_entry+2*H:
     reasons["SERIAL_OVERLAP_REJECTED"]+=1;continue
    last_entry=t+2*H
    signals+=1;weekly[w]["signals"]+=1
    if not fulfilled(m,t):
     reasons["POST_SIGNAL_PRICE_PATH_UNAVAILABLE"]+=1;continue
    a=m[t+2*H][0];b=m[t+4*H][0]
    g=NOTIONAL*side*(b/a-1);fee=NOTIONAL*COSTS[sid]
    gross+=g;cost+=fee;settled+=1
    weekly[w]["settled"]+=1;weekly[w]["gross_eur"]+=g
    weekly[w]["coarse_cost_eur"]+=fee;weekly[w]["coarse_net_eur"]+=g-fee
   total.update({"signals":signals,"settled":settled})
   weeks={k:{field:(round(v,6) if type(v) is float else v) for field,v in d.items()} for k,d in sorted(weekly.items())}
   net=gross-cost
   status="DATA_LIMITED_SIGNAL_CENSOR" if signals and settled<0.90*signals else "NO_SIGNAL" if not signals else "GROSS_EDGE_FAIL" if gross<=0 else "NET_COST_FAIL" if net<=0 else "EXPLORATORY_POSITIVE_UNCERTIFIED"
   markets.append({"instrument":name,"symbol_id":sid,"signal_count":signals,"settled":settled,
    "gross_eur":round(gross,6),"coarse_cost_eur":round(cost,6),"coarse_net_eur":round(net,6),
    "cost_fraction":COSTS[sid],"outcome":status,"rejections":dict(sorted(reasons.items())),
    "positive_net_weeks":sum(v["coarse_net_eur"]>0 for v in weekly.values()),"weekly":weeks})
  gross=sum(x["gross_eur"] for x in markets);net=sum(x["coarse_net_eur"] for x in markets)
  total_signals=sum(x["signal_count"] for x in markets)
  complete=sum(x["settled"] for x in markets)
  state="NO_CAUSAL_SIGNAL" if not total_signals else "DATA_LIMITED" if complete<0.90*total_signals else "GROSS_FAIL" if gross<=0 else "COARSE_NET_FAIL" if net<=0 else "DEVELOPMENT_POSITIVE_NOT_CERTIFIED"
  identity_out.append({"identity":ident,"family":model,"classification":state,"causal_signals":total_signals,
   "settled":complete,"gross_eur":round(gross,6),"cost_eur":round(gross-net,6),"net_estimated_eur":round(net,6),
   "per_market":markets,"stage_b_admitted":False,"independent_confirmation":False})
 return identity_out
def selftest():
 source={sid:{} for sid in SOURCES}
 t=START-3*H
 for i in range(670):
  ts=t+i*H
  if not session(ts) and dt.datetime.fromtimestamp(ts,dt.timezone.utc).weekday()>=5:continue
  for sid in TARGETS:
   p=1.0+0.01*sid+0.001*math.sin(i*0.5+sid)
   source[sid][ts]=(p,p+.0007,p-.0007,p+.0001)
  source[1][ts]=(1.1,1.11,1.09,1.1)
 a=support(source)
 need(a["source_admission"]=="PASS_BEFORE_IDENTITIES" and len(evaluate(source,a))==3,"SELFTEST_PATH")
 source[250].clear()
 need(support(source)["source_admission"]=="STOP_NO_IDENTITY_ADMITTED","SELFTEST_FAIL_CLOSED")
 print("MXM_SOURCE_FIRST_H1_SUPPORT_BEFORE_ECONOMICS_SELFTEST_PASS")
def main():
 import sys
 if sys.argv[1:]==["selftest"]:selftest();return
 need(sys.argv[1:]==["run"],"MODE")
 need(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield" and
  os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_RUN_ATTEMPT")=="1" and
  os.environ.get("GITHUB_REF_NAME")=="mxm-remediation-p0-p4-20261015-v1","GITHUB_SCOPE")
 s,_=validate()
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
 from research_core_v4.laboratory.budgets import historical_accounting
 account=historical_accounting(ROOT)
 need(account["reconciled"] and account["V2"]["remaining"]>=3,"BUDGET")
 with tempfile.TemporaryDirectory() as d:
  key,fp=_private_key_from_secret(Path(d));need(fp==FP,"ORIGINAL_CUSTODY")
  corpus={};originals={}
  for sid,(asset,digest_expected) in SOURCES.items():
   value,proof=load_asset(key,fp,Path(d),{"release_id":409747426,"asset_id":asset,"ciphertext_sha256":digest_expected})
   corpus[sid]=bars(value,sid);originals[str(sid)]=proof
  # NO identity is admitted before the source-only, price-free preflight.
  support_result=support(corpus)
  eligible=support_result["source_admission"]=="PASS_BEFORE_IDENTITIES"
  models=evaluate(corpus,support_result) if eligible else []
  doc={"schema":"mxm.source-first-comparative-economic-receipt.v1","run_id":int(os.environ["GITHUB_RUN_ID"]),
   "source_sha":os.environ["GITHUB_SHA"],"source_spec_sha256":digest(SPEC.read_bytes()),
   "cost_authority_sha256":digest(AUTH.read_bytes()),"original_sources":originals,
   "source_support":support_result,"identity_reservations_after_source_admission":3 if eligible else 0,
   "new_economic_models_executed":len(models),"models":models,
   "economic_qualifications":0,"stage_b":False,"source_resolutions":["H1"],
   "source_group":"PEPPERSTONE_AUTHENTICATED_DEVELOPMENT_OLD_RELEASE",
   "cost_state":"FROZEN_CONSERVATIVE_BOUND_NOT_HISTORICAL_BIDASK_FILL",
   "pnl_basis":"STAGE_A_FIXED_1000_EUR_NOT_REAL_EUR200_ACCOUNT",
   "causal_price_rule":"H1_FULL_BAR_KNOWN_AT_CLOSE_THEN_ENTRY_ON_NEXT_FOLLOWING_H1_OPEN_HOLD_2H",
   "cost_limitations":["historical_slippage_unverified","historical_funding_unverified","unobserved_historical_bidask_path"],
   "v2_used_unmodified":account["V2"]["used"],"v2_remaining_unmodified":account["V2"]["remaining"],
   "v4_separate_conditionally_opened_dependent_model_families":len(models),
   "no_protected_forward":True,"no_new_broker_requests":True,"orders":0,"cloud_activated":False}
  OUT.mkdir(parents=True,exist_ok=True)
  (OUT/"receipt.json").write_bytes(encode(doc))
  print("MXM_SOURCE_FIRST_COMPARATIVE_ECONOMICS "+json.dumps(doc,sort_keys=True),flush=True)
if __name__=="__main__":main()
