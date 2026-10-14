"""Minimum-volume EUR accounting. Proxy and native quotes never share labels."""
import math
from collections import Counter
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as existing
from . import kernel_v1 as k
SCENARIOS={'PRIMARY_S5_L2_F010':(5.,2.,.10),'S1_L0_F0':(1.,0.,0.),'S10_L5_F050':(10.,5.,.50)}

def reference(sid,j,panel,at_exit=False):
 o=panel.get(sid)
 if o is None:return None
 v=float(o['exit_reference'][j] if at_exit else o['entry'][j]);return v if math.isfinite(v) and v>0 else None

def conversion(amount,frm,to,j,panel,graph,at_exit=False):
 route=existing.route(frm,to,graph)
 if route is None:return None
 value=amount
 for sid,forward in route:
  mid=reference(sid,j,panel,at_exit)
  if mid is None:return None
  # Explicit adverse FX spread/slippage proxy 2bp per conversion edge.
  bid=mid*(1-.0002);ask=mid*(1+.0002)
  value=value*(bid if value>=0 else ask) if forward else value/(ask if value>=0 else bid)
 return value

def commission(row,f,units,price,j,panel,graph,at_exit=False):
 try:typ=int(f['commissionType']);rate=int(f['preciseTradingCommissionRate']);lot=int(f['lotSize'])/100;floor=int(f['preciseMinCommission'])/1e8;min_type=int(f['minCommissionType'])
 except (KeyError,ValueError,TypeError):return None
 if lot<=0:return None
 def cv(v,ccy):return conversion(-v,ccy,'EUR',j,panel,graph,at_exit)
 if rate==0:fee=0.
 elif typ==1:
  usd=conversion(-units*price,row['quote'],'USD',j,panel,graph,at_exit)
  if usd is None:return None
  fee=cv(-usd*rate/1e8/1e6,'USD')
 elif typ==2:fee=cv(units/lot*rate/1e8,'USD')
 elif typ==3:fee=cv(units*price*rate/1e5/100,row['quote'])
 elif typ==4:fee=cv(units/lot*rate/1e8,row['quote'])
 else:return None
 ccy=row['quote'] if min_type==2 else f.get('minCommissionAsset')
 minimum=0. if floor==0 else cv(floor,ccy)
 return max(-fee,-minimum) if fee is not None and minimum is not None else None

def planned(ev,row,f,panel,graph):
 j=ev['j'];price=reference(row['sid'],j,panel);out={'eligible':False,'reason':'ENTRY_REFERENCE_OR_ATR_UNAVAILABLE'}
 if price is None or ev['atr_price'] is None or ev['atr_price']<=0:return out
 units=row['min_units'];notional=conversion(-units*price,row['quote'],'EUR',j,panel,graph);risk=conversion(-units*ev['atr_price'],row['quote'],'EUR',j,panel,graph);fee=commission(row,f,units,price,j,panel,graph)
 if any(x is None for x in (notional,risk,fee)):out['reason']='CAUSAL_M5_FX_OR_CURRENT_FEE_UNAVAILABLE';return out
 notional=-notional;risk=-risk;cost=notional*.0009+2*fee+.10/24
 # Absolute PnL conversion fee stress is disclosed; do not count it as zero.
 rate=int(f['pnlConversionFeeRate'])/10000 if row['quote']!='EUR' else 0.;planned_loss=(risk+cost)*(1+rate)
 out.update(notional_eur=notional,planned_stop_eur=risk,current_roundtrip_commission_proxy_eur=2*fee,entry_cost_proxy_eur=cost,planned_total_loss_proxy_eur=planned_loss,stop_distance=ev['atr_price'],margin_eur=row['margin_eur'],predicted_net_eur=abs(ev['model'])*notional/10000-cost,pnl_conversion_fee_rate=rate)
 if row['margin_eur']>80:out['reason']='MARGIN_RESERVE'
 elif planned_loss>2:out['reason']='MINIMUM_TICKET_ATR_AND_FRICTION_GT2EUR'
 elif not sign_model(ev):out['reason']='ZERO_DIRECTION'
 elif out['predicted_net_eur']<=0:out['reason']='FORECAST_BELOW_FROZEN_ENTRY_COST_PROXY'
 else:out['eligible']=True;out['reason']='PAPER_ENTRY_PROXY_ONLY'
 return out

def sign_model(ev):return k.sign(ev['model'])

