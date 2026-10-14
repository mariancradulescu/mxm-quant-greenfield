"""Frozen causal quote-state and session-opening acceptance. No hidden outcomes."""
import math,datetime,bisect
from zoneinfo import ZoneInfo

def iso(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).strftime('%G-W%V')
def holiday_proxy(f,t):
 for h in f.get('holiday',[]):
  try:
   zone=ZoneInfo(h['scheduleTimeZone']);d=datetime.datetime.fromtimestamp(t,datetime.timezone.utc).astimezone(zone);ref=datetime.date(1970,1,1)+datetime.timedelta(days=int(h['holidayDate']));match=(d.month,d.day)==(ref.month,ref.day) if h['isRecurring'] else d.date()==ref
   if match and int(h.get('startSecond',0))<=d.hour*3600+d.minute*60+d.second<int(h.get('endSecond',86400)):return 'CURRENT_NATIVE_HOLIDAY_PROXY_CLOSED_NOT_HISTORICAL_ASOF_CERTIFICATE'
  except (KeyError,ValueError,TypeError):return 'NATIVE_HOLIDAY_SCHEMA_UNRESOLVED'
 return 'NO_CURRENT_NATIVE_HOLIDAY_MATCH_HISTORICAL_LIST_COMPLETENESS_UNKNOWN'
def schedule_clocks(f,start,end):
 tz=ZoneInfo(f['scheduleTimeZone']);out=[]
 for day in range(start,end,86400):
  d=datetime.datetime.fromtimestamp(day+43200,datetime.timezone.utc).astimezone(tz).date()
  sunday=d-datetime.timedelta(days=(d.weekday()+1)%7)
  for slot in f.get('schedule',[]):
   local=datetime.datetime.combine(sunday,datetime.time(),tz)+datetime.timedelta(seconds=int(slot['startSecond']))
   op=int(local.timestamp());close=int((datetime.datetime.combine(sunday,datetime.time(),tz)+datetime.timedelta(seconds=int(slot['endSecond']))).timestamp())
   if day<=op<day+86400 and op+8100<close and start<=op<end:
    out.extend([{'t':op+1200,'open_proxy':op,'kind':'REOPEN','date':local.date().isoformat(),'schedule':'CURRENT_WEEKLY_SCHEDULE_PROXY_NOT_HISTORICAL_HOLIDAY_AUTHORITY'}, {'t':op+7200,'open_proxy':op,'kind':'CONTROL','date':local.date().isoformat(),'schedule':'CURRENT_WEEKLY_SCHEDULE_PROXY_NOT_HISTORICAL_HOLIDAY_AUTHORITY'}])
 out=list({(v['t'],v['kind']):v for v in out}.values())
 for v in out:v['holiday_proxy']=holiday_proxy(f,v['t'])
 return out
def quote_state(bid,ask,t,ttl=300000,skew=None):
 def last(rows):
  vv=[r for r in rows if r[0]<=t]
  if not vv:return None,'NO_CAUSAL_SEED'
  tm=max(r[0] for r in vv);pp={r[1] for r in vv if r[0]==tm}
  if len(pp)!=1:return None,'SAME_MS_CONFLICT'
  if t-tm>ttl:return None,'STATE_EXPIRED'
  return (tm,next(iter(pp))),None
 b,br=last(bid);a,ar=last(ask)
 if br or ar:return {'state':br or ar,'valid':False}
 if b[1]<=0 or a[1]<b[1]:return {'state':'CROSSED_OR_INVALID','valid':False}
 if skew is not None and abs(b[0]-a[0])>skew:return {'state':'SIDE_SKEW','valid':False}
 return {'state':'CAUSAL_L1_STATE_REFERENCE_NOT_FILL','valid':True,'bid':b[1]/100000,'ask':a[1]/100000,'mid':(a[1]+b[1])/200000,'bid_time_ms':b[0],'ask_time_ms':a[0],'age_ms':max(t-b[0],t-a[0]),'side_skew_ms':abs(b[0]-a[0]),'expiry_ms':ttl}
def feature(bars,t,op,kind):
 # All bars must be closed with 5-second publication allowance before decision.
 tt=sorted(x for x in bars if x+305<=t)
 if len(tt)<15:return {'supported':False,'reason':'PRIOR_BARS_LT15'}
 if t-tt[-1]>1200:return {'supported':False,'reason':'LATEST_CLOSED_M5_BAR_STALE_GT20MIN'}
 prior=tt[-192:];ranges=[10000*(bars[x][1]-bars[x][2])/bars[x][3] for x in prior]
 s=sorted(ranges);tail=s[int((len(s)-1)*.95)];scale=sum(ranges[-12:])/min(12,len(ranges));z={'supported':True,'kind':kind,'model_side':0,'gap_side':0,'momentum_side':0,'scale_bps':scale,'tail_bps':tail,'max_observed_prior_gap_bps':max([abs(10000*math.log(bars[b][0]/bars[a][3])) for a,b in zip(prior,prior[1:]) if b-a>1800] or [0]),'prior_last_open':tt[-1]}
 if kind!='REOPEN':return z|{'reason':'MATCHED_INTRADAY_CONTROL_MODEL_CASH'}
 opening=[op+i*300 for i in range(3)]
 if not all(x in bars and x+305<=t for x in opening):return {'supported':False,'reason':'ACTUAL_FIRST_THREE_M5_BARS_UNAVAILABLE'}
 before=[x for x in tt if x<op]
 if not before or op-before[-1]<6*3600:return {'supported':False,'reason':'NO_AUTHENTIC_M5_SESSION_GAP_GE6H'}
 session=[before[-1]]
 for x in reversed(before[:-1]):
  if session[-1]-x>1800:break
  session.append(x)
 if len(session)<12:return {'supported':False,'reason':'PRIOR_SESSION_LT12_M5_BARS'}
 hi=max(bars[x][1] for x in session);lo=min(bars[x][2] for x in session);last=bars[before[-1]][3];cl=[bars[x][3] for x in opening];sg=lambda x:int(x>0)-int(x<0)
 # Range acceptance is a new causal admission rule; comparator trades every
 # ex-ante economically feasible reopening clock, including model abstentions.
 z.update(model_side=1 if all(v>hi for v in cl) else -1 if all(v<lo for v in cl) else 0,gap_side=sg(cl[-1]-last),momentum_side=sg(cl[-1]-bars[opening[0]][0]),prior_session_bars=len(session),prior_session_high=hi,prior_session_low=lo,reason='SUPPORTED_RANGE_ACCEPTANCE_OR_ABSTENTION')
 return z
