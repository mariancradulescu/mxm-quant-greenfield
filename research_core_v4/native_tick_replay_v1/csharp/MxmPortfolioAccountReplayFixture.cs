using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Mxm.Replay;

static void Require(bool ok,string code) {
 if(!ok)throw new Exception("MXM_ACCOUNT_PORTFOLIO_FIXTURE_"+code);
}
static List<MxmAccountFeed> Series(int bars=8,bool executableQuotes=true) {
 var events=new List<MxmAccountFeed>();
 var start=new DateTime(2026,8,24,12,0,0,DateTimeKind.Utc);
 for(int i=0;i<bars;i++) {
  var t=start.AddMinutes(5*i);
  decimal eur=1.1000m+i*0.0002m;
  decimal gbp=1.2000m-i*0.0002m;
  events.Add(new MxmBarClose(t,"EURUSD",eur));
  events.Add(new MxmBarClose(t,"GBPUSD",gbp));
  if(executableQuotes){
   events.Add(new MxmQuote(t.AddSeconds(1),"EURUSD",eur-.0001m,eur+.0001m,
    1m,1000m,70m,.10m,0m,1m));
   events.Add(new MxmQuote(t.AddSeconds(1),"GBPUSD",gbp-.0001m,gbp+.0001m,
    1m,1000m,70m,.10m,0m,1m));
  }
 }
 return events;
}
static MxmReplayParameters Params(int positions=2,decimal marginFraction=.8m,decimal riskFraction=.03m)=>
 new(StrategyMode.TrendOnly,marginFraction,positions,0m,riskFraction,.2m);
Require(MxmEurUsdCapturedCosts.ProductDefaultStop12Distance(5,4)==.0012m,
 "CTRADER_PRODUCT_DEFAULT_12_PIPS_ON_EXPLICIT_EURUSD_GEOMETRY");
foreach(var bad in new (int?,int?)[]{(5,null),(null,4),(4,4),(5,5)}) {
 bool rejected=false;
 try {MxmEurUsdCapturedCosts.ProductDefaultStop12Distance(bad.Item1,bad.Item2);}
 catch(InvalidDataException){rejected=true;}
 Require(rejected,"NO_GUESSED_PIP_GEOMETRY");
}
var balanced=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(Series());
// Current-snapshot money semantics are a counterfactual, not actual fees.
var cost=new MxmEurUsdCapturedCosts(100000,100000000,100000,10000000,1,3000000000,1000000,"USD");
// Synthetic metadata parser regression only: matching public commitments do
// not decrypt or authenticate a market source. The protected bridge does that.
var sourceTerms=Path.GetTempFileName();
string Week35Terms(long run,string cipher)=>JsonSerializer.Serialize(new {
 schema="mxm.captured-native-symbol-terms.v1",symbol_id=1,
 historical_commission_proven=false,dated_historical_volume_rules_proven=false,
 source_crypto_authenticated_by_week_native_replay=true,source_run=run,
 source_code_sha="b54ee59548846ad8013b25965dbe4bcb19d4a978",
 source_private_sha256="2b37063a948d7b761a7f854e59649793ba1d5ff5e30a7e5255b03f4042cadb13",
 source_ciphertext_sha256=cipher,
 classification="AUTHENTICATED_WEEK_CAPTURE_SNAPSHOT_NOT_DATED_HISTORICAL_EXECUTION_TERMS",
 raw_optional_fields=new {minVolume=100000L,maxVolume=100000000L,stepVolume=100000L,
  commissionType=1,minCommissionType=1,minCommissionAsset="USD",
  preciseTradingCommissionRate=3000000000L,preciseMinCommission=1000000L}
});
try {
 const string w35Cipher="0d1badd1a944eeac7a67f1f7c87e05d26c1ea14ea016a0ea25fbb40ce7cb92ee";
 File.WriteAllText(sourceTerms,Week35Terms(39946364621,w35Cipher));
 Require(MxmEurUsdCapturedCosts.Load(sourceTerms,false,true,true).Allows(1000m),
  "W35_MATCHING_FIXED_SOURCE_PROFILE");
 foreach(var bad in new (long,string,bool)[]{(39917922508,w35Cipher,true),
  (39946364621,"not-original-cipher",true),(39946364621,w35Cipher,false)}) {
  File.WriteAllText(sourceTerms,Week35Terms(bad.Item1,bad.Item2));
  bool refused=false;
  try {MxmEurUsdCapturedCosts.Load(sourceTerms,false,true,bad.Item3);}
  catch(InvalidDataException){refused=true;}
  Require(refused,"W35_CROSS_WEEK_OR_CIPHER_SOURCE_REJECTED");
 }
} finally {File.Delete(sourceTerms);}
Require(cost.Allows(1000m) && !cost.Allows(500m) && !cost.Allows(1500m),"CENTS_VOLUME_LATTICE");
Require(cost.FeeEur(1000m,1.10m,1.10m,1.11m)==.03m,"USD_MILLION_COMMISSION_TO_EUR");
Require((cost with {CommissionType=2,PreciseRate=300000000}).FeeEur(1000m,1.10m,1.10m,1.11m)==.03m/1.10m,
 "USD_PER_LOT_USES_LOT_SIZE_NOT_NOTIONAL");
