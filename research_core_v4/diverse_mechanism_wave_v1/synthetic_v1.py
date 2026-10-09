"""Two new fabricated source packages, never the old100-shard campaign."""
import json
from datetime import datetime,timezone
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n

def rows(ordinal,digits):
    result=[];price=1000.;variant=(ordinal-1)%8
    for i in range(72):
        h=i//12
        move=0. if h==0 or variant==5 else (1. if h==1 else 2.)
        if h>=3 and variant in (1,6):move=-2.
        o=price;c=o+move;price=c
        row={'time_utc':datetime.fromtimestamp(n.START+i*300,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'open':format(o,f'.{digits}f'),'high':format(max(o,c)+.0,f'.{digits}f'),'low':format(min(o,c)-.0,f'.{digits}f'),'close':format(c,f'.{digits}f'),'tick_volume':str(0 if variant==3 and h==2 else 10 if h>=2 else 1)}
        if variant==2 and i==26:continue
        if variant==4 and 24<=i<36:continue
        result.append(row)
    return result

def fabricated_shard(idx,master,digits):
    raw,meta=old.fabricated_shard(1,idx,master,digits);obj=json.loads(raw)
    for item in obj['items']:
        item['rows']=rows(item['ordinal'],digits[item['symbol_id']]);item['classification']='SHALLOW_SUPPORT_COMPLETE'
    raw=n.canonical.canonical(obj);meta=dict(meta)
    meta['ROW_COUNT']=sum(len(item['rows']) for item in obj['items']);meta['PLAINTEXT_CANONICAL_SHA256']=n.sha(raw)
    times=[r['time_utc'] for item in obj['items'] for r in item['rows']];meta['FIRST_TIMESTAMP']=min(times);meta['LAST_TIMESTAMP']=max(times)
    return raw,meta
