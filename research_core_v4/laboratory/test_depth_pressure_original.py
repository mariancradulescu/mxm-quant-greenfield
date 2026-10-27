import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_depth_pressure_result import ROOT,verify
class Originals(unittest.TestCase):
 def test_originals_actual_evaluator_and_terminal_dependent_result(self):
  r=verify();self.assertEqual(r['disposition'],'DATA_LIMITED');self.assertEqual(r['model_trials'],1);self.assertFalse(r['source_decrypted']);self.assertFalse(r['economic_rerun'])
 def test_source_result_receipt_or_favorable_manifest_substitution_is_rejected(self):
  for mode in ('source','result','receipt','promotion'):
   with tempfile.TemporaryDirectory() as td:
    root=Path(td)/'originals';shutil.copytree(ROOT,root)
    if mode=='source':(root/'source/part-00.b64').write_text('AAAA')
    elif mode=='result':(root/'result-artifact.zip.b64').write_text('AAAA')
    elif mode=='receipt':(root/'receipt.json').write_text('{}')
    else:
     p=root/'MANIFEST.json';m=json.loads(p.read_bytes());m['net_edge_proven']=True;p.write_text(json.dumps(m))
    with self.subTest(mode=mode),self.assertRaises(ValueError):verify(root)
 def test_symbolic_link_is_not_accepted_as_original_artifact(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'originals';shutil.copytree(ROOT,root);p=root/'receipt.json';p.unlink();p.symlink_to(ROOT/'receipt.json')
   with self.assertRaises(ValueError):verify(root)
if __name__=='__main__':unittest.main()
