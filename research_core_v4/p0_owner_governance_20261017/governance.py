"""Minimal authorization delta; no auditor key, signer, approval POST or writer.

Existing integrity/anti-replay helpers are reused unchanged. Native Git fencing
is not replaced by this authorization layer. Production acceptance stays closed.
"""
from dataclasses import dataclass
import json
import os
import urllib.request
from research_core_v4.p0_supersession_20261016.authority import (
    ACTIVE_REF, OWNER_ROOT, Evidence, PreparedInput, SyntheticLedger, Denied, need,
    canonical, digest, strict_json, closed_flags, exact_fields, oid, sha256)

REPO='mariancradulescu/mxm-quant-greenfield'
OWNER_ID=322088485


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise Denied('NATIVE_REDIRECT_DENIED')


class GitHubReadOnly:
    """Only native authenticated GETs. Never accepts caller-supplied review JSON."""
    def review_history(self,run_id):
        need(type(run_id) is int and run_id>0,'RUN_ID')
        result=[]
        for suffix in ('','/approvals'):
            url='https://api.github.com/repos/'+REPO+'/actions/runs/'+str(run_id)+suffix
            req=urllib.request.Request(url,method='GET',headers={
                'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json',
                'X-GitHub-Api-Version':'2022-11-28'})
            with urllib.request.build_opener(NoRedirect).open(req,timeout=30) as response:
                need(response.status==200,'NATIVE_GET_FAILED')
                result.append(json.loads(response.read(4*1024*1024)))
        return tuple(result)


@dataclass(frozen=True)
class GateBinding:
    run_id: int
    environment_id: int
    environment_name: str
    source_sha: str
    workflow_path: str
    manifest_sha256: str


class SyntheticNativeFixture:
    """Explicit test transport; cannot be used in native verification mode."""
    def __init__(self,run,reviews):self.run=run;self.reviews=reviews
    def review_history(self,run_id):return self.run,self.reviews


def verify_owner_review(reader,binding,manifest,*,mode='NATIVE_READONLY'):
    need(type(binding) is GateBinding and type(binding.environment_id) is int and binding.environment_id>0
         and oid(binding.source_sha) and sha256(binding.manifest_sha256),'ACCEPTED_GATE_BINDING_REQUIRED')
    need((mode=='NATIVE_READONLY' and type(reader) is GitHubReadOnly) or
         (mode=='SYNTHETIC_ONLY' and type(reader) is SyntheticNativeFixture),'NATIVE_PROVENANCE_REQUIRED')
    need(digest(canonical(manifest))==binding.manifest_sha256,'MANIFEST_BINDING')
    exact_fields(manifest,('schema','critical_operation','operation_id','source_sha','policy_sha256',
                           'audit_reception_sha256','owner_root_oid','not_before','expires_at'),'CRITICAL_MANIFEST_FIELDS')
    need(manifest['schema']=='mxm.owner-critical-manifest.v2' and
         manifest['critical_operation'] in ('ARM_BOUNDED_CHECKPOINT_POLICY','INSTALL_PROTECTED_INFRASTRUCTURE',
            'BOOTSTRAP_AND_DELEGATE','CHANGE_POLICY','RECOVER_UNCERTAIN_AUTHORITY','RESEARCH_GO') and
         manifest['source_sha']==binding.source_sha and manifest['owner_root_oid']==OWNER_ROOT[1] and
         sha256(manifest['policy_sha256']) and sha256(manifest['audit_reception_sha256']) and
         type(manifest['operation_id']) is str and len(manifest['operation_id'])>=8 and
         type(manifest['not_before']) is int and type(manifest['expires_at']) is int and
         manifest['not_before']<manifest['expires_at'],'CRITICAL_MANIFEST_SCOPE')
    run,reviews=reader.review_history(binding.run_id)
    need(type(run) is dict and run.get('id')==binding.run_id and run.get('run_attempt')==1 and
         run.get('head_sha')==binding.source_sha and run.get('path')==binding.workflow_path and
         run.get('repository',{}).get('full_name')==REPO,'NATIVE_RUN_BINDING')
    need(type(reviews) is list,'NATIVE_REVIEW_FORMAT')
    comment='MXM_OWNER_CRITICAL_APPROVAL_V2 sha256='+binding.manifest_sha256
    matched=[r for r in reviews if type(r) is dict and any(
        e.get('id')==binding.environment_id and e.get('name')==binding.environment_name
        for e in r.get('environments',[]) if type(e) is dict)]
    # Ambiguous/conflicting history is not resolved by guessing timestamps (the
    # native review-history schema has no approval ID/time field guaranteed here).
    need(len(matched)==1,'OWNER_REVIEW_MISSING_OR_CONFLICT')
    approval=matched[0]
    need(approval.get('state')=='approved' and approval.get('user',{}).get('id')==OWNER_ID and
         approval.get('user',{}).get('type')=='User' and approval.get('comment')==comment,
         'EXPLICIT_OWNER_REVIEW_REQUIRED')
    return {'state':'OWNER_ACCOUNT_NATIVE_REVIEW_VERIFIED' if mode=='NATIVE_READONLY' else 'SYNTHETIC_OWNER_REVIEW_VERIFIED',
            'run_id':binding.run_id,'attempt':1,'environment_id':binding.environment_id,
            'manifest_sha256':binding.manifest_sha256,'review_sha256':digest(canonical(approval)),
            'human_operator_independently_proven':False,'operational_authority':False}


