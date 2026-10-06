import unittest,json,tempfile,os,hashlib
from pathlib import Path
import numpy as np
from . import read_only_auth_preflight_v1 as auth
from .private_token_checkpoint_v1 import PrivateTokenCheckpoint
from .post_outcome_diagnostic_v1 import NAMES as STAGES,quote
from .data import STATE
from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
class FakeTransport:
 def __init__(self,scope=e.SCOPE_VIEW):self.scope=scope;self.sent=[];self.closed=False
 def request(self,msg,timeout=None):
  self.sent.append(type(msg).__name__);auth.require_message(msg)
  if isinstance(msg,m.ProtoOAApplicationAuthReq):return m.ProtoOAApplicationAuthRes()
  if isinstance(msg,m.ProtoOAGetAccountListByAccessTokenReq):return m.ProtoOAGetAccountListByAccessTokenRes(accessToken='synthetic',permissionScope=self.scope,ctidTraderAccount=[e.ProtoOACtidTraderAccount(ctidTraderAccountId=3,isLive=True)])
  if isinstance(msg,m.ProtoOAAccountAuthReq):return m.ProtoOAAccountAuthRes(ctidTraderAccountId=3)
  if isinstance(msg,m.ProtoOATraderReq):return m.ProtoOATraderRes(trader=e.ProtoOATrader(ctidTraderAccountId=3,balance=0,depositAssetId=1,brokerName='Pepperstone - Europe',accountType=e.HEDGED,totalMarginCalculationType=e.MAX,swapFree=False))
  if isinstance(msg,m.ProtoOAAssetListReq):return m.ProtoOAAssetListRes(ctidTraderAccountId=3,asset=[e.ProtoOAAsset(assetId=1,name='EUR')])
  raise AssertionError('unexpected fixture request')
 def close(self):self.closed=True
class Tests(unittest.TestCase):
 def test_historical_immutability(self):
  for name,digest in [('ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json','be255fcfadbcf412a9d7b01238772dde4dc94fe5972cca4eb68006c4987de4e0'),('ADAPTIVE_COMPETITION_POLICY_V1_FROZEN_SPEC.json','08274d6911bc7bbfc75500b63091236ea978e6d2e39cc9d7d1af98dbc187b89f')]:self.assertEqual(hashlib.sha256((STATE/name).read_bytes()).hexdigest(),digest)
 def test_diagnostic_reconciliation(self):
  j=json.loads((STATE/'ADAPTIVE_V1_POST_OUTCOME_CAUSAL_GATE_DECOMPOSITION_V1.json').read_text());raw=json.loads((STATE/'ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json').read_text())
  for k in STAGES:self.assertEqual(j['stage_counts_aggregate'][k],sum(h[k] for h in j['stage_counts_by_horizon'].values()))
  self.assertEqual(j['stage_counts_aggregate']['forecast_nonzero_count'],raw['opportunity_counts']['raw_signal_count']);self.assertEqual(j['stage_counts_aggregate']['conversion_supported_count'],raw['opportunity_counts']['cost_admissible_opportunity_count'])
  for h in j['stage_counts_by_horizon'].values():self.assertGreaterEqual(h['positive_after_spread_only_count'],h['positive_after_spread_plus_commission_count']);self.assertGreaterEqual(h['positive_after_spread_plus_commission_count'],h['positive_after_spread_plus_commission_plus_delay_count'])
 def test_uncertainty_initialization_partition(self):
  j=json.loads((STATE/'ADAPTIVE_V1_COST_COVERAGE_GAP_DIAGNOSTIC_V1.json').read_text());z=j['initialization_uncertainty_audit']
  self.assertEqual(j['observations_positive_before_cost_but_unmeasurable_after_cost'],z['positive_cost_unresolved_zero_uncertainty_count']+z['positive_cost_unresolved_nonzero_uncertainty_count'])
  self.assertEqual(sum(r['positive_lower_return_count'] for r in j['symbols']),j['observations_positive_before_cost_but_unmeasurable_after_cost'])
 def test_cost_ladder_monotonic(self):
  j=json.loads((STATE/'ADAPTIVE_V1_FROZEN_COST_STRESS_LADDER_RESULT_V1.json').read_text());rows=j['results'];self.assertEqual([r['multiplier'] for r in rows],[1,1.5,2]);self.assertEqual([r['positive_net_count'] for r in rows],sorted([r['positive_net_count'] for r in rows],reverse=True))
 def test_order_and_history_denied(self):
  for cls in [m.ProtoOANewOrderReq,m.ProtoOAClosePositionReq,m.ProtoOAGetTrendbarsReq,m.ProtoOASubscribeSpotsReq,m.ProtoOARefreshTokenReq]:
   with self.assertRaises(auth.PreflightRejected):auth.require_message(cls())
 def test_trading_scope_denied_before_account_auth(self):
  t=FakeTransport(e.SCOPE_TRADE);old=auth.fingerprint;auth.fingerprint=lambda x:auth.EXPECTED_FINGERPRINT
  try:
   with self.assertRaises(auth.PreflightRejected):auth.run('synthetic','synthetic','synthetic',3,t)
   self.assertEqual(t.sent,['ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq']);self.assertTrue(t.closed)
  finally:auth.fingerprint=old
 def test_exact_account_rejection_before_contact(self):
  t=FakeTransport()
  with self.assertRaises(auth.PreflightRejected):auth.run('synthetic','synthetic','synthetic',3,t)
  self.assertEqual(t.sent,[])
 def test_read_only_protocol(self):
  t=FakeTransport();old=auth.fingerprint;auth.fingerprint=lambda x:auth.EXPECTED_FINGERPRINT
  try:
   r=auth.run('synthetic','synthetic','synthetic',3,t);self.assertTrue(r['auth_proven']);self.assertEqual(len(t.sent),5);self.assertTrue(t.closed)
  finally:auth.fingerprint=old
 def test_private_checkpoint_atomic_local(self):
  with tempfile.TemporaryDirectory() as d:
   os.chmod(d,0o700);p=PrivateTokenCheckpoint(Path(d)/'state.json')
   with p.locked():p.replace({'scope':'accounts','refresh_token':'synthetic-no-credentials'})
   self.assertEqual(p.load()['scope'],'accounts');self.assertEqual(os.stat(p.path).st_mode&0o777,0o600)
   with self.assertRaises(ValueError):p.replace({'scope':'trading'})
if __name__=='__main__':unittest.main()
