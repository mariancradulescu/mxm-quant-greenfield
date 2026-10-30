"""ONE whole-authorized-universe cross-class lagged-breadth portfolio DEVELOPMENT
test. Predeclared current-account M5 ordinal+class join; nothing outcome-ranked.
All 100 original Pepperstone shards authenticated. No new API or trades.
"""
import collections
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import statistics
import subprocess
import tempfile
from pathlib import Path
from . import m5_authentic_envelope as env

ROOT=env.ROOT
REPO=env.REPO
RELEASE=env.RELEASE_IDENTITY
MANIFEST=env.MANIFEST
SPEC=ROOT/'research_core_v4/laboratory/BROAD_SHARED_BREADTH_RESPONSE_20261030_V1.json'
ROSTER=ROOT/'research_core_v4/state/MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json'
BROKER=ROOT/'data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json'
EPOCH=ROOT/'data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json'
OUT=ROOT/'verification/broad-shared-breadth-20261030'
KEY_FP='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
STUDY='V4-BROAD-COHORT-LAGGED-BREADTH-SHARED-20261030-V1'
BAR=300
FAST=12
ENTRY=2
EXIT=8
THRESHOLD_BPS=15
MAX_OWN_FRACTION=0.4
MIN_COHORT_MEMBERS=20
COSTS=(10,20,40)
ISO_FULL=('2026-W35','2026-W36','2026-W37')

def need(ok,why):
    if not ok:raise ValueError('MXM_BROAD_SHARED_'+why)

def sha(data):return hashlib.sha256(data).hexdigest()

def frozen():
    p=json.loads(SPEC.read_bytes())
    need(p['schema']=='mxm.broad-shared-breadth-first-development.v1' and
         p['id']==STUDY and
         p['source']==RELEASE and
         p['minimum_same_class_members']==MIN_COHORT_MEMBERS and
         p['completed_m5_lookback']==FAST and
         p['decision_utc_clock']=='EXACT_UTC_HOUR' and
         p['entry_delay_bars']==ENTRY and p['exit_offset_bars']==EXIT and
         p['cohort_median_bps_hurdle']==THRESHOLD_BPS and
         p['own_prior_move_max_median_fraction']==MAX_OWN_FRACTION and
         p['hypothetical_roundtrip_cost_bps']==list(COSTS) and
         p['source_outcome_preselection'] is False and
         p['single_shared_nonoverlap_slot'] is True and
         p['closed_candidates_rerun']==0 and p['protected_forward_opened'] is False,
         'FROZEN_SPEC_CHANGED')
    return p

def panel():
    frozen()
    roster=json.loads(ROSTER.read_bytes())
    old=json.loads(BROKER.read_bytes())
    latest=json.loads(EPOCH.read_bytes())
    need(latest['current_counts']['current_symbols']==5324 and
         latest['current_counts']['current_new_entry_accessible']==1689 and
         latest['current_counts']['current_eligible_post_exclusion_frontier']==1576 and
         latest['account_fingerprint_sha256']==old['account_fingerprint_sha256'] and
         latest['source_capture_utc']=='2026-09-25T07:46:05.447339Z','ACCOUNT_CAPTURE')
    need(roster['identity_count']==1575 and len(roster['entries'])==1575 and
         old['current_accessible_symbols_indexed']==1690,'EXACT_ROSTER')
    by_id={int(v[0]):(name,v) for name,v in old['products'].items()}
    need(len(by_id)==1690 and all(v[1][1]=='BOTH_FEASIBLE' for v in
         (by_id[int(x['SYMBOL_ID'])] for x in roster['entries'])
         if v[1][1]=='BOTH_FEASIBLE') ,'BROKER_JOIN') # not per-row effect filter
    out={}
    for r in roster['entries']:
        ordinal=int(r['MASTER_ORDINAL']);sid=int(r['SYMBOL_ID'])
        need(ordinal not in out and 1<=ordinal<=1576 and sid in by_id,'INDEX_JOIN')
        name,older=by_id[sid]
        need(older[1]=='BOTH_FEASIBLE' or
             (older[1]=='NEITHER_FEASIBLE' and
              latest['temporal_semantics']['historical_snapshot_remains_immutable']),
             'BROKER_OLD_VS_NEW_STATUS')
        out[ordinal]={'sid':sid,'name':name,'group':r['BROKER_NATIVE_CONTEXT'],
                      'older_snapshot_status':older[1]}
    need(len(out)==1575 and set(range(1,1577))-set(out)=={515},
         'MISSING_IDENTITY_EXPLICIT')
    return out,latest

