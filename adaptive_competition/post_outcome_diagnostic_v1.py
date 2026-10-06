"""Read-only reconstruction of frozen forecast heads. Never calls replay/decide/execute.
All temporary observation bytes stay private; only aggregate diagnostics published.
"""
import json,gzip,zipfile,hashlib,argparse,time
from pathlib import Path
from collections import defaultdict
import numpy as np
from .run import load,provenance_guard
from .models import ForecastModel
from .core import conversion_graph,commission_side,Portfolio
from .data import STATE,HORIZONS,HASHES,INNER_END,save,verify_zip
Q=[.5,.75,.9,.95,.99,.999,1.]
QN=['p50','p75','p90','p95','p99','p99_9','maximum']
NAMES=['forecast_nonzero_count','uncertainty_adjusted_positive_count','cost_supported_count','conversion_supported_count','positive_after_spread_only_count','positive_after_spread_plus_commission_count','positive_after_spread_plus_commission_plus_delay_count','final_frozen_positive_net_count']
DT=np.dtype([('symbol','u1'),('horizon','u1'),('ood','u1'),('health','u1'),('mu','f8'),('unc','f8'),('lower','f8')])
CT=np.dtype([('symbol','u1'),('horizon','u1'),('ood','u1'),('health','u1'),('gross','f8'),('spread','f8'),('commission','f8'),('delay','f8'),('cost','f8'),('ratio','f8')])
def quant(a):
 a=np.asarray(a);a=a[np.isfinite(a)]
 return dict(zip(QN,map(float,np.quantile(a,Q)))) if len(a) else {k:None for k in QN}
def quote(info,si,price,rate,r):
 m=info['metadata'][si];c=rate(info['assets'][str(m['current_light_metadata']['quoteAssetId'])])
 if c is None:return None
 unit=m['min_volume']/100;comm=commission_side(m,info['assets'],price,unit,rate)
 if comm is None:return None
 notional=unit*price*c
 return notional,notional*info['costs'][si]['spread_bound_bps']/10000,2*comm,notional*max(r,0)*.5

def augment_positive_funnel(scratch,info):
 h=np.memmap(scratch/'heads.bin',dtype=DT,mode='r');c=np.memmap(scratch/'cost.bin',dtype=CT,mode='r')
 costs=np.array([v['spread_bound_bps'] is not None for v in info['costs']]);by={};agg=np.zeros(4,dtype=int)
 for i,H in enumerate([15,30,60,240]):
  hp=h[h['horizon']==i];cp=c[c['horizon']==i];pos=hp['lower']>0;costpos=int((pos&costs[hp['symbol']]).sum());convpos=int((cp['gross']>0).sum())
  v={'positive_after_uncertainty_all145':int(pos.sum()),'positive_after_uncertainty_cost_supported':costpos,'positive_after_uncertainty_cost_and_conversion_supported':convpos,'positive_cost_supported_but_conversion_unresolved':costpos-convpos};by[str(H)]=v;agg+=list(v.values())
 name='ADAPTIVE_V1_POST_OUTCOME_CAUSAL_GATE_DECOMPOSITION_V1.json';j=json.loads((STATE/name).read_text());j['sequential_positive_funnel_by_horizon']=by;j['sequential_positive_funnel_aggregate']=dict(zip(v,map(int,agg)));j['dominant_first_gate']='UNCERTAINTY_RELATIVE_TO_FROZEN_FORECAST_MAGNITUDE';j['remaining_admissible_positive_heads_eliminated_by']='FROZEN_SPREAD_COMPONENT_ONLY';save(name,j)
 name='ADAPTIVE_V1_BREAK_EVEN_RATIO_DIAGNOSTIC_V1.json';j=json.loads((STATE/name).read_text());j['positive_lower_return_admissible_subset']={'count':int((c['gross']>0).sum()),'ratio_quantiles':quant(c['ratio'][c['gross']>0])};save(name,j)

 pos=h['lower']>0;zero=h['unc']==0;unresolved=~costs[h['symbol']]
 init={'positive_lower_return_zero_uncertainty_count':int((pos&zero).sum()),'positive_cost_unresolved_zero_uncertainty_count':int((pos&zero&unresolved).sum()),'positive_cost_unresolved_nonzero_uncertainty_count':int((pos&~zero&unresolved).sum()),'semantics':'FROZEN_FIT_WINDOW_LEAVES_SE_ZERO_FOR_COUNT_LT24;ALGEBRAIC_POSITIVE_LOWER_IS_NOT_EVIDENCE_OF_ZERO_TRUE_UNCERTAINTY;NO_CHANGE_TO_HISTORICAL_LAW'}
 name='ADAPTIVE_V1_POST_OUTCOME_CAUSAL_GATE_DECOMPOSITION_V1.json';j=json.loads((STATE/name).read_text());j['initialization_uncertainty_audit']=init;save(name,j)
 name='ADAPTIVE_V1_COST_COVERAGE_GAP_DIAGNOSTIC_V1.json';j=json.loads((STATE/name).read_text());j['initialization_uncertainty_audit']=init
 for record in j['symbols']:
  si=next(i for i,r in enumerate(info['records']) if r['symbol']==record['symbol']);sel=pos&(h['symbol']==si)
  record['positive_lower_return_zero_initialized_uncertainty_count']=int((sel&zero).sum());record['positive_lower_return_nonzero_uncertainty_count']=int((sel&~zero).sum())
  record['information_gain_priority_group']='POSITIVE_LOWER_NONZERO_UNCERTAINTY_COST_MISSING' if record['positive_lower_return_nonzero_uncertainty_count'] else 'COLD_START_UNCERTAINTY_SUPPORT_UNRESOLVED_AND_COST_MISSING' if record['positive_lower_return_zero_initialized_uncertainty_count'] else 'SUPPORTED_HISTORY_COST_MISSING_NO_POSITIVE_LOWER_RETURN'
 j['information_gain_priority_groups']=['POSITIVE_LOWER_NONZERO_UNCERTAINTY_COST_MISSING:resolve_cost_sign_first_within_outcome_blind_breadth_plan','COLD_START_UNCERTAINTY_SUPPORT_UNRESOLVED_AND_COST_MISSING:resolve_support_and_uncertainty_before_claiming_edge','SUPPORTED_HISTORY_COST_MISSING_NO_POSITIVE_LOWER_RETURN:structural_breadth_coverage_no_profit_ranking'];j['cost_unresolved_symbols_with_positive_lower_and_nonzero_uncertainty_count']=sum(r['positive_lower_return_nonzero_uncertainty_count']>0 for r in j['symbols']);save(name,j)


