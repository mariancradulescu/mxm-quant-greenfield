"""Reduce saved pre-entry economic references; never read prices, labels or model outputs."""
import math,statistics
from collections import Counter,defaultdict
from datetime import date

def need(ok,code):
    if not ok:raise ValueError(code)

def stats(values):
    v=[float(x) for x in values if isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)]
    return {'n':len(v),'min':min(v) if v else None,'median':statistics.median(v) if v else None,'max':max(v) if v else None}

def ratio(x,y):
    return x/y if x is not None and y is not None and y>0 else None

def consecutive(weeks):
    days=sorted(date.fromisocalendar(int(w[:4]),int(w[6:]),1) for w in weeks)
    return all((b-a).days==7 for a,b in zip(days,days[1:])) if len(days)>1 else False

def summarize(rows):
    witness=[r for r in rows if r['state']=='ECONOMIC_RANGE_WITNESS_NOT_DIRECTIONAL_EDGE']
    scenarios={}
    for name in sorted({k for r in rows for k in r['hurdles']}):
        z=[v for r in rows for v in r['hurdles'].get(name,[]) if v is not None]
        scenarios[name]={'side_references':len(z),'breakeven_bps':stats(v['break_even_bps'] for v in z),'flat_cost_eur':stats(v['flat_cost_eur'] for v in z)}
    def worst(r):
        vals=r['hurdles']['S2_F010']
        return max(v['break_even_bps'] for v in vals) if len(vals)==2 and all(v and v['break_even_bps'] is not None for v in vals) else None
    return {'frames':len(rows),'identities':len({r['sid'] for r in rows}),'states':dict(Counter(r['state'] for r in rows)),
        'range_risk_witnesses':len(witness),'witness_identities':len({r['sid'] for r in witness}),
        'causal_prior_M5_range_bps':stats(r['prior_M5_range_bps'] for r in rows),
        'cost_over_causal_prior_range':stats(ratio(r['cost_eur'],r['prior_M5_range_eur']) for r in rows),
        'both_side_worst_hurdle_over_causal_range':stats(ratio(worst(r),r['prior_M5_range_bps']) for r in rows),
        'witness_margin_eur':stats(r['margin_eur'] for r in witness),
        'witness_reference_reserve_eur':stats(200-r['margin_eur'] for r in witness),
        'witness_stressed_risk_eur':stats(r['stressed_risk_eur'] for r in witness),
        'witness_cost_eur':stats(r['cost_eur'] for r in witness),'scenarios':scenarios}

