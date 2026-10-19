"""Registered aggregate sensitivity analyses; never replay the accepted pilot.

These calculations are diagnostic sensitivity, not causal identification,
independent confirmation, historical fills or a strategy search.
"""
from research_core_v4.delegated_bc_20261019.science import partial_identification, number
from research_core_v4.p0_supersession_20261016.authority import need

EXTRA_ROUND_TRIP_EUR=(0.,.01,.05,.10,.20,.50,1.,2.)

def missingness(summary):
    p=partial_identification(summary);arms={}
    for name,a in p['arms'].items():
        subtotal=a['known_subtotal_eur'];m=a['missing']
        need(a['known']==0 or subtotal is not None,'BC_MISSING_OBSERVED_SUBTOTAL')
        # A threshold on missing outcomes is an algebraic condition, not their imputation.
        threshold=None if m==0 or subtotal is None else -subtotal/m
        arms[name]={'known':a['known'],'missing':m,'selected':a['selected'],
            'known_subtotal_eur':subtotal,'missing_mean_required_for_total_above_zero_eur':threshold,
            'point_total_eur':a['identified_set'].get('net_eur'),
            'unbounded_if_any_missing':m>0,'missing_outcome_model_assumed':False}
    return {'schema':'mxm.missingness-frontier.v1','arms':arms,
        'common_comparable_population_verified':False,
        'partial_matched_baseline_totals':p['paired'],
        'selection_bias_corrected':False,'unobserved_outcomes_estimated':False,
        'causal_interpretation_supported':False,'additional_experiment_replays':0,
        'p_values':None,'confidence_intervals':None,'cbot_qualified':False}

def cost_sensitivity(summary):
    p=partial_identification(summary);arms={}
    for name,a in p['arms'].items():
        k=a['known'];subtotal=a['known_subtotal_eur'];number(subtotal)
        need(k==0 or subtotal is not None,'BC_COST_OBSERVED_SUBTOTAL')
        cases=[{'additional_round_trip_charge_eur':c,
            'observable_subset_net_eur':None if subtotal is None else subtotal-c*k,
            'full_net_eur':(None if a['missing'] or a['selected']==0 or subtotal is None else subtotal-c*k)}
            for c in EXTRA_ROUND_TRIP_EUR]
        arms[name]={'known':k,'missing':a['missing'],'selected':a['selected'],
            'incremental_charge_budget_on_observable_subset_eur_per_trade':
                None if k==0 or subtotal is None else subtotal/k,
            'cases':cases,'full_net_identifiable':a['missing']==0 and a['selected']>0}
    return {'schema':'mxm.incremental-cost-sensitivity.v1','arms':arms,
        'existing_cost_terms':p['cost_terms'],'incremental_costs_are_scenarios':True,
        'historical_actual_costs_verified':False,'historical_fills_verified':False,
        'existing_costs_replaced':False,'orders_allowed':False,
        'additional_experiment_replays':0,'cbot_qualified':False}

def admission(results):
    need(len(results)==2 and results[0]['schema']=='mxm.missingness-frontier.v1' and
         results[1]['schema']=='mxm.incremental-cost-sensitivity.v1','BC_CAMPAIGN_ADMISSION_INPUT')
    need(all(r['cbot_qualified'] is False and r['additional_experiment_replays']==0 for r in results),
         'BC_UNSUPPORTED_PROMOTION')
    return {'schema':'mxm.research-evidence-admission.v1','cbot_qualified':False,
        'decision':'INSUFFICIENT_COMPLETE_CAUSAL_COST_RISK_AND_CONFIRMATION_SUPPORT',
        'registered_analyses_complete':True,'global_research_universe_exhausted':False,
        'next_evidence_requirements':['AUTHENTIC_COMPLETE_EXITS_ON_PREDECLARED_POPULATION',
            'COMPLETE_MATCHED_BASELINES_WITH_COMMON_ELIGIBILITY',
            'HISTORICALLY_SUPPORTED_COSTS_AND_EXECUTION_RISK',
            'SELECTION_AWARE_OR_UNEXPOSED_CONFIRMATION'],
        'additional_authorized_research_needed':True,'real_trading_allowed':False,
        'not_proof_of_unprofitability':True}
