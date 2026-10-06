from __future__ import annotations
import datetime as dt
from collections import Counter,defaultdict,deque
import numpy as np
from .data import START,HORIZONS

class ClockState:
 def __init__(self):self.last=-1
 def accept(self,event):
  if event<=self.last:return False
  self.last=event;return True

def assert_feature_available(feature_complete_event,decision_event):
 if feature_complete_event>decision_event:raise ValueError('future feature unavailable')

def lattice(v,minv,step,maxv):return v>=minv and v<=maxv and (v-minv)%step==0

def pnl(direction,units,entry,exit,conversion):return direction*units*(exit-entry)*conversion

def conversion_graph(info,prices,fresh):
 assets=info['assets'];edges=defaultdict(list)
 for si,(s,m) in enumerate(zip(info['records'],info['metadata'])):
  if m['asset_class']!='Forex (Spot)' or not fresh[si] or not np.isfinite(prices[si]) or prices[si]<=0:continue
  lm=m['current_light_metadata'];base=assets[str(lm['baseAssetId'])];quote=assets[str(lm['quoteAssetId'])]
  edges[base].append((quote,prices[si],s['symbol']));edges[quote].append((base,1/prices[si],s['symbol']))
 def rate(source,target='EUR'):
  if source==target:return 1.
  # BFS prefers direct then minimum-hop lexicographic broker symbol path.
  todo=deque([(source,1.,{source})])
  while todo:
   cur,r,seen=todo.popleft()
   for dest,mult,name in sorted(edges[cur],key=lambda e:(e[2],e[0])):
    if dest in seen:continue
    if dest==target:return r*mult
    todo.append((dest,r*mult,seen|{dest}))
  return None
 return rate

def commission_side(m,assets,price,units,rate):
 f=m['current_full_metadata'];lm=m['current_light_metadata'];quote=assets[str(lm['quoteAssetId'])];base=assets[str(lm['baseAssetId'])]
 qr=rate(quote);ur=rate('USD');raw=int(f.get('preciseTradingCommissionRate',0));typ=int(f.get('commissionType',0));lot=int(f.get('lotSize',0))/100
 if qr is None:return None
 fee=0.
 if raw:
  if typ==2 and ur is not None and lot>0:fee=raw/1e8*units/lot*ur
  elif typ==4 and lot>0:fee=raw/1e8*units/lot*qr
  elif typ==3:fee=raw/1e5/100*price*units*qr
  elif typ==1 and ur is not None:
   br=rate(base,'USD')
   if br is None:return None
   fee=raw/1e8*units*br/1e6*ur
  else:return None
 minimum=int(f.get('preciseMinCommission',0))/1e8
 if minimum:
  mt=int(f.get('minCommissionType',0));mc=quote if mt==2 else str(f.get('minCommissionAsset',''))
  mr=rate(mc)
  if mr is None:return None
  fee=max(fee,minimum*mr)
 return 2*fee # frozen conservative present-commission discovery scenario

def neff(values):
 a=np.abs(np.array(list(values),float));return float(a.sum()**2/(a@a)) if len(a) and a@a>0 else 0.

