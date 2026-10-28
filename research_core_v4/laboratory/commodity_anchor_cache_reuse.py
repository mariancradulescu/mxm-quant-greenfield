"""Finite cache-first H1 commodity-anchor investigation, VIEW-only, no orders."""
import base64,gzip,hashlib,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
from decimal import Decimal as D
from .common import need,encoded,bytes_digest
ROOT=Path(__file__).resolve().parents[2];HOME=ROOT.parent if ROOT.name=='.basis-native' else ROOT
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1';NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'
PATH='.github/workflows/mxm-commodity-anchor-cache-reuse.yml';MODULE='research_core_v4.laboratory.commodity_anchor_cache_reuse';PROJECT='research_core_v4/laboratory/csharp/commodity_anchor/MxmCommodityAnchor.csproj'
SPEC='research_core_v4/laboratory/COMMODITY_ANCHOR_H1_V1.json'
SPEC_SHA='f135ebf57cee3302f70e399695ec7dff40123fed3d2c3996933b5727a016f7e1'
TRANSPORT_SHA='f4c604eddcdc1a6dd1aa90a43e42cf1e55a2666add293b3fb6517ada31e308c2'
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
 transport=json.loads((HOME/'research_core_v4/laboratory/COMMODITY_ANCHOR_CACHE_REUSE_V1.json').read_bytes())
 need(bytes_digest((HOME/'research_core_v4/laboratory/COMMODITY_ANCHOR_CACHE_REUSE_V1.json').read_bytes())==TRANSPORT_SHA,'ANCHOR_TRANSPORT_SPEC')
 own='\n'.join("TRANSPORT_SHA='FROZEN_TRANSPORT_SHA'" if x.startswith('TRANSPORT_SHA=') else x for x in Path(__file__).read_text().splitlines())+'\n'
 need(bytes_digest(own.encode())==transport['normalized_transport_sha256'] and transport['economic_spec_sha256']==SPEC_SHA,'ANCHOR_TRANSPORT_CODE')
 return s
def context():
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'ANCHOR_NATIVE_CONTEXT')
 frozen()
