"""Append-only certificate identities and native issuer provenance.

The legacy R6 certificate is historical evidence and is never rewritten.
This certifier-only revision can certify the completed R7 run without rerunning
its worker or changing its frozen source, checkpoint or admission.
"""
import json,os,re,subprocess,urllib.error
from .common import need,encoded,bytes_digest

CERTIFIER_BRANCH='mxm-r3-certifier-source-20261021-r8'
EXECUTION_BRANCH='mxm-r3-integrated-source-20261021-r7'
EXECUTION_SOURCE='dbd0a42bf73f9ae5847a90a4ed159d21e0d7197a'
RECOVERY_RUN=39581281683
RECOVERY_PROOF='5034b7a5769def9692ecd3d51eae49e440da4a6a'
CERTIFIER_WORKFLOW='.github/workflows/mxm-r3-certify-v3.yml'
SCHEMA='mxm.e2e.native-certificate.v4'
LEGACY_CERT='typed-successor/END_TO_END_OPERATIONAL_ACCEPTANCE.json'

def certificate_path(source,run_id):
    need(type(source) is str and re.fullmatch('[a-f0-9]{40}',source) and
         type(run_id) is int and run_id>0,'CERTIFICATE_IDENTITY')
    return 'typed-successor/certificates/'+source+'/'+str(run_id)+'.json'

def validate_record(record,source,run_id):
    need(type(record) is dict and set(record)=={'schema','path','gate','issuer'} and
         record['schema']==SCHEMA and record['path']==certificate_path(source,run_id),
         'CERTIFICATE_RECORD_IDENTITY')
    gate=record['gate'];issuer=record['issuer']
    need(gate.get('source_sha')==source and gate.get('run_id')==run_id and
         type(issuer) is dict and set(issuer)=={'source_sha','trigger_sha','run_id','job_id'} and
         all(type(issuer[k]) is str and re.fullmatch('[a-f0-9]{40}',issuer[k]) for k in ('source_sha','trigger_sha')) and
         all(type(issuer[k]) is int and issuer[k]>0 for k in ('run_id','job_id')) and
         issuer['run_id']!=run_id,'CERTIFICATE_RECORD_ORIGIN')
    return record

def pre_mint_certifier(route,identity):
    """Read-only native context, clean checkout and exact admin seal before mint."""
    from .runtime import file_at,source_admission
    from .custody import resolve_control_policy,build_certifier_workflow
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    need(identity['operation']=='certify-v3' and identity['job']=='certify-v3',
         'CERTIFIER_SOURCE_CONTEXT')
    source=identity['source']
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==source and
         subprocess.run(['git','diff','--quiet','HEAD','--'],capture_output=True).returncode==0,
         'CERTIFIER_CLEAN_CHECKOUT')
    source_admission(source,source,route.json('git/ref/heads/'+CERTIFIER_BRANCH)['object']['sha'],
                     route.json('rulesets/25222248'))
    witness=strict_json(os.environ.get('R3_CONTROL_WITNESS','').encode())
    policies=[p for p in witness.get('policies',[]) if p.get('conditions',{}).get('ref_name')==
              {'include':['refs/heads/'+CERTIFIER_BRANCH],'exclude':[]}]
    need(len(policies)==1,'CERTIFIER_EXACT_ADMIN_SEAL')
    resolve_control_policy(route.json('rulesets/'+str(policies[0]['id'])),witness,source,CERTIFIER_BRANCH)
    need(strict_json(file_at(route,CERTIFIER_WORKFLOW,identity['trigger']))==build_certifier_workflow(source),
         'CERTIFIER_INSTALLED_WORKFLOW')

def verify_certifier_seal(route,source,native_seal=None):
    from .custody import effective_controls_reader
    controls=effective_controls_reader(route)
    need(route.json('git/ref/heads/'+CERTIFIER_BRANCH)['object']['sha']==source,'CERTIFICATE_ISSUER_SOURCE_REF')
    rules=controls.json('rules/branches/'+CERTIFIER_BRANCH)
    restrictions=[r for r in rules if r.get('type')=='update']
    need(restrictions,'CERTIFICATE_ISSUER_FREEZE_REQUIRED')
    for restriction in restrictions:
        policy=controls.json('rulesets/'+str(restriction['ruleset_id']))
        if 'bypass_actors' not in policy:
            matches=[p for p in (native_seal or {}).get('policies',[]) if p.get('id')==policy.get('id')]
            need(len(matches)==1 and all(k in policy and policy[k]==matches[0].get(k) for k in
                 ('id','enforcement','conditions','rules','updated_at')),
                 'CERTIFICATE_ISSUER_NATIVE_SEAL_REVISION')
            policy=matches[0]
        need(policy.get('enforcement')=='active' and policy.get('bypass_actors')==[] and
             policy.get('conditions',{}).get('ref_name')==
             {'include':['refs/heads/'+CERTIFIER_BRANCH],'exclude':[]} and
             {'creation','update','deletion','non_fast_forward'}<={r.get('type') for r in policy.get('rules',[])},
             'CERTIFICATE_ISSUER_EXACT_NO_BYPASS_FREEZE')

