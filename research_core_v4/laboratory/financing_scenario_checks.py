"""Independent Decimal check of supplied artificial financing cashflows.

This verifies accounting, never historical swap rates, calendar coverage or edge.
"""
from datetime import datetime
from decimal import Decimal as D, localcontext
import json
from pathlib import Path

SCENARIO = 'b' * 64

def need(ok, why):
    if not ok:
        raise ValueError('FINANCING_SCENARIO_' + why)

def money(x):
    return D(str(x))

def utc(x):
    t = datetime.fromisoformat(x.replace('Z', '+00:00'))
    need(t.utcoffset() is not None and t.utcoffset().total_seconds() == 0, 'UTC')
    return t

def verify(p):
    with localcontext() as ctx:
        ctx.prec = 65
        return _verify(p)

def _verify(p):
    need(p['schema'] == 'mxm.financing-scenario.artificial.v1' and p['checks'] >= 90, 'COMPILED_FIXTURE')
    need(p['financing_is_explicit_eur_scenario_only'] is True and
         p['historical_financing_proven'] is False and p['broker_orders'] == 0 and
         all(p[k] is False for k in ('native_ctrader_runtime_reception', 'economic_edge_proven', 'hard21_proven')), 'NO_PROMOTION')
    need(len(p['cases']) == 2 and {c['direction'] for c in p['cases']} == {-1, 1}, 'LONG_SHORT')
    for c in p['cases']:
        need(c['scenario_sha256'] == SCENARIO and c['cold_processes'] == 3 and
             c['every_event_cut_checked'] is True and c['next_week_booked'] is True, 'RECOVERY_CASE')
        report = c['report']; ledger = report['Ledger']
        need(len(ledger) == 4 and ledger[0]['Kind'] == 'ENTRY' and
             [r['Kind'] for r in ledger[1:]] == ['FINANCING'] * 3, 'LEDGER_SHAPE')
        entry = ledger[0]; cash = D(200) - money(entry['CommissionEur'])
        need(cash == D('199.9') == money(entry['CashEur']) and money(entry['GrossEur']) == 0 and
             entry['Direction'] == c['direction'] and entry['Symbol'] == 'GBPUSD' and
             money(entry['Units']) == 1000 and 'Financing' not in entry, 'SINGLE_INITIAL_FUNDING')
        through = utc(entry['Utc'])
        expected_amounts = [D('-1.25'), D('.40'), D('-.10')]
        need([money(x) for x in c['financing_amounts_eur']] == expected_amounts, 'FIXED_ARITHMETIC_INPUTS')
        for row, amount in zip(ledger[1:], expected_amounts):
            f = row['Financing']
            need(row['Symbol'] == f['Symbol'] == entry['Symbol'] and
                 row['Direction'] == f['Direction'] == entry['Direction'] and
                 money(row['Units']) == money(f['Units']) == money(entry['Units']) and
                 f['PositionEntryUtc'] == entry['Utc'] and f['Utc'] == row['Utc'] and
                 f['ScenarioSha256'] == SCENARIO, 'BOOKING_POSITION_BINDING')
            need(through <= utc(f['AccrualStartUtc']) < utc(f['AccrualEndUtc']) <= utc(f['Utc']), 'ACCRUAL_CLOCK')
            through = utc(f['AccrualEndUtc'])
            need(money(f['AmountEur']) == money(row['GrossEur']) == amount and
                 money(row['Price']) == money(row['CommissionEur']) == 0 and
                 row['Reason'] == 'EXPLICIT_EUR_FINANCING_SCENARIO', 'SIGNED_EUR_BOOKING')
            cash += amount
            need(money(row['CashEur']) == cash, 'EVERY_CASH_STEP')
        last = utc(ledger[-1]['Utc']); first = utc(entry['Utc'])
        need(last.isocalendar()[:2] != first.isocalendar()[:2], 'ACTUAL_ISO_WEEK_CROSSING')
        week = f'{first.isocalendar().year}-W{first.isocalendar().week:02}'
        need(report['EntriesByIsoWeek'] == {week: 1} and report['AcceptedEntries'] == c['accepted_entries'] == 1 and
             report['ExecutedExits'] == c['executed_exits'] == 0 and report['OpenPositions'] == 1, 'NO_PHANTOM_EXECUTIONS')
        mark = money(c['mark_bid'] if c['direction'] > 0 else c['mark_ask'])
        pnl = (mark - money(entry['Price'])) * money(entry['Units']) * c['direction']
        need(cash == money(c['cash_eur']) == money(report['FinalCashEur']) == D('198.95') and
             money(report['InitialCapitalEur']) == 200 and money(report['UsedMarginEur']) == 50 and
             money(report['MarkedEquityEur']) == money(c['after_equity_eur']) == cash + pnl and
             money(report['FreeMarginEur']) == money(c['after_free_margin_eur']) == cash + pnl - 50,
             'INDEPENDENT_CASH_MTM_MARGIN')
        need(money(c['before_equity_eur']) + sum(expected_amounts) == money(c['after_equity_eur']) and
             money(c['before_free_margin_eur']) + sum(expected_amounts) == money(c['after_free_margin_eur']), 'NO_RESET_OR_DOUBLE_CHARGE')
        need(report['Hard21Proven'] is False and report['BrokerFillsProven'] is False and
             report['CostsBrokerVerified'] is False and report['CompleteIsoUtcWeeks'] == 0, 'NO_HISTORICAL_CERTIFICATION')
    shared = p['shared_fx_cases']
    need(len(shared) == 2 and {c['direction'] for c in shared} == {-1, 1}, 'SHARED_FX_CASES')
    for c in shared:
        need([money(x) for x in c['amounts_eur']] == [D('-1.25'), D('.40')] and
             money(c['before_cash_eur']) == D('199.9') and money(c['after_cash_eur']) == D('199.05') and
             abs(money(c['after_equity_eur']) - (money(c['before_equity_eur']) - D('.85'))) < D('1e-24') and
             money(c['fx_bid']) == D('1.10') and money(c['fx_ask']) == D('1.11') and
             c['entries'] == 1 and c['exits'] == 0, 'EUR_CASH_NOT_CONVERTED_TWICE')
    return {'schema': 'mxm.financing-scenario.independent-check.v1', 'compiled_checks': p['checks'],
            'artificial_cash_paths': 2, 'shared_fx_paths': 2, 'cold_os_processes': 6,
            'every_financing_cash_step_checked': True, 'broker_orders': 0,
            'historical_financing_proven': False, 'economic_edge_proven': False,
            'hard21_proven': False, 'native_ctrader_runtime_reception': False}

