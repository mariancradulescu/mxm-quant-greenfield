"""Bounded evidence recovery and additive errata; never modifies preserved data.

Every conclusion carries its source universe. Integrity is not broker provenance,
and producer evidence is never promoted to independent acceptance.
"""
import copy
import gzip
import json
import math
import pathlib
from collections import Counter, defaultdict
from .safety import canonical, sha, require, bind_failure, JOURNAL

SCOPE = 'ALL_DIRECT_GENERATION_1807_CHECKPOINT_REFERENCES_ONLY'
LOW = 1787097600000
END = 1789344000000


def unique_metadata(journal):
    out = {}
    for field in ('shards', 'record_shards', 'snapshots_v2', 'increments_v2'):
        values = journal.get(field, [])
        for meta in values.values() if isinstance(values, dict) else values:
            aid = meta['id']
            if aid in out:
                fields = ('id', 'ciphertext_sha256', 'canonical_sha256', 'gzip_sha256', 'size', 'name')
                require(all(out[aid].get(k) == meta.get(k) for k in fields), 'DUPLICATE_ASSET_MANIFEST_CONFLICT')
            else:
                out[aid] = meta
    return out


class EvidenceIndex:
    def __init__(self, journal):
        self.expected = unique_metadata(journal)
        self.sources = []
        self.wire = {}
        self.wire_conflicts = []
        self.spans = defaultdict(list)
        self.raw = []
        self.errata = []
        self.failures = []
        self.errors = copy.deepcopy(journal.get('errors', []))
        self.terminal = copy.deepcopy(journal.get('autonomy_proof', {}).get('failure'))
        self.historical_catalog = []
        # These locators identify earlier import attempts, not an exhaustive
        # manifest of all historical research datasets or all raw requests.
        for key in ('archive', 'legacy_supplement'):
            for receipt in journal.get(key, {}).get('asset_receipts', []):
                self.historical_catalog.append({'catalog': key, **copy.deepcopy(receipt)})

    def unavailable(self, meta, code):
        self.sources.append({'asset_id': meta['id'], 'state': 'EVIDENCE_UNAVAILABLE', 'code': code})

    def consume(self, meta, value):
        require(meta['id'] in self.expected, 'FOREIGN_ASSET_NOT_IN_CHECKPOINT')
        aid = meta['id']
        before = sha(canonical(value))
        counts = Counter()
        invalid = []
        for field, width in (('bars', 7), ('ticks', 4), ('spans', 5), ('wire', 6)):
            rows = value.get(field, [])
            require(isinstance(rows, list), 'CHECKPOINT_TABLE_SCHEMA_UNKNOWN')
            counts[field] = len(rows)
            for i, row in enumerate(rows):
                if not isinstance(row, (list, tuple)) or len(row) != width:
                    invalid.append({'field': field, 'row': i, 'reason': 'ROW_SCHEMA_UNKNOWN'})
                    continue
                if field == 'bars':
                    _, t, o, h, l, c, v = row
                    reason = None
                    if type(t) is not int or t % 300 or not LOW <= t * 1000 < END:
                        reason = 'BAR_TIME_GRID_OR_DOMAIN_UNKNOWN'
                    elif not all(type(x) in (int, float) and math.isfinite(x) for x in (o, h, l, c, v)):
                        reason = 'BAR_NONFINITE'
                    elif min(o, h, l, c) <= 0 or not l <= min(o, c) <= max(o, c) <= h or v < 0:
                        reason = 'BAR_OHLC_OR_VOLUME_INVALID'
                    if reason:
                        invalid.append({'field': field, 'row': i, 'reason': reason})
                elif field == 'ticks':
                    _, side, t, price = row
                    if side not in ('bid', 'ask') or type(t) is not int or not LOW <= t < END or type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
                        invalid.append({'field': field, 'row': i, 'reason': 'TICK_DOMAIN_OR_VALUE_UNKNOWN'})
                elif field == 'wire':
                    k = tuple(row[:4]); v = tuple(row[4:])
                    prior = self.wire.get(k)
                    if prior and prior['value'] != v:
                        self.wire_conflicts.append({'key': k, 'predecessor': prior, 'successor': {'asset_id': aid, 'value': v}})
                    elif prior is None:
                        self.wire[k] = {'asset_id': aid, 'value': v}
                elif field == 'spans':
                    sid, kind, a, b, state = row
                    if type(a) is not int or type(b) is not int or a > b:
                        invalid.append({'field': field, 'row': i, 'reason': 'SPAN_DOMAIN_UNKNOWN'})
                    else:
                        self.spans[sid, kind].append({'a': a, 'b': b, 'state': state, 'asset_id': aid, 'row': i})
        for i, raw in enumerate(value.get('raw', [])):
            require(isinstance(raw, dict), 'RAW_RECEIPT_SCHEMA_UNKNOWN')
            req = raw.get('request', {})
            evidence = raw.get('preserved_failure_evidence')
            # Older remediations stored bind_failure's wrapper; unwrap only the
            # exact request-bound payload. Never trust its declared state alone.
            candidate = evidence.get('evidence', evidence) if isinstance(evidence, dict) else {}
            bound = bind_failure(raw, candidate)
            record = {'asset_id': aid, 'row': i, 'raw_sha256': sha(canonical(raw)), 'request': copy.deepcopy(req), 'state': raw.get('state'), 'exception_class': raw.get('exception_class'), 'failure_binding': bound['state'] if evidence is not None else 'NO_FAILURE_RECEIPT', 'has_more_presence': raw.get('has_more_present', 'hasMore' in raw), 'has_more': raw.get('has_more', raw.get('hasMore')), 'has_native_response': any(k in raw for k in ('response_b64', 'response_envelope_b64'))}
            self.raw.append(record)
            if evidence is not None and bound['state'] != 'REQUEST_BOUND':
                self.errata.append({'asset_id': aid, 'raw_row': i, 'original_raw_sha256': record['raw_sha256'], 'disposition': 'FAILURE_EVIDENCE_UNBOUND_KEEP_TRANSPORT_UNKNOWN', 'physical_cause': 'UNKNOWN', 'original_changed': False})
        for item in invalid:
            self.errata.append({'asset_id': aid, **item, 'disposition': 'QUARANTINE_FOR_FUTURE_CONSUMERS', 'original_changed': False})
        after = sha(canonical(value))
        require(before == after, 'EVIDENCE_SCAN_MUTATED_SOURCE')
        self.sources.append({'asset_id': aid, 'release_id': meta.get('release_id'), 'ciphertext_sha256': meta['ciphertext_sha256'], 'gzip_sha256': meta['gzip_sha256'], 'canonical_sha256': meta['canonical_sha256'], 'scan_value_before_sha256': before, 'scan_value_after_sha256': after, 'counts': dict(counts), 'invalid_rows': invalid, 'state': 'OWNER_VERIFIED_UNCHANGED', 'row_account_server_provenance': 'UNKNOWN_LEGACY_NO_COMPLETE_ROW_RECEIPTS', 'coverage_promoted': False})

    def finish(self):
        ids = [x['asset_id'] for x in self.sources]
        require(len(ids) == len(set(ids)) and set(ids) == set(self.expected), 'EVIDENCE_UNIVERSE_NOT_EXACT')
        conflicts = []
        good = {'CONFIRMED_COMPLETE', 'EMPTY_AUTHENTIC_RESPONSE', 'SESSION_CLOSED_SUPPORTED'}
        for key, rows in self.spans.items():
            active = []
            for row in sorted(rows, key=lambda r: (r['a'], r['b'], r['state'], r['asset_id'])):
                active = [r for r in active if r['b'] >= row['a']]
                for old in active:
                    if (old['state'] in good) != (row['state'] in good):
                        conflicts.append({'key': key, 'a': max(old['a'], row['a']), 'b': min(old['b'], row['b']), 'sources': [old, row], 'disposition': 'UNKNOWN_CONFLICT_QUARANTINE', 'original_changed': False})
                active.append(row)
        errata = self.errata + [{'kind': 'SPAN_CONFLICT', **x} for x in conflicts]
        errata += [{'kind': 'WIRE_CONFLICT', **x, 'disposition': 'UNKNOWN_CONFLICT_QUARANTINE', 'original_changed': False} for x in self.wire_conflicts]
        unavailable = sum(x['state'] != 'OWNER_VERIFIED_UNCHANGED' for x in self.sources)
        return {'schema': 'mxm.remediation.bounded.evidence.and.errata.v2', 'scope': SCOPE, 'generation': 1807, 'journal_sha256': JOURNAL, 'expected_assets': len(self.expected), 'sources': self.sources, 'unavailable_assets': unavailable, 'wire_keys_inspected': len(self.wire), 'wire_conflicts': self.wire_conflicts, 'span_conflicts': conflicts, 'raw_receipts': self.raw, 'additive_errata': errata, 'terminal_failure': self.terminal, 'journal_errors': self.errors, 'historical_import_locator_catalog': self.historical_catalog, 'historical_catalog_complete': False, 'physical_transport_cause': 'UNKNOWN_UNLESS_EXACT_REQUEST_BOUND_RECEIPT_EXISTS', 'global_historical_impact_closed': False, 'original_changed': False, 'new_broker_requests': 0, 'new_outcomes': 0}


