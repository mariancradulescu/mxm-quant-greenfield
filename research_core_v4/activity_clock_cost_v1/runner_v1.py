"""Owner-authorized new research only; existing capture/crypto left unchanged."""
import os,json,pathlib,tempfile,math,hashlib,gzip,base64,subprocess,bisect
from collections import Counter,defaultdict
from datetime import datetime,timezone
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility
from research_core_v4.cloud_native_covariance_v1.runner_v1 import fee
from research_core_v4.owner_recovery_v1.readback_v1 import iso,describe
from research_core_v4.activity_clock_cost_v1.kernel_v1 import observations,evaluate,stats,paired_return,n
e=rt.e;P='research_core_v4/activity_clock_cost_v1/';PHASE='GATE'
def need(x,code):e.w.old.need(bool(x),code)
def sha(x):return hashlib.sha256(x).hexdigest()
def gate():
    h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h)
    a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    need(a['authority']=='EXPLICIT_OWNER_COST_FIRST_NATIVE_ONLY_CONTINUATION_20261010' and
         not any(a[k] for k in ('orders','demo_orders','protected_forward','cloud_deployment','broker_requests','reexecute_closed_experiments')),'OWNER_SCOPE')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-activity-clock-cost-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'FROZEN_SOURCE_DRIFT')
    for p,s in a['preserved_blob_sha1'].items():
        need(subprocess.check_output(['git','hash-object',p],cwd=e.a.ROOT,text=True).strip()==s,'PRESERVED_REPOSITORY_DRIFT')
    need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED_INVOCATION')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    return h,a,e.w.old.verify_science()

def point(q):
    if not q or not q['two_sided_quote_available']:return None
    sides=q['sides']
    if any(sides[k]['state']!='AUTHENTIC_CAUSAL_QUOTE' or sides[k]['age_ms']>60000 or sides[k].get('source_has_more',False) for k in ('bid','ask')):return None
    b=sides['bid']['price'];a=sides['ask']['price']
    if not 0<b<=a:return None
    return {'bid':b,'ask':a,'mid':(b+a)/2,'spread_bps':10000*math.log(a/b),
      'max_age_ms':max(sides[k]['age_ms'] for k in ('bid','ask'))}

def universe(cost,master):
    native=cost['current_native_evidence']['private_native_evidence'];metadata={int(r['symbol_id']):r for r in cost['metadata_rows']}
    assets={str(x['assetId']):x['name'] for x in native['assets']}
    light={int(x['symbolId']):x for x in native['light']};census=defaultdict(Counter);selected={}
    for m in master:
        sid=m['symbol_id'];r=metadata.get(sid);c=m['asset_class'];census[c]['accepted_identities']+=1
        if r is None:census[c]['CURRENT_NATIVE_ROW_MISSING']+=1;continue
        # Reconcile a documented cash commodity classification only in this new screen.
        r=dict(r)
        if r['asset_class']=='Commodities (Cash)':r['product_type']='CASH_COMMODITY_CFD'
        ok,reasons=eligibility(r)
        if not ok:census[c].update(reasons);continue
        li=light.get(sid,{});f=native['full'].get(str(sid),{});q=assets.get(str(li.get('quoteAssetId')))
        if q not in ('EUR','USD'):census[c]['EUR_CONVERSION_ROUTE_UNSUPPORTED']+=1;continue
        if any(k not in f for k in ('preciseTradingCommissionRate','preciseMinCommission','commissionType','minCommissionType','lotSize','pnlConversionFeeRate')):
            census[c]['EXPLICIT_FEE_FIELDS_INCOMPLETE']+=1;continue
        r['quote_currency']=q
        r['captured_pnl_conversion_fraction']=int(f['pnlConversionFeeRate'])/10000 if q!='EUR' else 0.
        selected[sid]=r;census[c]['structurally_selected']+=1
    # Name and currency identities both verified from existing native metadata.
    fx=[int(r['symbol_id']) for r in cost['metadata_rows'] if r['broker_symbol']=='EURUSD' and r.get('base_asset')=='EUR' and r.get('quote_asset')=='USD']
    need(len(fx)==1 and fx[0] in {m['symbol_id'] for m in master},'EXISTING_NATIVE_EURUSD_IDENTITY')
    return selected,native,dict(census),fx[0]

