"""Integer-only prospective transport layout. No trial/RNG/execution entrypoint.
Unfinished started shard is case failure under the frozen no-retry policy.
Resume is allowed only at an already durable complete shard boundary, for
never-started remaining indices. No scientific interpretation of partial data.
"""
import json,hashlib
WIDTH=64
FIELDS=('false_significance','false_lead','any_nonnull_lead','all_nonnull_leads','supported')
def canonical(o):return (json.dumps(o,sort_keys=True,separators=(',',':'))+'\n').encode()
def layout(manifest,phase,case_id):
 cases=manifest['execution_policy'][phase+'_case_order'];assert case_id in cases
 n=manifest[phase+'_trials_per_case']
 return [{'phase':phase,'case_id':case_id,'start':i,'stop':min(n,i+WIDTH),'retry':False} for i in range(0,n,WIDTH)]
def merge(manifest,phase,case_id,parts):
 expected=layout(manifest,phase,case_id);by={}
 cells=manifest['partial_nulls'] if phase=='null' else manifest['power_cells'];ids=[c['id'] for c in cells]
 result={cid:{**{f:0 for f in FIELDS},'per_leaf_lead':[0]*12} for cid in ids}
 for p in parts:
  key=(p['start'],p['stop']);assert key not in by,'DUPLICATE_SHARD';by[key]=p
 assert set(by)=={(p['start'],p['stop']) for p in expected},'INCOMPLETE_EXACT_CASE'
 for spec in expected:
  p=by[spec['start'],spec['stop']];assert p['phase']==phase and p['case_id']==case_id
  assert p['manifest_sha256']==hashlib.sha256((json.dumps(manifest,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()
  assert p['complete'] is True and p['numerical_failures']==0 and set(p['cells'])==set(ids)
  n=p['stop']-p['start']
  for cid in ids:
   c=p['cells'][cid];assert set(c)==set(FIELDS)|{'per_leaf_lead'}
   assert len(c['per_leaf_lead'])==12
   for v in [*[c[f] for f in FIELDS],*c['per_leaf_lead']]:assert type(v) is int and 0<=v<=n
   assert c['supported']==n and c['false_lead']<=c['false_significance']
   for f in FIELDS:result[cid][f]+=c[f]
   result[cid]['per_leaf_lead']=[a+b for a,b in zip(result[cid]['per_leaf_lead'],c['per_leaf_lead'])]
 return {'phase':phase,'case_id':case_id,'trials':manifest[phase+'_trials_per_case'],'cells':result,'interpretation':'PENDING_COMPLETE_CASE_DURABLE_GIT_CHECKPOINT'}
