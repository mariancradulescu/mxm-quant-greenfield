"""Finite cache-first H1 commodity-anchor investigation, VIEW-only, no orders."""
import base64,gzip,hashlib,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
from decimal import Decimal as D
from .common import need,encoded,bytes_digest
ROOT=Path(__file__).resolve().parents[2];HOME=ROOT.parent if ROOT.name=='.basis-native' else ROOT
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1';NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'
PATH='.github/workflows/mxm-commodity-anchor-reference-units.yml';MODULE='research_core_v4.laboratory.commodity_anchor_reference_units';PROJECT='research_core_v4/laboratory/csharp/commodity_anchor/MxmCommodityAnchor.csproj'
SPEC='research_core_v4/laboratory/COMMODITY_ANCHOR_H1_V1.json'
SPEC_SHA='f135ebf57cee3302f70e399695ec7dff40123fed3d2c3996933b5727a016f7e1'
TRANSPORT_SHA='588bd967d8bab59a407e8487f76b854b44bed950547acd1af91beb9ccb98ebfa'
OUT=HOME/'verification/commodity-anchor';FP='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
START=1779840000000;EVAL=1780272000000;END=1782691200000 # partial warmup week then four complete June weeks
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683';UPLOAD='actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02';DOWNLOAD='actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093'
INSTALL='python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'
CACHE={1:{'release_id':409747426,'asset_id':631098100,'ciphertext_sha256':'c33f401a97d06e2efe31e49f37a1f977238b41b66eb1d939b1d6700fb2530915'},250:{'release_id':409747426,'asset_id':631098274,'ciphertext_sha256':'809e20a51550ad50bc6ac4a8df524deba47d640f5a0d35454b496ffd2a9d3c2f'}}
def frozen():
 raw=(HOME/SPEC).read_bytes();need(bytes_digest(raw)==SPEC_SHA,'ANCHOR_SPEC');s=json.loads(raw)
 normalized='\n'.join("SPEC_SHA='FROZEN_SPEC_SHA'" if x.startswith('SPEC_SHA=') else x for x in (HOME/'research_core_v4/laboratory/commodity_anchor_development.py').read_text().splitlines())+'\n'
 need(bytes_digest(normalized.encode())==s['runner_sha256_normalized'],'ANCHOR_RUNNER')
 for p,h in s['implementation_sha256'].items():need(bytes_digest((HOME/p).read_bytes())==h,'ANCHOR_IMPLEMENTATION')
 transport=json.loads((HOME/'research_core_v4/laboratory/COMMODITY_ANCHOR_REFERENCE_UNITS_V1.json').read_bytes())
 need(bytes_digest((HOME/'research_core_v4/laboratory/COMMODITY_ANCHOR_REFERENCE_UNITS_V1.json').read_bytes())==TRANSPORT_SHA,'ANCHOR_TRANSPORT_SPEC')
 own='\n'.join("TRANSPORT_SHA='FROZEN_TRANSPORT_SHA'" if x.startswith('TRANSPORT_SHA=') else x for x in Path(__file__).read_text().splitlines())+'\n'
 need(bytes_digest(own.encode())==transport['normalized_transport_sha256'] and transport['economic_spec_sha256']==SPEC_SHA,'ANCHOR_TRANSPORT_CODE')
 need(bytes_digest((HOME/'docs/economic-development/20261028/COMMODITY_REFERENCE_UNITS_ADMISSION_V1.md').read_bytes())==transport['admission_document_sha256'],'ANCHOR_UNIT_ADMISSION_DOCUMENT')
 return s
def context():
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'ANCHOR_NATIVE_CONTEXT')
 frozen()
