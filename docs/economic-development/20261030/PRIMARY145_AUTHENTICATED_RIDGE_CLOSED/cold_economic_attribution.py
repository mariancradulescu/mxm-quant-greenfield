"""No research replay. Attribute immutable single DEVELOPMENT model output."""
from pathlib import Path
import json,collections,datetime as dt,hashlib
P=Path('/mnt/data/mxm_primary145_originals')
private=P/'PRIMARY145_RIDGE_SINGLE_DEVELOPMENT_PRIVATE.json'
result=json.loads(private.read_text())
source=json.loads((P/'PRIMARY145_AUTHENTICATED_SOURCE_CLOCKS_PRIVATE.json').read_text())
rows=result['private_chosen_episode_outcomes']
full=[f'2026-W{i:02d}' for i in range(24,38)]
wkeys={x['datetime_utc'][:4]+'-W'+f'{dt.datetime.fromisoformat(x["datetime_utc"].replace("Z","+00:00")).isocalendar().week:02d}' for x in rows}
assert set(full)<=wkeys
week=collections.defaultdict(list)
for x in rows:
 d=dt.datetime.fromisoformat(x['datetime_utc'].replace('Z','+00:00'))
 w=d.strftime('%G-W%V');week[w].append(x)
assert len(rows)==result['coverage']['test_opportunity_hours']
assert sum(x['future_observed'] for x in rows)==result['coverage']['observed_gross_completions']
all_gross=sum(x['observed_gross_bps'] for x in rows if x['future_observed'])
assert abs(all_gross-result['gross_model']['gross_bps_sum'])<1e-6
n_full=[x for w in full for x in week[w]]
settled=[x for x in n_full if x['future_observed']]
censored=[x for x in n_full if not x['future_observed']]
gross=sum(x['observed_gross_bps'] for x in settled)
main=collections.defaultdict(lambda:{'proposals':0,'observed':0,'gross_bps_sum':0.})
for x in n_full:
 r=main[x['symbol_id']];r['proposals']+=1
 if x['future_observed']:
  r['observed']+=1;r['gross_bps_sum']+=x['observed_gross_bps']
rank=sorted(main.items(),key=lambda kv:-kv[1]['proposals'])
primary={row['symbol_id']:row['symbol'] for row in source['actual_series_clock_receipts']}
weeks=[]
for w in full:
 r=week[w];valid=[e for e in r if e['future_observed']]
 weeks.append({'iso_week':w,'modeled_proposals':len(r),'observable_episodes':len(valid),'censored':len(r)-len(valid),
  'hypothetical_20bps_net_bps_sum':sum(e['observed_gross_bps']-20 for e in valid), 'meets_21_PROPOSALS_only':len(r)>=21})
report={'schema':'mxm.primary145.cold-heldout-source-driven-concentration-audit.v1',
 'classification':'DEVELOPMENT_HYPOTHETICAL_COST_FAIL_FULL_ISO_WEEKS','development_independent_confirmation':False,
 'source_original_zip_sha256_verified':True,'training_and_selection_reexecuted':False,
 'evaluation_full_iso_weeks':'2026-W24..2026-W37', 'week_count':len(full),
 'full_week_proposals':len(n_full),'full_week_observed':len(settled),'full_week_censored':len(censored),
 'full_week_gross_bps_sum':gross,'full_week_hypothetical_cost_bps_net_sums':{str(cost):gross-cost*len(settled) for cost in (10,20,40)},
 'partial_week_2026_W38_excluded':{'proposals':len(week['2026-W38']), 'gross_bps_sum':sum(x['observed_gross_bps'] for x in week['2026-W38'] if x['future_observed'])},
 'full_weeks_with_at_least_21_modeled_proposals':sum(len(week[w])>=21 for w in full),
 'full_weeks_below_21_modeled_proposals':sum(len(week[w])<21 for w in full),
 'top_concentration':[{'symbol_id':sid,'symbol':primary[sid],**stats} for sid,stats in rank[:10]],
 'weeks':weeks,'no_broker_fills':True,'not_an_eur200_funded_account':True,'hypothetical_costs_only':True,
 'protected_forward_unopened':True,'orders':0,'cloud':False,'no_strategy_retuning':True}
assert len(weeks)==14 and report['full_week_gross_bps_sum']+report['partial_week_2026_W38_excluded']['gross_bps_sum']==all_gross
out=P/'PRIMARY145_RIDGE_COLD_FULL_WEEKS_VERDICT_PUBLIC.json';out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print('COLD_VERDICT',json.dumps({k:v for k,v in report.items() if k not in ('weeks','top_concentration')},sort_keys=True))
print('TOP_CONCENTRATION',report['top_concentration'][:3]);print('FILE',out)