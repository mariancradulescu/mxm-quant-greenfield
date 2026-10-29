"""Prospective actual CSharp versus independent arrays; synthetic source only."""
import copy,json,os,random,shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import depth_pressure_development as n
from .depth_pressure_reference import reference,verdict
BASE=1793100000000
ROOT=Path(__file__).resolve().parents[2]
def spot(t,b=100,a=101,server='auto'):return dict(kind='spot',t=t,seq=t+1,utc=BASE+t,server=BASE+t if server=='auto' else server,bid=b,ask=a)
def depth(t,sign=1):return dict(kind='depth',t=t,seq=t+1,utc=BASE+t,quotes=[dict(id=i+1,side=sign if i<9 else -sign,price=100 if sign==1 else 101,size=3 if i<9 else 1) for i in range(10)],deleted=[])
def prefix(sign=1):return [spot(0),spot(1),depth(2),spot(5999),depth(6000,sign)]
class Compiled(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required depth-pressure CSharp absent')
   raise unittest.SkipTest('Actual compilation required in native CI')
 def check(self,rows):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'in').write_bytes(n.encoded(rows));subprocess.run(['dotnet','run','--project',str(ROOT/n.PROJECT),'-c','Release','--no-build','--',str(p/'in'),str(p/'out')],check=True,capture_output=True)
   actual=json.loads((p/'out').read_bytes());expected=reference(rows)
   self.assertEqual({k:actual[k] for k in expected},expected);self.assertFalse(actual['capital_replay']);self.assertFalse(actual['broker_fills']);return actual
 def test_bid_ask_roundtrip_and_both_orientations(self):
  for sign in (1,-1):
   rows=prefix(sign)+[spot(6250),spot(8250,105,106) if sign==1 else spot(8250,95,96)]
   a=self.check(rows);self.assertEqual(a['episodes'][0]['gross_raw'],4)
 def test_initial_snapshot_and_five_second_depth_warmup_cannot_signal(self):
  a=self.check([spot(0),spot(1),depth(2),depth(3),depth(1000)]);self.assertEqual(a['signals'],0)
 def test_entry_is_strictly_later_first_eligible_spot_not_depth(self):
  a=self.check(prefix()+[depth(6250),spot(6251),spot(8251,105,106)])
  self.assertEqual(a['episodes'][0]['entry'],6251)
 def test_entry_deadline_and_terminal_censor_are_not_zero_trades(self):
  a=self.check(prefix()+[spot(7001)]);self.assertEqual(a['censors'][0]['reason'],'ENTRY_TIMEOUT')
  a=self.check(prefix());self.assertEqual(a['censors'][0]['reason'],'TERMINAL_UNSETTLED')
 def test_exit_deadline_inclusive_and_after_deadline_censored(self):
  self.assertEqual(len(self.check(prefix()+[spot(6250),spot(8750)])['episodes']),1)
  self.assertEqual(self.check(prefix()+[spot(6250),spot(8751)])['censors'][0]['reason'],'EXIT_TIMEOUT')
 def test_invalid_opposite_side_and_server_clock_censor_full_episode(self):
  for row in (spot(6500,102,101),spot(6500,100,100),spot(6500,server=BASE),spot(6500,server=None)):
   a=self.check(prefix()+[spot(6250),row,spot(8250,105,106)]);self.assertEqual(len(a['episodes']),0);self.assertEqual(len(a['censors']),1)
 def test_ambiguous_depth_suffix_is_not_favorable_feature_prefix(self):
  bad=depth(6500);bad['quotes'][-1]['id']=1
  a=self.check(prefix()+[spot(6250),bad,spot(8250,105,106)]);self.assertEqual(a['censors'][0]['reason'],'AMBIGUOUS_DEPTH_MESSAGE')
 def test_fresh_endpoint_cannot_heal_expired_opposite_side_inside_exposure(self):
  rows=[spot(0),spot(1),depth(2),spot(3000),spot(5999,a=None),depth(6000),spot(6250,a=None),spot(8250,105,106)]
  a=self.check(rows);self.assertEqual(len(a['episodes']),0);self.assertEqual(a['censors'][0]['reason'],'UNOBSERVED_OR_INVALID_PATH')
 def test_five_second_holdoff_and_announcements_are_not_full_book(self):
  a=self.check(prefix()+[spot(6250),spot(8250),depth(8251)])
  self.assertEqual(a['signals'],1)
 def test_independent_deterministic_announcement_paths(self):
  rng=random.Random(226);rows=[spot(0),spot(1),depth(2)];t=3
  for _ in range(400):
   t+=rng.randrange(1,301);r=spot(t,100+rng.randrange(-4,5),105+rng.randrange(-4,5)) if rng.randrange(3)==0 else depth(t,rng.choice([-1,1]));rows.append(r)
  self.check(rows)