def parse_rows(rows,segment):
    times=[];opens=[];closes=[]
    first=env.STARTS[segment-1];last=env.ENDS[segment-1]
    prev=-1
    for r in rows:
        need(set(r)=={'time_utc','open','high','low','close','tick_volume'},'BAR_FIELDS')
        stamp=r['time_utc'];t=int(dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp())
        need(stamp.endswith('Z') and first<=stamp[:10]<=last and stamp<env.PROTECTED_START and
             t%BAR==0 and t>prev,'SOURCE_CHRONOLOGY')
        o,h,l,c=[float(r[x]) for x in ('open','high','low','close')]
        v=int(r['tick_volume'])
        need(all(math.isfinite(z) and z>0 for z in (o,h,l,c)) and
             l<=min(o,c)<=max(o,c)<=h and v>=0,'SOURCE_OHLCV')
        times.append(t);opens.append(o);closes.append(c);prev=t
    return times,opens,closes

def extract_events(rows,ordinal,group,segment):
    stamps,opens,closes=parse_rows(rows,segment)
    for i in range(FAST,len(stamps)):
        t=stamps[i]
        if t%3600!=0:continue
        if any(stamps[j]-stamps[j-1]!=BAR for j in range(i-FAST+1,i+1)):
            continue
        past=10000*(closes[i]/closes[i-FAST]-1)
        if not math.isfinite(past):continue
        complete=(i+EXIT<len(stamps) and
                  stamps[i+EXIT]-t==EXIT*BAR and
                  all(stamps[j]-stamps[j-1]==BAR for j in range(i+1,i+EXIT+1)))
        future=(10000*(opens[i+EXIT]/opens[i+ENTRY]-1)) if complete else None
        yield (t,group,ordinal,past,future)

def choice(clock_rows,minmembers=MIN_COHORT_MEMBERS,hurdle=THRESHOLD_BPS):
    """Only past information may influence the winner. Future prices ignored."""
    byclass=collections.defaultdict(list)
    for row in clock_rows:
        t,group,ordinal,past,future=row
        byclass[group].append(row)
    candidates=[]
    for group,cohort in byclass.items():
        need(len({r[2] for r in cohort})==len(cohort),'DUPLICATE_COHORT')
        if len(cohort)<minmembers:continue
        median=statistics.median(r[3] for r in cohort)
        if abs(median)<hurdle:continue
        side=1 if median>0 else -1
        selected=[r for r in cohort if 0<=side*r[3]<=MAX_OWN_FRACTION*abs(median)]
        if not selected:continue
        # Single deterministic underreacting target; no forward outcome rank.
        row=min(selected,key=lambda r:(side*r[3],r[2]))
        candidates.append({'t':row[0],'group':group,'ordinal':row[2],
                           'side':side,'median_bps':median,'own_bps':row[3],
                           'unobserved_future_bps':row[4],'n_cohort':len(cohort)})
    if not candidates:return None
    # Single cross-class programme priority, not a best-in-hindsight context.
    return min(candidates,key=lambda r:(-abs(r['median_bps']),r['group'],r['ordinal']))

