import json,os,unittest
from . import read_only_auth_preflight_v3 as a
from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
ID=918273645
EXPECTED=a.fingerprint(ID)
SECRET='synthetic-secret-never-publish'
TOKEN='synthetic-token-never-publish'
IDENTITY={'rebound_accepted_account_fingerprint_sha256':EXPECTED,'broker_environment':'Pepperstone - Europe LIVE','broker_verified':True,'raw_account_id_persisted':False}
def run_fixture(*args):return a.run(*args,identity_authority=IDENTITY)
def accounts(ids=(ID,),scope=e.SCOPE_VIEW,live=True):
 return m.ProtoOAGetAccountListByAccessTokenRes(accessToken=TOKEN,permissionScope=scope,ctidTraderAccount=[e.ProtoOACtidTraderAccount(ctidTraderAccountId=i,isLive=live) for i in ids])
class Fake:
 def __init__(self,response=None,changes=None,error=None):self.response=response or accounts();self.changes=changes or {};self.sent=[];self.closed=False;self.error=error
 def request(self,msg,timeout=None):
  a.require_message(msg);self.sent.append(type(msg).__name__)
  if self.error:raise RuntimeError(SECRET+TOKEN+str(ID))
  if isinstance(msg,m.ProtoOAApplicationAuthReq):return m.ProtoOAApplicationAuthRes()
  if isinstance(msg,m.ProtoOAGetAccountListByAccessTokenReq):return self.response
  if isinstance(msg,m.ProtoOAAccountAuthReq):return m.ProtoOAAccountAuthRes(ctidTraderAccountId=ID)
  if isinstance(msg,m.ProtoOATraderReq):
   data={'ctidTraderAccountId':ID,'balance':0,'depositAssetId':1,'brokerName':'Pepperstone - Europe','accountType':e.HEDGED,'totalMarginCalculationType':e.MAX,'swapFree':False};data.update(self.changes);data={k:v for k,v in data.items() if v is not None}
   return m.ProtoOATraderRes(trader=e.ProtoOATrader(**data))
  if isinstance(msg,m.ProtoOAAssetListReq):return m.ProtoOAAssetListRes(ctidTraderAccountId=ID,asset=[e.ProtoOAAsset(assetId=1,name='EUR')])
  raise AssertionError('unexpected auth-only fixture request')
 def close(self):self.closed=True
