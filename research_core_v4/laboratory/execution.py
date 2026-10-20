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
