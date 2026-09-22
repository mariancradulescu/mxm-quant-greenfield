"""Shared EUR200 competition replay. No alpha logic or economic outcome is opened here."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Mapping

D=Decimal
STARTING_EQUITY_EUR=D("200")
FEASIBLE="EUR200_MIN_VOLUME_FEASIBLE"
INFEASIBLE="EUR200_MIN_VOLUME_INFEASIBLE"
UNRESOLVED="BROKER_OR_MARGIN_UNRESOLVED"
ACCOUNT_TYPES={"HEDGED","NETTED"}
MARGIN_TYPES={"MAX","SUM","NET"}

class ReplayContractError(ValueError):
    pass

def _d(v):
    x=v if isinstance(v,Decimal) else D(str(v))
    if not x.is_finite(): raise ReplayContractError("non-finite money")
    return x

def _t(s):
    x=datetime.fromisoformat(s[:-1]+"+00:00" if s.endswith("Z") else s)
    if x.tzinfo is None: raise ReplayContractError("timezone required")
    return x.astimezone(timezone.utc)

@dataclass(frozen=True)
class ReplayEvent:
    timestamp_utc:str; kind:str; candidate_id:str; symbol:str; position_id:str
    priority:int=100; direction:str|None=None
    direction_feasibility:str|None=None
    volume_cents:int|None=None; min_volume_cents:int|None=None
    step_volume_cents:int|None=None; max_volume_cents:int|None=None
    margin_eur:object=D("0"); transaction_cost_eur:object=D("0")
    realized_gross_pnl_eur:object=D("0")
    active_position_mtm_eur:Mapping[str,object]=field(default_factory=dict)
    causal_state:bool=True

@dataclass(frozen=True)
class OpenPosition:
    position_id:str; candidate_id:str; symbol:str; direction:str
    volume_cents:int; margin_eur:Decimal; opened_utc:str

@dataclass(frozen=True)
class ReplayDecision:
    timestamp_utc:str; kind:str; candidate_id:str; symbol:str; position_id:str
    accepted:bool; reason:str; cash_eur_after:Decimal; used_margin_eur_after:Decimal
    equity_eur_after:Decimal; free_margin_eur_after:Decimal

@dataclass(frozen=True)
class ReplayResult:
    starting_equity_eur:Decimal; terminal_equity_eur:Decimal; terminal_cash_eur:Decimal
    accepted_entries:int; rejected_entries:int
    decisions:tuple[ReplayDecision,...]; entries_by_iso_week:Mapping[str,int]

def _volume(e):
    if any(v is None for v in (e.volume_cents,e.min_volume_cents,e.step_volume_cents,e.max_volume_cents)):
        raise ReplayContractError("volume lattice unresolved")
    v,lo,step,hi=map(int,(e.volume_cents,e.min_volume_cents,e.step_volume_cents,e.max_volume_cents))
    if lo<=0 or step<=0 or hi<lo or v<lo or v>hi or (v-lo)%step:
        raise ReplayContractError("non-executable volume")

def _used_margin(pos,margin_type):
    if margin_type not in MARGIN_TYPES: raise ReplayContractError("unsupported total margin calculation type")
    by_symbol={}
    for p in pos.values():
        side=by_symbol.setdefault(p.symbol,{"LONG":D("0"),"SHORT":D("0")})
        side[p.direction]+=p.margin_eur
    total=D("0")
    for side in by_symbol.values():
        if margin_type=="SUM": total+=side["LONG"]+side["SHORT"]
        elif margin_type=="MAX": total+=max(side["LONG"],side["SHORT"])
        else: total+=abs(side["LONG"]-side["SHORT"])
    return total

def _state(cash,pos,mtm,timestamp_utc,margin_type):
    now=_t(timestamp_utc)
    values=[]
    for k,p in sorted(pos.items()):
        opened=_t(p.opened_utc)
        if k in mtm:
            value=_d(mtm[k])
            if opened==now and value!=0:
                raise ReplayContractError("same-timestamp position MTM must be zero")
        elif opened==now:
            value=D("0")
        else:
            raise ReplayContractError("missing causal MTM for active position")
        values.append(value)
    eq=cash+sum(values,D("0"))
    used=_used_margin(pos,margin_type)
    return eq,used,eq-used

def _stop_out_breached(eq,used,threshold_pct):
    if threshold_pct is None or used<=0:return False
    t=_d(threshold_pct)
    if t<0: raise ReplayContractError("invalid stop-out threshold")
    return (eq/used)*D("100")<=t

def replay_shared_eur200(events:Iterable[ReplayEvent],starting_equity_eur=STARTING_EQUITY_EUR,*,
                         account_type:str,total_margin_calculation_type:str,
                         stop_out_margin_level_pct=None)->ReplayResult:
    cash=_d(starting_equity_eur)
    account_type=str(account_type).upper()
    margin_type=str(total_margin_calculation_type).upper()
    if cash<=0 or account_type not in ACCOUNT_TYPES or margin_type not in MARGIN_TYPES:
        raise ReplayContractError("invalid account execution contract")
    seq=list(enumerate(events))
    for _,e in seq:
        if e.kind not in {"EXIT","ENTRY"} or not e.causal_state: raise ReplayContractError("invalid/non-causal event")
        _t(e.timestamp_utc)
    seq.sort(key=lambda p:(_t(p[1].timestamp_utc),0 if p[1].kind=="EXIT" else 1,p[1].priority,p[0]))
    pos={}; decisions=[]; weeks={}; accepted=rejected=0
    for _,e in seq:
        cost=_d(e.transaction_cost_eur)
        if cost<0: raise ReplayContractError("negative cost")
        if e.kind=="EXIT":
            p=pos.get(e.position_id)
            if p is None or p.symbol!=e.symbol or p.candidate_id!=e.candidate_id:
                raise ReplayContractError("exit identity mismatch")
            cash+=_d(e.realized_gross_pnl_eur)-cost
            del pos[e.position_id]
            eq,used,free=_state(cash,pos,e.active_position_mtm_eur,e.timestamp_utc,margin_type)
            decisions.append(ReplayDecision(e.timestamp_utc,e.kind,e.candidate_id,e.symbol,e.position_id,True,"EXIT_APPLIED",cash,used,eq,free))
            continue
        _volume(e)
        if e.direction not in {"LONG","SHORT"}: raise ReplayContractError("entry direction must be LONG or SHORT")
        if e.direction_feasibility not in {FEASIBLE,INFEASIBLE,UNRESOLVED}:
            raise ReplayContractError("direction feasibility missing or invalid")
        if e.position_id in pos: raise ReplayContractError("duplicate position")
        if account_type=="NETTED" and any(p.symbol==e.symbol for p in pos.values()):
            raise ReplayContractError("NETTED account requires pre-netted same-symbol order stream")
        margin=_d(e.margin_eur)
        if margin<=0: raise ReplayContractError("margin must be positive")
        eq,used,free=_state(cash,pos,e.active_position_mtm_eur,e.timestamp_utc,margin_type)
        if e.direction_feasibility==UNRESOLVED:
            rejected+=1
            decisions.append(ReplayDecision(e.timestamp_utc,e.kind,e.candidate_id,e.symbol,e.position_id,False,"REJECT_DIRECTION_FEASIBILITY_UNRESOLVED",cash,used,eq,free))
            continue
        if e.direction_feasibility==INFEASIBLE:
            rejected+=1
            decisions.append(ReplayDecision(e.timestamp_utc,e.kind,e.candidate_id,e.symbol,e.position_id,False,"REJECT_DIRECTION_INFEASIBLE",cash,used,eq,free))
            continue
        trial=dict(pos)
        trial[e.position_id]=OpenPosition(e.position_id,e.candidate_id,e.symbol,str(e.direction),int(e.volume_cents),margin,e.timestamp_utc)
        trial_mtm=dict(e.active_position_mtm_eur); trial_mtm[e.position_id]=D("0")
        trial_cash=cash-cost
        trial_eq,trial_used,trial_free=_state(trial_cash,trial,trial_mtm,e.timestamp_utc,margin_type)
        reason="ACCEPTED"
        if trial_free<0: reason="REJECT_INSUFFICIENT_FREE_MARGIN"
        elif _stop_out_breached(trial_eq,trial_used,stop_out_margin_level_pct): reason="REJECT_STOP_OUT_MARGIN_LEVEL"
        if reason!="ACCEPTED":
            rejected+=1
            decisions.append(ReplayDecision(e.timestamp_utc,e.kind,e.candidate_id,e.symbol,e.position_id,False,reason,cash,used,eq,free))
            continue
        cash=trial_cash; pos=trial
        accepted+=1
        iso=_t(e.timestamp_utc).isocalendar(); key=f"{iso.year}-W{iso.week:02d}"; weeks[key]=weeks.get(key,0)+1
        decisions.append(ReplayDecision(e.timestamp_utc,e.kind,e.candidate_id,e.symbol,e.position_id,True,reason,cash,trial_used,trial_eq,trial_free))
    if pos: raise ReplayContractError("terminal open positions")
    return ReplayResult(_d(starting_equity_eur),cash,cash,accepted,rejected,tuple(decisions),dict(sorted(weeks.items())))
