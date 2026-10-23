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
var balanced=new MxmPortfolioAccountReplay(new[]{"EURUSD","GBPUSD"},Params()).Run(Series());
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

var path=Path.Combine("verification","csharp-multisymbol-single-account","artificial-replay.json");
Directory.CreateDirectory(Path.GetDirectoryName(path)!);
File.WriteAllText(path,JsonSerializer.Serialize(balanced,new JsonSerializerOptions{
 PropertyNamingPolicy=JsonNamingPolicy.SnakeCaseLower,WriteIndented=true}));
Console.WriteLine("MXM_AUTHENTIC_CSHARP_KERNEL_TWO_SYMBOL_EUR200_BIDASK_SINGLE_ACCOUNT_SYNTHETIC_PASS_NO_BROKER_FILL_NO_HARD21");
