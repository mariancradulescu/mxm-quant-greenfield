"""New machine-side GitHub integration only. No closed audit/test is invoked."""
import copy, json, os, pathlib, tempfile, time, urllib.request, urllib.error
from .publisher import *
from .pipeline import Successor
from research_core_v4.p0_supersession_20261016.authority import FLAGS
RESULTS=[]
def observe(name,fn):
    value=fn();RESULTS.append({'name':name,'result':'PASS','evidence':value});return value

def denied(name,fn,transport=None):
    before=transport.head() if transport else None
    try:fn()
    except (Denied,AckUnknown) as error:
        after=transport.head() if transport else None
        need(before==after,'NEGATIVE_MUTATED_REF')
        RESULTS.append({'name':name,'result':'REFUSED','reason':str(error),'before':before,'after':after})
    else:raise AssertionError('UNAUTHORIZED_PATH_ACCEPTED:'+name)

def api(path):
    request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    try:
        with urllib.request.build_opener(__import__('research_core_v4.p0_owner_governance_20261017.governance',fromlist=['NoRedirect']).NoRedirect).open(request,timeout=30) as r:
            return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        if e.code==404:return 404,None
        raise

def payload(gen):return canonical({'schema':'mxm.synthetic.checkpoint-input.v1','marker':'SYNTHETIC_ONLY',
             'generation':gen,'checkpoint':{'fixture':'A_INTEGRATION_ONLY','sequence':gen},'permissions':FLAGS})

