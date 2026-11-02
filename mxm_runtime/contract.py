"""Source-blind validation contract for the new isolated MXM runtime.

No cTrader connection, token, account selection, trading, or previous first-only
workflow is touched by this module. A future collection must be a separately
admitted operation with a unique immutable id; a preflight is not admission.
"""
from __future__ import annotations
import datetime as dt
import re
import sys

SCHEMA = 'mxm.operational.readonly-authorization.v1'
EXPECTED_BROKER = 'PEPPERSTONE_EUROPE_LIVE_VIEW'
VALID_SYMBOLS = frozenset(('EURUSD', 'GBPUSD'))
CAPITAL_EUR = 200
RISK_CAP_EUR = 2
MARGIN_CAP_EUR = 80
RESERVE_FLOOR_EUR = 120
MAX_HOURS = 4
MAX_SLICES = 8
MAX_WIRE_CALLS = 3 + 1 + 1 + 1 + 2 * MAX_SLICES

def _require(test: bool, reason: str) -> None:
    if not test:
        raise ValueError('MXM_RUNTIME_CONTRACT_' + reason)

def _utc(text: str) -> dt.datetime:
    _require(isinstance(text, str) and text.endswith('Z'), 'UTC_FORMAT')
    value = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
    _require(value.utcoffset() == dt.timedelta(0), 'UTC_OFFSET')
    return value

def validate_operation(data: dict) -> dict:
    _require(type(data) is dict, 'NOT_OBJECT')
    _require(set(data) == {'schema', 'operation_id', 'authority', 'broker',
                            'symbol', 'start_utc', 'end_utc', 'slices',
                            'max_ticks', 'max_bars', 'mode', 'account_eur',
                            'risk_eur', 'margin_eur', 'reserve_eur'}, 'FIELDS')
    _require(data['schema'] == SCHEMA, 'SCHEMA')
    _require(bool(re.fullmatch(r'MXMRO-[0-9]{8}-[A-Z0-9]{8,24}', data['operation_id'])), 'ID')
    _require(data['authority'] == 'OWNER_EXPLICIT_NEW_OPERATION', 'AUTHORITY')
    _require(data['broker'] == EXPECTED_BROKER, 'BROKER')
    _require(data['mode'] == 'READ_ONLY_NO_ORDERS', 'NO_ORDERS')
    _require(data['symbol'] in VALID_SYMBOLS, 'SYMBOL')
    start, end = _utc(data['start_utc']), _utc(data['end_utc'])
    _require(start < end <= dt.datetime.now(dt.timezone.utc), 'PAST_WINDOW')
    _require((end - start) <= dt.timedelta(hours=MAX_HOURS), 'MAX_WINDOW')
    _require(start.timestamp() % 300 == 0 and end.timestamp() % 300 == 0, 'M5_ALIGNMENT')
    slices = data['slices']
    _require(type(slices) is int and 1 <= slices <= MAX_SLICES, 'SLICES')
    _require((end - start).total_seconds() % (slices * 300) == 0, 'SLICE_ALIGNMENT')
    _require(type(data['max_ticks']) is int and 100 <= data['max_ticks'] <= 100_000, 'TICK_CAP')
    _require(type(data['max_bars']) is int and 10 <= data['max_bars'] <= 4*12*24, 'BAR_CAP')
    _require(data['account_eur'] == CAPITAL_EUR, 'CAPITAL')
    _require(data['risk_eur'] == RISK_CAP_EUR, 'RISK')
    _require(data['margin_eur'] == MARGIN_CAP_EUR, 'MARGIN')
    _require(data['reserve_eur'] == RESERVE_FLOOR_EUR, 'RESERVE')
    return data

def selftest() -> None:
    operation = {
        'schema': SCHEMA, 'operation_id': 'MXMRO-20261102-PREFLIGHT',
        'authority': 'OWNER_EXPLICIT_NEW_OPERATION', 'broker': EXPECTED_BROKER,
        'symbol': 'EURUSD', 'start_utc': '2026-10-30T10:00:00Z',
        'end_utc': '2026-10-30T11:00:00Z', 'slices': 2,
        'max_ticks': 100_000, 'max_bars': 100, 'mode': 'READ_ONLY_NO_ORDERS',
        'account_eur': CAPITAL_EUR, 'risk_eur': RISK_CAP_EUR,
        'margin_eur': MARGIN_CAP_EUR, 'reserve_eur': RESERVE_FLOOR_EUR,
    }
    validate_operation(operation)
    for field, invalid in (('account_eur', 1000), ('risk_eur', 3),
                           ('margin_eur', 81), ('reserve_eur', 119),
                           ('mode', 'LIVE_ORDER'), ('broker', 'EXTERNAL')):
        bad = dict(operation, **{field: invalid})
        try:
            validate_operation(bad)
        except ValueError:
            continue
        raise AssertionError('FAIL_OPEN_' + field)
    print('MXM_RUNTIME_OFFLINE_CONTRACT_PASS no_secret_access no_orders no_historical_retry')

if __name__ == '__main__':
    _require(len(sys.argv) == 2 and sys.argv[1] == 'selftest', 'CLI')
    selftest()
