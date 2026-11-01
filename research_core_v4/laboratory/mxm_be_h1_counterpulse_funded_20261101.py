"""One first-only H1 12h/4h counter-pulse economic DEVELOPMENT trial.
Reuses authenticated Pepperstone H1 (4 pinned originals), the registered V4
Laboratory and the existing native C# shared funded account. No new cBot.
Costs are *dated scenarios*, NOT historical BID/ASK or verified fills.
No closed configurations are re-executed. No broker contact or orders.
"""
from __future__ import annotations
import collections
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import subprocess
import tempfile
from decimal import Decimal as D
from pathlib import Path
from research_core_v4.laboratory.common import need,encoded,digest
from research_core_v4.laboratory.budgets import TrialBook,historical_accounting
from research_core_v4.laboratory.programs import Laboratory
from research_core_v4.laboratory import portfolio_programme as shared

ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/"research_core_v4/laboratory/MXM_BE_H1_COUNTERPULSE_FUNDED_20261101.json"
OUT=ROOT/"verification/mxm-be-h1-counterpulse-funded-20261101"
H=3600
ID="V4-H1-COUNTERPULSE-COST-AWARE-20261101"
PROGRAM="MXM_BE_H1_COUNTERPULSE_FUNDED_20261101"
SRC_RELEASE=409747426
SOURCE_IDS={1,5,111,250}
# No post-hoc parameter search; fixed before any individual original outcomes.
SLOW_H=12
FAST_H=4
HOLD_DECISIONS=4
COST_HURDLE=3
MIN_COUNTER_FRACTION=D("0.25")
MAX_COUNTER_FRACTION=D("0.75")

