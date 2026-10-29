"""No-key admission and native-wire rejection cases for the single source question."""
import base64,copy,json,os,unittest
from pathlib import Path
from unittest.mock import patch
from . import panel_quote_support as n
from .common import encoded,bytes_digest
class ScopeTests(unittest.TestCase):
    def test_fixed_full_panel_window_and_no_economics(self):
        self.assertEqual(n.POLICY['symbols'],{'5':'AUDUSD','111':'Copper','250':'SpotCrude'})
        self.assertEqual(n.POLICY['to_ms']-n.POLICY['from_ms'],600000)
        self.assertEqual(n.POLICY['history_request_cap'],24)
        self.assertEqual(n.POLICY['from_ms'],1786442400000)
        for key in ('orders','strategy_trials'):self.assertEqual(n.POLICY[key],0)
        for key in ('automatic_retry','confirmation_eligible'):self.assertIs(n.POLICY[key],False)
        self.assertEqual(n.POLICY_SHA,bytes_digest(encoded(n.POLICY)))
        root=Path(os.environ.get('PANEL_TEST_MAIN_ROOT',n.ROOT))
        self.assertEqual(json.loads((root/n.PATH).read_bytes()),n.workflow())
        self.assertEqual(json.loads((root/n.PARTITION).read_bytes()),n.partition())
    def test_wrong_context_and_secrets_refused_before_io(self):
        env={'GITHUB_REPOSITORY':n.REPO,'GITHUB_REF_NAME':n.BRANCH,'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1',
          'GITHUB_JOB':'spot-collect','GITHUB_WORKFLOW_REF':n.REPO+'/'+n.PATH+'@refs/heads/'+n.BRANCH}
        for extra in ({'GITHUB_RUN_ATTEMPT':'2'},{'GITHUB_EVENT_NAME':'workflow_dispatch'},
          *({key:'artificial'} for key in (*n.BROKER,'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_REFRESH_TOKEN'))):
            with patch.dict(os.environ,{**env,**extra},clear=True),patch.object(n.subprocess,'check_output') as git:
                with self.assertRaises(ValueError):n.admission(n.ROOT)
                git.assert_not_called()
    def test_roles_and_no_direct_frames_or_second_sends(self):
        w=n.workflow();self.assertEqual(set(w['on']),{'push'});self.assertEqual(w['on']['push']['paths'],[n.PATH])
        for role,job in w['jobs'].items():
            self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(job))
            self.assertNotIn('PRIVATE_KEY' if role=='spot-collect' else 'R3_CTRADER_',json.dumps(job))
        for name,row in [('ProtoOANewOrderReq',None),('ProtoOAGetTickDataReq',None),
          ('ProtoOAGetTickDataReq',{'request_type':'ProtoOAGetTickDataReq','client_msg_id':'sent'}),
          ('ProtoOASubscribeSpotsReq',None),('ProtoOAGetTrendbarsReq',None)]:
            with self.assertRaises(ValueError):n.outbound_guard(name,row)

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
        from m6.ctrader_transport import encode_envelope
        from research_core_v4 import shallow_m5_support_v2_production as auth
        from . import chronology_reception
        cls.m=m;cls.e=e;cls.encode=staticmethod(encode_envelope);cls.auth=auth
    def initialized(self,msg):
        for f in msg.DESCRIPTOR.fields:
            if f.type==f.TYPE_MESSAGE:
                if f.label==f.LABEL_REPEATED:
                    for child in getattr(msg,f.name):self.initialized(child)
                elif msg.HasField(f.name) or f.label==f.LABEL_REQUIRED:self.initialized(getattr(msg,f.name))
            elif f.label==f.LABEL_REQUIRED and not msg.HasField(f.name):
                if f.type==f.TYPE_STRING:setattr(msg,f.name,'synthetic')
                elif f.type==f.TYPE_BOOL:setattr(msg,f.name,True)
                elif f.type==f.TYPE_ENUM:setattr(msg,f.name,f.enum_type.values[0].number)
                else:setattr(msg,f.name,1)
        return msg
    def wire(self,msg,cid):return base64.b64encode(self.encode(self.initialized(msg),cid)[4:]).decode()
    def private(self,empty=False):
        m,e=self.m,self.e;account=42
        p={'policy':n.POLICY,'identity':{'policy_sha256':n.POLICY_SHA,'native_source':n.NATIVE,
          'partition_sha256':bytes_digest(encoded(n.partition()))},'complete':True,'account':account,
          'receipts':[],'trees':{},'contact_start_ns':0,'contact_end_ns':1_000_000_000,
          'wire_bytes':10000,'connection_attempts':1}
        def add(req,res,name=None):
            name=name or type(req).__name__;cid='mxm-'+str(len(p['receipts'])+1).zfill(12)
            row={'request_type':name,'client_msg_id':cid,'response_wire':self.wire(res,cid)}
            if req is not None:row['request_wire']=self.wire(req,cid)
            p['receipts'].append(row)
        for name in n.AUTH:
            res=getattr(m,name[:-3]+'Res')()
            if name=='ProtoOAGetAccountListByAccessTokenReq':res.permissionScope=e.SCOPE_VIEW;res.ctidTraderAccount.add(ctidTraderAccountId=account,isLive=True)
            if name=='ProtoOAAccountAuthReq':res.ctidTraderAccountId=account
            add(None,res,name)
        trader=m.ProtoOATraderRes(ctidTraderAccountId=account);trader.trader.ctidTraderAccountId=account
        trader.trader.brokerName='Pepperstone';trader.trader.depositAssetId=1
        assets=m.ProtoOAAssetListRes(ctidTraderAccountId=account);assets.asset.add(assetId=1,name='EUR');assets.asset.add(assetId=2,name='USD')
        lights=m.ProtoOASymbolsListRes(ctidTraderAccountId=account);full=m.ProtoOASymbolByIdRes(ctidTraderAccountId=account)
        ids=[5,111,250]
        for key,name in n.POLICY['symbols'].items():
            sid=int(key);lights.symbol.add(symbolId=sid,symbolName=name,enabled=True,quoteAssetId=2)
            full.symbol.add(symbolId=sid,digits=5,pipPosition=4,minVolume=100,maxVolume=10000,stepVolume=100)
        for req,res in [(m.ProtoOATraderReq(ctidTraderAccountId=account),trader),
          (m.ProtoOAAssetListReq(ctidTraderAccountId=account),assets),
          (m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),lights),
          (m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=ids),full)]:add(req,res)
        for sid in ids:
            res=m.ProtoOAExpectedMarginRes(ctidTraderAccountId=account,moneyDigits=2)
            res.margin.add(volume=100,buyMargin=900,sellMargin=910)
            add(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,volume=[100]),res)
        for sid in ids:
            p['trees'][str(sid)]={}
            for label,side in (('BID',1),('ASK',2)):
                req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=side,
                  fromTimestamp=n.POLICY['from_ms'],toTimestamp=n.POLICY['to_ms']-1)
                res=m.ProtoOAGetTickDataRes(ctidTraderAccountId=account,hasMore=False)
                if not empty:res.tickData.add(timestamp=n.POLICY['from_ms']+1,tick=100001)
                p['trees'][str(sid)][label]=[{'lo':req.fromTimestamp,'hi':req.toTimestamp,'receipt_index':len(p['receipts']),'state':'LEAF_COMPLETE'}]
                add(req,res)
        return p
    def verify(self,p):
        with patch.object(self.auth,'ACCOUNT_FINGERPRINT_SHA256',n.old.fingerprint(42)):return n.verify_private(p)
    def test_full_panel_and_empty_source_are_diagnostics_not_economic_outcomes(self):
        for empty in (True,False):
            r=self.verify(self.private(empty));self.assertEqual(r['all_panel_sides_complete_nonempty'],not empty)
            self.assertEqual(len(r['quote_assets']),3);self.assertEqual(r['history_requests'],6)
    def test_wire_correlation_account_policy_tree_and_currency_tampering_rejected(self):
        for mutate in (lambda p:p.update(account=43),lambda p:p.update(connection_attempts=2),
          lambda p:p['identity'].update(policy_sha256='bad'),lambda p:p['receipts'][10].update(client_msg_id='wrong'),
          lambda p:p['trees']['5']['BID'][0].update(lo=n.POLICY['from_ms']+1),
          lambda p:p['trees']['5']['BID'][0].update(receipt_index=11),lambda p:p['trees'].pop('111')):
            p=self.private();mutate(p)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.verify(p)
        from m6.ctrader_transport import decode_envelope,extract_payload
        for change in ('currency','scope','margin','symbol'):
            p=self.private();index={'currency':5,'scope':1,'margin':7,'symbol':5}[change]
            row=p['receipts'][index];msg=extract_payload(decode_envelope(base64.b64decode(row['response_wire'])))
            if change=='currency':msg.symbol[0].quoteAssetId=1
            elif change=='scope':msg.permissionScope=self.e.SCOPE_TRADE
            elif change=='margin':msg.margin[0].volume=200
            else:msg.symbol[0].symbolName='different'
            row['response_wire']=self.wire(msg,row['client_msg_id'])
            with self.subTest(change=change),self.assertRaises(ValueError):self.verify(p)
    def test_sealed_splitter_handles_truncation_and_finite_cap_without_inventing_coverage(self):
        native=n.native_policy(5);calls=[]
        def send(req):
            calls.append(req);res=self.m.ProtoOAGetTickDataRes(ctidTraderAccountId=42,hasMore=True)
            return len(calls)-1,res
        tree=native.split_collect(send,42,1,n.POLICY['from_ms'],n.POLICY['to_ms']-1,lambda:2-len(calls))
        self.assertEqual(len(calls),2);self.assertTrue(any(x['state']=='REQUEST_CAP_UNRESOLVED' for x in tree))
if __name__=='__main__':unittest.main()
