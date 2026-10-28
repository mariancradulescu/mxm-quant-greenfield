"""Finite, non-ordering DEVELOPMENT Stage-A comparative screen on preserved Pepperstone H1.
Three prospectively fixed distinct mechanisms; never extends source, retunes, or reuses closed identities.
"""
import collections, datetime as dt, hashlib, json, math, os, tempfile
from pathlib import Path
from statistics import median
from research_core_v4.laboratory.common import need
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"verification"/"finite-compare-20261028"
SOURCE={
 1:{"release_id":409747426,"asset_id":631098100,"ciphertext_sha256":"c33f401a97d06e2efe31e49f37a1f977238b41b66eb1d939b1d6700fb2530915"},
 250:{"release_id":409747426,"asset_id":631098274,"ciphertext_sha256":"809e20a51550ad50bc6ac4a8df524deba47d640f5a0d35454b496ffd2a9d3c2f"}
}
AUTH="evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json"
SPEC="research_core_v4/laboratory/FINITE_H1_COMPARATIVE_20261028_V1.json"
START=int(dt.datetime(2026,8,3,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,8,31,tzinfo=dt.timezone.utc).timestamp())
H=3600
NOMINAL_EUR=1000.0
IDENTITIES=("V4-COMP-20261028-WICK","V4-COMP-20261028-ONLINE","V4-COMP-20261028-FX")
def encode(x):return (json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def validate():
 s=json.loads((ROOT/SPEC).read_bytes())
 need(s["schema"]=="mxm.v4.finite-multimechanism-stage-a.v1" and s["state"]=="FROZEN_BEFORE_OUTCOMES","FROZEN")
 need(s["identities"]==list(IDENTITIES) and s["identity_reservations"]==3 and s["max_outcomes"]==3,"ATTEMPTS")
 need(s["source"]==SOURCE and s["start_utc"]=="2026-08-03T00:00:00Z" and s["end_utc"]=="2026-08-31T00:00:00Z","SOURCE")
 need(s["notional_eur"]==1000 and s["hold_h"]==2 and s["entry_delay_h"]==1,"TIMING")
 need(s["authorities"]["cost"]==AUTH and s["protected_forward_opened"] is False and s["broker_requests"]==0 and s["orders"]==0,"BOUNDARIES")
 cost=json.loads((ROOT/AUTH).read_bytes())
 need(cost["cost_state"]=="CONSERVATIVE_BOUND" and cost["status"]=="FROZEN_PRE_C017_C022_ECONOMIC_OUTCOMES","COST_FROZEN")
 c=cost["symbols"]["SpotCrude"]
 need(c["source_friction_state"]=="FRICTION_PASS" and c["buy_feasibility"]=="EUR200_MIN_VOLUME_FEASIBLE" and c["sell_feasibility"]=="EUR200_MIN_VOLUME_FEASIBLE","BROKER_SCOPE")
 need(c["roundtrip_cost_fraction"]==0.0004207461369287441 and cost["rule"]["fixed_stage_a_abs_entry_notional_eur"]==1000,"COST_CHANGED")
 return s,c["roundtrip_cost_fraction"]
def week(t):
 d=dt.datetime.fromtimestamp(t,dt.timezone.utc).isocalendar()
 return str(d.year)+"-W"+str(d.week).zfill(2)
def get_bars(value,sid):
 need(value["schema"]=="mxm.wide.private.h1.v1" and value["identity"]["sid"]==sid and value["same_native_account"] is True,"ORIGINAL_ID")
 rows={}
 for k,v in value["bars"].items():
  t=int(k)
  if START-5*86400<=t<END:
   need(t%H==0 and len(v)>=4,"H1")
   p=tuple(float(z) for z in v[:4])
   need(all(math.isfinite(x) and x>0 for x in p) and p[2]<=min(p[0],p[3])<=max(p[0],p[3])<=p[1],"BAR_INVALID")
   need(t not in rows,"DUPLICATE")
   rows[t]=p
 return rows
def med_abs_move(series,t,n=24):
 v=[]
 for j in range(1,n+1):
  a=series.get(t-H*j);b=series.get(t-H*(j-1))
  if not a or not b:break
  v.append(abs(b[3]/a[3]-1))
 return median(v) if len(v)==n else None
def decision(model,t,oil,fx):
 now=oil.get(t)
 prior=oil.get(t-H)
 if now is None or prior is None:return None,"OBSERVATION_MISSING"
 z=med_abs_move(oil,t,24)
 if z is None or z<=0:return None,"WARMUP_OR_GAP"
 change=now[3]/prior[3]-1
 if model==IDENTITIES[0]:
  # Exceptional intra-hour wick rejection, not another mean-reversion hold/threshold grid.
  span=now[1]-now[2]
  if span<=0 or span/now[3]<2.5*z:return 0,"NO_SIGNAL"
  upper=(now[1]-max(now[0],now[3]))/span
  lower=(min(now[0],now[3])-now[2])/span
  if upper>=0.6:return -1,"SIGNAL"
  if lower>=0.6:return 1,"SIGNAL"
  return 0,"NO_SIGNAL"
 if model==IDENTITIES[1]:
  # Causal finite-state conditional response: all training labels settled by the decision.
  state=1 if change>z else -1 if change< -z else 0
  if not state:return 0,"NO_SIGNAL"
  samples=[]
  for k in range(5,101):
   u=t-k*H;a=oil.get(u);b=oil.get(u-H)
   entry=oil.get(u+2*H);exit=oil.get(u+4*H)
   if not a or not b or not entry or not exit:continue
   vz=med_abs_move(oil,u,24)
   if vz is None or vz<=0:continue
   cls=1 if a[3]/b[3]-1>vz else -1 if a[3]/b[3]-1< -vz else 0
   if cls==state:samples.append(exit[0]/entry[0]-1)
  if len(samples)<12:return 0,"TRAIN_SUPPORT_INSUFFICIENT"
  mean=sum(samples)/len(samples)
  if abs(mean)<=0.0004207461369287441*1.5:return 0,"COST_HURDLE"
  return (1 if mean>0 else -1),"SIGNAL"
 if model==IDENTITIES[2]:
  # Prior-completed FX shock as independent information, no reference currency conversion.
  f=fx.get(t);fp=fx.get(t-H)
  fm=med_abs_move(fx,t,24)
  if f is None or fp is None or fm is None or fm<=0:return None,"FX_SUPPORT_MISSING"
  change_fx=f[3]/fp[3]-1
  if abs(change_fx)<2.0*fm or abs(change)>z:return 0,"NO_SIGNAL"
  # USD weakening (EURUSD up) => commodity upward hypothesis.
  return (1 if change_fx>0 else -1),"SIGNAL"
 raise ValueError("UNKNOWN_MODEL")
def evaluate(oil,fx,cost):
 result=[]
 for model in IDENTITIES:
  raw=0;settled=0;gross=0.;costs=0.;last=-10**16;counts=collections.Counter()
  missing=collections.Counter();by_week=collections.defaultdict(lambda:{"signals":0,"settled":0,"gross_eur":0.,"coarse_net_eur":0.})
  for t in range(START,END,H):
   direction,reason=decision(model,t,oil,fx)
   if direction is None:
    missing[reason]+=1
    continue
   if direction==0:
    counts[reason]+=1
    continue
   if t-last<3*H:
    counts["CONCURRENT_SIGNAL_BLOCKED"]+=1
    continue
   last=t;raw+=1;w=week(t);by_week[w]["signals"]+=1
   entry=t+2*H;exit=t+4*H
   if exit>=END:
    missing["RIGHT_CENSORED"]+=1
    continue
   a=oil.get(entry);b=oil.get(exit)
   if a is None or b is None:
    missing["ENTRY_OR_EXIT_SUPPORT_MISSING"]+=1
    continue
   g=NOMINAL_EUR*direction*(b[0]/a[0]-1)
   fee=NOMINAL_EUR*cost
   gross+=g;costs+=fee;settled+=1
   by_week[w]["settled"]+=1
   by_week[w]["gross_eur"]+=g;by_week[w]["coarse_net_eur"]+=g-fee
  net=gross-costs
  # Do not promote if some signaled trades cannot be settled with fixed rules.
  valid=raw>0 and settled==raw and not missing["RIGHT_CENSORED"] and not missing["ENTRY_OR_EXIT_SUPPORT_MISSING"]
  status=("DATA_INSUFFICIENT" if not valid else "GROSS_EDGE_FAIL" if gross<=0 else "COARSE_NET_FAIL" if net<=0 else "EXPLORATORY_POSITIVE_NOT_CERTIFIED")
  weeks=[str(2026)+"-W"+str(w) for w in (32,33,34,35)]
  sums={w:{k:round(v,8) if isinstance(v,float) else v for k,v in by_week[w].items()} for w in weeks}
  result.append({"id":model,"status":status,"causal_signals":raw,"settled_opportunities":settled,
   "gross_eur_fixed_notional":round(gross,8),"friction_proxy_eur":round(costs,8),
   "conditional_net_eur":round(net,8),"per_signal_cost_fraction":cost,
   "weeks":sums,"rejections":dict(missing),"other_decisions":dict(counts),
   "weeks_at_least_21_signals":sum(v["signals"]>=21 for v in sums.values()),
   "positive_net_weeks":sum(v["coarse_net_eur"]>0 for v in sums.values()),
   "stage_b_admission":False,"historical_broker_fills_verified":False})
 return result
def selftest():
 t0=START-5*86400
 oil={t0+i*H:(70.0+i*.003,70.1+i*.003,69.9+i*.003,70.0+i*.003) for i in range(800)}
 fx={t0+i*H:(1.10+i*.000001,1.11+i*.000001,1.09+i*.000001,1.10+i*.000001) for i in range(800)}
 z=evaluate(oil,fx,.0004207461369287441)
 need(len(z)==3 and [x["id"] for x in z]==list(IDENTITIES),"SELFTEST_IDENTITIES")
 need(all(x["gross_eur_fixed_notional"]==0 for x in z),"SELFTEST_NO_HINDSIGHT")
 print("MXM_FINITE_COMPARE_SELFTEST_PASS")
def main():
 import sys
 if sys.argv[1:]==["--selftest"]:selftest();return
 need(sys.argv[1:]==["--run"],"MODE")
 need(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield"
  and os.environ.get("GITHUB_REF_NAME")=="mxm-remediation-p0-p4-20261015-v1"
  and os.environ.get("GITHUB_EVENT_NAME")=="push"
  and os.environ.get("GITHUB_RUN_ATTEMPT")=="1","EXACT_CONTEXT")
 s,cost=validate()
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
 OUT.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as temp:
  key,fp=_private_key_from_secret(Path(temp))
  need(fp==FP,"CUSTODY_FINGERPRINT")
  sources={};provenance={}
  for sid,b in SOURCE.items():
   original,proof=load_asset(key,fp,Path(temp),b)
   sources[sid]=get_bars(original,sid);provenance[str(sid)]=proof
 result=evaluate(sources[250],sources[1],cost)
 doc={"schema":"mxm.v4.finite-comparative-development-result.v1",
  "run_id":int(os.environ["GITHUB_RUN_ID"]),"source_head":os.environ["GITHUB_SHA"],
  "source_provenance":provenance,"manifest_sha256":sha((ROOT/SPEC).read_bytes()),
  "cost_authority_sha256":sha((ROOT/AUTH).read_bytes()),
  "source_window":["2026-08-03T00:00:00Z","2026-08-31T00:00:00Z"],
  "source_rows":{str(k):len(v) for k,v in sources.items()},
  "economic_attempts_opened":3,"identity_reservations":3,"legacy_prior_attempts":16,
  "existing_budget_consumed_not_refunded":True,"new_broker_requests":0,"orders":0,
  "cloud_activated":False,"protected_forward_opened":False,"stage_b_executed":False,
  "cost_claim":"PREEXISTING_CONSERVATIVE_BOUND_NOT_HISTORICAL_EXECUTION_TRUTH",
  "notional_claim":"FIXED_EUR1000_STAGE_A_SCREENING_ONLY_NOT_REALIZED_EUR200_POSITION",
  "fee_limitations":["historical_slippage_unverified","funding_unverified","bid_ask_path_unverified"],
  "independent_confirmation":False,"hard21_verified":False,"models":result}
 (OUT/"receipt.json").write_bytes(encode(doc))
 print("MXM_NEW_FINITE_COMPARATIVE_ECONOMICS "+json.dumps(doc,sort_keys=True))
if __name__=="__main__":main()