def workflow():
 def job(env):return {'runs-on':'ubuntu-24.04','timeout-minutes':20,'environment':env,'permissions':{'contents':'read','actions':'read'},'steps':[{'uses':CHECKOUT,'with':{'persist-credentials':False}}]}
 cache=job('mxm-r3-custody-v1');cache['if']=f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1";cache['outputs']={'clear':'${{ steps.cache.outputs.clear }}'}
 cache['steps'] += [{'name':'Admit exact finite source and model before keys','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
  {'name':'Compile shared account and independent artificial H1 policy before custody','run':INSTALL+'\ndotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_commodity_anchor -v'},
  {'name':'Authenticate existing H1 originals and prevent duplicate source acquisition','id':'cache','env':{'GH_TOKEN':'${{ github.token }}','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\npython3 -m '+MODULE+' cache'},
  {'uses':UPLOAD,'with':{'name':'anchor-cache-${{ github.run_id }}','path':'verification/commodity-anchor/cache.json\nverification/commodity-anchor/cache-input.mxmenc','if-no-files-found':'error','retention-days':90}}]
 collect=job('mxm-r3-pepperstone-v1');collect.update(needs='source-cache',**{'if':"needs.source-cache.outputs.clear == 'true'"})
 collect['steps'] += [{'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.basis-native','persist-credentials':False}},
  {'uses':DOWNLOAD,'with':{'name':'anchor-cache-${{ github.run_id }}','path':'verification/commodity-anchor'}},
  {'run':INSTALL+'\ncp research_core_v4/laboratory/commodity_anchor_cache_reuse.py .basis-native/research_core_v4/laboratory/'},
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
 return {'name':'MXM existing H1 cache reuse and missing anchor only','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{'source-cache':cache,'basis-collect':collect,'basis-evaluate':evaluate}}
def admit():
 context();need(not any(os.environ.get(k) for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','SUCCESSOR_APP_PRIVATE_KEY')),'ANCHOR_KEY_ROLES')
 head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();need(head==os.environ['GITHUB_SHA']==os.environ['GITHUB_WORKFLOW_SHA'] and json.loads((HOME/PATH).read_bytes())==workflow(),'ANCHOR_EXACT_CODE')
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'ANCHOR_OFFICIAL_HEAD')
 for ref,h in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==h,'ANCHOR_AUTHORITY')
 v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and v['workflow_runs'][0]['run_attempt']==1,'ANCHOR_ONE_ATTEMPT')
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

def cache():
 context();OUT.mkdir(parents=True,exist_ok=True)
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 proofs=[];overlap={};retained={}
 with tempfile.TemporaryDirectory() as d:
  key,fp=_private_key_from_secret(Path(d));need(fp==FP,'ANCHOR_CACHE_CUSTODY')
  for sid,b in CACHE.items():
   value,proof=load_asset(key,fp,Path(d),b);need(value['schema']=='mxm.wide.private.h1.v1' and value['identity']['sid']==sid and value['same_native_account'] is True,'ANCHOR_CACHE_ORIGINAL')
   retained[str(sid)]={'identity':value['identity'],'rows':[[int(t)*1000]+v[:4] for t,v in sorted(value['bars'].items(),key=lambda z:int(z[0])) if START<=int(t)*1000<END],'proof':proof}
   overlap[str(sid)]=len(retained[str(sid)]['rows']);proofs.append(proof)
 route=GetOnly();assets=route.json('releases/409747426')['assets'];anchor_cached=any(x['name']=='h1-7393.mxmenc' for x in assets)
 clear=all(n>=128 for n in overlap.values()) and not anchor_cached
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
 public=HOME/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
 encrypt_shard(gzip.compress(encoded({'retained':retained,'run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['GITHUB_SHA']}),mtime=0),public_key=public,output=OUT/'cache-input.mxmenc')
 r={'schema':'mxm.anchor-cache-admission.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['GITHUB_SHA'],'existing_source_overlap_rows':overlap,'anchor_asset_already_present':anchor_cached,'new_collection_admitted':clear,'new_history_symbols':[7393] if clear else [],'cache_input_sha256':bytes_digest((OUT/'cache-input.mxmenc').read_bytes()),'cache_reuse_original_provenance_not_all_independent_wire_redecode':True,'predecessor_run':40707021640,'proofs':proofs,'new_models':0,'new_broker_requests':0,'orders':0}
 (OUT/'cache.json').write_bytes(encoded(r));print('MXM_ANCHOR_CACHE '+encoded(r).decode(),flush=True)
 with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('clear='+str(clear).lower()+'\n')

def collect():
 context();need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and (ROOT/'research_core_v4/laboratory/commodity_anchor_cache_reuse.py').read_bytes()==(HOME/'research_core_v4/laboratory/commodity_anchor_cache_reuse.py').read_bytes(),'ANCHOR_PINNED_DECODER')
 need(not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'),'ANCHOR_NO_CUSTODY_IN_BROKER_PROCESS')
 OUT.mkdir(parents=True,exist_ok=True);cache=json.loads((OUT/'cache.json').read_bytes());need(cache['new_collection_admitted'] and cache['run_id']==int(os.environ['GITHUB_RUN_ID']),'ANCHOR_NO_DUPLICATION')
 from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector
 from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m
 from google.protobuf.json_format import MessageToDict
 names={1:'EURUSD',250:'SpotCrude',7393:'WTOIL-PERP'}
 from datetime import datetime,timezone
 p={'contact_start_utc':datetime.now(timezone.utc).isoformat(),'schema':'mxm.anchor-native-source.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'spec_sha256':SPEC_SHA,'complete':False,'metadata':[],'history':[],'failure_class':None,'cache':cache}
 class Panel(Collector):
  def send(self,req,historical=False):
   name=type(req).__name__
   if name in ('ProtoOAAssetListReq','ProtoOASymbolsListReq','ProtoOASymbolByIdReq','ProtoOAExpectedMarginReq'):
    need(self.counts['panel']<4 and req.ctidTraderAccountId==self.aid,'ANCHOR_PANEL_CAP');self.counts['panel']+=1;self.nrate.before_send();res=self.tr.request(req,timeout=30)
    need(not isinstance(res,m.ProtoOAErrorRes) and int(res.ctidTraderAccountId)==self.aid,'ANCHOR_PANEL_RESPONSE')
    p['metadata'].append({'type':name,'request_b64':base64.b64encode(req.SerializeToString()).decode(),'response_b64':base64.b64encode(res.SerializeToString()).decode()});return res
   return super().send(req,historical)
 col=Panel({'H1':3,'M5':0,'BID_ASK':0,'NONHISTORY':0})
 for a,b in [('R3_CTRADER_CLIENT_ID','CTRADER_CLIENT_ID'),('R3_CTRADER_CLIENT_SECRET','CTRADER_CLIENT_SECRET'),('R3_CTRADER_ACCESS_TOKEN','CTRADER_ACCESS_TOKEN')]:os.environ[b]=os.environ[a]
 try:
  col.connect();p['account']=col.aid
  assets={int(x.assetId):x.name for x in col.send(m.ProtoOAAssetListReq(ctidTraderAccountId=col.aid)).asset}
  res=col.send(m.ProtoOASymbolsListReq(ctidTraderAccountId=col.aid,includeArchivedSymbols=True));lights={int(x.symbolId):x for x in list(res.symbol)+list(res.archivedSymbol)}
  req=m.ProtoOASymbolByIdReq(ctidTraderAccountId=col.aid);req.symbolId.extend(sorted(names));res=col.send(req);full={int(x.symbolId):x for x in res.symbol}
  need(set(full)==set(names) and all(s in lights and lights[s].symbolName==n and assets[int(lights[s].quoteAssetId)]=='USD' for s,n in names.items() if s!=1),'ANCHOR_EXACT_USD_IDENTITIES')
  need(lights[1].symbolName=='EURUSD' and assets[int(lights[1].baseAssetId)]=='EUR' and assets[int(lights[1].quoteAssetId)]=='USD','ANCHOR_FX_IDENTITY')
  trade=full[250];need(lights[250].enabled and trade.HasField('tradingMode') and trade.tradingMode==0 and trade.HasField('enableShortSelling') and trade.enableShortSelling,'ANCHOR_TARGET_CURRENT_STATUS')
  required=('minVolume','stepVolume','maxVolume','lotSize','commissionType','preciseTradingCommissionRate','preciseMinCommission','pnlConversionFeeRate')
  need(all(trade.HasField(x) for x in required) and trade.minVolume>0 and trade.stepVolume>0 and trade.minVolume%trade.stepVolume==0 and trade.commissionType==2 and trade.preciseMinCommission==0,'ANCHOR_DECLARED_COST_VOLUME')
  req=m.ProtoOAExpectedMarginReq(ctidTraderAccountId=col.aid,symbolId=250);req.volume.append(trade.minVolume);mr=col.send(req)
  need(mr.HasField('moneyDigits') and len(mr.margin)==1 and mr.margin[0].volume==trade.minVolume and mr.margin[0].HasField('buyMargin') and mr.margin[0].HasField('sellMargin'),'ANCHOR_MARGIN_PRESENT')
  margin=max(mr.margin[0].buyMargin,mr.margin[0].sellMargin)/10**int(mr.moneyDigits)
  need(0<margin<=80 and 200-margin>=120,'ANCHOR_NECESSARY_CAPITAL_ONLY')
  p['terms']={'units':trade.minVolume/100,'step_units':trade.stepVolume/100,'max_units':trade.maxVolume/100,'margin_eur':margin,'fee_usd':float(D(trade.minVolume)*D(trade.preciseTradingCommissionRate)/D(100000000)/D(trade.lotSize)),'pnl_rate':trade.pnlConversionFeeRate/10000}
  p['panel']={str(s):MessageToDict(x,preserving_proto_field_name=True,use_integers_for_enums=True) for s,x in full.items()}
  for sid in (7393,):
   rows,receipts,state=col.h1(sid,int(full[sid].digits),START//1000,END//1000)
   p['history'].append({'sid':sid,'rows':[[int(t)*1000]+v[:4] for t,v in sorted(rows.items())],'receipts':receipts,'state':state})
  p['complete']=all(x['state']=='COMPLETE_EXACT_WINDOW' and len(x['rows'])>=128 and all(z[0]%3600000==0 and START<=z[0]<END for z in x['rows']) for x in p['history'])
 except Exception as e:
  p['failure_class']=type(e).__name__;message=str(e)
  p['failure_code']=message if message.startswith('LAB_ANCHOR_') and len(message)<160 and all(c.isupper() or c=='_' or c.isdigit() for c in message) else type(e).__name__
 finally:
  col.close();p['contact_end_utc']=datetime.now(timezone.utc).isoformat()
 p['wire_counts']=dict(col.wire_types);p['request_counts']=dict(col.counts);raw=encoded(p);private(raw)
 r={'schema':'mxm.anchor-producer.v1','run_id':p['run_id'],'source_sha':p['source_sha'],'spec_sha256':SPEC_SHA,'complete':p['complete'],'failure_class':p['failure_class'],'failure_code':p.get('failure_code'),'private_sha256':bytes_digest(raw),'cipher_sha256':bytes_digest((OUT/'source.mxmenc').read_bytes()),'request_counts':p['request_counts'],'rows':{str(x['sid']):len(x['rows']) for x in p['history']},'contact_start_utc':p['contact_start_utc'],'contact_end_utc':p['contact_end_utc'],'new_models':0,'orders':0}
 (OUT/'producer.json').write_bytes(encoded(r));print('MXM_ANCHOR_PRODUCER '+encoded(r).decode(),flush=True)

def export():
 context();r=json.loads((OUT/'producer.json').read_bytes());cipher=(OUT/'source.mxmenc').read_bytes();need(bytes_digest(cipher)==r['cipher_sha256'],'ANCHOR_SOURCE_CIPHER')
 raw=decrypt(OUT/'source.mxmenc');need(bytes_digest(raw)==r['private_sha256'],'ANCHOR_SOURCE_PLAIN');p=json.loads(raw)
 need(p['source_sha']==os.environ['GITHUB_SHA'] and p['spec_sha256']==SPEC_SHA and p['run_id']==int(os.environ['GITHUB_RUN_ID']),'ANCHOR_SOURCE_IDENTITY')
 cache=json.loads((OUT/'cache.json').read_bytes());need(bytes_digest((OUT/'cache-input.mxmenc').read_bytes())==cache['cache_input_sha256'],'ANCHOR_CACHE_HANDOFF')
 reused=json.loads(decrypt(OUT/'cache-input.mxmenc'));need(reused['run_id']==int(os.environ['GITHUB_RUN_ID']) and reused['source_sha']==os.environ['GITHUB_SHA'],'ANCHOR_CACHE_HANDOFF_SCOPE')
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
 r={'schema':'mxm.commodity-anchor-public.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'spec_sha256':SPEC_SHA,'disposition':verdict,'gates':gates,'source_rows':producer['rows'],'native_h1_requests':producer['request_counts'].get('H1',0),'metadata_requests':producer['request_counts'].get('panel',0),'models_executed':int(actual is not None),'conditional_cost_scenarios':int(actual is not None),'causal_forecasts':len(actual['decisions']) if actual is not None else 0,'causal_proposals':len(actual['proposals']) if actual is not None else 0,'account_fault':actual['fault'] if actual is not None else None,'source_sha256':producer['cipher_sha256'],'private_sha256':bytes_digest(private_result),'cipher_sha256':bytes_digest((OUT/'result.mxmenc').read_bytes()),'evaluator_sha256':bytes_digest(binary.read_bytes()),'native_rows_independently_redecoded':False,'new_anchor_rows_independently_redecoded':a.get('original_rows_redecoded',0),'authenticated_cached_rows':a.get('authenticated_cached_rows',0),'cache_input_sha256':cache_digest(),'forecasts_independently_reconciled':bool(a['admitted']),'initial_capital_eur':200,'initial_funding_count':int(actual is not None),'historical_costs_proven':False,'observed_bidask_path':False,'actual_fills_proven':False,'hard21_proven':False,'economic_edge_proven':False,'independent_confirmation':False,'protected_opened':False,'closed_configuration_reexecuted':False,'orders':0,'cloud_activated':False,'automatic_followup':False,'next_action':'CLOSE_FIXED_MODEL_NO_RETUNE' if actual is not None else 'STOP_SOURCE_PRECONDITION_NO_MODEL_NO_AUTOMATIC_RETRY'}
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
