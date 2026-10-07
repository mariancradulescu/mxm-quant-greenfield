"""Protocol parity on synthetic validity masks only, plus hostile ingress cases."""
import unittest, tempfile, io, json, ast
from pathlib import Path
import numpy as np
from research_core_v4.current_wave_support_worker_v1 import *
class Parity(unittest.TestCase):
 def test_windows(self):
  rng=np.random.default_rng(731);bits=rng.integers(0,32,G,dtype=np.uint8);bits[:100]=31;m=own_masks(bits)
  for source in SOURCES:
   for h in ([12] if source==SOURCES[4] else [1,12]):
    for k in [0,1,11,12,15,23,24,25,35,36,47,48,71,72,100,8039,8052,8063]:
     if source==SOURCES[4] and k%12:continue
     w=required_windows(source,START+k*300,h)
     B=all(START<=x<END and int(bits[(x-START)//300])&7==7 for x in w['baseline'])
     self.assertEqual(bool(m['B'][k]),B)
     lo=np.array([(w['feature'][0]-START)//300]);hi=np.array([(w['feature'][-1]-START)//300+1])
     want=all(START<=x<END and bits[(x-START)//300]&7==7 for x in w['feature'])
     self.assertEqual(bool(window(m['v'],lo,hi)[0]),want)
 def test_projection(self):
  r={'time_utc':'2026-08-20T00:00:00Z','open':'1.00','high':'1.00','low':'1.00','close':'1.00','tick_volume':'0'}
  self.assertEqual(project(r,1,2),(0,31));r['open']='0.00';r['low']='0.00';self.assertEqual(project(r,1,2),(0,23))
 def test_invalid_ohlc_boolean(self):
  r={'time_utc':'2026-08-20T00:00:00Z','open':'3.00','high':'2.00','low':'1.00','close':'1.00','tick_volume':'0'}
  self.assertEqual(project(r,1,2)[1]&OHLC,0)
 def test_invalid_count_boolean(self):
  r={'time_utc':'2026-08-20T00:00:00Z','open':'1.00','high':'1.00','low':'1.00','close':'1.00','tick_volume':'-1'}
  self.assertEqual(project(r,1,2)[1]&COUNT,0)
 def test_forward_fail_before_masks(self):
  with self.assertRaisesRegex(SupportError,'PROTECTED_FORWARD'):project({'time_utc':'2026-09-17T12:05:00Z','open':'1.00','high':'1.00','low':'1.00','close':'1.00','tick_volume':'0'},4,2)
 def test_grid_fail(self):
  with self.assertRaisesRegex(SupportError,'OUT_OF_GRID'):project({'time_utc':'2026-08-20T00:00:01Z','open':'1.00','high':'1.00','low':'1.00','close':'1.00','tick_volume':'0'},1,2)
 def test_no_availability_substitution(self):
  r={'time_utc':'2026-08-20T00:00:00Z','open':'1.00','high':'1.00','low':'1.00','close':'1.00','tick_volume':'0','original_available_at':'2026-08-20T00:05:00Z'}
  with self.assertRaisesRegex(SupportError,'INVALID_SCHEMA'):project(r,1,2)
 def test_mask_reducer_peers_frozen(self):
  roster=[{'SYMBOL_ID':i,'MASTER_ORDINAL':i+1,'BROKER_NATIVE_CONTEXT':'context'} for i in range(3)]
  bits=np.full((3,G),31,np.uint8);bits[1,100]=1
  with tempfile.TemporaryDirectory() as td:
   s,g=derive(bits,roster,td)
   records=s['per_candidate_identity_context_horizon'];self.assertEqual(len(records),27)
   self.assertTrue(all(x['causal_pass_count']==0 and x['causal_unknown_count']==x['potential_event_count'] for x in records))
   p=np.load(Path(td)/'event_masks.npz');key=SOURCES[3]+'__1__feature';feature=np.unpackbits(p[key][0],bitorder='little')[:G]
   # Missing peer future at 100 cannot change feature peer set at t=100.
   self.assertTrue(feature[100]);self.assertEqual(g['layers']['causal_certified_joint']['node_count'],0)
 def test_graph_vector_parity(self):
  g=CalendarGraph();g.add(np.array([True,True,False]),np.array([0,280,600]),np.array([2,300,900]),np.array([3,21,301]))
  d=g.result();self.assertEqual(d['node_count'],2);self.assertEqual(d['connected_component_count'],1);self.assertEqual(d['cross_midnight_incidence_count'],1)
 def test_no_forbidden_calculation(self):
  tree=ast.parse(Path('research_core_v4/current_wave_support_worker_v1.py').read_text())
  names={n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,(ast.Name,ast.Attribute))}
  self.assertFalse(names&{'log','sqrt','corrcoef','cov','polyfit','lstsq','regress','mean'})
 def test_stream_ingress(self):
  from research_core_v4.current_wave_support_machine_v1 import project_stream
  item={'ordinal':1,'symbol_id':3,'classification':'SHALLOW_SUPPORT_COMPLETE','request_count':1,'retry_count':0,'page_cap_hits':0,'failure':None,'transport_geometry_pages':[],'rows':[{'time_utc':'2026-08-20T00:00:00Z','open':'1.00','high':'1.00','low':'1.00','close':'1.00','tick_volume':'0'}]}
  raw=canonical({'schema':'mxm.v4.shallow-m5-v2.raw-shard.v1','segment_index':1,'shard_index':0,'identity_range':[1,1],'items':[item]})
  e={'master_ordinal_range':[1,1],'segment_index':1,'shard_index':0,'canonical_row_count_metadata':1,'plaintext_canonical_sha256':sha(raw),'encrypted_sha256':'a'*64,'asset_id':1,'name':'synthetic','encrypted_bytes':1}
  bits,a=project_stream(io.BytesIO(raw),e,[{'symbol_id':3}],{3:2},{1:0});self.assertEqual(bits[0,0],31);self.assertEqual(a['rows_streamed'],1)
  e['plaintext_canonical_sha256']='b'*64
  with self.assertRaisesRegex(SupportError,'PLAINTEXT_CANONICAL_SHA256'):project_stream(io.BytesIO(raw),e,[{'symbol_id':3}],{3:2},{1:0})
class Checkpoints(unittest.TestCase):
 def test_binding(self):
  from research_core_v4.current_wave_support_machine_v1 import verify_checkpoint
  e={'asset_id':1,'name':'synthetic','encrypted_bytes':1,'encrypted_sha256':'a'*64,'plaintext_canonical_sha256':'b'*64,'canonical_row_count_metadata':0}
  a={'asset_id':1,'asset_name':'synthetic','encrypted_bytes':1,'encrypted_sha256':'a'*64,'plaintext_canonical_sha256':'b'*64,'rows_streamed':0,'mask_sha256':'c'*64,'plaintext_discarded_before_checkpoint':True}
  verify_checkpoint([a],[e]);a['asset_id']=2
  with self.assertRaisesRegex(SupportError,'CHECKPOINT_PUBLIC_BINDING'):verify_checkpoint([a],[e])
 def test_recovery_without_double_count(self):
  from research_core_v4.current_wave_support_machine_v1 import verify_checkpoint
  verify_checkpoint([],[])
  with self.assertRaisesRegex(SupportError,'CHECKPOINT_INVENTORY'):verify_checkpoint([{}]*101,[])
 def test_arm_rejects_wrong_preflight_hash_before_network(self):
  from unittest.mock import patch
  import research_core_v4.current_wave_support_machine_v1 as m
  f,route,roster=m.bound()
  with tempfile.TemporaryDirectory() as td:
   pf=Path(td)/'preflight.json';pf.write_text('{}')
   arm=Path(td)/'arm.json';arm.write_bytes(canonical({'scope':'SUPPORT_ONLY','implementation_freeze_sha256':sha(Path(m.FREEZE).read_bytes()),'assets':route['assets'],'roster':roster,'protected_forward_boundary':'2026-09-17T12:02:58Z','preflight_ref':str(pf),'preflight_sha256':'0'*64}))
   with patch.object(m,'ARM',str(arm)),patch.object(m,'api',side_effect=AssertionError('NETWORK_FORBIDDEN')):
    with self.assertRaisesRegex(SupportError,'PREFLIGHT_HASH_BINDING'):m.execute()
TEST_COUNT=14
def run_tests():
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__,fromlist=["*"])))
 need(result.wasSuccessful() and result.testsRun==TEST_COUNT,'SYNTHETIC_PROTOCOL_PARITY')
if __name__=='__main__':run_tests()
