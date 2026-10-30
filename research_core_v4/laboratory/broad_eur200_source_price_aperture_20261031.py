"""Single SOURCE-ONLY, no-signal EUR200 broker/min-ticket and genuine M5 price-scale reconciliation.

The 1,576-quality-table population, 5,324 native broker inventory and 157 actually
archived annual M5 series are DIFFERENT source populations. Never reinterpret
absolute future movement as a prediction, a fill, NET or HARD21.
"""
from __future__ import annotations
import argparse, collections, hashlib, io, json, math, pathlib, zipfile
import numpy as np
import pandas as pd

DIR = pathlib.Path('/mnt/data/files')
BROKER = DIR / 'MXM_COMPETITION_BROKER_UNIVERSE_V2.zip'
DELTA = DIR / 'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip'
SELECTED = DIR / 'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip'
BROKER_SHA = '9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77'
FX_USD_EUR = .90  # HYPOTHETICAL, not an authenticated time-stamped FX quote
COST_BPS = 10       # HYPOTHETICAL incremental spread/slippage in addition to declared per-fill fee
BASE = pathlib.Path('/mnt/data')


def need(ok, why):
    if not ok:raise ValueError('MXM_BROAD_COST_' + why)

def digest(raw):return hashlib.sha256(raw).hexdigest()

def source_blind_selftest():
    need(abs((1000.0*.001*.9) - .9)<1e-10,'UNITS_USD_EUR')
    need(abs((1000.0*10000.0/10000.0)*.9-900)<1e-10,'USD_PRICE_DELTA')
    need(int(100000)/100 ==1000,'BROKER_VOLUME_CENTS')
    need(int(300000000)/1e8 * (100000/10000000)*2*.9 == .054,'FEE_SOURCE_LOT_ROUNDTRIP')
    need(COST_BPS==10 and FX_USD_EUR==.9,'LOCKED_SCENARIO')
    return True

def read_bundle(z, expected):
    cap=json.loads(z.read('CAPTURE_MANIFEST.json'))
    payload_raw=z.read('V3_CAPTURE_PAYLOAD.json')
    need(digest(payload_raw)==cap['sha256_per_canonical_payload']['V3_CAPTURE_PAYLOAD.json'],'CAPTURE_PAYLOAD_HASH')
    payload=json.loads(payload_raw)
    need(payload['classification']=='DEVELOPMENT_ONLY' and not payload['protected_forward_opened'] and
         not payload['orders_placed'] and len(payload['series'])==expected,'SOURCE_SCOPE')
    identities=json.loads(z.read('SELECTED_IDENTITY_MANIFEST.json'))['symbols']
    need(len(identities)==expected,'SOURCE_ROSTER')
    return payload


