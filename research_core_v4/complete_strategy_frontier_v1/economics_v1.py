"""Native cost feasibility references, not return predictors or authentic future fills."""
import math,statistics
from collections import Counter,defaultdict
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as a
SCENARIOS={'S0_F0':(0,0),'S2_F010':(2,.1),'S5_F010':(5,.1),'S2_F100':(2,1)}
def quote(sid,t,bid,ask):
 return {'symbol_id':sid,'boundary_ms':int(t*1000),'hypothetical_constant_spread_exit':True,'sides':{n:{'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':int(t*1000),'price':v,'age_ms':0,'source_has_more':False} for n,v in [('bid',bid),('ask',ask)]}}
def hurdles(d,row,f,t,quotes,g,slip,fund):
 q=a.point(quotes.get((row['sid'],t)))
 if q is None:return None
 context={(sid,tm):value for (sid,tm),value in quotes.items() if tm==t}
 def net(shift):
  zz=dict(context);zz[row['sid'],t+.001]=quote(row['sid'],t+.001,q['bid']+d*shift,q['ask']+d*shift)
  # Conversion chains retain actual ENTRY quotes; hypothetical future FX is a named reference.
  for (sid,tm),value in context.items():
   if tm==t:zz[sid,t+.001]=zz.get((sid,t+.001),value)
  z=a.account(d,row,f,t,t+.001,.5,zz,g,slip,fund)
  return z['net_eur'] if z else None
 z=net(0)
 if z is None:return None
 lo=0.;hi=q['mid']*.01
 if d<0:hi=min(hi,q['bid']*.9)
 for _ in range(7):
  v=net(hi)
  if v is None:return None
  if v>=0:break
  hi=min(hi*2,q['bid']*.9) if d<0 else hi*2
 else:return {'flat_cost_eur':-z,'break_even_bps':None,'state':'ROOT_NOT_BRACKETED'}
 for _ in range(28):
  mid=(lo+hi)/2
  if net(mid)>=0:hi=mid
  else:lo=mid
 return {'flat_cost_eur':-z,'break_even_bps':hi/q['mid']*10000,'break_even_native_price_move':hi,'state':'CURRENT_TERMS_FIXED_SPREAD_FX_REFERENCE'}
def stats(vals):
 vals=[x for x in vals if x is not None];return {'N':len(vals),'median':statistics.median(vals) if vals else None,'min':min(vals) if vals else None,'max':max(vals) if vals else None,'mean':statistics.mean(vals) if vals else None}
def lattice_units(rowA,fA,rowB,fB):
 steps=[int(f['stepVolume']) for f in (fA,fB)];minimum=max(int(f['minVolume']) for f in (fA,fB))
 if any(s<=0 for s in steps):return None
 common=math.lcm(*steps);volume=math.ceil(minimum/common)*common
 if any(volume>int(f['maxVolume']) for f in (fA,fB)):return None
 return volume/100

