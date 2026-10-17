"""Git receive-pack CAS, durable replay log and cold ACK reconciliation.

No REST ref PATCH, force update, secondary authority, implicit retry or mutable
local acceptance database. A contains only a synthetic launcher. Native active
access requires a separately received OWNER grant AND credential admission.
"""
import base64, copy, json, os, pathlib, re, subprocess, time
from research_core_v4.p0_supersession_20261016.authority import (
    ACTIVE_REF, OWNER_ROOT, FLAGS, Denied, need, canonical, digest, strict_json, closed_flags)
from research_core_v4.p0_owner_governance_20261017.governance import (
    GitHubReadOnly, GateBinding, verify_owner_review)
REPO='mariancradulescu/mxm-quant-greenfield'
REMOTE='https://github.com/'+REPO+'.git'
SYNTHETIC_PREFIX='refs/heads/mxm-o04-successor-a-synthetic-'
SOURCE_BRANCH='mxm-o04-successor-code-a-v1'
GATE_ENV='mxm-p0-owner-critical-v1'
GATE_ENV_ID=24553414129
PATH='.github/workflows/mxm-p0-successor-critical-a.yml'

class AckUnknown(RuntimeError):pass

class Grant:
    def __init__(self, policy, manifest, binding, reader, now, *, synthetic=False):
        # Real grants cannot be made from supplied JSON receipts or test readers.
        if not synthetic:
            need(type(reader) is GitHubReadOnly,'NATIVE_REVIEW_REQUIRED')
            need(binding.environment_id==GATE_ENV_ID and binding.environment_name==GATE_ENV
                 and binding.workflow_path==PATH,'FIXED_OWNER_GATE')
            verify_owner_review(reader,binding,manifest)
            need(manifest['critical_operation']=='BOOTSTRAP_AND_DELEGATE','NO_ACTIVATION_GRANT')
        else:
            need(manifest=={'fixture':'SYNTHETIC_ONLY'},'SYNTHETIC_GRANT_MARKER')
        need(policy.get('schema')=='mxm.successor-policy.v1','POLICY_SCHEMA')
        need(set(policy)=={'schema','scope','ref','source_sha','principal','epoch','first_generation',
            'last_generation','not_before','expires_at','max_payload_bytes','owner_root','research_go','access_sha256'},'POLICY_FIELDS')
        need(re.fullmatch('[0-9a-f]{64}',policy['access_sha256']) is not None,'ACCESS_CONFIG_DIGEST')
        need(policy['owner_root']==list(OWNER_ROOT) and policy['research_go'] is False,'OWNER_ROOT_AND_NO_RESEARCH')
        need(re.fullmatch('[0-9a-f]{40}',policy['source_sha']) is not None,'SOURCE_SHA')
        need(all(type(policy[k]) is int for k in ('epoch','first_generation','last_generation',
                  'not_before','expires_at','max_payload_bytes')),'POLICY_TYPES')
        need(policy['epoch']>=1 and 1808==policy['first_generation']<=policy['last_generation']<=policy['first_generation']+99
             and 0<policy['expires_at']-policy['not_before']<=86400 and
             policy['not_before']<=now<policy['expires_at'] and 0<policy['max_payload_bytes']<=1048576,'FINITE_POLICY')
        if synthetic:
            need(policy['scope']=='SYNTHETIC_ONLY' and re.fullmatch(re.escape(SYNTHETIC_PREFIX)+r'[0-9]+-1',policy['ref'])
                 and policy['principal']=='GITHUB_TOKEN_SYNTHETIC','SYNTHETIC_NAMESPACE')
        else:
            need(policy['scope']=='CHECKPOINT_ONLY_NO_RESEARCH' and policy['ref']==ACTIVE_REF
                 and policy['principal']=='APP:5343530:172030470','ACTIVE_POLICY_SCOPE')
            need(policy['source_sha']==binding.source_sha and digest(canonical(policy))==manifest['policy_sha256']
                 and manifest['not_before']<=now<manifest['expires_at'],'OWNER_POLICY_BINDING')
        self.raw=canonical(policy); self.hash=digest(self.raw); self.synthetic=synthetic
        self.manifest=canonical(manifest); self.binding=binding
    @property
    def policy(self):return json.loads(self.raw)
    def check(self, now, source, principal):
        p=self.policy
        need(p['not_before']<=now<p['expires_at'],'POLICY_EXPIRED')
        need(source==p['source_sha'] and principal==p['principal'],'SOURCE_OR_PRINCIPAL')

