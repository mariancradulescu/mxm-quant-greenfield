"""Prospective pure maps; zero observed bars, responses or external IO."""
from fractions import Fraction as F
from decimal import Decimal, localcontext
from research_core_v4.compact_baseline_v2 import baseline
FIELDS=('open','high','low','close')
def interval(t,bars,start,end):
    wanted=set(range(start,end,300));chosen={}
    for b in bars:
        ts=b.get('timestamp')
        if ts not in wanted:continue
        if ts in chosen:return None
        chosen[ts]=b
    if set(chosen)!=wanted:return None
    for ts,b in chosen.items():
        if type(ts) is not int or ts%300:return None
        a=b.get('available_at')
        if type(a) is not int or not ts+300<=a<=t:return None
        try:
            o,h,l,c=[F(b[k]) for k in FIELDS]
            if not l<=min(o,c)<=max(o,c)<=h:return None
        except (KeyError,ValueError,TypeError,OverflowError,ZeroDivisionError):return None
        if type(b.get('tick_volume')) is not int or b['tick_volume']<0:return None
    return [chosen[k] for k in sorted(chosen)]
def loc(b):
    width=F(b['high'])-F(b['low'])
    return (F(b['close'])-F(b['low']))/width if width else F(1,2)
def aggloc(b):
    return loc({'high':max(x['high'] for x in b),'low':min(x['low'] for x in b),'close':b[-1]['close']})
def sign(x):return int(x>0)-int(x<0)
def feature(source,t,bars):
    if type(t) is not int or t%300:raise ValueError('M5_DECISION_GRID')
    h=(t//3600)*3600;a=interval(t,bars,h-3600,h)
    if a is None:return None
    if source=='MULTISCALE_PRICE_STATE':
        q=interval(t,bars,h-4500,h-3600)
        return None if q is None else sign(aggloc(q)-F(1,2))*sign(aggloc(a)-F(1,2))
    if source=='BROKER_NATIVE_ACTIVITY_STATE':
        total=sum(b['tick_volume'] for b in a)
        return tuple(F(b['tick_volume'],total) if total else F(0) for b in a[:11])
    if source=='REGIME_AND_STRUCTURAL_BREAK_STATE':
        prev=interval(t,bars,h-7200,h-3600)
        return None if prev is None else sum(abs(x-y) for x,y in zip(sorted(map(loc,a)),sorted(map(loc,prev))))/12
    if source=='VOLATILITY_AND_REALIZED_VARIANCE_STATE':
        if any(b['open']<=0 or b['close']<=0 for b in a):return None
        # Semantic authority is the real logarithm. Decimal is synthetic QA only,
        # not a production numeric environment or an exact real-arithmetic claim.
        with localcontext() as ctx:
            ctx.prec=80
            def dec(x):
                q=F(x);return Decimal(q.numerator)/Decimal(q.denominator)
            r=[(dec(b['close'])/dec(b['open'])).ln() for b in a];q=[x*x for x in r];total=sum(q)
            return sum((x/total)**2 for x in q) if total else Decimal(0)
    raise ValueError('NO_AUTHORIZED_EXACT_MAP')
def synthetic_witness(source):
    # Explicit artificial legal domain pairs, not market observations.
    t=10800
    def bar(ts):return {'timestamp':ts,'available_at':ts+300,'open':2,'high':4,'low':1,'close':3,'tick_volume':2}
    a=[bar(ts) for ts in range(t-7200,t,300)];b=[dict(x) for x in a]
    h0=[x for x in a if x['timestamp']>=t-3600];h1=[x for x in b if x['timestamp']>=t-3600]
    if source=='MULTISCALE_PRICE_STATE':
        for x in b:
            if t-4500<=x['timestamp']<t-3600:x['close']=1
        analytic=['1','-1']
    elif source=='BROKER_NATIVE_ACTIVITY_STATE':
        h0[0]['tick_volume']=1;h0[1]['tick_volume']=3
        h1[0]['tick_volume']=3;h1[1]['tick_volume']=1
        analytic=['first weight 1/24','first weight 3/24']
    elif source=='VOLATILITY_AND_REALIZED_VARIANCE_STATE':
        for x in h0+h1:x['open']=2;x['close']=2
        h0[0]['close']=4;h1[0]['close']=4;h1[1]['close']=4
        analytic=['1','1/2: two identical nonzero log increments cancel common log(2)^2']
    elif source=='REGIME_AND_STRUCTURAL_BREAK_STATE':
        for x in b:
            if x['timestamp']<t-3600:x['close']=1
        analytic=['0','2/3']
    else:raise ValueError('SOURCE')
    ba=baseline(t,a);bb=baseline(t,b);pa=feature(source,t,a);pb=feature(source,t,b)
    assert ba is not None and ba==bb and pa is not None and pb is not None and pa!=pb
    return {'kind':'SYNTHETIC_LEGAL_DOMAIN_PAIR_NOT_MARKET_DATA','t':t,'bars_A':a,'bars_B':b,'baseline_equal':True,'analytic_features':analytic,'feature_values_qa':[str(pa),str(pb)],'proves':'Phi is not measurable with respect to the ten-coordinate compact B on the legal structural domain; no conditional predictability or profit claim'}
