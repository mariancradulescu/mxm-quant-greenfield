"""Reproduce actual cleanup masking correct CAS; artificial transport only."""
import os,subprocess,tempfile,unittest
from unittest.mock import Mock,patch
from .custody import CASRefused,publication_directory,writer_git_environment

class NativeGitCleanup(unittest.TestCase):
    def test_pack_cleanup_cannot_replace_original_cas_refusal(self):
        directory=Mock();directory.name='/artificial-publication-only'
        directory.cleanup.side_effect=OSError(39,'Directory not empty','pack')
        original=CASRefused('a'*40,'b'*40,'c'*40,'exact artificial reply')
        with patch('research_core_v4.laboratory.custody.tempfile.TemporaryDirectory',return_value=directory):
            with self.assertRaises(CASRefused) as caught:
                with publication_directory():raise original
            self.assertIs(caught.exception,original)
            # A separate cleanup failure after normal completion remains an error.
            with self.assertRaises(OSError):
                with publication_directory():pass
    def test_real_git_disables_both_automatic_maintenance_paths(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=True):
            env=writer_git_environment({'token':'ARTIFICIAL_TEST_TOKEN'})
            subprocess.run(['git','init','-q',folder],env=env,check=True)
            for key,expected in [('gc.auto','0'),('maintenance.auto','false')]:
                self.assertEqual(subprocess.check_output(['git','config','--get',key],cwd=folder,env=env,text=True).strip(),expected)

if __name__=='__main__':unittest.main()