class Scope(unittest.TestCase):
 def test_direct_or_repeated_order_capable_frames_are_rejected(self):
  n.outbound_guard('ProtoHeartbeatEvent',None)
  n.outbound_guard('ProtoOASubscribeDepthQuotesReq',{'name':'ProtoOASubscribeDepthQuotesReq'})
  for name,active in [('ProtoOANewOrderReq',None),('ProtoOAExpectedMarginReq',None),('ProtoOASubscribeDepthQuotesReq',{'name':'ProtoOASubscribeDepthQuotesReq','cid':'old'})]:
   with self.assertRaises(ValueError):n.outbound_guard(name,active)
 def test_fixed_one_attempt_workflow_and_roles(self):
  w=n.workflow();self.assertEqual(json.loads((ROOT/n.PATH).read_bytes()),w);self.assertNotIn('workflow_dispatch',w['on'])
  self.assertEqual(n.POLICY['native_attempts'],1);self.assertEqual(n.POLICY['orders'],0);self.assertFalse(n.POLICY['automatic_retry'])
  self.assertEqual(w['jobs']['evaluate']['needs'],'capture')
  for role,j in w['jobs'].items():
   self.assertEqual(j['permissions'],{'contents':'read','actions':'read'});self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(j))
   if role=='capture':self.assertNotIn('R3_CUSTODY_PRIVATE_KEY_PEM',json.dumps(j))
   else:self.assertNotIn('R3_CTRADER_ACCESS_TOKEN',json.dumps(j))
 def test_wrong_context_cannot_open_key_git_or_contact(self):
  with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
   with self.assertRaisesRegex(ValueError,'NATIVE_CONTEXT'):n.admit()
   git.assert_not_called()
 def test_frozen_spec_binds_all_actual_implementations_and_no_diagnostic_reuse(self):
  with self.assertRaisesRegex(ValueError,'PRESSURE_EXACT_IMPLEMENTATION'):n.spec(ROOT)
  self.assertFalse(n.partition()['prior_diagnostic_or_protected_data_reclassified'])
  frozen=json.loads((ROOT/n.SPEC).read_bytes());self.assertEqual(frozen['policy']['model_trials_max'],1)
 def test_verdict_support_and_censoring_precede_any_positive_headroom(self):
  self.assertEqual(verdict(dict(signals=1,episodes=[dict(gross_raw=100)],censors=[]))[0],'DATA_LIMITED')
  self.assertEqual(verdict(dict(signals=100,episodes=[dict(gross_raw=-1)]*100,censors=[]))[0],'GROSS_NONPOSITIVE')
  self.assertEqual(verdict(dict(signals=100,episodes=[dict(gross_raw=1)]*100,censors=[]))[0],'CONDITIONAL_QUOTED_HEADROOM_COSTS_UNRESOLVED')


