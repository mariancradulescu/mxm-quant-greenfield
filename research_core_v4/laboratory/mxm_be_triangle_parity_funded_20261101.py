"""Precommitted source-availability and capital-filtered triangular no-arbitrage
parity-development trial on the ALREADY SHA-authenticated annual Pepperstone tape.
FX triangle: AUDJPY ~= EURJPY / EURAUD. Exact 3 original H1 closed
prices only; original future M5 open prices used AFTER complete causal signal
freeze. This is NOT an arbitrage execution, synchronized BIDASK, or broker PNL.
ONE existing CSharp funded EUR200 account; no closed policy rerun. Existing
portfolio forensics applies independently to the *closed old* native ledger.
"""
from __future__ import annotations
import base64,collections,datetime as dt,hashlib,json,os,pathlib,subprocess,tempfile
from decimal import Decimal as D
from research_core_v4.laboratory.common import need,digest,encoded
from research_core_v4.laboratory.budgets import TrialBook,historical_accounting
from research_core_v4.laboratory.programs import Laboratory
from research_core_v4.laboratory.funded_account import execute as native_account
from research_core_v4.laboratory import native_h1_csharp_annual_receipt as original
from research_core_v4.laboratory import mxm_be_jpy_consensus_annual_funded_20261101 as adapter
from research_core_v4.laboratory import portfolio_programme as contract
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.successor_c_20261018.readback import FP

ROOT=pathlib.Path(__file__).resolve().parents[2]
SPEC=ROOT/"research_core_v4/laboratory/MXM_BE_TRIANGLE_PARITY_FUNDED_20261101.json"
OUT=ROOT/"verification/mxm-be-triangle-parity-funded-20261101"
OLD=ROOT/"verification/mxm-be-original-pr316-recon-20261101"
IDENT="V4-TRIANGLE-EURAUD-EURJPY-AUDJPY-PARITY-20261101"
PROGRAM="MXM_BE_TRIANGLE_PARITY_FUNDED_20261101"
FIRST=adapter.FIRST;LAST=adapter.LAST;H=adapter.H
SYMBOLS=("AUDJPY","EURJPY","EURAUD")
BASIS_MIN=D("0.0005")  # fixed 5bps relative cross parity, NOT cost retuned
COST_MULT=D("1.25")
BASE=D("0.04")
ORIGINAL_LEDGER_CIPHER="39aead51b11fa8e80e457d82a519c9e11d4aaec8c80d06439bdcd2b6d2f1b8a6"
ORIGINAL_LEDGER_RUN=41347641856
ORIGINAL_LEDGER_HEAD="f5f09a4d06994859fe3214a9ac5d1ab1f06704e5"

