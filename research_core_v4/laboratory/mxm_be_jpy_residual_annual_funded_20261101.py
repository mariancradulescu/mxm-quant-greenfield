"""One DISTINCT, prospectively frozen AUDJPY vs three JPY crosses four-hour
relative-velocity residual. Exactly original Pepperstone M5-derived year-tape
source and existing C# EUR200 funded account, zero orders. No re-execution of
V4-JPY-FACTORED-DISCORDANCE-20261101: its old signal() is NEVER called.
All cost and risk amounts are hypothetical; existing broker min ticket authentic
as-of Sep 2026; 2025-26 spread, slippage, fills and intrabar stops NOT proven.
"""
from __future__ import annotations
import base64,collections,datetime as dt,hashlib,json,os,pathlib,subprocess,tempfile
from decimal import Decimal as D
from research_core_v4.laboratory.common import need,encoded,digest
from research_core_v4.laboratory.budgets import TrialBook,historical_accounting
from research_core_v4.laboratory.programs import Laboratory
from research_core_v4.laboratory.funded_account import execute as funded_execute
from research_core_v4.laboratory import native_h1_csharp_annual_receipt as original
from research_core_v4.laboratory import mxm_be_jpy_consensus_annual_funded_20261101 as shared
from research_core_v4.laboratory import portfolio_programme as contract

ROOT=pathlib.Path(__file__).resolve().parents[2]
SPEC=ROOT/"research_core_v4/laboratory/MXM_BE_JPY_RESIDUAL_ANNUAL_FUNDED_20261101.json"
OUT=ROOT/"verification/mxm-be-jpy-residual-annual-20261101"
IDENT="V4-JPY-FOURHOUR-FACTOR-RESIDUAL-20261101"
PROGRAM="MXM_BE_JPY_RESIDUAL_ANNUAL_FUNDED_20261101"
H=shared.H;FIRST=shared.FIRST;LAST=shared.LAST
TARGET=shared.TARGET;FACTOR=shared.FACTOR;SCOPE=shared.SCOPE
BASE_SPREAD=D(".04")
SOURCE_SHA=original.EXPECTED_PLAINTEXT_SHA
# NEVER derive thresholds from previously opened stage economic PnL.
RESIDUAL_MIN=D(".0015");COHERENCE_MAX=D(".008")
SCALE=D(".65");FRICTION_MULT=D("1.25")

def flag(x,msg):need(x,"MXM_BE_JPY_RESIDUAL_"+msg)
def pdoc():
 p=json.loads(SPEC.read_bytes())
 flag(p["id"]==IDENT and p["programme"]==PROGRAM and
     p["risk"]["initial_eur"]==200 and p["orders"]==0 and
     p["cloud"] is False and p["max_authentic_attempts"]==1,"FREEZE")
 flag(p["source"]["original_plain_sha256"]==SOURCE_SHA and
     p["cost_scenario"]["spreads_jpy"]==["0.02","0.04","0.08"],"SOURCE_SCENARIO")
 for path,sha in p["implementation_sha256"].items():
  blob=subprocess.check_output(["git","hash-object",path],cwd=ROOT,text=True).strip()
  flag(blob==sha,"PINNED_SHARED_IMPLEMENTATION")
 return p

def signal(t,m):
 # ALL source observations are completed H1 CLOSES ending no later than
 # t-1H; full five-hour interval must be uninterrupted on 4 instruments.
 if not all(all(t-k*H in m[s] for k in range(1,6)) for s in SCOPE):return None
 rates=[m[s][t-H]/m[s][t-5*H]-1 for s in FACTOR]
 # Cross-sectional median is robust to one asynchronous JPY peer.
 # This is NOT the closed 3h all-consensus / last-1h opposite-sign model.
 med=sorted(rates)[1]
 if max(rates)-min(rates)>COHERENCE_MAX:return None
 own=m[TARGET][t-H]/m[TARGET][t-5*H]-1
 residual=med-own
 if abs(residual)<RESIDUAL_MIN:return None
 fx=m["EURJPY"][t-H]
 projected=SCALE*abs(residual)*m[TARGET][t-H]*shared.UNITS/fx
 cost=(BASE_SPREAD+2*shared.SLIP)*shared.UNITS/fx+2*shared.FEE
 if projected<FRICTION_MULT*cost:return None
 return 1 if residual>0 else -1

