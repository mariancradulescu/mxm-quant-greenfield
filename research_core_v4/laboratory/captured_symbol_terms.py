"""Decode an already-authenticated SymbolById snapshot, never historical terms.

Open API volumes and lot sizes are in hundredths of units. Optional protobuf
defaults are not observed evidence. Absent fees must not become free trading.
https://help.ctrader.com/open-api/model-messages/#protooasymbol
"""
from decimal import Decimal
import hashlib
import math


def captured_symbol_terms(symbol, modeled_units=Decimal('1000')):
    if not symbol.IsInitialized() or symbol.symbolId != 1:
        raise ValueError('CAPTURED_TERMS_INVALID_EURUSD_METADATA')
    units = Decimal(str(modeled_units))
    if not units.is_finite() or units <= 0 or units * 100 != (units * 100).to_integral_value():
        raise ValueError('CAPTURED_TERMS_VOLUME_NOT_EXACT_CENTS')
    raw = {}
    fields = ('digits', 'pipPosition', 'minVolume', 'maxVolume', 'stepVolume', 'lotSize',
              'commissionType', 'preciseTradingCommissionRate', 'preciseMinCommission',
              'minCommissionType', 'minCommissionAsset', 'pnlConversionFeeRate',
              'leverageId', 'swapLong', 'swapShort', 'swapCalculationType',
              'swapPeriod', 'swapTime', 'swapRollover3Days', 'scheduleTimeZone',
              'tradingMode', 'enableShortSelling', 'slDistance', 'distanceSetIn')
    for name in fields:
        # HasField matters even for enum defaults such as ENABLED or USD.
        value = getattr(symbol, name) if symbol.HasField(name) else None
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('CAPTURED_TERMS_NONFINITE_METADATA')
        raw[name] = value
    volume_present = all(raw[k] is not None for k in ('minVolume', 'maxVolume', 'stepVolume'))
    geometry_valid = None
    on_lattice = None
    if volume_present:
        low, high, step = (raw[k] for k in ('minVolume', 'maxVolume', 'stepVolume'))
        # Certify only unambiguous zero-anchored broker volume geometry.
        geometry_valid = low > 0 and high >= low and step > 0 and low % step == 0
        if geometry_valid:
            cents = int(units * 100)
            on_lattice = low <= cents <= high and cents % step == 0
    kind, precise = raw['commissionType'], raw['preciseTradingCommissionRate']
    rate = None
    rate_unit = None
    if precise is not None:
        if precise < 0:
            raise ValueError('CAPTURED_TERMS_NEGATIVE_COMMISSION')
        if kind in (1, 2):
            rate = str(Decimal(precise) / Decimal(10**8))
            rate_unit = 'USD_PER_MILLION_USD' if kind == 1 else 'USD_PER_LOT'
        elif kind == 3:
            rate = str(Decimal(precise) / Decimal(10**5))
            rate_unit = 'PERCENT_OF_VALUE_NOT_FRACTION'
    minimum = raw['preciseMinCommission']
    if minimum is not None and minimum < 0:
        raise ValueError('CAPTURED_TERMS_NEGATIVE_MINIMUM_COMMISSION')
    minimum_amount = str(Decimal(minimum)/Decimal(10**8)) if minimum is not None else None
    # A numeric amount alone is insufficient: asset/type presence is separate.
    minimum_semantics_known = (minimum is not None and
        (raw['minCommissionType'] == 2 or
         (raw['minCommissionType'] == 1 and bool(raw['minCommissionAsset']))))
    return {
        'schema': 'mxm.captured-native-symbol-terms.v1',
        'classification': 'DECODED_SNAPSHOT_REQUIRES_PINNED_NATIVE_CUSTODY_PROVENANCE',
        'source_authenticated_in_this_helper': False,
        'symbol_id': 1,
        'expected_symbol_name': 'EURUSD',
        'symbol_message_sha256': hashlib.sha256(symbol.SerializeToString()).hexdigest(),
        'raw_optional_fields': raw,
        'volume_wire_scale_units': 100,
        'modeled_units_checked': str(units),
        'volume_fields_present': volume_present,
        'unambiguous_volume_geometry': geometry_valid,
        'modeled_volume_on_captured_lattice': on_lattice,
        'minimum_units': str(Decimal(raw['minVolume'])/100) if raw['minVolume'] is not None else None,
        'maximum_units': str(Decimal(raw['maxVolume'])/100) if raw['maxVolume'] is not None else None,
        'step_units': str(Decimal(raw['stepVolume'])/100) if raw['stepVolume'] is not None else None,
        'lot_units': str(Decimal(raw['lotSize'])/100) if raw['lotSize'] is not None else None,
        'commission_rate': rate, 'commission_rate_unit': rate_unit,
        'minimum_commission_amount': minimum_amount,
        'minimum_commission_semantics_known': minimum_semantics_known,
        'dated_historical_volume_rules_proven': False,
        'historical_commission_proven': False,
        'account_deposit_currency_proven': False,
        'dynamic_margin_tiers_proven': False,
        'actual_fx_conversion_or_pnl_fee_charges_proven': False,
        'historical_broker_fills_proven': False,
        'new_broker_requests': 0, 'orders': 0,
    }
