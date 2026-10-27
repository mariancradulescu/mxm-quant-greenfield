"""Prospective scope, secret separation and artificial native wire negatives."""
import base64,copy,json,os,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from . import spot_observation_reception as n
from .common import encoded,bytes_digest
class SpotScopeTests(unittest.TestCase):
    def test_direct_business_frames_and_second_sends_cannot_bypass_request_caps(self):
        n.outbound_guard('ProtoHeartbeatEvent',None)
        n.outbound_guard('ProtoOATraderReq',{'request_type':'ProtoOATraderReq'})
        for name,active in [('ProtoOANewOrderReq',None),('ProtoOATraderReq',None),
          ('ProtoOATraderReq',{'request_type':'ProtoOAAssetListReq'}),
          ('ProtoOATraderReq',{'request_type':'ProtoOATraderReq','client_msg_id':'already-sent'})]:
            with self.assertRaises(ValueError):n.outbound_guard(name,active)
    def test_frozen_panel_and_scope(self):
        self.assertEqual(n.POLICY['symbols'],{'1':'EURUSD','2':'GBPUSD','250':'SpotCrude'})
        self.assertEqual(n.POLICY['capture_seconds_after_subscription'],360)
        self.assertFalse(n.POLICY['automatic_retry']);self.assertFalse(n.POLICY['confirmation_eligible'])
        for k in ('orders','strategy_trials','history_requests','reconnections'):self.assertEqual(n.POLICY[k],0)
        self.assertEqual(n.POLICY_SHA,bytes_digest(encoded(n.POLICY)))
        self.assertEqual(json.loads((n.ROOT/n.PARTITION).read_bytes()),n.partition())
        for name in ('ProtoOANewOrderReq','ProtoOAAmendOrderReq','ProtoOAGetTickDataReq','ProtoOASubscribeDepthQuotesReq'):
            self.assertNotIn(name,n.ALLOWED)
    def test_wrong_context_stops_before_git_network_or_keys(self):
        with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
            with self.assertRaisesRegex(ValueError,'NATIVE_CONTEXT'):n.admission(n.ROOT)
            git.assert_not_called()
    def test_no_secrets_available_to_prekey_admission(self):
        env={'GITHUB_REPOSITORY':n.REPO,'GITHUB_REF_NAME':n.BRANCH,'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1',
          'GITHUB_JOB':'spot-collect','GITHUB_WORKFLOW_REF':n.REPO+'/'+n.PATH+'@refs/heads/'+n.BRANCH}
        for secret in (*n.BROKER,'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_REFRESH_TOKEN'):
            with patch.dict(os.environ,{**env,secret:'artificial'},clear=True),patch.object(n.subprocess,'check_output') as git:
                with self.assertRaisesRegex(ValueError,'SECRET_ROLE_SEPARATION'):n.admission(n.ROOT)
                git.assert_not_called()
    def test_generated_workflow_has_separate_roles_no_dispatch_or_write(self):
        w=n.workflow();self.assertEqual(json.loads((n.ROOT/n.PATH).read_bytes()),w)
        self.assertEqual(w['on'],{'push':{'branches':[n.BRANCH],'paths':[n.PATH]}})
        collect=w['jobs']['spot-collect'];cold=w['jobs']['spot-cold']
        self.assertEqual(cold['needs'],'spot-collect');self.assertEqual(cold['if'],'always()')
        for role,j in w['jobs'].items():
            self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
            secretsteps=[s for s in j['steps'] if any(k in s.get('env',{}) for k in (*n.BROKER,'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'))]
            self.assertEqual(len(secretsteps),1)
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(j))
            if role=='spot-collect':self.assertNotIn('PRIVATE_KEY',json.dumps(j))
            else:self.assertNotIn('R3_CTRADER_',json.dumps(j))
        self.assertEqual(collect['environment'],'mxm-r3-pepperstone-v1');self.assertEqual(cold['environment'],'mxm-r3-custody-v1')

class NativeSpotWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
            from m6.ctrader_transport import encode_envelope
            from research_core_v4 import shallow_m5_support_v2_production as auth
        except ModuleNotFoundError:
            if os.environ.get('GITHUB_ACTIONS')=='true':raise
            raise unittest.SkipTest('Native protobuf/runtime dependencies installed and required in CI')
        cls.m=m;cls.e=e;cls.encode=staticmethod(encode_envelope);cls.auth=auth
    def initialized(self,msg):
        for f in msg.DESCRIPTOR.fields:
            if f.type==f.TYPE_MESSAGE:
                if f.label==f.LABEL_REPEATED:
                    for child in getattr(msg,f.name):self.initialized(child)
                elif msg.HasField(f.name) or f.label==f.LABEL_REQUIRED:self.initialized(getattr(msg,f.name))
                continue
            if f.label==f.LABEL_REQUIRED and not msg.HasField(f.name):
                if f.type==f.TYPE_STRING:setattr(msg,f.name,'synthetic')
                elif f.type==f.TYPE_BOOL:setattr(msg,f.name,True)
                elif f.type==f.TYPE_ENUM:setattr(msg,f.name,f.enum_type.values[0].number)
                else:setattr(msg,f.name,1)
        return msg
    def wire(self,msg,cid):return base64.b64encode(self.encode(self.initialized(msg),cid)[4:]).decode()
    def private(self,closed=False):
        m,e=self.m,self.e;account=42;begin=datetime(2026,10,27,tzinfo=timezone.utc)
        p={'policy':n.POLICY,'identity':{'policy_sha256':n.POLICY_SHA,'native_source':n.NATIVE,
          'partition_sha256':bytes_digest(encoded(n.partition()))},'complete':True,
          'account':account,'receipts':[],'market':[],'contact_start_utc':begin.isoformat(),
          'contact_end_utc':(begin+timedelta(seconds=361)).isoformat(),'contact_start_ns':0,'contact_end_ns':361_000_000_000,
          'subscription_start_ns':1_000_000_000,'stream_end_ns':361_000_000_000,
          'connection_epochs':1,'wire_bytes':10000,'received_envelopes':20,
          'cleanup_state':'CONNECTION_CLOSED_AT_DEADLINE_UNSUBSCRIBE_NOT_ACKNOWLEDGED' if closed else 'UNSUBSCRIBE_ACKNOWLEDGED',
          'stream_end':'CAPTURE_DEADLINE_TIMEOUT_CONNECTION_CLOSED' if closed else 'CAPTURE_DEADLINE'}
        rows=[]
        for name in n.AUTH:
            res=getattr(m,name[:-3]+'Res')()
            if name=='ProtoOAGetAccountListByAccessTokenReq':res.permissionScope=e.SCOPE_VIEW;res.ctidTraderAccount.add(ctidTraderAccountId=account,isLive=True)
            if name=='ProtoOAAccountAuthReq':res.ctidTraderAccountId=account
            rows.append((name,None,res))
        trader=m.ProtoOATraderRes(ctidTraderAccountId=account);trader.trader.ctidTraderAccountId=account;trader.trader.brokerName='Pepperstone';trader.trader.depositAssetId=1
        assets=m.ProtoOAAssetListRes(ctidTraderAccountId=account);assets.asset.add(assetId=1,name='EUR')
        lights=m.ProtoOASymbolsListRes(ctidTraderAccountId=account);full=m.ProtoOASymbolByIdRes(ctidTraderAccountId=account)
        for key,name in n.POLICY['symbols'].items():
            sid=int(key);lights.symbol.add(symbolId=sid,symbolName=name,enabled=True)
            full.symbol.add(symbolId=sid,digits=5,pipPosition=4,minVolume=100000)
        for name,res in [('ProtoOATraderReq',trader),('ProtoOAAssetListReq',assets),('ProtoOASymbolsListReq',lights),('ProtoOASymbolByIdReq',full)]:
            req=getattr(m,name)(ctidTraderAccountId=account)
            if name=='ProtoOASymbolByIdReq':req.symbolId.extend([1,2,250])
            rows.append((name,req,res))
        for sid in (1,2,250):
            req=m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,volume=[100000])
            res=m.ProtoOAExpectedMarginRes(ctidTraderAccountId=account,moneyDigits=2);self.initialized(res.margin.add());res.margin[0].volume=100000
            rows.append(('ProtoOAExpectedMarginReq',req,res))
        rows.append(('ProtoOASubscribeSpotsReq',m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=account,symbolId=[1,2,250],subscribeToSpotTimestamp=True),m.ProtoOASubscribeSpotsRes(ctidTraderAccountId=account)))
        if not closed:rows.append(('ProtoOAUnsubscribeSpotsReq',m.ProtoOAUnsubscribeSpotsReq(ctidTraderAccountId=account,symbolId=[1,2,250]),m.ProtoOAUnsubscribeSpotsRes(ctidTraderAccountId=account)))
        for i,(name,req,res) in enumerate(rows):
            cid='synthetic-'+str(i);r={'request_type':name,'client_msg_id':cid,'response_wire':self.wire(res,cid)}
            if req is not None:r['request_wire']=self.wire(req,cid)
            p['receipts'].append(r)
        profiler=n.SpotProfile([1,2,250]);ms=int(begin.timestamp()*1000)
        for i in range(2):
            msg=m.ProtoOASpotEvent(ctidTraderAccountId=account,symbolId=1,timestamp=ms+i*3000,bid=100,ask=102)
            raw=self.encode(msg,'')[4:];r={'sequence':i+1,'receive_monotonic_ns':i*3_000_000_000,
              'receive_utc':(begin+timedelta(seconds=i*3)).isoformat(),'wire':base64.b64encode(raw).decode(),'sha256':bytes_digest(raw)}
            p['market'].append(r);profiler.observe(**n.market_event(r,account))
        p['producer_profile']=profiler.result();return p
    def verify(self,p):
        with patch.object(self.auth,'ACCOUNT_FINGERPRINT_SHA256',n.fingerprint(42)):return n.verify_private(p)
    def test_both_acknowledged_cleanup_and_closed_tail_have_exact_native_readback(self):
        for closed in (False,True):
            p=self.private(closed);r=self.verify(p);self.assertEqual(r['1']['events'],2)
            self.assertEqual(r['1']['healthy'],1);self.assertEqual(r['250']['events'],0)
    def test_scope_correlation_panel_duration_and_profile_tampering_refused(self):
        for mutate in (lambda p:p['identity'].update(policy_sha256='bad'),
          lambda p:p.update(account=43),lambda p:p['receipts'][3].update(client_msg_id='different'),
          lambda p:p.update(stream_end_ns=5_000_000_000),lambda p:p.update(connection_epochs=2),
          lambda p:p['producer_profile']['1'].update(healthy=2),lambda p:p['market'][0].update(sha256='bad')):
            p=self.private();mutate(p)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.verify(p)
if __name__=='__main__':unittest.main()
