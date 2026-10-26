"""One frozen intrinsic-time policy on three originals and one continuous account."""
import base64,gzip,json,os,re,subprocess,sys
from decimal import Decimal as D
from pathlib import Path
from .common import need,encoded,bytes_digest
from .intrinsic_reference import reference,reconcile
from .three_week_source import FOLDERS,RUNS,ROWS,NATIVE
ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/'research_core_v4/laboratory/INTRINSIC_ACCOUNT_DEVELOPMENT_V1.json'
SPEC_SHA='61da70636bd4eb9a316ab7c7365836290f510be510e3d862247da493d6135b12'
PATH='.github/workflows/mxm-intrinsic-account-development.yml'
PROJECT='research_core_v4/laboratory/csharp/intrinsic/MxmIntrinsicAccount.csproj'
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
UPLOAD='actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
def spec():
    need(bytes_digest(SPEC.read_bytes())==SPEC_SHA,'INTRINSIC_FROZEN_SPEC')
    s=json.loads(SPEC.read_bytes())
    need(bytes_digest((ROOT/s['rules']).read_bytes())==s['rules_sha256'],'INTRINSIC_FROZEN_RULES')
    normalized='\n'.join("SPEC_SHA='FROZEN_SPEC_SHA'" if line.startswith('SPEC_SHA=') else line for line in Path(__file__).read_text().splitlines())+'\n'
    need(bytes_digest(normalized.encode())==s['runner_sha256_normalized'],'INTRINSIC_FROZEN_RUNNER')
    for p,h in s['implementation_sha256'].items():need(bytes_digest((ROOT/p).read_bytes())==h,'INTRINSIC_FROZEN_IMPLEMENTATION')
    return s
def workflow():
    return {'name':'MXM one intrinsic-time continuous EUR200 DEVELOPMENT','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
      'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{'intrinsic-account-development':{
       'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
       'runs-on':'ubuntu-24.04','timeout-minutes':30,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
        {'uses':CHECKOUT,'with':{'persist-credentials':False}},
        {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.sealed-chronology-source','persist-credentials':False}},
        {'name':'Admit the exact finite prospective model before key access','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m research_core_v4.laboratory.intrinsic_development admit'},
        {'name':'Compile and reconcile artificial continuous-account paths without secrets','run':
         'dotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_intrinsic_development -v\n'
         'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
         'python3 -m research_core_v4.laboratory.durable_week35_chronology --out "${RUNNER_TEMP}/mxm-intrinsic/W35"\n'
         'python3 -m research_core_v4.laboratory.durable_week36_chronology --out "${RUNNER_TEMP}/mxm-intrinsic/W36"\n'
         'python3 -m research_core_v4.laboratory.durable_week_chronology --out "${RUNNER_TEMP}/mxm-intrinsic/W37"\n'
         'cp research_core_v4/laboratory/week_chronology_reception.py research_core_v4/laboratory/three_week_source.py .sealed-chronology-source/research_core_v4/laboratory/'},
        {'name':'Reauthenticate and decode only the three exact originals in existing custody','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':
         'umask 077\ncd .sealed-chronology-source\n'+''.join('python3 -m research_core_v4.laboratory.three_week_source '+w+' "${RUNNER_TEMP}/mxm-intrinsic/'+w+'/capture.mxmenc" "${RUNNER_TEMP}/mxm-intrinsic/'+w+'.ndjson"\n' for w in ('W35','W36','W37'))},
        {'name':'Execute one fixed account across fresh processes and independently reconcile then encrypt','run':
         'umask 077\npython3 -m research_core_v4.laboratory.intrinsic_development result "${RUNNER_TEMP}/mxm-intrinsic" verification/intrinsic-account-development'},
        {'uses':UPLOAD,'with':{'name':'intrinsic-account-development-${{ github.run_id }}','path':'verification/intrinsic-account-development/receipt.json\nverification/intrinsic-account-development/full-result.mxmenc','if-no-files-found':'error','retention-days':90}}
       ]}}}
def admit():
    spec()
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')=='intrinsic-account-development' and
      os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'INTRINSIC_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID',
      'R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM')),'INTRINSIC_NO_KEY_BEFORE_ADMISSION')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      json.loads((ROOT/PATH).read_bytes())==workflow(),'INTRINSIC_EXACT_SOURCE_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==sha,'INTRINSIC_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'INTRINSIC_UNCHANGED_AUTHORITY')
    v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
    need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and
      v['workflow_runs'][0]['run_attempt']==1,'INTRINSIC_ONE_NATIVE_ATTEMPT')
    print('INTRINSIC_FINITE_DEPENDENT_DEVELOPMENT_ONE_CAPITAL_NO_BROKER_NO_WRITER')
def run_segments(paths,folder,context,policy,command=None):
    reports=[];previous='-'
    for index,path in enumerate(paths):
        output=Path(folder)/f'segment-{index}.json'
        command_prefix=command or ['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--']
        subprocess.run(command_prefix+['--segment',str(path),str(output),context,policy,previous],check=True,capture_output=True)
        r=json.loads(output.read_bytes(),parse_float=D);reports.append(r);previous=str(output)
        need(r['input_sha256']==bytes_digest(Path(path).read_bytes()) and r['source_context']==context and r['policy_sha256']==policy,'INTRINSIC_SEGMENT_SOURCE_BINDING')
        if r['fault'] or 'SIMULATED_EQUITY_OR_MARGIN_HALT_NOT_BROKER_STOPOUT' in r['account']['Rejections']:break
    return reports
