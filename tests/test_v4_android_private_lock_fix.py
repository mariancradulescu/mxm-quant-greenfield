"""Offline Android ENOSYS regression and real cross-process exclusion."""
import errno
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from research_core_v4.pydroid_quote_probe_v1 import acquire_device_lock,release_device_lock,claim_device_execution,PLAN_SHA

CHILD = '''
import sys
from pathlib import Path
from research_core_v4.pydroid_quote_probe_v1 import acquire_device_lock,release_device_lock
try:
 l=acquire_device_lock(Path(sys.argv[1]))
except BlockingIOError:
 print('BLOCKED');sys.exit(23)
release_device_lock(l);print('ACQUIRED')
'''

class PrivateLockTests(unittest.TestCase):
 def test_second_lock_in_same_process_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   l=acquire_device_lock(Path(d))
   try:
    with self.assertRaises(BlockingIOError):acquire_device_lock(Path(d))
    self.assertEqual(self.child(d).returncode,23)
   finally:release_device_lock(l)
   l=acquire_device_lock(Path(d));release_device_lock(l)
 def child(self,private):
  return subprocess.run([sys.executable,'-c',CHILD,str(private)],capture_output=True,text=True,timeout=10)
 def test_flock_enosys_does_not_disable_protection(self):
  with tempfile.TemporaryDirectory() as d,patch('fcntl.flock',side_effect=OSError(errno.ENOSYS,'synthetic Android')):
   l=acquire_device_lock(Path(d))
   try:self.assertEqual(self.child(d).returncode,23)
   finally:release_device_lock(l)
   self.assertEqual(self.child(d).returncode,0)
 def test_claim_keeps_run_lock_held(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'private';root=Path(d)/'deploy';l=acquire_device_lock(p)
   try:
    claim_device_execution(p,root,{},held_lock=l)
    self.assertEqual(self.child(p).returncode,23)
   finally:release_device_lock(l)
 def test_resume_preserves_binding_and_rejects_second_folder(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'private';root=Path(d)/'deploy'
   claim_device_execution(p,root,{})
   registry=p/('v4_probe_'+PLAN_SHA+'.json');before=registry.read_bytes()
   claim_device_execution(p,root,{})
   self.assertEqual(before,registry.read_bytes())
   with self.assertRaises(PermissionError):claim_device_execution(p,Path(d)/'other',{})
   self.assertEqual(before,registry.read_bytes())
 def test_unsupported_posix_lock_fails_closed(self):
  with tempfile.TemporaryDirectory() as d,patch('fcntl.lockf',side_effect=OSError(errno.ENOSYS,'synthetic unsupported')):
   with self.assertRaises(OSError):claim_device_execution(Path(d),Path(d)/'deploy',{})
   self.assertFalse((Path(d)/('v4_probe_'+PLAN_SHA+'.json')).exists())
 def test_unsupported_lock_stops_before_oauth_or_transport(self):
  from research_core_v4.pydroid_quote_probe_v1 import run_device
  with tempfile.TemporaryDirectory() as d,patch('research_core_v4.pydroid_quote_probe_v1.verify',return_value=({},{})),patch('fcntl.lockf',side_effect=OSError(errno.ENOSYS,'synthetic unsupported')):
   private=Path(d)/'private'
   oauth=SimpleNamespace(APP_CONFIG_PATH=private/'credentials.json')
   calls=[]
   with self.assertRaises(OSError):run_device(Path(d)/'deploy',oauth=oauth,transport_factory=lambda:calls.append('FORBIDDEN'),progress=lambda _:None)
   self.assertEqual(calls,[])
   self.assertFalse((private/('v4_probe_'+PLAN_SHA+'.json')).exists())
   self.assertFalse((Path(d)/'deploy/DEVICE_LOCAL_PROBE_RAW').exists())
 def test_killed_process_releases_kernel_lock(self):
  with tempfile.TemporaryDirectory() as d:
   code="from pathlib import Path;from research_core_v4.pydroid_quote_probe_v1 import acquire_device_lock;import sys,time;l=acquire_device_lock(Path(sys.argv[1]));print('READY',flush=True);time.sleep(30)"
   p=subprocess.Popen([sys.executable,'-c',code,d],stdout=subprocess.PIPE,text=True)
   try:
    self.assertEqual(p.stdout.readline().strip(),'READY')
    self.assertEqual(self.child(d).returncode,23)
   finally:p.kill();p.wait(timeout=5);p.stdout.close()
   self.assertEqual(self.child(d).returncode,0)
 def test_lock_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   target=Path(d)/'other';target.touch()
   (Path(d)/('v4_probe_'+PLAN_SHA+'.lock')).symlink_to(target)
   with self.assertRaises(PermissionError):acquire_device_lock(Path(d))

if __name__=='__main__':unittest.main()
