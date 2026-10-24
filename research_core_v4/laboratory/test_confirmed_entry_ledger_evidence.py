import copy,json,shutil,tempfile,unittest
from pathlib import Path
from .confirmed_entry_ledger_checks import check
from .verify_confirmed_entry_ledger_result import verify,ARCHIVE
class OriginalConfirmedEntryEvidenceTests(unittest.TestCase):
    def test_exact_originals_validate_without_native_execution(self):
        result=verify()
        self.assertEqual(result['original_archives_verified'],2)
        self.assertFalse(result['hard21_proven']);self.assertFalse(result['cli_executed'])
        self.assertFalse(result['native_storage_reception'])
    def test_corruption_false_promotion_and_provenance_fail(self):
        for mode in ('part','proof','source','promotion'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                target=Path(tmp)/'archive';shutil.copytree(ARCHIVE,target)
                if mode=='part':(target/'ledger-00.b64').write_text('AAAA')
                elif mode=='proof':(target/'proof.json').write_text('{}')
                else:
                    path=target/'MANIFEST.json';m=json.loads(path.read_bytes())
                    if mode=='source':m['pr_test_merge']='0'*40
                    else:m['hard21_proven']=True
                    path.write_text(json.dumps(m))
                with self.assertRaises(ValueError):verify(target)
    def test_independent_calendar_counter_and_barrier_refuse_false_receipts(self):
        original=json.loads((ARCHIVE/'proof.json').read_bytes())
        for mode in ('promotion','count','week','digest','barrier'):
            bad=copy.deepcopy(original)
            if mode=='promotion':bad['hard21_proven']=True
            elif mode=='count':bad['contracts']['weeks'][0]['ConfirmedProtectedEntries']+=1
            elif mode=='week':bad['contracts']['weeks'][0]['IsoWeek']='2021-W53'
            elif mode=='digest':bad['contracts']['journal']['Payload']+=' '
            else:bad['cases'][1]['restart_admitted']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):check(bad)
