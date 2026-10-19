"""Finite causal feature DSL and native-quote screening adapter.

A programme can express single/multi-instrument, temporal, session and regime
rules. Only completed observations are available. No arbitrary Python or eval.
Current broker snapshots do not certify historical fees, margin or funding.
"""
from .common import *
from .economics import screen
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as native

def expression(node,context):
    if number(node):return node
    need(isinstance(node,dict) and len(node)==1,'FEATURE_EXPRESSION')
    op,args=next(iter(node.items()))
    if op=='feature':return context.get(args)
    need(op in ('add','sub','mul','div','gt','lt','and','or','abs','neg'),'FEATURE_OPERATOR')
    vals=[expression(x,context) for x in args]
    if any(v is None for v in vals):return None
    if op=='abs':need(len(vals)==1,'FEATURE_ARITY');return abs(vals[0])
    if op=='neg':need(len(vals)==1,'FEATURE_ARITY');return -vals[0]
    need(len(vals)==2,'FEATURE_ARITY');a,b=vals
    return {'add':lambda:a+b,'sub':lambda:a-b,'mul':lambda:a*b,'div':lambda:a/b if b else None,
      'gt':lambda:int(a>b),'lt':lambda:int(a<b),'and':lambda:int(bool(a) and bool(b)),'or':lambda:int(bool(a) or bool(b))}[op]()

def causal_intents(spec,cache,assets):
    """Deterministic expression evaluated only against completed bars."""
    from datetime import datetime,timezone
    if 'volume_pressure' in spec['parameters']:
        from .volume_pressure import volume_pressure_intents
        return volume_pressure_intents(spec,cache,assets)
    rules=spec['parameters']['causal_dsl'];need(rules['entry_delay_ms']>0 and rules['hold_ms']>0,'CAUSAL_HORIZON')
    maps={}
    for name,asset in assets.items():
        m=cache.assets[asset];need(m['partition']=='DEVELOPMENT' and m['resolution'] in ('M5','H1'),'FEATURE_ASSET')
        need(m['invalid']==0 and m['conflicts']==0,'FEATURE_DATA_QUALITY')
        if not spec['provenance'].get('synthetic_reception'):need(m['source'].startswith(('PEPPERSTONE_','PRESERVED_AUTHENTIC_')),'UNAUTHENTIC_FEATURE_DATA')
        maps[name]=sorted(cache.rows[asset],key=lambda r:r['available_at'])
    intents=[];missing=[]
    for decision in rules['decision_times_ms']:
        need(decision<1789603200000,'PROTECTED_DECISION');d=datetime.fromtimestamp(decision/1000,timezone.utc)
        context={'utc_hour':d.hour,'utc_weekday':d.weekday()};latest=0
        for f in rules['features']:
            need(f['field'] in ('open','high','low','close','volume') and type(f['lag']) is int and f['lag']>=0,'FEATURE_LAG')
            available=[r for r in maps[f['asset']] if r['available_at']<=decision]
            idx=len(available)-1-f['lag'];context[f['name']]=available[idx][f['field']] if idx>=0 else None
            if idx>=0:
                latest=max(latest,available[idx]['available_at'])
                grid=300000 if cache.assets[assets[f['asset']]]['resolution']=='M5' else 3600000
                # Exact clock lags: no compressed adjacency across missing bars.
                if available[idx]['t']!=available[-1]['t']-f['lag']*grid:context[f['name']]=None
        value=expression(rules['direction_expression'],context)
        if value is None:missing.append({'decision_ms':decision,'reason':'FEATURE_SUPPORT_MISSING'});continue
        direction=1 if value>0 else -1 if value<0 else 0
        if direction:intents.append({'decision_ms':decision,'feature_available_ms':latest,'entry_ms':decision+rules['entry_delay_ms'],'exit_ms':decision+rules['entry_delay_ms']+rules['hold_ms'],'direction':direction,'symbol_id':rules['trade_symbol_id']})
    return {'intents':intents,'missing':missing,'feature_asset_sha256':digest({k:cache.assets[v] for k,v in assets.items()}),'expression_sha256':digest(rules)}

