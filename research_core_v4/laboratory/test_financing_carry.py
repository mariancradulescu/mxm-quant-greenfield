import copy,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import financing_carry_development as n
from .financing_carry_reference import reference,verdict

def source():return {'account_type':0,'swap_free':False,'rows':[{'symbol_id':1,'identity_available':True,'enabled':True,'full':{'tradingMode':0,'enableShortSelling':True,'swapCalculationType':0,'swapLong':'2','swapShort':'-3'}}]}
class Policy(unittest.TestCase):
 def test_fixed_source_scope_and_unchanged_prior_partitions(self):
  self.assertEqual(len(n.roster()),1576);self.assertEqual(n.spec(n.ROOT)['policy'],n.POLICY)
  self.assertEqual(json.loads((n.ROOT/n.PATH).read_bytes()),n.workflow());self.assertEqual(n.POLICY['model_trials_max'],1)
  self.assertNotIn('workflow_dispatch',n.workflow()['on'])
  for name in ['ProtoOANewOrderReq','ProtoOASubscribeSpotsReq','ProtoOASubscribeDepthQuotesReq','ProtoOAExpectedMarginReq','ProtoOAGetTickDataReq']:
   with self.assertRaises(ValueError):n.outbound_guard(name,None)
  with self.assertRaises(ValueError):n.outbound_guard('ProtoOASymbolByIdReq',{'name':'ProtoOASymbolByIdReq','cid':'used'})
 def test_context_checked_before_credentials_or_network(self):
  with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
   with self.assertRaises(ValueError):n.admit()
   git.assert_not_called()
 def test_support_and_positive_are_never_full_economics(self):
  self.assertEqual(verdict(reference(source()))[0],'NO_POSITIVE_CURRENT_PAIR_RATE')
  x=source();del x['rows'][0]['full']['swapShort'];self.assertEqual(verdict(reference(x))[0],'DATA_LIMITED')
  x=source();x['rows'][0]['full']['swapShort']='-1';self.assertEqual(verdict(reference(x))[0],'POSITIVE_CURRENT_PAIR_RATE_FULL_ECONOMICS_UNRESOLVED')
class Compiled(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required CSharp missing')
   raise unittest.SkipTest('CSharp compilation required in CI')
 def check(self,s):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'input').write_bytes(n.encoded(s))
   subprocess.run(['dotnet','run','--project',str(n.ROOT/n.PROJECT),'-c','Release','--no-build','--',str(p/'input'),str(p/'output')],check=True,capture_output=True)
   actual=json.loads((p/'output').read_bytes());self.assertEqual(actual['rows'],reference(s)['rows']);return actual
 def test_exact_signed_rate_comparisons_all_units_no_cash_inference(self):
  for kind in (0,1,2):
   for a,b in [('2','-3'),('2','-2'),('2','-1'),('1e308','1e308'),('1.0000000000000002','-1'),('-0','0')]:
    s=source();s['rows'][0]['full'].update(swapLong=a,swapShort=b,swapCalculationType=kind);self.check(s)
 def test_every_optional_missing_is_unresolved_not_default_zero(self):
  for key in source()['rows'][0]['full']:
   s=source();del s['rows'][0]['full'][key];self.assertEqual(self.check(s)['rows'][0]['classification'],'DATA_UNRESOLVED')
  for key in ('account_type','swap_free'):
   s=source();s[key]=None;self.assertEqual(self.check(s)['rows'][0]['classification'],'DATA_UNRESOLVED')
 def test_nonfinite_unknown_units_restrictions_and_missing_identity(self):
  for key,value in [('swapLong','NaN'),('swapShort','Infinity'),('swapCalculationType',99)]:
   s=source();s['rows'][0]['full'][key]=value;self.check(s)
  for key,value in [('tradingMode',1),('enableShortSelling',False)]:
   s=source();s['rows'][0]['full'][key]=value;self.assertEqual(self.check(s)['rows'][0]['classification'],'CURRENT_PAIR_UNAVAILABLE')
  for key,value in [('account_type',1),('account_type',2),('swap_free',True)]:
   s=source();s[key]=value;self.check(s)
  s=source();s['rows'][0]['identity_available']=False;self.check(s)
 def test_entire_universe_and_calendar_presence_retained(self):
  s=source();s['rows']=[dict(s['rows'][0],symbol_id=i+1,full=dict(s['rows'][0]['full'],swapLong=str(i-800),swapPeriod=24,skipSWAPPeriods=0)) for i in range(1576)]
  self.assertEqual(len(self.check(s)['rows']),1576)
