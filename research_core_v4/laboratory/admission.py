"""Prospective event accounting. Legacy bytes are immutable, not refunded.

Reservation encumbers capacity; only exposure to an economic value charges an
identity. Programmes/families have finite, shared caps; lane names create no cap.
"""
from copy import deepcopy
from .common import need,digest

def semantic_hash(candidate,version=1):
    need(version in (1,2,3),'SEMANTIC_HASH_VERSION')
    if version==3:
        from decimal import Decimal
        from discovery.schema import CANDIDATE_REQUIRED_FIELDS
        from .common import encoded,number
        metadata={'id','candidate_id','spec_hash','provenance','rationale','created_at','created_utc','hypothesis_dimensions'}
        allowed=set(CANDIDATE_REQUIRED_FIELDS)|metadata
        need(type(candidate) is dict and set(candidate)<=allowed and
             set(CANDIDATE_REQUIRED_FIELDS)-{'spec_hash'}<=set(candidate) and
             type(candidate.get('universe')) is list and bool(candidate['universe']),
             'SEMANTIC_SCHEMA_FIELDS')
        def canonical(value):
            if type(value) is bool:return ['boolean',value]
            if value is None:return ['null']
            if number(value):
                decimal=Decimal(str(value))
                text=format(decimal,'f')
                if '.' in text:text=text.rstrip('0').rstrip('.')
                return ['number','0' if not decimal else text]
            if type(value) is str:return ['string',value]
            if type(value) is list:return ['list',[canonical(v) for v in value]]
            need(type(value) is dict and all(type(k) is str for k in value),'SEMANTIC_VALUE')
            return ['object',[[k,canonical(v)] for k,v in sorted(value.items())]]
        payload={k:v for k,v in candidate.items() if k not in metadata}
        payload['universe']=sorted(payload['universe'],key=lambda v:encoded(canonical(v)))
        return digest({'schema':'mxm.causal-semantic-fingerprint.v3','payload':canonical(payload)})
    value={k:v for k,v in candidate.items() if k not in ('id','candidate_id','spec_hash','provenance','created_at','created_utc')}
    if version==2:value.pop('rationale',None)
    if isinstance(value.get('universe'),list):value['universe']=sorted(value['universe'],key=lambda x:repr(x))
    return digest(value)

