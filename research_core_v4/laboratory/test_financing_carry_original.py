"""Original custody bytes only; no decryption, broker, or model invocation."""
import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_financing_carry_result import ROOT,verify
class Originals(unittest.TestCase):
 def test_original_authenticated_chain(self):
  r=verify();self.assertEqual(r['source_rows'],1576);self.assertEqual(r['orders'],0);self.assertFalse(r['economic_rerun']);self.assertFalse(r['source_decrypted']);self.assertFalse(r['net_edge_proven'])
 def test_source_result_public_receipt_and_favorable_manifest_tampering_rejected(self):
  for relative in ('source/part-00.b64','result-artifact.zip.b64','receipt.json','MANIFEST.json'):
   with tempfile.TemporaryDirectory() as d:
    root=Path(d)/'copy';shutil.copytree(ROOT,root);p=root/relative
    if relative=='MANIFEST.json':
     m=json.loads(p.read_bytes());m['net_edge_proven']=True;p.write_text(json.dumps(m))
    elif relative=='receipt.json':
     r=json.loads(p.read_bytes());r['net_edge_proven']=True;p.write_text(json.dumps(r))
    else:
     b=p.read_bytes();p.write_bytes((b'A' if b[:1]!=b'A' else b'B')+b[1:])
    with self.assertRaises(ValueError):verify(root)
 def test_linked_original_part_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'copy';shutil.copytree(ROOT,root);p=root/'source/part-00.b64';original=p.read_bytes();external=Path(d)/'external';external.write_bytes(original);p.unlink();p.symlink_to(external)
   with self.assertRaises(ValueError):verify(root)
