"""Read completed encrypted results only; no row replay, claim, or retuning.

The task explicitly requests global A/B/paired means for all three lags,
support reasons and all four weeks. Those exact aggregates form this separate
output allowlist. Identity, time and context vectors never enter public output.
"""
import json, math, os, pathlib, tempfile
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.numeric_development_v2 import machine_v2 as v2
from research_core_v4.numeric_development_v3 import authority_v3 as a
from research_core_v4.numeric_development_v3.finalization_v3 import Store, verify_complete, JOURNAL

RUN=37927463493
APPROVAL_COMMIT='fcf42eb9a2c87f0701c120ffb41fc63d01cb87be'
ARM_SHA='f982857d38a385ca77c7d3944587bf20a1669ceb062c0d807ed5e53238021749'
LAGS=('0','300','900')
FIELDS={'supported','calendar','fixed_calendar_mean','supported_mean','agreement','disagreement','reasons'}

def approved_aggregate(x, denominator):
    a.need(type(x) is dict and set(x)==FIELDS,'AGGREGATE_FIELDS_DENIED')
    a.need(x['calendar']==denominator and type(x['calendar']) is int,'AGGREGATE_CALENDAR')
    for k in ('supported','agreement','disagreement'):
        a.need(type(x[k]) is int and 0<=x[k]<=denominator,'AGGREGATE_COUNT')
    a.need(x['agreement']+x['disagreement']==x['supported'],'AGGREGATE_PAIR_SUPPORT')
    reasons=x['reasons']
    a.need(type(reasons) is dict and set(reasons)==set(n.REASON),'AGGREGATE_REASON_FIELDS')
    a.need(all(type(v) is int and 0<=v<=denominator for v in reasons.values()) and sum(reasons.values())==denominator and reasons['SUPPORTED']==x['supported'],'AGGREGATE_REASON_COUNTS')
    for k in ('fixed_calendar_mean','supported_mean'):
        v=x[k]; a.need(type(v) is list and len(v)==3,'AGGREGATE_VECTOR_LENGTH')
        a.need(all((k=='supported_mean' and x['supported']==0 and z is None) or (type(z) in (int,float) and math.isfinite(z)) for z in v),'AGGREGATE_VALUE')
        if v[0] is not None:a.need(math.isclose(v[2],v[0]-v[1],rel_tol=1e-9,abs_tol=1e-9),'AGGREGATE_PAIRED_IDENTITY')
    return x

def project(summary, denominator):
    return approved_aggregate({k:summary[k] for k in FIELDS},denominator)

def public_result(document):
    a.need(set(document)=={'schema','original_run_id','original_head','completion_commit','identities','shards','rows','units','lags','qub_support_limited_preserved','claim','costs','receipt_provenance','scientific_reducer_calls','historical_input_downloads'},'PUBLIC_RESULT_FIELDS')
    a.need(document['schema']=='mxm.numeric.task.approved.global.aggregates.v1' and document['original_run_id']==RUN and document['original_head']==APPROVAL_COMMIT,'PUBLIC_RESULT_IDENTITY')
    a.need(document['identities']==1576 and document['shards']==100 and document['rows']==3355389,'PUBLIC_RESULT_COUNTS')
    a.need(document['qub_support_limited_preserved'] is True and document['scientific_reducer_calls']==0 and document['historical_input_downloads']==0,'PUBLIC_RESULT_SCOPE')
    a.need(document['units']=='gross_log_bps' and document['claim']=='DESCRIPTIVE_GROSS_DEVELOPMENT_ONLY' and document['costs']=='COST_UNRESOLVED' and document['receipt_provenance']=='UNKNOWN_CONDITIONAL_LAGS','PUBLIC_RESULT_LIMITATIONS')
    a.need(type(document['completion_commit']) is str and len(document['completion_commit'])==40 and all(c in '0123456789abcdef' for c in document['completion_commit']),'PUBLIC_COMPLETION_SHA')
    a.need(type(document['lags']) is dict and set(document['lags'])==set(LAGS),'PUBLIC_ALL_LAGS')
    for lag in LAGS:
        item=document['lags'][lag]
        a.need(type(item) is dict and set(item)=={'full_frontier','four_weeks'},'PUBLIC_LAG_FIELDS')
        approved_aggregate(item['full_frontier'],1576*672)
        a.need(type(item['four_weeks']) is list and len(item['four_weeks'])==4,'PUBLIC_FOUR_WEEKS')
        for week in item['four_weeks']:approved_aggregate(week,1576*168)
    raw=a.enc(document);a.need(len(raw)<32768,'PUBLIC_RESULT_SIZE')
    return raw

def preflight():
    head=os.environ['GITHUB_SHA'];v2.runtime(head);arm=a.real_gate(head)
    a.need(a.digest(a.ARM)==ARM_SHA,'EXACT_ACCEPTED_ARM')
    run=old.api('actions/runs/'+str(RUN))
    a.need(run['status']=='completed' and run['conclusion']=='success' and run['run_attempt']==1 and run['head_sha']==APPROVAL_COMMIT and run['path']==a.REAL_WORKFLOW,'ORIGINAL_SUCCESS_REQUIRED')
    refs=v2.existing_ref(v2.claim_name(arm));a.need(len(refs)==1 and refs[0]['object']['sha']==APPROVAL_COMMIT,'ORIGINAL_CLAIM')
    complete=v2.existing_ref('mxm-numeric-v3-complete-real-'+arm['invocation_id']);a.need(len(complete)==1,'AUTHORITATIVE_COMPLETION_REQUIRED')
    a.ancestor(APPROVAL_COMMIT,complete[0]['object']['sha']);a.ancestor(complete[0]['object']['sha'],head)
    return head,arm

