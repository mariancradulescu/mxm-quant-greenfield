"""Isolated Git receive-pack CAS specimen, deliberately unable to target GitHub.

This is executable design evidence, NOT a deployed global fence. A trusted
broker must authenticate callers, own the only writer credential, validate
artifacts and time, and enforce these transitions before production activation.
No client-side method here revokes any legacy GitHub authority.
"""
import copy
import dataclasses
import hashlib
import json
import os
import pathlib
import re
import subprocess

REF = 'refs/heads/o04-lab-state'
ZERO = '0'*40

class Denied(ValueError):
    pass

class Unknown(RuntimeError):
    def __init__(self, candidate):
        super().__init__('ACK_UNKNOWN_READBACK_ONLY')
        self.candidate = candidate

def need(ok, code):
    if not ok:
        raise Denied(code)

@dataclasses.dataclass(frozen=True)
class Claim:
    oid: str
    owner: str
    epoch: int
    version: int

def canonical(state):
    return json.dumps(state, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

class GitFenceLab:
    def __init__(self, workspace, remote, principals=frozenset({'writer-a','writer-b'})):
        # Deliberate capability restriction: filesystem-only, bare lab repository.
        # Never accept URLs, Git remotes, environment-supplied credentials or refs.
        self.workspace = pathlib.Path(workspace).resolve()
        self.remote = pathlib.Path(remote).resolve()
        need('://' not in str(remote) and self.remote.is_dir(), 'LIVE_BACKEND_DISABLED')
        self.principals = frozenset(principals)
        self.workspace.mkdir()
        self.env = {k:v for k,v in os.environ.items() if not k.startswith(('GIT_', 'GH_', 'GITHUB_', 'SSH_'))}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME='O04 Lab', GIT_AUTHOR_EMAIL='lab@example.invalid',
            GIT_COMMITTER_NAME='O04 Lab', GIT_COMMITTER_EMAIL='lab@example.invalid',
            GIT_TERMINAL_PROMPT='0')
        self.git('init','-q')
        need(self.git('--git-dir='+str(self.remote),'rev-parse','--is-bare-repository').strip()==b'true', 'BARE_LAB_REQUIRED')
        # Lab marker created only by tests; real repository never receives one.
        need((self.remote/'O04_SYNTHETIC_LAB_ONLY').read_text()=='synthetic\n', 'LAB_MARKER_REQUIRED')

    def git(self, *args, data=None, check=True):
        p = subprocess.run(['git', *args], cwd=self.workspace, env=self.env,
            input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and p.returncode:
            raise Denied('GIT_OPERATION_REJECTED')
        return p.stdout if check else p

    def read(self):
        self.git('fetch','-q','--no-tags',str(self.remote),REF)
        oid = self.git('rev-parse','FETCH_HEAD').decode().strip()
        state = json.loads(self.git('show',oid+':state.json'))
        need(state['schema']=='mxm.o04.synthetic.git-fence.v1','STATE_SCHEMA')
        return oid, state

    def _publish(self, expected, state, lose_ack=False):
        blob = self.git('hash-object','-w','--stdin',data=canonical(state)).decode().strip()
        tree = self.git('mktree',data=('100644 blob '+blob+'\tstate.json\n').encode()).decode().strip()
        args = ['commit-tree',tree]
        if expected != ZERO:
            args += ['-p',expected]
        candidate = self.git(*args,data=b'O04 synthetic append-only transition\n').decode().strip()
        result = self.git('push','--porcelain','--force-with-lease='+REF+':'+expected,
            str(self.remote),candidate+':'+REF,check=False)
        if result.returncode:
            # A rejected or interrupted transport never triggers automatic replay.
            # Readback is required to distinguish rejection from lost ACK.
            observed, _ = self.read()
            if observed == expected:
                raise Denied('CAS_REJECTED_OR_NOT_APPLIED')
            if observed != candidate:
                raise Denied('CAS_REJECTED_STALE')
            raise Unknown(candidate)
        if lose_ack:
            raise Unknown(candidate)
        return candidate

    def initialize_synthetic(self):
        state={'schema':'mxm.o04.synthetic.git-fence.v1', 'epoch':0, 'owner':None,
            'deadline':0, 'version':0, 'accepted':{'0':{'digest':hashlib.sha256(b'synthetic genesis').hexdigest(),'operation':'genesis'}}}
        return self._publish(ZERO,state)

    def claim(self, expected, principal, now, ttl=60):
        need(principal in self.principals,'AUTHORITY_MISSING')
        need(type(now) is int and type(ttl) is int and 1<=ttl<=300,'LEASE_INPUT')
        oid, state = self.read()
        need(oid==expected,'STALE_VERSION')
        need(state['owner'] is None or now>=state['deadline'],'LEASE_HELD')
        state=copy.deepcopy(state)
        state.update(epoch=state['epoch']+1,owner=principal,deadline=now+ttl)
        return Claim(self._publish(expected,state),principal,state['epoch'],state['version'])

    def accept(self, token, version, digest, operation, now, lose_ack=False):
        oid, state = self.read()
        need(token.owner in self.principals,'AUTHORITY_MISSING')
        need(oid==token.oid and token.epoch==state['epoch'] and token.owner==state['owner'],'FENCED_WRITER')
        need(type(now) is int and now<state['deadline'],'LEASE_EXPIRED')
        need(version==state['version']+1 and token.version==state['version'],'CHECKPOINT_VERSION')
        need(str(version) not in state['accepted'],'ACCEPTED_CHECKPOINT_IMMUTABLE')
        need(re.fullmatch('[0-9a-f]{64}',digest) is not None,'DIGEST_REQUIRED')
        need(isinstance(operation,str) and 1<=len(operation)<=128,'OPERATION_REQUIRED')
        need(operation not in {r['operation'] for r in state['accepted'].values()},'OPERATION_REPLAY')
        state=copy.deepcopy(state)
        state['accepted'][str(version)]={'digest':digest,'operation':operation}
        state.update(version=version,owner=None,deadline=0)
        return self._publish(oid,state,lose_ack=lose_ack)

    def resolve(self, version, digest, operation):
        _, state=self.read()
        record=state['accepted'].get(str(version))
        if record=={'digest':digest,'operation':operation}:
            return 'ACCEPTED_READBACK_NO_REPLAY'
        return 'UNKNOWN_OR_CONFLICT_STOP'

def production_backend(*args, **kwargs):
    raise Denied('GLOBAL_AUTHORITY_NOT_VERIFIED_NO_GO')
