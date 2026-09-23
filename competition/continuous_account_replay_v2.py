"""Deterministic continuous-account research replay; no alpha selection or live orders."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from itertools import groupby
from typing import Iterable, Mapping

D=Decimal
FEASIBLE="EUR200_MIN_VOLUME_FEASIBLE"; INFEASIBLE="EUR200_MIN_VOLUME_INFEASIBLE"; UNRESOLVED="BROKER_OR_MARGIN_UNRESOLVED"
ACCOUNT_TYPES={"HEDGED","NETTED"}; MARGIN_TYPES={"MAX","SUM","NET"}

class ReplayContractError(ValueError): pass

def _d(x):
    y=x if isinstance(x,D) else D(str(x))
    if not y.is_finite(): raise ReplayContractError("non-finite value")
    return y

def _t(s):
    x=datetime.fromisoformat(s[:-1]+"+00:00" if s.endswith("Z") else s)
    if x.tzinfo is None: raise ReplayContractError("timezone required")
    return x.astimezone(timezone.utc)

@dataclass(frozen=True)
class CapitalEvent:
    timestamp_utc:str; kind:str; candidate_id:str=""; symbol:str=""; position_id:str=""; priority:int=100
    direction:str|None=None; direction_feasibility:str|None=None
    volume_cents:int|None=None; min_volume_cents:int|None=None; step_volume_cents:int|None=None; max_volume_cents:int|None=None
    margin_eur:object=D("0"); price:object|None=None; base_units:object|None=None; quote_to_eur_rate:object|None=None
    transaction_cost_eur:object=D("0"); financing_eur:object=D("0"); cashflow_eur:object=D("0")
    causal_state:bool=True; metadata:Mapping[str,object]=field(default_factory=dict)

@dataclass
class _Position:
    candidate_id:str; symbol:str; direction:str; margin:Decimal; entry:Decimal; units:Decimal; mark:Decimal; rate:Decimal

@dataclass(frozen=True)
class Snapshot:
    timestamp_utc:str; broker_cash_eur:Decimal; broker_equity_eur:Decimal; strategy_nav_eur:Decimal
    used_margin_eur:Decimal; free_margin_eur:Decimal; external_cashflow_net_eur:Decimal
    open_positions:int; margin_level_ratio:Decimal|None

@dataclass(frozen=True)
class Decision:
    timestamp_utc:str; kind:str; position_id:str; accepted:bool; reason:str; snapshot:Snapshot

@dataclass(frozen=True)
class ReplayResult:
    status:str; halt_reason:str|None; starting_equity_eur:Decimal; terminal_broker_equity_eur:Decimal; terminal_strategy_nav_eur:Decimal
    external_cashflow_net_eur:Decimal; accepted_entries:int; rejected_entries:int; financing_eur:Decimal; transaction_costs_eur:Decimal
    turnover_eur:Decimal; maximum_drawdown_eur:Decimal; minimum_free_margin_eur:Decimal; minimum_margin_level_ratio:Decimal|None
    average_used_margin_eur:Decimal; average_broker_equity_eur:Decimal; capital_occupancy_ratio:Decimal
    weekly_final_equity_eur:Mapping[str,Decimal]; monthly_final_equity_eur:Mapping[str,Decimal]; entries_by_iso_week:Mapping[str,int]
    decisions:tuple[Decision,...]

def _volume(e):
    vals=(e.volume_cents,e.min_volume_cents,e.step_volume_cents,e.max_volume_cents)
    if any(v is None for v in vals): raise ReplayContractError("volume lattice unresolved")
    v,lo,step,hi=map(int,vals)
    if lo<=0 or step<=0 or hi<lo or v<lo or v>hi or (v-lo)%step: raise ReplayContractError("non-executable volume")

def _used(pos,kind):
    by={}
    for p in pos.values(): by.setdefault(p.symbol,{"LONG":D(0),"SHORT":D(0)})[p.direction]+=p.margin
    total=D(0)
    for s in by.values(): total += s["LONG"]+s["SHORT"] if kind=="SUM" else max(s.values()) if kind=="MAX" else abs(s["LONG"]-s["SHORT"])
    return total

def _snap(ts,cash,pos,margin_type,external):
    unreal=D(0)
    for p in pos.values(): unreal += (D(1) if p.direction=="LONG" else D(-1))*(p.mark-p.entry)*p.units*p.rate
    eq=cash+unreal; used=_used(pos,margin_type); free=eq-used
    return Snapshot(ts,cash,eq,eq-external,used,free,external,len(pos),None if used<=0 else eq/used)

def _keys(ts):
    d=_t(ts); i=d.isocalendar(); return f"{i.year}-W{i.week:02d}",f"{d.year:04d}-{d.month:02d}"

def replay_continuous_account(events:Iterable[CapitalEvent],*,starting_equity_eur:object,account_type:str,total_margin_calculation_type:str,
                              same_symbol_overlap_allowed:bool=True,entry_margin_level_floor_ratio:object|None=None,
                              unresolved_stop_out_guard_ratio:object|None=None)->ReplayResult:
    cash=_d(starting_equity_eur); account_type=account_type.upper(); margin_type=total_margin_calculation_type.upper()
    if cash<=0 or account_type not in ACCOUNT_TYPES or margin_type not in MARGIN_TYPES: raise ReplayContractError("invalid account contract")
    floor=None if entry_margin_level_floor_ratio is None else _d(entry_margin_level_floor_ratio)
    guard=None if unresolved_stop_out_guard_ratio is None else _d(unresolved_stop_out_guard_ratio)
    if (floor is not None and floor<=0) or (guard is not None and guard<=0): raise ReplayContractError("margin guard must be positive")
    order={"EXIT":0,"FINANCING":1,"DEPOSIT":2,"WITHDRAWAL":2,"MARK":3,"ENTRY":4}
    seq=list(events)
    for e in seq:
        if e.kind not in order or not e.causal_state: raise ReplayContractError("invalid/non-causal event")
        _t(e.timestamp_utc)
    seq.sort(key=lambda e:(_t(e.timestamp_utc),order[e.kind],e.priority,e.symbol,e.position_id))
    pos={}; inactive=set(); decisions=[]; external=D(0); financing=D(0); costs=D(0); turnover=D(0); accepted=rejected=0
    weekly={}; monthly={}; entries_week={}; peak=cash; maxdd=D(0); minfree=cash; minratio=None
    prev_ts=None; prev_snap=_snap(seq[0].timestamp_utc if seq else "1970-01-01T00:00:00Z",cash,pos,margin_type,external)
    used_time=eq_time=seconds_total=D(0); status="COMPLETE"; halt=None
    def record(e,ok,reason):
        nonlocal peak,maxdd,minfree,minratio,prev_snap
        s=_snap(e.timestamp_utc,cash,pos,margin_type,external); decisions.append(Decision(e.timestamp_utc,e.kind,e.position_id,ok,reason,s))
        peak=max(peak,s.strategy_nav_eur); maxdd=max(maxdd,peak-s.strategy_nav_eur); minfree=min(minfree,s.free_margin_eur)
        if s.margin_level_ratio is not None: minratio=s.margin_level_ratio if minratio is None else min(minratio,s.margin_level_ratio)
        prev_snap=s; return s
    def guard_snapshot(s):
        if s.broker_equity_eur<=0: return "HALT_RUIN","BROKER_EQUITY_NON_POSITIVE"
        if s.free_margin_eur<0: return "HALT_FREE_MARGIN","FREE_MARGIN_NEGATIVE"
        if guard is not None and s.margin_level_ratio is not None and s.margin_level_ratio<=guard: return "HALT_UNRESOLVED_BROKER_STOP_OUT","PATH_ENTERED_STOP_OUT_DEPENDENCY_GUARD"
        return None,None
    for ts,grp in groupby(seq,key=lambda e:e.timestamp_utc):
        batch=list(grp); now=_t(ts)
        if prev_ts is not None:
            sec=D(str((now-prev_ts).total_seconds()))
            if sec<0: raise ReplayContractError("chronology regression")
            used_time+=prev_snap.used_margin_eur*sec; eq_time+=prev_snap.broker_equity_eur*sec; seconds_total+=sec
        prev_ts=now
        non_entries=[]; marks=[]; entries=[]
        for e in batch: (entries if e.kind=="ENTRY" else marks if e.kind=="MARK" else non_entries).append(e)
        for e in non_entries:
            cost=_d(e.transaction_cost_eur)
            if cost<0: raise ReplayContractError("negative cost")
            if e.kind=="EXIT":
                if e.position_id in inactive: record(e,False,"SKIP_EXIT_REJECTED_ENTRY"); continue
                p=pos.get(e.position_id)
                if p is None or p.symbol!=e.symbol or p.candidate_id!=e.candidate_id: raise ReplayContractError("exit identity mismatch")
                price=_d(e.price); rate=_d(e.quote_to_eur_rate)
                gross=(D(1) if p.direction=="LONG" else D(-1))*(price-p.entry)*p.units*rate
                cash+=gross-cost; costs+=cost; turnover+=abs(price*p.units*rate); del pos[e.position_id]; record(e,True,"EXIT_APPLIED")
            elif e.kind=="FINANCING":
                amt=_d(e.financing_eur); cash+=amt; financing+=amt; record(e,True,"FINANCING_APPLIED")
            else:
                amt=_d(e.cashflow_eur)
                if amt<=0: raise ReplayContractError("external cashflow must be positive")
                if e.kind=="DEPOSIT": cash+=amt; external+=amt; reason="DEPOSIT_EXTERNAL_CASHFLOW"
                else: cash-=amt; external-=amt; reason="WITHDRAWAL_EXTERNAL_CASHFLOW"
                record(e,True,reason)
        for e in marks:
            if e.position_id in inactive: continue
            p=pos.get(e.position_id)
            if p is None: raise ReplayContractError("mark references unknown position")
            p.mark=_d(e.price); p.rate=_d(e.quote_to_eur_rate)
            if p.mark<=0 or p.rate<=0: raise ReplayContractError("invalid mark")
        for e in marks: record(e,e.position_id not in inactive,"MARK_APPLIED" if e.position_id not in inactive else "SKIP_MARK_REJECTED_ENTRY")
        snap=_snap(ts,cash,pos,margin_type,external); st,why=guard_snapshot(snap)
        if st: status,halt=st,why; break
        for e in entries:
            _volume(e); cost=_d(e.transaction_cost_eur)
            if cost<0 or e.direction not in {"LONG","SHORT"} or e.direction_feasibility not in {FEASIBLE,INFEASIBLE,UNRESOLVED}: raise ReplayContractError("invalid entry")
            if e.position_id in pos or e.position_id in inactive: raise ReplayContractError("duplicate position id")
            if account_type=="NETTED" and any(p.symbol==e.symbol for p in pos.values()): raise ReplayContractError("NETTED stream not pre-netted")
            reason=None
            if not same_symbol_overlap_allowed and any(p.symbol==e.symbol for p in pos.values()): reason="REJECT_SAME_SYMBOL_OVERLAP"
            elif e.direction_feasibility==UNRESOLVED: reason="REJECT_DIRECTION_FEASIBILITY_UNRESOLVED"
            elif e.direction_feasibility==INFEASIBLE: reason="REJECT_DIRECTION_INFEASIBLE"
            if reason:
                rejected+=1; inactive.add(e.position_id); record(e,False,reason); continue
            price=_d(e.price); units=_d(e.base_units); rate=_d(e.quote_to_eur_rate); margin=_d(e.margin_eur)
            if min(price,units,rate,margin)<=0: raise ReplayContractError("invalid entry primitives")
            trial=dict(pos); trial[e.position_id]=_Position(e.candidate_id,e.symbol,e.direction,margin,price,units,price,rate)
            trial_cash=cash-cost; trial_s=_snap(ts,trial_cash,trial,margin_type,external); reason="ACCEPTED"
            if trial_s.free_margin_eur<0: reason="REJECT_INSUFFICIENT_FREE_MARGIN"
            elif floor is not None and trial_s.margin_level_ratio is not None and trial_s.margin_level_ratio<=floor: reason="REJECT_CAPITAL_PRESERVATION_MARGIN_LEVEL"
            if reason!="ACCEPTED":
                rejected+=1; inactive.add(e.position_id); record(e,False,reason); continue
            pos=trial; cash=trial_cash; costs+=cost; turnover+=abs(price*units*rate); accepted+=1
            wk,_=_keys(ts); entries_week[wk]=entries_week.get(wk,0)+1; s=record(e,True,reason)
            st,why=guard_snapshot(s)
            if st: status,halt=st,why; break
        if status!="COMPLETE": break
        final_batch=_snap(ts,cash,pos,margin_type,external); wk,mo=_keys(ts); weekly[wk]=final_batch.broker_equity_eur; monthly[mo]=final_batch.broker_equity_eur; prev_snap=final_batch
    if status=="COMPLETE" and pos: raise ReplayContractError("terminal open positions")
    final=_snap(decisions[-1].timestamp_utc if decisions else "1970-01-01T00:00:00Z",cash,pos,margin_type,external)
    avg_used=D(0) if seconds_total<=0 else used_time/seconds_total; avg_eq=final.broker_equity_eur if seconds_total<=0 else eq_time/seconds_total
    return ReplayResult(status,halt,_d(starting_equity_eur),final.broker_equity_eur,final.strategy_nav_eur,external,accepted,rejected,financing,costs,turnover,
                        maxdd,minfree,minratio,avg_used,avg_eq,D(0) if avg_eq<=0 else avg_used/avg_eq,
                        dict(sorted(weekly.items())),dict(sorted(monthly.items())),dict(sorted(entries_week.items())),tuple(decisions))
