"""Resume-safe collection of only the frozen missing high-quality M5 identities."""
from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

from competition.frontier_data_capture import _windows, _write_rows, _inspect_csv, _deterministic_zip, _sha_file
from m6.ctrader_capture import CaptureContractError, MappingError, atomic_write_json, scan_bundle_for_secrets
from research_v3.capture_identity import build_capture_manifest

from .adaptive_collector import AdaptiveCollector, SCHEMA, WINDOW_DAYS, canonical_hash, validate_rows

FROZEN = 'research_core_v3/state/INCLUSIVE_FULL_DEPTH_DISCOVERY_CORE_V1.json'
QUALITY_GZ = 'research_core_v3/state/ACCEPTED_DATA_QUALITY_TABLE_V1.json.gz'
DELTA_OUTPUT = 'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip'


def frozen_scope(root):
    root = Path(root)
    document = json.loads((root / FROZEN).read_text())
    sha = document.pop('sha256')
    if canonical_hash(document) != sha:
        raise CaptureContractError('frozen high-quality manifest changed')
    document['sha256'] = sha
    quality_bytes = gzip.decompress((root / QUALITY_GZ).read_bytes())
    if __import__('hashlib').sha256(quality_bytes).hexdigest() != document['source_quality_table_sha256']:
        raise CaptureContractError('accepted frontier quality table hash changed')
    quality = json.loads(quality_bytes)['rows']
    if len(quality) != 1576 or len({r['symbol_id'] for r in quality}) != 1576:
        raise CaptureContractError('accepted frontier table incomplete')
    primary = {int(r['symbol_id']): r for r in document['primary_core']}
    delta = [primary[sid] for sid in document['delta_ids']]
    if len(primary) != document['primary_count'] or len(delta) != document['missing_delta_count'] or any(x['reused_authentic_sha256'] for x in delta):
        raise CaptureContractError('delta includes reused or duplicate identity')
    return document, quality_bytes, delta


