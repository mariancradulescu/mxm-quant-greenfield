import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_support_topology_result import ROOT,verify
class Original(unittest.TestCase):
 def test_exact_original_with_no_strategy_cost_or_signal_qualification(self):
  r=verify();self.assertEqual(r['cells_reconciled'],18912)
  self.assertEqual(r['unselected_grid_flags'],{'1':False,'12':False,'288':False})
  self.assertFalse(r['net_edge_proven']);self.assertFalse(r['source_decrypted'])
  self.assertEqual(r['new_strategy_identities'],0)
 def test_corrupted_cipher_bundle_public_copy_and_false_promotion_rejected(self):
  for relative in ('bundle/part-00.b64','receipt.json','MANIFEST.json'):
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'copy';shutil.copytree(ROOT,p)
    if relative=='bundle/part-00.b64':
     f=p/relative;b=f.read_bytes();f.write_bytes(b'A'+b[1:])
    else:
     f=p/relative;r=json.loads(f.read_bytes());r['net_edge_proven']=True;f.write_text(json.dumps(r))
    with self.assertRaises(ValueError):verify(p)
 def test_symlink_bundle_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'copy';shutil.copytree(ROOT,p);shutil.rmtree(p/'bundle');(p/'bundle').symlink_to(ROOT/'bundle',target_is_directory=True)
   with self.assertRaises(ValueError):verify(p)
