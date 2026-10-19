"""Finite economic support studies. No predictor replay, imputation or orders."""
import math
from collections import Counter, defaultdict
from itertools import combinations
from datetime import datetime, timezone


def need(v, code):
    if not v:
        raise ValueError('LAB_' + code)


def finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def quote_index(values):
    index = {}; conflicts = set()
    for q in values:
        key = (int(q['symbol_id']), int(q['boundary_ms']) // 1000)
        need(q['boundary_ms'] % 1000 == 0, 'QUOTE_GRID')
        if key in index and index[key] != q:
            conflicts.add(key)
        else:
            index[key] = q
    for key in conflicts:
        index.pop(key, None)
    return index, conflicts


def recover_targets(pilot, targets, corpus, quotes, accounts):
    """Only missing original selected arms; no feature/selection/portfolio rerun."""
    rows = {r['sid']: r for r in corpus['all_identity_status']}
    graph = accounts.graph(list(rows.values()))
    selected = {(r['sid'], r['t']): r for r in pilot['selected_accounting']}
    results = []; reasons = Counter()
    for target in targets:
        sid, t, exit = target['symbol_id'], target['entry_second'], target['scheduled_exit_second']
        need((sid, t) in selected and exit == t + 900, 'ORIGINAL_TARGET')
        original = selected[sid, t]
        need(set(target['missing_arms']) == {a for a in ('model','midpoint','quote_count') if original['accounts'].get(a) is None}, 'TARGET_ARMS')
        row = rows[sid]; contract = corpus['catalog']['full'][str(sid)]
        item = {**target, 'recovered': {}, 'unresolved': {}}
        for arm in target['missing_arms']:
            direction = original['feature'][{'model':'model_side','midpoint':'midpoint_baseline_side','quote_count':'quote_count_baseline_side'}[arm]]
            need(direction in (-1, 1), 'MISSING_CASH_ARM')
            entry_point = accounts.point(quotes.get((sid,t)))
            exit_point = accounts.point(quotes.get((sid,exit)))
            z = accounts.account(direction,row,contract,t,exit,.25,quotes,graph,2,.10,False)
            if z is None:
                reason = ('ORIGINAL_ENTRY_BILATERAL_QUOTE_UNRESOLVED' if entry_point is None else
                          'ORIGINAL_EXIT_BILATERAL_QUOTE_UNRESOLVED' if exit_point is None else
                          'ORIGINAL_FX_OR_COMMISSION_UNRESOLVED')
                item['unresolved'][arm] = reason; reasons[reason] += 1
            else:
                need(all(finite(z[k]) for k in ('gross_eur','net_eur','entry_commission_eur','exit_commission_eur','funding_stress_eur','pnl_conversion_fee_eur')), 'RECOVERED_ACCOUNT')
                item['recovered'][arm] = z
        results.append(item)
    unresolved = sum(len(x['unresolved']) for x in results)
    return {'schema':'mxm.original-target-recovery.v1','targets':results,
            'target_rows':len(results),'recovered_arms':sum(len(x['recovered']) for x in results),
            'unresolved_arms':unresolved,'reasons':dict(reasons),
            'classification':'DATA_INSUFFICIENT' if unresolved else 'ORIGINAL_TARGETS_SUPPORTED_CURRENT_TERMS_ONLY',
            'complete_pilot_reconstructed':False,'original_selection_extended':False,
            'historical_terms_fills_or_net_certified':False,'pilot_replays':0,
            'missing_is_loss_or_zero':False,'next':'ADVANCE_DISTINCT_ECONOMIC_SUPPORT_STUDY'}


def pair_frontier(corpus):
    """Ex-ante two-ticket cost and EUR200 capital contention, no return ranking.

    This is an economic feasibility hypothesis, not a directional strategy test.
    Saved eligible/risk flags are not used: their tactical 40% cap is not project law.
    Only exact common clocks, same class and same quote currency are compared.
    """
    identities = {r['sid']:r for r in corpus['all_identity_status']}
    clocks = {}; duplicates = Counter()
    for event in corpus['events']:
        if event['h'] != 15:
            continue
        sid, t = event['sid'], event['t']
        need(type(t) is int and t + 900 < 1789603200, 'DEVELOPMENT_BOUNDARY')
        key = (sid,t)
        entry = event['entry']
        if key in clocks:
            need(clocks[key]['entry'] == entry, 'EVENT_CONFLICT')
            duplicates[key] += 1
        else:
            clocks[key] = {'sid':sid,'t':t,'entry':entry}
    groups = defaultdict(list); unresolved = Counter(); tickets = []
    for (sid,t), ev in sorted(clocks.items()):
        row = identities[sid]; en = ev['entry']
        need(row['sid']==sid, 'IDENTITY')
        fields = ('margin_eur','cost_eur','notional_eur')
        if not all(finite(en.get(k)) and en[k] >= 0 for k in fields) or en.get('notional_eur',0)==0:
            unresolved[en.get('state','MISSING_ENTRY_TERMS')] += 1; continue
        if not finite(row.get('min_units')) or row['min_units'] <= 0:
            unresolved['MINIMUM_UNITS_UNKNOWN'] += 1; continue
        ticket = {**ev,'class':row['class'],'quote':row['quote'],'min_units':row['min_units']}
        tickets.append(ticket)
        groups[t,row['class'],row['quote']].append(ticket)
    pairs = []; weekly = defaultdict(lambda: {'pairs':0,'affordable_reference_pairs':0,'clocks':set()})
    for (t,cls,quote), members in sorted(groups.items()):
        for left,right in combinations(sorted(members,key=lambda r:r['sid']),2):
            margin = left['entry']['margin_eur'] + right['entry']['margin_eur']
            cost = left['entry']['cost_eur'] + right['entry']['cost_eur']
            affordable = margin + cost <= 200
            week = datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
            r={'t':t,'sids':[left['sid'],right['sid']],'class':cls,'quote':quote,
               'reference_margin_eur':margin,'entry_roundtrip_cost_proxy_eur':cost,
               'reference_free_capital_after_reserving_cost_eur':200-margin-cost,
               'reference_capital_feasible':affordable,
               'cost_over_combined_notional_bps':cost/(left['entry']['notional_eur']+right['entry']['notional_eur'])*10000}
            pairs.append(r); weekly[week]['pairs']+=1
            if affordable:
                weekly[week]['affordable_reference_pairs']+=1; weekly[week]['clocks'].add(t)
    for v in weekly.values():
        v['distinct_affordable_clocks']=len(v.pop('clocks'))
    feasible = [p for p in pairs if p['reference_capital_feasible']]
    return {'schema':'mxm.synchronous-pair-economic-feasibility.v1',
            'hypothesis':'SAME_CLASS_SAME_QUOTE_SIMULTANEOUS_MINIMUM_TICKETS_FIT_EUR200_AND_HAVE_OBSERVABLE_ENTRY_FRICTION',
            'unique_saved_clocks':len(clocks),'priced_minimum_tickets':len(tickets),
            'same_clock_pair_observations':len(pairs),'reference_affordable_pairs':len(feasible),
            'unresolved_entry_reasons':dict(unresolved),'weekly':dict(weekly),'pairs':pairs,
            'classification':'COST_UNRESOLVED' if feasible else 'DATA_INSUFFICIENT' if not pairs else 'STRUCTURALLY_INFEASIBLE_ON_SAVED_REFERENCE_COHORT',
            'historical_margin_commission_swap_slippage_certified':False,
            'entry_costs_are_current_terms_and_explicit_scenarios':True,
            'returns_opened_or_ranked':False,'strategy_trials_consumed':0,
            'pair_overlap_counts_are_not_independent_trials':True,
            'HARD21':False,'actual_orders':0,'actual_fills':0,
            'account_path':'EUR200_ONCE;NO_TRADING_PATH_IN_FEASIBILITY_STUDY',
            'risk_of_ruin':None,'net_economic_edge':None,'global_universe_exhausted':False,
            'historical_or_live_executability_proved':False}


def admission(recovery, frontier):
    need(recovery['pilot_replays']==0 and frontier['actual_orders']==0 and frontier['strategy_trials_consumed']==0,'ADMISSION_SCOPE')
    return {'schema':'mxm.finite-laboratory-evidence-admission.v1',
            'state':'REGISTERED_PROGRAM_COMPLETE_NO_CBOT_QUALIFICATION',
            'original_exit_disposition':recovery['classification'],
            'distinct_study_disposition':frontier['classification'],
            'next_scientific_action':('PROSPECTIVE_RELATIVE_VALUE_DESIGN_WITH_ATTEMPT_LEDGER_AND_HISTORICAL_EXECUTION_SUPPORT'
                if frontier['reference_affordable_pairs'] else 'SELECT_DIFFERENT_AUTHORIZED_DATA_SUPPORTED_MECHANISM'),
            'auto_generated_unlimited_hypotheses':False,'cbot_qualified':False,
            'new_strategy_trials':0,'data_absence_is_unprofitability':False,
            'pending':None,'safe_stop':True,
            'remaining':['INTEGRATED_CONFIRMED_EDGE_TO_SHARED_ACCOUNT_REPLAY',
              'HISTORICAL_EXECUTION_AND_COST_CERTIFICATION','SELECTION_AWARE_CONFIRMATION',
              'CONFIRMED_PORTFOLIO_ALLOCATOR_AND_RISK','CSHARP_PARITY_AND_FULL_DEMO_WEEK']}
