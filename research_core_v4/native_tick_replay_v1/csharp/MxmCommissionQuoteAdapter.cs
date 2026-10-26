using System;
using System.Collections.Generic;
namespace Mxm.Replay {
public sealed record MxmCommissionScenario(string ScenarioSha256,string MetadataSha256,string Symbol,
 long SymbolId,MxmCommissionTerms Terms);
public sealed record MxmBoundedCommissionQuote(MxmQuote Quote,MxmCommissionAmount BuyCost,
 MxmCommissionAmount SellCost,decimal ChargedPerSideCeilingEur,string ScenarioSha256,string MetadataSha256,
 string Classification="CONSERVATIVE_CURRENT_QUOTE_FEE_SCENARIO_NOT_EXACT_BROKER_CHARGE");
// The existing account's fixed-per-quote fee channel is retained. Use the MAX
// of both modeled execution sides, never an optimistic side or a fake cashflow.
// Refuse an admitted risk reserve too small for two current-quote fee ceilings.
// Future FX/fee changes, stop gaps, and historical broker charges remain unknown.
public static class MxmCommissionQuoteAdapter {
 static void Need(bool ok,string why){if(!ok)throw new ArgumentException("COMMISSION_QUOTE_"+why);}
 static bool Digest(string value)=>value!=null && value.Length==64 &&
  System.Linq.Enumerable.All(value,c=>c is >= '0' and <= '9' or >= 'a' and <= 'f');
 static bool Utc(DateTime v)=>v.Kind==DateTimeKind.Utc && v!=default;
 public static MxmBoundedCommissionQuote Apply(MxmQuote quote,MxmCommissionScenario scenario,string admittedScenarioSha256,
  DateTime fxObservedUtc,decimal? notionalUsdPerQuote,IReadOnlyDictionary<string,decimal> costEurPerAsset,
  MxmReplayParameters parameters){
  if(quote==null || scenario==null || parameters==null || costEurPerAsset==null || scenario.Terms==null)throw new ArgumentException("COMMISSION_QUOTE_INPUTS");
  Need(Digest(admittedScenarioSha256) && scenario.ScenarioSha256==admittedScenarioSha256 && Digest(scenario.MetadataSha256),"SCENARIO_OR_METADATA_BINDING");
  Need(!string.IsNullOrWhiteSpace(scenario.Symbol) && scenario.Symbol.Length<=128 && scenario.Symbol==quote.Symbol && scenario.SymbolId==scenario.Terms.SymbolId && MxmInstrumentCommission.Valid(scenario.Terms),"SYMBOL_IDENTITY");
  Need(quote.CapturedCosts==null && quote.CommissionPerSideEur==0,"NO_MIXED_OR_ALREADY_CHARGED_COST");
  Need(Utc(quote.Utc) && quote.Bid>0 && quote.Ask>=quote.Bid && quote.SlipPerSideQuote>=0 &&
   quote.QuoteToEur>0 && quote.QuoteLossToEur.HasValue && quote.QuoteLossToEur>=quote.QuoteToEur,"QUOTE_GEOMETRY_AND_CONVERSION");
  Need(Utc(fxObservedUtc) && fxObservedUtc<=quote.Utc && (quote.Utc-fxObservedUtc).TotalMilliseconds<=5000,"FX_OBSERVATION_CLOCK");
  Need(quote.BidSourceUtc.HasValue && quote.AskSourceUtc.HasValue && Utc(quote.BidSourceUtc.Value) && Utc(quote.AskSourceUtc.Value) &&
   quote.BidSourceUtc<=quote.Utc && quote.AskSourceUtc<=quote.Utc &&
   (quote.Utc-quote.BidSourceUtc.Value).TotalMilliseconds<=5000 && (quote.Utc-quote.AskSourceUtc.Value).TotalMilliseconds<=5000,"SOURCE_SIDE_CLOCKS");
  decimal cents=quote.ExecutableUnits*100m;
  Need(cents>0 && cents<=long.MaxValue && decimal.Truncate(cents)==cents,"EXACT_VOLUME_CENTS");
  var rates=new Dictionary<string,decimal>();foreach(var pair in costEurPerAsset)rates.Add(pair.Key,pair.Value);
  Need(rates.TryGetValue(scenario.Terms.QuoteAsset,out var quoteRate) && quoteRate==quote.QuoteLossToEur!.Value,"QUOTE_COST_FX_MUST_MATCH_LOSS_MARK");
  Need(!rates.TryGetValue("EUR",out var eur) || eur==1m,"EUR_IS_DEPOSIT_UNIT");
  decimal sellPrice=quote.Bid-quote.SlipPerSideQuote,buyPrice=quote.Ask+quote.SlipPerSideQuote;
  Need(sellPrice>0 && buyPrice>=sellPrice,"MODELED_FILL_PRICE");
  var buy=MxmInstrumentCommission.Price(scenario.Terms,(long)cents,buyPrice,notionalUsdPerQuote,rates);
  var sell=MxmInstrumentCommission.Price(scenario.Terms,(long)cents,sellPrice,notionalUsdPerQuote,rates);
  decimal ceiling=Math.Max(buy.UnroundedFeeEur,sell.UnroundedFeeEur);
  Need(parameters.RoundTripRiskReserveEur>=2m*ceiling,"CURRENT_ROUNDTRIP_FEES_EXCEED_ADMITTED_RESERVE");
  return new(quote with {CommissionPerSideEur=ceiling},buy,sell,ceiling,scenario.ScenarioSha256,scenario.MetadataSha256);
 }
}
}
