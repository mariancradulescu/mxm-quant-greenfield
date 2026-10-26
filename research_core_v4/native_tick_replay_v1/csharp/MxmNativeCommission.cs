using System;
namespace Mxm.Replay {
/// <summary>
/// Current cTrader Symbol commission estimate in EUR, for one requested
/// volume and contemporaneous bid/ask. Type IDs follow SymbolCommissionType
/// (0..3), minimum IDs follow SymbolMinCommissionType (0..1).
/// Conversion inputs must be obtained from actual AssetConverter observations.
/// This is NOT an exact broker fee, a bound on future execution, or an
/// historical commission receipt. Never default required FX to unity.
/// </summary>
public sealed record MxmNativeCommissionTerms(int Type,int MinimumType,
 string QuoteAsset,string MinimumAsset,decimal Commission,decimal Minimum,
 decimal LotSize);
public sealed record MxmNativeCommissionEstimate(
 decimal BuyEur,decimal SellEur,decimal PerSideCeilingEur,decimal RoundTripReserveEur,
 string Classification="CURRENT_NATIVE_SYMBOL_FEE_ESTIMATE_NOT_BROKER_CHARGE");
public static class MxmNativeCommission {
 static void Need(bool ok,string why){if(!ok)throw new ArgumentException("MXM_NATIVE_COMMISSION_"+why);}
 public static MxmNativeCommissionEstimate Price(MxmNativeCommissionTerms terms,
  decimal units,decimal bid,decimal ask,decimal quoteToUsd,
  decimal usdToEur,decimal quoteToEur,decimal minimumAssetToEur) {
  Need(terms!=null && terms.Type>=0 && terms.Type<=3 &&
   terms.MinimumType>=0 && terms.MinimumType<=1 &&
   !string.IsNullOrWhiteSpace(terms.QuoteAsset) &&
   !string.IsNullOrWhiteSpace(terms.MinimumAsset) &&
   terms.LotSize>0m && terms.Commission>=0m && terms.Minimum>=0m &&
   units>0m && bid>0m && ask>=bid,"TERMS_VOLUME_OR_BOOK");
  try {
   checked {
    if(terms.Commission>0m) {
     if(terms.Type==0)Need(quoteToUsd>0m && usdToEur>0m,"USD_NOTIONAL_COST_FX");
     if(terms.Type==1)Need(usdToEur>0m,"USD_LOT_COST_FX");
     if(terms.Type>=2)Need(quoteToEur>0m,"QUOTE_COST_FX");
    }
    if(terms.Minimum>0m)
     Need(terms.MinimumType==0?minimumAssetToEur>0m:quoteToEur>0m,"MINIMUM_COST_FX");
    decimal minimum=terms.Minimum*(terms.MinimumType==0?minimumAssetToEur:quoteToEur);
    decimal OneSide(decimal price) {
     decimal baseEur=terms.Type switch {
      0=>terms.Commission==0m?0m:units*price*quoteToUsd*terms.Commission/1000000m*usdToEur,
      1=>terms.Commission==0m?0m:units/terms.LotSize*terms.Commission*usdToEur,
      2=>terms.Commission==0m?0m:units*price*terms.Commission/100m*quoteToEur,
      3=>terms.Commission==0m?0m:units/terms.LotSize*terms.Commission*quoteToEur,
      _=>throw new ArgumentException("MXM_NATIVE_COMMISSION_TYPE")
     };
     return Math.Max(baseEur,minimum);
    }
    decimal buy=OneSide(ask),sell=OneSide(bid),ceiling=Math.Max(buy,sell);
    return new(buy,sell,ceiling,ceiling*2m);
   }
  }catch(OverflowException){throw new ArgumentException("MXM_NATIVE_COMMISSION_OVERFLOW");}
 }
}
