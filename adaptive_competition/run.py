from __future__ import annotations
import argparse,hashlib,json,subprocess,time
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.stats import rankdata
from .data import ROOT,STATE,HORIZONS,START,save,sha
from .models import ForecastModel
from .core import Portfolio,conversion_graph,assert_feature_available

def provenance_guard():
 spec=STATE/'ADAPTIVE_COMPETITION_POLICY_V1_FROZEN_SPEC.json'
 j=json.loads(spec.read_text());assert j['policy_id']=='ADAPTIVE_COMPETITION_POLICY_V1'
 for path,digest in j['implementation_hashes'].items():assert sha((ROOT/path).read_bytes())==digest,path
 return j,sha(spec.read_bytes())

class ForecastDiagnostics:
 def __init__(self):self.queue=defaultdict(list);self.mom=np.zeros((4,6));self.buckets=defaultdict(lambda:[0,0.,0.]);self.ood=defaultdict(lambda:[0,0.,0.]);self.cover=np.zeros((4,3));self.ic=[]
 def predict(self,g,mu,unc,sig,ood,costs):
  # Thinned diagnostic sampling is predeclared; every M5 remains eligible for trades.
  if g%6:return
  for hi,h in enumerate(HORIZONS):
   norm=sig*np.sqrt(h);p=mu[:,hi]/norm;u=unc[:,hi]/norm
   self.queue[g+h].append((g-1,hi,p.copy(),u.copy(),ood.copy(),np.array(costs)))
 def mature(self,g,Y):
  for j,hi,p,u,ood,costs in self.queue.pop(g,[]):
   y=Y[j,:,hi];valid=np.isfinite(p)&np.isfinite(y);a=p[valid];b=y[valid];self.mom[hi]+=np.array([len(a),a.sum(),b.sum(),a@a,b@b,a@b])
   if len(a)>3 and np.std(a)>0 and np.std(b)>0:self.ic.append(float(np.corrcoef(rankdata(a),rankdata(b))[0,1]))
   for si in np.flatnonzero(valid):
    key=f'h{HORIZONS[hi]*5}:abs_mu_bucket{int(np.searchsorted([.05,.1,.25,.5],abs(p[si])))}'
    vals=self.buckets[key];vals[0]+=1;vals[1]+=np.sign(p[si])*y[si];vals[2]+=abs(p[si])
    key=f'h{HORIZONS[hi]*5}:OOD={bool(ood[si])}:cost_admissible={bool(costs[si])}'
    vals=self.ood[key];vals[0]+=1;vals[1]+=p[si]*y[si];vals[2]+=y[si]**2
   self.cover[hi]+=np.array([valid.sum(),np.sum(abs(y[valid]-p[valid])<=u[valid]),np.sum(abs(y[valid]-p[valid])<=2*u[valid])])
 def result(self):
  corr=[]
  for n,sx,sy,xx,yy,xy in self.mom:
   den=np.sqrt(max(xx-sx*sx/max(n,1),0)*max(yy-sy*sy/max(n,1),0));corr.append((xy-sx*sy/max(n,1))/den if den else 0.)
  return {'forecast_observations_by_horizon':self.mom[:,0].astype(int).tolist(),'return_information_coefficient_by_horizon':corr,'mean_cross_sectional_rank_ic':float(np.mean(self.ic)) if self.ic else 0,'forecast_bucket_realized_returns':{k:{'n':n,'mean_signed_normalized_return':s/n if n else 0,'mean_abs_normalized_forecast':p/n if n else 0} for k,(n,s,p) in self.buckets.items()},'uncertainty_calibration':self.cover.tolist(),'uncertainty_interpretation':'MEAN_ESTIMATION_BAND_NOT_FULL_RETURN_PREDICTION_INTERVAL;TAIL=3_RESIDUAL_SD','OOD_and_no_trade_diagnostics':{k:{'n':n,'mean_forecast_return_product':p/n if n else 0,'mean_squared_realized_normalized_return':y/n if n else 0} for k,(n,p,y) in self.ood.items()},'overlap_dependence':'DAILY_CONTEXT_CLUSTERS;RAW_OBSERVATIONS_NOT_INDEPENDENT_REPLICATIONS'}

def load(cache):
 return {name:np.load(cache/(name+'.npy'),mmap_mode='r') for name in ['ohlcv','X','sigma','Y']},json.loads((cache/'info.json').read_text())

