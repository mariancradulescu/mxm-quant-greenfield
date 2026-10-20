"""Shared authentic-data binding and checkpoint conservation for native nodes."""
from copy import deepcopy
from .common import need
from .data import LazyNativeCollector

def bind_native(lab,corpus,collector_factory=LazyNativeCollector):
    need(lab.m['mode']=='DEVELOPMENT_RESEARCH','NATIVE_BINDING_MODE')
    lab.authentic_corpus=deepcopy(corpus)
    lab.authentic_corpus['raw_quote_receipts'].extend(r['quote_point'] for r in lab.acquisition.receipts if r.get('quote_point'))
    lazy=collector_factory({k:lab.acquisition.budget.get(k,0) for k in ('M5','H1','BID_ASK')});lab.acquisition.collector=lazy;return lazy

def catalogue_extends(new, old):
    """Fail closed if a shared cache lost any prior asset, provenance or quarantine.

    Overlapping IDs must have exactly the same normalized rows and trust metadata;
    quarantine is append-only, never deduplicated or silently repaired.
    """
    from .data import DataCatalogue
    DataCatalogue.restore(new)
    DataCatalogue.restore(old)
    need(set(old['assets']).issubset(new['assets']), 'SHARED_CATALOGUE_LOST_ASSET')
    for asset_id, old_meta in old['assets'].items():
        need(new['assets'][asset_id] == old_meta and
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
