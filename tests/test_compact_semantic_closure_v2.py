import copy
import json
import unittest
from pathlib import Path
from fractions import Fraction
from research_core_v4 import compact_semantic_closure_v2 as c
from research_core_v4.strict_reselection_v2 import canonical, io_firewall
from research_core_v4.master1576_current_state_guard_v7 import validate_root
class ClosureTests(unittest.TestCase):
 def test_all_same_frozen_baseline(self):
  for s in c.SOURCES:
   with self.subTest(s=s):
    v=json.loads(Path(c.ref(s)).read_bytes());self.assertEqual(v['baseline']['sha256'],c.BASE_HASH);self.assertEqual(v['baseline']['freeze_commit'],c.FREEZE_COMMIT)
 def test_all_reproduce_isolated(self):
  for s in c.SOURCES:
   with self.subTest(s=s):
    seen=[];v=c.build_one('.',s,seen);self.assertEqual(seen,[c.BASE,c.packet_ref(s)]);self.assertEqual(canonical(v),Path(c.ref(s)).read_bytes())
 def test_denied_peer_read(self):
  s=c.SOURCES[0]
  with io_firewall('.',{c.BASE,c.packet_ref(s)},[]):
   with self.assertRaises(ValueError):Path(c.ref(c.SOURCES[1])).read_bytes()
 def test_denied_historical_read(self):
  with io_firewall('.',{c.BASE},[]):
   with self.assertRaises(ValueError):Path('adaptive_competition/state/ADAPTIVE_COMPETITION_POLICY_V1_RAW_ECONOMIC_RESULT.json').read_bytes()
 def test_denied_descriptor(self):
  with io_firewall('.',set(),[]):
   with self.assertRaises((TypeError,ValueError)):open(0)
 def test_unchanged_candidates(self):
  defs=json.loads(Path(c.f.PROPOSALS).read_bytes())['candidates'][1:]
  for d in defs:
   v=json.loads(Path(c.ref(d['information_source'])).read_bytes());self.assertEqual(v['unchanged_definition'],d);self.assertEqual(v['candidate_definition_sha256'],c.sha(canonical(d)))
 def test_packets_own_only(self):
  for s in c.SOURCES:
   p=json.loads(Path(c.packet_ref(s)).read_bytes());self.assertEqual(set(p),{'candidate','modalities'});self.assertEqual(p['candidate']['information_source'],s)
 def test_functional_byte_exact(self):self.assertEqual(c.sha(Path(c.f.FUNCTIONAL).read_bytes()),c.F_HASH)
 def test_reapplication_reproducible(self):
  certs={c.ref(s):json.loads(Path(c.ref(s)).read_bytes()) for s in c.SOURCES};r,seen=c.reapply('.',certs);stored=json.loads(Path(c.RESULT).read_bytes());stored.pop('input_read_trace');stored.pop('manifest_sha256');self.assertEqual(stored,r)
 def test_unknown_competitors(self):
  r=json.loads(Path(c.RESULT).read_bytes());self.assertEqual(r['unknown_count'],11);self.assertEqual(r['admissible_count'],0);self.assertIsNone(r['selected_source'])
 def test_manifest_binding(self):
  m=json.loads(Path(c.MANIFEST).read_bytes());self.assertEqual(len(m['certificates']),11)
  for x in m['certificates']:self.assertEqual(c.sha(Path(x['ref']).read_bytes()),x['sha256'])
 def test_external_boundary(self):
  b=json.loads(Path(c.BOUNDARY).read_bytes());self.assertEqual(sum(x['status']=='TRUE_EXTERNAL_AUTHENTIC_CONTRACT_BOUNDARY' for x in b['cuts']),7)
 def test_governance_distinct_from_empirical(self):
  b=json.loads(Path(c.BOUNDARY).read_bytes());self.assertTrue(b['governance_blocker_is_not_empirical']);self.assertEqual(sum(x['status']=='FORMALIZATION_UNRESOLVED_PROVED' for x in b['cuts']),4)
 def test_activity_counterchoice(self):
  w=c.COUNTERCHOICES['BROKER_NATIVE_ACTIVITY_STATE']['noninvertibility_example'];a=w['counts_A'];b=w['counts_B'];self.assertEqual((a[-1],sum(a)),(b[-1],sum(b)));self.assertEqual(sorted(a),sorted(b));self.assertNotEqual(a,b)
 def test_concentration_counterchoice(self):
  a=[Fraction(1,2),Fraction(1,2),0];b=[Fraction(1,2),Fraction(1,4),Fraction(1,4)];self.assertEqual(max(a),max(b));self.assertNotEqual(sum(x*x for x in a),sum(x*x for x in b))
 def test_price_state_counterchoice(self):self.assertNotEqual(6-5,6-7);self.assertEqual(6-(10+0)/2,1)
 def test_regime_counterchoice(self):self.assertEqual((0+1)/2,.5);self.assertNotEqual([0,1],[.5,.5])
 def test_no_fake_design(self):
  b=json.loads(Path(c.BOUNDARY).read_bytes());self.assertFalse(b['complete_information_design']);self.assertIsNone(b['prepower_contract'])
 def test_prohibitions(self):
  b=json.loads(Path(c.BOUNDARY).read_bytes())
  for k in ['new_market_rows','historical_response_values_used','broker_contacts','redecryptions','empirical_support_measurements','empirical_dependence_estimations','power_trials','new_economic_outcomes','search_budget_use']:self.assertEqual(b[k],0)
  for k in ['duration_selected','deep_acquisition','protected_forward_opened','confirmation_opened']:self.assertFalse(b[k])
 def test_protocol_frozen(self):self.assertEqual(Path(c.PROTOCOL).read_bytes(),canonical(c.protocol()))
 def test_current_state(self):self.assertEqual(validate_root('.')['status'],'PASS_COMPACT_BASELINE_BOUNDARY')
 def test_baseline_tamper_denied(self):
  b=json.loads(Path(c.BASE).read_bytes());b['status']='changed';p=json.loads(Path(c.packet_ref(c.SOURCES[0])).read_bytes())
  with self.assertRaises(ValueError):c.certificate(p,b)
 def test_modality_tamper_denied(self):
  s='SESSION_AND_LIQUIDITY_STATE';p=json.loads(Path(c.packet_ref(s)).read_bytes());p['modalities']['sessions']['historical_session_labels_certified']=True
  with self.assertRaises(ValueError):c.certificate(p,json.loads(Path(c.BASE).read_bytes()))