class NativeWire(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from .test_spot_observation_reception import NativeSpotWireTests
  NativeSpotWireTests.setUpClass();cls.h=NativeSpotWireTests();cls.m=NativeSpotWireTests.m;cls.e=NativeSpotWireTests.e;cls.auth=NativeSpotWireTests.auth
 def source(self):
  import base64
  from datetime import datetime,timezone
  m,e=self.m,self.e;account=42;p=dict(complete=True,policy=n.POLICY,partition=n.partition(),account=account,receipts=[],market=[],epochs=1,start_ms=0,end_ms=720000,wire_bytes=10000,origin_ns=0,cleanup='CLOSED_AT_DEADLINE',
   contact_start_utc=datetime.fromtimestamp(BASE/1000,timezone.utc).isoformat(),contact_end_utc=datetime.fromtimestamp((BASE+720000)/1000,timezone.utc).isoformat())
  messages=[]
  for name in n.AUTH:
   res=getattr(m,name[:-3]+'Res')()
   if name=='ProtoOAGetAccountListByAccessTokenReq':res.permissionScope=e.SCOPE_VIEW;res.ctidTraderAccount.add(ctidTraderAccountId=account,isLive=True)
   if name=='ProtoOAAccountAuthReq':res.ctidTraderAccountId=account
   messages.append((name,None,res))
  trader=m.ProtoOATraderRes(ctidTraderAccountId=account);trader.trader.ctidTraderAccountId=account;trader.trader.brokerName='Pepperstone';trader.trader.depositAssetId=1
  assets=m.ProtoOAAssetListRes(ctidTraderAccountId=account);assets.asset.add(assetId=1,name='EUR')
  lights=m.ProtoOASymbolsListRes(ctidTraderAccountId=account);lights.symbol.add(symbolId=250,symbolName='SpotCrude',enabled=True)
  full=m.ProtoOASymbolByIdRes(ctidTraderAccountId=account);full.symbol.add(symbolId=250,digits=2,pipPosition=2,minVolume=100)
  for name,res in [('ProtoOATraderReq',trader),('ProtoOAAssetListReq',assets),('ProtoOASymbolsListReq',lights),('ProtoOASymbolByIdReq',full)]:
   req=getattr(m,name)(ctidTraderAccountId=account)
   if name=='ProtoOASymbolByIdReq':req.symbolId.extend([250])
   messages.append((name,req,res))
  req=m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=250,volume=[100]);res=m.ProtoOAExpectedMarginRes(ctidTraderAccountId=account,moneyDigits=2);self.h.initialized(res.margin.add());res.margin[0].volume=100
  messages.append(('ProtoOAExpectedMarginReq',req,res))
  for name in ('ProtoOASubscribeSpotsReq','ProtoOASubscribeDepthQuotesReq'):
   req=getattr(m,name)(ctidTraderAccountId=account,symbolId=[250])
   if name=='ProtoOASubscribeSpotsReq':req.subscribeToSpotTimestamp=True
   messages.append((name,req,getattr(m,name[:-3]+'Res')(ctidTraderAccountId=account)))
  for i,(name,req,res) in enumerate(messages):
   cid='artificial-'+str(i);row=dict(name=name,cid=cid,response=self.h.wire(res,cid))
   if req is not None:row['request']=self.h.wire(req,cid)
   p['receipts'].append(row)
  normalized=prefix()+[spot(6250),spot(8250,105,106)]
  for i,r in enumerate(normalized):
   if r['kind']=='spot':msg=m.ProtoOASpotEvent(ctidTraderAccountId=account,symbolId=250,timestamp=r['server'],bid=r['bid'],ask=r['ask'])
   else:
    msg=m.ProtoOADepthEvent(ctidTraderAccountId=account,symbolId=250)
    for q in r['quotes']:
     item=msg.newQuotes.add(id=q['id'],size=q['size']);setattr(item,'bid' if q['side']==1 else 'ask',q['price'])
   raw=self.h.encode(msg,'')[4:]
   p['market'].append(dict(sequence=i+1,receive_monotonic_ns=r['t']*1000000,receive_utc=datetime.fromtimestamp(r['utc']/1000,timezone.utc).isoformat(),wire=base64.b64encode(raw).decode(),sha256=n.bytes_digest(raw)))
  return p
 def check(self,p):
  with patch.object(self.auth,'ACCOUNT_FINGERPRINT_SHA256',n.fingerprint(42)):return n.normalize(p)
 def test_original_wire_decoding_and_account_view_symbol_correlation(self):
  rows=self.check(self.source());a=reference(rows);self.assertEqual(a['episodes'][0]['gross_raw'],4)
 def test_wire_scope_duration_identity_and_quote_corruption_rejected(self):
  for change in (lambda p:p.update(account=43),lambda p:p.update(epochs=2),lambda p:p.update(end_ms=5000),
   lambda p:p['market'][0].update(sha256='bad'),lambda p:p['receipts'][4].update(cid='wrong'),lambda p:p.update(partition={})):
   p=self.source();change(p)
   with self.subTest(change=change),self.assertRaises(ValueError):self.check(p)
if __name__=='__main__':unittest.main()
