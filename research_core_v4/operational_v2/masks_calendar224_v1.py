"""Boolean validity and exact factorized availability; zero real score arithmetic."""
import hashlib,json,pathlib
from datetime import datetime,timezone
import numpy as np
from bank import R,P,canonical,sha
S='research_core_v4/state/'
ROSTER=S+'MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json'

def derive(bits,roster,start,outdir):
 from research_core_v4 import current_wave_support_worker_v1 as w
 n,G=bits.shape;assert n==len(roster) and G%2016==0
 days=G//288;assert 28<=days<=224 and start%86400==0
 # Domain extension only; immutable source support/peer/window laws are reused.
 prior=(w.G,w.START,w.END);w.G=G;w.START=start;w.END=start+G*300
 outdir=pathlib.Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
 try:
  t=np.arange(G);hour=t//12*12;epochs=start+t*300
  base=np.zeros((n,G),bool);resp={h:np.zeros((n,G),bool) for h in [1,12]}
  for i in range(n):
   m=w.own_masks(bits[i]);base[i]=m['B']
   for h in [1,12]:resp[h][i]=w.window(m['o'],t,t+h)&w.indexed(m['close'],t-1)&w.indexed(m['close'],t+h-1)
  contexts={c:[i for i,e in enumerate(roster) if e['BROKER_NATIVE_CONTEXT']==c] for c in sorted({e['BROKER_NATIVE_CONTEXT'] for e in roster})}
  fresh={c:base[ix].sum(0,dtype=np.int32) for c,ix in contexts.items()};peer_response={(c,h):(base[ix]&resp[h][ix]).sum(0,dtype=np.int32) for c,ix in contexts.items() for h in [1,12]}
  inv=json.loads((R/S/'STRICT_PREOUTCOME_V2_CURRENT_WAVE_PROGRESSIVE_DEPTH_PAID_LEAF_INVENTORY_V1.json').read_bytes());daily=np.zeros((days,261),bool);leaf_index={(x['source'],x['context'],x['horizon_M5']):j for j,x in enumerate(inv['leaves'])}
  packed={};summaries=[];counts={}
  for source in w.SOURCES:
   for h in ([12] if source==w.SOURCES[4] else [1,12]):
    ti=t[::12] if source==w.SOURCES[4] else t;epoch=epochs[ti];joint=np.zeros((n,len(ti)),bool)
    for i,e in enumerate(roster):
     m=w.own_masks(bits[i]);ctx=e['BROKER_NATIVE_CONTEXT'];lo=hour-15 if source==w.SOURCES[0] else hour-24 if source==w.SOURCES[4] else hour-12
     feature=w.window(m['v'],lo,hour);response=resp[h][i].copy()
     if source==w.SOURCES[1]:feature &=w.window(m['pos'],lo,hour);response=w.window(m['o']&((bits[i]&w.POS_OPEN)!=0)&((bits[i]&w.POS_CLOSE)!=0),t,t+h)
     if source==w.SOURCES[4]:response=w.window(m['o'],t,t+h)
     if source==w.SOURCES[3]:feature=fresh[ctx]-base[i]>=2;response &=peer_response[ctx,h]-(base[i]&resp[h][i])>=2
     joint[i]=base[i,ti]&feature[ti]&response[ti]
    avail=np.zeros_like(joint);identity_days=np.zeros((n,days),np.uint16)
    for ctx,ix in contexts.items():
     j=leaf_index[source,ctx,h]
     for refit in range(start+56*86400,start+days*86400,7*86400):
      train=(epoch>=refit-56*86400)&(epoch<refit)&(epoch+245*60<refit)&(epoch%1800==0)
      has_training=bool(joint[np.ix_(ix,np.flatnonzero(train))].any())
      if not has_training:continue
      ev=(epoch>=refit)&(epoch<min(refit+7*86400,start+days*86400))&(epoch+h*300<start+days*86400)
      idx=np.flatnonzero(ev);avail[np.ix_(ix,idx)]=joint[np.ix_(ix,idx)]
     for i in ix:identity_days[i]=np.bincount((ti[avail[i]]//288),minlength=days)
     daily[:,j]=identity_days[ix].sum(0)>0
     summaries.append({'source':source,'context':ctx,'horizon_M5':h,'identity_count':len(ix),'geometric_joint_events':int(joint[ix].sum()),'prequential_available_events':int(identity_days[ix].sum()),'per_date_identity_days':(identity_days[ix]>0).sum(0).tolist(),'original_available_at':'UNKNOWN','no_values':True})
    name=source+'__'+str(h);packed[name+'__joint']=np.packbits(joint,axis=1,bitorder='little');packed[name+'__score_available']=np.packbits(avail,axis=1,bitorder='little');counts[name+'__identity_daily_events']=identity_days
  packed['baseline_geometric']=np.packbits(base,axis=1,bitorder='little')
  for h in [1,12]:packed['frozen_peer_response_'+str(h)]=np.packbits(base&resp[h],axis=1,bitorder='little')
  np.savez_compressed(outdir/'event_masks.npz',**packed);np.savez_compressed(outdir/'support_counts.npz',**counts);np.save(outdir/'daily_score_mask.npy',daily[56:])
  geometry={'schema':'mxm.operational-v2.exact-factorized-geometry.v1','start_epoch':start,'end_exclusive_epoch':start+G*300,'calendar_days':days,'identities':len(roster),'identity_order':[e['SYMBOL_ID'] for e in roster],'context_incidence':{c:[roster[i]['SYMBOL_ID'] for i in ix] for c,ix in contexts.items()},'factorization':{'query_templates_ref':'research_core_v4/current_wave_presupport_geometry_v1.py','query_templates_sha256':sha(R/'research_core_v4/current_wave_presupport_geometry_v1.py'),'baseline_and_peer_snapshot_masks':'event_masks.npz baseline_geometric, frozen_peer_response_1/12','joint_and_score_availability_masks':'event_masks.npz per source/horizon','all_potential_peers_queried':True,'own_identity_excluded':True,'all_dates_touched_by_readset':'exact template open-key dates; same global calendar across all5 sources; no dense pair expansion','all_within_day_overlaps_retained':'event-level Boolean mask plus exact query readsets before daily equal-identity aggregation','independent_N_not_event_or_component_count':True},'support':summaries,'original_available_at':'UNKNOWN_ALL_POTENTIAL_EVENTS','event_time_causal_layer':'PROSPECTIVE_COMPLETED_BAR_PLANNING_ONLY','real_values':0}
  (outdir/'geometry.json').write_bytes(canonical(geometry));return daily[56:],geometry
 finally:w.G,w.START,w.END=prior