Require((cost with {CommissionType=3,PreciseRate=10000}).FeeEur(1000m,1.10m,1.10m,1.11m)==1m,
 "PERCENT_RATE_IS_NOT_FRACTION_OR_CURRENCY_RATE");
Require((cost with {MinimumAsset="EUR",PreciseMinimum=5000000}).FeeEur(1000m,1.10m,1.10m,1.11m)==.05m,
 "EUR_MINIMUM_FEE_NOT_RECONVERTED");
Require(MxmEurUsdCapturedCosts.ConvertSignedUsd(111m,1.10m,1.11m)==100m &&
 MxmEurUsdCapturedCosts.ConvertSignedUsd(-110m,1.10m,1.11m)==-100m,"SIGNED_EXECUTABLE_FX_SIDES");
var dynamicFeed=Series();
for(int i=0;i<dynamicFeed.Count;i++)if(dynamicFeed[i] is MxmQuote q && q.Symbol=="EURUSD")
 dynamicFeed[i]=q with {QuoteToEur=1m/q.Ask,QuoteLossToEur=1m/q.Bid,CapturedCosts=cost};
var dynamic=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(dynamicFeed);
var eurEntry=dynamic.Ledger.Single(x=>x.Symbol=="EURUSD" && x.Kind=="ENTRY");
Require(eurEntry.CommissionEur!=.10m && dynamic.AcceptedEntries==2,
 "CAPTURED_FEE_COMPONENT_ACTUALLY_USED_BY_SHARED_ACCOUNT");
Require(!dynamic.CostsBrokerVerified && !dynamic.Hard21Proven,"NO_CAPTURED_SNAPSHOT_PROMOTION");
var lossFeed=new List<MxmAccountFeed>(dynamicFeed);
var adverse=new MxmQuote(new DateTime(2026,8,24,12,40,1,DateTimeKind.Utc),"EURUSD",
 1.099m,1.0991m,1m/1.0991m,1000m,70m,.1m,0m,1m,1m/1.099m,cost);
lossFeed.Add(adverse);
var lossMark=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(lossFeed);
decimal usdLoss=(adverse.Bid-eurEntry.Price)*1000m;
Require(usdLoss<0 && Math.Abs(lossMark.MarkedEquityEur-
 (lossMark.FinalCashEur+usdLoss/adverse.Bid+.2m))<.0000001m,"LOSING_POSITION_USES_BID_FX_NOT_GAIN_SIDE");
Console.WriteLine("MXM_CAPTURED_COMMISSION_COMPONENT_AND_SIGNED_BIDASK_FX_SYNTHETIC_PASS_NOT_HISTORICAL_COSTS");
Require(balanced.InitialCapitalEur==200m,"SINGLE_START_CAPITAL");
Require(balanced.AcceptedEntries==2 && balanced.OpenPositions==2 && balanced.ExecutedExits==0,
 "TWO_INSTRUMENTS_ONE_BROKER_ACCOUNT");
