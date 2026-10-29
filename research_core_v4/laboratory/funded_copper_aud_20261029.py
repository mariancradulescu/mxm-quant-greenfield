"""One original source-first genuine Pepperstone H1 to fixed 1000-base-unit AUDUSD EUR200 C# account.
No EUR1000 notional, no broker orders, no Cloud, no reinterpretation of OHLC as ticks.
"""
import collections
import datetime as dt
import gzip
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from decimal import Decimal as D
from .common import need
from . import source_first_diverse_h1_economics as original

ROOT=original.ROOT
SPEC=ROOT/"research_core_v4/laboratory/FUNDED_COPPER_AUD_LEAD_20261029_V1.json"
OUT=ROOT/"verification/funded-copper-aud-20261029"
PROJECT=ROOT/"research_core_v4/laboratory/csharp/funded_copper_aud/MxmFundedCopperAud.csproj"
H=3600;START=original.START;END=original.END
SOURCES={1:(631098100,"c33f401a97d06e2efe31e49f37a1f977238b41b66eb1d939b1d6700fb2530915"),
 5:original.SOURCES[5],111:original.SOURCES[111]}
def encode(x):return (json.dumps(x,separators=(",",":"),sort_keys=True,allow_nan=False)+"\n").encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def validate():
 s=json.loads(SPEC.read_bytes());a=s["account"];c=s["scenario"]
 need(s["identity"]=="V4-20261029-COPPER-TO-AUDUSD-CAUSAL-TRANSFER" and
      s["schema"]=="mxm.v4.real-200-copper-audusd-development.v1","FROZEN_ID")
 need(s["source"]=="ORIGINAL_AUTHENTICATED_PEPPERSTONE_H1_RELEASE_409747426" and
      set(s["sources"])=={"EURUSD","AUDUSD","Copper"},"SOURCE")
 need(a["starting_eur"]==200 and a["minimum_volume_aud_base_units"]==a["max_volume_aud_base_units"]==1000 and
      a["native_minimum_margin_buy_eur"]==31.04 and a["native_minimum_margin_sell_eur"]==31.04 and
      a["minimum_free_margin_eur"]==120 and a["stop_risk_fraction_of_equity"]==0.01 and
      a["stop_distance_audusd"]==.0012 and a["roundtrip_risk_reserve_eur"]==.4 and
      a["maximum_estimated_new_loss_eur"]==2 and a["max_positions"]==1,"ACTUAL_200_ACCOUNT")
 need(c["spread_full_price_audusd"]==.00015 and c["slippage_each_side_price"]==.00005 and
      c["commission_eur_each_side"]==.04 and not a["historical_broker_terms_proven"],"SCENARIO")
 need(s["research_attempts"]==1 and s["orders"]==0 and s["new_broker_requests"]==0 and
      not s["cloud"] and not s["hyperparameter_search"] and not s["automatic_retry"],"ONE_BOUNDED_TRIAL")
 return s
def common_times(corp):
 result=[]
 for t in range(START,END,H):
  date=dt.datetime.fromtimestamp(t,dt.timezone.utc)
  if date.weekday()>=5 or not 7<=date.hour<=15:continue
  if all(t-j*H in corp[k] for k in (5,111) for j in (1,4)) and t in corp[1]:
   result.append(t)
 return result
def support(corp):
 decision=common_times(corp)
 complete=sum(all(t+j*H in corp[5] and t+j*H in corp[1] for j in (1,3)) for t in decision)
 weeks=sorted({original.week(t) for t in decision})
 okay=len(decision)>=100 and len(weeks)>=3 and complete>=.9*len(decision)
 return dict(classification="SOURCE_ADMITTED_BEFORE_ECONOMIC_IDENTITY" if okay else "SOURCE_STOP_NO_IDENTITY",
  price_blind=True,common_decision_timestamps=len(decision),complete_future_reference_timestamps=complete,
  complete_fraction=complete/len(decision) if decision else 0,iso_weeks=weeks,
  h1_not_actual_bidask=True)
def arrays(corp):
 return {key:[[1000*t,*[float(x) for x in values]] for t,values in sorted(corp[sid].items())]
         for key,sid in (("aud",5),("copper",111),("fx",1))}
