using Mxm.Replay;
namespace Mxm.Research;
// Explicit MODEL assumptions, not broker/historical terms. No defaults/funding.
public sealed record MxmUsdAccountAssumptions(decimal Units,decimal MarginEur,
 decimal CommissionPerSideEur,decimal SlippageQuote,decimal EstimatedStopRiskEur,decimal StopDistanceQuote);
public static class MxmUsdPairAccountInput {
 static void Need(bool ok,string why){if(!ok)throw new ArgumentException("USD_ACCOUNT_INPUT_"+why);}
 static DateTime Utc(long ms)=>DateTimeOffset.FromUnixTimeMilliseconds(ms).UtcDateTime;
 public static MxmAccountFeed FromGbpAlignment(AlignedUsdSnapshot s,MxmUsdAccountAssumptions a){
  Need(a.Units>0 && a.MarginEur>0 && a.CommissionPerSideEur>=0 && a.SlippageQuote>=0 &&
   a.EstimatedStopRiskEur>0 && a.StopDistanceQuote>0,"EXPLICIT_MODEL_ASSUMPTIONS_REQUIRED");
  bool Fx(bool strict)=>s.FxBidRaw>0 && s.FxAskRaw>=s.FxBidRaw && s.FxBidMs.HasValue && s.FxAskMs.HasValue &&
   s.FxBidMs<=s.T && s.FxAskMs<=s.T && (!strict || s.FxBidMs<s.T && s.FxAskMs<s.T) &&
   s.T-s.FxBidMs<=5000 && s.T-s.FxAskMs<=5000;
  if(s.Purpose=="FX_VALUATION_ONLY"){
   if(!Fx(false))return new MxmUsdConversionUnavailable(Utc(s.T),"INVALID_TYPED_FX_VALUATION");
   Need(Math.Max(s.FxBidMs!.Value,s.FxAskMs!.Value)==s.T,"VALUATION_REQUIRES_NEW_FX_OBSERVATION");
   return new MxmUsdEurMark(Utc(s.T),Utc(s.FxBidMs.Value),Utc(s.FxAskMs.Value),s.FxBidRaw!.Value/100000m,s.FxAskRaw!.Value/100000m);
  }
  Need(s.Purpose=="GBP_QUOTE_GROUP","TYPED_PURPOSE");
  if(s.Code.StartsWith("FX_",StringComparison.Ordinal))return new MxmUsdConversionUnavailable(Utc(s.T),s.Code);
  if(s.Code.StartsWith("GBP_",StringComparison.Ordinal))return new MxmInstrumentQuoteUnavailable(Utc(s.T),"GBPUSD",s.Code);
  Need(s.Code=="READY_STRICT_PRIOR_FX" && Fx(true) && s.GbpBidRaw>0 && s.GbpAskRaw>=s.GbpBidRaw &&
   s.GbpBidMs.HasValue && s.GbpAskMs.HasValue && s.GbpBidMs<=s.T && s.GbpAskMs<=s.T &&
   s.T-s.GbpBidMs<=5000 && s.T-s.GbpAskMs<=5000,"READY_SNAPSHOT_VALUES_OR_CLOCKS");
  decimal fxBid=s.FxBidRaw!.Value/100000m,fxAsk=s.FxAskRaw!.Value/100000m;
  return new MxmQuote(Utc(s.T),"GBPUSD",s.GbpBidRaw!.Value/100000m,s.GbpAskRaw!.Value/100000m,
   1m/fxAsk,a.Units,a.MarginEur,a.CommissionPerSideEur,a.SlippageQuote,a.EstimatedStopRiskEur,
   1m/fxBid,StopDistanceQuote:a.StopDistanceQuote,BidSourceUtc:Utc(s.GbpBidMs!.Value),AskSourceUtc:Utc(s.GbpAskMs!.Value));
 }
}