def economic_gate(row,native,fxbars,spread_times,spread_values):
    def gate(r):
        out={'research_pass':False,'reason':'ECONOMIC_REFERENCE_OR_RANGE_UNAVAILABLE','full_cost_certified':False}
        p=r['causal_reference_price'];width=r['causal_h1_range'];t=r['action'];units=int(row['min_volume_cents'])/100
        if p is None or width is None or p<=0 or width<=0:return out
        if row['quote_currency']=='USD':
            fx=fxbars.get(t-300)
            if fx is None or not n.frozen.valid_bar(t-300,fx,t) or fx['tick_volume']<=0:
                out['reason']='CAUSAL_EURUSD_REFERENCE_MISSING';return out
            route=fx['close']
        else:route=1.
        f=fee(row,native,p)
        if f['bps'] is None:out['reason']='EXPLICIT_CURRENT_FEE_UNRESOLVED';return out
        k=bisect.bisect_right(spread_times,t)-1
        if k<7:out['reason']='LESS_THAN8_PRIOR_AUTHENTIC_SPREAD_BOUNDARIES';return out
        age=t-spread_times[k]
        if age>86400:out['reason']='LAST_SPREAD_CONTEXT_OLDER_THAN24H';return out
        # Prior same-symbol spread context only, never a quote at a new entry.
        spread=spread_values[k];notional=units*p/route;fee_eur=notional*f['bps']/10000
        drag=f['bps']+spread+2;rangebps=10000*width/p
        risk=(units*width/route+notional*drag/10000)*(1+row['captured_pnl_conversion_fraction'])
        out.update(fee_bps=f['bps'],fee_eur=fee_eur,prior_spread_bps=spread,spread_context_age_s=age,
          prior_spread_count=k+1,causal_H1_range_bps=rangebps,range_plus_cost_exposure_eur=risk,
          causal_reference_notional_eur=notional,reference_quote_to_eur=1/route,
          cost_fraction_of_H1_range=drag/rangebps,minimum_units=units,
          captured_worst_min_margin_eur=max(float(row['buy_margin_eur']),float(row['sell_margin_eur'])),
          current_pnl_conversion_fraction=row['captured_pnl_conversion_fraction'])
        out['reason']='ROUND_COMMISSION_GT0_50EUR' if fee_eur>.5 else 'RANGE_PLUS_COST_GT2EUR' if risk>2 else 'H1_RANGE_LT_TWICE_SPREAD_FEE_PLUS2BPS' if rangebps<2*drag else 'RESEARCH_ECONOMIC_SCREEN_PASS'
        out['research_pass']=out['reason']=='RESEARCH_ECONOMIC_SCREEN_PASS'
        return out
    return gate

