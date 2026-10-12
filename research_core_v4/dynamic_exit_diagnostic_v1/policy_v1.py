"""Frozen causal exit policies; price geometry is explicitly distinct from execution."""
import math,bisect,statistics
from collections import defaultdict,Counter
from datetime import datetime,timezone
BAR_TIMES={}
def times_of(bars):
 key=id(bars)
 if key not in BAR_TIMES:BAR_TIMES[key]=sorted(bars)
 return BAR_TIMES[key]
POLICIES=('BRACKET_R1_TP2','ATR_TRAIL_2','CHANDELIER_3','PROGRESSIVE_2R','MOMENTUM_INVALIDATION')
def atr(bars,t):
 times=times_of(bars);i=bisect.bisect_right(times,t-300);tt=times[max(0,i-15):i]
 if len(tt)<15 or tt[-1]+300!=t:return None
 z=[bars[u] for u in tt]
 return statistics.mean(max(v[1]-v[2],abs(v[1]-p[3]),abs(v[2]-p[3])) for p,v in zip(z,z[1:]))
def params(r,bars,q):
 t=r['t'];at=atr(bars,r['grid']);d=r['model_side'];en=r['entry']
 if at is None or not at>0 or not q or d not in (1,-1) or not en.get('notional_eur'):return None
 price=q['ask'] if d>0 else q['bid'];factor=en['notional_eur']/q['mid'];cost=en['cost_eur']/factor;R=max(at,2*cost)
 # A five-bps-per-side stress supplements the two-bps-per-side entry cost reference.
 risk=(max(R,3*at)+2*at)*factor+en['cost_eur']+.0006*en['notional_eur']
 return {'d':d,'price':price,'atr':at,'R':R,'cost_price':cost,'eur_per_price':factor,'stress_risk_eur':risk,'stress_eligible':risk<=2 and en.get('eligible',False) and en['margin_eur']<=80}
def initial(p,name):
 dist=2*p['atr'] if name=='ATR_TRAIL_2' else 3*p['atr'] if name=='CHANDELIER_3' else p['R']
 return {'stop':p['price']-p['d']*dist,'tp':p['price']+p['d']*2*p['R'] if name=='BRACKET_R1_TP2' else None,'invalid':0,'invalid_exit':False,'peak':p['price']}
def advance(state,p,name,bars,available,entry):
 # Call only after trigger tests at the close timestamp. All inputs are completed bars.
 times=times_of(bars);i=bisect.bisect_right(times,available-300);tt=times[max(0,i-15):i]
 if len(tt)<15:return
 z=[bars[t] for t in tt];close=z[-1][3];at=atr(bars,available)
 if at is None:return
 d=p['d'];state['peak']=max(state['peak'],close) if d>0 else min(state['peak'],close)
 candidate=None
 if name=='ATR_TRAIL_2':candidate=state['peak']-d*2*at
 elif name=='CHANDELIER_3':candidate=(max(v[1] for v in z[-14:]) if d>0 else min(v[2] for v in z[-14:]))-d*3*at
 elif name=='PROGRESSIVE_2R' and d*(close-p['price'])>=2*p['R']:candidate=p['price']+d*p['cost_price']
 elif name=='MOMENTUM_INVALIDATION' and available>entry:
  state['invalid']=state['invalid']+1 if d*(close-z[-13][3])<=0 else 0
  state['invalid_exit']=state['invalid']>=2
 if candidate is not None:state['stop']=max(state['stop'],candidate) if d>0 else min(state['stop'],candidate)
