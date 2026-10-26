"""Finite zero-broker-requests source census over ORIGINAL W35-37, custody only."""
import json,os,subprocess,sys
from copy import deepcopy
from pathlib import Path
from .source_compatibility_diagnostic import workflow as previous_workflow
from .source_exposure_capacity_profile import profile
from .three_week_source_recovery import FOLDERS,RUNS,ROWS
from .account_source_preflight import consecutive
from .common import need,encoded
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-source-exposure-capacity.yml'
def workflow():
    w=deepcopy(previous_workflow())
    w['name']='MXM finite authentic-source exposure observation census'
    w['on']['push']['paths']=[PATH]
    j=w['jobs'].pop('source-compatibility')
    j['if']=(f"github.repository == '{REPO}' && "
             f"github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1")
    j['steps'][2]['name']='Admit exactly one source-only operation before custody key'
    j['steps'][2]['run']='python3 -m research_core_v4.laboratory.source_exposure_capacity admit'
    j['steps'][3]['name']='Verify source contract and independent artificial observation census'
    j['steps'][3]['run']=j['steps'][3]['run'].replace(
       'research_core_v4.laboratory.test_source_compatibility_diagnostic -v',
       'research_core_v4.laboratory.test_source_exposure_capacity -v')
    j['steps'][5]['name']='Profile original observed BIDASK groups without model or order'
    j['steps'][5]['env']={}
    j['steps'][5]['run']='umask 077\npython3 -m research_core_v4.laboratory.source_exposure_capacity assess "${RUNNER_TEMP}/mxm-source-admission"'
    w['jobs']['source-exposure-capacity']=j
    return w
def admit():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and
         os.environ.get('GITHUB_REF_NAME')==BRANCH and
         os.environ.get('GITHUB_EVENT_NAME')=='push' and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
         os.environ.get('GITHUB_JOB')=='source-exposure-capacity' and
         os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,
         'EXPOSURE_CENSUS_NATIVE_CONTEXT')
    for name in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM',
                 'SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN',
                 'R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET',
                 'R3_CTRADER_REFRESH_TOKEN'):
        need(not os.environ.get(name),'EXPOSURE_CENSUS_NO_KEY_BEFORE_ADMISSION')
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
         subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
         json.loads((ROOT/PATH).read_bytes())==workflow(),
         'EXPOSURE_CENSUS_EXACT_WORKFLOW_CHECKOUT')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    github=GetOnly()
    need(github.json('git/ref/heads/'+BRANCH)['object']['sha']==head,
         'EXPOSURE_CENSUS_OFFICIAL_HEAD')
    for ref,expected in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),
                         ('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(github.json('git/ref/heads/'+ref)['object']['sha']==expected,'EXPOSURE_CENSUS_AUTHORITY')
    runs=github.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
    need(runs['total_count']==len(runs['workflow_runs'])==1 and
         runs['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and
         runs['workflow_runs'][0]['run_attempt']==1,'EXPOSURE_CENSUS_SINGLE_FINITE_ATTEMPT')
    print('MXM_SOURCE_CENSUS_ADMITTED_NO_ECONOMIC_MODEL_NO_BROKER_REQUEST')
def assess(folder):
    source=Path(folder);public={};receipts=[]
    for week,folder_name in FOLDERS.items():
        file=source/(week+'.ndjson')
        receipt=json.loads(Path(str(file)+'.receipt.json').read_bytes())
        manifest=json.loads((ROOT/folder_name/'MANIFEST.json').read_bytes())
        need(receipt['profile']==week and receipt['run']==RUNS[week] and
             receipt['rows']==ROWS[week],'EXPOSURE_CENSUS_REGISTERED_SOURCE')
        receipts.append(receipt);public[week]=profile(file,receipt,manifest)
    consecutive(receipts)
    result={'schema':'mxm.source-exposure-observation-census.v1',
      'run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['GITHUB_SHA'],
      'original_runs':RUNS,'profiles':public,
      'source_groups_reconciled':sum(p['observed_groups'] for p in public.values()),
      'fixed_age_ms':5000,'fixed_inter_group_gap_ms':5000,'fixed_observed_span_ms':300000,
      'no_interpolation_or_dropped_unavailable_groups':True,
      'observed_stretches_not_broker_executable_continuity':True,
      'no_price_or_timestamps_published':True,
      'new_directional_models':0,'economic_replays':0,'market_outcomes':0,
      'new_broker_requests':0,'orders':0,'cloud_activated':False,
      'hard21_proven':False,'after_cost_edge_proven':False,
      'action':'REQUIRE_PREREGISTERED_DISTINCT_SOURCE_WITH_FULL_FUNDED_EXPOSURE_CONTRACT'}
    print('MXM_SOURCE_EXPOSURE_CENSUS '+encoded(result).decode(),flush=True)
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==3 and sys.argv[1]=='assess':assess(sys.argv[2])
    else:raise ValueError('EXPOSURE_CENSUS_EXACT_PHASE')