def corpus(key,fp,tmp,source,selected,native,fullcost,fxid):
    master,entries,digits,manifest=source
    rel=e.w.old.api('releases/tags/'+manifest['DURABLE_RELEASE_IDENTITY'])
    assets={a['name']:a for a in e.w.old.api('releases/'+str(rel['id'])+'/assets?per_page=100')}
    quote_map={};spreads=defaultdict(list);quality=Counter()
    for q in fullcost['private_boundary_receipts']:
        t=q['boundary_ms']//1000;sid=q['symbol_id'];p=point(q)
        quality['valid' if p else 'excluded_stale_paged_missing_or_invalid']+=1
        if p:
            need((sid,t) not in quote_map,'DUPLICATE_COST_BOUNDARY')
            quote_map[sid,t]=p;spreads[sid].append((t,p['spread_bps']))
    for sid in spreads:spreads[sid].sort()
    fxordinal=next(k+1 for k,m in enumerate(master) if m['symbol_id']==fxid);fxgroup=(fxordinal-1)//64
    order=[fxgroup]+[k for k in range(25) if k!=fxgroup]
    fxbars=None;provenance=[];rows_total=0;results=[];screens=[]
    for group in order:
        buffers={o:{} for o in range(group*64+1,min(1576,group*64+64)+1)}
        for segment in range(1,5):
            entry=entries[(segment-1)*25+group];asset=assets[entry['ENCRYPTED_ASSET_NAME']]
            need(asset['digest']=='sha256:'+entry['ENCRYPTED_ASSET_SHA256'],'ARCHIVE_METADATA')
            blob=e.w.old.download(asset['browser_download_url'],asset['size']);need(sha(blob)==entry['ENCRYPTED_ASSET_SHA256'],'ARCHIVE_CIPHERTEXT')
            raw=e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
            need(sha(raw)==entry['PLAINTEXT_CANONICAL_SHA256'],'ARCHIVE_PLAINTEXT')
            obj=e.w.n.canonical.strict_json(raw)
            need(e.w.n.canonical.canonical(obj)==raw and set(obj)==e.w.n.canonical.PACKAGE_KEYS and
                 obj['segment_index']==segment and obj['shard_index']==group and obj['identity_range']==entry['IDENTITY_RANGE'],'ARCHIVE_SCHEMA')
            lo,hi=entry['IDENTITY_RANGE'];need(len(obj['items'])==hi-lo+1,'ARCHIVE_ITEMS');count=0
            for ordinal,item in zip(range(lo,hi+1),obj['items']):
                need(item['ordinal']==ordinal and item['symbol_id']==master[ordinal-1]['symbol_id'] and item['failure'] is None,'ARCHIVE_IDENTITY');prev=-1
                for row in item['rows']:
                    t,b=e.w.n._bar(row,digits[item['symbol_id']]);need(t>prev and t not in buffers[ordinal] and (t-n.START)//604800==segment-1,'ARCHIVE_TIME_DOMAIN')
                    prev=t;buffers[ordinal][t]=b;count+=1
            need(count==entry['ROW_COUNT'] and entry['PROTECTED_FORWARD_ROW_COUNT']==0,'ARCHIVE_COUNT');rows_total+=count
            provenance.append({'segment':segment,'shard':group,'rows':count,'ciphertext_sha256':sha(blob),'canonical_sha256':sha(raw)})
        if group==fxgroup:fxbars=buffers[fxordinal]
        for ordinal,bars in buffers.items():
            sid=master[ordinal-1]['symbol_id']
            if sid not in selected:continue
            r=selected[sid];ss=spreads.get(sid,[]);times=[v[0] for v in ss];vals=[v[1] for v in ss]
            gate=economic_gate(r,native,fxbars,times,vals);obs=observations(bars)
            es=[gate(v) for v in obs]
            screens.append({'sid':sid,'symbol':r['broker_symbol'],'class':r['asset_class'],'source_rows':len(bars),
              'hourly_screen_reasons':dict(Counter(v['reason'] for v in es)),
              'economic_pass_hourly':sum(v['research_pass'] for v in es),'historical_spread_observations':len(ss),
              'explicit_current_fee_eur':describe([v['fee_eur'] for v in es if 'fee_eur' in v]),
              'range_plus_cost_exposure_eur':describe([v['range_plus_cost_exposure_eur'] for v in es if v['research_pass']])})
            trials=evaluate(obs,gate)
            for tr in trials:
                tr.update(sid=sid,symbol=r['broker_symbol'],asset_class=r['asset_class'],block=tr['clock']//168,iso=iso(tr['action']))
                q0=quote_map.get((sid,tr['action']));q1=quote_map.get((sid,tr['exit']))
                tr['exact_quote_coverage']='BOTH' if q0 and q1 else 'PARTIAL' if q0 or q1 else 'NONE'
                tr['quote_model_bps']=tr['quote_baseline_bps']=None
                if tr['model'] is not None and tr['y'] is not None and q0 and q1:
                    tr['quote_model_bps']=paired_return((tr['model']>0)-(tr['model']<0),q0,q1)
                    tr['quote_baseline_bps']=paired_return((tr['baseline']>0)-(tr['baseline']<0),q0,q1)
            results.extend(trials)
        del buffers,raw,obj,blob
        e.w.old.budget(maxwall=1800,maxcpu=1400,maxkib=2097152)
    need(rows_total==3355389 and len(provenance)==100 and len(screens)==len(selected),'COMPLETE_CORPUS')
    return results,screens,provenance,quality

def aggregate(trials):
    byclock=defaultdict(list)
    for r in trials:
        # Allocation depends only on causal data/forecasts, never label or exit support.
        if r['model'] is not None and r['economics']['research_pass'] and abs(r['model'])>r['economics']['fee_bps']+r['economics']['prior_spread_bps']+2:
            byclock[r['action']].append(r)
    chosen=[]
    for t in sorted(byclock):
        chosen.append(min(byclock[t],key=lambda r:(r['economics']['cost_fraction_of_H1_range'],r['economics']['range_plus_cost_exposure_eur'],r['sid'])))
    report=lambda rr:{'global':stats(rr),'original_blocks':[{'block':b,**stats([r for r in rr if r['block']==b])} for b in range(4)],
      'ISO_UTC':[{'week':w,'complete':w in ('2026-W35','2026-W36','2026-W37'),**stats([r for r in rr if r['iso']==w])} for w in ('2026-W34','2026-W35','2026-W36','2026-W37','2026-W38')]}
    out=report(trials);out['classes']={c:report([r for r in trials if r['asset_class']==c]) for c in sorted({r['asset_class'] for r in trials})}
    out['portfolio']=report(chosen);out['portfolio'].update(max_positions=1,capital_eur=200,minimum_free_buffer_eur=50,clock_denominator=168,
      selected_before_exit_support=True,missing_selected_exit_never_replaced=True,actual_positions=0,certified_positive_expectancy_entries=0,
      cash_drawdown_and_portfolio_survival='NOT_CERTIFIED_REFERENCE_MARKOUTS_ONLY')
    full=[w for w in out['ISO_UTC'] if w['complete']];blocks=out['original_blocks'];valid=out['global']['paired']>=100 and all(w['paired']>=16 for w in blocks+full)
    positive=valid and all(w['model_reference_less_causal_current_fee_scenario_bps']>2 and w['paired_increment_bps']>0 and w['MSE_improvement_bps2']>0 for w in blocks+full)
    qvalid=out['global']['exact_quote_pairs']>=100 and all(w['exact_quote_pairs']>=16 for w in blocks+full)
    out.update(descriptive_support_gate=valid,reference_economic_increment_gate=positive,exact_quote_support_gate=qvalid,
      decision='CLOSED_NO_PROMOTION_DATA_LIMITED' if not valid else 'CLOSED_NO_PROMOTION_REFERENCE_ECONOMIC_OR_INCREMENT_FAIL' if not positive else 'DEVELOPMENT_INFORMATION_ONLY_COST_CONFIRMATION_REQUIRED',
      robust_NET=False,HARD21=False,independent_confirmation=False)
    return out,chosen

def relay(head,auth,summary):
    recipient=(e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem')).read_bytes();need(sha(recipient)==auth['recipient_public_key_sha256'],'RECIPIENT_BINDING')
    pub=serialization.load_pem_public_key(recipient);need(pub.key_size>=3072,'RECIPIENT_KEY_STRENGTH')
    packed=gzip.compress(e.a.enc(summary),mtime=0);key=os.urandom(32);nonce=os.urandom(12)
    wrapped=pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    b64=lambda x:base64.b64encode(x).decode()
    body=e.a.enc({'version':'MXM_PRIVATE_ACTIVITY_CLOCK_V1','head':head,'recipient_pub_sha256':sha(recipient),
       'nonce_b64':b64(nonce),'wrapped_key_b64':b64(wrapped),'ciphertext_b64':b64(AESGCM(key).encrypt(nonce,packed,head.encode())),
       'compressed_plain_sha256':sha(packed)}).decode();need(len(body)<160000,'RELAY_CIPHERTEXT_BUDGET')
    rel=e.w.old.api('releases',{'tag_name':'mxm-activity-clock-private-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],
       'target_commitish':head,'name':'MXM encrypted new activity-clock economic aggregates','body':body,'prerelease':True})
    need(e.w.old.api('releases/'+str(rel['id']))['body']==body,'PRIVATE_ENVELOPE_READBACK')
    print(json.dumps({'status':'PASS','run_id':int(os.environ['GITHUB_RUN_ID']),'head':head,'release_id':rel['id'],
      'envelope_sha256':sha(body.encode()),'numeric_outcomes_public':False,'orders':0}),flush=True)

def main():
    global PHASE
    os.umask(0o077);head,auth,source=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-activity-clock-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY_BINDING')
        PHASE='EXISTING_NATIVE_COST_SOURCES'
        cost,cp=load_asset(key,fp,tmp,auth['cost_source']);full,qp=load_asset(key,fp,tmp,auth['fullcost_source'])
        selected,native,census,fxid=universe(cost,source[0])
        PHASE='NEW_AUTHENTIC_ECONOMIC_AND_ACTIVITY_CLOCK_COMPARISON'
        trials,screens,provenance,quality=corpus(key,fp,tmp,source,selected,native,full,fxid)
        numeric,chosen=aggregate(trials)
        summary={'schema':'mxm.private.activity.clock.cost.first.development.v1','source_head':head,
          'design_sha256':auth['bindings'][P+'DESIGN_V1.json'],'mechanism':'H1_ACTIVITY_MEDIAN_CLOCK_PRICE_DISPLACEMENT_INCREMENT_V1',
          'authentic_shards':100,'authentic_M5_rows':3355389,'master_identities':1576,'structural_research_identities':len(selected),
          'economic_census':census,'source_provenance':[cp,qp],'source_quote_quality':dict(quality),
          'economic_screen_hourly_reasons':dict(sum((Counter(x['hourly_screen_reasons']) for x in screens),Counter())),
          'economic_screen_hourly_passes':sum(x['economic_pass_hourly'] for x in screens),
          'economic_screen_pass_identities':sum(x['economic_pass_hourly']>0 for x in screens),
          'exact_quote_prediction_coverage':dict(Counter(t['exact_quote_coverage'] for t in trials if t['model'] is not None)),
          'numeric':numeric,'broker_requests':0,'orders':0,'demo_orders':0,'protected_forward':False,'cloud_deployment':False,
          'historical_NET':'UNKNOWN_NOT_ZERO','fee_scenario':'EXPLICIT_CURRENT_CONTRACT_ON_CAUSAL_HISTORICAL_M5_REFERENCE',
          'spread_gate':'LATEST_VALID_PRIOR_SAME_SYMBOL_BOUNDARY_WITHIN24H_AFTER8PRIOR_OBSERVATIONS;CONTEXT_ONLY_NOT_NEW_ENTRY_SPREAD',
          'risk_gate':'H1_RANGE_MIN_TICKET_PLUS_CONTEXT_SPREAD_CURRENT_COMMISSION_AND2BPS<=2EUR;NOT_STOP_OR_GAP_RISK_CERTIFICATION',
          'conversion':'CAUSAL_M5_EURUSD_CLOSE_OR_DIRECT_EUR_REFERENCE_ONLY_NOT_EXECUTABLE_BID_CONVERSION',
          'pnl_conversion_scenario':'EXPLICIT_CAPTURED_FRACTION_TIMES_ABSOLUTE_PNL_WHEN_QUOTE_NOT_EUR;CONSERVATIVE_SCENARIO_NOT_HISTORICAL_CHARGE_PROOF',
          'missing_costs':'DATED_FEES_SWAP_FINANCING_ROLLOVER_SLIPPAGE_ACTUAL_FILLS_AND_LIVE_FIRST_RECEIPT_UNKNOWN',
          'native_mapping':'Bars.OpenTimes/OHLC/TickVolumes;bounded arrays and sufficient-statistic ridge CSharp;Symbol fees/minima/volume/margin;no external runtime input',
          'actual_Cloud_parity':'NOT_CLAIMED;DOCUMENTED_NATIVE_INPUTS_ONLY','selection_exposure':'ONE_FURTHER_FIXED_DEVELOPMENT_HYPOTHESIS_AFTER_ADAPTIVE_PROJECT_HISTORY',
          'dependence':'OVERLAPPING_TRAIN_LABELS;NONOVERLAPPING4H_EVAL_WITHIN_SYMBOL;CROSS_SYMBOL_DEPENDENCE;4BLOCKS3COMPLETEISO_WEEKS_NO_INDEPENDENCE_OR_MULTIPLICITY_CERTIFICATION',
          'closed_experiments_reexecuted':False,'robust_positive_NET':False,'HARD21':False}
        fullout={'summary':summary,'private_all_trials':trials,'private_all_identity_cost_screens':screens,
                 'private_causal_selected_candidates':chosen,'input_provenance':provenance}
        PHASE='OWNER_ENCRYPTED_PRIMARY_AND_ATTESTATION';rt.output(head,auth,tmp,key,'activityclock',fullout,summary)
        PHASE='PRIVATE_AGGREGATE_RELAY';relay(head,auth,summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
