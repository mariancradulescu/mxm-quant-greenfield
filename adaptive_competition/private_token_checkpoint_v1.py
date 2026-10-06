"""Private durable-host adapter DESIGN/PREPARED only; never enabled in hosted Actions.
No token leaves this file. Caller holds one exclusive lock during remote refresh and
checkpoint. fsync+atomic replace governs LOCAL persistence; no distributed atomicity
claim across cTrader and a storage service. Crash after server rotation before durable
receipt requires security recovery; unattended refresh remains locked pending audit.
"""
import os,json,tempfile,fcntl,stat
from pathlib import Path
from contextlib import contextmanager
class PrivateTokenCheckpoint:
 def __init__(self,path):
  self.path=Path(path).resolve()
  repo=Path(__file__).resolve().parents[1]
  if self.path.is_relative_to(repo):raise ValueError('private_checkpoint_must_be_outside_repository')
  if not self.path.parent.exists() or stat.S_IMODE(self.path.parent.stat().st_mode)&0o077:raise ValueError('private_checkpoint_parent_requires_0700')
 @contextmanager
 def locked(self):
  fd=os.open(str(self.path)+'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
  try:
   fcntl.flock(fd,fcntl.LOCK_EX);yield self
  finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
 def load(self):
  fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd) as f:
   if stat.S_IMODE(os.fstat(f.fileno()).st_mode)&0o077:raise ValueError('private_state_requires_0600')
   state=json.load(f)
  if state.get('scope')!='accounts':raise ValueError('accounts_only_required')
  return state
 def replace(self,state):
  if state.get('scope')!='accounts':raise ValueError('accounts_only_required')
  fd,name=tempfile.mkstemp(prefix='token-',dir=self.path.parent)
  try:
   with os.fdopen(fd,'w') as f:json.dump(state,f);f.flush();os.fsync(f.fileno())
   os.replace(name,self.path);d=os.open(self.path.parent,os.O_DIRECTORY)
   try:os.fsync(d)
   finally:os.close(d)
  finally:
   if os.path.exists(name):os.unlink(name)
