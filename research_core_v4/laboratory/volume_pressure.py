"""Prospective multi-asset volume-pressure experiment and bounded quote dependencies.

Research logic only: existing custody, collector, ledger and evaluator are reused.
The output is DEVELOPMENT quote simulation, never independent confirmation/fills.
"""
from .common import *
from .data import DEVELOPMENT_END_MS

def volume_pressure_intents(spec,cache,assets):
    p=spec['parameters']['volume_pressure']
    need(p['prior_bars']==12 and p['volume_multiple']==2 and p['close_location_threshold']==0.8,'PRESSURE_FROZEN_RULE')
    need(p['entry_delay_ms']==1000 and p['hold_ms']==1800000,'PRESSURE_FROZEN_TIMING')
    need(set(assets)==set(p['symbols']),'PRESSURE_UNIVERSE')
    intents=[];missing=[];support={}
    for name,sid in p['symbols'].items():
        cache.require_usable(assets[name])
        asset=cache.assets[assets[name]]
        need(asset['partition']=='DEVELOPMENT' and asset['resolution']=='M5' and asset['instrument']==name,'PRESSURE_ASSET')
        need(asset.get('trust') in ('AUTHENTICATED_NATIVE_COLLECTION','AUTHENTICATED_NATIVE_CUSTODY'),'PRESSURE_AUTHENTICITY')
        need(asset['invalid']==asset['conflicts']==0,'PRESSURE_QUALITY')
        rows={r['t']:r for r in cache.rows[assets[name]]};count=0
        for decision in p['decision_times_ms']:
            need(decision+p['entry_delay_ms']+p['hold_ms']<DEVELOPMENT_END_MS,'PRESSURE_PROTECTED')
            clocks=[decision-300000*j for j in range(13,0,-1)]
            observed=[rows.get(t) for t in clocks]
            if any(r is None or r['available_at']>decision for r in observed):
                missing.append({'symbol_id':sid,'decision_ms':decision,'reason':'EXACT_13_BAR_FEATURE_SUPPORT_MISSING'});continue
            count+=1;bar=observed[-1];prior=observed[:-1]
            average=sum(r['volume'] for r in prior)/12
            spread=bar['high']-bar['low']
            if average<=0 or spread<=0:continue
            location=(bar['close']-bar['low'])/spread
            direction=1 if location>=0.8 and bar['close']>bar['open'] else -1 if location<=0.2 and bar['close']<bar['open'] else 0
            if bar['volume']>=2*average and direction:
                intents.append({'decision_ms':decision,'feature_available_ms':max(r['available_at'] for r in observed),
                  'entry_ms':decision+1000,'exit_ms':decision+1801000,'direction':direction,'symbol_id':sid})
        support[name]=count
    intents.sort(key=lambda v:(v['decision_ms'],v['symbol_id']))
    return {'intents':intents,'missing':missing,'supported_decisions':support,
      'feature_asset_sha256':digest({k:cache.assets[v] for k,v in assets.items()}),
      'expression_sha256':digest(p),'minimum_support_met':not missing,
      'no_post_outcome_selection':True,'actual_fills':False}

