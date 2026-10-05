"""Fail-closed synthetic control plane. ARM absent => no RNG/trial execution.
Each complete raw case requires a durable Git checkpoint before interpretation.
"""
from pathlib import Path
import argparse, hashlib, json, socket, subprocess, sys
import numpy as np
import scipy
from scipy.stats import beta
from stochastic_worker_v1 import P,R,sha,canonical,Projection,load_geometry,aggregate_case
def fence():
 def deny(*a,**k):raise RuntimeError('NETWORK_FORBIDDEN_SYNTHETIC_ONLY')
 socket.socket=deny;socket.create_connection=deny;socket.getaddrinfo=deny
def preflight():
 manifest=json.loads((P/'TRIAL_MANIFEST_V1.json').read_text())
 authority=json.loads((P/'PREEXECUTION_AUTHORITY_V1.json').read_text())
 assert authority['manifest_sha256']==sha(P/'TRIAL_MANIFEST_V1.json')
 assert authority['preexecution_validation_pass'] and not authority['statistical_execution_authorized']
 for f,s in authority['bindings'].items():assert sha(R/f)==s,f
 assert np.__version__==manifest['runtime']['numpy'] and scipy.__version__==manifest['runtime']['scipy']
 assert sys.version.split()[0]==manifest['runtime']['python']
 return manifest,authority
def execution_arm(manifest,authority,phase):
 # Separate future governance must create this file on the authoritative branch.
 arm=json.loads((P/'EXECUTION_ARM_V1.json').read_text())
 assert arm['schema']=='TRIAD_V7_SEPARATE_STATISTICAL_EXECUTION_ARM_V1'
 assert arm['authority_sha256']==sha(P/'PREEXECUTION_AUTHORITY_V1.json')
 assert arm['manifest_sha256']==sha(P/'TRIAL_MANIFEST_V1.json')
 assert arm['authorized_phase']==phase and arm['real_response_authorized'] is False
 assert arm['maximum_case_attempts']==1 and arm['automatic_retry'] is False
 return arm
def interval(k,n,tail):
 return [0. if k==0 else float(beta.ppf(tail,k,n-k+1)),1. if k==n else float(beta.ppf(1-tail,k+1,n-k))]
def interpret(raw,manifest):
 mode=raw['mode'];n=raw['trials'];assert n==(manifest['null_trials_per_case'] if mode=='null' else manifest['power_trials_per_case'])
 assert mode in ['null','power'] and raw['case_id'] in (range(len(manifest['null_cases'])) if mode=='null' else manifest['power_case_ids'])
 expected=manifest['partial_nulls'] if mode=='null' else manifest['power_cells']
 assert set(raw['cells'])=={x['id'] for x in expected}
 for ct in raw['cells'].values():
  assert len(ct['per_leaf_lead'])==12
  assert all(type(v) is int and 0<=v<=n for v in [ct[k] for k in ['false_significance','false_lead','any_nonnull_lead','all_nonnull_leads','supported']]+ct['per_leaf_lead'])
  assert ct['false_lead']<=ct['false_significance'] and ct['all_nonnull_leads']<=ct['any_nonnull_lead']
 assert raw['numerical_failures']==0
 rows=[]
 if mode=='null':
  tail=manifest['size_confidence']['one_sided_tail']
  for config in manifest['partial_nulls']:
   ct=raw['cells'][config['id']];a=interval(ct['false_significance'],n,tail);b=interval(ct['false_lead'],n,tail);s=interval(ct['supported'],n,tail)
   passed=max(a[1],b[1])<=.05 and s[0]>=.95
   rows.append({'cell_id':config['id'],'FWER_significance_upper':a[1],'FWER_lead_upper':b[1],'full_support_lower':s[0],'pass':passed})
  return {'schema':'TRIAD_V7_COMPLETE_CASE_INTERPRETATION_V1','mode':mode,'case_id':raw['case_id'],'pass':all(x['pass'] for x in rows),'rows':rows,'failure_is_null_evidence':False}
 tail=manifest['power_confidence']['one_sided_tail']
 for alternative in manifest['power_alternatives']:
  curve=[]
  for effect in manifest['effect_grid']:
   cell=next(c for c in manifest['power_cells'] if c['alternative']==alternative['id'] and c['effect']==effect);ct=raw['cells'][cell['id']]
   curve.append({'effect':effect,'any_nonnull_lead_interval':interval(ct['any_nonnull_lead'],n,tail),'all_nonnull_lead_interval':interval(ct['all_nonnull_leads'],n,tail),'per_leaf_intervals':[interval(k,n,tail) for k in ct['per_leaf_lead']],'support_interval':interval(ct['supported'],n,tail)})
  mdi=next((x['effect'] for x in curve if x['effect']>0 and x['any_nonnull_lead_interval'][0]>=.8),None)
  rows.append({'alternative':alternative['id'],'curve':curve,'MDI_grid':mdi,'adequacy_required':alternative['localized']})
 return {'schema':'TRIAD_V7_COMPLETE_CASE_INTERPRETATION_V1','mode':mode,'case_id':raw['case_id'],'pass':all(x['MDI_grid'] is not None for x in rows if x['adequacy_required']),'rows':rows,'economic_threshold':False,'inconclusive_classification':'LOW_POWER_INFORMATION_UNRESOLVED_WITHIN_FROZEN_GRID_NOT_NULL'}