def reduce_saved(saved,archive,matched,design):
    rows=saved['instrument_frame_economics'];old=saved['summary'];need(len(rows)==old['quote_frames'],'FRAME_CONSERVATION')
    need(len({(r['sid'],r['t']) for r in rows})==len(rows),'DUPLICATE_FRAME')
    need(dict(Counter(r['state'] for r in rows))==old['states'],'STATE_CONSERVATION')
    need(not design['new_hypotheses_enrolled'],'UNQUALIFIED_HYPOTHESIS')
    for r in rows:
        if r['state']=='ECONOMIC_RANGE_WITNESS_NOT_DIRECTIONAL_EDGE':
            need(r['margin_eur']<=80 and r['stressed_risk_eur']<=2 and r['prior_M5_range_eur']>r['cost_eur'],'SAVED_WITNESS_CONTRADICTION')
    groups=defaultdict(list);weeks=defaultdict(list);ids=defaultdict(list)
    for r in rows:groups[r['class']].append(r);weeks[r['iso']].append(r);ids[r['sid']].append(r)
    schema={k:sorted(archive[k].keys()) for k in ('summary','catalog')}
    need(set(('all_identity_status','raw_quote_receipts','events','screen')).issubset(archive),'SOURCE_SCHEMA')
    # No old prediction, label, return, account, portfolio, or raw price field is accessed.
    entry_keys=sorted({k for event in archive['events'] for k in event.get('prior',{}).keys()})
    unavailable={'first_release_macro_surprise':'NO_CONSENSUS_FIRST_RELEASE_REVISION_PUBLICATION_RECEIPT_SERIES_IN_SAVED_SCHEMA',
                 'executed_flow_or_queue_imbalance':'QUOTE_PRICE_RECEIPTS_AND_M5_TICK_ACTIVITY_ONLY;NO_AGGRESSOR_TRANSACTIONS_OR_L2_SERIES'}
    m=matched['summary'];need(m['mechanism']=='MATCHED_BASE_UNIT_CROSS_CURRENCY_EXECUTABLE_VALUATION_V1','MATCHED_SOURCE')
    old_matched={k:m[k] for k in ('mechanism','candidate_pair_clocks','economic_signals','data_and_economic_states','selected_entry_decisions','modeled_entries','modeled_paired_complete_packages','unknown_selected_packages','weekly','scenario_NET','cash_EUR_closed_accounting','fixed_cash_EUR_closed_accounting','halt','actual_orders','actual_trades','HARD21','verdict','requests','source_head')}
    out={'schema':'mxm.private.predictive.feasibility.stopgo.v1','decision':'RESEARCH_GAP',
         'decision_scope':'NO_DISTINCT_SUFFICIENTLY_JUSTIFIED_PREDICTOR_WITH_AUTHENTIC_CAUSAL_ENTRY_INFORMATION_IDENTIFIED_IN_THIS_BOUNDED_RECONCILIATION;NOT_GLOBAL_IMPOSSIBILITY',
         'matched_base_exact':'CLOSE_EXACT_OWNER_ACCEPTED_ON_RESEARCHED_SCOPE;SAVED_OUTCOME_READBACK_ONLY',
         'all_frames':summarize(rows),'class_economics':{c:summarize(v) for c,v in sorted(groups.items())},
         'weekly_saved_frame_support':{w:summarize(v) for w,v in sorted(weeks.items())},
         'source_week_sequence_consecutive':consecutive(weeks),
         'complete_consecutive_ISO_week_strategy_evaluation':'NOT_STARTED_NO_QUALIFIED_NEW_HYPOTHESIS;SAVED_SPARSE_ACTION_FRAMES_CANNOT_SUBSTITUTE',
         'frequency':'SPARSE_FRAMES_ARE_FEASIBILITY_REFERENCES_NOT_SIGNALS_TRADES_OR_INDEPENDENT_OPPORTUNITIES;INDEPENDENT_OPPORTUNITY_RATE_UNIDENTIFIED',
         'minimum_required_conditional_gross':'MUST_EXCEED_SAVED_SIDE_SPECIFIC_BREAKEVEN_HURDLE_AFTER_ALL_SCENARIO_COSTS;PRIOR_RANGE_DOES_NOT_ESTIMATE_CONDITIONAL_GROSS_MEAN',
         'cost_terms':'CURRENT_DATED_COMMISSION_MARGIN_REFERENCE;FUTURE_SPREAD_FX_HELD_FIXED_FOR_ROOT;HISTORICAL_FINANCING_SLIPPAGE_AND_FILLS_UNVERIFIED',
         'source_schema':schema,'saved_causal_prior_keys':entry_keys,'information_gaps':unavailable,
         'new_hypotheses_enrolled':0,'new_models_fit':0,'new_strategy_entries':None,'new_strategy_NET_eur':None,
         'baseline_cash_comparison':'NOT_APPLICABLE_NO_NEW_STRATEGY;NO_TRADE_NET_ZERO_NOT_A_PREDICTIVE_RESULT',
         'fixed_dynamic_exit_comparison':'NOT_APPLICABLE_NO_NEW_ENTRIES;NO_STOP_TP_REOPTIMIZATION',
         'signal_development_time_MAE_premature_exit_returned_profit':'UNIDENTIFIED_NO_ENROLLED_MECHANISM_OR_ENTRIES;NOT_ZERO',
         'matched_saved_outcome':old_matched,'development_only':True,'independent_confirmation':False,
         'orders':0,'protected_forward':False,'Cloud_changes':False,'authentication_changes':False,
         'new_broker_requests':0,'closed_kernel_calls':0,'HARD21':False,'alpha_certified':False,
         'next_decision_changing_requirement':'A_SPECIFIED_DISTINCT_MECHANISM_WITH_AUTHENTIC_POINT_IN_TIME_ENTRY_INPUT_SOURCE_AND_INCREMENTAL_BASELINE;THEN_COST_GATE_AND_COMPLETE_STRATEGY_FREEZE;NO_BULK_ACQUISITION_AUTHORIZED_BY_THIS_RESULT'}
    detail={'summary':out,'all_saved_instrument_economic_support':[{ 'sid':sid,'symbol':rr[0]['symbol'],'class':rr[0]['class'],**summarize(rr)} for sid,rr in sorted(ids.items())]}
    return detail,out
