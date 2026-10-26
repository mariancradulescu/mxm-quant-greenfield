"""One newly registered transport recovery, only if original economics never ran."""
import json,os,subprocess,sys
from pathlib import Path
from .common import need,encoded,bytes_digest
from . import intrinsic_development as original
ROOT=original.ROOT
PATH='.github/workflows/mxm-intrinsic-account-recovery.yml'
PLAN=ROOT/'research_core_v4/laboratory/INTRINSIC_TECHNICAL_RECOVERY_V1.json'
RECOVERY_SHA='f7d3d65c8bc74031e9107c9a3acd2063483d8b625c2834adf42268fb9cac1d3f'
FAILED=40283113616;FAILED_JOB=121440966951
FAILED_HEAD='250ba6d79959aa710718d6dafee8b464e2ae9690'
def plan():
    original.spec();need(bytes_digest(PLAN.read_bytes())==RECOVERY_SHA,'INTRINSIC_RECOVERY_PLAN')
    p=json.loads(PLAN.read_bytes());normalized='\n'.join("RECOVERY_SHA='FROZEN_RECOVERY_SHA'" if line.startswith('RECOVERY_SHA=') else line for line in Path(__file__).read_text().splitlines())+'\n'
    need(bytes_digest(normalized.encode())==p['runner_sha256_normalized'],'INTRINSIC_RECOVERY_RUNNER')
    for path,h in p['implementation_sha256'].items():need(bytes_digest((ROOT/path).read_bytes())==h,'INTRINSIC_RECOVERY_IMPLEMENTATION')
    return p
def workflow():
    w=original.workflow();w['name']='MXM bounded intrinsic account first-outcome technical recovery'
    w['on']['push']['paths']=[PATH];job=w['jobs'].pop('intrinsic-account-development');w['jobs']['intrinsic-account-recovery']=job
    steps=job['steps'];steps[2]['run']='python3 -m research_core_v4.laboratory.intrinsic_recovery admit'
    steps[3]['run']=steps[3]['run'].replace('test_intrinsic_development -v','test_intrinsic_development research_core_v4.laboratory.test_intrinsic_recovery -v').replace('three_week_source.py','three_week_source_recovery.py')
    steps[4]['run']=steps[4]['run'].replace('laboratory.three_week_source ','laboratory.three_week_source_recovery ')
    steps[5]['run']=steps[5]['run'].replace('laboratory.intrinsic_development result','laboratory.intrinsic_recovery result')
    steps[6]['with']['name']='intrinsic-account-recovery-${{ github.run_id }}'
    steps[6]['with']['path']+='\nverification/intrinsic-account-development/recovery.json'
    # Capture exact public code bytes before custody/economic inputs. The
    # account capsule pins this assembly; a later rebuild is not that proof.
    binary='research_core_v4/laboratory/csharp/intrinsic/bin/Release/net8.0/MxmIntrinsicAccount'
    steps.insert(4,{'name':'Preserve exact compiled evaluator for same-assembly cold recovery','uses':original.UPLOAD,
      'with':{'name':'intrinsic-account-evaluator-${{ github.run_id }}','path':binary+'.dll\n'+binary+'.deps.json\n'+binary+'.runtimeconfig.json',
       'if-no-files-found':'error','retention-days':90}})
    return w
def no_original_outcome(run,jobs,artifacts):
    need(run['id']==FAILED and run['head_sha']==FAILED_HEAD and run['run_attempt']==1 and run['status']=='completed' and run['conclusion']=='failure','RECOVERY_ORIGINAL_FAILED_RUN')
    need(jobs['total_count']==len(jobs['jobs'])==1,'RECOVERY_ORIGINAL_JOB_COUNT');j=jobs['jobs'][0]
    need(j['id']==FAILED_JOB and j['conclusion']=='failure','RECOVERY_ORIGINAL_JOB')
    states={x['name']:x['conclusion'] for x in j['steps']}
    need(states.get('Reauthenticate and decode only the three exact originals in existing custody')=='failure' and
      states.get('Execute one fixed account across fresh processes and independently reconcile then encrypt')=='skipped' and
      states.get('Run actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02')=='skipped' and
      artifacts['total_count']==0 and not artifacts['artifacts'],'RECOVERY_CANNOT_REEXECUTE_OBSERVED_ECONOMICS')
def admit():
    plan()
    need(os.environ.get('GITHUB_REPOSITORY')==original.REPO and os.environ.get('GITHUB_REF_NAME')==original.BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')=='intrinsic-account-recovery' and
      os.environ.get('GITHUB_WORKFLOW_REF')==original.REPO+'/'+PATH+'@refs/heads/'+original.BRANCH,'RECOVERY_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET',
      'R3_CTRADER_REFRESH_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM')),'RECOVERY_NO_KEY_BEFORE_ADMISSION')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      json.loads((ROOT/PATH).read_bytes())==workflow(),'RECOVERY_EXACT_CHECKOUT_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+original.BRANCH)['object']['sha']==sha,'RECOVERY_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'RECOVERY_UNCHANGED_AUTHORITY')
    no_original_outcome(route.json(f'actions/runs/{FAILED}'),route.json(f'actions/runs/{FAILED}/jobs?per_page=100'),route.json(f'actions/runs/{FAILED}/artifacts?per_page=100'))
    v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
    need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and v['workflow_runs'][0]['run_attempt']==1,'RECOVERY_ONE_ADDITIONAL_TECHNICAL_ATTEMPT')
    print('INTRINSIC_ORIGINAL_ECONOMICS_SKIPPED_ONE_REGISTERED_TECHNICAL_RECOVERY_NO_BUDGET_REFUND')
def result(folder,destination):
    plan();original.result(folder,destination)
    receipt={'schema':'mxm.intrinsic-first-outcome-technical-recovery.v1','original_failed_run':FAILED,'original_failed_job':FAILED_JOB,
      'original_failed_head':FAILED_HEAD,'original_economic_execution':'SKIPPED','recovery_run':int(os.environ['GITHUB_RUN_ID']),
      'source_sha':os.environ['GITHUB_SHA'],'original_policy_spec_sha256':original.SPEC_SHA,'technical_recovery_spec_sha256':RECOVERY_SHA,
      'scientific_parameters_changed':False,'new_scientific_model':False,'original_native_attempt_refunded':False,
      'evaluator_dll_sha256':bytes_digest((ROOT/'research_core_v4/laboratory/csharp/intrinsic/bin/Release/net8.0/MxmIntrinsicAccount.dll').read_bytes()),
      'orders':0,'new_broker_requests':0,'hard21_proven':False,'economic_edge_proven':False}
    (Path(destination)/'recovery.json').write_bytes(encoded(receipt))
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==4 and sys.argv[1]=='result':result(*sys.argv[2:])
    else:raise ValueError('INTRINSIC_RECOVERY_EXACT_PHASE')
