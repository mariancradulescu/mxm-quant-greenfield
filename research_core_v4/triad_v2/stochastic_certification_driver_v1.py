"""Frozen synthetic execution wrapper. One complete case; never automatic rescue."""
from pathlib import Path
import argparse,json,hashlib,subprocess,math
from scipy.stats import beta
P=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def wilson(k,n,z):
 p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den;rad=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return [max(0,mid-rad),min(1,mid+rad)]
def exact_bounds(k,n):
 a=.05/88
 return [0 if k==0 else float(beta.ppf(a,k,n-k+1)),1 if k==n else float(beta.ppf(1-a,k+1,n-k))]
def interpret(raw,plan):
 n=raw['trials'];rows=[]
 if raw['mode']==0:
  for c,r in enumerate(raw['null']):
   ws=wilson(r[0],n,3.5);cs=exact_bounds(r[0],n);wl=wilson(r[1],n,3.5);cl=exact_bounds(r[1],n);su=wilson(r[2],n,3.5);se=exact_bounds(r[2],n)
   rows.append({'configuration':c,'false_significance':r[0],'false_leads':r[1],'trials':n,'point_FWER':r[0]/n,'lead_FWER':r[1]/n,'significance_Wilson_upper':ws[1],'significance_exact_upper':cs[1],'simultaneous_upper':max(ws[1],cs[1]),'lead_simultaneous_upper':max(wl[1],cl[1]),'fully_supported':r[2],'support_simultaneous_lower':min(su[0],se[0]),'numerical_clock_failures':r[3],'FWER_pass':max(ws[1],cs[1],wl[1],cl[1])<=.05,'support_pass':min(su[0],se[0])>=.95})
  return {'case_id':raw['case_id'],'gate_pass':all(x['FWER_pass'] and x['support_pass'] for x in rows),'rows':rows}
 for a,rr in enumerate(raw['power']):
  curve=[]
  for effect,r in zip(plan['power']['effect_grid'],rr):
   curve.append({'effect':effect,'any_paid_lead':r['any']/n,'Wilson_any':wilson(r['any'],n,1.96),'all_nonnull_leads':r['all']/n,'Wilson_all':wilson(r['all'],n,1.96),'per_leaf_power':[v/n for v in r['per_leaf']],'per_leaf_Wilson':[wilson(v,n,1.96) for v in r['per_leaf']],'supported':r['supported']})
  mdi=next((c['effect'] for c in curve if c['Wilson_any'][0]>=.8),None)
  rows.append({'alternative':plan['power']['alternatives'][a],'curve':curve,'minimum_reliably_detectable_grid_effect':mdi})
 return {'case_id':raw['case_id'],'gate_pass':all(r['minimum_reliably_detectable_grid_effect'] is not None for r in rows[:6]),'rows':rows}
def run(case,mode,binary):
 plan=json.loads((P/'EXACT_STOCHASTIC_CERTIFICATION_PLAN_V1.json').read_text())
 for f,h in plan['bindings'].items():assert sha(P/f)==h,(f,'binding drift')
 assert sha(Path(binary))==plan['compiler']['binary_sha256']
 assert case in range(11) and mode in [0,1]
 if mode==1:assert case in plan['power']['cases']
 trials=plan['precision']['null_trials_per_case'] if mode==0 else plan['precision']['power_trials_per_case']
 seed=(2026100522 if mode==0 else 2026100523)+1009*case
 name=f'RAW_NULL_CASE_{case:02d}_V1.json' if mode==0 else f'RAW_POWER_CASE_{case:02d}_V1.json';dest=P/name
 assert not dest.exists(),'No rerun or overwrite existing case'
 subprocess.run([binary,str(P/'EXACT_SYNTHETIC_GEOMETRY_V1.txt'),str(case),str(mode),str(seed),str(trials),str(dest)],check=True)
 raw=json.loads(dest.read_text());assert raw['trials']==trials and int(raw['seed'])==seed
 # RAW file saved independently. Caller must checkpoint it BEFORE interpretation.
 print(json.dumps({'raw':name,'sha256':sha(dest),'complete_trials':trials,'seed':seed}))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('case',type=int);ap.add_argument('mode',type=int);ap.add_argument('--binary',default='/tmp/triad_v2_worker');a=ap.parse_args();run(a.case,a.mode,a.binary)
