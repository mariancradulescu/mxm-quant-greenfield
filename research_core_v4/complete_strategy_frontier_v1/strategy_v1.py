"""One complete paired CFD strategy on native common-time quotes; no historical signal reuse."""
import bisect,math,statistics
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as a
SCENARIOS={'S0_F0':(0,0,False),'S1_F0':(1,0,False),'S2_F0':(2,0,False),'S2_F010':(2,.1,False),'S5_F0':(5,0,False),'S2_F050':(2,.5,False),'S2_F100':(2,1,False),'S2_ABS_F010':(2,.1,True)}
PAIRS=((2742,2746),(2744,2746));IDS=(2742,2744,2746,14,9)
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def atr15(rows,start):
 tt=list(range(start-4500,start,300))
 if any(t not in rows for t in tt):return None
 z=[rows[t] for t in tt];return statistics.mean(max(v[1]-v[2],abs(v[1]-p[3]),abs(v[2]-p[3])) for p,v in zip(z,z[1:]))
class Quotes:
 def __init__(self,streams):
  self.streams=streams;self.times={sid:{side:[v[0] for v in rows] for side,rows in sides.items()} for sid,sides in streams.items()}
 def at(self,sid,t):
  ms=t*1000;sides={}
  for side in ('bid','ask'):
   rows=self.streams.get(sid,{}).get(side,[]);tt=self.times.get(sid,{}).get(side,[]);i=bisect.bisect_right(tt,ms)-1
   if i<0:return None
   tm,price=rows[i];sides[side]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':tm,'price':price,'age_ms':ms-tm,'source_has_more':False}
  q={'symbol_id':sid,'boundary_ms':ms,'sides':sides}
  return q if a.point(q) else None
 def context(self,sids,t,common=True):
  values={};times=[]
  for sid in sids:
   q=self.at(sid,t)
   if q is None:return None
   values[sid,t]=q;times.extend(q['sides'][side]['timestamp_ms'] for side in ('bid','ask'))
  if common and max(times)-min(times)>2000:return None
  return values

def needed(row,f,g):
 paths=[a.route(c,'EUR',g) for c in a.currencies(row,f)]+([a.route(row['quote'],'USD',g)] if int(f['commissionType'])==1 and int(f['preciseTradingCommissionRate'])>0 else [])
 if any(path is None for path in paths):return None
 return {row['sid']}|{sid for path in paths for sid,_ in path}
def orientation(A,B,t,quotes,rows,cat,g,ATRs):
 rowA={**rows[A],'min_units':.01};rowB={**rows[B],'min_units':.01};fA=cat['full'][str(A)];fB=cat['full'][str(B)];qa=a.point(quotes[A,t]);qb=a.point(quotes[B,t]);out=[]
 for long,ql,short,qs in [(rowA,qa,rowB,qb),(rowB,qb,rowA,qa)]:
  grossA=a.convert(-.01*ql['ask'],long['quote'],'EUR',t,quotes,g);grossB=a.convert(.01*qs['bid'],short['quote'],'EUR',t,quotes,g)
  if grossA is None or grossB is None:continue
  discrepancy=grossA+grossB;directions={long['sid']:1,short['sid']:-1};cost=[];stressed=[];loss=[];fxstress=0.;margin=0.
  for row in (rowA,rowB):
   f=cat['full'][str(row['sid'])];d=directions[row['sid']];v=a.account(d,row,f,t,t,5/60,quotes,g,2,.1);w=a.account(d,row,f,t,t,5/60,quotes,g,5,.1)
   if v is None or w is None:return None
   cost.append(-v['net_eur']);stressed.append(-w['net_eur']);at=ATRs.get(row['sid'])
   if at is None:return None
   adverse=a.convert(-.01*5*at,row['quote'],'EUR',t,quotes,g)
   if adverse is None:return None
   loss.append(-adverse);q=a.point(quotes[row['sid'],t]);margin+=row['margin_eur']*.01/row['min_units']
   if row['quote']!='EUR':notional=a.convert(-.01*q['mid'],row['quote'],'EUR',t,quotes,g);fxstress+=-notional*.01
  total_cost=sum(cost);risk=sum(loss)+sum(stressed)+fxstress;out.append({'pair':[A,B],'long':long['sid'],'short':short['sid'],'directions':directions,'discrepancy_eur':discrepancy,'flat_roundtrip_cost_eur':total_cost,'headroom_eur':discrepancy-2*total_cost,'stress_risk_eur':risk,'margin_eur':margin,'signal':discrepancy>2*total_cost and risk<=2 and margin<=80})
 return max(out,key=lambda z:z['headroom_eur']) if out else None

