"""New native-NET side conditioning and cost-tail abstention, no old kernel calls."""
import math,statistics,bisect
from collections import defaultdict,Counter
from datetime import datetime,timezone
import numpy as np
from . import accounts_v1 as a
HORIZONS=(15,60,240)
FAMILIES=('NATIVE_NET_SIDE_COST_CONDITIONING_V1','NATIVE_COST_TAIL_ABSTENTION_V1')
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def finite_mean(v):return statistics.mean(v) if v else None
def prior(bars,t,times=None):
 times=sorted(bars) if times is None else times;i=bisect.bisect_left(times,t);first=max(bisect.bisect_left(times,t-5*86400),i-192);tt=times[first:i]
 if len(tt)<48 or tt[-1]!=t-300:return None
 tt=tt[-192:];zz=[bars[u] for u in tt];prices=[z[3] for z in zz]
 if any(p<=0 for p in prices):return None
 returns=np.diff(np.log(prices))*10000;ranges=[max(0,(z[1]-z[2])/z[3]*10000) for z in zz]
 scale=max(1e-6,statistics.mean(ranges[-48:]));volume=[z[4] for z in zz]
 v=statistics.median(volume[:-12]) if len(volume)>12 else 0
 return {'range_bps':scale,'tail_bps':float(np.quantile(ranges,.95,method='higher')),'signed12':float(sum(returns[-12:]))/max(scale,1e-6),'downside':float(sum(x*x for x in returns if x<0))/max(1e-12,float(sum(returns*returns))),'activity':statistics.mean(volume[-12:])/max(1,v),'reference_close':prices[-1],'prior_rows':len(zz),'last_open':tt[-1]}
def entry(ev,row,f,quotes,g,h):
 t=ev['t'];q=a.point(quotes.get((row['sid'],t)))
 if q is None:return {'state':'ENTRY_QUOTE_UNRESOLVED','eligible':False}
 notional=a.convert(-row['min_units']*q['mid'],row['quote'],'EUR',t,quotes,g)
 spread=a.convert(-row['min_units']*(q['ask']-q['bid']),row['quote'],'EUR',t,quotes,g)
 commissions=[a.commission(row,f,row['min_units'],q[n],t,quotes,g) for n in ('bid','ask')]
 if notional is None or spread is None or any(c is None for c in commissions):return {'state':'ENTRY_FX_OR_COMMISSION_UNRESOLVED','eligible':False}
 notional=-notional
 if not notional>0:return {'state':'INVALID_NOTIONAL','eligible':False}
 cost=-spread+2*max(commissions)+notional*.0004+.10*h/1440
 risk=notional*ev['prior']['tail_bps']/10000*math.sqrt(h/5)+cost
 scale_eur=notional*ev['prior']['range_bps']/10000*math.sqrt(h/5)
 features=[1,min(6,cost/max(scale_eur,1e-9)),min(6,-spread/max(scale_eur,1e-9)),min(2,math.log1p(notional)/10),min(1,row['margin_eur']/80),min(4,ev['prior']['activity'])/2,ev['prior']['downside'],max(-6,min(6,ev['prior']['signed12']))/6]
 return {'state':'ELIGIBLE_CURRENT_PROXY' if risk<=2 and row['margin_eur']<=80 else 'MINIMUM_TICKET_RISK_OR_MARGIN','eligible':risk<=2 and row['margin_eur']<=80,'notional_eur':notional,'cost_eur':cost,'cost_bps':cost/notional*10000,'risk_eur':risk,'margin_eur':row['margin_eur'],'features':features,'cost_bin':int(cost>scale_eur),'historical_risk':'PROXY_NO_STOP_FILL_OR_RUIN_CERTIFICATE'}
def lcb(values):
 if not values:return None
 return statistics.mean(values)-1.645*(statistics.stdev(values) if len(values)>1 else 0)/math.sqrt(len(values))
