"""Support-only Boolean worker. Never evaluates a feature or economic response.

The accepted archive has no original availability field. Every potential event
therefore has causal UNKNOWN, including geometrically complete events.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib, json, re
import numpy as np
from research_core_v4.current_wave_presupport_geometry_v1 import SOURCES, required_windows
START=1787184000  # asserted against ISO below
START=int(datetime(2026,8,20,tzinfo=timezone.utc).timestamp())
G=8064; END=START+G*300
PROTECTED=int(datetime(2026,9,17,12,2,58,tzinfo=timezone.utc).timestamp())
PRESENT=1; OHLC=2; COUNT=4; POS_OPEN=8; POS_CLOSE=16
ROW_KEYS={'time_utc','open','high','low','close','tick_volume'}
class SupportError(ValueError): pass
def need(v,code):
 if not v: raise SupportError(code)
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(d): return json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
def timestamp(s):
 need(isinstance(s,str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',s) is not None,'BAD_TIME_SCHEMA')
 try: return int(datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp())
 except Exception: raise SupportError('BAD_TIME_SCHEMA') from None
def project(row,segment,digits):
 """Only comparisons/field checks. Output is a time key and five validity bits."""
 need(type(row) is dict and set(row)==ROW_KEYS,'INVALID_SCHEMA_ROWS')
 t=timestamp(row['time_utc']);need(t<PROTECTED,'PROTECTED_FORWARD_ROW')
 need(START+(segment-1)*2016*300<=t<START+segment*2016*300,'SEGMENT_PROVENANCE')
 need(t%300==0,'OUT_OF_GRID_KEYS'); bits=PRESENT; vals=[]
 for k in ('open','high','low','close'):
  s=row[k];need(type(s) is str and len(s)<=1024 and re.fullmatch(r'-?\d+(?:\.\d+)?',s) is not None,'INVALID_SCHEMA_ROWS')
  try: d=Decimal(s)
  except InvalidOperation: raise SupportError('INVALID_SCHEMA_ROWS') from None
  need(d.is_finite() and format(abs(d) if d==0 else d,f'.{digits}f')==s,'INVALID_SCHEMA_ROWS');vals.append(d)
 o,h,l,c=vals
 if l<=o<=h and l<=c<=h: bits|=OHLC
 v=row['tick_volume'];need(type(v) is str and len(v)<=1024,'INVALID_SCHEMA_ROWS')
 if re.fullmatch(r'0|[1-9]\d*',v): bits|=COUNT
 if o>0:bits|=POS_OPEN
 if c>0:bits|=POS_CLOSE
 return (t-START)//300,bits

def window(valid,lo,hi):
 """Vector exact conjunction [lo,hi), absent queries outside domain are false."""
 prefix=np.r_[0,np.cumsum(~valid,dtype=np.int32)]
 in_domain=(lo>=0)&(hi<=len(valid))
 return in_domain & ((prefix[np.clip(hi,0,len(valid))]-prefix[np.clip(lo,0,len(valid))])==0)
def indexed(valid,k): return (k>=0)&(k<len(valid))&valid[np.clip(k,0,len(valid)-1)]
def own_masks(bits):
 t=np.arange(G);hour=(t//12)*12
 p=(bits&PRESENT)!=0; o=(bits&OHLC)!=0; c=(bits&COUNT)!=0
 valid=p&o&c; pos=valid&((bits&POS_OPEN)!=0)&((bits&POS_CLOSE)!=0)
 B=window(valid,hour-12,hour)&indexed(valid,t-1)
 return {'p':p,'o':p&o,'c':p&c,'v':valid,'pos':pos,'close':p&o&((bits&POS_CLOSE)!=0),'B':B,'t':t,'hour':hour}
def coverage(mask,t):
 idx=t[mask]; scheduled=np.flatnonzero(mask); gaps=np.diff(scheduled)-1
 edges=np.diff(np.r_[False,mask,False].astype(np.int8));runs=np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)
 return {'first_query_timestamp':int(START+t[0]*300),'last_query_timestamp':int(START+t[-1]*300),'first_complete_timestamp':int(START+idx[0]*300) if len(idx) else None,'last_complete_timestamp':int(START+idx[-1]*300) if len(idx) else None,'distinct_utc_date_count':int(len(np.unique(idx//288))),'observed_calendar_span_seconds':int((idx[-1]-idx[0])*300) if len(idx) else 0,'maximum_geometric_gap_scheduled_slots':int(max(gaps,default=0)),'longest_complete_run_scheduled_slots':int(max(runs,default=0)),'gap_histogram_scheduled_slots':dict(sorted(Counter(map(int,gaps[gaps>0])).items())),'per_day_complete_counts':np.bincount(idx//288,minlength=28).tolist(),'per_segment_complete_counts':np.bincount(idx//2016,minlength=4).tolist()}
class CalendarGraph:
 """Date hyperedges subsume bar/context edges; exact components without pairs.