def existing_record(route,head,path,expected):
    """Identical issuance is a read-only no-op; any collision is a HOLD."""
    from .runtime import file_at
    try:raw=file_at(route,path,head)
    except urllib.error.HTTPError as error:
        if error.code==404:return False
        raise
    need(raw==encoded(expected),'CERTIFICATE_IDENTITY_COLLISION')
    return True

def verify_registered_certificate(route,ref,source,run_id):
    """Consumer requires real completed issuer, immutable workflow and issued bytes."""
    from .runtime import file_at
    from .custody import build_certifier_workflow
    from .operational_acceptance import verify_operational_acceptance,EXEC
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    path=certificate_path(source,run_id)
    raw=file_at(route,path,ref);record=validate_record(strict_json(raw),source,run_id)
    issuer=record['issuer'];native=route.json('actions/runs/'+str(issuer['run_id']))
    need(native.get('id')==issuer['run_id'] and native.get('path')==CERTIFIER_WORKFLOW and
         native.get('head_branch')=='main' and native.get('head_sha')==issuer['trigger_sha'] and
         native.get('event') in ('workflow_dispatch','workflow_run') and native.get('run_attempt')==1 and
         native.get('status')=='completed' and native.get('conclusion')=='success',
         'CERTIFICATE_NATIVE_ISSUER_RUN')
    workflow=strict_json(file_at(route,CERTIFIER_WORKFLOW,issuer['trigger_sha']))
    need(workflow==build_certifier_workflow(issuer['source_sha']),'CERTIFICATE_ISSUER_WORKFLOW_CHANGED')
    jobs=route.json('actions/runs/'+str(issuer['run_id'])+'/attempts/1/jobs?per_page=100')
    need(jobs.get('total_count')==len(jobs.get('jobs',[]))==1,'CERTIFICATE_ISSUER_JOB_INVENTORY')
    job=jobs['jobs'][0]
    need(job.get('id')==issuer['job_id'] and job.get('name')=='certify-v3' and
         job.get('run_id')==issuer['run_id'] and job.get('status')=='completed' and
         job.get('conclusion')=='success','CERTIFICATE_NATIVE_ISSUER_JOB')
    checkout='Run actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
    need(len([s for s in job.get('steps',[]) if s.get('name')==checkout and
         s.get('status')=='completed' and s.get('conclusion')=='success'])==1,
         'CERTIFICATE_ISSUER_CHECKOUT_STEP')
    log=route.data('actions/jobs/'+str(job['id'])+'/logs').decode('utf-8')
    need(re.search(r"\[command\].*git log -1 --format=%H[^\r\n]*[\r\n]+[^\r\n]*"+
                   re.escape(issuer['source_sha'])+r'(?:\r?\n|$)',log) is not None,
         'CERTIFICATE_ISSUER_CHECKOUT_LOG')
    seals=[json.loads(v) for v in re.findall(r'MXM_CERTIFIER_SOURCE_CONTROL (\{[^\r\n]*\})',log)]
    need(len(seals)==1 and seals[0].get('source_sha')==issuer['source_sha'] and
         seals[0].get('run_id')==issuer['run_id'],'CERTIFICATE_ISSUER_NATIVE_SEAL_LOG')
    verify_certifier_seal(route,issuer['source_sha'],seals[0])
    issued=[json.loads(v) for v in re.findall(r'MXM_CERTIFICATE_ISSUED (\{[^\r\n]*\})',log)]
    need(len(issued)==1 and issued[0].get('path')==path and
         issued[0].get('sha256')==bytes_digest(raw) and issued[0].get('target_run_id')==run_id,
         'CERTIFICATE_NATIVE_ISSUANCE_LOG')
    committed=issued[0]['certificate_commit'];commit=route.json('commits/'+committed)
    need([p['sha'] for p in commit.get('parents',[])]==[record['gate']['evidence_oid']] and
         {(f['filename'],f['status']) for f in commit.get('files',[])}=={(path,'added')} and
         file_at(route,path,committed)==raw,'CERTIFICATE_NATIVE_APPEND_ONLY_COMMIT')
    if committed!=ref:
        relation=route.json('compare/'+committed+'...'+ref)
        need(relation.get('status')=='ahead' and relation.get('behind_by')==0 and
             relation.get('ahead_by',0)>0 and relation.get('base_commit',{}).get('sha')==committed,
             'CERTIFICATE_REF_ANCESTRY')
    protected={name:route.json('branches/'+name)['protected'] for name in ('main',EXEC)}
    verify_operational_acceptance(route,record['gate'],source,protected)
    return record['gate']