Require(balanced.FinalCashEur==199.8m && balanced.MarkedEquityEur==200.2m,
 "SIGNED_BID_ASK_MARKED_PORTFOLIO_EQUITY_AND_TWO_FEES");
Require(balanced.UsedMarginEur==140m && balanced.FreeMarginEur==60.2m,
 "PORTFOLIO_COMBINED_MARGIN");
Require(balanced.Ledger.Count==2 &&
 balanced.Ledger.Any(x=>x.Symbol=="EURUSD" && x.Direction==1 && x.Price==1.1011m) &&
 balanced.Ledger.Any(x=>x.Symbol=="GBPUSD" && x.Direction==-1 && x.Price==1.1989m),
 "ACTUAL_SIDE_OF_SPREAD_EXECUTION");
Require(balanced.EntriesByIsoWeek.TryGetValue("2026-W35",out var week) && week==2 &&
 balanced.CompleteIsoUtcWeeks==0 && !balanced.Hard21Proven,
 "HARD21_NO_SHORT_WINDOW_PROMOTION");
Require(!balanced.BrokerFillsProven && !balanced.CostsBrokerVerified,
 "NO_BROKER_EXECUTION_OR_COST_CLAIM");

// Native first-tick callback jitter must NOT cold-reset a mathematically
// consecutive five-minute bar sequence. But no order may happen before the
// actual observed first tick, only at a later executable quote.
var jitterFeed=Series();
for(int i=0;i<8;i++){
 var original=(MxmBarClose)jitterFeed[i*4];
 var jitter=original.Utc.AddMilliseconds(70+(i%3)*113);
 jitterFeed[i*4]=new MxmBarClose(jitter,"EURUSD",original.Close,original.Utc);
 var second=(MxmBarClose)jitterFeed[i*4+1];
 jitterFeed[i*4+1]=new MxmBarClose(jitter,"GBPUSD",second.Close,second.Utc);
}
var jittered=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(jitterFeed);
Require(jittered.AcceptedEntries==2 && jittered.MarkedEquityEur==balanced.MarkedEquityEur,
 "FIRST_TICK_ARRIVAL_JITTER_DOES_NOT_RESET_CONTIGUOUS_BARS");
Require(jittered.Ledger.All(z=>z.Utc.Millisecond==0 && z.Utc.Second==1),
 "SAME_CALLBACK_PRICE_NOT_TREATED_AS_EXECUTABLE");
var futureBoundary=Series();
var first=(MxmBarClose)futureBoundary[0];
futureBoundary[0]=new MxmBarClose(first.Utc,first.Symbol,first.Close,first.Utc.AddMinutes(5));
bool impossibleBoundary=false;
try{new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(futureBoundary);}
catch(ArgumentException e){impossibleBoundary=e.Message.Contains("INVALID_BAR_BOUNDARY_OR_NONCAUSAL_ARRIVAL");}
Require(impossibleBoundary,"REJECT_FUTURE_BAR_BOUNDARY");
var limited=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params(positions:1)).Run(Series());
Require(limited.AcceptedEntries==1 && limited.OpenPositions==1 &&
 limited.Rejections.Contains("REJECT_ACCOUNT_POSITION_CAP"),"ONE_GLOBAL_POSITION_CAP");
// Same timestamp on two independent feeds does NOT prove real broker
// precedence. The capital-constrained allocation changes if the observation
// order changes; do not infer a qualified asset selection from this replay.
var swappedFeed=Series();
for(int i=0;i<8;i++) {
 (swappedFeed[4*i+2],swappedFeed[4*i+3])=(swappedFeed[4*i+3],swappedFeed[4*i+2]);
}
var swapped=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params(positions:1)).Run(swappedFeed);
Require(swapped.AcceptedEntries==1 && swapped.Ledger[0].Symbol=="GBPUSD" &&
 limited.Ledger[0].Symbol=="EURUSD","SAME_TIMESTAMP_ALLOCATION_ORDER_AMBIGUITY");
