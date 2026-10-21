"""Real receive-pack race, no credential/network or fabricated success."""
import concurrent.futures
from pathlib import Path
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from .custody import native_cas_rejection

class NativeCASResponse(unittest.TestCase):
    def test_exact_destination_and_old_value_only(self):
        for reason in ('[rejected] (stale info)','[remote rejected] (incorrect old value provided)'):
            row=('!\tHEAD:refs/heads/probe\t'+reason+'\n').encode()
            self.assertTrue(native_cas_rejection(SimpleNamespace(stdout=row),'probe'))
            self.assertFalse(native_cas_rejection(SimpleNamespace(stdout=row),'other'))
            self.assertFalse(native_cas_rejection(SimpleNamespace(stdout=row+row),'probe'))
        for reason in ('[remote rejected] (protected branch hook declined)',
                       '[remote rejected] (failed to update ref)','[rejected] (non-fast-forward)',
                       'fatal: Authentication failed','network failure'):
            self.assertFalse(native_cas_rejection(SimpleNamespace(stdout=('!\tHEAD:refs/heads/probe\t'+reason+'\n').encode()),'probe'))

    def test_real_concurrent_receive_pack_and_stale_advertisement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);remote=root/'remote'
            subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
            def git(d,*args):
                return subprocess.run(['git',*args],cwd=d,capture_output=True,check=True).stdout.decode().strip()
            dirs=[]
            for name in ('A','B'):
                d=root/name;d.mkdir();git(d,'init','-q');git(d,'config','user.name','Local probe')
                git(d,'config','user.email','probe@example.invalid');git(d,'remote','add','origin',str(remote));dirs.append(d)
            (dirs[0]/'base').write_text('base');git(dirs[0],'add','.');git(dirs[0],'commit','-qm','base')
            parent=git(dirs[0],'rev-parse','HEAD');git(dirs[0],'push','-q','origin','HEAD:refs/heads/probe')
            git(dirs[1],'fetch','-q','origin',parent);git(dirs[1],'checkout','-q','--detach','FETCH_HEAD')
            for i,d in enumerate(dirs):
                (d/str(i)).write_text(str(i));git(d,'add','.');git(d,'commit','-qm','candidate')
            barrier=threading.Barrier(2)
            def push(d):
                barrier.wait()
                return subprocess.run(['git','push','--porcelain','--force-with-lease=refs/heads/probe:'+parent,'origin','HEAD:refs/heads/probe'],cwd=d,capture_output=True)
            with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(push,dirs))
            self.assertEqual(sum(r.returncode==0 for r in results),1)
            loser=next(r for r in results if r.returncode)
            self.assertTrue(native_cas_rejection(loser,'probe'),loser.stdout.decode()+loser.stderr.decode())
            winner=git(remote,'rev-parse','refs/heads/probe')
            self.assertEqual(git(remote,'rev-parse',winner+'^'),parent)
            # A subsequent stale lease uses the other explicit response form.
            stale=subprocess.run(['git','push','--porcelain','--force-with-lease=refs/heads/probe:'+parent,'origin','HEAD:refs/heads/probe'],cwd=dirs[results.index(loser)],capture_output=True)
            self.assertNotEqual(stale.returncode,0);self.assertTrue(native_cas_rejection(stale,'probe'))

if __name__=='__main__':unittest.main()
