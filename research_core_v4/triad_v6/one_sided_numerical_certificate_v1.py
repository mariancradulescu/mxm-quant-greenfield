"""Prospectively frozen one-sided certificate; no Y or response interface."""
from decimal import Decimal as D,localcontext
import math

def production_support(X,d,c):
 n=len(X);o={'accepted':False,'threshold_ambiguous':False,'reason':'CANDIDATE_FAIL_CLOSED','backward_error_eta':None}
 if not c['accepted']:return o
 if n<5 or n>23 or any(not math.isfinite(v) for row in X for v in row) or any(not math.isfinite(v) for v in d):o['reason']='DIMENSION_OR_FINITE_REJECTION';return o
 scale=[math.sqrt(math.fsum(row[j]*row[j] for row in X)/n) for j in range(3)]
 if any(not math.isfinite(v) or v<=1e-12 for v in scale):o['reason']='SCALE_REJECTION';return o
 Z=[[row[j]/scale[j] for j in range(3)] for row in X];normZ=math.sqrt(math.fsum(v*v for row in Z for v in row));u=2.**-53;K=3*n+6+300*(6*n+32)+12*n+30;gamma=K*u/(1-K*u);delta=gamma*normZ;sv=c['singular_values']
 if any(not math.isfinite(v) for v in sv):o['reason']='NONFINITE_SINGULAR_VALUES';return o
 gs=(2*n+5)*u/(1-(2*n+5)*u)
 ambiguous=any(abs(v-1e-12)<=2*delta or abs(v-1e-12*sv[0])<=2*(1+1e-12)*delta for v in sv) or any(abs(s-1e-12)<=2*gs*s for s in scale)
 o.update(threshold_ambiguous=ambiguous,spectral_radius=delta,rounding_budget_K=K)
 if ambiguous:o['reason']='NUMERICAL_SUPPORT_AMBIGUOUS_UNTESTED_NOT_NULL';return o
 rd=[float(v)*c['rms'] for v in c['normalized']];orth=max(abs(math.fsum(Z[i][j]*rd[i] for i in range(n))) for j in range(3));dnorm=math.sqrt(math.fsum(v*v for v in d));bound=1e-9*max(1.,dnorm);eta=orth/(normZ*max(1.,dnorm))
 o.update(independent_orthogonality_error=orth,orthogonality_bound=bound,backward_error_eta=eta)
 if not orth<bound:o['reason']='INDEPENDENT_ORTHOGONALITY_REJECTION';return o
 if not(c['rms']>=1e-10 and all(math.isfinite(v) for v in c['normalized'])):o['reason']='RESIDUAL_RELIABILITY_REJECTION';return o
 o.update(accepted=True,reason='PRODUCTION_ACCEPTED_SUBJECT_TO_ORACLE_HARD_SAFETY_AUDIT');return o

def certify(X,d,c,a,b):
 p=production_support(X,d,c);r={'oracle_certified':False,'oracle_eligible':bool(b['accepted']),'Jacobi_accept':bool(c['accepted']),'production_accept':p['accepted'],'production_support':p,'conservative_rejection':False,'unsafe_accept':False,'failures':[]}
 with localcontext() as ctx:
  ctx.prec=180
  # Fail-closed scalar support classifications require both-precision scalar decisions, no eigenproblem.
  if a['status']=='MATHEMATICAL_SCALE_REJECTED' and b['status']=='MATHEMATICAL_SCALE_REJECTED':r['oracle_certified']=True
  elif a.get('internal_certificate_pass') and b.get('internal_certificate_pass'):
   singular_rel=max(abs(D(x)-D(y))/max(abs(D(y)),D('1e-100')) for x,y in zip(a['singular_values'],b['singular_values']))
   rms_rel=abs(D(a['residual_RMS'])-D(b['residual_RMS']))/max(abs(D(b['residual_RMS'])),D('1e-100'))
   normalized_error=max((abs(D(x)-D(y)) for x,y in zip(a['normalized'],b['normalized'])),default=D(0))
   decisions=a['accepted']==b['accepted'] and a['rank']==b['rank'] and a['retained']==b['retained']
   stable=decisions and singular_rel<=D('1e-45') and rms_rel<=D('1e-45') and (not b['accepted'] or normalized_error<=D('1e-40'))
   r.update(oracle_certified=stable,cross_precision_singular_relative=str(singular_rel),cross_precision_RMS_relative=str(rms_rel),cross_precision_normalized_abs=str(normalized_error))
  if not r['oracle_certified']:r['failures'].append('NUMERICAL_ORACLE_UNCERTIFIED')
  r['conservative_rejection']=r['oracle_certified'] and r['oracle_eligible'] and not p['accepted']
  if p['accepted']:
   if not r['oracle_certified'] or not b['accepted']:r['unsafe_accept']=True;r['failures'].append('UNSAFE_PRODUCTION_ACCEPT_ORACLE_REJECTS_OR_UNCERTIFIED')
   elif 'singular_values' in b:
    sv_error=max(abs(D.from_float(float(x))-D(y)) for x,y in zip(c['singular_values'],b['singular_values']))
    nr_error=max(abs(D.from_float(float(x))-D(y)) for x,y in zip(c['normalized'],b['normalized']))
    rms_error=abs(D.from_float(float(c['rms']))-D(b['residual_RMS']));rms_bound=D('1e-9')*max(D(b['residual_RMS']),D('1e-10'))
    r.update(max_singular_discrepancy=str(sv_error),normalized_RD_error=str(nr_error),RMS_abs_error=str(rms_error))
    if sv_error>D.from_float(p['spectral_radius']):r['unsafe_accept']=True;r['failures'].append('SINGULAR_BACKWARD_BOUND_FAILURE')
    if nr_error>D('1e-7'):r['unsafe_accept']=True;r['failures'].append('PRODUCTION_FORWARD_ERROR_FAILURE')
    if rms_error>rms_bound:r['unsafe_accept']=True;r['failures'].append('PRODUCTION_RMS_ERROR_FAILURE')
  r['pass']=not r['failures']
 return r
