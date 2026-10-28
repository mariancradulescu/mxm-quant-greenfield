import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_displayed_financing_result import ROOT,verify
class Originals(unittest.TestCase):
 def test_original_unit_ledger_linked_to_exact_original_native_metadata_source(self):
  r=verify();self.assertEqual(r['rows'],1576);self.assertFalse(r['unit_calculation_rerun']);self.assertFalse(r['market_account_replay']);self.assertEqual(r['new_broker_requests'],0)
 def test_changed_zip_public_receipt_or_favorable_manifest_rejected(self):
  for relative in ('artifact/part-00.b64','receipt.json','MANIFEST.json'):
   with tempfile.TemporaryDirectory() as d:
    root=Path(d)/'copy';shutil.copytree(ROOT,root);p=root/relative
    if relative.endswith('.json'):
     x=json.loads(p.read_bytes());x['actual_broker_charges_proven']=True;p.write_text(json.dumps(x))
    else:
     b=p.read_bytes();p.write_bytes((b'A' if b[:1]!=b'A' else b'B')+b[1:])
    with self.assertRaises(ValueError):verify(root)
 def test_linked_original_part_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'copy';shutil.copytree(ROOT,root);p=root/'artifact/part-00.b64';outside=Path(d)/'outside';outside.write_bytes(p.read_bytes());p.unlink();p.symlink_to(outside)
   with self.assertRaises(ValueError):verify(root)
