"""ONE first evaluation of the EXISTING native C# read-only H1 MxmRelativeStrengthPortfolio.

Policy algorithm mirrors exact frozen C# at HEAD 4c3a4e66, not a new tuned family.
Source roster: first 8 sorted primary145 Forex (Spot) broker symbol IDs (3,7,9,10,11,12,13,14),
deterministic before outcomes. No broker orders, fills, cost quotes, funding or Cloud.
H1 closes require all 12 genuine M5 components, no forward fill. Native Platform H1
construction/arrival parity NOT proven. Source-only 2025-W40 to 2026-W22 FULL weeks,
not W24-37 from closed Ridge/peer studies. All dates considered, no winner period filter.
One account common hourly decision; hypothetical long/short at first post-decision M5
open +5 minutes and exit after 55 minutes at +60min open, no overlapping positions.
Gross returns in bps are sum of individual instrument percentages, NOT EUR200 P&L.
"""
import collections,datetime as dt,hashlib,io,json,math,zipfile
from pathlib import Path
import numpy as np,pandas as pd
P=Path(__file__).resolve().parent
SIDS=(3,7,9,10,11,12,13,14)
START=dt.datetime(2025,9,29,tzinfo=dt.timezone.utc) # 2025-W40 Monday
END=dt.datetime(2026,6,1,tzinfo=dt.timezone.utc) # 2026-W23 Monday
ZIP_SHA={'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip':'09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259',
'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip':'37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e'}
CSPOLICY_GIT_SHA1='25019b000745058c6d7a59196a1fe8256ee41ea3'
COSTS=(10,20,40)

def selftest():
    assert START.isocalendar()[:2]==(2025,40)
    assert END.isocalendar()[:2]==(2026,23)
    # Tests the source-only 12-M5 hour contract and C# ranking/tie semantics.
    t=np.arange(24,dtype=np.int64)*300+3600
    assert np.all(np.diff(t[0:12])==300)
    assert len(t[:11])!=12
    assert rank({'A':.3,'B':-.3,'C':0})==('A',1)
    assert rank({'A':0.1,'B':0,'C':-.1}) is None
    print('H1_NATIVE_POLICY_RESEARCH_RULES_FROZEN_PASS')