def asfloat(v):return float(v)
def account_analysis(payload,corpus):
 a=payload["account"];ledger=a["Ledger"];cash=D(200);gross=D(0);fees=D(0);entry=None
 by_week=collections.defaultdict(lambda:dict(entries=0,exits=0,realized_net_eur=D(0)))
 by_month=collections.defaultdict(lambda:dict(entries=0,exits=0,realized_net_eur=D(0)))
 executed=0;extra_stress=D(0)
 for x in ledger:
  k=x["Kind"];need(k in ("ENTRY","EXIT"),"ACCOUNT_NONTRADE_LEDGER")
  stamp=dt.datetime.fromisoformat(x["Utc"].replace("Z","+00:00"));week=stamp.strftime("%G-W%V");month=stamp.strftime("%Y-%m")
  if k=="ENTRY":
   need(entry is None and x["Symbol"]=="AUDUSD" and x["Units"]==1000 and x["Direction"] in (-1,1),"EXACT_NATIVE_VOLUME")
   entry=x;by_week[week]["entries"]+=1;by_month[month]["entries"]+=1
  else:
   need(entry is not None and x["Units"]==1000 and x["Symbol"]=="AUDUSD" and x["Direction"]==entry["Direction"],"MATCHED_EXIT")
   entry=None;executed+=1;by_week[week]["exits"]+=1;by_month[month]["exits"]+=1
   fx_hour=(int(stamp.timestamp())//H)*H
   fx_at=corpus[1].get(fx_hour)
   need(fx_at is not None and D(str(fx_at[0]))>D(".0003"),"LOSS_SIDE_FX_AT_EACH_EXIT")
   extra_stress+=D(".00010")*D(1000)/(D(str(fx_at[0]))-D(".0003"))
  fee=D(str(x["CommissionEur"]));g=D(str(x["GrossEur"]));fees+=fee;gross+=g;cash+=g-fee
  by_week[week]["realized_net_eur"]+=g-fee;by_month[month]["realized_net_eur"]+=g-fee
  need(abs(cash-D(str(x["CashEur"])))<D(".0000001"),"UNBROKEN_CASH_PATH")
 need(abs(cash-D(str(a["FinalCashEur"])))<D(".0000001"),"ACCOUNT_CASH_RECONCILED")
 need(a["InitialCapitalEur"]==200 and a["AcceptedEntries"]==sum(z["entries"] for z in by_week.values()) and
      a["AcceptedEntries"]==sum(z["entries"] for z in by_month.values()),"CONTINUOUS_INITIAL_CAPITAL")
 need(a["OpenPositions"]==0 and a["ExecutedExits"]==executed and entry is None and
      a["MarkedEquityEur"]==a["FinalCashEur"],"COMPLETED_EQUITY")
 # Independently compare original C# decisions to strict-only historical feature availability.
 expected=[]
 for t in common_times(corpus):
  a_last=corpus[5][t-H][3];a_before=corpus[5][t-4*H][3]
  c_last=corpus[111][t-H][3];c_before=corpus[111][t-4*H][3]
  ar=D(str(a_last))/D(str(a_before))-1;cr=D(str(c_last))/D(str(c_before))-1
  direction=(1 if cr>0 else -1) if abs(cr)>D(".004") and abs(ar)<D(".001") else 0
  expected.append((1000*t,direction))
 got=[(x["t"],x["direction"]) for x in payload["decisions"]]
 reference=dict(expected)
 need(len(got)==len(set(t for t,_ in got)) and
      all(t in reference and reference[t]==side for t,side in got),"FIRST_EXECUTION_CAUSAL_SIGNAL_PARITY")
 need(all(x["direction"]!=0 for x in payload["proposals"]),"ZERO_SIGNAL_PROPOSAL")
 return {"csharp_account_classification":a["Classification"],"actual_native_minimum_units":1000,
  "initial_cash_eur":200,"final_cash_eur":asfloat(a["FinalCashEur"]),
  "final_marked_equity_eur":asfloat(a["MarkedEquityEur"]),
  "gross_realized_eur":float(gross),"fees_eur":float(fees),"net_cash_eur":float(gross-fees),
  "additional_adverse_roundtrip_1pip_stress_eur":float(extra_stress),
  "stress_net_cash_eur":float(gross-fees-extra_stress),
  "accepted_entries":a["AcceptedEntries"],"completed_exits":a["ExecutedExits"],
  "rejected_entries":a["RejectedEntries"],"open_positions":a["OpenPositions"],
  "modeled_max_drawdown_eur":asfloat(a["MaxDrawdownEur"]),
  "proposal_count":len(payload["proposals"]),"complete_signal_audit":len(expected),
  "weekly":{k:{kk:float(vv) if isinstance(vv,D) else vv for kk,vv in val.items()} for k,val in sorted(by_week.items())},
  "monthly":{k:{kk:float(vv) if isinstance(vv,D) else vv for kk,vv in val.items()} for k,val in sorted(by_month.items())},
  "CSharp_account_replayed":True,"historical_bidask_fills":False,
  "cost_scenario_not_actual_historical":True,"hard21_real_broker":False}
def selftest():
 validate()
 corp={sid:{} for sid in SOURCES}
 for t in range(START-4*H,END+5*H,H):
  date=dt.datetime.fromtimestamp(t,dt.timezone.utc)
  if date.weekday()>=5:continue
  i=(t-START)//H
  for sid in SOURCES:
   price=1.07+sid*.005+.000001*i
   corp[sid][t]=(price,price+.001,price-.001,price+.0001)
 need(support(corp)["classification"]=="SOURCE_ADMITTED_BEFORE_ECONOMIC_IDENTITY","TEST_SUPPORT")
 # Execute the C# product on non-market artificial OHLC. It must preserve EUR200 and never create 1000EUR starting cash.
 with tempfile.TemporaryDirectory() as path:
  data={"policy":sha(SPEC.read_bytes()),"start":1000*START,"end":1000*END}
  data.update(arrays(corp))
  a=Path(path)/"input.json";b=Path(path)/"out.json";a.write_bytes(encode(data))
  subprocess.run(["dotnet","run","-c","Release","--no-build","--project",str(PROJECT),"--",str(a),str(b)],
   check=True,capture_output=True,text=True)
  v=json.loads(b.read_bytes())
  need(v["initial_cash_eur"]==200 and v["deposit_count"]==1 and v["reset_count"]==0 and
       v["model"]=="COPPER_SHOCK_TO_UNRESPONSIVE_AUDUSD","TEST_CSHARP_SOURCEFREE_ACCOUNT")
 corp[111]={}
 need(support(corp)["classification"]=="SOURCE_STOP_NO_IDENTITY","TEST_STOP_BEFORE_IDENTITY")
 print("MXM_COPPER_AUD_FUNDED200_PREFLIGHT_SUCCESS no originals unlocked")
def cold():
 """Verify the original encrypted CSharp-first economic outcome; no CSharp model rerun or H1 source loading."""
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack
 r=json.loads((OUT/"receipt.json").read_bytes())
 cipher=(OUT/"private.mxmenc").read_bytes()
 need(sha(cipher)==r["private_cipher_sha256"],"COLD_CIPHER")
 with tempfile.TemporaryDirectory() as t:
  key,fp=_private_key_from_secret(Path(t));need(fp==FP,"COLD_RECIPIENT")
  raw=unpack(owner.bounded_decrypt(cipher,key,Path(t)),max_bytes=40000000)
 need(sha(raw)==r["private_plain_sha256"],"COLD_FIRST_ORIGINAL")
 p=json.loads(raw)
 need(p["source_head"]==r["source_head"] and p["run_id"]==r["run_id"] and
      p["spec_sha256"]==r["spec_sha256"] and
      p["economic_outcome_count"]==r["economic_models_executed"] and
      (not p["economic_outcome_count"] or p["metrics"]==r["metrics"]),"COLD_FIRST_RESULT_BINDING")
 a={"schema":"mxm.funded200-copper-aud-independent-cold.v1","run_id":r["run_id"],
    "cipher_sha256":r["private_cipher_sha256"],"original_csharp_result_preserved":True,
    "original_csharp_model_rerun":False,"original_broker_source_reopened":False,"orders":0}
 (OUT/"cold.json").write_bytes(encode(a))
 print("MXM_FUNDED200_COLD "+encode(a).decode(),flush=True)
def main():
 import sys
 if sys.argv[1:]==["selftest"]:selftest();return
 if sys.argv[1:]==["cold"]:cold();return
 need(sys.argv[1:]==["run"],"RUN")
 validate()
 need(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield" and
      os.environ.get("GITHUB_REF_NAME")=="mxm-remediation-p0-p4-20261015-v1" and
      os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_RUN_ATTEMPT")=="1","EXACT_HEAD_EXECUTION")
 from .budgets import historical_accounting
 accounting=historical_accounting(ROOT)
 need(accounting["reconciled"] and accounting["V2"]["used"]==21,"ACCOUNTING_UNCHANGED")
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 public=ROOT/"research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
 need(public_spki_sha256(public)==FP,"CUSTODY_RECIPIENT")
 with tempfile.TemporaryDirectory() as tmp:
  key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,"CUSTODY_KEY")
  corp={};proofs={}
  for sid,(asset,expected) in SOURCES.items():
   original_value,proof=load_asset(key,fp,Path(tmp),{"release_id":409747426,"asset_id":asset,"ciphertext_sha256":expected})
   corp[sid]=original.bars(original_value,sid);proofs[str(sid)]=proof
  status=support(corp)
  OUT.mkdir(parents=True,exist_ok=True)
  executed=status["classification"]=="SOURCE_ADMITTED_BEFORE_ECONOMIC_IDENTITY"
  metrics=None;private_original=None
  if executed:
   data={"policy":sha(SPEC.read_bytes()),"start":1000*START,"end":1000*END}
   data.update(arrays(corp))
   input_path=Path(tmp)/"original-input.json";result_path=Path(tmp)/"original-csharp.json"
   input_path.write_bytes(encode(data))
   job=subprocess.run(["dotnet","run","--no-build","-c","Release","--project",str(PROJECT),"--",
       str(input_path),str(result_path)],check=True,text=True,capture_output=True)
   payload=json.loads(result_path.read_bytes())
   need(payload["schema"]=="mxm.funded200.copper-audusd.csharp-original.v1" and
       payload["policy"]==data["policy"] and payload["input_sha256"]==sha(input_path.read_bytes()),"IDENTICAL_CSHARP_INPUT")
   metrics=account_analysis(payload,corp)
   metrics.update({"fault":payload["fault"],"cold_restores":payload["restored_process_count"],
     "source_gaps":payload["source_gaps"],"orders":0,"cloud":False,"outcome_model_count":1})
   private_original={"schema":"mxm.funded200.original-private-first-result.v1",
     "source_head":os.environ["GITHUB_SHA"],"run_id":int(os.environ["GITHUB_RUN_ID"]),
     "spec_sha256":sha(SPEC.read_bytes()),"source_originals":proofs,
     "original_csharp_result":payload,"metrics":metrics,
     "economic_outcome_count":1}
  else:
   private_original={"schema":"mxm.funded200.original-private-first-result.v1",
    "source_head":os.environ["GITHUB_SHA"],"run_id":int(os.environ["GITHUB_RUN_ID"]),
    "spec_sha256":sha(SPEC.read_bytes()),"source_originals":proofs,
    "economic_outcome_count":0,"reason":"PRICE_BLIND_SUPPORT_NOT_ADMITTED"}
  plain=encode(private_original)
  encrypt_shard(gzip.compress(plain,mtime=0),public_key=public,output=OUT/"private.mxmenc")
  encrypted=(OUT/"private.mxmenc").read_bytes()
  receipt={"schema":"mxm.funded200.copper-aud-first-authentic-execution.v1",
   "source_head":os.environ["GITHUB_SHA"],"run_id":int(os.environ["GITHUB_RUN_ID"]),
   "source_originals":proofs,"spec_sha256":sha(SPEC.read_bytes()),
   "admission":status,"economic_models_executed":1 if executed else 0,
   "funding_eur":200,"reset_count":0,"broker_minimum_volume_aud_units":1000,
   "reference_1000_eur_notional_used":False,"metrics":metrics,
   "private_plain_sha256":sha(plain),"private_cipher_sha256":sha(encrypted),
   "source_partition":"EXPOSED_DEVELOPMENT","independent_confirmation":False,
   "actual_broker_fills":False,"historical_total_costs_proven":False,
   "real_hard21_certified":False,"orders":0,"cloud":False,"broker_requests":0,
   "closed_models_rerun":0,"no_retry":True}
  (OUT/"receipt.json").write_bytes(encode(receipt))
  print("MXM_GENUINE_FUNDED200_COPPER_AUD "+encode(receipt).decode(),flush=True)
if __name__=="__main__":main()