def aggregate(events,expected_market_rows,verified_shards,observed_identities):
    need(verified_shards==100 and expected_market_rows==3355389 and
         observed_identities==1576,'ALL_SOURCE_RECONCILED')
    events.sort(key=lambda r:(r[0],r[1],r[2]))
    weekly=collections.defaultdict(lambda:collections.Counter())
    members=collections.Counter()
    signal=collections.Counter()
    outcomes=collections.Counter()
    selected=[]
    total_clocks=0;active_until=-1
    i=0
    while i<len(events):
        t=events[i][0];group=[]
        while i<len(events) and events[i][0]==t:
            row=events[i];members[row[1]]+=1;group.append(row);i+=1
        total_clocks+=1
        if t<=active_until:continue
        c=choice(group)
        if c is None:continue
        active_until=t+EXIT*BAR
        signal[c['group']]+=1
        week=dt.datetime.fromtimestamp(t+ENTRY*BAR,dt.timezone.utc).strftime('%G-W%V')
        w=weekly[week];w['proposals']+=1
        if c['unobserved_future_bps'] is None:
            w['censored']+=1;outcomes['censored']+=1
        else:
            g=c['side']*c['unobserved_future_bps']
            w['complete']+=1;w['gross_bps']+=g
            outcomes['complete']+=1
            outcomes['gross_bps']+=g
            outcomes['positive']+=int(g>0)
            for cost in COSTS:
                outcomes[f'net_after_hypothetical_{cost}bps']+=g-cost
        selected.append({**c,'week':week})
    need(sum(w['proposals'] for w in weekly.values())==len(selected) and
         outcomes['complete']+outcomes['censored']==len(selected),'ACCOUNT_SELECTION')
    answer={'schema':'mxm.broad-shared-economic-first-result.v1','id':STUDY,
        'market_rows_auth_verified':expected_market_rows,
        'market_shards_auth_verified':verified_shards,
        'all_source_identities_count':observed_identities,
        'broker_roster_joined_ordinal_count':1575,
        'missing_class_identity_ordinal':515,
        'candidate_exact_hour_clocks':total_clocks,
        'source_class_group_counts':dict(sorted(members.items())),
        'programme_selected_classes':dict(sorted(signal.items())),
        'one_shared_position_slot':True,
        'programme_proposals':len(selected),'settled':outcomes['complete'],
        'censored':outcomes['censored'],
        'gross_bps_sum':outcomes['gross_bps'],
        'positive_share':outcomes['positive']/outcomes['complete'] if outcomes['complete'] else None,
        'hypothetical_net_bps_sums':{str(k):outcomes[f'net_after_hypothetical_{k}bps'] for k in COSTS},
        'full_iso_weeks':list(ISO_FULL),
        'weekly':{k:dict(v) for k,v in sorted(weekly.items())},
        'cost_is_not_broker_observed':True,
        'eur200_funded_and_min_volume_verified':False,
        'hard21_executed_entries_certified':False,
        'all_selections_development_exposed_not_independent':True,
        'source_market_data_already_exposed_for_other_development':True,
        'new_broker_requests':0,'new_external_providers':0,'live_demo_orders':0,
        'cloud_activations':0,'protected_forward':False,
        'closed_candidates_reexecuted':0}
    complete_each=all(weekly[w]['complete']>=21 for w in ISO_FULL)
    answer['gross_positive']=outcomes['gross_bps']>0
    answer['weekly_necessary_frequency_scenario']=complete_each
    answer['disposition']='INSUFFICIENT_BROKER_COST_AND_FUNDED_EXECUTION' if answer['gross_positive'] and outcomes['net_after_hypothetical_20bps']>0 else 'NO_GROSS_OR_HYPOTHETICAL_20BPS_EDGE'
    return answer,selected

def selftest():
    p,_=panel()
    need(len(p)==1575 and 515 not in p and
         len({z['group'] for z in p.values()})>12,'BROAD_CONTEXTS')
    date=int(dt.datetime(2026,8,24,tzinfo=dt.timezone.utc).timestamp())
    rows=[]
    for j in range(25):
        t=date+j*300;close=1+.0001*j
        rows.append({'time_utc':dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat().replace('+00:00','Z'),
                     'open':str(close),'high':str(close+.0002),'low':str(close-.0002),
                     'close':str(close),'tick_volume':'20'})
    events=list(extract_events(rows,1,'US Equities',1))
    need(len(events)>0,'PRIOR_SUPPORT')
    c=[(date,'US Equities',j,20.,100000.) for j in range(1,25)]
    c[0]=(date,'US Equities',1,2.,-100000.)
    first=choice(c);need(first and first['ordinal']==1,'CAUSAL_SELECTION')
    altered=[(t,g,o,r,-1000000. if o%2 else 1000000.) for t,g,o,r,f in c]
    need(choice(altered)['ordinal']==1,'FUTURE_LEAK')
    c[1]=(date,'US Equities',2,20.,None)
    need(choice(c)['ordinal']==1,'DOES_NOT_SKIP_CENSORED_FUTURE')
    rows[0]['time_utc']=env.PROTECTED_START
    try:parse_rows(rows,1)
    except ValueError:pass
    else:need(False,'NO_PROTECTED_SOURCE_GUARD')
    print('MXM_BROAD_1575_SHARED_ACCOUNT_SOURCE_BLIND_SELFTEST_PASS')