var tightMargin=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},
 Params(marginFraction:.30m)).Run(Series());
Require(tightMargin.AcceptedEntries==0 &&
 tightMargin.Rejections.Contains("REJECT_MARGIN_FRACTION"),"JOINT_EUR200_MARGIN");
var tightRisk=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},
 Params(riskFraction:.005m)).Run(Series());
Require(tightRisk.AcceptedEntries==0 &&
 tightRisk.Rejections.Contains("REJECT_AGGREGATE_STOP_RISK_EXCESS"),"JOINT_STOP_RISK");
var noFutureQuotes=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(Series(8,false));
Require(noFutureQuotes.AcceptedEntries==0 && noFutureQuotes.MarkedEquityEur==200m,
 "BAR_CLOSE_CANNOT_FILL_USING_BAR_PRICE");
var noFillAtClose=Series(6,false);
var finalBar=(MxmBarClose)noFillAtClose[noFillAtClose.Count-2];
MxmQuote After(DateTime time)=>new(time,"EURUSD",1.1009m,1.1011m,1m,1000m,70m,.1m,0m,1m);
noFillAtClose.Add(After(finalBar.Utc));
Require(new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(noFillAtClose)
 .AcceptedEntries==0,"NO_TICK_AT_SIGNAL_TIMESTAMP_FILL");
noFillAtClose.Add(After(finalBar.Utc.AddSeconds(1)));
Require(new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(noFillAtClose)
 .AcceptedEntries==1,"STRICTLY_LATER_SYMBOL_QUOTE_FILLS");
var expiredFeed=Series(6,false);
// First quote after feed silence can arrive BEFORE BarClosed at next boundary.
// An expired direction must not execute merely because no new bar was delivered.
expiredFeed.Add(After(finalBar.Utc.AddMinutes(5)));
Require(new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(expiredFeed)
 .AcceptedEntries==0,"NO_STALE_INTENT_ON_SESSION_REOPEN_QUOTE");
var invalid=Series();invalid[3]=new MxmQuote(
 ((MxmQuote)invalid[3]).Utc,"GBPUSD",1.20m,1.19m,1m,1000m,70m,.1m,0m,1m);
bool rejectedInvalid=false;
try {new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(invalid);}
catch(ArgumentException x){rejectedInvalid=x.Message.Contains("INVALID_EXECUTION_QUOTE");}
Require(rejectedInvalid,"CROSSED_OR_UNVERIFIED_QUOTES_FAIL_CLOSED");
var unsorted=Series();(unsorted[0],unsorted[4])=(unsorted[4],unsorted[0]);
bool rejectedTime=false;
try {new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(unsorted);}
catch(ArgumentException x){rejectedTime=x.Message.Contains("OUT_OF_ORDER_GLOBAL_FEED");}
Require(rejectedTime,"NO_LOOKAHEAD_GLOBAL_ORDER");

// Optional lifecycle extension: no historical replay is run by these fixtures.
var stops=Series(6);
for(int i=0;i<stops.Count;i++)if(stops[i] is MxmQuote q)
 stops[i]=q with {StopDistanceQuote=.0012m,SlipPerSideQuote=.00002m};
var stopTime=new DateTime(2026,8,24,12,30,1,DateTimeKind.Utc);
// Both stops gap beyond the requested price; first observed side plus adverse
// slippage is used. There is no fresh intent and no synthetic boundary fill.
stops.Add(new MxmQuote(stopTime,"EURUSD",1.0980m,1.0982m,1m,1000m,70m,.1m,.00002m,1m,StopDistanceQuote:.0012m));
stops.Add(new MxmQuote(stopTime,"GBPUSD",1.2020m,1.2022m,1m,1000m,70m,.1m,.00002m,1m,StopDistanceQuote:.0012m));
var stopped=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params(riskFraction:.1m)).Run(stops);
Require(stopped.AcceptedEntries==2 && stopped.ExecutedExits==2 && stopped.OpenPositions==0,
 "STOPS_ON_QUOTES_WITHOUT_BAR_INTENTS_BOTH_DIRECTIONS");