def prediction(training,x,bin_id):
 if len(training)<128:return None
 z=training[-2048:];yy=np.asarray([r['net_sides'] for r in z]);xx=np.asarray([r['entry']['features'] for r in z]);means=np.mean(yy,axis=0);base=int(np.argmax(means));base_d=1 if base==0 else -1
 base_ok=lcb(yy[:,base].tolist())>0
 ridge=np.linalg.solve(xx.T@xx+10*np.eye(xx.shape[1]),xx.T@yy);mu=np.asarray(x)@ridge;res=yy-xx@ridge;unc=1.645*np.std(res,axis=0,ddof=1)/math.sqrt(len(z));side=int(np.argmax(mu));direct_ok=bool(mu[side]-unc[side]>0)
 bb=[r['net_sides'][base] for r in z if r['entry']['cost_bin']==bin_id];bin_mean=finite_mean(bb);bin_lcb=lcb(bb);loss=float(np.quantile([-v for v in bb],.95,method='higher')) if bb else None
 return {'mature_N':len(z),'baseline_side':base_d,'baseline_admit':bool(base_ok),'baseline_expected_net_eur':float(means[base]),'conditional_side':1 if side==0 else -1,'conditional_expected_net_eur':float(mu[side]),'conditional_admit':direct_ok,'conditional_lower_net_eur':float(mu[side]-unc[side]),'bin_N':len(bb),'bin_expected_net_eur':bin_mean,'bin_lower_net_eur':bin_lcb,'bin_loss95_eur':loss,'bin_admit':bool(base_ok and len(bb)>=32 and bin_lcb>0 and loss<=2)}
def causal_evaluate(events):
 # The information argument contains only entry quantities. Labels enter training only after exit.
 rr=[];pending={h:[] for h in HORIZONS};training={h:[] for h in HORIZONS}
 for t in sorted({r['t'] for r in events}):
  group=[r for r in events if r['t']==t]
  for h in HORIZONS:
   mature=[r for r in pending[h] if r['exit']<t];pending[h]=[r for r in pending[h] if r['exit']>=t];training[h].extend(mature)
  for event in sorted(group,key=lambda r:(r['sid'],r['h'])):
   h=event['h'];en=event['entry'];pred=prediction(training[h],en['features'],en['cost_bin']) if 'features' in en else None
   for fam in FAMILIES:
    side=pred['conditional_side'] if pred and fam==FAMILIES[0] else pred['baseline_side'] if pred else 0
    flag=pred['conditional_admit'] if pred and fam==FAMILIES[0] else pred['bin_admit'] if pred else False
    admit=bool(en.get('eligible') and flag);base=bool(en.get('eligible') and pred and pred['baseline_admit'])
    r={**event,'family':fam,'prediction':pred,'model_side':side,'baseline_side':pred['baseline_side'] if pred else 0,'model_admit':admit,'baseline_admit':base,'predicted_net_eur':pred['conditional_expected_net_eur'] if pred and fam==FAMILIES[0] else pred['bin_expected_net_eur'] if pred else None}
    rr.append(r)
   if event.get('net_sides') is not None:pending[h].append(event)
 return rr
def outcomes(r,scenario):
 z=r.get('accounts',{}).get(scenario)
 if z is None or z[0] is None or z[1] is None or r['prediction'] is None:return None
 model=z[0 if r['model_side']>0 else 1]['net_eur'] if r['model_admit'] else 0.
 base=z[0 if r['baseline_side']>0 else 1]['net_eur'] if r['baseline_admit'] else 0.
 return model,base
