"""Cheap SOURCE admission before any model. No signals, positions, fills or P&L.

Returns private source diagnostics, not economic evidence. Any unavailable group
requires an explicit exposure-path guard; it does not prove every strategy
impossible. No interpolation, removal, or retrospective session selection.
"""
import hashlib,json
from collections import Counter
from pathlib import Path

def need(ok,why):
    if not ok:raise ValueError('ACCOUNT_SOURCE_PREFLIGHT_'+why)
def scan(path,receipt,manifest,*,max_age_ms=5000,strict_positive_spread=True):
    need(type(max_age_ms) is int and max_age_ms>0 and type(strict_positive_spread) is bool,'DECLARED_CONSUMER_CONTRACT')
    need(receipt['rows']==manifest['quote_events'] and receipt['run']==manifest['source_run_id'] and
         receipt['cipher_sha256']==manifest['members']['capture.mxmenc']['sha256'] and receipt['private_sha256']==manifest['private_sha256'] and
         receipt['source_code']==manifest['code_source'] and receipt['source_trigger']==manifest['source_head'],'PRODUCER_CONSUMER_IDENTITY')
    start,end=receipt['first_ms'],receipt['end_ms'];need(type(start) is int and type(end) is int and start<end,'WINDOW')
    digest=hashlib.sha256();rows=0;groups=0;bad=0;reasons=Counter();counts=Counter();latest={};previous=None;pending={'bid':set(),'ask':set()};clock=None;first=None;last=None
    def flush(t):
        nonlocal groups,bad
        groups+=1
        for side,values in pending.items():
            if values:latest[side]=(t,next(iter(values)) if len(values)==1 else None)
        why=[]
        if any(s not in latest for s in ('bid','ask')):why.append('MISSING_SIDE')
        elif any(latest[s][1] is None for s in ('bid','ask')):why.append('AMBIGUOUS_SIDE')
        else:
            if any(t-latest[s][0]>max_age_ms for s in ('bid','ask')):why.append('STALE_SIDE')
            bid,ask=latest['bid'][1],latest['ask'][1]
            if ask<bid:why.append('CROSSED_BOOK')
            elif ask==bid and strict_positive_spread:why.append('LOCKED_BOOK_CONSUMER_REJECTS')
        if why:bad+=1;reasons.update(why)
    with Path(path).open('rb') as f:
        for line in f:
            need(len(line)<=512,'ROW_BOUND');digest.update(line);e=json.loads(line)
            need(set(e)=={'t','side','raw'},'EXACT_ROW_SCHEMA');t,side,value=e['t'],e['side'],e['raw']
            need(type(t) is int and start<=t<end and side in pending and type(value) is int and value>0,'ROW_TYPES_AND_SCOPE')
            need(previous is None or t>=previous,'CHRONOLOGY')
            if clock is not None and t!=clock:
                flush(clock);pending={'bid':set(),'ask':set()}
            if first is None:first=t
            last=t;previous=t;clock=t;pending[side].add(value);counts[side]+=1;rows+=1
    if clock is not None:flush(clock)
    need(rows==receipt['rows'] and digest.hexdigest()==receipt['derived_sha256'],'EXACT_DERIVED_SOURCE')
    for side in ('bid','ask'):
        key=side+'_events'
        if key in manifest:need(type(manifest[key]) is int and manifest[key]==counts[side],'OPTIONAL_SIDE_COUNT')
    return {'schema':'mxm.account-source-preflight.v1','rows_verified':rows,'groups':groups,'unavailable_groups':bad,'reasons':dict(sorted(reasons.items())),
      'first_observation_ms':first,'last_observation_ms':last,'source_run':receipt['run'],'max_side_age_ms':max_age_ms,
      'strict_positive_spread':strict_positive_spread,'admission':'REQUIRES_EXPLICIT_EXPOSURE_PATH_GUARD' if bad else 'SOURCE_CONTRACT_PASS_ONLY',
      'coverage_between_observations_proven':False,'historical_costs_proven':False,'economic_evaluation_performed':False,'orders':0}
def consecutive(receipts):
    need(len(receipts)>0 and all(a['end_ms']==b['first_ms'] for a,b in zip(receipts,receipts[1:])),'CALENDAR_ADJACENCY')
    return True