def run():
    frozen()
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and
         os.environ.get('GITHUB_REF')=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.environ.get('GITHUB_EVENT_NAME')=='push' and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1','PROTECTED_CONTEXT')
    panelmap,latest=panel()
    manifest=json.loads(MANIFEST.read_bytes())
    entries=manifest['entries']
    need(manifest['status']=='COMPLETE' and
         manifest['DURABLE_RELEASE_IDENTITY']==RELEASE and
         manifest['PROTECTED_FORWARD_ROW_COUNT']==0 and
         manifest['ACCOUNT_FINGERPRINT_SHA256']==latest['account_fingerprint_sha256'] and
         len(entries)==100 and sum(x['ROW_COUNT'] for x in entries)==3355389,
         'ORIGINAL_MANIFEST')
    remote=env.gh_json('repos/'+REPO+'/releases/tags/'+RELEASE)
    asset={a['name']:a for a in remote['assets']}
    need(len(asset)==100 and remote['target_commitish']==manifest['ARM_COMMIT'],'REMOTE_RELEASE')
    for e in entries:
        a=asset[e['ENCRYPTED_ASSET_NAME']]
        need(a['digest']=='sha256:'+e['ENCRYPTED_ASSET_SHA256'] and
             a['state']=='uploaded','MANIFEST_CIPHER_REMOTE')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package,encrypt_shard,public_spki_sha256
    sourcecnt=0;identitycounts=collections.Counter();verified=0;events=[]
    with tempfile.TemporaryDirectory(prefix='mxm-broad-source-') as d:
        folder=Path(d); key,fp=_private_key_from_secret(folder)
        need(fp==KEY_FP,'CUSTODY_KEY_FINGERPRINT')
        shards=folder/'shards';shards.mkdir(mode=0o700)
        subprocess.run(['gh','release','download',RELEASE,'--repo',REPO,
                        '--dir',str(shards)],stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,check=True,timeout=300)
        need({a.name for a in shards.iterdir()}==set(asset),'100_IMMUTABLE_ASSETS')
        for e in sorted(entries,key=lambda x:(x['SEGMENT_INDEX'],x['SHARD_INDEX'])):
            raw=(shards/e['ENCRYPTED_ASSET_NAME']).read_bytes()
            need(sha(raw)==e['ENCRYPTED_ASSET_SHA256'],'CIPHER_SHA')
            plain=decrypt_synthetic_package(raw,private_key=key)
            need(sha(plain)==e['PLAINTEXT_CANONICAL_SHA256'],'PLAINTEXT_SHA')
            data=json.loads(plain)
            need(data['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and
                 data['segment_index']==e['SEGMENT_INDEX'] and
                 data['shard_index']==e['SHARD_INDEX'] and
                 data['identity_range']==e['IDENTITY_RANGE'],'SHARD_ORIGIN')
            ords=list(range(e['IDENTITY_RANGE'][0],e['IDENTITY_RANGE'][1]+1))
            need([a['ordinal'] for a in data['items']]==ords,'ORDINAL_ID')
            rows=0
            for item in data['items']:
                o=item['ordinal'];rows+=len(item['rows'])
                identitycounts[o]+=1
                if o in panelmap:
                    group=panelmap[o]['group']
                    events.extend(extract_events(item['rows'],o,group,e['SEGMENT_INDEX']))
                else:
                    need(o==515,'NO_OTHER_UNCLASSIFIED_IDENTITY')
                    parse_rows(item['rows'],e['SEGMENT_INDEX'])
            need(rows==e['ROW_COUNT'],'SHARD_ROW_COUNT')
            sourcecnt+=rows;verified+=1
        need(len(identitycounts)==1576 and
             all(n==4 for n in identitycounts.values()),'ALL_FOUR_SOURCE_SEGMENTS')
        result,selections=aggregate(events,sourcecnt,verified,len(identitycounts))
    OUT.mkdir(parents=True,exist_ok=False)
    pub=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(pub)==KEY_FP,'PRIVATE_RECIPIENT')
    details={'schema':'mxm.broad-shared-private.v1','original':result,
             'programme_selections':selections,
             'source_manifest_sha256':sha(MANIFEST.read_bytes()),
             'broker_old_index_sha256':sha(BROKER.read_bytes()),
             'broker_latest_authority_sha256':sha(EPOCH.read_bytes()),
             'roster_sha256':sha(ROSTER.read_bytes()),
             'frozen_spec_sha256':sha(SPEC.read_bytes())}
    cipher=OUT/'private.mxmenc'
    encrypt_shard(gzip.compress(json.dumps(details,sort_keys=True,allow_nan=False).encode(),mtime=0),
                  public_key=pub,output=cipher)
    result['encrypted_details_sha256']=sha(cipher.read_bytes())
    result['frozen_spec_sha256']=sha(SPEC.read_bytes())
    result['roster_sha256']=sha(ROSTER.read_bytes())
    result['latest_broker_authority_sha256']=sha(EPOCH.read_bytes())
    result['market_manifest_sha256']=sha(MANIFEST.read_bytes())
    (OUT/'public.json').write_text(json.dumps(result,sort_keys=True,allow_nan=False)+'\n')
    print('MXM_BROAD_SHARED_PORTFOLIO_ECONOMIC_RESULT '+json.dumps(result,sort_keys=True,allow_nan=False),flush=True)

if __name__=='__main__':
    import sys
    need(sys.argv[1:] in (['selftest'],['protected']),'ARGS')
    if sys.argv[1:]==['selftest']:selftest()
    else:run()