def quote_dependencies(lab,generated,policy):
    from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as native
    need(policy['max_intents']==64 and policy['orders']==0 and policy['automatic_retries']==0,'PRESSURE_QUOTE_POLICY')
    if generated['missing']:
        return {'classification':'DATA_INSUFFICIENT','reason':'FEATURE_POPULATION_INCOMPLETE','requests_reserved':0}
    if len(generated['intents'])>policy['max_intents']:
        return {'classification':'RESEARCH_BUDGET_EXHAUSTED','reason':'FULL_POPULATION_EXCEEDS_PROSPECTIVE_CAP_NO_TOP_K','requests_reserved':0}
    if not generated['intents']:
        return {'classification':'NO_ELIGIBLE_EVENTS','reason':'FROZEN_PRESSURE_RULE_NO_EVENTS','requests_reserved':0}
    data=lab.authentic_corpus;identities={int(r['sid']):r for r in data['all_identity_status']}
    graph=native.graph(list(identities.values()));required=set()
    for intent in generated['intents']:
        r=identities.get(intent['symbol_id']);terms=data['catalog']['full'].get(str(intent['symbol_id']))
        if r is None or terms is None:return {'classification':'DATA_INSUFFICIENT','reason':'ORIGINAL_SYMBOL_METADATA_MISSING','requests_reserved':0}
        try:currencies=native.currencies(r,terms)|{r['quote']}
        except (KeyError,TypeError,ValueError):return {'classification':'DATA_INSUFFICIENT','reason':'COMMISSION_CURRENCY_METADATA_MISSING','requests_reserved':0}
        needed={intent['symbol_id']}
        pairs=[(currency,'EUR') for currency in currencies]
        if int(terms.get('preciseTradingCommissionRate',0)) and int(terms['commissionType'])==1:pairs.append((r['quote'],'USD'))
        for currency,target in pairs:
            route=native.route(currency,target,graph)
            if route is None:return {'classification':'DATA_INSUFFICIENT','reason':'NO_NATIVE_FX_PATH','requests_reserved':0}
            needed.update(sid for sid,_ in route)
        for boundary in (intent['entry_ms'],intent['exit_ms']):
            for sid in needed:required.add((sid,boundary))
    points={}
    for q in data['raw_quote_receipts']:
        k=(int(q['symbol_id']),int(q['boundary_ms']))
        if k not in points:points[k]=q
        elif points[k]!=q:points[k]=None
    plans=[]
    for sid,boundary in sorted(required,key=lambda v:(v[1],v[0])):
        if native.point(points.get((sid,boundary))) is not None:continue
        plans.append({'provider':'PEPPERSTONE_OPEN_API','partition':'DEVELOPMENT','read_only':True,'automatic_retries':0,
          'instrument':str(sid),'kind':'BID_ASK','symbol_id':sid,'digits':0,
          'start_ms':boundary-60000,'end_ms':boundary,'max_pages':2,'account_scope':policy['account_scope']})
    # Reserve the full deterministic population budget before any data-dependent return.
    misses=sum(not lab.cache.query(p['instrument'],'BID_ASK',p['start_ms'],p['end_ms'],authentic_only=True) for p in plans)
    if 2*misses>lab.acquisition.remaining or 2*misses>lab.acquisition.budget.get('BID_ASK',0):
        return {'classification':'RESEARCH_BUDGET_EXHAUSTED','reason':'FULL_ORIGINAL_AND_FX_DEPENDENCIES_EXCEED_CAP','requests_reserved':0}
    before=lab.acquisition.remaining;bad=[]
    for plan in plans:
        receipt=lab.acquisition.request(plan)
        q=receipt.get('quote_point')
        if q is None:
            # An exact cached point is reusable with original native custody/trust;
            # no interpolation or reconstruction outside this one-minute window.
            asset=lab.cache.assets[receipt['asset_id']]
            rows=lab.cache.rows[receipt['asset_id']]
            sides={}
            for side in ('bid','ask'):
                values=[r for r in rows if r['side']==side and r['t']<=plan['end_ms']]
                if values:
                    last=max(values,key=lambda r:r['t'])
                    sides[side]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':last['t'],'price':last['price'],
                      'age_ms':plan['end_ms']-last['t'],'source_has_more':asset['completeness']!='CONFIRMED_COMPLETE'}
            q={'symbol_id':plan['symbol_id'],'boundary_ms':plan['end_ms'],'sides':sides,'cache_source_sha256':asset['source_sha256']}
            lab.acquisition.receipts.append({'quote_point':q,'state':'EXACT_CACHE_POINT_REUSED','asset_id':receipt['asset_id']})
        if native.point(q) is None:bad.append({'symbol_id':plan['symbol_id'],'boundary_ms':plan['end_ms'],'state':receipt['state']})
    return {'classification':'DATA_VALID' if not bad else 'DATA_INSUFFICIENT','required_original_quote_points':len(required),
      'requests_reserved':before-lab.acquisition.remaining,'unresolved':bad,
      'historical_nonspread_costs':'UNRESOLVED','numerical_economics_encrypted':True}
