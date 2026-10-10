"""Authenticate existing completed outputs, aggregate only; no scientific replay."""
import os,pathlib,tempfile,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.owner_recovery_v1.runtime_v1 import e,rt,gate,load_asset

def iso(ts):
    d=datetime.fromtimestamp(ts,timezone.utc).isocalendar();return f'{d.year}-W{d.week:02d}'

def describe(values):
    if not values:return {'n':0}
    s=sorted(values)
    return {'n':len(s),'min':s[0],'median':s[(len(s)-1)//2],'p95_nearest_rank':s[math.ceil(.95*len(s))-1],'max':s[-1],'mean':sum(s)/len(s)}

def diagnostics(full):
    records=full['private_event_coverage'];quotes=full['private_boundary_receipts']
    counts=Counter();weeks=defaultdict(Counter);isoweeks=defaultdict(Counter)
    ages=defaultdict(list);states=Counter();pages=Counter();matched_paged=Counter();positive=defaultdict(Counter);distinct=set()
    qmap={(q['symbol_id'],q['boundary_ms']):q for q in quotes}
    for q in quotes:
        for side,v in q['sides'].items():
            states[(side,v['state'])]+=1
            if v['state']=='AUTHENTIC_CAUSAL_QUOTE':ages[side].append(v['age_ms'])
        for p in q['raw_pages']:
            pages[(p['side'],'PROVIDER_ERROR' if 'error_code' in p else 'HAS_MORE' if p['hasMore'] else 'NO_MORE')]+=1
    for r in records:
        ev=r['event'];support=ev['response_support_status'];cat=r['coverage'];w=ev['fixed_week'];iw=iso(ev['entry_reference_boundary'])
        counts[(support,cat)]+=1;weeks[(w,support)][cat]+=1;isoweeks[iw]['emitted']+=1;isoweeks[iw][support]+=1;isoweeks[iw][cat]+=1
        if r['quote_markout']:
            positive[iw]['matched_quote_side_positive']+=int(r['quote_markout']['quote_side_markout_before_other_friction_bps']>0)
            distinct.add(ev['symbol_id'])
            qs=[qmap[(ev['symbol_id'],ev[k]*1000)] for k in ('entry_reference_boundary','exit_reference_boundary')]
            matched_paged['events_with_any_hasMore']+=int(any(s.get('source_has_more',False) for q in qs for s in q['sides'].values()))
            aa=[s['age_ms'] for q in qs for s in q['sides'].values()]
            ages['matched_event_max_side_age_ms'].append(max(aa))
    return {'coverage_by_support':[{'response_support':s,'category':c,'events':n} for (s,c),n in sorted(counts.items())],
      'coverage_by_fixed_week_and_support':[{'fixed_week':w,'response_support':s,**{c:v[c] for c in ('BOTH_BOUNDARIES','PARTIAL_BOUNDARY','NO_MATCHED_BOUNDARY')}} for (w,s),v in sorted(weeks.items())],
      'iso_utc_entry_week_counts':[{'iso_week':w,**v,**positive[w],'actual_executed_entries':0,'certified_positive_expectancy_entries':0,'full_iso_week_observed':w in ('2026-W35','2026-W36','2026-W37')} for w,v in sorted(isoweeks.items())],
      'quote_side_age_ms':{s:describe(v) for s,v in ages.items()},'quote_side_states':[{'side':s,'state':t,'n':v} for (s,t),v in sorted(states.items())],
      'provider_page_flags':[{'side':s,'page_flag':t,'n':v} for (s,t),v in sorted(pages.items())],
      'matched_events_hasMore':dict(matched_paged),'matched_distinct_identities':len(distinct),
      'semantics':'LAST_RETURNED_CAUSAL_QUOTE_IN_FIXED_60SECOND_WINDOW;NO_FILL_OR_FRESHNESS_CERTIFICATION;PAGINATION_NOT_COMPLETED;POSITIVE_REALIZATIONS_NOT_POSITIVE_EXPECTANCY'}

def main():
    os.umask(0o077);head,auth=gate('readback')
    with tempfile.TemporaryDirectory(prefix='mxm-readback-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'READBACK_KEY')
        values={};provenance=[]
        for name,b in auth['completed_sources'].items():
            value,meta=load_asset(key,fp,tmp,b);values[name]=value;provenance.append({'name':name,**meta})
        for name in ('fullcost','transition','quotes'):
            att=values[name+'_attestation'];primary=values[name]
            e.w.old.need(e.a.sha(e.a.enc(primary))==att['primary']['canonical_sha256'] and att['primary']['ciphertext_sha256']==auth['completed_sources'][name]['ciphertext_sha256'],'ATTESTED_PRIMARY_BYTES')
            ps=dict(primary['summary']);delivered=dict(att['summary'])
            for k in ('durable_primary','source_head','run_id'):delivered.pop(k,None)
            e.w.old.need(ps==delivered,'ATTESTED_SUMMARY_EQUALITY')
        full=values['fullcost'];e.w.old.need(len(full['private_event_coverage'])==4205 and len(full['private_boundary_receipts'])==8307,'FULL_RECOVERY_COUNTS')
        summary={'schema':'mxm.owner.authenticated.empirical.readback.v1','authentication':'ALL_EXACT_CIPHERS_AND_CANONICAL_BINDINGS_PASS','provenance':provenance,
          'fullcost_summary':full['summary'],'aidr_diagnostics':diagnostics(full),'transition_summary':values['transition']['summary'],'quotes_summary':values['quotes']['summary'],
          'coverage_summary':values['coverage']['summary'],'broker_requests':0,'original_experiments_replayed':False,'orders':0,'protected_forward':False,'independent_confirmation':False}
        rt.output(head,auth,tmp,key,'readback',summary,summary)

if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,'RECOVERY');raise SystemExit(2) from None
