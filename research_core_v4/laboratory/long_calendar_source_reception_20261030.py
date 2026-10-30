"""Pre-outcome long-calendar primary145 source reception and actual M5 clock masks.

Never infer independent weeks from pooled bar counts, first/last timestamps or
the three already studied market identities. Source-only, no strategy returns.
The accepted primary145 manifest spans a year; original ZIP bytes are necessary
for exact causal calendar support and have not been authenticated by this manifest.
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[2]
PRIMARY=ROOT/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json'
ROSTER=ROOT/'research_core_v4/state/MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json'
BROKER22=ROOT/'data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json'
BROKER25=ROOT/'data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json'
FULL=ROOT/'research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_DURABLE_MANIFEST_V1.json'
FRONTIER13=ROOT/'data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json'
START_PROTECTED='2026-09-17T12:02:58Z'
OLD_ORIGINAL='09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259'
OLD_DELTA='37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e'
TRAIN_END='2026-05-01T00:00:00Z'
EVAL_END='2026-09-17T00:00:00Z'
CLOCK=300
LOOKBACK=12
EXIT=8

def need(pred,reason):
    if not pred:raise ValueError('MXM_LONG_CALENDAR_'+reason)

def sha(b):return hashlib.sha256(b).hexdigest()

def load(p):return json.loads(p.read_bytes())

def accepted_catalog():
    primary,roster,old,new,full,front=[load(f) for f in (PRIMARY,ROSTER,BROKER22,BROKER25,FULL,FRONTIER13)]
    need(primary['primary_count']==len(primary['primary_series'])==145,'PRIMARY_145_COUNT')
    need(primary['total_primary_M5_rows']==sum(x['row_count'] for x in primary['primary_series'])==11406418,'PRIMARY_ROW_SUM')
    need(primary['original_capture_sha256']==OLD_ORIGINAL and primary['delta_capture_sha256']==OLD_DELTA,'PRIMARY_ARCHIVE_ID')
    need(primary['protected_forward_opened'] is False,'PRIMARY_FORWARD_STATE')
    need(new['source_capture_utc']=='2026-09-25T07:46:05.447339Z' and
         new['current_counts']['current_eligible_post_exclusion_frontier']==1576,'LAST_ACCOUNT_AUTHORITY')
    need(full['status']=='COMPLETE' and full['encrypted_shard_count']==100 and len(full['entries'])==100 and
         full['PROTECTED_FORWARD_ROW_COUNT']==0,'SHORT_ORIGINALS')
    need(sum(x['ROW_COUNT'] for x in full['entries'])==3355389,'SHORT_BAR_TOTAL')
    need(front['validation']['series_complete']==40 and front['validation']['total_m5_rows']==392181,'THIRTEEN_WEEK_SOURCE')
    byid={x['SYMBOL_ID']:x for x in roster['entries']}
    need(len(byid)==len(roster['entries']),'MASTER_IDS_UNIQUE')
    need(len(primary['primary_series'])==len({x['symbol_id'] for x in primary['primary_series']}),'PRIMARY_IDS_UNIQUE')
    buckets=collections.defaultdict(lambda:{'identities':0,'bars':0,'source_ordinal_bound':0})
    maps=[]
    for x in primary['primary_series']:
        sid=x['symbol_id'];b=byid.get(sid);name=x['symbol'];old_symbol=old['products'].get(name)
        need(b is not None and old_symbol and old_symbol[0]==sid and old_symbol[1]=='BOTH_FEASIBLE','CROSSWALK')
        need(x['file']==f'raw/{sid}_M5.csv' and x['series_sha256'] and
             x['source_archive_sha256'] in (OLD_ORIGINAL,OLD_DELTA),'SOURCE_IDENTITY')
        need(x['row_count']>0 and x['first_timestamp_utc']<x['last_timestamp_utc']<
             START_PROTECTED,'NO_PROTECTED_FORWARD')
        c=b['BROKER_NATIVE_CONTEXT'];a=buckets[c]
        a['identities']+=1;a['bars']+=x['row_count'];a['source_ordinal_bound']+=1
        maps.append({'sid':sid,'asset_class':c,'observed_rows_manifest':x['row_count'],
                     'first':x['first_timestamp_utc'],'last':x['last_timestamp_utc']})
    need(sum(x['identities'] for x in buckets.values())==145,'CLASSES')
    # Later account snapshot is aggregate, not a per-symbol identity-current refresh.
    # September 22 individual feasibility MUST NOT masquerade as September 25.
    return {'schema':'mxm.long-calendar.account-and-source-reception.v1',
      'mode':'AUTHENTICATED_ACCEPTED_METADATA_ONLY',
      'source_year':{'identities':145,'m5_rows':11406418,
                     'declared_from':'2025-09-16T00:00:00Z',
                     'declared_to':'2026-09-16T23:50:00Z',
                     'distinct_asset_classes':len(buckets),
                     'classes':dict(sorted(buckets.items())),
                     'per_identity_exact_weekly_coverage_proven':False,
                     'actual_original_zip_verified_in_inventory_mode':False,
                     'manifest_series_hashes_originals_not_revalidated':True},
      'mid_horizon_13week':{'identities_original':40,'m5_rows':392181,
                          'from':'2026-06-15T00:00:00Z','through':'2026-09-13T23:59:59Z',
                          'replacement_bundles_add_distinct_coverage':True,
                          'raw_archive_verified_this_execution':False},
      'short_horizon':{'identities':1576,'m5_rows':3355389,'shards':100,
                       'calendar_start':'2026-08-20T00:00:00Z',
                       'calendar_end':'2026-09-16T23:55:00Z'},
      'account':{'currency':'EUR','initial_capital':200,
                 'snapshot_20260922_per_identity_145_both_feasible':145,
                 'latest_20260925_eligible_master_identities':1576,
                 'current_per_identity_20260925_recheck_proven':False},
      'research_boundaries':{'prior_development_end':TRAIN_END,
          'later_exposed_development_end':EVAL_END,
          'protected_start':START_PROTECTED,
          'reserved_confirmation_opened':False,
          'independent_confirmation_claimed':False},
      'requires_for_annual_model_before_any_economic_claim':[
          'ORIGINAL_ANNUAL_RAW_ARCHIVE_SHA256_AND_PER_FILE_BYTES',
          'EXACT_PER_INSTRUMENT_WEEK_AND_MONTH_CLOCK_MASK',
          'SOURCE_OBSERVED_CONSECUTIVE_HISTORY_AND_FUTURE_CENSORING',
          'DATED_EXECUTION_BIDASK_FEES_AND_EUR200_BROKER_TICKET',
          'COLD_CONTINUOUS_ONE_ACCOUNT_CSHARP_EXECUTION_AND_INDEPENDENT_CONFIRMATION'],
      'no_closed_strategy_reexecution':True,'orders':0,'broker_requests':0,'cloud':False}

def exact_clock(series):
    """Source-only period coverage. Future existence is an OBSERVABILITY metric,
    never permission to choose a winner after returns. No interpolation, no
    assumptions that empty overnight/weekend slots should contain prices."""
    times=sorted(series)
    need(len(series)==len(times) and len(set(times))==len(times),'DUPLICATES')
    need(all(t%CLOCK==0 and t>=0 for t in times),'FIVE_MINUTE_GRID')
    ts=set(times)
    per=collections.defaultdict(lambda:collections.Counter())
    for t in times:
        d=dt.datetime.fromtimestamp(t,dt.timezone.utc)
        if d.weekday()>4:continue
        if not all(t-CLOCK*k in ts for k in range(LOOKBACK)):
            continue
        w=d.strftime('%G-W%V');q=per[w]
        q['causal_12bar_features']+=1
        if all(t+CLOCK*k in ts for k in range(1,EXIT+1)):
            q['future_8bar_observable']+=1
        else:q['future_8bar_missing']+=1
    return {w:dict(sorted(v.items())) for w,v in sorted(per.items())}

def exact_archive(archive_paths):
    """Read actual accepted raw original ZIPs ONLY, never by filename alone.
    Source is M5 plaintext and must be held privately, not uploaded to PR.
    Return only timestamp support, never prices or per-episode outcomes."""
    paths=list(archive_paths)
    need(len(paths)==2,'TWO_ORIGINAL_INPUT_BUNDLES')
    primary=load(PRIMARY);assertions=collections.defaultdict(list)
    for x in primary['primary_series']:assertions[x['source_archive_sha256']].append(x)
    original={}
    expected={OLD_ORIGINAL,OLD_DELTA}
    for p in paths:
        p=Path(p);digest=sha(p.read_bytes())
        need(digest in expected and digest not in original,'ORIGINAL_ARCHIVE_SHA256')
        original[digest]=p
    need(set(original)==expected,'ARCHIVES_BOTH_REQUIRED')
    result=[];covered=0
    for digest,p in sorted(original.items()):
        with zipfile.ZipFile(p) as z:
            need(z.testzip() is None,'ORIGINAL_ZIP_CRC')
            for entry in assertions[digest]:
                name=entry['file']
                need(z.namelist().count(name)==1,'RAW_MEMBER_IDENTITY')
                data=z.read(name)
                need(sha(data)==entry['series_sha256'],'RAW_MEMBER_SHA256')
                text=io.StringIO(data.decode('utf-8-sig'))
                reader=csv.DictReader(text)
                need(reader.fieldnames is not None,'RAW_HEADERS')
                dates=[];count=0
                for row in reader:
                    need('time_utc' in row,'UTC_COLUMN_NOT_FOUND')
                    d=dt.datetime.fromisoformat(row['time_utc'].replace('Z','+00:00'))
                    need(d.utcoffset()==dt.timedelta(0),'NOT_UTC')
                    t=int(d.timestamp())
                    need(t%300==0 and (not dates or t>dates[-1]),'TIME_ORDER')
                    dates.append(t);count+=1
                need(count==entry['row_count'],'SOURCE_ROW_COUNT')
                need(dt.datetime.fromtimestamp(dates[0],dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')==
                     entry['first_timestamp_utc'],'SOURCE_FIRST')
                need(dt.datetime.fromtimestamp(dates[-1],dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')==
                     entry['last_timestamp_utc'],'SOURCE_LAST')
                mask=exact_clock(dates);covered+=len(dates)
                result.append({'symbol_id':entry['symbol_id'],
                    'calendar_weeks_with_actual_12bar_features':len(mask),
                    'observed_feature_decisions':sum(v.get('causal_12bar_features',0) for v in mask.values()),
                    'observed_future_8bar_missing':sum(v.get('future_8bar_missing',0) for v in mask.values()),
                    'weekly_source_clock_only':mask})
    need(len(result)==145 and covered==11406418,'WHOLE_ANNUAL_SOURCE')
    return {'schema':'mxm.private.source-only.annual-clock-masks.v1',
      'source_originals_sha256':sorted(expected),'authenticated_originals':True,
      'source_bars_rechecked':covered,'series':result,
      'economic_returns_accessed':False,'protected_forward_opened':False,
      'new_broker_requests':0,'orders':0}

def main():
    a=argparse.ArgumentParser();a.add_argument('--mode',choices=('inventory','verify-raw'),default='inventory')
    a.add_argument('--archive',action='append',default=[])
    x=a.parse_args()
    if x.mode=='inventory':
        need(not x.archive,'UNUSED_RAW_SOURCE');print(json.dumps(accepted_catalog(),sort_keys=True))
    else:
        need(x.archive,'SOURCE_IS_REQUIRED')
        print(json.dumps(exact_archive(x.archive),sort_keys=True))

if __name__=='__main__':main()
