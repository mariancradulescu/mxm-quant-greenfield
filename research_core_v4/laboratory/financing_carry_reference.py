"""Independent necessary-condition screen; never a financing cash-flow calculator."""
import math
CALENDAR=('swapPeriod','swapTime','swapRollover3Days','skipSWAPPeriods','chargeSwapAtWeekends')
def reference(source):
 rows=[]
 for item in source['rows']:
  f=item['full'];reason='DATA_UNRESOLVED';sign=None
  observed=[k for k in CALENDAR if k in f]
  if not item['identity_available']:reason='IDENTITY_UNAVAILABLE'
  elif item['enabled'] is False or f.get('tradingMode') in (1,2,3) or f.get('enableShortSelling') is False or source['account_type'] in (1,2) or source['swap_free'] is True:reason='CURRENT_PAIR_UNAVAILABLE'
  elif (item['enabled'] is True and f.get('tradingMode')==0 and f.get('enableShortSelling') is True and source['account_type']==0 and source['swap_free'] is False and f.get('swapCalculationType') in (0,1,2)):
   try:
    a,b=float(f['swapLong']),float(f['swapShort'])
    if math.isfinite(a) and math.isfinite(b):
     # Comparison avoids cancellation/overflow in a+b and monetary-unit guesses.
     sign=1 if a>-b else -1 if a<-b else 0
     reason='POSITIVE_DISPLAYED_PAIR_RATE' if sign>0 else 'NONPOSITIVE_DISPLAYED_PAIR_RATE'
   except (KeyError,ValueError,TypeError,OverflowError):pass
  rows.append({'symbol_id':item['symbol_id'],'classification':reason,'pair_rate_sign':sign,'calendar_fields_present':observed})
 return {'rows':rows}
def verdict(result):
 status=[x['classification'] for x in result['rows']]
 complete=all(s in ('CURRENT_PAIR_UNAVAILABLE','NONPOSITIVE_DISPLAYED_PAIR_RATE','POSITIVE_DISPLAYED_PAIR_RATE') for s in status)
 positive='POSITIVE_DISPLAYED_PAIR_RATE' in status
 known='NONPOSITIVE_DISPLAYED_PAIR_RATE' in status or positive
 gates={'entire_universe_resolved':complete,'any_positive_displayed_pair_rate':positive,'any_pair_rate_observed':known}
 disposition='POSITIVE_CURRENT_PAIR_RATE_FULL_ECONOMICS_UNRESOLVED' if positive else 'DATA_LIMITED' if not complete else 'NO_POSITIVE_CURRENT_PAIR_RATE' if known else 'CURRENT_PAIR_UNAVAILABLE'
 return disposition,gates
