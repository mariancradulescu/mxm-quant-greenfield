import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_native_cli_metadata import ROOT,verify
class NativeCliOriginalEvidenceTests(unittest.TestCase):
    def test_actual_native_package_and_output_without_platform_execution(self):
        result=verify();self.assertTrue(result['native_package_metadata_accepted'])
        self.assertFalse(result['native_operational_accepted']);self.assertFalse(result['cli_executed_by_verifier'])
        self.assertEqual(result['explicit_native_defaults_verified'],10)
    def test_corruption_provenance_and_promoted_claim_refused(self):
        for mode in ('part','receipt','metadata','source','promotion','framework'):
            with tempfile.TemporaryDirectory() as tmp:
                target=Path(tmp)/'evidence';shutil.copytree(ROOT,target)
                if mode=='part':(target/'part-00.b64').write_text('AAAA')
                elif mode=='receipt':(target/'receipt.json').write_text('{}')
                elif mode=='metadata':(target/'metadata.stdout.txt').write_text('{}')
                else:
                    path=target/'MANIFEST.json';m=json.loads(path.read_bytes())
                    if mode=='source':m['pr_source_head']='0'*40
                    elif mode=='framework':m['net8_packaging_accepted']=True
                    else:m['native_operational_accepted']=True
                    path.write_text(json.dumps(m))
                with self.subTest(mode=mode),self.assertRaises(ValueError):verify(target)
