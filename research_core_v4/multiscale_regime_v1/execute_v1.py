"""One new authenticated two-law comparison, full-universe current economics."""
import os,json,pathlib,tempfile,math
from collections import Counter,defaultdict,deque
from research_core_v4.multiscale_regime_v1.runtime_v1 import gate,e,rt,P
from research_core_v4.multiscale_regime_v1.kernel_v1 import observations,evaluate,merge,NAMES,family_sensitivity,n
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.owner_recovery_v1.readback_v1 import describe,iso
PHASE='GATE'
def current_source(auth):
    tag='mxm-owner-frontier-costuniverse-'+auth['invocation_id'][:12]+'-'+os.environ['GITHUB_RUN_ID']
    rel=e.w.old.api('releases/tags/'+tag)
    assets=e.w.old.api('releases/'+str(rel['id'])+'/assets?per_page=100')
    a=next(x for x in assets if x['name']=='costuniverse-private-result.mxmenc')
    return {'release_id':rel['id'],'asset_id':a['id'],'ciphertext_sha256':a['digest'].split(':')[1]}
def corpus(key,fp,tmp,master,entries,digits,manifest,metadata):
    rel=e.w.old.api('releases/tags/'+manifest['DURABLE_RELEASE_IDENTITY']);assets={x['name']:x for x in e.w.old.api('releases/'+str(rel['id'])+'/assets?per_page=100')}
    results={name:[] for name in NAMES};prov=[];countall=0;fx=defaultdict(list)
    for shard in range(25):
        buffers={o:{} for o in range(shard*64+1,min(1576,shard*64+64)+1)}
        for segment in range(1,5):
            entry=entries[(segment-1)*25+shard];asset=assets[entry['ENCRYPTED_ASSET_NAME']]
            e.w.old.need(asset['digest']=='sha256:'+entry['ENCRYPTED_ASSET_SHA256'],'SHARD_METADATA')
            blob=e.w.old.download(asset['browser_download_url'],asset['size']);e.w.old.need(e.a.sha(blob)==entry['ENCRYPTED_ASSET_SHA256'],'SHARD_CIPHER')
            raw=e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp);e.w.old.need(e.a.sha(raw)==entry['PLAINTEXT_CANONICAL_SHA256'],'SHARD_PLAINTEXT')
            obj=e.w.n.canonical.strict_json(raw);e.w.old.need(e.w.n.canonical.canonical(obj)==raw and set(obj)==e.w.n.canonical.PACKAGE_KEYS and obj['segment_index']==segment and obj['shard_index']==shard and obj['identity_range']==entry['IDENTITY_RANGE'],'SHARD_PACKAGE')
            lo,hi=entry['IDENTITY_RANGE'];e.w.old.need(len(obj['items'])==hi-lo+1,'SHARD_ITEMS');count=0
            for ordinal,item in zip(range(lo,hi+1),obj['items']):
                e.w.old.need(item['ordinal']==ordinal and item['symbol_id']==master[ordinal-1]['symbol_id'] and item['failure'] is None,'SHARD_IDENTITY');previous=-1
                for row in item['rows']:
                    ts,bar=e.w.n._bar(row,digits[item['symbol_id']]);e.w.old.need(ts>previous and ts not in buffers[ordinal] and (ts-n.START)//604800==segment-1,'SHARD_ROW_ORDER');previous=ts;count+=1;buffers[ordinal][ts]=bar
            e.w.old.need(count==entry['ROW_COUNT'] and entry['PROTECTED_FORWARD_ROW_COUNT']==0,'SHARD_COUNTS');countall+=count
            prov.append({'segment':segment,'shard':shard,'ciphertext_sha256':entry['ENCRYPTED_ASSET_SHA256'],'canonical_sha256':entry['PLAINTEXT_CANONICAL_SHA256'],'rows':count})
        for ordinal,bars in buffers.items():
            sid=master[ordinal-1]['symbol_id'];r=metadata.get(sid,{})
            if r.get('asset_class')=='Forex (Spot)' and r.get('base_asset') and r.get('quote_asset'):
                for j in range(0,672,4):
                    action=n.START+j*3600+900;b=bars.get(action-300)
                    if b is not None and n.frozen.valid_bar(action-300,b,action) and b['tick_volume']>0:
                        fx[action].append((sid,r['base_asset'],r['quote_asset'],b['close']))
            obs=observations(bars)
            for name in NAMES:results[name].append(evaluate(sid,obs[name]))
        del buffers;e.w.old.budget(maxwall=2100,maxcpu=1800,maxkib=2097152)
    e.w.old.need(countall==3355389 and len(prov)==100 and all(len(v)==1576 for v in results.values()),'COMPLETE_CORPUS')
    return results,prov,fx,countall
def conversion(edges,src,dst):
    if src==dst:return 1.
    graph=defaultdict(list)
    for sid,a,b,p in sorted(edges):graph[a].append((b,p,sid));graph[b].append((a,1/p,sid))
    q=deque([(src,1.,0)]);seen={src}
    while q:
        a,rate,d=q.popleft()
        if d>=4:continue
        for b,p,sid in sorted(graph[a],key=lambda x:(x[0],x[2])):
            if b==dst:return rate*p
            if b not in seen:seen.add(b);q.append((b,rate*p,d+1))
    return None
def ticket_hurdle(r,tr,edges):
    try:
        price=tr['entry_reference_price'];units=float(r['min_volume_cents'])/100;lots=float(r['min_volume_cents'])/float(r['lot_size']);quote=r['quote_asset'];qeur=conversion(edges,quote,'EUR');usdq=conversion(edges,'USD',quote)
        if price is None or price<=0 or qeur is None:return {'state':'NOTIONAL_OR_EUR_CONVERSION_UNKNOWN'}
        notional=units*price;typ=r['commission_rate_unit'];rate=float(r['commission_rate_normalized']);minimum=float(r['min_commission_normalized']);mt=str(r['min_commission_type']);mc=r.get('min_commission_asset');minq=minimum if mt in ('2','QUOTE_CURRENCY') else minimum*conversion(edges,mc,quote) if mt in ('1','CURRENCY') and conversion(edges,mc,quote) is not None else None
        if minq is None:return {'state':'MINIMUM_FEE_CONVERSION_UNKNOWN','notional_eur':notional*qeur}
        if typ=='PERCENTAGE_OF_VALUE':fee=notional*rate/100
        elif typ=='USD_PER_LOT' and usdq is not None:fee=lots*rate*usdq
        elif typ in ('QUOTE_PER_LOT','QUOTE_CCY_PER_LOT'):fee=lots*rate
        elif typ=='USD_PER_MILLION_USD' and usdq is not None:fee=notional*rate/1e6
        else:return {'state':'COMMISSION_RATE_OR_CONVERSION_UNKNOWN','notional_eur':notional*qeur}
        # Entry notional on both sides: reference-ticket approximation, exit amount varies.
        fee=2*max(fee,minq)
        return {'state':'CURRENT_TERMS_ON_HISTORICAL_REFERENCE','notional_eur':notional*qeur,'round_fee_eur_reference':fee*qeur,'round_fee_bps_reference':fee/notional*10000}
    except (KeyError,TypeError,ValueError,ZeroDivisionError):return {'state':'CONTRACT_OR_CONVERSION_UNKNOWN'}
def economic(results,metadata,quotes,fx):
    qmap={(q['symbol_id'],q['boundary_ms']//1000):q for q in quotes['private_boundary_receipts']}
    reports={};private=[]
    for name,rr in results.items():
        cover=Counter();classes=defaultdict(lambda:{'commission':[],'notional':[],'fee_eur':[],'states':Counter(),'supported_gross':[],'after_current_reference_fee':[]});marks=defaultdict(list);simultaneous=defaultdict(list);iso_counts=defaultdict(Counter)
        for r in rr:
            sid=r['symbol_id'];contract=metadata.get(sid,{});ok,_=eligibility(contract)
            if not ok:continue
            for tr in r['trials']:
                side=(tr['model']>0)-(tr['model']<0)
                if not side:cover['FLAT_PREDICTION']+=1;continue
                c=contract['asset_class'];iw=iso(tr['action']);iso_counts[iw]['structurally_eligible_emitted']+=1;iso_counts[iw]['supported']+=int(tr['y'] is not None)
                simultaneous[tr['action']].append({'sid':sid,'class':c,'margin':float(contract['buy_margin_eur'] if side>0 else contract['sell_margin_eur']),'side':side})
                cost=ticket_hurdle(contract,tr,fx.get(tr['action'],[]));classes[c]['states'][cost['state']]+=1
                if cost.get('round_fee_bps_reference') is not None:
                    classes[c]['commission'].append(cost['round_fee_bps_reference']);classes[c]['notional'].append(cost['notional_eur']);classes[c]['fee_eur'].append(cost['round_fee_eur_reference'])
                    if tr['y'] is not None:classes[c]['supported_gross'].append(side*tr['y']);classes[c]['after_current_reference_fee'].append(side*tr['y']-cost['round_fee_bps_reference'])
                qq=[qmap.get((sid,tr[k])) for k in ('action','exit')];matched=[q is not None and q['two_sided_quote_available'] for q in qq]
                cat='BOTH_BOUNDARIES' if all(matched) else 'PARTIAL_BOUNDARY' if any(matched) else 'NO_MATCHED_BOUNDARY';cover[cat]+=1;cover[('SUPPORTED_' if tr['y'] is not None else 'UNSUPPORTED_')+cat]+=1
                if tr['y'] is None or not all(matched):continue
                a,b=qq;b0=a['sides']['bid']['price'];a0=a['sides']['ask']['price'];b1=b['sides']['bid']['price'];a1=b['sides']['ask']['price'];ages=[s['age_ms'] for q in qq for s in q['sides'].values()]
                if min(a0,b0,a1,b1)<=0 or a0<b0 or a1<b1:cover['INVALID_QUOTES']+=1;continue
                if max(ages)>60000:cover['STALE_OVER60S']+=1;continue
                gross=side*10000*math.log((a1+b1)/(a0+b0));quote=10000*math.log(b1/a0) if side>0 else 10000*math.log(b0/a1)
                mark={'midpoint_bps':gross,'quote_side_bps':quote,'spread_drag_bps':gross-quote,'max_quote_age_ms':max(ages),'has_more':any(s.get('source_has_more',False) for q in qq for s in q['sides'].values())}
                marks[tr['clock']//168].append(mark);private.append({'mechanism':name,'sid':sid,'action':tr['action'],'markout':mark,'current_contract_estimate':cost})
        classreport={c:{'commission_round_reference_bps':describe(v['commission']),'minimum_reference_notional_eur':describe(v['notional']),'round_reference_fee_eur':describe(v['fee_eur']),'cost_states':dict(v['states']),'same_covered_cohort_gross_bps':describe(v['supported_gross']),'gross_after_current_reference_fee_only_bps':describe(v['after_current_reference_fee']),'spread_swap_slippage_and_historical_terms_unknown':True} for c,v in classes.items()}
        reports[name]={'quote_boundary_coverage':dict(cover),'quote_side_by_original_block':{str(k):{field:describe([v[field] for v in vals]) for field in ('midpoint_bps','quote_side_bps','spread_drag_bps','max_quote_age_ms')} for k,vals in marks.items()},'commission_reference_by_asset_class':classreport,'ISO_UTC':[{ 'iso_week':w,**v,'full_iso_week':w in ('2026-W35','2026-W36','2026-W37'),'certified_positive_expectancy_entries':0,'executed_entries':0} for w,v in sorted(iso_counts.items())],'simultaneous_minimum_ticket_margin_eur':describe([sum(x['margin'] for x in v) for v in simultaneous.values()]),'clocks_over150eur_margin_with50eur_buffer':sum(sum(x['margin'] for x in v)>150 for v in simultaneous.values()),'same_side_asset_class_concentration':describe([max(Counter((x['class'],x['side']) for x in v).values()) for v in simultaneous.values()]),'capital_feasible_joint_entries':'UNKNOWN;DESCRIPTIVE_MARGINS_DO_NOT_ESTABLISH_STOPS_DRAWDOWN_CORRELATION_OR_FILLS','slippage_sensitivity':'subtract2,5,10bps round-trip from any reference quote-side; financing/conversion/historical fees remain unknown','historical_net_expectancy':None,'fills':0}
    return reports,private
def main():
    global PHASE
    os.umask(0o077);head,auth=gate('multiregime');master,entries,digits,manifest=e.w.old.verify_science()
    with tempfile.TemporaryDirectory(prefix='mxm-multiregime-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'REGIME_KEY')
        PHASE='CURRENT_COST_SOURCE';cost,costprov=load_asset(key,fp,tmp,current_source(auth));metadata={int(r['symbol_id']):r for r in cost['metadata_rows']}
        ids={m['symbol_id'] for m in master if m['symbol_id'] in metadata and eligibility(metadata[m['symbol_id']])[0]}
        PHASE='AUTHENTIC_NEW_COMPARISONS';results,provenance,fx,rowcount=corpus(key,fp,tmp,master,entries,digits,manifest,metadata)
        PHASE='EXISTING_QUOTE_INTERSECTION';old=json.loads((e.a.ROOT/'research_core_v4/synchronized_breadth_v1/EXECUTION_V1.json').read_text());quotes,quoteprov=load_asset(key,fp,tmp,old['fullcost_source']);econ,private=economic(results,metadata,quotes,fx)
        comparisons={};summaries={};promising=[]
        for name,rr in results.items():
            eligible=[r for r in rr if r['symbol_id'] in ids];groups={}
            for scope,subset in [('ALL_SUPPORTED_CORPUS',rr),('STRUCTURALLY_ELIGIBLE',eligible)]:
                glob=merge(subset);comparisons[name+'|'+scope]=glob
                groups[scope]={'identities':len(subset),'four_blocks':glob,'ISO_UTC':merge(subset,'iso_utc'),'asset_classes':{}}
                for c in sorted({metadata.get(r['symbol_id'],{}).get('asset_class','MISSING_METADATA') for r in subset}):
                    selected=[r for r in subset if metadata.get(r['symbol_id'],{}).get('asset_class','MISSING_METADATA')==c];w=merge(selected);iw=merge(selected,'iso_utc');comparisons[name+'|'+scope+'|'+c]=w
                    groups[scope]['asset_classes'][c]={'identities':len(selected),'four_blocks':w,'ISO_UTC':iw}
                    if scope=='STRUCTURALLY_ELIGIBLE' and len(selected)>=20 and sum(b['supported'] for b in w)>=100 and all(b['model_gross_bps'] is not None and b['model_gross_bps']>0 for b in w) and sum(b['MSE_improvement_bps2'] is not None and b['MSE_improvement_bps2']>0 for b in w)>=3 and sum(b['baseline_squared_error_sum']-b['model_squared_error_sum'] for b in w)>0 and all(b['model_gross_bps'] is not None and b['model_gross_bps']>0 for b in iw if b['iso_week'] in ('2026-W35','2026-W36','2026-W37')):promising.append({'mechanism':name,'class':c,'status':'EXPLORATORY_ECONOMIC_FOLLOWUP_ONLY'})
            summaries[name]=groups
        summary={'schema':'mxm.private.distinct.multiscale.regime.summary.v1','status':'AUTHENTIC_BOUNDED_DEVELOPMENT','design_sha256':auth['bindings'][P+'DESIGN_V1.json'],'scientific_identities':1576,'prospective_structural_eligible_accepted_identities':len(ids),'excluded_accepted_identities':1576-len(ids),'calendar_evaluation_clocks_per_mechanism':1576*168,'original_rows_authenticated':rowcount,'original_shards_authenticated':100,'mechanisms':summaries,'economic':econ,'cost_universe':cost['summary'],'source_provenance':{'current_cost':costprov,'original_quotes':quoteprov},'family_dependence_sensitivity':family_sensitivity(comparisons),'promising_predeclared_gate':promising,'independent_confirmation':False,'positive_net_certification':False,'HARD21_certified':False,'executed_fills':0,'broker_requests_this_science_job':0,'original_experiments_replayed':False,'protected_forward':False,'orders':0,'causal_availability':'CONDITIONAL_ACCEPTED_SYNTHETIC_OPEN_PLUS300S_PLUS15MIN_ACTION_LAG;NOT_AUTHENTIC_AVAILABILITY_OR_FILL_RECEIPT','previous_exact_closures_preserved':True,'numpy_version':__import__('numpy').__version__}
        fields=('clock','action','exit','training','baseline','model','y','reason','entry_reference_price')
        for rr in results.values():
            for r in rr:r['trials']=[[tr.get(k) for k in fields] for tr in r['trials']]
        PHASE='ENCRYPTED_DELIVERY';rt.output(head,auth,tmp,key,'multiregime',{'summary':summary,'trial_fields':fields,'all_identity_trials_and_denominators':results,'exact_quote_markouts':private,'authenticated_input_provenance':provenance},summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
