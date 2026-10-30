"""MXM one-shot development-only H1 FX currency-graph flow trial.

Frozen before economic inspection on 2026-10-30: source-only cross-currency
latent-flow continuation, no optimization, orders, Cloud or operational change.
Not a funded-account result, execution simulator or cost certification.
"""
import collections
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import numpy as np

SOURCE = Path('/mnt/data/files/PRIMARY145_NATIVE_H1_CSHARP_INPUT_PRIVATE.json')
EXPECTED = '7157db48811ed1f1e4583ab567c6e04c876a4c4738c4bd242f182632fff54ebb'
PAIRS = {'AUDJPY':('AUD','JPY'), 'CHFJPY':('CHF','JPY'),
         'EURAUD':('EUR','AUD'), 'EURCHF':('EUR','CHF'),
         'EURGBP':('EUR','GBP'), 'EURJPY':('EUR','JPY'),
         'GBPJPY':('GBP','JPY')}
ROSTER=tuple(sorted(PAIRS))
CURRENCIES=tuple(sorted(set(v for pair in PAIRS.values() for v in pair)))
START=dt.datetime(2025,9,29,tzinfo=dt.timezone.utc)
END=dt.datetime(2026,6,1,tzinfo=dt.timezone.utc)
COST_BPS=(2,5,10,20)

# All selection inputs are t and t-4h completed H1 closes. A 2h decision cadence
# with 1h modeled holding avoids overlapping inventory across decisions. This
# hypothetical schedule targets 5/day, not 21 broker fills.
ALLOWED_HOURS=(7,9,11,13,15)
LOOKBACK_HOURS=4
ENTRY_AFTER_HOURS=1/12   # first source M5 open after completed H1 end (5 min)
EXIT_AFTER_HOURS=1       # first source M5 open at following H1 end

M=np.zeros((len(ROSTER),len(CURRENCIES)))
for i,k in enumerate(ROSTER):
 a,b=PAIRS[k];M[i,CURRENCIES.index(a)]=1.;M[i,CURRENCIES.index(b)]=-1.
# Least-squares cross-market graph factor, gauge fixed by minimum-norm zero sum.
PINV=np.linalg.pinv(M)

def utc(s): return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def iso(t): return t.strftime('%G-W%V')

def frozen_selftest():
 assert len(ROSTER)==7 and len(CURRENCIES)==5
 assert set(ROSTER)=={'AUDJPY','CHFJPY','EURAUD','EURCHF','EURGBP','EURJPY','GBPJPY'}
 assert M.shape==(7,5) and np.allclose(M.sum(axis=1),0)
 latent=np.array([-.001,-.0005,.0004,.0001,.001])
 assert np.max(np.abs(M@PINV@(M@latent)-M@latent)) < 1e-12
 assert START.strftime('%G-W%V')=='2025-W40'
 assert END.strftime('%G-W%V')=='2026-W23'
 assert ALLOWED_HOURS==(7,9,11,13,15) and LOOKBACK_HOURS==4
 return True

