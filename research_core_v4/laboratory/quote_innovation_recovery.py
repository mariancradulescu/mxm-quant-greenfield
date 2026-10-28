"""One finite first-outcome recovery using the ALREADY EXISTING schema adapter.
Original scientific specification, kernel, account, decoder and sources unchanged.
"""
import base64,json,os,subprocess,sys,zipfile
from pathlib import Path
from .common import need,encoded,bytes_digest
from . import quote_innovation_development as original
ROOT=original.ROOT
PATH='.github/workflows/mxm-quote-innovation-first-outcome-recovery.yml'
PLAN=ROOT/'research_core_v4/laboratory/QUOTE_INNOVATION_TECHNICAL_RECOVERY_V1.json'
PLAN_SHA='a5d57b321142a6718ef5caff5ea387fb4164a6f0505ecbb6fc19fb82c4b2a55b'
FAILED=40674118381;FAILED_JOB=122768039335;FAILED_HEAD='37eac123ddab6ca529a5310913d1d1ccd6d4fd03'
def plan():
 original.spec();need(bytes_digest(PLAN.read_bytes())==PLAN_SHA,'INNOVATION_RECOVERY_SPEC');p=json.loads(PLAN.read_bytes())
 normalized='\n'.join("PLAN_SHA='FROZEN_RECOVERY_SHA'" if line.startswith('PLAN_SHA=') else line for line in Path(__file__).read_text().splitlines())+'\n'
 need(bytes_digest(normalized.encode())==p['runner_sha256_normalized'],'INNOVATION_RECOVERY_RUNNER')
 for path,h in p['implementation_sha256'].items():need(bytes_digest((ROOT/path).read_bytes())==h,'INNOVATION_RECOVERY_IMPLEMENTATION')
 return p
def workflow():
 w=original.workflow();w['name']='MXM quote-innovation first-outcome technical recovery'
 w['on']['push']['paths']=[PATH];j=w['jobs'].pop('quote_innovation-account-development');w['jobs']['quote-innovation-recovery']=j
 steps=j['steps'];steps[2]['run']='python3 -m research_core_v4.laboratory.quote_innovation_recovery admit'
 steps[3]['run']=steps[3]['run'].replace('test_quote_innovation_development -v','test_quote_innovation_development research_core_v4.laboratory.test_quote_innovation_recovery -v').replace('three_week_source.py','three_week_source_recovery.py')
 steps[4]['run']=steps[4]['run'].replace('laboratory.three_week_source ','laboratory.three_week_source_recovery ')
 steps[5]['run']=steps[5]['run'].replace('quote_innovation_development result','quote_innovation_recovery result')
 steps[7]['run']='python3 -m research_core_v4.laboratory.quote_innovation_recovery preserve'
 steps[8]['with']['name']='quote-innovation-recovery-${{ github.run_id }}';steps[8]['with']['path']+='\nverification/quote_innovation-account-development/recovery.json'
 return w
def no_original_outcome(run,jobs,artifacts):
 need(run['id']==FAILED and run['head_sha']==FAILED_HEAD and run['run_attempt']==1 and run['status']=='completed' and run['conclusion']=='failure','INNOVATION_ORIGINAL_FAILED')
 need(jobs['total_count']==len(jobs['jobs'])==1 and jobs['jobs'][0]['id']==FAILED_JOB and jobs['jobs'][0]['conclusion']=='failure','INNOVATION_ORIGINAL_JOB')
 states={s['name']:s['conclusion'] for s in jobs['jobs'][0]['steps']}
 need(states.get('Reauthenticate and decode only the three exact originals in existing custody')=='failure' and
  states.get('Execute one causal learner and one continuous account; reconcile forecasts and cash without keys')=='skipped' and
  states.get('Cold read original result without rerunning the model')=='skipped' and
  states.get('Preserve exact original ciphertext and evaluator without decryption')=='skipped' and
  artifacts['total_count']==0 and not artifacts['artifacts'],'INNOVATION_NO_REEXECUTION_OF_ECONOMICS')
def admit():
 plan();need(os.environ.get('GITHUB_REPOSITORY')==original.REPO and os.environ.get('GITHUB_REF_NAME')==original.BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')=='quote-innovation-recovery' and os.environ.get('GITHUB_WORKFLOW_REF')==original.REPO+'/'+PATH+'@refs/heads/'+original.BRANCH,'INNOVATION_RECOVERY_CONTEXT')
 need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM')),'INNOVATION_RECOVERY_NO_KEYS')
 sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and json.loads((ROOT/PATH).read_bytes())==workflow(),'INNOVATION_RECOVERY_EXACT_CODE')
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();need(route.json('git/ref/heads/'+original.BRANCH)['object']['sha']==sha,'INNOVATION_RECOVERY_HEAD')
 for ref,h in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==h,'INNOVATION_RECOVERY_AUTHORITY')
 no_original_outcome(route.json(f'actions/runs/{FAILED}'),route.json(f'actions/runs/{FAILED}/jobs?per_page=100'),route.json(f'actions/runs/{FAILED}/artifacts?per_page=100'))
 v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and v['workflow_runs'][0]['run_attempt']==1,'INNOVATION_ONE_TECHNICAL_RECOVERY')
 print('INNOVATION_ORIGINAL_EVALUATION_SKIPPED_ONE_TECHNICAL_RECOVERY_NO_REFUND',flush=True)
def result(folder,destination):
 plan();original.result(folder,destination)
 r={'schema':'mxm.quote-innovation-first-outcome-recovery.v1','failed_run':FAILED,'failed_job':FAILED_JOB,'failed_head':FAILED_HEAD,'original_economics':'SKIPPED','recovery_run':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['GITHUB_SHA'],'scientific_spec_sha256':original.SPEC_SHA,'technical_spec_sha256':PLAN_SHA,'new_scientific_models':0,'scientific_parameters_changed':False,'attempt_refunded':False,'existing_schema_adapter_reused':True,'new_broker_requests':0,'orders':0}
 (Path(destination)/'recovery.json').write_bytes(encoded(r));print('MXM_INNOVATION_RECOVERY '+encoded(r).decode(),flush=True)
def preserve():
 out=ROOT/'verification/quote_innovation-account-development';members=('receipt.json','cold.json','recovery.json','full-result.mxmenc','evaluator.dll')
 with zipfile.ZipFile(out/'runtime-original.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in members:z.write(out/p,p)
 b=(out/'runtime-original.zip').read_bytes();need(len(b)<2000000,'INNOVATION_RECOVERY_BUNDLE_BOUND')
 print('MXM_INNOVATION_BUNDLE '+encoded({'bytes':len(b),'sha256':bytes_digest(b),'members':{p:{'bytes':(out/p).stat().st_size,'sha256':bytes_digest((out/p).read_bytes())} for p in members}}).decode(),flush=True)
 for i in range(0,len(b),16384):print('MXM_INNOVATION_PART '+str(i//16384)+' '+base64.b64encode(b[i:i+16384]).decode(),flush=True)
if __name__=='__main__':
 os.umask(0o077)
 if sys.argv[1:]==['admit']:admit()
 elif len(sys.argv)==4 and sys.argv[1]=='result':result(*sys.argv[2:])
 elif sys.argv[1:]==['preserve']:preserve()
 else:raise ValueError('INNOVATION_RECOVERY_EXACT_PHASE')
