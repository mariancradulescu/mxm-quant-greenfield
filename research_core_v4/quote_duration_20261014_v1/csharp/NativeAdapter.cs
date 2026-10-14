using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Internals;
using Mxm.Duration;
namespace cAlgo {
// Compile-only native observability adapter. No order methods, logging or deployment.
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public class DurationObservability : Robot {
 Ticks ticks;readonly List<long[]> bids=new List<long[]>(),asks=new List<long[]>();bool invalid;
 protected override void OnStart(){ticks=MarketData.GetTicks(SymbolName);ticks.Tick+=Updated;Timer.Start(TimeSpan.FromSeconds(1));}
 void Updated(TicksTickEventArgs e){
  var tick=ticks.LastTick;double b=tick.Bid*100000.,a=tick.Ask*100000.;
  if(Math.Abs(b-Math.Round(b))>1e-6||Math.Abs(a-Math.Round(a))>1e-6){invalid=true;return;}
  long t=new DateTimeOffset(DateTime.SpecifyKind(tick.Time,DateTimeKind.Utc)).ToUnixTimeMilliseconds();
  bids.Add(new[]{t,(long)Math.Round(b)});asks.Add(new[]{t,(long)Math.Round(a)});
  bids.RemoveAll(x=>x[0]<t-120000);asks.RemoveAll(x=>x[0]<t-120000);
 }
 protected override void OnTimer(){
  if(invalid)return;long now=new DateTimeOffset(DateTime.SpecifyKind(Server.Time,DateTimeKind.Utc)).ToUnixTimeSeconds();
  // Only closed seconds <= now-1. Symbol/Bars/account fields are native planning inputs.
  var state=TimingKernel.Compute(bids.ToArray(),asks.ToArray(),now,false);
  double units=Symbol.NormalizeVolumeInUnits(Symbol.VolumeInUnitsMin,RoundingMode.Up);
  double margin=Math.Max(Symbol.GetEstimatedMargin(TradeType.Buy,units),Symbol.GetEstimatedMargin(TradeType.Sell,units));
  var bars=MarketData.GetBars(TimeFrame.Minute5,SymbolName);
  bool budget=margin<=.4*Account.Equity&&Account.Equity-margin>=.6*Account.Equity;
  // Deliberately no trading entrypoint; native risk/cost and feed delivery certification remain separate.
 }
 protected override void OnStop(){ticks.Tick-=Updated;Timer.Stop();}
}
}