class Wire(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from .test_spot_observation_reception import NativeSpotWireTests
  NativeSpotWireTests.setUpClass();cls.h=NativeSpotWireTests();cls.m=NativeSpotWireTests.m;cls.e=NativeSpotWireTests.e;cls.auth=NativeSpotWireTests.auth
 def make(self):
  import base64
  m,e=self.m,self.e;account=42
  p=dict(complete=True,policy=n.POLICY,partition=n.partition(),account=account,receipts=[],epochs=1,wire_bytes=1000,end_ms=1000)
  pairs=[]
  for name in n.AUTH:
   res=getattr(m,name[:-3]+'Res')()
   if name=='ProtoOAGetAccountListByAccessTokenReq':res.permissionScope=e.SCOPE_VIEW;res.ctidTraderAccount.add(ctidTraderAccountId=account,isLive=True)
   if name=='ProtoOAAccountAuthReq':res.ctidTraderAccountId=account
   pairs.append((name,None,res))
  trader=m.ProtoOATraderRes(ctidTraderAccountId=account);self.h.initialized(trader.trader);trader.trader.ctidTraderAccountId=account;trader.trader.brokerName='Pepperstone';trader.trader.depositAssetId=1;trader.trader.accountType=0;trader.trader.swapFree=False
  assets=m.ProtoOAAssetListRes(ctidTraderAccountId=account);assets.asset.add(assetId=1,name='EUR')
  lights=m.ProtoOASymbolsListRes(ctidTraderAccountId=account);ident=n.roster()[0];sid=ident['symbol_id'];lights.symbol.add(symbolId=sid,symbolName=ident['symbol'],enabled=True)
  full=m.ProtoOASymbolByIdRes(ctidTraderAccountId=account);full.symbol.add(symbolId=sid,digits=5,pipPosition=4,swapLong=2,swapShort=-3,swapCalculationType=0)
  for name,res in [('ProtoOATraderReq',trader),('ProtoOAAssetListReq',assets),('ProtoOASymbolsListReq',lights),('ProtoOASymbolByIdReq',full)]:
   req=getattr(m,name)(ctidTraderAccountId=account)
   if name=='ProtoOASymbolByIdReq':req.symbolId.extend([sid])
   pairs.append((name,req,res))
  for i,(name,req,res) in enumerate(pairs):
   self.h.initialized(res)
   row={'name':name,'cid':str(i),'response':self.h.wire(res,str(i))}
   if req is not None:row['request']=self.h.wire(req,str(i))
   p['receipts'].append(row)
  return p
 def test_original_wire_all_optional_presence_and_universe_retained(self):
  p=self.make()
  with patch.object(self.auth,'ACCOUNT_FINGERPRINT_SHA256',n.fingerprint(42)):
   a=n.normalize(p);self.assertEqual(len(a['rows']),1576);self.assertEqual(a['rows'][0]['full']['swapLong'],'2');self.assertNotIn('swapPeriod',a['rows'][0]['full'])
 def test_wrong_scope_missing_batch_or_forged_correlation_rejected(self):
  p=self.make()
  for mutation in ('missing','cid','view'):
   q=copy.deepcopy(p)
   if mutation=='missing':q['receipts'].pop()
   if mutation=='cid':q['receipts'][-1]['cid']='wrong'
   if mutation=='view':
    import base64
    from m6.ctrader_transport import decode_envelope,extract_payload
    row=q['receipts'][1];env=decode_envelope(base64.b64decode(row['response']));msg=extract_payload(env);msg.permissionScope=self.e.SCOPE_TRADE;row['response']=self.h.wire(msg,row['cid'])
   with patch.object(self.auth,'ACCOUNT_FINGERPRINT_SHA256',n.fingerprint(42)),self.assertRaises(ValueError):n.normalize(q)
