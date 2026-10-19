"""New row-level audit of a saved pilot; no feature/account/portfolio replay."""
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

ARMS = ('model', 'midpoint', 'quote_count')
FIELDS = ('midpoint_gross_eur', 'spread_drag_eur', 'slippage_drag_eur',
          'entry_commission_eur', 'exit_commission_eur',
          'pnl_conversion_fee_eur', 'funding_stress_eur', 'net_eur')

def need(v, code):
    if not v: raise ValueError('PS_' + code)

def number(v):
    need(type(v) in (int, float) and math.isfinite(v), 'NONFINITE')
    return v

def close(a, b):
    need(math.isclose(number(a), number(b), rel_tol=1e-9, abs_tol=1e-9), 'ACCOUNT_IDENTITY')

def check_account(a):
    if a is None: return
    for f in FIELDS: number(a[f])
    close(a['net_eur'], a['midpoint_gross_eur'] - sum(a[f] for f in FIELDS[1:-1]))
    if a.get('cash_tie'):
        need(all(a[f] == 0 for f in FIELDS), 'CASH_TIE')

def contrast(rows, baseline):
    pairs = [r for r in rows if r['accounts'].get('model') is not None
             and r['accounts'].get(baseline) is not None]
    deltas = [{f: r['accounts']['model'][f] - r['accounts'][baseline][f]
               for f in FIELDS} for r in pairs]
    totals = {f: sum(d[f] for d in deltas) if deltas else None for f in FIELDS}
    if deltas: close(totals['net_eur'], totals['midpoint_gross_eur'] - sum(totals[f] for f in FIELDS[1:-1]))
    def deletion(field):
        groups = defaultdict(float)
        for r, d in zip(pairs, deltas):
            key = str(r['sid']) if field == 'identity' else datetime.fromtimestamp(r['t'], timezone.utc).strftime('%G-W%V')
            groups[key] += d['net_eur']
        # Descriptive influence only; a deletion is not an independent resample.
        return {k: totals['net_eur'] - v for k, v in sorted(groups.items())}
    return {'paired': len(pairs), 'unpaired': len(rows)-len(pairs),
            'saved_component_increment_eur': totals,
            'positive_pairs': sum(d['net_eur'] > 0 for d in deltas),
            'negative_pairs': sum(d['net_eur'] < 0 for d in deltas),
            'zero_pairs': sum(d['net_eur'] == 0 for d in deltas),
            'cash_tie_baselines': sum(bool(r['accounts'][baseline].get('cash_tie')) for r in pairs),
            'leave_one_identity_out_known_increment_eur': deletion('identity'),
            'leave_one_week_out_known_increment_eur': deletion('week'),
            'full_population_increment_identified': bool(rows) and len(pairs) == len(rows),
            'known_subset_is_exploratory': True, 'selection_correction': False,
            'p_value': None, 'confidence_interval': None}

def analyze(full):
    s=full['summary']; rows=full['selected_accounting']; seen=set()
    need(type(rows) is list, 'ROW_SCHEMA')
    selected=s['portfolio']['selected']
    need(len(rows)==len(selected), 'SELECTED_COUNT')
    selection={(r['sid'],r['entry']) for r in selected}
    need(len(selection)==len(selected), 'DUPLICATE_SELECTION')
    patterns=Counter(); targets=[]
    for r in rows:
        key=(r['sid'],r['t'])
        need(key not in seen and key in selection and r['exit']==r['t']+900, 'ROW_IDENTITY')
        seen.add(key)
        need(type(r['accounts']) is dict, 'ARMS_SCHEMA')
        for a in ARMS: check_account(r['accounts'].get(a))
        pattern='|'.join(a+('=KNOWN' if r['accounts'].get(a) is not None else '=MISSING') for a in ARMS)
        patterns[pattern]+=1
        missing=[a for a in ARMS if r['accounts'].get(a) is None]
        if missing:
            targets.append({'symbol_id':r['sid'],'entry_second':r['t'],
                            'scheduled_exit_second':r['exit'],'missing_arms':missing,
                            'cause':'NOT_IDENTIFIED_BY_SAVED_ACCOUNT_NULL',
                            'required_next_lookup':'AUTHENTIC_BILATERAL_QUOTES_FX_AND_TERMS_AT_ORIGINAL_EXIT_NO_REPLACEMENT'})
    need(seen==selection, 'SELECTION_PARITY')
    for a in ARMS:
        known=[r['accounts'][a] for r in rows if r['accounts'].get(a) is not None]
        saved=s['accounting'][a]
        need(saved['selected']==len(rows) and saved['evaluable']==len(known) and saved['unknown']==len(rows)-len(known), 'SUMMARY_DENOMINATORS')
        for f in FIELDS:
            expected=sum(r[f] for r in known) if known else None
            if expected is None: need(saved['known_subtotal'][f] is None, 'EMPTY_SUBTOTAL')
            else: close(expected,saved['known_subtotal'][f])
    contrasts={a:contrast(rows,a) for a in ARMS[1:]}
    for a,v in contrasts.items():
        need(v['paired']==s['accounting'][a]['paired_entries'], 'PAIRED_COUNT')
        saved=s['accounting'][a]['paired_model_increment_eur']; got=v['saved_component_increment_eur']['net_eur']
        if got is None: need(saved is None, 'EMPTY_PAIR')
        else: close(got,saved)
    return {'schema':'mxm.row-level-paired-support-cost-attribution.v1',
            'support_patterns':dict(sorted(patterns.items())), 'exact_unresolved_targets':targets,
            'contrasts':contrasts,'source_rows_reconciled':True,
            'new_analysis':'JOINT_SUPPORT_COST_COMPONENT_CANCELLATION_AND_CLUSTER_DELETION_INFLUENCE',
            'saved_account_null_does_not_identify_quote_or_fx_or_fee_cause':True,
            'historical_fills_or_costs_verified':False,'causal_effect_identified':False,
            'unexposed_confirmation':False,'hypothesis_or_direction_selected':False,
            'missing_outcomes_imputed':False,'price_feature_portfolio_replays':0,
            'cbot_qualified':False,'orders_allowed':False,
            'next_stage':'ORIGINAL_EXIT_AUTHENTIC_SUPPORT_LOOKUP_ONLY_NO_PILOT_RESTART' if targets else 'AUTHENTIC_COST_EXECUTION_AND_SELECTION_AWARE_CONFIRMATION_REQUIRED'}