def disposition(reports):
    if any(r['fault'] for r in reports):return 'DATA_LIMITED',{'complete_three_week_account':False}
    a=reports[-1]['account'];weeks=a['EntriesByIsoWeek'];cash=D(str(a['FinalCashEur']))
    gates={'complete_three_week_account':len(reports)==3 and a['OpenPositions']==0,
      'net_positive':D(str(a['MarkedEquityEur']))>200,
      'all_three_weeks_21_modeled_entries':all(weeks.get(f'2026-W{i}',0)>=21 for i in (35,36,37)),
      'every_week_positive_increment':all(D(str(r['account']['MarkedEquityEur']))>D(str(reports[i-1]['account']['MarkedEquityEur'])) if i else D(str(r['account']['MarkedEquityEur']))>200 for i,r in enumerate(reports)),
      'drawdown_at_most_20pct_initial':D(str(a['MaxDrawdownEur']))<=40}
    if 'SIMULATED_EQUITY_OR_MARGIN_HALT_NOT_BROKER_STOPOUT' in a['Rejections']:return 'CAPITAL_INFEASIBLE_SCENARIO',gates
    if not gates['complete_three_week_account']:return 'DATA_LIMITED',gates
    if not gates['net_positive']:return 'NET_FAIL_SCENARIO',gates
    if not gates['all_three_weeks_21_modeled_entries']:return 'HARD21_FAIL_SCENARIO',gates
    return ('DEVELOPMENT_SURVIVOR_UNCONFIRMED' if all(gates.values()) else 'ROBUSTNESS_FAIL_SCENARIO'),gates
def result(folder,destination):
    spec();folder=Path(folder);paths=[folder/(w+'.ndjson') for w in FOLDERS];bridges=[]
    for w,p in zip(FOLDERS,paths):
        r=json.loads(Path(str(p)+'.receipt.json').read_bytes());m=json.loads((ROOT/FOLDERS[w]/'MANIFEST.json').read_bytes())
        need(r['profile']==w and r['run']==RUNS[w] and r['rows']==ROWS[w] and
          r['source_code']==m['code_source'] and r['source_trigger']==m['source_head'] and
          r['cipher_sha256']==m['members']['capture.mxmenc']['sha256'] and r['private_sha256']==m['private_sha256'] and
          r['derived_sha256']==bytes_digest(p.read_bytes()),'INTRINSIC_ALL_ORIGINAL_SOURCES');bridges.append(r)
    need(all(a['end_ms']==b['first_ms'] for a,b in zip(bridges,bridges[1:])),'INTRINSIC_CALENDAR_ADJACENCY')
    context=bytes_digest(encoded({'bridges':bridges,'policy':SPEC_SHA}));reports=run_segments(paths,folder,context,SPEC_SHA)
    expected=reference(paths);reconcile(reports,expected);verdict,gates=disposition(reports)
    details={'schema':'mxm.intrinsic-account-private.v1','source_sha':os.environ['GITHUB_SHA'],'spec_sha256':SPEC_SHA,
      'bridges':bridges,'context_sha256':context,'original_csharp_json_b64':[base64.b64encode((folder/f'segment-{i}.json').read_bytes()).decode() for i in range(len(reports))],
      'independent_reference':expected,'disposition':verdict,'gates':gates,'independent_all_decisions_and_money_reconciled':True,
      'models':1,'cost_scenarios':1,'partition':'DEVELOPMENT_ALREADY_M5_EXPOSED'}
    # Monetary Decimal reference values stay exact decimal strings; original
    # C# bytes are retained separately, never float-reserialized as evidence.
    def serial(v):
        if isinstance(v,D):return str(v)
        if isinstance(v,dict):return {k:serial(x) for k,x in v.items()}
        if isinstance(v,list):return [serial(x) for x in v]
        return v
    private=encoded(serial(details));out=Path(destination);out.mkdir(parents=True,exist_ok=True)
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','INTRINSIC_EXISTING_RECIPIENT')
    encrypt_shard(gzip.compress(private,mtime=0),public_key=public,output=out/'full-result.mxmenc')
    receipt={'schema':'mxm.intrinsic-account-public.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
      'spec_sha256':SPEC_SHA,'source_runs':RUNS,'source_rows_verified':sum(ROWS.values()),'disposition':verdict,'gates':gates,
      'independent_all_decisions_and_money_reconciled':True,'private_sha256':bytes_digest(private),'ciphertext_sha256':bytes_digest((out/'full-result.mxmenc').read_bytes()),
      'fresh_csharp_processes_executed':len(reports),'models':1,'cost_scenarios':1,'canonical_V2_C033_changed':False,
      'orders':0,'new_broker_requests':0,'cloud_activated':False,'hard21_proven':False,'economic_edge_proven':False,
      'historical_costs_proven':False,'native_ctrader_runtime_reception':False,'next_action':'STOP_FIXED_MODEL_NO_RETUNE' if verdict!='DEVELOPMENT_SURVIVOR_UNCONFIRMED' else 'SEPARATE_COST_AND_INDEPENDENT_CONFIRMATION_ADMISSION_REQUIRED'}
    (out/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True))
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==4 and sys.argv[1]=='result':result(*sys.argv[2:])
    else:raise ValueError('INTRINSIC_EXACT_PHASE')
