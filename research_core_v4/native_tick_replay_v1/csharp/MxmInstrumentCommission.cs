using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.Json;
namespace Mxm.Replay {
// Explicit protocol fields only; missing optional fields are NOT free trading.
public sealed record MxmCommissionTerms(long SymbolId,string QuoteAsset,int Kind,long PreciseRate,
 int MinimumKind,long PreciseMinimum,string MinimumAsset,long MinimumVolume,long MaximumVolume,long StepVolume,long LotSize) {
 public decimal Rate=>PreciseRate/(Kind==3?100000m:100000000m);
 public decimal Minimum=>PreciseMinimum/100000000m;
}
public sealed record MxmCommissionAmount(decimal BaseFee,string BaseAsset,decimal BaseFeeEur,
 decimal MinimumFee,string MinimumAsset,decimal MinimumFeeEur,decimal UnroundedFeeEur,
 bool HistoricalCostProven=false,bool BrokerChargeProven=false);
public static class MxmInstrumentCommission {
 static void Need(bool ok,string why){if(!ok)throw new ArgumentException("INSTRUMENT_COMMISSION_"+why);}
 static long Integer(JsonElement root,string key){
  Need(root.TryGetProperty(key,out var v),"MISSING_"+key);
  if(v.ValueKind==JsonValueKind.Number && v.TryGetInt64(out long n))return n;
  if(v.ValueKind==JsonValueKind.String && long.TryParse(v.GetString(),NumberStyles.AllowLeadingSign,CultureInfo.InvariantCulture,out n))return n;
  throw new ArgumentException("INSTRUMENT_COMMISSION_INTEGER_"+key);
 }
 public static bool Valid(MxmCommissionTerms? t)=>t!=null && t.SymbolId>0 &&
  !string.IsNullOrWhiteSpace(t.QuoteAsset) && t.QuoteAsset.Length<=64 &&
  t.Kind is >=1 and <=4 && t.MinimumKind is 1 or 2 && t.PreciseRate>=0 && t.PreciseMinimum>=0 &&
  !string.IsNullOrWhiteSpace(t.MinimumAsset) && t.MinimumAsset.Length<=64 &&
  (t.MinimumKind!=2 || t.MinimumAsset==t.QuoteAsset) && t.MinimumVolume>0 &&
  t.MaximumVolume>=t.MinimumVolume && t.StepVolume>0 && t.MinimumVolume%t.StepVolume==0 && t.LotSize>0;
 public static MxmCommissionTerms Decode(JsonElement full,long expectedSymbolId,string quoteAsset){
  Need(expectedSymbolId>0 && Integer(full,"symbolId")==expectedSymbolId,"SYMBOL_IDENTITY");
  int kind=checked((int)Integer(full,"commissionType")),minimumKind=checked((int)Integer(full,"minCommissionType"));
  string asset=quoteAsset;
  if(minimumKind==1){
   Need(full.TryGetProperty("minCommissionAsset",out var a) && a.ValueKind==JsonValueKind.String,"MISSING_MINIMUM_ASSET");asset=a.GetString()!;
  }
  var t=new MxmCommissionTerms(expectedSymbolId,quoteAsset,kind,Integer(full,"preciseTradingCommissionRate"),minimumKind,
   Integer(full,"preciseMinCommission"),asset,Integer(full,"minVolume"),Integer(full,"maxVolume"),Integer(full,"stepVolume"),Integer(full,"lotSize"));
  Need(Valid(t),"INVALID_OR_UNRESOLVED_TERMS");return t;
 }
 // One hypothetical executed fill. Rates are explicit, already-admitted COST-side
 // EUR per currency, and NOT inferred from a symbol name or defaulted to unity.
 // No broker rounding, funding, spread, slippage, margin or PnL fee is invented.
 public static MxmCommissionAmount Price(MxmCommissionTerms t,long volumeCents,decimal fillPrice,
  decimal? notionalUsdPerQuote,IReadOnlyDictionary<string,decimal> costEurPerAsset){
  Need(Valid(t),"TERMS");Need(volumeCents>=t.MinimumVolume && volumeCents<=t.MaximumVolume && volumeCents%t.StepVolume==0,"VOLUME_LATTICE");
  Need(fillPrice>0 && costEurPerAsset!=null,"FILL_OR_FX");
  decimal units=volumeCents/100m,lots=(decimal)volumeCents/t.LotSize;decimal fee;string asset;
  checked {
   switch(t.Kind){
    case 1:Need(notionalUsdPerQuote.HasValue && notionalUsdPerQuote>0,"USD_NOTIONAL_CONVERSION_REQUIRED");fee=units*fillPrice*notionalUsdPerQuote!.Value*t.Rate/1000000m;asset="USD";break;
    case 2:fee=lots*t.Rate;asset="USD";break;
    case 3:fee=units*fillPrice*t.Rate/100m;asset=t.QuoteAsset;break;
    case 4:fee=lots*t.Rate;asset=t.QuoteAsset;break;
    default:throw new ArgumentException("INSTRUMENT_COMMISSION_KIND");
   }
   decimal Convert(decimal amount,string currency){
    if(amount==0)return 0m; // Only an explicitly observed zero rate/minimum.
    Need(costEurPerAsset!.TryGetValue(currency,out var rate) && rate>0,"MISSING_COST_SIDE_FX_"+currency);return amount*rate;
   }
   decimal baseEur=Convert(fee,asset),minimumEur=Convert(t.Minimum,t.MinimumAsset);
   return new(fee,asset,baseEur,t.Minimum,t.MinimumAsset,minimumEur,Math.Max(baseEur,minimumEur));
  }
 }
}
}