def m5_geometry(r,bars,p,name):
 if p is None:return {'state':'ENTRY_ATR_OR_COST_NA'}
 s=initial(p,name);d=p['d'];start=r['t'];end=start+14400;grid=r['grid'];mae=mfe=0.;last=None
 for t in range(grid,int(end//300)*300+1,300):
  if t>=end:break
  v=bars.get(t)
  if v is None:return {'state':'M5_PATH_GAP','first_missing':t,'MFE_price':mfe,'MAE_price':mae}
  adverse=v[2] if d>0 else v[1];favorable=v[1] if d>0 else v[2]
  stop=d*(adverse-s['stop'])<=0;tp=s['tp'] is not None and d*(favorable-s['tp'])>=0
  # A partial first/last bar cannot establish that its extrema occurred inside the position.
  partial=t<start or t+300>end
  if (stop or tp) and partial:return {'state':'M5_PARTIAL_BAR_AMBIGUOUS','bar':t,'stop_touched':stop,'tp_touched':tp}
  if stop and tp:return {'state':'M5_DOUBLE_TOUCH_AMBIGUOUS','bar':t}
  if t>=start and t+300<=end:
   mae=max(mae,-d*(adverse-p['price']));mfe=max(mfe,d*(favorable-p['price']))
  if stop or tp:return {'state':'M5_SINGLE_TOUCH_GEOMETRY_ONLY','reason':'STOP' if stop else 'TP','bar':t,'level':s['stop'] if stop else s['tp'],'MFE_price':mfe,'MAE_price':mae,'execution_price':None,'NET':None}
  if s['invalid_exit'] and t>=start:return {'state':'M5_INVALIDATION_GEOMETRY_ONLY','bar':t,'MFE_price':mfe,'MAE_price':mae,'NET':None}
  if t+300<=end:advance(s,p,name,bars,t+300,start)
  last=t
 return {'state':'M5_SAFETY_CAP_GEOMETRY_ONLY','exit':end,'MFE_price':mfe,'MAE_price':mae,'NET':None}
def fresh(bid,ask,t):
 if bid is None or ask is None:return None
 if t-bid[0]>5000 or t-ask[0]>5000 or abs(bid[0]-ask[0])>2000 or not 0<bid[1]<=ask[1]:return None
 return {'bid':bid[1],'ask':ask[1],'mid':(bid[1]+ask[1])/2,'bid_ts':bid[0],'ask_ts':ask[0]}
def tick_exit(r,bars,p,name,stream,complete,entry_q):
 if not complete:return {'state':'TICK_PATH_INCOMPLETE','NET':None}
 if p is None:return {'state':'ENTRY_ATR_OR_COST_NA','NET':None}
 s=initial(p,name);start=int(r['t']*1000);end=start+14400000;d=p['d'];bid=ask=None;mae=mfe=0.;last_quote=None;gaps=0
 # Raw timestamps and bar availability share one chronology; quotes at a close test old levels.
 events=defaultdict(list)
 for side,rows in stream.items():
  for t,price in rows:
   if start-60000<=t<=end:events[t].append((side,price))
 for t in range(int(r['grid']+300),int(end//1000)+1,300):events[t*1000].append(('bar',None))
 events[end].append(('cap',None))
 for tm in sorted(events):
  group=events[tm];had_quote=False
  for side,price in group:
   if side=='bid':bid=(tm,price);had_quote=True
   elif side=='ask':ask=(tm,price);had_quote=True
  q=fresh(bid,ask,tm)
  if tm>=start and q:
   exit_price=q['bid'] if d>0 else q['ask'];delta=d*(exit_price-p['price']);mae=max(mae,-delta);mfe=max(mfe,delta)
   if had_quote:
    if last_quote is not None and tm-last_quote>300000:gaps+=1
    last_quote=tm
   reason='STOP' if d*(exit_price-s['stop'])<=0 else 'TP' if s['tp'] is not None and d*(exit_price-s['tp'])>=0 else 'INVALIDATION' if s['invalid_exit'] else 'SAFETY_CAP' if tm==end else None
   if reason:
    return {'state':'BID_ASK_CAUSAL_TRIGGER_MODELED_FILL','reason':reason,'exit':tm/1000,'quote':q,'MFE_price':mfe,'MAE_price':mae,'observed_fresh_pair_gaps_over5min':gaps,'stop_level':s['stop'],'fill_assumption':'FIRST_OBSERVABLE_EXIT_SIDE_PLUS_SCENARIO_SLIPPAGE_NOT_ACTUAL_FILL'}
  if any(side=='bar' for side,_ in group) and tm>start:
   if bars.get(tm//1000-300) is None:return {'state':'M5_UPDATE_BAR_NA','NET':None}
   advance(s,p,name,bars,tm//1000,r['t'])
 return {'state':'SAFETY_CAP_FRESH_EXIT_QUOTE_NA','NET':None,'MFE_price':mfe,'MAE_price':mae}
def quote_record(sid,t,q):
 return {'symbol_id':sid,'boundary_ms':int(t*1000),'sides':{n:{'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':int(q.get(n+'_ts',t*1000)),'price':q[n],'age_ms':int(t*1000-q.get(n+'_ts',t*1000)),'source_has_more':False} for n in ('bid','ask')}}
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def paired_stats(records,h,name):
 rr=[r for r in records if r['h']==h and r['policy']==name];z=[r for r in rr if r.get('dynamic_net') is not None and r.get('fixed_net') is not None];clocks=defaultdict(list)
 for r in z:clocks[r['t']].append((r['dynamic_net'],r['dynamic_net']-r['fixed_net']))
 ww=defaultdict(list)
 for t,vals in clocks.items():ww[iso(t)].append([statistics.mean(v[i] for v in vals) for i in (0,1)])
 w={k:[statistics.mean(v[i] for v in vals) for i in (0,1)] for k,vals in sorted(ww.items())};arr=list(w.values());lower=None;halves=[]
 if len(arr)>=2:halves=[[statistics.mean(v[i] for v in part) for i in (0,1)] for part in (arr[:len(arr)//2],arr[len(arr)//2:])]
 if len(arr)>=26:
  import numpy as np
  rng=np.random.default_rng(20261012);a=np.asarray(arr);bs=[]
  for _ in range(2000):
   ix=np.concatenate([(np.arange(4)+int(v))%len(a) for v in rng.integers(0,len(a),size=math.ceil(len(a)/4))])[:len(a)];bs.append(np.mean(a[ix],axis=0))
  lower=np.quantile(bs,.05/15,axis=0).tolist()
 return {'saved_entries':len(rr),'paired_NET':len(z),'dynamic_NET_eur':sum(r['dynamic_net'] for r in z) if z else None,'fixed_NET_same_entries_eur':sum(r['fixed_net'] for r in z) if z else None,'increment_eur':sum(r['dynamic_net']-r['fixed_net'] for r in z) if z else None,'cash_NET_eur':0,'supported_weeks':len(w),'week_paired_means':w,'equal_clock_equal_week_NET_increment':[statistics.mean(v[i] for v in arr) for i in (0,1)] if arr else None,'lower_family15':lower,'temporal_halves':halves,'lead':bool(lower and all(v>0 for v in lower) and all(all(v>0 for v in z) for z in halves)),'alpha_certified':False,'complete_case_selection_bias':'UNRESOLVED_AND_UNSAMPLED_ENTRIES_NOT_IMPUTED','states':dict(Counter(r['state'] for r in rr))}
def portfolio(records,h,name,slots,dynamic=True):
 rr=sorted([r for r in records if r['h']==h and r['policy']==name],key=lambda x:(x['t'],x['sid']));cash=200.;opened=[];selected=[];closed=[];halt=None;peak=cash;dd=0.
 def settle(t):
  nonlocal cash,peak,dd,halt
  unknown=[r['t']+14400 for r in opened if dynamic and r.get('exit') is None and r['t']+14400<=t]
  boundary=min(unknown) if unknown else t
  for r in sorted([r for r in opened if (r.get('exit') if dynamic else r['fixed_exit']) is not None and (r.get('exit') if dynamic else r['fixed_exit'])<=boundary],key=lambda r:((r.get('exit') if dynamic else r['fixed_exit']),r['sid'])):
   net=r.get('dynamic_net') if dynamic else r.get('fixed_net')
   if net is None:halt='FIRST_SELECTED_UNKNOWN_EXIT_OR_COST';return
   cash+=net;peak=max(peak,cash);dd=max(dd,peak-cash);opened.remove(r);closed.append(r)
  if unknown:halt='FIRST_SELECTED_UNKNOWN_EXIT_OR_COST'
 for r in rr:
  settle(r['t'])
  if halt:break
  risk=r.get('stress_risk_eur')
  if risk is None or not r.get('stress_eligible') or len(opened)>=slots or any(x['sid']==r['sid'] for x in opened):continue
  if sum(x['margin_eur'] for x in opened)+r['margin_eur']>.4*cash or sum(x['stress_risk_eur'] for x in opened)+risk>.01*cash:continue
  opened.append(r);selected.append(r)
 if not halt:settle(float('inf'))
 return {'selected':len(selected),'closed':len(closed),'cash_closed_accounting_eur':cash,'closed_cash_drawdown_eur':dd,'halt':halt or 'END','open_positions':len(opened),'selected_by_week':dict(Counter(iso(r['t']) for r in selected)),'closed_by_exit_week':dict(Counter(iso(r.get('exit') if dynamic else r['fixed_exit']) for r in closed)),'MTM_and_execution_failure_risk':'UNRESOLVED','HARD21':False}
