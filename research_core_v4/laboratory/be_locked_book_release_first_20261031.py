"""One frozen *dependent* DEVELOPMENT hypothesis: native quote-lock resolution impulse.

This is neither spread reversion nor price-only momentum nor quote-innovation AR.
The old W37 original sources are already exposed. No confirmation or actual
executability: source timestamps != arrival/fill timestamps, commission and
margin are from a later Pepperstone capture, slippage is a hypothesis.
No new broker access, orders, Cloud or secondary strategy/account.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from decimal import Decimal as D
from datetime import datetime,timezone
import argparse,hashlib,heapq,itertools,json,gzip
from pathlib import Path
from .w37_authentic_spread_cash_20261031 import source_stream,digest
from .usd_pair_native_reception import SOURCES,START,END

# One a-priori study identity. Never modify these values after the first result.
RULE={
 "id":"MXM_BE_NATIVE_LOCK_RELEASE_IMPULSE_W37_20261031_V1",
 "symbols":["EURUSD","GBPUSD"],"source_window":"W37_2026_09_07_13",
 "quote_max_age_ms":5000,"lock_min_ms":2000,
 "release_own_spread_max_raw":3,"release_min_directional_move_raw":12,
 "decision_utc_hours":[7,20],"entry_delay_ms":1000,"entry_deadline_ms":4000,
 "hold_ms":60000,"exit_deadline_ms":65000,"stop_distance_raw":120,
 "minimum_base_units":1000,"eur200_start":200,
 "postdated_margin_eur":{"EURUSD":"33.33","GBPUSD":"38.88"},
 "ticket_margin_cap_eur":80,"free_reserve_eur":120,"max_single_stop_risk_eur":2,
 "scenario_per_side_commission_usd":"0.03",
 "hypothetical_slippage_usd_per_side":"0.01",
 "no_weekend_entry":True,"single_account_single_position":True,
 "no_retune":True,"not_historical_executability":True
}

def need(ok,label):
 if not ok:raise ValueError("MXM_LOCK_RELEASE_"+label)
def is_market_hour(t):
 d=datetime.fromtimestamp(t/1000,timezone.utc)
 return d.weekday()<5 and 7<=d.hour<20
def ready(book,sym,t,*,strict=False):
 b=book[sym]
 if 'bid' not in b or 'ask' not in b:return None
 bid,bt=b['bid'];ask,at=b['ask']
 if bid is None or ask is None:return None
 if (bt>=t or at>=t) if strict else (bt>t or at>t):return None
 if t-bt>RULE['quote_max_age_ms'] or t-at>RULE['quote_max_age_ms']:return None
 if ask<=bid:return None
 return (bid,ask)
def money_fx(book,sym,t):
 # GBPUSD USD cash cannot consume a EURUSD observation from an atomic
 # same-timestamp packet of unknown historical cross-symbol arrival order.
 # For EURUSD its *own* observed book defines the conversion at the quote.
 v=ready(book,"EURUSD",t,strict=(sym!="EURUSD"))
 return v
def price_covered(book,sym,t):
 b=ready(book,sym,t)
 fx=money_fx(book,sym,t)
 return (b,fx) if b and fx else None
def verdict_net(entry,exit_,side,fx,stop=False):
 # Transaction at a future quote, not at the decision quote or mid.
 # USD cash signed payoff uses actual BID/ASK sides observed at entry/exit.
 start=entry[1] if side>0 else entry[0]
 finish=exit_[0] if side>0 else exit_[1]
 gross_usd=D(side)*D(finish-start)*D(1000)/D(100000)
 commission=D(RULE["scenario_per_side_commission_usd"])*2
 slip=D(RULE["hypothetical_slippage_usd_per_side"])*2
 net_usd=gross_usd-commission-slip
 # A USD liability -> EUR at EURUSD BID; a positive USD receipt -> EUR
 # at EURUSD ASK. Both must come from a valid contemporaneous FX lease.
 fxraw=fx[1] if net_usd>=0 else fx[0]
 fxgross=fx[1] if gross_usd>=0 else fx[0]
 net_eur=net_usd*D(100000)/D(fxraw)
 gross_eur=gross_usd*D(100000)/D(fxgross)
 return gross_eur,net_eur,net_eur-gross_eur,stop

def analyze(eur,gbp):
 files={"EURUSD":Path(eur),"GBPUSD":Path(gbp)}
 for sym,path in files.items():
  p=json.loads(Path(str(path)+".receipt.json").read_bytes())
  o=SOURCES[sym]
  need(p["symbol"]==sym and p["source_run"]==o["run"] and
       p["cipher_sha256"]==o["cipher"] and p["private_sha256"]==o["private"]
       and p["events"]==o["bid"]+o["ask"] and p["derived_sha256"]==digest(path),
       "EXACT_AUTHENTIC_ORIGINAL_"+sym)
 books={s:{} for s in RULE["symbols"]}
 locks={s:None for s in RULE["symbols"]}
 last_equal={s:None for s in RULE["symbols"]}
 stats=Counter();weekly=defaultdict(Counter);days=defaultdict(Counter)
 cash=D(RULE["eur200_start"]);top=cash;maxdd=D(0)
 gross=D(0);cost=D(0);net=D(0)
 risk_fault=None;pending=None;position=None
 hashes=hashlib.sha256();nrows=Counter();last=-1
 event_decisions=0;event_entries=0;private_ledger=[]
 def week(t):return datetime.fromtimestamp(t/1000,timezone.utc).strftime("%G-W%V")
 def day(t):return datetime.fromtimestamp(t/1000,timezone.utc).strftime("%Y-%m-%d")
 def confirm_exit(t,b,fx,is_stop):
  nonlocal position,cash,top,maxdd,gross,cost,net
  result=verdict_net(position["entry"],b,position["dir"],fx,is_stop)
  g,n,delta,st=result
  gross+=g;net+=n;cost-=delta;cash+=n;top=max(top,cash);maxdd=max(maxdd,top-cash)
  stats["settled"]+=1;stats["stops"]+=int(st)
  stats["gross_positive"]+=int(g>0)
  stats["scenario_net_positive"]+=int(n>0)
  private_ledger.append({"decision_ms":position["decision"],"entry_ms":position["t"],"exit_ms":t,
    "symbol":position["sym"],"direction":position["dir"],"entry_bid_ask_raw":position["entry"],
    "exit_bid_ask_raw":b,"eurusd_fx_bid_ask_raw":fx,"gross_eur":str(g),
    "scenario_net_eur":str(n),"scenario_cost_eur":str(-delta),"stop_observed":bool(st)})
  weekly[position["week"]]["settled"]+=1
  days[day(t)]["settled"]+=1
  hashes.update((f'{position["decision"]}|{position["t"]}|{t}|{position["sym"]}|{position["dir"]}|'+
                f'{g:.10f}|{n:.10f}\n').encode())
  position=None
 with files["EURUSD"].open() as eh,files["GBPUSD"].open() as gh:
  merged=heapq.merge(source_stream(eh,"EURUSD"),source_stream(gh,"GBPUSD"))
  for t,pack in itertools.groupby(merged,key=lambda v:v[0]):
   need(t>=last,"SOURCE_ORDER");last=t
   by=defaultdict(set)
   for _,sym,side,v in pack:by[sym,side].add(v);nrows[sym]+=1
   for (sym,side),v in by.items():
    books[sym][side]=(next(iter(v)) if len(v)==1 else None,t)
   stats["atomic_groups"]+=1
   for sym in RULE["symbols"]:
    b=books[sym]
    fresh=all(x in b and b[x][0] is not None and t-b[x][1]<=5000 for x in ("bid","ask"))
    if not fresh:
     locks[sym]=None;last_equal[sym]=None;continue
    bid,ask=b["bid"][0],b["ask"][0]
    if bid==ask:
     if locks[sym] is None:locks[sym]=t
     last_equal[sym]=bid
   # A simulated position remains exposed even if quote marks disappear.
   # If its close cannot be observed by the fixed deadline, STOP the full
   # account permanently rather than manufacture an exit/flattening.
   if position:
    sym=position["sym"];q=price_covered(books,sym,t)
    if q is not None and t>=position["t"]:
     b,fx=q
     triggered=(b[0]<=position["entry"][1]-RULE["stop_distance_raw"] if position["dir"]>0 else
                b[1]>=position["entry"][0]+RULE["stop_distance_raw"])
     if triggered and t>position["t"]:confirm_exit(t,b,fx,True)
     elif t>=position["due"] and t<=position["deadline"]:confirm_exit(t,b,fx,False)
    if position and t>position["deadline"]:
     risk_fault="UNOBSERVABLE_ACTIVE_POSITION_AT_EXIT_DEADLINE"
     stats["unresolved_positions"]+=1
     break
   if pending:
    sym=pending["sym"]
    if t>pending["deadline"]:
     stats["unfilled_pending"]+=1;pending=None
    elif t>=pending["ready"]:
     q=price_covered(books,sym,t)
     if q:
      b,fx=q
      if b[1]-b[0]>RULE["release_own_spread_max_raw"]:
       stats["entry_quote_spread_rejected"]+=1;pending=None
       continue
      scenario_margin=D(RULE["postdated_margin_eur"][sym])
      stop_risk=(D(RULE["stop_distance_raw"]+2*RULE["release_own_spread_max_raw"])*D(1000)/D(fx[0])+
                 D('0.08')*D(100000)/D(fx[0]))
      # Owner one-account capital *today*. No prospective earnings added.
      if (scenario_margin>D(RULE["ticket_margin_cap_eur"]) or
          cash-scenario_margin<D(RULE["free_reserve_eur"]) or
          stop_risk>D(RULE["max_single_stop_risk_eur"])):
       stats["funded_admission_rejected"]+=1;pending=None
      else:
       position={"sym":sym,"dir":pending["dir"],"entry":b,"decision":pending["decision"],
                 "t":t,"due":t+RULE["hold_ms"],"deadline":t+RULE["exit_deadline_ms"],
                 "week":week(t)}
       stats["funded_model_entries"]+=1;weekly[week(t)]["entries"]+=1
       days[day(t)]["entries"]+=1
       pending=None;event_entries+=1
   # Evaluate only the first genuine unlock from a prior stable equality.
   # Current positivity is required; equality never becomes a zero-cost fill.
   candidate=[]
   for sym in RULE["symbols"]:
    if locks[sym] is None:continue
    b=ready(books,sym,t)
    if b is None:
     # when current book is still equal, preserve lock state, otherwise
     # discard; stale/conflicted state was cleared before this section.
     raw=books[sym]
     if raw["bid"][0]!=raw["ask"][0]:
      locks[sym]=None;last_equal[sym]=None
     continue
    locktime=locks[sym];baseline=last_equal[sym]
    locks[sym]=None;last_equal[sym]=None
    stats["unlock_observations"]+=1
    if t-locktime<RULE["lock_min_ms"] or baseline is None:continue
    spread=b[1]-b[0]
    midtwice=sum(b)
    delta=midtwice-2*baseline
    if abs(delta)<2*RULE["release_min_directional_move_raw"] or spread>RULE["release_own_spread_max_raw"]:continue
    if not is_market_hour(t):stats["outside_predefined_session"]+=1;continue
    if money_fx(books,sym,t) is None:stats["unqualified_fx"]+=1;continue
    candidate.append((sym,1 if delta>0 else -1))
   if candidate:
    stats["causal_release_signals"]+=len(candidate)
    if pending is None and position is None:
     # deterministic alphabetic precedence; never rank by future result.
     sym,direction=sorted(candidate)[0]
     pending={"sym":sym,"dir":direction,"decision":t,
              "ready":t+RULE["entry_delay_ms"],
              "deadline":t+RULE["entry_deadline_ms"]}
     stats["scheduled"]+=1;event_decisions+=1
    else:stats["busy_single_account"]+=len(candidate)
 need(nrows["EURUSD"]<=SOURCES["EURUSD"]["bid"]+SOURCES["EURUSD"]["ask"] and
      nrows["GBPUSD"]<=SOURCES["GBPUSD"]["bid"]+SOURCES["GBPUSD"]["ask"],"SOURCE_BUDGET")
 if not risk_fault:
  need(all(nrows[s]==SOURCES[s]["bid"]+SOURCES[s]["ask"] for s in RULE["symbols"]),
       "ALL_SOURCE_EVENTS_CONSUMED")
 if position and not risk_fault:
  risk_fault="UNSETTLED_FINAL_SOURCE_POSITION"
  stats["unresolved_positions"]+=1
 # An unfilled pending decision can expire with the original source; it is
 # not a broker order and is explicitly accounted for, never a phantom fill.
 if pending:stats["unfilled_pending"]+=1
 need(stats["settled"]+stats["unresolved_positions"]==stats["funded_model_entries"],
      "EACH_MODELED_EXPOSURE_RECONCILED")
 if risk_fault:stats["halted_incomplete_account"]+=1
 ready_weeks=sum(v["entries"]>=21 for v in weekly.values())
 report={
  "schema":"mxm.be.lock-release-native-bidask-dependent-economic-v1",
  "hypothesis":RULE,"source_runs":{s:SOURCES[s]["run"] for s in RULE["symbols"]},
  "source_event_counts_before_fault":dict(nrows),
  "stats":dict(stats),"weeks_utc":{k:dict(v) for k,v in sorted(weekly.items())},
  "daily_utc":{k:dict(v) for k,v in sorted(days.items())},
  "gross_model_eur_scenario":str(gross),"conditional_model_costs_eur":str(cost),
  "net_model_eur_scenario":str(net),"current_continuous_equity_eur_scenario":str(cash),
  "maximum_closed_cash_drawdown_eur_scenario":str(maxdd),
  "unresolved_exposure_fault":risk_fault,"full_one_account_valid":risk_fault is None,
  "hard21_model_weeks":ready_weeks,"hard21_broker_confirmed":False,
  "all_original_source_events_processed":risk_fault is None,
  "private_individual_episodes_digest":hashes.hexdigest(),
  "individual_episode_count":len(private_ledger),
  "broker_orders":0,"cloud_activations":0,
  "historical_native_arrival_order_proven":False,
  "historical_fee_margin_slippage_qualified":False,
  "real_historical_net_alpha_proven":False,
  "independent_confirmation":False,
  "verdict":"CENSORED_ACCOUNT_FAIL_CLOSED" if risk_fault else
   "INSUFFICIENT_COMPLETE_EPISODES" if stats["settled"]<20 else
   "NEGATIVE_CONDITIONAL_NET" if net<=0 else
   "DEPENDENT_DEVELOPMENT_UNCONFIRMED"
 }
 return report,private_ledger
def selftest():
 need(ready({"EURUSD":{"bid":(110000,123),"ask":(110003,123)}},"EURUSD",124)==(110000,110003),
      "OBSERVED_QUOTE")
 need(ready({"EURUSD":{"bid":(110000,123),"ask":(110000,123)}},"EURUSD",124) is None,
      "NO_ZERO_SPREAD_EXECUTION")
 need(ready({"EURUSD":{"bid":(110000,123),"ask":(110003,123)}},"EURUSD",5125) is None,
      "NO_STALE_EXECUTION")
 need(ready({"EURUSD":{"bid":(110000,123),"ask":(110003,123)}},"EURUSD",123,strict=True) is None,
      "STRICT_PRIOR_EURUSD_FX")
 g,n,c,_=verdict_net((110000,110003),(110014,110017),1,(110000,110003))
 need(g>0 and n<g and c<0,"EFFECTIVE_BIDASK_PLUS_FEES")
 g2,n2,c2,_=verdict_net((110000,110003),(110014,110017),-1,(110000,110003))
 need(g2<0 and n2<g2 and c2<0,"ADVERSE_SHORT_SIDE")
 need(RULE["eur200_start"]==200 and RULE["minimum_base_units"]==1000
      and RULE["stop_distance_raw"]==120 and RULE["max_single_stop_risk_eur"]==2
      and RULE["no_retune"],"FROZEN_ACCOUNT")
 print("MXM_FROZEN_NATIVE_LOCK_RELEASE_BLIND_SELFTEST_SUCCESS")
def main():
 p=argparse.ArgumentParser()
 p.add_argument("mode",choices=["selftest","original"])
 p.add_argument("--eur",type=Path);p.add_argument("--gbp",type=Path);p.add_argument("--out",type=Path);p.add_argument("--private",type=Path)
 a=p.parse_args();selftest()
 if a.mode=="original":
  need(a.eur and a.gbp and a.out and a.private,"PRIVATE_ORIGINAL_INPUTS")
  out,individual=analyze(a.eur,a.gbp)
  from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
  from research_core_v4.laboratory.common import encoded
  public=Path(__file__).resolve().parents[2]/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
  need(public_spki_sha256(public)=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11',
       'EXISTING_R3_PUBLIC_RECIPIENT')
  a.private.parent.mkdir(parents=True,exist_ok=True)
  need(not a.private.exists(),"NO_PRIVATE_RESULT_OVERWRITE")
  confidential=encoded({"model":RULE["id"],"episodes":individual})
  out["private_individual_plaintext_sha256"]=hashlib.sha256(confidential).hexdigest()
  encrypt_shard(gzip.compress(confidential,mtime=0),public_key=public,output=a.private)
  out["private_r3_ciphertext_sha256"]=digest(a.private)
  a.out.parent.mkdir(parents=True,exist_ok=True)
  need(not a.out.exists(),"NO_OVERWRITE")
  a.out.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
  # Public aggregate only. No raw quote or individual entry endpoints logged.
  print("MXM_BE_LOCK_RELEASE_PUBLIC_RESULT "+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
