"""Current-cost scenarios on causal entries; exact later reference quotes separate."""
import math,statistics
from collections import Counter,defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from research_core_v4.integrated_alpha_campaign_v1 import kernel_v1 as k
from research_core_v4.native_body_persistence_v1 import kernel_v1 as cash
SCENARIOS={'S0_F0':(0,0,False),'S1_F0':(1,0,False),'S2_F0':(2,0,False),'S5_F0':(5,0,False),'S2_F010':(2,.10,False),'S2_F050':(2,.50,False),'S2_F100':(2,1.,False),'S2_ABS':(2,0,True)}
def universe(cost,source_ids):
    from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility
    n=cost['current_native_evidence']['private_native_evidence'];meta={int(r['symbol_id']):r for r in cost['metadata_rows']};assets={str(r['assetId']):r['name'] for r in n['assets']};light={int(r['symbolId']):r for r in n['light']};selected={};pairs={};why=Counter()
    for sid in source_ids:
        r=meta.get(sid);f=n['full'].get(str(sid));li=light.get(sid)
        if not r or not f or not li:why['NATIVE_IDENTITY_MISSING']+=1;continue
        base=assets.get(str(li['baseAssetId']));quote=assets.get(str(li['quoteAssetId']))
        if r['asset_class']=='Forex (Spot)' and base in k.G10 and quote in k.G10:pairs[sid]=(base,quote)
        rr=dict(r)
        if rr['asset_class']=='Commodities (Cash)':rr['product_type']='CASH_COMMODITY_CFD'
        ok,reasons=eligibility(rr)
        if not ok:why.update(reasons);continue
        if quote!='USD':why['NO_AUTHENTIC_TWO_SIDED_EUR_CONVERSION_ROUTE_IN_CURRENT_COHORT']+=1;continue
        if any(p not in f for p in ('preciseTradingCommissionRate','preciseMinCommission','commissionType','minCommissionType','lotSize','pnlConversionFeeRate')):why['NATIVE_FEE_FIELDS_MISSING']+=1;continue
        if cash.commission(f,int(r['min_volume_cents'])/100,1,{'bid':1,'ask':1}) is None:why['COMMISSION_CURRENCY_OR_UNIT_UNSUPPORTED']+=1;continue
        selected[sid]=rr
    return selected,pairs,meta,n,dict(why)
def session(t,f,r):
    from research_core_v4.native_executable_qualification_v1.runner_v1 import schedule_state
    if any(schedule_state(t+300*j,f,r)!='OPEN_CURRENT_SCHEDULE_PROXY' for j in range(49)):return False
    a=datetime.fromtimestamp(t,timezone.utc).astimezone(ZoneInfo('America/New_York'));b=datetime.fromtimestamp(t+k.H,timezone.utc).astimezone(ZoneInfo('America/New_York'))
    if a.hour<17<=b.hour:return False
    if 'swapPeriod' in f and 'swapTime' in f:
        period=int(f['swapPeriod'])*3600;offset=int(f['swapTime'])*60
        if period>0 and (t-offset)//period!=(t+k.H-offset)//period:return False
    return True
def pre_cost(r,row,f,quotes):
    q=cash.point(quotes.get((r['sid'],r['t'])));fx=cash.point(quotes.get((1,r['t'])))
    if not r['d'] or not r['b']:return {'eligible':False,'reason':'NO_PAIRED_DIRECTION'}
    if r['feature'] is None:return {'eligible':False,'reason':'FEATURE_GAP'}
    rr={'d':r['d'],'range':r['feature']['range']}
    return cash.entry_gate(rr,row,f,q,fx,session(r['t'],f,row) if q and fx else False)
def evaluate(rr,selected,native,quotes):
    out=[];contracts=[];context=[];fxrefs={r["t"]:r["feature"]["price"] for r in rr if r["sid"]==1 and r["feature"]}
    for sid,row in selected.items():
        f=native['full'][str(sid)];u=int(row['min_volume_cents'])/100
        contracts.append({'sid':sid,'symbol':row['broker_symbol'],'units':u,'step_units':int(row['step_volume_cents'])/100,'margin_eur':max(float(row['buy_margin_eur']),float(row['sell_margin_eur'])),'commission_type':f['commissionType'],'precise_rate':f['preciseTradingCommissionRate'],'precise_floor':f['preciseMinCommission'],'minimum_currency':f.get('minCommissionAsset'),'minimum_type':f['minCommissionType'],'pnlConversionFeeRate':f['pnlConversionFeeRate'],'current_not_historical':True})
    for r in rr:
        sid=r['sid']
        if sid not in selected:continue
        row=selected[sid];f=native['full'][str(sid)];z=dict(r);z['entry']=pre_cost(r,row,f,quotes);z['scenarios']=None
        u=int(row['min_volume_cents'])/100
        # Causal M5 EUR reference commission-only lower bound. Unknown spread/slip NOT zero.
        if r['feature']:
            p=r['feature']['price'];fxr=r['feature']['price'] if sid==1 else None
            ownfx=fxrefs.get(r['t']) if fxr is None else fxr
            if ownfx:
                c=cash.commission(f,u,p,{'bid':ownfx,'ask':ownfx});z['commission_only_reference_bps']=2*c/(u*p/ownfx)*10000 if c is not None else None
        q0=cash.point(quotes.get((sid,r['t'])));fx0=cash.point(quotes.get((1,r['t'])));q1=cash.point(quotes.get((sid,r['exit'])));fx1=cash.point(quotes.get((1,r['exit'])))
        if r['d'] and r['b'] and q0 and fx0 and q1 and fx1:
            z['scenarios']={name:{'model':cash.account(r['d'],u,q0,q1,fx0,fx1,f,slip,fund,absolute),'baseline':cash.account(r['b'],u,q0,q1,fx0,fx1,f,slip,fund,absolute)} for name,(slip,fund,absolute) in SCENARIOS.items()}
            if any(v['model'] is None or v['baseline'] is None for v in z['scenarios'].values()):z['scenarios']=None
        out.append(z)
    return out,contracts

