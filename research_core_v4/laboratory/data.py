"""Catalogue, quality/cache and generic bounded acquisition over existing collector."""
from dataclasses import dataclass,field
from .common import *
DEVELOPMENT_END_MS=1789603200000
KINDS={'M5','H1','BID_ASK'}

@dataclass
class DataCatalogue:
    assets:dict=field(default_factory=dict)
    rows:dict=field(default_factory=dict)
    quarantine:list=field(default_factory=list)
    def ingest(self,manifest,rows,*,trust='UNVERIFIED'):
        required={'instrument','resolution','partition','start_ms','end_ms','source','source_sha256','available_at_ms','session_semantics','completeness','account_scope'}
        need(required<=set(manifest),'MANIFEST_FIELDS');m=dict(manifest)
        need(not set(m)&{'id','normalized_sha256','row_count','conflicts','invalid','interpolated','trust','identity_version'},'MANIFEST_RESERVED_FIELDS')
        need(m['partition'] in ('DEVELOPMENT','CONFIRMATION','PROTECTED'),'PARTITION')
        need(len(m['source_sha256'])==64 and m['source'] and m['account_scope'],'PROVENANCE')
        need(type(m['start_ms']) is int and type(m['end_ms']) is int and m['start_ms']<m['end_ms'],'INTERVAL')
        if m['partition']=='DEVELOPMENT':need(m['end_ms']<=DEVELOPMENT_END_MS,'PROTECTED_DATA')
        need(m['resolution'] in KINDS,'RESOLUTION_NOT_IMPLEMENTED')
        normalized=[];seen={};conflicts=set();invalid=[];ranks={}
        for original in rows:
            r=dict(original);t=utc_ms(r['t']);a=utc_ms(r.get('available_at',r['t']))
            need(m['start_ms']<=t<m['end_ms'] and a>=t,'ROW_TIME')
            r['t']=t;r['available_at']=a
            key=(t,r.get('side','M5'))
            if m['resolution'] in ('M5','H1'):
                period=300000 if m['resolution']=='M5' else 3600000
                good=a>=t+period and t%period==0 and all(number(r.get(k)) for k in ('open','high','low','close','volume'))
                good=good and min(r.get(k,0) for k in ('open','high','low','close'))>0 and r.get('volume',-1)>=0
                good=good and r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']
            else:good=r.get('side') in ('bid','ask') and number(r.get('price')) and r['price']>0
            if not good:invalid.append({'row_sha256':digest(r),'reason':'INVALID_NATIVE_VALUE_OR_GRID'});continue
            if m['resolution']=='BID_ASK':
                # Independent side streams have no fabricated cross-side
                # sequence. Preserve every update in source order within side.
                rank=ranks.get(key,0);ranks[key]=rank+1
                r['source_side_rank']=rank;key=(*key,rank)
            if key in seen and seen[key]!=r:conflicts.add(key)
            else:seen[key]=r
        for k in conflicts:seen.pop(k,None)
        normalized=[seen[k] for k in sorted(seen)];self.quarantine.extend(invalid)
        self.quarantine.extend({'key':list(k),'reason':'CONFLICT_NO_FAVORABLE_DEDUPLICATION'} for k in sorted(conflicts))
        # The raw source identity is preserved separately from the normalized digest.
        m['identity_version']=2
        ident=digest({'manifest':m,'normalized':normalized,'trust':trust})
        self.assets[ident]={**m,'id':ident,'normalized_sha256':digest(normalized),'row_count':len(normalized),
            'conflicts':len(conflicts),'invalid':len(invalid),'interpolated':False,'trust':trust}
        self.rows[ident]=normalized
        return ident
    def query(self,instrument,resolution,start_ms,end_ms,partition='DEVELOPMENT',authentic_only=False):
        ids=[k for k,m in self.assets.items() if m['instrument']==instrument and m['resolution']==resolution and m['partition']==partition and m['start_ms']<=start_ms and m['end_ms']>=end_ms and m['completeness']=='CONFIRMED_COMPLETE' and not m['conflicts'] and not m['invalid'] and self.structural_support(k,start_ms,end_ms) and (not authentic_only or m.get('trust') in ('AUTHENTICATED_NATIVE_CUSTODY','AUTHENTICATED_NATIVE_COLLECTION'))]
        return sorted(k for k in ids if not self.is_quarantined(k))
    def is_quarantined(self,ident):
        return any(q.get('reason')=='LEGACY_TRUST_PROVENANCE_CONFLICT' and
                   q.get('asset_id')==ident for q in self.quarantine)
    def require_usable(self,ident):
        need(ident in self.assets and not self.is_quarantined(ident),'CACHE_PROVENANCE_QUARANTINED')
    def structural_support(self,ident,start_ms,end_ms):
        """Necessary support, never a certification of provenance or sessions.

        Updates are asynchronous. Carry forward only observed sides, never
        invent an opposite quote or treat absence as a closed session.
        """
        if self.is_quarantined(ident):return False
        rows=[r for r in self.rows[ident] if start_ms<=r['t']<end_ms]
        if not rows:return False
        m=self.assets[ident]
        if m['resolution']!='BID_ASK':return True
        if {r['side'] for r in rows}!={'bid','ask'}:return False
        quotes={}
        for r in sorted(rows,key=lambda r:(r['available_at'],r['t'])):
            quotes[r['side']]=r['price']
            if len(quotes)==2 and quotes['bid']>quotes['ask']:return False
        return True
    def view(self,asset_id,decision_ms):
        self.require_usable(asset_id)
        m=self.assets[asset_id];need(m['partition']=='DEVELOPMENT','PROTECTED_READ_GATE')
        return [r for r in self.rows[asset_id] if r['available_at']<=decision_ms]
    def gaps(self,asset_id,expected_times):
        m=self.assets[asset_id];actual={r['t'] for r in self.rows[asset_id]}
        return {'missing_times':sorted(set(expected_times)-actual),'absence_means_session_closed':False,'manifest_completeness':m['completeness']}
    def export(self):return {'assets':self.assets,'rows':self.rows,'quarantine':self.quarantine}
    @classmethod
    def restore(cls,value):
        cat=cls()
        for ident,m in value['assets'].items():
            rows=value['rows'][ident];need(digest(rows)==m['normalized_sha256'],'CACHE_CHANGED')
            basis={'manifest':{k:v for k,v in m.items() if k not in ('id','normalized_sha256','row_count','conflicts','invalid','interpolated','trust')},'normalized':rows}
            if m.get('identity_version')==2:basis['trust']=m['trust']
            need(digest(basis)==ident,'CACHE_MANIFEST_CHANGED')
        # Detach snapshots before mutation: validation must never mutate their
        # source or a sibling programme's durable cache by reference.
        from copy import deepcopy
        need(set(value['assets'])==set(value['rows']) and isinstance(value['quarantine'],list),'CACHE_KEYS_AND_QUARANTINE')
        cat.assets=deepcopy(value['assets']);cat.rows=deepcopy(value['rows']);cat.quarantine=deepcopy(value['quarantine']);return cat

