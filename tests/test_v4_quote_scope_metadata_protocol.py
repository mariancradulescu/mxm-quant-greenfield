"""Protocol-real, transport-fictional tests; no socket or broker."""
import unittest
from unittest.mock import patch
from m6.ctrader_proto import OpenApiMessages_pb2 as o
from research_core_v4.quote_scope_metadata_v1 import localize,FINGERPRINT,checked_request

class ProtocolProof(unittest.TestCase):
 def test_real_proto_historical_request_and_envelope_denied(self):
  class T:
   def request(self,m):raise AssertionError('unsafe request reached transport')
  from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
  for msg in [o.ProtoOAGetTickDataReq(),o.ProtoOANewOrderReq(),ProtoMessage()]:
   with self.assertRaises(PermissionError):checked_request(T(),msg)
 def transport(self,trade=False):
  class T:
   calls=[]
   def connect(self):self.calls=[]
   def close(self):pass
   def request(self,m):
    n=type(m).__name__;self.calls.append(n)
    if n=='ProtoOAApplicationAuthReq':return o.ProtoOAApplicationAuthRes()
    if n=='ProtoOAGetAccountListByAccessTokenReq':
     a=o.ProtoOAGetAccountListByAccessTokenRes(permissionScope=int(trade));a.ctidTraderAccount.add(ctidTraderAccountId=123,isLive=True);return a
    if n=='ProtoOAAccountAuthReq':return o.ProtoOAAccountAuthRes(ctidTraderAccountId=123)
    if n=='ProtoOATraderReq':
     a=o.ProtoOATraderRes(ctidTraderAccountId=123);a.trader.ctidTraderAccountId=123;a.trader.depositAssetId=1;a.trader.brokerName='Pepperstone';return a
    if n=='ProtoOAAssetListReq':
     a=o.ProtoOAAssetListRes(ctidTraderAccountId=123);a.asset.add(assetId=1,name='EUR',displayName='EUR');return a
    if n=='ProtoOASymbolsListReq':
     a=o.ProtoOASymbolsListRes(ctidTraderAccountId=123)
     for i in range(1,1577):a.symbol.add(symbolId=i,symbolName='S'+str(i),enabled=True,baseAssetId=1,quoteAssetId=2)
     return a
    if n=='ProtoOASymbolByIdReq':
     a=o.ProtoOASymbolByIdRes(ctidTraderAccountId=123)
     # Missing full metadata is represented, never silently dropped.
     return a
    raise AssertionError(n)
  return T()
 def test_all1576_no_skips_no_quotes_no_secrets(self):
  f=[{'symbol':'S'+str(i),'symbol_id':i,'asset_class':'Forex (Spot)'} for i in range(1,1577)];t=self.transport()
  with patch('m6.ctrader_capture.account_fingerprint',return_value=FINGERPRINT):
   r=localize(f,client_id='fiction-id',client_secret='fiction-secret',access_token='fiction-token',transport=t)
  self.assertEqual(len(r['rows']),1576);self.assertTrue(all(x['status']=='METADATA_INSUFFICIENT' for x in r['rows']))
  self.assertEqual(t.calls.count('ProtoOASymbolByIdReq'),1576);self.assertEqual(r['historical_requests_sent'],0)
  self.assertNotIn('fiction-secret',str(r));self.assertNotIn('fiction-token',str(r))
 def test_trade_token_denied(self):
  f=[{'symbol':'S'+str(i),'symbol_id':i,'asset_class':'Forex (Spot)'} for i in range(1,1577)];t=self.transport(True)
  with self.assertRaises(RuntimeError):localize(f,client_id='fiction-id',client_secret='fiction-secret',access_token='fiction-token',transport=t)
  self.assertEqual(t.calls,['ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq'])