Require(stopped.Ledger.Where(x=>x.Kind=="EXIT").All(x=>x.Reason=="OBSERVED_QUOTE_STOP"),"STOP_EXIT_REASON");
Require(stopped.Ledger.Single(x=>x.Kind=="EXIT" && x.Direction==1).Price==1.09798m &&
 stopped.Ledger.Single(x=>x.Kind=="EXIT" && x.Direction==-1).Price==1.20222m,"GAP_NOT_FILLED_AT_REQUESTED_STOP");
Require(stopped.FinalCashEur==193.12m && stopped.MarkedEquityEur==193.12m &&
 stopped.UsedMarginEur==0 && stopped.FreeMarginEur==193.12m,"STOP_FEES_PNL_MARGIN_RELEASE");
// A newly published valid direction must not reopen after the stop on the
// very quote that would otherwise consume it, or on the following quote.
var simultaneous=Series(7);
for(int i=0;i<simultaneous.Count;i++)if(simultaneous[i] is MxmQuote q) {
 if(q.Utc>=stopTime)simultaneous[i]=q with {
  Bid=q.Symbol=="EURUSD"?1.0980m:1.2020m,
  Ask=q.Symbol=="EURUSD"?1.0982m:1.2022m,StopDistanceQuote=.0012m};
 else simultaneous[i]=q with {StopDistanceQuote=.0012m};
}
simultaneous.Add(new MxmQuote(stopTime.AddSeconds(1),"EURUSD",1.0980m,1.0982m,1m,1000m,70m,.1m,0m,1m,StopDistanceQuote:.0012m));
var noReentry=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params(riskFraction:.1m)).Run(simultaneous);
Require(noReentry.AcceptedEntries==2 && noReentry.ExecutedExits==2 && noReentry.OpenPositions==0,
 "STOP_PRIORITY_CLEARS_VALID_INTENT_AND_FORBIDS_NEXT_QUOTE_REENTRY");
// Reverse callback ordering: quote stop BEFORE BarClosed at the same UTC
// boundary. Neither that publication nor another tick may resurrect the intent.
var stopBeforeBar=Series(6);
for(int i=0;i<stopBeforeBar.Count;i++)if(stopBeforeBar[i] is MxmQuote q)
 stopBeforeBar[i]=q with {StopDistanceQuote=.0012m};
var reopenBoundary=stopTime.AddSeconds(-1);
MxmQuote StopQuote(DateTime t,string symbol)=>new(t,symbol,
 symbol=="EURUSD"?1.0980m:1.2020m,symbol=="EURUSD"?1.0982m:1.2022m,
 1m,1000m,70m,.1m,0m,1m,StopDistanceQuote:.0012m);
foreach(var symbol in new[]{"EURUSD","GBPUSD"})stopBeforeBar.Add(StopQuote(reopenBoundary,symbol));
stopBeforeBar.Add(new MxmBarClose(reopenBoundary,"EURUSD",1.1012m));
stopBeforeBar.Add(new MxmBarClose(reopenBoundary,"GBPUSD",1.1988m));
foreach(var symbol in new[]{"EURUSD","GBPUSD"})stopBeforeBar.Add(StopQuote(reopenBoundary.AddSeconds(1),symbol));
var reverseOrder=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params(riskFraction:.1m)).Run(stopBeforeBar);
Require(reverseOrder.AcceptedEntries==2 && reverseOrder.ExecutedExits==2 &&
 reverseOrder.OpenPositions==0,"STOP_BEFORE_BAR_CANNOT_REPUBLISH_SAME_BOUNDARY");
// Revocation is per symbol and finite: the next complete bar may publish.
var nextBoundary=reopenBoundary.AddMinutes(5);
stopBeforeBar.Add(new MxmBarClose(nextBoundary,"EURUSD",1.1014m));
stopBeforeBar.Add(new MxmBarClose(nextBoundary,"GBPUSD",1.1986m));
foreach(var symbol in new[]{"EURUSD","GBPUSD"})stopBeforeBar.Add(StopQuote(nextBoundary.AddSeconds(1),symbol));
var resumed=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params(riskFraction:.1m)).Run(stopBeforeBar);
Require(resumed.AcceptedEntries==4 && resumed.ExecutedExits==2 && resumed.OpenPositions==2 &&
 resumed.Ledger.Where(x=>x.Kind=="ENTRY").Skip(2).All(x=>x.Utc==nextBoundary.AddSeconds(1)),
 "STOP_REVOCATION_EXPIRES_ONLY_ON_GENUINELY_NEW_BOUNDARY");
