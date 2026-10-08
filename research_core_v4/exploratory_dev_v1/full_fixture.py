"""Full frozen calendar and145 identities, fabricated bars ONLY."""
import json
import resource
import time
import numpy as np
from . import worker as w
from .test_offline import fixture

def main():
    started=time.process_time()
    identities=json.loads(w.MANIFEST.read_bytes())['primary_series']
    ids=sorted(x['symbol_id'] for x in identities)
    prototypes=[]
    for offset in (0,5):
        bars=fixture(days=366,offset=offset)
        prototypes.append(w.derive(bars));del bars
    caches=[prototypes[i%2] for i in range(145)]
    report=w.evaluate(caches,ids)
    assert len(report['comparisons'])==18
    assert len(report['score_clock_utc_epoch'])==1240
    assert all(x['identities']==145 and x['fixed_opportunities']==179800 for x in report['comparisons'])
    for f in report['fit_audits']:
        assert f['latest_training_maturity']<f['refit']
        assert f['latest_training_clock']+245*60<f['refit']
    report['data_kind']='DETERMINISTIC_FABRICATED_ONLY_NOT_MARKET_EVIDENCE'
    report['CPU_seconds']=time.process_time()-started
    report['max_RSS_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['real_numerical_market_fields_parsed']=0
    w.atomic_json(w.HERE/'FULL_SYNTHETIC_REPORT_V1.json',report)
    print(json.dumps({'data_kind':report['data_kind'],'comparisons':18,'identities':145,
      'calendar_units':1240,'CPU_seconds':report['CPU_seconds'],'max_RSS_KiB':report['max_RSS_KiB'],
      'negative_comparisons':sum(x['mean_bounded_score_gain']<0 for x in report['comparisons']),
      'unsupported_comparisons':sum(x['status']=='UNSUPPORTED' for x in report['comparisons']),
      'no_lookahead_fit_checks':len(report['fit_audits'])}))

if __name__=='__main__':main()
