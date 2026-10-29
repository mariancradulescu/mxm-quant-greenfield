"""Independent Decimal/source-array reconciliation; never used as signal authority."""
from bisect import bisect_left
from decimal import Decimal as D,localcontext,ROUND_CEILING
from .common import need
from .universe_commission_checks import terms,fee

def source_views(data):
 books={sid:dict(first=True,maximum=None,bid=None,ask=None) for sid in (1,2,9)};result=[]
 term=terms(dict(symbol_id=2,quote_asset='USD',full=data['target_terms']));units=D(term['MinimumVolume'])/100
 previous_ns=previous_utc=previous_seq=-1
 with localcontext() as ctx:
  ctx.prec=55
  for event in data['events']:
   sid=event['symbol'];ns=event['arrival_ns'];utc=event['received_ms'];seq=event['sequence'];b=books[sid];server=event['server_ms']
   need(seq>previous_seq and ns>=previous_ns and utc>=previous_utc,'TRIAD_REFERENCE_CHRONOLOGY')
   previous_ns,previous_utc,previous_seq=ns,utc,seq
   valid=server is not None and 0<=utc-server<=5000 and (b['maximum'] is None or server>=b['maximum'])
   if server is not None:b['maximum']=max(server,b['maximum']) if b['maximum'] is not None else server
   for side in ('bid','ask'):
    if event[side] is not None:b[side]=(D(event[side])/100000,ns,server if valid and not b['first'] else None)
   b['first']=False
   def view(sid):
    b=books[sid];x,y=b['bid'],b['ask'];ok=all(v is not None and v[2] is not None and v[0]>0 and 0<=utc-v[2]<=5000 and 0<=ns-v[1]<=5000000000 for v in (x,y)) and y[0]>=x[0]
    return dict(Bid=x[0] if x else None,Ask=y[0] if y else None,BidArrival=x[1] if x else None,AskArrival=y[1] if y else None,
     BidServer=x[2] if x else None,AskServer=y[2] if y else None,Markable=ok,Positive=bool(ok and y[0]>x[0]))
   t,f,c=view(2),view(1),view(9);ceiling=None;affordable=False
   if t['Markable'] and f['Markable']:
    fx=(1/f['Bid']).quantize(D('1e-18'),rounding=ROUND_CEILING)
    def price(p):return fee(dict(fill=dict(volume_cents=term['MinimumVolume'],price=str(p),usd_per_quote='1',cost_eur_per_asset={'EUR':'1','USD':str(fx)})),term)['UnroundedFeeEur']
    ceiling=max(price(t['Bid']),price(t['Ask']));m=D(data['margin_eur'])
    affordable=0<m<=80 and D(200)-m-ceiling>=120 and 2*ceiling<=D('.2') and D('.0012')*units/f['Bid']+2*ceiling<=2
   result.append(dict(Symbol=sid,Sequence=seq,Ns=ns,Utc=utc,Target=t,Fx=f,Cross=c,
    SyntheticBid=f['Bid']/c['Ask'] if f['Markable'] and c['Markable'] else None,
    SyntheticAsk=f['Ask']/c['Bid'] if f['Markable'] and c['Markable'] else None,Fee=ceiling,Affordable=affordable))
 return result

def admission(views):
 own=[s for s in views if s['Symbol']==2];clocks=[s['Ns'] for s in own];positions={s['Sequence']:i for i,s in enumerate(views)}
 bad=[0]
 for s in views:bad.append(bad[-1]+int(not s['Target']['Markable'] or not s['Fx']['Markable']))
 potential=complete=0
 for s in own:
  if not(s['Target']['Positive'] and s['Fx']['Markable'] and s['Cross']['Markable'] and s['Fee'] is not None and s['Affordable']):continue
  potential+=1;j=bisect_left(clocks,s['Ns']+250000000)
  if j==len(own) or own[j]['Ns']>s['Ns']+3000000000 or not own[j]['Target']['Positive'] or not own[j]['Fx']['Markable']:continue
  k=bisect_left(clocks,own[j]['Ns']+1000000000)
  if k==len(own) or own[k]['Ns']>own[j]['Ns']+4000000000 or not own[k]['Target']['Positive'] or not own[k]['Fx']['Markable']:continue
  if bad[positions[own[k]['Sequence']]+1]-bad[positions[s['Sequence']]+1]:continue
  complete+=1
 return dict(potential=potential,complete=complete,admitted=potential>=100 and complete>=.8*potential)
def close(a,b):
 if a is None or b is None:return a is b
 return abs(D(a)-D(b))<=D('1e-20')