def liquidation(position,t,ctx,rows,cat,g,scenario):
 slip,fund,absolute=SCENARIOS[scenario];both={**position['entry_ctx'],**ctx};values=[]
 for sid,d in position['directions'].items():
  row={**rows[sid],'min_units':.01};v=a.account(d,row,cat['full'][str(sid)],position['entry'],t,(t-position['entry'])/3600,both,g,slip,fund,absolute)
  if v is None:return None
  values.append(v)
 return {'net_eur':sum(v['net_eur'] for v in values),'gross_eur':sum(v['gross_eur'] for v in values),'entry_commission_eur':sum(v['entry_commission_eur'] for v in values),'exit_commission_eur':sum(v['exit_commission_eur'] for v in values),'funding_eur':sum(v['funding_stress_eur'] for v in values),'conversion_fee_eur':sum(v['pnl_conversion_fee_eur'] for v in values),'legs':values}
def exit_reason(value,position,current_discrepancy,t):
 if value<=-.5*position['stress_risk_eur']:return 'STOP'
 if value>=.5*position['headroom_eur']:return 'PROFIT'
 if current_discrepancy<=0:return 'INVALIDATION'
 if t>=position['entry']+300:return 'SAFETY'
 return None

def evaluate(days,rows,cat,graph):
 cash=200.;fixed_cash=200.;pending=None;position=None;records=[];opps=[];week=defaultdict(Counter);halt=None;cooldown=-1;phase_states=Counter();open_margin=0.;peak=200.;drawdown=0.
 for day in days:
  start=day['start'];end=start+2100;w=iso(start);week[w]['strategy_session_days']+=1;Q=Quotes(day['streams']);ATRs=day['ATRs'];data_complete=all(v=='COMPLETE_AUTHENTIC_WINDOW' for v in day['status'].values())
  if not data_complete:week[w]['incomplete_session_days']+=1
  for t in range(start,end+1):
   # Data missingness is retained. A supported cash abstention is separate from an unknown fill.
   if pending is not None and t==pending['decision']+1:
    ctx=Q.context(pending['required_ids'],t)
    if ctx is None or not data_complete:
     halt='FIRST_SELECTED_ENTRY_UNKNOWN';pending.update(state=halt,entry=None);records.append(pending);pending=None
    else:
     position={**pending,'entry':t,'entry_ctx':ctx,'dynamic_exit':None,'fixed_exit':None,'MFE_eur':0.,'MAE_eur':0.,'last_valid_quote':t,'quote_gap_seconds':0};pending=None;open_margin=position['margin_eur'];week[w]['modeled_entries']+=1
   if position is not None:
    required=position['required_ids'];ctx=Q.context(required,t)
    if ctx is not None:
     quote_gap=t-position['last_valid_quote'];position['quote_gap_seconds']=max(position['quote_gap_seconds'],quote_gap);position['last_valid_quote']=t
     if position['fixed_exit'] is None and t==position['entry']+60:
      position['fixed_accounts']={name:liquidation(position,t,ctx,rows,cat,graph,name) for name in SCENARIOS};position['fixed_exit']=t
     if position['dynamic_exit'] is None:
      val=liquidation(position,t,ctx,rows,cat,graph,'S2_F010')
      if val is None:halt='FIRST_SELECTED_COST_UNKNOWN'
      else:
       position['MFE_eur']=max(position['MFE_eur'],val['net_eur']);position['MAE_eur']=max(position['MAE_eur'],-val['net_eur']);A,B=position['pair'];ql=a.point(ctx[position['long'],t]);qs=a.point(ctx[position['short'],t]);long=rows[position['long']];short=rows[position['short']];debit=a.convert(-.01*ql['ask'],long['quote'],'EUR',t,ctx,graph);credit=a.convert(.01*qs['bid'],short['quote'],'EUR',t,ctx,graph);discrepancy=debit+credit if debit is not None and credit is not None else None
       if discrepancy is None:halt='FIRST_SELECTED_FX_UNKNOWN'
       else:
        reason=exit_reason(val['net_eur'],position,discrepancy,t)
        if reason:
         position['dynamic_exit']=t;position['reason']=reason;position['dynamic_accounts']={name:liquidation(position,t,ctx,rows,cat,graph,name) for name in SCENARIOS};cash+=val['net_eur'];peak=max(peak,cash);drawdown=max(drawdown,peak-cash);open_margin=0.;week[iso(t)]['modeled_dynamic_closed_packages']+=1
    if position['fixed_exit'] is None and t>position['entry']+60:halt='FIRST_SELECTED_FIXED_EXIT_UNKNOWN'
    if position['dynamic_exit'] is None and t>=position['entry']+300:halt='FIRST_SELECTED_DYNAMIC_EXIT_UNKNOWN'
    if halt:
     position.update(state=halt);records.append(position);position=None
    elif position['dynamic_exit'] is not None and position['fixed_exit'] is not None:
     f=position['fixed_accounts'].get('S2_F010')
     if f is None:halt='FIRST_SELECTED_FIXED_COST_UNKNOWN';position['state']=halt
     else:fixed_cash+=f['net_eur'];position['state']='PAIRED_MODELED_COMPLETE';week[w]['paired_NET_packages']+=1
     records.append(position);cooldown=max(position['dynamic_exit'],position['fixed_exit'])+30;position=None
   if (t-start)%5!=0 or t>=start+1800:continue
   candidate=[]
   for A,B in PAIRS:
    week[w]['candidate_pair_clocks']+=1;ids=needed(rows[A],cat['full'][str(A)],graph)|needed(rows[B],cat['full'][str(B)],graph);ctx=Q.context(ids,t);state='QUOTE_OR_FX_NA' if ctx is None or not data_complete else 'WARMUP_M5_NA' if any(ATRs.get(sid) is None for sid in (A,B)) else None;value=None
    if state is None:
     value=orientation(A,B,t,ctx,rows,cat,graph,ATRs)
     if value is None:state='CONTRACT_OR_CONVERSION_NA'
     elif value['discrepancy_eur']<=0:state='NO_POSITIVE_EXECUTABLE_VALUE_DISCREPANCY'
     elif value['headroom_eur']<=0:state='COST_BUFFER_NOT_MET'
     elif not value['signal']:state='RISK_OR_MARGIN'
     else:state='ECONOMIC_SIGNAL';candidate.append({**value,'required_ids':sorted(ids),'decision':t,'iso':w})
    week[w][state]+=1;opps.append({'t':t,'pair':[A,B],'state':state,'value':value})
   if not candidate or halt or pending is not None or position is not None or t<cooldown:continue
   candidate.sort(key=lambda z:(-z['headroom_eur'],z['pair'][0]));r=candidate[0];cap=min(cash,fixed_cash)
   if r['margin_eur']>.4*cap or r['stress_risk_eur']>.01*cap:week[w]['current_capital_rejected']+=1;continue
   pending=r;week[w]['selected_entry_decisions']+=1
  if position is not None or pending is not None:
   halt=halt or 'SESSION_END_UNCLOSED_OR_PENDING'
   if position:position['state']=halt;records.append(position)
   if pending:pending['state']=halt;records.append(pending)
   position=pending=None
 complete=[r for r in records if r['state']=='PAIRED_MODELED_COMPLETE'];scenario={}
 for name in SCENARIOS:
  vv=[r for r in complete if r['dynamic_accounts'][name] is not None and r['fixed_accounts'][name] is not None];scenario[name]={'paired':len(vv),'dynamic_NET_eur':sum(r['dynamic_accounts'][name]['net_eur'] for r in vv) if vv else None,'fixed_NET_same_entries_eur':sum(r['fixed_accounts'][name]['net_eur'] for r in vv) if vv else None,'increment_eur':sum(r['dynamic_accounts'][name]['net_eur']-r['fixed_accounts'][name]['net_eur'] for r in vv) if vv else None}
 weekly={}
 for w in ('2026-W12','2026-W13'):
  vv=[r for r in complete if r['iso']==w];weekly[w]={'counts':dict(week[w]),'dynamic_NET_eur':sum(r['dynamic_accounts']['S2_F010']['net_eur'] for r in vv) if vv else None,'fixed_NET_eur':sum(r['fixed_accounts']['S2_F010']['net_eur'] for r in vv) if vv else None,'cash_only_known':not any(r.get('iso')==w for r in records),'supported_no_trade_cash_NET':0 if not any(r.get('iso')==w for r in records) else None,'modeled_HARD21':len(vv)>=21,'actual_trades':0}
 selected=len(records);unknown=sum(r['state']!='PAIRED_MODELED_COMPLETE' for r in records);summary={'schema':'mxm.private.complete.strategy.net.v1','mechanism':'MATCHED_BASE_UNIT_CROSS_CURRENCY_EXECUTABLE_VALUATION_V1','candidate_pair_clocks':len(opps),'economic_signals':sum(r['state']=='ECONOMIC_SIGNAL' for r in opps),'data_and_economic_states':dict(Counter(r['state'] for r in opps)),'selected_entry_decisions':selected,'modeled_entries':sum(r.get('entry') is not None for r in records),'modeled_paired_complete_packages':len(complete),'unknown_selected_packages':unknown,'weekly':weekly,'scenario_NET':scenario,'cash_EUR_closed_accounting':cash,'fixed_cash_EUR_closed_accounting':fixed_cash,'closed_cash_drawdown_eur':drawdown,'halt':halt,'actual_orders':0,'actual_trades':0,'HARD21':False,'two_leg_atomic_execution':'ASSUMPTION_NOT_OBSERVED;FX_AND_LEGGING_STRESS_NOT_LOSS_GUARANTEE','historical_funding_fees_fills':'UNKNOWN_CURRENT_REFERENCE_SCENARIOS','alpha_certified':False,'statistics':'TWO_WEEKS_LT26_NO_PVALUE_OR_LEAD_PROMOTION','verdict':'INSUFICIENT_DATE' if unknown or any(k.endswith('_NA') for k in Counter(r['state'] for r in opps)) else 'NEGATIV_NO_ECONOMIC_ENTRY' if not complete else 'EXPLORATORIU_NO_CERTIFICATION'}
 return {'summary':summary,'opportunities':opps,'packages':records},summary
