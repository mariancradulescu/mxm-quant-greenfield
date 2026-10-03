import unittest,copy,json,pathlib,hashlib,gzip,collections
from research_core_v4.quote_scope_metadata_v1 import classify,checked_request,localize,ALLOWED
from research_core_v4.quote_scope_power_v1 import holm,information
ROOT=pathlib.Path(__file__).resolve().parents[1]
class ScopeAudit(unittest.TestCase):
 def fixture(self):
  return ({'symbol':'S','symbol_id':1,'asset_class':'Forex (Spot)'},
   {'symbolName':'S','enabled':True,'baseAssetId':1,'quoteAssetId':2},
   {'symbolId':1,'tradingMode':0,'enableShortSelling':True,'minVolume':100,'stepVolume':100,'maxVolume':10000,'lotSize':100,
    'minCommission':0,'minCommissionType':1,'minCommissionAsset':'USD','commissionType':1,'preciseTradingCommissionRate':0,'pnlConversionFeeRate':0,'scheduleTimeZone':'UTC','schedule':[{'startSecond':86400,'endSecond':172800}]},
   {'requested_volume':100,'moneyDigits':2,'buyMargin':500,'sellMargin':1000})
 def test_valid_explicit_metadata(self):
  self.assertEqual(classify(*self.fixture())['status'],'STRUCTURALLY_ELIGIBLE')
 def test_unresolved_lattice_not_forced_exclusion(self):
  args=self.fixture();args[2]['minVolume']=125;self.assertEqual(classify(*args)['status'],'METADATA_INSUFFICIENT')
 def test_unknown_timezone_not_certified(self):
  args=self.fixture();args[2]['scheduleTimeZone']='NOT_A_ZONE';self.assertEqual(classify(*args)['status'],'METADATA_INSUFFICIENT')
 def test_disabled_and_short_false(self):
  for field,value in [('tradingMode',1),('enableShortSelling',False)]:
   args=self.fixture();args[2][field]=value;self.assertEqual(classify(*args)['status'],'STRUCTURALLY_INELIGIBLE')
 def test_missing_zero_not_inferred(self):
  for key in ['enableShortSelling','commissionType','pnlConversionFeeRate','schedule']:
   args=self.fixture();del args[2][key];self.assertEqual(classify(*args)['status'],'METADATA_INSUFFICIENT')
 def test_money_digits_and_eur200_boundary(self):
  args=self.fixture();args[3]['sellMargin']=20000;self.assertEqual(classify(*args)['status'],'ECONOMICALLY_UNEXECUTABLE_FOR_EUR200')
  args[3]['moneyDigits']=None;self.assertEqual(classify(*args)['status'],'METADATA_INSUFFICIENT')
 def test_margin_wrong_volume_and_negative(self):
  for field,value in [('requested_volume',125),('buyMargin',-1)]:
   args=self.fixture();args[3][field]=value;self.assertEqual(classify(*args)['status'],'METADATA_INSUFFICIENT')
 def test_no_identity_replacement(self):
  args=self.fixture();args[1]['symbolName']='OTHER';self.assertEqual(classify(*args)['status'],'METADATA_INSUFFICIENT')
 def test_historical_orders_quotes_all_rejected_before_transport(self):
  class Fake:
   def request(self,msg):raise AssertionError('transport reached')
  for name in ['ProtoOAGetTickDataReq','ProtoOAGetTrendbarsReq','ProtoOANewOrderReq','ProtoOASubscribeSpotsReq','ProtoMessage','ProtoOAReconcileReq']:
   with self.assertRaises(PermissionError):checked_request(Fake(),type(name,(),{})())
 def test_only_exact_8_metadata_messages(self):
  self.assertEqual(len(ALLOWED),8)
 def test_missing_credentials_before_import_or_network(self):
  with self.assertRaises(PermissionError):localize([],client_id='',client_secret='',access_token='')
 def test_full_population_no_omissions(self):
  d=json.loads((ROOT/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_FULL_FRONTIER_ELIGIBILITY_V1.json').read_bytes()); original=json.loads(gzip.decompress((ROOT/d['source_ref']).read_bytes()))['rows']
  cols=d['columns'];rows=[dict(zip(cols,r)) for r in d['rows']];self.assertEqual(len(rows),1576)
  self.assertEqual({(r['symbol'],r['symbol_id']) for r in rows},{(r['symbol'],r['symbol_id']) for r in original})
  self.assertEqual(collections.Counter(r['asset_class'] for r in rows),d['asset_class_counts'])
  self.assertEqual({r['current_eligibility'] for r in rows},{'METADATA_INSUFFICIENT'})
  self.assertTrue(all(r['exclusion_reason'] is None for r in rows))
 def test_raw_and_interpretation_preserved(self):
  for name,expected in [('FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json','77462da0329b21dd981896c3ab31f3383ef8f092948ac1c6c61a6c148e630208'),('FIRST_V4_DEVELOPMENT_RESPONSE_INTERPRETATION_V1.json','715e0d100fddda9b525fedc6f1dbf852973419d14634fa0c347fdb445d31cad2')]:
   self.assertEqual(hashlib.sha256((ROOT/'research_core_v4/state'/name).read_bytes()).hexdigest(),expected)
 def test_design_no_final_panel_no_best_identity(self):
  d=json.loads((ROOT/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_DESIGN_V2.json').read_bytes());self.assertEqual(d['signal_symbols'],[])
  self.assertEqual(d['multiplicity']['context_count_frozen'],29);self.assertEqual(len(d['multiplicity']['contexts']),29)
  self.assertEqual(d['calendar']['iso_week_count'],52)
  self.assertIsNone(d['scope_adaptive_basis']['final_current_eligible_symbol_count'])
 def test_request_manifest_nonexecutable(self):
  d=json.loads((ROOT/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_REQUEST_MANIFEST_V2.json').read_bytes());self.assertEqual(d['exact_executable_rows'],[])
  self.assertEqual(d['census_maximum_base_side_requests'],1576*52*2)
 def test_correlation_limits_information(self):
  a=information(5,17,.8,0);b=information(1576,17,.8,0)
  self.assertLess(b['effective_independent_identity_equivalents'],1.25)
  self.assertLess(b['context_mean_standard_error_weekly_noise_units'],a['context_mean_standard_error_weekly_noise_units'])
  self.assertGreater(information(1576,52,.8,.5)['context_mean_standard_error_weekly_noise_units'],information(1576,52,.8,0)['context_mean_standard_error_weekly_noise_units'])
 def test_holm_keeps_absent_siblings(self):
  self.assertFalse(holm([.01]+[1]*28)[0]);self.assertTrue(holm([.001]+[1]*28)[0]);self.assertFalse(holm([1]*29).any())