def workflow():
 def job(env):return {'runs-on':'ubuntu-24.04','timeout-minutes':20,'environment':env,'permissions':{'contents':'read','actions':'read'},'steps':[{'uses':CHECKOUT,'with':{'persist-credentials':False}}]}
 cache=job('mxm-r3-custody-v1');cache['if']=f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1";cache['outputs']={'clear':'${{ steps.cache.outputs.clear }}'}
 cache['steps'] += [{'name':'Admit exact finite source and model before keys','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
  {'name':'Compile shared account and independent artificial H1 policy before custody','run':INSTALL+'\ndotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_commodity_anchor -v'},
  {'name':'Reuse exact existing encrypted handoff without decrypting or contacting broker','id':'cache','run':'umask 077\npython3 -m '+MODULE+' cache'},
  {'uses':UPLOAD,'with':{'name':'anchor-cache-${{ github.run_id }}','path':'verification/commodity-anchor/cache.json\nverification/commodity-anchor/cache-input.mxmenc','if-no-files-found':'error','retention-days':90}}]
 collect=job('mxm-r3-pepperstone-v1');collect.update(needs='source-cache',**{'if':"needs.source-cache.outputs.clear == 'true'"})
 collect['steps'] += [{'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.basis-native','persist-credentials':False}},
  {'uses':DOWNLOAD,'with':{'name':'anchor-cache-${{ github.run_id }}','path':'verification/commodity-anchor'}},
  {'run':INSTALL+'\ncp research_core_v4/laboratory/commodity_anchor_reference_units.py .basis-native/research_core_v4/laboratory/'},
  {'name':'Reuse two cached sources and request only missing anchor plus four metadata responses','env':{**{k:'${{ secrets.'+k+' }}' for k in ('R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_ACCESS_TOKEN')}},'run':'umask 077\ncd .basis-native\npython3 -m '+MODULE+' collect'},
  {'uses':UPLOAD,'if':'always()','with':{'name':'anchor-source-${{ github.run_id }}','path':'verification/commodity-anchor/source.mxmenc\nverification/commodity-anchor/producer.json\nverification/commodity-anchor/cache.json\nverification/commodity-anchor/cache-input.mxmenc','if-no-files-found':'error','retention-days':90}}]
 evaluate=job('mxm-r3-custody-v1');evaluate['needs']='basis-collect'
 evaluate['steps'] += [{'uses':DOWNLOAD,'with':{'name':'anchor-source-${{ github.run_id }}','path':'verification/commodity-anchor'}},
  {'run':INSTALL+'\ndotnet build '+PROJECT+' -c Release'},
  {'name':'Authenticate captured source and export exact private model input','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\npython3 -m '+MODULE+' export'},
  {'name':'One prospective conditional CSharp account and independent causal forecast audit','run':'umask 077\npython3 -m '+MODULE+' evaluate'},
  {'name':'Cold original output readback without model rerun','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'python3 -m '+MODULE+' cold'},
  {'name':'Preserve exact source result evaluator and public receipts','run':'python3 -m '+MODULE+' preserve'},
  {'uses':UPLOAD,'with':{'name':'anchor-result-${{ github.run_id }}','path':'verification/commodity-anchor/*.json\nverification/commodity-anchor/*.mxmenc\nverification/commodity-anchor/*.dll\nverification/commodity-anchor/*.zip','if-no-files-found':'error','retention-days':90}}]
 return {'name':'MXM first reference-unit-aware commodity account evaluation','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{'source-cache':cache,'basis-collect':collect,'basis-evaluate':evaluate}}
def admit():
 context();need(not any(os.environ.get(k) for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','SUCCESSOR_APP_PRIVATE_KEY')),'ANCHOR_KEY_ROLES')
 head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();need(head==os.environ['GITHUB_SHA']==os.environ['GITHUB_WORKFLOW_SHA'] and json.loads((HOME/PATH).read_bytes())==workflow(),'ANCHOR_EXACT_CODE')
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'ANCHOR_OFFICIAL_HEAD')
 for ref,h in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==h,'ANCHOR_AUTHORITY')
 v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and v['workflow_runs'][0]['run_attempt']==1,'ANCHOR_ONE_ATTEMPT')
 from .verify_commodity_anchor_original import verify
 verify();identity();terms_from_identity();need(route.json('actions/runs/40713165061')['conclusion']=='success','ANCHOR_AUTHENTIC_METADATA_READBACK')
 predecessor=route.json('actions/runs/40707021640/jobs')
 need({j['name']:j['conclusion'] for j in predecessor['jobs']}=={'source-cache':'success','basis-collect':'skipped','basis-evaluate':'skipped'},'ANCHOR_PREDECESSOR_ZERO_MODELS')
def private(raw):
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 public=HOME/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'ANCHOR_RECIPIENT');return encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=OUT/'source.mxmenc')
def decrypt(path):
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack
 with tempfile.TemporaryDirectory() as d:
  key,fp=_private_key_from_secret(Path(d));need(fp==FP,'ANCHOR_CUSTODY');raw=unpack(owner.bounded_decrypt(path.read_bytes(),key,Path(d)),max_bytes=20000000)
 return raw

