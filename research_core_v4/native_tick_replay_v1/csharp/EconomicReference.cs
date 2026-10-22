using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Mxm.Replay;

record Quote(long T,string Side,long Raw);
sealed class Position {
 public int Direction; public long OpenT;public decimal OpenPrice;
}
sealed class Replay {
 const long BarMs=300000;
 readonly MxmDecisionKernel kernel=new();
 readonly bool synthetic,scenario;
 bool Simulated=>synthetic||scenario;
 decimal Fx=>scenario?1m/1.10m:1m;
 decimal Slippage=>scenario?0.00002m:0.00001m;
 decimal PriceUnits=>1000m;
 readonly List<object> trades=new(),equityPath=new(),signals=new();
 long lastT=-1,bidAt=-1,askAt=-1,barStart=-1;
 decimal bid,ask,closeOfBar,realized=200m,peak=200m,maxDrawdown=0m,totalCosts=0m;
 int pendingSignal,ambiguousGroups,gapBars,invalidSnapshots,entries,exits;
 Position? pos;
 public Replay(bool fixture,bool modeledScenario=false){synthetic=fixture;scenario=modeledScenario;}
 static decimal Round(decimal x)=>Math.Round(x,6,MidpointRounding.ToEven);
 decimal Equity(decimal b,decimal a) =>
  realized+(pos is null?0m:pos.Direction*PriceUnits*((pos.Direction==1?b:a)-pos.OpenPrice)*Fx);
 void Mark(long t){
  var current=Equity(bid,ask);if(current>peak)peak=current;
  if(peak-current>maxDrawdown)maxDrawdown=peak-current;
  equityPath.Add(new{timestamp_ms=t,equity_eur=Round(current),balance_eur=Round(realized),margin_eur=pos is null?0m:50m,position_direction=pos?.Direction??0});
  if(pos is not null && current<=25m)throw new InvalidDataException("SYNTHETIC_STOP_OUT_HALT");
 }
 void Open(long t,int direction) {
  if(realized<50m || pos is not null)throw new InvalidDataException("MARGIN_OR_POSITION");
  decimal price=direction>0?ask+Slippage:bid-Slippage;
  pos=new Position{Direction=direction,OpenT=t,OpenPrice=price};
  realized-=0.10m;totalCosts+=0.10m+PriceUnits*Slippage*Fx;entries++;
  trades.Add(new{kind="ENTRY",timestamp_ms=t,direction,price=Round(price),units=1000,
   charged_commission_eur=0.10m,slippage_eur=0.01m,margin_eur=50m,balance_eur=Round(realized)});
 }
 void Close(long t) {
  if(pos is null)throw new InvalidDataException("NO_POSITION");
  decimal exit=pos.Direction>0?bid-Slippage:ask+Slippage;
  decimal pnl=pos.Direction*PriceUnits*(exit-pos.OpenPrice)*Fx;
  realized+=pnl-0.10m;totalCosts+=0.10m+PriceUnits*Slippage*Fx;exits++;
  trades.Add(new{kind="EXIT",timestamp_ms=t,direction=pos.Direction,price=Round(exit),units=1000,
   gross_price_pnl_eur=Round(pnl),charged_commission_eur=0.10m,slippage_eur=0.01m,
   balance_eur=Round(realized),entry_timestamp_ms=pos.OpenT});
  pos=null;
 }
 Dictionary<string,int> WeekCounts(IReadOnlyList<Quote> ticks){
  var counts=new Dictionary<string,int>();
  if(ticks.Count==0)return counts;
  var start=DateTimeOffset.FromUnixTimeMilliseconds(ticks[0].T).UtcDateTime;
  var end=DateTimeOffset.FromUnixTimeMilliseconds(ticks[ticks.Count-1].T).UtcDateTime;
  var monday=start.Date.AddDays(-(((int)start.DayOfWeek+6)%7));
  while(monday<=end){
   var k=System.Globalization.ISOWeek.GetYear(monday)+"-W"+System.Globalization.ISOWeek.GetWeekOfYear(monday).ToString("D2");
   counts[k]=0;monday=monday.AddDays(7);
  }
  foreach(var row in trades){
   // Ledger rows are anonymous event records; no economic counting from signals.
   var item=JsonSerializer.SerializeToElement(row);
   if(item.GetProperty("kind").GetString()!="ENTRY")continue;
   var t=DateTimeOffset.FromUnixTimeMilliseconds(item.GetProperty("timestamp_ms").GetInt64()).UtcDateTime;
   var k=System.Globalization.ISOWeek.GetYear(t)+"-W"+System.Globalization.ISOWeek.GetWeekOfYear(t).ToString("D2");
   counts[k]++;
  }
  return counts;
 }
 public object Run(IReadOnlyList<Quote> ticks) {
  if(ticks.Count==0)throw new InvalidDataException("EMPTY_TICK_INPUT");
  for(int i=0;i<ticks.Count;i++){
   Quote x=ticks[i];
   if(x.T<0||x.Raw<=0||!(x.Side=="bid"||x.Side=="ask"))throw new InvalidDataException("INVALID_QUOTE");
   if(i>0 && x.T<ticks[i-1].T)throw new InvalidDataException("NONMONOTONIC_EVENTS");
  }
  foreach(var group in ticks.GroupBy(x=>x.T)){
   var g=group.ToArray();long t=g[0].T;
   if(g.Where(x=>x.Side=="bid").Select(x=>x.Raw).Distinct().Count()>1 ||
      g.Where(x=>x.Side=="ask").Select(x=>x.Raw).Distinct().Count()>1){
    ambiguousGroups++;continue; // Different same-ms revisions have no trusted cross-side order.
   }
   foreach(var x in g) {
    if(x.Side=="bid"){bid=x.Raw/100000m;bidAt=t;}
    else {ask=x.Raw/100000m;askAt=t;}
   }
   if(bidAt<0||askAt<0||bid<=0m||ask<=bid){invalidSnapshots++;continue;}
   // These are last-observed sides, not a historical arrival-time certification.
   if(t-bidAt>300000||t-askAt>300000){invalidSnapshots++;continue;}
   long bar=t/BarMs*BarMs;
   if(barStart>=0 && bar!=barStart) {
    if(bar==barStart+BarMs){
     pendingSignal=kernel.OnCompletedBar(closeOfBar);
     signals.Add(new{decision_ms=bar,completed_bar_end_ms=bar,completed_close=Round(closeOfBar),direction=pendingSignal});
    }else{
     gapBars+=(int)Math.Min(1000000,(bar-barStart)/BarMs-1);
     kernel.Reset();pendingSignal=0;
    }
   }
   if(bar!=barStart){barStart=bar;closeOfBar=(bid+ask)/2m;}
   else closeOfBar=(bid+ask)/2m;
   if(Simulated){
    if(pendingSignal!=0){
     if(pos is not null && pos.Direction!=pendingSignal)Close(t);
     if(pos is null)Open(t,pendingSignal);
     pendingSignal=0;
    }
    Mark(t);
   }
   lastT=t;
  }
  if(Simulated && pos is not null){Close(lastT);Mark(lastT);}
  if(synthetic && (entries<1||entries!=exits||realized<=0||totalCosts<=0))
   throw new InvalidDataException("REFERENCE_FIXTURE_DID_NOT_EXERCISE_ACCOUNT");
  return new {
   schema="mxm.csharp.reference-replay.v1",
   classification=synthetic?(scenario?"ARTIFICIAL_SCENARIO_COST_FX_TEST_ONLY":"SYNTHETIC_MATHEMATICAL_ONLY"):scenario?"OBSERVED_PEPPERSTONE_QUOTES_ASSUMPTION_SCENARIO_UNCERTIFIED":"AUTHENTIC_CHRONOLOGY_NONOUTCOME_ONLY",
   pepperstone_historical_fills_proven=false,
   cTrader_native_backtest=false,
   authenticated_market_corpus=false, // Only the protected custody workflow can certify market source bytes.
   broker_historical_costs_verified=false,
   timing_assumption="ATOMIC_PER_MS_WITH_UNKNOWN_INTRA_MS_ORDER;TIMESTAMPS_ARE_NOT_HISTORICAL_ARRIVAL",
   account_convention=synthetic&&!scenario?"FIXTURE_EURUSD_QUOTE_TO_EUR_AT_1;MIN_1000_UNITS;MARGIN_EUR50;PER_SIDE_FEE_EUR0.10;SLIPPAGE_0.00001;NOT_PEPPERSTONE_TERMS":scenario?"UNVERIFIED_SCENARIO_EURUSD_USD_PER_EUR_1.10;1000_UNITS;MARGIN_EUR50;FEE_EUR0.10_PER_SIDE;SLIPPAGE_0.00002;NO_SWAP;NO_STOP_OUT_PARITY":"NONE_NO_ECONOMIC_FILLS",
   no_historical_fee_margin_swap_fx_authority=true,
   price_path_timestamps_are_not_historical_arrival_times=true,
   historical_execution_fills_proven=false,
   economic_identity_opened=false,
   terminal_position_exit_is_assumed_not_historical_fill=Simulated,
   initial_equity_eur=200m,final_equity_eur=Simulated?Round(realized):(decimal?)null,
   economic_entries=entries,economic_exits=exits,charged_cost_eur=Round(totalCosts),
   maximum_absolute_drawdown_eur=Round(maxDrawdown),hard21=Simulated && WeekCounts(ticks).Values.All(n=>n>=21),entries_per_iso_week=Simulated?WeekCounts(ticks):new Dictionary<string,int>(),
   raw_events=ticks.Count,bar_decisions=signals.Count,
   same_ms_conflict_groups=ambiguousGroups,gap_bars=gapBars,invalid_quote_snapshots=invalidSnapshots,
   ledger=trades,equity=equityPath,causal_signals=signals
  };
 }
}
static class Program {
 static List<Quote> Fixture(){
  // Known mathematical *fixture*, not a Pepperstone quote, fill or hypothesis.
  var list=new List<Quote>();long begin=1736164800000L; // January 2025 UTC
  for(int i=0;i<44;i++){
   decimal drift=i<15?i*0.00016m:i<30?(30-i)*0.00016m:(i-30)*0.00016m;
   for(int j=0;j<2;j++){
    long t=begin+i*300000L+60000+j*120000;
    decimal mid=1.10000m+drift+j*0.00001m;
    list.Add(new Quote(t,"bid",(long)((mid-0.00004m)*100000m)));
    list.Add(new Quote(t,"ask",(long)((mid+0.00004m)*100000m)));
   }
  }
  return list;
 }
 static List<Quote> Read(string file){
  var rows=new List<Quote>();
  foreach(string line in File.ReadLines(file)){
   if(string.IsNullOrWhiteSpace(line))continue;
   using var json=JsonDocument.Parse(line);
   var r=json.RootElement;
   rows.Add(new Quote(r.GetProperty("t").GetInt64(),r.GetProperty("side").GetString()??"",r.GetProperty("raw").GetInt64()));
  }
  return rows;
 }
 public static int Main(string[] args){
  try {
   if(args.Length!=3 || !(args[0]=="--fixture"||args[0]=="--model-fixture"||args[0]=="--authentic-nonoutcome"||args[0]=="--authentic-scenario"))
    throw new ArgumentException("USAGE: --fixture unused OUT | --model-fixture unused OUT | --authentic-nonoutcome INPUT.ndjson OUT | --authentic-scenario INPUT.ndjson OUT");
   bool fixture=args[0]=="--fixture"||args[0]=="--model-fixture";
   if(!fixture && !File.Exists(args[1]))throw new FileNotFoundException("AUTHENTIC_INPUT_REQUIRED");
   var report=new Replay(fixture,args[0]=="--model-fixture"||args[0]=="--authentic-scenario").Run(fixture?Fixture():Read(args[1]));
   Directory.CreateDirectory(args[2]);
   var options=new JsonSerializerOptions{WriteIndented=true};
   File.WriteAllText(Path.Combine(args[2],"reference-report.json"),JsonSerializer.Serialize(report,options));
   Console.WriteLine(JsonSerializer.Serialize(new{status="REFERENCE_CSHARP_EXECUTED",economic_fixture_only=fixture,modeled_assumptions=args[0]=="--model-fixture"||args[0]=="--authentic-scenario",report=Path.Combine(args[2],"reference-report.json")}));
   return 0;
  } catch(Exception e) {Console.Error.WriteLine("MXM_REFERENCE_FAILED:"+e.GetType().Name+":"+e.Message);return 1;}
 }
}
