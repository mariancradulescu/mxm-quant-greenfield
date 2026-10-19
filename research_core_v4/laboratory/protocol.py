"""Shared admission/claim/worker/publisher/recovery invariants."""
from copy import deepcopy
from .common import need,digest
from .admission import TypedTrialBook,bootstrap_typed_book

ORIGINAL_SOURCE='b430a303dc76bd1ea07fbd7dd9e91dcc7c7e9ee5'
ORIGINAL_CIPHER='eb031d18ee5b517ea1d4c3e6378cb276c4f3f46e2da810b86b8aabcc01a3ba8f'
ORIGINAL_PUBLIC='1f8d3ed42a276ad6c28a29d9c19d406fe45971dcdf8a239c589b090feff70e83'
STATE_PATH='typed-successor/program-state.json'

def identity_budget(m):
    typed=m['schema']=='mxm.laboratory-program.v2';key='new_identities' if typed else 'new_V2_identities'
    need(key in m['budget'] and type(m['budget'][key]) is int and m['budget'][key]>=0,'IDENTITY_BUDGET_SCHEMA')
    other='new_V2_identities' if typed else 'new_identities';need(other not in m['budget'],'IDENTITY_BUDGET_AMBIGUOUS');return m['budget'][key]

def accounting(value):
    if value.get('schema')==TypedTrialBook.SCHEMA:return TypedTrialBook.restore(value).view()
    need('used' in value and 'limits' in value,'ACCOUNTING_SCHEMA')
    return {'schema':'LEGACY_RESERVATION_INCLUSIVE','lanes':{k:{'limit':v,'encumbered':value['used'].get(k,0)} for k,v in value['limits'].items()},'outcomes_not_inferred_from_legacy_used':True}

def check_accounting(after,before,admission):
    need(after['universal_project_cap'] is None and after['refunds']==0,'ACCOUNTING_NO_RESET')
    v=after['lanes']['V2'];need(v['limit']==84 and 21<=v['outcome_charged']<=v['encumbered']<=84 and v['reservation_holds']>=1 and v['outcome_charged']+v['reservation_holds']==v['encumbered'],'ACCOUNTING_V2_CONSERVATION')
    if admission['mode']=='TECHNICAL_NONOUTCOME':need(after==before,'TECHNICAL_ACCOUNTING_CHANGED')
    else:
        cap=sum(identity_budget(m) for m in admission['programmes'])
        for lane,old in before['lanes'].items():
            now=after['lanes'][lane];need(now['limit']==old['limit'] and 0<=now['encumbered']-old['encumbered']<=cap and now['outcome_charged']>=old['outcome_charged'],'ACCOUNTING_MONOTONIC')
        need(after['economic_observations']>=before['economic_observations'],'OBSERVATION_RESET')

def migrate_private(private,state,history,candidates,source,original_public_sha):
    need(original_public_sha==ORIGINAL_PUBLIC and state['sequence']==16 and state['source_sha']==ORIGINAL_SOURCE and state['ciphertext_sha256']==ORIGINAL_CIPHER,'TRANSITION_EXACT_ORIGINAL')
    need(private['source_sha']==ORIGINAL_SOURCE and private['sequence']==16 and private['pending'] is None and all(v['progress']['safe_stop'] for v in private['programmes'].values()),'TRANSITION_CLOSED_PREDECESSOR')
    before=digest(private);new=deepcopy(private);book=bootstrap_typed_book(history,private['trial_book'],candidates)
    need(digest(book.export())=='a10c6754da01fcb7140f6f459e4982ad77da8790cb5adf83aa041154880e7829','TRANSITION_ACCEPTED_NATIVE_BASELINE')
    new['trial_book']=book.export();new['source_sha']=source
    new['typed_transition']={'original_source':ORIGINAL_SOURCE,'original_cipher':ORIGINAL_CIPHER,'original_public_sha256':ORIGINAL_PUBLIC,'original_private_sha256':before,'legacy_snapshot_sha256':book.baseline['legacy_snapshot_sha256'],'refunds':0}
    need(digest(private)==before,'TRANSITION_ORIGINAL_MUTATED');return new

def register_and_validate(private,a,history):
    from .programs import validate_manifest
    book=TypedTrialBook.restore(private['trial_book'])
    for p in a['family_policies']:
        if p['id'] in book.families:need(book.families[p['id']]==p,'FAMILY_POLICY_CHANGED')
        else:book.register_family(p)
    for p in a['programme_policies']:
        if p['id'] in book.programmes:need(book.programmes[p['id']]==p,'PROGRAMME_POLICY_CHANGED')
        else:book.register_programme(p)
    need({p['id'] for p in a['programme_policies']}=={m['id'] for m in a['programmes']},'POLICY_PROGRAMME_COVERAGE')
    for m in a['programmes']:
        identity_budget(m)
        saved=private['programmes'].get(m['id'])
        if saved:
            need(saved['programme']==m,'ADMISSION_SAVED_MANIFEST_CHANGED')
            # Full restore checks the saved result journal and schema; definitions
            # were validated before their first claim. Never refreeze on resume.
            from .programs import Laboratory
            Laboratory.restore(saved,history)
        else:validate_manifest(m,history,book)
    private['trial_book']=book.export();return book

def can_recover_before_exposure(state,jobs):
    p=state.get('pending')
    if not p or p.get('phase')!='PRE_EXPOSURE':return False
    by={j['name']:j for j in jobs}
    if len(by)!=len(jobs):return False
    claim=by.get('segment-intent');fence=by.get('execution-fence');worker=by.get('investigation')
    return bool(claim and claim['status']=='completed' and claim['conclusion']=='failure' and fence and worker and all(j['status']=='completed' and j['conclusion']=='skipped' for j in (fence,worker)))

def require_jobs(jobs,names):
    for name in names:
        found=[j for j in jobs if j['name']==name];need(len(found)==1 and found[0]['status']=='completed' and found[0]['conclusion']=='success','NATIVE_JOB_NOT_SUCCESS_'+name.upper().replace('-','_'))
