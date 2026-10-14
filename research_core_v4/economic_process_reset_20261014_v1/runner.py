"""Isolated economic lane; accepted immutable inputs, no collection writes."""
import os,json,pathlib,tempfile,hashlib,gzip,base64,datetime,subprocess,re
from . import frontier
from research_core_v4.final_recovery_20261014_v1 import storage as io
from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2 as snapshots,archive_v2 as ar
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as old
E=old.E;need=old.need;P='research_core_v4/economic_process_reset_20261014_v1/';TAG='mxm-economic-process-reset-20261014-v1'

def hypotheses(front):
    cfg=json.loads((E.a.ROOT/(P+'FROZEN_QUALIFICATION_V1.json')).read_text());econ=front['candidate_economics'];results=[]
    for c in cfg['candidates']:
        failures=[]
        if c['id']=='FIXED_PRICE_BOOK_REPLENISHMENT_RESILIENCE_V1':
            if econ['accepted_development_L2_rows_in_snapshot']==0:failures+=['NO_ACCEPTED_PREPROTECTED_NATIVE_L2_QUANTITY_HISTORY']
            failures+=['TECHNICAL_DOM_CAPTURE_NOT_DEVELOPMENT_ALPHA_SUPPORT','HISTORICAL_RECEIPT_TO_NATIVE_CALLBACK_TIMING_UNPROVEN']
        elif c['id']=='NATIVE_RESTING_ORDER_LIQUIDITY_COMPENSATION_V1':
            if econ['quoted_width_ceiling_positive']==0:failures+=['NO_POSITIVE_QUOTED_WIDTH_MINUS_KNOWN_CURRENT_FEES_CEILING_IN_CAPITAL_CONTEXTS']
            if econ['native_passive_fill_and_receipt_history_in_bound_schema']==0:failures+=['PASSIVE_ACCEPTANCE_FILL_CANCEL_AND_ADVERSE_SELECTION_EVIDENCE_NA']
            failures+=['QUOTE_TOUCH_OR_HEDGED_SPREAD_LOCK_NOT_CERTIFIED_INCOME','SERVER_RESTING_VS_CLIENT_ACTIVE_LATENCY_ADVANTAGE_UNMEASURED']
        elif c['id']=='REGIONAL_NATIVE_SESSION_STAGGERED_REPRICING_V1':
            failures+=['AUTHENTIC_HISTORICAL_SESSION_CLOSURE_AUTHORITY_NA','POINT_IN_TIME_COMMON_UNDERLYING_RELATION_AUTHORITY_NOT_ENROLLED','NO_NATIVE_CALLBACK_HISTORICAL_TIMING_PARITY']
        results.append({'candidate':c,'economic_evidence':econ,'qualified':not failures,'failures':failures,'gross':None,'NET':None,'outcomes_read':False,'decision':'DO_NOT_PILOT_UNQUALIFIED_HYPOTHESIS' if failures else 'QUALIFIED_FOR_ONE_PROSPECTIVE_PILOT'})
    return results