def evaluate():
 frozen_selftest()
 raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 tape=json.loads(raw)
 assert set(ROSTER).issubset(tape['symbols']) and set(tape['symbols'])==set(ROSTER)|{'NZDUSD'}
 # NZDUSD has no independent shared-currency cross-edges in the eight-symbol
 # frozen source, so assigning its latent factor would be unidentifiable.
 bars={s:{} for s in ROSTER}
 for x in tape['bars']:
  if x['symbol'] not in bars: continue
  end=utc(x['end']);avail=utc(x['available'])
  assert end.tzinfo is not None and avail>=end and avail<end+dt.timedelta(hours=1)
  assert end not in bars[x['symbol']]
  bars[x['symbol']][end]=(float(x['close']),avail)
 outcomes=tape['outcome_lookup_PRIVATE_NOT_NATIVE_INPUT']
 rows=[];admission=collections.Counter()
 # Every eligible clock is evaluated without future outcome selection or
 # retrospective symbol pruning. Missing future opens remain censored.
 t=START
 while t<END:
  if t.weekday()>=5 or t.hour not in ALLOWED_HOURS:
   t+=dt.timedelta(hours=1);continue
  old=t-dt.timedelta(hours=LOOKBACK_HOURS)
  if not all(t in bars[s] and old in bars[s] for s in ROSTER):
   admission['MISSING_CONCURRENT_GRAPH_ENDPOINT']+=1
   t+=dt.timedelta(hours=1);continue
  if not all(bars[s][t][1]<=t+dt.timedelta(minutes=5) for s in ROSTER):
   admission['SOURCE_NOT_AVAILABLE_BY_ENTRY']+=1
   t+=dt.timedelta(hours=1);continue
  ret=np.array([math.log(bars[s][t][0]/bars[s][old][0]) for s in ROSTER])
  # Fixed currency-flow estimate from seven paired Forex moves; no target
  # series uses a price later than its own decision time.
  fx=PINV@ret
  fitted=M@fx
  choice=sorted(((-abs(fitted[i]),ROSTER[i],1 if fitted[i]>0 else -1)
   for i in range(len(ROSTER))),key=lambda x:(x[0],x[1]))[0]
  _,symbol,direction=choice
  key=symbol+'|'+t.strftime('%Y-%m-%dT%H:%M:%SZ')
  op=outcomes.get(key)
  e={'week':iso(t),'boundary':t.isoformat(),'symbol':symbol,
     'direction':direction,'observable':bool(op),
     'prior_factor_bps':abs(float(fitted[ROSTER.index(symbol)]))*10000}
  if op:
   entry=float(op['entry']);exit=float(op['exit'])
   assert entry>0 and exit>0
   e['gross_bps']=direction*10000*(exit/entry-1)
  rows.append(e)
  t+=dt.timedelta(hours=1)
 weekrows=collections.defaultdict(list)
 for row in rows:weekrows[row['week']].append(row)
 weeks=[];t=START
 while t<END:
  w=iso(t);ep=weekrows[w];complete=[r['gross_bps'] for r in ep if r['observable']]
  gross=sum(complete)
  weeks.append({'iso_week':w,'proposals':len(ep),'observable':len(complete),
                'censored':len(ep)-len(complete),'gross_bps_sum':round(gross,5),
                'hypothetical_net_bps_sum':{str(c):round(gross-c*len(complete),5) for c in COST_BPS}})
  t+=dt.timedelta(days=7)
 total=[r['gross_bps'] for r in rows if r['observable']]
 gross=sum(total)
 return {'schema':'mxm.currency-graph-flow.first-frozen-development.v1',
  'method':'currency-graph minimum-norm least squares 4h trend continuation; 1h future open-to-open, 2h cadence',
  'source_sha256':EXPECTED,'source_status':'ORIGINAL_DERIVED_DEVELOPMENT_EXPOSED_NOT_FORWARD',
  'roster':list(ROSTER),'disconnected_excluded_NZDUSD':True,
  'initial_capital_eur_funded_test':False,'broker_orders':0,'broker_fills_proven':False,
  'historical_costs_proven':False,'cloud':False,'hard21_broker_certified':False,
  'complete_iso_weeks':len(weeks),'proposals':len(rows),'observable':len(total),
  'censored':len(rows)-len(total),'gross_bps_sum':round(gross,5),
  'gross_bps_mean_per_observed':round(gross/len(total),5) if total else None,
  'weeks_21_proposals_not_fills':sum(w['proposals']>=21 for w in weeks),
  'weeks_positive_gross':sum(w['gross_bps_sum']>0 for w in weeks),
  'hypothetical_net_bps_sum':{str(c):round(gross-c*len(total),5) for c in COST_BPS},
  'weeks_positive_hypothetical_net':{str(c):sum(w['hypothetical_net_bps_sum'][str(c)]>0 for w in weeks) for c in COST_BPS},
  'predeclared_no_go':'if 5bps hypothetical net is nonpositive, close this identity; no retuning',
  'source_eligibility_exclusions':dict(admission),
  'weeks':weeks}, rows

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['selftest','evaluate']);a=ap.parse_args()
 frozen_selftest()
 if a.mode=='selftest':print('MXM_FROZEN_CURRENCY_GRAPH_SOURCE_BLIND_SELFTEST_OK')
 else:
  report,private=evaluate()
  Path('/mnt/data/MXM_CURRENCY_GRAPH_FIRST_DEVELOPMENT_PUBLIC.json').write_text(json.dumps(report,indent=2)+'\n')
  Path('/mnt/data/MXM_CURRENCY_GRAPH_FIRST_DEVELOPMENT_PRIVATE.json').write_text(json.dumps(private,separators=(',',':'))+'\n')
  for k in ('complete_iso_weeks','proposals','observable','censored','gross_bps_sum','weeks_21_proposals_not_fills','weeks_positive_gross','hypothetical_net_bps_sum','weeks_positive_hypothetical_net'):
   print(k,report[k])
