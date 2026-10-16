"""Real GitHub synthetic transport tests. SUCCESS is not STAGED_READY.

Expected security outcome: missing principal isolation is a demonstrated NO_GO.
Every live mutation targets run-scoped mxm-o04-stage-*; no OWNER write exists.
"""
import base64
import concurrent.futures
import copy
import email.utils
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from ..writer_fencing_o04_20261016 import git_fence_lab as lab
from ..writer_fencing_o04_20261016 import live_proof as old
from .readers import ENTRYPOINTS,dry_run
from .protocol import FixtureProtocol,SyntheticIssuer,digest,accept_checkpoint,owner_reader,staging_reader,ROOT

old.PREFIX='refs/heads/mxm-o04-stage-'

def scope():
    old.scope()
    lab.need(os.environ.get('GITHUB_EVENT_NAME')=='push','EVENT_SCOPE')
    run=old.get('actions/runs/'+os.environ['GITHUB_RUN_ID'])
    lab.need(run['head_sha']==os.environ['GITHUB_SHA'] and run['event']=='push' and run['run_attempt']==1 and run['actor']['id']==322088485,'RUN_SHA_ACTOR')

def now():
    req=urllib.request.Request('https://api.github.com/repos/'+old.REPO,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=30) as r:
        return int(email.utils.parsedate_to_datetime(r.headers['Date']).timestamp())

def receipt(name,obj):
    pathlib.Path('verification').mkdir(exist_ok=True)
    pathlib.Path('verification/'+name+'.json').write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
    print(json.dumps(obj,sort_keys=True))

def reject_verified(p,fn,code=None):
    before=p.read()[0]
    try:fn()
    except lab.Denied as ex:
        if code:lab.need(str(ex)==code,'WRONG_DENIAL_'+str(ex))
        lab.need(p.read()[0]==before,'NEGATIVE_CHANGED_SERVER')
        return {'result':'CLIENT_REFUSED_SERVER_REF_UNCHANGED','reason':str(ex),'before':before,'after':before}
    raise RuntimeError('DENIAL_MISSING')

def raw_candidate(t,oid,state):
    blob=t.git('hash-object','-w','--stdin',data=lab.canonical(state)).decode().strip()
    tree=t.git('mktree',data=('100644 blob '+blob+'\tstate.json\n').encode()).decode().strip()
    return t.git('commit-tree',tree,'-p',oid,data=b'SYNTHETIC_ONLY O04 unauthorized grant counterexample\n').decode().strip()

def child():
    # New interpreter/workspace. No in-memory state/claim survives restart.
    scope();d=pathlib.Path(sys.argv[2]);mode=sys.argv[3]
    t=old.RemoteProof(d/('child-'+mode));issuer=object.__new__(SyntheticIssuer)
    issuer.directory=d/'issuer';issuer.key=issuer.directory/'synthetic-private.pem';issuer.public=issuer.directory/'synthetic-public.pem';issuer.fingerprint=digest(issuer.public.read_bytes())
    p=FixtureProtocol(t,issuer,os.environ['GITHUB_SHA'],now)
    if mode=='before':os._exit(71)
    if mode=='after':p.accept_fixture(p.read()[0]);os._exit(72)
    if mode=='restart':
        oid,s=p.read();oid=p.claim(oid,'new-process-session')
        (d/'restart.json').write_text(json.dumps({'oid':oid,'epoch':p.read()[1]['epoch'],'pid':os.getpid()}));return
    if mode=='recover':
        request=json.loads((d/'recover-request.json').read_text());result=p.resolve(**request)
        (d/'recovered.json').write_text(json.dumps({**result,'pid':os.getpid()}));return
    raise ValueError('CHILD_MODE')