def main():
    os.umask(0o077);head,arm=preflight()
    master,entries,digits,manifest=old.verify_science()
    with tempfile.TemporaryDirectory(prefix='mxm-completed-result-reader-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);tmp.chmod(0o700);key,fp=old._private_key_from_secret(tmp);a.need(fp==old.FP,'EXISTING_KEY_FINGERPRINT')
        store=Store(head,key,a.ROOT/old.PUBLIC_KEY,tmp,arm,a.digest(a.APPROVAL),fp)
        store.original_run=RUN;store.name=v2.release_name(arm,RUN);store.release=old.api('releases/tags/'+store.name)
        a.need(store.release['target_commitish']==APPROVAL_COMMIT,'REAL_RELEASE_IDENTITY')
        completion=verify_complete(store);a.need(completion is not None,'COMPLETE_REMOTE_READBACK')
        journal,jmeta=store.load_named(JOURNAL);report=journal['report'];engine=journal['engine']
        prefix={'processed_sources':report['source_bindings']['processed_sources'],'expected_rows':report['rows'],'engine':engine}
        v2.verify_processed(prefix,'real',master,digits,entries)
        a.need(report['rows']==engine['rows']==3355389 and sum(s['rows'] for s in engine['states'])==3355389 and len(report['identity_results'])==1576,'REAL_IDENTITY_ROW_ACCOUNTING')
        a.need(report['source_bindings']['files']==arm['bindings'] and report['source_bindings']['scope']==arm['scope'],'REAL_REPORT_BINDINGS')
        for i,(s,r,m) in enumerate(zip(engine['states'],report['identity_results'],master)):
            a.need(s['ordinal']==r['ordinal']==i+1 and s['symbol_id']==r['symbol_id']==m['symbol_id'] and s['rows']==r['rows'] and s['next_clock']==672,'ALL_IDENTITIES_PRESERVED')
            for lag in LAGS:a.need(r['lags'][lag]==n._summary(s['lag'][lag],672),'IDENTITY_ACCUMULATOR_READBACK')
        qub=[i for i,m in enumerate(master) if m.get('symbol')=='QUB.AU' and m['symbol_id']==3741]
        a.need(len(qub)==1,'QUB_IDENTITY_PRESERVED')
        a.need(report['identity_results'][qub[0]]['symbol_id']==3741,'QUB_SUPPORT_LIMITED_PRESERVED')
        roster=a.read('research_core_v4/state/MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json')
        a.need({m['symbol_id'] for m in master}-{e['SYMBOL_ID'] for e in roster['entries']}=={3741},'QUB_FROZEN_SUPPORT_LIMITED_CLASS')
        lags={}
        for lag in LAGS:
            full=n._summary(n._combine([s['lag'][lag] for s in engine['states']]),1576*672)
            weeks=[n._summary(n._combine([s['weekly'][w][lag] for s in engine['states']]),1576*168) for w in range(4)]
            a.need(full==report['full_frontier'][lag] and weeks==report['four_weeks'][lag],'GLOBAL_WEEKLY_ACCUMULATORS')
            a.need(sum(w['supported'] for w in weeks)==full['supported'],'WEEKLY_SUPPORT_ACCOUNTING')
            lags[lag]={'full_frontier':project(full,1576*672),'four_weeks':[project(w,1576*168) for w in weeks]}
        document={'schema':'mxm.numeric.task.approved.global.aggregates.v1','original_run_id':RUN,'original_head':APPROVAL_COMMIT,'completion_commit':completion['completion_commit'],'identities':1576,'shards':100,'rows':3355389,'units':'gross_log_bps','lags':lags,'qub_support_limited_preserved':True,'claim':report['claim'],'costs':report['costs'],'receipt_provenance':report['receipt_provenance'],'scientific_reducer_calls':0,'historical_input_downloads':0}
        safe=public_result(document)
        evidence=store.encrypted({'schema':'mxm.numeric.authentic.result.readback.v1','reader_head':head,'reader_run':int(os.environ['GITHUB_RUN_ID']),'completion':completion,'journal':jmeta,'global_aggregates':document,'all1576_identity_and_row_accounting':'PASS','same_common_AB_support':'PASS','all_lags_and_fixed_weeks':'PASS','scientific_response_replayed':False,'historical_input_downloads':0,'resources':old.usage()},'authentic-result-readback.mxmenc')
        print('APPROVED_GLOBAL_AGGREGATES_V1='+safe.decode().strip(),flush=True)
        print('AUTHENTIC_ENCRYPTED_RESULT_READBACK='+json.dumps({'status':'PASS','evidence':evidence,'completion':completion,'resources':old.usage(),'scientific_reducer_calls':0,'historical_input_downloads':0}),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','code':str(e.args[0]) if isinstance(e,n.NumericalStop) and e.args else 'READBACK_FAILURE','scientific_reducer_calls':0,'historical_input_downloads':0}),flush=True)
        raise SystemExit(2) from None
