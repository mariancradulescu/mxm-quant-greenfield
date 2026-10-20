"""Shared authentic-data binding and checkpoint conservation for native nodes."""
from copy import deepcopy
from .common import need
from .data import LazyNativeCollector

def bind_native(lab,corpus,collector_factory=LazyNativeCollector):
    need(lab.m['mode']=='DEVELOPMENT_RESEARCH','NATIVE_BINDING_MODE')
    lab.authentic_corpus=deepcopy(corpus)
    lab.authentic_corpus['raw_quote_receipts'].extend(r['quote_point'] for r in lab.acquisition.receipts if r.get('quote_point'))
    lazy=collector_factory({k:lab.acquisition.budget.get(k,0) for k in ('M5','H1','BID_ASK')});lab.acquisition.collector=lazy;return lazy

def preserved_legacy_conflict(catalogue, ident, new_meta, old_meta):
    if new_meta.get('identity_version') not in (None,1) or old_meta.get('identity_version') not in (None,1):
        return False
    if {k for k in set(new_meta)|set(old_meta) if new_meta.get(k)!=old_meta.get(k)}!={'trust'}:
        return False
    return any(q.get('reason')=='LEGACY_TRUST_PROVENANCE_CONFLICT' and
               q.get('asset_id')==ident and new_meta in q.get('metadata_variants',[]) and
               old_meta in q.get('metadata_variants',[]) for q in catalogue['quarantine'])


def quarantine_legacy_trust_conflicts(shared, catalogues):
    """Append immutable conflicting metadata variants; never choose better trust.

    Used only after the exact closed predecessor private hash is authenticated.
    Original assets, rows, programmes and ledgers remain byte-for-byte intact.
    A quarantined identity cannot be queried or consumed by feature adapters.
    """
    from .data import DataCatalogue
    from .common import digest
    DataCatalogue.restore(shared)
    result=deepcopy(shared)
    variants={}
    for saved in catalogues:
        DataCatalogue.restore(saved)
        need(set(saved['assets'])<=set(shared['assets']),'SHARED_CATALOGUE_LOST_ASSET')
        need(shared['quarantine'][:len(saved['quarantine'])]==saved['quarantine'],
             'SHARED_CATALOGUE_LOST_QUARANTINE')
        for ident, old in saved['assets'].items():
            new=shared['assets'][ident]
            need(shared['rows'][ident]==saved['rows'][ident],'SHARED_CATALOGUE_PROVENANCE_CONFLICT')
            if new==old:continue
            need(new.get('identity_version') in (None,1) and old.get('identity_version') in (None,1) and
                 {k for k in set(new)|set(old) if new.get(k)!=old.get(k)}=={'trust'},
                 'SHARED_CATALOGUE_PROVENANCE_CONFLICT')
            if preserved_legacy_conflict(result,ident,new,old):continue
            variants.setdefault(ident,{})[digest(new)]=new
            variants[ident][digest(old)]=old
    for ident, values in sorted(variants.items()):
        result['quarantine'].append({'reason':'LEGACY_TRUST_PROVENANCE_CONFLICT',
            'asset_id':ident,'metadata_variants':[deepcopy(values[h]) for h in sorted(values)]})
    for saved in catalogues:catalogue_extends(result,saved)
    catalogue_extends(result,shared)
    return result


def catalogue_extends(new, old):
    """Fail closed if a shared cache lost any prior asset, provenance or quarantine.

    Overlapping rows are exact. Differing legacy trust is permitted only when
    both complete metadata variants are retained in an explicit read-blocking
    quarantine. No trust variant is selected, upgraded or silently repaired.
    """
    from .data import DataCatalogue
    DataCatalogue.restore(new)
    DataCatalogue.restore(old)
    need(set(old['assets']).issubset(new['assets']), 'SHARED_CATALOGUE_LOST_ASSET')
    for asset_id, old_meta in old['assets'].items():
        need((new['assets'][asset_id] == old_meta or
              preserved_legacy_conflict(new,asset_id,new['assets'][asset_id],old_meta)) and
             new['rows'][asset_id] == old['rows'][asset_id],
             'SHARED_CATALOGUE_PROVENANCE_CONFLICT')
    need(new['quarantine'][:len(old['quarantine'])] == old['quarantine'],
         'SHARED_CATALOGUE_LOST_QUARANTINE')

