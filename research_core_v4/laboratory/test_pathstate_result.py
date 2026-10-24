import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_pathstate_result import ROOT,verify
class PathStateOriginalResultTests(unittest.TestCase):
    def test_original_result_is_preserved_without_decrypting_or_rerunning(self):
        v=verify();self.assertEqual(v['disposition'],'GROSS_FAIL')
        self.assertEqual(v['training_forecast_signal_episode_ledgers_reconciled'],1576)
        self.assertFalse(v['decrypted']);self.assertFalse(v['economic_rerun']);self.assertEqual(v['orders'],0)
    def test_corruption_source_and_false_promotion_refused(self):
        for mode in ('part','receipt','source','promotion','disposition','erratum'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'result';shutil.copytree(ROOT,root)
                if mode=='part':(root/'part-00.b64').write_text('AAAA')
                elif mode=='receipt':(root/'receipt.json').write_text('{}')
                else:
                    p=root/'MANIFEST.json';m=json.loads(p.read_bytes())
                    if mode=='source':m['source_commit']='0'*40
                    elif mode=='promotion':m['economic_edge_confirmed']=True
                    elif mode=='disposition':m['disposition']='REFERENCE_SCREEN_SURVIVOR_UNCONFIRMED'
                    else:m['erratum']=''
                    p.write_text(json.dumps(m))
                with self.assertRaises(ValueError):verify(root)
