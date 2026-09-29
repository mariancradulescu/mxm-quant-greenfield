"""Hash-bound ingestion of the authenticated full-frontier development capture."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

from .model import Bar, Series, _dt


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_capture(path: Path):
    """Return validated series and frontier quality rows; reject partial captures."""
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError("duplicate ZIP names or CRC failure")

        def read(name):
            data = archive.read(name)
            copies = [n for n in names if n.endswith('/' + name) and n != name]
            for duplicate in copies:
                if archive.read(duplicate) != data:
                    raise ValueError(f"conflicting ZIP copy: {name}")
            return data

        manifest = json.loads(read('CAPTURE_MANIFEST.json'))
        payload_bytes = read('V3_CAPTURE_PAYLOAD.json')
        payload = json.loads(payload_bytes)
        identities = json.loads(read('SELECTED_IDENTITY_MANIFEST.json'))
        quality = json.loads(read('DATA_QUALITY_TABLE.json'))['rows']
        checksums = read('CHECKSUMS.sha256').decode('ascii').splitlines()
        for line in checksums:
            digest, name = line.split('  ', 1)
            if _sha(read(name)) != digest:
                raise ValueError(f'capture checksum mismatch: {name}')
        if manifest['sha256_per_canonical_payload']['V3_CAPTURE_PAYLOAD.json'] != _sha(payload_bytes):
            raise ValueError('payload hash mismatch')
        identity_sha = identities.pop('sha256')
        if _sha(json.dumps(identities,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()) != identity_sha:
            raise ValueError('selected identity manifest hash mismatch')
        identities['sha256'] = identity_sha
        if (manifest['completion_state'] != 'COMPLETE' or
                payload['status'] != 'CAPTURE_COMPLETE' or
                payload['source_environment'] != manifest['source_environment'] or
                payload['selected_identity_manifest_sha256'] != identities['sha256'] or
                payload['plan_sha256'] != identities['plan_sha256'] or
                manifest['protected_evidence_opened'] or payload['protected_forward_opened'] or
                manifest['orders_placed'] or payload['orders_placed']):
            raise ValueError('incomplete or unsafe capture')
        if len(quality) != 1576 or len({q['symbol_id'] for q in quality}) != 1576:
            raise ValueError('frontier identity integrity failure')
        selected = {int(x['symbol_id']): x for x in identities['symbols']}
        if len(selected) != len(identities['symbols']):
            raise ValueError('duplicate selected identity')
        result = []
        zip_sha = _sha(path.read_bytes())
        for item in payload['series']:
            sid = int(item['symbol_id'])
            if sid not in selected or selected[sid]['broker_symbol'] != item['broker_symbol']:
                raise ValueError('broker identity mismatch')
            data = read(item['file'])
            if _sha(data) != item['sha256']:
                raise ValueError(f"series hash mismatch: {sid}")
            bars = []
            for row in csv.DictReader(io.StringIO(data.decode('utf-8-sig'))):
                ts = _dt(row['time_utc'])
                o, h, l, c, v = (float(row[k]) for k in ('open','high','low','close','tick_volume'))
                if not all(map(math.isfinite,(o,h,l,c,v))) or h < max(o,c) or l > min(o,c) or h < l or v < 0:
                    raise ValueError(f"invalid OHLC: {sid}")
                if ts.minute % 5 or ts.second or ts.microsecond or (bars and (ts <= bars[-1].ts or (ts - bars[-1].ts).total_seconds() % 300)):
                    raise ValueError(f"nonmonotone M5 grid: {sid}")
                if ts >= _dt(identities['protected_forward_start']):
                    raise ValueError('protected forward opened')
                bars.append(Bar(ts,o,h,l,c,v))
            if (len(bars) != item['row_count'] or not bars or
                    bars[0].ts != _dt(item['first_timestamp_utc']) or
                    bars[-1].ts != _dt(item['last_timestamp_utc'])):
                raise ValueError(f"series metadata mismatch: {sid}")
            result.append(Series(item['broker_symbol'],sid,f"{zip_sha}!{item['file']}",tuple(bars)))
        if len(result) != len(selected) or sum(len(s.bars) for s in result) != payload['total_m5_rows']:
            raise ValueError('selected series count mismatch')
        return result, quality, payload
