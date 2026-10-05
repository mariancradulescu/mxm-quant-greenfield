"""Outcome-blind engineering candidate. Not a certified or armed campaign worker.
Reference RNG, score bytecode, kernel and support certificate are unchanged.
Only invariant topology and exactly duplicate coefficient tuples are cached.
"""
from pathlib import Path
import importlib.util, types, numpy as np
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('v7_engine_reference',P.parent/'stochastic_worker_v1.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
class PreparedScores:
 def __init__(self,g):
  self.g=g; self.topology={}
  for day in range(len(g['causal'])):
   for k in range(8):
    for c in range(3):
     rr=np.flatnonzero((g['relation_cohort']==c)&g['causal'][day,k]);declared=np.flatnonzero(g['target_cohort']==c).tolist()
     ids=sorted(set(int(g['relation_target'][r]) for r in rr))
     if len(ids)<max(5,(len(declared)+1)//2) or len(rr)<(int((g['relation_cohort']==c).sum())+1)//2:self.topology[day,k,c]=None;continue
     groups=[np.flatnonzero(g['relation_target'][rr]==t) for t in ids]
     keep={t:np.array([i!=t for i in ids]) for t in declared}
     self.topology[day,k,c]=(rr,ids,g['target_asset'][ids],groups,keep)
  # The scientific score function executes the SAME code object; only the
  # clock_fits dependency is replaced. No mutation of reference module globals.
  namespace=dict(reference.scores.__globals__);namespace['clock_fits']=self.clock_fits
  self.score_function=types.FunctionType(reference.scores.__code__,namespace)
 def clock_fits(self,g,path,day,k,c,project):
  topo=self.topology[day,k,c]
  if topo is None:return None
  rr,ids,assets,groups,keeps=topo;q=12+12*k;past=path[q-11:q+1].sum(axis=0);last=path[q]
  # Each 3-leg contiguous reduction preserves the original summation order.
  val=np.clip(np.sum(g['sign'][rr]*past[g['leg'][rr]],axis=1)/g['relation_scale'][rr],-3,3)
  X=np.column_stack([np.ones(len(ids)),last[assets]/g['scale'][assets],past[assets]/g['scale'][assets]])
  D=np.array([np.mean(val[idx]) for idx in groups]);full=project(X,D);loo={}
  for target,keep in keeps.items():loo[target]=(keep,full if keep.all() else project(X[keep],D[keep]))
  return {'ids':ids,'assets':assets,'X':X,'D':D,'full':full,'loo':loo}
 def scores(self,base,case,delta,project):return self.score_function(self.g,base,case,delta,project)
 def configurations(self,base,case,cells,project):
  # Cache scoped to this one base path and one case. Nonzero distinct deltas
  # always recompute all causal full/leaveout geometries after signal feedback.
  cache={};out={}
  for cell in cells:
   key=tuple(float(x) for x in cell['delta'])
   if key not in cache:cache[key]=self.scores(base,case,key,project)
   out[cell['id']]=cache[key]
  return out
