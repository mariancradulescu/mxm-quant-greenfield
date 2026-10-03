"""Pure metadata planning. No broker transport or market-result imports."""
import base64,collections,hashlib,json,zlib
from datetime import datetime,timedelta,timezone,date
from pathlib import Path
from zoneinfo import ZoneInfo
SEED=20261003
WEEK_INDICES=[0,6,12,18,24,30,36,42,48,51]
STATE='research_core_v4/state/'
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def rank(identity):return sha(canonical({'seed':SEED,'identity_tuple':[identity['symbol_id'],identity['symbol'],identity['asset_class']]}))
def roster(rows):
    groups=collections.defaultdict(list)
    for r in rows:
        if r['status']!='STRUCTURALLY_ELIGIBLE':raise ValueError('complete eligible census expected')
        groups[r['asset_class']].append({k:r[k] for k in ['symbol_id','symbol','asset_class']})
    out=[]
    for ctx,ids in sorted(groups.items()):
        for order,ident in enumerate(sorted(ids,key=rank)[:2]):out.append(dict(ident,selection_sha256=rank(ident),rank_in_context=order,context_census_count=len(ids),transport_only_singleton=len(ids)==1))
    if len(out)!=56 or len(groups)!=29:raise ValueError('exact56/29 probe required')
    return out

def subtract(intervals,cut):
    a,b=cut;out=[]
    for x,y in intervals:
        if b<=x or a>=y:out.append((x,y))
        else:
            if x<a:out.append((x,a))
            if b<y:out.append((b,y))
    return out

def utc_wall(dt):
    # Reject ambiguous/nonexistent local boundary rather than guess a fold.
    if dt.utcoffset()!=dt.replace(fold=1).utcoffset():raise ValueError('ambiguous DST wall boundary')
    u=dt.astimezone(timezone.utc)
    if u.astimezone(dt.tzinfo).replace(tzinfo=None)!=dt.replace(tzinfo=None):raise ValueError('nonexistent DST wall boundary')
    return u

def day_intervals(full,day):
    tz=ZoneInfo(full['scheduleTimeZone']);sunday=day-timedelta(days=(day.weekday()+1)%7)
    origin=datetime.combine(sunday,datetime.min.time(),tz);lo=datetime.combine(day,datetime.min.time(),tz);hi=lo+timedelta(days=1)
    intervals=[]
    for r in full['schedule']:
        start=origin+timedelta(seconds=int(r['startSecond']));end=origin+timedelta(seconds=int(r['endSecond']))
        a,b=max(start,lo),min(end,hi)
        if a<b:intervals.append((a,b))
    for h in full.get('holiday',[]):
        hd=date(1970,1,1)+timedelta(days=int(h['holidayDate']))
        matches=(hd.month,hd.day)==(day.month,day.day) if h.get('isRecurring') else hd==day
        if matches:
            a,b=int(h['startSecond']),int(h['endSecond'])
            if a==b==0:a,b=0,86400
            elif b>=a:b=min(86400,b+1)
            else:raise ValueError('holiday interval invalid')
            intervals=subtract(intervals,(lo+timedelta(seconds=a),lo+timedelta(seconds=b)))
    out=[]
    for a,b in intervals:
        x,y=utc_wall(a),utc_wall(b)
        if y-x>=timedelta(minutes=60):out.append((x,y))
    return sorted(out,key=lambda p:(-(p[1]-p[0]).total_seconds(),p[0]))

def materialize(full,monday,index):
    monday=date.fromisoformat(monday)
    for offset in range(5):
        weekday=(index%5+offset)%5;day=monday+timedelta(days=weekday)
        intervals=day_intervals(full,day)
        if intervals:
            a,b=intervals[0];center=a+(b-a)/2;start=center-timedelta(minutes=30)
            start=start.replace(microsecond=0);end=start+timedelta(hours=1)
            frm=int((start-timedelta(seconds=120)).timestamp()*1000);to=int((end+timedelta(seconds=105)).timestamp()*1000)-1
            if to>=int(datetime(2026,9,12,tzinfo=timezone.utc).timestamp()*1000):raise ValueError('calendar/protected guard')
            return {'status':'PLANNED','local_date':day.isoformat(),'signal_from_ms':int(start.timestamp()*1000),'signal_to_ms':int(end.timestamp()*1000),'from_ms':frm,'to_ms':to,'schedule_timezone':full['scheduleTimeZone']}
    return {'status':'NO_WINDOW','reason':'NO_60_MIN_OPEN_INTERVAL_IN_FROZEN_WEEK_FROM_CURRENT_METADATA'}

def build(root):
    root=Path(root);raw=zlib.decompress(base64.b64decode((root/(STATE+'NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64')).read_bytes()))
    if sha(raw)!='4ceb988206c6caf5c0077d12201e9043c5bd640c63fd645c20273fafa9fcb63f':raise ValueError('metadata binding')
    metadata=json.loads(raw);rows=metadata['rows'];ids=roster(rows);byid={r['symbol_id']:r for r in rows}
    design=json.loads((root/(STATE+'NEXT_QUOTE_SEQUENCE_DESIGN_V2.json')).read_bytes());weeks=design['calendar']['iso_week_mondays_utc'];slots=[]
    for ident in ids:
        for wi in WEEK_INDICES:
            window=materialize(byid[ident['symbol_id']]['current_full_metadata'],weeks[wi],wi)
            for side in ['BID','ASK']:
                slot={**ident,**window,'week_index':wi,'iso_week_monday':weeks[wi],'side':side}
                slot['request_id']=sha(canonical(slot));slot['audit_subset']=ident['rank_in_context']==0 and wi==0
                slots.append(slot)
    count=sum(x['status']=='PLANNED' for x in slots)
    if len(slots)!=1120 or count>1120:raise ValueError('probe budget')
    return {'schema':'mxm.v4.quote-support-transport-probe-plan.v1','role':'SUPPORT_TRANSPORT_ONLY_NO_RESPONSE','source_metadata_sha256':sha(raw),'design_v2_sha256':sha((root/(STATE+'NEXT_QUOTE_SEQUENCE_DESIGN_V2.json')).read_bytes()),'frontier_identity_sha256':metadata['frontier_identity_sha256'],'census_count':1576,'seed':SEED,'identity_selection':'SHA256_CANONICAL_JSON_SEED_AND_FULL_IDENTITY_TUPLE_LOWEST_TWO_PER_CONTEXT;SINGLETON_ONE;NO_REPLACEMENT','identities':ids,'week_indices':WEEK_INDICES,'selected_weeks':[weeks[i] for i in WEEK_INDICES],'slot_count':1120,'base_request_count':count,'no_window_side_slots':1120-count,'maximum_base_requests':1120,'maximum_wire_attempts':11200,'maximum_local_compressed_bytes':2000000000,'maximum_run_wall_seconds':7200,'raw_audit_subset_rule':'LOWEST_HASH_IDENTITY_EACH_CONTEXT;WEEK_INDEX0;BOTH_SIDES;NO_REPLACEMENT','maximum_return_raw_bytes':50000000,'historical_capture_by_Work_authorized':False,'full_census_capture_authorized':False,'scientific_response_authorized':False,'slots':slots}

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];p=root/(STATE+'NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json');d=build(root);p.write_bytes(canonical(d)+b'\n');print(json.dumps({'identities':len(d['identities']),'contexts':len({x['asset_class'] for x in d['identities']}),'base_requests':d['base_request_count'],'no_window_slots':d['no_window_side_slots'],'sha256':sha(p.read_bytes())}))