def main():
    out=pathlib.Path('verification/successor-a');out.mkdir(parents=True,exist_ok=True)
    try:
        run_id=int(os.environ['GITHUB_RUN_ID']);source=os.environ['GITHUB_SHA'];now=int(time.time())
        status,run=api('actions/runs/'+str(run_id))
        need(status==200 and run['head_sha']==source and run['run_attempt']==1 and
             run['head_branch']=='mxm-remediation-p0-p4-20261015-v1' and run['event']=='push' and
             run['actor']['id']==322088485 and run['repository']['id']==1374181010,'NATIVE_PROBE_CONTEXT')
        ref=SYNTHETIC_PREFIX+str(run_id)+'-1'
        p={'schema':'mxm.successor-policy.v1','scope':'SYNTHETIC_ONLY','ref':ref,'source_sha':source,
           'principal':'GITHUB_TOKEN_SYNTHETIC','epoch':1,'first_generation':1808,'last_generation':1810,
           'not_before':now-5,'expires_at':now+1200,'max_payload_bytes':4096,'owner_root':list(OWNER_ROOT),'research_go':False,'access_sha256':digest(b'SYNTHETIC_NO_CREDENTIAL')}
        g=Grant(p,{'fixture':'SYNTHETIC_ONLY'},None,None,now,synthetic=True)
        for label,changes in [('active_ref_in_synthetic',{'ref':ACTIVE_REF}),('stage_ref_in_synthetic',{'ref':'refs/heads/mxm-o04-stage-authority-v1'}),('unbounded_generation',{'last_generation':9999}),('research_go',{'research_go':True}),('skip_OWNER_generation',{'first_generation':1809})]:
            denied(label,lambda changes=changes:Grant(dict(p,**changes),{'fixture':'SYNTHETIC_ONLY'},None,None,now,synthetic=True))
        denied('native_grant_from_director_json',lambda:Grant(p,{},None,None,now))
        from .issuer import admit
        denied('synthetic_grant_cannot_mint_App_token',lambda:admit(g,{'enabled':True}))
        with tempfile.TemporaryDirectory() as d:
            os.environ['SUCCESSOR_APP_PRIVATE_KEY']='SYNTHETIC_ENV_ISOLATION_CANARY_NOT_A_KEY'
            t=GitCAS(pathlib.Path(d)/'client',os.environ['GH_TOKEN'],g);pub=Publisher(t,g,source,p['principal'])
            need('SUCCESSOR_APP_PRIVATE_KEY' not in t.env,'SUBPROCESS_KEY_LEAK')
            RESULTS.append({'name':'private_key_env_excluded_from_Git_subprocess','result':'PASS','evidence':'synthetic canary removed'})
            del os.environ['SUCCESSOR_APP_PRIVATE_KEY']
            genesis=observe('native_isolated_genesis_CAS',pub.bootstrap)
            denied('bootstrap_twice',pub.bootstrap,t)
            proposal=pub.issue(genesis,'A-checkpoint-1808',payload(1808))
            altered=copy.deepcopy(proposal);altered['state']['payload']['checkpoint']['sequence']=0
            denied('altered_proposal',lambda:pub.publish(altered),t)
            denied('wrong_principal',lambda:Publisher(t,g,source,'DIRECTOR').issue(genesis,'A-other-1808',payload(1808)),t)
            denied('wrong_source',lambda:Publisher(t,g,'0'*40,p['principal']).issue(genesis,'A-other-1808',payload(1808)),t)
            denied('expired_policy',lambda:Publisher(t,g,source,p['principal'],lambda:now+2000).issue(genesis,'A-other-1808',payload(1808)),t)
            denied('wrong_generation',lambda:pub.issue(genesis,'A-other-1808',payload(1809)),t)
            wrong_flags=json.loads(payload(1808));wrong_flags['permissions']['research']=0
            denied('non_boolean_permission',lambda:pub.issue(genesis,'A-badflags-1808',canonical(wrong_flags)),t)
            # Two different proposals prepared against SAME remote OID; the stale
            # candidate is sent to receive-pack (not only refused by a Python if).
            competing=pub.issue(genesis,'A-racer-1808',payload(1808))
            first=observe('native_checkpoint_CAS',lambda:pub.publish(proposal))
            denied('native_stale_competing_CAS',lambda:t.cas(genesis,competing['state']),t)
            denied('checkpoint_intent_replay',lambda:pub.issue(first,'A-checkpoint-1808',payload(1809)),t)
            successor=Successor(pub)
            for name in ('restore','worker','handoff','economic'):
                value=observe('successor_'+name,lambda name=name:getattr(successor,name)(expected_oid=first))
                if hasattr(value,'payload'):RESULTS[-1]['evidence']={'consumer':value.consumer,'oid':value.oid,'generation':value.generation,'execution_allowed':value.execution_allowed}
            denied('release_as_authority',lambda:successor.restore(source_kind='GITHUB_RELEASE'),t)
            denied('side_ref_as_authority',lambda:successor.worker(source_kind='SIDE_REF'),t)
            denied('OID_conflict',lambda:successor.handoff(expected_oid=genesis),t)
            second=pub.issue(first,'A-checkpoint-1809',payload(1809))
            try:pub.publish(second,lose_ack=True)
            except AckUnknown:pass
            else:raise AssertionError('ACK_FAULT_NOT_INJECTED')
            # Cold process-equivalent client: no local journal/state or retry.
            cold=GitCAS(pathlib.Path(d)/'cold',os.environ['GH_TOKEN'],g);recovered=Publisher(cold,g,source,p['principal'])
            resolution=observe('cold_native_ACK_readback',lambda:recovered.reconcile('A-checkpoint-1809',digest(payload(1809))))
            head=resolution['head'];denied('ACK_duplicate_acceptance',lambda:recovered.publish(second),cold)
            denied('ACK_wrong_digest',lambda:recovered.reconcile('A-checkpoint-1809','0'*64),cold)
            third=recovered.issue(head,'A-checkpoint-1810',payload(1810))
            final=observe('last_finite_generation',lambda:recovered.publish(third))
            denied('finite_policy_exhausted',lambda:recovered.issue(final,'A-checkpoint-1811',payload(1811)),cold)
            # Native no-bypass append-only rule is inherited, unchanged. Distinct
            # from prior 422 creation probe; no protected target is touched.
            before=cold.head();rollback=cold.git('push','--force',REMOTE,genesis+':'+ref,check=False)
            need(rollback.returncode!=0 and b'GH013' in rollback.stderr and cold.head()==before,'APPEND_ONLY_NEGATIVE')
            RESULTS.append({'name':'native_synthetic_force_rollback','result':'REFUSED','server':'GH013','before':before,'after':cold.head()})
            snapshot=cold.read()[1]
            for label,mutate in [
                ('altered_state_digest',lambda q:q['payload']['checkpoint'].update(sequence=0)),
                ('revoked_authority',lambda q:q.update(revoked=True)),
                ('rollback_generation_log',lambda q:q.update(generation=1808)),
                ('epoch_conflict',lambda q:q.update(epoch=0)),
                ('principal_conflict',lambda q:q.update(principal='UNAUTHORIZED'))]:
                bad=copy.deepcopy(snapshot);mutate(bad)
                bad_oid=cold.cas(cold.head(),bad)
                denied(label,lambda:Successor(recovered).restore(expected_oid=bad_oid),cold)
                denied(label+'_publisher',lambda:recovered.issue(bad_oid,'A-corrupt-1811',payload(1811)),cold)
                # Deliberately invalid fixture remains synthetic; never consumed
                # as active authority. Each next mutation starts from valid snapshot.
            final=cold.head()
            snapshot=cold.read()[1]
            (out/'final-synthetic-state.json').write_bytes(canonical(snapshot))
            (out/'policy.json').write_bytes(canonical(p))
        preserved={}
        for name,wanted in [('mxm-o04-accepted-owner-1807-v1',OWNER_ROOT[1]),('mxm-o04-stage-authority-v1','c6644174244cd92b8e41b17f241b8f5e545fddd9')]:
            status,obj=api('git/ref/heads/'+name);need(status==200 and obj['object']['sha']==wanted,'PRESERVED_REF');preserved[name]=wanted
        status,_=api('git/ref/heads/mxm-o04-active-v1');need(status==404,'ACTIVE_REF_CREATED')
        (out/'summary.json').write_bytes(canonical({'status':'PASS','run_id':run_id,'source_sha':source,
            'synthetic_ref':ref,'final_oid':final,'probe_head_is_authority':False,'cases':len(RESULTS),'negative_cases':sum(r['result']=='REFUSED' for r in RESULTS),
            'preserved':preserved,'active_ref_HTTP':404,'real_checkpoints':0,'research_go':False}))
    finally:
        (out/'cases.json').write_bytes(canonical(RESULTS))
if __name__=='__main__':main()
