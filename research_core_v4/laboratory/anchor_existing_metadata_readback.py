"""Read existing encrypted three-response metadata capture, never acquire or model."""
import base64,hashlib,json,os,subprocess,tempfile,zipfile
from pathlib import Path
from .common import need,encoded,bytes_digest
from .verify_commodity_anchor_original import verify,DIR,ROOT
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-anchor-existing-metadata-readback-v2.yml';MODULE='research_core_v4.laboratory.anchor_existing_metadata_readback'
def workflow():
 return {'name':'MXM existing metadata typed readback recovery only','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{'original-readback':{'if':"github.repository == '"+REPO+"' && github.ref == 'refs/heads/"+BRANCH+"' && github.run_attempt == 1",'runs-on':'ubuntu-24.04','timeout-minutes':10,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[{'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','with':{'persist-credentials':False}},{'name':'Verify exact originals and single readback route before custody','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},{'run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'},{'name':'Read only public symbol identity facts from existing encrypted metadata','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\npython3 -m '+MODULE+' readback'},{'uses':'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02','with':{'name':'anchor-original-identity-${{ github.run_id }}','path':'verification/commodity-identity/readback.json','if-no-files-found':'error','retention-days':90}}]}}}
def admit():
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'ANCHOR_READBACK_CONTEXT')
 need(not any(os.environ.get(x) for x in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','CTRADER_ACCESS_TOKEN','R3_CTRADER_ACCESS_TOKEN','SUCCESSOR_APP_PRIVATE_KEY')),'ANCHOR_READBACK_NO_KEYS')
 need(json.loads((ROOT/PATH).read_bytes())==workflow(),'ANCHOR_READBACK_EXACT_WORKFLOW');verify()
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
 need(head==os.environ['GITHUB_SHA']==os.environ['GITHUB_WORKFLOW_SHA']==route.json('git/ref/heads/'+BRANCH)['object']['sha'],'ANCHOR_READBACK_HEAD')
 for ref,sha in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==sha,'ANCHOR_READBACK_AUTHORITY')
 old=route.json('actions/runs/40711949846/jobs')['jobs']
 need(len(old)==1 and old[0]['conclusion']=='failure' and any(x['name']=='Read only public symbol identity facts from existing encrypted metadata' and x['conclusion']=='failure' for x in old[0]['steps']) and route.json('actions/runs/40711949846/artifacts')['total_count']==0,'ANCHOR_READBACK_FAILED_WITHOUT_PUBLICATION')
 v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']),'ANCHOR_READBACK_ONCE')
def project_symbol(sid,assets,active,archived,full):
 x=active.get(sid) if sid in active else archived.get(sid);f=full.get(sid)
 def field(name):
  return getattr(x,name) if x is not None and name in x.DESCRIPTOR.fields_by_name and x.HasField(name) else None
 name=field('symbolName') if sid in active else field('name')
 fields=('minVolume','stepVolume','maxVolume','lotSize','commissionType','preciseTradingCommissionRate','preciseMinCommission','pnlConversionFeeRate','tradingMode','enableShortSelling')
 declared={k:int(getattr(f,k)) if f is not None and k in f.DESCRIPTOR.fields_by_name and f.HasField(k) else None for k in fields}
 return {'symbol_id':sid,'light_present':x is not None,'archived':sid not in active and sid in archived,'name':name,'base':assets.get(field('baseAssetId')),'quote':assets.get(field('quoteAssetId')),'enabled':field('enabled'),'full_present':f is not None,'digits':int(f.digits) if f is not None else None,'contemporary_declared_terms_not_historical_costs':declared}
def readback():
 need(not any(os.environ.get(x) for x in ('CTRADER_ACCESS_TOKEN','R3_CTRADER_ACCESS_TOKEN','SUCCESSOR_APP_PRIVATE_KEY')),'ANCHOR_READBACK_NO_BROKER_OR_APP')
 verify()
 from .commodity_anchor_cache_reuse import decrypt
 from m6.ctrader_proto import OpenApiMessages_pb2 as m
 with tempfile.TemporaryDirectory() as tmp:
  f=Path(tmp)/'source.mxmenc'
  with zipfile.ZipFile(DIR/'runtime-original.zip') as z:f.write_bytes(z.read('source.mxmenc'))
  raw=decrypt(f);p=json.loads(raw);receipt=json.loads((DIR/'logged-receipt.json').read_bytes())
  with zipfile.ZipFile(DIR/'runtime-original.zip') as z:producer=json.loads(z.read('producer.json'))
  need(bytes_digest(raw)==producer['private_sha256'] and p['run_id']==40709936368 and p['source_sha']==receipt['source_sha'] and len(p['metadata'])==3 and p['history']==[],'ANCHOR_READBACK_SOURCE')
  classes={'ProtoOAAssetListReq':m.ProtoOAAssetListRes,'ProtoOASymbolsListReq':m.ProtoOASymbolsListRes,'ProtoOASymbolByIdReq':m.ProtoOASymbolByIdRes}
  values={}
  for x in p['metadata']:
   cls=classes[x['type']];res=cls.FromString(base64.b64decode(x['response_b64'],validate=True));need(res.IsInitialized() and res.ctidTraderAccountId==p['account'],'ANCHOR_READBACK_SCOPE');values[x['type']]=res
  assets={int(x.assetId):x.name for x in values['ProtoOAAssetListReq'].asset}
  catalogue=values['ProtoOASymbolsListReq'];active={int(x.symbolId):x for x in catalogue.symbol};archived={int(x.symbolId):x for x in catalogue.archivedSymbol}
  full={int(x.symbolId):x for x in values['ProtoOASymbolByIdReq'].symbol}
  def project(sid):return project_symbol(sid,assets,active,archived,full)
  requested=[project(s) for s in (1,250,7393)]
  oil=sorted(s for s in set(active)|set(archived) if any(v in (project(s)['name'] or '').upper() for v in ('CRUDE','WTI','OIL','BRENT')))[:16]
  same=all(project(s)['full_present'] and project(s)['name']==name and project(s)['quote']=='USD' for s,name in [(250,'SpotCrude'),(7393,'WTOIL-PERP')])
  output={'schema':'mxm.original-commodity-identity-readback.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_run':40709936368,'source_sha256':receipt['source_sha256'],'source_private_sha256_verified':True,'captured_request_count':3,'requested_full_ids':sorted(full),'full_ids_exact':set(full)=={1,250,7393},'requested_identity_and_usd_check':same,'requested':requested,'oil_named_catalogue_facts_not_candidates': [project(s) for s in oil],'catalogue_is_contemporary_not_historical':True,'price_or_outcome_exposed':False,'new_broker_requests':0,'new_history_requests':0,'new_models':0,'funding_count':0,'orders':0,'cloud_activated':False,'automatic_followup':False}
 out=ROOT/'verification/commodity-identity';out.mkdir(parents=True,exist_ok=True);(out/'readback.json').write_bytes(encoded(output));print('MXM_ANCHOR_IDENTITY '+encoded(output).decode(),flush=True)
if __name__=='__main__':
 import sys
 if sys.argv[1:]==['admit']:admit()
 elif sys.argv[1:]==['readback']:readback()
 else:raise ValueError('ANCHOR_READBACK_ARGUMENT')
