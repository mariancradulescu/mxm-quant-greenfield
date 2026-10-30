"""Read-only necessary funding diagnostic on ONE FROZEN ML selection ledger.
No alternative predictions, changes to selected opportunities, retuning, or orders.
Only QUOTE USD SPOT_CRYPTO_CFD and EXTENDED_HOURS_SHARE_CFD allow this
simplified linear minimum-ticket P&L attribution. ALL other positions are
UNRESOLVED and prevent a full system capital qualification. No real spread.
USD/EUR conversion is purely hypothetical 0.90; 2026-09-22 broker margin &
fee metadata not contemporaneous to original 2025-2026 market observations.
"""
import json,zipfile,hashlib,pathlib,collections,datetime as dt
import numpy as np,pandas as pd
from decimal import Decimal as D
from pathlib import Path
A=Path('/mnt/data/files/MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip')
B=Path('/mnt/data/files/MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip')
BROKER=Path('/mnt/data/files/MXM_COMPETITION_BROKER_UNIVERSE_V2.zip')
LEDGER=Path('/mnt/data/MXM_ANNUAL145_GLOBAL_ML_FIRST_PRIVATE_20261030.json')
USD_EUR=D('.90'); FRICTION_BPS=(10,20,40,80)
PRICESHA='9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77'

