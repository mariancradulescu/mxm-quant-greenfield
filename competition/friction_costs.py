"""Type-aware cTrader commission/friction helpers for ultra-fast competition discovery.

Official Open API semantics bound here:
- ProtoOACommissionType 1 USD_PER_MILLION_USD, 2 USD_PER_LOT,
  3 PERCENTAGE_OF_VALUE, 4 QUOTE_CCY_PER_LOT.
- preciseTradingCommissionRate scale: 1e8 for non-percentage; 1e5 for percentage.
- ProtoOAMinCommissionType 1 CURRENCY, 2 QUOTE_CURRENCY.
- preciseMinCommission scale: 1e8.

Historical currency conversion is supplied by the capture runtime from official
ProtoOASymbolsForConversionReq chains and same-window historical BID/ASK evidence.
This module never substitutes a current rate for a historical friction window.
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


def _currency_amount_to_quote_price_equivalent(
    amount: float,
    *,
    currency: str | None,
    quote_asset: str | None,
    base_units: float,
    currency_to_quote_rates: Mapping[str,float] | None,
) -> Conversion:
    if amount==0:
        return Conversion(0.0,"RESOLVED_ZERO")
    if not currency or not quote_asset or base_units<=0:
        return Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"missing currency/quote/volume context")
    c=currency.upper();q=quote_asset.upper()
    if c==q:
        return Conversion(amount/base_units,"RESOLVED_IN_QUOTE")
    rates={str(k).upper():float(v) for k,v in (currency_to_quote_rates or {}).items() if v is not None}
    rate=rates.get(c)
    if rate is None or rate<=0:
        return Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,f"missing causal historical {c}->{q} conversion")
    return Conversion(amount*rate/base_units,"RESOLVED_VIA_BROKER_NATIVE_HISTORICAL_CONVERSION_CHAIN")


def required_conversion_currencies(
    full_symbol: Mapping[str,Any],
    light_symbol: Mapping[str,Any],
    asset_names: Mapping[str,str],
) -> set[str]:
    """Currencies that must be convertible into the symbol quote currency for commission."""
    out=set()
    quote=(asset_names.get(str(light_symbol.get("quoteAssetId"))) or "").upper()
    base=(asset_names.get(str(light_symbol.get("baseAssetId"))) or "").upper()
    rate_raw=int(full_symbol.get("preciseTradingCommissionRate") or 0)
    try: ctype=int(full_symbol.get("commissionType")) if full_symbol.get("commissionType") is not None else None
    except (TypeError,ValueError): ctype=None
    if rate_raw:
        if ctype in (1,2):
            if quote!="USD":
                out.add("USD")
            if ctype==1 and base!="USD":
                # USD_PER_MILLION_USD requires base-volume conversion into USD notional.
                out.add("__BASE_TO_USD__")
        elif ctype not in (3,4):
            out.add("__UNSUPPORTED_COMMISSION_TYPE__")
    min_raw=int(full_symbol.get("preciseMinCommission") or 0)
    if min_raw:
        try: mtype=int(full_symbol.get("minCommissionType")) if full_symbol.get("minCommissionType") is not None else None
        except (TypeError,ValueError): mtype=None
        if mtype==1:
            asset=str(full_symbol.get("minCommissionAsset") or "").upper()
            if asset and asset!=quote:
                out.add(asset)
        elif mtype not in (2,):
            out.add("__UNSUPPORTED_MIN_COMMISSION_TYPE__")
    return out


def type_aware_roundtrip_commission(
    full_symbol: Mapping[str,Any],
    light_symbol: Mapping[str,Any],
    asset_names: Mapping[str,str],
    *,
    mid: float | None,
    min_volume_cents: int,
    currency_to_quote_rates: Mapping[str,float] | None = None,
    base_to_usd_rate: float | None = None,
    conversion_evidence: Mapping[str,Any] | None = None,
) -> dict[str,Any]:
    """Minimum-volume open+close commission in symbol quote-price units when resolvable."""
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
    rate_conv=Conversion(0.0,"RESOLVED_ZERO")

    if rate_raw!=0:
        if ctype in (1,2,4):
            rate_real=rate_raw/1e8
        elif ctype==3:
            rate_real=rate_raw/1e5
        else:
            rate_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,f"unsupported commissionType={ctype_raw}")

        if ctype==1:
            if not mid or mid<=0 or base_units<=0:
                rate_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"USD_PER_MILLION_USD missing mid/volume")
            else:
                b=(base_asset or "").upper()
                if b=="USD":
                    usd_notional=base_units
                elif base_to_usd_rate is not None and base_to_usd_rate>0:
                    usd_notional=base_units*base_to_usd_rate
                else:
                    usd_notional=None
                if usd_notional is None:
                    rate_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"USD_PER_MILLION_USD missing causal base->USD historical conversion")
                else:
                    usd_fee=rate_real*(usd_notional/1_000_000.0)
                    rate_conv=_currency_amount_to_quote_price_equivalent(
                        usd_fee,currency="USD",quote_asset=quote_asset,base_units=base_units,
                        currency_to_quote_rates=currency_to_quote_rates,
                    )
        elif ctype==2:
            if lots is None:
                rate_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"USD_PER_LOT missing lotSize")
            else:
                rate_conv=_currency_amount_to_quote_price_equivalent(
                    rate_real*lots,currency="USD",quote_asset=quote_asset,base_units=base_units,
                    currency_to_quote_rates=currency_to_quote_rates,
                )
        elif ctype==3:
            if not mid or mid<=0 or base_units<=0:
                rate_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"PERCENTAGE_OF_VALUE missing mid/volume")
            else:
                quote_notional=base_units*mid
                quote_fee=quote_notional*(rate_real/100.0)
                rate_conv=Conversion(quote_fee/base_units,"RESOLVED_PERCENTAGE_OF_QUOTE_NOTIONAL")
        elif ctype==4:
            if lots is None:
                rate_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,"QUOTE_CCY_PER_LOT missing lotSize")
            else:
                rate_conv=Conversion((rate_real*lots)/base_units,"RESOLVED_QUOTE_CCY_PER_LOT")

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
            min_conv=_currency_amount_to_quote_price_equivalent(
                min_real,currency=quote_asset,quote_asset=quote_asset,base_units=base_units,
                currency_to_quote_rates=currency_to_quote_rates,
            )
        elif mtype==1:
            min_conv=_currency_amount_to_quote_price_equivalent(
                min_real,currency=str(min_asset) if min_asset else None,quote_asset=quote_asset,
                base_units=base_units,currency_to_quote_rates=currency_to_quote_rates,
            )
        else:
            min_conv=Conversion(None,COMMISSION_CONVERSION_UNRESOLVED,f"unsupported minCommissionType={mtype_raw}")

    unresolved=[x.reason for x in (rate_conv,min_conv) if x.price_equivalent is None]
    if unresolved:
        confidence=COMMISSION_CONVERSION_UNRESOLVED
        one_side=None;roundtrip=None
    else:
        confidence=FULL_FRICTION_RESOLVED
        one_side=max(float(rate_conv.price_equivalent or 0.0),float(min_conv.price_equivalent or 0.0))
        roundtrip=2.0*one_side

    pnl_raw=int(full_symbol.get("pnlConversionFeeRate") or 0)
    if pnl_raw and confidence==FULL_FRICTION_RESOLVED:
        confidence=SPREAD_RESOLVED_COMMISSION_BOUNDED

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
        "one_side_rate_commission_price_equivalent":rate_conv.price_equivalent,
        "one_side_min_commission_price_equivalent":min_conv.price_equivalent,
        "one_side_effective_commission_price_equivalent":one_side,
        "roundtrip_commission_price_equivalent":roundtrip,
        "rate_conversion_state":rate_conv.state,
        "minimum_conversion_state":min_conv.state,
        "cost_confidence_state":confidence,
        "unresolved_reasons":unresolved,
        "currency_to_quote_rates":dict(currency_to_quote_rates or {}),
        "base_to_usd_rate":base_to_usd_rate,
        "conversion_evidence":dict(conversion_evidence or {}),
        "pnl_conversion_fee_rate_raw":pnl_raw,
        "pnl_conversion_fee_rate_percent":pnl_raw*0.01,
    }
