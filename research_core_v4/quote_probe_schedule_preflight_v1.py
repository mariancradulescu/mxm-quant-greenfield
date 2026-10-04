"""Current metadata preflight only. Correct holiday timezones; never changes plan."""
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from research_core_v4.quote_probe_plan_v1 import utc_wall,subtract,canonical,sha

WINDOW_KEYS=('status','local_date','signal_from_ms','signal_to_ms','from_ms','to_ms','schedule_timezone','reason')
def day_intervals(full,day):
    tz=ZoneInfo(full['scheduleTimeZone'])
    sunday=day-timedelta(days=(day.weekday()+1)%7)
    origin=datetime.combine(sunday,datetime.min.time(),tz)
    lo=datetime.combine(day,datetime.min.time(),tz);hi=lo+timedelta(days=1)
    intervals=[]
    if not isinstance(full['schedule'],list):raise ValueError('schedule required')
    for q in full['schedule']:
        a,b=int(q['startSecond']),int(q['endSecond'])
        if not 0<=a<b<=604800:raise ValueError('weekly interval')
        x,y=max(origin+timedelta(seconds=a),lo),min(origin+timedelta(seconds=b),hi)
        if x<y:intervals.append((utc_wall(x),utc_wall(y)))
    for h in full.get('holiday',[]):
        if not all(k in h for k in ['scheduleTimeZone','holidayDate','isRecurring']):raise ValueError('holiday required timezone/date/recurrence')
        hz=ZoneInfo(h['scheduleTimeZone'])
        if type(h['isRecurring']) is not bool:raise ValueError('holiday recurrence')
        hd=date(1970,1,1)+timedelta(days=int(h['holidayDate']))
        dates=[]
        if h['isRecurring']:
            for year in [day.year-1,day.year,day.year+1]:
                try:dates.append(date(year,hd.month,hd.day))
                except ValueError:pass # annual Feb29 is absent in non-leap years
        else:dates=[hd]
        a,b=int(h.get('startSecond',0)),int(h.get('endSecond',0))
        if not 0<=a<=b<=86399:raise ValueError('holiday seconds')
        if a==b==0:a,b=0,86400
        else:b+=1 # broker holiday endSecond inclusive
        for d in dates:
            base=datetime.combine(d,datetime.min.time(),hz)
            cut=(utc_wall(base+timedelta(seconds=a)),utc_wall(base+timedelta(seconds=b)))
            intervals=subtract(intervals,cut)
    return sorted([(a,b) for a,b in intervals if b-a>=timedelta(hours=1)],key=lambda p:(-(p[1]-p[0]).total_seconds(),p[0]))

def materialize(full,monday,index):
    monday=date.fromisoformat(monday)
    for offset in range(5):
        day=monday+timedelta(days=(index%5+offset)%5)
        intervals=day_intervals(full,day)
        if intervals:
            a,b=intervals[0];start=(a+(b-a)/2-timedelta(minutes=30)).replace(microsecond=0);end=start+timedelta(hours=1)
            frm=int((start-timedelta(seconds=120)).timestamp()*1000);to=int((end+timedelta(seconds=105)).timestamp()*1000)-1
            if to>=int(datetime(2026,9,12,tzinfo=timezone.utc).timestamp()*1000):raise ValueError('protected calendar boundary')
            return dict(status='PLANNED',local_date=day.isoformat(),signal_from_ms=int(start.timestamp()*1000),signal_to_ms=int(end.timestamp()*1000),from_ms=frm,to_ms=to,schedule_timezone=full['scheduleTimeZone'])
    return dict(status='NO_WINDOW',reason='NO_60_MIN_OPEN_INTERVAL_IN_FROZEN_WEEK_FROM_CURRENT_METADATA')

def preflight(meta,account,plan):
    from m6.ctrader_proto import OpenApiMessages_pb2 as oa
    from google.protobuf.json_format import MessageToDict
    fresh={};failures=[]
    for ident in plan['identities']:
        sid=ident['symbol_id']
        req=oa.ProtoOASymbolByIdReq(ctidTraderAccountId=account);req.symbolId.append(sid)
        res=meta.request(req)
        found=[s for s in res.symbol if int(s.symbolId)==sid]
        if len(res.symbol)!=1 or len(found)!=1 or not found[0].IsInitialized():
            fresh[sid]={};continue # explicit unresolved windows; no historical call
        full=MessageToDict(found[0],preserving_proto_field_name=False)
        # Keep only non-price calendar inputs, with holiday's own timezone.
        fresh[sid]={k:full.get(k,[]) if k in ['schedule','holiday'] else full.get(k) for k in ['scheduleTimeZone','schedule','holiday']}
    checked=set()
    for slot in plan['slots']:
        key=(slot['symbol_id'],slot['week_index'])
        if key in checked:continue
        checked.add(key);expected={k:slot[k] for k in WINDOW_KEYS if k in slot}
        try:
            actual=materialize(fresh[slot['symbol_id']],slot['iso_week_monday'],slot['week_index'])
            if actual!=expected:failures.append(dict(symbol_id=key[0],week_index=key[1],reason='EXACT_WINDOW_MISMATCH',expected=expected,actual=actual))
        except (ValueError,KeyError,TypeError):failures.append(dict(symbol_id=key[0],week_index=key[1],reason='INVALID_OR_UNRESOLVED_SCHEDULE_TIMEZONE_HOLIDAY'))
    return dict(schema='mxm.v4.probe-schedule-preflight.v1',status='EXACT_FROZEN_WINDOWS_MATCH' if not failures else 'STOP_BEFORE_HISTORICAL_SCHEDULE_MISMATCH',identities_checked=len(fresh),identity_week_windows_checked=len(checked),base_slot_count=len(plan['slots']),fresh_calendar_metadata_sha256=sha(canonical(fresh)),mismatches=failures,historical_requests_sent=0,orders_sent=0,responses_computed=False,plan_mutated=False)