def preserve_node(private,lab):
    # Never replace the durable shared catalogue with a stale programme snapshot.
    # A resumed programme must first restore using the exact common catalogue.
    new_catalogue=lab.cache.export()
    previous=private.get('shared_catalogue')
    if previous is not None:catalogue_extends(new_catalogue,previous)
    checkpoint=lab.checkpoint()
    private['programmes'][lab.m['id']]=checkpoint
    private['shared_catalogue']=deepcopy(new_catalogue)

def preserved_pepperstone_nonoutcome(lab,corpus,limit):
    """Consume preserved decrypted Pepperstone quote evidence, never synthetic fills.

    No client ID, market API request, economic trial, order or outcome is opened.
    Missing authentic observations fail closed rather than becoming fixtures.
    """
    from .data import DEVELOPMENT_END_MS
    from .common import digest
    from .runtime import preserved_registry
    need(lab.m['mode']=='TECHNICAL_NONOUTCOME' and
         lab.m['budget']['broker_requests']==0 and
         type(limit) is int and 0<limit<=32,
         'AUTHENTIC_NONOUTCOME_TECHNICAL_SCOPE')
    need(isinstance(corpus,dict) and
         isinstance(corpus.get('raw_quote_receipts'),list) and
         isinstance(corpus.get('catalog',{}).get('full'),dict),
         'AUTHENTIC_NONOUTCOME_CORPUS')
    registry=preserved_registry()
    source_sha=registry['cached_input']['ciphertext_sha256']
    need(isinstance(source_sha,str) and len(source_sha)==64,
         'AUTHENTIC_NONOUTCOME_CIPHER_BINDING')
    ids=[];rows=0
    for q in corpus['raw_quote_receipts'][:limit]:
        from .data import verify_quote_reference
        verify_quote_reference(q)
        t=q['boundary_ms'];sid=str(q['symbol_id'])
        need(sid in corpus['catalog']['full'] and
             type(t) is int and 60000<=t<DEVELOPMENT_END_MS,
             'AUTHENTIC_NONOUTCOME_SYMBOL_AND_WINDOW')
        points=[]
        for side,value in q['sides'].items():
            if value.get('state')!='AUTHENTIC_CAUSAL_QUOTE':
                continue
            need(side in ('bid','ask'),'AUTHENTIC_NONOUTCOME_SIDE')
            points.append({'t':value['timestamp_ms'],
                           'available_at':value['timestamp_ms'],
                           'side':side,'price':value['price']})
        if not points:continue
        manifest={'instrument':sid,'resolution':'BID_ASK',
                  'partition':'DEVELOPMENT','start_ms':t-60000,'end_ms':t+1,
                  'source':'PRESERVED_AUTHENTIC_PEPPERSTONE_QUOTE',
                  'source_sha256':digest(q),'available_at_ms':t,
                  'session_semantics':'POINT_REFERENCE_NOT_CONTINUOUS',
                  'completeness':'UNRESOLVED',
                  'account_scope':'EXISTING_AUTHENTICATED_ACCOUNT_FINGERPRINT'}
        asset=lab.cache.ingest(manifest,points,trust='AUTHENTICATED_NATIVE_CUSTODY')
        quality=lab.cache.assets[asset]
        need(quality['invalid']==quality['conflicts']==0 and
             quality['row_count']>0,'AUTHENTIC_NONOUTCOME_QUALITY')
        ids.append(asset);rows+=quality['row_count']
    need(rows>0,'AUTHENTIC_NONOUTCOME_EMPTY')
    return {'classification':'AUTHENTIC_CORPUS_NONOUTCOME_VERIFIED',
            'preserved_ciphertext_sha256':source_sha,
            'asset_ids':sorted(set(ids)),
            'instruments':len({lab.cache.assets[k]['instrument'] for k in ids}),
            'verified_quote_rows':rows,'broker_requests':0,
            'economic_outcomes':0,'orders':0,'fixture_only':False}