def main():
    scope();before=old.get('releases/412686323')['body'];old.verify_stop_registry(before);results={}
    with tempfile.TemporaryDirectory() as tmp:
        d=pathlib.Path(tmp);issuer=SyntheticIssuer(d/'issuer');a=old.RemoteProof(d/'a')
        p=FixtureProtocol(a,issuer,os.environ['GITHUB_SHA'],now);genesis=p.genesis()
        for n in (2,10):
            oid,s=p.read();barrier=threading.Barrier(n);s=copy.deepcopy(s);s.update(status='UNCLAIMED',owner=None,lease_until=0)
            def race(i):
                t=old.RemoteProof(d/('race-'+str(n)+'-'+str(i)));t.read()
                candidate=copy.deepcopy(s);candidate['race_contender']=i;barrier.wait(timeout=60)
                try:return ('WIN',t._publish(oid,candidate))
                except lab.Denied:return ('LOSE',None)
            with concurrent.futures.ThreadPoolExecutor(n) as pool:out=list(pool.map(race,range(n)))
            lab.need(sum(x[0]=='WIN' for x in out)==1,'RACE_WINNERS')
            final=p.read()[0];lab.need(final==next(x[1] for x in out if x[0]=='WIN'),'RACE_READBACK')
            results['race_'+str(n)]={'winners':1,'losers':n-1,'expected_old_oid':oid,'server_oid':final,'scope':'GIT_TRANSPORT_CAS_NOT_AUTHENTICATION'}
        claim=p.claim(p.read()[0],'first-process-session');proposal=p.proposal(claim,'synthetic-op-1')
        mutations={'manifest':lambda q:q.update(manifest=base64.b64encode(b'SYNTHETIC_ONLY altered').decode()),
                   'ciphertext':lambda q:q.update(ciphertext=base64.b64encode(b'SYNTHETIC_ONLY altered').decode()),
                   'signature':lambda q:q.update(signature=base64.b64encode(b'bad signature').decode()),
                   'source_SHA':lambda q:q['record'].update(source_SHA='0'*40),
                   'version':lambda q:q['record'].update(version=99),
                   'generation':lambda q:q['record'].update(generation=99),
                   'epoch':lambda q:q['record'].update(epoch=0),
                   'writer_principal':lambda q:q['record'].update(writer_principal='untrusted'),
                   'expired':lambda q:q['record'].update(lease_until=1)}
        for name,mutate in mutations.items():
            q=copy.deepcopy(proposal);mutate(q)
            results[name]=reject_verified(p,lambda q=q:p.pending(claim,q))
        results['missing_exclusive_grant']=reject_verified(p,lambda:accept_checkpoint(proposal),'PRINCIPAL_ISOLATION_NO_GO')
        pending=p.pending(claim,proposal)
        results['replay_pending']=reject_verified(p,lambda:p.pending(claim,proposal))
        cmd=[sys.executable,'-m',__package__+'.live_stage','--child',str(d)]
        pre=p.read()[0];r=subprocess.run(cmd+['before'],check=False);lab.need(r.returncode==71 and p.read()[0]==pre,'BEFORE_COMMIT_CUT')
        results['process_cut_before_commit']={'exit':71,'server_unchanged':True,'oid':pre}
        r=subprocess.run(cmd+['after'],check=False);lab.need(r.returncode==72,'AFTER_COMMIT_CUT')
        (d/'recover-request.json').write_text(json.dumps({'operation':'synthetic-op-1','manifest_sha256':proposal['record']['manifest_sha256']}))
        subprocess.run(cmd+['recover'],check=True);recovery=json.loads((d/'recovered.json').read_text())
        lab.need(recovery['status']=='SYNTHETIC_ACCEPTED_READBACK_NO_REPLAY' and recovery['pid']!=os.getpid(),'NEW_PROCESS_RECOVERY')
        results['lost_ack_new_process']=recovery
        accepted_oid,state=p.read()
        results['reader_adapters']={e:dry_run(e,lab.REF,accepted_oid,state,issuer,os.environ['GITHUB_SHA'],lab.REF) for e in ENTRYPOINTS}
        results['reader_valid_fixture']=staging_reader(lab.REF,accepted_oid,state,issuer,os.environ['GITHUB_SHA'])
        results['replay_after_accept']=reject_verified(p,lambda:p.accept_fixture(pending))
        # New process increments the durable epoch, then old epoch is unusable.
        subprocess.run(cmd+['restart'],check=True);restart=json.loads((d/'restart.json').read_text());lab.need(restart['epoch']==2,'RESTART_EPOCH')
        results['new_process_epoch']=restart
        results['late_writer']=reject_verified(p,lambda:p.pending(claim,proposal))
        oid,s=p.read();stale=copy.deepcopy(s);stale['stale_attempt']='SYNTHETIC_ONLY'
        results['stale_raw_push']=reject_verified(p,lambda:a._publish(claim,stale))
        for name,args in [('force_rollback',['push','--force',old.REMOTE,genesis+':'+lab.REF]),('delete',['push',old.REMOTE,':'+lab.REF])]:
            before_oid=p.read()[0];r=a.git(*args,check=False)
            lab.need(r.returncode!=0 and p.read()[0]==before_oid and (b'GH013' in r.stderr or b'repository rule' in r.stderr.lower()),'SERVER_NEGATIVE_'+name)
            results[name]={'result':'GITHUB_RULESET_REJECTED','server_oid':before_oid,'stderr':r.stderr.decode()[-1600:]}
        results['owner_gate']={r:owner_reader(r,{'oid':ROOT['root_o04_stop_oid']},PRODUCTION_GO=True) for r in [lab.REF,'refs/heads/mxm-o04-active-v1','release:412686323',lab.REF+'-side','UNKNOWN']}
        lab.need(set(results['owner_gate'].values())=={'NOT_AUTHORIZED'},'OWNER_GATE')
        results['side_reader']=staging_reader(lab.REF+'-side',oid,s,issuer,os.environ['GITHUB_SHA']);lab.need(results['side_reader']=='NOT_AUTHORIZED','SIDE_READER')
        # Demonstrate a generic write token can bypass ALL application validation:
        # upload forward candidate to non-authoritative SYNTHETIC carrier only.
        oid,s=p.read();forged=copy.deepcopy(s);forged.update(status='QUARANTINED',unauthorized_write='SYNTHETIC_ONLY NO_ACCEPTOR_ROLE')
        candidate=raw_candidate(a,oid,forged);carrier=lab.REF+'-side'
        a.git('push',old.REMOTE,candidate+':'+carrier)
        receipt('o04-stage-protocol',{'schema':'mxm.o04.stage.receipt.v1','marker':'SYNTHETIC_ONLY','run_id':os.environ['GITHUB_RUN_ID'],
            'head':os.environ['GITHUB_SHA'],'ref':lab.REF,'genesis_oid':genesis,'final_oid':oid,'candidate':candidate,'carrier':carrier,
            'issuer_public_key_pem':issuer.public.read_text(),'results':results,'root':ROOT,
            'verdict':'PRINCIPAL_ISOLATION_NO_GO','WRITER_STATE':'BLOCKED_STOP_ONLY','OWNER_ACCEPTS_NEW_CHECKPOINTS':False,
            'CAMPAIGN_RESTART_ALLOWED':False,'PRODUCTION_GO':False,
            'limitations':['Fixture signature is not a GitHub identity or exclusive grant.','Server Date is an observation; receive-pack does not enforce lease semantics.','Process/ACK cut injection is not an actual GitHub network outage.','Validation refusals are client-side; ref readback only confirms no mutation.']})
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('proof_ref='+lab.REF+'\ncandidate='+candidate+'\nexpected='+oid+'\n')
    lab.need(old.get('releases/412686323')['body']==before,'OWNER_CHANGED');old.verify_stop_registry(before)

