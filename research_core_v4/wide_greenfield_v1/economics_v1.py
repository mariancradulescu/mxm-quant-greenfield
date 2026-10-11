"""Signed native-currency accounting, multi-currency conversion and causal risk admission."""
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
  if len(path)>=2:continue
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

def admission(event,row,f,quotes,g):
 t=event['t']+300;fc=event['forecast'];z={'eligible':False,'reason':'NO_RETURN_FORECAST'}
 if not fc or not fc['d']:return z
 q=point(quotes.get((row['sid'],t)))
 if not q:z['reason']='ENTRY_QUOTE_UNRESOLVED';return z
 # All entry quantities use only entry conversion graph. Exit quotes are never consulted here.
 u=row['min_units'];n=convert(-u*q['mid'],row['quote'],'EUR',t,quotes,g);spread=convert(-u*(q['ask']-q['bid']),row['quote'],'EUR',t,quotes,g);c=commission(row,f,u,q['ask'] if fc['d']>0 else q['bid'],t,quotes,g)
 if n is None or spread is None or c is None:z['reason']='ENTRY_FX_OR_COMMISSION_UNRESOLVED';return z
 notional=-n;flat=-spread+2*c+notional*.0004+.10*event['h']/24;hurdle=flat/notional*10000;tail=notional*fc['tail95_bps']/10000
 z.update(notional_eur=notional,entry_flat_cost_eur=flat,entry_break_even_bps=hurdle,tail95_proxy_eur=tail,margin_eur=row['margin_eur'],entry_commission_eur=c,planned_loss_budget_eur=2.,free_reserve_eur=200-row['margin_eur'])
 if schedule_state(t,f,{})!='OPEN_CURRENT_SCHEDULE_PROXY':z['reason']='CURRENT_ENTRY_SESSION_CLOSED_OR_UNKNOWN'
 elif schedule_state(t+event['h']*3600,f,{})!='OPEN_CURRENT_SCHEDULE_PROXY':z['reason']='KNOWN_CURRENT_EXIT_SESSION_CLOSED_OR_UNKNOWN'
 elif row['margin_eur']>80:z['reason']='CURRENT_MARGIN_RESERVE_POLICY'
 elif tail+flat>2:z['reason']='MINIMUM_TICKET_TAIL_COST_EXCEEDS_1PCT_CAPITAL_PROXY'
 elif abs(fc['model'])<=hurdle:z['reason']='PREDICTED_MEAN_BELOW_ENTRY_BREAK_EVEN'
 else:z['eligible']=True;z['reason']='ELIGIBLE_MODEL_PROXY_NOT_FILL_OR_RUIN_CERTIFICATE'
 return z

def evaluate(cohort,rows,cat,quotes):
 byid={r['sid']:r for r in rows};g=graph(rows);out=[]
 for ev in cohort:
  r=byid[ev['sid']];f=cat['full'][str(r['sid'])];e=ev['t']+300;x=e+ev['h']*3600;z={'sid':r['sid'],'class':r['class'],'t':e,'exit':x,'h':ev['h'],'iso':ev['iso'],'block':ev['block'],'forecast':ev['forecast'],'entry':admission(ev,r,f,quotes,g),'scenarios':None}
  if ev['forecast'] and ev['forecast']['d']:
   zz={name:{'model':account(ev['forecast']['d'],r,f,e,x,ev['h'],quotes,g,s,fund,absfee),'baseline':account(ev['forecast']['b'],r,f,e,x,ev['h'],quotes,g,s,fund,absfee) if ev['forecast']['b'] else None} for name,(s,fund,absfee) in SCENARIOS.items()}
   if all(v['model'] is not None for v in zz.values()):z['scenarios']=zz
  out.append(z)
 return out

def stat(rows):
 calc=[r for r in rows if 'entry_flat_cost_eur' in r['entry']];eligible=[r for r in rows if r['entry']['eligible']];z={'cohort':len(rows),'forecasts':sum(bool(r['forecast']) for r in rows),'entry_reasons':dict(Counter(r['entry']['reason'] for r in rows)),'groups':{}}
 for name,rr in [('ALL_CALCULABLE',calc),('ELIGIBLE',eligible)]:
  vv=[r for r in rr if r['scenarios']];n=len(vv);paired=[r for r in vv if r['scenarios']['S0_F0']['baseline'] is not None]
  z['groups'][name]={'entries':len(rr),'evaluable_model':n,'evaluable_paired_baseline':len(paired),'exit_censored':len(rr)-n,'mean_entry_flat_cost_eur':statistics.mean(r['entry']['entry_flat_cost_eur'] for r in rr) if rr else None,'mean_entry_break_even_bps':statistics.mean(r['entry']['entry_break_even_bps'] for r in rr) if rr else None,'scenarios':{s:{'N_model':n,'model_net_eur':sum(r['scenarios'][s]['model']['net_eur'] for r in vv) if n else None,'N_same_cohort_baseline':len(paired),'paired_model_net_eur':sum(r['scenarios'][s]['model']['net_eur'] for r in paired) if paired else None,'paired_baseline_net_eur':sum(r['scenarios'][s]['baseline']['net_eur'] for r in paired) if paired else None,'paired_increment_eur':sum(r['scenarios'][s]['model']['net_eur']-r['scenarios'][s]['baseline']['net_eur'] for r in paired) if paired else None,'mean_roundtrip_commission_eur':statistics.mean(r['scenarios'][s]['model']['entry_commission_eur']+r['scenarios'][s]['model']['exit_commission_eur'] for r in vv) if n else None} for s in SCENARIOS}}
 return z

def report(rr):return {'global':stat(rr),'blocks':[stat([r for r in rr if r['block']==b]) for b in range(4)],'complete_weeks':{w:stat([r for r in rr if r['iso']==w]) for w in k.weeks()}}
def portfolio(rr):
 selected=[];busy=-1
 for t in sorted({r['t'] for r in rr}):
  if t<busy:continue
  valid=[r for r in rr if r['t']==t and r['entry']['eligible']]
  if valid:
   chosen=min(valid,key=lambda r:(r['entry']['entry_flat_cost_eur']/max(1e-12,abs(r['forecast']['model'])*r['entry']['notional_eur']/10000),r['sid']));selected.append(chosen);busy=chosen['exit']
 cash=200.;peak=200.;dd=0.;n=0;halt='END'
 for r in selected:
  if not r['scenarios']:halt='FIRST_SELECTED_EXIT_CENSORED';break
  if r['entry']['margin_eur']>.4*cash or r['entry']['tail95_proxy_eur']+r['entry']['entry_flat_cost_eur']>.01*cash:halt='REALIZED_CASH_RESERVE_OR_RISK_POLICY';break
  cash+=r['scenarios']['S2_F010_DAY']['model']['net_eur'];peak=max(peak,cash);dd=max(dd,peak-cash);n+=1
 return {'selected_entries':len(selected),'max_simultaneous':1,'report':report(selected),'cash_ledger':{'priced':n,'cash_eur':cash,'closed_cash_drawdown_eur':dd,'halt':halt,'intratrade_gap_fill_ruin':'UNIDENTIFIED;NO_ORDERS_OR_FILLS'},'HARD21':False}