Every node touches all dates of its query set. Other declared incidences share
one of those same global dates, so cannot connect distinct date components.
"""
 def __init__(self):self.parent=list(range(32));self.weights=[0]*32;self.nodes=0;self.inc=0;self.cross=0;self.bar=0;self.context=0;self.touched=set();self.contextkeys=set()
 def root(self,x):
  while self.parent[x]!=x:self.parent[x]=self.parent[self.parent[x]];x=self.parent[x]
  return x
 def add(self,mask,a,b,bar_counts,context=False,context_key=None,entries=None):
  a=a[mask]//288+1;b=b[mask]//288+1
  self.nodes+=len(a);self.cross+=int(np.count_nonzero(a!=b));self.bar+=int(np.asarray(bar_counts)[mask].sum());self.context+=int(np.count_nonzero(np.asarray(context)[mask]&1)+np.count_nonzero(np.asarray(context)[mask]&2)) if not isinstance(context,bool) else int(len(a)*2) if context else 0
  if context_key is not None:
   for role in (1,2):
    active=mask&((np.asarray(context)&role)!=0)
    self.contextkeys.update((context_key,int(k),role) for k in entries[active])
  w=np.bincount(a,minlength=32);self.weights=[x+int(y) for x,y in zip(self.weights,w)];self.inc+=int((b-a+1).sum())
  for pair in np.unique(a*32+b):
   x,y=divmod(int(pair),32);self.touched.update(range(x,y+1))
   for z in range(x,y):self.parent[self.root(z+1)]=self.root(x)
 def result(self):
  groups=Counter()
  for i,n in enumerate(self.weights):
   if n:groups[self.root(i)]+=n
  sizes=sorted(groups.values())
  return {'node_count':int(self.nodes),'incidence_count':int(self.inc+self.bar+self.context),'bar_query_incidence_count':int(self.bar),'utc_date_hyperedge_incidence_count':int(self.inc),'utc_date_hyperedge_count':len(self.touched),'context_hyperedge_count':len(self.contextkeys),'context_hyperedge_incidence_count':int(self.context),'connected_component_count':len(sizes),'component_size_summaries':{'minimum':min(sizes,default=0),'maximum':max(sizes,default=0),'sum':sum(sizes),'histogram':dict(Counter(sizes))},'cross_midnight_incidence_count':int(self.cross),'no_overlap_class_counts':{'singleton_components':sum(x==1 for x in sizes)},'not_independent_N':True}

def derive(validity,roster,outdir):
 """Rows have already been discarded. All operations below consume bitmaps."""
 from pathlib import Path
 import gzip
 outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
 n=len(roster);need(validity.shape==(n,G),'MASK_DOMAIN')
 contexts={c:[i for i,e in enumerate(roster) if e['BROKER_NATIVE_CONTEXT']==c] for c in sorted({e['BROKER_NATIVE_CONTEXT'] for e in roster})}
 base=np.zeros((n,G),bool); resp={h:np.zeros((n,G),bool) for h in (1,12)}
 t=np.arange(G);hour=t//12*12
 for i in range(n):
  m=own_masks(validity[i]);base[i]=m['B']
  for h in (1,12):resp[h][i]=window(m['o'],t,t+h)&indexed(m['close'],t-1)&indexed(m['close'],t+h-1)
 counts={c:base[ix].sum(axis=0,dtype=np.int32) for c,ix in contexts.items()}
 validpeers={(c,h):(base[ix]&resp[h][ix]).sum(axis=0,dtype=np.int32) for c,ix in contexts.items() for h in (1,12)}
 records=[];graphs={layer:CalendarGraph() for layer in ('potential','geometric_joint','causal_unknown_joint','causal_certified_joint')}
 packed={};calendar={};context_counts=Counter();peer_hist=Counter();valid_peer_hist=Counter()
 for source in SOURCES:
  horizons=(12,) if source==SOURCES[4] else (1,12)
  ti=t[::12] if source==SOURCES[4] else t
  for h in horizons:
   layerpack={k:np.zeros((n,(len(ti)+7)//8),np.uint8) for k in ('baseline','feature','response','joint','causal_unknown')}
   dateunion={c:np.zeros(len(ti),bool) for c in contexts}
   for i,e in enumerate(roster):
    m=own_masks(validity[i]);ctx=e['BROKER_NATIVE_CONTEXT'];hr=hour
    lo=hr-15 if source==SOURCES[0] else hr-24 if source==SOURCES[4] else hr-12
    feature=window(m['v'],lo,hr)
    if source==SOURCES[1]:feature &=window(m['pos'],lo,hr)
    response=resp[h][i].copy()
    if source==SOURCES[1]:response=window(m['o']&((validity[i]&POS_OPEN)!=0)&((validity[i]&POS_CLOSE)!=0),t,t+h)
    if source==SOURCES[4]:response=window(m['o'],t,t+h)
    peers=counts[ctx]-base[i];rp=validpeers[(ctx,h)]-(base[i]&resp[h][i])
    if source==SOURCES[3]:
     feature=peers>=2;response &= rp>=2
     peer_hist.update(map(int,peers));valid_peer_hist.update(map(int,rp))
    B=base[i][ti];F=feature[ti];R=response[ti];joint=B&F&R
    reason={}
    tests={'BASELINE_WINDOW_INCOMPLETE':~B,'FEATURE_WINDOW_INCOMPLETE':~F,'RESPONSE_WINDOW_INCOMPLETE':~R,'LEFT_CENSORED':lo[ti]<0,'RIGHT_CENSORED':ti+h>G,'ROW_ABSENT':~(window(m['p'],lo,hr)&indexed(m['p'],t-1))[ti],'INVALID_OHLC':~(window(m['o'],lo,hr)&indexed(m['o'],t-1))[ti],'INVALID_COUNT':~(window(m['c'],lo,hr)&indexed(m['c'],t-1))[ti]}
    if source==SOURCES[1]:tests['NONPOSITIVE_REQUIRED_PRICE']=~window(m['pos'],lo,hr)[ti]
    if source==SOURCES[3]:tests.update(MIN_FRESH_PEERS_NOT_MET=peers[ti]<2,MIN_VALID_RESPONSE_PEERS_NOT_MET=rp[ti]<2,CONTEXT_SIZE_BELOW_3=np.full(len(ti),len(contexts[ctx])<3))
    for code,mask in tests.items():reason[code]=int(mask.sum())
    reason['ORIGINAL_AVAILABILITY_UNKNOWN']=len(ti)
    combos=Counter()
    codes=list(tests)
    codebits=np.zeros(len(ti),np.uint16)
    for j,code in enumerate(codes):codebits |=tests[code].astype(np.uint16)<<j
    for val,num in zip(*np.unique(codebits,return_counts=True)):
     combos['|'.join([code for j,code in enumerate(codes) if int(val)&(1<<j)]) or 'NONE']=int(num)
    rec={'source':source,'identity':e['SYMBOL_ID'],'context':ctx,'horizon_M5':h,'potential_event_count':len(ti),'geometrically_complete_event_count':int((B&F).sum()),'geometrically_incomplete_event_count':int((~(B&F)).sum()),'geometric_joint_count':int(joint.sum()),'causal_pass_count':0,'causal_false_count':0,'causal_unknown_count':len(ti),'response_window_available_count':int(R.sum()),'missingness_reason_counts':reason,'missingness_combination_counts':dict(combos),'segment_boundary_counts':int(np.count_nonzero(lo[ti]//2016!=(ti+h-1)//2016)),**coverage(joint,ti)}
    if source==SOURCES[3]:rec.update(events_with_at_least_two_geometric_peers=int((peers>=2).sum()),events_with_at_least_two_valid_response_peers=int((rp>=2).sum()),causally_certified_peer_events=0,context_size=len(contexts[ctx]))
    records.append(rec);context_counts[(source,ctx,h)]+=int(joint.sum());dateunion[ctx]|=joint
    masks={'baseline':B,'feature':F,'response':R,'joint':joint,'causal_unknown':np.ones(len(ti),bool)}
    for k,v in masks.items():layerpack[k][i]=np.packbits(v,bitorder='little')
    # Unique local preentry query cardinality includes disjoint last-M5 key.
    pre=hr-lo+(t-1>=hr)
    bars=pre+h
    if source==SOURCES[3]:bars=(hr-(hr-12)+(t-1>=hr))*len(contexts[ctx])+h*(1+peers)
    a=np.minimum(lo,t-1)[ti];b=(ti+h-1)
    ctxroles=np.full(len(ti),int(len(contexts[ctx])>1),np.uint8)|((peers[ti]>0).astype(np.uint8)*2) if source==SOURCES[3] else False
    for layer,mask in [('potential',np.ones(len(ti),bool)),('geometric_joint',joint),('causal_unknown_joint',joint)]:graphs[layer].add(mask,a,b,bars[ti],ctxroles,ctx if source==SOURCES[3] else None,ti)
   for k,v in layerpack.items():packed[source+'__'+str(h)+'__'+k]=v
   calendar[source+'__'+str(h)]={c:{'unique_entry_slots':int(v.sum()),'distinct_entry_dates':int(len(np.unique(ti[v]//288))),'per_date_entry_slot_counts':np.bincount(ti[v]//288,minlength=28).tolist()} for c,v in dateunion.items()}
 np.savez_compressed(outdir/'event_masks.npz',**packed,baseline_geometric=np.packbits(base,axis=1,bitorder='little'),**{'peer_response_'+str(h):np.packbits(base&resp[h],axis=1,bitorder='little') for h in (1,12)})
 geometry={'schema':'mxm.v4.current-wave.dependence-geometry-result.v1','layers':{k:v.result() for k,v in graphs.items()},'factorization':{'event_node_domain':'frozen source/horizon/roster/entry-grid Cartesian domain','query_templates_ref':'research_core_v4/current_wave_presupport_geometry_v1.py','all_potential_peer_B_queries':True,'geometric_peer_snapshot':'event_masks.npz:baseline_geometric, own identity excluded','response_peer_set':'same frozen geometric entry snapshot; future validity never adds peers','causal_peer_snapshot':'empty certified set; all otherwise geometric peers UNKNOWN','context_hyperedges':'(frozen context,t,role), two roles B and future; future identity incidence only frozen fresh peers','dates':'every date touched by exact queried keys incl absent queries','interval_key_incidence':'exact required_windows plus all potential peer baseline keys and frozen geometric peer future keys','graph_component_proof':'global date hyperedges subsume any shared identity-key/context incidence; exact date-union DSU','no_dense_pairs':True},'calendar_support':calendar,'not_effective_independent_N':True}
 aggregated={}
 for rec in records:
  key=(rec['source'],rec['context'],rec['horizon_M5'])
  if key not in aggregated:aggregated[key]={'source':key[0],'context':key[1],'horizon_M5':key[2],'identity_count':0,'missingness_reason_counts':Counter()}
  dst=aggregated[key];dst['identity_count']+=1;dst['missingness_reason_counts'].update(rec['missingness_reason_counts'])
  for field in ('potential_event_count','geometrically_complete_event_count','geometrically_incomplete_event_count','geometric_joint_count','causal_pass_count','causal_false_count','causal_unknown_count','response_window_available_count'):
   dst[field]=dst.get(field,0)+rec[field]
 support={'schema':'mxm.v4.current-wave.support-result.v1','status':'SUPPORT_RESULT_COMPLETE_PENDING_INDEPENDENT_AUDIT','identities':n,'candidates':list(SOURCES),'per_candidate_identity_context_horizon':records,'context_support_counts':[aggregated[k] for k in sorted(aggregated)],'cross_sectional_peer_count_distribution':dict(sorted(peer_hist.items())),'cross_sectional_valid_response_peer_count_distribution':dict(sorted(valid_peer_hist.items())),'causal_law':'UNKNOWN for all events; zero PASS and FALSE; archive has no original_available_at','no_ranking':True,'power_trials':0,'duration_selected':False,'new_economic_outcomes':0}
 for name,obj in [('support_counts.json.gz',support),('dependence_geometry.json.gz',geometry)]:
  with gzip.GzipFile(filename=str(outdir/name),mode='wb',mtime=0) as f:f.write(canonical(obj))
 return support,geometry
