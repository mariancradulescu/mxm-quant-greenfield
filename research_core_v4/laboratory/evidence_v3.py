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
         all(private['programmes'][x]['progress']['safe_stop'] and
             private['programmes'][x]['progress']['stop_reason']=='AUTHORIZED_PROGRAMME_COMPLETE' and
             set(private['programmes'][x]['progress']['results']).isdisjoint(private['programmes'][x]['progress']['skipped']) and
             set(private['programmes'][x]['progress']['results'])|set(private['programmes'][x]['progress']['skipped'])==set(private['programmes'][x]['programme']['tasks'])
             for x in admitted),
         'COLD_V3_ADMITTED_PROGRAMMES_OPEN')
    # The actual timeline, not a two-program count, proves A-B-A.
    # Legacy records cannot fabricate a v3 execution order retrospectively.
    events=private.get('programme_execution_history',[])
    need(type(events) is list,'COLD_V3_EVENT_JOURNAL')
    need(private.get('programme_execution_history_seal')=={
         'count':len(events),'head_sha256':events[-1]['event_sha256'] if events else None},
         'COLD_V3_EVENT_ENDPOINT_CHANGED')
    previous=None
    previous_ids=set()
    names=[]
    observed=set()
    for i,event in enumerate(events):
        need(type(event) is dict and
             event.get('previous_event_sha256')==previous and
             event.get('event_sha256')==
             digest({k:v for k,v in event.items() if k!='event_sha256'})
             and event.get('programme') in private['programmes'] and
             type(event.get('native_checkpoint_sequence')) is int and
             type(event.get('within_segment_step')) is int and
             event['within_segment_step']>0,
             'COLD_V3_NATIVE_JOURNAL_CHAIN')
        saved=private['programmes'][event['programme']]
        identity=(event['programme'],event['task'])
        need(identity not in observed,'COLD_V3_DUPLICATE_TASK_EVENT')
        observed.add(identity)
        need(event['task'] in saved['progress']['results'] and
             digest(saved['progress']['results'][event['task']])==
             event['result_sha256'] and
             event['programme_budget_remaining']>=0,
             'COLD_V3_NATIVE_EVENT_RESULT')
        before=event['catalogue_before_asset_ids']
        after=event['catalogue_after_asset_ids']
        need(before==sorted(set(before)) and
             after==sorted(set(after)) and
             set(before)<=set(after)<=set(shared.assets),
             'COLD_V3_EVENT_ASSET_CONSERVATION')
        if i:
            need(set(before)==previous_ids and
                 (event['native_checkpoint_sequence']>
                  events[i-1]['native_checkpoint_sequence'] or
                  (event['native_checkpoint_sequence']==
                   events[i-1]['native_checkpoint_sequence'] and
                   event['within_segment_step']>
                   events[i-1]['within_segment_step'])),
                 'COLD_V3_EVENT_ORDER_OR_CATALOGUE_DRIFT')
        previous_ids=set(after);previous=event['event_sha256']
        names.append(event['programme'])
    # Every task in the current admission must be witnessed exactly once.
    # A valid hash chain prefix is not evidence of terminality.
    expected={(ident,task) for ident in admitted
              for task in private['programmes'][ident]['progress']['results']}
    need({x for x in observed if x[0] in admitted}==expected,
         'COLD_V3_TASK_EVENT_BIJECTION')
    for ident in admitted:
        saved=private['programmes'][ident]
        need([e['task'] for e in events if e['programme']==ident]==
             [e['task'] for e in saved['progress']['journal']],
             'COLD_V3_PROGRAMME_EVENT_ORDER')
    # To count as native A-B-A, B must have added at least one preserved
    # asset, and the later A must carry that asset forward.
    aba=any(
        names[i]==names[k] and names[i]!=names[j] and
        bool(set(events[j]['catalogue_after_asset_ids'])-
             set(events[j]['catalogue_before_asset_ids'])) and
        set(events[j]['catalogue_after_asset_ids'])<=
        set(events[k]['catalogue_before_asset_ids'])
        for i in range(len(names)) for j in range(i+1,len(names))
        for k in range(j+1,len(names)))
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
         all(x['verified_quote_rows']>0 and x['preserved_corpus_sha256']==
             values[0]['preserved_corpus_sha256'] for x in values),
         'V3_ADAPTER_EVIDENCE')
    return {'schema':ADAPTER_SCHEMA,'source_sha':cold['source_sha'],
            'checkpoint_oid':cold['evidence_oid'],
            'run_id':cold['run_id'],'cold_private_sha256':cold['private_sha256'],
            'cold_proof_sha256':digest(cold),
            'nonoutcome_result_refs':values,
            'preserved_corpus_sha256':values[0]['preserved_corpus_sha256'],
            'orders':0,'economic_outcomes':0,'fixture_only':False}
