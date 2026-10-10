import math
def feature(bid,ask,digits):
 if not 0<bid<ask or not all(math.isfinite(x) for x in (bid,ask)) or not 0<=digits<=8:return {'direction':0,'level':0.,'distance':0.,'headroom_bps':0.,'stop_distance':0.,'reason':'INVALID'}
 mid=(bid+ask)/2;q=10.**(3-digits);level=math.floor(mid/q+0.5)*q;delta=mid-level;dist=abs(delta)
 reason='ON_LEVEL' if dist<=q*1e-10 else 'OUTSIDE_BARRIER_ZONE' if dist>q/4 else 'SIGNAL'
 return {'direction':(1 if delta>0 else -1) if reason=='SIGNAL' else 0,'level':level,'distance':dist,'headroom_bps':10000*(q/2-dist)/mid,'stop_distance':dist+2*(ask-bid),'reason':reason}
def changed_point(record):
 from m6.cost_evidence import decode_ctrader_tick_page
 if record is None:return None,'NO_BOUNDARY'
 v={};age={}
 for page in record['raw_pages']:
  if page.get('hasMore') or 'error_code' in page:return None,'PAGE_GAP_OR_ERROR'
  seen={};last=None;changes=[]
  for x in decode_ctrader_tick_page(page['encoded']):
   t=int(x.timestamp_ms);price=int(x.raw_tick)
   if t in seen and seen[t]!=price:return None,'AMBIGUOUS_SAME_MS'
   seen[t]=price
   if last is not None and last!=price:changes.append((t,price/100000))
   last=price
  if not changes:return None,'NO_OBSERVED_PRICE_CHANGE'
  ts,price=changes[-1];a=record['boundary']*1000-ts
  if not 0<=a<=5000:return None,'CHANGED_PRICE_AGE_GT5S'
  v[page['side']]=price;age[page['side']]=a
 if set(v)!={'bid','ask'} or not 0<v['bid']<v['ask']:return None,'INVALID_QUOTE'
 return {**v,'mid':sum(v.values())/2,'age_ms':max(age.values()),'spread_bps':10000*math.log(v['ask']/v['bid'])},'VALID'

def allocate(events,times):
 chosen=[]
 for t in times:
  same=[x for x in events if x['action']==t and x['causal_eligible']]
  if same:chosen.append(min(same,key=lambda x:(x['economics']['spread_plus_fee_bps'],x['economics']['risk_eur'],x['sid'])))
 return chosen