IDENTITY='docs/economic-development/20261028/commodity-anchor-40709936368/identity-readback-40713165061.json'
IDENTITY_SHA='29424ae11527955b0c92fe4a4ac5f0f419256f34271a5e79f121d9d5b95a7e60'
def identity():
 raw=(HOME/IDENTITY).read_bytes();need(bytes_digest(raw)==IDENTITY_SHA,'ANCHOR_EXACT_CAPTURED_IDENTITY');r=json.loads(raw)
 need(r['source_run']==40709936368 and r['run_id']==40713165061 and r['full_ids_exact'] and r['new_models']==0 and r['new_broker_requests']==0,'ANCHOR_CAPTURED_METADATA_ONLY')
 by={x['symbol_id']:x for x in r['requested']}
 for sid,name,quote in [(1,'EURUSD','USD'),(250,'SpotCrude','USD'),(7393,'WTOIL-PERP','USC')]:
  x=by[sid];need(x['name']==name and x['quote']==quote and x['full_present'] and x['enabled'] is True and not x['archived'],'ANCHOR_EXACT_CAPTURED_IDENTITIES')
 return r,by
def terms_from_identity():
 r,by=identity();d=by[250]['contemporary_declared_terms_not_historical_costs']
 required=('minVolume','stepVolume','maxVolume','lotSize','commissionType','preciseTradingCommissionRate','preciseMinCommission','pnlConversionFeeRate','tradingMode','enableShortSelling')
 need(all(d[k] is not None for k in required) and d['minVolume']>0 and d['stepVolume']>0 and d['minVolume']%d['stepVolume']==0 and d['lotSize']>0 and d['commissionType']==2 and d['preciseMinCommission']==0 and d['tradingMode']==0 and d['enableShortSelling']==1,'ANCHOR_ORIGINAL_DECLARED_COST_VOLUME')
 return {'units':d['minVolume']/100,'step_units':d['stepVolume']/100,'max_units':d['maxVolume']/100,'fee_usd':float(D(d['minVolume'])*D(d['preciseTradingCommissionRate'])/D(100000000)/D(d['lotSize'])),'pnl_rate':d['pnlConversionFeeRate']/10000}
def cache():
 context();identity();terms_from_identity();OUT.mkdir(parents=True,exist_ok=True)
 from .verify_commodity_anchor_original import verify,DIR
 verify()
 with zipfile.ZipFile(DIR/'runtime-original.zip') as z:
  for name in ('cache.json','cache-input.mxmenc'):(OUT/name).write_bytes(z.read(name))
 r=json.loads((OUT/'cache.json').read_bytes());need(r['run_id']==40709936368 and r['existing_source_overlap_rows']=={'1':545,'250':521} and r['new_collection_admitted'],'ANCHOR_REUSE_AUTHENTICATED_HANDOFF')
 print('MXM_ANCHOR_CACHE '+encoded({'run_id':int(os.environ['GITHUB_RUN_ID']),'reused_original_cache_run':40709936368,'cache_input_sha256':r['cache_input_sha256'],'new_decryptions':0,'new_broker_requests':0,'new_models':0,'orders':0}).decode(),flush=True)
 with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('clear=true\n')
