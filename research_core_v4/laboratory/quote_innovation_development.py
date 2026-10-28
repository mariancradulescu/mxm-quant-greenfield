"""One frozen quote_innovation-time policy on three originals and one continuous account."""
import base64,gzip,json,os,re,subprocess,sys
from decimal import Decimal as D
from pathlib import Path
from .common import need,encoded,bytes_digest
from .quote_innovation_reference import reference,reconcile,forecast_errors
from .three_week_source import FOLDERS,RUNS,ROWS,NATIVE
ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/'research_core_v4/laboratory/INNOVATION_ACCOUNT_DEVELOPMENT_V1.json'
SPEC_SHA='047ba47a9a6607e87d2cd6aff9ee38b37d44273084ece3a7835c94fa49b2a8cf'
PATH='.github/workflows/mxm-quote_innovation-account-development.yml'
PROJECT='research_core_v4/laboratory/csharp/quote_innovation/MxmQuoteInnovation.csproj'
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
UPLOAD='actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
def spec():
    need(bytes_digest(SPEC.read_bytes())==SPEC_SHA,'INNOVATION_FROZEN_SPEC')
    s=json.loads(SPEC.read_bytes())
    need(bytes_digest((ROOT/s['rules']).read_bytes())==s['rules_sha256'],'INNOVATION_FROZEN_RULES')
    normalized='\n'.join("SPEC_SHA='FROZEN_SPEC_SHA'" if line.startswith('SPEC_SHA=') else line for line in Path(__file__).read_text().splitlines())+'\n'
    need(bytes_digest(normalized.encode())==s['runner_sha256_normalized'],'INNOVATION_FROZEN_RUNNER')
    for p,h in s['implementation_sha256'].items():need(bytes_digest((ROOT/p).read_bytes())==h,'INNOVATION_FROZEN_IMPLEMENTATION')
    return s
def workflow():
    return {'name':'MXM one causal quote-innovation continuous EUR200 DEVELOPMENT','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
      'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{'quote_innovation-account-development':{
       'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
       'runs-on':'ubuntu-24.04','timeout-minutes':30,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
        {'uses':CHECKOUT,'with':{'persist-credentials':False}},
        {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.sealed-chronology-source','persist-credentials':False}},
        {'name':'Admit the exact finite prospective model before key access','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m research_core_v4.laboratory.quote_innovation_development admit'},
        {'name':'Compile and reconcile artificial continuous-account paths without secrets','run':
         'dotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_quote_innovation_development -v\n'
         'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
         'python3 -m research_core_v4.laboratory.durable_week35_chronology --out "${RUNNER_TEMP}/mxm-quote_innovation/W35"\n'
         'python3 -m research_core_v4.laboratory.durable_week36_chronology --out "${RUNNER_TEMP}/mxm-quote_innovation/W36"\n'
         'python3 -m research_core_v4.laboratory.durable_week_chronology --out "${RUNNER_TEMP}/mxm-quote_innovation/W37"\n'
         'cp research_core_v4/laboratory/week_chronology_reception.py research_core_v4/laboratory/three_week_source.py .sealed-chronology-source/research_core_v4/laboratory/'},
        {'name':'Reauthenticate and decode only the three exact originals in existing custody','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':
         'umask 077\ncd .sealed-chronology-source\n'+''.join('python3 -m research_core_v4.laboratory.three_week_source '+w+' "${RUNNER_TEMP}/mxm-quote_innovation/'+w+'/capture.mxmenc" "${RUNNER_TEMP}/mxm-quote_innovation/'+w+'.ndjson"\n' for w in ('W35','W36','W37'))},
        {'name':'Execute one causal learner and one continuous account; reconcile forecasts and cash without keys','run':
         'umask 077\npython3 -m research_core_v4.laboratory.quote_innovation_development result "${RUNNER_TEMP}/mxm-quote_innovation" verification/quote_innovation-account-development'},
        {'name':'Cold read original result without rerunning the model','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'python3 -m research_core_v4.laboratory.quote_innovation_development cold'},
        {'name':'Preserve exact original ciphertext and evaluator without decryption','run':'python3 -m research_core_v4.laboratory.quote_innovation_development preserve'},
        {'uses':UPLOAD,'with':{'name':'quote_innovation-account-development-${{ github.run_id }}','path':'verification/quote_innovation-account-development/receipt.json\nverification/quote_innovation-account-development/full-result.mxmenc\nverification/quote_innovation-account-development/cold.json\nverification/quote_innovation-account-development/evaluator.dll\nverification/quote_innovation-account-development/runtime-original.zip','if-no-files-found':'error','retention-days':90}}
       ]}}}
