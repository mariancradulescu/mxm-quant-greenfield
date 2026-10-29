"""One frozen distinct session-opening inventory unwind on authentic Pepperstone H1.
First use is source/time admission; no new broker contact, order, model re-run or protected opening.
Results remain fixed EUR1000 normalized DEVELOPMENT, never EUR200 realized account returns.
"""
import collections
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import statistics
import tempfile
from pathlib import Path
from . import source_first_diverse_h1_economics as src
from .common import need

ROOT=src.ROOT
SPEC=ROOT/"research_core_v4/laboratory/SESSION_OPEN_INVENTORY_20261029_V1.json"
OUT=ROOT/"verification/session-inventory-20261029"
H=3600
IDENTITY="V4-SESSION-20261029-EUROPE-OVERNIGHT-INVENTORY"
BAR_HOUR=7
NOTIONAL=1000.
def dump(a):return (json.dumps(a,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def digest(b):return hashlib.sha256(b).hexdigest()
def validate():
    s=json.loads(SPEC.read_bytes())
    need(s["schema"]=="mxm.v4.single-prospective-session-inventory.v1" and s["identity"]==IDENTITY,"SPEC_IDENTITY")
    need(s["source_release_id"]==409747426 and {int(k):v for k,v in s["targets"].items()}==src.TARGETS,"SPEC_SOURCE")
    need(s["decision_bar_utc_hour"]==7 and s["min_priceblind_decision_days_per_target"]==12 and
         s["min_priceblind_complete_fraction"]==.9 and s["min_eligible_calendar_weeks"]==3,"SPEC_SUPPORT")
    need(s["single_procedure_identity_count"]==1 and s["dependent_market_cells"]==3 and
         s["broker_requests"]==0 and s["orders"]==0 and not s["automatic_retry"] and
         not s["protected_forward_opened"] and s["closed_models_rerun"]==0,"NO_EXTRANEOUS_WORK")
    need(s["sizing"]=="1000EUR_FIXED_STAGE_A_REFERENCE_NOT_BROKER_VOLUME_NOT_EUR200_ACCOUNT","NOTIONAL")
    source_spec,authority=src.validate()
    need(all(s["roundtrip_coarse_cost_fraction"][str(sid)]==src.COSTS[sid] for sid in src.TARGETS),"SOURCE_COST_FROZEN")
    need(s["cost_authority"]=="evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json","COST_LINK")
    proj=json.loads((ROOT/s["broker_minimum_margin_projection"]).read_bytes())
    need(proj["historical_applicability_proven"] is False and
         {int(x["symbol_id"]) for x in proj["items"]}==set(src.TARGETS),"MARGIN_REFERENCE_SCOPE")
    return s,proj
def days(corpus,sid):
    m=corpus[sid]
    result=[]
    for t in range(src.START,src.END,H):
        clock=dt.datetime.fromtimestamp(t,dt.timezone.utc)
        if clock.hour!=BAR_HOUR or clock.weekday()>=5:continue
        if all(t-j*H in m for j in range(5)):
            result.append(t)
    return result
def support(corpus):
    # Strictly timestamp/row-existence only: no OHLC values, returns or cost signs.
    stats={}
    for sid in src.TARGETS:
        candidates=days(corpus,sid)
        complete=sum(all(t+j*H in corpus[sid] for j in (2,4)) for t in candidates)
        weeks=sorted({src.week(t) for t in candidates})
        passed=len(candidates)>=12 and len(weeks)>=3 and complete>=.9*len(candidates)
        stats[str(sid)]={"admissible_timestamp_days":len(candidates),
         "future_09_and_11_UTC_bar_presence":complete,
         "future_response_present_fraction":complete/len(candidates) if candidates else 0.,
         "eligible_weeks":weeks,"passed":passed}
    return {"source_admission":"PASS_BEFORE_ECONOMIC_IDENTITY" if all(x["passed"] for x in stats.values()) else "SOURCE_STOP_NO_ECONOMIC_IDENTITY",
      "price_blind":True,"profiles":stats}
def evaluate(corpus):
    records=[];weekly=collections.defaultdict(lambda:dict(decisions=0,signals=0,settled=0,censored=0,gross=0.,cost=0.,net=0.))
    per_market={sid:dict(instrument=name,decisions=0,signals=0,settled=0,censored=0,gross=0.,cost=0.,net=0.)
      for sid,name in src.TARGETS.items()}
    for sid,name in src.TARGETS.items():
        m=corpus[sid]
        for t in days(corpus,sid):
            w=src.week(t);a=weekly[w];b=per_market[sid];a["decisions"]+=1;b["decisions"]+=1
            anchor=m[t-4*H][0];close=m[t][3]
            drift=close/anchor-1.
            ranges=sorted((m[t-j*H][1]-m[t-j*H][2])/m[t-j*H][0] for j in range(5))
            hurdle=max(1.5*src.COSTS[sid], .35*ranges[2])
            side=0 if abs(drift)<=hurdle else (-1 if drift>0 else 1)
            row=dict(target=name,sid=sid,decision_bar_utc=dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat(),
             usable_at_utc=dt.datetime.fromtimestamp(t+H,dt.timezone.utc).isoformat(),
             entry_utc=dt.datetime.fromtimestamp(t+2*H,dt.timezone.utc).isoformat(),
             exit_utc=dt.datetime.fromtimestamp(t+4*H,dt.timezone.utc).isoformat(),
             observed_overnight_displacement=drift,median_completed_range_fraction=ranges[2],
             frozen_cost_fraction=src.COSTS[sid],hurdle_fraction=hurdle,side=side,
             reason="FILTER_ABSTAIN" if side==0 else "PENDING_RESPONSE",gross_eur=None,cost_eur=None,coarse_net_eur=None)
            if side:
                a["signals"]+=1;b["signals"]+=1
                if t+2*H not in m or t+4*H not in m:
                    a["censored"]+=1;b["censored"]+=1;row["reason"]="MISSING_FUTURE_PRICE_CENSORED"
                else:
                    entry=m[t+2*H][0];exit=m[t+4*H][0]
                    gross=NOTIONAL*side*(exit/entry-1.);cost=NOTIONAL*src.COSTS[sid]
                    for x in (a,b):
                        x["settled"]+=1;x["gross"]+=gross;x["cost"]+=cost;x["net"]+=gross-cost
                    row.update(reason="SETTLED_REFERENTIAL_ONLY",modeled_entry_open=entry,modeled_exit_open=exit,
                      gross_eur=gross,cost_eur=cost,coarse_net_eur=gross-cost)
            records.append(row)
    gross=sum(x["gross"] for x in per_market.values())
    cost=sum(x["cost"] for x in per_market.values())
    net=gross-cost;count=sum(x["settled"] for x in per_market.values())
    censored=sum(x["censored"] for x in per_market.values())
    stress={"frozen_coarse":net,"twice_coarse":gross-2*cost,"twice_coarse_plus_2bps":gross-2*cost-0.20*count}
    wk=dict(sorted(weekly.items()))
    positives=sum(x["net"]>0 for x in wk.values())
    status=("SOURCE_RESPONSE_CENSOR_UNRESOLVED" if censored else
        "NO_SIGNALS" if not count else "GROSS_FAIL" if gross<=0 else
        "COARSE_NET_FAIL" if net<=0 else "COST_SCENARIO_SIGN_FAIL" if min(stress.values())<=0 else
        "EXPLORATORY_COST_SCENARIO_POSITIVE_NO_CERTIFICATION")
    return records,{"identity":IDENTITY,"classification":status,"decisions":len(records),
      "signals":sum(x["signals"] for x in per_market.values()),"settled":count,"censored":censored,
      "gross_reference_eur":gross,"coarse_cost_eur":cost,"coarse_net_reference_eur":net,
      "cost_sensitivity_reference_eur":stress,
      "weekly":wk,"per_market":per_market,"positive_coarse_net_weeks":positives,
      "hard21_certified":False,"continuous_200_account_replayed":False,
      "all_in_historical_costs_proven":False,"independent_confirmation":False,
      "trading_permitted":False,"stage_b_executed":False}
def selftest():
    validate()
    m={sid:{} for sid in src.TARGETS}
    for t in range(src.START-5*H,src.END+5*H,H):
        if dt.datetime.fromtimestamp(t,dt.timezone.utc).weekday()>=5:continue
        i=(t-src.START)//H
        for sid in m:
            p=100+sid*.1+(i%24)*.01+(i//24)*.005
            m[sid][t]=(p,p+.05,p-.05,p+.002)
    need(support(m)["source_admission"]=="PASS_BEFORE_ECONOMIC_IDENTITY","TEST_SUPPORT")
    rows,r=evaluate(m)
    need(len(rows)==sum(x["decisions"] for x in r["per_market"].values()),"TEST_ROW_PRESERVATION")
    need(all(x["side"]==0 or x["entry_utc"]>x["usable_at_utc"] for x in rows),"TEST_CAUSAL_DELAY")
    cutoff=src.END-7*86400
    old=[x for x in rows if x["decision_bar_utc"]<dt.datetime.fromtimestamp(cutoff,dt.timezone.utc).isoformat()]
    for sid in m:
        for t in list(m[sid]):
            if t>=cutoff:
                m[sid][t]=tuple(v*1.11 for v in m[sid][t])
    new,_=evaluate(m)
    need(old==[x for x in new if x["decision_bar_utc"]<dt.datetime.fromtimestamp(cutoff,dt.timezone.utc).isoformat()],"TEST_NO_FUTURE_LEAK")
    m[250]={}
    need(support(m)["source_admission"]=="SOURCE_STOP_NO_ECONOMIC_IDENTITY","TEST_SOURCE_GATE")
    print("MXM_SESSION_INVENTORY_PREFLIGHT_PASS no source decryption, no broker requests, no economic result")
def main():
    import sys
    if sys.argv[1:]==["selftest"]:selftest();return
    need(sys.argv[1:]==["run"],"RUN_MODE")
    s,projection=validate()
    need(os.environ.get("GITHUB_REPOSITORY")=="mariancradulescu/mxm-quant-greenfield" and
         os.environ.get("GITHUB_REF_NAME")=="mxm-remediation-p0-p4-20261015-v1" and
         os.environ.get("GITHUB_EVENT_NAME")=="push" and
         os.environ.get("GITHUB_RUN_ATTEMPT")=="1","GITHUB_EXECUTION_SCOPE")
    from .budgets import historical_accounting
    account=historical_accounting(ROOT)
    need(account["reconciled"] and account["V2"]["remaining"]>=0,"ACCOUNTING_MUST_REMAIN_CLOSED")
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    public=ROOT/"research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
    need(public_spki_sha256(public)==FP,"NO_CUSTODY_RECIPIENT_CHANGE")
    with tempfile.TemporaryDirectory() as path:
        private,fp=_private_key_from_secret(Path(path));need(fp==FP,"SOURCE_CUSTODY_BOUND")
        corp={};proofs={}
        for sid,(asset,expected) in src.SOURCES.items():
            value,proof=load_asset(private,fp,Path(path),{"release_id":409747426,"asset_id":asset,"ciphertext_sha256":expected})
            corp[sid]=src.bars(value,sid);proofs[str(sid)]=proof
        admiss=support(corp)
        opened=admiss["source_admission"]=="PASS_BEFORE_ECONOMIC_IDENTITY"
        records,metrics=evaluate(corp) if opened else ([],None)
        private_ledger={"schema":"mxm.session-inventory-private-first-execution.v1",
          "source_head":os.environ["GITHUB_SHA"],"run_id":int(os.environ["GITHUB_RUN_ID"]),
          "identity":IDENTITY if opened else None,"spec_sha256":digest(SPEC.read_bytes()),
          "source_proofs":proofs,"source_admission":admiss,
          "individual_decision_ledger":records,"metrics":metrics,
          "historical_cost_truth":False,"continuous_eur200_account":False,
          "prior_closed_models_executed":0,"orders":0}
        private_bytes=dump(private_ledger)
        OUT.mkdir(parents=True,exist_ok=True)
        encrypt_shard(gzip.compress(private_bytes,mtime=0),public_key=public,output=OUT/"private.mxmenc")
        cipher=(OUT/"private.mxmenc").read_bytes()
        public_receipt={"schema":"mxm.session-inventory-authentic-development.v1",
          "source_head":os.environ["GITHUB_SHA"],"run_id":int(os.environ["GITHUB_RUN_ID"]),
          "spec_sha256":digest(SPEC.read_bytes()),"source_proofs":proofs,"source_admission":admiss,
          "economic_identity_count":1 if opened else 0,"new_model_outcomes":1 if opened else 0,
          "metrics":metrics,"individual_decisions_encrypted":len(records),
          "private_plaintext_sha256":digest(private_bytes),"private_cipher_sha256":digest(cipher),
          "private_result_bytes":len(private_bytes),"original_minimum_margin_reference_eur":
             {str(x["symbol_id"]):max(x["margin"]["buy"],x["margin"]["sell"])/100 for x in projection["items"]},
          "margin_historical_applicability":False,"minimum_volume_full_entry_admission":False,
          "pnl_basis":"FIXED_EUR1000_STAGE_A_REFERENCE_NOT_EUR200_ACCOUNT",
          "historic_slippage_swap_fees_verified":False,"capital_path_verified":False,
          "funded_realization":False,"HARD21_certified":False,"independent_confirmation":False,
          "prior_experiments_rerun":0,"v2_used_unchanged":account["V2"]["used"],
          "v2_remaining_unchanged":account["V2"]["remaining"],
          "broker_requests":0,"orders":0,"cloud_activated":False,
          "automatic_retry":False}
        (OUT/"receipt.json").write_bytes(dump(public_receipt))
        print("MXM_AUTHENTIC_SESSION_INVENTORY "+dump(public_receipt).decode(),flush=True)
if __name__=="__main__":main()
