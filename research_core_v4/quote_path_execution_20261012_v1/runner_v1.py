"""One fixed quote-path pilot over authenticated saved Pepperstone data.

No broker connection, new data, orders or plaintext result publication.
Only integration and reporting around the immutable scientific kernel.
"""
import json,os,subprocess,tempfile,pathlib,math,statistics
from collections import Counter
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as a
from research_core_v4.quote_path_order_20261012_v1 import kernel_v1 as k
from m6.cost_evidence import decode_ctrader_tick_page

e=rt.e
P='research_core_v4/quote_path_execution_20261012_v1/'
WF='.github/workflows/mxm-quote-path-empirical-20261012-v1.yml'
PHASE='GATE'

def need(condition,code):
    e.w.old.need(bool(condition),code)

def inventory(ref):
    return dict(z.split('\t',1)[::-1] for z in subprocess.check_output(
        ['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())

def gate():
    head=os.environ['GITHUB_SHA']; e.w.v2.runtime(head)
    auth=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    need(auth['authority']=='EXPLICIT_OWNER_FIXED_QUOTE_PATH_EMPIRICAL_20261012','OWNER_AUTHORITY')
    need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','EVENT_ATTEMPT')
    need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/'+WF+'@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
    need(auth['broker_requests']==0 and not any(auth[n] for n in ('orders','protected_forward','cloud_deployment','closed_exact_replay','authentication_changes')),'SCOPE')
    need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'EXPIRED')
    for path,digest in auth['bindings'].items():
        need(e.w.old.filehash(path)==digest,'SOURCE_BINDING')
    e.a.ancestor(auth['base_head'],head)
    old,new=inventory(auth['base_head']),inventory(head)
    need(all(new.get(path)==blob for path,blob in old.items()),'ALL_OLD_FILES_PRESERVED')
    e.w.old.verify_science()
    need(e.w.old.api('git/ref/heads/'+e.w.old.BRANCH)['object']['sha']==head,'LIVE_HEAD_DRIFT')
    run=e.w.old.api('actions/runs/'+str(auth['source']['run_id']))
    need(run['conclusion']=='success' and run['head_sha']==auth['source']['head_sha'] and run['run_attempt']==1,'SOURCE_RUN_BINDING')
    need(not e.w.v2.existing_ref(auth['one_use_ref']),'CONSUMED')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':head})
    return head,auth

def schema_and_accounting(full,source_head):
    need(type(full)==dict and all(x in full for x in ('summary','events','catalog','all_identity_status','raw_quote_receipts')),'PRIVATE_SCHEMA')
    need(full['summary']['source_head']==source_head,'PRIVATE_SOURCE_HEAD')
    need(full['summary']['orders']==0 and full['summary']['fills']==0 and full['summary']['protected_forward'] is False,'PRIVATE_SCOPE')
    rows={r['sid']:r for r in full['all_identity_status']}
    need(len(rows)==len(full['all_identity_status']),'DUPLICATE_IDENTITIES')
    quotes={}
    for q in full['raw_quote_receipts']:
        key=(int(q['symbol_id']),int(q['boundary_ms'])//1000)
        need(key not in quotes or quotes[key]==q,'DUPLICATE_QUOTE_CONFLICT')
        need(q['boundary_ms']%1000==0 and q['boundary_ms']<1789603200000,'QUOTE_DOMAIN')
        quotes[key]=q
        for page in q.get('pages',[]):
            need(page['side'] in ('bid','ask') and type(page['hasMore'])==bool,'PAGE_SCHEMA')
            for encoded in page['encoded']:
                need(set(encoded)=={'timestamp','tick'},'ENCODED_TICK_SCHEMA')
            dec=decode_ctrader_tick_page(page['encoded'])
            need(all(q['boundary_ms']-60000<=z.timestamp_ms<=q['boundary_ms'] for z in dec),'RAW_QUOTE_WINDOW')
            side=q['sides'].get(page['side'],{})
            if side.get('state')=='AUTHENTIC_CAUSAL_QUOTE':
                need(bool(dec),'CAUSAL_SIDE_EMPTY')
                last=max(dec,key=lambda z:z.timestamp_ms)
                need(last.timestamp_ms==side['timestamp_ms'] and math.isclose(last.raw_tick/100000,side['price'],rel_tol=0,abs_tol=1e-10),'DECODER_LAST_SIDE_PARITY')
    unique={}
    for ev in full['events']:
        need(ev['sid'] in rows and str(ev['sid']) in full['catalog']['full'],'EVENT_CONTRACT')
        need(ev['t']+ev['h']*60<1789603200,'EVENT_DOMAIN')
        if ev['h']==15:
            key=(ev['sid'],ev['t'])
            need(key not in unique or unique[key]['entry']==ev['entry'],'ENTRY_DUPLICATE_PARITY')
            unique[key]=ev
    graph=a.graph(list(rows.values())); checks=0
    # Accounting parity only; no previous predictive model is called or selected.
    for ev in unique.values():
        saved=ev['accounts']['S2_F010_DAY'];row=rows[ev['sid']];contract=full['catalog']['full'][str(ev['sid'])]
        for index,d in enumerate((1,-1)):
            current=a.account(d,row,contract,ev['t'],ev['t']+900,.25,quotes,graph,2,.10,False)
            old=saved[index]
            need((current is None)==(old is None),'ACCOUNT_SUPPORT_PARITY')
            if current is not None:
                for field in ('gross_eur','entry_commission_eur','exit_commission_eur','pnl_conversion_fee_eur','funding_stress_eur','net_eur'):
                    need(math.isclose(current[field],old[field],rel_tol=1e-10,abs_tol=1e-10),'ACCOUNT_VALUE_PARITY')
            checks+=1
    return unique,rows,quotes,graph,{'schema':'PASS','raw_quote_parity':'PASS','native_accounting_parity':'PASS','side_account_checks':checks}

def pilot(full,unique,rows,quotes,graph):
    candidates=[]; reasons=Counter(); entry_reasons=Counter()
    for (sid,t),ev in sorted(unique.items()):
        q=quotes.get((sid,t)); pages={p['side']:p for p in q.get('pages',[])} if q else {}
        if set(pages)!={'bid','ask'}:
            feature={'state':'MISSING_RAW_PAGES'}
        else:
            decoded={side:[(z.timestamp_ms,z.raw_tick/100000) for z in decode_ctrader_tick_page(pages[side]['encoded'])] for side in ('bid','ask')}
            feature=k.feature(decoded['bid'],decoded['ask'],t,any(p['hasMore'] for p in pages.values()))
        reasons[feature['state']]+=1; entry_reasons[ev['entry']['state']]+=1
        candidates.append({'sid':sid,'t':t,'entry':ev['entry'],'feature':feature})
    details={}
    def account(event,d):
        key=(event['sid'],event['t'],d)
        if key not in details:
            row=rows[event['sid']];f=full['catalog']['full'][str(event['sid'])]
            details[key]=a.account(d,row,f,event['t'],event['t']+900,.25,quotes,graph,2,.10,False)
            value=details[key]
            if value is not None:
                q0=a.point(quotes.get((event['sid'],event['t'])));q1=a.point(quotes.get((event['sid'],event['t']+900)))
                u=row['min_units'];p0=q0['ask'] if d>0 else q0['bid'];p1=q1['bid'] if d>0 else q1['ask']
                mid_native=d*u*(q1['mid']-q0['mid']);quote_native=d*u*(p1-p0)
                mid_eur=a.convert(mid_native,row['quote'],'EUR',event['t']+900,quotes,graph)
                quote_eur=a.convert(quote_native,row['quote'],'EUR',event['t']+900,quotes,graph)
                need(mid_eur is not None and quote_eur is not None,'DECOMPOSITION_FX')
                value.update(midpoint_gross_eur=mid_eur,quote_gross_before_slippage_eur=quote_eur,
                             spread_drag_eur=mid_eur-quote_eur,slippage_drag_eur=quote_eur-value['gross_eur'],
                             gross_native_quote_currency_with_slippage=d*u*(p1*(1-d*.0002)-p0*(1+d*.0002)),quote_currency=row['quote'])
        return details[key]['net_eur'] if details[key] is not None else None
    portfolio=k.portfolio(candidates,account)
    bykey={(r['sid'],r['t']):r for r in candidates}; traces=[]
    for selected in portfolio['selected']:
        event=bykey[selected['sid'],selected['entry']];f=event['feature']
        z={name:(None if (value:=details.get((event['sid'],event['t'],d))) is None else value)
           for name,d in [('model',f['model_side']),('midpoint',f['midpoint_baseline_side']),('quote_count',f['quote_count_baseline_side'])] if d}
        for name,d in [('midpoint',f['midpoint_baseline_side']),('quote_count',f['quote_count_baseline_side'])]:
            if not d:z[name]={field:0. for field in ('gross_eur','entry_commission_eur','exit_commission_eur','pnl_conversion_fee_eur','funding_stress_eur','net_eur','midpoint_gross_eur','quote_gross_before_slippage_eur','spread_drag_eur','slippage_drag_eur')};z[name]['cash_tie']=True
        traces.append({'sid':event['sid'],'t':event['t'],'exit':event['t']+900,'accounts':z,'feature':f,'entry':event['entry']})
    iso=lambda t:datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
    weeks=full['summary']['weeks'];weekly={}
    for week in weeks:
        cc=[r for r in candidates if iso(r['t'])==week];ss=[r for r in traces if iso(r['t'])==week]
        weekly[week]={'candidate_boundaries':len(cc),'feature_reasons':dict(Counter(r['feature']['state'] for r in cc)),
                      'entry_proxy_eligible':sum(k.admit(r['entry']) for r in cc),'model_proposed':sum(r['feature'].get('model_side',0)!=0 and k.admit(r['entry']) for r in cc),
                      'portfolio_selected':len(ss),'accounting':aggregate(ss),'calendar_week_complete':True,'full_opportunity_coverage':False}
    halves=[aggregate([r for r in traces if iso(r['t']) in set(group)]) for group in (weeks[:len(weeks)//2],weeks[len(weeks)//2:])]
    summary={'schema':'mxm.quote.path.empirical.summary.v1','mechanism':'PRICE_SPREAD_TEMPORAL_ORDER_RESPONSE_V1',
             'all_original_event_rows':len(full['events']),'unique_candidate_boundaries':len(candidates),'candidate_identities':len({r['sid'] for r in candidates}),
             'feature_states':dict(reasons),'calculable_features':sum(r['feature']['state']=='SUPPORTED_FEATURE' for r in candidates),
             'entry_proxy_eligible_all':sum(k.admit(r['entry']) for r in candidates),'entry_reasons':dict(entry_reasons),
             'model_proposed_eligible':sum(r['feature'].get('model_side',0)!=0 and k.admit(r['entry']) for r in candidates),
             'portfolio':portfolio,'accounting':aggregate(traces),'weekly':weekly,'temporal_halves':halves,
             'broker_requests':0,'orders':0,'fills':0,'protected_forward':False,'HARD21_demonstrated':False,
             'prior_selection_preserved':True,'all_corpus_identities_retained':True,'universe_exhausted':False,'alpha_certified':False,
             'cost_terms':'CURRENT_NATIVE_TERMS_HYPOTHETICAL2BPS_PER_SIDE_FUNDING0.10EUR_PER_DAY;HISTORICAL_FILLS_AND_CHARGES_UNKNOWN',
             'gross_semantics':'NATIVE_ACCOUNT_GROSS_ALREADY_INCLUDES_QUOTE_SPREAD_AND_SIMULATED_SLIPPAGE;NOT_MIDPOINT_GROSS',
             'uncertainty':'DESCRIPTIVE_EXPLORATORY_PILOT;NO_INDEPENDENT_CONFIRMATION_OR_CONFIDENCE_CLAIM',
             'risk':'PLANNING_PROXY_NOT_GAP_STOP_OR_RUIN_GUARANTEE'}
    return {'summary':summary,'candidate_features':candidates,'selected_accounting':traces},summary

def aggregate(traces):
    result={}
    for name in ('model','midpoint','quote_count'):
        z=[r['accounts'].get(name) for r in traces];known=[v for v in z if v is not None]
        result[name]={'selected':len(z),'evaluable':len(known),'unknown':len(z)-len(known),
                      'known_subtotal':{field:sum(v[field] for v in known) if known else None for field in ('midpoint_gross_eur','quote_gross_before_slippage_eur','spread_drag_eur','slippage_drag_eur','gross_eur','entry_commission_eur','exit_commission_eur','pnl_conversion_fee_eur','funding_stress_eur','net_eur')},
                      'complete_net_eur':sum(v['net_eur'] for v in known) if z and len(z)==len(known) else None}
    for name in ('midpoint','quote_count'):
        paired=[(r['accounts'].get('model'),r['accounts'].get(name)) for r in traces]
        paired=[(m,b) for m,b in paired if m is not None and b is not None]
        result[name]['paired_model_increment_eur']=sum(m['net_eur']-b['net_eur'] for m,b in paired) if paired else None
        result[name]['paired_entries']=len(paired)
    result['cash']={'net_eur':0.,'positions':0}
    return result

def main():
    global PHASE
    os.umask(0o077);head,auth=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-path-pilot-',dir=os.environ['RUNNER_TEMP']) as directory:
        tmp=pathlib.Path(directory);key,fp=e.w.old._private_key_from_secret(tmp)
        need(fp==e.w.old.FP,'EXISTING_OWNER_KEY')
        PHASE='SAVED_CORPUS_DECRYPTION';full,proof=load_asset(key,fp,tmp,auth['source'])
        PHASE='SCHEMA_ACCOUNTING_PREFLIGHT';unique,rows,quotes,graph,checks=schema_and_accounting(full,auth['source']['head_sha'])
        PHASE='FIXED_NUMERIC_PILOT';result,summary=pilot(full,unique,rows,quotes,graph)
        summary.update(source_provenance=proof,preflight=checks,design_sha256=auth['bindings']['research_core_v4/quote_path_order_20261012_v1/DESIGN_V1.json'],scientific_bindings=auth['bindings'],independent_acceptance_claimed=False)
        result['summary']=summary;PHASE='ENCRYPTED_PUBLICATION'
        rt.output(head,auth,tmp,key,'quotepath',result,summary)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        rt.fail(exc,PHASE);raise SystemExit(1)