def evaluate(full):
 cat=full['catalog'];rows=full['all_identity_status'];byid={r['sid']:r for r in rows};g=a.graph(rows);quotes={(int(q['symbol_id']),int(q['boundary_ms'])/1000):q for q in full['raw_quote_receipts']};frames={}
 for r in full['events']:frames.setdefault((r['sid'],r['t']),r)
 details=[]
 for (sid,t),r in sorted(frames.items(),key=lambda z:(z[0][1],z[0][0])):
  row=byid[sid];f=cat['full'][str(sid)];q=a.point(quotes.get((sid,t)));values={};notional=a.convert(-row['min_units']*q['mid'],row['quote'],'EUR',t,quotes,g) if q else None
  for name,(slip,fund) in SCENARIOS.items():values[name]=[hurdles(d,row,f,t,quotes,g,slip,fund) for d in (1,-1)]
  main=values['S2_F010'];worst=values['S5_F010'];range_eur=-notional*r['prior']['range_bps']/10000 if notional is not None else None
  cost=max(z['flat_cost_eur'] for z in main) if all(z for z in main) else None;stress_cost=max(z['flat_cost_eur'] for z in worst) if all(z for z in worst) else None;stress=3*range_eur+stress_cost if range_eur is not None and stress_cost is not None else None
  regime='LE5BPS' if r['prior']['range_bps']<=5 else '5_TO20BPS' if r['prior']['range_bps']<=20 else 'GT20BPS'
  state='ENTRY_QUOTE_NA' if not q else 'ENTRY_FX_OR_FEES_NA' if cost is None else 'RISK_OR_MARGIN' if stress is None or stress>2 or row['margin_eur']>80 else 'PRICE_RANGE_BELOW_COST' if range_eur<=cost else 'ECONOMIC_RANGE_WITNESS_NOT_DIRECTIONAL_EDGE'
  details.append({'sid':sid,'symbol':row['symbol'],'class':row['class'],'quote':row['quote'],'t':t,'iso':r['iso'],'prior_regime':regime,'state':state,'native_min_units':row['min_units'],'margin_eur':row['margin_eur'],'reference_notional_eur':-notional if notional is not None else None,'prior_M5_range_eur':range_eur,'prior_M5_range_bps':r['prior']['range_bps'],'cost_eur':cost,'stressed_risk_eur':stress,'hurdles':values})
 grouped={};regimes={}
 for label,groups in [('class',defaultdict(list)),('regime',defaultdict(list))]:
  for r in details:groups[r['class'] if label=='class' else r['prior_regime']].append(r)
  for key,vv in groups.items():
   out={'frames':len(vv),'instruments':len({r['sid'] for r in vv}),'states':dict(Counter(r['state'] for r in vv)),'cost_eur':stats(r['cost_eur'] for r in vv),'minimum_hurdle_bps':stats(min(v['break_even_bps'] for v in r['hurdles']['S2_F010'] if v and v['break_even_bps'] is not None) for r in vv if all(v and v['break_even_bps'] is not None for v in r['hurdles']['S2_F010'])),'stressed_risk_eur':stats(r['stressed_risk_eur'] for r in vv)}
   (grouped if label=='class' else regimes)[key]=out
 crypto=[r for r in rows if r['research_contract_eligible'] and r['class']=='Crypto Currency (Spot)'];groups=defaultdict(list)
 for r in crypto:
  if r['base']:groups[r['base']].append(r)
 catalog_pairs=[]
 for base,vv in sorted(groups.items()):
  for i,r in enumerate(sorted(vv,key=lambda z:z['sid'])):
   for b in sorted(vv,key=lambda z:z['sid'])[i+1:]:
    if r['quote']==b['quote']:continue
    u=lattice_units(r,cat['full'][str(r['sid'])],b,cat['full'][str(b['sid'])]);catalog_pairs.append({'base':base,'a':r['sid'],'b':b['sid'],'symbols':[r['symbol'],b['symbol']],'matched_units':u,'margin_eur':r['margin_eur']*(u/r['min_units'])+b['margin_eur']*(u/b['min_units']) if u else None,'relationship':'SHARED_NATIVE_BASE_ASSET_AND_VOLUME_UNITS;NOT_LEGAL_DELIVERABLE_ARBITRAGE_CERTIFICATE'})
 pair_details={};pair_summary={}
 for A,B in [('ETHAUD','ETHEUR'),('ETHGBP','ETHEUR')]:
  aa=next((r for r in rows if r['symbol']==A),None);bb=next((r for r in rows if r['symbol']==B),None)
  if not aa or not bb:pair_summary[A+'_'+B]={'state':'NATIVE_IDENTITY_NA','go':False};continue
  fA=cat['full'][str(aa['sid'])];fB=cat['full'][str(bb['sid'])];nativeA=next(z for z in cat['light'] if int(z['symbolId'])==aa['sid']);nativeB=next(z for z in cat['light'] if int(z['symbolId'])==bb['sid']);same=int(nativeA['baseAssetId'])==int(nativeB['baseAssetId']);u=lattice_units(aa,fA,bb,fB);rr=[]
  for t in sorted({t for sid,t in frames if sid==aa['sid']} & {t for sid,t in frames if sid==bb['sid']}):
   x=next(r for r in details if (r['sid'],r['t'])==(aa['sid'],t));y=next(r for r in details if (r['sid'],r['t'])==(bb['sid'],t));qA=a.point(quotes.get((aa['sid'],t)));qB=a.point(quotes.get((bb['sid'],t)));value={'t':t,'iso':frames[aa['sid'],t]['iso'],'go_witness':False,'valuation_discrepancies':None}
   if u and same and qA and qB and x['cost_eur'] is not None and y['cost_eur'] is not None:
    margin=aa['margin_eur']*u/aa['min_units']+bb['margin_eur']*u/bb['min_units'];cost=x['cost_eur']*u/aa['min_units']+y['cost_eur']*u/bb['min_units'];rng=x['prior_M5_range_eur']*u/aa['min_units']+y['prior_M5_range_eur']*u/bb['min_units'];risk=x['stressed_risk_eur']*u/aa['min_units']+y['stressed_risk_eur']*u/bb['min_units'];values=[]
    for long,ql,short,qs in [(aa,qA,bb,qB),(bb,qB,aa,qA)]:
     debit=a.convert(-u*ql['ask'],long['quote'],'EUR',t,quotes,g);credit=a.convert(u*qs['bid'],short['quote'],'EUR',t,quotes,g);values.append(credit+debit if debit is not None and credit is not None else None)
    value.update(margin_eur=margin,cost_eur=cost,prior_range_eur=rng,stress_risk_eur=risk,valuation_discrepancies=values,go_witness=margin<=80 and risk<=2 and rng>cost)
   rr.append(value)
  good=[r for r in rr if r['go_witness']];priced=[r for r in rr if r['valuation_discrepancies'] is not None];pair_details[A+'_'+B]=rr;pair_summary[A+'_'+B]={'native_shared_base':same,'native_base_asset_id':nativeA['baseAssetId'],'sid_a':aa['sid'],'sid_b':bb['sid'],'matched_units':u,'common_frames':len(rr),'economic_witness_frames':len(good),'witness_weeks':len({r['iso'] for r in good}),'cost_eur':stats(r.get('cost_eur') for r in priced),'margin_eur':stats(r.get('margin_eur') for r in priced),'stress_risk_eur':stats(r.get('stress_risk_eur') for r in priced),'positive_current_executable_valuation_discrepancy':sum(any(v is not None and v>0 for v in r['valuation_discrepancies']) for r in priced),'go':same and u is not None and len(good)>=4,'current_discrepancy_NOT_NET_return':True}
 summary={'schema':'mxm.private.complete.strategy.feasibility.v1','catalog':{'offered':len(rows),'contract_eligible':sum(r['research_contract_eligible'] for r in rows),'entry_active':sum('CURRENT_NOT_ENTRY_ENABLED' not in r['reasons'] for r in rows),'classes':len({r['class'] for r in rows}),'reasons_overlapping':dict(Counter(v for r in rows for v in r['reasons']))},'quote_frames':len(details),'quote_instruments':len({r['sid'] for r in details}),'states':dict(Counter(r['state'] for r in details)),'class_economics':grouped,'prior_regime_economics':regimes,'catalog_same_base_cross_currency_pairs':catalog_pairs,'pair_economics':pair_summary,'range_is_not_predictability':True,'hypothetical_hurdle_is_not_authentic_future_price':True,'source_window':'2000_EXISTING_FROZEN_ACTION_FRAMES;40_ALTERNATE_WEEKS;NO_NEW_RETURN_LABELS','instruments_contract_eligible_without_quote_frames':sum(r['research_contract_eligible'] for r in rows)-len({r['sid'] for r in details}),'new_broker_requests':0,'closed_kernel_calls':0,'orders':0,'Cloud_changes':False,'HARD21':False,'alpha_certified':False}
 return {'summary':summary,'instrument_frame_economics':details,'pair_details':pair_details},summary
