"""ONE 26-week genuinely out-of-source-account JPY factor disagreement study.
Pepperstone 2025-2026 original M5-derived, SHA-pinned annual H1 tape, encrypted
in the EXISTING repository. Pure calendar H1 is a source property, not OWNER
timeframe preference. No LIVE/DEMO orders, Cloud, retuning or new laboratory.
Entry/exit ORIGINAL future M5 opens are observed, spreads/slippage/fees are
DECLARED scenarios. Missing intrabar stop path/true BIDASK prohibits promotion.
"""
from __future__ import annotations
import base64,collections,datetime as dt,hashlib,json,os,pathlib,subprocess,tempfile
from decimal import Decimal as D
from research_core_v4.laboratory.common import need,digest,encoded
from research_core_v4.laboratory.budgets import TrialBook,historical_accounting
from research_core_v4.laboratory.programs import Laboratory
from research_core_v4.laboratory.funded_account import execute as funded_execute
from research_core_v4.laboratory import portfolio_programme as joint
from research_core_v4.laboratory import native_h1_csharp_annual_receipt as tape_source

ROOT=pathlib.Path(__file__).resolve().parents[2]
P=ROOT/"research_core_v4/laboratory/MXM_BE_JPY_CONSENSUS_ANNUAL_FUNDED_20261101.json"
OUT=ROOT/"verification/mxm-be-jpy-consensus-annual-20261101"
IDENT="V4-JPY-FACTORED-DISCORDANCE-20261101"
PROGRAM="MXM_BE_JPY_FACTORED_DISCORDANCE_ANNUAL_20261101"
H=3600
FIRST=int(dt.datetime(2025,12,1,tzinfo=dt.timezone.utc).timestamp())
LAST=int(dt.datetime(2026,6,1,tzinfo=dt.timezone.utc).timestamp())
TARGET="AUDJPY"
FACTOR=("EURJPY","GBPJPY","CHFJPY")
SCOPE=set((TARGET,*FACTOR))
# Broker's ORIGINAL 2026-09-22 account snapshot: exact minimum 1000 AUDJPY,
# 31.02 EUR BUY/SELL required margin; not historical 2025-2026 margin.
UNITS=D("1000")
MARGIN=D("31.02")
SPREADS=(D(".02"),D(".04"),D(".08"))
SLIP=D(".005")
FEE=D(".04")
STOP=D(".20")
HURDLE=D("2")
CONSENSUS_MIN=D(".0006")
COUNTERMOVE_MIN=D(".0001")

def flag(value,tag):
 need(value,"MXM_BE_JPY_"+tag)
def now(t):
 return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat().replace("+00:00","Z")
def stamp(v):
 return int(dt.datetime.fromisoformat(v.replace("Z","+00:00")).timestamp())
def week(t):
 return dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime("%G-W%V")

def read_spec():
 p=json.loads(P.read_bytes())
 flag(p["schema"]=="mxm.registered-portfolio-policy.v1" and p["id"]==IDENT and
      p["programme"]==PROGRAM and p["risk"]["initial_eur"]==200,"FREEZE")
 flag(p["orders"]==0 and p["cloud"] is False and
      p["max_authentic_attempts"]==1 and p["source"]["original_plain_sha256"]==
      tape_source.EXPECTED_PLAINTEXT_SHA,"CUSTODY")
 flag(p["cost_scenario"]["spreads_jpy"]==[str(x) for x in SPREADS] and
      p["cost_scenario"]["commission_per_side_eur"]==str(FEE),"SCENARIOS")
 for path,sha in p["implementation_sha256"].items():
  actual=subprocess.check_output(["git","hash-object",path],cwd=ROOT,text=True).strip()
  flag(actual==sha,"PINNED_EXISTING_IMPLEMENTATION")
 return p