def authority_probe(readonly=False):
    scope();ref=os.environ['PROOF_REF'];candidate=os.environ['CANDIDATE'];expected=os.environ['EXPECTED']
    lab.need(ref==lab.REF and old.get('git/ref/'+ref.removeprefix('refs/'))['object']['sha']==expected,'PROBE_SCOPE')
    req=urllib.request.Request('https://api.github.com/repos/'+old.REPO+'/git/refs/'+ref.removeprefix('refs/'),method='PATCH',
        data=json.dumps({'sha':candidate,'force':False}).encode(),headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:status=r.status
    except urllib.error.HTTPError as ex:status=ex.code
    after=old.get('git/ref/'+ref.removeprefix('refs/'))['object']['sha']
    if readonly:lab.need(status==403 and after==expected,'READONLY_PROBE')
    else:lab.need(status==200 and after==candidate,'WRITE_PRINCIPAL_OBSERVATION_CHANGED')
    receipt('o04-stage-'+('readonly' if readonly else 'write-bypass'),{'run_id':os.environ['GITHUB_RUN_ID'],'head':os.environ['GITHUB_SHA'],'ref':ref,'HTTP_status':status,
        'expected_before':expected,'server_after':after,'role':'NO_ACCEPTOR_ROLE','credential':'SEPARATE_JOB_GITHUB_TOKEN_CONTENTS_'+('READ' if readonly else 'WRITE'),
        'verdict':'READONLY_DENIED' if readonly else 'PRINCIPAL_ISOLATION_NO_GO_SERVER_ACCEPTED_UNGRANTED_FORWARD_WRITE',
        'OWNER_ACCEPTS_NEW_CHECKPOINTS':False,'PRODUCTION_GO':False})
    old.verify_stop_registry(old.get('releases/412686323')['body'])

if __name__=='__main__':
    if '--child' in sys.argv:child()
    elif '--readonly' in sys.argv:authority_probe(True)
    elif '--write-bypass' in sys.argv:authority_probe(False)
    else:main()
