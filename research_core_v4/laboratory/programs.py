"""Bounded declarative programmes over existing laboratory capabilities.

Manifests are prospective, versioned scientific decisions. The scheduler selects
eligible nodes by declared information priority and observed dependency verdicts.
No code generation, arbitrary imports, shell, orders or unbounded hypothesis loop.
"""
from copy import deepcopy
import re
from .common import *
from .budgets import TrialBook
from .data import DataCatalogue,Acquisition
from .economics import screen,replay,robustness
from discovery.engine import DiscoveryEngine
OPS={'native_replay','causal_intents','native_screen','catalogue','acquire','freeze','screen','replay','robustness','classify','report'}
AUTHORITY='07d1ddbe0b83753bbf189770af1911623fef8d6f'
ID=re.compile(r'^[A-Za-z0-9_-]{1,96}$')

def validate_manifest(m,history,global_book):
    need(m['schema']=='mxm.laboratory-program.v1' and ID.fullmatch(m['id']) and type(m['version']) is int and m['version']>0,'PROGRAM_ID')
    need(m['authority']==AUTHORITY and m['partition']=='DEVELOPMENT' and m['orders']==0,'PROGRAM_SCOPE')
    need(m['mode'] in ('SYNTHETIC_RECEPTION','DEVELOPMENT_RESEARCH'),'PROGRAM_MODE')
    need(m['budget']['steps']>0 and m['budget']['steps']>=len(m['tasks']) and m['budget']['broker_requests']>=0,'PROGRAM_BUDGET')
    need(history['reconciled'] and m['budget']['new_V2_identities']<=history['V2']['remaining'],'HISTORICAL_BUDGET')
    need(type(m['prospective_at_ms']) is int and m['provenance'] and len(m['source_sha256'])==64,'PROGRAM_PROVENANCE')
    tasks=m['tasks'];need(bool(tasks) and len(tasks)==len(set(tasks)),'TASKS')
    charged=[]
    for ident,t in tasks.items():
        need(ID.fullmatch(ident) and t['operator'] in OPS,'OPERATOR')
        need(type(t['priority']) is int and type(t['trial_units']) is int and t['trial_units']>=0,'TASK_BUDGET')
        need(set(t['dependencies'])<=set(tasks) and ident not in t['dependencies'],'DEPENDENCY')
        need(set(t.get('when',{}))<=set(t['dependencies']),'CONDITIONAL_DEPENDENCY')
        need(all(isinstance(v,list) and v for v in t.get('when',{}).values()),'CONDITIONAL_VERDICTS')
        need(t['operator']=='freeze' or t['trial_units']==0,'TRIAL_UNIT_LOCATION')
        if t['operator']=='freeze':
            candidate=DiscoveryEngine().freeze_candidate(t['input']['candidate'],persist=False)
            need(candidate['provenance'].get('programme')==m['id'],'CANDIDATE_PROGRAMME')
            need(candidate['provenance'].get('prospective_at_ms')==m['prospective_at_ms'],'CANDIDATE_PROSPECTIVE')
            if m['mode']=='SYNTHETIC_RECEPTION':
                need(t['trial_units']==0 and candidate['provenance'].get('synthetic_reception') is True,'SYNTHETIC_LANE')
            else:
                need(candidate['provenance'].get('synthetic_reception') is not True,'SYNTHETIC_RESEARCH_MIX')
                need(t['trial_units']==1 and candidate['id'] not in history['V2']['charged'] and candidate['id'] not in history['V2'].get('existing_candidate_ids',[]),'IDENTITY_ALREADY_OPENED')
                need('V2:'+candidate['id'] not in global_book.identities,'IDENTITY_ALREADY_RESERVED')
            charged.append(candidate['id'])
        if m['mode']=='DEVELOPMENT_RESEARCH':
            need(t['operator'] not in ('screen','catalogue','replay'),'REAL_DATA_REQUIRES_NATIVE_ADAPTER')
            if t['operator'] in ('native_screen','native_replay'):
                need(t['input'].get('corpus')=={'bound_authentic_corpus':True},'AUTHENTIC_CORPUS_BINDING')
                ref=t['input'].get('candidate',{}).get('result_of');need(ref in tasks and tasks[ref]['operator']=='freeze','ECONOMICS_REQUIRES_PROSPECTIVE_REGISTRY')
        if t['operator']=='acquire':need(m['mode']=='DEVELOPMENT_RESEARCH','SYNTHETIC_NETWORK_FORBIDDEN')
    need(len(charged)==len(set(charged)) and sum(t['trial_units'] for t in tasks.values())<=m['budget']['new_V2_identities'],'PROGRAM_TRIAL_TOTAL')
    visiting=set();done=set()
    def visit(k):
        need(k not in visiting,'CYCLIC_PROGRAMME')
        if k in done:return
        visiting.add(k)
        for dep in tasks[k]['dependencies']:visit(dep)
        visiting.remove(k);done.add(k)
    for k in tasks:visit(k)
    return digest(m)