def selftest():
 p=json.loads(P.read_bytes())
 flag(p["id"]==IDENT and p["risk"]["initial_eur"]==200,"SELF_SPEC")
 flag(len(set(FACTOR))==3 and TARGET not in FACTOR,"SELF_UNIVERSE")
 flag(FIRST<LAST and (LAST-FIRST)//(7*24*3600)==26,"SELF_WEEK_COUNT")
 flag(UNITS==1000 and MARGIN==D("31.02") and SPREADS[1]==D(".04"),"SELF_COST")
 # Degenerate exactly flat artificial source MUST never generate a trade.
 m={x:{t:D("100") for t in range(FIRST-8*H,FIRST,H)} for x in SCOPE}
 flag(signal(FIRST,m) is None,"SELF_FLAT_CAUSAL")
 # A future-only mutation never enters the closed-input calculation.
 for v in m.values():v[FIRST+2*H]=D("100000")
 flag(signal(FIRST,m) is None,"SELF_FUTURE_LEAK")
 parts=sorted(tape_source.CIPHER_DIR.glob("chunk-*.b64"))
 flag(len(parts)==7,"SELFTEST_ORIGINAL_SOURCE_PARTS")
 # Reuse the already certified original reader's whitespace-tolerant Base64
 # semantics. Authenticate the exact ENCRYPTED envelope without any secret.
 cipher=b"".join(base64.b64decode(q.read_text(),validate=False) for q in parts)
 flag(hashlib.sha256(cipher).hexdigest()==tape_source.EXPECTED_CIPHER_SHA,
      "SELFTEST_SOURCE_ENVELOPE_SHA256")
 print("MXM_JPY_FACTOR_ANNUAL_FROZEN_SOURCE_BLIND_SELFTEST_SUCCESS")

def decode(tape):
 flag(set(tape["symbols"])==set(tape_source.IDS) and
      len(tape["bars"])>=30000 and tape["source_original_verified"],"ANNUAL_IDENTITY")
 m={s:{} for s in SCOPE};stamps={s:set() for s in SCOPE}
 for r in tape["bars"]:
  symbol=r["symbol"]
  if symbol not in SCOPE:continue
  t=stamp(r["end"]);avail=stamp(r["available"])
  flag(avail>=t+300 and avail<t+H and t%H==0,"SOURCE_AVAILABLE_CLOCK")
  v=D(str(r["close"]))
  flag(v.is_finite() and v>0 and t not in m[symbol],"SOURCE_VALID_CLOSE")
  m[symbol][t]=v;stamps[symbol].add(t)
 flag(all(len(m[s])>=3500 for s in SCOPE),"LONG_SOURCE_POPULATION")
 return m

def source_admit(m):
 # Price blind. Calendar/week coverage, not later price or selected profits.
 full=0;future=0;weekly=collections.Counter()
 for t in range(FIRST,LAST,H):
  d=dt.datetime.fromtimestamp(t,dt.timezone.utc)
  if d.weekday()>=5 or d.hour<7 or d.hour>15:continue
  if not all(all(t-k*H in m[s] for k in range(1,9)) for s in SCOPE):continue
  full+=1;weekly[week(t)]+=1
  # Future-source admission uses only the timestamp identity at a *global*
  # price-blind level, not as a hindsight-selected candidate filter.
  future+=int(all(t+H in m[s] for s in SCOPE))
 passed=(full>=600 and len(weekly)>=22 and min(weekly.values())>=12)
 return {"admitted":passed,"causal_joint_hours":full,"clock_forward_h1_present":future,
   "weeks":len(weekly),"min_supported_hours_per_week":min(weekly.values()) if weekly else 0,
   "source_only":True,"outcome_values_accessed":False}

def signal(t,m):
 # Rule is frozen before ANY outcome extraction. Only H1 closes ending
 # <= t-1h can enter; all required hours strictly past t.
 if not all(all(t-k*H in m[s] for k in (1,2,4)) for s in SCOPE):return None
 changes=[m[s][t-H]/m[s][t-4*H]-1 for s in FACTOR]
 signs=[1 if x>0 else -1 if x<0 else 0 for x in changes]
 if not(signs[0]==signs[1]==signs[2] and signs[0]!=0):return None
 consensus=sorted(abs(x) for x in changes)[1]
 if consensus<CONSENSUS_MIN:return None
 aud_last=m[TARGET][t-H]/m[TARGET][t-2*H]-1
 if abs(aud_last)<COUNTERMOVE_MIN or aud_last*D(signs[0])>=0:return None
 # The fixed 0.35 exposure estimate is explicitly a *hypothesis scale*
 # derived from a 3-hour completed factor, NOT conditional expectancy.
 projected=D(".35")*consensus*m[TARGET][t-H]*UNITS/m["EURJPY"][t-H]
 approx_friction=(SPREADS[1]+2*SLIP)*UNITS/m["EURJPY"][t-H]+2*FEE
 if projected<HURDLE*approx_friction:return None
 return signs[0]

def freeze_decisions(m):
 result=[];counts=collections.Counter()
 for t in range(FIRST,LAST,H):
  d=dt.datetime.fromtimestamp(t,dt.timezone.utc)
  if d.weekday()>=5 or not 7<=d.hour<=15:continue
  side=signal(t,m)
  if side is None:counts["flat"]+=1
  else:result.append((t,side));counts["signal"]+=1
 return result,dict(counts)

def after_observation(tape,signals):
 # Opening this original M5 future-price lookup occurs only AFTER the same
 # frozen policy has registered and ALL causal decisions have been stored.
 future=tape["outcome_lookup_PRIVATE_NOT_NATIVE_INPUT"]
 settled=[];censored=[]
 for t,side in signals:
  a=future.get(TARGET+"|"+now(t));b=future.get("EURJPY|"+now(t))
  if not a or not b:
   censored.append({"time":now(t),"reason":"MISSING_ORIGINAL_NEXT_M5_OPEN"});continue
  vals=[D(str(r[k])) for r in (a,b) for k in ("entry","exit")]
  flag(all(v.is_finite() and v>0 for v in vals),"SOURCE_FUTURE_PRICE")
  settled.append((t,side,vals))
 return settled,censored

def feed(settled,candidate,spread):
 events=[];seq=0
 for t,side,vals in settled:
  a,b,ea,eb=vals
  def quote(at,px,fx):
   bid=px-spread/2;ask=px+spread/2
   flag(bid>0 and fx>0 and STOP>spread,"BIDASK_SCENARIO_GEOMETRY")
   return {"$feed":"quote","Utc":now(at),"Symbol":TARGET,
      "Bid":float(bid),"Ask":float(ask),"QuoteToEur":float(1/fx),
      "QuoteLossToEur":float(1/(fx-D(".0002"))),
      "ExecutableUnits":float(UNITS),"InitialMarginEur":float(MARGIN),
      "CommissionPerSideEur":float(FEE),"SlipPerSideQuote":float(SLIP),
      "EstimatedStopRiskEur":float(STOP*UNITS/(fx-D(".0002"))),
      "StopDistanceQuote":float(STOP),"BidSourceUtc":now(at),
      "AskSourceUtc":now(at),"NativeSizingScenarioSha256":candidate["spec_hash"],
      "BrokerVolumeMinUnits":float(UNITS),"BrokerVolumeMaxUnits":float(UNITS),
      "BrokerVolumeStepUnits":float(UNITS)}
  seq+=1
  events.append({"$feed":"explicit-decision","Utc":now(t),"Symbol":TARGET,
   "Sequence":seq,"Desired":side,"ValidFromUtc":now(t+300),
   "ExpiresUtc":now(t+301),"PolicySha256":candidate["spec_hash"]})
  events.append(quote(t+300,a,ea))
  seq+=1
  # Time-based exit is committed upon entry, before future exit pricing.
  events.append({"$feed":"explicit-decision","Utc":now(t+H-2),"Symbol":TARGET,
   "Sequence":seq,"Desired":0,"ValidFromUtc":now(t+H),
   "ExpiresUtc":now(t+H+1),"PolicySha256":candidate["spec_hash"]})
  events.append(quote(t+H,b,eb))
 events.sort(key=lambda x:(x["Utc"],0 if x["$feed"]=="quote" else 1))
 return {"schema":"mxm.funded-programme-feed.v1","partition":"DEVELOPMENT",
  "orders":0,"cloud":False,"synthetic":False,"policy_sha256":candidate["spec_hash"],
  "events":events,"events_sha256":digest(events),"source_sha256":digest(candidate["source"]),
  "symbols":[TARGET],"execution_chunk_size":1500,
  "preserve_chunk_originals":True,
  "parameters":{"Strategy":0,"MaxMarginFraction":.4,"MaxPositions":1,
   "MinimumFreeMarginReserveEur":120,"MaxEstimatedStopRiskFraction":.01,
   "RoundTripRiskReserveEur":.4,"MaxQuoteAgeSeconds":3602,
   "ExplicitPolicySha256":candidate["spec_hash"],
   "NativeSizingScenarioSha256":candidate["spec_hash"]},
  "price_basis":"ORIGINAL_M5_NEXT_OPEN_PRICE_WITH_HYPOTHETICAL_BIDASK_COST",
  "historical_total_costs_proven":False,"historical_fills":False,
  "intrabar_stop_path_observed":False}

def reconcile(result):
 account=result["account"]
 cash=D(200);open_=False;gross=D(0);fees=D(0)
 for item in account["Ledger"]:
  flag(item["Symbol"]==TARGET and item["Kind"] in ("ENTRY","EXIT"),"LEDGER_ID")
  if item["Kind"]=="ENTRY":
   flag(not open_,"OVERLAPPING_CSHARP_POSITIONS");open_=True
  else:
   flag(open_,"UNPAIRED_CSHARP_EXIT");open_=False
  gross+=D(str(item["GrossEur"]));fees+=D(str(item["CommissionEur"]))
  cash+=D(str(item["GrossEur"]))-D(str(item["CommissionEur"]))
  flag(abs(cash-D(str(item["CashEur"])))<D(".00000001"),"INDEPENDENT_CASH")
 flag(not open_ and account["OpenPositions"]==0,"FINAL_OPEN")
 flag(abs(cash-D(str(account["FinalCashEur"])))<D(".00000001"),"FINAL_CASH")
 return {"initial_eur":200,"final_cash_eur":float(cash),
  "final_marked_equity_eur":account["MarkedEquityEur"],
  "net_eur":float(cash-200),"gross_price_pnl_eur":float(gross),
  "commissions_eur":float(fees),"max_drawdown_eur":account["MaxDrawdownEur"],
  "entries":account["AcceptedEntries"],"exits":account["ExecutedExits"],
  "rejections":account["RejectedEntries"],"entries_by_week":account["EntriesByIsoWeek"],
  "week_count":len(account["EntriesByIsoWeek"]),"reset_count":result["reset_count"],
  "CSharp_actual":True,"HARD21_proven":False,"broker_fill_proven":False}

def verify_original_scope():
 flag(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield" and
      os.environ.get("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1" and
      os.environ.get("GITHUB_EVENT_NAME")=="push" and
      os.environ.get("GITHUB_RUN_ATTEMPT")=="1","ONE_OFFICIAL_ATTEMPT")
 def get(s):
  return json.loads(subprocess.check_output(
   ["gh","api","repos/mariancradulescu/mxm-quant-greenfield/"+s],text=True))
 head=os.environ["GITHUB_SHA"]
 flag(get("git/ref/heads/mxm-remediation-p0-p4-20261015-v1")["object"]["sha"]==head,"HEAD_CAS")
 flag(len(get("commits/"+head)["parents"])==2,"REVIEWED_MERGE")
 history=get("actions/workflows/mxm-be-jpy-consensus-annual-20261101.yml/runs?per_page=100")
 pushes=[r for r in history["workflow_runs"] if r["event"]=="push" and
  r["head_branch"]=="mxm-remediation-p0-p4-20261015-v1"]
 flag(history["total_count"]<=100 and len(pushes)==1 and
      pushes[0]["id"]==int(os.environ["GITHUB_RUN_ID"]),"SINGLE_PUSH")
 parents=get("commits/"+head)["parents"]
 runs=get("actions/runs?event=pull_request&per_page=100")["workflow_runs"]
 passed={r["name"] for r in runs if r["head_sha"]==parents[1]["sha"] and
         r["conclusion"]=="success"}
 flag({"MXM R3 protected technical installation CI",
       "MXM CSharp Pepperstone protected gateway CI"}<=passed,"PR_CI")
 flag(not OUT.exists(),"EXISTING_OUTCOME")
 print("MXM_JPY_ANNUAL_FIRST_EXECUTION_ADMITTED")


def recover_admit():
 # A NEW reviewed one-shot recovery lane, not a second economic hypothesis,
 # and never a rerun of a completed economic outcome.
 flag(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield"
      and os.environ.get("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1"
      and os.environ.get("GITHUB_EVENT_NAME")=="push"
      and os.environ.get("GITHUB_RUN_ATTEMPT")=="1","RECOVERY_OFFICIAL_FIRST")
 def get(s):
  return json.loads(subprocess.check_output(
   ["gh","api","repos/mariancradulescu/mxm-quant-greenfield/"+s],text=True))
 old=get("actions/runs/41345691597")
 flag(old["conclusion"]=="failure" and old["run_attempt"]==1 and
      old["head_sha"]=="7c84ffd3cfd6fb1bc9ea0a57034e26e8b6f47c09",
      "RECOVERY_ONLY_ORIGINAL_FAILED_HEAD")
 oldart=get("actions/runs/41345691597/artifacts")
 flag(oldart["total_count"]==0,"RECOVERY_ORIGINAL_ECONOMIC_ARTIFACT_EXISTS")
 oldjobs=get("actions/runs/41345691597/jobs?per_page=100")
 bad=[j for j in oldjobs["jobs"] if j["name"]=="one-original-annual-csharp-funded"]
 flag(len(bad)==1 and bad[0]["conclusion"]=="failure"
      and any(z["name"].startswith("Authentic annual Pepperstone tape")
              and z["conclusion"]=="failure" for z in bad[0]["steps"]),
      "RECOVERY_ORIGINAL_FAILED_BEFORE_SOURCE_ADMISSION")
 head=os.environ["GITHUB_SHA"]
 flag(get("git/ref/heads/mxm-remediation-p0-p4-20261015-v1")["object"]["sha"]==head,
      "RECOVERY_EXACT_OFFICIAL_HEAD")
 parents=get("commits/"+head)["parents"]
 flag(len(parents)==2 and parents[0]["sha"]==
      "7c84ffd3cfd6fb1bc9ea0a57034e26e8b6f47c09","RECOVERY_ON_ORIGINAL_HEAD")
 history=get("actions/workflows/mxm-be-jpy-annual-one-recovery-20261101.yml/runs?per_page=100")
 pushes=[r for r in history["workflow_runs"] if r["event"]=="push" and
        r["head_branch"]=="mxm-remediation-p0-p4-20261015-v1"]
 flag(history["total_count"]<=100 and len(pushes)==1 and
      pushes[0]["id"]==int(os.environ["GITHUB_RUN_ID"]),
      "RECOVERY_ONE_NEW_PUSH_ONLY")
 runs=get("actions/runs?event=pull_request&per_page=100")["workflow_runs"]
 passed={r["name"] for r in runs if r["head_sha"]==parents[1]["sha"] and
       r["conclusion"]=="success"}
 flag({"MXM R3 protected technical installation CI",
       "MXM CSharp Pepperstone protected gateway CI"}<=passed,
      "RECOVERY_REVIEWED_CI")
 flag(not OUT.exists(),"RECOVERY_NO_PRIOR_OUTPUT")
 read_spec();selftest()
 print("MXM_JPY_ORIGINAL_ONLY_FIRST_RECOVERY_ADMITTED")

def run():
 p=read_spec();history=historical_accounting(ROOT)
 flag(history["reconciled"] and history["V2"]["used"]==21,"HISTORICAL_REGISTRY")
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.shallow_m5_support_v2_production import public_spki_sha256
 flag(public_spki_sha256(tape_source.KEY)==FP,"EXISTING_RECIPIENT")
 private=os.environ.get("MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM")
 flag(private is not None and "BEGIN" in private,"CUSTODY_PRIVATE_AUTH")
 OUT.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory() as directory:
  tmp=pathlib.Path(directory)
  parts=sorted(tape_source.CIPHER_DIR.glob("chunk-*.b64"))
  flag(len(parts)==7,"SEVEN_PINNED_SOURCE_PARTS")
  blob=b"".join(base64.b64decode(q.read_text(),validate=False) for q in parts)
  raw=tape_source.decrypt(blob,private.encode(),tmp)
  tape=json.loads(raw)
  m=decode(tape);support=source_admit(m)
  result={"schema":"mxm.jpy-factor-original-annual-csharp-first.v1",
   "head":os.environ["GITHUB_SHA"],"run_id":int(os.environ["GITHUB_RUN_ID"]),
   "source_sha256":hashlib.sha256(raw).hexdigest(),
   "source_support":support,"roster_fixed_preoutcome":list(FACTOR)+[TARGET],
   "source_annual_8_pairs":len(tape["symbols"]),"orders":0,
   "broker_requests":0,"Cloud":False,"capital_eur":200,
   "source_decisions":0,"censored":0,"HARD21_certified":False,
   "historical_spread_fee_swap_proven":False,"economic_qualification":False,
   "independent_holdout":False}
  private_out={"spec":p,"support":support,"source_sha256":result["source_sha256"]}
  if support["admitted"]:
   manifest=joint.programme(p)
   lab=Laboratory(manifest,history,
    TrialBook({"V4":1,"V2":history["V2"]["limit"]},
              {"V4":0,"V2":history["V2"]["used"]}))
   lab.execute("register")
   candidate=lab.state["results"]["register"]["value"]
   decisions,counts=freeze_decisions(m)
   # Complete prospective signal list is sealed before future outcome retrieval.
   provenance=hashlib.sha256(encoded(decisions)).hexdigest()
   settled,censored=after_observation(tape,decisions)
   private_out.update({"decision_hash":provenance,"decisions":decisions,
                       "settled":settled,"censored":censored})
   result.update({"source_decisions":len(decisions),"observable":len(settled),
                  "censored":len(censored),"candidate_counts":counts,
                  "decision_sha256":provenance})
   if settled:
    receipts={}
    for i,sp in enumerate(SPREADS):
     data=feed(settled,candidate,sp)
     if i==1:
      # Exactly ONE registered V4 economic account. Other two precommitted
      # prices are sensitivity counterfactuals, never separate alpha studies.
      lab.authenticated_csharp_feed=data
      lab.execute("account");lab.execute("report")
      original=lab.state["results"]["account"]["value"]
     else:
      original=funded_execute(candidate,data,False)
     receipts[str(sp)]=reconcile(original)
     private_out["scenario_"+str(sp)]=original
    result["scenario_results"]=receipts
    result["classification"]="NO_PROMOTION_CENSORED" if censored else (
      "NET_FAIL_CSHARP_FUNDED" if receipts["0.04"]["net_eur"]<=0 else
      "DEVELOPMENT_POSITIVE_UNCERTIFIED")
   else:result["classification"]="STOP_ZERO_SETTLED_SIGNALS"
  else:result["classification"]="STOP_PRICE_BLIND_LONG_SOURCE_GAP"
  private_text=encoded(private_out)
  tape_source.encrypt_private_output(private_text,tmp,OUT/"private.mxmenc")
  result["private_sha256"]=hashlib.sha256(private_text).hexdigest()
  result["private_cipher_sha256"]=hashlib.sha256((OUT/"private.mxmenc").read_bytes()).hexdigest()
  (OUT/"receipt.json").write_bytes(encoded(result))
  print("MXM_JPY_ANNUAL_ACTUAL_CSHARP_ECONOMIC_RESULT "+json.dumps(result,sort_keys=True),flush=True)

def cold():
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack
 from research_core_v4.successor_c_20261018.readback import FP
 rec=json.loads((OUT/"receipt.json").read_bytes());enc=(OUT/"private.mxmenc").read_bytes()
 flag(hashlib.sha256(enc).hexdigest()==rec["private_cipher_sha256"],"COLD_CIPHER")
 with tempfile.TemporaryDirectory() as directory:
  tmp=pathlib.Path(directory);key,fp=_private_key_from_secret(tmp)
  flag(fp==FP,"COLD_RECIPIENT")
  raw=unpack(owner.bounded_decrypt(enc,key,tmp))
 flag(hashlib.sha256(raw).hexdigest()==rec["private_sha256"],"COLD_PLAIN")
 d=json.loads(raw)
 if "scenario_results" in rec:
  for key in ("0.02","0.04","0.08"):
   flag(reconcile(d["scenario_"+key])==rec["scenario_results"][key],
       "COLD_INDEPENDENT_CSHARP_LEDGER")
 print("MXM_JPY_ANNUAL_ACTUAL_CSHARP_COLD_SUCCESS",rec["run_id"],flush=True)

if __name__=="__main__":
 import sys
 flag(len(sys.argv)==2 and sys.argv[1] in ("selftest","admit","recover-admit","run","cold"),"ACTION")
 {"selftest":selftest,"admit":verify_original_scope,
  "recover-admit":recover_admit,"run":run,"cold":cold}[sys.argv[1]]()
