import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from research_core_v4 import encrypted_transport_segments_v1 as t
class SegmentTests(unittest.TestCase):
 def fixture(self,root):
  parts=[]
  for i in range(69):
   b=bytes([i])*262144 if i<68 else b'end'
   p=f'research_core_v4/runtime_inputs/transport_segments/chunk-{i:03d}.bin'
   f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
   parts.append(dict(path=p,size_bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),git_blob_sha=hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()))
  data=b''.join((root/p['path']).read_bytes() for p in parts)
  return dict(schema='mxm.v4.exact-encrypted-payload-segments.v1',payload_sha256=hashlib.sha256(data).hexdigest(),payload_size_bytes=len(data),parts=parts),data
 def test_integrity_and_rejections(self):
  for mode in ['valid','corrupt','missing','reordered','wrong_total','wrong_git_sha']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
    root=Path(d);index,data=self.fixture(root)
    with patch.object(t,'SHA',index['payload_sha256']),patch.object(t,'SIZE',len(data)):
     if mode=='corrupt': (root/index['parts'][0]['path']).write_bytes(b'x'*262144)
     if mode=='missing': (root/index['parts'][1]['path']).unlink()
     if mode=='reordered': index['parts'][0],index['parts'][1]=index['parts'][1],index['parts'][0]
     if mode=='wrong_total': index['payload_size_bytes']+=1
     if mode=='wrong_git_sha': index['parts'][0]['git_blob_sha']='0'*40
     if mode=='valid':
      t.reconstruct(root,index);self.assertEqual((root/t.PAYLOAD).read_bytes(),data)
      with self.assertRaises(AssertionError):t.reconstruct(root,index)
     else:
      with self.assertRaises((AssertionError,FileNotFoundError)):t.reconstruct(root,index)
      self.assertFalse((root/t.PAYLOAD).exists())
