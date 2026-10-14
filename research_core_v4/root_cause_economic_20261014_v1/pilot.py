"""One conditional DEVELOPMENT pilot; accepted immutable support, outcome-blind enrollment."""
import os,json,pathlib,tempfile,datetime,math,subprocess
from collections import Counter,defaultdict
from functools import lru_cache
from .evidence import E,old,io,snap,ar,P
from .pressure import feature
from research_core_v4.critical_frontier_repair_20261014_v2 import runner_v2 as support
from research_core_v4.full_native_frontier_20261014_v1 import accounting_v1 as fx
from research_core_v4.economic_process_reset_20261014_v1.frontier import quote_map,distribution
from research_core_v4.final_recovery_20261014_v1 import economic as accounting
TAG='mxm-level-pressure-development-20261014-v1'

def route_qualification(qualified):return 'EXECUTE_FROZEN_PILOT' if qualified else 'STOP_SPECIFIC_SUPPORT_LIMIT'

def portfolio(records,rows,st,quotes,g):
    active=[];admitted=[];closed=[];balance=200.;halt=None;maxrisk=maxmargin=0.;maximum=0;marked=[]
    groups=defaultdict(list)
    for r in records:groups[r['event']['t']].append(r)
    clocks=sorted(set(groups)|{r['event']['t']+900 for r in records})
    for t in clocks:
        for r in sorted([r for r in active if r['event']['t']+900<=t],key=lambda r:(r['event']['t'],r['event']['sid'])):
            if r['model'] is None:halt='UNKNOWN_SELECTED_EXIT_NO_SUBSTITUTION';break
            balance+=r['model']['net_eur'];active.remove(r);closed.append(r)
        if halt:break
        unrealized=0.;margin=0.;risk=0.
        for r in active:
            e=r['event'];row=rows[e['sid']];f=st['catalog']['full'][str(e['sid'])];qs=quotes(e['ids'],(e['t'],t),True)
            mark=fx.account(e['feature']['side'],row,f,e['t'],t,(t-e['t'])/3600,qs,g,2,.1)
            if mark is None:halt='UNKNOWN_OPEN_POSITION_MARK_NO_FABRICATED_EQUITY';break
            q0=fx.point(qs.get((e['sid'],e['t'])));qt=fx.point(qs.get((e['sid'],t)))
            now_notional=fx.convert(-row['min_units']*qt['mid'],row['quote'],'EUR',t,qs,g)
            if now_notional is None:halt='UNKNOWN_OPEN_POSITION_FX';break
            unrealized+=mark['net_eur'];margin+=e['margin_eur']*(-now_notional/e['notional_eur'])
            # Budget is a prior-range stress envelope, never a claim of guaranteed stop loss.
            risk+=e['risk_eur']+max(0.,mark['net_eur'])
        if halt:break
        equity=balance+unrealized
        if active and (risk>.01*equity or margin>.4*equity or equity-margin<.6*equity):halt='MARKED_REFERENCE_CAPITAL_CONSTRAINT_BREACH_NO_RESCUE';break
        pending=[]
        for r in sorted(groups.get(t,[]),key=lambda r:(r['event']['cost_eur'],r['event']['sid'])):
            e=r['event'];newrisk=risk+e['risk_eur'];newmargin=margin+e['margin_eur'];aftercost=equity-e['cost_eur']
            if aftercost<=0 or newrisk>.01*aftercost or newmargin>.4*aftercost or aftercost-newmargin<.6*aftercost:continue
            pending.append(r);risk=newrisk;margin=newmargin;equity=aftercost
        # The intent list reserves both risk and margin before any hypothetical acceptance.
        active.extend(pending);admitted.extend(pending);maximum=max(maximum,len(active));maxrisk=max(maxrisk,risk);maxmargin=max(maxmargin,margin)
        marked.append({'t':t,'reference_liquidation_equity':equity,'open_and_pending':len(active),'risk':risk,'margin':margin})
    return {'initial_equity_eur':200,'closed_balance_eur':balance,'admitted':len(admitted),'closed':len(closed),'open_at_stop':len(active),'halt':halt,'maximum_concurrent':maximum,'peak_planned_risk_eur':maxrisk,'peak_reference_margin_eur':maxmargin,'entries_by_week':dict(Counter(r['event']['iso'] for r in admitted)),'closed_by_week':dict(Counter(r['event']['iso'] for r in closed)),'marks':marked,'closed_paired_result':accounting.aggregate(closed),'HARD21':False,'risk_status':'CAUSAL_RANGE_STRESS_NOT_GUARANTEED_STOP;NO_EXECUTABLE_PORTFOLIO_CERTIFICATION','margin_status':'CURRENT_MARGIN_SCALED_BY_CAUSAL_NOTIONAL_NOT_HISTORICAL_BROKER_MARGIN','mark_status':'AUTHENTIC_CLOCK_MARKS;INTRATICK_STOP_EXECUTION_NOT_CERTIFIED','actual_orders':0}

