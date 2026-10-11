"""One integrated authenticated campaign; three distinct laws, no closed exact replay."""
import os,json,pathlib,tempfile,hashlib,base64,gzip,math,subprocess
from collections import Counter
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.native_body_persistence_v1.runner_v1 import native_bars,acquire
from research_core_v4.integrated_alpha_campaign_v1 import kernel_v1 as k,economics_v1 as econ
from research_core_v4.integrated_alpha_campaign_v1.history_v1 import extend
e=rt.e;P='research_core_v4/integrated_alpha_campaign_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def sha(b):return hashlib.sha256(b).hexdigest()
def inv(ref):return dict(x.split('\t',1)[::-1] for x in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
def compact(r):
    names=['calendar','signals','paired','censored_signals','model_mean_bps','baseline_mean_bps','increment_mean_bps']
    return {'global':r['global'],'blocks':r['blocks'],'week_columns':names,'complete_weeks':{w:[v[n] for n in names] for w,v in r['weeks'].items()}}
def economic_compact(r):
    names=['calendar','signals','calculable_entries','eligible'];ww={}
    for w,v in r['weeks'].items():
        x=v['scenario']['ELIGIBLE'];s=x['outcomes']['S2_F010'];ww[w]=[v[n] for n in names]+[x['evaluable'],x['censored'],s['model_net_eur'],s['baseline_net_eur']]
    return {'global':r['global'],'blocks':r['blocks'],'week_columns':names+['evaluable_eligible','censored_eligible','net_S2_F010_eur','baseline_S2_F010_eur'],'complete_weeks':ww}
def staged(key,fp,tmp,a):
    m=json.loads((e.a.ROOT/(P+'INPUT_MANIFEST_V1.json')).read_text());blob=base64.b64decode(''.join((e.a.ROOT/p).read_text().strip() for p in m['parts']),validate=True);need(sha(blob)==m['ciphertext_sha256'],'FEATURE_PACKAGE_CIPHER');raw=gzip.decompress(e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp));need(sha(raw)==m['canonical_sha256'],'FEATURE_PACKAGE_CANON');value=e.w.old.crypto.strict_json(raw);need(e.a.enc(value)==raw,'FEATURE_PACKAGE_STRICT_JSON');need(value['kernel_sha256']==e.w.old.filehash(P+'kernel_v1.py') and value['extractor_sha256']==e.w.old.filehash(P+'stage_v1.py'),'LOCAL_FROZEN_EXTRACTOR');need(value['source_rows']==11406418,'YEAR_CORPUS_ROWCOUNT');records={};manifest=json.loads((e.a.ROOT/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());sources={x['symbol_id']:x for x in manifest['primary_series']}
    for item in value['items']:
        sid=item['source']['symbol_id'];need(sid not in records and sources[sid]==item['source'],'ACCEPTED_SOURCE_IDENTITY');rr=item['records'];need([r[0] for r in rr]==list(k.grid()),'FIXED_CALENDAR_INPUT');need(all(r[2] is None or math.isfinite(r[2]) for r in rr),'LABEL_DOMAIN');records[sid]=rr
    need(len(records)==145,'ACCEPTED145_COMPLETE');return records,{n:v for n,v in value.items() if n!='items'},m

def main():
    global PHASE
    os.umask(0o077);h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text());need(a['authority']=='EXPLICIT_OWNER_INTEGRATED_ALPHA_CAMPAIGN_20261011' and not any(a[x] for x in ('orders','protected_forward','cloud_deployment','closed_exact_replay')),'AUTHORITY');need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-integrated-alpha-campaign-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW');need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h);e.a.ancestor(a['design_commit'],h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'FROZEN_SOURCE_BINDING')
    oldtree=inv(a['base_head']);newtree=inv(h);need(all(newtree.get(p)==v for p,v in oldtree.items()),'ALL_ACCEPTED_OLD_FILES_PRESERVED');science=e.w.old.verify_science();need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    with tempfile.TemporaryDirectory(prefix='mxm-integrated-alpha-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='AUTHENTIC_COSTS_BEFORE_NEW_COMPARISONS';cost,cp=load_asset(key,fp,tmp,a['cost_source']);old,op=load_asset(key,fp,tmp,a['qualification_source']);fullcost,fcp=load_asset(key,fp,tmp,a['fullcost_source']);need(old['summary']['decision']=='DATA_LIMITED','V1_UNCHANGED');records,prep,manifest=staged(key,fp,tmp,a)
        nativebars,np=native_bars(old);bars={s:{t:[float(r[n]) for n in ('open','high','low','close','tick_volume')] for t,r in zz.items()} for s,zz in nativebars.items()};del nativebars
        selected,pairs,meta,native,exclusions=econ.universe(cost,set(records)|{1,2,250});source_ids=set(records);PHASE='MISSING_NATIVE_PREFIX';hist=extend(h,a,tmp,key,bars,{s:int(native['full'][str(s)]['digits']) for s in (1,2,250)})
        for s in (1,2,250):records[s]=k.extract(bars[s])
        PHASE='FROZEN_SHARED_FEATURES_AND_CAUSAL_COST_FIRST';features={(sid,t):f for sid,rr in records.items() for t,f,y in rr};quotes={(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in old['private_quote_receipts']};saved=300;additional=0
        for q in fullcost['private_boundary_receipts']:
            z=(int(q['symbol_id']),int(q['boundary_ms'])//1000)
            # Strict complete side provenance is required by this campaign. Unknown is retained missing.
            if z not in quotes and k.ORIGINAL<=z[1]<=k.END and all('source_has_more' in q['sides'].get(n,{}) for n in ('bid','ask')):quotes[z]=q;additional+=1
        # Contract/commission-only reference envelope is computed before direction markout comparisons.
        costfirst={};fxrefs={t:f['price'] for t,f,y in records[1] if f}
        for s,row in selected.items():
            f=native['full'][str(s)];u=int(row['min_volume_cents'])/100;vals=[]
            for t,x,y in records[s]:
                if not x or t not in fxrefs:continue
                ref=fxrefs[t];c=econ.cash.commission(f,u,x['price'],{'bid':ref,'ask':ref});vals.append((2*c/(u*x['price']/ref)*10000,u*x['range']/ref))
            costfirst[str(s)]={'feature_reference_N':len(vals),'minimum_units':u,'current_margin_eur':max(float(row['buy_margin_eur']),float(row['sell_margin_eur'])),'mean_commission_only_lower_bound_bps':sum(x[0] for x in vals)/len(vals) if vals else None,'mean_prior4h_range_eur':sum(x[1] for x in vals)/len(vals) if vals else None,'spread_slippage_historical_swap':'UNKNOWN_UNLESS_EXACT_QUOTE;LOWER_BOUND_NOT_BREAK_EVEN_CERTIFICATE'}
        print(json.dumps({'phase':'COST_FIRST_COMPLETE','authentic_primary145_source_rows':11406418,'frozen_families':3,'outcomes_public':False}),flush=True)
        PHASE='THREE_NEW_NUMERIC_MECHANISMS';events=k.events(records,pairs,features);reports={};rawreports={};identities=[];gates={}
        for name in k.NAMES:
            own=[r for r in events if r['family']==name];reports[name]={};rawreports[name]={}
            for view,ids in [('accepted145',source_ids),('native_reference',{1,2,250}),('economic_structural',set(selected))]:
                rr=[r for r in own if r['sid'] in ids];rp=k.report(rr);cl=k.clustered(rr);rawreports[name][view]={'report':rp,'clustered':cl};reports[name][view]={'report':compact(rp),'clustered':{n:v for n,v in cl.items() if n not in ('weekly_equal_clock_model_bps','weekly_equal_clock_baseline_bps','weekly_supported_moments')}}
            gates[name]=rawreports[name]['native_reference']['clustered']['exploratory_gross_lead']
            for s in sorted(records):identities.append({'family':name,'sid':s,'report':k.report([r for r in own if r['sid']==s])})
            print(json.dumps({'phase':'NEW_MECHANISM_CALCULATED','family_ordinal':k.NAMES.index(name)+1,'outcomes_public':False}),flush=True)
            e.w.old.budget(maxwall=6500,maxcpu=4200,maxkib=3145728)
        # Optional missing quote collection uses whole frozen native cohort only after family-level gross support.
        requests=0;newraw=[];required=set()
        for r in events:
            if r['sid'] in (1,2,250) and gates[r['family']] and k.ORIGINAL<=r['t']<k.END and r['d'] and r['b'] and econ.session(r['t'],native['full'][str(r['sid'])],meta[r['sid']]):required.update((s,t) for s in (r['sid'],1) for t in (r['t'],r['exit']) if t<=k.END)
        need(len(required-set(quotes))*2<=2400,'FIXED_QUOTE_BUDGET')
        if required:PHASE='PREDECLARED_NATIVE_COHORT_MISSING_QUOTES';requests,newraw=acquire(required,quotes,cost,tmp)
        PHASE='CAUSAL_ENTRIES_AND_RETROSPECTIVE_NET_SCENARIOS';priced,contracts=econ.evaluate(events,selected,native,quotes);economic={};fulleconomic={}
        for name in k.NAMES:
            r=econ.report([x for x in priced if x['family']==name]);fulleconomic[name]=r;economic[name]=economic_compact(r)
        chosen,ledger=econ.allocator(priced);pr=econ.report(chosen);portfolio=economic_compact(pr);portfolio['cash_ledger']=ledger
        support={str(s):{'rows':len(bars[s]),'first_utc':datetime.fromtimestamp(min(bars[s]),timezone.utc).isoformat(),'last_utc':datetime.fromtimestamp(max(bars[s]),timezone.utc).isoformat(),'source_identity_same_account':True,'missing_slots_24x7_reference':(k.END-k.PREFIX)//300-len([t for t in bars[s] if k.PREFIX<=t<k.END])} for s in bars}
        upper={str(s):{w:sum(econ.session(t,native['full'][str(s)],meta[s]) for t in k.grid() if k.iso(t)==w) for w in k.complete_weeks()} for s in selected}
        upper_portfolio={w:sum(any(econ.session(t,native['full'][str(s)],meta[s]) for s in selected) for t in k.grid() if k.iso(t)==w) for w in k.complete_weeks()}
        covariance=[]
        # Descriptive cross-asset dependency of markouts, not independent opportunities or fitted weights.
        for s in (1,2,250):
            for v in (1,2,250):
                if s>=v:continue
                xx={t:y for t,f,y in records[s] if y is not None};yy={t:y for t,f,y in records[v] if y is not None};times=sorted(set(xx)&set(yy));rho=float(k.np.corrcoef([xx[t] for t in times],[yy[t] for t in times])[0,1]) if len(times)>2 else None;covariance.append({'sids':[s,v],'paired_moments':len(times),'reference_return_correlation':rho})
        out={'schema':'mxm.private.integrated.alpha.campaign.v1','source_head':h,'design_commit':a['design_commit'],'design_sha256':e.w.old.filehash(P+'DESIGN_FREEZE_V1.json'),'source_integrity':{'accepted145_source_rows':11406418,'accepted145_identities':145,'runner_feature_package_authenticated':True,'local_source_csv_byte_verification':True,'runner_raw145_csv_redecode':False,'native_saved_sources':np,'native_history_extension':{n:v for n,v in hist.items() if n!='raw_receipts'},'native_support':support,'input_manifest_cipher_sha256':manifest['ciphertext_sha256'],'input_provenance':[cp,op,fcp],'master1576_inventory_shards':len(science[1]),'master1576_inventory_rows':sum(x['ROW_COUNT'] for x in science[1]),'master100shards_reexecuted':False},'families':reports,'native_gross_gates':gates,'economics':economic,'portfolio':portfolio,'structural_economic_identities':len(selected),'structural_exclusions':exclusions,'current_contracts':contracts,'cost_first':costfirst,'new_tick_side_requests':requests,'existingV1_boundaries_reused':saved,'existing_fullcost_receipts_available':len(fullcost['private_boundary_receipts']),'existing_fullcost_complete_side_boundaries_reused':additional,'native_return_correlations':covariance,'HARD21':{'calendar_moments_upper_per_complete_week':42,'instrument_current_session_upper_range':{sid:{'min':min(v.values()),'max':max(v.values())} for sid,v in upper.items()},'portfolio_current_session_upper':upper_portfolio,'selected_entry_eligible_by_week':{w:v['eligible'] for w,v in pr['weeks'].items()},'priced_by_week':{w:v['scenario']['ELIGIBLE']['evaluable'] for w,v in pr['weeks'].items()},'supported_NET_trades':0,'demonstrated':False,'independent_moment_count':'UNIDENTIFIED_SERIAL_AND_CROSS_ASSET;42_IS_EXECUTABLE_CALENDAR_GEOMETRY_ONLY'},'classification':'EXPLORATORY_GROSS_LEAD_COST_UNRESOLVED' if any(gates.values()) else 'NO_NATIVE_EXPLORATORY_GROSS_LEAD;NO_ALPHA_PROMOTION','alpha_validated':False,'actual_orders':0,'fills':0,'protected_forward':False,'V1_V2_closed_exact_governance_unchanged':True,'historical_contract_fills_slippage_funding':'UNKNOWN;REFERENCE_AND_STRESS_ONLY;FUNDING0_NOT_KNOWN_ZERO','missing_outcomes':'ENTRY_COHORT_RETAINED;NO_EXIT_MEMBERSHIP_IN_CAUSAL_ENTRY_OR_ALLOCATOR','feature_cohort_sha256':sha(e.a.enc([[r['sid'],r['t'],r['family'],r['d'],r['b']] for r in events])),'bindings':a['bindings']}
        # Keep public outcomes encrypted; full weeks/instruments are primary, concise aggregate relay.
        PHASE='ENCRYPTED_INTEGRATED_DELIVERY';rt.output(h,a,tmp,key,'integratedalpha',{'summary':out,'full_family_reports':rawreports,'private_identity_reports':identities,'full_economic_reports':fulleconomic,'private_economic_events':[{n:v for n,v in r.items() if n not in ('feature','y')} for r in priced],'private_selected_portfolio':chosen,'private_native_m5_history':bars,'new_quote_receipts':newraw,'native_history_raw_receipts':hist['raw_receipts'],'input_preprocessing_provenance':prep,'full_HARD21_current_session_upper':upper},out);relay_summary=json.loads(e.a.enc(out));
        if len(e.a.enc(relay_summary))>=155000:
            relay_summary['cost_first']={'identities':len(costfirst),'full_details':'ENCRYPTED_PRIMARY'};relay_summary['bindings']={'full_manifest':'FROZEN_EXECUTION_V1_JSON'};relay_summary['current_contracts']={'count':len(contracts),'full_details':'ENCRYPTED_PRIMARY'}
        if len(e.a.enc(relay_summary))>=155000:
            for f in relay_summary['families'].values():
                for view in f.values():view['report']['global'].pop('reasons',None)
        need(len(e.a.enc(relay_summary))<160000,'SESSION_RELAY_AGGREGATE_BUDGET');relay(h,a,tmp,relay_summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
