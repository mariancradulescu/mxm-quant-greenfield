"""Frozen native accounting reused with additive up-to-four-edge legitimate FX routes."""
import math,statistics
from collections import Counter,defaultdict,deque
from research_core_v4.native_executable_qualification_v1.runner_v1 import schedule_state
from research_core_v4.wide_greenfield_v1 import kernel_v1 as k
SCENARIOS={'S0_F0':(0,0,False),'S1_F0':(1,0,False),'S2_F0':(2,0,False),'S5_F0':(5,0,False),'S2_F010_DAY':(2,.10,False),'S2_F050_DAY':(2,.50,False),'S2_F100_DAY':(2,1.,False),'S2_ABS_F010_DAY':(2,.10,True)}
def graph(rows):
 g=defaultdict(list)
 for r in rows:
  if 'forex' in r['class'].lower() and r['base'] and r['quote'] and 'CURRENT_NOT_ENTRY_ENABLED' not in r.get('reasons',[]):
   g[r['base']].append((r['quote'],r['sid'],True));g[r['quote']].append((r['base'],r['sid'],False))
 return g

def route(frm,to,g):
 if frm==to:return []
 q=deque([(frm,[])]);seen={frm}
 while q:
  c,path=q.popleft()
  if len(path)>=4:continue
  for nxt,sid,forward in sorted(g.get(c,[]),key=lambda v:v[1]):
   p=path+[(sid,forward)]
   if nxt==to:return p
   if nxt not in seen:seen.add(nxt);q.append((nxt,p))
 return None

def point(q):
 if not q:return None
 s=q['sides']
 if any(s.get(n,{}).get('state')!='AUTHENTIC_CAUSAL_QUOTE' or s[n].get('source_has_more',True) or s[n].get('age_ms',10**9)>5000 for n in ('bid','ask')):return None
 if abs(s['bid']['timestamp_ms']-s['ask']['timestamp_ms'])>2000:return None
 b=s['bid']['price'];a=s['ask']['price']
 return {'bid':b,'ask':a,'mid':(b+a)/2} if 0<b<=a else None

def convert(amount,frm,to,t,quotes,g):
 p=route(frm,to,g)
 if p is None:return None
 out=amount
 for sid,forward in p:
  q=point(quotes.get((sid,t)))
  if q is None:return None
  out=out*(q['bid'] if out>=0 else q['ask']) if forward else out/(q['ask'] if out>=0 else q['bid'])
 return out

def currencies(r,f):
 out={r['quote']}
 typ=int(f['commissionType']);floor=int(f['preciseMinCommission'])/1e8;rate=int(f['preciseTradingCommissionRate'])
 if rate and typ in (1,2):out.add('USD')
 if floor:out.add(r['quote'] if int(f['minCommissionType'])==2 else f.get('minCommissionAsset'))
 return out

def commission(r,f,u,p,t,quotes,g):
 typ=int(f['commissionType']);raw=int(f['preciseTradingCommissionRate']);lot=int(f['lotSize'])/100
 if not lot>0:return None
 if raw==0:calc=0.
 elif typ==1:
  usd=convert(-u*p,r['quote'],'USD',t,quotes,g)
  if usd is None:return None
  calc=convert(usd*raw/1e8/1e6,'USD','EUR',t,quotes,g)
 elif typ==2:calc=convert(-u/lot*raw/1e8,'USD','EUR',t,quotes,g)
 elif typ==3:calc=convert(-u*p*(raw/1e5)/100,r['quote'],'EUR',t,quotes,g)
 elif typ==4:calc=convert(-u/lot*raw/1e8,r['quote'],'EUR',t,quotes,g)
 else:return None
 floor=int(f['preciseMinCommission'])/1e8;ccy=r['quote'] if int(f['minCommissionType'])==2 else f.get('minCommissionAsset')
 fl=0. if floor==0 else convert(-floor,ccy,'EUR',t,quotes,g)
 if calc is None or fl is None:return None
 return max(-calc,-fl)

def account(d,r,f,entry,exit,h,quotes,g,slip,fund,absolute=False):
 q0=point(quotes.get((r['sid'],entry)));q1=point(quotes.get((r['sid'],exit)))
 if d==0 or not q0 or not q1:return None
 u=r['min_units'];p0=(q0['ask'] if d>0 else q0['bid'])*(1+d*slip/10000);p1=(q1['bid'] if d>0 else q1['ask'])*(1-d*slip/10000)
 gross=convert(d*u*(p1-p0),r['quote'],'EUR',exit,quotes,g);c0=commission(r,f,u,p0,entry,quotes,g);c1=commission(r,f,u,p1,exit,quotes,g)
 if gross is None or c0 is None or c1 is None:return None
 fee=(abs(gross) if absolute else max(gross,0))*int(f['pnlConversionFeeRate'])/10000 if r['quote']!='EUR' else 0.
 funding=fund*h/24
 return {'gross_eur':gross,'entry_commission_eur':c0,'exit_commission_eur':c1,'pnl_conversion_fee_eur':fee,'funding_stress_eur':funding,'net_eur':gross-c0-c1-fee-funding,'historical_terms_and_fills':'UNKNOWN_CURRENT_TERMS_REFERENCE_QUOTES_ONLY'}

