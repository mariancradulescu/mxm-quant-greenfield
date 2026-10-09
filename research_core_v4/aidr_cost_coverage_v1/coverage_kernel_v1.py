"""Exact availability intersection only. No real-access entry point; no prices, returns or cost arithmetic."""
from collections import Counter
FIELDS={'ordinal','symbol_id','decision_timestamp','entry_reference_boundary','exit_reference_boundary','direction','fixed_week','response_support_status','receipt_semantics'}
CATEGORIES=('EVENTS_WITH_BOTH_BOUNDARIES_COVERED','EVENTS_WITH_PARTIAL_BOUNDARY_COVERAGE','EVENTS_WITH_UNAVAILABLE_SOURCE','EVENTS_WITH_UNRESOLVED_COST_SEMANTICS','EVENTS_OUTSIDE_AUTHENTIC_EVIDENCE_DOMAIN')
def prepare(index):
 assert index['schema']=='mxm.aidr.existing.cost.availability.v1' and index['compiled_without_event_access'] is True
 out={}
 for source in index['sources']:
  s=dict(source);r=s.pop('records')
  if s['kind']=='BOUNDARY':
   s['lookup']={}
   for row in r:
    key=row['timestamp_ms'];assert key not in s['lookup'],'DUPLICATE_SOURCE_BOUNDARY'
    s['lookup'][key]=row
  else:
   assert s['kind']=='JOINT';s['lookup']={}
   for row in r:
    key=(row['entry_ms'],row['exit_ms']);assert key not in s['lookup'],'DUPLICATE_JOINT'
    s['lookup'][key]=row
  out.setdefault(s['symbol_id'],[]).append(s)
 return out
def one(event,sources):
 # Boundary presence and cost applicability are separate axes; no cross-source side stitching.
 entry=event['entry_reference_boundary']*1000;exit=event['exit_reference_boundary']*1000
 details=[]
 for source in sources.get(event['symbol_id'],[]):
  if source['kind']=='JOINT':
   row=source['lookup'].get((entry,exit))
   e=x=bool(row);qe=qx=False;fresh='OTHER_LAW_EVENT_DIRECTION_NOT_VERIFIED_TRADE_SIDE'
   refs=[row['row_sha256']] if row else []
  else:
   er=source['lookup'].get(entry);xr=source['lookup'].get(exit)
   e=er is not None;x=xr is not None;qe=bool(er and er['two_sided']);qx=bool(xr and xr['two_sided'])
   fresh='DECLARED_FRESH' if qe and qx and er['fresh'] is True and xr['fresh'] is True else 'UNRESOLVED_OR_NOT_FRESH'
   refs=[r['row_sha256'] for r in (er,xr) if r is not None]
  details.append({'source':source['source'],'member':source['member'],'member_sha256':source['member_sha256'],
    'entry_record_present':e,'exit_record_present':x,'entry_quote_available':qe,'exit_quote_available':qx,
    'both_boundaries_quoted':qe and qx,'quote_freshness':fresh,'row_sha256':refs,
    'cost_semantics':'ACCOUNT_TERMS_CONVERSION_EXECUTION_NOT_ESTABLISHED'})
 if not details:category=CATEGORIES[2]
 elif any(d['both_boundaries_quoted'] for d in details):category=CATEGORIES[0]
 elif any(d['entry_record_present'] != d['exit_record_present'] for d in details):category=CATEGORIES[1]
 elif any(d['entry_record_present'] or d['exit_record_present'] for d in details):category=CATEGORIES[3]
 else:category=CATEGORIES[4]
 return {'category':category,'unresolved_cost_semantics':True,'source_matches':details}
def intersect(events,index,expected=None):
 # Caller must authenticate locator plaintext before calling; this pure kernel grants no authority.
 sources=prepare(index);seen=set();counts=Counter();result=[]
 for event in events:
  assert set(event)==FIELDS and event['direction'] in (-1,1)
  key=(event['ordinal'],event['decision_timestamp']);assert key not in seen,'DUPLICATE_EVENT';seen.add(key)
  assert event['entry_reference_boundary']==event['decision_timestamp'] and event['exit_reference_boundary']==event['decision_timestamp']+3600
  clock=(event['decision_timestamp']*1000-index['start_ms'])//3600000
  assert 0<=clock<672 and event['decision_timestamp']*1000==index['start_ms']+clock*3600000 and event['fixed_week']==clock//168
  support=event['response_support_status'];assert support in ('SUPPORTED','LABEL_GAP')
  counts[(event['ordinal'],event['fixed_week'],support)]+=1
  result.append({'event':event,'coverage':one(event,sources)})
 if expected is not None:assert dict(counts)==expected,'IDENTITY_WEEK_SUPPORT_MISMATCH'
 assert len(result)==len(events) and len(seen)==len(events)
 summary=Counter((r['coverage']['category'],r['event']['response_support_status'],r['event']['fixed_week']) for r in result)
 return {'schema':'mxm.aidr.private.cost.coverage.v1','records':result,'identity_week_support_counts':sorted((list(k),v) for k,v in counts.items()),
   'category_week_support_counts':sorted((list(k),v) for k,v in summary.items()),
   'unresolved_cost_semantics_overlay':len(events),'economic_responses_recomputed':False,'cohort_net_headroom_established':False}