class BoundedCheckpointPreparation:
    """Changed G03.2 gate composed with the accepted synthetic replay journal.

    Initialization verifies the critical review once. Ordinary checkpoints use
    the same approved finite policy without additional human reviews/signatures.
    Inputs are prepared only, never published or restored operationally.
    """
    def __init__(self,reader,binding,manifest,policy,ledger,clock,*,mode='NATIVE_READONLY'):
        self.review=verify_owner_review(reader,binding,manifest,mode=mode)
        need(manifest['critical_operation'] in ('ARM_BOUNDED_CHECKPOINT_POLICY','BOOTSTRAP_AND_DELEGATE'),
             'NOT_A_CHECKPOINT_DELEGATION')
        exact_fields(policy,('schema','marker','authority_ref','issuer_principal','source_sha','epoch',
                            'first_generation','last_generation','not_before','expires_at','max_payload_bytes',
                            'owner_root','ordinary_operation'),'POLICY_FIELDS')
        need(policy['schema']=='mxm.owner-bounded-checkpoint-policy.v2' and policy['marker']=='SYNTHETIC_ONLY'
             and policy['authority_ref']==ACTIVE_REF and policy['owner_root']==list(OWNER_ROOT)
             and policy['source_sha']==binding.source_sha and
             policy['ordinary_operation']=='CHECKPOINT_ONLY' and
             type(policy['issuer_principal']) is str and policy['issuer_principal'].startswith('SYNTHETIC_'),
             'POLICY_SCOPE')
        need(all(type(policy[k]) is int for k in ('epoch','first_generation','last_generation',
                  'not_before','expires_at','max_payload_bytes')) and policy['epoch']>=1 and
             1808<=policy['first_generation']<=policy['last_generation'] and
             policy['not_before']<policy['expires_at'] and 0<policy['max_payload_bytes']<=1024*1024,
             'FINITE_POLICY_BOUNDS')
        self.policy_raw=canonical(policy);self.policy_hash=digest(self.policy_raw)
        need(self.policy_hash==manifest['policy_sha256'],'OWNER_APPROVED_POLICY_HASH')
        need(type(ledger) is SyntheticLedger,'ACCEPTED_SYNTHETIC_LEDGER_REQUIRED')
        self.ledger=ledger;self.clock=clock
        self.manifest_raw=canonical(manifest)

    def prepare(self,evidence,intent,*,current_policy_sha256,revoked=False):
        p=json.loads(self.policy_raw);m=json.loads(self.manifest_raw);now=self.clock()
        need(type(now) is int and p['not_before']<=now<p['expires_at'] and
             m['not_before']<=now<m['expires_at'],'DELEGATION_EXPIRED')
        need(revoked is False and current_policy_sha256==self.policy_hash,'POLICY_REVOKED_OR_CHANGED')
        need(type(evidence) is Evidence and evidence.source_kind=='EXACT_ACTIVE_REF' and evidence.ref==ACTIVE_REF
             and evidence.transport=='CONFIRMED_READ','EXPLICIT_AUTHORITY_NO_FALLBACK')
        need(evidence.issuer_principal==p['issuer_principal'] and type(evidence.epoch) is int
             and evidence.epoch==p['epoch'],'WRITER_FENCED')
        need(type(evidence.generation) is int and p['first_generation']<=evidence.generation<=p['last_generation']
             and oid(evidence.oid) and oid(evidence.predecessor_oid),'CHECKPOINT_BOUNDS_OR_IDENTITY')
        need(type(evidence.payload) is bytes and len(evidence.payload)<=p['max_payload_bytes'],'PAYLOAD_BUDGET')
        payload=strict_json(evidence.payload)
        exact_fields(payload,('schema','marker','generation','checkpoint','permissions'),'PAYLOAD_FIELDS')
        need(payload['schema']=='mxm.synthetic.checkpoint-input.v1' and payload['marker']=='SYNTHETIC_ONLY'
             and type(payload['generation']) is int and payload['generation']==evidence.generation
             and closed_flags(payload['permissions']) and type(payload['checkpoint']) is dict,'PAYLOAD_SCOPE')
        data_hash=digest(evidence.payload)
        need(evidence.authority_claims==((ACTIVE_REF,evidence.oid,evidence.generation,data_hash),),'INTEGRITY_OR_CONFLICT')
        need(type(intent) is str and 8<=len(intent)<=80,'INTENT')
        statement={'generation':evidence.generation,'oid':evidence.oid,'payload_sha256':data_hash,
                   'epoch':p['epoch'],'predecessor_oid':evidence.predecessor_oid,'intent':intent}
        # Existing accepted journal enforces head/parent/epoch/intent rules.
        # No auditor receipt or fresh human approval is required per checkpoint.
        try:
            self.ledger.consume(statement,(('GENERATION',str(evidence.generation)),),
                digest(canonical({'statement':statement,'policy':self.policy_hash})))
        except Denied as error:
            if str(error)=='RECEIPT_REUSE':raise Denied('CHECKPOINT_GENERATION_ALREADY_PREPARED') from None
            raise
        return PreparedInput('owner_bounded_checkpoint',evidence.oid,evidence.generation,evidence.payload,intent)


def real_checkpoint(*args,**kwargs):
    raise Denied('NATIVE_ATOMIC_WRITER_NOT_INSTALLED_NO_GO')