def selftest():
 p=json.loads(SPEC.read_bytes())
 flag(p["id"]==IDENT and p["risk"]["initial_eur"]==200,"SELF_FREEZE")
 flag(RESIDUAL_MIN==D(".0015") and COHERENCE_MAX==D(".008"),"SELF_FROZEN_THRESHOLDS")
 m={s:{} for s in SCOPE};base=FIRST
 for s in SCOPE:
  for k in range(1,6):m[s][base-k*H]=D("100")
 # Four-hour EURJPY +0.6%; GBPJPY +0.5%; CHFJPY +0.4%;
 # AUDJPY -0.1%; expect factor-relative long independent of old model.
 for s,start,end in [("EURJPY","100","100.6"),("GBPJPY","100","100.5"),
                     ("CHFJPY","100","100.4"),("AUDJPY","100","99.9")]:
  m[s][base-5*H]=D(start);m[s][base-H]=D(end)
 flag(signal(base,m)==1,"SELF_DISTINCT_POSITIVE")
 for x in m.values():x[base+H]=D("10000000")
 flag(signal(base,m)==1,"SELF_FUTURE_CAUSALITY")
 # All private output numeric observations must be explicitly JSON-safe
 # BEFORE entering protected custody. This closes PR315's material defect.
 test={"settled":[[base,1,[str(D("100.123")),str(D("100.234"))]]]}
 json.loads(encoded(test))
 flag(json.loads(b'{"original":"json-no-gzip"}')["original"]=="json-no-gzip",
      "SELF_COLD_PLAINTEXT_IS_JSON")
 parts=sorted(original.CIPHER_DIR.glob("chunk-*.b64"))
 flag(len(parts)==7,"SELF_CIPHERTEXT_COUNT")
 cipher=b"".join(base64.b64decode(x.read_text(),validate=False) for x in parts)
 flag(hashlib.sha256(cipher).hexdigest()==original.EXPECTED_CIPHER_SHA,
      "SELF_CIPHER_SHA")
 print("MXM_JPY_RESIDUAL_ANNUAL_SOURCE_BLIND_AND_JSON_CUSTODY_SELFTEST_PASS")

def decisions(m):
 out=[];counts=collections.Counter()
 for t in range(FIRST,LAST,H):
  d=dt.datetime.fromtimestamp(t,dt.timezone.utc)
  if d.weekday()>=5 or not 7<=d.hour<=15:continue
  side=signal(t,m)
  if side is None:counts["flat"]+=1
  else:out.append((t,side));counts["signaled"]+=1
 return out,dict(counts)

