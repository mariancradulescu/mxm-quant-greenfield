"""Shared EUR200 competition replay. No alpha logic or economic outcome is opened here."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Mapping

D=Decimal
STARTING_EQUITY_EUR=D("200")

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

def _state(cash,pos,mtm):
    if set(pos)!=set(mtm): raise ReplayContractError("causal MTM key mismatch")
    eq=cash+sum((_d(mtm[k]) for k in sorted(mtm)),D("0"))
    used=sum((p.margin_eur for p in pos.values()),D("0"))
    return eq,used,eq-used

def replay_shared_eur200(events:Iterable[ReplayEvent],starting_equity_eur=STARTING_EQUITY_EUR,
                         max_active_positions_per_symbol:int=1)->ReplayResult:
    cash=_d(starting_equity_eur)
    if cash<=0 or max_active_positions_per_symbol<1: raise ReplayContractError("invalid account contract")
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
            eq,used,free=_state(cash,pos,e.active_position_mtm_eur)
            decisions.append(ReplayDecision(e.timestamp_utc,e.kind,e.candidate_id,e.symbol,e.position_id,True,"EXIT_APPLIED",cash,used,eq,free))
            continue
        _volume(e)
        if e.position_id in pos: raise ReplayContractError("duplicate position")
        margin=_d(e.margin_eur)
        if margin<=0: raise ReplayContractError("margin must be positive")
        eq,used,free=_state(cash,pos,e.active_position_mtm_eur)
        same=sum(p.symbol==e.symbol for p in pos.values())
        reason="ACCEPTED"
        if same>=max_active_positions_per_symbol: reason="REJECT_SAME_SYMBOL_CONCURRENCY"
        elif free-cost<margin: reason="REJECT_INSUFFICIENT_FREE_MARGIN"
        if reason!="ACCEPTED":
            rejected+=1
            decisions.append(ReplayDecision(e.timestamp_utc,e.kind,e.candidate_id,e.symbol,e.position_id,False,reason,cash,used,eq,free))
            continue
        cash-=cost
        pos[e.position_id]=OpenPosition(e.position_id,e.candidate_id,e.symbol,str(e.direction or "UNKNOWN"),int(e.volume_cents),margin,e.timestamp_utc)
        accepted+=1
        iso=_t(e.timestamp_utc).isocalendar(); key=f"{iso.year}-W{iso.week:02d}"; weeks[key]=weeks.get(key,0)+1
        mtm=dict(e.active_position_mtm_eur); mtm[e.position_id]=D("0")
        eq,used,free=_state(cash,pos,mtm)
        decisions.append(ReplayDecision(e.timestamp_utc,e.kind,e.candidate_id,e.symbol,e.position_id,True,reason,cash,used,eq,free))
    if pos: raise ReplayContractError("terminal open positions")
    return ReplayResult(_d(starting_equity_eur),cash,cash,accepted,rejected,tuple(decisions),dict(sorted(weeks.items())))