def main():
    io.install();os.umask(0o077);head=os.environ['GITHUB_SHA'];a=json.loads((E.a.ROOT/(P+'AUTHORITY_V1.json')).read_text())
    need(os.environ['GITHUB_REPOSITORY']==E.w.old.REPO and os.environ['GITHUB_REF']=='refs/heads/'+a['economic_branch'],'ISOLATED_ECONOMIC_BRANCH')
    need(os.environ['GITHUB_RUN_ATTEMPT']=='1','NO_UNCONTROLLED_RERUN')
    need(datetime.datetime.now(datetime.timezone.utc).isoformat()<a['expires_utc'],'EXPIRED')
    E.a.ancestor(a['accepted_execution_head'],head)
    for path,digest in a['bindings'].items():need(E.w.old.filehash(path)==digest,'PROSPECTIVE_FREEZE_BINDING')
    need(io.api('git/ref/heads/'+a['economic_branch'])['object']['sha']==head,'ECONOMIC_SOURCE_DRIFT')
    canonical_before=io.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']
    with tempfile.TemporaryDirectory(prefix='mxm-economic-process-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY')
        source=old.FrontierStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,'real')
        source.anchor={'body':json.dumps(a['snapshot'])};db=ar.dbopen(tmp/'accepted.sqlite');snapshots.track(db);st=snapshots.restore(db,source)
        need(st['generation']==1293 and len(st['rows'])==5326 and len(st['eligible'])==1562,'ACCEPTED_SNAPSHOT_IDENTITY')
        # Read the accepted negative result as immutable evidence. No predictor replay,
        # new outcomes, sign inversion, threshold or horizon rescue of its exact.
        previous=source.restore(a['accepted_previous_primary']);need(previous['summary']['run_id']==38601324998,'ACCEPTED_PREVIOUS_RESULT')
        output=io.Store(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,TAG)
        print(json.dumps({'phase':'ACCEPTED_OWNER_SNAPSHOT_RESTORED','generation':st['generation'],'catalog':len(st['rows']),'broker_requests':0}),flush=True)
        numeric=frontier.evaluate(db,st);review=hypotheses(numeric)
        qualified=[c for c in review if c['qualified']]
        need(not qualified,'UNEXPECTED_QUALIFIED_CANDIDATE_REQUIRES_SEPARATELY_FROZEN_PILOT_ARM')
        scientific_decision='STOP_NEW_PILOT_NO_QUALIFIED_ECONOMIC_MECHANISM;PRESERVE_NATIVE_FRONTIER_NOT_GLOBAL_UNPROFITABILITY'
        # Registered scientific closures are reconciled by pinned definitions/ledgers,
        # not by recalculating prices or searching their historic profit rankings.
        closure=json.loads((E.a.ROOT/(P+'CLOSURE_SOURCE_PINS_V1.json')).read_text())
        native=json.loads((E.a.ROOT/(P+'csharp/native-contract-result.json')).read_text())
        summary={'schema':'mxm.quantified.native.economic.process.reset.v1','source_head':head,'accepted_execution_head':a['accepted_execution_head'],'run_id':int(os.environ['GITHUB_RUN_ID']),'snapshot':a['snapshot'],'catalog':numeric['catalog'],'eligible':numeric['eligible'],'counts':numeric['counts'],'cases':numeric['cases'],'class_primary':numeric['class_primary'],'candidate_economics':numeric['candidate_economics'],'hypothesis_qualification':review,'qualified_hypotheses':len(qualified),'pilot_executed':False,'pilot_reason':'NONE_PASSES_ALL_PROSPECTIVE_ENTRY_CONDITIONS;NO_FORCE_BY_REFERENCE_FILL_ASSUMPTION','accepted_previous_result':previous['summary'],'closed_results_recomputed':0,'closed_source_pins':len(closure['sources']),'native_information_contract':native,'broker_requests':0,'actual_orders':0,'protected_forward':False,'Stage8':False,'cloud_deployment':False,'HARD21':False,'alpha_certified':False,'historical_full_cost_executable_NET':None,'decision':scientific_decision,'resolved_economic_unknowns':['FULL_NATIVE_MINIMUM_TICKET_CURRENT_COST_REFERENCE_AND_NA_BY_ALL_CATALOG_IDENTITIES','SLIPPAGE_AND_HOLDING_COST_RISK_FRONTIER_WITHOUT_PROFIT_SELECTION','SIMULTANEOUS_HEDGED_CAPACITY_UNDER_AGGREGATE_RISK_MARGIN_RESERVE','EXANTE_FREQUENCY_VS_EXIT_CENSORING_AND_CONTINUOUS_PATH_SUPPORT','PASSIVE_QUOTED_WIDTH_CEILING_VS_AUTHENTIC_EXECUTION_INFORMATION_GAP'],'limits':{k:numeric[k] for k in ('historical_cost_terms','risk_semantics','native_vs_proxy','full_ticket_cost_semantics')},'collection_status_observed':a['snapshot']['state'],'collection_stop_cause':'TRANSPORT_OR_PROTOCOL_STOP_NO_INFINITE_RETRY','collection_restarted':False,'collection_infrastructure_modified':False}
        full={'summary':summary,'all5326_status_manifest':numeric['structural_manifest'],'economic_references':numeric['events'],'closed_source_pins':closure,'qualification_design':json.loads((E.a.ROOT/(P+'FROZEN_QUALIFICATION_V1.json')).read_text())}
        primary=output.encrypted(json.loads(old.encode(full)),'complete-economic-frontier-owner.mxmenc');summary['primary']=primary
        report=render(summary)
        report_packet={'summary':summary,'complete_primary':primary,'report_bytes_b64':base64.b64encode(report.encode()).decode(),'report_sha256':hashlib.sha256(report.encode()).hexdigest()}
        report_ref=output.encrypted(json.loads(old.encode(report_packet)),'complete-economic-report-owner.mxmenc')
        # Delivery can be read in the owner session; private key stays on the runner.
        relay=E.upload_extra(output.release,tmp,E.a.ROOT/'research_core_v4/final_recovery_20261014_v1/RECIPIENT_PUBLIC_KEY.pem',json.loads(old.encode(report_packet)),'economic-reset-session-report.mxmenc');relay['release_id']=output.release['id']
        canonical_after=io.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha'];need(canonical_before==canonical_after,'ACTIVE_CANONICAL_BRANCH_CHANGED_EXTERNALLY')
        safe={'state':scientific_decision,'source_head':head,'run_id':summary['run_id'],'catalog':5326,'eligible':1562,'qualified_hypotheses':0,'pilot_executed':False,'primary':primary,'complete_report':report_ref,'recipient_report':relay,'OWNER_READBACK_SUCCESS':True,'canonical_head_unchanged':canonical_after,'collection_manifest_written':False,'broker_requests':0,'orders':0,'HARD21':False,'alpha_certified':False,'case_counts':{k:{n:v[n] for n in ('cohort','entry_risk_cost_feasible','paired_endpoint_support','continuous_bilateral_path_support')} for k,v in numeric['cases'].items()}}
        output.commit(safe);print(json.dumps(safe,sort_keys=True),flush=True)

