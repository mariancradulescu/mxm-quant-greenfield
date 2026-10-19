"""Typed history reconciliation and prospectively reserved trial accounting."""
from pathlib import Path
from .common import *

def historical_accounting(root):
    root=Path(root)
    from discovery.accounting import derive_current_accounting
    v2=derive_current_accounting(root)
    lock=json.loads((root/'adaptive_competition/state/OUTER_OPENING_LOCK_V1.json').read_text())
    policy=json.loads((root/'adaptive_competition/state/ADAPTIVE_COMPETITION_POLICY_V1_FROZEN_SPEC.json').read_text())
    from discovery.canonical import canonical_json
    # Adaptive policy is one separately opened identity, not every inner model or
    # result row. Its published semantic hash is bound by the opening lock.
    need(lock['policy_hash']==lock['arm']['exact_policy_spec_hash'] and bytes_digest((root/'adaptive_competition/state/ADAPTIVE_COMPETITION_POLICY_V1_FROZEN_SPEC.json').read_bytes())==lock['policy_hash'],'POLICY_BINDING')
    extras=[lock['arm']['policy_id']] if lock['outer_opened'] else []
    governance=json.loads((root/'research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json').read_text())
    used=v2['v2_attempts_used']+len(extras)
    need(used==governance['current']['used'] and governance['current']['total']==v2['v2_search_budget'],'HISTORICAL_BUDGET_RECONCILIATION')
    sources=['discovery/ledger.jsonl','V2_SEARCH_BUDGET_V1.json','adaptive_competition/state/OUTER_OPENING_LOCK_V1.json','adaptive_competition/state/ADAPTIVE_COMPETITION_POLICY_V1_FROZEN_SPEC.json','research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json']
    # Preserve the entire checked-in later research namespace, with its own unit.
    # Closed nodes, power simulations and selection events are not V2 identities.
    later=[]
    paths=set()
    for namespace in ('research_v3','research_core_v3','research_core_v4','adaptive_competition'):
        paths.update((root/namespace).rglob('*.json'))
    for path in sorted(paths):
        if '/laboratory/' in str(path):continue
        raw=path.read_bytes();later.append({'path':str(path.relative_to(root)),'sha256':bytes_digest(raw)})
    selection_audit=json.loads((root/'research_core_v4/state/PROJECT_SELECTION_BIAS_AUDIT_V1.json').read_text())
    closures=json.loads((root/'research_core_v4/state/POST_QUOTE_V4_CLOSURE_LEDGER_V2.json').read_text())
    adaptive=json.loads((root/'research_core_v4/state/V4_ADAPTIVE_SELECTION_HISTORY_V3.json').read_text())
    need(adaptive['new_selection_consumes_v2_economic_budget'] is False,'LATER_LANE_UNIT')
    return {'schema':'mxm.reconciled-typed-research-history.v1','legacy':{'used':v2['legacy_prior_attempts'],'unit':'ACCEPTED_LEGACY_ATTEMPTS'},
      'V2':{'limit':v2['v2_search_budget'],'used':used,'remaining':v2['v2_search_budget']-used,'existing_candidate_ids':sorted(p.stem for p in (root/'discovery/candidates').glob('V2-C*.json')),'charged':v2['budget_charged_candidate_ids']+extras,'result_observations':v2['economic_outcomes_opened']+len(extras)},
      'V3':{'unit':'ACCEPTED_DEPENDENT_CELLS_FAMILIES_AND_ADAPTIVE_SELECTION','accepted_selection_bias_audit':selection_audit,'independent_count_invented':False},
      'V4':{'selection_history':adaptive,'unit':'SEPARATELY_AUTHORIZED_PROGRAMS_AND_ADAPTIVE_SELECTION','closure_nodes':closures['nodes'],'source_index':later,'effective_independent_trial_count':None,'consumes_V2_identity_budget':False},
      'source_digests':{p:bytes_digest((root/p).read_bytes()) for p in sources},'reconciled':True,'unknown_effective_N_is_budget_exhaustion':False}

class TrialBook:
    def __init__(self,limits,used=None,identities=None):
        self.limits=dict(limits);self.used=dict(used or {k:0 for k in limits});self.identities=dict(identities or {})
        need(all(type(v) is int and v>=0 and self.used.get(k,0)<=v for k,v in limits.items()),'BUDGET_LIMIT')
    def reserve(self,lane,identity,spec_hash,units):
        need(lane in self.limits and type(units) is int and units>=0,'BUDGET_LANE')
        key=lane+':'+identity
        need(key not in self.identities,'DUPLICATE_EXPERIMENT')
        need(self.used.get(lane,0)+units<=self.limits[lane],'BUDGET_EXHAUSTED')
        self.used[lane]=self.used.get(lane,0)+units;self.identities[key]={'spec_hash':spec_hash,'units':units,'state':'RESERVED'}
    def finish(self,lane,identity,spec_hash):
        item=self.identities[lane+':'+identity];need(item['spec_hash']==spec_hash and item['state']=='RESERVED','IDENTITY_CHANGED')
        item['state']='OBSERVED'
    def export(self):return {'limits':self.limits,'used':self.used,'identities':self.identities}
    @classmethod
    def restore(cls,value):return cls(**value)