def main():
    io.install();os.umask(0o077);head=os.environ['GITHUB_SHA'];a=json.loads((E.a.ROOT/(P+'PILOT_AUTHORITY_V1.json')).read_text());design=json.loads((E.a.ROOT/(P+'DESIGN_V1.json')).read_text())
    old.need(os.environ['GITHUB_REF_NAME']==a['branch'] and os.environ['GITHUB_RUN_ATTEMPT']=='1','SCOPE');old.need(datetime.datetime.now(datetime.timezone.utc).isoformat()<a['expires'],'EXPIRED');E.a.ancestor(a['base'],head)
    for p,h in a['bindings'].items():old.need(E.w.old.filehash(p)==h,'SOURCE_FREEZE')
    pins=json.loads((E.a.ROOT/'research_core_v4/economic_process_reset_20261014_v1/CLOSURE_SOURCE_PINS_V1.json').read_text())
    for p,h in pins['sources'].items():old.need(E.w.old.filehash(p)==h,'CLOSED_SOURCE_PRESERVED')
    old.need(route_qualification(True)=='EXECUTE_FROZEN_PILOT' and route_qualification(False)=='STOP_SPECIFIC_SUPPORT_LIMIT','QUALIFICATION_ROUTING')
    with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);old.need(fp==E.w.old.FP,'OWNER_KEY');source=old.FrontierStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,'real');source.anchor={'body':json.dumps(a['snapshot'])}
        db=ar.dbopen(tmp/'snapshot.sqlite');snap.track(db);st=snap.restore(db,source);old.need(st['generation']==1293 and len(st['rows'])==5326 and len(st['eligible'])==1562,'SNAPSHOT_IDENTITY')
        accepted=source.restore(a['accepted_primary']);refs=[]
        for z in accepted['economic_reference_shards']:
            part=source.restore(z['asset']);refs.extend(e for e in part['economic_references'] if e['mode']=='STRICT5S' and e['h']==900)
        old.need(len(refs)==7930,'ACCEPTED_ENTRY_POPULATION');rows={int(s):r for s,r in st['rows'].items()};g=fx.graph(list(rows.values()));qp=lru_cache(maxsize=300000)(lambda sid,t,strict=False:support.covered_qpoint(db,sid,t,strict))
        quotes=lambda ids,times,strict=True:quote_map(ids,times,strict,qp)
        barcache={};cohort=[];vectors=[];counts=Counter();perid=defaultdict(Counter)
        for e in sorted(refs,key=lambda x:(x['sid'],x['t'])):
            sid=e['sid'];t=e['t'];bb=barcache.setdefault(sid,old.bars_for(db,sid)) if sid not in barcache else barcache[sid]
            bars=[bb[b] for b in range(t-3900,t-300,300)];z=feature(bars);vectors.append(bars);counts['native_feature_support']+=1;perid[sid]['feature_support']+=1
            if not z['side']:counts['no_pressure_signal']+=1;continue
            counts['pressure_signals']+=1;perid[sid]['pressure_signals']+=1
            scenario=e['scenarios']['2']
            if not scenario['feasible']:counts['accepted_entry_cost_risk_margin_fail']+=1;continue
            q=qp(sid,t,True);old.need(q.get('valid'),'ACCEPTED_ENTRY_DRIFT')
            if not z['lower']<q['mid']<z['upper']:counts['entry_already_outside_level']+=1;continue
            room=e['notional_eur']*z['range']/q['mid']
            if room<2*scenario['cost_eur']:counts['prior_excursion_less_than_twice_cost']+=1;continue
            ev={**e,'feature':z,'cost_eur':scenario['cost_eur'],'risk_eur':scenario['risk_eur'],'margin_eur':e['margin_eur_current'],'break_even_bps':scenario['break_even_bps'],'prior_range_eur':room}
            cohort.append(ev);counts['entry_qualified']+=1;perid[sid]['entry_qualified']+=1
        inp=tmp/'vectors.jsonl';out=tmp/'sides.txt';inp.write_text(''.join(json.dumps(v)+'\n' for v in vectors));subprocess.run(['dotnet',str(E.a.ROOT/(P+'csharp/bin/Release/net8.0/Replay.dll')),str(inp),str(out)],check=True,stdout=subprocess.DEVNULL)
        sides=[int(x) for x in out.read_text().splitlines()];old.need(len(sides)==len(vectors) and all(feature(v)['side']==s for v,s in zip(vectors,sides)),'AUTHENTIC_CSHARP_PARITY')
        gate=design['gates'];support_counts={'entry_count':len(cohort),'dates':len({e['t']//86400 for e in cohort}),'weeks':dict(Counter(e['iso'] for e in cohort)),'classes':dict(Counter(e['class'] for e in cohort)),'identities':len({e['sid'] for e in cohort}),'paired_endpoint_count':sum(e['endpoint_cost_support'] for e in cohort),'continuous_path_count':sum(e['continuous_bilateral_path_support'] for e in cohort)}
        tests={'entry_count':len(cohort)>=gate['entry_count'],'dates':support_counts['dates']>=gate['distinct_dates'],'weeks':set(support_counts['weeks'])==set(gate['all_weeks']),'classes':len(support_counts['classes'])>=gate['classes'],'paired_endpoint':support_counts['paired_endpoint_count']>=gate['paired_endpoint_count'],'path':support_counts['continuous_path_count']>=gate['continuous_path_count']};qualified=all(tests.values())
        manifest=[{**x,'pressure_support':dict(perid[x['sid']]),'pressure_state':'ENTRY_QUALIFIED' if perid[x['sid']]['entry_qualified'] else 'FEATURE_PRESENT_NO_ENTRY' if perid[x['sid']]['feature_support'] else x['state']} for x in accepted['all5326_status_manifest']]
        output=io.Store(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,TAG)
        pre={'source_head':head,'design':design,'design_sha256':E.w.old.filehash(P+'DESIGN_V1.json'),'immutable_snapshot':a['snapshot']['current_journal'],'counts':dict(counts),'support':support_counts,'tests':tests,'qualified':qualified,'route':route_qualification(qualified),'cohort':cohort,'all5326_manifest':manifest,'native_feature_parity_vectors':len(vectors),'closed_sources_verified':len(pins['sources']),'outcomes_read':False}
        arm=output.encrypted(pre,'preoutcome-frozen-arm.mxmenc');output.commit({'state':'FROZEN_ARM_OWNER_READBACK_BEFORE_OUTCOMES','arm':arm,'qualified':qualified,'run_id':int(os.environ['GITHUB_RUN_ID']),'OWNER_READBACK_SUCCESS':True})
        records=[]
        if qualified:
            for e in sorted(cohort,key=lambda e:(e['t'],e['sid'])):
                row=rows[e['sid']];f=st['catalog']['full'][str(e['sid'])]
                records.append({'event':e,'model':accounting.account(e['feature']['side'],e,row,f,quotes,g,strict=True),'baseline':accounting.account(e['feature']['baseline'],e,row,f,quotes,g,strict=True)})
        agg=accounting.aggregate(records);unc=accounting.uncertainty(records) if qualified else None;port=portfolio(records,rows,st,quotes,g) if qualified else None
        verdict='NO_PILOT_MEASURED_SUPPORT_GATES_FAIL' if not qualified else 'PILOT_ALL_ENDPOINTS_CENSORED' if not agg['paired_supported'] else 'CLOSED_EXACT_NO_PROMOTION' if agg['model']['net_eur']<=0 or agg['paired_increment_net_eur']<=0 else 'POSITIVE_EXPLORATORY_REFERENCE_ONLY'
        summary={'schema':'mxm.level.pressure.development.result.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_head':head,'mechanism':design['mechanism'],'decision':verdict,'catalog':5326,'eligible':1562,'counts':dict(counts),'support':support_counts,'tests':tests,'pilot_executed':qualified,'arm':arm,'economic_aggregate':agg if qualified else None,'cash_comparator_net_eur':0 if qualified else None,'portfolio':port,'uncertainty':unc,'entry_cost_eur':distribution([e['cost_eur'] for e in cohort]),'break_even_bps':distribution([e['break_even_bps'] for e in cohort]),'native_feature_parity_vectors':len(vectors),'closed_source_pins':len(pins['sources']),'historical_executable_NET':None,'NET_semantics':'STRICT_NATIVE_BBO_FX_REFERENCE_CURRENT_FEES_2BPS_EACH_SIDE_AND010EUR_DAY_STRESS;NO_ACTUAL_FILL_CERTIFICATION','prior_selection_control':design['repeated_selection'],'alpha_certified':False,'HARD21':False,'orders':0,'broker_requests':0,'protected_forward':False,'collection_write':False,'cloud_deployment':False,'next_scientific_decision':'NO_RETUNING_OR_AUTOMATIC_REPEAT;REVIEW_EXACT_NOVELTY_AND_INFORMATION_BEFORE_ANY_NEXT_DESIGN','native_contract':'PURE_CSHARP_FEATURE_AUTHENTIC_PARITY;ACCEPTED_NATIVE_SCHEDULER_AND_MULTISYMBOL_CONTRACT_REUSED;LIVE_CALLBACK_FILL_RESTART_POSITION_PARITY_NOT_CERTIFIED'}
        primary=output.encrypted({'summary':summary,'records':records,'all5326_manifest':manifest,'design':design,'preoutcome_arm':arm},'pressure-complete-owner.mxmenc');summary['primary']=primary
        relay=E.upload_extra(output.release,tmp,E.a.ROOT/'research_core_v4/final_recovery_20261014_v1/RECIPIENT_PUBLIC_KEY.pem',summary,'pressure-summary-session.mxmenc');relay['release_id']=output.release['id']
        output.commit({'state':verdict,'run_id':summary['run_id'],'source_head':head,'primary':primary,'recipient':relay,'support':support_counts,'tests':tests,'pilot_executed':qualified,'OWNER_READBACK_SUCCESS':True,'orders':0,'HARD21':False,'alpha_certified':False})
if __name__=='__main__':
    try:main()
    except Exception as ex:
        import traceback
        print(json.dumps({'safe_trace':[(pathlib.Path(x.filename).name,x.lineno,x.name) for x in traceback.extract_tb(ex.__traceback__)]}),flush=True);io.evidence(ex,'PRESSURE_PILOT');raise SystemExit(1) from None
