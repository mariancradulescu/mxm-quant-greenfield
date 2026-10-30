"""Cold economic attribution of ONE completed, authenticated EUR200 programme.

This module NEVER loads market sources, evaluates policies, replays the account,
or sends broker requests. The raw original can only be unsealed by the existing
OWNER custody key in the protected GitHub Actions environment. All ex-post
midpoint comparisons are diagnostic reference scenarios, not new backtests.
"""
from __future__ import annotations
import collections
from decimal import Decimal, getcontext
import gzip
import hashlib
import json
from pathlib import Path
import tempfile

getcontext().prec = 34
EXPECTED_RUN = 41005510200
EXPECTED_HEAD = '7fc1926d6a9e9ed8d1e85bb87d337fecd3309721'
EXPECTED_CIPHER = '814ba2b451ef43b4c5e4cedced455bd94c07e7e93edce7645ecb512f734d2ed7'
EXPECTED_ARTIFACT_DIGEST = '912a2085b350ba520f6ed8059939b0e5b4fda02c9e33bb2699f8cec7a9fdf340'
ZERO = Decimal(0)
TOLERANCE = Decimal('0.0000001')


def need(condition, code):
    if not condition:
        raise ValueError('MXM_FORENSIC_' + code)


def num(value):
    result = Decimal(str(value))
    need(result.is_finite(), 'NONFINITE_NUMERIC')
    return result


def currency_conv(quote, amount):
    return amount * num(quote['QuoteToEur'] if amount >= 0 else quote.get('QuoteLossToEur') or quote['QuoteToEur'])


def week(utc):
    from datetime import datetime
    moment = datetime.fromisoformat(utc.replace('Z', '+00:00'))
    need(moment.utcoffset().total_seconds() == 0, 'NON_UTC_TRADE')
    return '%04d-W%02d' % moment.isocalendar()[:2]


