import copy,json,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import quote_triangle_development as n
from .quote_triangle_reference import reconcile,source_views,admission
from .economic_journal import validate

def fixture(dislocation=True):
 t={'symbolId':2,'commissionType':2,'minCommissionType':1,'preciseTradingCommissionRate':300000000,'preciseMinCommission':0,
 'minCommissionAsset':'USD','minVolume':100000,'maxVolume':10000000,'stepVolume':100000,'lotSize':10000000}
 rows=[];utc=1793275200000
 for i in range(450):
  for sid in (1,9,2):
   # Positive complete source. A deliberately displaced synthetic relation
   # creates auditable proposals; no observed market behavior is inferred.
   bid={1:110000,9:88000,2:124000 if dislocation else 125000}[sid]
   seq=len(rows)+1;ms=i*200+sid
   rows.append(dict(symbol=sid,sequence=seq,arrival_ns=(i*200+{1:0,9:1,2:2}[sid])*1000000,received_ms=utc+ms,server_ms=utc+ms,bid=bid,ask=bid+10))
 # Actual UTC monotonic receipt is independently required globally.
 for r in rows:r['received_ms']=r['server_ms']=utc+r['arrival_ns']//1000000
 return dict(target_terms=t,margin_eur='35',events=rows)

class ScopeTests(unittest.TestCase):
 def test_frozen_scope_roles_and_no_old_source(self):
  n.validate();self.assertEqual(json.loads((n.ROOT/n.PATH).read_bytes()),n.workflow())
  self.assertEqual(n.POLICY['symbols'],{'1':'EURUSD','2':'GBPUSD','9':'EURGBP'})
  self.assertEqual(n.POLICY['maximum_new_identities_after_source_admission'],1)
  self.assertEqual(n.POLICY['history_requests'],0);self.assertEqual(n.POLICY['orders'],0)
  w=n.workflow();self.assertEqual(set(w['on']),{'push'})
  for name,j in w['jobs'].items():
   self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
   self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(j))
   if name=='spot-collect':self.assertNotIn('PRIVATE_KEY',json.dumps(j))
   else:self.assertNotIn('secrets.R3_CTRADER_',json.dumps(j))
 def test_configuration_preserves_old_profile_and_policy(self):
  old=copy.deepcopy(n.source.POLICY);fn=n.source.partition
  with n.configured():self.assertEqual(n.source.POLICY['symbols'],n.POLICY['symbols']);self.assertEqual(n.source.partition(),n.partition())
  self.assertEqual(n.source.POLICY,old);self.assertIs(n.source.partition,fn)
 def test_exact_decimal_journal_hash_survives_original_json_readback(self):
  from decimal import Decimal
  row=dict(ordinal=1,source_sequence=1,received_ms=1,arrival_ns=1,state='ABSTAIN',reason='TEST',direction=0,opportunity_id=None,
   context=dict(source_symbol=2,target=dict(Bid=Decimal('1.234567890123456789012345678')),fx=None,synthetic=None,cost_state='UNRESOLVED',margin_state=None,risk_state=None),modeled_fill=None)
  a=validate([row],target_events=1,source_sha256='a'*64,policy_sha256='b'*64)
  raw=json.dumps([row],default=str).replace('"1.234567890123456789012345678"','1.234567890123456789012345678')
  self.assertEqual(a,validate(json.loads(raw,parse_float=Decimal),target_events=1,source_sha256='a'*64,policy_sha256='b'*64))
 def test_forbidden_context_and_secrets_fail_before_git_or_network(self):
  with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
   with self.assertRaises(ValueError):n.admit()
   git.assert_not_called()
 def test_price_blind_geometry_and_reference_support(self):
  a=fixture();v=source_views(a);self.assertTrue(admission(v)['admitted'])
  # A common scale change preserves clocks/geometry and no returns are read.
  b=copy.deepcopy(a)
  for e in b['events']:
   e['bid']*=2;e['ask']*=2
  self.assertEqual(admission(source_views(b)),admission(v))
  a['events']=[e for e in a['events'] if e['symbol']!=9]
  self.assertFalse(admission(source_views(a))['admitted'])

class CompiledTests(unittest.TestCase):
 def execute(self,data):
  self.assertIsNotNone(shutil.which('dotnet'),'Actual CSharp execution is mandatory; never skip in CI')
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/'input.json';b=Path(tmp)/'output.json';a.write_text(json.dumps(data));n.run_csharp(a,b)
   return json.loads(b.read_bytes(),parse_float=__import__('decimal').Decimal)
 def test_full_individual_ledger_and_source_arrays(self):
  data=fixture();actual=self.execute(data);self.assertEqual(actual['models'],1);self.assertTrue(actual['episodes']);reconcile(data,actual)
  audit=validate(actual['journal'],target_events=actual['target_events'],source_sha256='a'*64,policy_sha256='b'*64)
  self.assertTrue(audit['complete_individual_ledger'])
  bad=copy.deepcopy(actual['journal']);bad.pop(0)
  with self.assertRaises(ValueError):validate(bad,target_events=actual['target_events'],source_sha256='a'*64,policy_sha256='b'*64)
 def test_no_identity_without_reference_or_capital_support(self):
  for change in ('reference','margin'):
   data=fixture()
   if change=='reference':data['events']=[e for e in data['events'] if e['symbol']!=9]
   else:data['margin_eur']='90'
   actual=self.execute(data);reconcile(data,actual);self.assertEqual(actual['models'],0);self.assertFalse(actual['journal'])
 def test_causal_prefix_and_unknown_terminal_episode_preserved(self):
  data=fixture();data['events']=[e for e in data['events'] if e['arrival_ns']<89000000000]
  actual=self.execute(data);changed=copy.deepcopy(data);cut=40000000000
  for e in changed['events']:
   if e['arrival_ns']>=cut and e['symbol']==2:e['bid']+=30;e['ask']+=30
  other=self.execute(changed)
  self.assertEqual([r for r in actual['journal'] if r['arrival_ns']<cut],[r for r in other['journal'] if r['arrival_ns']<cut])
  self.assertEqual(actual['episodes'][-1]['exit'],None)
if __name__=='__main__':unittest.main()