def calibrate_dd(arrays,info,model,start):
 # Pre-inner-validation scale: distribution of minimum-lattice forecast downside
 # exposures in the training prefix only, using fresh conversions.
 model.update(start//288);stresses=[]
 for g in range(start-7*288,start,12):
  if g<1:continue
  price=arrays['ohlcv'][g-1,:,3];fresh=np.isfinite(price);rate=conversion_graph(info,price,fresh)
  mu,u,tail,rel,ood=model.predict(arrays['X'][g-1],arrays['sigma'][g-1])
  p=Portfolio(info,1)
  for si in range(len(price)):
   if not np.isfinite(tail[si]).all():continue
   q=p.quote(si,price[si],rate)
   if q is not None:stresses.append(q['notional']*np.max(tail[si])+2*q['cost'])
 if not stresses:
  # If no executable unit exists, finite financial state remains dormant;
  # functional ruin threshold cannot be invented from unavailable economics.
  return 1.,{'source':'NO_COST_CONVERSION_ADMISSIBLE_UNIT_FINANCIAL_STATES_DORMANT','count':0}
 base=float(np.quantile(stresses,.99))/200
 return base,{'source':'TRAINING_PREFIX_Q99_MINIMUM_EXECUTABLE_UNIT_TAIL_PLUS_ROUNDTRIP_COST_DIVIDED_BY_EUR200','count':len(stresses),'threshold_base_fraction':base,'levels':[base,2*base,4*base,8*base]}

def replay(cache,start,end,nonlinear,dd_base=None):
 arrays,info=load(cache);model=ForecastModel(arrays['X'],arrays['Y'],info,nonlinear)
 if dd_base is None:dd_base,ddsource=calibrate_dd(arrays,info,model,start)
 else:ddsource={'source':'FROZEN_INNER_DERIVED','threshold_base_fraction':dd_base}
 p=Portfolio(info,dd_base);diag=ForecastDiagnostics();costok=[c['spread_bound_bps'] is not None for c in info['costs']]
 ohlcv=arrays['ohlcv'];begin=time.time()
 # Portfolio initializes only once. Model reconstructs itself from bounded,
 # matured trailing data at the first timestamp of this replay.
 for g in range(start,end):
  if g%288==0:
   model.update(g//288)
   if g%(7*288)==0:print('replay day',g//288,'/',end//288,'cash',round(p.cash,6),'entries',p.counts['executed_entry_count'],'seconds',round(time.time()-begin,1),flush=True)
  opens=ohlcv[g,:,0];closed=ohlcv[g-1,:,3];fresh=np.isfinite(closed);openfresh=np.isfinite(opens)&fresh
  # current executable open and already-complete conversion legs at event g;
  # conversion observations have explicit <=5m freshness, never weekend carry.
  rate=conversion_graph(info,closed,fresh)
  p.execute(g,opens,openfresh,rate)
  diag.mature(g,arrays['Y'])
  assert_feature_available(g,g)
  mu,unc,tail,rel,ood=model.predict(arrays['X'][g-1],arrays['sigma'][g-1])
  ranges=(ohlcv[g-1,:,1]-ohlcv[g-1,:,2])/closed
  p.decide(g,closed,mu,unc,tail,rel,ood,fresh,rate,ranges)
  diag.predict(g,mu,unc,arrays['sigma'][g-1],ood,costok)
 # No retrospective final liquidation. Intraday cutoff empties positions before
 # end if executable events exist. Any unresolved residual exposure is explicit.
 result=p.result(end);result['forecasting']=diag.result();result['drawdown_calibration']=ddsource
 result['elapsed_seconds']=time.time()-begin;result['replay_start_bar_index']=start;result['replay_end_bar_index_exclusive']=end
 result['model_classes']=['REGULARIZED_LINEAR_BASELINE','REGULARIZED_NONLINEAR_BASIS_LINEAR'] if nonlinear else ['REGULARIZED_LINEAR_BASELINE']
 result['functional_ruin']={'state':'COST_FEASIBLE_UNITS_AVAILABLE' if costok.count(True) else 'NO_COST_ADMISSIBLE_EXECUTION_SET','definition':'EQUITY_MINUS_PORTFOLIO_STRESS_BELOW_EVERY_AVAILABLE_MINIMUM_MARGIN_UNIT;NO_ARBITRARY_EQUITY_THRESHOLD','cost_supported_count':costok.count(True)}
 result['telemetry_semantics']={'market_open_count':'KNOWN_BY_CURRENT_OBSERVED_COMPLETED_BAR;NOT_EXACT_HISTORICAL_SCHEDULE','master':1576,'data_supported':145,'cost_supported':costok.count(True),'capital_selected_count':result['opportunity_counts'].get('executed_entry_count',0)}
 return result

def inner(cache):
 spec,spec_hash=provenance_guard();start=56*288;end=91*288
 results=[]
 for ci,nonlinear in enumerate([False,True]):
  result=replay(cache,start,end,nonlinear);save(f'INNER_CONFIG_{ci}_ECONOMIC_TRACE_V1.json',result)
  # complete predeclared configs: economic growth penalized by drawdown and
  # unresolved financing. Ties prefer compact baseline; no extension.
  utility=np.log(max(result['terminal_equity_eur'],1e-9)/200)-result['max_drawdown_pct']/100
  if result['opportunity_counts'].get('financing_unresolved_positions',0):utility=-1e9
  results.append({'configuration':ci,'nonlinear':nonlinear,'utility':float(utility),'terminal_equity_eur':result['terminal_equity_eur'],'max_drawdown_pct':result['max_drawdown_pct'],'entries':result['opportunity_counts'].get('executed_entry_count',0),'dd_base':result['drawdown_calibration'].get('threshold_base_fraction',1.),'trace_sha256':sha((STATE/f'INNER_CONFIG_{ci}_ECONOMIC_TRACE_V1.json').read_bytes())})
 chosen=sorted(results,key=lambda r:(-r['utility'],r['configuration']))[0]
 ledger={'configuration_count':2,'maximum_allowed':12,'predeclared_complete_configurations':results,'selected':chosen,'inner_only':True,'folds':[{'start_day':56,'end_day':70},{'start_day':70,'end_day':91}],'purge_law':'EXACT_LABEL_MATURITY_BEFORE_REFIT;240MIN_MAX_LABEL_PLUS_COMPLETED_BAR;NO_RANDOM_SHUFFLE','validation_account':'ONE_CONTINUOUS_INNER_EUR200_PER_COMPLETE_CONFIGURATION','frozen_spec_hash':spec_hash}
 save('INNER_SELECTION_LEDGER_V1.json',ledger)
 spec['selected_inner_configuration']=chosen;spec['inner_selection_ledger_sha256']=sha((STATE/'INNER_SELECTION_LEDGER_V1.json').read_bytes());spec['outer_policy_frozen']=True
 finalhash=save('ADAPTIVE_COMPETITION_POLICY_V1_FROZEN_SPEC.json',spec)
 print('INNER_COMPLETE outer frozen policy SHA256',finalhash,flush=True)

def outer(cache):
 spec,spec_hash=provenance_guard();assert spec['outer_policy_frozen'];selected=spec['selected_inner_configuration']
 arm=json.loads((STATE/'OUTER_EXECUTION_ARM_V1.json').read_text());assert arm['exact_policy_spec_hash']==spec_hash
 assert not (STATE/'ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json').exists(),'outer already persisted; do not rerun'
 opening=STATE/'OUTER_OPENING_LOCK_V1.json';assert not opening.exists(),'opening lock exists; recover exact attempt rather than rerun'
 save(opening.name,{'policy_hash':spec_hash,'arm':arm,'outer_opened':True,'protected_forward_opened':False,'confirmation_opened':False})
 result=replay(cache,91*288,len(np.load(cache/'sigma.npy',mmap_mode='r')),selected['nonlinear'],selected['dd_base'])
 result.update({'policy_id':spec['policy_id'],'exact_policy_spec_hash':spec_hash,'exact_source_head':arm['exact_source_head'],'exact_data_hashes':spec['data_hashes'],'protected_forward_opened':False,'confirmation_opened':False,'outer_economic_replay_actually_ran':True,'outer_type':'PREQUENTIAL_DEVELOPMENT','inner_configuration_count':2})
 save('ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json',result)
 print('OUTER_RAW_RESULT_PERSISTED',result['terminal_equity_eur'],result['gross_pnl_eur'],result['conservative_net_pnl_eur'],flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['inner','outer']);parser.add_argument('--cache',type=Path,required=True);a=parser.parse_args()
 {'inner':inner,'outer':outer}[a.phase](a.cache)
