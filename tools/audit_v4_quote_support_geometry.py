"""Deterministic outcome-blind support geometry: mathematics and synthetic masks."""
import collections,json,math,random,sys
from pathlib import Path
from research_core_v4.quote_probe_plan_v1 import canonical,sha,build,STATE

def run(root):
    root=Path(root);design=(root/(STATE+'NEXT_QUOTE_SEQUENCE_DESIGN_V2.json')).read_bytes();p=build(root)
    counts={i['asset_class']:i['context_census_count'] for i in p['identities']}
    mathrows=[]
    for ctx,n in sorted(counts.items()):
        for q in [0.99,0.95,0.8]:
            allq=q**n
            common40=sum(math.comb(52,k)*allq**k*(1-allq)**(52-k) for k in range(40,53))
            mathrows.append({'context':ctx,'identities':n,'hypothetical_independent_identity_week_support':q,'all_identity_common_week_probability':allq,'expected_common_weeks_of52':52*allq,'probability_at_least40_common_weeks':common40})
    rng=random.Random(20261003);sim=[]
    for n in [2,5,86,743]:
        qualified=0
        for _ in range(1000):qualified+=all(rng.random()<0.99 for _ in range(n))
        sim.append({'identities':n,'per_identity_qualification_probability_assumed':0.99,'trials':1000,'complete_census_qualified_trials':qualified,'expected_fraction':0.99**n})
    # Deterministic selection-bias counterexample. A missing identity's mean can
    # vary without affecting any observed supported-identity datum. Therefore
    # a relaxed support fraction cannot identify the SAME whole-census target
    # without new missingness/heterogeneity assumptions.
    worlds=[{'observed_supported_identity_means':[1,1],'unobserved_identity_mean':x,'full_census_mean':(2+x)/3} for x in [-100,100]]
    # Conditional symmetry statement verified on exhaustive +/- synthetic weeks.
    # Support mask fixed independently of outcome; negating every outcome keeps
    # every support gate and maps each context-week statistic to its negative.
    pairs=[]
    for bits in range(1024):
        values=[1 if bits&(1<<i) else -1 for i in range(10)]
        mask=[i not in [2,7] for i in range(10)]
        pairs.append(sum(v for v,m in zip(values,mask) if m))
    symmetry=collections.Counter(pairs)==collections.Counter(-x for x in pairs)
    return {'schema':'mxm.v4.quote-sequence-method-support-audit.v1','source_parent_head':'973b506a469b474d93d765862e7a337337ceda12','design_v2_sha256':sha(design),'decision':'RETAIN_V2_UNCHANGED_NO_SUPPORT_FRACTION_RELAXATION','prospective_supersession':False,
      'reason':'100% support is intentionally conservative identification of fixed whole-context census mean. Lowering fraction without changing estimand or adding independently justified missingness assumptions silently selects support-qualified identities and cannot identify original target. Fragility is real and forbids presuming full acquisition worthwhile; bounded probe decides feasibility only.',
      'complete_identity_support_geometry':mathrows,'synthetic_independent_mask_checks':sim,'correlated_support_caveat':'If all identities share a common availability mask, all-member support equals q, not q**N. Independence examples are stress illustrations, never observed-market forecasts.',
      'nonidentification_counterexample_same_observed_values_different_census_target':worlds,'exhaustive_synthetic_sign_symmetry_with_fixed_support_mask':{'sign_vectors':1024,'pass':symmetry,'not_full_maxT_Holm_or_market_power_certification':True},
      'singleton_contexts':{'Energies (Spot)':1,'Forwards - Commodities':1},'singleton_law':'RETAIN_IN1576_CENSUS_AND29_CONTEXT_FAMILY;P1_DATA_LIMITED_UNTESTED_NOT_NULL_FOR_REPLICATED_DISCOVERY;TRANSPORT_AND_LOCAL_DIAGNOSTIC_ONLY;NEVER_FORCE_MERGER_OR_REPLACEMENT',
      'support_window_semantics':'completed_events_per_window_min15 refers to original60-minute scheduled window, NOT each20-minute subwindow. Predecessor has three60-minute windows; V2 replaces them by one60-minute window with three20-minute diagnostic/stability slices. Applying15 to each slice would be an implementation defect, not the declared per-window rule.',
      'nonoverlap_upper_bounds':{'90sec_horizon_plus1sec_entry_in60min':40,'90sec_horizon_plus1sec_entry_in20min':14,'per60min_threshold':15},
      'redundant_support_minima':'40 common supported weekly dates implies >=40 distinct dates and >=40 weeks, hence18date and10week identity minima are weaker inherited floors; keep unchanged. Ten-week probe cannot satisfy40week gate and cannot authorize response.',
      'real_geometry_calibration_required_before_any_development_response':True,'null_validity_not_certified_from_metadata_or_probe':True,'future_endpoint_timestamp_masks_are_necessary_not_sufficient_for_price_validity':True,
      'no_first_v4_outcome_or_strategy_winner_inputs':True,'causal_feature_family_direction_grid_horizons_and_multiplicity_unchanged':True,'no_closure_from_probe':True,'full_census_capture_authorized':False,'historical_requests_sent_by_Work':0,'response_values_opened':False}
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];d=run(root);p=root/(STATE+'NEXT_QUOTE_SEQUENCE_METHOD_SUPPORT_AUDIT_V1.json');p.write_bytes(canonical(d)+b'\n');print('RETAIN_V2_UNCHANGED',sha(p.read_bytes()))