class TypedTrialBook:
    SCHEMA='mxm.typed-prospective-trial-book.v2'
    def __init__(self,baseline,events=None):
        self.baseline=deepcopy(baseline);self.events=[];self.families={};self.programmes={}
        need(baseline['V2_limit']==84 and baseline['V2_outcome_charged']==21 and baseline['economic_observations']==29,'ADMISSION_HISTORICAL_BASELINE')
        need(len(set(baseline['charged_ids']))==21,'ADMISSION_CHARGED_IDENTITIES')
        need(baseline['legacy_snapshot']['used']['V2']==22 and baseline['legacy_snapshot_sha256']==digest(baseline['legacy_snapshot']),'ADMISSION_LEGACY_BINDING')
        need(baseline['legacy_snapshot']['identities']['V2:V2-C033']==baseline['C033_legacy_item'],'ADMISSION_C033_BINDING')
        need(baseline['C033_legacy_item']['state']=='RESERVED' and baseline['C033_legacy_item']['units']==1 and 'V2-C033' not in baseline['charged_ids'],'ADMISSION_C033_NOT_OUTCOME')
        self.limits={'V2':84};self.items={};self.semantic_registry=dict(baseline['semantic_registry']);self.observation_ids=set();self.hash_version=1;self.identity_semantics=dict(baseline.get('identity_semantics',{}))
        for ident in baseline['charged_ids']:self.items['V2:'+ident]={'lane':'V2','id':ident,'units':1,'opened':True,'legacy':True}
        self.items['V2:V2-C033']={'lane':'V2','id':'V2-C033','units':1,'opened':False,'legacy':True,'spec_hash':baseline['C033_legacy_item']['spec_hash']}
        for event in events or []:
            need(event['sequence']==len(self.events)+1 and event['previous']==(self.events[-1]['sha256'] if self.events else None),'ADMISSION_EVENT_CHAIN')
            need(event['sha256']==digest({k:v for k,v in event.items() if k!='sha256'}),'ADMISSION_EVENT_DIGEST')
            self._apply(event['kind'],event['payload']);self.events.append(deepcopy(event))

    def _append(self,kind,payload):
        self._apply(kind,payload);e={'sequence':len(self.events)+1,'previous':self.events[-1]['sha256'] if self.events else None,'kind':kind,'payload':deepcopy(payload)}
        e['sha256']=digest(e);self.events.append(e)

    def _used(self,where,ident):
        return sum(x['units'] for x in self.items.values() if not x.get('legacy') and x.get(where)==ident)

    def _apply(self,kind,p):
        if kind=='FINGERPRINT_INDEX_UPGRADED':
            need(self.hash_version==1 and not any(not x['legacy'] for x in self.items.values()) and p['previous_index_sha256']==digest(self.semantic_registry),'ADMISSION_FINGERPRINT_TRANSITION')
            need(set(p['identity_semantics'])==set(self.baseline['identity_semantics']) and set(p['source_spec_hashes'])==set(p['identity_semantics']) and len(p['source_sha'])==40,'ADMISSION_FINGERPRINT_COVERAGE')
            derived={}
            for ident,h in p['identity_semantics'].items():
                need(len(h)==64 and len(p['source_spec_hashes'][ident])==64,'ADMISSION_FINGERPRINT_BINDING');derived.setdefault(h,[]).append(ident)
            self.semantic_registry={h:sorted(ids) for h,ids in derived.items()};self.identity_semantics=dict(p['identity_semantics']);self.hash_version=2
        elif kind=='SEMANTIC_SCHEMA_UPGRADED':
            from discovery.canonical import verify_spec_hash
            import re
            need(set(p)=={'previous_index_sha256','previous_view_sha256','source_sha','source_candidates'} and
                 self.hash_version==2 and not any(not x['legacy'] for x in self.items.values()) and
                 p['previous_index_sha256']==digest(self.semantic_registry) and
                 p['previous_view_sha256']==digest(self.view()) and
                 type(p['source_sha']) is str and re.fullmatch('[a-f0-9]{40}',p['source_sha']),
                 'SEMANTIC_SCHEMA_TRANSITION')
            candidates=p['source_candidates']
            need(type(candidates) is list and len(candidates)==len(self.identity_semantics) and
                 {c['id'] for c in candidates}==set(self.identity_semantics),'SEMANTIC_SCHEMA_COVERAGE')
            derived={};identities={}
            for candidate in candidates:
                verify_spec_hash(candidate)
                ident=candidate['id']
                need(semantic_hash(candidate,2)==self.identity_semantics[ident],
                     'SEMANTIC_SCHEMA_ORIGINAL_SPEC_CHANGED')
                h=semantic_hash(candidate,3);identities[ident]=h;derived.setdefault(h,[]).append(ident)
            # Add the new index without dropping any historical hash/alias.
            need(all(not self.semantic_registry.get(h) or self.semantic_registry[h]==sorted(ids)
                     for h,ids in derived.items()),'SEMANTIC_SCHEMA_HASH_COLLISION')
            self.semantic_registry.update({h:sorted(ids) for h,ids in derived.items()})
            self.identity_semantics=identities;self.hash_version=3
        elif kind=='FAMILY_REGISTERED':
            technical=p.get('mode')=='TECHNICAL_NONOUTCOME'
            need(p['id'] not in self.families and type(p['identity_cap']) is int and type(p['observation_cap']) is int and ((p['identity_cap']==p['observation_cap']==0) if technical else (p['identity_cap']>0 and p['observation_cap']>0)),'ADMISSION_FAMILY_CAP')
            need(len(p['decision_sha256'])==64 and len(p['novelty_justification'])>=40 and p['selection_history_ref'] and p['adaptive_exposure'],'ADMISSION_NOVELTY_AND_EXPOSURE')
            lane=p['lane'];need(lane=='V2' or lane.startswith('DISTINCT_'),'ADMISSION_LANE')
            limit=self.limits.get(lane,p['lane_cap'])
            need(type(limit) is int and limit>0 and 0<=p['identity_cap']<=limit and p['lane_cap']==limit,'ADMISSION_NO_LANE_RESET')
            self.limits[lane]=limit
            self.families[p['id']]=deepcopy(p)
        elif kind=='PROGRAMME_REGISTERED':
            need(p['id'] not in self.programmes and p['family'] in self.families,'ADMISSION_PROGRAMME')
            f=self.families[p['family']];technical=f.get('mode')=='TECHNICAL_NONOUTCOME'
            need(p['lane']==f['lane'] and type(p['identity_cap']) is int and (p['identity_cap']==0 if technical else 0<p['identity_cap']<=f['identity_cap']),'ADMISSION_PROGRAMME_CAP')
            need(type(p['observation_cap']) is int and (p['observation_cap']==0 if technical else 0<p['observation_cap']<=f['observation_cap']) and len(p['manifest_sha256'])==64,'ADMISSION_PROGRAMME_OBSERVATIONS')
            self.programmes[p['id']]=deepcopy(p)
        elif kind=='IDENTITY_RESERVED':
            if self.hash_version==3:
                from discovery.canonical import verify_spec_hash
                candidate=p.get('candidate');verify_spec_hash(candidate)
                need(candidate['id']==p['id'] and candidate['spec_hash']==p['spec_hash'] and
                     semantic_hash(candidate,3)==p['semantic_hash'],'SEMANTIC_RESERVATION_BINDING')
            key=p['lane']+':'+p['id'];need(not any(x['id']==p['id'] for x in self.items.values()) and p['programme'] in self.programmes,'ADMISSION_IDENTITY_DUPLICATE')
            q=self.programmes[p['programme']];f=self.families[q['family']]
            need(p['lane']==q['lane'] and p['family']==q['family'] and p['units']==1,'ADMISSION_IDENTITY_SCOPE')
            old=self.semantic_registry.get(p['semantic_hash']);known=self.identity_semantics.get(p['id'])
            need(len(p['spec_hash'])==64 and len(p['semantic_hash'])==64 and (old is None or old==p['id'] or old==[p['id']]) and (known is None or known==p['semantic_hash']),'ADMISSION_CROSS_LANE_SEMANTIC_DUPLICATE')
            need(self.encumbered(p['lane'])+1<=self.limits[p['lane']] and self._used('programme',q['id'])+1<=q['identity_cap'] and self._used('family',f['id'])+1<=f['identity_cap'],'ADMISSION_FINITE_CAP_EXHAUSTED')
            self.items[key]={**deepcopy(p),'opened':False,'legacy':False};self.semantic_registry[p['semantic_hash']]=key
        elif kind=='ECONOMIC_OUTCOME_OPENED':
            x=self.items[p['key']];need(not x['legacy'] and not x['opened'] and x['spec_hash']==p['spec_hash'],'ADMISSION_OUTCOME_IDENTITY')
            x['opened']=True
        elif kind=='ECONOMIC_OBSERVATION_RECORDED':
            x=self.items[p['key']];need(not x['legacy'] and x['opened'] and x['spec_hash']==p['spec_hash'] and len(p['result_sha256'])==64,'ADMISSION_OBSERVATION_WITHOUT_OUTCOME')
            token=p['key']+':'+p['observation_id'];need(token not in self.observation_ids,'ADMISSION_DUPLICATE_OBSERVATION')
            q=self.programmes[x['programme']];f=self.families[x['family']]
            observed=[e for e in self.events if e['kind']=='ECONOMIC_OBSERVATION_RECORDED']
            need(sum(self.items[e['payload']['key']]['programme']==q['id'] for e in observed)<q['observation_cap'] and sum(self.items[e['payload']['key']]['family']==f['id'] for e in observed)<f['observation_cap'],'ADMISSION_OBSERVATION_CAP_EXHAUSTED')
            self.observation_ids.add(token)
        else:need(False,'ADMISSION_UNKNOWN_EVENT')

    def register_family(self,policy):self._append('FAMILY_REGISTERED',policy)
    def register_programme(self,policy):self._append('PROGRAMME_REGISTERED',policy)
    def validate_programme(self,m):
        need(m['id'] in self.programmes,'ADMISSION_UNREGISTERED_PROGRAMME');q=self.programmes[m['id']]
        need(q['manifest_sha256']==digest(m) and m['economic_lane']==q['lane'] and m['family_id']==q['family'],'ADMISSION_MANIFEST_BINDING')
        need(m['budget']['new_identities']==q['identity_cap'],'ADMISSION_MANIFEST_CAP')
        if m['mode']=='DEVELOPMENT_RESEARCH':need(self.hash_version in (2,3),'ADMISSION_CAUSAL_FINGERPRINT_REQUIRED')
    @property
    def identities(self):return self.items
    def encumbered(self,lane):return sum(x['units'] for x in self.items.values() if x['lane']==lane)
    def reserve(self,lane,identity,spec_hash,units,*,candidate,programme):
        need(programme in self.programmes,'ADMISSION_UNREGISTERED_PROGRAMME')
        payload={'lane':lane,'id':identity,'spec_hash':spec_hash,'units':units,'semantic_hash':semantic_hash(candidate,self.hash_version),'programme':programme,'family':self.programmes[programme]['family']}
        if self.hash_version==3:payload['candidate']=deepcopy(candidate)
        self._append('IDENTITY_RESERVED',payload)
    def upgrade_semantic_schema(self,candidates,source):
        self._append('SEMANTIC_SCHEMA_UPGRADED',{'previous_index_sha256':digest(self.semantic_registry),
            'previous_view_sha256':digest(self.view()),'source_sha':source,'source_candidates':deepcopy(candidates)})
    def open_outcome(self,lane,identity,spec_hash):
        key=lane+':'+identity;x=self.items[key];need(x.get('spec_hash')==spec_hash and not x['legacy'],'ADMISSION_OUTCOME_BINDING')
        q=self.programmes[x['programme']];f=self.families[x['family']]
        observed=[e for e in self.events if e['kind']=='ECONOMIC_OBSERVATION_RECORDED']
        need(sum(self.items[e['payload']['key']]['programme']==q['id'] for e in observed)<q['observation_cap'] and sum(self.items[e['payload']['key']]['family']==f['id'] for e in observed)<f['observation_cap'],'ADMISSION_OBSERVATION_CAP_BEFORE_EXPOSURE')
        if not x['opened']:self._append('ECONOMIC_OUTCOME_OPENED',{'key':key,'spec_hash':spec_hash})
    def observe(self,lane,identity,spec_hash,observation_id,result_sha256):
        self._append('ECONOMIC_OBSERVATION_RECORDED',{'key':lane+':'+identity,'spec_hash':spec_hash,'observation_id':observation_id,'result_sha256':result_sha256})
    def view(self):
        lanes={lane:{'limit':limit,'outcome_charged':sum(x['units'] for x in self.items.values() if x['lane']==lane and x['opened']),
          'reservation_holds':sum(x['units'] for x in self.items.values() if x['lane']==lane and not x['opened']),'encumbered':self.encumbered(lane)} for lane,limit in self.limits.items()}
        result={'lanes':lanes,'economic_observations':29+len(self.observation_ids),'new_events':len(self.events),'refunds':0,'universal_project_cap':None,'legacy_snapshot_sha256':self.baseline['legacy_snapshot_sha256']}
        if self.hash_version in (2,3):result['causal_identity_fingerprint_version']=self.hash_version
        return result
    def export(self):return {'schema':self.SCHEMA,'baseline':deepcopy(self.baseline),'events':deepcopy(self.events),'view':self.view()}
    @classmethod
    def restore(cls,v):
        need(v['schema']==cls.SCHEMA,'ADMISSION_SCHEMA');obj=cls(v['baseline'],v['events']);need(v['view']==obj.view(),'ADMISSION_VIEW_TAMPER');return obj

def bootstrap_typed_book(history,legacy,candidates):
    need(history['V2']['used']==21 and history['V2']['result_observations']==29 and legacy['used']['V2']==22,'ADMISSION_BASELINE_RECONCILIATION')
    hashes={semantic_hash(c):c['id'] for c in candidates}
    base={'V2_limit':84,'V2_outcome_charged':21,'economic_observations':29,'charged_ids':history['V2']['charged'],
      'legacy_snapshot':deepcopy(legacy),'legacy_snapshot_sha256':digest(legacy),'C033_legacy_item':deepcopy(legacy['identities']['V2:V2-C033']),'semantic_registry':hashes,'identity_semantics':{c['id']:semantic_hash(c) for c in candidates}}
    return TypedTrialBook(base)