def write_private(result, root, key, tmp, decrypt, filename='resolution-evidence.mxmenc'):
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
    from .safety import unpack, strict_json
    out = root / 'verification'; out.mkdir(exist_ok=True)
    require(filename in ('resolution-evidence.mxmenc', 'economic-label-errata.mxmenc'), 'PRIVATE_OUTPUT_PATH')
    path = out / filename
    raw = canonical(result); packed = gzip.compress(raw, mtime=0)
    encrypt_shard(packed, public_key=root / 'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem', output=path)
    observed = decrypt(path.read_bytes(), key, tmp)
    require(observed == packed and canonical(strict_json(unpack(observed), max_elements=8000000)) == raw, 'RESOLUTION_OWNER_LOCAL_READBACK')
    return {'file': path.name, 'ciphertext_sha256': sha(path.read_bytes()), 'gzip_sha256': sha(packed), 'canonical_sha256': sha(raw), 'OWNER_readback': True}


def economic_errata(corrected, accepted, historical, pins):
    """Read saved summary/corrected labels only. No outcome or scenario replay."""
    before = [sha(canonical(x)) for x in (corrected, accepted, historical)]
    require(corrected['accepted_result_reused_without_signal_replay']['canonical_sha256'] == pins['accepted']['canonical_sha256'], 'CORRECTED_ACCEPTED_SOURCE_MISMATCH')
    require(corrected.get('new_directional_outcomes') == 0, 'CORRECTION_HAS_NEW_OUTCOME')
    cases = accepted['summary']['cases']; fixed = corrected['corrected_cost_populations']
    require(set(cases) == set(fixed), 'CORRECTED_CASE_SET_MISMATCH')
    receipts = []
    for name, old in cases.items():
        parts = fixed[name]
        require(set(parts) == {'all_cost_observable', 'entry_feasible', 'entry_feasible_exit_observed', 'entry_feasible_path_complete'}, 'CORRECTED_SUBSET_SCHEMA')
        a, b, c, d = (parts[k]['n'] for k in ('all_cost_observable', 'entry_feasible', 'entry_feasible_exit_observed', 'entry_feasible_path_complete'))
        require(all(type(v) is int and v >= 0 for v in (a, b, c, d)), 'CORRECTED_COUNT_INVALID')
        require(a == old['cohort'] and d <= c <= b <= a, 'CORRECTED_POPULATION_MISMATCH')
        receipts.append({'case': name, 'historical_case_sha256': sha(canonical(old)), 'saved_corrected_case_sha256': sha(canonical(parts)), 'denominators': {k: v['n'] for k, v in parts.items()}, 'no_population_reselection': True})
    summary = historical['summary']
    require(summary.get('alpha_certified') is False and summary.get('HARD21') is False, 'HISTORICAL_PROMOTION_FORBIDDEN')
    require('portfolio' in summary and 'economic_aggregate' in summary, 'HISTORICAL_EQUITY_REPORT_MISSING')
    after = [sha(canonical(x)) for x in (corrected, accepted, historical)]
    require(before == after, 'ECONOMIC_HISTORY_CHANGED')
    return {'schema': 'mxm.remediation.economic.label.erratum.v2', 'sources': pins, 'input_before_sha256': before, 'input_after_sha256': after, 'cases': receipts, 'historical_reference': {'schema': summary['schema'], 'decision': summary['decision'], 'portfolio_sha256': sha(canonical(summary['portfolio'])), 'aggregate_sha256': sha(canonical(summary['economic_aggregate'])), 'semantics': summary.get('NET_semantics'), 'label': 'HISTORICAL_REFERENCE_SCENARIOS_NOT_REAL_ACCOUNT'}, 'successor_continuous_ledger': {'path': 'research_core_v4/remediation_p0_p4_20261015/economics.py', 'scope': 'OFFLINE_SYNTHETIC_CONTROL_ONLY', 'real_account_certified': False}, 'new_outcomes': 0, 'new_NET': None, 'original_numbers_changed': False, 'HARD21': False, 'independent_acceptance': False}


