import hashlib,io,tempfile,time,unittest
from pathlib import Path
from . import download_pinned_ctrader_cli as d
class Response(io.BytesIO):
    status=206
    def __init__(self,raw,**headers):
        super().__init__(raw);self.headers={'Content-Range':f'bytes 5-7/{d.SIZE}','Content-Length':'3',**headers}
class PinnedDownloadTests(unittest.TestCase):
    def test_exact_range_and_no_invented_bytes(self):
        self.assertEqual(d.read_part(Response(b'abc'),5,7,time.monotonic()+10),b'abc')
        for response in (Response(b'ab'),Response(b'abcd'),Response(b'abc',**{'Content-Range':f'bytes 4-6/{d.SIZE}'}),
                         Response(b'abc',**{'Content-Length':'4'}),Response(b'abc',**{'Content-Encoding':'gzip'})):
            with self.subTest(response=response),self.assertRaises(ValueError):d.read_part(response,5,7,time.monotonic()+10)
    def test_ignored_range_rejected_before_body(self):
        response=Response(b'abc');response.status=200
        with self.assertRaises(ValueError):d.read_part(response,5,7,time.monotonic()+10)
        self.assertEqual(response.tell(),0)
    def test_deadline_prevents_body_read(self):
        response=Response(b'abc')
        with self.assertRaises(ValueError):d.read_part(response,5,7,time.monotonic()-1)
        self.assertEqual(response.tell(),0)
    def test_hash_length_order_corruption_never_publishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'vendor';digest=hashlib.sha256(b'abcdef').hexdigest()
            for parts in ([b'abc',b'defg'],[b'def',b'abc'],[b'abc'],[b'abx',b'def']):
                with self.assertRaises(ValueError):d.publish(out,parts,6,digest)
                self.assertFalse(out.exists());self.assertFalse(out.with_name('vendor.partial').exists())
            d.publish(out,[b'abc',b'def'],6,digest);self.assertEqual(out.read_bytes(),b'abcdef')
            with self.assertRaises(ValueError):d.publish(out,[b'abc',b'def'],6,digest)
            self.assertEqual(out.read_bytes(),b'abcdef')
if __name__=='__main__':unittest.main()
