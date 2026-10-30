"""One reusable C# funded-account path for bounded laboratory programmes.

This host does not invent a strategy, authenticate prices, or certify costs.
The source adapter supplies an authenticated DEVELOPMENT feed; synthetic
reception remains separately labelled. Each chunk resumes the previous account
in a NEW process, including positions, pending decisions and source cursor.
"""
import datetime as dt
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from .common import need, digest

PROJECT = Path(__file__).resolve().parent / 'csharp/shared_account/MxmSharedAccount.csproj'

def validate_feed(feed, policy_hash, synthetic):
    need(feed['schema'] == 'mxm.funded-programme-feed.v1', 'FUNDED_FEED_SCHEMA')
    need(feed['partition'] == 'DEVELOPMENT' and feed['orders'] == 0 and feed['cloud'] is False,
         'FUNDED_FEED_SCOPE')
    need(feed['synthetic'] is synthetic, 'FUNDED_SOURCE_LANE')
    need(feed['policy_sha256'] == policy_hash, 'FUNDED_POLICY_BINDING')
    need(feed['events'] and len(feed['events']) <= 1000000, 'FUNDED_EVENT_BUDGET')
    need(feed['events_sha256'] == digest(feed['events']), 'FUNDED_SOURCE_EVENTS_CHANGED')
    need(isinstance(feed['source_sha256'], str) and len(feed['source_sha256']) == 64 and
         all(c in '0123456789abcdef' for c in feed['source_sha256']), 'FUNDED_SOURCE_DIGEST')
    p = feed['parameters']
    need(p['ExplicitPolicySha256'] == policy_hash and p['NativeSizingScenarioSha256'] == policy_hash,
         'FUNDED_SETTINGS_POLICY')
    # Owner limits are ceilings, not optimisation knobs. The C# account applies
    # the native volume lattice, fee reserve and account-wide stop admission.
    need(0 < p['MaxMarginFraction'] <= .4 and p['MinimumFreeMarginReserveEur'] >= 120 and
         0 < p['MaxEstimatedStopRiskFraction'] <= .01, 'FUNDED_OWNER_LIMITS')
    need(feed['symbols'] and len(feed['symbols']) <= 16 and
         len(set(x.upper() for x in feed['symbols'])) == len(feed['symbols']), 'FUNDED_ROSTER')
    previous = None
    for event in feed['events']:
        stamp = dt.datetime.fromisoformat(event['Utc'].replace('Z', '+00:00'))
        need(stamp.utcoffset() == dt.timedelta(0) and
             stamp < dt.datetime(2026, 9, 17, tzinfo=dt.timezone.utc), 'FUNDED_PROTECTED_CLOCK')
        need(previous is None or stamp >= previous, 'FUNDED_SOURCE_ORDER')
        previous = stamp
    return feed

def observed_periods(observations):
    """Observed equity changes only; no invented midnight/weekend valuation."""
    out = {'iso_weeks': {}, 'utc_months': {}}
    for row in observations:
        stamp = dt.datetime.fromisoformat(row['Utc'].replace('Z', '+00:00'))
        for group, key in [('iso_weeks', stamp.strftime('%G-W%V')), ('utc_months', stamp.strftime('%Y-%m'))]:
            period = out[group].setdefault(key, {'first': row, 'last': row, 'observations': 0})
            period['last'] = row
            period['observations'] += 1
    for group in out.values():
        for period in group.values():
            period['exact_calendar_boundary_equity_proven'] = False
    return out

def execute(candidate, feed, synthetic, chunk_size=None, observer=None):
    validate_feed(feed, candidate['spec_hash'], synthetic)
    if chunk_size is None:chunk_size=feed.get('execution_chunk_size',10000)
    need(type(chunk_size) is int and 1 <= chunk_size <= 100000, 'FUNDED_CHUNK_BOUND')
    # Binding includes ALL event bytes and policy/settings, not just a caller's
    # source label. It remains a checksum, not source authentication.
    binding = digest(feed)
    observations = []; chunks = []; prior = '-'; prior_sha = None
    with tempfile.TemporaryDirectory(prefix='mxm-funded-') as directory:
        root = Path(directory)
        for offset in range(0, len(feed['events']), chunk_size):
            batch = feed['events'][offset:offset + chunk_size]
            request = {'Schema': 'mxm.shared-funded-account.request.v1', 'SourceSha256': binding,
                       'Symbols': feed['symbols'], 'Parameters': feed['parameters'],
                       'ExpectedOrdinal': offset, 'PriorSha256': prior_sha, 'Events': batch}
            inp = root / f'{offset}.input.json'; output = root / f'{offset}.result.json'
            inp.write_text(json.dumps(request, allow_nan=False))
            subprocess.run(['dotnet', 'run', '--no-build', '-c', 'Release', '--project', str(PROJECT),
                            '--', str(inp), prior, str(output)], check=True, capture_output=True,
                           text=True, timeout=180)
            raw = output.read_bytes()
            capsule = Path(str(output) + '.capsule').read_bytes()
            if observer is not None:
                observer({'phase':'CSHARP_ORIGINAL_BEFORE_VALIDATION','first_ordinal':offset,
                          'result_base64':__import__('base64').b64encode(raw).decode(),
                          'capsule_base64':__import__('base64').b64encode(capsule).decode()})
            result = json.loads(raw)
            need(result['Schema'] == 'mxm.shared-funded-account.result.v1' and
                 result['SourceSha256'] == binding and result['ExpectedOrdinal'] == offset and
                 result['NextEventOrdinal'] == offset + len(batch), 'FUNDED_RESULT_CURSOR')
            need(result['Account']['InitialCapitalEur'] == 200 and
                 len(result['Observations']) == len(batch), 'FUNDED_CONTINUOUS_ACCOUNT')
            prior_sha = hashlib.sha256(capsule).hexdigest()
            need(prior_sha == result['CheckpointSha256'], 'FUNDED_CAPSULE_DIGEST')
            chunks.append({'first_ordinal': offset, 'next_ordinal': result['NextEventOrdinal'],
                           'result_sha256': hashlib.sha256(raw).hexdigest(), 'capsule_sha256': prior_sha})
            if feed.get('preserve_chunk_originals',False):
                chunks[-1]['original_result_base64']=__import__('base64').b64encode(raw).decode()
                chunks[-1]['original_capsule_base64']=__import__('base64').b64encode(capsule).decode()
            observations.extend(result['Observations']); prior = str(output) + '.capsule'
        account = result['Account']
        # Every original sample, ledger and final capsule remains in the private
        # programme result; publishing/custody uses the existing laboratory path.
        return {'classification': 'SYNTHETIC_FUNDED_RECEPTION' if synthetic else 'FUNDED_DEVELOPMENT_UNCERTIFIED',
                'source_binding_sha256': binding, 'account': account, 'observations': observations,
                'periods': observed_periods(observations), 'chunks': chunks,
                'final_capsule_base64': __import__('base64').b64encode(capsule).decode(),
                'deposit_count': 1, 'reset_count': 0, 'process_count': len(chunks),
                'hard21_certified': False, 'economic_qualification': False,
                'broker_fills': False, 'orders': 0, 'cloud': False}