def admit():
    spec()
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')=='quote_innovation-account-development' and
      os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'INNOVATION_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID',
      'R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM')),'INNOVATION_NO_KEY_BEFORE_ADMISSION')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      json.loads((ROOT/PATH).read_bytes())==workflow(),'INNOVATION_EXACT_SOURCE_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==sha,'INNOVATION_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'INNOVATION_UNCHANGED_AUTHORITY')
    v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
    need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and
      v['workflow_runs'][0]['run_attempt']==1,'INNOVATION_ONE_NATIVE_ATTEMPT')
    print('INNOVATION_FINITE_DEPENDENT_DEVELOPMENT_ONE_CAPITAL_NO_BROKER_NO_WRITER')
def disposition(actual,errors):
    a=actual['account']
    predictive={str(i+35):e['model_beats_zero_mse'] for i,e in enumerate(errors)}
    account_complete=actual['fault'] is None and a is not None and a['OpenPositions']==0
    gates={'all_three_source_blocks_model_mse_below_zero_forecast':all(predictive.values()),
      'predictive_by_week':predictive,'complete_continuous_account':account_complete,
      'net_positive_scenario':account_complete and D(str(a['MarkedEquityEur']))>200,
      'all_three_weeks_21_modeled_entries':account_complete and all(a['EntriesByIsoWeek'].get(f'2026-W{i}',0)>=21 for i in (35,36,37)),
      'drawdown_at_most_40eur':account_complete and D(str(a['MaxDrawdownEur']))<=40}
    verdict='DATA_LIMITED' if not account_complete else 'NET_FAIL_SCENARIO' if not gates['net_positive_scenario'] else 'HARD21_FAIL_SCENARIO' if not gates['all_three_weeks_21_modeled_entries'] else 'DEVELOPMENT_SURVIVOR_UNCONFIRMED' if all(gates[k] for k in ('all_three_source_blocks_model_mse_below_zero_forecast','drawdown_at_most_40eur')) else 'PREDICTIVE_OR_ROBUSTNESS_FAIL'
    return verdict,gates
