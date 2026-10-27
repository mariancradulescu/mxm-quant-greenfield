"""Independent array-window oracle for one prospective depth-size mechanism."""
def reference(rows):
    bids={};times={};stamps={};first=True;last_server=-1;announcements=[];pending=None;blocked=-1
    decisions=[];episodes=[];censors=[];last=-1;sequence=-1;first_depth=None
    def healthy(t,u):return all(s in bids and bids[s]>0 and s in stamps and stamps[s]>=0 and
      0<=t-times[s]<=5000 and 0<=u-stamps[s]<=5000 for s in (1,-1)) and bids[-1]>bids[1]
    def censor(t,why):
        nonlocal pending
        censors.append(dict(decision=pending['decision'],direction=pending['direction'],entry=pending['entry'],t=t,reason=why));pending=None
    for r in rows:
        t,u=r['t'],r['utc'];kind=r['kind']
        if t<0 or t<last or r['seq']<=sequence:raise ValueError('SOURCE_ORDER')
        last=t;sequence=r['seq'];prior_good=healthy(t,u)
        if kind=='spot':
            stamp=r['server'];valid=stamp is not None and stamp>=last_server and 0<=u-stamp<=5000
            if stamp is not None:last_server=max(last_server,stamp)
            for field,side in (('bid',1),('ask',-1)):
                if r[field] is not None:bids[side]=r[field];times[side]=t;stamps[side]=stamp if valid and not first else -1
            first=False
        good=healthy(t,u)
        if pending:
            if not good or not prior_good:censor(t,'UNOBSERVED_OR_INVALID_PATH')
            elif pending['entry'] is None:
                if t>pending['decision']+1000:censor(t,'ENTRY_TIMEOUT')
                elif kind=='spot' and t>=pending['decision']+250:
                    pending['entry']=t;pending['price']=bids[-pending['direction']]
            elif t>pending['entry']+2500:censor(t,'EXIT_TIMEOUT')
            elif kind=='spot' and t>=pending['entry']+2000:
                price=bids[pending['direction']]
                episodes.append(dict(decision=pending['decision'],direction=pending['direction'],entry=pending['entry'],exit=t,
                 entry_price=pending['price'],exit_price=price,gross_raw=pending['direction']*(price-pending['price'])));pending=None
        announcements=[x for x in announcements if x[0]>=t-1000]
        if kind=='depth':
            if first_depth is None:first_depth=t;announcements=[];continue
            q=r['quotes'];valid=len(q)<=10000 and len({x['id'] for x in q})==len(q) and all(x['side'] in (-1,1) and x['price']>0 and x['size']>0 for x in q)
            if not valid:
                announcements=[]
                if pending:censor(t,'AMBIGUOUS_DEPTH_MESSAGE')
            else:
                announcements.extend((t,x['side'],x['size']) for x in q)
                if len(announcements)>100000:raise ValueError('FLOW_RESOURCE_CAP')
                if pending is None and t>=blocked and t-first_depth>=5000 and good and len(announcements)>=10:
                    b=sum(x[2] for x in announcements if x[1]==1);a=sum(x[2] for x in announcements if x[1]==-1)
                    sign=1 if a>0 and b>=3*a else -1 if b>0 and a>=3*b else 0
                    if sign:
                        pending=dict(decision=t,direction=sign,entry=None);blocked=t+5000;decisions.append(dict(t=t,direction=sign))
        elif kind!='spot':raise ValueError('SOURCE_KIND')
    if pending:censor(last,'TERMINAL_UNSETTLED')
    return dict(signals=len(decisions),episodes=episodes,censors=censors,decisions=decisions)
def verdict(r):
    complete=len(r['episodes']);total=r['signals'];censored=len(r['censors']);gross=sum(e['gross_raw'] for e in r['episodes'])
    gates=dict(at_least_100_complete=complete>=100,censor_fraction_at_most_5pct=total>0 and censored*20<=total,quoted_gross_positive=gross>0)
    result='DATA_LIMITED' if not gates['at_least_100_complete'] or not gates['censor_fraction_at_most_5pct'] else 'GROSS_NONPOSITIVE' if gross<=0 else 'CONDITIONAL_QUOTED_HEADROOM_COSTS_UNRESOLVED'
    return result,gates
