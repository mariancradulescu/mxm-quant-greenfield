using System;
using System.Collections.Generic;
using System.Linq;
namespace Mxm.Replay {
/// <summary>New 2026-11-01 experimental M5 volume-flow predictor.
/// One completed OHLCV bar per input; never issues orders, sets volume or
/// overrides an account/risk/unknown-result fence. Not promoted to trading.
/// Parameters were fixed before opening the authentic R3 DEVELOPMENT outcome.
/// </summary>
public sealed class MxmVolumeFlowKernel {
 public const int Lookback=12, Half=6;
 public const decimal RecentFlowThresholdBps=8m, FlowAccelerationBps=6m,
  PriorAbsMultiplier=1.5m, TrendThresholdBps=3m;
 public const long MaxVolume=1000000000L;
 readonly Queue<(decimal Open,decimal Close,long Volume)> bars=new();
 DateTime? lastOpen;
 public int CompletedBars {get;private set;}
 public int LastSignal {get;private set;}
 public void Reset(){bars.Clear();lastOpen=null;CompletedBars=0;LastSignal=0;}
 public int OnCompletedBar(DateTime barOpenUtc, decimal open, decimal high,
                           decimal low, decimal close, long tickVolume) {
  if(barOpenUtc.Kind!=DateTimeKind.Utc || barOpenUtc==default ||
     barOpenUtc.Ticks%TimeSpan.FromMinutes(5).Ticks!=0 ||
     open<=0 || low<=0 || high<=0 || close<=0 ||
     low>Math.Min(open,close) || high<Math.Max(open,close) ||
     low>high || tickVolume<0 || tickVolume>MaxVolume)
   throw new ArgumentException("FLOW_BAR_INVALID_OR_UNVERIFIED");
  if(lastOpen.HasValue){
   if(barOpenUtc<=lastOpen.Value)throw new ArgumentException("FLOW_BAR_DUPLICATE_OR_REORDERED");
   if(barOpenUtc-lastOpen.Value!=TimeSpan.FromMinutes(5))Reset();
  }
  lastOpen=barOpenUtc;
  checked{CompletedBars++;}
  bars.Enqueue((open,close,tickVolume));
  if(bars.Count>Lookback)bars.Dequeue();
  LastSignal=0;
  if(bars.Count<Lookback)return 0;
  var a=bars.ToArray();
  decimal Flow(int first,int end){
   decimal acc=0,vol=0;
   for(int i=first;i<end;i++){
    decimal v=a[i].Volume;
    acc+=10000m*(a[i].Close/a[i].Open-1m)*v;
    vol+=v;
   }
   return vol>0m?acc/vol:0m;
  }
  decimal earlier=Flow(0,Half),recent=Flow(Half,Lookback);
  decimal trend=10000m*(a[Lookback-1].Close/a[Half].Open-1m);
  if(recent>=RecentFlowThresholdBps && recent-earlier>=FlowAccelerationBps &&
     Math.Abs(recent)>=PriorAbsMultiplier*Math.Abs(earlier) &&
     trend>=TrendThresholdBps)LastSignal=1;
  else if(recent<=-RecentFlowThresholdBps && earlier-recent>=FlowAccelerationBps &&
     Math.Abs(recent)>=PriorAbsMultiplier*Math.Abs(earlier) &&
     trend<=-TrendThresholdBps)LastSignal=-1;
  return LastSignal;
 }
}
}