class GitCAS:
    """Credential is internal to a single process; subprocess output never logged."""
    def __init__(self, directory, token, grant):
        need(type(grant) is Grant,'GRANT_REQUIRED')
        self.grant=grant;self.ref=grant.policy['ref'];self.directory=pathlib.Path(directory)
        self.directory.mkdir(); self.env={k:v for k,v in os.environ.items()
            if not k.startswith(('GIT_','GH_','GITHUB_','SSH_','APP_','ACTIONS_'))}
        self.env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',
            GIT_AUTHOR_NAME='MXM successor A synthetic',GIT_AUTHOR_EMAIL='mxm@example.invalid',
            GIT_COMMITTER_NAME='MXM successor A synthetic',GIT_COMMITTER_EMAIL='mxm@example.invalid',
            GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
            GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode())
        self.git('init','-q')
    def git(self,*args,data=None,check=True):
        r=subprocess.run(['git',*args],cwd=self.directory,env=self.env,input=data,capture_output=True,timeout=90)
        if check and r.returncode:raise AckUnknown('GIT_TRANSPORT_UNCERTAIN_STOP')
        return r
    def head(self):
        result=self.git('ls-remote','--refs',REMOTE,self.ref).stdout.decode().splitlines()
        need(len(result)<=1,'CONFLICTING_HEADS')
        if not result:return None
        sha,ref=result[0].split();need(ref==self.ref and re.fullmatch('[0-9a-f]{40}',sha),'EXACT_REF_READ')
        return sha
    def read(self):
        head=self.head()
        if head is None:return None,None
        self.git('fetch','--quiet','--no-tags',REMOTE,head)
        raw=self.git('show',head+':state.json').stdout
        state=strict_json(raw)
        need(state.get('marker')==('SYNTHETIC_ONLY' if self.grant.synthetic else 'CHECKPOINT_ONLY_NO_RESEARCH'),
             'STATE_SCOPE')
        need(state.get('policy_sha256')==self.grant.hash and state.get('root')==list(OWNER_ROOT),'STATE_BINDING')
        need(self.head()==head,'READ_MOVED_STOP')
        return head,state
    def candidate(self, expected, state):
        blob=self.git('hash-object','-w','--stdin',data=canonical(state)).stdout.decode().strip()
        tree=self.git('mktree',data=('100644 blob '+blob+'\tstate.json\n').encode()).stdout.decode().strip()
        args=['commit-tree',tree]
        if expected:args+=['-p',expected]
        return self.git(*args,data=b'MXM successor atomic state\n').stdout.decode().strip()
    def cas(self, expected, state, *, lose_ack=False):
        candidate=self.candidate(expected,state)
        # Explicit lease is evaluated by Git send-pack and receive-pack. Candidate
        # has EXACT expected parent; no unconditional force or REST PATCH exists.
        result=self.git('push','--porcelain','--force-with-lease='+self.ref+':'+(expected or ''),
                        REMOTE,candidate+':'+self.ref,check=False)
        if lose_ack:raise AckUnknown('ACK_UNCERTAIN_READBACK_ONLY')
        if result.returncode:
            current=self.head()
            if current==candidate:return candidate
            if current!=expected:raise Denied('STALE_CAS')
            raise Denied('SERVER_WRITE_REJECTED')
        need(self.head()==candidate,'ACK_HEAD_CONFLICT')
        return candidate

