import json,shutil,tempfile,unittest
from pathlib import Path
from discovery.ledger import append_entry,read_ledger
ROOT=Path(__file__).resolve().parents[1]
OPENED=("V2-C017","V2-C018","V2-C019","V2-C020")
TIMES={
 "V2-C017":"2026-09-22T10:43:11Z",
 "V2-C018":"2026-09-22T10:43:17Z",
 "V2-C019":"2026-09-22T10:44:12Z",
 "V2-C020":"2026-09-22T10:44:14Z",
}
HASHES={
 "V2-C017":"9870baf130d12e9864489c6d0ebe83a80b4fa3a38f1b2c5321ac03e1dc64029b",
 "V2-C018":"f1a647f633d46d26dfa2b9d971b72e4bf3c53dd4eef9971ed0503cd2018fe69c",
 "V2-C019":"65cf8e6358da6f304cce53a9f3ec3abfb922525c8de2f2a59ca0ce1fe637e9c6",
 "V2-C020":"28b9fac70c1b39e7d782103324327c5c6249452868293c5a9bcc4fa137a7b8c2",
}
class UltraFastPostOutcomeReconciliationTests(unittest.TestCase):
 def test_01_existing_result_files_are_exact_and_remaining_two_unopened(self):
  for cid in OPENED:
   r=json.loads((ROOT/'discovery/results'/f'{cid}_STAGE_A_V1.json').read_text())
   self.assertEqual(r['candidate_id'],cid);self.assertEqual(r['result_hash'],HASHES[cid])
  for cid in ('V2-C021','V2-C022'):self.assertFalse((ROOT/'discovery/results'/f'{cid}_STAGE_A_V1.json').exists())
 def test_02_generate_append_only_result_authority_without_recomputing_economics(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'ledger.jsonl';shutil.copyfile(ROOT/'discovery/ledger.jsonl',p)
   self.assertEqual(len(read_ledger(p)),32)
   for cid in OPENED:
    r=json.loads((ROOT/'discovery/results'/f'{cid}_STAGE_A_V1.json').read_text())
    append_entry(p,entry_type='RESULT_RECORDED',candidate_id=cid,spec_hash=r['spec_hash'],payload={'result':r,'result_hash':r['result_hash']},timestamp_utc=TIMES[cid])
   lines=p.read_text().splitlines();entries=read_ledger(p)
   self.assertEqual(len(entries),36);self.assertEqual([e['candidate_id'] for e in entries[-4:]],list(OPENED))
   for line in lines[-4:]:print('RECONCILE_LINE::'+line)
if __name__=='__main__':unittest.main()