class DeltaCollector(AdaptiveCollector):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.frozen, self.quality_bytes, self.delta = frozen_scope(self.root)
        if (self.plan['account_fingerprint_sha256'] != self.frozen['source_account_fingerprint_sha256'] or
                self.plan['source_environment'] != 'Pepperstone - Europe LIVE'):
            raise MappingError('original capture account or broker mismatch')
        self.plan = {'schema':'mxm.research-core-v3.high-quality-delta.v1',
                     'frozen_core_sha256':self.frozen['sha256'],
                     'source_quality_table_sha256':self.frozen['source_quality_table_sha256'],
                     'source_capture_zip_sha256':self.frozen['source_capture_zip_sha256'],
                     'account_fingerprint_sha256':self.plan['account_fingerprint_sha256'],
                     'development_end_utc':self.frozen['development_end_utc'],
                     'window_days':WINDOW_DAYS,'resolution':'M5','economic_outcomes_opened':0}
        self.plan_sha = canonical_hash(self.plan)
        self.work = self.root / '.research_core_v3_delta_work' / self.plan_sha[:16]
        self.bundle = self.work / 'bundle'
        self.state_path = self.work / 'progress.json'
        self.zip_path = self.root / DELTA_OUTPUT
        self.initial_phase = 'DEEP_DEVELOPMENT_CAPTURE'
        self.initial_work_units = sum(len(_windows(r['development_start_utc'],self.frozen['development_end_utc'],WINDOW_DAYS)) for r in self.delta)
        self.initial_symbols = len(self.delta)

    def _workflow(self):
        aid, light, full = self._auth()
        for item in self.delta:
            sid = item['symbol_id']
            if (sid not in light or sid not in full or
                    light[sid].get('symbolName') != item['broker_symbol'] or
                    int(full[sid].get('tradingMode',-1)) != 0):
                raise MappingError(f'delta broker identity drift: {sid}')
        windows = {r['symbol_id']:_windows(r['development_start_utc'],self.frozen['development_end_utc'],WINDOW_DAYS) for r in self.delta}
        self.state['selected_identity_manifest_sha256'] = self.frozen['sha256']
        self._phase('DEEP_DEVELOPMENT_CAPTURE',sum(map(len,windows.values())),len(self.delta))
        self.bundle.mkdir(parents=True,exist_ok=True)
        (self.bundle/'DATA_QUALITY_TABLE.json').write_bytes(self.quality_bytes)
        manifest = {'schema':SCHEMA,'plan_sha256':self.plan_sha,
                    'symbols':[{'broker_symbol':r['broker_symbol'],'symbol_id':r['symbol_id'],
                                'development_start_utc':r['development_start_utc']} for r in self.delta],
                    'frozen_primary_core_sha256':self.frozen['sha256'],
                    'selection_law':{'frozen_inclusive_high_quality_core':self.frozen['sha256'],
                                     'delta_only':True,'market_outcomes_used':False},
                    'development_end_utc':self.frozen['development_end_utc'],
                    'protected_forward_start':self.frozen['protected_forward_start']}
        manifest['sha256'] = canonical_hash(manifest)
        atomic_write_json(self.bundle/'SELECTED_IDENTITY_MANIFEST.json',manifest)
        results=[]
        for index,item in enumerate(self.delta,1):
            sid=item['symbol_id']; self.state.update(current_symbol=item['broker_symbol'],current_symbol_id=sid,current_symbol_rows=0)
            combined={}
            for wi,(start_ms,end_ms) in enumerate(windows[sid]):
                key=f'deep_{sid}_{wi:03d}';self.state['current_work_unit']=key;self._save()
                for bar in self._unit(key,aid,sid,int(full[sid].get('digits',5)),start_ms,end_ms,item['development_start_utc'],self.frozen['development_end_utc']):
                    old=combined.get(bar['time_utc'])
                    if old is not None and old != bar:raise CaptureContractError('conflicting cross-window M5 duplicate')
                    combined[bar['time_utc']]=bar
            path=self.bundle/'raw'/f'{sid}_M5.csv';path.parent.mkdir(exist_ok=True)
            bars=[combined[k] for k in sorted(combined)]
            validate_rows(bars,item['development_start_utc'],self.frozen['development_end_utc'])
            _write_rows(path,bars,'w'); meta=_inspect_csv(path)
            results.append({'broker_symbol':item['broker_symbol'],'symbol_id':sid,
                            'file':path.relative_to(self.bundle).as_posix(),
                            'development_start_utc':item['development_start_utc'],**meta})
            self.state['completed_symbols']=index;self._save()
            self.progress(f'[SERIES {index}/{len(self.delta)}] {item["broker_symbol"]}: {len(bars)} authentic M5 rows')
        payload={'schema':SCHEMA,'status':'CAPTURE_COMPLETE','plan_sha256':self.plan_sha,
                 'selected_identity_manifest_sha256':manifest['sha256'],
                 'frozen_primary_core_sha256':self.frozen['sha256'],
                 'account_fingerprint_sha256':self.plan['account_fingerprint_sha256'],
                 'source_environment':self.plan['source_environment'] if 'source_environment' in self.plan else 'Pepperstone - Europe LIVE',
                 'resolution':'M5','classification':'DEVELOPMENT_ONLY',
                 'development_end_utc':self.frozen['development_end_utc'],'series':results,
                 'total_m5_rows':sum(x['row_count'] for x in results),
                 'protected_forward_opened':False,'economic_outcomes_opened':0,
                 'orders_placed':False,'account_mutation':False}
        payload_path=self.bundle/'V3_CAPTURE_PAYLOAD.json';atomic_write_json(payload_path,payload)
        provenance=build_capture_manifest(capture_session_id='research-core-v3-delta-'+self.frozen['sha256'][:16],
            capture_schema=SCHEMA,tool_version='FROZEN_HIGH_QUALITY_DELTA_V3',
            account_fingerprint=self.plan['account_fingerprint_sha256'],
            source_environment='Pepperstone - Europe LIVE',
            capture_start_utc=min(x['development_start_utc'] for x in self.delta),
            capture_end_utc=self.frozen['development_end_utc'],completion_state='COMPLETE',
            canonical_payloads={'V3_CAPTURE_PAYLOAD.json':payload_path.read_bytes()},
            original_collector_package_sha256=self.config.get('collector_package_sha256'),
            read_only_assertion=True,economic_outcomes_opened=0,orders_placed=False,
            account_mutation=False,protected_evidence_opened=False)
        atomic_write_json(self.bundle/'CAPTURE_MANIFEST.json',provenance)
        (self.bundle/'CHECKSUMS.sha256').write_text(''.join(f'{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}\n' for p in sorted(self.bundle.rglob('*')) if p.is_file() and p.name!='CHECKSUMS.sha256'))
        scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])
        digest=_deterministic_zip(self.bundle,self.zip_path)
        self.state['phase']='CAPTURE_COMPLETE';self._save()
        self.progress(f'CAPTURE_COMPLETE final_zip_path={self.zip_path} final_zip_sha256={digest} selected_identity_count={len(self.delta)} total_M5_rows={payload["total_m5_rows"]} integrity_status=PASS')