class Portfolio:
 def __init__(self,info,dd_base):
  self.info=info;self.cash=200.;self.cost=0.;self.gross=0.;self.hwm=200.;self.maxdd=0.;self.dd_duration=0;self.dd_start=None;self.minfree=200.;self.dd_base=dd_base;self.financial_state=0
  self.positions=defaultdict(list);self.pending={};self.clock=ClockState();self.trades=[];self.equity=[];self.counts=Counter();self.by_symbol=defaultdict(float);self.capital_time=defaultdict(float);self.risk_time=defaultdict(float);self.by_week=Counter();self.by_context=defaultdict(float);self.weekly={};self.monthly={};self.maxcost=0.;self.turnover=0.;self.util=0.;self.nmarks=0;self.action_counts=Counter();self.minunit_stresses=[];self.model_health=0;self.last_valuations={};self.rotation_count=0;self.functional_ruin_events=0;self.telemetry=[]
 def quote(self,si,price,rate,range_fraction=0,units_override=None):
  m=self.info['metadata'][si];quote=self.info['assets'][str(m['current_light_metadata']['quoteAssetId'])];conv=rate(quote)
  if conv is None:return None
  bound=self.info['costs'][si]['spread_bound_bps']
  if bound is None:return None
  unit=m['min_volume']/100 if units_override is None else units_override;commission=commission_side(m,self.info['assets'],price,unit,rate)
  if commission is None:return None
  spread=unit*price*conv*bound/20000
  delay=unit*price*conv*max(range_fraction,0)*.25
  margin=2*max(float(m['buy_min_margin_eur']),float(m['sell_min_margin_eur']))*unit/(m['min_volume']/100)
  return {'unit':unit,'conv':conv,'notional':unit*price*conv,'spread':spread,'commission':commission,'delay':delay,'cost':spread+commission+delay,'margin':margin}
 def mark(self,g,prices,rate):
  value=self.cash;margin=0.;stress=0.
  for si,lots in self.positions.items():
   if not lots:continue
   m=self.info['metadata'][si];q=self.info['assets'][str(m['current_light_metadata']['quoteAssetId'])];conv=rate(q)
   if conv is None or not np.isfinite(prices[si]):
    # visible unresolved mark, never silently carry a conversion across a closure.
    self.counts['unresolved_position_marks']+=1
    # Explicit conservative mark bound, not a silent stale conversion fill.
    value+=self.last_valuations.get(si,0.)-sum(l['stress'] for l in lots)
    margin+=sum(l['margin'] for l in lots);stress+=sum(l['stress'] for l in lots)
    continue
   symbol_value=0.
   for lot in lots:
    symbol_value+=pnl(lot['direction'],lot['units'],lot['entry'],prices[si],conv)-lot['exit_cost_reserve']
    margin+=lot['margin'];stress+=lot['stress'];self.capital_time[si]+=lot['margin']*5/60;self.risk_time[si]+=lot['stress']*5/60
   self.last_valuations[si]=symbol_value;value+=symbol_value
  minimum=min((2*max(float(m['buy_min_margin_eur']),float(m['sell_min_margin_eur'])) for m,c in zip(self.info['metadata'],self.info['costs']) if c['spread_bound_bps'] is not None),default=float('inf'))
  if value-margin-stress<minimum:self.functional_ruin_events+=1
  self.hwm=max(self.hwm,value);dd=max(0.,1-value/max(self.hwm,1e-12));self.maxdd=max(self.maxdd,dd)
  if dd>1e-10:
   if self.dd_start is None:self.dd_start=g
   self.dd_duration=max(self.dd_duration,(g-self.dd_start)*5)
  else:self.dd_start=None
  self.minfree=min(self.minfree,value-margin);self.util+=margin/max(value,1e-9);self.nmarks+=1
  # thresholds derived from inner stress/loss scale, deterministic hysteresis.
  levels=np.array([1,2,4,8])*self.dd_base
  state=int(np.sum(dd>=levels))
  if state>self.financial_state:self.financial_state=state
  elif self.financial_state and dd<.75*levels[self.financial_state-1]:self.financial_state=state
  date=(START+dt.timedelta(minutes=g*5)).to_pydatetime();self.weekly[f'{date.isocalendar().year}-W{date.isocalendar().week:02d}']=value;self.monthly[date.strftime('%Y-%m')]=value
  if g%288==0 or not self.equity:self.equity.append({'timestamp_utc':date.isoformat(),'equity_eur':value,'free_margin_eur':value-margin,'financial_state':self.financial_state})
  return value,margin,stress
 def execute(self,g,opens,fresh,rate):
  if not self.clock.accept(g):return
  jobs=self.pending;self.pending={}
  # All reductions settle before any entry. No atomic reversal.
  for si,j in sorted(jobs.items()):
   if j['due']!=g or not fresh[si] or not np.isfinite(opens[si]):
    self.counts['stale_signal_expiry']+=1;continue
   lots=self.positions[si];target=j['target'];remove=max(0,len(lots)-target)
   for _ in range(remove):
    lot=lots[-1];q=self.quote(si,opens[si],rate,j['range'],lot['units'])
    if q is None:self.counts['rejected_conversion_count']+=1;break
    lots.pop();gross=pnl(lot['direction'],lot['units'],lot['entry'],opens[si],q['conv']);self.cash+=gross-q['cost'];self.gross+=gross;self.cost+=q['cost'];self.turnover+=q['notional']
    net=gross-lot['entry_cost']-q['cost'];self.by_symbol[si]+=net;self.by_context[self.info['metadata'][si]['asset_class']]+=net
    action='EXIT' if not lots else 'REDUCE';self.action_counts[action]+=1
    self.trades.append({'event':g,'symbol':self.info['records'][si]['symbol'],'action':action,'direction':lot['direction'],'units':lot['units'],'open_event':lot['open_event'],'gross_pnl_eur':gross,'net_pnl_eur':net,'spread_eur':lot['spread']+q['spread'],'commission_eur':lot['commission']+q['commission'],'delay_eur':lot['delay']+q['delay'],'margin_scenario':'CURRENT_EXPECTED_MIN_MARGIN_X2','financing_state':'INTRADAY_AVOIDED' if lot['open_event']//288==g//288 else 'FINANCING_UNRESOLVED','conversion_state':'CAUSAL_FRESH_M5_PROXY_NOT_EXACT_BID_ASK'})
    if lot['open_event']//288!=g//288:self.counts['financing_unresolved_positions']+=1
  value,margin,stress=self.mark(g,opens,rate)
  # Gather every same-time eligible entry; sort marginal utility, canonical tie.
  additions=[]
  for si,j in sorted(jobs.items()):
   if j['due']!=g or not fresh[si] or not np.isfinite(opens[si]):continue
   if self.positions[si] and self.positions[si][0]['direction']!=j['direction']:
    self.counts['rejected_conflict_count']+=1;continue
   q=self.quote(si,opens[si],rate,j['range'])
   if q is None:self.counts['rejected_conversion_count']+=1;continue
   for ordinal in range(len(self.positions[si]),j['target']):
    m=self.info['metadata'][si]
    q=self.quote(si,opens[si],rate,j['range'],(m['min_volume'] if ordinal==0 else m['step_volume'])/100)
    if q is None:continue
    adjusted=j['lower_return']-j['direction']*np.log(opens[si]/j['signal_price'])
    net=q['notional']*adjusted-2*q['cost']
    additions.append((si,ordinal,j,q,net))
  remaining=additions
  while remaining:
   scored=[]
   for si,ordinal,j,q,net in remaining:
    # Worst common shock: sum tails, plus shared context/currency cluster stress.
    tail=q['notional']*j['tail'];cluster=sum(l['stress'] for sj,ls in self.positions.items() for l in ls if self.info['metadata'][sj]['asset_class']==self.info['metadata'][si]['asset_class'])
    stress_next=stress+tail+.5*cluster
    factor=(1,1.5,2,4,1e9)[self.financial_state]
    utility=net/max(value,1e-9)-factor*(stress_next**2-stress**2)/max(value,1e-9)**2
    # compare capital-time opportunity density; no fixed position/trade cap.
    density=utility/max(q['margin']*j['horizon']/60,1e-9)
    scored.append((density,utility,self.info['records'][si]['symbol_id'],ordinal,si,j,q,net,tail))
   row=sorted(scored,key=lambda a:(-a[0],a[2],a[3]))[0];density,utility,sid,ordinal,si,j,q,net,tail=row
   remaining=[v for v in remaining if not(v[0]==si and v[1]==ordinal)]
   if net<=0:self.counts['rejected_uncertainty_count']+=1;continue
   if utility<=0 or self.financial_state==4 or self.model_health==2:self.counts['rejected_risk_count']+=1;continue
   # free-margin reserve derives from the complete portfolio tail; no percentage rule.
   if value-margin-q['margin'] < stress+tail+2*q['cost']:
    self.counts['rejected_margin_count']+=1;continue
   if ordinal!=len(self.positions[si]):continue
   m=self.info['metadata'][si];volume=m['min_volume']+ordinal*m['step_volume']
   if not lattice(volume,m['min_volume'],m['step_volume'],int(m['current_full_metadata']['maxVolume'])):continue
   # first tranche min units; later tranches step units, broker lattice preserved.
   action='ENTRY' if not self.positions[si] else 'ADD';self.action_counts[action]+=1
   lot={'direction':j['direction'],'units':q['unit'],'entry':opens[si],'entry_cost':q['cost'],'exit_cost_reserve':q['cost'],'margin':q['margin'],'stress':tail,'open_event':g,'spread':q['spread'],'commission':q['commission'],'delay':q['delay']}
   self.positions[si].append(lot);self.cash-=q['cost'];self.cost+=q['cost'];self.turnover+=q['notional'];margin+=q['margin'];stress+=tail;value-=2*q['cost']
   self.counts['executed_entry_count']+=1
   date=(START+dt.timedelta(minutes=g*5)).to_pydatetime();self.by_week[f'{date.isocalendar().year}-W{date.isocalendar().week:02d}']+=1
   self.trades.append({'event':g,'symbol':self.info['records'][si]['symbol'],'action':action,'direction':j['direction'],'units':q['unit'],'cost_eur':q['cost'],'margin_eur':q['margin'],'tail_stress_eur':tail})
  self.minfree=min(self.minfree,value-margin)
 def decide(self,g,close,mu,unc,tail,reliability,ood,fresh,rate,ranges):
  hour=(g%288)*5/60;self.counts['master_universe_count']=1576;self.counts['data_supported_count']=len(close)
  before=self.counts.copy()
  valid=np.isfinite(mu).all(axis=1)&fresh
  self.counts['broad_scored_observations']+=int(valid.sum());self.counts['rich_state_observations']+=int(valid.sum());self.counts['ood_observations']+=int((ood&valid).sum())
  # Financial stress and statistical model stress are separate.
  health_bad=np.mean(ood[valid]) if valid.any() else 1
  self.model_health=2 if health_bad>.75 else 1 if health_bad>.5 else 0
  retain_candidates=[];challengers=[]
  for si in np.flatnonzero(valid):
   self.counts['raw_signal_count']+=4
   gross=abs(mu[si]);self.counts['gross_positive_opportunity_count']+=int((gross>0).sum())
   q=self.quote(si,close[si],rate,ranges[si])
   lower=gross-unc[si]*(1 if self.model_health==0 else 2)
   best=int(np.argmax(lower/np.array(HORIZONS)))
   direction=1 if mu[si,best]>=0 else -1;horizon=HORIZONS[best]*5
   lots=self.positions[si]
   if q is None:
    key='rejected_cost_count' if self.info['costs'][si]['spread_bound_bps'] is None else 'rejected_conversion_count';self.counts[key]+=1
    continue
   self.counts['cost_admissible_opportunity_count']+=4
   unit_tail=q['notional']*float(tail[si,best]);self.minunit_stresses.append(unit_tail)
   if len(self.minunit_stresses)>20000:self.minunit_stresses=self.minunit_stresses[-20000:]
   net=q['notional']*lower[best]-2*q['cost'];positive=net>0
   self.counts['positive_net_opportunity_count']+=int(positive)
   if lots and lots[0]['direction']==direction:retain_candidates.append((net/max(q['margin']*horizon,1e-9),si,net,q['cost']))
   if positive and not lots:challengers.append((net/max(q['margin']*horizon,1e-9),si,net,q['cost']))
   # Intraday law avoids unresolved financing; starts locked after 19 UTC.
   target=len(lots)
   if hour>=19 or g>=self.info['outer_end_index']-288:
    target=0
   elif lots and lots[0]['direction']!=direction:
    target=0;self.counts['rejected_conflict_count']+=1
   elif not positive or self.financial_state==4 or self.model_health==2:
    target=0 if lots else 0
    if not positive:self.counts['rejected_uncertainty_count']+=1
   else:
    # Endogenous broker lattice count, bounded by available capital, not fixed top-K.
    upper=int(max(0,(self.cash+sum(l['margin'] for ls in self.positions.values() for l in ls))/max(q['margin'],1e-9)))
    target=min(upper,int((int(self.info['metadata'][si]['current_full_metadata']['maxVolume'])-self.info['metadata'][si]['min_volume'])/self.info['metadata'][si]['step_volume'])+1)
   # Retain/rotate friction hysteresis: don't churn for tiny mean reversals.
   if lots and hour<19 and positive and direction==lots[0]['direction']:
    retain=q['notional']*lower[best]-q['cost']
    if retain>0:target=max(target,len(lots))
   if target!=len(lots):self.pending[si]={'due':g+1,'target':target,'direction':direction,'lower_return':float(lower[best]),'tail':float(tail[si,best]),'horizon':horizon,'signal_price':close[si],'range':float(ranges[si])}
  if g%288==0:
   self.telemetry.append({'event':g,'master_universe_count':1576,'data_supported_count':len(close),'market_open_count_if_known':int(fresh.sum()),'broad_scored_count':int(valid.sum()),'rich_state_count':int(valid.sum()),'gross_positive_opportunity_count':self.counts['gross_positive_opportunity_count']-before['gross_positive_opportunity_count'],'cost_admissible_opportunity_count':self.counts['cost_admissible_opportunity_count']-before['cost_admissible_opportunity_count'],'positive_net_opportunity_count':self.counts['positive_net_opportunity_count']-before['positive_net_opportunity_count'],'capital_selected_count':sum(bool(lots) for lots in self.positions.values()),'exclusion_reason_counts':{k:self.counts[k]-before[k] for k in self.counts if k.startswith('rejected_')}})
  # One bounded local marginal swap; uplift must pay switching costs and
  # hysteresis. No forced rotation if the incumbent remains superior.
  if retain_candidates and challengers and hour<19:
   worst=sorted(retain_candidates,key=lambda r:(r[0],self.info['records'][r[1]]['symbol_id']))[0]
   best=sorted(challengers,key=lambda r:(-r[0],self.info['records'][r[1]]['symbol_id']))[0]
   if best[0]>worst[0] and best[2]-worst[2]>2*(best[3]+worst[3]):
    si=worst[1];lots=self.positions[si]
    self.pending[si]={'due':g+1,'target':len(lots)-1,'direction':lots[0]['direction'],'lower_return':0.,'tail':0.,'horizon':15,'signal_price':close[si],'range':float(ranges[si])}
    self.rotation_count+=1
  # Liquidate existing symbols even if their forecast becomes missing: orders
  # remain fail-closed if next executable proxy/conversion is unavailable.
  for si,lots in self.positions.items():
   if lots and (not valid[si] or hour>=19):self.pending[si]={'due':g+1,'target':0,'direction':lots[0]['direction'],'lower_return':0.,'tail':0.,'horizon':15,'signal_price':close[si] if np.isfinite(close[si]) else lots[0]['entry'],'range':float(ranges[si]) if np.isfinite(ranges[si]) else 0.}
 def result(self,end_g):
  entries=[t for t in self.trades if t['action'] in ('ENTRY','ADD')];exits=[t for t in self.trades if t['action'] in ('EXIT','REDUCE')]
  eq=self.weekly[next(reversed(self.weekly))] if self.weekly else 200
  syms=sorted({t['symbol'] for t in entries});contexts={self.info['metadata'][i]['asset_class'] for i,s in enumerate(self.info['records']) if s['symbol'] in syms}
  shares=sorted([abs(v) for v in self.by_symbol.values()],reverse=True);s=sum(shares)
  weeks={w:{'entries':self.by_week[w],'pass_floor21':self.by_week[w]>=21} for w in self.weekly};counts=list(self.by_week[w] for w in weeks)
  return {'starting_equity_eur':200.,'terminal_equity_eur':eq,'gross_pnl_eur':self.gross,'conservative_net_pnl_eur':eq-200,'terminal_return_pct':(eq/200-1)*100,'weekly_equity_path':self.weekly,'monthly_equity_path':self.monthly,'max_drawdown_pct':self.maxdd*100,'max_drawdown_duration_minutes':self.dd_duration,'minimum_free_margin_eur':self.minfree,'total_cost_eur':self.cost,'turnover_eur':self.turnover,'capital_utilization_mean_margin_fraction':self.util/max(self.nmarks,1),'opportunity_counts':dict(self.counts),'entries_by_utc_iso_week':weeks,'minimum_entries_per_week':min(counts,default=0),'mean_entries_per_week':float(np.mean(counts)) if counts else 0,'median_entries_per_week':float(np.median(counts)) if counts else 0,'maximum_entries_per_week':max(counts,default=0),'hard21_role':'FLOOR_ONLY_FOR_FINAL_CERTIFICATION;NO_UPPER_CAP_NO_FILLERS','unique_symbols_traded':syms,'unique_contexts_traded':sorted(contexts),'unique_asset_classes_traded':sorted(contexts),'symbol_neff':neff(self.by_symbol.values()),'context_neff':neff(self.by_context.values()),'temporal_neff':neff(np.diff([200]+list(self.weekly.values()))),'capital_time_neff':neff(self.capital_time.values()),'risk_contribution_neff':neff(self.risk_time.values()),'top_contributor_shares':{f'top{k}':sum(shares[:k])/s if s else 0 for k in (1,5,20)},'functional_ruin_events':self.functional_ruin_events,'capital_rotation_decisions':self.rotation_count,'action_counts':dict(self.action_counts),'spread_cost_eur':sum(t['spread_eur'] for t in exits),'commission_cost_eur':sum(t['commission_eur'] for t in exits),'slippage_delay_bound_cost_eur':sum(t['delay_eur'] for t in exits),'open_tranche_count':sum(map(len,self.positions.values())),'closed_trade_count':len(exits),'trades':self.trades,'runtime_breadth_telemetry':self.telemetry,'daily_equity_path':self.equity,'symbol_net_pnl_eur':{self.info['records'][k]['symbol']:v for k,v in self.by_symbol.items()},'context_net_pnl_eur':dict(self.by_context),'independent_opportunity_cluster_count':len({(t['event']//288,self.info['metadata'][next(i for i,s in enumerate(self.info['records']) if s['symbol']==t['symbol'])]['asset_class']) for t in entries}),'financing_state':'AVOIDED_BY_INTRADAY_LAW' if not self.counts['financing_unresolved_positions'] else 'UNRESOLVED_CARRY_OCCURRED','currency_conversion_state':'CAUSAL_COMPLETED_M5_PROXY_FRESH_5MIN_GRAPH_NO_FORWARD_FILL','cost_state':'PREFIX_SAMPLE_MAX_X2_WITH_CURRENT_COMMISSION_X2_CONDITIONAL_DISCOVERY_BOUND','margin_state':'CURRENT_AUTHENTIC_EXPECTED_MIN_MARGIN_X2_DISCOVERY_SCENARIO_NOT_EXACT_HISTORICAL_MARGIN','not_certified':True}