def result(folder,destination):
    spec();folder=Path(folder);paths=[folder/(w+'.ndjson') for w in FOLDERS];bridges=[]
    for w,p in zip(FOLDERS,paths):
        r=json.loads(Path(str(p)+'.receipt.json').read_bytes());m=json.loads((ROOT/FOLDERS[w]/'MANIFEST.json').read_bytes())
        need(r['profile']==w and r['run']==RUNS[w] and r['rows']==ROWS[w] and
          r['source_code']==m['code_source'] and r['source_trigger']==m['source_head'] and
          r['cipher_sha256']==m['members']['capture.mxmenc']['sha256'] and r['private_sha256']==m['private_sha256'] and
          r['derived_sha256']==bytes_digest(p.read_bytes()),'INNOVATION_ALL_ORIGINAL_SOURCES');bridges.append(r)
    need(all(a['end_ms']==b['first_ms'] for a,b in zip(bridges,bridges[1:])),'INNOVATION_CALENDAR_ADJACENCY')
    context=bytes_digest(encoded({'bridges':bridges,'policy':SPEC_SHA}))
    actual_path=folder/'actual.json'
    subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(actual_path),SPEC_SHA,context]+[str(p) for p in paths],check=True,capture_output=True)
    actual=json.loads(actual_path.read_bytes(),parse_float=D);expected=reference(paths);reconcile(actual,expected)
    errors=forecast_errors(actual['summaries']);verdict,gates=disposition(actual,errors)
    details={'schema':'mxm.quote-innovation-private.v1','source_sha':os.environ['GITHUB_SHA'],'spec_sha256':SPEC_SHA,
      'bridges':bridges,'context_sha256':context,'original_csharp_json_b64':base64.b64encode(actual_path.read_bytes()).decode(),
      'independent_forecasts_and_decisions_reconciled':True,'forecast_errors':errors,'disposition':verdict,'gates':gates}
    private=encoded(details);out=Path(destination);out.mkdir(parents=True,exist_ok=False)
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','INNOVATION_EXISTING_RECIPIENT')
    encrypt_shard(gzip.compress(private,mtime=0),public_key=public,output=out/'full-result.mxmenc')
    binary=ROOT/'research_core_v4/laboratory/csharp/quote_innovation/bin/Release/net8.0/MxmQuoteInnovation.dll'
    (out/'evaluator.dll').write_bytes(binary.read_bytes())
    receipt={'schema':'mxm.quote-innovation-public.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
      'spec_sha256':SPEC_SHA,'source_runs':RUNS,'source_rows_verified':sum(ROWS.values()),'disposition':verdict,'gates':gates,
      'forecasts':actual['predictions'],'signals':actual['signals'],'matured_training_samples':actual['learned_samples'],
      'account_fault':actual['fault'],'predictive_errors_are_reference_midpoints_not_executable_pnl':True,
      'one_initial_capital_eur':200,'initial_funding_count':1,'closed_model_reexecuted':False,
      'independent_forecasts_and_decisions_reconciled':True,'private_sha256':bytes_digest(private),'ciphertext_sha256':bytes_digest((out/'full-result.mxmenc').read_bytes()),
      'actual_evaluator_sha256':bytes_digest(binary.read_bytes()),'models':1,'cost_scenarios':1,'canonical_V2_C033_changed':False,
      'orders':0,'new_broker_requests':0,'cloud_activated':False,'hard21_proven':False,'economic_edge_proven':False,
      'historical_costs_proven':False,'native_ctrader_runtime_reception':False,'next_action':'STOP_FIXED_MODEL_NO_RETUNE_NO_AUTOMATIC_FOLLOWUP'}
    (out/'receipt.json').write_bytes(encoded(receipt));print('MXM_QUOTE_INNOVATION '+json.dumps(receipt,sort_keys=True),flush=True)

def cold():
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import unpack,strict_json
    import tempfile
    out=ROOT/'verification/quote_innovation-account-development';r=json.loads((out/'receipt.json').read_bytes());cipher=(out/'full-result.mxmenc').read_bytes()
    with tempfile.TemporaryDirectory() as d:
        key,fp=_private_key_from_secret(Path(d));need(fp=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','INNOVATION_COLD_RECIPIENT')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(d)),max_bytes=20000000);p=strict_json(raw,max_elements=2000000)
    need(bytes_digest(cipher)==r['ciphertext_sha256'] and bytes_digest(raw)==r['private_sha256'] and p['source_sha']==r['source_sha'] and p['spec_sha256']==r['spec_sha256'] and p['gates']==r['gates'],'INNOVATION_ORIGINAL_COLD')
    c={'schema':'mxm.quote-innovation-cold.v1','run_id':r['run_id'],'ciphertext_sha256':r['ciphertext_sha256'],'original_readback':True,'model_reexecuted':False,'orders':0}
    (out/'cold.json').write_bytes(encoded(c));print('MXM_INNOVATION_COLD '+encoded(c).decode(),flush=True)

def preserve():
    import zipfile
    out=ROOT/'verification/quote_innovation-account-development'
    members=('receipt.json','cold.json','full-result.mxmenc','evaluator.dll')
    with zipfile.ZipFile(out/'runtime-original.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in members:z.write(out/p,p)
    bundle=(out/'runtime-original.zip').read_bytes();need(len(bundle)<2000000,'INNOVATION_ORIGINAL_BOUND')
    print('MXM_INNOVATION_BUNDLE '+encoded({'bytes':len(bundle),'sha256':bytes_digest(bundle),'members':{p:{'bytes':(out/p).stat().st_size,'sha256':bytes_digest((out/p).read_bytes())} for p in members}}).decode(),flush=True)
    for i in range(0,len(bundle),16384):print('MXM_INNOVATION_PART '+str(i//16384)+' '+base64.b64encode(bundle[i:i+16384]).decode(),flush=True)
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==4 and sys.argv[1]=='result':result(*sys.argv[2:])
    elif sys.argv[1:]==['preserve']:preserve()
    elif sys.argv[1:]==['cold']:cold()
    else:raise ValueError('INNOVATION_EXACT_PHASE')
