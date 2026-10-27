"""Independent decimal debit-side graph/reference; no strategy, order or cash path."""
import json,subprocess,tempfile
from collections import deque,Counter
from decimal import Decimal as D,localcontext,ROUND_CEILING
from pathlib import Path
from .common import need,encoded,bytes_digest
from .universe_commission_checks import terms,fee
ROOT=Path(__file__).resolve().parents[2]
PROJECT='research_core_v4/laboratory/csharp/observed_cost_fx/MxmObservedCostFx.csproj'
AGE=5000
class FxHold(ValueError):pass
def ceil18(x):return x.quantize(D('1e-18'),rounding=ROUND_CEILING)
def route(instruments,source,target):
    if not source or not target:raise FxHold('FX_MISSING_ASSET')
    if source==target:return []
    q=deque([(source,[],{source})]);solutions=[];shortest=4
    while q:
        asset,path,visited=q.popleft()
        if len(path)>=shortest or len(path)>=3:continue
        for i in instruments:
            if i['BaseAsset']==asset:next_asset=i['QuoteAsset'];rev=False
            elif i['QuoteAsset']==asset:next_asset=i['BaseAsset'];rev=True
            else:continue
            if next_asset in visited:continue
            p=path+[dict(Source=i['Source'],Reverse=rev)]
            if next_asset==target:
                if len(p)<shortest:solutions=[];shortest=len(p)
                if len(p)==shortest:solutions.append(p)
            else:q.append((next_asset,p,visited|{next_asset}))
    if not solutions:raise FxHold('FX_NO_DECLARED_PATH_WITHIN_THREE_LEGS')
    if len(solutions)>1:raise FxHold('FX_AMBIGUOUS_SHORTEST_METADATA_PATH')
    return solutions[0]
def empty():return dict(bid=None,ask=None,bt=None,at=None,open=True,epoch=1,last=None)
def update(b,bid,ask,t):
    b['last']=t
    if bid is not None:b['bid']=D(str(bid));b['bt']=t
    if ask is not None:b['ask']=D(str(ask));b['at']=t

def rate(instruments,books,source,target,t):
    path=route(instruments,source,target);value=D(1);max_age=0
    for leg in path:
        b=books.get(leg['Source']);bid=b['bid'] if b else None;ask=b['ask'] if b else None
        if not b or not b['open'] or bid is None or ask is None or bid<=0 or ask<bid or b['bt']>t or b['at']>t or t-b['bt']>AGE or t-b['at']>AGE:
            raise FxHold('FX_REQUIRED_BOOK_UNOBSERVED_INVALID_OR_TOO_OLD')
        max_age=max(max_age,t-b['bt'],t-b['at'])
        value=ceil18(value*ceil18(1/bid if leg['Reverse'] else ask))
    return dict(Rate=value,Path=path,MaximumSideAgeMs=max_age,Classification='OBSERVED_UPWARD_ROUNDED_COST_SIDE_ESTIMATE_NOT_BROKER_CHARGE',ExecutabilityProven=False,SourceTimestampCertified=False)
def fixture_reference(data):
    books={i['Source']:empty() for i in data['instruments']};out=[]
    with localcontext() as ctx:
        ctx.prec=70
        for a in data['actions']:
            op=a['op'];t=a['now']
            if op=='observe':update(books[a['source']],a['bid'],a['ask'],t)
            elif op=='clock':
                from datetime import datetime,timezone
                if not a['simulation']:
                    out.append(dict(status='CLOCK',value=t) if t>=0 else dict(status='HOLD',reason='FX_INVALID_PROCESS_CLOCK'))
                elif not a['utc'].endswith('Z'):
                    out.append(dict(status='HOLD',reason='FX_INVALID_SIMULATION_CLOCK'))
                else:
                    stamp=datetime.fromisoformat(a['utc'].replace('Z','+00:00'));delta=stamp-datetime(1970,1,1,tzinfo=timezone.utc)
                    value=delta.days*86400000+delta.seconds*1000+delta.microseconds//1000
                    out.append(dict(status='CLOCK',value=value) if value>=0 else dict(status='HOLD',reason='FX_INVALID_SIMULATION_CLOCK'))
            elif op in ('begin','end'):
                b=empty();b['open']=op=='begin';books[a['source']]=b
            else:
                try:out.append(dict(status='ESTIMATE',estimate=rate(data['instruments'],books,a['from'],a['to'],t)))
                except FxHold as e:out.append(dict(status='HOLD',reason=str(e)))
    return out
def run(data,mode='--fixture'):
    with tempfile.TemporaryDirectory() as d:
        a=Path(d)/'input.json';b=Path(d)/'output.json';a.write_bytes(encoded(data))
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',mode,str(a),str(b)],check=True,capture_output=True)
        return json.loads(b.read_bytes(),parse_float=D)
def source_reference(data):
    books={s:empty() for s in data['sources']};metadata={i['symbol_id']:i for i in data['terms']};out=[]
    with localcontext() as ctx:
        ctx.prec=70
        for e in data['events']:
            sid=e['symbol'];t=e['arrival_ns']//1000000;b=books[str(sid)]
            update(b,D(e['bid'])/100000 if e['bid'] is not None else None,D(e['ask'])/100000 if e['ask'] is not None else None,t)
            status='ESTIMATE';ceiling=None
            try:
                if b['bid'] is None or b['ask'] is None or b['bid']<=0 or b['ask']<b['bid'] or t-b['bt']>AGE or t-b['at']>AGE:raise FxHold('SOURCE_TICKET_BOOK_UNOBSERVED_INVALID_OR_TOO_OLD')
                i=metadata[sid];terms_i=terms(i);costs={}
                kind=terms_i['Kind'];quote=terms_i['QuoteAsset']
                def fx(a,b):return rate(data['instruments'],books,a,b,t)['Rate']
                if terms_i['Rate']:
                    asset='USD' if kind in (1,2) else quote;costs[asset]=str(fx(asset,'EUR'))
                if terms_i['Minimum']:
                    asset=terms_i['MinimumAsset'];costs[asset]=str(fx(asset,'EUR'))
                u=str(fx(quote,'USD')) if kind==1 and terms_i['Rate'] else None
                fees=[]
                for p in (b['bid'],b['ask']):
                    priced={**i,'fill':dict(volume_cents=terms_i['MinimumVolume'],price=str(p),usd_per_quote=u,cost_eur_per_asset=costs)}
                    fees.append(fee(priced,terms_i)['UnroundedFeeEur'])
                ceiling=ceil18(max(fees))
            except FxHold as ex:status=str(ex)
            except (ValueError,KeyError):status='SOURCE_FEE_UNRESOLVED'
            out.append(dict(sequence=e['sequence'],symbol=sid,status=status,per_side_ceiling_eur=ceiling))
    return out
def reconcile_source(data,actual):
    normalized=[{**r,'per_side_ceiling_eur':None if r['per_side_ceiling_eur'] is None else D(r['per_side_ceiling_eur'])} for r in actual]
    expected=source_reference(data);need(normalized==expected,'EVERY_OBSERVED_COST_FX_SOURCE_ESTIMATE')
    counts={str(s):dict(sorted(Counter(r['status'] for r in expected if r['symbol']==s).items())) for s in (1,2,250)}
    return counts
