"""Independent full-array causal basis calculation and account cash audit."""
from decimal import Decimal as D,localcontext
import json

def reference(data):
 with localcontext() as c:
  c.prec=50;return _reference(data)
def _reference(data):
 target={int(x[0]):list(map(lambda v:D(str(v)),x[1:])) for x in data['target']};anchor={int(x[0]):list(map(lambda v:D(str(v)),x[1:])) for x in data['anchor']};fx={int(x[0]) for x in data['fx']}
 history=[];results=[]
 for t in range(data['start'],data['end'],3600000):
  if t not in target or t not in fx or t-3600000 not in target or t-3600000 not in anchor:continue
  history=[x for x in history if t-x[0]<=7*86400000];basis=target[t-3600000][3]/anchor[t-3600000][3];mean=variance=D(0);direction=0
  if len(history)==48:
   vals=[b for _,b in history];mean=sum(vals)/48;variance=sum((v-mean)**2 for v in vals)/48;delta=basis-mean
   if abs(delta*anchor[t-3600000][3])>D('.30') and delta*delta>variance:direction=-1 if delta>0 else 1
  results.append({'Time':t,'Count':len(history),'Basis':basis,'Mean':mean,'Variance':variance,'Direction':direction});history=(history+[(t,basis)])[-48:]
 return results

def reconcile(actual,data):
 expected=reference(data)
 if len(actual['decisions'])!=len(expected):raise ValueError('ANCHOR_FORECAST_COUNT')
 for a,e in zip(actual['decisions'],expected):
  for k,v in e.items():
   if isinstance(v,D):
    if abs(D(str(a[k]))-v)>D('0.000000000000000001'):raise ValueError('ANCHOR_FORECAST_'+k)
   elif a[k]!=v:raise ValueError('ANCHOR_FORECAST_'+k)
 if actual['initial_capital_eur']!=200 or actual['initial_funding_count']!=1:raise ValueError('ANCHOR_CAPITAL')
 for account in (actual['account'],actual['last_verified_prefix']):
  if account is None:continue
  cash=D(200);position=None
  for e in account['Ledger']:
   if e['Kind']=='ENTRY':
    if position is not None:raise ValueError('ANCHOR_PARALLEL_POSITION')
    position=e
   elif e['Kind']=='EXIT':
    if position is None:raise ValueError('ANCHOR_ORPHAN_EXIT')
    if e['Direction']!=position['Direction']:raise ValueError('ANCHOR_SIDE')
    position=None
   elif e['Kind']=='FINANCING':
    if position is None or D(str(e['GrossEur']))!=D('-.10'):raise ValueError('ANCHOR_FINANCING_ALLOWANCE')
   else:raise ValueError('ANCHOR_UNREGISTERED_CASHFLOW')
   cash+=D(str(e['GrossEur']))-D(str(e['CommissionEur']))
   if abs(cash-D(str(e['CashEur'])))>D('.0000001'):raise ValueError('ANCHOR_CASH')
  if abs(cash-D(str(account['FinalCashEur'])))>D('.0000001'):raise ValueError('ANCHOR_FINAL_CASH')
 return True
