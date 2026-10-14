"""Independent outcome-blind cohort first, then one frozen native-cost pilot."""
import os,json,pathlib,tempfile,math,statistics,datetime,subprocess,base64,hashlib,gzip
from collections import Counter,defaultdict
from functools import lru_cache
import numpy as np
from . import storage as io,order_kernel as kernel
from .runtime import gate,store_for,P
from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2 as old,archive_v2 as ar,runner_v2 as repair
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as v1,accounting_v1 as fx
E=v1.E;need=v1.need;TAG='mxm-independent-economic-order-20261014-v1'

def iso(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).strftime('%G-W%V')
def stats(v):return {'n':len(v),'min':min(v) if v else None,'median':statistics.median(v) if v else None,'max':max(v) if v else None}

def quote_clock_candidates(db,sid):
    # Input availability only. Do not inspect exit quotes or returns here.
    spans=db.execute('SELECT a,b,z FROM span WHERE s=? AND k IN (\'bid\',\'ask\')',(sid,)).fetchall();clocks=set()
    for lo,hi,z in spans:
        if ar.category(z)!='CONFIRMED_COMPLETE':continue
        lo=max(ar.START,(lo+999)//1000);hi=min(ar.END-900,hi//1000)
        clocks.update(range(((lo+299)//300)*300,hi+1,300))
    return sorted(clocks)

def prepare(db,st):
    rows={int(s):r for s,r in st['rows'].items()};g=fx.graph(list(rows.values()));counts=Counter();cohort=[];vectors=[];manifest=[]
    # Cache causal quote states, including authentic interval masks.
    qp=lru_cache(maxsize=200000)(lambda sid,t,strict=False:repair.covered_qpoint(db,sid,t,strict))
    def quotes(ids,times,strict=False):
        out={}
        for sid in ids:
            for t in times:
                z=qp(sid,t,strict)
                if z.get('valid'):out[sid,t]={'symbol_id':sid,'boundary_ms':t*1000,'state_expiry_ms':5000 if strict else 300000,'sides':{k:{'state':'AUTHENTIC_CAUSAL_QUOTE_RECONSTRUCTED_STATE','price':z[k],'timestamp_ms':z[k+'_time_ms'],'age_ms':t*1000-z[k+'_time_ms']} for k in ('bid','ask')}}
        return out
    for index,sid in enumerate(st['eligible']):
        row=rows[sid];f=st['catalog']['full'].get(str(sid));local=Counter();bars=v1.bars_for(db,sid)
        local['calendar_clocks']=len(range(ar.START,ar.END-899,300))
        candidates=quote_clock_candidates(db,sid);local['entry_interval_clocks']=len(candidates)
        local['unsampled_or_unconfirmed_entry_clocks']=local['calendar_clocks']-len(candidates)
        if not f:local['contract_missing']=len(candidates);candidates=[]
        for t in candidates:
            tt=list(range(t-3900,t-300,300))
            if any(b not in bars for b in tt):local['feature_m5_gap']+=1;continue
            if ar.missing(db,sid,'M5',(t-3900)*1000,(t-300)*1000-1):local['feature_m5_interval_unconfirmed']+=1;continue
            rr=[math.log(bars[b][3]/bars[b][0]) for b in tt];z=kernel.feature(rr);vectors.append(rr)
            local['feature_supported']+=1
            if not z['side']:local['numeric_degenerate_cash']+=1;continue
            q0=qp(sid,t)
            if not q0.get('valid'):local['entry_quote_missing']+=1;continue
            paths,routeids=v1.needed_routes(row,f,g)
            if any(p is None for p in paths):local['fx_route_unresolved']+=1;continue
            ids=sorted({sid}|routeids);qs=quotes(ids,(t,))
            notional=fx.convert(-row['min_units']*q0['mid'],row['quote'],'EUR',t,qs,g)
            spread=fx.convert(-row['min_units']*(q0['ask']-q0['bid']),row['quote'],'EUR',t,qs,g)
            fees=[fx.commission(row,f,row['min_units'],q0[k],t,qs,g) for k in ('bid','ask')]
            if notional is None or spread is None or any(v is None for v in fees):local['entry_conversion_or_fee_missing']+=1;continue
            notional=-notional;need(notional>0,'ENTRY_NOTIONAL_NONPOSITIVE')
            rate=int(f['pnlConversionFeeRate'])/10000 if row['quote']!='EUR' else 0.;need(0<=rate<1,'PNL_FEE_RATE')
            cost=-spread+.0004*notional+(sum(fees)+.1/96)/(1-rate)
            ranges=[10000*(bars[b][1]-bars[b][2])/bars[b][3] for b in tt]
            tail=max(ranges);scale=statistics.mean(ranges)*math.sqrt(3)
            gap=max([5.]+[abs(10000*math.log(bars[b][0]/bars[a][3])) for a,b in zip(tt,tt[1:])])
            risk=cost+notional*max(tail*math.sqrt(3),gap)/10000
            local['cost_observable_entry']+=1
            if risk>2:local['risk_reject']+=1;continue
            if row['margin_eur']>80:local['margin_reject']+=1;continue
            if cost>notional*scale/10000:local['cost_vs_prior_scale_reject']+=1;continue
            local['exante_model_entries']+=1
            cohort.append({'sid':sid,'t':t,'iso':iso(t),'date':datetime.datetime.fromtimestamp(t,datetime.timezone.utc).date().isoformat(),'class':row['class'],'feature':z,'cost_eur':cost,'break_even_bps':cost/notional*10000,'risk_eur':risk,'margin_eur':row['margin_eur'],'notional_eur':notional,'ids':ids,'strict_entry_supported':qp(sid,t,True).get('valid',False),'native_volume_units':row['min_units']})
        counts.update(local);manifest.append({'sid':sid,'symbol':row['symbol'],'class':row['class'],'counts':dict(local),'state':'HAS_EXANTE_MODEL_SUPPORT' if local['exante_model_entries'] else 'LIMITED_WITH_EXPLICIT_ENTRY_BARRIERS'})
        if index%128==0:print(json.dumps({'phase':'INDEPENDENT_PREOUTCOME_SUPPORT','classified':index+1,'total':len(st['eligible']),'exante_entries':len(cohort),'broker_requests':0}),flush=True)
    return rows,g,counts,cohort,vectors,manifest,quotes

def parity(vectors,tmp):
    inp=tmp/'order-input.jsonl';out=tmp/'order-output.jsonl';inp.write_text(''.join(json.dumps(v)+'\n' for v in vectors))
    subprocess.run(['dotnet',str(E.a.ROOT/(P+'csharp/bin/Release/net8.0/Replay.dll')),str(inp),str(out)],check=True,stdout=subprocess.DEVNULL)
    lines=out.read_text().splitlines();need(len(lines)==len(vectors),'NATIVE_PARITY_COUNT')
    for v,line in zip(vectors,lines):
        py=kernel.feature(v);cs=json.loads(line);need(py.keys()==cs.keys(),'NATIVE_PARITY_SCHEMA')
        for k,x in py.items():need(math.isclose(x,cs[k],rel_tol=1e-11,abs_tol=1e-18) if isinstance(x,float) else x==cs[k],'NATIVE_FEATURE_PARITY')
    return {'state':'AUTHENTIC_PYTHON_CSHARP_FEATURE_PARITY_PASS','vectors':len(vectors),'native_adapter_compile':True,'cloud_delivery_or_order_parity':'NOT_DEPLOYED_NOT_CERTIFIED','restart_policy':'NATIVE_HISTORY_RESEED;ANY_EXISTING_POSITION_BLOCKS_OBSERVER;FINAL_ORDER_RECONCILIATION_UNIMPLEMENTED_UNTIL_QUALIFIED_STRATEGY'}

def account(d,ev,row,f,quotes,g,slip=2.,fund=.1,strict=False):
    if d==0:return {'midpoint_gross_eur':0.,'net_eur':0.,'total_cost_eur':0.,'cash_by_frozen_rule':True}
    t=ev['t'];qs=quotes(ev['ids'],(t,t+900),strict);z=fx.account(d,row,f,t,t+900,.25,qs,g,slip,fund)
    if z is None:return None
    q0=fx.point(qs.get((row['sid'],t)));q1=fx.point(qs.get((row['sid'],t+900)))
    mid=fx.convert(d*row['min_units']*(q1['mid']-q0['mid']),row['quote'],'EUR',t+900,qs,g)
    native=fx.convert(d*row['min_units']*((q1['bid'] if d>0 else q1['ask'])-(q0['ask'] if d>0 else q0['bid'])),row['quote'],'EUR',t+900,qs,g)
    if mid is None or native is None:return None
    return {**z,'midpoint_gross_eur':mid,'spread_drag_eur':mid-native,'slippage_drag_eur':native-z['gross_eur'],'total_cost_eur':mid-z['net_eur']}

def aggregate(records):
    paired=[r for r in records if r['model'] is not None and r['baseline'] is not None]
    fields=('midpoint_gross_eur','spread_drag_eur','slippage_drag_eur','entry_commission_eur','exit_commission_eur','funding_stress_eur','pnl_conversion_fee_eur','total_cost_eur','net_eur')
    out={'cohort':len(records),'paired_supported':len(paired),'model_exit_censored':sum(r['model'] is None for r in records),'baseline_censored':sum(r['baseline'] is None for r in records)}
    for name in ('model','baseline'):out[name]={k:sum(r[name].get(k,0.) for r in paired) if paired else None for k in fields}
    out['paired_increment_net_eur']=out['model']['net_eur']-out['baseline']['net_eur'] if paired else None
    return out

def portfolio(records):
    equity=200.;selected=[];closed=[];active=None;halt=None
    groups=defaultdict(list)
    for r in records:groups[r['event']['t']].append(r)
    for t,vv in sorted(groups.items()):
        if active and active['event']['t']+900<=t:
            if active['model'] is None:halt='FIRST_SELECTED_UNKNOWN_EXIT;NO_HINDSIGHT_REPLACEMENT';break
            equity+=active['model']['net_eur'];closed.append(active);active=None
        if active:continue
        # Ranking uses entry costs and native identity only, never exit support or PnL.
        eligible=[r for r in vv if r['event']['risk_eur']<=min(2,.01*equity) and r['event']['margin_eur']<=min(80,.4*equity) and equity-r['event']['margin_eur']>=.6*equity]
        if not eligible:continue
        active=min(eligible,key=lambda r:(r['event']['cost_eur'],r['event']['sid']));selected.append(active)
    if active and not halt:
        if active['model'] is None:halt='FIRST_SELECTED_UNKNOWN_EXIT;NO_HINDSIGHT_REPLACEMENT'
        else:equity+=active['model']['net_eur'];closed.append(active)
    return {'initial_equity_eur':200,'closed_equity_eur':equity,'selected':len(selected),'closed':len(closed),'halt':halt,'selected_by_ISO_week':dict(Counter(r['event']['iso'] for r in selected)),'closed_by_ISO_week':dict(Counter(r['event']['iso'] for r in closed)),'matched_shadow':aggregate(closed),'actual_orders':0,'actual_fills':0,'HARD21':False,'risk_margin_contract':'PLANNED_MAX1PCT_EQUITY_AND2EUR;MARGIN_MAX40PCT_AND80EUR;MIN60PCT_RESERVE;NO_GUARANTEED_STOP_OR_UNOBSERVED_MARK_TO_MARKET_RISK_BOUND'}

def uncertainty(records):
    weeks=['2026-W35','2026-W36','2026-W37'];weekly={w:aggregate([r for r in records if r['event']['iso']==w]) for w in weeks}
    if any(weekly[w]['paired_supported']==0 for w in weeks):return {'weekly':weekly,'intervals':None,'cause':'ALL_THREE_BLOCKS_NOT_SUPPORTED','confirmatory_inference':False}
    rng=np.random.default_rng(20261014);index=rng.integers(0,3,(2000,3));model=np.array([weekly[w]['model']['net_eur'] for w in weeks]);inc=np.array([weekly[w]['paired_increment_net_eur'] for w in weeks])
    return {'weekly':weekly,'descriptive_95pct_week_block_resampling_total_intervals':{'model_net_eur':[float(x) for x in np.quantile(model[index].sum(axis=1),[.025,.975])],'paired_increment_net_eur':[float(x) for x in np.quantile(inc[index].sum(axis=1),[.025,.975])]},'resamples':2000,'seed':20261014,'independent_blocks':3,'confirmatory_inference':False,'limitation':'ONLY3_ADAPTIVELY_EXPOSED_WEEKS;RESAMPLING_INTERVALS_NOT_COVERAGE_GUARANTEES_OR_GLOBAL_FWER_CONTROL;NO_ALPHA_CERTIFICATION'}

def main():
    head,a=gate();design=json.loads((E.a.ROOT/(P+'ECONOMIC_DESIGN_V1.json')).read_text())
    with tempfile.TemporaryDirectory(prefix='mxm-independent-economic-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY')
        source=store_for(head,key,tmp);db=ar.dbopen(tmp/'accepted.sqlite');old.track(db)
        st=io.restore_snapshot(db,source,a['snapshot']);before=dict(st['requests'])
        output=store_for(head,key,tmp,TAG);rows,g,counts,cohort,vectors,manifest,quotes=prepare(db,st)
        need(st['requests']==before,'READ_ONLY_SNAPSHOT_REQUESTS_CHANGED')
        par=parity(vectors,tmp);dates={r['date'] for r in cohort};weeks={r['iso'] for r in cohort};classes={r['class'] for r in cohort}
        support={'model_entries':len(cohort),'dates':len(dates),'weeks':len(weeks),'classes':len(classes),'gate_pass':len(cohort)>=48 and len(dates)>=12 and weeks=={'2026-W35','2026-W36','2026-W37'} and len(classes)>=2}
        pre={'design_sha256':E.w.old.filehash(P+'ECONOMIC_DESIGN_V1.json'),'source_snapshot':a['snapshot']['current_journal'],'counts':dict(counts),'support':support,'cohort':cohort,'manifest':manifest,'parity':par,'new_requests':0,'outcomes_read':False}
        arm=output.encrypted(json.loads(v1.encode(pre)),'preoutcome-cohort-arm.mxmenc')
        records=[];strict=[]
        if support['gate_pass']:
            for ev in sorted(cohort,key=lambda e:(e['t'],e['sid'])):
                row=rows[ev['sid']];f=st['catalog']['full'][str(ev['sid'])]
                records.append({'event':ev,'model':account(ev['feature']['side'],ev,row,f,quotes,g),'baseline':account(ev['feature']['baseline'],ev,row,f,quotes,g)})
                strict.append({'event':ev,'model':account(ev['feature']['side'],ev,row,f,quotes,g,strict=True),'baseline':account(ev['feature']['baseline'],ev,row,f,quotes,g,strict=True)})
        agg=aggregate(records);port=portfolio(records);bounds=uncertainty(records)
        if not support['gate_pass']:verdict='CLOSED_DATA_LIMITED_PREOUTCOME;NO_FAMILY_NULL'
        elif not agg['paired_supported']:verdict='EXECUTED_ALL_EXIT_ACCOUNTING_CENSORED;NO_FAMILY_NULL'
        elif agg['model']['net_eur']<=0 or agg['paired_increment_net_eur']<=0:verdict='CLOSED_EXACT_NO_PROMOTION_MEASURED_NONPOSITIVE_NET_OR_INCREMENT'
        else:verdict='POSITIVE_EXPLORATORY_REFERENCE_CANDIDATE_ONLY;NO_ALPHA_CERTIFICATION'
        summary={'schema':'mxm.independent.economic.order.result.v1','source_head':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'mechanism':design['mechanism'],'snapshot':a['snapshot']['current_journal'],'catalog':5326,'eligible':len(st['eligible']),'novelty':design['novelty'],'preoutcome_counts':dict(counts),'support':support,'pilot_executed':support['gate_pass'],'cohort_arm':arm,'economic_aggregate':agg,'strict5s_quote_reference':aggregate(strict),'portfolio':port,'uncertainty':bounds,'break_even_bps':stats([r['break_even_bps'] for r in cohort]),'entry_cost_eur':stats([r['cost_eur'] for r in cohort]),'decision':verdict,'alpha_certified':False,'HARD21':False,'protected_forward':False,'broker_requests':0,'actual_orders':0,'new_Cloud_deployment':False,'native_parity':par,'NET_semantics':'NATIVE_SIDE_AWARE_REFERENCE_QUOTES_CURRENT_CONTRACT_PLUS2BPS_PER_SIDE_AND010EUR_DAY_STRESS;HISTORICAL_FINANCING_COMMISSION_FILL_SLIPPAGE_UNKNOWN;NOT_CERTIFIED_EXECUTABLE_NET','prior_adaptive_selection_control':design['repeated_selection_control'],'next_distinct_family':design['next_family_if_not_qualified']}
        full={'summary':summary,'records':records,'strict_records':strict,'universe_manifest':manifest,'design':design,'safe_io_errors':io.ERRORS}
        primary=output.encrypted(json.loads(v1.encode(full)),'complete-economic-result-owner.mxmenc');summary['primary']=primary
        relay=E.upload_extra(output.release,tmp,E.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem'),json.loads(v1.encode(summary)),'economic-summary-session.mxmenc')
        relay['release_id']=output.release['id'];safe={'state':verdict,'source_head':head,'run_id':summary['run_id'],'mechanism':design['mechanism'],'pilot_executed':summary['pilot_executed'],'support':support,'counts':dict(counts),'catalog':5326,'eligible':len(st['eligible']),'primary':primary,'recipient_summary':relay,'OWNER_READBACK_SUCCESS':True,'SESSION_DELIVERY_SUCCESS':False,'broker_requests':0,'HARD21':False,'alpha_certified':False,'actual_orders':0}
        output.commit(safe);print(json.dumps(safe),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as ex:
        io.evidence(ex,'INDEPENDENT_ECONOMIC_STOP');print('FAIL_CLOSED_INDEPENDENT_ECONOMIC_'+type(ex).__name__,flush=True);raise SystemExit(1) from None