class Laboratory:
    def __init__(self,manifest,history,global_book,cache=None,collector=None,state=None):
        self.m=deepcopy(manifest);self.history=history;self.book=global_book;self.cache=cache or DataCatalogue();self.collector=collector
        mh=validate_manifest(self.m,history,global_book) if state is None else digest(self.m)
        self.acquisition=Acquisition(self.cache,collector,{k:self.m['budget']['broker_requests'] for k in ('M5','H1','BID_ASK','TOTAL')})
        self.state=deepcopy(state) if state else {'schema':'mxm.laboratory-progress.v1','manifest_sha256':mh,'programme':self.m['id'],
          'version':self.m['version'],'sequence':0,'results':{},'skipped':{},'pending':None,'steps_used':0,'safe_stop':False,'stop_reason':None,'journal':[]}
        self.check()
    def check(self):
        s=self.state;need(s['schema']=='mxm.laboratory-progress.v1' and s['manifest_sha256']==digest(self.m),'CHECKPOINT_MANIFEST_CHANGED')
        need(s['programme']==self.m['id'] and s['version']==self.m['version'],'CHECKPOINT_IDENTITY')
        need(set(s['results'])<=set(self.m['tasks']) and set(s['skipped'])<=set(self.m['tasks']),'CHECKPOINT_TASKS')
        need(s['pending'] is None,'UNSAFE_PENDING_RESUME')
        need(s['steps_used']==len(s['results']) and s['steps_used']<=self.m['budget']['steps'],'CHECKPOINT_BUDGET')
        prev=None
        for i,e in enumerate(s['journal']):
            need(e['sequence']==i+1 and e['previous']==prev and e['sha256']==digest({k:v for k,v in e.items() if k!='sha256'}),'CHECKPOINT_JOURNAL_CHANGED');prev=e['sha256']
        need(len(s['journal'])==s['sequence']==len(s['results']),'CHECKPOINT_SEQUENCE')
        for e in s['journal']:need(digest(s['results'][e['task']])==e['result_sha256'],'CHECKPOINT_RESULT_CHANGED')
        if s['safe_stop'] and s['stop_reason']=='AUTHORIZED_PROGRAMME_COMPLETE':
            for task,expect in self.m.get('acceptance',{}).items():
                need(task in s['results'] and s['results'][task]['classification']==expect['classification'],'RECEPTION_CLASSIFICATION')
                for path,expected in expect.get('value_equal',{}).items():
                    actual=s['results'][task]['value']
                    for key in path.split('.'):actual=actual[key]
                    need(actual==expected,'RECEPTION_KNOWN_ANSWER')
    def next(self):
        self.check();s=self.state
        if s['safe_stop']:return None
        while True:
            changed=False;finished=set(s['results'])|set(s['skipped']);eligible=[]
            for ident,t in self.m['tasks'].items():
                if ident in finished or not set(t['dependencies'])<=finished:continue
                allowed=all(d in s['results'] and s['results'][d]['classification'] in states for d,states in t.get('when',{}).items()) and not any(d in s['skipped'] for d in t['dependencies'])
                if not allowed:s['skipped'][ident]='DECLARED_DEPENDENCY_VERDICT';changed=True;continue
                eligible.append((t['priority'],ident))
            if eligible:return sorted(eligible)[0][1]
            if not changed:break
        s['safe_stop']=True;s['stop_reason']='AUTHORIZED_PROGRAMME_COMPLETE' if len(s['results'])+len(s['skipped'])==len(self.m['tasks']) else 'NO_ADMISSIBLE_CONTINUATION'
        return None
    def resolve(self,value):
        if isinstance(value,dict):
            if set(value)=={'native_acquisition_plan'}:
                need(hasattr(self,'authentic_corpus'),'AUTHENTIC_CORPUS_UNAVAILABLE')
                plan=deepcopy(value['native_acquisition_plan']);sid=str(plan['symbol_id']);terms=self.authentic_corpus['catalog']['full'].get(sid)
                need(terms is not None and 'digits' in terms,'NATIVE_SYMBOL_METADATA_UNAVAILABLE')
                plan['digits']=int(terms['digits']);return plan
            if set(value)=={'bound_authentic_corpus'}:
                need(value['bound_authentic_corpus'] is True and hasattr(self,'authentic_corpus'),'AUTHENTIC_CORPUS_UNAVAILABLE');return self.authentic_corpus
            if set(value)=={'result_of'}:
                need(value['result_of'] in self.state['results'],'UNAVAILABLE_DEPENDENCY')
                return deepcopy(self.state['results'][value['result_of']]['value'])
            if set(value)=={'field_of','field'}:
                need(value['field_of'] in self.state['results'],'UNAVAILABLE_DEPENDENCY');return deepcopy(self.state['results'][value['field_of']]['value'][value['field']])
            return {k:self.resolve(v) for k,v in value.items()}
        if isinstance(value,list):return [self.resolve(v) for v in value]
        return value
    def execute(self,ident):
        need(ident==self.next(),'DUPLICATE_OR_INADMISSIBLE_EXECUTION');t=self.m['tasks'][ident];s=self.state
        need(s['steps_used']<self.m['budget']['steps'],'BUDGET_EXHAUSTED')
        s['pending']={'task':ident,'intent_sha256':digest(t)}
        # A process lost after this intent is unsafe to resume blindly. Worker
        # invocation identity and evidence-parent CAS provide durable exclusion.
        try:
            x=self.resolve(t['input']);op=t['operator']
            if op=='catalogue':
                asset=self.cache.ingest(x['manifest'],x['rows']);a=self.cache.assets[asset]
                value={'asset_id':asset,'quality':a};verdict='DATA_VALID' if not a['invalid'] and not a['conflicts'] and a['row_count'] and a['completeness']=='CONFIRMED_COMPLETE' else 'DATA_INSUFFICIENT'
            elif op=='acquire':
                need(self.acquisition.budget.get(x['kind'],0)<=self.m['budget']['broker_requests'],'NETWORK_BUDGET')
                value=self.acquisition.request(x);verdict='DATA_VALID' if self.cache.assets[value['asset_id']]['completeness']=='CONFIRMED_COMPLETE' else 'DATA_INSUFFICIENT'
            elif op=='causal_intents':
                from .science import causal_intents
                value=causal_intents(x['candidate'],self.cache,x['assets']);verdict='CAUSAL_INTENTS_DEFINED' if not value['missing'] else 'DATA_INSUFFICIENT'
            elif op=='native_screen':
                from .science import native_quote_screen
                value=native_quote_screen(x['candidate'],x['generated'],x['corpus'],x['terms_authority']);verdict=value['classification']
                lane='RECEPTION' if self.m['mode']=='SYNTHETIC_RECEPTION' else 'V2';self.book.finish(lane,x['candidate']['id'],x['candidate']['spec_hash'])
            elif op=='native_replay':
                from .science import native_replay
                value=native_replay(x['candidate'],x['generated'],x['corpus'],x['authority'],x['spec']);verdict=value['classification']
            elif op=='freeze':
                value=DiscoveryEngine().freeze_candidate(x['candidate'],persist=False)
                lane='RECEPTION' if self.m['mode']=='SYNTHETIC_RECEPTION' else 'V2'
                self.book.reserve(lane,value['id'],value['spec_hash'],t['trial_units']);verdict='PROSPECTIVELY_ADMITTED'
            elif op=='screen':
                need(self.m['mode']=='SYNTHETIC_RECEPTION' or all(r['execution_basis']!='SYNTHETIC_RECEPTION' for r in x['evidence'].get('trades',[])),'SYNTHETIC_RESEARCH_MIX')
                value=screen(x['candidate'],x['evidence']);verdict=value['status']
                lane='RECEPTION' if self.m['mode']=='SYNTHETIC_RECEPTION' else 'V2'
                self.book.finish(lane,x['candidate']['id'],x['candidate']['spec_hash'])
            elif op=='replay':value=replay(x['spec'],x['evidence']);verdict=value['classification']
            elif op=='robustness':value=robustness(x);verdict=value['classification']
            elif op=='classify':
                value=x['result'];verdict=value.get('status',value.get('classification'))
                need(isinstance(verdict,str) and bool(verdict),'RESULT_CLASSIFICATION')
            else:value={'inputs':x,'economic_qualification':False};verdict='PROGRAMME_REPORT_SAVED'
            result={'operator':op,'classification':verdict,'input_sha256':digest(x),'value':value}
            s['results'][ident]=result;s['steps_used']+=1;s['sequence']+=1
            entry={'sequence':s['sequence'],'previous':s['journal'][-1]['sha256'] if s['journal'] else None,'task':ident,'definition_sha256':digest(t),'result_sha256':digest(result)}
            entry['sha256']=digest(entry);s['journal'].append(entry);s['pending']=None
            self.check();return result
        except Exception:
            s['safe_stop']=True;s['stop_reason']='EXECUTION_AMBIGUOUS_NO_AUTOMATIC_RETRY';raise
    def checkpoint(self):
        self.check();return deepcopy({'schema':'mxm.integrated-laboratory-checkpoint.v1','programme':self.m,'progress':self.state,
          'trial_book':self.book.export(),'catalogue':self.cache.export(),'acquisition_budget':self.acquisition.budget,'acquisition_remaining':self.acquisition.remaining,'native_receipts':self.acquisition.receipts})
    @classmethod
    def restore(cls,value,history,collector=None):
        need(value['schema']=='mxm.integrated-laboratory-checkpoint.v1','CHECKPOINT_SCHEMA')
        obj=cls(value['programme'],history,TrialBook.restore(value['trial_book']),DataCatalogue.restore(value['catalogue']),collector,state=value['progress'])
        obj.acquisition.budget=value['acquisition_budget'];obj.acquisition.remaining=value['acquisition_remaining'];obj.acquisition.receipts=value['native_receipts'];return obj