def estats(rr):
    z={'calendar':len(rr),'moments':len({r['t'] for r in rr}),'signals':sum(bool(r['d']) for r in rr),'eligible':sum(r['entry']['eligible'] for r in rr),'eligible_moments':len({r['t'] for r in rr if r['entry']['eligible']}),'entry_reasons':dict(Counter(r['entry']['reason'] for r in rr)),'calculable_entry_mean_flat_cost_eur':None,'calculable_entry_mean_break_even_bps':None,'scenario':{}}
    calc=[r for r in rr if r['entry'].get('flat_cost_eur') is not None];z['calculable_entries']=len(calc)
    if calc:
        z['calculable_entry_mean_flat_cost_eur']=statistics.mean(r['entry']['flat_cost_eur'] for r in calc);z['calculable_entry_mean_break_even_bps']=statistics.mean(10000*r['entry']['flat_cost_eur']/r['entry']['notional_eur'] for r in calc)
    for group,zz in [('ALL_CALCULABLE',calc),('ELIGIBLE',[r for r in rr if r['entry']['eligible']])]:
        vv=[r for r in zz if r['scenarios']];entry=[r['entry']['flat_cost_eur'] for r in zz];z['scenario'][group]={'entries':len(zz),'evaluable':len(vv),'censored':len(zz)-len(vv),'mean_entry_flat_cost_eur':statistics.mean(entry) if entry else None,'outcomes':{name:{'N':len(vv),'model_net_eur':sum(r['scenarios'][name]['model']['net_eur'] for r in vv),'baseline_net_eur':sum(r['scenarios'][name]['baseline']['net_eur'] for r in vv),'mean_roundtrip_commission_eur':statistics.mean(r['scenarios'][name]['model']['entry_commission_eur']+r['scenarios'][name]['model']['exit_commission_eur'] for r in vv) if vv else None,'increment_eur':sum(r['scenarios'][name]['model']['net_eur']-r['scenarios'][name]['baseline']['net_eur'] for r in vv)} for name in SCENARIOS}}
    return z

def report(rr):return {'global':estats(rr),'blocks':[estats([r for r in rr if r['block']==b]) for b in range(4)],'weeks':{w:estats([r for r in rr if r['iso']==w]) for w in k.complete_weeks()}}
def allocator(rr):
    groups=defaultdict(list)
    for r in rr:
        if r['entry']['eligible']:groups[r['t']].append(r)
    chosen=[]
    for t,rows in sorted(groups.items()):
        conflicts={s for s in {r['sid'] for r in rows} if len({r['d'] for r in rows if r['sid']==s})>1};valid=[r for r in rows if r['sid'] not in conflicts]
        if valid:chosen.append(min(valid,key=lambda r:(r['entry']['flat_cost_eur']/r['entry']['range_eur'],r['sid'],k.NAMES.index(r['family']))))
    cashbalance=200.;peak=200.;dd=0.;count=0;halt='END';baseline=200.
    for r in chosen:
        if not r['scenarios']:halt='FIRST_SELECTED_EXIT_CENSORED';break
        if cashbalance-r['entry']['margin_eur']<150:halt='FREE_CAPITAL_BUFFER';break
        cashbalance+=r['scenarios']['S2_F010']['model']['net_eur'];baseline+=r['scenarios']['S2_F010']['baseline']['net_eur'];peak=max(peak,cashbalance);dd=max(dd,peak-cashbalance);count+=1
    return chosen,{'cash_ledger_priced':count,'halt':halt,'cash_eur':cashbalance,'baseline_cash_eur':baseline,'closed_cash_drawdown_eur':dd,'max_simultaneous':1,'actual_fills':0,'HARD21':False,'certified_NET_trades':0,'ruin_risk':'NOT_IDENTIFIED_NO_FILL_GAP_STOP_TAIL_CERTIFICATE'}