def report(rows,weeks):
 vv=[r for r in rows if outcomes(r,'S2_F010_DAY') is not None]
 byclock=defaultdict(list)
 for r in vv:byclock[r['t']].append(outcomes(r,'S2_F010_DAY'))
 byweek=defaultdict(list)
 for t,vals in byclock.items():byweek[iso(t)].append(np.mean(vals,axis=0))
 stats={w:np.mean(byweek[w],axis=0).tolist() if byweek[w] else None for w in weeks}
 ws=[stats[w] for w in weeks if stats[w] is not None];arr=np.asarray([[z[0],z[0]-z[1]] for z in ws]);lower=None;halves=[]
 if len(arr)>=2:halves=[np.mean(arr[:len(arr)//2],axis=0).tolist(),np.mean(arr[len(arr)//2:],axis=0).tolist()]
 if len(arr)>=26:
  rng=np.random.default_rng(20261012);bs=[]
  for _ in range(2000):
   ix=np.concatenate([(np.arange(4)+int(v))%len(arr) for v in rng.integers(0,len(arr),size=math.ceil(len(arr)/4))])[:len(arr)];bs.append(np.mean(arr[ix],axis=0))
  lower=np.quantile(bs,.05/6,axis=0).tolist()
 lead=bool(lower and all(x>0 for x in lower) and all(all(x>0 for x in z) for z in halves))
 scenarios={}
 for name in a.SCENARIOS:
  z=[outcomes(r,name) for r in rows];z=[x for x in z if x is not None]
  scenarios[name]={'paired_evaluable':len(z),'model_net_eur':sum(x[0] for x in z) if z else None,'baseline_net_eur':sum(x[1] for x in z) if z else None,'increment_eur':sum(x[0]-x[1] for x in z) if z else None}
 return {'cohort':len(rows),'model_entries':sum(r['model_admit'] for r in rows),'baseline_entries':sum(r['baseline_admit'] for r in rows),'structural_eligible':sum(r['entry'].get('eligible',False) for r in rows),'mature_predictions':sum(r['prediction'] is not None for r in rows),'priced_model_entries':sum(r['model_admit'] for r in vv),'exit_or_FX_censored':sum(r['prediction'] is not None and outcomes(r,'S2_F010_DAY') is None for r in rows),'supported_weeks':len(ws),'week_paired_means':stats,'equal_clock_equal_week_net_and_increment':np.mean(arr,axis=0).tolist() if len(arr) else None,'lower_one_sided_family6':lower,'temporal_halves':halves,'exploratory_NET_information_lead':lead,'alpha_certified':False,'independent_N':'UNIDENTIFIED_SERIAL_CROSS_ASSET_PRIOR_ADAPTIVE_SELECTION','scenarios':scenarios}
def portfolio(rows,weeks,slots,baseline=False):
 cash=200.;peak=200.;dd=0.;opened=[];selected=[];closed=[];halt=None
 for t in sorted({r['t'] for r in rows}):
  due=sorted([r for r in opened if r['exit']<=t],key=lambda r:(r['exit'],r['sid']))
  for r in due:
   z=r.get('accounts',{}).get('S2_F010_DAY');side=r['baseline_side'] if baseline else r['model_side']
   value=z[0 if side>0 else 1] if z else None
   if value is None:halt='FIRST_SELECTED_UNKNOWN_EXIT';break
   cash+=value['net_eur'];peak=max(peak,cash);dd=max(dd,peak-cash);closed.append(r);opened.remove(r)
  if halt:break
  candidates=[r for r in rows if r['t']==t and (r['baseline_admit'] if baseline else r['model_admit'])]
  candidates.sort(key=lambda r:(-max(0,r['prediction']['baseline_expected_net_eur'] if baseline else r['predicted_net_eur'] or 0)/max(1e-9,r['entry']['cost_eur']+r['entry']['risk_eur']),r['sid']))
  for r in candidates:
   if len(opened)>=slots:break
   if any(v['sid']==r['sid'] for v in opened):continue
   if sum(x['entry']['margin_eur'] for x in opened)+r['entry']['margin_eur']>.4*cash:continue
   if sum(x['entry']['risk_eur'] for x in opened)+r['entry']['risk_eur']>.01*cash:continue
   opened.append(r);selected.append(r)
 if not halt:
  for r in sorted(opened,key=lambda r:(r['exit'],r['sid'])):
   z=r.get('accounts',{}).get('S2_F010_DAY');side=r['baseline_side'] if baseline else r['model_side'];value=z[0 if side>0 else 1] if z else None
   if value is None:halt='FIRST_SELECTED_UNKNOWN_EXIT';break
   cash+=value['net_eur'];peak=max(peak,cash);dd=max(dd,peak-cash);closed.append(r)
 return {'slots':slots,'selected':len(selected),'closed':len(closed),'cash_eur':cash,'closed_cash_drawdown_eur':dd,'halt':halt or 'END','selected_entries_by_complete_week':{w:sum(iso(r['t'])==w for r in selected) for w in weeks},'HARD21_demonstrated':False,'open_risk':'SUM_PRIOR_M5_PROXY_MAX1PCT_CASH;INTRATRADE_MARK_TO_MARKET_FILLS_AND_RUIN_UNKNOWN','selected_receipts':[{'sid':r['sid'],'entry':r['t'],'exit':r['exit'],'h':r['h']} for r in selected]}
