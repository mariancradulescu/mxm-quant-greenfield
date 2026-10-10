"""Authenticated corpus reduction, frozen breadth, existing quote cost intersection."""
import json,os,pathlib,tempfile,gzip,base64,csv,io,math
from collections import Counter,defaultdict
from research_core_v4.synchronized_breadth_v1.runtime_v1 import gate,e,rt,P
from research_core_v4.synchronized_breadth_v1.kernel_v1 import reduce,peer_breadth,evaluate,merge
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.owner_recovery_v1.readback_v1 import describe
PHASE='GATE'

def eligible(r):
    try:
        return r['product_type']=='STANDARD_CASH_SHARE_CFD' and r['directional_summary']=='BOTH_FEASIBLE' and r['shortability']=='True' and max(float(r['buy_margin_eur']),float(r['sell_margin_eur']))<=50 and int(r['min_volume_cents'])>0 and int(r['step_volume_cents'])>0 and int(r['lot_size'])>0
    except (ValueError,KeyError):return False

def group(r):return '|'.join(r[k] for k in ('asset_class','product_type','schedule_time_zone','session_regions'))

def costs(metadata,master,results,full):
    receipts=full['private_boundary_receipts'];qmap={(q['symbol_id'],q['boundary_ms']//1000):q for q in receipts};existing=defaultdict(list)
    for q in receipts:
        if not q['two_sided_quote_available']:continue
        bid=q['sides']['bid']['price'];ask=q['sides']['ask']['price']
        if min(bid,ask)>0 and ask>=bid:existing[q['symbol_id']].append(10000*math.log(ask/bid))
    groups={};byid=[];exact=Counter();markouts=defaultdict(list);commission=defaultdict(list);simultaneous=defaultdict(lambda:{'candidates':0,'captured_minimum_margin_sum_eur':0.,'markets':Counter()})
    for item in master:
        sid=item['symbol_id'];r=metadata.get(sid)
        if r is None:byid.append({'symbol_id':sid,'status':'NO_CAPTURED_STRUCTURAL_ROW'});continue
        c=r['asset_class'];g=groups.setdefault(c,{'identities':0,'both_captured_margin_le50':0,'historical_quote_identities':0,'spreads':[],'margin':[],'volume_grids':Counter(),'fee_contracts':Counter()})
        g['identities']+=1;g['both_captured_margin_le50']+=int(max(float(r['buy_margin_eur']),float(r['sell_margin_eur']))<=50)
        g['margin'].append(max(float(r['buy_margin_eur']),float(r['sell_margin_eur'])))
        g['volume_grids'][(r['min_volume_cents'],r['step_volume_cents'],r['lot_size'])]+=1
        g['fee_contracts'][tuple(r[k] for k in ('commission_rate_normalized','commission_rate_unit','min_commission_normalized','min_commission_type','min_commission_asset','pnl_conversion_fee_pct'))]+=1
        if existing[sid]:g['historical_quote_identities']+=1;g['spreads']+=existing[sid]
        byid.append({'symbol_id':sid,'captured_worst_margin_eur':max(float(r['buy_margin_eur']),float(r['sell_margin_eur'])),
          'min_volume_cents':r['min_volume_cents'],'step_volume_cents':r['step_volume_cents'],'lot_size':r['lot_size'],'historical_spread_bps':describe(existing[sid]),'research_eligible':eligible(r)})
    for result in results:
        sid=result['symbol_id'];r=metadata[sid]
        for tr in result['trials']:
            if tr['model'] is None:continue
            exact['emitted']+=1
            cap=simultaneous[tr['action']];cap['candidates']+=1;cap['captured_minimum_margin_sum_eur']+=float(r['buy_margin_eur'] if tr['model']>0 else r['sell_margin_eur']);cap['markets'][r['asset_class']]+=1
            if tr['y'] is not None:
                if r['commission_rate_unit']=='PERCENTAGE_OF_VALUE':commission[r['asset_class']].append(2*float(r['commission_rate_normalized'])*100)
                elif r['asset_class']=='US Equities' and r['commission_rate_unit']=='USD_PER_LOT' and tr.get('entry_reference_price'):
                    units=float(r['min_volume_cents'])/100;lots=float(r['min_volume_cents'])/float(r['lot_size']);fee=2*max(float(r['commission_rate_normalized'])*lots,float(r['min_commission_normalized']));commission[r['asset_class']].append(10000*fee/(units*tr['entry_reference_price']))
            if tr['y'] is None:exact['label_unsupported']+=1
            qs=[qmap.get((sid,tr[k])) for k in ('action','exit')]
            matched=[q is not None and q['two_sided_quote_available'] for q in qs]
            coverage='BOTH_BOUNDARIES' if all(matched) else 'PARTIAL_BOUNDARY' if any(matched) else 'NO_MATCHED_BOUNDARY';exact[coverage]+=1
            if tr['y'] is None or not all(matched):continue
            q0,q1=qs;b0=q0['sides']['bid']['price'];a0=q0['sides']['ask']['price'];b1=q1['sides']['bid']['price'];a1=q1['sides']['ask']['price']
            if min(b0,a0,b1,a1)<=0 or a0<b0 or a1<b1:exact['invalid_quotes']+=1;continue
            side=(tr['model']>0)-(tr['model']<0);gross=side*10000*math.log(((b1+a1)/2)/((b0+a0)/2))
            quote=10000*math.log(b1/a0) if side>0 else 10000*math.log(b0/a1) if side<0 else 0.
            markouts[str(tr['clock']//168)].append({'midpoint_bps':gross,'quote_side_bps':quote,'drag_bps':gross-quote,
              'max_quote_age_ms':max(s['age_ms'] for q in qs for s in q['sides'].values())})
            exact['supported_both']+=1;exact['provider_has_more']+=int(any(s.get('source_has_more',False) for q in qs for s in q['sides'].values()))
    for c,g in groups.items():
        g['worst_margin_eur']=describe(g.pop('margin'));g['historical_one_boundary_spread_bps']=describe(g.pop('spreads'))
        g['volume_grids']=[{'min_cents':a,'step_cents':b,'lot_cents':c,'identities':v} for (a,b,c),v in sorted(g['volume_grids'].items())]
        g['fee_contracts']=[{'rate':a,'unit':b,'minimum':c,'minimum_type':d,'minimum_asset':f,'pnl_conversion_fee_pct':h,'identities':v} for (a,b,c,d,f,h),v in sorted(g['fee_contracts'].items())]
    return {'source_semantics':'HASH_BOUND_CAPTURED_CURRENT_TERMS_NOT_POINT_IN_TIME_AUG_SEP_COSTS;EXISTING_HISTORICAL_QUOTES_AIDR_CONDITIONAL_NOT_UNIVERSE_SELECTION',
      'all_master_identities':1576,'metadata_matched':sum(x['symbol_id'] in metadata for x in master),'by_asset_class':groups,'identity_costs':byid,
      'exact_new_prediction_boundary_coverage':dict(exact),'exact_new_supported_quote_side_by_block':{k:{name:describe([x[name] for x in v]) for name in v[0]} for k,v in markouts.items()},
      'historical_commission_terms':'UNAVAILABLE','historical_conversion_and_financing':'NOT_RECONCILED','real_fills':0,'certified_positive_expectancy_entries':0,
      'captured_current_commission_hurdle_bps_on_supported_reference':{k:describe(v) for k,v in commission.items()},
      'commission_hurdle_semantics':'US_MINIMUM_VOLUME_FEE_USD_PER_LOT_AND_MINIMUM_OVER_THEORETICAL_REFERENCE_NOTIONAL;GB_AU_PERCENTAGE_ONLY_LOWER_BOUND_BEFORE_MINIMUM;CAPTURED_CURRENT_NOT_HISTORICAL_FEES',
      'simultaneous_theoretical_entries':{'clocks':len(simultaneous),'candidate_count':describe([x['candidates'] for x in simultaneous.values()]),'captured_minimum_margin_sum_eur':describe([x['captured_minimum_margin_sum_eur'] for x in simultaneous.values()]),'clocks_margin_sum_gt200':sum(x['captured_minimum_margin_sum_eur']>200 for x in simultaneous.values()),'per_clock':[{'action':t,**v} for t,v in sorted(simultaneous.items())]},
      'current_margin_is_loss_buffer_or_stop_risk':False,'portfolio_concurrent_cost_and_drawdown_replay':'NOT_ESTABLISHED'}

def main():
    global PHASE
    os.umask(0o077);head,auth=gate();master,entries,digits,manifest=e.w.old.verify_science()
    with tempfile.TemporaryDirectory(prefix='mxm-breadth-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'BREADTH_KEY')
        PHASE='CONTRACT_METADATA'
        cipher=base64.b64decode((e.a.ROOT/(P+'CONTRACT_METADATA_V1.mxmenc.b64')).read_text(),validate=True)
        e.w.old.need(e.a.sha(cipher)==auth['contract_ciphertext_sha256'],'CONTRACT_CIPHER')
        raw=gzip.decompress(e.w.old.crypto.decrypt_package(cipher,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp))
        e.w.old.need(e.a.sha(raw)==auth['contract_csv_sha256'],'CONTRACT_PLAINTEXT');rs=list(csv.DictReader(io.StringIO(raw.decode())))
        e.w.old.need(len(rs)==1641,'CONTRACT_ROSTER');metadata={int(r['symbol_id']):r for r in rs}
        ids=[m['symbol_id'] for m in master if m['symbol_id'] in metadata and eligible(metadata[m['symbol_id']])]
        e.w.old.need(len(ids)==auth['prospective_eligible_count'],'ELIGIBLE_FROZEN_COUNT');rosters=defaultdict(list)
        for sid in ids:rosters[group(metadata[sid])].append(sid)
        for members in rosters.values():e.w.old.need(len({metadata[s]['broker_symbol'] for s in members})==len(members),'DUPLICATE_UNDERLYING')
        full,costprov=load_asset(key,fp,tmp,auth['fullcost_source'])
        PHASE='AUTHENTIC_CORPUS'
        rel=e.w.old.api('releases/tags/'+manifest['DURABLE_RELEASE_IDENTITY']);assets={x['name']:x for x in e.w.old.api('releases/'+str(rel['id'])+'/assets?per_page=100')}
        panel={};provenance=[];rowcount=0
        for shard in range(25):
            buffers={ordinal:{} for ordinal in range(shard*64+1,min(1576,shard*64+64)+1)}
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
                        ts,bar=e.w.n._bar(row,digits[item['symbol_id']]);e.w.old.need(ts>previous and ts not in buffers[ordinal] and (ts-e.w.n.START)//604800==segment-1,'SHARD_ROW_ORDER');previous=ts;count+=1
                        buffers[ordinal][ts]=bar
                e.w.old.need(count==entry['ROW_COUNT'] and entry['PROTECTED_FORWARD_ROW_COUNT']==0,'SHARD_COUNTS');rowcount+=count
                provenance.append({'segment':segment,'shard':shard,'ciphertext_sha256':entry['ENCRYPTED_ASSET_SHA256'],'canonical_sha256':entry['PLAINTEXT_CANONICAL_SHA256'],'rows':count})
            for ordinal,bars in buffers.items():
                sid=master[ordinal-1]['symbol_id']
                if sid in ids:panel[sid]=reduce(bars)
            del buffers;e.w.old.budget(maxwall=1700,maxcpu=1400,maxkib=2097152)
        e.w.old.need(rowcount==3355389 and len(provenance)==100 and len(panel)==len(ids),'COMPLETE_CORPUS')
        PHASE='FROZEN_PREQUENTIAL_COMPARISON';breadth,coverage=peer_breadth(panel,rosters);results=[evaluate(sid,panel,breadth) for sid in ids]
        economic=costs(metadata,master,results,full)
        groupresults={k:merge([r for r in results if r['symbol_id'] in v]) for k,v in rosters.items()}
        summary={'schema':'mxm.private.synchronized.breadth.summary.v1','status':'BOUNDED_DEVELOPMENT_ONLY','all_master_identities':1576,'research_eligible_identities':len(ids),'excluded_identities':1576-len(ids),
          'calendar_target_clocks':len(ids)*672,'original_rows_authenticated':rowcount,'original_shards_authenticated':100,'four_weeks':merge(results),'iso_utc':merge(results,'iso_utc'),
          'groups':groupresults,'common_clock_coverage':coverage,'cost_first':economic,'all_identity_week_counts':[{'symbol_id':r['symbol_id'],'four_weeks':r['four_weeks'],'iso_utc':r['iso_utc']} for r in results],
          'design':json.loads((e.a.ROOT/(P+'DESIGN_V1.json')).read_text()),'cost_source_provenance':costprov,'broker_requests':0,'original_experiments_replayed':False,
          'orders':0,'protected_forward':False,'scientific_significance_claimed':False,'independent_confirmation':False,'net_expectancy_established':False,'causal_availability':'FROZEN_SYNTHETIC_BAR_AVAILABILITY_PLUS_15MIN_DELAY;NOT_LIVE_RECEIPT_OR_FILL_PROOF'}
        del panel,breadth,full
        PHASE='ENCRYPTED_DELIVERY';rt.output(head,auth,tmp,key,'breadth',{'summary':summary,'all_trials':results,'input_provenance':provenance},summary)

if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