def analyze(original, receipt):
    """Exact C# ledger cash attribution plus explicitly labeled ex-post mid reference."""
    need(receipt['schema'] == 'mxm.integrated-portfolio-first-result.v1' and
         receipt['run_id'] == EXPECTED_RUN and receipt['head'] == EXPECTED_HEAD and
         receipt['private_cipher_sha256'] == EXPECTED_CIPHER and
         receipt['economic_outcomes'] == 1 and receipt['orders'] == 0 and
         receipt['cloud'] is False, 'PINNED_AUTHORITY')
    need(original['run_id'] == EXPECTED_RUN and original['head'] == EXPECTED_HEAD and
         original['economic_outcomes'] == 1 and original['metrics']['initial_eur'] == 200,
         'ORIGINAL_IDENTITY')
    need(original['metrics']['classification'] == 'NET_FAIL_FUNDED_PORTFOLIO_SCENARIO',
         'CLOSED_NEGATIVE_IDENTITY_ONLY')
    result = original['programme_checkpoint']['progress']['results']['account']['value']
    account = result['account']
    feed = original['feed']
    need(feed['schema'] == 'mxm.funded-programme-feed.v1' and
         feed['partition'] == 'DEVELOPMENT' and feed['orders'] == 0 and feed['cloud'] is False and
         feed['synthetic'] is False and result['deposit_count'] == 1 and
         result['reset_count'] == 0 and result['orders'] == 0 and
         result['economic_qualification'] is False, 'UNFUNDED_OR_UNBOUND')
    need(num(account['InitialCapitalEur']) == 200 and account['OpenPositions'] == 0 and
         account['AcceptedEntries'] == account['ExecutedExits'], 'CONTINUOUS_ACCOUNT')
    quote_by_key = {}
    for event in feed['events']:
        if event['$feed'] != 'quote':
            continue
        key = (event['Symbol'], event['Utc'])
        need(key not in quote_by_key, 'AMBIGUOUS_EXECUTION_QUOTE')
        need(num(event['Bid']) > 0 and num(event['Ask']) >= num(event['Bid']) and
             num(event['SlipPerSideQuote']) >= 0 and num(event['QuoteToEur']) > 0,
             'INVALID_QUOTE')
        quote_by_key[key] = event
    open_trade = {}
    cash = num(account['InitialCapitalEur'])
    episodes = []
    for trade in account['Ledger']:
        kind, symbol = trade['Kind'], trade['Symbol']
        direction, units, price = int(trade['Direction']), num(trade['Units']), num(trade['Price'])
        fee, gross = num(trade['CommissionEur']), num(trade['GrossEur'])
        need(kind in ('ENTRY', 'EXIT') and direction in (-1, 1) and units > 0 and
             fee >= 0, 'LEDGER_TRADE_TYPE')
        key = (symbol, trade['Utc'])
        need(key in quote_by_key, 'MISSING_ORIGINAL_EXECUTION_QUOTE')
        quote = quote_by_key[key]
        midpoint = (num(quote['Bid']) + num(quote['Ask'])) / 2
        slip = num(quote['SlipPerSideQuote'])
        expected = (num(quote['Ask']) + slip if direction > 0 else num(quote['Bid']) - slip) if kind == 'ENTRY' else (num(quote['Bid']) - slip if direction > 0 else num(quote['Ask']) + slip)
        need(abs(price - expected) <= TOLERANCE, 'LEDGER_QUOTE_FILL_DISAGREEMENT')
        need(units <= num(quote['ExecutableUnits']) and units > 0, 'UNFUNDED_VOLUME')
        cash += gross - fee
        need(abs(cash - num(trade['CashEur'])) <= TOLERANCE, 'LEDGER_CASH_MISMATCH')
        if kind == 'ENTRY':
            need(symbol not in open_trade and len(open_trade) == 0 and gross == 0,
                 'NONATOMIC_ENTRY_OR_GROSS')
            open_trade[symbol] = (trade, quote, midpoint)
        else:
            need(symbol in open_trade, 'UNMATCHED_EXIT')
            entry, entry_quote, entry_mid = open_trade.pop(symbol)
            need(entry['Direction'] == direction and num(entry['Units']) == units and
                 entry['Utc'] <= trade['Utc'], 'POSITION_LIFECYCLE')
            # Same observed scenario entry/exit times, replacing ONLY prices
            # with quote mids, NOT an actionable/tradable counterfactual.
            mid_quote_profit = (midpoint - entry_mid) * units * direction
            mid_eur = currency_conv(quote, mid_quote_profit)
            drag = mid_eur - gross
            need(drag >= -TOLERANCE, 'EXECUTION_REFERENCE_SIGN')
            total_fee = num(entry['CommissionEur']) + fee
            episode_net = gross - total_fee
            episodes.append({
                'symbol': symbol, 'direction': direction, 'entry_utc': entry['Utc'],
                'exit_utc': trade['Utc'], 'week': week(trade['Utc']),
                'entry_week': week(entry['Utc']),
                'month': entry['Utc'][:7], 'exit_reason': trade.get('Reason'),
                'units': str(units), 'gross_eur': str(gross), 'net_eur': str(episode_net),
                'commission_eur': str(total_fee), 'mid_reference_eur': str(mid_eur),
                'modeled_execution_drag_eur': str(drag),
            })
    need(not open_trade and len(episodes) == account['AcceptedEntries'] and
         abs(cash - num(account['FinalCashEur'])) <= TOLERANCE, 'UNRECONCILED_FINAL_ACCOUNT')
    def summarize(rows):
        values = lambda k: sum((num(x[k]) for x in rows), ZERO)
        gross, fees, drag, mid = (values(k) for k in ('gross_eur', 'commission_eur',
                                   'modeled_execution_drag_eur', 'mid_reference_eur'))
        net = values('net_eur')
        need(abs(gross - fees - net) <= TOLERANCE and
             abs(mid - gross - drag) <= TOLERANCE, 'DECOMPOSITION_NOT_EXACT')
        return {'round_trips': len(rows), 'gross_eur': str(gross), 'commissions_eur': str(fees),
                'modeled_execution_drag_eur': str(drag), 'ex_post_mid_reference_eur': str(mid),
                'net_eur': str(net), 'win_round_trips': sum(num(x['net_eur']) > 0 for x in rows),
                'loss_round_trips': sum(num(x['net_eur']) < 0 for x in rows)}
    total = summarize(episodes)
    need(abs(num(total['net_eur']) - num(original['metrics']['net_eur'])) <= TOLERANCE and
         abs(num(total['net_eur']) - (cash - 200)) <= TOLERANCE,
         'PUBLISHED_ECONOMIC_RESULT_DISAGREES')
    def by(field):
        groups = collections.defaultdict(list)
        for row in episodes:
            groups[row[field]].append(row)
        return {str(key) if key is not None else 'UNSPECIFIED':summarize(rows)
                for key, rows in sorted(groups.items(),key=lambda item:str(item[0]))}
    return {'schema': 'mxm.cold-portfolio-economic-attribution.v1',
            'source_run_id': EXPECTED_RUN, 'source_head': EXPECTED_HEAD,
            'classification': 'CLOSED_NEGATIVE_DEVELOPMENT_SCENARIO',
            'single_account_initial_eur': 200,
            'single_account_final_eur': str(cash),
            'gross_to_net': total,
            'by_symbol': by('symbol'), 'by_week': by('week'),
            'by_month': by('month'), 'by_exit_reason': by('exit_reason'),
            'round_trips': episodes,
            'account_max_drawdown_eur': str(account['MaxDrawdownEur']),
            'rejected_entries': account['RejectedEntries'],
            'historical_broker_fills_proven': False,
            'historical_costs_proven': False,
            'midpoint_reference_is_tradable': False,
            'new_policy_evaluations': 0, 'new_account_executions': 0,
            'original_market_sources_opened': 0, 'new_broker_requests': 0,
            'broker_orders': 0, 'cloud_activations': 0}