def check_admit():
 flag(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield"
      and os.environ.get("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1"
      and os.environ.get("GITHUB_EVENT_NAME")=="push"
      and os.environ.get("GITHUB_RUN_ATTEMPT")=="1","ONE_FIRST_OFFICIAL")
 def api(path):
  return json.loads(subprocess.check_output(["gh","api",
   "repos/mariancradulescu/mxm-quant-greenfield/"+path],text=True))
 head=os.environ["GITHUB_SHA"]
 flag(api("git/ref/heads/mxm-remediation-p0-p4-20261015-v1")["object"]["sha"]==head,
      "HEAD")
 parents=api("commits/"+head)["parents"]
 flag(len(parents)==2 and parents[0]["sha"]==
      "ef4c2485b125fec5de735330abe474ce29081992","EXACT_PREVIOUS_HEAD")
 runs=api("actions/workflows/mxm-be-jpy-residual-annual-20261101.yml/runs?per_page=100")
 pushes=[r for r in runs["workflow_runs"] if r["event"]=="push" and
         r["head_branch"]=="mxm-remediation-p0-p4-20261015-v1"]
 flag(runs["total_count"]<=100 and len(pushes)==1 and
      pushes[0]["id"]==int(os.environ["GITHUB_RUN_ID"]), "NO_REPEAT")
 prs=api("actions/runs?event=pull_request&per_page=100")["workflow_runs"]
 done={r["name"] for r in prs if r["head_sha"]==parents[1]["sha"] and
       r["conclusion"]=="success"}
 flag({"MXM R3 protected technical installation CI",
       "MXM CSharp Pepperstone protected gateway CI"}<=done,"CI")
 flag(not OUT.exists(),"NO_PRIOR_OUTCOME")
 selftest();pdoc()
 print("MXM_JPY_RESIDUAL_FROZEN_FIRST_PROSPECTIVE_ADMITTED")

def results():
 p=pdoc();history=historical_accounting(ROOT)
 flag(history["reconciled"] and history["V2"]["used"]==21,"REGISTRY")
 private=os.environ.get("MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM")
 flag(private and "BEGIN" in private,"EXISTING_CUSTODY")
 OUT.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory() as directory:
  tmp=pathlib.Path(directory)
  chunks=sorted(original.CIPHER_DIR.glob("chunk-*.b64"))
  flag(len(chunks)==7,"ORIGINAL_PARTS")
  ciphertext=b"".join(base64.b64decode(q.read_text(),validate=False) for q in chunks)
  tape=json.loads(original.decrypt(ciphertext,private.encode(),tmp))
  corpus=shared.decode(tape);support=shared.source_admit(corpus)
  report={"schema":"mxm.be.jpy-fourhour-factor-residual-annual-first-native-funded.v1",
   "run_id":int(os.environ["GITHUB_RUN_ID"]),"head":os.environ["GITHUB_SHA"],
   "source_sha256":SOURCE_SHA,"source_admission":support,"capital_start_eur":200,
   "deposit_count":1,"resets":0,"orders":0,"cloud":False,"broker_requests":0,
   "timeframe_selected_by_original_data":"H1_DEVELOPMENT_SOURCE_NOT_OWNER_PREFERENCE",
   "instrument_selected_by_captured_min_ticket":"AUDJPY_1000_UNITS_31_02_EUR",
   "historical_bidask_cost_stop_fills_proven":False,
   "robust_edge_proven":False,"HARD21_verified":False,"independent_holdout":False,
   "original_closed_jpy_consensus_repeated":False,"identity":IDENT}
  private_out={"spec":p,"support":support,"source_sha256":SOURCE_SHA}
  if support["admitted"]:
   lab=Laboratory(contract.programme(p),history,
       TrialBook({"V4":1,"V2":history["V2"]["limit"]},
                 {"V4":0,"V2":history["V2"]["used"]}))
   lab.execute("register");candidate=lab.state["results"]["register"]["value"]
   targets,counts=decisions(corpus)
   signal_sha=hashlib.sha256(encoded(targets)).hexdigest()
   settled,censored=shared.after_observation(tape,targets)
   # Exact, explicit conversion of *only* source price Decimal values
   # before private data serialization; never round, truncate or expose them.
   settled_safe=[[t,side,[str(v) for v in prices]] for t,side,prices in settled]
   private_out.update({"targets":targets,"settled":settled_safe,
                       "censored":censored,"signal_sha":signal_sha})
   report.update({"proposals":len(targets),"observable":len(settled),
    "censored":len(censored),"causal_decisions_sha256":signal_sha,
    "signal_counts":counts})
   if settled:
    sensitivities={};by_week={}
    for spread in shared.SPREADS:
     feed=shared.feed(settled,candidate,spread)
     if spread==BASE_SPREAD:
      lab.authenticated_csharp_feed=feed
      lab.execute("account");lab.execute("report")
      outcome=lab.state["results"]["account"]["value"]
     else:outcome=funded_execute(candidate,feed,False)
     value=shared.reconcile(outcome)
     sensitivities[str(spread)]=value
     private_out["native_csharp_"+str(spread)]=outcome
     if spread==BASE_SPREAD:
      for w,q in outcome["periods"]["iso_weeks"].items():
       by_week[w]={"first_equity_eur":q["first"]["MarkedEquityEur"],
         "last_observed_equity_eur":q["last"]["MarkedEquityEur"],
         "observed_account_events":q["observations"],
         "calendar_week_end_mark_proven":False}
    report.update({"scenario_results":sensitivities,
      "baseline_weekly_equity_observed":by_week,
      "economic_outcomes":1,
      "classification":"NO_PROMOTION_CENSORED" if censored else
      "NET_FAIL_FUNDED_SCENARIO" if sensitivities["0.04"]["net_eur"]<=0
      else "DEVELOPMENT_POSITIVE_UNCERTIFIED"})
   else:
    report.update({"economic_outcomes":0,"classification":"STOP_NO_OBSERVABLE_TRADES"})
  else:report.update({"economic_outcomes":0,
                        "classification":"STOP_PRICE_BLIND_SOURCE_LIMITED"})
  # Guarantee public coarse receipt survives even if later owner private
  # encryption fails; account result will never be silently lost again.
  (OUT/"receipt.json").write_bytes(encoded(report))
  print("MXM_JPY_RESIDUAL_CSHARP_ORIGINAL_AGGREGATE "+json.dumps(report,sort_keys=True),flush=True)
  original_plain=encoded(private_out)
  original.encrypt_private_output(original_plain,tmp,OUT/"private.mxmenc")
  report["private_sha256"]=hashlib.sha256(original_plain).hexdigest()
  report["private_cipher_sha256"]=hashlib.sha256((OUT/"private.mxmenc").read_bytes()).hexdigest()
  (OUT/"receipt.json").write_bytes(encoded(report))
  print("MXM_JPY_RESIDUAL_CSHARP_ORIGINAL_CUSTODY "+json.dumps({
    "run_id":report["run_id"],"classification":report["classification"],
    "private_cipher_sha256":report["private_cipher_sha256"]}),flush=True)

def cold():
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack
 from research_core_v4.successor_c_20261018.readback import FP
 r=json.loads((OUT/"receipt.json").read_bytes())
 raw=(OUT/"private.mxmenc").read_bytes()
 flag(hashlib.sha256(raw).hexdigest()==r["private_cipher_sha256"],"COLD_CIPHER")
 with tempfile.TemporaryDirectory() as directory:
  tmp=pathlib.Path(directory);key,fp=_private_key_from_secret(tmp)
  flag(fp==FP,"COLD_RECIPIENT")
  plain=owner.bounded_decrypt(raw,key,tmp)
  flag(plain.startswith(b'{') and plain.endswith(b'}'),"COLD_NATIVE_JSON_NOT_GZIP")
 flag(hashlib.sha256(plain).hexdigest()==r["private_sha256"],"COLD_SHA")
 d=json.loads(plain)
 if r.get("economic_outcomes"):
  for scenario in ("0.02","0.04","0.08"):
   flag(shared.reconcile(d["native_csharp_"+scenario])==
        r["scenario_results"][scenario],"COLD_EUR200_NATIVE_LEDGER")
 proof={"schema":"mxm.be.jpy-fourhour.original-native-csharp-cold-readback.v1",
  "original_run_id":r["run_id"],"original_head":r["head"],
  "private_cipher_sha256":r["private_cipher_sha256"],
  "original_ledger_scenarios_verified":sorted(r.get("scenario_results",{})),
  "original_full_ledger_recomputed_without_economic_policy":True,
  "model_rerun":False,"source_market_opened":False,"orders":0,"cloud":False,
  "original_classification":r["classification"]}
 (OUT/"cold.json").write_bytes(encoded(proof))
 print("MXM_JPY_RESIDUAL_ANNUAL_COLD_NATIVE_FUNDED_PASS",r["run_id"],
       json.dumps(proof,sort_keys=True),flush=True)

if __name__=="__main__":
 import sys
 flag(len(sys.argv)==2 and sys.argv[1] in ("selftest","admit","run","cold"),
      "CLI")
 {"selftest":selftest,"admit":check_admit,"run":results,"cold":cold}[sys.argv[1]]()
