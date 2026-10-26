using Mxm.Replay;
namespace Mxm.Research;
// Consume the EXISTING paired source clock in its EUR-only mode. No new clock,
// funding, signal, fill, interpolation, or assertion of historical executability.
public static class MxmEurAccountInput {
 static DateTime Utc(long ms)=>DateTimeOffset.FromUnixTimeMilliseconds(ms).UtcDateTime;
 public static string SourceCode(AlignedUsdSnapshot s){
  if(s.Purpose!="FX_VALUATION_ONLY" || s.GbpBidRaw.HasValue || s.GbpAskRaw.HasValue ||
     s.GbpBidMs.HasValue || s.GbpAskMs.HasValue)throw new ArgumentException("EUR_BOOK_REQUIRES_ISOLATED_EUR_SOURCE");
  if(s.FxBidRaw is null || s.FxAskRaw is null || s.FxBidMs is null || s.FxAskMs is null)return "SOURCE_MISSING_OR_CONFLICT";
  if(s.FxBidRaw<=0 || s.FxAskRaw<=0 || s.FxBidMs>s.T || s.FxAskMs>s.T || s.FxBidMs<0 || s.FxAskMs<0)
   throw new ArgumentException("EUR_BOOK_INVALID_VALUES_OR_FUTURE_SOURCE");
  if(s.FxAskRaw<s.FxBidRaw)return "SOURCE_CROSSED";
  if(s.T-s.FxBidMs>MxmUsdPairAlignment.MaxAgeMs || s.T-s.FxAskMs>MxmUsdPairAlignment.MaxAgeMs)return "SOURCE_AGE_LIMIT";
  if(Math.Max(s.FxBidMs.Value,s.FxAskMs.Value)!=s.T)throw new ArgumentException("EUR_BOOK_NO_CURRENT_OBSERVATION");
  return s.FxAskRaw==s.FxBidRaw?"OBSERVED_LOCKED":"OBSERVED_POSITIVE_SPREAD";
 }
 public static MxmAccountFeed FromAlignment(AlignedUsdSnapshot s,MxmUsdAccountAssumptions a){
  if(a==null || a.Units<=0 || a.MarginEur<=0 || a.CommissionPerSideEur<0 || a.SlippageQuote<0 ||
     a.EstimatedStopRiskEur<=0 || a.StopDistanceQuote<=0)throw new ArgumentException("EUR_BOOK_EXPLICIT_MODEL_ASSUMPTIONS_REQUIRED");
  string code=SourceCode(s);var time=Utc(s.T);
  if(!code.StartsWith("OBSERVED_",StringComparison.Ordinal))return new MxmInstrumentQuoteUnavailable(time,"EURUSD",code);
  decimal bid=s.FxBidRaw!.Value/100000m,ask=s.FxAskRaw!.Value/100000m;
  return new MxmQuote(time,"EURUSD",bid,ask,1m/ask,a.Units,a.MarginEur,a.CommissionPerSideEur,
   a.SlippageQuote,a.EstimatedStopRiskEur,1m/bid,StopDistanceQuote:a.StopDistanceQuote,
   BidSourceUtc:Utc(s.FxBidMs!.Value),AskSourceUtc:Utc(s.FxAskMs!.Value));
 }
}
