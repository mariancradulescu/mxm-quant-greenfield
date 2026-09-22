"""Type-aware cTrader commission/friction helpers for ultra-fast competition discovery.

Official Open API authority:
- ProtoOACommissionType 1 USD_PER_MILLION_USD, 2 USD_PER_LOT,
  3 PERCENTAGE_OF_VALUE, 4 QUOTE_CCY_PER_LOT.
- preciseTradingCommissionRate scale: 1e8 for non-percentage; 1e5 for percentage.
- ProtoOAMinCommissionType 1 CURRENCY, 2 QUOTE_CURRENCY.
- preciseMinCommission scale: 1e8.

This module is structural/friction evidence only. It does not open candidate alpha outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

FULL_FRICTION_RESOLVED="FULL_FRICTION_RESOLVED"
SPREAD_RESOLVED_COMMISSION_BOUNDED="SPREAD_RESOLVED_COMMISSION_BOUNDED"
COMMISSION_CONVERSION_UNRESOLVED="COMMISSION_CONVERSION_UNRESOLVED"
FRICTION_UNRESOLVED="FRICTION_UNRESOLVED"

COMMISSION_TYPES={
    1:"USD_PER_MILLION_USD",
    2:"USD_PER_LOT",
    3:"PERCENTAGE_OF_VALUE",
    4:"QUOTE_CCY_PER_LOT",
}
MIN_COMMISSION_TYPES={1:"CURRENCY",2:"QUOTE_CURRENCY"}

@dataclass(frozen=True)
class Conversion:
    price_equivalent: float | None
    state: str
    reason: str | None = None

def _positive(value: Any) -> float | None:
    try:
        x=float(value)
    except (TypeError,ValueError):
        return None
    return x if x>0 else None

def _currency_amount_to_quote_price_equivalent(
    amount: float,
    *,
    currency: str | None,
    base_asset: str | None,
    quote_asset: str | None,
    mid: float | None,
    base_units: float,
) -> Conversion:
    if amount==0:
        return Conversion(0.0,"RESOLVED_ZERO")
    if not currency or not base_asset or not quote_asset or not mid or mid<=0 or base_units<=0:
        return Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"missing currency/base/quote/mid/volume context")
    c=currency.upper();b=base_asset.upper();q=quote_asset.upper()
    if c==q:
        return Conversion(amount/base_units,"RESOLVED_IN_QUOTE")
    if c==b:
        return Conversion(amount*mid/base_units,"RESOLVED_BASE_TO_QUOTE_VIA_SYMBOL_MID")
    if c=="USD" and q=="USD":
        return Conversion(amount/base_units,"RESOLVED_USD_IS_QUOTE")
    if c=="USD" and b=="USD":
        return Conversion(amount*mid/base_units,"RESOLVED_USD_IS_BASE")
    return Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,f"no causal direct {c}->quote conversion in sampled symbol")

def type_aware_roundtrip_commission(
    full_symbol: Mapping[str,Any],
    light_symbol: Mapping[str,Any],
    asset_names: Mapping[str,str],
    *,
    mid: float | None,
    min_volume_cents: int,
) -> dict[str,Any]:
    """Return minimum-volume round-trip commission in symbol-price units when resolvable.

    Volume and lotSize are protocol cents. One side is computed first, minimum commission
    is applied per trade side, then doubled for an open+close round trip.
    """
    base_units=float(min_volume_cents)/100.0
    lot_size_cents=int(full_symbol.get("lotSize") or 0)
    lots=(float(min_volume_cents)/lot_size_cents) if lot_size_cents>0 else None
    base_asset=asset_names.get(str(light_symbol.get("baseAssetId")))
    quote_asset=asset_names.get(str(light_symbol.get("quoteAssetId")))

    ctype_raw=full_symbol.get("commissionType")
    try: ctype=int(ctype_raw) if ctype_raw is not None else None
    except (TypeError,ValueError): ctype=None
    rate_raw=int(full_symbol.get("preciseTradingCommissionRate") or 0)
    ctype_name=COMMISSION_TYPES.get(ctype)
    rate_real=None
    base_conv=Conversion(0.0,"RESOLVED_ZERO")

    if rate_raw!=0:
        if ctype in (1,2,4):
            rate_real=rate_raw/1e8
        elif ctype==3:
            rate_real=rate_raw/1e5
        else:
            base_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,f"unsupported commissionType={ctype_raw}")
        if ctype==1:
            if not mid or mid<=0 or base_units<=0:
                base_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"USD_PER_MILLION_USD missing mid/volume")
            elif (base_asset or "").upper()=="USD":
                usd_notional=base_units
                usd_fee=rate_real*(usd_notional/1_000_000.0)
                base_conv=_currency_amount_to_quote_price_equivalent(usd_fee,currency="USD",base_asset=base_asset,quote_asset=quote_asset,mid=mid,base_units=base_units)
            elif (quote_asset or "").upper()=="USD":
                usd_notional=base_units*mid
                usd_fee=rate_real*(usd_notional/1_000_000.0)
                base_conv=_currency_amount_to_quote_price_equivalent(usd_fee,currency="USD",base_asset=base_asset,quote_asset=quote_asset,mid=mid,base_units=base_units)
            else:
                base_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"USD_PER_MILLION_USD requires a causal USD notional conversion for cross")
        elif ctype==2:
            if lots is None:
                base_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"USD_PER_LOT missing lotSize")
            else:
                base_conv=_currency_amount_to_quote_price_equivalent(rate_real*lots,currency="USD",base_asset=base_asset,quote_asset=quote_asset,mid=mid,base_units=base_units)
        elif ctype==3:
            if not mid or mid<=0 or base_units<=0:
                base_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"PERCENTAGE_OF_VALUE missing mid/volume")
            else:
                # rate_real is percentage units, e.g. 0.005 means 0.005%.
                quote_notional=base_units*mid
                quote_fee=quote_notional*(rate_real/100.0)
                base_conv=Conversion(quote_fee/base_units,"RESOLVED_PERCENTAGE_OF_QUOTE_NOTIONAL")
        elif ctype==4:
            if lots is None:
                base_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"QUOTE_CCY_PER_LOT missing lotSize")
            else:
                quote_fee=rate_real*lots
                base_conv=Conversion(quote_fee/base_units,"RESOLVED_QUOTE_CCY_PER_LOT")

    min_raw=int(full_symbol.get("preciseMinCommission") or 0)
    min_real=min_raw/1e8
    mtype_raw=full_symbol.get("minCommissionType")
    try: mtype=int(mtype_raw) if mtype_raw is not None else None
    except (TypeError,ValueError): mtype=None
    mtype_name=MIN_COMMISSION_TYPES.get(mtype)
    min_asset=full_symbol.get("minCommissionAsset")
    min_conv=Conversion(0.0,"RESOLVED_ZERO")
    if min_raw!=0:
        if mtype==2:
            min_conv=_currency_amount_to_quote_price_equivalent(min_real,currency=quote_asset,base_asset=base_asset,quote_asset=quote_asset,mid=mid,base_units=base_units)
        elif mtype==1:
            min_conv=_currency_amount_to_quote_price_equivalent(min_real,currency=str(min_asset) if min_asset else None,base_asset=base_asset,quote_asset=quote_asset,mid=mid,base_units=base_units)
        else:
            min_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,f"unsupported minCommissionType={mtype_raw}")

    unresolved=[x.reason for x in (base_conv,min_conv) if x.price_equivalent is None]
    if unresolved:
        confidence=COMMISSION_CONVERSION_UNRESOLVED
        one_side=None
        roundtrip=None
    else:
        confidence=FULL_FRICTION_RESOLVED
        one_side=max(float(base_conv.price_equivalent or 0.0),float(min_conv.price_equivalent or 0.0))
        roundtrip=2.0*one_side

    pnl_raw=int(full_symbol.get("pnlConversionFeeRate") or 0)
    return {
        "commission_type_raw":ctype_raw,
        "commission_type":ctype_name or ("ZERO_RATE_TYPE_NOT_REQUIRED" if rate_raw==0 else "UNSUPPORTED"),
        "precise_trading_commission_rate_raw":rate_raw,
        "precise_trading_commission_rate":rate_real if rate_raw!=0 else 0.0,
        "trading_commission_scale":100_000 if ctype==3 else 100_000_000,
        "min_commission_type_raw":mtype_raw,
        "min_commission_type":mtype_name or ("ZERO_MINIMUM_TYPE_NOT_REQUIRED" if min_raw==0 else "UNSUPPORTED"),
        "precise_min_commission_raw":min_raw,
        "precise_min_commission":min_real,
        "min_commission_asset":min_asset,
        "base_asset":base_asset,
        "quote_asset":quote_asset,
        "base_units_at_min_volume":base_units,
        "lots_at_min_volume":lots,
        "one_side_rate_commission_price_equivalent":base_conv.price_equivalent,
        "one_side_min_commission_price_equivalent":min_conv.price_equivalent,
        "one_side_effective_commission_price_equivalent":one_side,
        "roundtrip_commission_price_equivalent":roundtrip,
        "rate_conversion_state":base_conv.state,
        "minimum_conversion_state":min_conv.state,
        "cost_confidence_state":confidence,
        "unresolved_reasons":unresolved,
        "pnl_conversion_fee_rate_raw":pnl_raw,
        "pnl_conversion_fee_rate_percent":pnl_raw*0.01,
    }