def raw_checkpoint_verified(rawpath,receipt):
 r=json.loads(Path(receipt).read_text());assert r['raw_sha256']==sha(rawpath)
 # Verify durable Git bytes, not an asserted checkpoint string alone.
 b=subprocess.check_output(['git','show',r['checkpoint_head']+':'+r['repository_path']],cwd=R)
 assert hashlib.sha256(b).hexdigest()==r['raw_sha256'];return r
def verified_gate(out,phase,case,manifest):
 rawpath=out/f'{phase}_{case:02}_raw.json';receipt=out/f'{phase}_{case:02}_raw_receipt.json'
 r=raw_checkpoint_verified(rawpath,receipt);raw=json.loads(rawpath.read_text())
 assert raw['manifest_sha256']==sha(P/'TRIAL_MANIFEST_V1.json') and raw['worker_sha256']==sha(P/'stochastic_worker_v1.py')
 gate=json.loads((out/f'{phase}_{case:02}_interpretation.json').read_text());expected=interpret(raw,manifest)
 expected.update(manifest_sha256=sha(P/'TRIAL_MANIFEST_V1.json'),raw_sha256=sha(rawpath),raw_checkpoint_head=r['checkpoint_head'])
 assert gate==expected and gate['pass'];return gate
def run_next(output,phase):
 fence();manifest,authority=preflight();execution_arm(manifest,authority,phase)
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
 cases=list(range(len(manifest['null_cases']))) if phase=='null' else manifest['power_case_ids']
 if phase=='power':
  for case in range(len(manifest['null_cases'])):
   verified_gate(out,'null',case,manifest)
 for case in cases:
  gatefile=out/f'{phase}_{case:02}_interpretation.json'
  if gatefile.exists():
   verified_gate(out,phase,case,manifest)
   continue
  lock=out/f'{phase}_{case:02}_attempt.lock'
  with lock.open('x') as f:f.write(sha(P/'TRIAL_MANIFEST_V1.json')+'\n')
  try:
   g=load_geometry();project=Projection(P/'projection_bridge_v1.so')
   raw=aggregate_case(manifest,g,project,phase,case)
   raw['manifest_sha256']=sha(P/'TRIAL_MANIFEST_V1.json');raw['worker_sha256']=sha(P/'stochastic_worker_v1.py')
   with (out/f'{phase}_{case:02}_raw.json').open('xb') as f:f.write(canonical(raw))
   return {'status':'RAW_PERSISTED_LOCALLY_REQUIRES_DURABLE_GIT_CHECKPOINT_BEFORE_INTERPRETATION','case':case,'phase':phase}
  except Exception as e:
   with (out/f'{phase}_{case:02}_failure.json').open('x') as f:json.dump({'classification':'STOCHASTIC_CASE_EXECUTION_BLOCKED_UNTESTED_NOT_NULL','exception_type':type(e).__name__,'reason':str(e),'retry_authorized':False,'partial_counts_used':False,'manifest_sha256':sha(P/'TRIAL_MANIFEST_V1.json')},f,indent=2)
   raise
 return {'status':'ALL_FROZEN_CASES_COMPLETED_STOP_FOR_INDEPENDENT_AUDIT','phase':phase}
def interpret_complete_case(rawpath,receipt,output):
 fence();manifest,authority=preflight();raw=json.loads(Path(rawpath).read_text());execution_arm(manifest,authority,raw['mode']);r=raw_checkpoint_verified(rawpath,receipt)
 assert raw['manifest_sha256']==sha(P/'TRIAL_MANIFEST_V1.json')
 assert raw['worker_sha256']==sha(P/'stochastic_worker_v1.py')
 result=interpret(raw,manifest);result['manifest_sha256']=sha(P/'TRIAL_MANIFEST_V1.json');result['raw_sha256']=sha(rawpath);result['raw_checkpoint_head']=r['checkpoint_head']
 with Path(output).open('xb') as f:f.write(canonical(result))
 return {'status':'COMPLETE_CASE_INTERPRETATION_PERSISTED_REQUIRES_DURABLE_CHECKPOINT','pass':result['pass']}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action',choices=['preflight','run-next','interpret']);a.add_argument('--phase',choices=['null','power']);a.add_argument('--output');a.add_argument('--raw');a.add_argument('--receipt');args=a.parse_args()
 if args.action=='preflight':preflight();result={'status':'PREEXECUTION_HASHES_VALID_EXECUTION_NOT_AUTHORIZED'}
 elif args.action=='run-next':result=run_next(args.output,args.phase)
 else:result=interpret_complete_case(args.raw,args.receipt,args.output)
 print(json.dumps(result,sort_keys=True))
