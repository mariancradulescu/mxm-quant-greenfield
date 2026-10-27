"""Receipt-clock source observability only. No signals, fills or future returns."""
from collections import Counter
AGE_MS=5000
SPAN_NS=300_000_000_000
class SpotProfile:
    def __init__(self,symbols):
        if not symbols or len(set(symbols))!=len(symbols):raise ValueError('SPOT_ROSTER')
        self.books={s:{'first':True,'sides':{},'server_max':None,'start':None,'end':None,
          'counts':Counter(),'reasons':Counter(),'longest':0} for s in symbols}
        self.sequence=0;self.arrival=-1;self.received=-1
    def close(self,b):
        if b['start'] is not None:
            span=b['end']-b['start'];b['counts']['stretches']+=1
            b['counts']['stretches_at_least_5min']+=int(span>=SPAN_NS)
            b['longest']=max(span,b['longest'])
        b['start']=b['end']=None
    def observe(self,*,symbol,sequence,arrival_ns,received_ms,server_ms,bid,ask):
        if (symbol not in self.books or type(sequence) is not int or sequence<=self.sequence or
          type(arrival_ns) is not int or arrival_ns<self.arrival or type(received_ms) is not int or
          received_ms<self.received or (server_ms is not None and type(server_ms) is not int) or
          any(v is not None and (type(v) is not int or v<0) for v in (bid,ask))):raise ValueError('SPOT_EVENT_SCOPE_OR_CLOCK')
        self.sequence=sequence;self.arrival=arrival_ns;self.received=received_ms
        b=self.books[symbol];c=b['counts'];c['events']+=1;reasons=[]
        first=b['first'];b['first']=False
        if first:reasons.append('INITIAL_SNAPSHOT_NOT_FRESHNESS_PROOF')
        if bid is None and ask is None:reasons.append('NO_PRICE_SIDE')
        server_ok=(server_ms is not None and 0<=received_ms-server_ms<=AGE_MS and
                   (b['server_max'] is None or server_ms>=b['server_max']))
        if not server_ok:reasons.append('SERVER_CLOCK_MISSING_STALE_FUTURE_OR_REVERSED')
        if server_ms is not None:b['server_max']=server_ms if b['server_max'] is None else max(b['server_max'],server_ms)
        for name,value in (('bid',bid),('ask',ask)):
            if value is not None:
                c[name+'_updates']+=1
                # Initial latest-price response, even two-sided, is not a new
                # update of both sides. Require subsequent observations per side.
                b['sides'][name]=(value,arrival_ns,server_ms if server_ok and not first else None)
        if any(s not in b['sides'] for s in ('bid','ask')):reasons.append('MISSING_SIDE')
        else:
            for side in ('bid','ask'):
                value,arrived,server=b['sides'][side]
                if value<=0:reasons.append('NONPOSITIVE_SIDE')
                if server is None or not 0<=received_ms-server<=AGE_MS or arrival_ns-arrived>AGE_MS*1_000_000:
                    reasons.append('UNVERIFIED_OR_STALE_SIDE')
            bid_value=b['sides']['bid'][0];ask_value=b['sides']['ask'][0]
            if ask_value<=bid_value:reasons.append('LOCKED_OR_CROSSED_BOOK')
        if reasons:
            c['unavailable']+=1;b['reasons'].update(set(reasons));self.close(b)
        else:
            c['healthy']+=1
            if b['start'] is None or arrival_ns-b['end']>AGE_MS*1_000_000:
                self.close(b);b['start']=arrival_ns
            b['end']=arrival_ns
    def result(self):
        out={}
        for symbol,b in self.books.items():
            self.close(b);c=b['counts']
            out[str(symbol)]={'events':c['events'],'bid_updates':c['bid_updates'],'ask_updates':c['ask_updates'],
              'healthy':c['healthy'],'unavailable':c['unavailable'],'stretches':c['stretches'],
              'stretches_at_least_5min':c['stretches_at_least_5min'],
              'longest_span_bucket':'NONE' if not c['healthy'] else 'AT_LEAST_5_MINUTES' if b['longest']>=SPAN_NS else 'LESS_THAN_5_MINUTES',
              'unavailability_reasons':dict(sorted(b['reasons'].items())),
              'initial_snapshot_not_promoted':True,'between_receipt_liquidity_proven':False,
              'broker_fills_proven':False,'economic_model_executed':False}
            if c['events']!=c['healthy']+c['unavailable']:raise ValueError('SPOT_ALL_EVENTS_RECONCILIATION')
        return out
