import copy,math,random,unittest
from unittest.mock import patch
from research_core_v4 import factor_residual_v1 as f
class FactorResidualTests(unittest.TestCase):
 def history(self,n=400):
  rng=random.Random(123);return [{i:rng.gauss(0,.001) for i in range(6)} for _ in range(n)]
 def test_leave_out_own_does_not_affect_factor(self):
  a=dict(enumerate(range(6)));b=dict(a);b[2]=100000;self.assertEqual(f.leave_out(a,2),f.leave_out(b,2))
 def test_reference_parity(self):
  for seed in range(10):
   history=self.history(288+seed*5)
   for sid in range(6):
    a,b=f.fit(history,sid),f.fit_reference(history,sid)
    for k in ['alpha','beta','sigma']:self.assertAlmostEqual(a[k],b[k],places=13)
 def test_self_never_in_peer_set(self):self.assertEqual(f.leave_out({i:float(i) for i in range(6)},0),3.)
 def test_wrong_membership(self):
  with self.assertRaises(ValueError):f.leave_out({1:1.,2:2.},1)
 def test_insufficient_training(self):
  with self.assertRaises(ValueError):f.fit(self.history(200),0)
 def test_singular_factor(self):
  with self.assertRaises(ValueError):f.fit([{i:0. for i in range(6)}]*300,0)
 def test_gap_never_filled(self):
  s={i:{t:1+t*.000001 for t in range(0,3900,300)} for i in range(6)};del s[1][600];self.assertIsNone(f.hour_returns(s,3600))
 def test_hour_accessor_reads_no_future(self):
  class Guard(dict):
   def __getitem__(self,t):
    if t>3600:raise AssertionError('future price read')
    return super().__getitem__(t)
  s={i:Guard({t:1+t*.000001 for t in range(0,4200,300)}) for i in range(6)};self.assertIsNotNone(f.hour_returns(s,3600))
 def test_real_entry_denied(self):
  with self.assertRaises(ValueError):f.evaluate_synthetic_only({}, {'synthetic_only':False})
 def test_missing_joint_calendar_fails(self):
  with self.assertRaises(ValueError):f.inference({'A':{i:float(i) for i in range(12)},'B':{i:float(i) for i in range(1,13)}})
 def test_noncontiguous_joint_calendar_fails(self):
  with self.assertRaises(ValueError):f.inference({'A':{i:float(i) for i in range(13) if i!=4}})
 def test_degenerate_inference_fails(self):
  with self.assertRaises(ValueError):f.hac_t([1.]*20)
 def test_deterministic_shared_bootstrap(self):
  rng=random.Random(20);leaves={'A':{i:rng.gauss(0,1) for i in range(20)},'B':{i:rng.gauss(0,1) for i in range(20)}};self.assertEqual(f.inference(leaves,resamples=31),f.inference(leaves,resamples=31))
 def test_family_not_best_symbol(self):
  rng=random.Random(21);r=f.inference({k:{i:rng.gauss(0,1) for i in range(20)} for k in ['A:12','A:48','B:12','B:48']},resamples=31);self.assertEqual(len(r['adjusted_pvalues']),4)
 def test_support_not_raw_event_independence(self):
  self.assertFalse(f.geometry([],12)['support_pass'])
 def test_response_censor(self):
  with self.assertRaises(ValueError):f.response({'retained':{'12':False}},12,{})

 def fixture(self):
  rng=random.Random(42);series={i:{0:100.} for i in range(6)}
  for t in range(300,35*86400,300):
   common=rng.gauss(0,.0001)
   for i in series:series[i][t]=series[i][t-300]*math.exp(common+rng.gauss(0,.0002))
  d={'memberships':{'A':list(range(6))},'training_start':0,'training_end':14*86400,'evaluation_start':15*86400,'evaluation_end':34*86400}
  return series,d
 def test_prepare_no_response_no_network(self):
  series,d=self.fixture()
  with patch.object(f,'response',side_effect=AssertionError('response forbidden')) as response,patch('socket.socket',side_effect=AssertionError('network forbidden')) as sock:
   report,events=f.prepare({'A':series},d)
   self.assertFalse(report['response_opened']);self.assertEqual(response.call_count,0);self.assertEqual(sock.call_count,0);self.assertGreater(len(events),0)
 def test_future_mutation_does_not_change_prior_features(self):
  series,d=self.fixture();cut=25*86400;a,models=f.events(series,d,'A')
  for p in series.values():
   for t in p:
    if t>cut:p[t]*=1.1
  b,later_models=f.events(series,d,'A');self.assertEqual(models,later_models);self.assertEqual([e for e in a if e['time']<=cut],[e for e in b if e['time']<=cut])
 def test_training_evaluation_overlap_denied(self):
  series,d=self.fixture();d['training_end']=d['evaluation_start']
  with self.assertRaises(ValueError):f.events(series,d,'A')
 def test_missing_future_timestamp_is_right_censored(self):
  series,d=self.fixture();es,_=f.events(series,d,'A');t=es[0]['time'];del series[1][t+300];later,_=f.events(series,d,'A');e=next(e for e in later if e['time']==t and e['symbol_id']==es[0]['symbol_id']);self.assertFalse(e['retained']['12']);self.assertFalse(e['retained']['48'])


 def test_response_reference_formula(self):
  s={i:{0:100.,3600:100.} for i in range(6)};s[0][3600]=110.
  e={'time':0,'symbol_id':0,'direction':-1,'model':{'alpha':0.,'beta':0.,'sigma':.01},'retained':{'12':True}}
  self.assertAlmostEqual(f.response(e,12,s),-math.log(1.1)/.01,places=12)
 def test_replication_not_best_context(self):
  leaves={c+':'+str(h):{b:1.+b/100 for b in range(21)} for c in ('A','B') for h in (12,48)}
  result={'adjusted_pvalues':{k:.001 for k in leaves}};result['adjusted_pvalues']['B:12']=.5;result['adjusted_pvalues']['B:48']=.5
  self.assertFalse(f.decision(leaves,result)['eligible_horizons'])
 def test_temporal_replication_required(self):
  leaves={c+':'+str(h):{b:(-1. if b//8==1 else 2.) for b in range(21)} for c in ('A','B') for h in (12,48)}
  self.assertFalse(f.decision(leaves,{'adjusted_pvalues':{k:.001 for k in leaves}})['eligible_horizons'])
 def test_same_sign_replication_required(self):
  leaves={c+':'+str(h):{b:1. if c=='A' else -1. for b in range(21)} for c in ('A','B') for h in (12,48)}
  self.assertFalse(f.decision(leaves,{'adjusted_pvalues':{k:.001 for k in leaves}})['eligible_horizons'])

if __name__=='__main__':unittest.main()