def render(s):
    lines=['# MXM — Frontiera economică și calificarea mecanismelor, 14 octombrie 2026','',f"Run {s['run_id']}; source HEAD {s['source_head']}; snapshot OWNER 1293.",'','Decizie: nu pornește un pilot nou. Cele trei ipoteze economice analizate nu îndeplinesc toate condițiile prospectiv înghețate. Datele și universul rămân deschise; aceasta nu este o demonstrație a imposibilității profitului.','', 'Catalog 5326; toate identitățile contabilizate, 1562 eligibile. Intrările sunt referințe economice, nu ordine sau alpha.','', '| Mod / orizont, 2 bps/sens | Referințe cu cost | Fezabile ex ante | Ieșire disponibilă | Traseu bilateral complet | Cost median EUR | BE median bps | Capacitate simultană maximă |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for m in frontier.MODES:
        for h in frontier.HORIZONS:
            v=s['cases'][f'{m}_H{h}_S2'];fmt=lambda x:'N/A' if x is None else f'{x:.6f}'
            lines.append(f"| {m}/{h//60}m | {v['cohort']} | {v['entry_risk_cost_feasible']} | {v['paired_endpoint_support']} | {v['continuous_bilateral_path_support']} | {fmt(v['cost_eur']['median'])} | {fmt(v['break_even_bps']['median'])} | {v['simultaneous_capacity_upper']['maximum_simultaneous']} |")
    lines+=['','Costurile sunt BID/ASK și FX autentice, volume minime și comisioane precise curente, plus scenarii înghețate 0/1/2/5 bps pe sens și finanțare 0,10 EUR/zi. Taxa PnL are un envelope prospectiv, nu un PnL calculat. Termenii istorici, slippage-ul realizat, fillurile și NET executabil certificat sunt N/A. Intervalele fără cost observabil nu sunt cost zero.','', 'Riscul este proxy din 12 bare M5 native închise, maxima range-ului × sqrt(orizont/5m) sau gap observat, plus cost. Stopul nu garantează pierderea. Marja este referință contractuală curentă, nu marjă istorică certificată.','', '| Mod / orizont | Capacitate W35 | W36 | W37 | Limită prin prima ieșire N/A |','|---|---:|---:|---:|---|']
    for m in frontier.MODES:
        for h in frontier.HORIZONS:
            v=s['cases'][f'{m}_H{h}_S2'];a=v['simultaneous_capacity_upper'];z=v['chronological_censor_guard_capacity'];w=a['by_ISO_week']
            lines.append(f"| {m}/{h//60}m | {w.get('2026-W35',0)} | {w.get('2026-W36',0)} | {w.get('2026-W37',0)} | {z['admitted_ticket_opportunities']} admiteri; {z['halt'] or 'fără HALT în suportul inspectat'} |")
    lines+=['','Aceste planuri permit bilete simultane HEDGED sub risc agregat 2 EUR, marjă 80 EUR și rezervă 120 EUR. Equity este referință fixă 200 EUR; nu există rezultate de strategie sau reset al cash-ului după pierderi. Capacitatea este un plafon de oportunități ex ante, nu o certificare HARD21. Nu se selectează după PnL sau după disponibilitatea viitoare a ieșirii. Gardul cronologic oprește la prima ieșire selectată neobservabilă.','', '## Calificarea economică înainte de outcomes','']
    for q in s['hypothesis_qualification']:
        c=q['candidate'];lines += [f"**{c['id']}**",c['economic_channel'],f"Comparator: {c['comparator']}. Sens: {c['direction']}. Orizont: {c['horizon_seconds']} secunde.",f"Falsificator: {c['falsifier']}", 'Rezultat de calificare: '+', '.join(q['failures']), 'GROSS și NET ale unui pilot nou: N/A; pilot neexecutat.','']
    e=s['candidate_economics'];lines += [f"Referințe cu capital pentru două leg-uri pending: {e['passive_quote_reference_contexts']}; plafon optimist lățime BBO minus comisioane/finanțare pozitiv: {e['quoted_width_ceiling_positive']}. Acesta nu este profit așteptat. Capturarea spreadului prin două poziții CFD HEDGED nu creează venit gratuit: costul lichidării și adversitatea fillurilor contează. Istoric de acceptare/fill/cancel/latency în schema legată: zero; suport L2 DEVELOPMENT în snapshot: zero. Autoritatea închiderii istorice a sesiunilor: "+e['historical_session_closure_authority'], '', 'Factor drift, lead-lag generic, carry/dividend fără autoritate temporală și exactul return–variation închis nu sunt relansate. Reconcilierea folosește ledgerele și designurile acceptate, fără calculul din nou al rezultatelor lor.','', '## Rezultatul acceptat anterior, reutilizat fără replay','']
    old=s['accepted_previous_result']['economic_aggregate'];lines += [f"Exactul SIGNED_RETURN_QUADRATIC_VARIATION_TEMPORAL_ORDER_V1 rămâne CLOSED_NO_PROMOTION: {old['paired_supported']} perechi; GROSS model {old['model']['midpoint_gross_eur']:.6f} EUR; cost {old['model']['total_cost_eur']:.6f} EUR; NET {old['model']['net_eur']:.6f} EUR; comparator NET {old['baseline']['net_eur']:.6f} EUR. Sunt markouturi individuale de referință, nu pierderi de cont. Nu se schimbă sensul/pragurile/exitul pentru salvare.",'','## Contractul C# nativ și limite','',json.dumps(s['native_information_contract'],ensure_ascii=False,sort_keys=True),'','Testele de scheduler, acces multi-symbol și gard de restart verifică implementarea noului contract; nu sunt performanță economică și nu certifică paritatea Cloud live sau broker fill. Nu există deployment, ordine, protected forward sau Stage8.','', '## Starea colectării','', 'Runul acceptat 38612599613 a închis SUCCESS. Campania succesoare 38617224792 a închis FAILURE la transport/protocol, păstrând generația 1293: 95 identități procesate, 1467 rămase; BID/ASK 9525, M5 132; zero cereri pending în ancora finală. Nu am întrerupt o colectare sănătoasă și nu am relansat infrastructura în buclă. Manifestul/release-ul/canonical HEAD au rămas nemodificate de această cercetare.','', '## Decizie fermă','', 'STOP pentru un pilot nou pe cele trei ipoteze actuale; niciuna nu are suport autentic al informației economice necesare. Frontiera numerică și manifestul tuturor identităților sunt conservate pentru alegerea unui mecanism calificabil. Rezolvarea unui gap de execuție sau a unui gap de autoritate temporală trebuie să preceadă un alt pilot, folosind numai surse Pepperstone autorizate și fără deployment/ordine/protected forward. Fără testarea în buclă a transformărilor acelorași randamente și fără declararea întregului univers nul.']
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    try:main()
    except Exception as ex:
        import traceback
        print(json.dumps({'safe_code_trace':[{'file':pathlib.Path(x.filename).name,'line':x.lineno,'function':x.name} for x in traceback.extract_tb(ex.__traceback__)]}),flush=True)
        io.evidence(ex,'ECONOMIC_RESET_STOP');print('FAIL_CLOSED_ECONOMIC_RESET_'+(str(ex) if re.fullmatch('[A-Z0-9_]{1,120}',str(ex)) else type(ex).__name__),flush=True);raise SystemExit(1) from None
