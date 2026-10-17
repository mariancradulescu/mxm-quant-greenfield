"""Local bare-Git CAS proof, explicit fixture namespace, no network credentials.

This is a test transport, not production exclusivity evidence.
"""
import os
import pathlib
import subprocess
from .continuity import canonical, digest, need

REF='refs/heads/b-continuity-fixture'
def git(folder,*args,data=None,check=True):
    env={k:v for k,v in os.environ.items() if not k.startswith(('GIT_','GH_','GITHUB_','SSH_','SUCCESSOR_','MXM_'))}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',
               GIT_AUTHOR_NAME='MXM B fixture',GIT_COMMITTER_NAME='MXM B fixture',
               GIT_AUTHOR_EMAIL='fixture@example.invalid',GIT_COMMITTER_EMAIL='fixture@example.invalid')
    r=subprocess.run(['git',*args],cwd=folder,env=env,input=data,capture_output=True,timeout=30)
    if check:need(r.returncode==0,'B_LAB_GIT_ERROR')
    return r

class Lab:
    def __init__(self,folder):
        self.folder=pathlib.Path(folder).resolve()
        need(self.folder.name=='b-continuity-fixture.git' and not self.folder.is_symlink(),'B_LAB_NAMESPACE')
    def initialize(self):
        need(not self.folder.exists(),'B_LAB_EXISTS')
        self.folder.mkdir(parents=True);git(self.folder,'init','--bare','-q')
    def head(self):
        r=git(self.folder,'rev-parse','--verify',REF,check=False)
        return r.stdout.decode().strip() if r.returncode==0 else None
    def read(self):
        h=self.head();need(h is not None,'B_LAB_MISSING')
        return h,__import__('json').loads(git(self.folder,'show',h+':state.json').stdout)
    def candidate(self,expected,state):
        blob=git(self.folder,'hash-object','-w','--stdin',data=canonical(state)).stdout.decode().strip()
        tree=git(self.folder,'mktree',data=('100644 blob '+blob+'\tstate.json\n').encode()).stdout.decode().strip()
        args=['commit-tree',tree]+(['-p',expected] if expected else [])
        return git(self.folder,*args,data=b'B isolated fixture\n').stdout.decode().strip()
    def cas(self,expected,state):
        candidate=self.candidate(expected,state)
        # update-ref old-value locking exercises Git's atomic expected-OID
        # primitive locally. It does not certify GitHub App/server ACLs.
        r=git(self.folder,'update-ref',REF,candidate,expected or '0'*40,check=False)
        need(r.returncode==0,'B_LAB_STALE_CAS')
        return candidate
