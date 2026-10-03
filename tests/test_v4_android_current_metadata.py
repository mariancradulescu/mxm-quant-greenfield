"""Offline safety and complete1576 round trip. No real broker/OAuth execution."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from research_core_v4.quote_metadata_android_v1 import (
 Secrets,MetadataTransport,canonical,sha,load_frontier,verify_package,verify_runtime,sanitize,publish_return,
 EXPECTED_IDENTITY_SHA,EXPECTED_LOCALIZER_SHA,OUTPUT_NAME,STATUSES,
)
from research_core_v4.pydroid_quote_metadata_launcher_v1 import run_device,main
from research_core_v4.quote_scope_metadata_v1 import FINGERPRINT,localize
from m6.ctrader_proto import OpenApiMessages_pb2 as o
from m6 import pydroid_oauth
from tools.build_v4_current_metadata_android_package import build

ROOT=Path(__file__).resolve().parents[1]
FRONT=load_frontier(ROOT)
WHEELS=ROOT.parent/'metadata-wheels'
PRIVATE_ID='fiction-client-long-UUID-a3d9f115'
PRIVATE_SECRET='fiction-secret-long-212c61df-ONLY-PRIVATE'
PRIVATE_TOKEN='fiction-access-long-319aac79-ONLY-PRIVATE'
PRIVATE_REFRESH='fiction-refresh-long-ace63217-ONLY-PRIVATE'
PRIVATE_CODE='fiction-code-long-98214cab-ONLY-PRIVATE'
FAKE_AID=876543210

class FakeOAuth:
 APP_CONFIG_PATH='APP';TOKEN_STATE_PATH='TOKEN';ACCOUNT_SELECTION_PATH='ACCOUNT'
 def __init__(self,mode='REUSED_SAVED_ACCESS_TOKEN',saved=FAKE_AID):
  self.mode=mode;self.saved=saved;self.ensure_calls=0;self.fresh_calls=0;self.selector_calls=0
  self._token_request=lambda params:{'accessToken':PRIVATE_TOKEN,'refreshToken':PRIVATE_REFRESH}
 def _load_json(self,path):
  return {'APP':{'client_id':PRIVATE_ID,'client_secret':PRIVATE_SECRET,'scope':'accounts'},
   'TOKEN':{'access_token':PRIVATE_TOKEN,'refresh_token':PRIVATE_REFRESH},
   'ACCOUNT':{'ctid_trader_account_id':self.saved}}[path]
 def ensure_v2_authorization(self):
  self.ensure_calls+=1
  if self.mode=='FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION':self._token_request({'code':PRIVATE_CODE,'client_secret':PRIVATE_SECRET})
  return self._load_json('APP'),PRIVATE_TOKEN,self.mode
 def force_fresh_v2_authorization(self):
  self.fresh_calls+=1;self._token_request({'code':PRIVATE_CODE,'client_secret':PRIVATE_SECRET})
  return self._load_json('APP'),PRIVATE_TOKEN,'FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION_FORCED'
 def load_saved_account_id(self):return self.saved
 def choose_live_account_locally(self,candidates):self.selector_calls+=1;self.saved=FAKE_AID;return self.saved

class FakeTransport:
 def __init__(self,trade=False,multiple=False,unavailable=False,token_bad=False,timeout=False):
  self.trade=trade;self.multiple=multiple;self.unavailable=unavailable;self.token_bad=token_bad;self.timeout=timeout
  self.calls=[];self.connections=0;self._once=False
 def connect(self):self.connections+=1
 def close(self):pass
 def request(self,m):
  n=type(m).__name__;self.calls.append(n)
  if n=='ProtoOAApplicationAuthReq':return o.ProtoOAApplicationAuthRes()
  if n=='ProtoOAGetAccountListByAccessTokenReq':
   if self.token_bad:return o.ProtoOAErrorRes(errorCode='ACCESS_TOKEN_INVALID')
   a=o.ProtoOAGetAccountListByAccessTokenRes(permissionScope=int(self.trade),accessToken=PRIVATE_TOKEN);a.ctidTraderAccount.add(ctidTraderAccountId=FAKE_AID,isLive=True)
   if self.multiple:a.ctidTraderAccount.add(ctidTraderAccountId=123456789,isLive=True)
   return a
  if n=='ProtoOAAccountAuthReq':return o.ProtoOAAccountAuthRes(ctidTraderAccountId=FAKE_AID)
  if n=='ProtoOATraderReq':
   a=o.ProtoOATraderRes(ctidTraderAccountId=FAKE_AID);a.trader.ctidTraderAccountId=FAKE_AID;a.trader.depositAssetId=1;a.trader.brokerName='Pepperstone';a.trader.balance=999999
   return a
  if n=='ProtoOAAssetListReq':
   a=o.ProtoOAAssetListRes(ctidTraderAccountId=FAKE_AID);a.asset.add(assetId=1,name='EUR',displayName='EUR');return a
  if n=='ProtoOASymbolsListReq':
   a=o.ProtoOASymbolsListRes(ctidTraderAccountId=FAKE_AID)
   for row in FRONT:a.symbol.add(symbolId=row['symbol_id'],symbolName=row['symbol'],enabled=True,baseAssetId=1,quoteAssetId=2)
   return a
  if n=='ProtoOASymbolByIdReq':
   if self.timeout and not self._once:self._once=True;raise TimeoutError('private exception '+PRIVATE_TOKEN)
   if self.unavailable:return o.ProtoOAErrorRes(ctidTraderAccountId=FAKE_AID,errorCode='SYMBOL_NOT_FOUND',description=PRIVATE_SECRET)
   sid=int(m.symbolId[0]);a=o.ProtoOASymbolByIdRes(ctidTraderAccountId=FAKE_AID)
   f=a.symbol.add(symbolId=sid,digits=5,pipPosition=4,enableShortSelling=True,minVolume=100,stepVolume=100,maxVolume=100000,lotSize=100,tradingMode=1 if sid%4==0 else 0,commission=0,commissionType=1,minCommission=0,minCommissionType=1,minCommissionAsset='USD',pnlConversionFeeRate=0,scheduleTimeZone='UTC')
   f.schedule.add(startSecond=86400,endSecond=172800)
   if sid%4!=1:f.preciseTradingCommissionRate=0
   else:f.ClearField('commissionType')
   return a
  if n=='ProtoOAExpectedMarginReq':
   a=o.ProtoOAExpectedMarginRes(ctidTraderAccountId=FAKE_AID,moneyDigits=2)
   a.margin.add(volume=m.volume[0],buyMargin=20000 if int(m.symbolId)%4==2 else 500,sellMargin=600)
   return a
  raise AssertionError('forbidden call reached fake transport '+n)

class AndroidProof(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.package=Path(cls.temp.name)/'package.zip'
  build(ROOT,cls.package,wheel_dir=WHEELS,source_head='OFFLINE_TEST_ONLY')
  with zipfile.ZipFile(cls.package) as z:z.extractall(cls.temp.name)
  cls.bundle=Path(cls.temp.name)/'MXM_V4_CURRENT_METADATA_ANDROID_V1'
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def fake_wrapper(self,inner=None,oauth=None):
  return MetadataTransport(inner or FakeTransport(),oauth or FakeOAuth(),Secrets(),progress=lambda x:None,sleep=lambda x:None,clock=lambda:1.)
 def result(self,inner=None):
  tr=self.fake_wrapper(inner)
  with patch('m6.ctrader_capture.account_fingerprint',side_effect=lambda n:FINGERPRINT if int(n)==FAKE_AID else 'other'):
   r=localize(FRONT,client_id=PRIVATE_ID,client_secret=PRIVATE_SECRET,access_token=PRIVATE_TOKEN,transport=tr)
  r['asset_metadata']=tr.asset_metadata
  return r,tr
 def test_all1576_round_trip_and_classifications(self):
  result,tr=self.result();clean=sanitize(result,FRONT)
  self.assertEqual(len(clean['rows']),1576);self.assertEqual(sum(clean['summary_counts'].values()),1576)
  self.assertEqual(set(clean['summary_counts']),STATUSES);self.assertTrue(all(clean['summary_counts'][k]>0 for k in STATUSES))
  self.assertEqual(clean['frontier_identity_sha256'],EXPECTED_IDENTITY_SHA)
  self.assertEqual(sum(clean['asset_class_composition'].values()),1576)
  self.assertNotIn('balance',canonical(clean).decode());self.assertNotIn(str(FAKE_AID),canonical(clean).decode())
  self.assertEqual(tr.request_counts['ProtoOASymbolByIdReq'],1576)
 def test_all_forbidden_real_protos_and_envelope_rejected(self):
  tr=self.fake_wrapper()
  from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
  messages=[o.ProtoOAGetTickDataReq(),o.ProtoOAGetTrendbarsReq(),o.ProtoOASubscribeSpotsReq(),o.ProtoOANewOrderReq(),o.ProtoOACancelOrderReq(),o.ProtoOAAmendOrderReq(),o.ProtoOAClosePositionReq(),o.ProtoOAAmendPositionSLTPReq(),ProtoMessage()]
  for msg in messages:
   with self.assertRaises(PermissionError):tr.request(msg)
  self.assertEqual(tr._inner.calls,[])
 def test_allowlisted_type_payload_override_rejected(self):
  tr=self.fake_wrapper();m=o.ProtoOATraderReq(ctidTraderAccountId=FAKE_AID,payloadType=o.ProtoOANewOrderReq().payloadType)
  with self.assertRaises(PermissionError):tr.request(m)
  self.assertEqual(tr._inner.calls,[])
 def test_wrong_proto_response_and_account_rejected(self):
  for response in [o.ProtoOAApplicationAuthRes(),o.ProtoOATraderRes(ctidTraderAccountId=123)]:
   class Inner:
    def request(self,m):return response
   tr=self.fake_wrapper(Inner())
   with self.assertRaises(PermissionError):tr.request(o.ProtoOATraderReq(ctidTraderAccountId=FAKE_AID))
 def test_scope_trade_denied_before_account_auth(self):
  inner=FakeTransport(trade=True);tr=self.fake_wrapper(inner)
  with self.assertRaises(PermissionError):tr.request(o.ProtoOAGetAccountListByAccessTokenReq(accessToken=PRIVATE_TOKEN))
  self.assertEqual(inner.calls,['ProtoOAGetAccountListByAccessTokenReq'])
 def test_wrong_bound_account_denied(self):
  tr=self.fake_wrapper()
  with patch('m6.ctrader_capture.account_fingerprint',return_value='wrong'):
   with self.assertRaises(PermissionError):tr.request(o.ProtoOAGetAccountListByAccessTokenReq(accessToken=PRIVATE_TOKEN))
 def test_multiple_accounts_existing_private_selector_only_when_needed(self):
  for saved,expected in [(None,1),(FAKE_AID,0)]:
   oauth=FakeOAuth(saved=saved);tr=self.fake_wrapper(FakeTransport(multiple=True),oauth)
   with patch('m6.ctrader_capture.account_fingerprint',side_effect=lambda n:FINGERPRINT if int(n)==FAKE_AID else 'other'):
    tr.request(o.ProtoOAGetAccountListByAccessTokenReq(accessToken=PRIVATE_TOKEN))
   self.assertEqual(oauth.selector_calls,expected)
 def test_per_symbol_metadata_rejection_all_unresolved_no_omissions(self):
  r,tr=self.result(FakeTransport(unavailable=True));c=sanitize(r,FRONT)
  self.assertEqual(c['summary_counts']['METADATA_INSUFFICIENT'],1576)
  self.assertNotIn(PRIVATE_SECRET,canonical(c).decode())
 def test_reconnect_reauth_only_readonly(self):
  inner=FakeTransport(timeout=True);tr=self.fake_wrapper(inner)
  with patch('m6.ctrader_capture.account_fingerprint',side_effect=lambda n:FINGERPRINT if int(n)==FAKE_AID else 'other'):
   r=localize(FRONT,client_id=PRIVATE_ID,client_secret=PRIVATE_SECRET,access_token=PRIVATE_TOKEN,transport=tr)
  self.assertEqual(len(r['rows']),1576);self.assertEqual(inner.connections,2)
  self.assertEqual(tr.request_counts['ProtoOAApplicationAuthReq'],2)
  self.assertEqual(tr.request_counts['ProtoOAAccountAuthReq'],2)
 def test_duplicate_missing_additional_output_identity_rejected(self):
  r,tr=self.result()
  for mutation in ['duplicate','missing','extra']:
   d=copy.deepcopy(r)
   if mutation=='duplicate':d['rows'][-1]=d['rows'][0]
   if mutation=='missing':d['rows'].pop()
   if mutation=='extra':d['rows'].append(dict(d['rows'][0],symbol_id=999999999))
   with self.assertRaises(ValueError):sanitize(d,FRONT)
 def test_all_sensitive_key_variants_rejected(self):
  r,tr=self.result()
  for key in ['client_id','clientSecret','accessToken','refresh_token','authorization_code','ctidTraderAccountId','balance']:
   d=copy.deepcopy(r);d['rows'][0][key]='private'
   with self.assertRaises(PermissionError):sanitize(d,FRONT)
 def test_authentication_URL_rejected(self):
  r,tr=self.result();r['rows'][0]['current_full_metadata']['scheduleTimeZone']='https://example.invalid/?code=PRIVATE'
  with self.assertRaises(PermissionError):sanitize(r,FRONT)
 def test_known_secrets_and_escaped_forms_rejected(self):
  import urllib.parse
  sec=Secrets();secret='fiction-private-\"quoted\" token/a';sec.add(secret)
  for encoded in [secret,json.dumps(secret)[1:-1],urllib.parse.quote(secret,safe=''),urllib.parse.quote_plus(secret,safe='')]:
   with self.assertRaises(PermissionError):sec.scan(encoded.encode())
 def test_exact_return_zip_checksums_no_private_material(self):
  r,tr=self.result();sec=Secrets()
  for value in [PRIVATE_ID,PRIVATE_SECRET,PRIVATE_TOKEN,PRIVATE_REFRESH,PRIVATE_CODE,str(FAKE_AID)]:sec.add(value)
  with tempfile.TemporaryDirectory() as d:
   out=publish_return(r,FRONT,self.bundle,d,sec,[tr],verify_package(self.bundle))
   self.assertEqual(out.name,OUTPUT_NAME)
   with zipfile.ZipFile(out) as z:
    self.assertEqual(set(z.namelist()),{'CURRENT_METADATA_LOCALIZATION.json','FRONTIER_IDENTITIES.json','EXECUTION_MANIFEST.json','CHECKSUMS.sha256'})
    for line in z.read('CHECKSUMS.sha256').decode().splitlines():
     h,name=line.split('  ',1);self.assertEqual(sha(z.read(name)),h)
    for name in z.namelist():sec.scan(z.read(name))
    self.assertFalse(json.loads(z.read('EXECUTION_MANIFEST.json'))['responses_computed'])
 def test_secret_under_allowed_value_rejects_zip_without_partial(self):
  r,tr=self.result();r['rows'][0]['reason']=PRIVATE_SECRET;sec=Secrets();sec.add(PRIVATE_SECRET)
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(PermissionError):publish_return(r,FRONT,self.bundle,d,sec,[tr],verify_package(self.bundle))
   self.assertEqual(list(Path(d).iterdir()),[])
 def test_package_tamper_and_wrong_frontier_fail_before_oauth(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'copy';shutil.copytree(self.bundle,root)
   file=root/'research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json';file.write_text('[]')
   oauth=FakeOAuth()
   with self.assertRaises(ValueError):run_device(root,oauth=oauth,transport_factory=lambda:(_ for _ in ()).throw(AssertionError('broker')),progress=lambda x:None)
   self.assertEqual(oauth.ensure_calls,0)
 def test_duplicate_frontier_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=root/'research_core_v4/state';f.mkdir(parents=True);v=copy.deepcopy(FRONT);v[-1]=v[0]
   (f/'QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json').write_bytes(canonical(v))
   with self.assertRaises(ValueError):load_frontier(root)
 def test_single_launcher_full_output_and_fresh_transient_code_scanned(self):
  oauth=FakeOAuth(mode='FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION');transports=[]
  def factory():
   t=FakeTransport();transports.append(t);return t
  with tempfile.TemporaryDirectory() as d,patch('m6.ctrader_capture.account_fingerprint',side_effect=lambda n:FINGERPRINT if int(n)==FAKE_AID else 'other'),patch('research_core_v4.pydroid_quote_metadata_launcher_v1.MetadataTransport',side_effect=lambda inner,oa,sec,**kw:MetadataTransport(inner,oa,sec,**kw,sleep=lambda x:None,clock=lambda:1.)):
   out=run_device(self.bundle,oauth=oauth,transport_factory=factory,progress=lambda x:None,output_dir=d)
   self.assertTrue(out.is_file());self.assertEqual(oauth.ensure_calls,1);self.assertEqual(oauth.fresh_calls,0)
   with zipfile.ZipFile(out) as z:self.assertNotIn(PRIVATE_CODE,b''.join(z.read(n) for n in z.namelist()).decode())
 def test_stale_cached_grant_one_fresh_round_no_second_run(self):
  oauth=FakeOAuth();transports=[]
  def factory():
   t=FakeTransport(token_bad=not transports);transports.append(t);return t
  with tempfile.TemporaryDirectory() as d,patch('m6.ctrader_capture.account_fingerprint',side_effect=lambda n:FINGERPRINT if int(n)==FAKE_AID else 'other'),patch('research_core_v4.pydroid_quote_metadata_launcher_v1.MetadataTransport',side_effect=lambda inner,oa,sec,**kw:MetadataTransport(inner,oa,sec,**kw,sleep=lambda x:None,clock=lambda:1.)):
   out=run_device(self.bundle,oauth=oauth,transport_factory=factory,progress=lambda x:None,output_dir=d)
   self.assertTrue(out.is_file());self.assertEqual(oauth.fresh_calls,1)
 def test_transport_exception_details_never_printed(self):
  with patch('research_core_v4.pydroid_quote_metadata_launcher_v1.run_device',side_effect=RuntimeError(PRIVATE_SECRET+' https://invalid/?code='+PRIVATE_CODE)),patch('sys.stdout',new_callable=io.StringIO) as out:
   self.assertEqual(main(self.bundle),1);self.assertNotIn(PRIVATE_SECRET,out.getvalue());self.assertNotIn(PRIVATE_CODE,out.getvalue())
 def test_bundled_vendor_preflight_is_offline(self):
  code='import sys, pathlib, socket; r=pathlib.Path(sys.argv[1]); sys.path[:0]=[str(r/"vendor"),str(r)]; socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(AssertionError("network")); from research_core_v4.quote_metadata_android_v1 import verify_package,verify_runtime; verify_package(r); verify_runtime(r); import google.protobuf,tzdata; assert google.protobuf.__version__=="5.29.5"; assert tzdata.__version__=="2026.5"; from zoneinfo import ZoneInfo,reset_tzpath; reset_tzpath([]); ZoneInfo("America/New_York"); print("offline vendor PASS")'
  result=subprocess.run(['python','-I','-c',code,str(self.bundle)],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertIn('PASS',result.stdout)
 def test_other_loaded_dependency_origin_rejected(self):
  with self.assertRaises(PermissionError):verify_runtime(self.bundle)
 def test_deterministic_deployment_zip(self):
  with tempfile.TemporaryDirectory() as d:
   a=build(ROOT,Path(d)/'a.zip',wheel_dir=WHEELS,source_head='OFFLINE_TEST_ONLY');b=build(ROOT,Path(d)/'b.zip',wheel_dir=WHEELS,source_head='OFFLINE_TEST_ONLY')
   self.assertEqual(a['sha256'],b['sha256'])
 def test_metadata_rate_limit_guard(self):
  waits=[];t=self.fake_wrapper();t._sleep=waits.append
  t.request(o.ProtoOAApplicationAuthReq(clientId=PRIVATE_ID,clientSecret=PRIVATE_SECRET));t.request(o.ProtoOAApplicationAuthReq(clientId=PRIVATE_ID,clientSecret=PRIVATE_SECRET))
  self.assertEqual(waits,[.05])
 def test_nonmetadata_result_states_rejected(self):
  r,tr=self.result()
  for key,value in [('historical_requests_sent',1),('orders_sent',1),('features_computed',True),('responses_computed',True)]:
   d=copy.deepcopy(r);d[key]=value
   with self.assertRaises(PermissionError):sanitize(d,FRONT)
 def test_role_gate_does_not_retry_permission_failure(self):
  inner=FakeTransport();tr=self.fake_wrapper(inner)
  tr._send=lambda m:(_ for _ in ()).throw(PermissionError('gate denied'))
  with self.assertRaises(PermissionError):tr.request(o.ProtoOAApplicationAuthReq(clientId=PRIVATE_ID,clientSecret=PRIVATE_SECRET))
  self.assertEqual(inner.connections,0)
 def test_actual_existing_oauth_valid_cache_no_browser(self):
  app={'client_id':PRIVATE_ID,'client_secret':PRIVATE_SECRET,'scope':'accounts'}
  state={'scope':'accounts','access_token':PRIVATE_TOKEN,'refresh_token':PRIVATE_REFRESH,'expires_at_unix':9999999999}
  with patch.object(pydroid_oauth,'_load_app_credentials',return_value=app),patch.object(pydroid_oauth,'_load_token_state',return_value=state),patch.object(pydroid_oauth,'_fresh_browser_authorization',side_effect=AssertionError('browser')):
   a,t,mode=pydroid_oauth.ensure_v2_authorization();self.assertEqual(mode,'REUSED_SAVED_ACCESS_TOKEN')
 def test_actual_existing_oauth_refresh_locally(self):
  app={'client_id':PRIVATE_ID,'client_secret':PRIVATE_SECRET,'scope':'accounts'}
  state={'access_token':PRIVATE_TOKEN,'refresh_token':PRIVATE_REFRESH,'expires_at_unix':0}
  with patch.object(pydroid_oauth,'_load_app_credentials',return_value=app),patch.object(pydroid_oauth,'_load_token_state',return_value=state),patch.object(pydroid_oauth,'_token_request',return_value={'accessToken':PRIVATE_TOKEN}),patch.object(pydroid_oauth,'_save_token_state') as saved,patch.object(pydroid_oauth,'_fresh_browser_authorization',side_effect=AssertionError('browser')):
   a,t,mode=pydroid_oauth.ensure_v2_authorization();self.assertEqual(mode,'REFRESHED_SAVED_ACCESS_TOKEN');saved.assert_called_once()
 def test_actual_existing_oauth_fresh_without_cache_deletion(self):
  with patch.object(pydroid_oauth,'_reuse_or_refresh_authorization',return_value=None),patch.object(pydroid_oauth,'_fresh_browser_authorization',return_value=({'scope':'accounts'},PRIVATE_TOKEN)) as fresh,patch('pathlib.Path.unlink',side_effect=AssertionError('cache deletion')):
   a,t,mode=pydroid_oauth.ensure_v2_authorization();fresh.assert_called_once();self.assertEqual(mode,'FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION')

if __name__=='__main__':unittest.main()
