using cAlgo.API;
using cAlgo.API.Internals;
namespace cAlgo {
// Compile-only observer. No order API, logging, deployment or external runtime.
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public class NativeFrontierObservability:Robot {
 Ticks ticks;Bars bars;readonly List<long[]> bid=new(),ask=new();bool invalid;
 protected override void OnStart(){ticks=MarketData.GetTicks(SymbolName);bars=MarketData.GetBars(TimeFrame.Minute5,SymbolName);ticks.Tick+=Updated;Timer.Start(TimeSpan.FromSeconds(1));}
 void Updated(TicksTickEventArgs e){var z=ticks.LastTick;long t=new DateTimeOffset(DateTime.SpecifyKind(z.Time,DateTimeKind.Utc)).ToUnixTimeMilliseconds();double b=z.Bid*100000,a=z.Ask*100000;if(Math.Abs(b-Math.Round(b))>1e-6||Math.Abs(a-Math.Round(a))>1e-6){invalid=true;return;}bid.Add(new[]{t,(long)Math.Round(b)});ask.Add(new[]{t,(long)Math.Round(a)});bid.RemoveAll(x=>x[0]<t-1800000);ask.RemoveAll(x=>x[0]<t-1800000);}
 protected override void OnTimer(){if(invalid)return;long now=new DateTimeOffset(DateTime.SpecifyKind(Server.Time,DateTimeKind.Utc)).ToUnixTimeMilliseconds();var state=Kernel.State(new Input{bid=bid.ToArray(),ask=ask.ToArray(),t=now,ttl=300000});double u=Symbol.NormalizeVolumeInUnits(Symbol.VolumeInUnitsMin,RoundingMode.Up);double margin=Math.Max(Symbol.GetEstimatedMargin(TradeType.Buy,u),Symbol.GetEstimatedMargin(TradeType.Sell,u));bool reserve=margin<=.4*Account.Equity&&Account.Equity-margin>=.6*Account.Equity;int known=Positions.Count;bool open=Symbol.MarketHours.IsOpened();/* Native joint tick timestamp is not certified equivalent to Open API side publication timestamp. Missing seed/reload abstains. Observability only, never trading. */}
 protected override void OnStop(){ticks.Tick-=Updated;Timer.Stop();}
}
}
