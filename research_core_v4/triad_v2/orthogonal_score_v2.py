"""Exact current-clock predictor projection and purged forward linear nuisance.
Numerical functions only. This module has no market reader or network interface.
"""
import numpy as np

def current_projection(X,D):
 X=np.asarray(X,dtype=float);D=np.asarray(D,dtype=float)
 assert X.ndim==2 and D.shape==(len(X),) and X.shape[1]==3
 assert np.isfinite(X).all() and np.isfinite(D).all()
 # Column scaling changes numerical coordinates, never the declared span.
 scale=np.sqrt(np.mean(X*X,axis=0));assert np.all(scale>1e-12)
 Z=X/scale;rank=int(np.linalg.matrix_rank(Z,tol=1e-12))
 assert rank==3 and len(X)>=max(5,rank+2)
 beta=np.linalg.pinv(Z,rcond=1e-12)@D;rd=D-Z@beta
 orth=float(np.max(np.abs(Z.T@rd)));assert orth<1e-9*max(1.,float(np.linalg.norm(D)))
 rms=float(np.sqrt(np.mean(rd*rd)));assert rms>=1e-10
 # A single scalar preserves orthogonality. NEVER clip after projection.
 return {'residual':rd,'normalized':rd/rms,'rms':rms,'rank':rank,'beta':beta/scale,'orthogonality_error':orth}

def score(X,D,Y,g_beta):
 fit=current_projection(X,D);Y=np.asarray(Y,dtype=float)
 assert Y.shape==D.shape and np.isfinite(Y).all()
 residual_Y=Y-X@np.asarray(g_beta,dtype=float)
 psi=float(np.mean(fit['normalized']*residual_Y))
 coefficient=float(fit['residual']@residual_Y/(fit['residual']@fit['residual']))
 return {'psi':psi,'partial_coefficient':coefficient,'projection':fit}

def eligible_training_indices(decisions,maturities,update_time):
 decisions=np.asarray(decisions);maturities=np.asarray(maturities)
 # Fixed90day rolling window, full label maturity plus240minute purge.
 return np.flatnonzero((decisions>=update_time-90*1440)&(decisions<update_time)&(maturities+240<update_time))

def forward_baseline(train_X,train_Y,decisions,maturities,update_time):
 ii=eligible_training_indices(decisions,maturities,update_time)
 X=np.asarray(train_X)[ii];Y=np.asarray(train_Y)[ii]
 # Caller passes ten frozen training columns: intercept, two own changes,
 # seven UTC dummies. At a fixed evaluationclock prediction is in3columnspan.
 assert X.shape[1]==10 and len(X)>=240 and np.linalg.matrix_rank(X)==10
 beta=np.linalg.pinv(X,rcond=1e-12)@Y
 return {'beta':beta,'training_indices':ii,'last_maturity_plus_purge':int(np.max(np.asarray(maturities)[ii]+240))}

def clock_baseline_beta(beta,clock_index):
 beta=np.asarray(beta);assert beta.shape==(10,) and 0<=clock_index<8
 intercept=beta[0]+(beta[clock_index+2] if clock_index else 0.)
 return np.array([intercept,beta[1],beta[2]])