def main():
 with BROKER.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==PRICESHA
 with zipfile.ZipFile(BROKER) as z: broker=json.loads(z.read(next(x for x in z.namelist() if x.endswith('.json'))))
 terms={x['broker_symbol']:x for x in broker['symbols']}
 ledger=json.loads(LEDGER.read_text())
 names=set(p['symbol'] for p in ledger)
 source={}
 for path in (B,A):
  with zipfile.ZipFile(path) as z:
   manifest=json.loads(z.read('SELECTED_IDENTITY_MANIFEST.json'))
   symbol_ids={str(s['symbol_id']):s['broker_symbol'] for s in manifest['symbols']}
   for csv in z.namelist():
    if not(csv.startswith('raw/') and csv.endswith('M5.csv')):continue
    key=csv.split('/')[-1].split('_')[0];name=symbol_ids.get(key)
    if name not in names or name in source:continue
    df=pd.read_csv(z.open(csv),usecols=['time_utc','open'])
    times=pd.to_datetime(df.time_utc,utc=True)
    source[name]=dict(zip(times.astype('int64').to_numpy(),df.open.to_numpy()))
 if source.keys()!=names:raise RuntimeError('ORIGINAL_INSTRUMENT_NOT_FOUND')
 evidence=[]
 for trade in ledger:
  symbol=trade['symbol'];meta=terms[symbol];t=pd.Timestamp(trade['t']).value
  entry=source[symbol].get(t+5*60*10**9);exit=source[symbol].get(t+60*60*10**9)
  if not(entry is not None and exit is not None):raise RuntimeError('MISSING_EXACT_ENTRY_OR_EXIT')
  direction=1 if trade['prediction_bps']>0 else -1
  bps=1e4*(exit/entry-1)*direction
  if abs(bps-trade['signed_gross_bps'])>1e-7:raise RuntimeError('PRIVATE_LEDGER_PRICE_OUTCOME_MISMATCH')
  kind=meta.get('product_type');asset=meta.get('quote_asset');minvol=D(str(meta['min_volume_cents']))/100
  broker_margin=meta['expected_margin_at_min_volume']
  margin=broker_margin['buy_margin_eur'] if direction==1 else broker_margin['sell_margin_eur']
  is_simple=kind in ('SPOT_CRYPTO_CFD','EXTENDED_HOURS_SHARE_CFD') and asset=='USD'
  row=dict(t=trade['t'],symbol=symbol,product=kind,quote=asset,source_signed_gross_bps=round(bps,6),volume_cents=int(meta['min_volume_cents']),
           captured_min_margin_eur=margin,current_broker_minimum_direction_feasible=meta['buy_eligible_current' if direction==1 else 'sell_eligible_current'],
           price_enter=float(entry),price_exit=float(exit),
           linear_usd_cash_proxy_applicable=is_simple)
  if is_simple:
    notional=minvol*D(str(entry))*USD_EUR
    gross=notional*D(str(bps))/10000
    rate=D(str(meta['precise_trading_commission_rate']))/D(10**8)
    minimum=D(str(meta['precise_min_commission']))/D(10**8)
    # Zero `commission` is NOT zero spread. Fee for USD-per-lot type2.
    if meta['commission_type']!=2:raise RuntimeError('UNKNOWN_FEE_TYPE_FOR_CASH_PROXY')
    per_side=max(minimum, D(str(meta['min_volume_cents']))*rate/D(str(meta['lot_size'])))
    declared_2side_eur=per_side*2*USD_EUR
    row.update(notional_eur_proxy=float(notional),gross_eur_proxy=float(gross),
        declared_commission_eur_proxy=float(declared_2side_eur),
        cost_stress_net_eur_proxy={str(c):float(gross-declared_2side_eur-notional*D(c)/10000) for c in FRICTION_BPS})
  evidence.append(row)
 cash={}
 for scenario in FRICTION_BPS:
  equity=200.;curve=[];accepted=0;necessary_admission_reject=0;unresolved=0
  for x in evidence:
   if not x['linear_usd_cash_proxy_applicable']:
    unresolved+=1;continue
   if x['captured_min_margin_eur']+max(0,x['declared_commission_eur_proxy'])>=equity or not x['current_broker_minimum_direction_feasible']:
    necessary_admission_reject+=1;continue
   pnl=x['cost_stress_net_eur_proxy'][str(scenario)];equity+=pnl;curve.append(equity);accepted+=1
  peak=200;dd=0
  for v in curve:
   peak=max(peak,v);dd=max(dd,peak-v)
  cash[str(scenario)]={'end_equity_eur_proxy':round(equity,4),'pnl_eur_proxy':round(equity-200,4),
     'max_cash_drawdown_eur_proxy':round(dd,4),'attended_linear_usd_min_ticket_episodes':accepted,
     'rejected_necessary_current_snapshot_margin':necessary_admission_reject,'all_nonusd_or_non_linear_unresolved':unresolved}
 aggregated={
  'schema':'mxm.annual145.one-frozen-ml-min-ticket-necessary-cash-proxy.v1',
  'source_broker_snapshot_sha256':PRICESHA,
  'not_full_system_certification':True,'captured_broker_terms_at_2026_09_22_not_historical':True,
  'single_initial_capital_eur':200,'additional_deposits':0,'new_predictions_or_reselection':0,
  'original_frozen_ml_proposals':len(ledger),'all_original_price_level_outcomes_reconciled':len(evidence),
  'linear_usd_crypto_share_cfd_episodes':sum(x['linear_usd_cash_proxy_applicable'] for x in evidence),
  'unresolved_non_linear_or_currency_episodes':sum(not x['linear_usd_cash_proxy_applicable'] for x in evidence),
  'no_broker_bidask_spread_slippage_funding_or_real_commission_certification':True,
  'modeled_roundtrip_friction_bps_in_addition_to_declared_fee':list(FRICTION_BPS),
  'assumed_eur_per_usd':str(USD_EUR),'linear_min_volume_eur_cash_proxy_scenarios':cash,
  'notional_eur_proxy_median':round(float(np.median([x['notional_eur_proxy'] for x in evidence if x['linear_usd_cash_proxy_applicable']])),5),
  'known_margin_eur_median':round(float(np.median([x['captured_min_margin_eur'] for x in evidence])),5),
  'positive_predictive_edge_proven':False,'hard21_broker_fills':0,'cloud_activated':False,'orders':0,
  'decision':'DIAGNOSTIC_ONLY_NO_PROMOTION_PRICE_ONLY_SNAPSHOT_NONCERTIFYING'}
 Path('/mnt/data/MXM_ANNUAL145_ML_MINIMUM_TICKET_PUBLIC_20261030.json').write_text(json.dumps(aggregated,indent=2,sort_keys=True)+'\n')
 Path('/mnt/data/MXM_ANNUAL145_ML_MINIMUM_TICKET_PRIVATE_20261030.json').write_text(json.dumps(evidence))
 print(json.dumps(aggregated,indent=2,sort_keys=True))
if __name__=='__main__':main()
