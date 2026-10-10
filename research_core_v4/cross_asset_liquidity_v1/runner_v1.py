"""Frozen cross-asset liquidity: increment over previous own quote model, no orders."""
import os,json,math,statistics,tempfile,pathlib
from collections import Counter
from datetime import datetime,timezone
import numpy as np
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.broker_liquidity_forecast_v1.runner_v1 import quote_state,feature
e=rt.e;P='research_core_v4/cross_asset_liquidity_v1/';PHASE='GATE'
def main():
 global PHASE
 os.umask(0o077);head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head)
 a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
 e.w.old.need(a['orders'] is False and a['protected_forward'] is False and not a['independent_acceptance_claimed'],'CROSS_ASSET_SCOPE')
 e.w.old.need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-cross-asset-liquidity-v1.yml@refs/heads/'+e.w.old.BRANCH,'CROSS_ASSET_WORKFLOW')
 e.a.ancestor(a['base_head'],head)
 for p,h in a['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'SOURCE_DRIFT')
 original=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
 for p,h in original['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ORIGINAL_DRIFT')
 tag='mxm-cross-asset-liquidity-'+a['invocation_id']
 e.w.old.need(not e.w.v2.existing_ref(tag),'CONSUMED')
 e.w.old.api('git/refs',{'ref':'refs/tags/'+tag,'sha':head})
 with tempfile.TemporaryDirectory(prefix='mxm-cross-asset-liquidity-',dir=os.environ['RUNNER_TEMP']) as dirname:
  tmp=pathlib.Path(dirname);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'PRIVATE_KEY')
  PHASE='IMMUTABLE_ENCRYPTED_PRIOR_QUOTE_DATA'
  old,provenance=load_asset(key,fp,tmp,a['source'])
  q={(int(z['symbol_id']),int(datetime.fromisoformat(z['timestamp_utc']).timestamp())):z for z in old['private_historical_ticks']}
  prior=old['all_predeclared_events'];contracts={int(z['symbol_id']):z for z in old['private_current_contract_metadata']}
  e.w.old.need(len(prior)==32*len(contracts) and len(contracts)>1,'FROZEN_COHORT')
  clocks=sorted({int(datetime.fromisoformat(t['action_utc']).timestamp()) for t in prior})
  e.w.old.need(len(clocks)==32,'FROZEN_CLOCKS')
  index={(int(t['symbol_id']),int(datetime.fromisoformat(t['action_utc']).timestamp())):t for t in prior}
  out=[]
  for sid in sorted(contracts):
   history=[]
   for t in clocks:
    pre=quote_state(q.get((sid,t-300)));now=quote_state(q.get((sid,t)))
    peer=[]
    for other in sorted(contracts):
     if other==sid or contracts[other]['asset_class']==contracts[sid]['asset_class']:continue
     past=quote_state(q.get((other,t-300)));cur=quote_state(q.get((other,t)))
     if past and cur:peer.append((math.log(cur['spread']/past['spread']),(cur['bid_age']+cur['ask_age'])/2000))
    selfx=feature(pre,now) if pre and now else None
    extra=[statistics.median(z[0] for z in peer),statistics.median(z[1] for z in peer)] if len(peer)>=2 else None
    x=selfx+extra if selfx is not None and extra is not None else None
    original=index[sid,t];y=original['future_authentic_spread_bps']
    cohort=original['model_spread_bps'] is not None and y is not None
    ready=x is not None and len(history)>=6 and cohort
    if ready:
     X=np.asarray([a for a,b in history],float);Y=np.asarray([b for a,b in history],float)
     mu=X.mean(axis=0);scale=np.maximum(X.std(axis=0),1e-9);U=(X-mu)/scale
     forecast=float(Y.mean()+((np.asarray(x)-mu)/scale)@np.linalg.solve(U.T@U+25*np.eye(8),U.T@(Y-Y.mean())))
    else:forecast=None
    reason='PEER_SUPPORT_UNDER2' if len(peer)<2 else 'OWN_FEATURE_GAP' if selfx is None else 'TRAIN_UNDER6' if len(history)<6 else 'FROZEN_BASELINE_OR_LABEL_GAP' if not cohort else 'PAIRED_SUPPORTED'
    out.append({'symbol_id':sid,'asset_class':contracts[sid]['asset_class'],'block':original['block'],'iso_utc':original['iso_utc'],'action_utc':original['action_utc'],'peer_count':len(peer),'cross_training':len(history),'reason':reason,'target_future_spread_bps':y,'frozen_own_model':original['model_spread_bps'] if ready else None,'cross_asset_model':forecast,'frozen_carryforward':original['baseline_spread_bps'] if ready else None})
    if x is not None and y is not None:history.append((x,y))
  PHASE='PAIRED_CROSS_CLASS_ESTIMANDS'
  def stats(rows):
   count=Counter(z['reason'] for z in rows);pair=[z for z in rows if z['reason']=='PAIRED_SUPPORTED']
   if not pair:return {'scheduled':len(rows),'paired':0,'reasons':dict(count),'increment_mse_bps2':None,'own_model_mse_bps2':None,'cross_model_mse_bps2':None}
   ref=[(z['frozen_own_model']-z['target_future_spread_bps'])**2 for z in pair]
   alt=[(z['cross_asset_model']-z['target_future_spread_bps'])**2 for z in pair]
   return {'scheduled':len(rows),'paired':len(pair),'reasons':dict(count),'increment_mse_bps2':sum(x-y for x,y in zip(ref,alt))/len(pair),'own_model_mse_bps2':sum(ref)/len(pair),'cross_model_mse_bps2':sum(alt)/len(pair),'mean_supported_cross_class_peers':sum(z['peer_count'] for z in pair)/len(pair)}
  aggregate={'all':stats(out),'four_original_blocks':[{'block':b,**stats([z for z in out if z['block']==b])} for b in range(4)],'iso_utc':[{'week':w,'complete_iso_week':w in ('2026-W35','2026-W36','2026-W37'),**stats([z for z in out if z['iso_utc']==w])} for w in sorted({z['iso_utc'] for z in out})],'classes':[{'class':c,**stats([z for z in out if z['asset_class']==c])} for c in sorted({z['asset_class'] for z in out})]}
  result={'schema':'mxm.private.cross.asset.liquidity.increment.development.v1','source_head':head,'underlying_quote_provenance':provenance,'new_actual_numeric':aggregate,'data':'EXISTING_AUTHENTIC_NATIVE_BROKER_QUOTES_WITH_ORIGINAL_SELECTION_EXPOSURE','new_broker_requests':0,'independent_confirmation':False,'net_certified':False,'HARD21_certified':False,'orders':0,'protected_forward':False,'actual_fills':0,'uncertainty':'ONLY_FOUR_SHARED_BLOCKS_NO_FAMILYWISE_CERTIFICATION'}
  PHASE='ENCRYPTED_RESULTS';rt.output(head,a,tmp,key,'crossassetliquidity',{'summary':result,'all_private_paired_cross_asset_trials':out},result)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