def run_custody():
    """Protected-only diagnostic. All raw/private material stays inside Actions."""
    import os
    need(os.getenv('GITHUB_REPOSITORY') == 'mariancradulescu/mxm-quant-greenfield' and
         os.getenv('GITHUB_REF') == 'refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.getenv('GITHUB_EVENT_NAME') == 'push' and os.getenv('GITHUB_RUN_ATTEMPT') == '1',
         'PROTECTED_RUN_SCOPE')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import unpack
    from research_core_v4.successor_c_20261018.readback import FP
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard, public_spki_sha256
    from research_core_v4.laboratory.portfolio_programme import account_checks
    root = Path(__file__).resolve().parents[2]
    src = root / 'verification/portfolio-programme-20261030'
    dst = root / 'verification/portfolio-forensics-20261030'
    receipt_bytes = (src/'receipt.json').read_bytes()
    receipt = json.loads(receipt_bytes)
    cipher = (src/'private.mxmenc').read_bytes()
    need(hashlib.sha256(cipher).hexdigest() == EXPECTED_CIPHER == receipt['private_cipher_sha256'],
         'SOURCE_CIPHER_NOT_ORIGINAL')
    cold = json.loads((src/'cold.json').read_bytes())
    need(cold['originals_verified'] is True and cold['models_rerun'] == 0 and
         cold['source_reopened'] is False and cold['orders'] == 0 and
         cold['private_cipher_sha256'] == EXPECTED_CIPHER, 'COLD_ORIGINAL_NOT_VERIFIED')
    public_key = root/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public_key) == FP, 'CUSTODY_RECIPIENT_CHANGED')
    with tempfile.TemporaryDirectory(prefix='mxm-portfolio-forensics-') as directory:
        tmp = Path(directory)
        key, fp = _private_key_from_secret(tmp)
        need(fp == FP, 'PRIVATE_KEY_IDENTITY')
        raw = unpack(owner.bounded_decrypt(cipher, key, tmp))
        need(hashlib.sha256(raw).hexdigest() == receipt['private_plain_sha256'], 'PRIVATE_BYTES_CHANGED')
        for journal in receipt['journals']:
            blob = (src/journal['path']).read_bytes()
            need(hashlib.sha256(blob).hexdigest() == journal['cipher_sha256'] and
                 hashlib.sha256(unpack(owner.bounded_decrypt(blob,key,tmp))).hexdigest() == journal['plain_sha256'],
                 'ORIGINAL_JOURNAL_CHANGED')
        original = json.loads(raw)
        result = original['programme_checkpoint']['progress']['results']['account']['value']
        need(account_checks(result) == original['metrics'], 'INDEPENDENT_LEDGER_CHALLENGE')
        analysis = analyze(original, receipt)
    dst.mkdir(parents=True, exist_ok=False)
    detail = json.dumps(analysis,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    encrypt_shard(gzip.compress(detail,mtime=0),public_key=public_key,output=dst/'diagnostic.mxmenc')
    ciphertext_sha = hashlib.sha256((dst/'diagnostic.mxmenc').read_bytes()).hexdigest()
    # Public only coarse accounting, *no* individual transactions/quotes/positions.
    public = {k:analysis[k] for k in ('schema','source_run_id','source_head','classification',
             'single_account_initial_eur','single_account_final_eur','gross_to_net',
             'account_max_drawdown_eur','historical_broker_fills_proven',
             'historical_costs_proven','new_policy_evaluations','new_account_executions',
             'original_market_sources_opened','new_broker_requests','broker_orders','cloud_activations')}
    public.update({'source_private_cipher_sha256':EXPECTED_CIPHER,
                   'encrypted_diagnostic_sha256':ciphertext_sha,
                   'forensic_method':'same logged C# trades/times; quote mid references non-tradable'})
    (dst/'public.json').write_text(json.dumps(public,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(public,sort_keys=True))


if __name__ == '__main__':
    import sys
    need(sys.argv[1:] == ['cold'], 'ONLY_COLD_COMMAND_PERMITTED')
    run_custody()
