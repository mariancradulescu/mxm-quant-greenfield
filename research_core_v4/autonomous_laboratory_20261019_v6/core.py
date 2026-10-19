"""Prospective, finite research registry and economically honest data gates."""
import hashlib,json,math
from collections import Counter,defaultdict
from decimal import Decimal

CAPITALS=(80,200,350,1000,5000)
TASKS=('CARRY_TEMPORAL_AUTHORITY','MINIMUM_TICKET_CAPITAL_SCALE')
VERDICTS={'DATA_INSUFFICIENT','COST_UNRESOLVED','STRUCTURALLY_INFEASIBLE','SUPPORTED_REFERENCE_ONLY'}

def need(v,code):
    if not v:raise ValueError('V6_'+code)
def enc(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def dist(v):
    v=sorted(v)
    return {'n':len(v),'min':v[0] if v else None,'median':v[len(v)//2] if v else None,'max':v[-1] if v else None}

def next_task(task,verdict,completed,registry):
    need(task in registry['tasks'] and verdict in VERDICTS,'VERDICT_IDENTITY')
    need(len(completed)==len(set(completed)) and task not in completed,'REPLAY')
    need(len(completed)<registry['budgets']['feasibility_investigations'],'BUDGET')
    done=completed+[task]
    route=registry['tasks'][task]['on_verdict'][verdict]
    if route=='STOP':return None
    need(route in registry['tasks'] and route not in done,'NEXT_NOT_ADMISSIBLE')
    need(registry['tasks'][route]['strategy_trials']==0,'DIRECTIONAL_BUDGET_UNRECONCILED')
    need(set(registry['tasks'][route]['requires_completed'])<=set(done),'DEPENDENCY')
    return route

def carry_temporal_authority(corpus):
    """Research carry cashflows: dated current terms cannot identify historical carry.

    No sign/ranking of swap is used to choose a trade. This study asks whether
    the preserved source can identify time-valid accrual and its currency/unit.
    The producer labels this catalogue as current October terms, whereas all
    candidate clocks precede September17. Current figures are not historic rates.
    """
    label=corpus['summary'].get('dated_contract_terms')
    need(isinstance(label,str) and 'CURRENT_REFERENCE' in label,'CURRENT_CATALOGUE_PROVENANCE')
    catalog=corpus['catalog']['full'];rows={str(r['sid']):r for r in corpus['all_identity_status']}
    candidate_dates=sorted({e['t']//86400 for e in corpus['events']})
    inspected=[];patterns=Counter()
    for sid,terms in sorted(catalog.items()):
        # Presence is reported without inventing a history schema from a snapshot.
        swap_keys=sorted(k for k in terms if 'swap' in k.lower() or 'rollover' in k.lower())
        record={'sid':sid,'offered_row_present':sid in rows,'current_swap_field_names':swap_keys,
                'dated_historical_accrual_schedule':False,'historical_cashflow':None,
                'reason':'CURRENT_SNAPSHOT_NOT_TEMPORAL_FUNDING_AUTHORITY'}
        patterns['CURRENT_FIELDS_PRESENT' if swap_keys else 'CURRENT_FIELDS_MISSING']+=1
        inspected.append(record)
    return {'schema':'mxm.carry-temporal-authority-study.v1','classification':'DATA_INSUFFICIENT',
        'mechanism':'CARRY_TERM_STRUCTURE','current_terms_provenance':label,'scope':'BOUND_PRESERVED_CORPUS_NOT_ALL_AUTHORIZED_ARCHIVES','catalogue_identities':len(catalog),
        'candidate_date_count':len(candidate_dates),'current_fields':dict(patterns),'identities':inspected,
        'historical_carry_net_eur':None,'future_costs_imputed_zero':False,
        'causal_entry_possible_from_later_terms':False,'direction_or_winner_selected':False,
        'minimal_data_requirement':{'reuse_first':'DATED_AUTHORIZED_PEPPERSTONE_FINANCING_RECEIPTS_IF_PRESENT_IN_ARCHIVE',
          'required':['ACCOUNT_SYMBOL_CURRENCY_AND_PRECISE_UNIT','EFFECTIVE_TIME_START_END','LONG_SHORT_RATE',
                      'ACCRUAL_TIME_TIMEZONE_AND_CALENDAR','NATIVE_CURRENCY_FX_AT_CASHFLOW','HISTORICAL_MINIMUM_COMMISSION_AND_MARGIN'],
          'current_Open_API_snapshot_repairs_history':False,
          'unsupported_historical_endpoint_assumed':False},
        'strategy_trials_consumed':0,'orders':0,'protected_forward':False,'cbot_qualified':False}

def capital_scale(corpus,accounts):
    """Minimum executable volume lattice and cost burden across contract capitals.

    Uses authentic saved entry quotes/FX and native current precise fees. No
    prices, exits, fill receipts, financing histories or equity paths are invented.
    Every calendar snapshot is a sensitivity state, never a fresh funded account.
    """
    identities={int(r['sid']):r for r in corpus['all_identity_status']}
    contracts=corpus['catalog']['full']
    quotes={};conflicts=set()
    for q in corpus['raw_quote_receipts']:
        key=(int(q['symbol_id']),int(q['boundary_ms'])//1000)
        need(q['boundary_ms']%1000==0,'QUOTE_GRID')
        if key in quotes and quotes[key]!=q:conflicts.add(key)
        else:quotes[key]=q
    for key in conflicts:quotes.pop(key,None)
    graph=accounts.graph(list(identities.values()));unique={}
    for event in corpus['events']:
        sid,t=event['sid'],event['t']
        need(type(t) is int and t<1789603200,'PROTECTED_BOUNDARY')
        unique.setdefault((sid,t),event)
    status=[];burdens={str(c):[] for c in CAPITALS};unknown=Counter();states={str(c):Counter() for c in CAPITALS}
    for (sid,t),ev in sorted(unique.items()):
        r=identities[sid];f=contracts[str(sid)];q=accounts.point(quotes.get((sid,t)))
        margin=r.get('margin_eur');units=r.get('min_units')
        lattice=all(type(f.get(k)) in (int,str) for k in ('minVolume','stepVolume','maxVolume'))
        if lattice:
            lo,step,hi=(int(f[k]) for k in ('minVolume','stepVolume','maxVolume'))
            lattice=lo>0 and step>0 and hi>=lo and finite(units) and abs(units*100-lo)<1e-6
        reason=None;spread=fee=notional=cost=None
        if not lattice:reason='NATIVE_VOLUME_LATTICE_UNRESOLVED'
        elif not finite(margin) or margin<0:reason='CURRENT_MARGIN_UNRESOLVED'
        elif q is None:reason='ENTRY_BILATERAL_QUOTE_UNRESOLVED'
        else:
            n=accounts.convert(-units*q['mid'],r['quote'],'EUR',t,quotes,graph)
            s=accounts.convert(-units*(q['ask']-q['bid']),r['quote'],'EUR',t,quotes,graph)
            fees=[accounts.commission(r,f,units,q[k],t,quotes,graph) for k in ('bid','ask')]
            if n is None or s is None or any(x is None for x in fees):reason='SIGNED_FX_OR_COMMISSION_UNRESOLVED'
            else:
                notional=-n;spread=-s;fee=max(fees)*2
                if notional<=0 or min(spread,fee)<0:reason='INVALID_ECONOMIC_FIELDS'
                else:cost=spread+fee+notional*.0004+.10*900/86400
        row={'sid':sid,'t':t,'class':r['class'],'reference_margin_eur':margin,'minimum_units':units,
             'native_lattice_valid':bool(lattice),'entry_reference_roundtrip_cost_eur':cost,
             'cost_components':{'spread_eur':spread,'current_commission_reference_eur':fee,
               'slippage_2bps_each_side_eur':notional*.0004 if notional is not None else None,
               'funding_15minute_stress_eur':.10*900/86400},'reason':reason,'capital_states':{}}
        for c in CAPITALS:
            state='UNRESOLVED' if reason else 'REFERENCE_ADMISSIBLE' if margin+cost<=c else 'REFERENCE_CAPITAL_INFEASIBLE'
            states[str(c)][state]+=1
            row['capital_states'][str(c)]={'state':state,'free_capital_after_cost_reserve_eur':None if reason else c-margin-cost,
                'cost_fraction':None if reason else cost/c}
            if not reason:burdens[str(c)].append(cost/c)
        if reason:unknown[reason]+=1
        status.append(row)
    priced=sum(r['reason'] is None for r in status)
    return {'schema':'mxm.minimum-ticket-capital-scale-study.v1',
        'classification':'COST_UNRESOLVED' if priced else 'DATA_INSUFFICIENT',
        'mechanism':'MINIMUM_TICKET_DISCRETIZATION_AND_CAPITAL_FRICTION',
        'capital_sensitivity_states_eur':list(CAPITALS),'capital_states_are_deposits':False,
        'initial_deposit_eur':200,'deposit_count':1,'capital_reset':False,
        'unique_authentic_entry_boundaries':len(status),'priced_boundaries':priced,
        'state_counts':{k:dict(v) for k,v in states.items()},'cost_equity_fraction':{k:dist(v) for k,v in burdens.items()},
        'unresolved':dict(unknown),'events':status,
        'pnl_conversion_fee_amount':None,'cost_semantics':'ENTRY_SPREAD_AND_CURRENT_COMMISSION_PLUS_EXPLICIT_SLIPPAGE_FUNDING_SCENARIOS;PNL_FEE_AMOUNT_UNKNOWN_UNTIL_PNL;NOT_COMPLETE_NET',
        'historical_margin_and_fees_verified':False,'authentic_quotes_are_fills':False,
        'realizable_net_pnl':None,'weekly_monthly_growth':None,'risk_of_ruin':None,
        'HARD21':False,'actual_entries':0,'strategy_trials_consumed':0,'cbot_qualified':False,
        'next_economic_requirements':['TIME_VALID_BROKER_TERMS','SUPPORTED_DISTINCT_EDGE_IDENTITY_WITH_BUDGET',
          'FULL_MARK_TO_MARKET_PATH_AND_EXECUTION','CONTINUOUS_ACCOUNT_REPLAY_THEN_CONFIRMATION']}

def candidate_gate(spec,evidence,budget):
    """Shared admission to existing economic replay; no budget or missing-data rescue."""
    if not budget.get('global_reconciled'):return 'BUDGET_UNRECONCILED'
    if budget.get('remaining',0)<=0:return 'BUDGET_EXHAUSTED'
    if not evidence.get('causal'):return 'IMPLEMENTATION_INVALID'
    if not evidence.get('full_dependency_support'):return 'DATA_INSUFFICIENT'
    if not evidence.get('costs_identified_or_certified_bound'):return 'COST_UNRESOLVED'
    if not evidence.get('positive_edge'):return 'NO_CONFIRMED_EDGE'
    need(spec.get('starting_equity_eur')==200 and spec.get('deposit_count')==1,'CAPITAL_CONTRACT')
    return 'ADMIT_EXISTING_CONTINUOUS_ACCOUNT_REPLAY'


def replay_candidate(spec,evidence,budget,events):
    gate=candidate_gate(spec,evidence,budget)
    if gate!='ADMIT_EXISTING_CONTINUOUS_ACCOUNT_REPLAY':return {'state':gate,'result':None}
    from competition.continuous_account_replay_v2 import replay_continuous_account
    # Reuse the established evaluator, with authentic causal adapters only.
    result=replay_continuous_account(events,starting_equity_eur=200,
        account_type=spec['account_type'],total_margin_calculation_type=spec['margin_type'])
    return {'state':result.status,'result':result}