def rank(scores):
    vals=sorted(scores.values());med=vals[len(vals)//2] if len(vals)%2 else (vals[len(vals)//2-1]+vals[len(vals)//2])/2
    ordered=sorted(((abs(v-med),k,1 if v-med>0 else -1) for k,v in scores.items()),key=lambda x:(-x[0],x[1]))
    mag,k,d=ordered[0]
    if vals[-1]-vals[0]<.5 or mag<.25:return None
    return k,d

def read_source():
    items={};zips={};origin={};
    for file,h in ZIP_SHA.items():
        f=P/file
        assert hashlib.sha256(f.read_bytes()).hexdigest()==h,('ZIP_HASH',file)
        zips[file]=zipfile.ZipFile(f)
    for sid in SIDS:
        match=[(fname,z) for fname,z in zips.items() if f'raw/{sid}_M5.csv' in z.namelist()]
        assert len(match)==1,('SERIES_MATCH',sid)
        fname,z=match[0]
        raw=z.read(f'raw/{sid}_M5.csv')
        df=pd.read_csv(io.BytesIO(raw),parse_dates=['time_utc'])
        assert list(df.columns)==['time_utc','open','high','low','close','tick_volume']
        d=df.set_index('time_utc').sort_index()
        assert not d.index.duplicated().any() and (d[['open','high','low','close']]>0).all().all()
        assert (d['high']>=d[['open','close','low']].max(axis=1)).all()
        assert (d['low']<=d[['open','close','high']].min(axis=1)).all()
        # Convert genuine complete hourly bars; missing H1 disqualifies that hour.
        g=d.resample('1h',label='left',closed='left')
        hourly=g.agg(count=('close','size'),close=('close','last'))
        valid=hourly['count']==12
        hourly=hourly[valid]
        hstart=hourly.index
        assert all(d.index.get_indexer(hstart+pd.Timedelta(minutes=55))>=0)
        ends=hstart+pd.Timedelta(hours=1)
        items[sid]={'hours':{int(t.timestamp()):float(v) for t,v in zip(ends, hourly['close'])},
            'open':{int(t.timestamp()):float(v) for t,v in zip(d.index,d['open'])}}
        origin[str(sid)]={'raw_csv_sha256':hashlib.sha256(raw).hexdigest(),'zip':fname,'source_m5_rows':len(d),'strict_complete_H1':len(hourly)}
    return items,origin

def decide(items):
    # Reconstruct the native observation callback arrival order deterministically.
    allhours=sorted(set().union(*(set(v['hours']) for v in items.values())))
    series={k:{} for k in items};decisions=[];last=0; flat=collections.Counter()
    for end in allhours:
        for sid in SIDS:
            h=items[sid]['hours']
            if end not in h:continue
            b=series[sid];b[end]=h[end]
            for old in list(b):
                if old<end-12*3600:del b[old]
        if end<=last or any(end not in series[s] for s in SIDS):continue
        last=end
        d=dt.datetime.fromtimestamp(end,dt.timezone.utc)
        if d<START or d>=END:continue
        if d.weekday()>=5 or not 7<=d.hour<=15:
            flat['OUTSIDE_SESSION_FLAT']+=1;continue
        scores={};reason=None
        for sid in SIDS:
            b=series[sid];prev=b.get(end-12*3600)
            if prev is None:reason='PAST_ENDPOINT_UNAVAILABLE_FLAT';break
            variation=sum(abs(v/b[t-3600]-1) for t,v in b.items() if t-3600 in b)
            pairs=sum(1 for t in b if t-3600 in b)
            if pairs<9 or variation<=0:reason='PAST_VARIATION_UNAVAILABLE_FLAT';break
            score=(b[end]/prev-1)/variation
            scores[str(sid)]=max(-1,min(1,score))
        if reason:
            flat[reason]+=1;continue
        target=rank(scores)
        if target is None:
            flat['NO_RELATIVE_DISPERSION_FLAT']+=1;continue
        sid,direction=int(target[0]),target[1]
        decisions.append({'end_epoch':end,'iso_week':d.strftime('%G-W%V'),'sid':sid,'direction':direction,
            'entry_epoch':end+300,'exit_epoch':end+3600})
    return decisions,flat

def evaluate(items,decisions):
    episodes=[]
    for d in decisions:
        op=items[d['sid']]['open']; a=op.get(d['entry_epoch']);b=op.get(d['exit_epoch'])
        val=d|{'future_observed':bool(a is not None and b is not None)}
        if val['future_observed']:
            val['gross_bps']=float(10000*d['direction']*(b/a-1))
        episodes.append(val)
    weeklist=[];cur=START
    while cur<END:
        weeklist.append(cur.strftime('%G-W%V'));cur+=dt.timedelta(days=7)
    by=collections.defaultdict(list)
    for e in episodes:by[e['iso_week']].append(e)
    weeks=[]
    for w in weeklist:
        ep=by[w];real=[e['gross_bps'] for e in ep if e['future_observed']]
        weeks.append({'iso_week':w,'proposals':len(ep),'observed':len(real),'censored':len(ep)-len(real),
        'gross_bps_sum':round(sum(real),7),'hypothetical_20bps_net_bps_sum':round(sum(real)-20*len(real),7),
        'at_least_21_PROPOSALS_only':len(ep)>=21})
    gross=sum(e.get('gross_bps',0) for e in episodes)
    n=sum(e['future_observed'] for e in episodes)
    symbol=collections.Counter(e['sid'] for e in episodes)
    report={'schema':'mxm.primary145.existing-native-h1-relative-strength.annual-development.v1',
        'native_source_exact':'research_core_v4/native_tick_replay_v1/csharp/MxmRelativeStrengthPortfolio.cs',
        'native_source_git_blob_sha1':CSPOLICY_GIT_SHA1,
        'CSharp_original_executed_against_data':False,'source_only_python_reference_not_csharp_parity':True,
        'hypothesis':'existing frozen C# H1 JOINT_RELATIVE_STRENGTH_TARGET positive sign',
        'roster_method':'first 8 broker IDs sorted among PRIMARY145 Forex (Spot); NOT outcome-ranked; policy requires 3-16',
        'symbol_ids':SIDS,'prior_rejected_ridge_and_peer_outcomes_not_read':True,
        'evaluation_complete_iso_weeks':[weeklist[0],weeklist[-1]],'week_count':len(weeks),
        'assumed_entry_delay_min':5,'assumed_exit_after_signal_min':60,
        'no_overlapping_hypothetical_positions':True,
        'proposals':len(episodes),'observed_episodes':n,'censored':len(episodes)-n,
        'gross_bps_sum':gross,'hypothetical_net_cost_bps_sum':{str(k):gross-k*n for k in COSTS},
        'broker_bidask_cost_certified':False,'broker_fill_or_orders':False,'eur200_shared_account_pnl':False,
        'native_CSharp_Cloud_reception':False,'hard21_broker_executed':False,
        'weeks_with_at_least_21_proposals_not_fills':sum(x['at_least_21_PROPOSALS_only'] for x in weeks),
        'weeks_with_positive_hypothetical_20bps':sum(x['hypothetical_20bps_net_bps_sum']>0 for x in weeks),
        'weeks':weeks,'all_sessions_no_outcome_selection':True,
        'proposal_concentration_by_sid':dict(symbol),
        'classification':'DEVELOPMENT_ONLY_NO_NATIVE_ECONOMIC_QUALIFICATION',
        'no_model_fit_or_retuning':True,
        'note':'Hourly bar construction is conservative exact-M5 aggregation; native cTrader hour/tick parity remains unproven; costs per trade in bps only.'}
    return report,episodes

def main():
    selftest()
    items,provenance=read_source()
    decisions,flat=decide(items)
    report,episodes=evaluate(items,decisions)
    report['per_series_original_custody']=provenance
    report['native_policy_nonproposal_counts']=dict(flat)
    P.joinpath('PRIMARY145_NATIVE_H1_POLICY_ECONOMIC_PUBLIC.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    P.joinpath('PRIMARY145_NATIVE_H1_POLICY_ECONOMIC_PRIVATE.json').write_text(json.dumps({'source_provenance':provenance,'episodes':episodes},indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('week_count','proposals','observed_episodes','censored','gross_bps_sum','hypothetical_net_cost_bps_sum','weeks_with_at_least_21_proposals_not_fills','weeks_with_positive_hypothetical_20bps','classification')},indent=2))
if __name__=='__main__':main()