def main(cache,data,scratch):
 spec,sh=provenance_guard();assert not spec['selected_inner_configuration']['nonlinear'];assert spec['frozen_cost_stress_ladder']==[1,1.5,2]
 immutable={p:hashlib.sha256((STATE/p).read_bytes()).hexdigest() for p in ['ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json','ADAPTIVE_COMPETITION_POLICY_V1_FROZEN_SPEC.json']}
 raw=json.loads((STATE/'ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json').read_text())
 for name,h in HASHES.items():assert hashlib.sha256((data/name).read_bytes()).hexdigest()==h
 a,info=load(cache);model=ForecastModel(a['X'],a['Y'],info,False);scratch.mkdir(exist_ok=True)
 counts=np.zeros((4,8),dtype=np.int64);gap=np.zeros((145,4),dtype=np.int64);sc=np.zeros((145,4),dtype=np.int64)
 selected=0;scope=0;convfail=0;streamhash=hashlib.sha256();t=time.time();checks=0
 costs=np.array([c['spread_bound_bps'] is not None for c in info['costs']])
 with (scratch/'heads.bin').open('wb') as fa,(scratch/'cost.bin').open('wb') as fc:
  for day in range(91,info['T']//288):
   model.update(day);heads=[];cs=[]
   for g in range(day*288,(day+1)*288):
    price=a['ohlcv'][g-1,:,3];fresh=np.isfinite(price);rate=conversion_graph(info,price,fresh)
    mu,u,tail,rel,ood=model.predict(a['X'][g-1],a['sigma'][g-1]);valid=np.isfinite(mu).all(axis=1)&fresh
    hb=np.mean(ood[valid]) if valid.any() else 1;health=2 if hb>.75 else 1 if hb>.5 else 0
    lower=abs(mu)-u*(1 if health==0 else 2);r=(a['ohlcv'][g-1,:,1]-a['ohlcv'][g-1,:,2])/price
    si=np.flatnonzero(valid);v=np.empty(len(si)*4,DT);v['symbol']=np.repeat(si,4);v['horizon']=np.tile(np.arange(4),len(si));v['ood']=np.repeat(ood[si],4);v['health']=health
    v['mu']=abs(mu[si]).ravel();v['unc']=u[si].ravel();v['lower']=lower[si].ravel();heads.append(v);streamhash.update(v.tobytes())
    counts[:,0]+=(abs(mu[si])>0).sum(axis=0);counts[:,1]+=(lower[si]>0).sum(axis=0)
    scope+=int(costs[si].sum());counts[:,2]+=int(costs[si].sum())
    for s in si:
     if not costs[s]:gap[s]+=(lower[s]>0);continue
     q=quote(info,s,price[s],rate,r[s])
     if q is None:convfail+=1;continue
     notional,spread,comm,delay=q;total=spread+comm+delay;gross=notional*lower[s]
     if checks<30:
      old=Portfolio(info,1).quote(s,price[s],rate,r[s]);assert np.isclose(total,2*old['cost'],rtol=1e-14);assert np.isclose(notional,old['notional']);checks+=1
     counts[:,3]+=1;counts[:,4]+=(gross>spread);counts[:,5]+=(gross>spread+comm);counts[:,6]+=(gross>total)
     best=np.argmax(lower[s]/np.array(HORIZONS));selected+=int(gross[best]>total);counts[best,7]+=int(gross[best]>total)
     z=np.empty(4,CT);z['symbol']=s;z['horizon']=np.arange(4);z['ood']=ood[s];z['health']=health;z['gross']=gross;z['spread']=spread;z['commission']=comm;z['delay']=delay;z['cost']=total;z['ratio']=gross/total if total>0 else np.nan;cs.append(z)
     sc[s]+=(gross>total)
   np.concatenate(heads).tofile(fa)
   if cs:np.concatenate(cs).tofile(fc)
   if day%14==0:print('read-only forecast diagnostic day',day,'seconds',round(time.time()-t),flush=True)
 assert int(counts[:,0].sum())==raw['opportunity_counts']['raw_signal_count']
 assert int(counts[:,3].sum())==raw['opportunity_counts']['cost_admissible_opportunity_count']
 assert selected==raw['opportunity_counts']['positive_net_opportunity_count']
 h=np.memmap(scratch/'heads.bin',dtype=DT,mode='r');c=np.memmap(scratch/'cost.bin',dtype=CT,mode='r')
 common={'policy_id':spec['policy_id'],'exact_policy_spec_hash':sh,'historical_raw_result_sha256':immutable['ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json'],'source_head':'1247015532d748b5d02aa97b850c999e10ee4aad','mode':'READ_ONLY_COUNTERFACTUAL_FORECAST_RECONSTRUCTION_NOT_POLICY_REPLAY','new_economic_outcome':False,'search_budget_consumed':0,'protected_forward_opened':False,'confirmation_opened':False,'orders_placed':False,'forecast_stream_sha256':streamhash.hexdigest(),'observations_not_independent':True,'verified_raw_archive_hashes':HASHES,'derived_cache_hashes':{name:hashlib.file_digest((cache/(name+'.npy')).open('rb'),'sha256').hexdigest() for name in ['X','Y','sigma','ohlcv']},'diagnostic_implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 def emit(name,d):save(name,{**common,**d})
 totals={k:float(c[k].sum()) for k in ['spread','commission','delay','cost']};sums=totals['cost']
 emit('ADAPTIVE_V1_POST_OUTCOME_CAUSAL_GATE_DECOMPOSITION_V1.json',{'stage_counts_aggregate':dict(zip(NAMES,map(int,counts.sum(axis=0)))),'stage_counts_by_horizon':{str(hh*5):dict(zip(NAMES,map(int,counts[i]))) for i,hh in enumerate(HORIZONS)},'semantics':{'historical_gross_positive_opportunity_count':'NONZERO_FORECAST_HEAD_COUNT_ABS_MU_GT_ZERO_NOT_PROVEN_ECONOMIC_OPPORTUNITY','cost_supported_count':'SPREAD_EVIDENCE_AVAILABLE_INDEPENDENT_OF_UNCERTAINTY','conversion_supported_count':'SPREAD_PLUS_TYPED_COMMISSION_AND_CAUSAL_EUR_CONVERSION_ADMISSIBLE_INDEPENDENT_OF_UNCERTAINTY','cost_survival':'POSITIVE_LOWER_RETURN_ON_CONVERSION_ADMISSIBLE_MINIMUM_VOLUME_HEAD','final_frozen_positive_net_count':'ONLY_ARGMAX_LOWER_RETURN_PER_BAR_HORIZON_SELECTED_BY_FROZEN_POLICY;NOT_SUM_OF_ALL_HEADS','uncertainty_multiplier':'1_NORMAL_HEALTH_ELSE_2;HEALTH_FROM_SAME_TIMESTAMP_OOD_FRACTION'},'cost_supported_symbol_decisions':scope,'conversion_unresolved_symbol_decisions':convfail,'counterfactual_counts':{'survives_uncertainty_only':int(counts[:,1].sum()),'survives_uncertainty_only_on_cost_conversion_scope':int((c['gross']>0).sum()),'survives_uncertainty_plus_spread':int(counts[:,4].sum()),'survives_uncertainty_plus_spread_plus_commission':int(counts[:,5].sum()),'survives_full_frozen_cost':int(counts[:,6].sum())},'cost_component_attribution':{'total_over_candidate_heads_eur':totals,'component_shares':{k:totals[k]/sums for k in ['spread','commission','delay']},'not_actual_paid_costs':True},'reconstruction_checks':{'historical_counts_match':True,'pure_quote_matches_frozen_quote':checks,'policy_trading_methods_called':False}})
 def distribution(hh,cc):return {'mu_absolute_quantiles':quant(hh['mu']),'uncertainty_quantiles':quant(hh['unc']),'lower_return_quantiles':quant(hh['lower']),'uncertainty_adjusted_gross_eur_quantiles':quant(cc['gross']),'full_cost_eur_quantiles':quant(cc['cost']),'forecast_to_cost_ratio_quantiles':quant(cc['ratio']),'fraction_lower_return_positive':float(np.mean(hh['lower']>0)) if len(hh) else None,'fraction_above_cost_break_even':float(np.mean(cc['ratio']>1)) if len(cc) else None,'forecast_head_count':len(hh),'cost_conversion_head_count':len(cc)}
 groups={}
 for key,labels in [('symbol',range(145)),('horizon',range(4)),('OOD_state',range(2)),('model_health_state',range(3))]:
  field={'OOD_state':'ood','model_health_state':'health'}.get(key,key);groups[key]={}
  for label in labels:
   sel=c[field]==label;name=info['records'][label]['symbol'] if key=='symbol' else str(HORIZONS[label]*5) if key=='horizon' else str(label)
   groups[key][name]={'count':int(sel.sum()),'ratio_quantiles':quant(c['ratio'][sel])}
 ci=np.array([info['contexts'].index(m['asset_class']) for m in info['metadata']]);groups['asset_class_or_broker_context']={ctx:{'count':int((ci[c['symbol']]==i).sum()),'ratio_quantiles':quant(c['ratio'][ci[c['symbol']]==i])} for i,ctx in enumerate(info['contexts'])}
 emit('ADAPTIVE_V1_BREAK_EVEN_RATIO_DIAGNOSTIC_V1.json',{'aggregate':distribution(h,c),'by_horizon':{str(hh*5):distribution(h[h['horizon']==i],c[c['horizon']==i]) for i,hh in enumerate(HORIZONS)},'ratio_groupings':groups,'R_definition':'UNCERTAINTY_ADJUSTED_GROSS_EUR_DIVIDED_BY_FULL_FROZEN_ROUND_TRIP_COST_EUR;NEGATIVE_VALUES_RETAINED;ONLY_COST_CONVERSION_SUPPORTED_SCOPE','missing_costs_never_imputed':True})
 ladder=[]
 for mult in [1.,1.5,2.]:
  ok=c['gross']>mult*c['cost'];ids=set(map(int,c['symbol'][ok]));ladder.append({'multiplier':mult,'uncertainty_adjusted_positive_count':int(counts[:,1].sum()),'uncertainty_adjusted_positive_count_on_admissible_scope':int((c['gross']>0).sum()),'positive_net_count':int(ok.sum()),'symbols_with_any_positive_net_opportunity':[info['records'][s]['symbol'] for s in sorted(ids)],'contexts_with_any_positive_net_opportunity':sorted({info['metadata'][s]['asset_class'] for s in ids}),'break_even_ratio_quantiles':quant(c['ratio']/mult),'approximate_opportunity_density_per_admissible_head':float(ok.mean()),'actual_trading_pnl_claim':False})
 emit('ADAPTIVE_V1_FROZEN_COST_STRESS_LADDER_RESULT_V1.json',{'frozen_ladder':[1.,1.5,2.],'results':ladder,'scope':'ALL_AVAILABLE_HORIZON_CANDIDATE_HEADS;COST_SCALING_ONLY;NO_EXECUTION_OR_ACCOUNT_SIMULATION'})
 records=[]
 for si in np.flatnonzero(~costs):
  records.append({'symbol':info['records'][si]['symbol'],'asset_class':info['metadata'][si]['asset_class'],'positive_lower_return_count':int(gap[si].sum()),'by_horizon':dict(zip(map(lambda x:str(x*5),HORIZONS),map(int,gap[si]))),'information_gain_priority_group':'POSITIVE_LOWER_RETURN_COST_MISSING' if gap[si].sum() else 'SUPPORTED_HISTORY_COST_MISSING_NO_POSITIVE_LOWER_RETURN'})
 emit('ADAPTIVE_V1_COST_COVERAGE_GAP_DIAGNOSTIC_V1.json',{'cost_unresolved_symbols':117,'cost_unresolved_symbols_with_positive_lower_return_count':sum(r['positive_lower_return_count']>0 for r in records),'observations_positive_before_cost_but_unmeasurable_after_cost':int(gap.sum()),'symbols':records,'asset_class_distribution':{ctx:{'symbols':sum(r['asset_class']==ctx and r['positive_lower_return_count']>0 for r in records),'positive_observations':sum(r['positive_lower_return_count'] for r in records if r['asset_class']==ctx)} for ctx in info['contexts']},'horizon_distribution':dict(zip([str(x*5) for x in HORIZONS],map(int,gap.sum(axis=0)))),'information_gain_priority_groups':['POSITIVE_LOWER_RETURN_COST_MISSING:measure_cost_to_resolve_sign','SUPPORTED_HISTORY_COST_MISSING_NO_POSITIVE_LOWER_RETURN:lower_immediate_sign_resolution_information_gain'],'ranking_law':'STRUCTURAL_COST_MISSINGNESS_PLUS_FORECAST_UNCERTAINTY_SIGN;NO_OUTER_PNL;GROUPS_NOT_PERMANENT_SYMBOL_SELECTION;ALL145_RETAINED'})
 friction=defaultdict(list)
 for name in list(HASHES)[2:]:
  z=verify_zip(data/name)
  for fn in z.namelist():
   if fn.startswith('derived/') and fn.endswith('.jsonl.gz'):
    for line in gzip.decompress(z.read(fn)).splitlines():
     j=json.loads(line)
     for row in j['rows']:
      if row['boundary_ms']>=INNER_END.value//1000000:continue
      for key in ('d0s','d1s','d5s','d30s'):
       q=row[key]
       if q.get('fresh') and q.get('spread_bps') is not None and q['spread_bps']>=0:friction[j['symbol']].append(q['spread_bps'])
 severity=[]
 for si in np.flatnonzero(costs):
  symbol=info['records'][si]['symbol'];vals=friction[symbol];qq=np.quantile(vals,[0,.25,.5,.75,.9,.95,1]);bound=info['costs'][si]['spread_bound_bps'];assert bound==2*max(vals);assert len(vals)==info['costs'][si]['prefix_fresh_sample_count']
  severity.append({'symbol':symbol,'prefix_fresh_sample_count':len(vals),**dict(zip(['minimum_authentic_spread_bps','p25_authentic_spread_bps','median_authentic_spread_bps','p75_authentic_spread_bps','p90_authentic_spread_bps','p95_authentic_spread_bps','maximum_authentic_spread_bps'],map(float,qq))),'frozen_v1_spread_bound_bps':bound,'ratio_frozen_bound_to_median':bound/qq[2] if qq[2]>0 else None,'ratio_frozen_bound_to_p95':bound/qq[5] if qq[5]>0 else None})
 emit('ADAPTIVE_V1_FRICTION_BOUND_SEVERITY_AUDIT_V1.json',{'symbol_count':28,'symbols':severity,'bound_to_median_ratio_quantiles':quant([x['ratio_frozen_bound_to_median'] for x in severity]),'bound_to_p95_ratio_quantiles':quant([x['ratio_frozen_bound_to_p95'] for x in severity]),'semantics':'AUTHENTIC_PREFIX_SAMPLES;CORRELATED_EVENT_OFFSETS_NOT_INDEPENDENT;MAX_X2_DISCOVERY_ENVELOPE_NOT_EXACT_HISTORICAL_OUTER_COST','frozen_bound_changed':False})
 augment_positive_funnel(scratch,info)
 for p,digest in immutable.items():assert hashlib.sha256((STATE/p).read_bytes()).hexdigest()==digest
 print('DIAGNOSTICS_COMPLETE',counts.tolist(),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--scratch',type=Path,required=True);a=p.parse_args();main(a.cache,a.data,a.scratch)
