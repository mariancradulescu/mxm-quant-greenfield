"""Prepare one existing exploratory experiment, without computing responses.

No CLI for execution, network, secret access, writer or campaign activation.
An eventual B-authorized worker must authenticate/decrypt the pinned saved
asset before passing its payload here. Hash checks are not broker provenance.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = 'research_core_v4/'
BINDINGS = {
    BASE+'quote_path_order_20261012_v1/kernel_v1.py': '0f8a384542329645a7e2129d0b48fd5f6af735b9eabb1e5d036b80707e0321cb',
    BASE+'quote_path_order_20261012_v1/DESIGN_V1.json': '5f9da2487c84f9176291ecfc7518d3a0c62396eb9b26e6265f00d29fdd706837',
    BASE+'cost_frequency_discovery_v1/accounts_v1.py': '1fc36a6b60bebbfc2f3a76a7d6ba007e1b244bc3d002af4b7076b89bf266add4',
}
SOURCE = {'release_id': 410189283, 'asset_id': 632722856,
          'ciphertext_sha256': '45c16cfeaba328f72305a176f6c988663c29895eebd75d7874d8ba2081f4e12d',
          'head_sha': '962d1afc8918afdc6ad42759c659bc54aa48023e', 'run_id': 38197915724}
FORWARD = 1789603200

def require(ok, code):
    if not ok:
        raise ValueError(code)

def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def method_plan(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    for path, expected in BINDINGS.items():
        require(hashlib.sha256((root/path).read_bytes()).hexdigest() == expected, 'C_METHOD_DRIFT')
    return {'schema': 'mxm.successor-c-preparation.v1', 'status': 'PREPARED_NOT_ARMED',
            'hypothesis': 'PRICE_SPREAD_TEMPORAL_ORDER_RESPONSE_V1',
            'bindings': dict(BINDINGS), 'saved_source': dict(SOURCE),
            'selection': 'ALL_SAVED_15MIN_BOUNDARIES_NO_OUTCOME_RANKING',
            'direction': 'MINUS_SIGN_AREA', 'holding_seconds': 900,
            'feature_seconds': 45, 'slippage_bps_each_side': 2,
            'funding_eur_per_24h': .10, 'starting_capital_eur': 200,
            'temporal_halves': 'MIDPOINT_OF_SAVED_ENTRY_TIME_RANGE_NOT_TRADE_COUNT',
            'confirmation': 'EXPLORATORY_PRIOR_ADAPTIVE_EXPOSURE_NO_SIGNIFICANCE_CLAIM',
            'unknown_exit': 'HALT_NO_REPLACEMENT_COMPLETE_NET_NULL',
            'empirical_support': 'UNMEASURED', 'net_eur': None,
            'campaign_armed': False, 'orders_allowed': False}

def unique(values, key, code):
    out = {}
    for value in values:
        k = key(value)
        require(k not in out or encoded(out[k]) == encoded(value), code)
        out[k] = value
    return out

def prepare_saved(full):
    """Private schema/cohort preparation after existing source authentication.

    Does not decode quotes, read targets, call accounts, or compute returns.
    Missing quote support stays in the denominator. Conflicting duplicates
    must stop rather than inherit the legacy adapter's last-write behavior.
    Returned IDs/times are PRIVATE and must not be published as public logs.
    """
    rows = unique(full['all_identity_status'], lambda r: r['sid'], 'C_IDENTITY_CONFLICT')
    quotes = unique(full['raw_quote_receipts'],
                    lambda q: (q['symbol_id'], q['boundary_ms']), 'C_QUOTE_CONFLICT')
    selected = []
    for event in full['events']:
        if event['h'] != 15:
            continue
        require(type(event['sid']) is int and type(event['t']) is int and
                0 < event['t'] and event['t']+900 < FORWARD, 'C_TIME_DOMAIN')
        require(event['sid'] in rows and str(event['sid']) in full['catalog']['full'],
                'C_IDENTITY_OR_CONTRACT_MISSING')
        # Explicitly discard historical predictors and outcomes at this boundary.
        selected.append({k: event[k] for k in ('sid', 't', 'entry')})
    entries = unique(selected, lambda e: (e['sid'], e['t']), 'C_ENTRY_CONFLICT')
    events = sorted(entries.values(), key=lambda e: (e['t'], e['sid']))
    require(bool(events), 'C_EMPTY_COHORT')
    midpoint = (events[0]['t']+events[-1]['t'])//2
    halves = Counter('first' if e['t'] <= midpoint else 'second' for e in events)
    weeks = Counter(datetime.fromtimestamp(e['t'], timezone.utc).strftime('%G-W%V') for e in events)
    missing = sum((e['sid'], e['t']*1000) not in quotes for e in events)
    return {'events': events, 'cohort_sha256': fingerprint(events),
            'half_boundary_second': midpoint, 'halves': dict(halves),
            'weekly_candidate_denominators': dict(weeks), 'candidate_boundaries': len(events),
            'missing_quote_boundaries': missing, 'outcomes_evaluated': 0,
            'campaign_armed': False}

def describe_result(prepared, result):
    """Private post-processing for a future result; never invokes the engine.

    Halves are slices of one continuous ledger, not independently reset accounts.
    Partial known sums are labeled separately from complete NET. Only complete
    matched comparators can support a descriptive increment.
    """
    p = result['portfolio']
    admitted = {(e['sid'], e['t']) for e in prepared['events']}
    require(all((e['sid'], e['entry']) in admitted for e in p['selected']), 'C_FOREIGN_SELECTED')
    chosen = {(e['sid'], e['entry']) for e in p['selected']}
    closes = unique(p['closed'], lambda e: (e['sid'], e['entry']), 'C_CLOSE_CONFLICT')
    require(all(k in chosen and e['exit'] == e['entry']+900 for k,e in closes.items()), 'C_FOREIGN_CLOSE')
    complete = p['halt'] == 'END' and set(closes) == chosen and p['complete_net_eur'] is not None
    net = p['complete_net_eur'] if complete else None
    halves = {}
    for name in ('first', 'second'):
        def belongs(t):
            return ('first' if t <= prepared['half_boundary_second'] else 'second') == name
        selected = [e for e in p['selected'] if belongs(e['entry'])]
        closed = [e for e in closes.values() if belongs(e['entry'])]
        halves[name] = {'candidate_boundaries': prepared['halves'].get(name, 0),
                        'selected': len(selected), 'known_closes': len(closed),
                        'partial_known_net_eur': sum(e['net_eur'] for e in closed) if closed else None,
                        'entire_run_complete': complete}
    comparators = p['shadow_comparator_net_eur']
    increments = {k: None if net is None or v is None else net-v for k,v in comparators.items()}
    return {'complete_net_eur': net, 'matched_increment_eur': increments, 'halves': halves,
            'weekly_support': result['weekly_support'], 'HARD21_demonstrated': False,
            'independent_confirmation': False, 'actual_fills': 0}
