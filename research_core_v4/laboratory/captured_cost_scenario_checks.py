"""No-secret artificial source for actual C# execution + independent money checks."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
from .csharp_native_portfolio_independent_mark import independent_terminal_mark, MarkParityError, captured_fee_reference


def prepare(root):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    terms = dict(schema='mxm.captured-native-symbol-terms.v1', symbol_id=1,
        classification='ARTIFICIAL_CAPTURED_TERMS_FIXTURE_ONLY',
        historical_commission_proven=False, dated_historical_volume_rules_proven=False,
        raw_optional_fields=dict(minVolume=100000, maxVolume=100000000, stepVolume=100000,
            lotSize=10000000, commissionType=1, preciseTradingCommissionRate=3000000000,
            preciseMinCommission=1000000, minCommissionType=1, minCommissionAsset='USD'))
    (root/'terms.json').write_text(json.dumps(terms))
    start = int(datetime(2026,8,24,12,tzinfo=timezone.utc).timestamp()*1000)
    with (root/'quotes.ndjson').open('w') as out:
        for i in range(30):
            bid = 110000+i*20 if i<10 else 110180-(i-9)*30 if i<20 else 109880+(i-19)*25
            for offset in (0,1000):
                for side, price in (('bid',bid),('ask',bid+10)):
                    out.write(json.dumps(dict(t=start+i*300000+(i%3)*113+offset,side=side,raw=price))+'\n')


def verify(root):
    root = Path(root)
    report = json.loads((root/'out/portfolio-exposed-quote-readback.json').read_text(),parse_float=D)
    assert report['classification']=='ARTIFICIAL_QUOTE_STREAM_ONLY'
    assert report['valuation_mode']=='CAPTURED_COMMISSION_AND_QUOTE_SIDE_FX_COMPONENTS_ONLY'
    original = independent_terminal_mark(root/'quotes.ndjson',report,root/'terms.json')
    assert original['captured_commission_component_checked'] and original['quote_side_fx_conversion_checked']
    assert original['ledger_entry_count']>=2 and original['ledger_exit_count']>=1
    assert not original['all_cost_components_verified'] and not original['hard21']
    fee_reference = captured_fee_reference(root/'terms.json',report)
    assert fee_reference(D(1000),D('1.10'),D('1.10'),D('1.11'))==D('.03')
    for field,delta,label in [('commission_eur',D('.1'),'FEE_DRIFT'),
                               ('gross_eur',D(1),'GROSS_PNL_DRIFT')]:
        changed = deepcopy(report)
        trade = next(e for e in changed['account']['ledger'] if e['kind']=='EXIT')
        trade[field]+=delta
        try: independent_terminal_mark(root/'quotes.ndjson',changed,root/'terms.json')
        except MarkParityError as e: assert label in str(e),str(e)
        else: raise AssertionError('altered '+field+' accepted')
    changed=deepcopy(report); changed['account']['marked_equity_eur']+=D(1)
    try: independent_terminal_mark(root/'quotes.ndjson',changed,root/'terms.json')
    except MarkParityError as e: assert 'TERMINAL_LIQUIDATION_MTM' in str(e)
    else: raise AssertionError('altered terminal FX accepted')
    changed=deepcopy(report); changed['captured_terms_sha256']='0'*64
    try: independent_terminal_mark(root/'quotes.ndjson',changed,root/'terms.json')
    except MarkParityError as e: assert 'CAPTURED_TERMS_HASH' in str(e)
    else: raise AssertionError('changed snapshot hash accepted')
    # Absent optional fee cannot be interpreted as zero, even with a rehashed
    # artificial fixture. Production separately binds its digest to custody.
    terms=json.loads((root/'terms.json').read_text())
    terms['raw_optional_fields']['commissionType']=None
    altered=root/'missing-type.json';altered.write_text(json.dumps(terms))
    from hashlib import sha256
    changed=deepcopy(report);changed['captured_terms_sha256']=sha256(altered.read_bytes()).hexdigest()
    try: independent_terminal_mark(root/'quotes.ndjson',changed,altered)
    except MarkParityError as e: assert 'CAPTURED_OPTIONAL_MISSING_commissionType' in str(e)
    else: raise AssertionError('absent optional commission accepted as default')
    print('MXM_ACTUAL_CSHARP_CAPTURED_COMPONENT_FEES_SIGNED_FX_INDEPENDENT_DECIMAL_AND_MUTATIONS_PASS_ARTIFICIAL_ONLY')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','verify'));p.add_argument('root')
    args=p.parse_args()
    (prepare if args.mode=='prepare' else verify)(args.root)