def account(ev,d,row,f,panel,graph,scenario):
 j=ev['j'];price=reference(row['sid'],j,panel);distance=ev['atr_price'];path=panel[row['sid']]['path'][j]
 if price is None or distance is None or distance<=0 or d==0:return None
 exit=k.stop_path(d,path,distance)
 if exit is None:return None
 spread,slip,funding=SCENARIOS[scenario];units=row['min_units'];p0=price*(1+d*(spread/2+slip)/10000);p1=exit['price']*(1-d*(spread/2+slip)/10000)
 gross=conversion(d*units*(exit['price']-price),row['quote'],'EUR',j,panel,graph,True);priced=conversion(d*units*(p1-p0),row['quote'],'EUR',j,panel,graph,True)
 c0=commission(row,f,units,p0,j,panel,graph);c1=commission(row,f,units,p1,j,panel,graph,True)
 if any(x is None for x in (gross,priced,c0,c1)):return None
 rate=int(f['pnlConversionFeeRate'])/10000 if row['quote']!='EUR' else 0.;fee=abs(priced)*rate;fund=funding/24
 return {'gross_eur':gross,'spread_slippage_drag_eur':gross-priced,'commission_eur':c0+c1,'pnl_conversion_fee_eur':fee,'funding_eur':fund,'net_eur':priced-c0-c1-fee-fund,'exit_kind':exit['kind'],'stop_loss_breach_gt2':priced-c0-c1-fee-fund < -2-1e-8}

def exact(ev,d,row,f,quotes,graph,panel):
 # Never pretend a M5-triggered stop is an authenticated tick exit.
 stop=k.stop_path(d,panel[row['sid']]['path'][ev['j']],ev['atr_price']) if ev['atr_price'] else None
 if stop is None or stop['kind']!='FIXED_60MIN_CLOSE_REFERENCE':return None
 return existing.account(d,row,f,ev['t'],ev['exit'],1,quotes,graph,2.,.10,True)

def totals(records,scope='all'):
 rr=records if scope=='all' else [r for r in records if r['entry']['eligible']];out={'events':len(rr),'entry_reasons':dict(Counter(r['entry']['reason'] for r in rr)),'scenarios':{}}
 for name in SCENARIOS:
  qq=[r['scenarios'][name] for r in rr if r['scenarios'].get(name) is not None];n=len(qq)
  out['scenarios'][name]={'paired_evaluable':n,'model':{key:sum(z['model'][key] for z in qq) if n else None for key in ('gross_eur','spread_slippage_drag_eur','commission_eur','pnl_conversion_fee_eur','funding_eur','net_eur')},'baseline':{key:sum(z['baseline'][key] for z in qq) if n else None for key in ('gross_eur','spread_slippage_drag_eur','commission_eur','pnl_conversion_fee_eur','funding_eur','net_eur')},'paired_net_increment_eur':sum(z['model']['net_eur']-z['baseline']['net_eur'] for z in qq) if n else None,'model_stop_risk_breaches':sum(z['model']['stop_loss_breach_gt2'] for z in qq),'stop_kinds':dict(Counter(z['model']['exit_kind'] for z in qq))}
 q=[r['exact'] for r in rr if r.get('exact')];out['native_quote_current_terms_reference']={'paired_evaluable':len(q),'model_net_eur':sum(z['model']['net_eur'] for z in q) if q else None,'baseline_net_eur':sum(z['baseline']['net_eur'] for z in q) if q else None,'historical_charges_slippage_fills':'UNRESOLVED_CURRENT_TERMS_AND_FROZEN_STRESS_ONLY'}
 return out

def portfolio(records):
 chosen=[];busy=-1;cash=200.;peak=cash;dd=0.;halt='END';ledger=[]
 bytime={}
 for r in records:bytime.setdefault(r['t'],[]).append(r)
 for t,vv in sorted(bytime.items()):
  if t<busy:continue
  eligible=[r for r in vv if r['entry']['eligible'] and r['entry']['margin_eur']<=min(80.,cash-120.) and r['entry']['planned_total_loss_proxy_eur']<=2]
  if not eligible:continue
  r=min(eligible,key=lambda z:(-z['entry']['predicted_net_eur'],z['sid']));chosen.append(r);busy=r['exit'];a=r['scenarios'].get('PRIMARY_S5_L2_F010')
  if not a:halt='FIRST_SELECTED_EXIT_OR_FX_CENSORED';break
  cash+=a['model']['net_eur'];peak=max(peak,cash);dd=max(dd,peak-cash);ledger.append({'t':t,'sid':r['sid'],'net_eur':a['model']['net_eur'],'cash_eur':cash})
  if a['model']['stop_loss_breach_gt2']:halt='FIRST_STOP_GAP_OR_COST_RISK_BREACH';break
 return {'chosen':len(chosen),'priced':len(ledger),'max_simultaneous':1,'cash_eur':cash,'closed_drawdown_eur':dd,'halt':halt,'ledger':ledger,'weekly':{w:sum(k.iso(z['t'])==w for z in ledger) for w in sorted({k.iso(t) for t in bytime})},'valuation':'PAPER_PROXY_ONLY_NO_POSITIVE_EXECUTABLE_EDGE_CERTIFICATION','report':totals(chosen)}
