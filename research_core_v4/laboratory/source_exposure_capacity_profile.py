"""One source-only census. Valid observed quote groups != continuous executable bid/ask."""
import hashlib,json
from pathlib import Path
from .account_source_preflight import scan,need
AGE=5000
WINDOW=300000
def profile(path,receipt,manifest):
    earlier=scan(path,receipt,manifest,max_age_ms=AGE,strict_positive_spread=True)
    latest={};pending={'bid':set(),'ask':set()};clock=prior=None
    digest=hashlib.sha256();rows=valid=invalid=runs=long_runs=max_span=max_groups=0
    run_start=run_end=None;run_groups=0
    def close():
        nonlocal runs,long_runs,max_span,max_groups,run_start,run_end,run_groups
        if run_start is not None:
            runs+=1;span=run_end-run_start
            long_runs+=span>=WINDOW;max_span=max(max_span,span)
            max_groups=max(max_groups,run_groups)
        run_start=run_end=None;run_groups=0
    def finish(t):
        nonlocal valid,invalid,run_start,run_end,run_groups
        for side,values in pending.items():
            if values:latest[side]=(t,next(iter(values)) if len(values)==1 else None)
        healthy=(all(s in latest for s in ('bid','ask')) and
                 all(latest[s][1] is not None and t-latest[s][0]<=AGE for s in ('bid','ask')) and
                 latest['ask'][1]>latest['bid'][1])
        if not healthy:
            invalid+=1;close();return
        valid+=1
        if run_start is None or t-run_end>AGE:
            close();run_start=t;run_groups=0
        run_end=t;run_groups+=1
    with Path(path).open('rb') as source:
        for line in source:
            need(len(line)<=512,'EXPOSURE_ROW_BOUND')
            digest.update(line);rows+=1
            e=json.loads(line);need(set(e)=={'t','side','raw'},'EXPOSURE_EXACT_ROW')
            t,side,value=e['t'],e['side'],e['raw']
            need(type(t) is int and type(value) is int and value>0 and
                 receipt['first_ms']<=t<receipt['end_ms'] and side in pending and
                 (prior is None or t>=prior),'EXPOSURE_SIDE_CLOCK_PRICE')
            if clock is not None and t!=clock:
                finish(clock);pending={'bid':set(),'ask':set()}
            pending[side].add(value);clock=prior=t
    if clock is not None:finish(clock)
    close()
    need(rows==earlier['rows_verified'] and digest.hexdigest()==receipt['derived_sha256'] and
         valid+invalid==earlier['groups'] and invalid==earlier['unavailable_groups'],
         'EXPOSURE_SAME_SOURCE_AND_CONTRACT')
    bucket='NONE' if not valid else 'LESS_THAN_5_MINUTES' if max_span<WINDOW else 'AT_LEAST_5_MINUTES'
    return {'source_run':receipt['run'],'rows_verified':rows,'observed_groups':earlier['groups'],
      'healthy_observation_groups':valid,'unavailable_observation_groups':invalid,
      'unavailability_categories':sorted(earlier['reasons']),
      'observed_qualified_stretches':runs,'observed_stretches_at_least_5min':long_runs,
      'longest_qualified_observation_span_bucket':bucket,'max_groups_in_one_stretch':max_groups,
      'declared_age_and_group_gap_ms':AGE,'declared_span_ms':WINDOW,
      'between_observation_liquidity_proven':False,'broker_fills_proven':False,
      'historical_execution_costs_proven':False,'economic_model_executed':False,'orders':0}