def native_quote_screen(spec,generated,corpus,terms_authority):
    """Direct reuse of native accounts FX/commission/quote semantics.

    Without prospectively certified historical costs or conservative bounds,
    native current commissions stay a reference and no net edge is declared.
    """
    identities={int(r['sid']):r for r in corpus['all_identity_status']};quotes={};conflicts=set()
    for q in corpus['raw_quote_receipts']:
        key=(int(q['symbol_id']),int(q['boundary_ms'])//1000)
        if key in quotes and quotes[key]!=q:conflicts.add(key)
        else:quotes[key]=q
    for key in conflicts:quotes.pop(key,None)
    graph=native.graph(list(identities.values()));records=[];missing=list(generated['missing'])
    need(terms_authority['state'] in ('UNRESOLVED','VERIFIED','CONSERVATIVE_BOUND'),'TERMS_AUTHORITY')
    known=terms_authority['state']!='UNRESOLVED'
    if known:
        need(terms_authority['prospectively_frozen'] is True and len(terms_authority['source_sha256'])==64,'COST_AUTHORITY_PROVENANCE')
        need(terms_authority['current_snapshot_is_historical'] is False,'RETROSPECTIVE_CURRENT_TERMS')
    for intent in generated['intents']:
        sid=int(intent['symbol_id']);r=identities.get(sid);f=corpus['catalog']['full'].get(str(sid))
        need(intent['entry_ms']%1000==0 and intent['exit_ms']%1000==0,'QUOTE_NATIVE_TIME_GRID')
        entry=intent['entry_ms']//1000;exit=intent['exit_ms']//1000
        if not r or not f or not native.point(quotes.get((sid,entry))) or not native.point(quotes.get((sid,exit))):
            missing.append({'intent_sha256':digest(intent),'reason':'ORIGINAL_ENTRY_OR_EXIT_QUOTE_MISSING'});continue
        a=native.account(intent['direction'],r,f,entry,exit,(exit-entry)/3600,quotes,graph,0,0)
        if a is None:missing.append({'intent_sha256':digest(intent),'reason':'CAUSAL_FX_OR_NATIVE_COMMISSION_UNRESOLVED'});continue
        # Native gross already includes the executable bid/ask spread.
        costs={'spread':0.,'commission':None,'slippage':None,'funding':None,'fx_conversion':None}
        if known:
            bound=terms_authority['per_intent_costs_eur'].get(digest(intent))
            if bound is not None:
                need(set(bound)==set(costs) and all(number(v) for v in bound.values()),'EXPLICIT_ALL_COSTS')
                need(bound['spread']==0,'SPREAD_ALREADY_IN_NATIVE_PRICES');costs=bound
        records.append({**intent,'partition':'DEVELOPMENT','source_sha256':digest([quotes[(sid,entry)],quotes[(sid,exit)]]),
          'execution_evidence_sha256':digest(a),'execution_basis':'CAUSAL_QUOTE_SIMULATION','gross_eur':a['gross_eur'],'costs':costs})
    result=screen(spec,{'identity':generated['feature_asset_sha256'],'implementation_valid':True,'complete':not missing and bool(records),
      'cost_state':terms_authority['state'],'trades':records})
    return {'classification':result['status'],'result':result,'cashflows':records,'missing':missing,'native_current_terms_reference_is_verified_history':False,'authentic_quotes_are_fills':False}

def native_replay(candidate,generated,corpus,authority,spec):
    """Native bilateral quote path -> existing continuous account, no fake fills.

    All original entries/exits/marks must exist. Dated margin, volume and every
    fee/financing item must be supplied by a prospectively bound authority. A
    current snapshot never supplies missing historical terms. Missing support
    blocks the entire population rather than selecting favorable complete trades.
    """
    from .economics import replay
    from datetime import datetime,timezone
    need(authority['screen_status']=='DISCOVERY_SURVIVOR','DEEP_WITHOUT_SCREEN_SURVIVOR')
    if authority['cost_state'] not in ('VERIFIED','CONSERVATIVE_BOUND'):
        return {'classification':'COST_UNRESOLVED','result':None,'reason':'DATED_ALL_FRICTION_AUTHORITY_MISSING'}
    need(authority['prospectively_frozen'] is True and len(authority['source_sha256'])==64 and authority['current_snapshot_is_historical'] is False,'REPLAY_AUTHORITY')
    if generated['missing']:return {'classification':'DATA_INSUFFICIENT','result':None,'reason':'ORIGINAL_FEATURE_SUPPORT_MISSING'}
    quotes={};conflicts=set()
    for q in corpus['raw_quote_receipts']:
        key=(int(q['symbol_id']),int(q['boundary_ms'])//1000)
        if key in quotes and quotes[key]!=q:conflicts.add(key)
        else:quotes[key]=q
    for key in conflicts:quotes.pop(key,None)
    graph=native.graph(corpus['all_identity_status']);identities={int(r['sid']):r for r in corpus['all_identity_status']};events=[];missing=[]
    iso=lambda t:datetime.fromtimestamp(t/1000,timezone.utc).isoformat().replace('+00:00','Z')
    for intent in generated['intents']:
        token=digest(intent);terms=authority['by_intent'].get(token);sid=int(intent['symbol_id']);identity=identities.get(sid)
        if terms is None or identity is None:missing.append('DATED_BROKER_TERMS');continue
        required=('volume_cents','min_volume_cents','step_volume_cents','max_volume_cents','margin_eur','entry_cost_components_eur','exit_cost_components_eur','financing_cashflows','source_sha256','effective_start_ms','effective_end_ms')
        need(all(k in terms for k in required) and len(terms['source_sha256'])==64,'NATIVE_REPLAY_TERMS')
        need(terms['effective_start_ms']<=intent['entry_ms']<intent['exit_ms']<=terms['effective_end_ms'],'DATED_BROKER_TERMS')
        need(type(terms['volume_cents']) is int and terms['volume_cents']>0,'NATIVE_REPLAY_VOLUME')
        step=authority['mark_interval_ms'];need(type(step) is int and step>0,'MARK_CADENCE')
        clocks=list(range(intent['entry_ms'],intent['exit_ms'],step))+[intent['exit_ms']]
        need(all(t%1000==0 for t in clocks),'NATIVE_REPLAY_CLOCK')
        points={t:native.point(quotes.get((sid,t//1000))) for t in clocks}
        if any(p is None for p in points.values()):missing.append('ORIGINAL_ENTRY_EXIT_OR_MARK_QUOTE');continue
        direction=intent['direction'];need(direction in (-1,1),'NATIVE_REPLAY_DIRECTION');units=terms['volume_cents']/100
        entry=points[intent['entry_ms']]['ask' if direction>0 else 'bid'];position=candidate['id']+':'+token
        for t in clocks:
            kind='ENTRY' if t==intent['entry_ms'] else 'EXIT' if t==intent['exit_ms'] else 'MARK'
            price=entry if kind=='ENTRY' else points[t]['bid' if direction>0 else 'ask']
            pnl=direction*units*(price-entry);amount=pnl if pnl else -1.
            eur=native.convert(amount,identity['quote'],'EUR',t//1000,quotes,graph)
            if eur is None:missing.append('CAUSAL_SIGNED_FX');break
            rate=eur/amount
            components=terms['entry_cost_components_eur'] if kind=='ENTRY' else terms['exit_cost_components_eur'] if kind=='EXIT' else None
            if components is not None:
                from .economics import COSTS
                need(set(components)==set(COSTS) and all(number(x) for x in components.values()),'NATIVE_REPLAY_ALL_COSTS')
                need(components['spread']==components['funding']==0,'NATIVE_REPLAY_SPREAD_OR_FUNDING_DOUBLE_COUNT')
            row={'timestamp_utc':iso(t),'kind':kind,'candidate_id':candidate['id'],'symbol':identity.get('symbol',str(sid)),'position_id':position,'causal_state':True,
              'price':price,'quote_to_eur_rate':rate,'transaction_cost_eur':sum(components.values()) if components else 0,
              'metadata':{'source_sha256':digest(quotes[(sid,t//1000)]),'available_at_ms':t,'cost_components_eur':components or {}}}
            if kind=='ENTRY':row.update(direction='LONG' if direction>0 else 'SHORT',direction_feasibility='EUR200_MIN_VOLUME_FEASIBLE',base_units=units,
              **{k:terms[k] for k in ('volume_cents','min_volume_cents','step_volume_cents','max_volume_cents','margin_eur')})
            events.append(row)
        for cashflow in terms['financing_cashflows']:
            need(intent['entry_ms']<=cashflow['timestamp_ms']<=intent['exit_ms'] and number(cashflow['amount_eur']) and len(cashflow['source_sha256'])==64,'DATED_FINANCING')
            events.append({'timestamp_utc':iso(cashflow['timestamp_ms']),'kind':'FINANCING','candidate_id':candidate['id'],'symbol':identity.get('symbol',str(sid)),'position_id':position,'causal_state':True,
              'financing_eur':cashflow['amount_eur'],'metadata':{'source_sha256':cashflow['source_sha256'],'available_at_ms':cashflow['timestamp_ms']}})
    if missing or not events:return {'classification':'DATA_INSUFFICIENT','result':None,'missing_dependencies':dict(__import__('collections').Counter(missing)),'missing_is_loss':False}
    evidence={'screen_status':'DISCOVERY_SURVIVOR','cost_state':authority['cost_state'],'full_mark_path':True,'dated_broker_terms':True,'events':events}
    need(spec['price_cost_convention']=='BID_ASK_PLUS_NONSPREAD_COSTS','NATIVE_REPLAY_PRICE_CONVENTION')
    result=replay(spec,evidence)
    return {'classification':result['classification'],'result':result,'input_population_sha256':digest(generated),'authentic_quotes_are_fills':False,'economic_certification':False}