class Publisher:
    def __init__(self,transport,grant,source,principal,clock=lambda:int(time.time())):
        need(type(transport) is GitCAS and type(grant) is Grant and transport.grant is grant,'BOUND_TRANSPORT')
        self.t=transport;self.g=grant;self.source=source;self.principal=principal;self.clock=clock
    def guard(self):self.g.check(self.clock(),self.source,self.principal)
    def bootstrap(self):
        self.guard();head,_=self.t.read();need(head is None,'BOOTSTRAP_EXISTS')
        p=self.g.policy
        return self.t.cas(None,{'schema':'mxm.successor-state.v1','marker':p['scope'],
            'root':list(OWNER_ROOT),'policy_sha256':self.g.hash,'source_sha':self.source,
            'principal':self.principal,'generation':p['first_generation']-1,'epoch':p['epoch'],
            'revoked':False,'last_parent':None,'records':[], 'payload':None})
    def validate_head(self,head,s):
        p=self.g.policy
        need(type(s) is dict and s.get('schema')=='mxm.successor-state.v1' and
             s['revoked'] is False and s['epoch']==p['epoch'] and s['source_sha']==self.source
             and s['principal']==self.principal,'FENCED_OR_REVOKED')
        rows=s['records']
        need(type(rows) is list and len(rows)==s['generation']-1807 and
             1807<=s['generation']<=p['last_generation'],'GENERATION_LOG')
        seen=set()
        for n,r in enumerate(rows):
            need(r['generation']==1808+n and r['epoch']==p['epoch'] and
                 r['policy_sha256']==self.g.hash and r['intent'] not in seen,'LOG_REPLAY_OR_ROLLBACK')
            seen.add(r['intent'])
        parents=self.t.git('rev-list','--parents','-n','1',head).stdout.decode().split()[1:]
        if rows:
            need(rows[-1]['parent']==s['last_parent'] and parents==[s['last_parent']] and
                 digest(canonical(s['payload']))==rows[-1]['payload_sha256'] and
                 s['payload']['generation']==s['generation'] and closed_flags(s['payload']['permissions']),
                 'CURRENT_STATE_INTEGRITY')
        else:
            need(s['generation']==1807 and s['last_parent'] is None and s['payload'] is None and not parents,
                 'GENESIS_INTEGRITY')
    def issue(self,expected,intent,payload):
        self.guard();head,s=self.t.read();need(head==expected and s is not None,'STALE_CAS')
        p=self.g.policy
        self.validate_head(head,s)
        need(s['revoked'] is False and s['epoch']==p['epoch'] and s['source_sha']==self.source
             and s['principal']==self.principal,'FENCED_OR_REVOKED')
        need(isinstance(intent,str) and re.fullmatch(r'[A-Za-z0-9_-]{8,80}',intent),'INTENT')
        need(all(r['intent']!=intent for r in s['records']),'REPLAY')
        generation=s['generation']+1
        need(p['first_generation']<=generation<=p['last_generation'],'GENERATION_EXHAUSTED')
        need(type(payload) is bytes and len(payload)<=p['max_payload_bytes'],'PAYLOAD_BUDGET')
        obj=strict_json(payload)
        need(set(obj)=={'schema','marker','generation','checkpoint','permissions'} and
             obj['schema']=='mxm.synthetic.checkpoint-input.v1' and obj['marker']=='SYNTHETIC_ONLY'
             and obj['generation']==generation and type(obj['checkpoint']) is dict and
             closed_flags(obj['permissions']),'PAYLOAD_SCOPE')
        # A deliberately cannot admit real checkpoint formats. Activating a real
        # data format needs its own received parser/policy revision under B.
        record={'intent':intent,'generation':generation,'epoch':p['epoch'],'parent':head,
                'payload_sha256':digest(payload),'policy_sha256':self.g.hash}
        candidate=copy.deepcopy(s);candidate.update(generation=generation,last_parent=head,payload=obj)
        candidate['records'].append(record)
        return {'expected':head,'state':candidate,'record':record}
    def publish(self,proposal,*,lose_ack=False):
        # Re-derive everything from the immutable current Git head. Caller cannot
        # forge the state or skip policy checks by supplying a prepared proposal.
        r=proposal['record'];rebuilt=self.issue(proposal['expected'],r['intent'],canonical(proposal['state']['payload']))
        need(rebuilt==proposal,'PROPOSAL_TAMPERED')
        return self.t.cas(proposal['expected'],proposal['state'],lose_ack=lose_ack)
    def reconcile(self,intent,payload_sha256):
        self.guard();head,s=self.t.read();need(s is not None,'NO_AUTHORITY')
        self.validate_head(head,s)
        found=[r for r in s['records'] if r['intent']==intent]
        need(len(found)==1 and found[0]['payload_sha256']==payload_sha256,'ACK_UNKNOWN_STOP_NO_RETRY')
        return {'status':'ACCEPTED_READBACK_NO_REEXECUTION','head':head,'record':found[0],
                'execution_allowed':False,'retry_allowed':False}
