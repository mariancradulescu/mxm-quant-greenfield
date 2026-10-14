using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;
namespace cAlgo {
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public class EconomicContractObserver:Robot {
 [Parameter("Native symbols")]public string NativeSymbols{get;set;}="";
 readonly Dictionary<string,Bars> bars=new();readonly Dictionary<string,Ticks> ticks=new();readonly Dictionary<string,MarketDepth> depth=new();bool restartBlocked;
 protected override void OnStart(){restartBlocked=Positions.Any(p=>p.Label!="MXM_ECONOMIC"||!p.StopLoss.HasValue);foreach(string name in NativeSymbols.Split(',',StringSplitOptions.TrimEntries|StringSplitOptions.RemoveEmptyEntries)){Symbol symbol=Symbols.GetSymbol(name);bars[name]=MarketData.GetBars(TimeFrame.Minute5,name);ticks[name]=MarketData.GetTicks(name);depth[name]=MarketData.GetMarketDepth(name);bars[name].BarClosed+=Closed;}Timer.Start(TimeSpan.FromSeconds(1));}
 void Closed(BarClosedEventArgs args){/* Event receipt is not immediate tradability: publication allowance and timer gate still apply. */}
 protected override void OnTimer(){if(restartBlocked||Positions.Any(p=>p.Label!="MXM_ECONOMIC"||!p.StopLoss.HasValue))return;long now=new DateTimeOffset(DateTime.SpecifyKind(Server.Time,DateTimeKind.Utc)).ToUnixTimeSeconds();if(now%300!=0)return;foreach(var item in bars){var symbol=Symbols.GetSymbol(item.Key);long[] opened=Enumerable.Range(0,item.Value.Count).Select(i=>new DateTimeOffset(DateTime.SpecifyKind(item.Value.OpenTimes[i],DateTimeKind.Utc)).ToUnixTimeSeconds()).ToArray();long? closed=EconomicContract.LatestClosed(now,opened);if(!closed.HasValue)continue;double units=symbol.NormalizeVolumeInUnits(symbol.VolumeInUnitsMin,RoundingMode.Up);double margin=Math.Max(symbol.GetEstimatedMargin(TradeType.Buy,units),symbol.GetEstimatedMargin(TradeType.Sell,units));_=symbol.Commission;_=symbol.CommissionType;_=symbol.MinCommission;_=symbol.MinCommissionType;_=symbol.MinCommissionAsset;_=symbol.PnLConversionFeeRate;_=symbol.VolumeInUnitsStep;bool reserve=Account.Equity-margin>=.6*Account.Equity;int owned=Positions.Count(p=>p.SymbolName==item.Key);/* Pure observer. No order or position mutation. Live callback and fill parity remain uncertified. */}}
 protected override void OnStop(){foreach(var b in bars.Values)b.BarClosed-=Closed;Timer.Stop();}
}
}
