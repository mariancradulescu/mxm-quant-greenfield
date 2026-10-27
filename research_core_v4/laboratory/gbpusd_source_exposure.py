"""One registered source-only question on existing GBPUSD W37, no model/broker."""
import json,os,subprocess,sys
from pathlib import Path
from .common import need,encoded
from .source_exposure_capacity_profile import profile
from .usd_pair_native_reception import SOURCES,NATIVE,START,END,CHECKOUT,UPLOAD,one_shot
from .durable_gbpusd_week37_chronology import ROOT as ARCHIVE
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-gbpusd-source-exposure.yml'
MODULE='research_core_v4.laboratory.gbpusd_source_exposure'
JOB='gbpusd-source-exposure'
OUT='verification/gbpusd-source-exposure/receipt.json'
SECRET_NAMES=('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM',
 'SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID',
 'R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN')

def workflow():
    prep=('python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
      'python3 -m unittest research_core_v4.laboratory.test_gbpusd_source_exposure research_core_v4.laboratory.test_source_exposure_capacity -v\n'
      'python3 -m research_core_v4.laboratory.durable_gbpusd_week37_chronology --out "${RUNNER_TEMP}/mxm-gbp-source/original"\n'
      'cp research_core_v4/laboratory/week_chronology_reception.py research_core_v4/laboratory/usd_pair_native_reception.py research_core_v4/laboratory/usd_pair_alignment.py .sealed-chronology-source/research_core_v4/laboratory/')
    return {'name':'MXM one existing GBPUSD source exposure census',
     'on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
     'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},
     'jobs':{JOB:{'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
      'runs-on':'ubuntu-24.04','timeout-minutes':20,'environment':'mxm-r3-custody-v1',
      'permissions':{'contents':'read','actions':'read'},'steps':[
       {'uses':CHECKOUT,'with':{'persist-credentials':False}},
       {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.sealed-chronology-source','persist-credentials':False}},
       {'name':'Admit one registered source-only question before custody access','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
       {'name':'Restore exact existing GBPUSD bytes and native decoder extension','run':prep},
       {'name':'Reauthenticate only existing GBPUSD original inside native custody',
        'env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},
        'run':'umask 077\ncd .sealed-chronology-source\npython3 -m research_core_v4.laboratory.usd_pair_native_reception export GBPUSD "${RUNNER_TEMP}/mxm-gbp-source/original/capture.mxmenc" "${RUNNER_TEMP}/mxm-gbp-source/gbp.ndjson"'},
       {'name':'Assess all original source groups under unchanged five-minute contract',
        'env':{'GH_TOKEN':'${{ github.token }}'},
        'run':'umask 077\npython3 -m '+MODULE+' assess "${RUNNER_TEMP}/mxm-gbp-source/gbp.ndjson"'},
       {'uses':UPLOAD,'with':{'name':'gbpusd-source-exposure-${{ github.run_id }}','path':OUT,'if-no-files-found':'error','retention-days':90}}
      ]}}}

def admit():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')==JOB and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,
      'GBP_EXPOSURE_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in SECRET_NAMES),'GBP_EXPOSURE_NO_KEYS_BEFORE_ADMISSION')
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C','.sealed-chronology-source','rev-parse','HEAD'],text=True).strip()==NATIVE and
      json.loads((ROOT/PATH).read_bytes())==workflow(),'GBP_EXPOSURE_EXACT_CHECKOUT_AND_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly()
    need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'GBP_EXPOSURE_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),
                     ('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'GBP_EXPOSURE_AUTHORITY')
    one_shot(route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100'),int(os.environ['GITHUB_RUN_ID']))
    print('GBP_SOURCE_EXPOSURE_ADMITTED_NO_MODEL_NO_BROKER_NO_WRITER',flush=True)

def source_receipt(bridge,manifest):
    cfg=SOURCES['GBPUSD']
    need(bridge['symbol']=='GBPUSD' and bridge['source_run']==cfg['run'] and
      bridge['source_code']==cfg['code'] and bridge['source_trigger']==cfg['trigger'] and
      bridge['cipher_sha256']==cfg['cipher'] and bridge['private_sha256']==cfg['private'] and
      bridge['events']==cfg['bid']+cfg['ask'] and
      bridge['orders']==bridge['strategy_trials']==bridge['economic_outcomes']==0 and
      bridge['historical_arrival_order_proven'] is False and bridge['historical_costs_proven'] is False,
      'GBP_EXPOSURE_EXACT_ORIGINAL_BRIDGE')
    need(manifest['policy']['symbol_id']==2 and manifest['policy']['symbol_name']=='GBPUSD' and
      manifest['policy']['from_ms']==START and manifest['policy']['to_ms']==END and
      manifest['source_run_id']==cfg['run'] and manifest['code_source']==cfg['code'] and
      manifest['source_head']==cfg['trigger'] and manifest['private_sha256']==cfg['private'] and
      manifest['members']['capture.mxmenc']['sha256']==cfg['cipher'] and
      manifest['quote_events']==cfg['bid']+cfg['ask'],'GBP_EXPOSURE_EXACT_ORIGINAL_MANIFEST')
    return {'run':bridge['source_run'],'rows':bridge['events'],'source_code':bridge['source_code'],
      'source_trigger':bridge['source_trigger'],'cipher_sha256':bridge['cipher_sha256'],
      'private_sha256':bridge['private_sha256'],'derived_sha256':bridge['derived_sha256'],
      'first_ms':START,'end_ms':END}

def assess(path):
    admit()
    path=Path(path);bridge=json.loads(Path(str(path)+'.receipt.json').read_bytes())
    manifest=json.loads((ROOT/ARCHIVE/'MANIFEST.json').read_bytes())
    receipt=source_receipt(bridge,manifest)
    observed=profile(path,receipt,manifest)
    result={'schema':'mxm.gbpusd-source-exposure-census.v1','run_id':int(os.environ['GITHUB_RUN_ID']),
      'source_sha':os.environ['GITHUB_SHA'],'original_run':SOURCES['GBPUSD']['run'],
      'symbol':'GBPUSD','iso_week':'2026-W37','partition':'DEVELOPMENT_ALREADY_EXPOSED',
      'profile':observed,'fixed_age_ms':5000,'fixed_inter_group_gap_ms':5000,'fixed_observed_span_ms':300000,
      'new_broker_requests':0,'new_directional_models':0,'economic_replays':0,'market_outcomes':0,
      'orders':0,'cloud_activated':False,'hard21_proven':False,'after_cost_edge_proven':False,
      'all_original_groups_retained':True,'no_price_or_timestamps_published':True,
      'between_observation_liquidity_proven':False,
      'next_action':'REQUIRE_DISTINCT_PREREGISTERED_SOURCE' if observed['observed_stretches_at_least_5min']==0 else 'REQUIRE_EXPOSURE_PATH_AND_DATED_COST_ADMISSION_BEFORE_MODEL'}
    output=ROOT/OUT;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(encoded(result)+b'\n')
    print('MXM_GBPUSD_SOURCE_EXPOSURE '+encoded(result).decode(),flush=True)
    return result

if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==3 and sys.argv[1]=='assess':assess(sys.argv[2])
    else:raise ValueError('GBP_EXPOSURE_EXACT_PHASE')
