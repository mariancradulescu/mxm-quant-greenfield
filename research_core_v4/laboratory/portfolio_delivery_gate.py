"""Portfolio-level delivery eligibility from immutable completed Stage B receipts.

This is a CLOSED-RESULT readback, NOT a new alpha evaluation or portfolio replay.
Do not combine separate EUR200 equity paths as a new EUR200 equity path.
Only explicitly overlapping ISO weeks may be compared. A sum of *accepted*
entries is an optimistic upper bound, not a feasible joint-order count.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[2]
RESULTS = {
    'V2-C006': ('m6/results/V2-C006_STAGE_B_CURRENT_CONFIG_V1.json',
                '0234d84f09a168ff70da4c07b9ccde49159010fc'),
    'V2-C012': ('m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V1.json',
                '8c3b1fcdad6b43fcfed2af0919f3ddffd3b541f7'),
    'V2-C031': ('m6/results/V2-C031_STAGE_B_CURRENT_CONFIG_V1.json',
                '8ece3eea143413198008b9a3926e5e0f810c7293'),
}
FIRST = '2026-W25'
LAST = '2026-W37'
CAPITAL = Decimal('200')
TICKET_MARGIN_CAP = Decimal('80')
MINIMUM_FREE_RESERVE = Decimal('120')
HARD21 = 21

def need(x, code):
    if not x:
        raise ValueError('MXM_SURVIVOR_DELIVERY_' + code)

def decimal(x):
    result = Decimal(str(x))
    need(result.is_finite(), 'NONFINITE')
    return result

def git_blob_hash(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def load_originals(root=ROOT):
    out = {}
    for ident, (path, pinned_blob) in RESULTS.items():
        raw = (root/path).read_bytes()
        need(git_blob_hash(raw) == pinned_blob, 'FROZEN_BLOB_CHANGED_'+ident)
        item = json.loads(raw)
        need(item['candidate_id'] == ident and
             item['label'] == 'STAGE_B_CURRENT_CONFIGURATION_SCENARIO' and
             item['scenario_boundary']['historical_point_in_time_margin_certification'] is False,
             'NOT_FROZEN_UNCERTIFIED_RESULT_'+ident)
        out[ident] = item
    return out

def extract(result):
    ident = result['candidate_id']
    if ident in ('V2-C006','V2-C012'):
        e = result['economic_summary']
        d = result['frozen_reporting']
        need(e['starting_equity_eur'] == 200 and d['continuous_capital']['starting_capital_eur'] == 200,
             'SEPARATE_INITIAL_CAPITAL')
        counts = d['executed_trade_distribution']['weekly_executed_entries']
        coverage = set(d['weekly_final_equity_eur'])
        need(d['executed_trade_distribution']['executed_trades'] == e['executed_trades'] and
             sum(counts.values()) == e['executed_trades'], 'ENTRY_INVENTORY_'+ident)
        need(abs(decimal(e['final_equity_eur'])-CAPITAL-decimal(e['net_pnl_eur'])) < Decimal('0.000001'),
             'SEPARATE_NET_CASH_'+ident)
        max_margin = decimal(d['capital_occupancy']['maximum_required_margin_eur'])
        free = None
        net = decimal(e['net_pnl_eur'])
        equity = decimal(e['final_equity_eur'])
        dd = decimal(e['maximum_drawdown_eur'])
        count = e['executed_trades']
    else:
        b = result['base_path']
        stress = result['adverse_bar_stress_path']
        need(result['capital_policy']['starting_equity_eur'] == 200 and
             result['capital_policy']['continuous_account'] is True,
             'C031_SEPARATE_ACCOUNT')
        counts = b['entries_by_iso_week']
        coverage = set(counts)
        count = b['accepted_entries']
        need(sum(counts.values()) == count and
             stress['accepted_entries'] == count, 'C031_ENTRY_INVENTORY')
        net = decimal(b['terminal_broker_equity_eur'])-CAPITAL
        equity = decimal(b['terminal_broker_equity_eur'])
        dd = decimal(b['maximum_drawdown_eur'])
        max_margin = None
        free = decimal(b['minimum_free_margin_eur'])
    need(count>=0 and all(isinstance(v,int) and v>=0 for v in counts.values()) and
         abs(equity-CAPITAL-net)<Decimal('0.000001'), 'ENTRIES_OR_ACCOUNT')
    margin_result = ('NECESSARY_MARGIN_CAP_FAIL' if max_margin is not None and
                     max_margin > TICKET_MARGIN_CAP else
                     'MARGIN_CAP_NOT_PROVEN' if max_margin is None else
                     'MARGIN_CAP_NECESSARY_PASS_ONLY')
    reserve_result = ('OBSERVED_SCENARIO_FREE_RESERVE_FAIL' if free is not None and
                      free < MINIMUM_FREE_RESERVE else
                      'FREE_RESERVE_NOT_PROVEN' if free is None else 'RESERVE_NECESSARY_PASS_ONLY')
    return {'id':ident,'count':count,'by_week':counts,'covered_weeks':coverage,
            'net':net,'final_equity':equity,'max_drawdown':dd,
            'max_ticket_margin':max_margin,'minimum_free_margin':free,
            'ticket_margin_result':margin_result,'free_reserve_result':reserve_result}

def iso_week(y,w):
    from datetime import date
    # Assert ISO-week label exists; no invented overrun or future stub.
    date.fromisocalendar(y,w,1)
    return f'{y}-W{w:02d}'

def diagnose(items):
    need(set(items) == set(RESULTS), 'CANDIDATE_ROSTER')
    extracted = {k:extract(v) for k,v in items.items()}
    # The short-history C031 programme has only W25..W37 available. This is
    # an explicitly scoped intersection; it is NOT padded with zero trades in 2022–25.
    window = [iso_week(2026,i) for i in range(25,38)]
    need(window[0] == FIRST and window[-1] == LAST and
         all(set(window) <= d['covered_weeks'] for d in extracted.values()),
         'COMMON_OBSERVATION_WINDOW_INCOMPLETE')
    # Unknown same-account collisions can REDUCE jointly accepted entries,
    # never increase the count already logged on each separate scenario.
    weeks = []
    for w in window:
        by = {k:d['by_week'].get(w,0) for k,d in extracted.items()}
        upper = sum(by.values())
        weeks.append({'iso_week':w,'separate_account_entry_counts':by,
                      'optimistic_joint_entries_upper_bound':upper,
                      'shortfall_to_HARD21_at_least':max(0,HARD21-upper)})
    max_upper = max(w['optimistic_joint_entries_upper_bound'] for w in weeks)
    peak_sum = sum(max(d['by_week'].values(), default=0) for d in extracted.values())
    status = 'CERTAINLY_BELOW_HARD21_FROM_FROZEN_CANDIDATES' if max_upper < HARD21 else 'UNRESOLVED_REQUIRES_TRUE_FUNDED_JOINT_REPLAY'
    per = {}
    for k,v in extracted.items():
        per[k]={'scenario_net_eur':str(v['net']),
                'separate_scenario_final_equity_eur':str(v['final_equity']),
                'executed_entries':v['count'],
                'individual_peak_week_entries':max(v['by_week'].values(),default=0),
                'maximum_drawdown_eur':str(v['max_drawdown']),
                'maximum_reported_ticket_margin_eur':None if v['max_ticket_margin'] is None else str(v['max_ticket_margin']),
                'minimum_reported_free_margin_eur':None if v['minimum_free_margin'] is None else str(v['minimum_free_margin']),
                'owner_margin_80':v['ticket_margin_result'],
                'owner_free_reserve_120':v['free_reserve_result'],
                'source_path':RESULTS[k][0], 'source_git_blob_sha1':RESULTS[k][1]}
    return {'schema':'mxm.closed-candidate-common-capital-delivery-gate.v1',
            'status':status,
            'owner_bounds':{'initial_capital_eur':200,'max_ticket_margin_eur':80,
                            'minimum_free_margin_eur':120,'systemic_minimum_entries_each_iso_week':HARD21},
            'scope':'EXISTING_EXPOSED_DEVELOPMENT_STAGE_B_RESULTS_ONLY',
            'overlapping_iso_weeks':[FIRST,LAST],
            'overlap_weeks_count':len(window),
            'peak_sum_even_if_on_different_weeks':peak_sum,
            'max_same_iso_week_optimistic_combined_entries':max_upper,
            'all_overlapping_weeks_below_HARD21':max_upper < HARD21,
            'entry_count_aggregation':'UPPER_BOUND_ONLY_NOT_A_FUNDED_JOINT_PORTFOLIO',
            'separate_scenario_equity_and_net_must_never_be_added':True,
            'candidates':per,'weekly_upper_bounds':weeks,
            'historical_costs_and_fills_certified':False,
            'owner_stop_risk_proven':False,
            'actual_system_HARD21_proven':False,
            'economic_edge_robust_or_independent_proven':False,
            'common_eur200_account_simulated':False,
            'new_economic_executions':0, 'previous_models_rerun':0,
            'new_broker_requests':0, 'live_demo_orders':0, 'cloud_activations':0}

def main():
    import sys
    need(sys.argv[1:] == ['report'],'NO_MODEL_ENTRYPOINT')
    result=diagnose(load_originals())
    print(json.dumps(result,sort_keys=True,separators=(',',':')))
if __name__ == '__main__':
    main()
