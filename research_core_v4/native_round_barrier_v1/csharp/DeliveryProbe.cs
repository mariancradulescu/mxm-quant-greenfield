using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Internals;
namespace Mxm.Native {
// PREPARED ONLY. This class contains no order methods and is never deployed by research workflows.
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public class DeliveryProbe:Robot {
 [Parameter("Symbols",DefaultValue="EURUSD,US500,SpotCrude")] public string NativeSymbols {get;set;}
 private sealed class S {public string Name;public Ticks Ticks;public long Events,Reloads,Backward,SameMs,ChangedBid,ChangedAsk,Late;public double Bid=double.NaN,Ask=double.NaN;public long Last=long.MinValue;}
 private readonly List<S> states=new();private DateTime started;
 protected override void OnStart(){started=Server.TimeInUtc;
  foreach(var name in NativeSymbols.Split(',',StringSplitOptions.RemoveEmptyEntries)){if(states.Count>=3)throw new InvalidOperationException("THREE_SYMBOL_SCOPE");
   var symbol=Symbols.GetSymbol(name.Trim());var s=new S{Name=symbol.Name,Ticks=MarketData.GetTicks(symbol.Name)};
   _=MarketData.GetBars(TimeFrame.Minute5,symbol.Name).TickVolumes;_=symbol.Digits;_=symbol.VolumeInUnitsMin;_=symbol.VolumeInUnitsStep;
   _=symbol.Commission;_=symbol.MinCommission;_=symbol.GetEstimatedMargin(TradeType.Buy,symbol.VolumeInUnitsMin);_=symbol.GetEstimatedMargin(TradeType.Sell,symbol.VolumeInUnitsMin);
   _=symbol.MarketHours.IsOpened();_=symbol.SwapLong;_=symbol.SwapShort;_=Account.FreeMargin;_=Positions.Count;
   s.Ticks.Tick+=a=>{var q=a.Ticks.LastTick;long t=q.Time.Ticks;s.Events++;if(t<s.Last)s.Backward++;if(t==s.Last)s.SameMs++;
    if(!double.IsNaN(s.Bid)&&q.Bid!=s.Bid)s.ChangedBid++;if(!double.IsNaN(s.Ask)&&q.Ask!=s.Ask)s.ChangedAsk++;
    if((Server.TimeInUtc-q.Time).TotalSeconds>5)s.Late++;s.Last=t;s.Bid=q.Bid;s.Ask=q.Ask;};
   s.Ticks.Reloaded+=a=>{s.Reloads++;s.Last=long.MinValue;s.Bid=s.Ask=double.NaN;};states.Add(s);
  }Timer.Start(TimeSpan.FromSeconds(60));Print("MXM_NO_ORDER_NATIVE_DELIVERY_PROBE_STARTED;STATE_IN_MEMORY_ONLY");}
 protected override void OnTimer(){foreach(var s in states)Print("MXM_NATIVE_DELIVERY {0} events={1} reloads={2} backwards={3} sameMs={4} changedBid={5} changedAsk={6} lagGt5s={7}",s.Name,s.Events,s.Reloads,s.Backward,s.SameMs,s.ChangedBid,s.ChangedAsk,s.Late);
  if((Server.TimeInUtc-started).TotalMinutes>=120)Stop();}
 protected override void OnStop(){Print("MXM_NO_ORDER_NATIVE_DELIVERY_PROBE_STOPPED;NO_RAW_PRICES_OR_ACCOUNT_VALUES_LOGGED");}
}}
