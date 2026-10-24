import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from .ctrader_cli_metadata import EXPECTED,metadata_contract,worker,no_external_routes
from .install_pinned_ctrader_cli import extract
class NativeMetadataBoundaryTests(unittest.TestCase):
    def test_generic_help_or_incomplete_parameters_cannot_be_reception(self):
        for text in ('cTrader CLI 5.9.0 metadata <path>', ' '.join(EXPECTED[:-1]),' '.join(x+'Suffix' for x in EXPECTED)):
            with self.assertRaises(ValueError):metadata_contract(text)
        self.assertEqual(metadata_contract(' '.join(EXPECTED)),list(EXPECTED))
    def test_empty_header_and_blank_route_tables_are_not_external_routes(self):
        for text in ('','\n','Iface Destination Gateway Flags RefCnt Use Metric Mask\n','Iface Destination Gateway Flags RefCnt Use Metric Mask\n\n'):
            self.assertEqual(no_external_routes(text),0)
        for text in ('eth0 00000000 01010101 0003 0 0 0 00000000\n','unparseable'):
            with self.assertRaises(ValueError):no_external_routes(text)
    def test_host_namespace_worker_never_executes_vendor(self):
        with patch('subprocess.run') as invoked:
            with self.assertRaisesRegex(ValueError,'NETWORK_NAMESPACE_AND_NONROOT'):
                worker('/does/not/run','/not/an/algo','metadata',os.readlink('/proc/self/ns/net'),os.getuid())
            invoked.assert_not_called()
    def test_unpinned_download_cannot_be_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'wrong.tar.gz';raw.write_bytes(b'not a pinned release')
            with self.assertRaisesRegex(ValueError,'VENDOR_TARBALL_PIN'):extract(raw,Path(tmp)/'unpacked')
            self.assertFalse((Path(tmp)/'unpacked').exists())
