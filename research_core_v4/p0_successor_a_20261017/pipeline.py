"""Single successor consumer pipeline. Historical code is never imported/run.

Reuses accepted PreparedInput, strict parser, flags and archive adapter. Only
verified input restoration and synthetic deterministic work are installed in A.
Economic is a security boundary, not an economic backtest or market engine.
"""
from .publisher import Publisher, canonical, digest, Denied, need
from research_core_v4.p0_supersession_20261016.authority import PreparedInput, FLAGS, strict_json
from research_core_v4.p0_supersession_20261016.adapters import ConsumerAdapters

class Successor:
    def __init__(self,publisher):
        need(type(publisher) is Publisher,'SINGLE_PUBLISHER_REQUIRED');self.p=publisher
    def select(self,kind,*,source_kind='EXACT_AUTHORITY',expected_oid=None):
        need(kind in ('restore','worker','handoff','economic'),'CONSUMER')
        need(source_kind=='EXACT_AUTHORITY','HISTORICAL_SOURCE_NOT_AUTHORITY')
        self.p.guard();head,s=self.p.t.read();need(s is not None and s['revoked'] is False,'NO_AUTHORITY_OR_REVOKED')
        if expected_oid is not None:need(head==expected_oid,'OID_CONFLICT')
        self.p.validate_head(head,s)
        p=self.p.g.policy
        need(s['source_sha']==p['source_sha'] and s['principal']==p['principal'] and s['epoch']==p['epoch'],
             'SOURCE_PRINCIPAL_EPOCH')
        rows=s['records'];need(len(rows)==s['generation']-p['first_generation']+1,'GENERATION_LOG')
        seen=set()
        for n,r in enumerate(rows):
            need(r['generation']==p['first_generation']+n and r['epoch']==p['epoch'] and
                 r['policy_sha256']==self.p.g.hash and r['intent'] not in seen,'LOG_REPLAY_OR_ROLLBACK')
            seen.add(r['intent'])
        need(rows and rows[-1]['parent']==s['last_parent'] and
             digest(canonical(s['payload']))==rows[-1]['payload_sha256'],'PAYLOAD_INTEGRITY')
        parents=self.p.t.git('rev-list','--parents','-n','1',head).stdout.decode().split()[1:]
        need(parents==[s['last_parent']],'NATIVE_PARENT_FENCE')
        need(s['payload']['generation']==s['generation'] and s['payload']['permissions']==FLAGS,'PAYLOAD_GENERATION_OR_GO')
        return PreparedInput(kind,head,s['generation'],canonical(s['payload']),rows[-1]['intent'])
    def restore(self,**kw):return self.select('restore',**kw)
    def worker(self,**kw):
        verified=self.select('worker',**kw)
        payload=strict_json(verified.payload)
        need(payload['marker']=='SYNTHETIC_ONLY','REAL_WORK_NOT_AUTHORIZED')
        return {'input_oid':verified.oid,'generation':verified.generation,
                'synthetic_result_sha256':digest(canonical(payload['checkpoint'])),
                'execution_allowed':False,'external_calls_allowed':False}
    def handoff(self,**kw):return self.select('handoff',**kw)
    def economic(self,**kw):
        verified=self.select('economic',**kw)
        return {'input_oid':verified.oid,'generation':verified.generation,'research_go':False,
                'economic_execution_allowed':False,'reason':'OWNER_RESEARCH_SCOPE_ABSENT'}
    archive=staticmethod(ConsumerAdapters.archive)
