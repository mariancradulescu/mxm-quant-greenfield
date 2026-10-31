"""No-signal authenticated original 1576-M5-identity x broker EUR200
minimum ticket two-sided COMMISSION declaration scenario; not a fee charge,
not time-aligned EUR FX, not PnL/forecast/negative model rerun.
"""
import collections, hashlib, json, pathlib, zipfile
from decimal import Decimal
DIR=pathlib.Path('/mnt/data/files');OUT=pathlib.Path('/mnt/data')
SOURCE_SHA='9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77'
USD_EUR_SCENARIO=Decimal('.90')
BROKER=DIR/'MXM_COMPETITION_BROKER_UNIVERSE_V2.zip'
QUALITY=DIR/'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip'

def run():
    if hashlib.sha256(BROKER.read_bytes()).hexdigest()!=SOURCE_SHA:raise ValueError('BROKER_HASH')
    with zipfile.ZipFile(BROKER) as z:
        names=[n for n in z.namelist() if n.endswith('/BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json')]
        if len(names)!=1:raise ValueError('BROKER_MEMBER')
        broker=json.loads(z.read(names[0]))
    if broker['account_currency']!='EUR' or broker['starting_capital_eur']!=200 or len(broker['symbols'])!=5324 or broker['orders_placed']:raise ValueError('BROKER_SCOPE')
    byid={int(x['symbol_id']):x for x in broker['symbols']}
    with zipfile.ZipFile(QUALITY) as z:
        qr=z.read('DATA_QUALITY_TABLE.json');q=json.loads(qr)
    if q['frontier_count']!=1576 or len(q['rows'])!=1576:raise ValueError('QUALITY_SCOPE')
    class_counts=collections.defaultdict(collections.Counter)
    totals=collections.Counter()
    fee_levels=[]
    source_ids=set()
    for quality in q['rows']:
        sid=int(quality['symbol_id'])
        if sid in source_ids:raise ValueError('DUP_SOURCE_ID')
        source_ids.add(sid)
        b=byid[sid]
        if quality['symbol']!=b['broker_symbol'] or quality['asset_class']!=b['asset_class']:
            raise ValueError('AUTHENTIC_SYMBOL_ID_NAME_CLASS_JOIN')
        cls=b['asset_class'];d=class_counts[cls]
        d['identity_matched']+=1;totals['matched']+=1
        m=b['expected_margin_at_min_volume']
        if not(b['buy_eligible_current'] and b['sell_eligible_current'] and
               0<Decimal(str(m['buy_margin_eur']))<=200 and 0<Decimal(str(m['sell_margin_eur']))<=200):continue
        d['both_200_eur_margin_necessary']+=1;totals['both_200_eur_margin_necessary']+=1
        if max(Decimal(str(m['buy_margin_eur'])),Decimal(str(m['sell_margin_eur'])))>80:continue
        d['both_director_80_eur_margin_necessary']+=1;totals['both_80']+=1
        if not(b['quote_asset']=='USD' and b['commission_type']==2 and b['min_commission_asset']=='USD' and b['min_commission_type']==1):continue
        volume=Decimal(str(b['min_volume_cents']));lot=Decimal(str(b['lot_size']))
        if volume<=0 or lot<=0 or Decimal(str(m['volume_cents']))!=volume:raise ValueError('BAD_VOLUMES')
        # Already broker-declared minimum cost per side in USD at min volume.
        rate=Decimal(str(b['precise_trading_commission_rate']))/Decimal(10)**8
        min_fee=Decimal(str(b['precise_min_commission']))/Decimal(10)**8
        if rate<0 or min_fee<0:raise ValueError('BAD_FEES')
        fee=USD_EUR_SCENARIO*2*max(rate*volume/lot,min_fee)
        if fee<0:raise ValueError('NEGATIVE_FEE')
        fee_levels.append(fee)
        d['usd_per_lot_fee_scenario_qualifiable']+=1;totals['usd_qualifiable']+=1
        for cap,label in [(Decimal('.20'),'fee_le_old_20cent_floor'),(Decimal('2'),'fee_le_old_risk_cap')]:
            if fee<=cap:d[label]+=1;totals[label]+=1
    if totals['matched']!=1576 or totals['both_200_eur_margin_necessary']!=1575 or totals['both_80']!=1530 or totals['usd_qualifiable']!=873 or totals['fee_le_old_20cent_floor']!=873:
        raise ValueError('AUTHENTIC_AGGREGATE_REGRESSION')
    fee_levels.sort();med=fee_levels[len(fee_levels)//2]
    report={
        'schema':'mxm.1576-original-M5-identity-broker-native-declared-min-lot-fee-capacity.v1',
        'broker_original_zip_sha256':SOURCE_SHA,
        'quality_original_table_sha256':hashlib.sha256(qr).hexdigest(),
        'broker_capture_utc':broker['captured_utc'],
        'population':{'m5_quality_matched_ids':1576,'margin_both_directions_eur200_necessary_only':1575,'within_historical_director80_ticket_margin':1530,
          'usd_quoted_type2_commission_eligible_for_this_scenario':873,'NOT_priced_by_this_narrow_USD_fee_path':1530-873,
          'fee_covered_by_old_20cent_floor':totals['fee_le_old_20cent_floor']},
        'commission_scenario':{'usd_eur':str(USD_EUR_SCENARIO),'account_eur':True,'per_side_estimate':'max(native declared rate * min ticket lots, declared minimum), two sides','min_roundtrip_declared_fee_median_eur':str(med),'min_roundtrip_declared_fee_max_eur':str(max(fee_levels))},
        'by_asset_class':{k:dict(v) for k,v in sorted(class_counts.items())},
        'limitations':{'broker_usd_eur_historical_time_aligned':False,'historical_broker_quote_spread_observed':False,'future_slippage_bounded':False,'actual_broker_ledger_commission':False,'pnl_contract_payoff_verified':False,'funded_common_account_tested':False,'predictive_edge_tested':False,'negative_closed_models_rerun':False,'owner_numeric_80_120_2_mandates_immutable':False,'real_orders_placed':0,'cloud_activation':0,'HARD21_broker_proven':False},
        'decision':'Fee declaration at minimum volume often is not the bottleneck; true observed spread and total stop exposure must be evaluated, no instrument class retrospectively excluded'
    }
    dest=OUT/'MXM_1576_BROKER_DECLARED_MIN_FEE_EUR200_20261031.json'
    dest.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'file':str(dest),'population':report['population'],'fee':report['commission_scenario'],'classes':len(class_counts)},indent=2))
if __name__=='__main__':run()
