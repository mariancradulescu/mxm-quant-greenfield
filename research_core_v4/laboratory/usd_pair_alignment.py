"""Independent full-array/bisect alignment reference; no strategy, decryption or broker access."""
from bisect import bisect_left,bisect_right
from collections import Counter,defaultdict
from decimal import Decimal,localcontext,ROUND_HALF_UP
import hashlib,json
from pathlib import Path
SYMBOLS=('EURUSD','GBPUSD')
MAX_AGE_MS=5000

def need(ok,why):
    if not ok:raise ValueError('USD_PAIR_'+why)
def digest(data):return hashlib.sha256(data).hexdigest()
def reference(eur,gbp,trace=None):
    records={};timeline={};counts={};touch=defaultdict(set);conflicts={s:0 for s in SYMBOLS}
    for symbol,path in zip(SYMBOLS,(eur,gbp)):
        same=defaultdict(list);count=0;last=-1
        with Path(path).open() as source:
            for line in source:
                r=json.loads(line);t=r['t'];side=r['side'];raw=r['raw']
                need(type(t) is int and t>=last and t>=0 and side in ('bid','ask') and type(raw) is int and raw>0,'ROW_OR_ORDER')
                last=t;count+=1;same[t,side].append(raw);touch[t].add(symbol)
        counts[symbol]=count;bad=set()
        for side in ('bid','ask'):
            cells=[]
            for (stamp,label),values in same.items():
                if label!=side:continue
                unique=set(values);conflict=len(unique)>1
                if conflict:bad.add(stamp)
                cells.append((stamp,None if conflict else unique.pop(),conflict))
            cells.sort();records[symbol,side]=cells;timeline[symbol,side]=[c[0] for c in cells]
        conflicts[symbol]=len(bad)
    def book(symbol,t,strict=False):
        result=[]
        for side in ('bid','ask'):
            key=symbol,side;index=(bisect_left if strict else bisect_right)(timeline[key],t)-1
            if index<0:result.append((None,None,False))
            else:
                stamp,raw,bad=records[key][index];result.append((raw,stamp,bad))
        return result
    def canon(b):return ','.join('-' if n is None else str(int(n)) for cell in b for n in cell)
    def check(b,t,label):
        if any(x[2] for x in b):return label+'_CONFLICT'
        if any(x[0] is None for x in b):return label+'_MISSING'
        if b[1][0]<b[0][0]:return label+'_CROSSED'
        if any(t-x[1]>MAX_AGE_MS for x in b):return label+'_STALE'
        return ''
    def convert(b):
        with localcontext() as ctx:
            ctx.prec=60;scale=Decimal('0.00000001')
            gain=(Decimal(10000000)/b[1][0]).quantize(scale,rounding=ROUND_HALF_UP)
            loss=(-Decimal(10000000)/b[0][0]).quantize(scale,rounding=ROUND_HALF_UP)
            return f'{gain:.8f},{loss:.8f}'
    states=hashlib.sha256();routes=hashlib.sha256();marks=hashlib.sha256();routing=Counter();crossed={s:0 for s in SYMBOLS};fxonly=0
    def add(h,line):h.update((line+'\n').encode())
    for t in sorted(touch):
        eurbook=book('EURUSD',t);gbpbook=book('GBPUSD',t)
        for symbol,b in [('EURUSD',eurbook),('GBPUSD',gbpbook)]:
            if symbol in touch[t] and all(x[0] is not None for x in b) and b[1][0]<b[0][0]:crossed[symbol]+=1
        add(states,f'{t}|{canon(eurbook)}|{canon(gbpbook)}')
        if 'GBPUSD' in touch[t]:
            prior=book('EURUSD',t,strict=True)
            code=check(gbpbook,t,'GBP') or check(prior,t,'FX') or 'READY_STRICT_PRIOR_FX';routing[code]+=1
            if code=='READY_STRICT_PRIOR_FX':need(all(x[1]<t for x in prior),'STRICT_PRIOR_FX')
            line=f'{t}|{code}|{canon(gbpbook)}|{canon(prior)}|'+(convert(prior) if code=='READY_STRICT_PRIOR_FX' else '-')
            add(routes,line)
            if trace is not None:trace.append(line)
        if 'EURUSD' in touch[t]:
            fxonly+=int('GBPUSD' not in touch[t])
            code=check(gbpbook,t,'GBP') or check(eurbook,t,'FX') or 'VALUATION_ONLY'
            add(marks,f'{t}|{code}|{canon(gbpbook)}|{canon(eurbook)}|'+(convert(eurbook) if code=='VALUATION_ONLY' else '-'))
    return {'Rows':sum(counts.values()),'Groups':len(touch),'SourceRows':counts,'Routing':dict(routing),'Conflicts':conflicts,
            'Crossed':crossed,'FxOnlyMarkGroups':fxonly,'StateSha256':states.hexdigest(),'RoutingSha256':routes.hexdigest(),'MarkSha256':marks.hexdigest()}

def verify(eur,gbp,report):
    value=json.loads(Path(report).read_bytes())
    need(value['schema']=='mxm.csharp.usd-pair-source-alignment.v1' and value['max_age_ms']==MAX_AGE_MS,'REPORT_CONTRACT')
    need(value['eur_file_sha256']==digest(Path(eur).read_bytes()) and value['gbp_file_sha256']==digest(Path(gbp).read_bytes()),'SOURCE_HASHES')
    expected=reference(eur,gbp);need(value['result']==expected,'EVERY_GROUP_ROUTING_AND_MARK_HASH')
    need(value['typed_routing_snapshots']==sum(expected['Routing'].values()) and value['typed_valuation_snapshots']>0,'TYPED_CONSUMER_CALLBACKS')
    need(value['broker_orders']==value['strategy_trials']==value['economic_outcomes']==0 and
         all(value[k] is False for k in ('economic_edge_proven','hard21_proven','historical_arrival_order_proven','historical_fills_proven','account_replay_executed')) and
         value['source_timestamps_not_arrivals'] is True,'NO_FALSE_ECONOMIC_OR_NATIVE_PROMOTION')
    return {'schema':'mxm.independent.usd-pair-alignment.v1','every_state_routing_mark_group_checked':True,
            'source_rows':expected['SourceRows'],'groups':expected['Groups'],'routing':expected['Routing'],
            'state_sha256':expected['StateSha256'],'routing_sha256':expected['RoutingSha256'],'mark_sha256':expected['MarkSha256'],
            'broker_orders':0,'strategy_trials':0,'economic_outcomes':0,'economic_edge_proven':False,'hard21_proven':False,'account_replay_executed':False}
if __name__=='__main__':
    import sys
    need(len(sys.argv)==5,'EUR_GBP_REPORT_RECEIPT_ARGUMENTS')
    result=verify(*sys.argv[1:4]);Path(sys.argv[4]).write_text(json.dumps(result,sort_keys=True)+'\n')
