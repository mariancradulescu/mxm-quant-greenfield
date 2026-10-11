"""New fixed DEVELOPMENT exact. No fitting, ranking by returns, or old runner calls."""
import math
from collections import Counter
from datetime import datetime,timezone
START=1787184000;END=1789603200;SIDS=(1,2,250)
WEEKS=('2026-W34','2026-W35','2026-W36','2026-W37','2026-W38')
FULL=WEEKS[1:4]
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def sign(x):return (x>0)-(x<0)
def grid():return range(START+900,END,3600)
def direction(prior):
    r=[math.log(float(x['close'])/float(x['open'])) for x in prior]
    x,y=r[:-1],r[1:];mx=sum(x)/11;my=sum(y)/11
    cov=sum((a-mx)*(b-my) for a,b in zip(x,y))/11
    vx=sum((a-mx)**2 for a in x)/11;vy=sum((b-my)**2 for b in y)/11
    b=sign(r[-1]);d=sign(cov)*b if vx>0 and vy>0 else 0
    return d,b,cov
def observations(bars):
    out=[]
    for t in grid():
        z={'t':t,'exit':t+3600,'block':(t-START)//604800,'iso':iso(t),'d':0,'b':0,'reason':'FEATURE_GAP','y':None}
        pp=[bars.get(t-3900+i*300) for i in range(12)]
        if all(x is not None for x in pp):
            z['d'],z['b'],z['cov']=direction(pp)
            z.update(reason='SIGNAL' if z['d'] and z['b'] else 'FLAT_OR_DEGENERATE',range=max(float(x['high']) for x in pp)-min(float(x['low']) for x in pp))
        # Outcome availability changes evaluability only; never d, b, or entry rules.
        if z['d'] and z['b']:
            future=[bars.get(t+i*300) for i in range(12)]
            if t+3600>END:z['outcome_reason']='DOMAIN_CENSOR'
            elif not all(x is not None for x in future):z['outcome_reason']='LABEL_GAP'
            else:z['y']=10000*math.log(float(future[-1]['close'])/float(future[0]['open']));z['outcome_reason']='PAIRED'
        out.append(z)
    return out
def stats(rr):
    v=[r for r in rr if r.get('y') is not None];a=sum(r['d']*r['y'] for r in v);b=sum(r['b']*r['y'] for r in v)
    return {'calendar':len(rr),'feature_valid':sum(r['reason']!='FEATURE_GAP' for r in rr),'signals':sum(bool(r['d']) for r in rr),'paired':len(v),'model_sum_bps':a,'baseline_sum_bps':b,'increment_sum_bps':a-b,'model_mean_bps':a/len(v) if v else None,'baseline_mean_bps':b/len(v) if v else None,'increment_mean_bps':(a-b)/len(v) if v else None,'missing':dict(Counter(r.get('outcome_reason',r['reason']) for r in rr if r.get('y') is None))}
def report(rr):return {'global':stats(rr),'blocks':[stats([r for r in rr if r['block']==j]) for j in range(4)],'iso':{w:stats([r for r in rr if r['iso']==w]) for w in WEEKS}}
def merge(ss):
    keys=('calendar','feature_valid','signals','paired','model_sum_bps','baseline_sum_bps','increment_sum_bps');r={k:sum(x[k] for x in ss) for k in keys};r['missing']=dict(sum((Counter(x['missing']) for x in ss),Counter()))
    for key in ('model','baseline','increment'):r[key+'_mean_bps']=r[key+'_sum_bps']/r['paired'] if r['paired'] else None
    return r
def merge_reports(rr):return {'global':merge([x['global'] for x in rr]),'blocks':[merge([x['blocks'][j] for x in rr]) for j in range(4)],'iso':{w:merge([x['iso'][w] for x in rr]) for w in WEEKS}}
def promising(r):
    z=r['blocks']+[r['iso'][w] for w in FULL]
    return all(x['paired']>=30 and x['model_mean_bps']>0 and x['increment_mean_bps']>0 for x in z)
def point(q):
    if not q:return None
    s=q['sides']
    if any(s.get(n,{}).get('state')!='AUTHENTIC_CAUSAL_QUOTE' or s[n].get('source_has_more',True) or s[n].get('age_ms',float('inf'))>5000 for n in ('bid','ask')):return None
    if abs(s['bid']['timestamp_ms']-s['ask']['timestamp_ms'])>2000:return None
    b,a=s['bid']['price'],s['ask']['price']
    return {'bid':b,'ask':a} if 0<b<=a else None
def convert(usd,fx):return usd/(fx['ask'] if usd>=0 else fx['bid'])
def commission(f,units,p,fx):
    if any(n not in f for n in ('preciseTradingCommissionRate','preciseMinCommission','commissionType','minCommissionType','lotSize')):return None
    kind=int(f['commissionType']);rate=int(f['preciseTradingCommissionRate']);lot=int(f['lotSize']);floor=int(f['preciseMinCommission'])/1e8
    if lot<=0:return None
    if rate==0:usd=0.
    elif kind==1:usd=rate/1e8*units*p/1e6
    elif kind in (2,4):usd=rate/1e8*units*100/lot # quote asset USD is verified for this panel
    elif kind==3:usd=rate/1e5/100*units*p
    else:return None
    typ=int(f['minCommissionType']);asset=f.get('minCommissionAsset')
    if typ==2:floor_eur=floor/fx['bid']
    elif typ==1 and asset=='USD':floor_eur=floor/fx['bid']
    elif typ==1 and asset=='EUR':floor_eur=floor
    elif floor==0:floor_eur=0.
    else:return None
    return max(usd/fx['bid'],floor_eur)
def account(d,u,q0,q1,fx0,fx1,f,slip,funding,absolute_fee=False):
    p0=(q0['ask'] if d==1 else q0['bid'])*(1+d*slip/10000)
    p1=(q1['bid'] if d==1 else q1['ask'])*(1-d*slip/10000)
    gross=convert(d*u*(p1-p0),fx1);c0=commission(f,u,p0,fx0);c1=commission(f,u,p1,fx1)
    if c0 is None or c1 is None or 'pnlConversionFeeRate' not in f:return None
    frac=int(f['pnlConversionFeeRate'])/10000
    fee=(abs(gross) if absolute_fee else max(gross,0))*frac
    return {'gross_eur':gross,'entry_commission_eur':c0,'exit_commission_eur':c1,'conversion_fee_eur':fee,'funding_eur':funding,'net_eur':gross-c0-c1-fee-funding,'slip_per_side_bps':slip,'loss_fee_convention':'ABSOLUTE_GROSS_STRESS' if absolute_fee else 'POSITIVE_REALIZED_GROSS_BASE'}
def entry_gate(r,row,f,q,fx,session_open):
    z={'eligible':False,'reason':'NO_SIGNAL','range_cost_proxy_eur':None}
    if not r['d']:return z
    if not q or not fx:z['reason']='ENTRY_OR_FX_QUOTE_UNAVAILABLE';return z
    u=int(row['min_volume_cents'])/100
    if u<=0 or int(row['step_volume_cents'])<=0 or int(f.get('lotSize',0))<=0:z['reason']='VOLUME_LATTICE';return z
    margin=max(float(row['buy_margin_eur']),float(row['sell_margin_eur']))
    p=q['ask'] if r['d']==1 else q['bid'];c=commission(f,u,p,fx)
    if c is None or 'pnlConversionFeeRate' not in f:z['reason']='COMMISSION_UNRESOLVED';return z
    risk=u*r['range']/fx['bid'];notional=u*p/fx['bid'];flatcost=u*(q['ask']-q['bid'])/fx['bid']+2*c+notional*4/10000+.10
    proxy=risk+flatcost;z.update(units=u,margin_eur=margin,notional_eur=notional,range_eur=risk,flat_cost_eur=flatcost,range_cost_proxy_eur=proxy)
    z['reason']='CURRENT_SESSION_OR_ROLLOVER' if not session_open else 'MARGIN_GT50' if margin>50 else 'RANGE_COST_PROXY_GT2' if proxy>2 else 'NO_RANGE_HEADROOM' if risk<=flatcost else 'ELIGIBLE'
    z['eligible']=z['reason']=='ELIGIBLE';return z
def cost_stats(rr,eligible_only=False):
    rr=[r for r in rr if r['entry']['eligible']] if eligible_only else [r for r in rr if r['entry'].get('flat_cost_eur') is not None]
    v=[r for r in rr if r.get('scenarios')]
    out={'denominator_kind':'ELIGIBLE_ENTRIES' if eligible_only else 'ALL_CALCULABLE_SIGNAL_ENTRIES','entries':len(rr),'evaluable':len(v),'missing_exit_or_FX':sum(not r.get('scenarios') for r in rr),'scenarios':{}}
    for key in ('0','1','2','2_F010','2_F050','2_ABS'):
        z=[r['scenarios'][key] for r in v];n=len(z)
        out['scenarios'][key]={'n':n,'model_net_sum_eur':sum(x['model']['net_eur'] for x in z),'baseline_net_sum_eur':sum(x['baseline']['net_eur'] for x in z),'paired_net_increment_eur':sum(x['model']['net_eur']-x['baseline']['net_eur'] for x in z),'model_mean_net_eur':sum(x['model']['net_eur'] for x in z)/n if n else None,'mean_commission_eur':sum(x['model']['entry_commission_eur']+x['model']['exit_commission_eur'] for x in z)/n if n else None,'mean_conversion_fee_eur':sum(x['model']['conversion_fee_eur'] for x in z)/n if n else None}
    return out
def economic_report(rr):
    def part(v):return {'calendar':len(v),'signals':sum(bool(r['d']) for r in v),'eligible':sum(r['entry']['eligible'] for r in v),'entry_reasons':dict(Counter(r['entry']['reason'] for r in v)),'all_calculable':cost_stats(v),'eligible_only':cost_stats(v,True)}
    return {'global':part(rr),'blocks':[part([r for r in rr if r['block']==b]) for b in range(4)],'iso':{w:part([r for r in rr if r['iso']==w]) for w in WEEKS}}