def negatives(p):
    from copy import deepcopy
    mutations = [
        lambda x: x['cases'][0]['report'].__setitem__('FinalCashEur', D(200)),
        lambda x: x['cases'][0]['report']['Ledger'][1]['Financing'].__setitem__('AmountEur', D(1)),
        lambda x: x['cases'][0]['report']['Ledger'].__delitem__(1),
        lambda x: x['cases'][0]['report']['Ledger'][2]['Financing'].__setitem__('AccrualStartUtc', x['cases'][0]['report']['Ledger'][0]['Utc']),
        lambda x: x['cases'][0]['report']['Ledger'][1]['Financing'].__setitem__('PositionEntryUtc', '2026-09-01T00:00:00Z'),
        lambda x: x['cases'][0]['report'].__setitem__('AcceptedEntries', 4),
        lambda x: x['cases'][0]['report'].__setitem__('CostsBrokerVerified', True),
        lambda x: x['shared_fx_cases'][0].__setitem__('after_equity_eur', money(x['shared_fx_cases'][0]['before_equity_eur']) - D('.85') / D('1.1')),
        lambda x: x.__setitem__('historical_financing_proven', True),
    ]
    for i, mutation in enumerate(mutations):
        altered = deepcopy(p); mutation(altered)
        try:
            verify(altered)
        except ValueError:
            continue
        raise ValueError('FINANCING_SCENARIO_TAMPER_ACCEPTED_' + str(i))
    return len(mutations)

def original(folder=None):
    import base64, hashlib, io, zipfile
    root = Path(__file__).resolve().parents[2]
    folder = Path(folder) if folder is not None else root / 'docs/economic-development/20261026/financing-account-40275418143'
    sha = lambda b: hashlib.sha256(b).hexdigest()
    manifest = (folder / 'MANIFEST.json').read_bytes()
    need(sha(manifest) == '035a4672b3ed84779ed77f2e8120f1db8d347cbf3a72c0e6881f7543d71cb1da', 'ORIGINAL_MANIFEST')
    m = json.loads(manifest); encoded = (folder / 'artifact.zip.b64').read_bytes()
    need(len(encoded) < 4096, 'ORIGINAL_ARCHIVE_BOUND')
    archive = base64.b64decode(encoded.strip(), validate=True)
    need(len(archive) == m['archive_bytes'] == 1458 and sha(archive) == m['archive_sha256'], 'ORIGINAL_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        need(z.namelist() == ['proof.json'] and z.infolist()[0].file_size == 7923, 'ORIGINAL_MEMBERS')
        raw = z.read('proof.json')
    need(len(raw) == m['proof_bytes'] and sha(raw) == m['proof_sha256'] and
         (folder / 'proof.json').read_bytes() == raw, 'ORIGINAL_PROOF')
    need(m['run_id'] == 40275418143 and m['job_id'] == 121417029454 and m['artifact_id'] == 12630066771 and
         m['source_head'] == 'd62bed7a6212f05de784f5c8c54fb62afd5e7096' and
         m['test_merge'] == '66f048309efe2fdad501ed484f808596b6052d69', 'ORIGINAL_NATIVE_PROVENANCE')
    p = json.loads(raw, parse_float=D); result = verify(p['financing'])
    from .shared_usd_account_checks import verify as shared_verify
    shared_verify(p)
    changed = [p for p, h in m['implementation_sha256'].items() if not (root / p).is_file() or sha((root / p).read_bytes()) != h]
    result.update(original_archive_verified=True, source_run=m['run_id'],
                  current_compiled_sources_match_original=not changed, changed_implementation_paths=changed)
    return result

if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--original']:
        result = original()
    else:
        p = json.loads(Path(sys.argv[1]).read_bytes(), parse_float=D)
        result = verify(p['financing'])
        result['independent_tamper_negatives'] = negatives(p['financing'])
    print(json.dumps(result, sort_keys=True))
