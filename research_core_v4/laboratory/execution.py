"""Shared authentic-data binding and checkpoint conservation for native nodes."""
from copy import deepcopy
from .common import need
from .data import LazyNativeCollector

def bind_native(lab,corpus,collector_factory=LazyNativeCollector):
    need(lab.m['mode']=='DEVELOPMENT_RESEARCH','NATIVE_BINDING_MODE')
    lab.authentic_corpus=deepcopy(corpus)
    lab.authentic_corpus['raw_quote_receipts'].extend(r['quote_point'] for r in lab.acquisition.receipts if r.get('quote_point'))
    lazy=collector_factory({k:lab.acquisition.budget.get(k,0) for k in ('M5','H1','BID_ASK')});lab.acquisition.collector=lazy;return lazy

def preserve_node(private,lab):
    # One authoritative shared catalogue across programmes; acquisition.remaining
    # is an integer and is persisted by Laboratory.checkpoint, never reset here.
    private['programmes'][lab.m['id']]=lab.checkpoint();private['shared_catalogue']=lab.cache.export()
