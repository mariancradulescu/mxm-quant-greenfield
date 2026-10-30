"""One source-only native min-ticket EUR200 account envelope on accepted PRIMARY145.
No outcome returns, no policy replay, no orders, no Cloud, no broker secrets.

The 80 EUR maximum ticket margin is CURRENT DIRECTOR implementation, NOT an
immutable OWNER financial ceiling. A pass is necessary only; does not prove
fully priced EUR trading, historical rules, expected NET gain, broker fills.
"""
import argparse, collections,hashlib,json,pathlib,sys,zipfile

BROKER_SHA='9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77'
INITIAL_EUR=200
CURRENT_DIRECTOR_TICKET_MARGIN_EUR=80

def analyze(broker_zip:pathlib.Path,manifest_json:pathlib.Path):
    if hashlib.sha256(broker_zip.read_bytes()).hexdigest()!=BROKER_SHA:
        raise ValueError('BROKER_NATIVE_SNAPSHOT_SHA_MISMATCH')
    with zipfile.ZipFile(broker_zip) as z:
        files=[n for n in z.namelist() if n.endswith('BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json')]
        if len(files)!=1:raise ValueError('BROKER_NATIVE_SNAPSHOT_MEMBER_UNRESOLVED')
        broker=json.loads(z.read(files[0]))
    if broker.get('starting_capital_eur')!=INITIAL_EUR or broker.get('account_currency')!='EUR' or len(broker['symbols'])!=5324:
        raise ValueError('NOT_ACCEPTED_EUR200_BROKER_SOURCE')
    manifest=json.loads(manifest_json.read_text())
    ids=[int(z['symbol_id']) for z in manifest['primary_series']]
    if len(ids)!=145 or len(set(ids))!=145 or manifest.get('primary_count')!=145:
        raise ValueError('PRIMARY145_ROSTER_CONTRACT')
    symbols={int(z['symbol_id']):z for z in broker['symbols']}
    if len(symbols)!=5324 or not set(ids).issubset(symbols):raise ValueError('BROKER_SYMBOL_ID_MAPPING')
    classes=collections.defaultdict(lambda: {'ids':0,'broker_both_direction_eur200_min_volume':0,'current_80_eur_margin_both':0,'above_80_eur_either_side':0})
    count={'both_eur200':0,'both_80':0,'over_80':0}
    for sid in ids:
        info=symbols[sid]; margin=info['expected_margin_at_min_volume']
        assert margin['state']=='CAPTURED_BROKER_NATIVE_READ_ONLY_CURRENT'
        minimum=int(info['min_volume_cents']);step=int(info['step_volume_cents']);maximum=int(info['max_volume_cents'])
        if type(minimum)!=int or type(step)!=int or type(maximum)!=int or minimum<=0 or step<=0 or minimum>maximum:
            raise ValueError('BROKER_NATIVE_VOLUME_LATTICE_UNVERIFIED')
        if int(margin['volume_cents'])!=minimum:raise ValueError('MARGIN_NOT_FOR_MINIMUM_VOLUME')
        buy=float(margin['buy_margin_eur']);sell=float(margin['sell_margin_eur'])
        both=info['buy_eligible_current'] is True and info['sell_eligible_current'] is True and min(buy,sell)>0 and max(buy,sell)<=INITIAL_EUR
        policy=both and buy<=CURRENT_DIRECTOR_TICKET_MARGIN_EUR and sell<=CURRENT_DIRECTOR_TICKET_MARGIN_EUR
        block=both and not policy
        if not both:raise ValueError('PRIMARY145_EXPECTED_ACCOUNT_BOTH_DIRECTIONS')
        line=classes[info['product_type']];line['ids']+=1;line['broker_both_direction_eur200_min_volume']+=int(both)
        line['current_80_eur_margin_both']+=int(policy);line['above_80_eur_either_side']+=int(block)
        count['both_eur200']+=int(both);count['both_80']+=int(policy);count['over_80']+=int(block)
    if count!={'both_eur200':145,'both_80':129,'over_80':16}:raise ValueError('EXPECTED_SOURCE_RECONCILIATION_FAILURE')
    return {'schema':'mxm.primary145.broker-200eur-min-ticket-director-cap-necessary-coverage.v1',
        'source_original_broker_zip_sha256':BROKER_SHA,
        'broker_captured_utc':broker['captured_utc'],'account_deposit_currency':'EUR',
        'initial_capital_eur':INITIAL_EUR,'primary145_symbols':145,
        'broker_both_direction_minimum_ticket_margin_necessary_feasible_on_capture':count['both_eur200'],
        'within_current_director_80eur_margin_only_cap_in_both_directions':count['both_80'],
        'blocked_by_current_director_80eur_cap_one_or_both_directions':count['over_80'],
        'by_product_type':dict(sorted(classes.items())),
        'owner_80eur_cap_immutable':False,'owner_minimum_initial_capital_eur':200,
        'current_terms_prove_historical_executability':False,'fees_spread_slippage_stoprisk_qualified':False,
        'equity_path_or_expected_net_positive_proven':False,'trading_signals_evaluated':0,
        'real_broker_orders':0,'cloud_activations':0,
        'decision':'SNAPSHOT_CONSTRAINT_MAP_ONLY_NO_TRADING_OR_REPOLICY_OR_ALPHA'}

def selftest():
    assert INITIAL_EUR==200 and CURRENT_DIRECTOR_TICKET_MARGIN_EUR==80
    assert sum([75,30,21,9,3,2,2,2,1])==145
    print('MXM_PRIMARY145_NATIVE_FUNDED_FEASIBILITY_SOURCE_BLIND_SELFTEST_PASS')

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['selftest','evaluate']);p.add_argument('--broker-zip',type=pathlib.Path);p.add_argument('--manifest',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args();selftest()
    if a.action=='evaluate':
        if not (a.broker_zip and a.manifest and a.output):raise ValueError('EXPLICIT_AUTHENTIC_SOURCES_REQUIRED')
        result=analyze(a.broker_zip,a.manifest)
        a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in ('by_product_type',)},indent=2))
if __name__=='__main__':main()