Console.WriteLine("MXM_STOP_CALLBACK_ORDER_BOTH_DIRECTIONS_SYNTHETIC_PASS_NO_SAME_BAR_RESURRECTION");
var touched=Series(6);
for(int i=0;i<touched.Count;i++)if(touched[i] is MxmQuote q)
 touched[i]=q with {StopDistanceQuote=.0001m};
Require(new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(touched)
 .Rejections.Contains("REJECT_STOP_ALREADY_TOUCHED_AT_ENTRY"),"SPREAD_TOUCHES_NEW_STOP");
var horizon=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},
 Params() with {ExitPolicy=ExitMode.Horizon12}).Run(Series(20));
Require(horizon.ExecutedExits==2 && horizon.AcceptedEntries==4 &&
 horizon.Ledger.Where(x=>x.Kind=="EXIT").All(x=>x.Reason=="HORIZON12" && x.Utc.Minute==30),
 "HORIZON_USES_ENTRY_TIME_NOT_ROUNDED_ENTRY_BAR");
Require(horizon.Ledger.Where(x=>x.Kind=="EXIT").All(x=>
 !horizon.Ledger.Any(y=>y.Kind=="ENTRY" && y.Utc==x.Utc && y.Symbol==x.Symbol)),
 "NO_SAME_INTENT_REENTRY_AFTER_HORIZON");
var neutralFeed=Series(14);
for(int i=0;i<neutralFeed.Count;i++)if(neutralFeed[i] is MxmBarClose b && i/4>=6)
 neutralFeed[i]=b with {Close=b.Symbol=="EURUSD"?1.1010m:1.1990m};
var neutral=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},
 Params() with {ExitPolicy=ExitMode.NeutralFlat}).Run(neutralFeed);
Require(neutral.ExecutedExits==2 && neutral.AcceptedEntries==2 && neutral.OpenPositions==0 &&
 neutral.Ledger.Where(x=>x.Kind=="EXIT").All(x=>x.Reason=="NEUTRAL_FLAT"),"NEUTRAL_FLAT_POLICY");
Require(MxmExitPolicy.Reason(ExitMode.NeutralFlat,0,1,false,6,stopTime,stopTime.AddHours(-2),5)==null,
 "GAP_NOT_REINTERPRETED_AS_NEUTRAL");
var lifecyclePath=Path.Combine("verification","csharp-multisymbol-single-account","lifecycle-replay.json");
Directory.CreateDirectory(Path.GetDirectoryName(lifecyclePath)!);
File.WriteAllText(lifecyclePath,JsonSerializer.Serialize(stopped,new JsonSerializerOptions{
 PropertyNamingPolicy=JsonNamingPolicy.SnakeCaseLower,WriteIndented=true}));
Console.WriteLine("MXM_SHARED_EXIT_POLICY_AND_OBSERVED_GAP_STOP_SYNTHETIC_PASS_NOT_BROKER_STOP_ROUTING");

var path=Path.Combine("verification","csharp-multisymbol-single-account","artificial-replay.json");
Directory.CreateDirectory(Path.GetDirectoryName(path)!);
File.WriteAllText(path,JsonSerializer.Serialize(balanced,new JsonSerializerOptions{
 PropertyNamingPolicy=JsonNamingPolicy.SnakeCaseLower,WriteIndented=true}));
Console.WriteLine("MXM_AUTHENTIC_CSHARP_KERNEL_TWO_SYMBOL_EUR200_BIDASK_SINGLE_ACCOUNT_SYNTHETIC_PASS_NO_BROKER_FILL_NO_HARD21");
