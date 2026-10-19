"""New partial-identification analysis of an authenticated preserved summary.

No price/feature/portfolio replay; no new market provider. Private counts, cost
amounts and partial totals stay within the encrypted checkpoint. Missing exits
have no invented bound and simulated charges are not historical fills.
"""
import math
from research_core_v4.p0_supersession_20261016.authority import need
from research_core_v4.successor_c_20261018.readback import DESIGN_SHA

def count(v):
    need(type(v) is int and v>=0,'BC_SCIENCE_COUNT');return v

def number(v):
    need(v is None or (type(v) in (int,float) and math.isfinite(v)),'BC_SCIENCE_NUMBER')
    return v

def identified_sum(a):
    n=count(a['selected']);known=count(a['evaluable']);missing=count(a['unknown'])
    need(known+missing==n,'BC_SCIENCE_DENOMINATORS')
    subtotal=number(a['known_subtotal']['net_eur']);complete=number(a['complete_net_eur'])
    need(complete is None or (n>0 and missing==0 and subtotal==complete),'BC_FALSE_COMPLETE_NET')
    return {'selected':n,'known':known,'missing':missing,'known_subtotal_eur':subtotal,
        'identified_set':({'kind':'POINT','net_eur':complete} if complete is not None else
            {'kind':'UNBOUNDED_WITHOUT_JUSTIFIED_OUTCOME_BOUNDS','lower_eur':None,'upper_eur':None}),
        'complete_case_extrapolation_allowed':False,'unknown_costs_imputed_as_zero':False}

def partial_identification(s):
    need(s['schema']=='mxm.quote.path.empirical.summary.v1' and s['design_sha256']==DESIGN_SHA,
         'BC_SCIENCE_SUMMARY')
    need(s['broker_requests']==s['orders']==s['fills']==0 and
         s['protected_forward'] is False and s['alpha_certified'] is False and
         s['HARD21_demonstrated'] is False,'BC_SCIENCE_SCOPE')
    arms={k:identified_sum(s['accounting'][k]) for k in ('model','midpoint','quote_count')}
    n=arms['model']['selected'];paired={}
    for k in ('midpoint','quote_count'):
        a=s['accounting'][k];m=count(a['paired_entries']);need(m<=n,'BC_SCIENCE_PAIRED_DENOMINATOR')
        delta=number(a['paired_model_increment_eur'])
        paired[k]={'paired':m,'unpaired':n-m,'known_paired_subtotal_eur':delta,
            'complete_increment_eur':delta if n>0 and m==n and
                arms['model']['missing']==arms[k]['missing']==0 else None,
            'subset_selection_correction_claimed':False}
    # Denominators are recorded separately; no false nested-cohort assumption.
    coverage={k:count(s[k]) for k in ('all_original_event_rows','unique_candidate_boundaries',
        'calculable_features','entry_proxy_eligible_all','model_proposed_eligible')}
    return {'schema':'mxm.partial-identification.v1','arms':arms,'paired':paired,
        'coverage':coverage,'cost_terms':s['cost_terms'],
        'historical_fill_support':False,'independent_confirmation':False,
        'statistical_inference':'NO_P_VALUE_OR_CI_FROM_AGGREGATES_OR_ADAPTIVELY_EXPOSED_SUMMARY',
        'orders_allowed':False,'HARD21_demonstrated':False,
        'next_evidence_required':['BOUND_UNRESOLVED_EXITS_WITH_AUTHENTIC_EXISTING_DATA',
            'COMPLETE_CAUSAL_MODEL_AND_MATCHED_BASELINES','COST_AND_RISK_SUPPORT',
            'UNEXPOSED_CONFIRMATION_OR_SELECTION_AWARE_INFERENCE'],
        'kernel_recalculations':0,'new_postprocessing':True}

def admission(result):
    need(result['schema']=='mxm.partial-identification.v1','BC_ADMISSION_INPUT')
    net=result['arms']['model']['identified_set'];paired=result['paired']
    qualified=(net['kind']=='POINT' and net['net_eur']>0 and
        all(x['complete_increment_eur'] is not None and x['complete_increment_eur']>0
            for x in paired.values()) and result['historical_fill_support'] is True and
        result['independent_confirmation'] is True and result['HARD21_demonstrated'] is True)
    need(not qualified,'BC_UNEXPECTED_PROMOTION_REQUIRES_NEW_VALIDATION')
    return {'schema':'mxm.offline-economic-admission.v1','cbot_qualified':False,
        'decision':'NO_PROMOTION_INCOMPLETE_EMPIRICAL_SUPPORT',
        'not_a_proof_of_unprofitability':True,'orders_allowed':False,
        'full_research_universe_exhausted':False,'additional_authorized_research_needed':True}