class Acquisition:
    """Whitelist adapter. No orders, arbitrary endpoints, retries or new providers."""
    def __init__(self,cache,collector,budget):self.cache=cache;self.collector=collector;self.budget=dict(budget);self.receipts=[];self.remaining=budget.get('TOTAL',sum(budget.values()))
    def request(self,plan):
        need(plan['provider']=='PEPPERSTONE_OPEN_API' and plan['partition']=='DEVELOPMENT','DATA_DOMAIN')
        need(plan['kind'] in KINDS and 0<=plan['start_ms']<plan['end_ms']<=DEVELOPMENT_END_MS,'ACQUISITION_SCOPE')
        need(plan.get('read_only') is True and plan.get('automatic_retries',0)==0,'ACQUISITION_MODE')
        hit=self.cache.query(plan['instrument'],plan['kind'],plan['start_ms'],plan['end_ms'],authentic_only=True)
        if hit:return {'state':'CACHE_REUSED','asset_id':hit[0],'requests':0}
        # Reserve the whole bounded call before any possible network send.
        cap=plan['max_pages'];need(type(cap) is int and cap==(2 if plan['kind']=='BID_ASK' else 3),'PAGE_CAP')
        need(self.budget.get(plan['kind'],0)>=cap and self.remaining>=cap,'ACQUISITION_BUDGET');self.budget[plan['kind']]-=cap;self.remaining-=cap
        need(self.collector is not None,'ACQUISITION_TRANSPORT_UNAVAILABLE')
        if plan['kind'] in ('M5','H1'):
            period=300 if plan['kind']=='M5' else 3600
            values,raw,state=getattr(self.collector,plan['kind'].lower())(plan['symbol_id'],plan['digits'],plan['start_ms']//1000,plan['end_ms']//1000)
            rows=[{'t':t*1000,'available_at':(t+period)*1000,**dict(zip(('open','high','low','close','volume'),v))} for t,v in values.items()]
        else:
            need(plan['end_ms']-plan['start_ms']==60000,'QUOTE_WINDOW')
            q=self.collector.quote(plan['symbol_id'],plan['end_ms']//1000);raw=q.get('pages',[]);state='COMPLETE_EXACT_WINDOW' if len(raw)==2 and {p['side'] for p in raw}=={'bid','ask'} and all(p.get('hasMore') is False for p in raw) else 'QUOTE_WINDOW_UNRESOLVED'
            from m6.cost_evidence import decode_ctrader_tick_page
            rows=[{'t':z.timestamp_ms,'available_at':z.timestamp_ms,'side':page['side'],'price':z.raw_tick/100000} for page in raw for z in decode_ctrader_tick_page(page['encoded']) if plan['start_ms']<=z.timestamp_ms<plan['end_ms']]
        complete='CONFIRMED_COMPLETE' if state=='COMPLETE_EXACT_WINDOW' else 'UNRESOLVED'
        manifest={'instrument':plan['instrument'],'resolution':plan['kind'],'partition':'DEVELOPMENT','start_ms':plan['start_ms'],'end_ms':plan['end_ms'],'source':'PEPPERSTONE_OPEN_API_NATIVE_RESPONSE','source_sha256':digest(raw),'available_at_ms':plan['end_ms'],'session_semantics':'AUTHENTIC_GAPS_RETAINED;NO_SESSION_INFERENCE','completeness':complete,'account_scope':plan['account_scope']}
        ident=self.cache.ingest(manifest,rows,trust='AUTHENTICATED_NATIVE_COLLECTION');receipt={'state':state,'asset_id':ident,'native_receipts':raw,'plan_sha256':digest(plan),'budget_reserved':cap}
        if plan['kind']=='BID_ASK':receipt['quote_point']=q
        self.receipts.append(receipt);return receipt


def native_collector(caps):
    # Existing authentication verifies exact account fingerprint, live EUR broker
    # domain and explicit VIEW scope. Credentials are never read by catalogue code.
    from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector
    return Collector({'M5':caps.get('M5',0),'BID_ASK':caps.get('BID_ASK',0),'NONHISTORY':0,'H1':caps.get('H1',0)})

class LazyNativeCollector:
    """Connect only on cache miss, after the durable segment intent exists."""
    def __init__(self,caps):self.caps=caps;self.instance=None
    def __getattr__(self,name):
        need(name in ('m5','h1','quote'),'TRANSPORT_METHOD_WHITELIST')
        if self.instance is None:
            self.instance=native_collector(self.caps);self.instance.connect()
        return getattr(self.instance,name)
    def close(self):
        if self.instance is not None:self.instance.close()
