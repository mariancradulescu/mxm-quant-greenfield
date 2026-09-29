"""Read-only, outcome-blind Pepperstone M5 frontier selection and capture."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from competition.frontier_data_capture import (
    FrontierDataCaptureRunner, _plain, _windows, _write_rows, _inspect_csv,
    _deterministic_zip, _sha_file, normalize_m5,
)
from m6.ctrader_capture import (
    CaptureContractError, MappingError, account_fingerprint, atomic_write_json,
    live_account_candidates, redact_text, scan_bundle_for_secrets,
    select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq, ProtoOAAccountAuthReq,
    ProtoOAGetAccountListByAccessTokenReq, ProtoOATraderReq,
    ProtoOASymbolsListReq, ProtoOASymbolByIdReq, ProtoOAGetTrendbarsReq,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport
from research_v3.capture_identity import build_capture_manifest

FRONTIER_REL = 'evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json'
FEASIBILITY_REL = 'data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json'
SPEC_REL = 'research_core_v3/state/FROZEN_EXPERIMENT_SPEC_V1.json'
PROTECTED = '2026-09-17T12:02:58Z'
RECENT = {'start_utc': '2026-09-02T00:00:00Z', 'end_utc': '2026-09-15T23:59:59Z'}
DEVELOPMENT_END = '2026-09-16T23:59:59Z'
DEPTH_ANCHORS = (
    ('2025-09-16T00:00:00Z', '2025-09-17T23:59:59Z'),
    ('2025-12-16T00:00:00Z', '2025-12-17T23:59:59Z'),
    ('2026-03-17T00:00:00Z', '2026-03-18T23:59:59Z'),
    ('2026-06-16T00:00:00Z', '2026-06-17T23:59:59Z'),
)
CONTINUOUS_CLASSES = frozenset({
    'NEAR_24X5_MULTI_SESSION_SCHEDULE',
    'NEAR_24X7_OR_WEEKEND_CAPABLE_SCHEDULE',
})
SCHEMA = 'mxm.research-core-v3.full-frontier-quality-acquisition.v2'
OUTPUT = 'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip'
MIN_CAUSAL_RUN_BARS = 60  # frozen V3 base-family maximum lookback 48 + maximum response horizon 12.
WINDOW_DAYS = 14  # 14*288 = 4032 possible 24x7 M5 bars, below the broker 5000-bar limit.


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def frontier(root):
    root = Path(root)
    peer = json.loads((root / FRONTIER_REL).read_text())
    feasibility = json.loads((root / FEASIBILITY_REL).read_text())
    identities = peer['identities']
    if len(identities) != 1576 or len({int(x['symbol_id']) for x in identities}) != 1576:
        raise CaptureContractError('full exact identity frontier is not 1576 unique IDs')
    if int(feasibility['current_counts']['current_eligible_post_exclusion_frontier']) != 1576:
        raise CaptureContractError('broker feasibility authority changed')
    return identities, feasibility


def _dt(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate_rows(rows, start, end):
    previous = None
    for row in rows:
        ts = _dt(row['time_utc'])
        if previous is not None and ts <= previous:
            raise CaptureContractError('M5 timestamps are not strictly increasing')
        if ts.minute % 5 or ts.second or ts.microsecond:
            raise CaptureContractError('off-grid M5 timestamp')
        o, h, l, c = map(float, (row['open'], row['high'], row['low'], row['close']))
        if not all(map(math.isfinite, (o, h, l, c))) or not (0 < l <= o <= h and l <= c <= h):
            raise CaptureContractError('OHLC invariant')
        if not start <= row['time_utc'] <= end:
            raise CaptureContractError('out-of-window M5 timestamp')
        previous = ts


def continuity(rows):
    """Observed-grid statistics; scheduled closes and holidays are not imputed."""
    runs = []
    run = 0
    gaps = 0
    missing = 0
    previous = None
    for row in rows:
        ts = _dt(row['time_utc'])
        if previous is not None:
            steps = int((ts - previous).total_seconds() // 300)
            if steps > 1:
                gaps += 1
                missing += steps - 1
                runs.append(run)
                run = 0
        run += 1
        previous = ts
    if run:
        runs.append(run)
    return {'gap_count': gaps, 'estimated_missing_grid_bars': missing,
            'gap_fraction': gaps / max(1, len(rows) - 1),
            'longest_contiguous_run': max(runs, default=0),
            'contiguous_run_summary': {'run_count': len(runs), 'median_bars': sorted(runs)[len(runs)//2] if runs else 0}}


def _dominates(a, b):
    """Within the same schedule class, no weighted or outcome-fitted score."""
    higher = ('schedule_adjusted_coverage_proxy', 'longest_contiguous_run',
              'depth_anchor_count', 'effective_sample_potential')
    lower = ('gap_fraction', 'minimum_margin_estimate_for_EUR200')
    comparisons = [(float(a[k]), float(b[k])) for k in higher]
    comparisons += [(-float(a[k]), -float(b[k])) for k in lower]
    return all(x >= y for x, y in comparisons) and any(x > y for x, y in comparisons)


def select_core(table):
    candidates = []
    for row in table:
        row['initial_core_selected'] = False
        if row['identity_status'] != 'VERIFIED':
            row['selection_or_deferral_reason'] = 'BROKER_IDENTITY_OR_TRADING_MODE_DRIFT'
        elif row['schedule_continuity_class'] not in CONTINUOUS_CLASSES:
            row['selection_or_deferral_reason'] = 'LIMITED_SESSION_COMPLEMENTARY_FRONTIER'
        elif row['recent_probe_rows'] == 0:
            row['selection_or_deferral_reason'] = 'NO_AUTHENTIC_RECENT_M5_HISTORY'
        elif row['longest_contiguous_run'] < MIN_CAUSAL_RUN_BARS:
            row['selection_or_deferral_reason'] = 'NO_CONTIGUOUS_WINDOW_FOR_FROZEN_BASE_FAMILIES'
        elif row['depth_anchor_count'] < 1:
            row['selection_or_deferral_reason'] = 'NO_VERIFIED_EARLIER_DEVELOPMENT_DEPTH'
        else:
            candidates.append(row)
    for row in candidates:
        peers = [other for other in candidates if other is not row and
                 other['schedule_continuity_class'] == row['schedule_continuity_class']]
        if any(_dominates(other, row) for other in peers):
            row['selection_or_deferral_reason'] = 'PARETO_DOMINATED_WITHIN_BROKER_SCHEDULE_CLASS'
        else:
            row['initial_core_selected'] = True
            row['selection_or_deferral_reason'] = 'NONDOMINATED_VERIFIED_RECENT_AND_HISTORICAL_M5_QUALITY'
    return [r for r in table if r['initial_core_selected']]


class AdaptiveCollector(FrontierDataCaptureRunner):
    def __init__(self, *, client_id, client_secret, access_token, config, repo_root,
                 progress=print, transport=None):
        self.root = Path(repo_root)
        self.identities, self.feasibility = frontier(self.root)
        self.plan = {'schema': SCHEMA, 'source_environment': self.feasibility['source_environment'],
                     'account_fingerprint_sha256': self.feasibility['account_fingerprint_sha256'],
                     'frontier_sha256': _sha_file(self.root / FRONTIER_REL),
                     'feasibility_sha256': _sha_file(self.root / FEASIBILITY_REL),
                     'frozen_spec_sha256': _sha_file(self.root / SPEC_REL), 'recent': RECENT,
                     'depth_anchors': DEPTH_ANCHORS, 'development_end': DEVELOPMENT_END,
                     'protected_forward_start': PROTECTED, 'resolution': 'M5',
                     'window_days': WINDOW_DAYS, 'economic_outcomes_opened': 0}
        self.plan_sha = canonical_hash(self.plan)
        self.client_id, self.client_secret, self.access_token = client_id, client_secret, access_token
        self.config = dict(config)
        self.progress = progress
        self.transport = transport or StdlibCTraderTransport(LIVE_HOST, LIVE_PORT, response_timeout=60)
        self.work = self.root / '.research_core_v3_capture_work' / self.plan_sha[:16]
        self.bundle = self.work / 'bundle'
        self.zip_path = self.root / OUTPUT
        self.state_path = self.work / 'progress.json'
        self._app = False
        self._account = None
        self._last_hist = None
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.started = time.monotonic()
        self.session_rows = 0
        self.session_successful_requests = 0
        self.phase_new_units = 0
        self.phase_started = self.started
        self.state = {}

    def _save(self):
        with self.lock:
            self.state['last_heartbeat_utc'] = datetime.now(timezone.utc).isoformat()
            phase = self.state['phase']
            prefix = {'FRONTIER_PROBE': 'recent_', 'HISTORY_DEPTH_PREFLIGHT': 'depth_',
                      'DEEP_DEVELOPMENT_CAPTURE': 'deep_'}.get(phase)
            if prefix:
                completed = sum(key.startswith(prefix) for key in self.state['completed_units'])
                total = self.state['phase_total_work_units']
                self.state['completed_work_units'] = completed
                self.state['phase_percent'] = round(100 * completed / total, 4) if total else 0.0
            else:
                self.state['phase_percent'] = 100.0 if phase == 'CAPTURE_COMPLETE' else None
            self.state['percentage_complete'] = self.state['phase_percent']
            atomic_write_json(self.state_path, self.state)

    def _heartbeat(self):
        keys = ('last_heartbeat_utc', 'phase', 'phase_percent', 'current_symbol',
                'current_symbol_id', 'current_work_unit', 'completed_work_units',
                'phase_total_work_units', 'completed_symbols', 'phase_total_symbols',
                'current_symbol_rows', 'rows_total', 'successful_requests',
                'failed_requests', 'retry_count', 'reconnection_count',
                'timeout_count', 'throttle_count', 'zero_history_count',
                'failed_identity_count', 'last_successful_data_timestamp')
        while not self.stop.wait(10):
            self._save()
            with self.lock:
                snapshot = {key: self.state.get(key) for key in keys}
            elapsed = max(0.001, time.monotonic() - self.started)
            snapshot.update(current_UTC_time=datetime.now(timezone.utc).isoformat(),
                            rows_per_second=round(self.session_rows/elapsed, 2),
                            requests_per_minute=round(self.session_successful_requests*60/elapsed, 2),
                            elapsed_seconds=round(elapsed, 1), checkpoint_path=str(self.state_path))
            done, total = snapshot['completed_work_units'], snapshot['phase_total_work_units']
            phase_elapsed = max(0.001, time.monotonic()-self.phase_started)
            snapshot['estimated_remaining_seconds'] = round((total-done)*phase_elapsed/self.phase_new_units) if self.phase_new_units >= 10 and total > done else None
            self.progress('[HEARTBEAT] ' + json.dumps(snapshot, sort_keys=True))

    def _request(self, request, historical=False):
        try:
            response = super()._request(request, historical)
        except Exception as exc:
            with self.lock:
                self.state['failed_requests'] += 1
                msg = str(exc).lower()
                if isinstance(exc, TimeoutError) or 'timed out' in msg or 'timeout' in msg:
                    self.state['timeout_count'] += 1
                if 'rate limit' in msg or 'throttl' in msg or 'too many requests' in msg:
                    self.state['throttle_count'] += 1
                self._save()
            raise
        with self.lock:
            self.state['successful_requests'] += 1
            self.session_successful_requests += 1
        return response

    def _send(self, request, historical=False, retries=3):
        last = None
        for attempt in range(retries):
            if attempt:
                with self.lock:
                    self.state['retry_count'] += 1
                    self._save()
            try:
                return self._request(request, historical)
            except Exception as exc:
                last = exc
                if attempt + 1 == retries:
                    break
                time.sleep(min(4.0, 2**attempt))
                try:
                    self.transport.close()
                    self._restore()
                    with self.lock:
                        self.state['reconnection_count'] += 1
                except Exception as reconnection_error:
                    last = reconnection_error
        raise CaptureContractError(f'{type(request).__name__} failed: {redact_text(str(last))}')

    def _auth(self):
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id, clientSecret=self.client_secret))
        self._app = True
        accounts = [_plain(x) for x in self._send(
            ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved = self.config.get('ctid_trader_account_id')
        try:
            account = select_live_pepperstone_account(accounts, account_override=saved)
        except MappingError:
            selector = self.config.get('account_selector')
            if saved is not None or not callable(selector):
                raise
            account = select_live_pepperstone_account(
                accounts, account_override=int(selector(live_account_candidates(accounts))))
        aid = int(account['ctidTraderAccountId'])
        self._account = aid
        if account_fingerprint(aid) != self.plan['account_fingerprint_sha256']:
            raise MappingError('account fingerprint mismatch')
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid, accessToken=self.access_token))
        trader = _plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if 'pepperstone' not in str(trader.get('brokerName', '')).lower() and \
           'pepperstone' not in str(account.get('brokerTitleShort', '')).lower():
            raise MappingError('broker mismatch')
        light = {int(x.symbolId): _plain(x) for x in self._send(
            ProtoOASymbolsListReq(ctidTraderAccountId=aid, includeArchivedSymbols=False)).symbol}
        full = {}
        ids = [int(x['symbol_id']) for x in self.identities]
        for offset in range(0, len(ids), 64):
            request = ProtoOASymbolByIdReq(ctidTraderAccountId=aid)
            request.symbolId.extend(ids[offset:offset+64])
            for item in self._send(request).symbol:
                full[int(item.symbolId)] = _plain(item)
        return aid, light, full

    def _fetch_window(self, aid, sid, digits, start, end, scope_start, scope_end):
        rows = {}
        page_to = end
        pages = 0
        while page_to >= start:
            request = ProtoOAGetTrendbarsReq(ctidTraderAccountId=aid, symbolId=sid,
                period=ProtoOATrendbarPeriod.Value('M5'), fromTimestamp=start,
                toTimestamp=page_to, count=5000)
            response = self._send(request, historical=True)
            bars = [_plain(x) for x in response.trendbar]
            pages += 1
            for row in normalize_m5(bars, digits=digits, start_utc=scope_start,
                                    end_utc=scope_end, protected_utc=PROTECTED):
                old = rows.get(row['time_utc'])
                if old is not None and old != row:
                    raise CaptureContractError('conflicting duplicate M5 timestamp')
                rows[row['time_utc']] = row
            if not getattr(response, 'hasMore', False):
                break
            if not bars:
                raise CaptureContractError('hasMore without M5 bars')
            next_to = min(int(x['utcTimestampInMinutes'])*60000 for x in bars)-1
            if next_to >= page_to or next_to < start:
                raise CaptureContractError('invalid M5 pagination')
            page_to = next_to
        result = [rows[key] for key in sorted(rows)]
        validate_rows(result, scope_start, scope_end)
        if result:
            self.state['last_successful_data_timestamp'] = result[-1]['time_utc']
        return result, pages

    def _unit(self, key, aid, sid, digits, start, end, scope_start, scope_end):
        file = self.work / 'units' / f'{key}.csv'
        meta = file.with_suffix('.json')
        file.parent.mkdir(parents=True, exist_ok=True)
        if key in self.state['completed_units']:
            if not file.is_file() or not meta.is_file():
                raise CaptureContractError('checkpointed work unit missing')
            saved = json.loads(meta.read_text())
            if (_sha_file(file) != saved['sha256'] or saved['symbol_id'] != sid or
                saved['requested_start_ms'] != start or saved['requested_end_ms'] != end or
                saved['scope_start'] != scope_start or saved['scope_end'] != scope_end):
                raise CaptureContractError('checkpointed work unit integrity mismatch')
            with file.open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            validate_rows(rows, scope_start, scope_end)
            if len(rows) != saved['rows']:
                raise CaptureContractError('checkpointed work unit row-count mismatch')
            self.state['current_symbol_rows'] += len(rows)
            return rows
        rows, pages = self._fetch_window(aid, sid, digits, start, end, scope_start, scope_end)
        tmp = file.with_suffix('.tmp')
        _write_rows(tmp, rows, 'w')
        tmp.replace(file)
        atomic_write_json(meta, {'sha256': _sha_file(file), 'rows': len(rows), 'pages': pages,
                                 'requested_start_ms': start, 'requested_end_ms': end,
                                 'symbol_id': sid, 'scope_start': scope_start, 'scope_end': scope_end})
        with self.lock:
            self.state['completed_units'].append(key)
            self.state['rows_total'] += len(rows)
            self.session_rows += len(rows)
            self.phase_new_units += 1
            self.state['current_symbol_rows'] += len(rows)
            self._save()
        return rows

    def _phase(self, name, units, symbols):
        self.phase_started = time.monotonic()
        self.phase_new_units = 0
        self.state.update(phase=name, phase_total_work_units=units,
                          phase_total_symbols=symbols, completed_symbols=0,
                          current_symbol=None, current_work_unit=None)
        self._save()

    def run(self):
        self.work.mkdir(parents=True, exist_ok=True)
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
            if self.state['plan_sha256'] != self.plan_sha:
                raise CaptureContractError('checkpoint plan mismatch')
        else:
            self.state = {'plan_sha256': self.plan_sha, 'selected_identity_manifest_sha256': None,
                'started_utc': datetime.now(timezone.utc).isoformat(), 'completed_units': [],
                'phase': 'FRONTIER_PROBE', 'phase_total_work_units': 1576,
                'phase_total_symbols': 1576, 'completed_work_units': 0,
                'completed_symbols': 0, 'current_symbol_rows': 0, 'rows_total': 0,
                'successful_requests': 0, 'failed_requests': 0, 'retry_count': 0,
                'reconnection_count': 0, 'timeout_count': 0, 'throttle_count': 0,
                'zero_history_ids': [], 'zero_history_count': 0, 'failed_identity_count': 0,
                'last_successful_data_timestamp': None,
                'resumable_checkpoint': str(self.state_path)}
            self._save()
        heartbeat = threading.Thread(target=self._heartbeat, daemon=True)
        heartbeat.start()
        try:
            self.transport.connect()
            self._workflow()
        finally:
            self.stop.set()
            heartbeat.join(timeout=2)
            self.transport.close()
        return self.zip_path

    def _workflow(self):
        aid, light, full = self._auth()
        table = []
        self._phase('FRONTIER_PROBE', len(self.identities), len(self.identities))
        recent_window = _windows(RECENT['start_utc'], RECENT['end_utc'], WINDOW_DAYS)[0]
        for index, identity in enumerate(self.identities, 1):
            sid = int(identity['symbol_id'])
            name = identity['broker_symbol']
            li, fu = light.get(sid), full.get(sid)
            valid = li is not None and fu is not None and li.get('symbolName') == name and \
                    li.get('enabled') is not False and int(fu.get('tradingMode', -1)) == 0
            row = {'symbol': name, 'symbol_id': sid,
                'asset_class': identity['peer_coherence_metadata'].get('asset_class'),
                'product_type': identity['peer_coherence_metadata'].get('product_type'),
                'current_accessibility': identity['current_entry_accessible'],
                'directional_feasibility': identity['directional_feasibility'],
                'shortability': identity['directional_feasibility'] == 'BOTH_FEASIBLE',
                'minimum_executable_volume': identity['minimum_executable_volume'],
                'minimum_margin_estimate_for_EUR200': identity['minimum_directional_margin_eur'],
                'schedule_minutes_per_week': identity['schedule_minutes_per_week'],
                'schedule_continuity_class': identity['peer_coherence_metadata'].get('coverage_bucket'),
                'identity_status': 'VERIFIED' if valid else 'DRIFT',
                'recent_probe_rows': 0, 'recent_probe_history_start': None,
                'recent_probe_history_end': None, 'schedule_adjusted_coverage_proxy': 0,
                'gap_count': 0, 'estimated_missing_M5_bars_from_detected_gaps_where_honest': 0,
                'gap_fraction': 1, 'longest_contiguous_run': 0,
                'contiguous_run_summary': {'run_count': 0, 'median_bars': 0},
                'timestamp_integrity': 'UNKNOWN', 'OHLC_integrity': 'UNKNOWN',
                'depth_preflight_status': 'NOT_APPLICABLE', 'depth_anchor_count': 0,
                'earliest_verified_development_history': None,
                'latest_verified_development_history': None,
                'effective_sample_potential': 0, 'initial_core_selected': False,
                'selection_or_deferral_reason': None}
            table.append(row)
            if not valid:
                raise MappingError(f'full frontier identity drift: {name}/{sid}')
            self.state.update(current_symbol=name, current_symbol_id=sid,
                              current_work_unit=f'recent_{sid}', current_symbol_rows=0)
            rows = self._unit(f'recent_{sid}', aid, sid, int(fu.get('digits', 5)),
                              *recent_window, RECENT['start_utc'], RECENT['end_utc'])
            row['recent_probe_rows'] = len(rows)
            row['schedule_adjusted_coverage_proxy'] = len(rows) / max(1, 2*float(row['schedule_minutes_per_week'])/5)
            if rows:
                row['recent_probe_history_start'] = rows[0]['time_utc']
                row['recent_probe_history_end'] = rows[-1]['time_utc']
                metrics = continuity(rows)
                row.update(gap_count=metrics['gap_count'],
                           estimated_missing_M5_bars_from_detected_gaps_where_honest=metrics['estimated_missing_grid_bars'],
                           gap_fraction=metrics['gap_fraction'],
                           longest_contiguous_run=metrics['longest_contiguous_run'],
                           contiguous_run_summary=metrics['contiguous_run_summary'],
                           effective_sample_potential=len(rows),
                           timestamp_integrity='PASS', OHLC_integrity='PASS')
            else:
                ids = self.state['zero_history_ids']
                if sid not in ids:
                    ids.append(sid)
                self.state['zero_history_count'] = len(ids)
            self.state['completed_symbols'] = index
            self._save()
        candidates = [r for r in table if r['identity_status'] == 'VERIFIED' and
                      r['schedule_continuity_class'] in CONTINUOUS_CLASSES and
                      r['recent_probe_rows'] and r['longest_contiguous_run'] >= MIN_CAUSAL_RUN_BARS]
        self._phase('HISTORY_DEPTH_PREFLIGHT', len(candidates)*len(DEPTH_ANCHORS), len(candidates))
        for index, row in enumerate(candidates, 1):
            sid, name = row['symbol_id'], row['symbol']
            self.state.update(current_symbol=name, current_symbol_id=sid, current_symbol_rows=0)
            anchors = []
            for ai, (start_iso, end_iso) in enumerate(DEPTH_ANCHORS):
                key = f'depth_{sid}_{ai:02d}'
                self.state['current_work_unit'] = key
                start_ms, end_ms = _windows(start_iso, end_iso, WINDOW_DAYS)[0]
                rows = self._unit(key, aid, sid, int(full[sid].get('digits', 5)),
                                  start_ms, end_ms, start_iso, end_iso)
                if rows:
                    anchors.append({'anchor': ai, 'rows': len(rows),
                                    'first': rows[0]['time_utc'], 'last': rows[-1]['time_utc'],
                                    'continuity': continuity(rows)})
            row['depth_anchor_count'] = len(anchors)
            row['depth_preflight_status'] = 'VERIFIED' if anchors else 'NO_EARLIER_HISTORY'
            row['depth_anchor_evidence'] = anchors
            if anchors:
                row['earliest_verified_development_history'] = anchors[0]['first']
                row['latest_verified_development_history'] = row['recent_probe_history_end']
                row['effective_sample_potential'] += sum(x['rows'] for x in anchors)
                row['development_start_utc'] = DEPTH_ANCHORS[anchors[0]['anchor']][0]
            self.state['completed_symbols'] = index
            self._save()
        selected = select_core(table)
        if not selected:
            raise CaptureContractError('no non-dominated identity has verified recent and earlier M5 history')
        manifest = {'schema': SCHEMA, 'plan_sha256': self.plan_sha,
                    'symbols': [{'broker_symbol': r['symbol'], 'symbol_id': r['symbol_id'],
                                 'development_start_utc': r['development_start_utc']}
                                for r in selected],
                    'selection_law': {'broker_semantic_continuity_classes': sorted(CONTINUOUS_CLASSES),
                        'recent_history_required': True, 'earlier_history_anchor_required': True,
                        'pareto_dimensions': ['schedule_adjusted_coverage_proxy',
                            'longest_contiguous_run', 'depth_anchor_count',
                            'effective_sample_potential', 'gap_fraction',
                            'minimum_margin_estimate_for_EUR200'],
                        'pareto_comparison_scope': 'within broker schedule class',
                        'numerical_quality_cutoffs': [{'field': 'longest_contiguous_run',
                            'minimum_bars': MIN_CAUSAL_RUN_BARS,
                            'basis': 'frozen V3 base-family largest lookback 48 M5 bars plus frozen longest response horizon 12 bars; minimum one causal signal and response window'}],
                        'structural_depth_basis': 'at least one older sampled period plus recent observations for distinct chronological periods; earliest nonempty anchor determines each symbol development start',
                        'schedule_completeness_is_proxy': True,
                        'gap_estimates_include_scheduled_closures_and_holidays': True,
                        'market_outcomes_used': False},
                    'development_end_utc': DEVELOPMENT_END,
                    'protected_forward_start': PROTECTED}
        manifest['sha256'] = canonical_hash(manifest)
        prior = self.state.get('selected_identity_manifest_sha256')
        if prior not in (None, manifest['sha256']):
            raise CaptureContractError('frozen selected identity manifest changed on resume')
        self.state['selected_identity_manifest_sha256'] = manifest['sha256']
        windows_by_id = {r['symbol_id']: _windows(r['development_start_utc'], DEVELOPMENT_END, WINDOW_DAYS)
                         for r in selected}
        self._phase('DEEP_DEVELOPMENT_CAPTURE', sum(map(len, windows_by_id.values())), len(selected))
        self.bundle.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.bundle/'DATA_QUALITY_TABLE.json',
                          {'frontier_count': len(table), 'rows': table,
                           'quality_method': manifest['selection_law']})
        atomic_write_json(self.bundle/'SELECTED_IDENTITY_MANIFEST.json', manifest)
        results = []
        for index, row in enumerate(selected, 1):
            sid, name = row['symbol_id'], row['symbol']
            self.state.update(current_symbol=name, current_symbol_id=sid, current_symbol_rows=0)
            combined = {}
            for wi, (start_ms, end_ms) in enumerate(windows_by_id[sid]):
                key = f'deep_{sid}_{wi:03d}'
                self.state['current_work_unit'] = key
                self._save()
                for bar in self._unit(key, aid, sid, int(full[sid].get('digits', 5)),
                                      start_ms, end_ms, row['development_start_utc'], DEVELOPMENT_END):
                    old = combined.get(bar['time_utc'])
                    if old is not None and old != bar:
                        raise CaptureContractError('conflicting cross-window M5 duplicate')
                    combined[bar['time_utc']] = bar
            path = self.bundle/'raw'/f'{sid}_M5.csv'
            path.parent.mkdir(exist_ok=True)
            bars = [combined[key] for key in sorted(combined)]
            validate_rows(bars, row['development_start_utc'], DEVELOPMENT_END)
            _write_rows(path, bars, 'w')
            meta = _inspect_csv(path)
            results.append({'broker_symbol': name, 'symbol_id': sid,
                            'file': path.relative_to(self.bundle).as_posix(),
                            'development_start_utc': row['development_start_utc'], **meta})
            self.state['completed_symbols'] = index
            self._save()
            self.progress(f'[SERIES {index}/{len(selected)}] {name}: {len(bars)} authentic M5 rows')
        payload = {'schema': SCHEMA, 'status': 'CAPTURE_COMPLETE',
                   'plan_sha256': self.plan_sha, 'selected_identity_manifest_sha256': manifest['sha256'],
                   'account_fingerprint_sha256': self.plan['account_fingerprint_sha256'],
                   'source_environment': self.plan['source_environment'],
                   'resolution': 'M5', 'classification': 'DEVELOPMENT_ONLY',
                   'development_end_utc': DEVELOPMENT_END, 'series': results,
                   'total_m5_rows': sum(x['row_count'] for x in results),
                   'protected_forward_opened': False, 'economic_outcomes_opened': 0,
                   'orders_placed': False, 'account_mutation': False}
        payload_path = self.bundle/'V3_CAPTURE_PAYLOAD.json'
        atomic_write_json(payload_path, payload)
        provenance = build_capture_manifest(
            capture_session_id='research-core-v3-selected-'+manifest['sha256'][:16],
            capture_schema=SCHEMA, tool_version='FULL_FRONTIER_GENERIC_V3',
            account_fingerprint=self.plan['account_fingerprint_sha256'],
            source_environment=self.plan['source_environment'],
            capture_start_utc=min(r['development_start_utc'] for r in selected),
            capture_end_utc=DEVELOPMENT_END, completion_state='COMPLETE',
            canonical_payloads={'V3_CAPTURE_PAYLOAD.json': payload_path.read_bytes()},
            original_collector_package_sha256=self.config.get('collector_package_sha256'),
            read_only_assertion=True, economic_outcomes_opened=0,
            orders_placed=False, account_mutation=False, protected_evidence_opened=False)
        atomic_write_json(self.bundle/'CAPTURE_MANIFEST.json', provenance)
        (self.bundle/'CHECKSUMS.sha256').write_text(''.join(
            f'{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}\n'
            for p in sorted(self.bundle.rglob('*'))
            if p.is_file() and p.name != 'CHECKSUMS.sha256'))
        scan_bundle_for_secrets(self.bundle, [self.client_secret, self.access_token])
        digest = _deterministic_zip(self.bundle, self.zip_path)
        self.state['phase'] = 'CAPTURE_COMPLETE'
        self._save()
        self.progress(f'CAPTURE_COMPLETE final_zip_path={self.zip_path} final_zip_sha256={digest} '
                      f'selected_identity_count={len(selected)} '
                      f'successful_nonempty_identity_count={sum(r["row_count"]>0 for r in results)} '
                      f'authentic_zero_history_identity_count={sum(r["row_count"]==0 for r in results)} '
                      f'failed_identity_count=0 total_M5_rows={payload["total_m5_rows"]} '
                      f'history_start_utc={min(r["development_start_utc"] for r in selected)} '
                      f'history_end_utc={DEVELOPMENT_END} elapsed_seconds={int(time.monotonic()-self.started)} '
                      'integrity_status=PASS')