def flag(x,key):need(x,"MXM_BE_TRIANGLE_"+key)
def qtime(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat().replace("+00:00","Z")
def stamp(t):return int(dt.datetime.fromisoformat(t.replace("Z","+00:00")).timestamp())
def week(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime("%G-W%V")
def spec():
 p=json.loads(SPEC.read_bytes())
 flag(p["id"]==IDENT and p["programme"]==PROGRAM and p["risk"]["initial_eur"]==200,"PIN")
 flag(not p["cloud"] and p["orders"]==0 and p["max_authentic_attempts"]==1,"NO_ORDERS")
 flag(p["source"]["original_plain_sha256"]==original.EXPECTED_PLAINTEXT_SHA,"SOURCE")
 flag(p["source"]["triangular_peer_symbols"]==list(SYMBOLS),"SYMBOLS")
 flag(p["cost_scenario"]["spreads_jpy"]==["0.02","0.04","0.08"],"COSTS")
 for path,sha in p["implementation_sha256"].items():
  actual=subprocess.check_output(["git","hash-object",path],text=True,cwd=ROOT).strip()
  flag(actual==sha,"IMMUTABLE_SHARED")
 return p

def selftest():
 p=json.loads(SPEC.read_bytes())
 flag(p["id"]==IDENT and p["risk"]["initial_eur"]==200,"SELF_FREEZE")
 flag(BASIS_MIN==D(".0005") and COST_MULT==D("1.25"),"SELF_THRESHOLD")
 m={s:{} for s in SYMBOLS}
 for t in (FIRST-2*H,FIRST-H):
  m["EURJPY"][t]=D("150");m["EURAUD"][t]=D("1.5");m["AUDJPY"][t]=D("99.90")
 # implied 100; AUDJPY discounted; fixed minimum price/fees hurdle.
 flag(signal(FIRST,m)==1,"SELF_LONG")
 m["AUDJPY"][FIRST-H]=D("100.20")
 flag(signal(FIRST,m)==-1,"SELF_SHORT")
 m["AUDJPY"][FIRST-H]=D("100")
 flag(signal(FIRST,m) is None,"SELF_PARITY_NULL")
 m["AUDJPY"][FIRST-H]=D("99.90")
 for item in m.values():item[FIRST+H]=D("999999")
 flag(signal(FIRST,m)==1,"SELF_FUTURE_BLIND")
 parts=sorted(original.CIPHER_DIR.glob("chunk-*.b64"))
 flag(len(parts)==7,"SELF_SEVEN_PARTS")
 cipher=b"".join(base64.b64decode(x.read_text()) for x in parts)
 flag(hashlib.sha256(cipher).hexdigest()==original.EXPECTED_CIPHER_SHA,"SELF_CIPHER")
 # Exact non-rounding Decimal-to-JSON custody.
 flag(json.loads(encoded({"n":str(D("1.123400"))}))["n"]=="1.123400","JSON_CUSTODY")
 from research_core_v4.laboratory import mxm_be_jpy_residual_cold_only_20261101 as prior_cold
 flag(ORIGINAL_LEDGER_CIPHER==prior_cold.ORIGINAL_PRIVATE_SHA and
      len(ORIGINAL_LEDGER_CIPHER)==64,"SELF_PREVIOUS_SHA_CERTIFIED")
 print("MXM_TRIANGLE_FAMILY_FROZEN_SOURCE_BLIND_PASS")

def decode(tape):
 flag(set(tape["symbols"])==set(original.IDS) and
      len(tape["bars"])>=30000 and tape["source_original_verified"],"ORIGINAL_IDENTITY")
 m={s:{} for s in SYMBOLS}
 for r in tape["bars"]:
  s=r["symbol"]
  if s not in m:continue
  t=stamp(r["end"]);available=stamp(r["available"])
  flag(available>=t+300 and available<t+H and t%H==0,"SOURCE_CLOCK")
  v=D(str(r["close"]))
  flag(v>0 and v.is_finite() and t not in m[s],"SOURCE_CLOSE")
  m[s][t]=v
 flag(all(len(m[s])>3000 for s in SYMBOLS),"SOURCE_LONG")
 return m

def time_admit(m):
 weekly=collections.Counter();total=0
 for t in range(FIRST,LAST,H):
  d=dt.datetime.fromtimestamp(t,dt.timezone.utc)
  if d.weekday()>4 or not 7<=d.hour<=15:continue
  if all(t-H in m[s] and t-2*H in m[s] for s in SYMBOLS):
   total+=1;weekly[week(t)]+=1
 return {"source_only":True,"weeks":len(weekly),"causal_cells":total,
  "min_cells_per_week":min(weekly.values()) if weekly else 0,
  "admitted":len(weekly)>=22 and total>=600 and min(weekly.values())>=12,
  "not_used": "FUTURE_RETURNS_PNL_OR_COST_BROKER"}

def signal(t,m):
 # Clock completed: all three FX products already closed at t-H and t-2H.
 if not all(t-H in m[s] and t-2*H in m[s] for s in SYMBOLS):return None
 aud=m["AUDJPY"][t-H];eurj=m["EURJPY"][t-H];eura=m["EURAUD"][t-H]
 theoretical=eurj/eura
 basis=(theoretical/aud)-1
 if abs(basis)<BASIS_MIN:return None
 # Pre-decision gross price displacement proxy cannot be projected as profit.
 # The fee/slippage scenario is a screening COST hurdle, not an edge estimate.
 gross_proxy=abs(theoretical-aud)*adapter.UNITS/eurj
 full_friction=(BASE+2*adapter.SLIP)*adapter.UNITS/eurj+2*adapter.FEE
 if gross_proxy<COST_MULT*full_friction:return None
 return 1 if basis>0 else -1

def decisions(m):
 complete=[];count=collections.Counter()
 for t in range(FIRST,LAST,H):
  d=dt.datetime.fromtimestamp(t,dt.timezone.utc)
  if d.weekday()>4 or not 7<=d.hour<=15:continue
  side=signal(t,m)
  if side is None:count["FLAT"]+=1
  else:count["COST_FEASIBLE_PROPOSAL"]+=1;complete.append((t,side))
 return complete,dict(count)

def public_loss_attribution():
 """Forensics only: read SAVED old CSharp ledger, not market sources or models."""
 o=json.loads((OLD/"receipt.json").read_bytes())
 flag(o["run_id"]==ORIGINAL_LEDGER_RUN and o["head"]==ORIGINAL_LEDGER_HEAD and
      o["identity"]=="V4-JPY-FOURHOUR-FACTOR-RESIDUAL-20261101" and
      o["classification"]=="NET_FAIL_FUNDED_SCENARIO","CLOSED_ID")
 blob=(OLD/"private.mxmenc").read_bytes()
 flag(hashlib.sha256(blob).hexdigest()==ORIGINAL_LEDGER_CIPHER and
      o["private_cipher_sha256"]==ORIGINAL_LEDGER_CIPHER,"CLOSED_ORIGINAL_SHA")
 with tempfile.TemporaryDirectory() as tmpdir:
  tmp=pathlib.Path(tmpdir);key,fp=_private_key_from_secret(tmp)
  flag(fp==FP,"OLD_RECIPIENT")
  plain=owner.bounded_decrypt(blob,key,tmp)
 flag(hashlib.sha256(plain).hexdigest()==o["private_sha256"],"OLD_PLAIN_SHA")
 d=json.loads(plain)
 from research_core_v4.laboratory import mxm_be_jpy_residual_annual_funded_20261101 as previous
 r=previous.shared.reconcile(d["native_csharp_0.04"])
 flag(r==o["scenario_results"]["0.04"],"OLD_NATIVE_PARITY")
 acc=d["native_csharp_0.04"]["account"]
 reasons=collections.Counter(acc["Rejections"])
 exits=collections.Counter(z.get("Reason") or "UNSPECIFIED" for z in acc["Ledger"] if z["Kind"]=="EXIT")
 entries_by_week=acc["EntriesByIsoWeek"]
 first_no_more=next((w for w in sorted(o["baseline_weekly_equity_observed"])
   if w>max(entries_by_week)),None)
 # "GrossEur" includes spread/slip via filled ledger Price. Do not mislabel
 # it as source midpoint raw return or present fixed costs as broker charges.
 fee=sum(D(str(z["CommissionEur"])) for z in acc["Ledger"])
 gross=sum(D(str(z["GrossEur"])) for z in acc["Ledger"])
 net=D(str(r["net_eur"]))
 flag(abs(gross-fee-net)<D(".000001"),"GROSS_MINUS_FEE_EQUALS_NET")
 outcome={"schema":"mxm.be.original-closed-account-loss-attribution.v1",
  "original_head":ORIGINAL_LEDGER_HEAD,"original_run_id":ORIGINAL_LEDGER_RUN,
  "model_rerun":False,"new_source_opened":False,
  "first_week_after_last_entry":first_no_more,
  "entered_weeks":len(entries_by_week),"total_proposals":o["proposals"],
  "accepted_entries":r["entries"],"rejected_entries":r["rejections"],
  "gross_native_filled_quote_pnl_eur":float(gross),
  "commission_scenario_eur":float(fee),"net_scenario_eur":float(net),
  "drawdown_eur":r["max_drawdown_eur"],
  "native_rejection_reasons":dict(sorted(reasons.items())),
  "native_exit_reasons":dict(sorted(exits.items())),
  "spread_slippage_inside_gross":True,
  "unadjusted_raw_midprice_profit_proven":False,
  "no_lookahead_broker_or_cloud_claim":True}
 flag(outcome["accepted_entries"]==149 and
      abs(net-D("-49.092221988142526"))<D(".000001"),"OLD_PUBLIC_ECONOMIC")
 # Read ONLY preserved source prices from the *closed* old private account.
 # This is ex-post analytical attribution; no native model/account rerun.
 existing={}
 for t,side,values in d["settled"]:
  flag(len(values)==4 and int(side) in (-1,1),"OLD_ORIGINAL_SHAPE")
  key=(qtime(int(t)+300),qtime(int(t)+H))
  flag(key not in existing,"OLD_SOURCE_UNIQUE")
  existing[key]=(int(side),[D(str(v)) for v in values])
 open_entry=None
 original_mid=D(0);spread_component=D(0);slip_component=D(0);matched=0
 def conversion(amount,eurj_exit):
  fx=(D(1)/eurj_exit) if amount>=0 else (D(1)/(eurj_exit-D(".0002")))
  return amount*fx
 for line in acc["Ledger"]:
  if line["Kind"]=="ENTRY":
   flag(open_entry is None,"OLD_INDEPENDENT_ENTRY_PAIR")
   open_entry=line
   continue
  flag(line["Kind"]=="EXIT" and open_entry is not None,"OLD_INDEPENDENT_EXIT_PAIR")
  entry=open_entry;open_entry=None
  when=(entry["Utc"],line["Utc"])
  flag(when in existing,"OLD_CSHARP_EPISODE_FROM_ORIGINAL_TAPE")
  side,prices=existing[when]
  a,b,fx_entry,fx_exit=prices
  flag(entry["Symbol"]=="AUDJPY" and line["Symbol"]=="AUDJPY" and
       int(entry["Direction"])==side and int(line["Direction"])==side,
       "OLD_CSHARP_SIGN")
  units=D(str(entry["Units"]))
  spot_mid=(b-a)*D(side)*units
  mid_gross=conversion(spot_mid,fx_exit)
  after_spread=conversion(spot_mid-D(".04")*units,fx_exit)
  after_slip=conversion(spot_mid-(D(".04")+2*D(".005"))*units,fx_exit)
  actual=D(str(line["GrossEur"]))
  flag(abs(after_slip-actual)<D(".001"),"OLD_CSHARP_EXACT_PRICE_COST_PARITY")
  original_mid+=mid_gross
  spread_component+=mid_gross-after_spread
  slip_component+=after_spread-actual
  matched+=1
 flag(open_entry is None and matched==r["entries"],"OLD_EXACT_CSHARP_MATCHED_ALL_ENTRIES")
 flag(abs(original_mid-spread_component-slip_component-gross)<D(".000001"),
       "OLD_MARK_PRICE_COST_ACCOUNTING_IDENTITY")
 outcome["price_and_cost_attribution"]={
   "basis":"COUNTERFACTUAL_ORIGINAL_M5_OPEN_TO_OPEN_MID_PRICE_AND_EXIT_FX; NOT_EXECUTED_BIDASK",
   "matched_existing_native_CSharp_entries":matched,
   "original_m5_mid_price_gross_eur":float(original_mid),
   "modeled_spread_component_eur":float(spread_component),
   "modeled_slippage_component_eur":float(slip_component),
   "native_filled_quote_gross_eur":float(gross),
   "modeled_commissions_eur":float(fee),
   "native_funded_net_eur":float(net),
   "algebra":"original_mid - modeled_spread - modeled_slippage - modeled_commissions = native_net",
   "not_historical_cost_proof":True,"no_model_rerun":True
 }
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"closed_pr316_attribution.json").write_bytes(encoded(outcome))
 print("MXM_CLOSED_PR316_NATIVE_FORENSICS_NO_RERUN "+json.dumps(outcome,sort_keys=True),flush=True)


def isolated_read_only_forensics():
 """The *old* forensic has its own strict SHA, paired-trade and CSharp guards.
 Do not let an ancillary old-ledger failure veto the NEW untouched source
 and native EUR200 account trial. A failure is plainly and durably recorded.
 """
 try:
  public_loss_attribution()
 except Exception as err:
  OUT.mkdir(parents=True,exist_ok=True)
  note={"schema":"mxm.be.pr316-read-only-forensics-unavailable.v1",
        "status":"FORENSICS_NOT_COMPLETED","original_run_id":ORIGINAL_LEDGER_RUN,
        "reason_type":type(err).__name__,"reason":str(err)[:240],
        "original_digests_relaxed":False,"new_market_source_opened":False,
        "new_strategy_executed":False,"old_model_rerun":False,
        "new_strategy_not_dependent_on_old_forensics":True}
  (OUT/"closed_pr316_attribution_error.json").write_bytes(encoded(note))
  print("MXM_CLOSED_PR316_FORENSICS_UNAVAILABLE_NOT_ECONOMIC_GATE "+
        json.dumps(note,sort_keys=True),flush=True)

def first_only():
 flag(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield"
      and os.environ.get("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1"
      and os.environ.get("GITHUB_EVENT_NAME")=="push" and
      os.environ.get("GITHUB_RUN_ATTEMPT")=="1","FIRST_ONLY")
 def get(path):
  return json.loads(subprocess.check_output(["gh","api",
    "repos/mariancradulescu/mxm-quant-greenfield/"+path],text=True))
 head=os.environ["GITHUB_SHA"]
 flag(get("git/ref/heads/mxm-remediation-p0-p4-20261015-v1")["object"]["sha"]==head,
      "OFFICIAL_CAS")
 parents=get("commits/"+head)["parents"]
 flag(len(parents)==2 and parents[0]["sha"]==
      "0705e56e659bf0b2ef31bec86e9416d407592945","NO_MISSING_MERGE")
 runs=get("actions/workflows/mxm-be-triangle-parity-funded-20261101.yml/runs?per_page=100")
 pushes=[z for z in runs["workflow_runs"]
  if z["event"]=="push" and z["head_branch"]=="mxm-remediation-p0-p4-20261015-v1"]
 flag(runs["total_count"]<=100 and len(pushes)==1 and
      pushes[0]["id"]==int(os.environ["GITHUB_RUN_ID"]),"NO_RERUN")
 allruns=get("actions/runs?event=pull_request&per_page=100")["workflow_runs"]
 passnames={z["name"] for z in allruns if z["head_sha"]==parents[1]["sha"] and
            z["conclusion"]=="success"}
 flag({"MXM R3 protected technical installation CI",
       "MXM CSharp Pepperstone protected gateway CI"}<=passnames,"PROTECTED_NATIVE_CI")
 orig=get("actions/runs/41347641856/artifacts")
 flag(orig["total_count"]==1 and orig["artifacts"][0]["id"]==13099648067,
      "EXACT_SAVED_ORIGINAL")
 flag(not OUT.exists(),"NO_PRIOR_ECONOMIC_OUTPUT")
 selftest();spec()
 print("MXM_TRIANGLE_ORIGINAL_ONE_NATIVE_ECONOMIC_TRIAL_ADMITTED")


def recover_admit():
 # NEW first-only reviewed recovery only for original #41350541329
 # where immutable archival hash was truncated BEFORE the prior-ledger
 # cold read, new source, registration, signals or CSharp evaluation.
 flag(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield"
      and os.environ.get("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1"
      and os.environ.get("GITHUB_EVENT_NAME")=="push"
      and os.environ.get("GITHUB_RUN_ATTEMPT")=="1","RECOVERY_ONE_OFFICIAL")
 def api(path):
  return json.loads(subprocess.check_output(["gh","api",
       "repos/mariancradulescu/mxm-quant-greenfield/"+path],text=True))
 original_run=api("actions/runs/41350541329")
 flag(original_run["conclusion"]=="failure" and
      original_run["head_sha"]=="079ad99a9e28b1eda0b3cacbc619d9eb26ea6e8d"
      and original_run["run_attempt"]==1,"RECOVERY_OLD_FAILURE_IDENTITY")
 oldart=api("actions/runs/41350541329/artifacts")
 flag(oldart["total_count"]==0,"RECOVERY_OLD_ECONOMIC_ARTIFACT_EXISTS")
 jobs=api("actions/runs/41350541329/jobs?per_page=100")
 j=[x for x in jobs["jobs"] if x["name"]=="actual-first-source-only"]
 flag(len(j)==1 and j[0]["conclusion"]=="failure","RECOVERY_OLD_JOB")
 stages={x["name"]:x["conclusion"] for x in j[0]["steps"]}
 flag(stages["Read ONLY saved closed PR316 EUR200 original ledger for cost and risk loss attribution"]=="failure"
       and stages["Execute ONE independently frozen FX parity family on the actual source and native CSharp EUR200 account"]=="skipped",
       "RECOVERY_NO_PRIOR_TRIANGLE_ECONOMIC")
 head=os.environ["GITHUB_SHA"]
 flag(api("git/ref/heads/mxm-remediation-p0-p4-20261015-v1")["object"]["sha"]==head,
      "RECOVERY_HEAD")
 parents=api("commits/"+head)["parents"]
 flag(len(parents)==2 and parents[0]["sha"]==
      "079ad99a9e28b1eda0b3cacbc619d9eb26ea6e8d","RECOVERY_OFFICIAL_MERGE")
 runs=api("actions/workflows/mxm-be-triangle-parity-one-recovery-20261101.yml/runs?per_page=100")
 pushes=[r for r in runs["workflow_runs"] if r["event"]=="push" and
         r["head_branch"]=="mxm-remediation-p0-p4-20261015-v1"]
 flag(runs["total_count"]<=100 and len(pushes)==1 and
       pushes[0]["id"]==int(os.environ["GITHUB_RUN_ID"]),"RECOVERY_NO_RELAUNCH")
 ci=api("actions/runs?event=pull_request&per_page=100")["workflow_runs"]
 passed={r["name"] for r in ci if r["head_sha"]==parents[1]["sha"] and
         r["conclusion"]=="success"}
 flag({"MXM R3 protected technical installation CI",
       "MXM CSharp Pepperstone protected gateway CI"}<=passed,
       "RECOVERY_PROTECTED_CI")
 flag(not OUT.exists(),"RECOVERY_NO_OUTCOME")
 selftest();spec()
 print("MXM_TRIANGLE_IDENTICAL_STUDY_FIRST_SOURCE_RECOVERY_AUTHORIZED",flush=True)

def run():
 p=spec()
 history=historical_accounting(ROOT)
 flag(history["reconciled"] and history["V2"]["used"]==21,"BUDGET")
 priv=os.environ.get("MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM")
 flag(priv and "BEGIN" in priv,"OWNER_PRIVATE_CUSTODY")
 # The prior forensic may be independently executed first by the same
 # protected job; never run old policy in this source process.
 with tempfile.TemporaryDirectory() as td:
  tmp=pathlib.Path(td)
  pts=sorted(original.CIPHER_DIR.glob("chunk-*.b64"))
  flag(len(pts)==7,"ORIGINAL_CIPHER_PARTS")
  blob=b"".join(base64.b64decode(q.read_text()) for q in pts)
  tape=json.loads(original.decrypt(blob,priv.encode(),tmp))
  m=decode(tape);support=time_admit(m)
  receipt={"schema":"mxm.be.triangle-parity-first-real-native-funded.v1",
   "run_id":int(os.environ["GITHUB_RUN_ID"]),"head":os.environ["GITHUB_SHA"],
   "id":IDENT,"source_sha256":original.EXPECTED_PLAINTEXT_SHA,
   "source_clock_admission":support,"orders":0,"cloud":False,
   "broker_requests":0,"start_eur":200,"resets":0,
   "source_tape_previously_development_exposed":True,
   "historical_BIDASK_or_actual_fills_proven":False,
   "independent_holdout":False,"HARD21_broker_proven":False,
   "native_bot_qualified":False}
  OUT.mkdir(parents=True,exist_ok=True)
  private_result={"spec":p,"support":support,"original_sha":original.EXPECTED_PLAINTEXT_SHA}
  if support["admitted"]:
   lab=Laboratory(contract.programme(p),history,TrialBook(
      {"V4":1,"V2":history["V2"]["limit"]},
      {"V4":0,"V2":history["V2"]["used"]}))
   lab.execute("register");candidate=lab.state["results"]["register"]["value"]
   fixed,counts=decisions(m)
   source_bound_decision_sha=hashlib.sha256(encoded(fixed)).hexdigest()
   settled,censored=adapter.after_observation(tape,fixed)
   private_result.update({"fixed_decisions":fixed,
    "original_outcomes":[[t,d,[str(v) for v in prices]] for t,d,prices in settled],
    "censored":censored,"source_bound_decision_sha":source_bound_decision_sha})
   receipt.update({"candidate_count":len(fixed),"observable_count":len(settled),
    "censored_count":len(censored),"counts":counts,
    "causal_decisions_sha256":source_bound_decision_sha})
   if settled:
    comparisons={}
    for spread in adapter.SPREADS:
     f=adapter.feed(settled,candidate,spread)
     if spread==BASE:
      lab.authenticated_csharp_feed=f
      lab.execute("account");lab.execute("report")
      native=lab.state["results"]["account"]["value"]
     else:native=native_account(candidate,f,False)
     comparisons[str(spread)]=adapter.reconcile(native)
     private_result["native_original_"+str(spread)]=native
     if spread==BASE:
      receipt["observed_iso_week_equity"]={
       w:{"first":rec["first"]["MarkedEquityEur"],
          "last_observed":rec["last"]["MarkedEquityEur"],
          "is_exact_week_close":False} for w,rec in native["periods"]["iso_weeks"].items()}
      receipt["observed_utc_month_equity"]={
       w:{"first":rec["first"]["MarkedEquityEur"],
          "last_observed":rec["last"]["MarkedEquityEur"],
          "is_exact_month_close":False} for w,rec in native["periods"]["utc_months"].items()}
    receipt.update({"economic_outcomes":1,"net_scenario":comparisons,
      "classification":"OBSERVATION_CENSORED_NO_PROMOTION" if censored else (
       "NET_FAIL_NATIVE_FUNDED" if comparisons["0.04"]["net_eur"]<=0 else
       "DEVELOPMENT_POSITIVE_UNQUALIFIED")})
   else:receipt.update({"economic_outcomes":0,
                        "classification":"SOURCE_CAUSAL_NO_COST_FEASIBLE_TRIANGLE_SIGNALS"})
  else:receipt.update({"economic_outcomes":0,"classification":"NO_LONG_SOURCE_SUPPORT"})
  # Publish aggregate FIRST so source observations are not lost if owner
  # encrypted private custody fails. This creates NO trading intent.
  (OUT/"receipt.json").write_bytes(encoded(receipt))
  print("MXM_TRIANGLE_NATIVE_200EUR_ORIGINAL_AGGREGATE "+
        json.dumps(receipt,sort_keys=True),flush=True)
  plaintext=encoded(private_result)
  original.encrypt_private_output(plaintext,tmp,OUT/"private.mxmenc")
  receipt["private_plain_sha256"]=hashlib.sha256(plaintext).hexdigest()
  receipt["private_cipher_sha256"]=hashlib.sha256((OUT/"private.mxmenc").read_bytes()).hexdigest()
  (OUT/"receipt.json").write_bytes(encoded(receipt))
  print("MXM_TRIANGLE_ORIGINAL_CUSTODY "+
     json.dumps({"run_id":receipt["run_id"],
                 "classification":receipt["classification"]},sort_keys=True),flush=True)

def cold():
 from research_core_v4.laboratory import mxm_be_jpy_residual_annual_funded_20261101 as old_helper
 r=json.loads((OUT/"receipt.json").read_bytes())
 raw=(OUT/"private.mxmenc").read_bytes()
 flag(hashlib.sha256(raw).hexdigest()==r["private_cipher_sha256"],"COLD_CIPHER")
 with tempfile.TemporaryDirectory() as td:
  tmp=pathlib.Path(td);key,fp=_private_key_from_secret(tmp)
  flag(fp==FP,"RECIPIENT")
  rawplain=owner.bounded_decrypt(raw,key,tmp)
 flag(hashlib.sha256(rawplain).hexdigest()==r["private_plain_sha256"],"COLD_PLAIN")
 d=json.loads(rawplain)
 for spread in ("0.02","0.04","0.08"):
  if r.get("economic_outcomes"):
   flag(adapter.reconcile(d["native_original_"+spread])==
        r["net_scenario"][spread],"COLD_CSHARP_"+spread)
 proof={"schema":"mxm.be.triangle-original-csharp-cold-proven.v1",
  "source_run_id":r["run_id"],"source_head":r["head"],
  "closed_original_reruns":0,"three_native_ledgers_reconciled":r.get("economic_outcomes",0)==1,
  "capital_eur":200,"orders":0,"cloud":False}
 (OUT/"cold.json").write_bytes(encoded(proof))
 print("MXM_TRIANGLE_ORIGINAL_CSHARP_COLD_SUCCESS "+json.dumps(proof,sort_keys=True),flush=True)

if __name__=="__main__":
 import sys
 flag(len(sys.argv)==2 and sys.argv[1] in ("selftest","admit","recover-admit","forensics","run","cold"),
     "ENTRY_USAGE")
 {"selftest":selftest,"admit":first_only,
  "recover-admit":recover_admit,"forensics":isolated_read_only_forensics,"run":run,"cold":cold}[sys.argv[1]]()
