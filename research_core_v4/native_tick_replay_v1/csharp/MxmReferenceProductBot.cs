using System;
using cAlgo.API;
using Mxm.Replay;

namespace cAlgo.Robots {
/// <summary>Source-compatible cloud-facing adapter; never activated by the CI workflow.
/// OnBarClosed uses the exact same C# decision state as the machine-side reference.</summary>
[Robot(TimeZone=TimeZones.UTC,AccessRights=AccessRights.None)]
public sealed class MxmReferenceProductBot : Robot {
 const string Label="MXM_CSHARP_REFERENCE_V1";
 readonly MxmDecisionKernel kernel=new();
 [Parameter("Enable DEMO Trading",DefaultValue=false)]
 public bool EnableDemoTrading {get;set;}
 [Parameter("Stop Loss Pips",DefaultValue=12,MinValue=1)]
 public int StopLossPips {get;set;}
 [Parameter("Requested Units",DefaultValue=1000,MinValue=1)]
 public double RequestedUnits {get;set;}
 protected override void OnStart() {
  kernel.Reset();
  // Reference kernel consumes M5 only. No silent timeframe substitution.
  if(TimeFrame!=cAlgo.API.TimeFrame.Minute5){Print("MXM_REQUIRES_M5");Stop();return;}
  // The current running bar must not be a warmup feature.
  for(int i=Math.Max(0,Bars.Count-7);i<Bars.Count-1;i++)
   kernel.OnCompletedBar((decimal)Bars.ClosePrices[i]);
  // The position book is authoritative on restart. No serialized direction or replayed orders.
  if(Positions.FindAll(Label,SymbolName).Length>1)Print("MXM_DUPLICATE_OWNED_POSITIONS_SAFE_HOLD");
 }
 protected override void OnBar() {
  // OnBar has the just-opened live bar at Last(0), so Last(1) is unambiguously closed.
  if(Bars.Count<3)return;
  if((Bars.OpenTimes.Last(1)-Bars.OpenTimes.Last(2)).TotalMinutes!=5)kernel.Reset();
  int desired=kernel.OnCompletedBar((decimal)Bars.ClosePrices.Last(1));
  // Backtesting is simulation; realtime LIVE trading is never authorized.
  bool simulation=IsBacktesting;
  if(!(simulation || (EnableDemoTrading && !Account.IsLive)) || desired==0 || !Symbol.MarketHours.IsOpened())return;
  var owned=Positions.FindAll(Label,SymbolName);
  if(owned.Length>1){Print("MXM_MULTIPLE_POSITIONS_SAFE_HOLD");return;}
  TradeType direction=desired>0?TradeType.Buy:TradeType.Sell;
  if(owned.Length==1){
   if(owned[0].TradeType==direction)return;
   var result=ClosePosition(owned[0]);
   if(!result.IsSuccessful){Print("MXM_CLOSE_FAILED_SAFE_HOLD");return;}
  }
  // Inspect actual broker minimum/step/margin; do not assume EUR200 volume feasibility.
  if(Account.Equity<=0||Account.FreeMargin<=0||Account.Asset.Name!="EUR")return;
  double units=Symbol.NormalizeVolumeInUnits(Math.Max(RequestedUnits,Symbol.VolumeInUnitsMin),RoundingMode.Up);
  if(units<=0 || units>Symbol.VolumeInUnitsMax)return;
  double margin=Symbol.GetEstimatedMargin(direction,units);
  if(double.IsNaN(margin)||margin<=0||margin>Account.FreeMargin*0.4)return;
  ExecuteMarketOrder(direction,SymbolName,units,Label,StopLossPips,null);
 }
}
}