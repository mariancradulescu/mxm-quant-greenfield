"""Independent offline-array/Decimal policy and one-account reconstruction.

Source snapshots use side-group arrays and bisect, not C# streaming state.
"""
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal as D,localcontext
import hashlib,json
from pathlib import Path
def need(ok,why):
    if not ok:raise ValueError('INTRINSIC_REFERENCE_'+why)
def stamp(ms):return datetime.fromtimestamp(ms/1000,timezone.utc)
def snapshots(path):
    sides={'bid':defaultdict(set),'ask':defaultdict(set)};rows=0;previous=-1
    with Path(path).open() as stream:
        for line in stream:
            e=json.loads(line);t=e['t'];side=e['side'];v=e['raw']
            need(type(t) is int and t>=previous and side in sides and type(v) is int and v>0,'SOURCE_ROW')
            previous=t;sides[side][t].add(v);rows+=1
    arrays={k:sorted(v) for k,v in sides.items()}
    values={k:[next(iter(v[t])) if len(v[t])==1 else None for t in arrays[k]] for k,v in sides.items()}
    all_times=sorted(set(arrays['bid'])|set(arrays['ask']))
    for t in all_times:
        ii={k:bisect_right(arrays[k],t)-1 for k in arrays}
        vals={k:values[k][i] if i>=0 else None for k,i in ii.items()}
        times={k:arrays[k][i] if i>=0 else None for k,i in ii.items()}
        bad=any(x is None for x in vals.values()) or (vals['ask'] or 0)<=(vals['bid'] or 0) or any(t-v>5000 for v in times.values() if v is not None)
        yield t,None if bad else (D(vals['bid'])/100000,D(vals['ask'])/100000)

def reference(paths):
    with localcontext() as ctx:
        ctx.prec=60;return _reference(paths)
def _reference(paths):
    cash=D(200);peak=cash;dd=D(0);holding=None;pending=None;blocked=-1;seq=0
    day=None;trend=0;extreme=None;target=0;due=0;ledger=[];reject=[];weeks=defaultdict(int)
    decisions=hashlib.sha256();last_quote=None;segments=[];fault=None;count_decisions=0
    def fee(price,bid):return max(D(1000)*price*30/D(1000000),D('.01'))/bid
    def mark(bid,ask):
        if holding is None:return cash
        direction,entry,stop=holding;usd=(bid-entry if direction>0 else entry-ask)*1000
        return cash+usd/(ask if usd>=0 else bid)
    def trade(kind,t,direction,price,commission,gross,reason=None):
        nonlocal cash
        cash+=gross-commission
        ledger.append({'Kind':kind,'Utc':t,'Symbol':'EURUSD','Direction':direction,'Price':price,'Units':D(1000),
          'CashEur':cash,'CommissionEur':commission,'GrossEur':gross,**({'Reason':reason} if reason else {})})
    def exit(t,bid,ask,reason):
        nonlocal holding
        direction,entry,_=holding;price=bid-D('.00002') if direction>0 else ask+D('.00002')
        usd=(price-entry)*1000*direction;gross=usd/(ask if usd>=0 else bid)
        trade('EXIT',t,direction,price,fee(price,bid),gross,reason);holding=None
    def enter(t,bid,ask,direction):
        nonlocal holding
        price=ask+D('.00002') if direction>0 else bid-D('.00002');cost=fee(price,bid)
        stop=price-direction*D('.0012')
        if stop<=0 or (stop>=bid if direction>0 else stop<=ask):reject.append('REJECT_STOP_ALREADY_TOUCHED_AT_ENTRY');return
        if cash<=0:reject.append('REJECT_UNVERIFIED_OR_INVALID_ACCOUNT_INPUT');return
        if D(50)>cash*D('.4'):reject.append('REJECT_MARGIN_FRACTION');return
        if cash-50-cost<0:reject.append('REJECT_FREE_MARGIN_RESERVE');return
        if D('1.2')/bid+D('.2')>cash*D('.02'):reject.append('REJECT_AGGREGATE_STOP_RISK_EXCESS');return
        trade('ENTRY',t,direction,price,cost,D(0));holding=(direction,price,stop)
        w=stamp(t).isocalendar();weeks[f'{w.year}-W{w.week:02}']+=1
    for path in paths:
        segment_decisions=hashlib.sha256();local_decisions=0;groups=0;invalid=0
        for t,q in snapshots(path):
            groups+=1
            if q is None:
                invalid+=1;pending=None;blocked=t;trend=target=0;extreme=None;due=0
                if holding is not None:fault='OPEN_EXPOSURE_INSTRUMENT_UNPRICEABLE';break
                continue
            bid,ask=q;last_quote=q;stopped=False
            if holding is not None and (bid<=holding[2] if holding[0]>0 else ask>=holding[2]):
                exit(t,bid,ask,'OBSERVED_QUOTE_STOP');pending=None;blocked=t;stopped=True
            if not stopped and pending is not None:
                observed,desired=pending
                if t>=observed+5000:pending=None
                elif t>=observed+250:
                    pending=None
                    if holding is not None and desired!=holding[0]:exit(t,bid,ask,'EXPLICIT_POLICY_FLAT' if desired==0 else 'EXPLICIT_POLICY_REVERSAL')
                    if holding is None and desired:enter(t,bid,ask,desired)
            equity=mark(bid,ask);peak=max(peak,equity);dd=max(dd,peak-equity)
            if equity<=0 or equity<(50 if holding else 0):reject.append('SIMULATED_EQUITY_OR_MARGIN_HALT_NOT_BROKER_STOPOUT');fault='CAPITAL_HALTED';break
            dt=stamp(t);key=dt.strftime('%Y%m%d');mid=(bid+ask)/2
            if key!=day:day=key;trend=0;extreme=None
            desired=None;minute=dt.hour*60+dt.minute
            if dt.weekday()>=5 or minute<420 or minute>=955:
                trend=0;extreme=None
                if target:desired=0
            elif target and t>=due:desired=0
            elif extreme is None:extreme=mid
            else:
                direction=1 if mid>extreme else -1
                change=(trend==0 and abs(mid-extreme)>=D('.0005')) or (trend>0 and extreme-mid>=D('.0005')) or (trend<0 and mid-extreme>=D('.0005'))
                if change:trend=direction;extreme=mid;desired=direction
                elif trend>0:extreme=max(extreme,mid)
                elif trend<0:extreme=min(extreme,mid)
            if desired is not None:
                target=desired;due=t+300000 if desired else 0;seq+=1;local_decisions+=1;count_decisions+=1
                raw=f'{t}|{seq}|{desired}\n'.encode();segment_decisions.update(raw);decisions.update(raw)
                pending=(t,desired) if t>blocked else None
        equity=mark(*last_quote) if last_quote else cash
        segments.append({'decisions':local_decisions,'decision_sha256':segment_decisions.hexdigest(),'groups_processed':groups,'invalid_groups':invalid,
          'fault':fault,'cash':cash,'equity':equity,'drawdown':dd,'ledger':list(ledger),'weeks':dict(weeks),'rejections':list(reject),'open':holding is not None})
        if fault:break
    return {'segments':segments,'decisions':count_decisions,'decision_sha256':decisions.hexdigest()}