def reconcile(data,actual):
 views=source_views(data);by_seq={s['Sequence']:s for s in views};a=admission(views)
 need(all(actual['admission'][k]==v for k,v in a.items()),'TRIAD_PRICE_BLIND_ADMISSION_PARITY')
 need(actual['models']==int(a['admitted']) and actual['source_events']==len(views) and actual['target_events']==sum(s['Symbol']==2 for s in views),'TRIAD_COMPLETE_SOURCE_RECONCILIATION')
 if not a['admitted']:
  need(not actual['journal'] and not actual['episodes'],'TRIAD_NO_ECONOMICS_BEFORE_SOURCE_ADMISSION');return dict(source_points=len(views),admission=a,model_replayed=False)
 units=D(str(data['target_terms']['minVolume']))/100;checked=0
 for row in actual['journal']:
  s=by_seq[row['source_sequence']];need(row['arrival_ns']==s['Ns'] and row['received_ms']==s['Utc'],'TRIAD_AUDIT_ORIGINAL_CLOCK')
  for name,view in (('target',s['Target']),('fx',s['Fx'])):
   need(row['context'][name]['Markable']==view['Markable'] and row['context'][name]['Positive']==view['Positive'],'TRIAD_EVERY_AUDITED_BOOK_HEALTH')
   for key in ('Bid','Ask','BidArrival','AskArrival','BidServer','AskServer'):need(close(row['context'][name][key],view[key]),'TRIAD_EVERY_SOURCE_SIDE_AND_CLOCK')
  need(row['context']['source_symbol']==s['Symbol'],'TRIAD_ORIGINAL_EVENT_SYMBOL')
  for key in ('Bid','Ask','BidArrival','AskArrival','BidServer','AskServer'):
   need(close(row['context']['synthetic']['cross'][key],s['Cross'][key]),'TRIAD_CROSS_SOURCE_CONTEXT')
  need(close(row['context']['synthetic']['bid'],s['SyntheticBid']) and close(row['context']['synthetic']['ask'],s['SyntheticAsk']) and
       close(row['context']['fee_per_side_ceiling_eur'],s['Fee']),'TRIAD_SYNTHETIC_PRICE_AND_FEE_CONTEXT')
  if row['state']=='ABSTAIN' and row['reason']=='BELOW_FIXED_TRIAD_FRICTION_HURDLE':
   h=2*(s['Target']['Ask']-s['Target']['Bid'])+2*s['Fee']*s['Fx']['Ask']/units+D('1e-20')
   need(s['SyntheticBid']-s['Target']['Ask']<=h and s['Target']['Bid']-s['SyntheticAsk']<=h,'TRIAD_ABSTENT_OPPORTUNITY_NOT_LOST')
  if row['state']=='PROPOSAL':
   need(s['Target']['Positive'] and s['Fx']['Markable'] and s['Cross']['Markable'] and s['Affordable'],'TRIAD_ADMITTED_SIGNAL_SOURCE')
   hurdle=2*(s['Target']['Ask']-s['Target']['Bid'])+2*s['Fee']*s['Fx']['Ask']/units
   desired=1 if s['SyntheticBid']-s['Target']['Ask']>hurdle+D('1e-20') else -1 if s['Target']['Bid']-s['SyntheticAsk']>hurdle+D('1e-20') else 0
   need(row['direction']==desired!=0,'TRIAD_PROSPECTIVE_DIRECTION_AND_COST_HURDLE');checked+=1
 need({r['opportunity_id'] for r in actual['journal'] if r['state']=='PROPOSAL'}=={e['id'] for e in actual['episodes']},'TRIAD_EVERY_OPPORTUNITY_RETAINED')
 for e in actual['episodes']:
  if e['exit'] is None:need(e['gross_eur'] is None and e['net_scenario_eur'] is None,'TRIAD_CENSOR_NOT_ZERO');continue
  entry,exit=e['entry'],e['exit'];direction=e['direction']
  need(250000000<=entry['Ns']-e['decision']['Ns']<=3000000000 and 1000000000<=exit['Ns']-entry['Ns']<=4000000000,'TRIAD_RECEIPT_CLOCK_EXECUTION_WINDOWS')
  ep=entry['Target']['Ask'] if direction>0 else entry['Target']['Bid'];xp=exit['Target']['Bid'] if direction>0 else exit['Target']['Ask']
  usd=direction*(xp-ep)*units;gross=usd/(exit['Fx']['Ask'] if usd>=0 else exit['Fx']['Bid'])
  need(close(gross,e['gross_eur']) and close(gross-entry['Fee']-exit['Fee'],e['net_scenario_eur']),'TRIAD_EVERY_EPISODE_SPREAD_FEE_SIGNED_FX')
 return dict(source_points=len(views),admission=a,proposal_directions_verified=checked,every_individual_source_context_and_episode_checked=True,model_replayed=False)
