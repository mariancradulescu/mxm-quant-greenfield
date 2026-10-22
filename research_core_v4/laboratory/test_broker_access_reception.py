"""Artificial protobuf transport; no native authentication claim or secrets."""
import unittest
from unittest.mock import patch
from . import broker_access_reception as access
from .common import LabError
from m6.ctrader_proto import OpenApiMessages_pb2 as m
from m6.ctrader_proto import OpenApiModelMessages_pb2 as e
from research_core_v4 import shallow_m5_support_v2_production as auth

class Transport:
    def __init__(self,scope=e.SCOPE_VIEW):self.scope=scope;self.names=[];self.closed=False
    def connect(self):pass
    def close(self):self.closed=True
    def request(self,req,**kwargs):
        self.names.append(type(req).__name__)
        if isinstance(req,m.ProtoOAApplicationAuthReq):return m.ProtoOAApplicationAuthRes()
        if isinstance(req,m.ProtoOAGetAccountListByAccessTokenReq):
            response=m.ProtoOAGetAccountListByAccessTokenRes(permissionScope=self.scope)
            response.ctidTraderAccount.add(ctidTraderAccountId=1,isLive=True)
            return response
        if isinstance(req,m.ProtoOAAccountAuthReq):return m.ProtoOAAccountAuthRes(ctidTraderAccountId=1)
        raise AssertionError('Artificial transport received unexpected wire type')

class BrokerAccessReception(unittest.TestCase):
    def test_existing_authentication_sends_exact_three_view_requests_and_closes(self):
        transport=Transport()
        with patch.object(auth,'ACCOUNT_FINGERPRINT_SHA256',auth._fingerprint(1)):
            result=access.authenticate_only(transport,('artificial-id','artificial-secret','artificial-token'))
        self.assertEqual(tuple(transport.names),access.AUTH_TYPES);self.assertTrue(transport.closed)
        self.assertTrue(result['expected_account_fingerprint_verified']);self.assertEqual(result['historical_requests'],0)
        self.assertNotIn('account_id',result);self.assertFalse(result['research_capability_accepted'])
    def test_trade_scope_refused_before_account_authentication(self):
        transport=Transport(scope=e.SCOPE_TRADE)
        with self.assertRaises(auth.SystemicFailure):access.authenticate_only(transport,('id','secret','token'))
        self.assertEqual(tuple(transport.names),access.AUTH_TYPES[:2]);self.assertTrue(transport.closed)
    def test_historical_or_order_request_cannot_escape_authentication_guard(self):
        transport=Transport()
        def unexpected(guard,*values):guard.request(m.ProtoOAGetTickDataReq())
        with patch.object(auth,'authenticate_segment',unexpected),self.assertRaises(LabError):
            access.authenticate_only(transport,('id','secret','token'))
        self.assertEqual(transport.names,[]);self.assertTrue(transport.closed)
    def test_partial_connect_failure_still_closes_transport(self):
        transport=Transport()
        transport.connect=lambda:(_ for _ in ()).throw(TimeoutError())
        with self.assertRaises(TimeoutError):access.authenticate_only(transport,('id','secret','token'))
        self.assertTrue(transport.closed);self.assertEqual(transport.names,[])
    def test_workflow_uses_only_existing_isolated_broker_role_and_read_token(self):
        workflow=access.build_workflow('a'*40);job=workflow['jobs']['pepperstone-access']
        self.assertEqual(set(workflow['on']),{'workflow_dispatch'})
        self.assertEqual(job['permissions'],{'contents':'read'});self.assertEqual(job['environment'],'mxm-r3-pepperstone-v1')
        env=job['steps'][2]['env']
        self.assertEqual(set(env),{'GH_TOKEN','LAB_BROKER_ACCESS_SOURCE',*access.SECRET_NAMES})
        with self.assertRaises(LabError):access.build_workflow('main')

if __name__=='__main__':unittest.main()