def reconcile(reports,expected):
    need(len(reports)==len(expected['segments']),'SEGMENT_COUNT')
    def close(a,b):need(abs(D(str(a))-D(str(b)))<D('1e-18'),'MONETARY_MISMATCH')
    for actual,e in zip(reports,expected['segments']):
        need(actual['decisions']==e['decisions'] and actual['decision_sha256']==e['decision_sha256'] and
             actual['groups_processed']==e['groups_processed'] and actual['invalid_groups']==e['invalid_groups'],'CAUSAL_SOURCE_AND_DECISIONS')
        if e['fault'] and e['fault']!='CAPITAL_HALTED':
            need(actual['fault'] is not None and e['fault'] in actual['fault'] and actual['account'] is None,'INVALID_FUNDED_PATH_CANNOT_REPORT');continue
        need(actual['fault'] is None and actual['account'] is not None,'ACCOUNT_PRESENT')
        a=actual['account'];need(len(a['Ledger'])==len(e['ledger']),'LEDGER_COUNT')
        for row,ref in zip(a['Ledger'],e['ledger']):
            need(set(row)==set(ref),'LEDGER_FIELDS')
            for key in ref:
                if key=='Utc':
                    delta=datetime.fromisoformat(row[key].replace('Z','+00:00'))-datetime(1970,1,1,tzinfo=timezone.utc)
                    need(delta.days*86400000+delta.seconds*1000+delta.microseconds//1000==ref[key],'EXECUTION_CLOCK')
                elif key in ('Price','Units','CashEur','CommissionEur','GrossEur'):close(row[key],ref[key])
                else:need(row[key]==ref[key],'ORDER_EVENT')
        close(a['FinalCashEur'],e['cash']);close(a['MarkedEquityEur'],e['equity']);close(a['MaxDrawdownEur'],e['drawdown'])
        need(a['EntriesByIsoWeek']==e['weeks'] and a['Rejections']==e['rejections'] and a['InitialCapitalEur']==200 and
             a['AcceptedEntries']==sum(e['weeks'].values()) and a['OpenPositions']==int(e['open']) and
             not a['Hard21Proven'] and not a['BrokerFillsProven'] and not a['CostsBrokerVerified'],'SINGLE_CAPITAL_COUNTS')
    return True