def public_summary(result, private, economic=None):
    return {'schema': 'mxm.remediation.resolution.summary.v2', 'scope': SCOPE, 'journal_sha256': JOURNAL, 'expected_assets': result['expected_assets'], 'verified_assets': result['expected_assets'] - result['unavailable_assets'], 'unavailable_assets': result['unavailable_assets'], 'span_conflicts_quarantined': len(result['span_conflicts']), 'wire_conflicts_quarantined': len(result['wire_conflicts']), 'additive_errata': len(result['additive_errata']), 'raw_receipts_inspected': len(result['raw_receipts']), 'row_provenance_complete': False, 'private_evidence': private, 'economic_label_receipt': {'verified': economic is not None, 'case_count': len(economic['cases']) if economic else 0}, 'history_complete': False, 'original_changed': False, 'broker_requests': 0, 'new_outcomes': 0, 'alpha_certified': False, 'HARD21': False, 'independent_acceptance': False}


def consumer_state(impact):
    """A recovered ciphertext is not automatically eligible economic input."""
    bad = impact.get('unavailable_assets', 0) or impact.get('additive_errata', []) or impact.get('row_provenance_complete') is not True
    return {'data_blocked': bool(bad), 'outcomes_read': False, 'resolved_unknown': 'BOUNDED_SOURCE_QUARANTINE_INSTALLED' if bad else 'BOUNDED_INTEGRITY_INSPECTED_PROVENANCE_STILL_UNKNOWN', 'source_sha256': JOURNAL}