def evaluate():
    need(digest(BROKER.read_bytes())==BROKER_SHA,'BROKER_ZIP_HASH')
    with zipfile.ZipFile(BROKER) as z:
        matches=[n for n in z.namelist() if n.endswith('/BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json')]
        need(len(matches)==1,'BROKER_MEMBER')
        broker=json.loads(z.read(matches[0]))
    need(broker['account_currency']=='EUR' and broker['starting_capital_eur']==200 and
         broker['source_environment']=='Pepperstone - Europe LIVE' and not broker['orders_placed'] and
         len(broker['symbols'])==5324,'BROKER_ACCOUNT_IDENTITY')
    broker_map={int(z['symbol_id']):z for z in broker['symbols']}
    need(len(broker_map)==5324,'UNIQUE_BROKER_SYMBOLS')
    with zipfile.ZipFile(DELTA) as z:
        quality_raw=z.read('DATA_QUALITY_TABLE.json');quality=json.loads(quality_raw)
    need(quality['frontier_count']==1576 and len(quality['rows'])==1576,'1576_QUALITY_SOURCE')
    qrows=quality['rows'];qmap={int(row['symbol_id']):row for row in qrows}
    need(len(qmap)==1576 and set(qmap)<=set(broker_map),'1576_IDENTITY_JOIN')
    qcounts=collections.Counter();classrows=collections.defaultdict(lambda: collections.Counter())
    for sid,q in qmap.items():
        b=broker_map[sid];need(q['symbol']==b['broker_symbol'] and q['asset_class']==b['asset_class'],'SOURCE_NATIVE_JOIN_NAME_CLASS')
        qcounts['all_1576']+=1
        classrows[q['asset_class']]['quality_source_ids']+=1
        if b['buy_eligible_current'] and b['sell_eligible_current']:
            qcounts['broker_both_access']+=1;classrows[q['asset_class']]['both_access']+=1
            m=b['expected_margin_at_min_volume']
            buy,sell=m['buy_margin_eur'],m['sell_margin_eur']
            need(int(m['volume_cents'])==int(b['min_volume_cents']),'MINIMUM_MARGIN_IDENTITY')
            if 0<buy<=200 and 0<sell<=200:
                qcounts['both_eur200_margin_necessary']+=1;classrows[q['asset_class']]['both_eur200_margin_necessary']+=1
                if buy<=80 and sell<=80:qcounts['both_director80_necessary']+=1;classrows[q['asset_class']]['both_director80_necessary']+=1
        if q['longest_contiguous_run']>=60:qcounts['run_60_m5']+=1;classrows[q['asset_class']]['run_60_m5']+=1
        if q['depth_anchor_count']>=1:qcounts['prior_depth_anchor']+=1
    metrics=[];archive_ids=set();arch_classes=collections.Counter();source_counts={}
    with zipfile.ZipFile(DELTA) as a, zipfile.ZipFile(SELECTED) as c:
        for label,z,sz in [('HIGH_QUALITY_DELTA_128',a,128),('SELECTED_29',c,29)]:
            p=read_bundle(z,sz)
            source_counts[label]=sz
            for record in p['series']:
                sid=int(record['symbol_id']);need(sid in qmap and sid not in archive_ids,'ARCHIVED_ID_SCOPE')
                archive_ids.add(sid)
                q=qmap[sid];b=broker_map[sid]
                name=record['file'];raw=z.read(name)
                need(digest(raw)==record['sha256'],'RAW_SOURCE_SHA256_'+str(sid))
                arch_classes[q['asset_class']]+=1
                df=pd.read_csv(io.BytesIO(raw),usecols=['time_utc','open'],dtype={'open':'float64'})
                need(len(df)==int(record['row_count']),'RAW_ROW_COUNT')
                dt=pd.to_datetime(df.time_utc,utc=True).to_numpy(dtype='datetime64[s]').astype('int64')
                prices=df.open.to_numpy();need(np.isfinite(prices).all() and (prices>0).all(),'ORIGINAL_OPEN_PRICES')
                need(len(dt)>=100 and np.all(dt[1:]>dt[:-1]),'ORIGINAL_TIMELINE_ASC')
                valid=(dt[12:]-dt[:-12]==3600) & (prices[12:]>0)
                if not valid.any():continue
                abs_delta=np.abs(prices[12:]-prices[:-12])[valid];starts=prices[:-12][valid]
                md={'asset_class':b['asset_class'],'symbol_id':sid,'observed_exact_1h_pairs':int(valid.sum()),'p90_abs_bps':float(np.quantile(abs_delta/starts*10000,.90))}
                # Exactly USD-quoted, linear *scenario* only. No nonlinear payoff/multiplier certification.
                m=b['expected_margin_at_min_volume']
                if b['quote_asset']=='USD' and b['commission_type']==2 and b['min_commission_asset']=='USD' and b['min_commission_type']==1 and b['buy_eligible_current'] and b['sell_eligible_current'] and 0<m['buy_margin_eur']<=200 and 0<m['sell_margin_eur']<=200:
                    units=int(b['min_volume_cents'])/100
                    fee_usd=max((int(b['min_volume_cents'])/int(b['lot_size']))*(int(b['precise_trading_commission_rate'])/1e8),int(b['precise_min_commission'])/1e8)
                    fee_eur=2*fee_usd*FX_USD_EUR
                    notional_eur=units*float(np.median(starts))*FX_USD_EUR
                    p90_eur=units*float(np.quantile(abs_delta,.90))*FX_USD_EUR
                    needed_eur=fee_eur+notional_eur*COST_BPS/10000
                    md.update(minimum_ticket_linear_usd_proxy=True,p90_hourly_absolute_price_potential_eur=p90_eur,fee_eur_roundtrip_declaration=fee_eur,notional_eur_reference=notional_eur,modeled_10bps_cost_eur=needed_eur,p90_abs_gross_beat_fee_plus_10bps=p90_eur>needed_eur,above_reference_0_2eur= p90_eur>needed_eur+.20)
                else:md['minimum_ticket_linear_usd_proxy']=False
                metrics.append(md)
    need(len(archive_ids)==157 and len(metrics)==157,'FULL_157_ARCHIVES')
    economy=[v for v in metrics if v['minimum_ticket_linear_usd_proxy']];rates=collections.Counter()
    for row in metrics:
        c=classrows[row['asset_class']];c['actually_archived_year_series']+=1;c['genuine_1h_pairs']+=row['observed_exact_1h_pairs']
        if row['minimum_ticket_linear_usd_proxy']:
            c['usd_linear_ticket_proxy_candidates']+=1
            c['p90_absolute_gross_exceeds_10bps_plus_fee']+=int(row['p90_abs_gross_beat_fee_plus_10bps'])
            c['p90_absolute_gross_exceeds_cost_plus_0_20eur']+=int(row['above_reference_0_2eur'])
    need(sum(v['actually_archived_year_series'] for v in classrows.values())==157,'CLASS_SUM_157')
    public={
      'schema':'mxm.1576-plus-157-annual-original-broker-cash-potential-envelope.v1',
      'source_scope':{
        'broker_original_zip_sha256':BROKER_SHA,
        'price_source_corpus':'FROZEN HIGH QUALITY DELTA 128 and SELECTED 29 original M5 archives, independent of PRIMARY145',
        'quality_table_instruments':1576,'broker_inventory_symbols':5324,
        'original_annual_price_archives':157,'original_archive_roster':source_counts,
        'time_horizon_hours':1,'bar_resolution':'M5','no_gap_interpolation':True,
        'authentic_source_raw_sha256_verified':157,
      },
      'scenario':{
        'usd_to_eur':'0.90 HYPOTHETICAL', 'one_hour_absolute_price_delta':'Original observed 12 adjacent M5 opens, 90th percentile; NOT a forecast',
        'fee':'Declared 2026-09-22 broker minimum-volume rate and minimum; BUY+SELL, USD only',
        'incremental_spread_slippage':'10bps notional ASSUMPTION in addition to declared fees',
        'payoff':'Linear units x USD price difference ASSUMPTION; actual contract payout/multiplier not independently broker-certified',
        'headroom_0_20eur':'Illustrative p90 potential > fee + 10bps friction + EUR0.20, not expected profit'
      },
      'quality_broker_join_counts':dict(qcounts),'observed_157_original_price_series':len(metrics),
      'observed_exact_one_hour_m5_pairs':sum(x['observed_exact_1h_pairs'] for x in metrics),
      'usd_linear_necessary_proxy_series':len(economy),
      'usd_linear_proxy_p90_gross_beats_declaration_plus10bps':sum(x['p90_abs_gross_beat_fee_plus_10bps'] for x in economy),
      'usd_linear_proxy_p90_gross_beats_declaration_plus10bps_plus0_20_eur':sum(x['above_reference_0_2eur'] for x in economy),
      'by_asset_class':{name:dict(c) for name,c in sorted(classrows.items())},
      'limitations':{'source_usd_eur_observed':False,'actual_historical_bid_ask':False,'actual_spread_and_slippage':False,'contract_payoff_certified':False,'fees_historical_certified':False,'predicted_direction':False,'expected_net_eur_positive':False,'continuous_200eur_account_simulated':False,'native_cloud_runtime_certified':False,'actual_broker_fills':0,'HARD21_proven':False},
      'no_new_models':True,'no_trading_actions':True,'closed_results_untouched':True,
      'decision':'SOURCE_FIRST_BROAD_MONEY_SCALE_ONLY_NOT_ALPHA_OR_PROFIT_OR_TRADABLE_ROSTER'
    }
    return public


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['selftest','evaluate']);ap.add_argument('--output',default='/mnt/data/MXM_BROAD_1576_157_ANNUAL_NATIVE_CASH_SOURCE_PUBLIC.json');args=ap.parse_args()
    source_blind_selftest()
    if args.mode=='selftest':print('MXM_BROAD_1576_SOURCE_BLIND_SELFTEST_PASS');return
    out=evaluate();pathlib.Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k in ['quality_broker_join_counts','observed_157_original_price_series','observed_exact_one_hour_m5_pairs','usd_linear_necessary_proxy_series','usd_linear_proxy_p90_gross_beats_declaration_plus10bps','usd_linear_proxy_p90_gross_beats_declaration_plus10bps_plus0_20_eur']},indent=2))
if __name__=='__main__':main()