def need_eq(x,y,tag):need(x==y,"COUNTERPULSE_"+tag)
def qtime(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat().replace("+00:00","Z")
def iso_week(ts):return dt.datetime.fromtimestamp(ts,dt.timezone.utc).strftime("%G-W%V")
def spec():
 p=json.loads(SPEC.read_bytes())
 need_eq(p["id"],ID,"ID")
 need_eq(p["programme"],PROGRAM,"PROGRAMME")
 need_eq(p["risk"]["initial_eur"],200,"FUNDED_200")
 need_eq(p["orders"],0,"NO_ORDERS")
 need(p["cloud"] is False and p["max_authentic_attempts"]==1,"COUNTERPULSE_SCOPE")
 need_eq({int(k) for k in p["source"]["assets"]},SOURCE_IDS,"FOUR_ORIGINALS")
 for f,expected in p["implementation_sha256"].items():
  need(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==expected,"COUNTERPULSE_IMPLEMENTATION_CHANGED")
 shared.specification() # Source-priced scenario, minimum units, old programme frozen SHA are still genuine.
 return p

def choose(t,corpus,p):
 """At H1 time t, only bars with OPEN <= t-H are read. No target peek."""
 terms=p["cost_scenario"]["instruments"]; fx=corpus[1].get(t-H)
 if fx is None or fx[3]<=0:return None
 to_eur=D(1)/fx[3]
 feasible=[]
 for sid,name in sorted(shared.ROSTER.items()):
  history=corpus[sid]
  # Slow = completed 12h displacement; fast = last completed 4h adverse move.
  # Strict H1 continuity over all thirteen prior bars (no weekend compression).
  if not all(t-j*H in history for j in range(1,SLOW_H+2)):continue
  last=history[t-H][3];slow0=history[t-(SLOW_H+1)*H][3]
  fast0=history[t-(FAST_H+1)*H][3]
  slow=(last/slow0)-1;fast=(last/fast0)-1
  if slow==0 or slow*fast>=0 or not(MIN_COUNTER_FRACTION<=abs(fast/slow)<=MAX_COUNTER_FRACTION):
   continue
  broker=terms[name];units=D(str(broker["units"]))
  spread=D(str(broker["spread"]));slip=D(str(broker["slippage"]))
  sidefee=D(str(broker["fee_eur"]));stop=D(str(broker["stop"]))
  cost=(spread+2*slip)*units*to_eur+2*sidefee
  projected=abs(last-slow0)*units*to_eur
  stop_risk=stop*units*to_eur+cost
  margin=D(str(broker["margin_eur"]))
  if not(0<cost and projected>=COST_HURDLE*cost and
         stop_risk<=D(2) and 0<margin<=D(80) and D(200)-margin-cost>=D(120)):
   continue
  # Prospective opportunity-to-friction score, deterministic tie by symbol.
  feasible.append((projected/cost,name,1 if slow>0 else -1))
 if not feasible:return None
 best=sorted(feasible,key=lambda x:(-x[0],x[1]))[0]
 return (best[1],best[2])

def targets(corpus,p):
 """Hold at most 4 decisions, leave flat when unsupported and at session end.
 A four-hour signal is not a fixed-count churn generator to force HARD21."""
 result=[];held=None;expires=0;counts=collections.Counter()
 for t in shared.day_hours(range(7,16)):
  hour=dt.datetime.fromtimestamp(t,dt.timezone.utc).hour
  if hour==7:held=None
  if held is not None and t<expires:
   choice=held;counts["held"]+=1
  else:
   choice=choose(t,corpus,p)
   held=choice
   expires=t+HOLD_DECISIONS*H
   counts["new_candidate" if choice else "flat"]+=1
  if choice:
   result.append({"BoundaryUtc":qtime(t),"Symbol":choice[0],"Direction":choice[1]})
 return result,dict(counts)

def selftest():
 p=json.loads(SPEC.read_text())
 need_eq(p["id"],ID,"ID")
 need_eq(SLOW_H,12,"SLOW")
 need_eq(FAST_H,4,"FAST")
 need_eq(HOLD_DECISIONS,4,"HOLD")
 need_eq(COST_HURDLE,3,"HURDLE")
 base=shared.START
 # Artificial vector yields a 12h upward net displacement and an adverse
 # 4h pullback, but never tests future prices or C# economic results.
 def fake():
  m={}
  for j in range(14):
   t=base-(13-j)*H
   last=D("1.10") if j==0 else (D("1.15") if j<=8 else D("1.125"))
   m[t]=(last,last,last,last)
  return m
 corpus={1:{base-H:(D("1.10"),)*4},5:fake(),111:{},250:{}}
 observed=choose(base,corpus,p)
 need_eq(observed,("AUDUSD",1),"CAUSAL_COUNTERPULSE")
 # Flip the last completed 4h movement to agree with the 12h displacement.
 m=corpus[5];last=m[base-H][3]
 for j in range(1,6):
  t=base-j*H;m[t]=(D("1.16"),)*4
 need(choose(base,corpus,p) is None,"COUNTERPULSE_FUTURE_FREE")
 print("MXM_BE_H1_COUNTERPULSE_COST_FUNDED_SOURCE_BLIND_SUCCESS")

def admit():
 p=spec()
 need(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield"
      and os.environ.get("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1"
      and os.environ.get("GITHUB_EVENT_NAME")=="push"
      and os.environ.get("GITHUB_RUN_ATTEMPT")=="1","COUNTERPULSE_FIRST_OFFICIAL")
 def get(s):return json.loads(subprocess.check_output(
     ["gh","api","repos/mariancradulescu/mxm-quant-greenfield/"+s],text=True))
 head=os.environ["GITHUB_SHA"]
 need(get("git/ref/heads/mxm-remediation-p0-p4-20261015-v1")["object"]["sha"]==head,
      "COUNTERPULSE_HEAD")
 parents=get("commits/"+head)["parents"]
 need(len(parents)==2,"COUNTERPULSE_REVIEWED_MERGE")
 history=get("actions/workflows/mxm-be-h1-counterpulse-funded-20261101.yml/runs?per_page=100")
 need(history["total_count"]<=100 and history["total_count"]==len(history["workflow_runs"]),
      "COUNTERPULSE_RUN_INVENTORY")
 pushes=[z for z in history["workflow_runs"]
         if z["event"]=="push" and z["head_branch"]=="mxm-remediation-p0-p4-20261015-v1"]
 need(len(pushes)==1 and pushes[0]["id"]==int(os.environ["GITHUB_RUN_ID"]),
      "COUNTERPULSE_NO_SECOND_OUTCOME")
 runs=get("actions/runs?event=pull_request&per_page=100")["workflow_runs"]
 success={r["name"] for r in runs if r["head_sha"]==parents[1]["sha"] and r["conclusion"]=="success"}
 need({"MXM R3 protected technical installation CI",
       "MXM CSharp Pepperstone protected gateway CI"}<=success,
      "COUNTERPULSE_PROTECTED_CI")
 need(not OUT.exists(),"COUNTERPULSE_NO_REWRITE")
 print("MXM_BE_H1_COUNTERPULSE_FIRST_PROSPECTIVE_OUTCOME_ADMITTED")

def run():
 p=spec();history=historical_accounting(ROOT)
 need(history["reconciled"] and history["V2"]["used"]==21,"COUNTERPULSE_PRESERVE_BOOK")
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 recipient=ROOT/"research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
 need(public_spki_sha256(recipient)==FP,"COUNTERPULSE_RECIPIENT")
 OUT.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory() as directory:
  tmp=Path(directory);key,fp=_private_key_from_secret(tmp)
  need(fp==FP,"COUNTERPULSE_CUSTODY_FINGERPRINT")
  corpus={};proof={}
  for raw,asset in p["source"]["assets"].items():
   sid=int(raw)
   original,provenance=load_asset(key,fp,tmp,{"release_id":SRC_RELEASE,
      "asset_id":asset["asset_id"],"ciphertext_sha256":asset["sha256"]})
   corpus[sid]=shared.decode(original,sid)
   proof[raw]=provenance
  coverage=shared.support(corpus)
  # This source-mask gate uses only timestamps, never profits/labels.
  evaluated=coverage["classification"]=="SOURCE_ADMITTED"
  original={"spec":p,"proof":proof,"coverage":coverage,"outcome_count":0}
  public={"schema":"mxm.be.h1-counterpulse-first-funded-result.v1",
    "head":os.environ["GITHUB_SHA"],"run_id":int(os.environ["GITHUB_RUN_ID"]),
    "initial_eur":200,"resets":0,"orders":0,"cloud":False,"broker_requests":0,
    "cost_status":"DATED_BROKER_TERMS_PLUS_HYPOTHETICAL_H1_OHLC_FRICTION",
    "historical_bidask_or_fills_proven":False,"independent_holdout":False,
    "HARD21_broker_certified":False,"source_admission":coverage["classification"],
    "economically_qualified_for_native_bot":False,"identity":ID}
  if evaluated:
   targets_,decision_counts=targets(corpus,p)
   original["decision_counts"]=decision_counts
   original["targets"]=targets_
   manifest=shared.programme(p)
   lab=Laboratory(manifest,history,TrialBook({"V4":1,"V2":history["V2"]["limit"]},
     {"V4":0,"V2":history["V2"]["used"]}))
   lab.execute("register")
   candidate=lab.state["results"]["register"]["value"]
   feed=shared.build_feed(corpus,targets_,candidate["spec_hash"],p)
   # C# account native, all 200 EUR shared, source-aware events.
   lab.authenticated_csharp_feed=feed
   lab.execute("account");lab.execute("report")
   result=lab.state["results"]["account"]["value"]
   metrics=shared.account_checks(result)
   original["outcome_count"]=1;original["feed"]=feed
   original["metrics"]=metrics;original["result"]=result
   public.update({"economic_outcomes":1,"candidate_count":len(targets_),
     "decision_counts":decision_counts,"metrics":metrics,
     "observed_periods":{k:{p:{"observations":r["observations"],
        "first_equity_eur":r["first"]["MarkedEquityEur"],
        "last_equity_eur":r["last"]["MarkedEquityEur"]}
        for p,r in v.items()} for k,v in result["periods"].items()}})
  else:public.update({"economic_outcomes":0,"reason":"PRICE_BLIND_TEMPORAL_SUPPORT_FAIL"})
  plaintext=encoded(original)
  encrypt_shard(gzip.compress(plaintext,mtime=0),public_key=recipient,
                output=OUT/"private.mxmenc")
  public.update({"private_plain_sha256":hashlib.sha256(plaintext).hexdigest(),
    "private_cipher_sha256":hashlib.sha256((OUT/"private.mxmenc").read_bytes()).hexdigest()})
  (OUT/"receipt.json").write_bytes(encoded(public))
  print("MXM_BE_H1_COUNTERPULSE_FUNDED_FIRST "+json.dumps(public,sort_keys=True),flush=True)

def cold():
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack
 from research_core_v4.successor_c_20261018.readback import FP
 doc=json.loads((OUT/"receipt.json").read_bytes())
 raw=(OUT/"private.mxmenc").read_bytes()
 need(hashlib.sha256(raw).hexdigest()==doc["private_cipher_sha256"],"COUNTERPULSE_CIPHER")
 with tempfile.TemporaryDirectory() as td:
  tmp=Path(td);key,fp=_private_key_from_secret(tmp)
  need(fp==FP,"COUNTERPULSE_COLD_FINGERPRINT")
  plaintext=unpack(owner.bounded_decrypt(raw,key,tmp))
 need(hashlib.sha256(plaintext).hexdigest()==doc["private_plain_sha256"],"COUNTERPULSE_COLD_SHA")
 original=json.loads(plaintext)
 if original["outcome_count"]:
  metrics=shared.account_checks(original["result"])
  need(metrics==original["metrics"]==doc["metrics"],"COUNTERPULSE_COLD_EUR200_LEDGER")
 need(original["outcome_count"]==doc["economic_outcomes"],"COUNTERPULSE_COLD_ECONOMIC_COUNT")
 print("MXM_BE_H1_COUNTERPULSE_COLD_OK",doc["run_id"],flush=True)

if __name__=="__main__":
 import sys
 need(len(sys.argv)==2 and sys.argv[1] in ("selftest","admit","run","cold"),
      "COUNTERPULSE_USAGE")
 {"selftest":selftest,"admit":admit,"run":run,"cold":cold}[sys.argv[1]]()
