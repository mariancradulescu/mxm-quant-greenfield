"""V3 cold-process proof producer. The producer only runs after decrypting the
actual remotely fetched ciphertext inside the independent cold-readback job.

This module cannot issue a certificate and never equates fixture tests with
native programme progress or authentic Pepperstone data.
"""
from .common import need,digest
from .data import DataCatalogue
from .execution import catalogue_extends

COLD_SCHEMA='mxm.integrated-cold-readback.v3'
ADAPTER_SCHEMA='mxm.e2e.authentic-adapter.v3'
NEGATIVE_SCHEMA='mxm.e2e.native-negatives.v3'

def cold_attestation(private, public, admission, evidence_oid, run_id, source_sha):
    need(public['pending'] is None and public['safe_stop'] is True and
         private['pending'] is None and private['safe_stop'] is True and
         private['source_sha']==public['source_sha']==source_sha and
         private['sequence']==public['sequence'] and
         private['sequence']>=21 and public['last_run_id']==run_id,
         'COLD_V3_STATE_IDENTITY')
    from .protocol import accounting,ORIGINAL_PUBLIC
    from .admission import TypedTrialBook
    book=TypedTrialBook.restore(private['trial_book'])
    need(accounting(book.export())==public['accounting'] and
         public['original_public_sha256']==ORIGINAL_PUBLIC and
         book.baseline['legacy_snapshot']['used']['V2']==22,
         'COLD_V3_LEDGER_NO_RESET')
    shared=DataCatalogue.restore(private['shared_catalogue'])
    programmes=[]
    for ident,saved in sorted(private['programmes'].items()):
        from .programs import Laboratory
        lab=Laboratory.restore(saved,private['history'],
                               shared_catalogue=shared.export())
        need(saved['programme']['id']==ident and
             lab.checkpoint()['progress']==saved['progress'],
             'COLD_V3_PROGRAMME_RESTORE')
        catalogue_extends(shared.export(),saved['catalogue'])
        need(type(saved['acquisition_remaining']) is int and
             saved['acquisition_remaining']>=0 and
             all(type(v) is int and v>=0 for v in
                 saved['acquisition_budget'].values()),
             'COLD_V3_RESOURCE_REMAINING')
        programmes.append({
            'id':ident,'checkpoint_sha256':digest(saved),
            'progress_sha256':digest(saved['progress']),
            'catalogue_sha256':digest(saved['catalogue']),
            'acquisition_budget_sha256':digest(saved['acquisition_budget']),
            'acquisition_remaining':saved['acquisition_remaining'],
            'native_receipts_sha256':digest(saved['native_receipts']),
            'steps_used':saved['progress']['steps_used'],
            'safe_stop':saved['progress']['safe_stop']})
    admitted={m['id'] for m in admission['programmes']}
    need(all(x in private['programmes'] for x in admitted) and
         all(private['programmes'][x]['progress']['safe_stop'] for x in admitted),
         'COLD_V3_ADMITTED_PROGRAMMES_OPEN')
    # The actual timeline, not a two-program count, proves A-B-A.
    # Legacy records cannot fabricate a v3 execution order retrospectively.
    events=private.get('programme_execution_history',[])
    need(type(events) is list,'COLD_V3_EVENT_JOURNAL')
    chain=[x['programme'] for x in events if
           type(x) is dict and x.get('native_checkpoint_sequence') is not None]
    aba=any(chain[i]==chain[k] and chain[i]!=chain[j]
            for i in range(len(chain)) for j in range(i+1,len(chain))
            for k in range(j+1,len(chain)))
    actual_adapter=[]
    for item in programmes:
        saved=private['programmes'][item['id']]
        for task,result in saved['progress']['results'].items():
            if result.get('operator')!='native_corpus_readonly':continue
            value=result.get('value',{})
            need(value.get('classification')==
                 'AUTHENTIC_CORPUS_NONOUTCOME_VERIFIED' and
                 type(value.get('verified_quote_rows')) is int and
                 value['verified_quote_rows']>0 and
                 value.get('broker_requests')==value.get('economic_outcomes')==
                 value.get('orders')==0 and value.get('fixture_only') is False,
                 'COLD_V3_AUTHENTIC_OPERATOR_REJECTED')
            ids=value.get('asset_ids',[])
            need(bool(ids) and all(x in shared.assets and
                shared.assets[x]['trust']=='AUTHENTICATED_NATIVE_CUSTODY'
                and shared.assets[x]['source']=='PRESERVED_AUTHENTIC_PEPPERSTONE_QUOTE'
                for x in ids),'COLD_V3_AUTHENTIC_SOURCE_BINDING')
            actual_adapter.append({
                'programme':item['id'],'task':task,
                'result_sha256':digest(result),
                'asset_ids':ids,
                'preserved_corpus_sha256':value['preserved_ciphertext_sha256'],
                'verified_quote_rows':value['verified_quote_rows']})
    origin=private.get('programme_accounting_origins',{}).get(
        digest(admission),{'economic_observations':29})
    need(public['accounting']['economic_observations']-
         origin['economic_observations']==0 and
         public['accounting']['refunds']==0,'COLD_V3_OUTCOMES_CHANGED')
    return {
        'schema':COLD_SCHEMA,'source_sha':source_sha,'run_id':run_id,
        'evidence_oid':evidence_oid,'sequence':public['sequence'],
        'ciphertext_sha256':public['ciphertext_sha256'],
        'private_sha256':digest(private),'accounting':public['accounting'],
        'shared_catalogue_sha256':digest(shared.export()),
        'shared_catalogue_asset_count':len(shared.assets),
        'shared_catalogue_quarantine_sha256':digest(shared.quarantine),
        'programme_checkpoints':programmes,
        'programme_execution_history_sha256':digest(events),
        'multi_program_A_B_A_verified':aba,
        'budgets_and_quarantine_verified':True,
        'authentic_nonoutcome_results':actual_adapter,
        'all_admitted_programmes_complete':True,'original_unchanged':True,
        'orders':0,'new_outcomes':0,'economic_workflow_released':False
    }

def native_adapter_attestation(cold):
    """No positive adapter attestation unless a real cold-restored result exists."""
    need(cold['schema']==COLD_SCHEMA and
         cold['authentic_nonoutcome_results'],'V3_AUTHENTIC_PROOF_ABSENT')
    values=cold['authentic_nonoutcome_results']
    need(len({(x['programme'],x['task']) for x in values})==len(values) and
         all(x['verified_quote_rows']>0 for x in values),
         'V3_ADAPTER_EVIDENCE')
    return {'schema':ADAPTER_SCHEMA,'source_sha':cold['source_sha'],
            'checkpoint_oid':cold['evidence_oid'],
            'run_id':cold['run_id'],'cold_private_sha256':cold['private_sha256'],
            'cold_proof_sha256':digest(cold),
            'nonoutcome_result_refs':values,
            'preserved_corpus_sha256':values[0]['preserved_corpus_sha256'],
            'orders':0,'economic_outcomes':0,'fixture_only':False}
