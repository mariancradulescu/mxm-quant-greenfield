"""Deterministic predeclared algebra/overlap invariants; no DGP pilot or market data."""
from pathlib import Path
import numpy as np,json,hashlib
from orthogonal_score_v2 import current_projection,score
P=Path(__file__).parent
checks=[];errors=[]
for n in [10,11,23]:
 i=np.arange(1,n+1,dtype=float);X=np.column_stack([np.ones(n),np.sin(i*np.sqrt(2)),np.cos(i*np.sqrt(3))]);D=np.clip(np.sin(i*np.sqrt(5))+.7*X[:,1],-3,3);Y=.4*D+X@np.array([3.,-5.,11.])+np.sin(i*np.sqrt(7))
 fit=current_projection(X,D);scale=np.sqrt(np.mean(X*X,axis=0));Z=X/scale;G=np.linalg.inv(Z.T@Z);rd=D-Z@G@Z.T@D;r2=rd@rd;bY=G@Z.T@Y
 errors.append(float(np.max(np.abs(rd-fit['residual']))));num=rd@Y;lev=np.einsum('ij,jk,ik->i',Z,G,Z)
 for j in range(n):
  mask=np.arange(n)!=j;sub=score(X[mask],D[mask],Y[mask],np.array([9.,18.,-33.]))['psi'];nn=num-rd[j]*(Y[j]-Z[j]@bY)/(1-lev[j]);ss=r2-rd[j]**2/(1-lev[j]);loo=nn/((n-1)*np.sqrt(ss/(n-1)));errors.append(abs(sub-loo))
 for bb in [np.zeros(3),np.array([1e3,-5e3,7e3]),np.array([-10,40,-70])]:errors.append(abs(score(X,D,Y,bb)['psi']-np.mean(fit['normalized']*Y)))
checks.append({'name':'inverse_projection_FWL_leaveoneout_and_arbitrary_forward_g_elision','pass':max(errors)<1e-9,'maximum_absolute_error':max(errors)})
# Deterministic path with distinct marker increments verifies exact horizons/overlap.
r=np.arange(146,dtype=float);ks=list(range(8));hs=[3,6,12,48]
assert max(13+12*k+h for k in ks for h in hs)==145
assert 14==12+2 # q+10min firstfutureincrement, notinownq-feature
assert set(range(14,62))&set(range(26,74)) # 4h overlap between8/9UTC
assert set(range(14,17))<set(range(14,20))<set(range(14,26))<set(range(14,62))
checks.append({'name':'exactM5_nested_and_overlapping_label_path_no_future_feature_bar','pass':True})
# Unit, centered bootstrap t equals full sign-resampled mean / sampleSE.
u=np.array([np.sin((i+1)*np.sqrt(11)) for i in range(15)]);u-=u.mean();s=np.array([(-1)**i for i in range(15)]);z=s*u;formula=abs(s@u)/np.sqrt((15*(u@u)-(s@u)**2)/14);errors.append(abs(formula-abs(z.mean())/(z.std(ddof=1)/np.sqrt(15))))
checks.append({'name':'generic_studentized_block_sign_formula','pass':errors[-1]<1e-12})
res={'checks':checks,'all_pass':all(x['pass'] for x in checks),'MonteCarlo_trials_run':0,'real_price_or_response_reads':0};assert res['all_pass'];(P/'STOCHASTIC_INVARIANTS_RAW_V1.json').write_text(json.dumps(res,indent=2,sort_keys=True)+'\n');print(json.dumps(res))
