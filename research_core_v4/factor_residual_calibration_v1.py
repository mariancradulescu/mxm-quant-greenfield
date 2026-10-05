"""Predeclared synthetic null/power diagnostics; no market input accepted."""
import math,random,statistics
from research_core_v4.factor_residual_v1 import inference

def wilson(k,n):
 z=1.959963984540054;a=k/n;d=1+z*z/n;center=(a+z*z/(2*n))/d;half=z*math.sqrt(a*(1-a)/n+z*z/(4*n*n))/d;return [center-half,center+half]
def trial(rng,kind,n,effect=0):
 rows={f'{c}:{h}':{} for c in ('A','B') for h in (12,48)};previous={k:0. for k in rows}
 for i in range(n):
  common=rng.gauss(0,1)
  for key in sorted(rows):
   x=rng.gauss(0,1)
   if kind=='heavy':x/=math.sqrt(sum(rng.gauss(0,1)**2 for _ in range(5))/5)
   if kind=='skew':x=(math.exp(.7*x)-math.exp(.245))/math.sqrt((math.exp(.49)-1)*math.exp(.49))
   x=.4*common+math.sqrt(.84)*x
   if kind=='ar':x=.35*previous[key]+math.sqrt(1-.35**2)*x
   previous[key]=x;rows[key][i]=x+effect
 return rows

def run(trials=512,resamples=255):
 rng=random.Random(20261005);null={};power={}
 for kind in ('normal','heavy','skew','ar'):
  rejects=0
  for i in range(trials):
   r=inference(trial(rng,kind,21),seed=50000+i,resamples=resamples);rejects+=any(p<=.01 for p in r['adjusted_pvalues'].values())
  null[kind]={'trials':trials,'family_rejections':rejects,'fwer_estimate':rejects/trials,'wilson95':wilson(rejects,trials)}
 for effect in (.25,.5,1.,2.):
  passed=0
  for i in range(trials):
   r=inference(trial(rng,'normal',21,effect),seed=90000+i,resamples=resamples);passed+=r['adjusted_pvalues']['A:12']<=.01 and r['adjusted_pvalues']['B:12']<=.01
  power[str(effect)]={'replicated_horizon_power':passed/trials,'wilson95':wilson(passed,trials),'effect_unit':'BLOCK_STANDARD_DEVIATIONS_NOT_BPS_OR_PROFIT'}
 return {'schema':'mxm.v4.factor-residual-synthetic-calibration.v1','seed':20261005,'null':null,'power':power,'bootstrap_replicates_per_trial':resamples,'production_replicates':1023,'prospective_selection_alpha':.01,'target_family_error_ceiling':.05,'assumptions':'stationary short-memory block vectors; asymptotic MBB/HAC, not exact randomization','mc_gate_pass':all(v['wilson95'][1]<=.05 for v in null.values()),'mc_gate_definition':'upper Wilson95 FWER<=.05 in each prespecified stress case; limited diagnostic precision, not a proof of exact nominal5% control','small_effect_null_interpretation':'LOW_POWER_NOT_ECONOMIC_NULL','market_data_read':False,'real_response_opened':False}
if __name__=='__main__':
 import json,sys
 print(json.dumps(run(),sort_keys=True))
