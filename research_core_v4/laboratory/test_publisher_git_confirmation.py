"""Real local Git publication with deliberately stale REST metadata.

Artificial App scope/URL adapter only; no native reception or credentials.
"""
import os
from pathlib import Path
import subprocess,tempfile,unittest
from unittest.mock import patch
from . import custody,runtime

class PublisherGitConfirmation(unittest.TestCase):
    def exercise(self,lose_ack):
        original_run=subprocess.run
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);remote=root/'remote';work=root/'seed';work.mkdir()
            def git(directory,*args):
                return subprocess.check_output(['git',*args],cwd=directory,stderr=subprocess.DEVNULL).decode().strip()
            git(root,'init','--bare','-q',str(remote));git(work,'init','-q');git(work,'config','user.name','Artificial local test');git(work,'config','user.email','test@example.invalid')
            (work/'base').write_text('ARTIFICIAL_ONLY');git(work,'add','.');git(work,'commit','-qm','base');parent=git(work,'rev-parse','HEAD')
            git(work,'push',str(remote),'HEAD:refs/heads/'+runtime.EVIDENCE_BRANCH)
            pushes=[]
            def adapted_run(args,*a,**kw):
                if args[:4]==['git','remote','add','origin']:args=[*args[:4],str(remote)]
                if args[:2]==['git','push']:pushes.append(list(args))
                return original_run(args,*a,**kw)
            class StaleREST:
                def json(self,path):return {'object':{'sha':parent}}
            env={'GITHUB_JOB':'durable-archive','LAB_SOURCE_SHA':'a'*40,'GH_TOKEN':'ARTIFICIAL_READ_TOKEN'}
            if lose_ack:env['LAB_FAULT_ACK']='AFTER_PUSH'
            scope={'source':'a'*40,'job':'durable-archive','operation':'publish','token':'ARTIFICIAL_APP_TOKEN','guard':lambda:None}
            raw=b'ARTIFICIAL_EXACT_BYTES\n';path='typed-successor/transport-fixture/receipt.json'
            def read_remote(route,p,oid):
                return subprocess.check_output(['git','--git-dir='+str(remote),'show',oid+':'+p])
            with patch.dict(os.environ,env,clear=True),patch.object(custody,'_NATIVE_WRITER_SCOPE',scope), \
                 patch.object(custody.subprocess,'run',side_effect=adapted_run), \
                 patch.object(runtime,'file_at',side_effect=read_remote):
                commit=custody.atomic_publish(StaleREST(),parent,{path:raw},'Artificial strong Git ref confirmation')
            self.assertEqual(git(remote,'rev-parse','refs/heads/'+runtime.EVIDENCE_BRANCH),commit)
            self.assertEqual(read_remote(None,path,commit),raw);self.assertEqual(len(pushes),1)
    def test_success_uses_native_git_ref_when_rest_stays_at_parent(self):self.exercise(False)
    def test_lost_ack_verifies_remote_bytes_without_second_push(self):self.exercise(True)

if __name__=='__main__':unittest.main()