def collect():
 context();need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and (ROOT/'research_core_v4/laboratory/commodity_anchor_reference_units.py').read_bytes()==(HOME/'research_core_v4/laboratory/commodity_anchor_reference_units.py').read_bytes(),'ANCHOR_PINNED_DECODER')
 need(not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'),'ANCHOR_NO_CUSTODY_IN_BROKER_PROCESS')
 OUT.mkdir(parents=True,exist_ok=True);cache=json.loads((OUT/'cache.json').read_bytes());need(cache['run_id']==40709936368 and cache['new_collection_admitted'],'ANCHOR_ORIGINAL_HANDOFF_SCOPE')
 from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector
 from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m
 from datetime import datetime,timezone
 prior,by=identity();terms=terms_from_identity()
 p={'contact_start_utc':datetime.now(timezone.utc).isoformat(),'schema':'mxm.anchor-native-source.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'spec_sha256':SPEC_SHA,'complete':False,'metadata':[],'history':[],'failure_class':None,'cache':cache,'reused_metadata_source_run':40709936368,'reused_metadata_identity_sha256':IDENTITY_SHA,'reference_quote':'USC','reference_fx_conversion_assumed':False,'panel':{str(k):{'digits':v['digits']} for k,v in by.items()}}
 class Panel(Collector):
  def send(self,req,historical=False):
   if type(req).__name__=='ProtoOAExpectedMarginReq':
    need(self.counts['panel']<1 and req.ctidTraderAccountId==self.aid and req.symbolId==250 and list(req.volume)==[int(terms['units']*100)],'ANCHOR_ONE_MARGIN_ONLY');self.counts['panel']+=1;self.nrate.before_send();res=self.tr.request(req,timeout=30)
    need(not isinstance(res,m.ProtoOAErrorRes) and int(res.ctidTraderAccountId)==self.aid,'ANCHOR_MARGIN_RESPONSE_SCOPE')
    p['metadata'].append({'type':type(req).__name__,'request_b64':base64.b64encode(req.SerializeToString()).decode(),'response_b64':base64.b64encode(res.SerializeToString()).decode()});return res
   return super().send(req,historical)
 col=Panel({'H1':3,'M5':0,'BID_ASK':0,'NONHISTORY':0})
 for a,b in [('R3_CTRADER_CLIENT_ID','CTRADER_CLIENT_ID'),('R3_CTRADER_CLIENT_SECRET','CTRADER_CLIENT_SECRET'),('R3_CTRADER_ACCESS_TOKEN','CTRADER_ACCESS_TOKEN')]:os.environ[b]=os.environ[a]
 try:
  col.connect();p['account']=col.aid
  req=m.ProtoOAExpectedMarginReq(ctidTraderAccountId=col.aid,symbolId=250);req.volume.append(int(terms['units']*100));mr=col.send(req)
  need(mr.HasField('moneyDigits') and len(mr.margin)==1 and mr.margin[0].volume==int(terms['units']*100) and mr.margin[0].HasField('buyMargin') and mr.margin[0].HasField('sellMargin'),'ANCHOR_MARGIN_PRESENT')
  margin=max(mr.margin[0].buyMargin,mr.margin[0].sellMargin)/10**int(mr.moneyDigits);need(0<margin<=80 and 200-margin>=120,'ANCHOR_NECESSARY_CAPITAL_ONLY');terms['margin_eur']=margin;p['terms']=terms
  rows,receipts,state=col.h1(7393,int(by[7393]['digits']),START//1000,END//1000)
  p['history'].append({'sid':7393,'rows':[[int(t)*1000]+v[:4] for t,v in sorted(rows.items())],'receipts':receipts,'state':state})
  p['complete']=state=='COMPLETE_EXACT_WINDOW' and len(rows)>=128 and all(int(t)*1000%3600000==0 and START<=int(t)*1000<END for t in rows)
 except Exception as e:
  p['failure_class']=type(e).__name__;message=str(e);p['failure_code']=message if message.startswith('LAB_ANCHOR_') and len(message)<160 and all(c.isupper() or c=='_' or c.isdigit() for c in message) else type(e).__name__
 finally:
  col.close();p['contact_end_utc']=datetime.now(timezone.utc).isoformat()
 p['wire_counts']=dict(col.wire_types);p['request_counts']=dict(col.counts);raw=encoded(p);private(raw)
 r={'schema':'mxm.anchor-producer.v1','run_id':p['run_id'],'source_sha':p['source_sha'],'spec_sha256':SPEC_SHA,'complete':p['complete'],'failure_class':p['failure_class'],'failure_code':p.get('failure_code'),'private_sha256':bytes_digest(raw),'cipher_sha256':bytes_digest((OUT/'source.mxmenc').read_bytes()),'request_counts':p['request_counts'],'rows':{str(x['sid']):len(x['rows']) for x in p['history']},'contact_start_utc':p['contact_start_utc'],'contact_end_utc':p['contact_end_utc'],'reused_metadata_source_run':40709936368,'reference_quote':'USC','reference_fx_conversion_assumed':False,'new_models':0,'orders':0}
 (OUT/'producer.json').write_bytes(encoded(r));print('MXM_ANCHOR_PRODUCER '+encoded(r).decode(),flush=True)

def export():
 context();r=json.loads((OUT/'producer.json').read_bytes());cipher=(OUT/'source.mxmenc').read_bytes();need(bytes_digest(cipher)==r['cipher_sha256'],'ANCHOR_SOURCE_CIPHER')
 raw=decrypt(OUT/'source.mxmenc');need(bytes_digest(raw)==r['private_sha256'],'ANCHOR_SOURCE_PLAIN');p=json.loads(raw)
 need(p['source_sha']==os.environ['GITHUB_SHA'] and p['spec_sha256']==SPEC_SHA and p['run_id']==int(os.environ['GITHUB_RUN_ID']),'ANCHOR_SOURCE_IDENTITY')
 cache=json.loads((OUT/'cache.json').read_bytes());need(bytes_digest((OUT/'cache-input.mxmenc').read_bytes())==cache['cache_input_sha256'],'ANCHOR_CACHE_HANDOFF')
 reused=json.loads(decrypt(OUT/'cache-input.mxmenc'));need(reused['run_id']==40709936368 and reused['source_sha']=='88c2907a125581cb6c6b84654565688cb91a2db5','ANCHOR_CACHE_HANDOFF_SCOPE')
 temp=Path(os.environ['RUNNER_TEMP'])/'commodity-anchor';temp.mkdir(parents=True,exist_ok=True)
 if not p['complete']:
  (temp/'admission.json').write_bytes(encoded({'admitted':False,'reason':'SOURCE_OR_CONTEMPORARY_TERMS_UNRESOLVED','producer':r}));return
 from research_core_v4 import shallow_m5_support_v2 as v2
 from datetime import datetime
 from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import enums
 # Re-decode ORIGINAL native response envelopes, not copied normalized prices.
 for h in p['history']:
  decoded={};sid=h['sid'];digits=int(p['panel'][str(sid)]['digits'])
  for receipt in h['receipts']:
   from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
   env=ProtoMessage.FromString(base64.b64decode(receipt['raw_response_envelope_b64'],validate=True))
   need(env.IsInitialized() and int(env.payloadType)==v2.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE and bytes_digest(env.payload)==receipt['raw_payload_sha256'],'ANCHOR_RAW_RESPONSE')
   response=v2.ProtoOAGetTrendbarsResV2.FromString(env.payload)
   need(response.IsInitialized() and int(response.ctidTraderAccountId)==p['account'] and int(response.period)==int(enums.H1) and (not response.HasField('symbolId') or int(response.symbolId)==sid),'ANCHOR_NATIVE_RESPONSE_SCOPE')
   for b in response.trendbar:
    z=v2.decode_trendbar(v2.ProtoOATrendbarV2.FromString(b.SerializeToString()),digits=digits,segment_from_ms=0,segment_to_ms=receipt['to_ms'])
    t=int(datetime.fromisoformat(z['time_utc'].replace('Z','+00:00')).timestamp())*1000
    if START<=t<END:
     values=[float(z[k]) for k in ('open','high','low','close')];need(t not in decoded or decoded[t]==values,'ANCHOR_CONFLICT');decoded[t]=values
  need([[t]+z for t,z in sorted(decoded.items())]==h['rows'],'ANCHOR_ALL_NATIVE_BARS_REDECODED')
 by={x['sid']:x['rows'] for x in p['history']}
 need(set(by)=={7393} and set(reused['retained'])=={'1','250'},'ANCHOR_NO_DUPLICATE_HISTORY')
 for sid in (1,250):
  old=reused['retained'][str(sid)];need(old['identity']['sid']==sid and old['proof'] in cache['proofs'] and old['proof']['ciphertext_sha256']==CACHE[sid]['ciphertext_sha256'],'ANCHOR_ORIGINAL_CACHE_BINDING');by[sid]=old['rows']
 overlap=set(z[0] for z in by[1]) & set(z[0] for z in by[250]) & set(z[0] for z in by[7393])
 if len(overlap)<128:
  (temp/'admission.json').write_bytes(encoded({'admitted':False,'reason':'INSUFFICIENT_JOINT_H1_SUPPORT','joint_hours':len(overlap),'producer':r}));return
 data={'policy':SPEC_SHA,'start':START,'evaluation_start':EVAL,'end':END,'terms':p['terms'],'target':by[250],'anchor':by[7393],'fx':by[1]}
 need(all(all(len(z)==5 and z[0]%3600000==0 and min(z[1:])>0 and z[3]<=min(z[1],z[4])<=max(z[1],z[4])<=z[2] for z in h) for h in by.values()),'ANCHOR_INPUT_OHLC')
 (temp/'input.json').write_bytes(encoded(data));(temp/'admission.json').write_bytes(encoded({'admitted':True,'input_sha256':bytes_digest((temp/'input.json').read_bytes()),'original_rows_redecoded':len(by[7393]),'authenticated_cached_rows':len(by[1])+len(by[250])}))

def cache_digest():return bytes_digest((OUT/'cache-input.mxmenc').read_bytes())

def evaluate():
 context();temp=Path(os.environ['RUNNER_TEMP'])/'commodity-anchor';a=json.loads((temp/'admission.json').read_bytes());producer=json.loads((OUT/'producer.json').read_bytes());actual=None
 if a['admitted']:
  from .commodity_anchor_reference import reconcile
  data=json.loads((temp/'input.json').read_bytes());need(bytes_digest((temp/'input.json').read_bytes())==a['input_sha256'],'ANCHOR_DERIVED_INPUT')
  subprocess.run(['dotnet','run','--project',PROJECT,'-c','Release','--no-build','--',str(temp/'input.json'),str(temp/'actual.json')],check=True,capture_output=True)
  actual=json.loads((temp/'actual.json').read_bytes(),parse_float=D);need(actual['input_sha256']==a['input_sha256'] and reconcile(actual,data),'ANCHOR_CAUSAL_REFERENCE')
  account=actual['account'];complete=actual['fault'] is None and account is not None and account['OpenPositions']==0
  frequency=complete and all(account['EntriesByIsoWeek'].get('2026-W'+str(w),0)>=21 for w in (23,24,25,26))
  net=complete and D(str(account['MarkedEquityEur']))>200
  gates={'complete_conditional_account':complete,'net_positive_in_declared_scenario':net,'every_complete_week_21_modeled_entries':bool(frequency),'drawdown_at_most40eur':complete and D(str(account['MaxDrawdownEur']))<=40,'every_complete_week_net_positive':complete and len(actual['weekMarks'])==5 and all(D(str(b))>D(str(a)) for a,b in zip(actual['weekMarks'],actual['weekMarks'][1:]))}
  verdict='DATA_LIMITED' if not complete else 'NET_FAIL_SCENARIO' if not net else 'HARD21_FAIL_SCENARIO' if not frequency else 'TEMPORAL_OR_DRAWDOWN_FAIL_SCENARIO' if not gates['every_complete_week_net_positive'] or not gates['drawdown_at_most40eur'] else 'CONDITIONAL_SCENARIO_SURVIVOR_NOT_QUALIFIED'
 else:verdict='SOURCE_NOT_ADMITTED';gates={}
 private_result=encoded({'schema':'mxm.anchor-private.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'spec_sha256':SPEC_SHA,'admission':a,'original_csharp_b64':base64.b64encode((temp/'actual.json').read_bytes()).decode() if actual is not None else None,'gates':gates,'disposition':verdict})
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
 encrypt_shard(gzip.compress(private_result,mtime=0),public_key=HOME/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem',output=OUT/'result.mxmenc')
 binary=HOME/'research_core_v4/laboratory/csharp/commodity_anchor/bin/Release/net8.0/MxmCommodityAnchor.dll';(OUT/'evaluator.dll').write_bytes(binary.read_bytes())
 account_summary=None
 if actual is not None:
  report=actual['account'] or actual['last_verified_prefix']
  if report is not None:
   fields=('Classification','InitialCapitalEur','FinalCashEur','MarkedEquityEur','UsedMarginEur','FreeMarginEur','MaxDrawdownEur','AcceptedEntries','ExecutedExits','RejectedEntries','OpenPositions','CompleteIsoUtcWeeks','EntriesByIsoWeek')
   account_summary={k:str(report[k]) if isinstance(report[k],D) else report[k] for k in fields}
 r={'conditional_account_summary':account_summary,'conditional_week_equity_marks':[str(x) for x in actual['weekMarks']] if actual is not None else [],'schema':'mxm.commodity-anchor-public.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'spec_sha256':SPEC_SHA,'disposition':verdict,'gates':gates,'reference_quote':'USC','reference_fx_conversion_assumed':False,'reused_metadata_source_run':40709936368,'source_rows':producer['rows'],'native_h1_requests':producer['request_counts'].get('H1',0),'metadata_requests':producer['request_counts'].get('panel',0),'models_executed':int(actual is not None),'conditional_cost_scenarios':int(actual is not None),'causal_forecasts':len(actual['decisions']) if actual is not None else 0,'causal_proposals':len(actual['proposals']) if actual is not None else 0,'account_fault':actual['fault'] if actual is not None else None,'source_sha256':producer['cipher_sha256'],'private_sha256':bytes_digest(private_result),'cipher_sha256':bytes_digest((OUT/'result.mxmenc').read_bytes()),'evaluator_sha256':bytes_digest(binary.read_bytes()),'native_rows_independently_redecoded':False,'new_anchor_rows_independently_redecoded':a.get('original_rows_redecoded',0),'authenticated_cached_rows':a.get('authenticated_cached_rows',0),'cache_input_sha256':cache_digest(),'forecasts_independently_reconciled':bool(a['admitted']),'initial_capital_eur':200,'initial_funding_count':int(actual is not None),'historical_costs_proven':False,'observed_bidask_path':False,'actual_fills_proven':False,'hard21_proven':False,'economic_edge_proven':False,'independent_confirmation':False,'protected_opened':False,'closed_configuration_reexecuted':False,'orders':0,'cloud_activated':False,'automatic_followup':False,'next_action':'CLOSE_FIXED_MODEL_NO_RETUNE' if actual is not None else 'STOP_SOURCE_PRECONDITION_NO_MODEL_NO_AUTOMATIC_RETRY'}
 (OUT/'receipt.json').write_bytes(encoded(r));print('MXM_COMMODITY_ANCHOR '+encoded(r).decode(),flush=True)

def cold():
 context();r=json.loads((OUT/'receipt.json').read_bytes());raw=decrypt(OUT/'result.mxmenc');p=json.loads(raw)
 need(bytes_digest(raw)==r['private_sha256'] and bytes_digest((OUT/'result.mxmenc').read_bytes())==r['cipher_sha256'] and p['source_sha']==r['source_sha'] and p['spec_sha256']==r['spec_sha256'] and p['gates']==r['gates'],'ANCHOR_ORIGINAL_COLD')
 c={'run_id':r['run_id'],'original_readback':True,'model_reexecuted':False,'cipher_sha256':r['cipher_sha256'],'orders':0};(OUT/'cold.json').write_bytes(encoded(c));print('MXM_ANCHOR_COLD '+encoded(c).decode(),flush=True)
def preserve():
 context();members=('cache-input.mxmenc','source.mxmenc','producer.json','cache.json','result.mxmenc','receipt.json','cold.json','evaluator.dll')
 with zipfile.ZipFile(OUT/'runtime-original.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name in members:z.write(OUT/name,name)
 b=(OUT/'runtime-original.zip').read_bytes();need(len(b)<2500000,'ANCHOR_ORIGINAL_BOUND')
 print('MXM_ANCHOR_BUNDLE '+encoded({'bytes':len(b),'sha256':bytes_digest(b),'members':{p:{'bytes':(OUT/p).stat().st_size,'sha256':bytes_digest((OUT/p).read_bytes())} for p in members}}).decode(),flush=True)
 for i in range(0,len(b),16384):print('MXM_ANCHOR_PART '+str(i//16384)+' '+base64.b64encode(b[i:i+16384]).decode(),flush=True)
if __name__=='__main__':
 os.umask(0o077);command=sys.argv[1:]
 if command==['admit']:admit()
 elif command==['cache']:cache()
 elif command==['collect']:collect()
 elif command==['export']:export()
 elif command==['evaluate']:evaluate()
 elif command==['cold']:cold()
 elif command==['preserve']:preserve()
 else:raise ValueError('ANCHOR_EXACT_PHASE')