class Tests(unittest.TestCase):
 def test_fingerprint_formula(self):
  import hashlib
  self.assertEqual(a.fingerprint(ID),hashlib.sha256(('ctrader-account:'+str(ID)).encode('ascii')).hexdigest())
 def test_autodiscovery_unique(self):self.assertEqual(a.autodiscover(accounts((111,ID,222)),EXPECTED),ID)
 def test_zero_match_fail_closed(self):
  with self.assertRaises(a.Rejected) as c:a.autodiscover(accounts((111,222)),EXPECTED)
  self.assertEqual(c.exception.code,'HISTORICAL_ACCOUNT_FINGERPRINT_NOT_FOUND')
 def test_multiple_match_fail_closed(self):
  with self.assertRaises(a.Rejected) as c:a.autodiscover(accounts((ID,ID)),EXPECTED)
  self.assertEqual(c.exception.code,'MULTIPLE_HISTORICAL_ACCOUNT_FINGERPRINT_MATCHES')
 def test_nonlive_rejected(self):
  with self.assertRaises(a.Rejected) as c:a.autodiscover(accounts(live=False),EXPECTED)
  self.assertEqual(c.exception.code,'MATCHED_ACCOUNT_NOT_LIVE')
 def test_trade_scope_rejected_before_accountauth(self):
  f=Fake(accounts(scope=e.SCOPE_TRADE));r=run_fixture('fixture',SECRET,TOKEN,f,EXPECTED)
  self.assertEqual(r['safe_reason'],'TOKEN_SCOPE_NOT_EXPLICIT_VIEW_ONLY');self.assertNotIn('ProtoOAAccountAuthReq',f.sent);self.assertTrue(f.closed)
 def test_missing_explicit_view_rejected(self):
  response=accounts();response.ClearField('permissionScope')
  with self.assertRaises(a.Rejected):a.autodiscover(response,EXPECTED)
 def test_success_five_messages(self):
  f=Fake();r=run_fixture('fixture',SECRET,TOKEN,f,EXPECTED)
  self.assertTrue(r['auth_proven']);self.assertTrue(all(r[k] for k in a.GATES));self.assertEqual(set(f.sent),a.ALLOWED);self.assertEqual(len(f.sent),5);self.assertTrue(f.closed);self.assertFalse(any(r[k] for k in a.FORBIDDEN_FLAGS))
 def test_disallowed_message(self):
  class Unknown:pass
  with self.assertRaises(a.Rejected):a.require_message(Unknown())
 def test_refresh_rejected(self):
  with self.assertRaises(a.Rejected):a.require_message(m.ProtoOARefreshTokenReq())
 def test_history_and_subscriptions_rejected(self):
  for n in ['ProtoOAGetTrendbarsReq','ProtoOAGetTickDataReq','ProtoOASubscribeSpotsReq','ProtoOASubscribeDepthQuotesReq']:
   with self.subTest(n=n),self.assertRaises(a.Rejected):a.require_message(getattr(m,n)())
 def test_order_and_position_mutation_rejected(self):
  for n in ['ProtoOANewOrderReq','ProtoOAClosePositionReq','ProtoOACancelOrderReq','ProtoOAAmendOrderReq','ProtoOAAmendPositionSLTPReq']:
   with self.subTest(n=n),self.assertRaises(a.Rejected):a.require_message(getattr(m,n)())
 def test_wire_whitelist_blocks_forbidden_without_connection(self):
  from m6.ctrader_transport import encode_envelope
  tr=a.make_transport()
  for msg in [m.ProtoOANewOrderReq(),m.ProtoOAGetTrendbarsReq(),m.ProtoOARefreshTokenReq()]:
   # Supply required fields only enough for serialization via empty partial frame.
   from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
   raw=ProtoMessage(payloadType=msg.payloadType,payload=msg.SerializePartialToString()).SerializeToString()
   import struct
   with self.assertRaises(a.Rejected):tr._send_bytes(struct.pack('!I',len(raw))+raw)
  with self.assertRaises(a.Rejected):tr.send_heartbeat()
  self.assertFalse(tr.connected)
 def test_safe_artifact_no_values_or_raw_identity(self):
  f=Fake();r=run_fixture('fixture',SECRET,TOKEN,f,EXPECTED);text=json.dumps(r)
  for bad in (SECRET,TOKEN,str(ID),'traderLogin','accessToken','clientSecret'):self.assertNotIn(bad,text)
  r['expected_account_fingerprint_sha256']=a.EXPECTED_FINGERPRINT;self.assertTrue(a.validate_safe(r))
  r['extra']=SECRET
  with self.assertRaises(a.Rejected):a.validate_safe(r)
 def test_exception_text_not_published(self):
  r=run_fixture('fixture',SECRET,TOKEN,Fake(error=True),EXPECTED);text=json.dumps(r)
  self.assertEqual(r['safe_reason'],'TRANSPORT_FAILURE')
  for bad in (SECRET,TOKEN,str(ID)):self.assertNotIn(bad,text)
 def test_remaining_gates_fail_closed(self):
  for changes,reason in [({'accountType':e.NETTED},'ACCOUNT_TYPE_NOT_HEDGED'),({'totalMarginCalculationType':e.SUM},'MARGIN_MODE_NOT_MAX'),({'swapFree':True},'SWAP_FREE_STATE_MISMATCH'),({'depositAssetId':2},'ACCOUNT_CURRENCY_NOT_EUR')]:
   with self.subTest(reason=reason):
    r=run_fixture('fixture',SECRET,TOKEN,Fake(changes=changes),EXPECTED);self.assertFalse(r['auth_proven']);self.assertEqual(r['safe_reason'],reason);self.assertTrue(r['transport_closed'])
 def test_broker_text_is_not_a_gate(self):
  for text in ['other','unrelated whitelabel',None]:
   with self.subTest(text=text):
    r=run_fixture('fixture',SECRET,TOKEN,Fake(changes={'brokerName':text}),EXPECTED)
    self.assertTrue(r['auth_proven']);self.assertFalse(r['broker_text_used_as_identity_or_region_gate'])
 def test_protocol_defaults_are_reported(self):
  r=run_fixture('fixture',SECRET,TOKEN,Fake(changes={'accountType':None,'totalMarginCalculationType':None,'swapFree':None}),EXPECTED)
  self.assertTrue(r['auth_proven']);self.assertFalse(r['account_type_field_explicit']);self.assertFalse(r['margin_mode_field_explicit']);self.assertFalse(r['swap_free_field_explicit'])
 def test_historical_authority_rejects_before_contact(self):
  f=Fake();bad=dict(IDENTITY);bad['broker_verified']=False
  r=a.run('fixture',SECRET,TOKEN,f,EXPECTED,identity_authority=bad)
  self.assertFalse(r['auth_proven']);self.assertEqual(r['safe_reason'],'HISTORICAL_IDENTITY_AUTHORITY_INVALID');self.assertEqual(f.sent,[])
 def test_trader_response_mismatch(self):
  r=run_fixture('fixture',SECRET,TOKEN,Fake(changes={'ctidTraderAccountId':ID+1}),EXPECTED)
  self.assertFalse(r['auth_proven']);self.assertFalse(r['trader_response_same_account_pass']);self.assertEqual(r['safe_reason'],'TRADER_REQUEST_FAILED')
 def test_presence_only_booleans_no_values(self):
  from unittest.mock import patch
  with patch.dict(os.environ,{n:SECRET for n in a.REQUIRED}|{'CTRADER_REFRESH_TOKEN':TOKEN},clear=True):r=a.presence()
  self.assertTrue(all(r['required_runtime_secret_presence'].values()));self.assertTrue(r['refresh_token_present']);self.assertFalse(r['refresh_token_used']);self.assertNotIn(TOKEN,json.dumps(r));self.assertNotIn(SECRET,json.dumps(r))
if __name__=='__main__':unittest.main()
