"""One finite paired-source native engineering reception. No model or account replay."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
from .usd_pair_alignment import digest,need
PATH='.github/workflows/mxm-usd-pair-source-reception.yml'
BRANCH='mxm-remediation-p0-p4-20261015-v1'
REPO='mariancradulescu/mxm-quant-greenfield'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'
START=1788739200000;END=1789344000000
SOURCES={
 'EURUSD':{'id':1,'profile':'W37','run':39917922508,'code':'120db3391ed1f4105120274b73a9259690eeeb64',
  'trigger':'e65fea6321d84acce19c0a965f7814ca6d842183','cipher':'2403c74dfd81ab410f9b9c3bdabf4f3d5a5a4df0133cd0adc03933a364d539b6',
  'private':'8dde8355c79f3f379bf14f1fd47a8ed5815646cafbcfc287762fb68c2c2e7b51','bid':342248,'ask':343226},
 'GBPUSD':{'id':2,'profile':'GBPUSD_W37','run':40179011821,'code':'e750288c76eb2d917cbadcea0c9a3449ea4941d5',
  'trigger':'ca3cd598a14be12785e1e1ed2ef7866a70e35ed1','cipher':'3c643d7f4d72503deb39873e5bf10a8f6cb210d83d310d11150acd549dc7c08a',
  'private':'d1dd4ff123f9542f99db15a2e982022e2074e1e63a3a703807d2c2ad2defd513','bid':639246,'ask':635868}}
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
UPLOAD='actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'

def build_workflow():
    return {'name':'MXM native EURUSD GBPUSD strict-prior source reception','on':{'push':{'branches':[BRANCH],'paths':[PATH]},'workflow_dispatch':{}},
     'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{'usd-pair-source':{
      'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
      'runs-on':'ubuntu-24.04','timeout-minutes':25,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
       {'uses':CHECKOUT,'with':{'persist-credentials':False}},
       {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.sealed-chronology-source','persist-credentials':False}},
       {'name':'Admit exact one-shot engineering scope before custody access','env':{'GH_TOKEN':'${{ github.token }}'},
        'run':'python3 -m research_core_v4.laboratory.usd_pair_native_reception admit'},
       {'name':'Restore exact preserved sources and install original wire-decoder extension','run':
        'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
        'python3 -m research_core_v4.laboratory.durable_week_chronology --out "${RUNNER_TEMP}/mxm-usd-pair/eur-source"\n'
        'python3 -m research_core_v4.laboratory.durable_gbpusd_week37_chronology --out "${RUNNER_TEMP}/mxm-usd-pair/gbp-source"\n'
        'cp research_core_v4/laboratory/week_chronology_reception.py research_core_v4/laboratory/usd_pair_native_reception.py research_core_v4/laboratory/usd_pair_alignment.py .sealed-chronology-source/research_core_v4/laboratory/'},
       {'name':'Verify and decode exact originals only inside existing custody','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':
        'umask 077\ncd .sealed-chronology-source\n'
        'python3 -m research_core_v4.laboratory.usd_pair_native_reception export EURUSD "${RUNNER_TEMP}/mxm-usd-pair/eur-source/capture.mxmenc" "${RUNNER_TEMP}/mxm-usd-pair/eur.ndjson"\n'
        'python3 -m research_core_v4.laboratory.usd_pair_native_reception export GBPUSD "${RUNNER_TEMP}/mxm-usd-pair/gbp-source/capture.mxmenc" "${RUNNER_TEMP}/mxm-usd-pair/gbp.ndjson"'},
       {'name':'Execute actual bounded CSharp source alignment and independent full-array verification','run':
        'mkdir -p verification/usd-pair-source\n'
        'dotnet run --project research_core_v4/laboratory/csharp/usd_pair/MxmUsdPairAlignment.csproj -c Release -- "${RUNNER_TEMP}/mxm-usd-pair/eur.ndjson" "${RUNNER_TEMP}/mxm-usd-pair/gbp.ndjson" "${RUNNER_TEMP}/mxm-usd-pair/csharp.json"\n'
        'python3 -m research_core_v4.laboratory.usd_pair_alignment "${RUNNER_TEMP}/mxm-usd-pair/eur.ndjson" "${RUNNER_TEMP}/mxm-usd-pair/gbp.ndjson" "${RUNNER_TEMP}/mxm-usd-pair/csharp.json" "${RUNNER_TEMP}/mxm-usd-pair/independent.json"'},
       {'name':'Bind native source and publish only bounded public reception facts','env':{'GH_TOKEN':'${{ github.token }}'},'run':
        'python3 -m research_core_v4.laboratory.usd_pair_native_reception finalize "${RUNNER_TEMP}/mxm-usd-pair" verification/usd-pair-source/receipt.json'},
       {'uses':UPLOAD,'with':{'name':'usd-pair-native-public-reception-${{ github.run_id }}','path':'verification/usd-pair-source/receipt.json','if-no-files-found':'error','retention-days':90}}
      ]}}}

def one_shot(value,run):
    need(value['total_count']==len(value['workflow_runs'])==1 and value['workflow_runs'][0]['id']==run and value['workflow_runs'][0]['run_attempt']==1,'ONE_REGISTERED_NATIVE_ATTEMPT')
def admit():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
         os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch') and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
         os.environ.get('GITHUB_JOB')=='usd-pair-source' and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID',
         'R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM')),'NO_KEY_BEFORE_ADMISSION')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
         subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
         subprocess.check_output(['git','-C','.sealed-chronology-source','rev-parse','HEAD'],text=True).strip()==NATIVE,'EXACT_SOURCE_CHECKOUTS')
    need(json.loads(Path(PATH).read_bytes())==build_workflow(),'EXACT_NATIVE_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();run=int(os.environ['GITHUB_RUN_ID'])
    need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==sha,'OFFICIAL_TRIGGER_HEAD')
    for ref,expected in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==expected,'UNCHANGED_AUTHORITIES')
    one_shot(route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100'),run)
    print('USD_PAIR_FINITE_NATIVE_ADMISSION_NO_MODEL_NO_BROKER_NO_ACCOUNT_REPLAY',flush=True)
    return sha

def export(symbol,cipher,output):
    need(symbol in SOURCES,'REGISTERED_SYMBOL');cfg=SOURCES[symbol]
    os.environ['LAB_CHRONOLOGY_PROFILE']=cfg['profile']
    from . import week_chronology_reception as native
    from .common import encoded
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and
         subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'EXACT_NATIVE_DECODER')
    for name in ('usd_pair_native_reception.py','usd_pair_alignment.py','week_chronology_reception.py'):
        need((Path('research_core_v4/laboratory')/name).read_bytes()==(Path('../research_core_v4/laboratory')/name).read_bytes(),'EXACT_EXTENSION_BYTES')
    cipher=Path(cipher).read_bytes();need(digest(cipher)==cfg['cipher'],'ORIGINAL_CIPHER')
    with tempfile.TemporaryDirectory() as scratch:
        key,fp=_private_key_from_secret(Path(scratch));need(fp==FP,'EXISTING_CUSTODY_RECIPIENT')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(scratch)))
        need(len(raw)<=120000000 and digest(raw)==cfg['private'],'ORIGINAL_PRIVATE')
        private=strict_json(raw,max_elements=8000000);i=private['identity']
        need(i['run_id']==cfg['run'] and i['source_sha']==cfg['code'] and i['trigger_sha']==cfg['trigger'] and
             i['native_decoder_source_sha']==NATIVE and i['engine_source_sha']=='dbd0a42bf73f9ae5847a90a4ed159d21e0d7197a' and i['attempt']==1,'ORIGINAL_NATIVE_IDENTITY')
        result=native.replay(private)
        need(result['provider_window_complete'] and result['bid_events']==cfg['bid'] and result['ask_events']==cfg['ask'],'ORIGINAL_NATIVE_ROW_COUNTS')
        req,res=native.decode_record(private['receipts'][1],private['account'])
        need(list(req.symbolId)==[cfg['id']] and len(res.symbol)==1 and res.symbol[0].symbolId==cfg['id'] and
             res.symbol[0].HasField('digits') and res.symbol[0].digits==5 and res.symbol[0].HasField('pipPosition') and res.symbol[0].pipPosition==4,'OBSERVED_NATIVE_PRICE_SCALE')
        bid,bc,_=native.verify_tree(private['trees']['BID'],private['receipts'],private['account'],1)
        ask,ac,_=native.verify_tree(private['trees']['ASK'],private['receipts'],private['account'],2)
        need(bc and ac,'COMPLETE_TREES');out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('wb') as stream:
            a=b=0
            while a<len(bid) or b<len(ask):
                stamp=min(bid[a][0] if a<len(bid) else 2**63,ask[b][0] if b<len(ask) else 2**63)
                need(START<=stamp<END,'ORIGINAL_WEEK_INTERVAL')
                while a<len(bid) and bid[a][0]==stamp:stream.write(encoded({'t':stamp,'side':'bid','raw':bid[a][1]})+b'\n');a+=1
                while b<len(ask) and ask[b][0]==stamp:stream.write(encoded({'t':stamp,'side':'ask','raw':ask[b][1]})+b'\n');b+=1
        receipt={'symbol':symbol,'source_run':cfg['run'],'cipher_sha256':cfg['cipher'],'private_sha256':cfg['private'],
          'source_code':cfg['code'],'source_trigger':cfg['trigger'],'events':cfg['bid']+cfg['ask'],'derived_sha256':digest(out.read_bytes()),
          'historical_arrival_order_proven':False,'historical_costs_proven':False,'orders':0,'strategy_trials':0,'economic_outcomes':0}
        Path(str(out)+'.receipt.json').write_bytes(encoded(receipt))

def finalize(folder,output):
    admit()  # Still the exact admitted native run; no custody or broker key in this step.
    folder=Path(folder)
    c=json.loads((folder/'csharp.json').read_bytes());p=json.loads((folder/'independent.json').read_bytes())
    bridges={s:json.loads((folder/(name+'.ndjson.receipt.json')).read_bytes()) for s,name in [('EURUSD','eur'),('GBPUSD','gbp')]}
    for symbol,field in [('EURUSD','eur_file_sha256'),('GBPUSD','gbp_file_sha256')]:
        cfg=SOURCES[symbol];r=bridges[symbol]
        need(r['source_run']==cfg['run'] and r['source_code']==cfg['code'] and r['source_trigger']==cfg['trigger'] and
             r['cipher_sha256']==cfg['cipher'] and r['private_sha256']==cfg['private'] and
             r['events']==cfg['bid']+cfg['ask'] and r['derived_sha256']==c[field],'BOTH_NATIVE_DERIVATIONS')
    need(c['result']['Rows']==1960588 and c['result']['SourceRows']=={'EURUSD':685474,'GBPUSD':1275114} and
         p['every_state_routing_mark_group_checked'] is True and p['state_sha256']==c['result']['StateSha256'] and
         p['routing_sha256']==c['result']['RoutingSha256'] and p['mark_sha256']==c['result']['MarkSha256'],'ORIGINAL_NATIVE_CSHARP_PYTHON_PARITY')
    need(c['broker_orders']==c['strategy_trials']==c['economic_outcomes']==0 and
         all(c[k] is False for k in ('economic_edge_proven','hard21_proven','historical_arrival_order_proven',
                                    'historical_fills_proven','account_replay_executed')) and
         p['broker_orders']==p['strategy_trials']==p['economic_outcomes']==0 and
         all(p[k] is False for k in ('economic_edge_proven','hard21_proven','account_replay_executed')),'NO_FAVOURABLE_PROMOTION')
    receipt={'schema':'mxm.native.usd-pair-source-reception.v1','run_id':int(os.environ['GITHUB_RUN_ID']),
      'source_sha':os.environ['GITHUB_SHA'],'native_decoder_sha':NATIVE,'partition':'DEVELOPMENT_M5_ALREADY_EXPOSED',
      'bridges':bridges,'original_csharp_report':c,'independent_receipt':p,'original_csharp_report_sha256':digest((folder/'csharp.json').read_bytes()),
      'native_custody_verified':True,'new_broker_requests':0,'broker_orders':0,'strategy_trials':0,'economic_outcomes':0,
      'economic_edge_proven':False,'hard21_proven':False,'account_replay_executed':False,'historical_costs_proven':False,
      'native_ctrader_runtime_reception':False}
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('MXM_NATIVE_USD_PAIR_SOURCE_RECEPTION '+json.dumps(receipt,sort_keys=True),flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==5 and sys.argv[1]=='export':export(*sys.argv[2:])
    elif len(sys.argv)==4 and sys.argv[1]=='finalize':finalize(*sys.argv[2:])
    else:raise ValueError('USD_PAIR_EXACT_PHASE_ARGUMENTS')
