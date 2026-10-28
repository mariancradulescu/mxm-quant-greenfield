import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_peer_residual_result import ROOT,verify
class Originals(unittest.TestCase):
 def test_original_authentic_outcome_keeps_failed_censor_and_temporal_gates(self):
  r=verify();self.assertEqual(r['disposition'],'DATA_LIMITED');self.assertFalse(r['gates']['censor_fraction_at_most_5pct']);self.assertFalse(r['gates']['all_three_source_blocks_above_5bps']);self.assertFalse(r['economic_rerun'])
 def test_favorable_verdict_receipt_or_archive_mutation_rejected(self):
  for relative in ('MANIFEST.json','receipt.json','artifact/part-00.b64'):
   with tempfile.TemporaryDirectory() as d:
    root=Path(d)/'copy';shutil.copytree(ROOT,root);p=root/relative
    if relative.endswith('.json'):
     x=json.loads(p.read_bytes());x['disposition']='CONFIRMED_EDGE';p.write_text(json.dumps(x))
    else:
     b=p.read_bytes();p.write_bytes((b'A' if b[:1]!=b'A' else b'B')+b[1:])
    with self.assertRaises(ValueError):verify(root)
 def test_symlinked_original_part_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'copy';shutil.copytree(ROOT,root);p=root/'artifact/part-00.b64';external=Path(d)/'external';external.write_bytes(p.read_bytes());p.unlink();p.symlink_to(external)
   with self.assertRaises(ValueError):verify(root)
