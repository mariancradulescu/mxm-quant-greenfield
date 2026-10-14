"""Causal marked waiting-time law; raw quote-price integers, no outcomes or I/O."""
import math
from collections import Counter

def sign(x): return (x>0)-(x<0)

def durations(path):
    if len(path)!=45: return {'state':'PATH_LENGTH'}
    first=path[0][1]; previous=first; last=None; up=[]; down=[]
    for t,p in path[1:]:
        if p!=previous:
            # The first interval is left censored. No invented event at window start.
            if last is not None: (up if p>previous else down).append(t-last)
            last=t
        previous=p
    if len(up)<2 or len(down)<2:
        return {'state':'INSUFFICIENT_TWO_SIDED_DURATIONS','up_n':len(up),'down_n':len(down)}
    u=sum(up)/len(up);d=sum(down)/len(down)
    value=math.log(d/u)
    if abs(d-u)<=64*math.ulp(max(1.,u,d)): value=0.
    return {'state':'SUPPORTED','score':value,'model_side':sign(value),
            'count_side':sign(len(up)-len(down)),'momentum_side':sign(previous-first),
            'up_n':len(up),'down_n':len(down),'up_mean_ms':u,'down_mean_ms':d}

def side(rows,lo,hi):
    found={}
    for t,p in rows:
        if lo<=t<=hi:
            if p<=0: return None,'INVALID_PRICE'
            if t in found and found[t]!=p: return None,'AMBIGUOUS_SIDE_MS'
            found[t]=p
    changed=[];last=None;ct=-1
    for t,p in sorted(found.items()):
        if last is not None and p!=last: ct=t
        changed.append((t,p,ct));last=p
    return changed,None

def feature(bids,asks,t,has_more=False):
    if has_more: return {'state':'INCOMPLETE_PAGE'}
    lo=(t-60)*1000;hi=(t-1)*1000
    b,reason=side(bids,lo,hi)
    if reason:return {'state':reason}
    a,reason=side(asks,lo,hi)
    if reason:return {'state':reason}
    if not b or not a:return {'state':'MISSING_SIDE'}
    ib=ia=-1;path=[]
    for sec in range(t-45,t):
        now=sec*1000
        while ib+1<len(b) and b[ib+1][0]<=now:ib+=1
        while ia+1<len(a) and a[ia+1][0]<=now:ia+=1
        if ib<0 or ia<0:return {'state':'MISSING_PATH_STATE'}
        tb,bp,bc=b[ib];ta,ap,ac=a[ia]
        if bc<0 or ac<0:return {'state':'CHANGED_SIDE_WARMUP'}
        if now-bc>5000 or now-ac>5000 or abs(bc-ac)>2000:return {'state':'STALE_OR_SKEWED_CHANGED_SIDE'}
        if bp>ap:return {'state':'CROSSED_PATH'}
        path.append((now,bp+ap))
    result=durations(path);result['last_feature_ms']=hi;return result

def admit(entry,cash=200.):
    return bool(entry.get('eligible') and entry['margin_eur']<=min(80.,.4*cash)
                and cash-entry['margin_eur']>=max(120.,.6*cash)
                and entry['risk_eur']<=min(2.,.01*cash))

def ledger(records,account):
    cash=peak=200.;dd=0.;selected=[];closed=[];halt=None;opened=None
    def settle(ev):
        nonlocal cash,peak,dd,halt
        value=account(ev,ev['feature']['model_side'])
        if value is None:halt='FIRST_SELECTED_UNKNOWN_EXIT_OR_FX';return False
        cash+=value['net_eur'];peak=max(peak,cash);dd=max(dd,peak-cash)
        closed.append({'sid':ev['sid'],'t':ev['t'],'exit':ev['t']+900,'net_eur':value['net_eur'],'risk_eur':ev['entry']['risk_eur']})
        if -value['net_eur']>ev['entry']['risk_eur']:halt='REALIZED_REFERENCE_LOSS_EXCEEDS_PLANNED_RISK';return False
        return True
    groups={}
    for ev in records:groups.setdefault(ev['t'],[]).append(ev)
    for t,group in sorted(groups.items()):
        if opened and opened['t']+900<=t:
            if not settle(opened):break
            opened=None
        if opened:continue
        eligible=[e for e in group if e['feature'].get('state')=='SUPPORTED' and e['feature']['model_side'] and admit(e['entry'],cash)]
        eligible.sort(key=lambda e:(e['entry']['cost_eur'],e['sid']))
        if eligible:opened=eligible[0];selected.append({'sid':opened['sid'],'t':t})
    if opened and not halt:settle(opened)
    return {'initial_eur':200.,'cash_known_closes_eur':cash,'known_NET_eur':cash-200.,'complete_NET_eur':None if halt else cash-200.,'closed_drawdown_eur':dd,'selected':selected,'closed':closed,'halt':halt,'max_simultaneous':1,'actual_orders':0,'actual_fills':0,'HARD21':False}
